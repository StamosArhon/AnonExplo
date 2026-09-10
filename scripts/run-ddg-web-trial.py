"""Approved bounded DDG web trial; invoke only through its preflight wrapper.

No test CA/DNS override, public listener, raw error recording or query cache.
Default is initialization-only, suitable for network=none validation.
"""
import argparse
import asyncio
from contextlib import ExitStack
from hashlib import sha256
import importlib.util
import json
import logging
import os
from pathlib import Path
import secrets
import time
from unittest.mock import patch

from ddg_web_guard import SOURCE_SHA256
from ddg_web_integration import BoundedTransport, processor_type, verify_integration_sources
from ddg_web_trial import FIXTURES, acceptable, grade


def emit(value):
    print(json.dumps(value), flush=True)


class MetricsContainer:
    def __init__(self):
        self.rows, self.errors = [], []

    def extend(self, _engine, rows):
        self.rows.extend(rows)

    def add_timing(self, *_args):
        pass

    def add_unresponsive_engine(self, _engine, error, **_kwargs):
        # Never emit a raw exception/message; only fixed categories.
        name = error.split('.')[-1]
        self.errors.append(name if name in (
            'Timeout', 'HTTPError', 'RequestException', 'ConnectionError',
            'CertificateVerifyError', 'SearxEngineTooManyRequestsException',
            'SearxEngineAccessDeniedException', 'SearxEngineCaptchaException') else 'other')


def main(live=False):
    logging.disable(logging.CRITICAL)
    os.environ['SEARXNG_SECRET'] = secrets.token_hex(32)
    verify_integration_sources()
    if sha256(Path(__file__).with_name('ddg_web_trial.py').read_bytes()).hexdigest() != 'e7ed615ba8de830dec6e09a506677d6be9db1518c4a6ee414e56486218a79175':
        raise RuntimeError('Frozen fixture/policy mismatch')
    source = Path('/upstream/duckduckgo_web.py')
    if sha256(source.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise RuntimeError('Source mismatch')
    import searx
    from searx.engines import engines
    from searx.network.network import Network, NETWORKS
    from searx.network.client import get_loop
    from searx.search.processors import abstract
    from searx.search.processors.online import default_request_params
    from searx.utils import gen_useragent

    outgoing = searx.settings['outgoing']
    if outgoing['request_timeout'] != 4 or outgoing['max_request_timeout'] != 8:
        raise RuntimeError('Unreviewed budgets')
    for key in ('SearxEngineTooManyRequests', 'SearxEngineAccessDenied'):
        if searx.get_setting('search.suspended_times.' + key) > 180:
            raise RuntimeError('Unreviewed cooldown')
    if max(searx.get_setting('search.ban_time_on_fail'), searx.get_setting('search.max_ban_time_on_fail')) > 180:
        raise RuntimeError('Unreviewed generic cooldown')
    if live:
        if os.environ.get('ANONEXPLO_WEB_TRIAL_AUTHORIZED') != 'frozen-web-trial-v1':
            raise RuntimeError('Wrapper preflight required')
        nameservers = [line.split()[1] for line in Path('/etc/resolv.conf').read_text().splitlines()
                       if line.startswith('nameserver ')]
        if nameservers != ['127.0.0.1']:
            raise RuntimeError('VPN-local resolver required')
    spec = importlib.util.spec_from_file_location('trial_ddg_web', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.name = 'offline-reviewed-ddg-web'
    module.logger = logging.getLogger('trial-disabled')
    module.timeout, module.paging, module.max_page = 6, False, 1
    module.time_range_support, module.send_accept_language_header = False, False
    network = Network(enable_http=False, verify=True, enable_http2=outgoing['enable_http2'],
                      max_connections=1, max_redirects=0, retries=0)
    try:
        with ExitStack() as stack:
            stack.enter_context(patch.dict(engines, {module.name: module}))
            stack.enter_context(patch.dict(NETWORKS, {module.name: network}))
            for name in ('counter_inc', 'count_exception', 'count_error', 'histogram_observe'):
                stack.enter_context(patch.object(abstract, name, lambda *_args, **_kwargs: None))
            transport = BoundedTransport(network)
            stages = []
            def observed_transport(url, **kwargs):
                started = time.perf_counter()
                row = {'call': len(stages) + 1}
                try:
                    response = transport(url, **kwargs)
                    row['http_status'] = response.status_code
                    return response
                except Exception:
                    row['failed'] = True
                    raise
                finally:
                    row['seconds'] = round(time.perf_counter() - started, 3)
                    stages.append(row)
            processor = processor_type()(module, observed_transport)
            emit({'status': 'initialized', 'live': live, 'no_listener': True, 'fixture_count': len(FIXTURES)})
            if not live:
                return 0
            # One UA, module, native Network and suspension state for entire trial.
            headers = {'User-Agent': gen_useragent()}
            for index, (sample, query, domain) in enumerate(FIXTURES):
                stages.clear()
                container = MetricsContainer()
                params = {**default_request_params(), 'headers': dict(headers), 'query': query,
                          'pageno': 1, 'safesearch': 0, 'time_range': None, 'searxng_locale': 'all'}
                started = time.perf_counter()
                processor.search(query, params, container, started, 6)
                metrics = grade(container.rows, domain)
                healthy = acceptable(metrics, container.errors)
                emit({'sample': sample, **metrics, 'seconds': round(time.perf_counter() - started, 3),
                      'errors': container.errors, 'stages': list(stages), 'accepted': healthy})
                container.rows.clear()
                if not healthy:
                    emit({'status': 'stopped_on_degradation', 'no_retry': True})
                    return 2
                if index + 1 < len(FIXTURES):
                    time.sleep(20)
            emit({'status': 'completed', 'production_unchanged': True})
            return 0
    finally:
        asyncio.run_coroutine_threadsafe(network.aclose(), get_loop()).result(3)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    try:
        result = main(args.live)
    except Exception:
        emit({'status': 'internal_failure', 'details_suppressed': True, 'no_retry': True})
        result = 2
    raise SystemExit(result)
