"""Pinned-client characterization; mock futures and container-loopback only.

Run via test-ddg-diagnostic.ps1 -TimeoutSemantics (network=none).
No production imports, upstream queries, payload logs, certificates or files.
"""
import asyncio
from contextlib import nullcontext
from hashlib import sha256
import importlib
import json
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from ddg_diagnostic import Trace, verify_sources
from ddg_transport import observe_transport


def verify_client_sources(profile='production'):
    verify_sources()
    for name, expected in {
        'searx.network.network': '230eda36d0632377e91fdbe2f542c2aee544c85c743c3d1f6f8c3d129fa45afe',
        'searx.network.client': '4fe47480cd80169132e56c66ba0122c0beb8bb6af7db08bf8f54ee83b12ecd0e',
        'curl_cffi.requests.utils': {
            'production': '70336a034312cdaab0ca9d2f1f07606bae727dca3d57b31ae0a0e9c005c80b75',
            'candidate-0.16.3': 'bb61f6493a70f0524a10d27a74983ef85de92526ad873bc226a55c69ebb749d4',
        }[profile],
    }.items():
        module = importlib.import_module(name)
        if sha256(Path(module.__file__).read_bytes()).hexdigest() != expected:
            raise RuntimeError('Offline source compatibility changed')
    with observe_transport(Trace(), profile=profile):
        pass


class CallerTests(unittest.TestCase):
    def setUp(self):
        import searx.network as network
        self.network = network

    def budget(self, elapsed, explicit=None):
        kwargs = {} if explicit is None else {'timeout': explicit}
        with patch.object(self.network, 'THREADLOCAL', SimpleNamespace(timeout=6)), \
             patch.object(self.network, 'default_timer', return_value=100 + elapsed):
            wait = self.network._get_timeout(100, kwargs)
        return wait, kwargs['timeout']

    def test_token_explicit_budget(self):
        wait, transport = self.budget(0, 2)
        self.assertAlmostEqual(wait, 2.2)
        self.assertEqual(transport, 2)

    def test_downstream_wait_shares_elapsed_engine_time(self):
        wait, transport = self.budget(1.5)
        self.assertAlmostEqual(wait, 4.7)
        self.assertEqual(transport, 6)

    def test_expired_wait_not_clamped_or_transport_shortened(self):
        wait, transport = self.budget(7)
        self.assertAlmostEqual(wait, -.8)
        self.assertEqual(transport, 6)

    def call_with_future(self, future):
        n = self.network
        async def no_network(*args, **kwargs):
            raise AssertionError('Mock coroutine must not execute')
        def submit(coro, loop):
            coro.close()
            return future
        with patch.object(n, '_record_http_time', lambda: nullcontext(100)), \
             patch.object(n, '_get_timeout', return_value=.1), \
             patch.object(n, 'get_context_network', return_value=SimpleNamespace(request=no_network)), \
             patch.object(n, 'get_loop', return_value=object()), \
             patch.object(n.asyncio, 'run_coroutine_threadsafe', side_effect=submit):
            return n.request('GET', 'https://example.invalid/')

    def test_caller_timeout_does_not_cancel_future(self):
        from curl_cffi.requests.exceptions import Timeout
        future = Mock()
        future.result.side_effect = TimeoutError()
        with self.assertRaises(Timeout) as caught:
            self.call_with_future(future)
        self.assertIsInstance(caught.exception.__cause__, TimeoutError)
        future.result.assert_called_once_with(.1)
        future.cancel.assert_not_called()

    def test_transport_timeout_identity_is_preserved(self):
        from curl_cffi.requests.exceptions import Timeout
        error = Timeout('synthetic', 28)
        future = Mock()
        future.result.side_effect = error
        with self.assertRaises(Timeout) as caught:
            self.call_with_future(future)
        self.assertIs(caught.exception, error)
        self.assertEqual(caught.exception.code, 28)
        future.cancel.assert_not_called()


class RetryTests(unittest.IsolatedAsyncioTestCase):
    async def fake_failure(self, error, expected):
        from searx.network.network import Network
        n = Network(retries=0)
        client = Mock()
        client.request = AsyncMock(side_effect=error)
        client.aclose = AsyncMock()
        with patch.object(Network, 'get_client', AsyncMock(return_value=client)):
            with self.assertRaises(type(error)):
                await n.request('GET', 'https://example.invalid/')
        self.assertEqual(client.request.await_count, expected)
        self.assertEqual(client.aclose.await_count, expected - 1)

    async def test_timeout_not_retried_with_zero_retries(self):
        from curl_cffi.requests.exceptions import Timeout
        await self.fake_failure(Timeout('synthetic', 28), 1)

    async def test_connection_error_has_one_native_retry(self):
        from curl_cffi.requests.exceptions import ConnectionError
        await self.fake_failure(ConnectionError('synthetic', 7), 2)


class LoopbackTests(unittest.IsolatedAsyncioTestCase):
    client_profile = 'production'
    async def asyncSetUp(self):
        from searx.network.client import new_client
        self.client = new_client(True, True, True, False, 1, {}, None, 0)
        self.trace = Trace()
        self.observer = observe_transport(self.trace, profile=self.client_profile)
        self.observer.__enter__()
        self.tasks = set()
        self.accepted = 0

    async def asyncTearDown(self):
        await self.client.aclose()
        self.observer.__exit__(None, None, None)
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    async def server(self, good=False):
        async def handler(reader, writer):
            self.accepted += 1
            task = asyncio.current_task()
            self.tasks.add(task)
            try:
                if good:
                    await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 2)
                    writer.write(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nOK')
                    await writer.drain()
                else:
                    # Accept TCP but send no TLS handshake or HTTP response.
                    await asyncio.sleep(2)
            finally:
                writer.close()
                await writer.wait_closed()
                self.tasks.discard(task)
        return await asyncio.start_server(handler, '127.0.0.1', 0)

    async def transfer(self, server, tls=False, timeout=.3):
        port = server.sockets[0].getsockname()[1]
        return await self.client.get(f'{"https" if tls else "http"}://127.0.0.1:{port}/', timeout=timeout)

    def counters(self, label):
        rows = self.trace.snapshot()
        counters = [r for r in rows if r['event'] == 'counters'][-1]
        # Only existing numeric allowlist; no response, address or exception text.
        print(json.dumps({'fixture': label, **counters}), flush=True)
        return counters

    async def test_success_and_default_retry_count(self):
        self.assertEqual(self.client.retry.count, 0)
        server = await self.server(good=True)
        async with server:
            response = await self.transfer(server, timeout=2)
        self.assertEqual(response.status_code, 200)
        row = self.counters('loopback-success')
        self.assertEqual(row['http_status'], 200)
        self.assertEqual(row['download_bytes'], 2)

    async def stalled(self, tls, warm=False):
        from curl_cffi.requests.exceptions import Timeout
        if warm:
            good = await self.server(good=True)
            async with good:
                self.assertEqual((await self.transfer(good, timeout=2)).status_code, 200)
        server = await self.server()
        async with server:
            with self.assertRaises(Timeout) as caught:
                await self.transfer(server, tls)
        self.assertEqual(caught.exception.code, 28)
        row = self.counters('loopback-' + ('tls' if tls else 'http') + ('-after-success' if warm else '-cold'))
        self.assertEqual(row['http_status'], 0)
        self.assertEqual(row['download_bytes'], 0)
        self.assertGreaterEqual(row['total_seconds'], .2)
        self.assertLess(row['total_seconds'], 2)
        self.assertEqual(self.accepted, 2 if warm else 1)
        if tls:
            # Characterize this pin's misleading failure counters: the server
            # accepted TCP and sent nothing, yet FIRST_BYTE is near the timeout.
            self.assertEqual(row['connect_seconds'], 0)
            self.assertEqual(row['tls_seconds'], 0)
            self.assertGreaterEqual(row['first_byte_seconds'], .2)
        else:
            self.assertGreater(row['connect_seconds'], 0)
            self.assertEqual(row['first_byte_seconds'], 0)

    async def test_stalled_http_response(self):
        await self.stalled(False)

    async def test_stalled_tls_handshake(self):
        await self.stalled(True)

    async def test_stalled_tls_after_successful_handle_use(self):
        await self.stalled(True, warm=True)


if __name__ == '__main__':
    logging.disable(logging.CRITICAL)
    try:
        verify_client_sources()
        suite = unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__))
        result = unittest.TestResult()
        suite.run(result)
        print(json.dumps({'tests': result.testsRun, 'failures': len(result.failures),
                          'errors': len(result.errors), 'skipped': len(result.skipped),
                          'failed_cases': [test.id().split('.')[-1] for test, _ in result.failures + result.errors]}))
        raise SystemExit(0 if result.wasSuccessful() else 1)
    except Exception:
        print('{"status":"offline_timeout_probe_failed","details_suppressed":true}')
        raise SystemExit(3) from None
