import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ddg_web_guard import CandidateRejected, NoCache, challenge_url, checked_url


def challenge(destination='/d.js?jsa=', body='return num * 3;', operations='jsa = f(jsa);', initial='7'):
    return (f'let jsa = {initial}; let f = function(num) {{{body}}}; '
            f"{operations} DDG.deep.initialize('{destination}')")


class GuardTests(unittest.TestCase):
    def test_exact_destinations(self):
        for url, first in [('https://duckduckgo.com/?q=fixture', True),
                           ('https://links.duckduckgo.com/d.js?x=1', False)]:
            self.assertEqual(checked_url(url, first), url)

    def test_untrusted_destinations(self):
        for url in ['http://links.duckduckgo.com/d.js', '//links.duckduckgo.com/d.js',
                    'https://other.invalid/d.js', 'https://links.duckduckgo.com.other.invalid/d.js',
                    'https://127.0.0.1/d.js', 'https://user@links.duckduckgo.com/d.js',
                    'https://links.duckduckgo.com:443/d.js', 'https://links.duckduckgo.com./d.js',
                    'https://LINKS.duckduckgo.com/d.js', 'https://links.duckduckgo.com/d.js#',
                    'https://links.duckduckgo.com/other', 'https://links.duckduckgo.com/%64.js',
                    'https://links.duckduckgo.com/d.js\n', 'https://links.duckduckgo.com/d.js?é',
                    'https://links.duckduckgo.com\\@other.invalid/d.js', 'https://[/d.js']:
            with self.subTest(case=url), self.assertRaises(CandidateRejected):
                checked_url(url)

    def test_stage_hosts_cannot_swap(self):
        with self.assertRaises(CandidateRejected):
            checked_url('https://links.duckduckgo.com/d.js', first=True)
        with self.assertRaises(CandidateRejected):
            checked_url('https://duckduckgo.com/')

    def test_url_length(self):
        with self.assertRaises(CandidateRejected):
            checked_url('https://links.duckduckgo.com/d.js?' + 'x' * 8192)

    def test_arithmetic(self):
        self.assertEqual(challenge_url(challenge()), 'https://links.duckduckgo.com/d.js?jsa=21')
        self.assertEqual(challenge_url(challenge(body='const s = `<p><div></p><p></div`;')),
                         'https://links.duckduckgo.com/d.js?jsa=39')

    def test_foreign_followup(self):
        for destination in ['https://other.invalid/d.js?x=', '//other.invalid/d.js?x=', '/other?x=']:
            with self.assertRaises(CandidateRejected):
                challenge_url(challenge(destination=destination))

    def test_malformed_challenge(self):
        for text in ['', challenge(initial='-1'), challenge(initial='1' * 13),
                     challenge(body='return num * 1234567;'), challenge(body='return num;'),
                     challenge(body='const s = `unknown`;'), challenge(operations='jsa = missing(jsa);'),
                     challenge() + 'let jsa = 2;',
                     challenge() + 'let f = function(num) {return num * 2;};',
                     challenge() + "DDG.deep.initialize('/d.js?x=')"]:
            with self.assertRaises(CandidateRejected):
                challenge_url(text)

    def test_challenge_size(self):
        with self.assertRaises(CandidateRejected):
            challenge_url(challenge() + ' ' * 65536)

    def test_operation_bound(self):
        with self.assertRaises(CandidateRejected):
            challenge_url(challenge(operations='jsa = f(jsa);' * 33))

    def test_numeric_bound(self):
        with self.assertRaises(CandidateRejected):
            challenge_url(challenge(initial='999999999999', body='return num * 999999;'))

    def test_generic_error(self):
        try:
            checked_url('https://other.invalid/private-query')
        except CandidateRejected as error:
            self.assertEqual(str(error), 'Offline candidate policy rejected input')

    def test_no_cache(self):
        cache = NoCache()
        cache.set('fixture', 'value', expire=7200)
        self.assertIsNone(cache.get('fixture'))


if __name__ == '__main__':
    unittest.main()
