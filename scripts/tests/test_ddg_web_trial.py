import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ddg_web_trial import FIXTURES, acceptable, grade


class TrialTests(unittest.TestCase):
    def test_fixture_shape(self):
        self.assertEqual(len(FIXTURES), 3)
        self.assertEqual(len({query for _, query, _ in FIXTURES}), 3)

    def test_expected_subdomain(self):
        value = grade([SimpleNamespace(url='https://www.openlibrary.org/')], 'openlibrary.org')
        self.assertEqual(value['expected_rank'], 1)

    def test_suffix_spoof(self):
        self.assertFalse(grade([SimpleNamespace(url='https://fakeopenlibrary.org/')], 'openlibrary.org')['expected_top5'])

    def test_top5_only(self):
        rows = [SimpleNamespace(url='https://example.invalid/')] * 5 + [SimpleNamespace(url='https://openlibrary.org/')]
        self.assertIsNone(grade(rows, 'openlibrary.org')['expected_rank'])

    def test_errors_stop(self):
        self.assertFalse(acceptable({'results': 10, 'expected_top5': True}, ['Timeout']))

    def test_empty_or_missed_target_stop(self):
        self.assertFalse(acceptable({'results': 0, 'expected_top5': False}, []))
        self.assertFalse(acceptable({'results': 10, 'expected_top5': False}, []))

    def test_success(self):
        self.assertTrue(acceptable({'results': 5, 'expected_top5': True}, []))
