import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ddg_transport import INFO_FIELDS, FIXTURES, SESSION_PROFILES, endpoint_stage, phase_metrics, verify_session_digest


class TransportTests(unittest.TestCase):
    def test_profile_exact_matches(self):
        for profile, digest in SESSION_PROFILES.items():
            verify_session_digest(profile, digest)

    def test_profiles_cannot_cross_match(self):
        with self.assertRaises(RuntimeError):
            verify_session_digest('production', SESSION_PROFILES['candidate-0.16.3'])
        with self.assertRaises(RuntimeError):
            verify_session_digest('candidate-0.16.3', SESSION_PROFILES['production'])

    def test_unknown_profile_or_source_refused(self):
        with self.assertRaises(RuntimeError):
            verify_session_digest('unknown', SESSION_PROFILES['production'])
        with self.assertRaises(RuntimeError):
            verify_session_digest('production', '0' * 64)

    def test_only_allowlisted_numeric_counters_read(self):
        names = list(INFO_FIELDS.values())
        infos = SimpleNamespace(**{name: name for name in names})
        called = []
        def read(name):
            called.append(name)
            return 0.12345678
        metrics = phase_metrics(read, infos)
        self.assertEqual(called, names)
        self.assertTrue(all(v == 0.123457 for v in metrics.values()))
        self.assertFalse(any(any(word in name for word in ('URL', 'IP', 'HEADER', 'COOKIE')) for name in called))

    def test_invalid_values_and_exceptions_not_printed(self):
        infos = SimpleNamespace(**{name: name for name in INFO_FIELDS.values()})
        for value in ('private-response-text', float('nan'), float('inf'), -1, True):
            metrics = phase_metrics(lambda _: value, infos)
            self.assertTrue(all(v is None for v in metrics.values()))
            self.assertNotIn('private', json.dumps(metrics))
        def fail(_):
            raise ValueError('private-url')
        self.assertTrue(all(v is None for v in phase_metrics(fail, infos).values()))

    def test_stage_labels_exclude_query_and_token(self):
        self.assertEqual(endpoint_stage('https://duckduckgo.com/?q=private'), 'token')
        self.assertEqual(endpoint_stage('https://duckduckgo.com/news.js?vqd=private'), 'news')
        self.assertEqual(endpoint_stage('https://example.invalid/news.js?q=private'), 'other')

    def test_fresh_fixtures_not_old_failed_queries(self):
        from ddg_diagnostic import FIXTURES as old
        self.assertEqual(len(FIXTURES), 2)
        self.assertFalse({q for _, q in FIXTURES} & {q for _, q in old})


if __name__ == '__main__':
    unittest.main()
