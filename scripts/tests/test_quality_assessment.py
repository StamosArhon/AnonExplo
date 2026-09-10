import json
from pathlib import Path
import sys
import unittest
import tempfile
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from quality_assessment import FIXTURE_PATH, grade_metrics, orders, passes, validate_grades
import quality_assessment as assessment


class QualityTests(unittest.TestCase):
    def test_split_and_balance(self):
        fixtures = json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))
        seen = set()
        for rows in fixtures.values():
            self.assertEqual(len(rows), 16)
            self.assertEqual(sum(r[2] == 'el' for r in rows), 8)
            for intent in ('explanation', 'technical', 'resource', 'recent'):
                self.assertEqual(sum(r[1] == intent for r in rows), 4)
            for row in rows:
                self.assertNotIn(row[3], seen)
                seen.add(row[3])

    def test_host_cap_stable_and_retains_rows(self):
        rows = [{'url': f'https://a.test/{i}', 'score': i} for i in range(4)]
        rows += [{'url': 'https://b.test/', 'score': 4}, {'url': 'https://c.test/', 'score': 5}]
        actual = orders(rows)
        self.assertEqual(actual['native'], [0, 1, 2, 3, 4])
        self.assertEqual(actual['score'], [5, 4, 3, 2, 1])
        self.assertEqual(actual['host-cap'], [0, 1, 4, 5, 2])

    def test_host_case_and_trailing_dot(self):
        rows = [{'url': 'https://A.TEST./', 'score': 1}, {'url': 'https://a.test/', 'score': 1},
                {'url': 'https://a.test/x', 'score': 1}, {'url': 'https://b.test/', 'score': 1}]
        self.assertEqual(orders(rows)['host-cap'], [0, 1, 3, 2])

    def test_utility_and_facet_union(self):
        self.assertEqual(grade_metrics([0, 1, 2], {0: 2, 1: 1, 2: 0}, {0: 3, 1: 4, 2: 0}),
                         {'utility': .3, 'coverage': 1, 'unrelated': 1, 'full': 1})

    def test_invalid_grading_rejected(self):
        for value in ({'grades': [True], 'facets': [0]}, {'grades': [0], 'facets': [1]},
                      {'grades': [3], 'facets': [0]}, {'grades': [2], 'facets': [8]},
                      {'grades': [2], 'facets': []}, {'grades': [2], 'facets': [0], 'text': 'secret'}):
            with self.assertRaises(ValueError):
                validate_grades(value, 1)

    def test_valid_grading(self):
        validate_grades({'grades': [0, 1, 2], 'facets': [0, 1, 7]}, 3)

    def rows(self):
        return [{'errors': 0, 'seconds': 1, 'language': 'en' if i % 2 else 'el',
                 'quality': {'native': {'utility': .5, 'coverage': .5},
                             'score': {'utility': .7, 'coverage': .5}}} for i in range(16)]

    def test_acceptance_requires_full_healthy_split(self):
        rows = self.rows()
        self.assertTrue(passes(rows, 'score'))
        self.assertFalse(passes(rows[:-1], 'score'))
        rows[0]['errors'] = 1
        self.assertFalse(passes(rows, 'score'))
        rows[0]['errors'] = 0
        rows[0]['seconds'] = 8.1
        self.assertFalse(passes(rows, 'score'))

    def test_ties_and_regressions_fail(self):
        rows = self.rows()
        for row in rows:
            row['quality']['score']['utility'] = .5
        self.assertFalse(passes(rows, 'score'))
        rows = self.rows()
        for row in rows[:3]:
            row['quality']['score']['utility'] = .4
        self.assertFalse(passes(rows, 'score'))

    def test_coverage_regression_fails(self):
        rows = self.rows()
        rows[0]['quality']['score']['coverage'] = 0
        self.assertFalse(passes(rows, 'score'))

    def simulation(self, degraded=False, bad_grade=False):
        with tempfile.TemporaryDirectory() as folder, patch.object(assessment, 'ROOT', Path(folder)), \
                patch.dict(assessment.os.environ, {'ANONEXPLO_QUALITY_PREFLIGHT': 'approved-v1'}), \
                patch.object(assessment.urllib.request, 'build_opener') as factory, \
                patch('builtins.input', return_value='{}' if bad_grade else '{"grades":[2,2,2,2,2],"facets":[7,7,7,7,7]}'), \
                patch.object(assessment.time, 'sleep'), patch.object(assessment, 'emit'):
            config = {'engines': [{'name': name, 'enabled': True, 'categories': ['general']}
                                   for name in ('brave', 'bing', 'yahoo', 'wikipedia')]}
            payload = {'results': [{'url': f'https://site{i}.invalid/SECRET', 'title': 'SECRET',
                                    'content': 'SECRET', 'score': 5-i, 'engines': ['brave']}
                                   for i in range(5)]}
            if degraded:
                payload['unresponsive_engines'] = [['brave', 'timeout']]
            factory.return_value.open.return_value.__enter__.return_value.read.side_effect = [
                json.dumps(config).encode()] + [json.dumps(payload).encode()] * 16
            result = assessment.run()
            saved = (Path(folder) / 'build/quality-assessment-v1.json').read_text()
            self.assertNotIn('SECRET', saved)
            self.assertTrue((Path(folder) / 'build/quality-assessment-v1.attempted').exists())
            return result, json.loads(saved), factory.return_value.open.call_count

    def test_full_development_tie_stops_before_holdout(self):
        code, report, calls = self.simulation()
        self.assertEqual((code, report['status'], calls), (0, 'stop_no_development_gain', 17))
        self.assertEqual(len(report['rows']), 16)

    def test_failure_stops_without_grading_or_retry(self):
        code, report, calls = self.simulation(degraded=True)
        self.assertEqual((code, report['status'], calls), (2, 'stopped_degraded', 2))
        self.assertEqual(report['rows'], [])

    def test_invalid_grades_stop_without_next_query(self):
        code, report, calls = self.simulation(bad_grade=True)
        self.assertEqual((code, report['status'], calls), (2, 'stopped_internal_or_grading_failure', 2))


if __name__ == '__main__':
    unittest.main()
