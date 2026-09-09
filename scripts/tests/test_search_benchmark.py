import sys
import json
import unittest
import urllib.error
import urllib.parse
import datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import search_benchmark as benchmark


class BenchmarkTests(unittest.TestCase):
    def test_browser_request_uses_unmodified_query_and_no_selectors(self):
        request = benchmark.make_request(8085, benchmark.FIXTURES[3], "browser")
        url = urllib.parse.urlsplit(request.full_url)
        self.assertEqual(url.netloc, "127.0.0.1:8085")
        self.assertEqual(urllib.parse.parse_qs(url.query), {"q": [benchmark.FIXTURES[3][1]], "format": ["json"]})
        self.assertFalse(request.has_header("Cookie"))

    def test_explicit_language(self):
        request = benchmark.make_request(8085, benchmark.FIXTURES[3], "explicit")
        self.assertEqual(urllib.parse.parse_qs(urllib.parse.urlsplit(request.full_url).query)["language"], ["el"])

    def test_domain_boundary_and_ranking(self):
        result = benchmark.metrics({"results": [
            {"url": "https://notpython.org/a", "engines": ["brave"]},
            {"url": "https://docs.python.org/3", "engines": ["bing", "brave"]},
            {"url": "https://python.org.attacker.example/", "engines": ["bing"]},
        ]}, "python.org")
        self.assertEqual(result["expected_rank"], 2)
        self.assertEqual(result["reciprocal_rank"], .5)
        self.assertEqual(result["contributing_engines"], 2)

    def test_malformed_url_does_not_change_positions(self):
        result = benchmark.metrics({"results": [None, {"url": "http://["}, {"url": "https://python.org"}]}, "python.org")
        self.assertEqual(result["expected_rank"], 3)
        self.assertEqual(result["domains"], 1)

    def test_no_payloads_in_metrics(self):
        result = benchmark.metrics({"results": [], "unresponsive_engines": [["brave", "SECRET QUERY"]]}, "python.org")
        self.assertNotIn("SECRET", str(result))
        self.assertEqual(result["engine_errors"], 1)
        self.assertFalse(result["expected_top5"])

    def test_redirect_refused(self):
        with self.assertRaises(urllib.error.HTTPError) as raised:
            benchmark.NoRedirect().redirect_request(benchmark.make_request(8085, benchmark.FIXTURES[0], "browser"), None, 302, "", {}, "https://example.com")
        raised.exception.close()

    def test_failure_stops_without_echoing_exception(self):
        with patch.object(benchmark.urllib.request, "build_opener") as opener, patch("builtins.print") as output:
            opener.return_value.open.side_effect = ValueError("SECRET QUERY")
            self.assertEqual(benchmark.run(8085, "browser", 6, pause=0), 2)
            self.assertEqual(opener.return_value.open.call_count, 1)
            self.assertNotIn("SECRET", str(output.call_args_list))

    def test_engine_degradation_stops_without_retry(self):
        with patch.object(benchmark.urllib.request, "build_opener") as opener, patch("builtins.print") as output:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value = json.dumps({
                "results": [{"url": "https://behance.net"}],
                "unresponsive_engines": [["brave", "SECRET QUERY"]],
            }).encode()
            self.assertEqual(benchmark.run(8085, "browser", 6, pause=0), 2)
            self.assertEqual(opener.return_value.open.call_count, 1)
            self.assertNotIn("SECRET", str(output.call_args_list))

    def test_sixth_result_does_not_count_as_top_five(self):
        rows = [{"url": "https://example.com"}] * 5 + [{"url": "https://python.org"}]
        result = benchmark.metrics({"results": rows}, "python.org")
        self.assertFalse(result["expected_top5"])
        self.assertEqual(result["expected_rank"], 6)

    def test_successful_run_reports_summary(self):
        with patch.object(benchmark.urllib.request, "build_opener") as opener, patch("builtins.print") as output:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value = b'{"results":[{"url":"https://behance.net"}]}'
            self.assertEqual(benchmark.run(8085, "browser", 1, pause=0), 0)
            summary = json.loads(output.call_args.args[0])
            self.assertEqual(summary['top5_matches'], 1)
            self.assertEqual(summary['samples'], 1)

    def test_news_category_and_month_are_separate_cases(self):
        for fixture, filtered in ((benchmark.NEWS[0], False), (benchmark.NEWS_MONTH[0], True)):
            request = benchmark.make_request(8085, fixture, "browser")
            params = urllib.parse.parse_qs(urllib.parse.urlsplit(request.full_url).query)
            self.assertEqual(params['categories'], ['news'])
            self.assertEqual('time_range' in params, filtered)

    def test_single_engine_never_unions_category_recipients(self):
        request = benchmark.make_request(8085, benchmark.NEWS[0], "explicit", 'brave.news')
        params = urllib.parse.parse_qs(urllib.parse.urlsplit(request.full_url).query)
        self.assertEqual(params['engines'], ['brave.news'])
        self.assertNotIn('categories', params)
        self.assertEqual(params['language'], ['en'])

    def test_unknown_engine_rejected(self):
        with self.assertRaises(ValueError):
            benchmark.make_request(8085, benchmark.FIXTURES[0], "browser", 'SECRET QUERY')

    def test_error_names_and_reasons_cannot_leak_payloads(self):
        result = benchmark.error_metrics([['SECRET QUERY', 'SECRET URL'],
                                          ['brave', 'too many requests'], ['bing', 'timeout'], None])
        self.assertNotIn('SECRET', str(result))
        self.assertEqual(result[1], {'engine': 'brave', 'kind': 'rate_limited'})
        self.assertEqual(result[2]['kind'], 'timeout')

    def test_unknown_result_engine_is_sanitized(self):
        result = benchmark.metrics({'results': [{'url': 'https://example.com', 'engines': ['SECRET']}]}, None)
        self.assertEqual(result['engine_result_counts'], {'unknown': 1})
        self.assertNotIn('SECRET', str(result))

    def test_review_is_bounded_plain_text_without_urls(self):
        result = benchmark.top5_review({'results': [{'title': '<b>A</b>\x1b\n' + 'x' * 400,
                 'content': 'y' * 1000, 'url': 'https://SECRET.example', 'engines': ['brave']}] * 8})
        self.assertEqual(len(result), 5)
        self.assertLessEqual(len(result[0]['title']), 180)
        self.assertLessEqual(len(result[0]['snippet']), 400)
        self.assertNotIn('SECRET', str(result))
        self.assertNotIn('\x1b', str(result))
        self.assertNotIn('<b>', str(result))

    def test_freshness_unknown_old_future_and_naive(self):
        now = datetime.datetime(2026, 9, 10, tzinfo=datetime.timezone.utc)
        rows = [{'publishedDate': value} for value in
                ('2026-09-09T00:00:00Z', '2020-01-01T00:00:00Z', None,
                 '2027-01-01T00:00:00Z', '2026-09-01T00:00:00')]
        self.assertEqual(benchmark.freshness_metrics(rows, now),
                         {'top5_dated': 4, 'top5_within_31_days': 2, 'top5_future_dates': 1})

    def test_informational_cases_have_no_expected_domain(self):
        self.assertTrue(all(f[3] is None and f[6] for f in benchmark.INFORMATIONAL))
        self.assertEqual({f[2] for f in benchmark.INFORMATIONAL}, {'en', 'el'})

    def test_samples_cannot_silently_exceed_suite(self):
        with self.assertRaises(ValueError):
            benchmark.run(8085, 'browser', 6, suite='news')

    def mock_responses(self, opener, catalogue, payload):
        response = opener.return_value.open.return_value.__enter__.return_value
        response.read.side_effect = [json.dumps(catalogue).encode(), json.dumps(payload).encode()]

    def test_informational_summary_does_not_claim_navigation_score(self):
        with patch.object(benchmark.urllib.request, 'build_opener') as opener, patch('builtins.print') as output:
            self.mock_responses(opener, {'engines': [{'name': 'brave', 'enabled': True, 'categories': ['general']}]},
                                {'results': [{'url': 'https://example.com', 'title': 'SECRET', 'engines': ['brave']}]})
            self.assertEqual(benchmark.run(8085, 'browser', 1, suite='informational'), 0)
            summary = json.loads(output.call_args.args[0])
            self.assertNotIn('top5_matches', summary)
            self.assertNotIn('SECRET', str(output.call_args_list))

    def test_wrong_category_rejected_before_search(self):
        with patch.object(benchmark.urllib.request, 'build_opener') as opener, patch('builtins.print'):
            self.mock_responses(opener, {'engines': [{'name': 'brave', 'categories': ['general']}]}, {})
            self.assertEqual(benchmark.run(8085, 'browser', 1, suite='news', engine='brave'), 2)
            self.assertEqual(opener.return_value.open.call_count, 1)

    def test_unsupported_filter_rejected_before_search(self):
        with patch.object(benchmark.urllib.request, 'build_opener') as opener, patch('builtins.print') as output:
            self.mock_responses(opener, {'engines': [{'name': 'brave.news', 'categories': ['news'], 'time_range_support': False}]}, {})
            self.assertEqual(benchmark.run(8085, 'browser', 1, suite='news-month', engine='brave.news'), 2)
            self.assertEqual(opener.return_value.open.call_count, 1)
            self.assertIn('skipped_unsupported_time_filter', str(output.call_args_list))

    def test_unrequested_contributor_stops_without_payload_dump(self):
        with patch.object(benchmark.urllib.request, 'build_opener') as opener, patch('builtins.print') as output:
            self.mock_responses(opener, {'engines': [{'name': 'brave', 'categories': ['general']}]},
                                {'results': [{'url': 'https://SECRET.example', 'engines': ['bing']}]})
            self.assertEqual(benchmark.run(8085, 'browser', 1, engine='brave'), 2)
            self.assertNotIn('SECRET', str(output.call_args_list))

    def test_oversize_response_stops_without_dump(self):
        with patch.object(benchmark.urllib.request, 'build_opener') as opener, patch('builtins.print') as output:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value = b'x' * 4_000_001
            self.assertEqual(benchmark.run(8085, 'browser', 1), 2)
            self.assertIn('request_failed', str(output.call_args_list))


if __name__ == "__main__":
    unittest.main()
