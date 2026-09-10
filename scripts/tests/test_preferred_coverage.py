import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preferred_coverage import CoverageBudget, relevance_order
from preview_server import evaluate_v2


def row(host='other.example'):
    return {'url': 'https://' + host + '/a', 'title': 'Public fixture', 'content': 'Authored text', 'score': 1}


class CoverageTests(unittest.TestCase):
    def test_relevance_not_native_score(self):
        rows = [row(), row('example.org')]
        rows[0]['score'] = 100
        rows[1]['score'] = .001
        self.assertEqual(relevance_order(rows, [.01, .95], {'example.org'}, 2)['order'], [1, 0])

    def test_small_preference_not_irrelevant_boost(self):
        rows = [row(), row('example.org')]
        for values, order in [([.9, .89], [1, 0]), ([.95, .9], [0, 1]), ([.1, .09], [0, 1])]:
            self.assertEqual(relevance_order(rows, values, {'example.org'}, 2)['order'], order)

    def test_admission_and_host_boundary(self):
        rows = [row(), row('example.org'), row('notexample.org'), row('example.org')]
        result = relevance_order(rows, [.1, .79, .99, .9], {'example.org'}, 1)
        self.assertEqual(result['order'], [3, 0])
        self.assertEqual(result['added'], 1)

    def test_no_preferred_still_ranks(self):
        value = evaluate_v2({'query': 'fixture', 'results': [row(), row()], 'native_count': 2}, set(), lambda p: [.1, .9])
        self.assertEqual(value['order'], [1, 0])

    def test_request_limits(self):
        for count, size in [(True, 2), (0, 2), (3, 2), (25, 25), (24, 33), (1, 10)]:
            with self.assertRaises(ValueError):
                evaluate_v2({'query': 'fixture', 'results': [row()]*size, 'native_count': count}, set(), lambda p: [.9]*len(p))
        value = evaluate_v2({'query': 'fixture', 'results': [row('example.org')]*32, 'native_count': 24}, {'example.org'}, lambda p: [.9]*len(p))
        self.assertEqual(len(value['order']), 32)

    def test_bad_scores(self):
        for values in [[float('nan')], [True], [], [1.1]]:
            with self.assertRaises(ValueError):
                relevance_order([row()], values, set(), 1)

    def test_plan_limits_and_expiry(self):
        budget = CoverageBudget()
        domains = {f'{i}.example' for i in range(18)}
        plan = budget.plan(domains, 100)
        self.assertEqual([len(g) for g in plan['groups']], [9, 9])
        self.assertEqual(set(sum(plan['groups'], [])), domains)
        self.assertEqual(budget.plan(domains, 159)['groups'], [])
        self.assertEqual(budget.plan(domains, 160)['status'], 'ready')
        self.assertEqual(CoverageBudget().plan({f'{i}.example' for i in range(19)})['status'], 'source_limit')

    def test_tabs_share_allowance(self):
        budget = CoverageBudget()
        with ThreadPoolExecutor(8) as pool:
            values = list(pool.map(lambda _: budget.plan({'example.org'}, 100), range(8)))
        self.assertEqual(sum(v['status'] == 'ready' for v in values), 1)


if __name__ == '__main__': unittest.main()
