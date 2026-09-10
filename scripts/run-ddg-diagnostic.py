"""Disposable same-image diagnostic: at most two new queries; stop on failure."""
import argparse
import json
import logging
import os
import secrets
import time
from contextlib import nullcontext

from ddg_diagnostic import FIXTURES, Trace, observe_native, verify_sources


def main(live=False, transport=False):
    logging.disable(logging.CRITICAL)
    verify_sources()
    os.environ['SEARXNG_SECRET'] = secrets.token_hex(32)
    import searx
    chosen = [dict(e) for e in searx.settings['engines'] if e['name'] in ('duckduckgo', 'duckduckgo news')]
    assert {e['name'] for e in chosen} == {'duckduckgo', 'duckduckgo news'}
    for entry in chosen:
        entry['disabled'] = entry['name'] == 'duckduckgo'
        assert entry['timeout'] == 6
    searx.settings['engines'] = chosen
    from searx.webapp import app
    from searx.engines import engines
    import searx.network as network
    fixtures = FIXTURES
    transport_observer = lambda trace: nullcontext()
    if transport:
        from ddg_transport import FIXTURES as transport_fixtures, observe_transport
        fixtures = transport_fixtures
        transport_observer = observe_transport
        # Source guard and hook installation are exercised even offline.
        with transport_observer(Trace()):
            pass
    assert set(engines) == {'duckduckgo', 'duckduckgo news'}
    assert all(not hasattr(e, 'init') for e in engines.values())
    with app.test_client(use_cookies=False) as client:
        assert client.get('/').status_code == 200
    print(json.dumps({'status': 'initialized', 'no_listener': True, 'live': live}), flush=True)
    if not live:
        if transport:
            from ddg_transport import offline_wrapper_check
            offline_wrapper_check()
            print('{"status":"offline_transport_bindings_passed"}', flush=True)
        return 0
    for index, (sample, query) in enumerate(fixtures):
        trace = Trace()
        with transport_observer(trace), observe_native(engines['duckduckgo news'], network, trace), app.test_client(use_cookies=False) as client:
            started = time.monotonic()
            response = client.get('/search', query_string={'q': query, 'engines': 'duckduckgo news', 'format': 'json'},
                                  headers={'Accept-Language': 'en-US,en;q=0.9'}, follow_redirects=False)
            elapsed = time.monotonic() - started
            payload = response.get_json(silent=True) or {}
            rows = payload.get('results', [])
            errors = len(payload.get('unresponsive_engines', []))
            healthy = response.status_code == 200 and bool(rows) and errors == 0
            # Native engine may finish shortly after the web response deadline.
            # Observation only: no extended network budget and no second request.
            if not healthy:
                time.sleep(1)
            print(json.dumps({'sample': sample, 'http_status': response.status_code,
                              'seconds': round(elapsed, 3), 'results': len(rows),
                              'engine_errors': errors, 'trace': trace.snapshot(),
                              'stopped': not healthy}), flush=True)
        if not healthy:
            return 2
        if index + 1 < len(fixtures):
            time.sleep(20)
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--transport', action='store_true')
    args = parser.parse_args()
    try:
        raise SystemExit(main(args.live, args.transport))
    except Exception:
        print('{"status":"diagnostic_failed","details_suppressed":true}', flush=True)
        raise SystemExit(3) from None
