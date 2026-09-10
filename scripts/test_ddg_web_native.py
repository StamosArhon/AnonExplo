"""Exact upstream adapter request/response tests, with mock-only transport.

Run only through the network-disabled PowerShell wrapper. No result payloads,
URLs, query strings or exception tracebacks are printed by this runner.
"""
import hashlib
import importlib.util
import json
import logging
import unittest
from pathlib import Path

from ddg_diagnostic import verify_sources
from ddg_web_guard import CandidateRejected, GuardedWeb, SOURCE_SHA256

logging.disable(logging.CRITICAL)
SOURCE = Path('/upstream/duckduckgo_web.py')


class Response:
    def __init__(self, text, status=200):
        self.text, self.status_code = text, status

    def json(self):
        return json.loads(self.text)


def landing(url='https://links.duckduckgo.com/d.js?vqd=fixture'):
    return Response(f'<html><link id="deep_preload_link" href="{url}"></html>')


def results():
    # Synthetic payload, not fetched provider results. Never persisted/output.
    return Response(json.dumps({'results': [{'u': 'https://example.invalid/', 't': 'Fixture',
                                            'a': 'Synthetic', 'n': '/d.js?p=2'}]}))


def challenge(url='/d.js?jsa='):
    return Response("let jsa = 7; let f = function(num) {return num * 3;}; "
                    f"jsa = f(jsa); DDG.deep.initialize('{url}')")


class NativeTests(unittest.TestCase):
    def candidate(self, responses, delays=None):
        spec = importlib.util.spec_from_file_location('reviewed_ddg_web', SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.logger = logging.getLogger('offline-disabled')
        self.now, self.sent = 0.0, []
        queue = list(responses)
        elapsed = list(delays or [0] * len(queue))

        def transport(url, **kwargs):
            self.sent.append((url, kwargs))
            self.now += elapsed.pop(0)
            value = queue.pop(0)
            if isinstance(value, Exception):
                raise value
            return value

        return GuardedWeb(module, transport, clock=lambda: self.now)

    def test_native_roundtrip(self):
        candidate = self.candidate([landing(), results()])
        result = candidate.run('public fixture')
        self.assertEqual(type(result).__name__, 'EngineResults')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].url, 'https://example.invalid/')
        self.assertEqual(result[0].title, 'Fixture')
        self.assertEqual(len(self.sent), 2)
        self.assertIn('/d.js?o=json&', self.sent[1][0])
        self.assertIsNone(candidate.module.CACHE.get('nextpage_url|public fixture|2'))

    def test_one_guarded_followup(self):
        candidate = self.candidate([landing(), challenge(), results()])
        candidate.run('public fixture')
        self.assertEqual(len(self.sent), 3)
        self.assertEqual(self.sent[2][0], 'https://links.duckduckgo.com/d.js?jsa=21')

    def test_foreign_preload_stops(self):
        candidate = self.candidate([landing('https://other.invalid/d.js?x=1')])
        with self.assertRaises(CandidateRejected):
            candidate.run('public fixture')
        self.assertEqual(len(self.sent), 1)

    def test_foreign_challenge_stops(self):
        candidate = self.candidate([landing(), challenge('//other.invalid/d.js?x=')])
        with self.assertRaises(CandidateRejected):
            candidate.run('public fixture')
        self.assertEqual(len(self.sent), 2)

    def test_redirects_stop_at_each_stage(self):
        for sequence in [[Response('', 302)], [landing(), Response('', 302)],
                         [landing(), challenge(), Response('', 302)]]:
            candidate = self.candidate(sequence)
            with self.assertRaises(CandidateRejected):
                candidate.run('public fixture')
            self.assertEqual(len(self.sent), len(sequence))

    def test_transport_policy_and_header_filter(self):
        candidate = self.candidate([landing(), challenge(), results()])
        candidate.run('public fixture', {'User-Agent': 'Fixture', 'Cookie': 'private',
                                        'Authorization': 'private', 'Host': 'other.invalid'})
        for _, args in self.sent:
            self.assertFalse(args['allow_redirects'])
            self.assertEqual(args['max_redirects'], 0)
            self.assertTrue(args['verify'])
            self.assertFalse(args['default_headers'])
            self.assertEqual(args['impersonate'], 'firefox')
            for name in ['Cookie', 'Authorization', 'Host']:
                self.assertNotIn(name, args['headers'])

    def test_deadline_shared(self):
        candidate = self.candidate([landing(), challenge(), results()], [1.5, 2, 1])
        candidate.run('public fixture')
        self.assertEqual([args['timeout'] for _, args in self.sent], [2, 4.5, 2.5])

    def test_expired_response_stops(self):
        candidate = self.candidate([landing(), challenge()], [1, 5])
        with self.assertRaises(CandidateRejected):
            candidate.run('public fixture')
        self.assertEqual(len(self.sent), 2)

    def test_repeated_challenge_stops(self):
        candidate = self.candidate([landing(), challenge(), challenge()])
        with self.assertRaises(CandidateRejected):
            candidate.run('public fixture')
        self.assertEqual(len(self.sent), 3)

    def test_transport_failure_not_retried(self):
        candidate = self.candidate([TimeoutError('synthetic')])
        with self.assertRaises(TimeoutError):
            candidate.run('public fixture')
        self.assertEqual(len(self.sent), 1)

    def test_post_buffer_bound(self):
        candidate = self.candidate([Response('x' * 1048577)])
        with self.assertRaises(CandidateRejected):
            candidate.run('public fixture')

    def test_instance_not_reusable(self):
        candidate = self.candidate([landing(), results()])
        candidate.run('public fixture')
        with self.assertRaises(CandidateRejected):
            candidate.run('public fixture')
        self.assertEqual(len(self.sent), 2)

    def test_missing_preload_stops(self):
        candidate = self.candidate([Response('<html></html>')])
        with self.assertRaises(CandidateRejected):
            candidate.run('public fixture')
        self.assertEqual(len(self.sent), 1)

    def test_invalid_query_never_requests(self):
        for query in ['', 'x' * 500, None]:
            candidate = self.candidate([])
            with self.assertRaises(CandidateRejected):
                candidate.run(query)
            self.assertEqual(len(self.sent), 0)

    def test_expired_before_request(self):
        candidate = self.candidate([])
        candidate.deadline = 6
        self.now = 6
        with self.assertRaises(CandidateRejected):
            candidate.fetch('https://duckduckgo.com/')
        self.assertEqual(len(self.sent), 0)

    def test_header_injection_rejected(self):
        for headers in [{'User-Agent': 'Fixture\r\nCookie: private'},
                        {'Referer': 'https://other.invalid/'}]:
            candidate = self.candidate([])
            with self.assertRaises(CandidateRejected):
                candidate.run('public fixture', headers)
            self.assertEqual(len(self.sent), 0)

    def test_empty_results(self):
        candidate = self.candidate([landing(), Response('{"results": []}')])
        self.assertEqual(len(candidate.run('public fixture')), 0)
        self.assertEqual(len(self.sent), 2)

    def test_rate_limit_not_retried(self):
        candidate = self.candidate([landing(), Response('', 429)])
        with self.assertRaises(CandidateRejected):
            candidate.run('public fixture')
        self.assertEqual(len(self.sent), 2)


if __name__ == '__main__':
    try:
        verify_sources()
        if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256:
            raise ValueError('Source mismatch')
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(NativeTests)
        report = unittest.TestResult()
        suite.run(report)
        print(json.dumps({'tests': report.testsRun, 'failures': len(report.failures),
                          'errors': len(report.errors),
                          'failed_tests': [case._testMethodName for case, _ in report.failures + report.errors]}))
        raise SystemExit(0 if report.wasSuccessful() else 1)
    except Exception:
        print('FAIL: offline web candidate setup; details suppressed')
        raise SystemExit(1) from None
