"""Offline characterization of the pinned SearXNG ranking, no upstream queries.

Run in the SearXNG venv in isolated validation. These assertions deliberately
flag changed upstream behavior during future image updates; review then rather
than blindly preserving the old grouping algorithm.
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from searx.engines import engines
from searx.results import ResultContainer, calculate_score
from searx.result_types import MainResult

engines['probe-text'] = SimpleNamespace(name='probe-text', weight=1, categories=['news'], paging=False)
engines['probe-image'] = SimpleNamespace(name='probe-image', weight=1, categories=['news'], paging=False)
container = ResultContainer()
# The offline process has no web-app metric storage. Disable counters only;
# normalization, deduplication, score calculation and grouping are real code.
with patch('searx.results.histogram_observe'), patch('searx.results.counter_add'):
    container.extend('probe-text', [MainResult(url=f'https://example.invalid/text/{i}', title='Synthetic text')
                                    for i in range(9)])
    container.extend('probe-image', [MainResult(url='https://example.invalid/image', title='Synthetic image',
                                              thumbnail='https://example.invalid/thumb')])
    ordered = container.get_ordered_results()
assert len(ordered) == 10
assert all(r.engine == 'probe-text' for r in ordered[:9])
assert ordered[9].engine == 'probe-image'
assert ordered[9].score > ordered[1].score, 'Review upstream grouping changes'

old = {'engines': {'probe-text'}, 'positions': [1], 'publishedDate': datetime(2000, 1, 1, tzinfo=timezone.utc)}
new = {**old, 'publishedDate': datetime(2026, 1, 1, tzinfo=timezone.utc)}
assert calculate_score(old, '') == calculate_score(new, ''), 'Review upstream recency scoring changes'
print('PASS: pinned news grouping can override score order; dates do not affect native scores. No requests sent.')
