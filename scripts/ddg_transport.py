"""Read-only transport counters in a disposable native DDG diagnostic process."""
from contextlib import contextmanager
from contextvars import ContextVar
from hashlib import sha256
import math
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch

FIXTURES = (('transport-battery', 'sodium ion battery recycling research'),
            ('transport-wetlands', 'Mediterranean wetland restoration research'))
SESSION_SHA256 = '322ed676e7a9e666858bca7b281b314d47dae8a07902b2f3e705869f88fa7171'
INFO_FIELDS = {
    'dns_seconds': 'NAMELOOKUP_TIME', 'connect_seconds': 'CONNECT_TIME',
    'tls_seconds': 'APPCONNECT_TIME', 'first_byte_seconds': 'STARTTRANSFER_TIME',
    'total_seconds': 'TOTAL_TIME', 'new_connections': 'NUM_CONNECTS',
    'http_status': 'RESPONSE_CODE', 'download_bytes': 'SIZE_DOWNLOAD_T',
    'redirects': 'REDIRECT_COUNT', 'os_errno': 'OS_ERRNO',
}


def phase_metrics(getinfo, info_type):
    values = {}
    for label, name in INFO_FIELDS.items():
        try:
            value = getinfo(getattr(info_type, name))
            values[label] = round(value, 6) if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None
        except Exception:
            values[label] = None
    return values


def endpoint_stage(url):
    parsed = urlsplit(str(url))
    if parsed.hostname == 'duckduckgo.com':
        if parsed.path in ('', '/'):
            return 'token'
        if parsed.path == '/news.js':
            return 'news'
    return 'other'


@contextmanager
def observe_transport(trace):
    import curl_cffi.requests.session as session
    from curl_cffi import CurlInfo
    from searx.network.client import AsyncClient
    if sha256(Path(session.__file__).read_bytes()).hexdigest() != SESSION_SHA256:
        raise RuntimeError('Transport source changed; review before observing')
    original_parse = session.AsyncSession._parse_response
    original_request = AsyncClient.request
    stage = ContextVar('ddg_transport_stage', default='other')

    def parse(self, curl, *args, **kwargs):
        # Read counters before native parsing/handle reset, including on CurlError.
        # No URL/address/header/body getinfo options, debug or content callbacks.
        trace.add({'stage': 'transport', 'endpoint': stage.get(), 'event': 'counters',
                   **phase_metrics(curl.getinfo, CurlInfo)})
        return original_parse(self, curl, *args, **kwargs)

    async def request(self, method, url, *args, **kwargs):
        marker = stage.set(endpoint_stage(url))
        try:
            return await original_request(self, method, url, *args, **kwargs)
        except Exception as exc:
            code = getattr(exc, 'code', None)
            trace.add({'stage': 'transport', 'endpoint': stage.get(), 'event': 'failed',
                       'curl_code': int(code) if isinstance(code, int) else None})
            raise
        finally:
            stage.reset(marker)

    with patch.object(session.AsyncSession, '_parse_response', parse), patch.object(AsyncClient, 'request', request):
        yield


def offline_wrapper_check():
    """Exercise real hook bindings on fake transfers; never create an HTTP client."""
    import asyncio
    from types import SimpleNamespace
    import curl_cffi.requests.session as session
    from curl_cffi.requests.exceptions import Timeout
    from searx.network.client import AsyncClient
    from ddg_diagnostic import Trace
    import json
    trace, sentinel = Trace(), object()
    error = Timeout('sensitive-url-and-token', 28)

    async def fake_request(self, method, url, *args, **kwargs):
        assert kwargs == {'timeout': 2}
        response = session.AsyncSession._parse_response(self, SimpleNamespace(getinfo=lambda _: 0.1))
        if method == 'FAIL':
            raise error
        return response

    async def run():
        with patch.object(session.AsyncSession, '_parse_response', lambda *a, **kw: sentinel), \
             patch.object(AsyncClient, 'request', fake_request), observe_transport(trace):
            assert await AsyncClient.request(object(), 'GET', 'https://duckduckgo.com/?q=sensitive', timeout=2) is sentinel
            try:
                await AsyncClient.request(object(), 'FAIL', 'https://duckduckgo.com/news.js?vqd=sensitive', timeout=2)
            except Timeout as caught:
                assert caught is error
            else:
                raise AssertionError('Exception swallowed')
    asyncio.run(run())
    rows = trace.snapshot()
    assert [r['endpoint'] for r in rows] == ['token', 'news', 'news']
    assert rows[-1]['curl_code'] == 28
    assert 'sensitive' not in json.dumps(rows)
