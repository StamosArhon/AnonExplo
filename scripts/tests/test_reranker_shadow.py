import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reranker_shadow import checked_domains, checked_scores
from reranker_shadow_worker import checked_pairs


class ShadowTests(unittest.TestCase):
    def test_domains(self):
        self.assertEqual(checked_domains(['example.org']), {'example.org'})
        for value in ([], ['https://example.org'], ['example.org/path'], ['a@b.org'], ['EXAMPLE.org'], ['-a.org']):
            with self.assertRaises(ValueError):
                checked_domains(value)

    def test_scores(self):
        self.assertEqual(checked_scores([.1, .9], 2), [.1, .9])
        for value in ([float('nan')], [True], [2], [], None):
            with self.assertRaises(ValueError):
                checked_scores(value, 1)

    def test_pairs(self):
        self.assertEqual(checked_pairs([['q', 'd']]), [['q', 'd']])
        for value in ([], [['q','d']]*25, [['q', 1]], [['q', 'a'*601]], [['q']], {}):
            with self.assertRaises(ValueError):
                checked_pairs(value)


if __name__ == '__main__':
    unittest.main()
