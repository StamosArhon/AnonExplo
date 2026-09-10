import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reranker_gate import gated_order, preferred


class GateTests(unittest.TestCase):
    def test_domain_boundaries(self):
        for url in ('https://preferred.example/', 'https://www.preferred.example/a'):
            self.assertTrue(preferred(url, ['preferred.example']))
        for url in ('https://notpreferred.example/', 'https://preferred.example.evil/',
                    'https://preferred.example@evil.example/', 'file://preferred.example/a', None):
            self.assertFalse(preferred(url, ['preferred.example']))

    def rows(self):
        return [{'url': 'https://ordinary.example/', 'score': 10},
                {'url': 'https://preferred.example/', 'score': 9}]

    def test_irrelevant_preference_does_not_move(self):
        self.assertEqual(gated_order(self.rows(), [.9, .1], ['preferred.example']), [0, 1])

    def test_relevant_preference_gets_modest_boost(self):
        self.assertEqual(gated_order(self.rows(), [.85, .9], ['preferred.example']), [1, 0])

    def test_better_match_not_displaced(self):
        self.assertEqual(gated_order(self.rows(), [.99, .8], ['preferred.example']), [0, 1])

    def test_invalid_scores_fail_unchanged(self):
        for scores in ([float('nan'), .9], [.9], [True, .9], [.9, 2]):
            self.assertEqual(gated_order(self.rows(), scores, ['preferred.example']), [0, 1])

    def test_low_native_score_not_elevated(self):
        rows = self.rows()
        rows[1]['score'] = 1
        self.assertEqual(gated_order(rows, [.8, .9], ['preferred.example']), [0, 1])

    def test_maximum_two_positions(self):
        rows = [{'url': 'https://ordinary.example/', 'score': 10}] * 4 + [{'url': 'https://preferred.example/', 'score': 10}]
        self.assertEqual(gated_order(rows, [.9] * 5, ['preferred.example']), [0, 1, 4, 2, 3])
