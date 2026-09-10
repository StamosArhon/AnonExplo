"""Metadata-only observation of the unchanged native DDG News request path.

No runtime service imports this helper. No tokens, URLs, queries, bodies or raw
exceptions enter the trace. Fixture strings are synthetic public test inputs.
"""
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from threading import Lock
from time import monotonic
from unittest.mock import patch

FIXTURES = (
    ('ddg-wind', 'offshore wind maintenance research'),
    ('ddg-heat-el', '\u03b1\u03c3\u03c4\u03b9\u03ba\u03ae \u03b8\u03b5\u03c1\u03bc\u03b9\u03ba\u03ae \u03bd\u03b7\u03c3\u03af\u03b4\u03b1 \u0395\u03bb\u03bb\u03ac\u03b4\u03b1'),
)
SOURCE_HASHES = {
    'engines/duckduckgo_extra.py': 'f9c44d75800edb2c50cec532f04e902da88bc910ebad33ab59048805be020b7e',
    'search/processors/online.py': 'ee844305b99418df640fdb5a79a0ff15201d2a35a702edbca1e88171d6996bc0',
    'network/__init__.py': '0b570a5fff402a38774addd8570b059f7038b09fe56f57b27fe043e3d22acfd0',
}


def verify_sources():
    for relative, expected in SOURCE_HASHES.items():
        if sha256(Path('/usr/local/searxng/searx', relative).read_bytes()).hexdigest() != expected:
            raise RuntimeError('Diagnostic source fingerprint changed; review before use')


class Trace:
    def __init__(self):
        self.rows = []
        self.lock = Lock()

    def add(self, row):
        with self.lock:
            if len(self.rows) < 40:
                self.rows.append(row)

    def snapshot(self):
        with self.lock:
            return [row.copy() for row in self.rows]

    def observe(self, stage, function, summary=lambda value: {}):
        def call(*args, **kwargs):
            started = monotonic()
            self.add({'stage': stage, 'event': 'entered'})
            try:
                value = function(*args, **kwargs)
            except Exception as exc:
                kind = type(exc).__name__
                if kind not in ('Timeout', 'TimeoutError', 'HTTPError', 'JSONDecodeError',
                                'SearxEngineTooManyRequestsException', 'SearxEngineAccessDeniedException',
                                'SearxEngineCaptchaException'):
                    kind = 'other'
                self.add({'stage': stage, 'event': 'failed', 'kind': kind,
                          'seconds': round(monotonic() - started, 3)})
                raise
            self.add({'stage': stage, 'event': 'returned',
                      'seconds': round(monotonic() - started, 3), **summary(value)})
            return value
        return call


@contextmanager
def observe_native(engine, network, trace):
    # Token get is the adapter's imported function; downstream get is resolved
    # dynamically by OnlineProcessor. Do not replace native request/parse logic.
    status = lambda response: {'http_status': int(response.status_code)}
    timeout_original = network._get_timeout

    def budget(start_time, kwargs):
        wait = timeout_original(start_time, kwargs)
        trace.add({'stage': 'native_budget', 'event': 'calculated',
                   'caller_wait_seconds': round(wait, 3),
                   'transport_timeout_seconds': kwargs.get('timeout')})
        return wait

    with patch.object(engine, 'get', trace.observe('token_http', engine.get, status)), \
         patch.object(engine, 'get_vqd', trace.observe('token_cache', engine.get_vqd, lambda value: {'hit': bool(value)})), \
         patch.object(engine, 'fetch_vqd', trace.observe('token_parse', engine.fetch_vqd, lambda value: {'present': bool(value)})), \
         patch.object(engine, 'request', trace.observe('request_prepare', engine.request)), \
         patch.object(network, 'get', trace.observe('news_http', network.get, status)), \
         patch.object(network, '_get_timeout', budget), \
         patch.object(engine, 'response', trace.observe('news_parse', engine.response)):
        yield
