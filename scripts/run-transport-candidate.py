"""Offline wheel overlay only; never imported by production or given VPN access."""
from hashlib import sha256
import json
import logging
import platform
from pathlib import Path, PurePosixPath
import runpy
import sys
import unittest
from zipfile import ZipFile


def main():
    assert platform.machine() == 'x86_64' and platform.libc_ver()[0] == 'glibc', 'Unsupported candidate platform'
    wheel = Path('/review/candidate.whl')
    assert sha256(wheel.read_bytes()).hexdigest() == 'a875a661e2f9a949be29454880bbb9553307a487c4c08819738298cf5c1622e2'
    target = Path('/candidate')
    assert not any(target.iterdir()), 'Overlay must start empty'
    with ZipFile(wheel) as archive:
        entries = archive.infolist()
        assert sum(e.file_size for e in entries) < 64 * 1024 * 1024
        for entry in entries:
            path = PurePosixPath(entry.filename)
            assert not path.is_absolute() and '..' not in path.parts and '\\' not in entry.filename
            assert path.parts[0] in ('curl_cffi', 'curl_cffi.libs', 'curl_cffi-0.16.3.dist-info')
            assert (entry.external_attr >> 16) & 0o170000 != 0o120000, 'No symlinks'
        archive.extractall(target)
    sys.path.insert(0, str(target))
    import curl_cffi
    assert curl_cffi.__version__ == '0.16.3'
    assert Path(curl_cffi.__file__).is_relative_to(target)
    curl = curl_cffi.Curl()
    try:
        print(json.dumps({'candidate': curl_cffi.__version__, 'transport_build': curl.version().decode()}), flush=True)
    finally:
        curl.close()
    import test_timeout_semantics as tests
    tests.verify_client_sources('candidate-0.16.3')
    tests.LoopbackTests.client_profile = 'candidate-0.16.3'
    suite = unittest.defaultTestLoader.loadTestsFromModule(tests)
    # Existing date repair stays active and its tests run against the overlay.
    sys.path.insert(0, '/opt/anonexplo')
    import test_date_merge
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(test_date_merge))
    result = unittest.TestResult()
    suite.run(result)
    print(json.dumps({'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
                      'failed_cases': [t.id().split('.')[-1] for t, _ in result.failures + result.errors]}), flush=True)
    if not result.wasSuccessful():
        return 1
    runpy.run_path('/diagnostic/check-search-settings.py')
    return 0


if __name__ == '__main__':
    logging.disable(logging.CRITICAL)
    try:
        raise SystemExit(main())
    except Exception:
        print('{"status":"offline_candidate_failed","details_suppressed":true}')
        raise SystemExit(3) from None
