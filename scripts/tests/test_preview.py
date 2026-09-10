import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preview_server import checked_request, checked_domains, evaluate


def data():
    return {'query': 'public fixture', 'results': [
        {'url': 'https://other.example/a', 'title': 'A', 'content': 'A', 'score': 1.05},
        {'url': 'https://example.org/a', 'title': 'B', 'content': 'B', 'score': 1.0}]}


class PreviewTests(unittest.TestCase):
    def test_relevant_promotes_and_does_not_mutate(self):
        original = data()
        before = copy.deepcopy(original)
        value = evaluate(original, {'example.org'}, lambda pairs: [.85, .95])
        self.assertEqual(value['order'], [1, 0])
        self.assertEqual(value['promoted'], 1)
        self.assertEqual(original, before)

    def test_irrelevant_never_promotes(self):
        self.assertEqual(evaluate(data(), {'example.org'}, lambda pairs: [.95, .01])['order'], [0, 1])

    def test_stronger_result_protected(self):
        self.assertEqual(evaluate(data(), {'example.org'}, lambda pairs: [.99, .8])['order'], [0, 1])

    def test_no_matches_skips_model(self):
        score = Mock()
        self.assertEqual(evaluate(data(), {'elsewhere.org'}, score)['status'], 'no_preferred_matches')
        score.assert_not_called()

    def test_invalid_scores_rejected(self):
        for scores in ([float('nan'), .9], [True, .9], [2, .9], [.9]):
            with self.assertRaises(ValueError):
                evaluate(data(), {'example.org'}, lambda p: scores)

    def test_request_bounds(self):
        for field, value in [('query', ''), ('query', 'a'*513), ('results', []), ('results', data()['results']*13)]:
            payload = data()
            payload[field] = value
            with self.assertRaises(ValueError):
                checked_request(payload)
        for key, value in [('url','a'*2049), ('content','a'*401), ('title','a'*181), ('score',True), ('score',float('inf'))]:
            payload = data()
            payload['results'][0][key] = value
            with self.assertRaises(ValueError):
                checked_request(payload)

    def test_domains(self):
        self.assertEqual(checked_domains(['example.org']), {'example.org'})
        for domains in ([], ['https://example.org'], ['a.org/path'], ['-a.org']):
            with self.assertRaises(ValueError):
                checked_domains(domains)

    def test_domain_boundary(self):
        payload = data()
        payload['results'][1]['url'] = 'https://notexample.org/a'
        score = Mock()
        self.assertEqual(evaluate(payload, {'example.org'}, score)['status'], 'no_preferred_matches')
        score.assert_not_called()


if __name__ == '__main__':
    unittest.main()
