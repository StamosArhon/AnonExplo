"""Frozen public trial fixtures and metrics-only policy (no network imports)."""
from urllib.parse import urlsplit

FIXTURES = (
    ('web-library', 'Open Library borrowing ebooks', 'openlibrary.org'),
    ('web-air', 'European Environment Agency air quality index', 'eea.europa.eu'),
    ('web-observatory-el', '\u0395\u03b8\u03bd\u03b9\u03ba\u03cc \u0391\u03c3\u03c4\u03b5\u03c1\u03bf\u03c3\u03ba\u03bf\u03c0\u03b5\u03af\u03bf \u0391\u03b8\u03b7\u03bd\u03ce\u03bd \u03b5\u03c0\u03af\u03c3\u03b7\u03bc\u03bf\u03c2 \u03b9\u03c3\u03c4\u03cc\u03c4\u03bf\u03c0\u03bf\u03c2', 'noa.gr'),
)


def grade(rows, domain):
    rank = None
    for index, row in enumerate(rows[:5], 1):
        try:
            host = (urlsplit(row.url).hostname or '').lower()
        except (ValueError, AttributeError):
            continue
        if host == domain or host.endswith('.' + domain):
            rank = index
            break
    return {'results': len(rows), 'expected_top5': rank is not None, 'expected_rank': rank}


def acceptable(metrics, errors):
    return not errors and metrics['results'] >= 5 and metrics['expected_top5']
