"""Disposable experiment helpers, never imported by production SearXNG."""
import hashlib
import inspect
import math
from pathlib import Path

IMAGE = 'searxng/searxng:latest@sha256:3547509b419cd6a67333d6d68bd1ffad8d46d3669d82e7a7bd538f7b45827432'
SOURCE_HASHES = {
    'results.py': '5c1be81f866473021370f3f92fc32173e2df30446191aa151d9358c1f4512cc7',
    'engines/duckduckgo_extra.py': 'f9c44d75800edb2c50cec532f04e902da88bc910ebad33ab59048805be020b7e',
    'network/__init__.py': '0b570a5fff402a38774addd8570b059f7038b09fe56f57b27fe043e3d22acfd0',
    'engines/brave.py': 'bd9cede0ec3181f60312104321afb5dd6bd11966cfafeece1bf644a4961beccb',
}
NEWS_ENGINES = frozenset(('brave.news', 'duckduckgo news', 'reuters'))
# Frozen before first live use. A failed run ends this trial, not an automatic
# invitation to resume/retry with a fresh cache or suspension state.
FIXTURES = (
    ('candidate-geothermal', 'geothermal energy research', 'Recent reporting on geothermal research, not generic investment listings.'),
    ('candidate-coral', 'coral reef restoration research', 'Recent reporting about reef restoration research, not travel listings.'),
    ('candidate-water-el', 'λειψυδρία Ελλάδα', 'Recent Greek reporting on water scarcity in Greece.'),
    ('candidate-fire-el', 'πρόληψη δασικών πυρκαγιών Ελλάδα', 'Recent Greek reporting about forest fire prevention in Greece.'),
)


def verify_sources(root=Path('/usr/local/searxng/searx')):
    for relative, expected in SOURCE_HASHES.items():
        if hashlib.sha256((root / relative).read_bytes()).hexdigest() != expected:
            raise ValueError('Pinned source changed; review candidate before running')


def token_candidate(engine):
    """Compile just the pinned function with its inner limit changed to 4s.

    The original native network context still enforces the engine deadline on
    subsequent requests. No retries, parser/UA changes or cache bypasses.
    Caller verifies full module hashes before using this experiment.
    """
    source = inspect.getsource(engine.fetch_vqd)
    if source.count('timeout=2,') != 1:
        raise ValueError('Unexpected token function')
    namespace = {}
    exec(compile(source.replace('timeout=2,', 'timeout=4,'), '<isolated-token-candidate>', 'exec'),
         engine.__dict__, namespace)
    return namespace['fetch_vqd']


def news_score_candidate(container, native):
    """Only healthy, News-only containers; retain native scoring and all rows.

    Start from the pre-grouping insertion order to preserve native score ties.
    Original method must run first to populate categories and scores. Returning
    a new list leaves its cached native order and all metadata untouched.
    """
    if container.unresponsive_engines or not native or any(r.category != 'news' for r in native):
        return native
    rows = list(container.main_results_map.values())
    if any(isinstance(r.score, bool) or not isinstance(r.score, (int, float))
           or not math.isfinite(r.score) for r in rows):
        raise ValueError('Invalid native score')
    return sorted(rows, key=lambda r: r.score, reverse=True)
