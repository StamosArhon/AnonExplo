import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ddg_diagnostic import FIXTURES, Trace, observe_native


class DiagnosticTests(unittest.TestCase):
    def test_return_value_and_arguments_untouched(self):
        trace, sentinel = Trace(), object()
        received = []
        def original(*args, **kwargs):
            received.append((args, kwargs))
            return sentinel
        self.assertIs(trace.observe('stage', original)('private-query', token='private-token'), sentinel)
        self.assertEqual(received, [(('private-query',), {'token': 'private-token'})])
        self.assertNotIn('private-', json.dumps(trace.snapshot()))

    def test_exception_identity_preserved_without_text(self):
        trace = Trace()
        error = ValueError('private-token-and-url')
        def fail():
            raise error
        with self.assertRaises(ValueError) as caught:
            trace.observe('stage', fail)()
        self.assertIs(caught.exception, error)
        self.assertNotIn('private', json.dumps(trace.snapshot()))
        self.assertEqual(trace.snapshot()[-1]['kind'], 'other')

    def test_trace_bounded_and_snapshot_independent(self):
        trace = Trace()
        for i in range(100):
            trace.add({'count': i})
        snapshot = trace.snapshot()
        self.assertEqual(len(snapshot), 40)
        snapshot[0]['count'] = -1
        self.assertEqual(trace.snapshot()[0]['count'], 0)

    def test_wrappers_restore_native_functions_and_budget(self):
        def get(*args, **kwargs):
            return SimpleNamespace(status_code=200, text='private-token')
        def budget(start, kwargs):
            kwargs['timeout'] = 6
            return 5.5
        engine = SimpleNamespace(get=get, get_vqd=lambda **kw: 'private-token',
                                 fetch_vqd=lambda **kw: 'private-token', request=lambda *a: None,
                                 response=lambda *a: [])
        network = SimpleNamespace(get=get, _get_timeout=budget)
        trace = Trace()
        with observe_native(engine, network, trace):
            self.assertEqual(engine.get_vqd(), 'private-token')
            self.assertEqual(engine.fetch_vqd(), 'private-token')
            self.assertEqual(engine.get().status_code, 200)
            self.assertEqual(network.get().status_code, 200)
            kwargs = {}
            self.assertEqual(network._get_timeout(0, kwargs), 5.5)
            self.assertEqual(kwargs, {'timeout': 6})
        self.assertIs(engine.get, get)
        self.assertIs(network.get, get)
        self.assertIs(network._get_timeout, budget)
        self.assertNotIn('private', json.dumps(trace.snapshot()))

    def test_fixed_distinct_bounded_fixtures(self):
        self.assertEqual(len(FIXTURES), 2)
        self.assertEqual(len({q for _, q in FIXTURES}), 2)
        self.assertTrue(all(len(q) < 100 for _, q in FIXTURES))


if __name__ == '__main__':
    unittest.main()
