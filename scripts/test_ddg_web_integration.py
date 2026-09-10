"""Real native processor/client tests over container-loopback TLS only.

Ephemeral test certificate/key stay in capped /tmp; no provider requests,
payload/headers/URLs/exception dumps or production state. Network=none required.
"""
import asyncio
import concurrent.futures
from contextlib import ExitStack
import hashlib
import gzip
import importlib.util
import json
import logging
from pathlib import Path
import ssl
import subprocess
import tempfile
import traceback
from timeit import default_timer
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ddg_web_guard import CandidateRejected, SOURCE_SHA256
from ddg_web_integration import BoundedTransport, processor_type, verify_integration_sources

logging.disable(logging.CRITICAL)
DIAGNOSTICS = {}
FAILURE_LOCATIONS = {}


def run(coro):
    from searx.network.client import get_loop
    return asyncio.run_coroutine_threadsafe(coro, get_loop()).result(10)


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='ddg-tls-', dir='/tmp')
        cls.cert, cls.key = Path(cls.temp.name, 'cert.pem'), Path(cls.temp.name, 'key.pem')
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                        '-keyout', str(cls.key), '-out', str(cls.cert), '-days', '1',
                        '-subj', '/CN=duckduckgo.com', '-addext',
                        'subjectAltName=DNS:duckduckgo.com,DNS:links.duckduckgo.com'],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        from curl_cffi import CurlOpt
        from searx.network.network import Network, NETWORKS
        from searx.engines import engines
        from searx.search.processors import abstract
        import searx
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.seen, self.mode, self.handlers = [], 'normal', set()
        self.closed_stall = None
        self.server = run(self.start_server())
        self.port = self.server.sockets[0].getsockname()[1]
        self.network = Network(enable_http=False, verify=True, max_connections=1, max_redirects=0, retries=0)
        self.addCleanup(lambda: run(self.cleanup_async()))
        original = Network.get_client
        self.trust_fixture = True

        async def routed(network, **kwargs):
            options = {CurlOpt.RESOLVE: ('duckduckgo.com:443:127.0.0.1',
                                        'links.duckduckgo.com:443:127.0.0.1')}
            if self.trust_fixture:
                options[CurlOpt.CAINFO] = str(self.cert)
            kwargs['curl_options'] = options
            return await original(network, **kwargs)

        self.stack.enter_context(patch.object(Network, 'get_client', routed))
        for name in ['counter_inc', 'count_exception', 'count_error', 'histogram_observe']:
            self.stack.enter_context(patch.object(abstract, name, Mock()))
        def locate(_engine, error):
            frames = traceback.extract_tb(error.__traceback__)
            FAILURE_LOCATIONS[self._testMethodName] = [(Path(f.filename).name, f.lineno) for f in frames[-3:]]
        self.stack.enter_context(patch.object(abstract, 'count_exception', side_effect=locate))
        self.stack.enter_context(patch.dict(abstract.SUSPENDED_STATUS))
        self.stack.enter_context(patch.dict(searx.settings['search']['suspended_times'],
                                          {'SearxEngineTooManyRequests': 180,
                                           'SearxEngineAccessDenied': 180}))
        spec = importlib.util.spec_from_file_location('integration_ddg', '/upstream/duckduckgo_web.py')
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.module.name = 'offline-ddg-web'
        self.module.logger = logging.getLogger('offline-disabled')
        self.module.timeout = 6
        self.module.paging = False
        self.module.max_page = 1
        self.module.time_range_support = False
        self.module.send_accept_language_header = False
        self.stack.enter_context(patch.dict(engines, {self.module.name: self.module}))
        self.stack.enter_context(patch.dict(NETWORKS, {self.module.name: self.network}))
        self.transport = BoundedTransport(self.network)
        self.processor = processor_type()(self.module, self.transport)

    async def start_server(self):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(self.cert), str(self.key))
        context.set_alpn_protocols(['http/1.1'])
        self.closed_stall = asyncio.Event()
        # Docker's unprivileged-port setting permits this as uid 65534, with all
        # capabilities dropped. No published host port or permission relaxation.
        return await asyncio.start_server(self.handle, '127.0.0.1', 443, ssl=context)

    async def cleanup_async(self):
        await self.network.aclose()
        self.server.close()
        await self.server.wait_closed()
        pending = list(self.handlers)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

    async def handle(self, reader, writer):
        task = asyncio.current_task()
        self.handlers.add(task)
        try:
            raw = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 3)
            lines = raw.decode('ascii').split('\r\n')
            path = lines[0].split()[1]
            headers = dict(line.split(': ', 1) for line in lines[1:] if ': ' in line)
            self.seen.append({key.lower(): value for key, value in headers.items()})
            status, extra = 200, 'Set-Cookie: fixture=private; Domain=duckduckgo.com; Path=/; Secure\r\n'
            if self.mode == 'shared-deadline' and path.startswith('/?'):
                await asyncio.sleep(.12)
            if self.mode == 'stall' or (self.mode == 'shared-deadline' and not path.startswith('/?')):
                await asyncio.wait_for(reader.read(), 3)
                self.closed_stall.set()
                return
            if self.mode == 'disconnect':
                return
            if self.mode == 'redirect':
                status, extra = 302, 'Location: https://links.duckduckgo.com/d.js?redirect=1\r\n'
                body = b''
            elif self.mode in ('429', '403', '503'):
                status, body = int(self.mode), b'fixture'
            elif self.mode in ('large', 'compressed-large'):
                body = b'x' * 2097152
                if self.mode == 'compressed-large':
                    body = gzip.compress(body)
                    extra += 'Content-Encoding: gzip\r\n'
            elif self.mode == 'exact-body':
                body = b'x' * 1048576
            elif path.startswith('/?'):
                body = b'<html><link id="deep_preload_link" href="https://links.duckduckgo.com/d.js?vqd=fixture"></html>'
            elif self.mode == 'challenge' and 'jsa=' not in path:
                body = b"let jsa = 7; let f = function(num) {return num * 3;}; jsa = f(jsa); DDG.deep.initialize('/d.js?jsa=')"
            else:
                body = b'{"results":[{"u":"https://example.invalid/","t":"Fixture","a":"Synthetic"}]}'
            writer.write(f'HTTP/1.1 {status} Fixture\r\nContent-Length: {len(body)}\r\n{extra}Connection: close\r\n\r\n'.encode())
            writer.write(body)
            await writer.drain()
        except (ConnectionError, asyncio.TimeoutError, ssl.SSLError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, ssl.SSLError):
                pass
            self.handlers.discard(task)

    def search(self, budget=6, changes=None, processor=None):
        from searx.search.processors.online import default_request_params
        params = {**default_request_params(), 'query': 'public fixture', 'pageno': 1,
                  'safesearch': 0, 'time_range': None, 'searxng_locale': 'all',
                  'headers': {'User-Agent': 'OfflineFixture', 'Cookie': 'private', 'Authorization': 'private'}}
        params.update(changes or {})
        container = Mock()
        (processor or self.processor).search('public fixture', params, container, default_timer(), budget)
        if container.add_unresponsive_engine.called:
            name = container.add_unresponsive_engine.call_args.args[1].split('.')[-1]
            DIAGNOSTICS[self._testMethodName] = name if name in (
                'TypeError', 'ValueError', 'AttributeError', 'RequestException', 'Timeout',
                'SearxEngineTooManyRequestsException', 'SearxEngineAccessDeniedException',
                'HTTPError', 'SSLError', 'CertificateVerifyError', 'ConnectionError') else 'other'
        return container

    def test_real_tls_native_results(self):
        container = self.search()
        self.assertEqual(len(self.seen), 2)
        container.add_unresponsive_engine.assert_not_called()
        results = container.extend.call_args.args[1]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, 'Fixture')

    def test_challenge_followup_over_tls(self):
        self.mode = 'challenge'
        container = self.search()
        self.assertEqual(len(self.seen), 3)
        container.add_unresponsive_engine.assert_not_called()

    def test_cookie_and_browser_header_isolation_across_queries(self):
        self.search()
        self.search()
        self.assertEqual(len(self.seen), 4)
        for headers in self.seen:
            self.assertNotIn('cookie', headers)
            self.assertNotIn('authorization', headers)
            self.assertNotIn('sec-ch-ua', headers)
            self.assertNotIn('accept-language', headers)
            self.assertEqual(headers['user-agent'], 'OfflineFixture')
        self.assertEqual(len(self.network._clients), 1)
        self.assertEqual(len(next(iter(self.network._clients.values())).cookies), 0)

    def test_redirect_never_followed(self):
        self.mode = 'redirect'
        container = self.search()
        self.assertEqual(len(self.seen), 1)
        container.extend.assert_not_called()
        self.assertTrue(self.processor.suspended_status.is_suspended)

    def test_native_429_cooldown_shared_with_new_processor(self):
        self.mode = '429'
        before = default_timer()
        container = self.search()
        status = self.processor.suspended_status
        self.assertTrue(status.is_suspended)
        self.assertIn('SearxEngineTooManyRequestsException', container.add_unresponsive_engine.call_args.args[1])
        self.assertGreaterEqual(status.suspend_end_time, before + 180)
        self.assertLess(status.suspend_end_time, default_timer() + 181)
        self.mode = 'normal'
        replacement = processor_type()(self.module, self.transport)
        self.assertIs(replacement.suspended_status, status)
        blocked = self.search(processor=replacement)
        self.assertEqual(len(self.seen), 1)
        self.assertTrue(blocked.add_unresponsive_engine.call_args.kwargs['suspended'])

    def test_native_403_mapping(self):
        self.mode = '403'
        container = self.search()
        self.assertIn('SearxEngineAccessDeniedException', container.add_unresponsive_engine.call_args.args[1])
        self.assertTrue(self.processor.suspended_status.is_suspended)
        self.assertEqual(len(self.seen), 1)

    def test_native_http_error_mapping(self):
        self.mode = '503'
        container = self.search()
        self.assertIn('HTTPError', container.add_unresponsive_engine.call_args.args[1])
        self.assertTrue(self.processor.suspended_status.is_suspended)

    def test_body_limit_aborts_before_parser(self):
        self.mode = 'large'
        container = self.search()
        container.extend.assert_not_called()
        self.assertEqual(len(self.seen), 1)
        self.assertTrue(self.processor.suspended_status.is_suspended)

    def test_decompressed_body_limit(self):
        self.mode = 'compressed-large'
        container = self.search()
        container.extend.assert_not_called()
        self.assertEqual(len(self.seen), 1)
        self.assertTrue(self.processor.suspended_status.is_suspended)

    def test_body_limit_exact_boundary(self):
        self.mode = 'exact-body'
        response = run(self.transport.transfer('https://links.duckduckgo.com/d.js',
                       headers={}, timeout=2, allow_redirects=False, max_redirects=0,
                       verify=True, impersonate='firefox', default_headers=False))
        self.assertEqual(len(response.content), 1048576)

    def test_timeout_cancels_transfer_and_starts_no_followup(self):
        self.mode = 'stall'
        before = default_timer()
        container = self.search(budget=.3)
        self.assertLess(default_timer() - before, 1.5)
        self.assertIn('Timeout', container.add_unresponsive_engine.call_args.args[1])
        self.assertEqual(len(self.seen), 1)
        self.assertTrue(self.processor.suspended_status.is_suspended)
        run(asyncio.wait_for(self.closed_stall.wait(), 1))

    def test_connection_error_not_retried(self):
        self.mode = 'disconnect'
        self.search()
        self.assertEqual(len(self.seen), 1)
        self.assertTrue(self.processor.suspended_status.is_suspended)

    def test_shared_deadline_includes_first_fetch(self):
        self.mode = 'shared-deadline'
        before = default_timer()
        container = self.search(budget=.3)
        self.assertLess(default_timer() - before, 1.5)
        self.assertEqual(len(self.seen), 2)
        self.assertIn('Timeout', container.add_unresponsive_engine.call_args.args[1])
        run(asyncio.wait_for(self.closed_stall.wait(), 1))

    def test_caller_timeout_requests_future_cancellation(self):
        from curl_cffi.requests.exceptions import Timeout
        future = Mock()
        future.result.side_effect = concurrent.futures.TimeoutError()
        def submit(coro, _loop):
            coro.close()
            return future
        with patch('asyncio.run_coroutine_threadsafe', side_effect=submit):
            with self.assertRaises(Timeout):
                self.transport('https://duckduckgo.com/', headers={}, timeout=.1,
                               allow_redirects=False, max_redirects=0, verify=True,
                               impersonate='firefox', default_headers=False)
        future.cancel.assert_called_once_with()
        self.assertEqual(len(self.seen), 0)

    def test_native_cooldown_expiry_without_reset(self):
        from searx.search.processors import abstract
        self.mode = '429'
        self.search()
        status = self.processor.suspended_status
        self.mode = 'normal'
        # Advance only the isolated native status clock; never clear/reset it.
        with patch.object(abstract, 'default_timer', return_value=status.suspend_end_time + 1):
            container = self.search()
        container.add_unresponsive_engine.assert_not_called()
        self.assertEqual(len(self.seen), 3)
        self.assertEqual(status.continuous_errors, 0)

    def test_untrusted_tls_certificate_rejected(self):
        self.trust_fixture = False
        container = self.search()
        container.extend.assert_not_called()
        self.assertEqual(len(self.seen), 0)
        self.assertTrue(self.processor.suspended_status.is_suspended)

    def test_unsupported_filters_never_requested(self):
        for changes in [{'safesearch': 1}, {'time_range': 'week'}, {'pageno': 2}, {'searxng_locale': 'el'}]:
            self.search(changes=changes).extend.assert_not_called()
        self.assertEqual(len(self.seen), 0)

    def test_native_get_params_rejects_unsupported_filters(self):
        query = dict(query='public fixture', pageno=1, safesearch=0, time_range=None,
                     engine_data={}, lang='all', locale=None)
        self.assertIsNotNone(self.processor.get_params(SimpleNamespace(**query), 'general'))
        for changes in [{'safesearch': 1}, {'time_range': 'week'}, {'pageno': 2}, {'lang': 'el'}]:
            self.assertIsNone(self.processor.get_params(SimpleNamespace(**{**query, **changes}), 'general'))
        self.assertEqual(len(self.seen), 0)

    def test_native_processor_drops_false_characterization(self):
        from searx.search.processors.online import OnlineProcessor, default_request_params
        processor = OnlineProcessor(self.module)
        params = {**default_request_params(), 'url': 'https://duckduckgo.com/',
                  'default_headers': False, 'impersonate': 'firefox'}
        with patch('searx.network.get', return_value=SimpleNamespace(history=[])) as get:
            processor._send_http_request(params)
        self.assertNotIn('default_headers', get.call_args.kwargs)
        self.assertFalse(get.call_args.kwargs['allow_redirects'])

    def test_contaminated_cookie_jar_refused(self):
        client = run(self.network.get_client(verify=True, max_redirects=0, impersonate='firefox'))
        client.cookies.set('fixture', 'private', domain='duckduckgo.com')
        container = self.search()
        container.extend.assert_not_called()
        self.assertEqual(len(self.seen), 0)


if __name__ == '__main__':
    try:
        verify_integration_sources()
        if hashlib.sha256(Path('/upstream/duckduckgo_web.py').read_bytes()).hexdigest() != SOURCE_SHA256:
            raise RuntimeError('Upstream source mismatch')
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(IntegrationTests)
        report = unittest.TestResult()
        suite.run(report)
        print(json.dumps({'tests': report.testsRun, 'failures': len(report.failures),
                          'errors': len(report.errors), 'skipped': len(report.skipped),
                          'error_classes': DIAGNOSTICS if not report.wasSuccessful() else {},
                          'error_locations': FAILURE_LOCATIONS if not report.wasSuccessful() else {},
                          'failed_tests': [case.id().split('.')[-1] for case, _ in report.failures + report.errors]}))
        raise SystemExit(0 if report.wasSuccessful() else 1)
    except Exception:
        print('FAIL: offline integration setup; details suppressed')
        raise SystemExit(1) from None
