# SPDX-License-Identifier: AGPL-3.0-or-later
# Challenge arithmetic adapted from SearXNG duckduckgo_web.py at 765a999.
"""Offline experiment boundary for a reviewed upstream DDG web adapter.

No production imports or default network implementation. The caller supplies
transport explicitly; the shipped test runner supplies only mocks.
"""
import re
from time import monotonic
from urllib.parse import urljoin, urlsplit

SOURCE_SHA256 = 'e3cf8fe33807c62d504a2b39e790e38ce6353850a367816fbdcce6c441ee7f73'
HTML_LENGTHS = {'<p><div></p><p></div': 32, '<li><div></li><li></div': 29,
                '<div><div></div><div></div': 33, '<br><div></br><br></div': 23}


class CandidateRejected(ValueError):
    """Intentionally generic: never include query, URL, token or response text."""


def reject():
    raise CandidateRejected('Offline candidate policy rejected input')


def checked_url(url, first=False):
    if not isinstance(url, str) or len(url) > 8192 or any(ord(c) <= 32 or ord(c) >= 127 for c in url) or '\\' in url:
        reject()
    try:
        parsed = urlsplit(url)
    except ValueError:
        reject()
    host, path = ('duckduckgo.com', '/') if first else ('links.duckduckgo.com', '/d.js')
    if not url.startswith('https://') or parsed.scheme != 'https' or parsed.netloc != host or parsed.path != path or '#' in url:
        reject()
    return url


def challenge_url(text):
    if not isinstance(text, str) or len(text) > 65536:
        reject()
    initial = re.findall(r'let jsa = ([0-9]+);', text)
    links = re.findall(r"DDG\.deep\.initialize\('([^']+)'", text)
    functions = re.findall(r'let (\w+) = function\(num\) \{([^}]*)\};', text)
    operations = re.findall(r'jsa = (\w+)\(jsa\);', text)
    if len(initial) != 1 or len(initial[0]) > 12 or len(links) != 1 or len(functions) > 32 or len(operations) > 32:
        reject()
    if len({name for name, _ in functions}) != len(functions):
        reject()
    functions = dict(functions)
    value = int(initial[0])
    for name in operations:
        body = functions.get(name)
        if body is None or len(body) > 512:
            reject()
        mul = re.search(r'num \* ([0-9]+)', body)
        if mul:
            if len(mul[1]) > 6:
                reject()
            value *= int(mul[1])
        else:
            snippet = re.search(r'`([^`]+)`', body)
            if not snippet or snippet[1] not in HTML_LENGTHS:
                reject()
            value += HTML_LENGTHS[snippet[1]]
        # Avoid diverging from exact integer arithmetic in browser JavaScript.
        if value > 2**53 - 1:
            reject()
    return checked_url(urljoin('https://links.duckduckgo.com', links[0] + str(value)))


class NoCache:
    def get(self, _key):
        return None

    def set(self, *_args, **_kwargs):
        pass


class GuardedWeb:
    """One first-page request only; fresh module and instance per query."""
    def __init__(self, module, transport, clock=monotonic):
        self.module, self.transport, self.clock = module, transport, clock
        self.calls, self.used, self.followed = 0, False, False
        module.CACHE = NoCache()
        module.get = self.fetch
        module._solve_jsa = self.solve

    def fetch(self, url, **kwargs):
        checked_url(url, first=self.calls == 0)
        remaining = self.deadline - self.clock()
        if remaining <= 0 or self.calls >= 3:
            reject()
        headers = {}
        for name, value in kwargs.get('headers', {}).items():
            if name not in ('User-Agent', 'Accept', 'Referer', 'Sec-Fetch-Dest', 'Sec-Fetch-Mode', 'Sec-Fetch-Site'):
                continue
            if not isinstance(value, str) or len(value) > 1024 or any(ord(c) < 32 for c in value):
                reject()
            if name == 'Referer' and value != 'https://duckduckgo.com/':
                reject()
            headers[name] = value
        timeout = min(remaining, 2 if self.calls == 0 else 6)
        self.calls += 1
        response = self.transport(url, headers=headers, timeout=timeout, allow_redirects=False,
                                  max_redirects=0, verify=True, impersonate='firefox', default_headers=False)
        # Post-buffer parse bound, not a streaming download-size guarantee.
        if self.clock() >= self.deadline or response.status_code != 200 or len(response.text) > 1048576:
            reject()
        return response

    def solve(self, response):
        if self.followed:
            reject()
        url = challenge_url(response.text)
        self.followed = True
        follow = self.fetch(url, headers=response.search_params['headers'])
        if 'let jsa =' in follow.text:
            reject()
        follow.search_params = response.search_params
        return follow

    def run(self, query, headers=None, budget=6):
        if self.used or not isinstance(query, str) or not query or len(query) >= 500:
            reject()
        if not isinstance(budget, (int, float)) or not 0 < budget <= 6:
            reject()
        self.used = True
        self.deadline = self.clock() + budget
        params = {'query': query, 'pageno': 1, 'headers': dict(headers or {}), 'url': None}
        self.module.request(query, params)
        if not params['url']:
            reject()
        response = self.fetch(params['url'], headers=params['headers'])
        response.search_params = params
        result = self.module.response(response)
        if self.clock() >= self.deadline:
            reject()
        return result
