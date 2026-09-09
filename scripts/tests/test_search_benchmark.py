import sys
import json
import unittest
import urllib.error
import urllib.parse
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


if __name__ == "__main__":
    unittest.main()
