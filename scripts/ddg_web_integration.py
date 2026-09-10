"""Offline-only native processor/client integration. Not a production import.

The shipped runner has network=none and routes the exact allowed HTTPS hosts to
an ephemeral container-loopback TLS fixture. No live entrypoint is provided.
"""
import asyncio
import concurrent.futures
from hashlib import sha256
from pathlib import Path
from threading import Lock
from timeit import default_timer

from ddg_web_guard import CandidateRejected, GuardedWeb, checked_url
from test_timeout_semantics import verify_client_sources


def verify_integration_sources():
    verify_client_sources()
    for path, expected in {
        'search/processors/abstract.py': '4f8f74ad99cd3785928d4d38ecaf4dcee7f32875a9008bdf86fa9db3dc347a9a',
        'network/raise_for_httperror.py': '1f6b87ab081b8a16843e895454980e099f958c9e6e2f54fd97df211e7c57caaf',
        'exceptions.py': '40b796a2baed9f1282e715829b0f7df6182b741a43033b760af15831c7a5bab5',
    }.items():
        if sha256(Path('/usr/local/searxng/searx', path).read_bytes()).hexdigest() != expected:
            raise RuntimeError('Offline integration source mismatch')


class BoundedTransport:
    """Use native client acquisition/error mapping, but make exactly one attempt.

Network.request's special ConnectionError retry is intentionally not used here.
The native session has zero retries and discard_cookies=True; enforce both.
Only body bytes are capped; native TLS/headers/internal allocations are not.
"""
    def __init__(self, network):
        self.network = network

    async def transfer(self, url, *, headers, timeout, allow_redirects, max_redirects,
                       verify, impersonate, default_headers):
        from curl_cffi.requests.exceptions import Timeout
        if url.startswith('https://duckduckgo.com/'):
            checked_url(url, first=True)
        else:
            checked_url(url)
        if (allow_redirects is not False or max_redirects != 0 or verify is not True
                or impersonate != 'firefox' or default_headers is not False
                or not 0 < timeout <= 6):
            raise CandidateRejected('Offline transport policy rejected')
        body = bytearray()
        exceeded = False

        def collect(chunk):
            nonlocal exceeded
            if len(body) + len(chunk) > 1048576:
                exceeded = True
                return 0  # libcurl aborts the write; never retain excess bytes.
            body.extend(chunk)
            return len(chunk)

        async def once():
            client = await self.network.get_client(verify=True, max_redirects=0, impersonate='firefox')
            if client.retry.count != 0 or not client.discard_cookies or len(client.cookies):
                raise CandidateRejected('Offline client policy rejected')
            client.check_url(url)
            try:
                response = await client.request('GET', url, headers=headers, timeout=timeout,
                                                allow_redirects=False, max_redirects=0,
                                                default_headers=False, discard_cookies=True,
                                                content_callback=collect)
            except Exception:
                if exceeded:
                    raise CandidateRejected('Offline body bound exceeded') from None
                raise
            response.content = bytes(body)
            return self.network.patch_response(response, True)

        try:
            return await asyncio.wait_for(once(), timeout)
        except asyncio.TimeoutError:
            raise Timeout('Offline candidate deadline') from None

    def __call__(self, url, **kwargs):
        from curl_cffi.requests.exceptions import Timeout
        from searx.network.client import get_loop
        future = asyncio.run_coroutine_threadsafe(self.transfer(url, **kwargs), get_loop())
        try:
            # async wait_for enforces transport budget; allowance is cleanup only.
            return future.result(kwargs['timeout'] + .2)
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise Timeout('Offline candidate caller deadline') from None


def processor_type():
    """Import native processor only after the runner verifies exact sources."""
    from curl_cffi.requests.exceptions import RequestException
    from searx.search.processors.online import OnlineProcessor

    class GuardedProcessor(OnlineProcessor):
        def __init__(self, engine, transport):
            super().__init__(engine)
            self.transport = transport
            self.serial = Lock()

        @staticmethod
        def supported(params):
            return (params.get('pageno') == 1 and params.get('safesearch') == 0
                    and not params.get('time_range') and params.get('searxng_locale') == 'all')

        def get_params(self, search_query, engine_category):
            params = super().get_params(search_query, engine_category)
            return params if params is not None and self.supported(params) else None

        def _search_basic(self, query, params):
            if not self.supported(params):
                return None
            remaining = self.deadline - default_timer()
            try:
                return GuardedWeb(self.engine, self.transport, clock=default_timer).run(
                    query, params['headers'], budget=remaining)
            except CandidateRejected:
                # A policy rejection is an unsuccessful request, not healthy empty
                # results. Native request-error handling supplies its normal ban.
                raise RequestException('Offline candidate policy rejected') from None

        def search(self, query, params, result_container, start_time, timeout_limit):
            if not self.serial.acquire(blocking=False):
                result_container.add_unresponsive_engine(self.engine.name, 'candidate busy')
                return
            try:
                # Native orchestrator normally checks this before dispatch. This
                # isolated entrypoint must also check, including after a new object.
                if self.extend_container_if_suspended(result_container):
                    return
                self.deadline = start_time + min(6, timeout_limit)
                super().search(query, params, result_container, start_time, timeout_limit)
            finally:
                self.serial.release()

    return GuardedProcessor
