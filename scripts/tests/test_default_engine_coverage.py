import unittest
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from search_benchmark import DEFAULT_AUDIT, make_request, metrics, top5_attribution


class DefaultCoverageTests(unittest.TestCase):
    def test_credit_is_deduplicated_not_ablation(self):
        rows = [{'engines': ['brave', 'brave', 'yahoo']}, {'engines': ['bing']}]
        self.assertEqual(top5_attribution(rows), {
            'brave': {'credited': 1, 'sole_credit': 0},
            'yahoo': {'credited': 1, 'sole_credit': 0},
            'bing': {'credited': 1, 'sole_credit': 1}})

    def test_only_top_five_and_allowlisted_names(self):
        rows = [{'engines': ['private-query-url']}] * 5 + [{'engines': ['bing']}]
        self.assertEqual(top5_attribution(rows), {'unknown': {'credited': 5, 'sole_credit': 5}})

    def test_empty_and_non_result_rows(self):
        self.assertEqual(top5_attribution([None, {}, {'engines': []}]), {})

    def test_public_fixture_balance_and_default_selection(self):
        self.assertEqual([f[2] for f in DEFAULT_AUDIT], ['en', 'en', 'el', 'el'])
        self.assertEqual(len({f[0] for f in DEFAULT_AUDIT}), 4)
        for fixture in DEFAULT_AUDIT:
            request = make_request(8085, fixture, 'browser')
            params = parse_qs(urlsplit(request.full_url).query)
            self.assertEqual(set(params), {'q', 'format'})
            self.assertNotIn('Cookie', request.headers)

    def test_host_suffix_and_metrics_do_not_leak_payload(self):
        payload = {'results': [
            {'url': 'https://docs.python.org.evil.invalid/private', 'title': 'private', 'engines': ['brave']},
            {'url': 'https://docs.python.org/3/', 'engines': ['yahoo']}]}
        result = metrics(payload, 'docs.python.org')
        self.assertEqual(result['expected_rank'], 2)
        self.assertNotIn('private', str(result))


if __name__ == '__main__':
    unittest.main()
