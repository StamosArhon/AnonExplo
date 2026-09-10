"""Offline tests against actual pinned source; requires network=none."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
import unittest

from news_candidate import FIXTURES, verify_sources, token_candidate, news_score_candidate
from searx.engines import engines
from searx.engines import duckduckgo_extra as ddg
from searx.network import _get_timeout, THREADLOCAL
from searx.result_types import MainResult
from searx.results import ResultContainer


class CandidateTests(unittest.TestCase):
    def setUp(self):
        engines['probe-text'] = SimpleNamespace(name='probe-text', weight=1, categories=['news'], paging=False)
        engines['probe-image'] = SimpleNamespace(name='probe-image', weight=1, categories=['news'], paging=False)

    def container(self):
        container = ResultContainer()
        with patch('searx.results.histogram_observe'), patch('searx.results.counter_add'):
            container.extend('probe-text', [MainResult(url=f'https://example.invalid/{i}', title='Synthetic') for i in range(9)])
            container.extend('probe-image', [MainResult(url='https://example.invalid/image', title='Synthetic',
                                                      thumbnail='https://example.invalid/thumb')])
            native = container.get_ordered_results()
        return container, native

    def test_source_fingerprints(self):
        verify_sources()

    def test_rank_and_ties(self):
        container, native = self.container()
        candidate = news_score_candidate(container, native)
        self.assertEqual([r.engine for r in candidate[:2]], ['probe-text', 'probe-image'])
        self.assertEqual([r.score for r in candidate], sorted((r.score for r in native), reverse=True))

    def test_preserve_rows_thumbnails_native_cache(self):
        container, native = self.container()
        candidate = news_score_candidate(container, native)
        self.assertEqual({id(r) for r in native}, {id(r) for r in candidate})
        self.assertEqual(candidate[1].thumbnail, 'https://example.invalid/thumb')
        self.assertIs(container.get_ordered_results(), native)
        self.assertEqual(native[-1].engine, 'probe-image')

    def test_dates_not_invented_or_rescored(self):
        container, native = self.container()
        native[0].publishedDate = datetime(2000, 1, 1, tzinfo=timezone.utc)
        candidate = news_score_candidate(container, native)
        self.assertEqual(candidate[0].publishedDate.year, 2000)
        self.assertIsNone(candidate[1].publishedDate)
        self.assertEqual(candidate[0].score, candidate[1].score)

    def test_degraded_unchanged(self):
        container, native = self.container()
        container.unresponsive_engines.add(('probe-text', 'timeout', False))
        self.assertIs(news_score_candidate(container, native), native)

    def test_other_categories_unchanged(self):
        container, native = self.container()
        native[0].category = 'general'
        self.assertIs(news_score_candidate(container, native), native)

    def test_invalid_score_rejected(self):
        container, native = self.container()
        native[0].score = float('nan')
        with self.assertRaises(ValueError):
            news_score_candidate(container, native)

    def test_token_only_timeout_changed(self):
        candidate = token_candidate(ddg)
        response = SimpleNamespace(status_code=200, text='vqd="synthetic-value"')
        with patch.object(ddg, 'logger', Mock(), create=True), patch.object(ddg, 'get', return_value=response) as get, \
             patch.object(ddg, 'set_vqd') as cache:
            params = {'headers': {'User-Agent': 'Synthetic'}}
            self.assertEqual(candidate('synthetic query', params), 'synthetic-value')
            self.assertEqual(get.call_count, 1)
            self.assertEqual(get.call_args.kwargs['timeout'], 4)
            self.assertEqual(get.call_args.kwargs['headers'], params['headers'])
            cache.assert_called_once_with(query='synthetic query', value='synthetic-value', params=params)

    def test_no_retry_on_token_failure(self):
        candidate = token_candidate(ddg)
        with patch.object(ddg, 'logger', Mock(), create=True), patch.object(ddg, 'get', side_effect=TimeoutError) as get:
            with self.assertRaises(TimeoutError):
                candidate('synthetic query', {'headers': {}})
            self.assertEqual(get.call_count, 1)

    def test_missing_token_not_invented(self):
        candidate = token_candidate(ddg)
        with patch.object(ddg, 'logger', Mock(), create=True), \
             patch.object(ddg, 'get', return_value=SimpleNamespace(status_code=200, text='No token')), \
             patch.object(ddg, 'set_vqd') as cache:
            self.assertEqual(candidate('synthetic query', {'headers': {}}), '')
            cache.assert_not_called()

    def test_native_total_budget_remaining(self):
        # Network wait uses elapsed time from the engine start, not a fresh
        # six seconds after spending time in token acquisition.
        with patch.object(THREADLOCAL, 'timeout', 6, create=True), \
             patch('searx.network.default_timer', return_value=103.5):
            self.assertAlmostEqual(_get_timeout(100, {}), 2.7)

    def test_frozen_distinct_queries(self):
        from search_benchmark import SUITES
        previous = {f[1] for suite in SUITES.values() for f in suite}
        self.assertEqual(len({f[1] for f in FIXTURES}), 4)
        self.assertFalse(previous & {f[1] for f in FIXTURES})


if __name__ == '__main__':
    unittest.main()
