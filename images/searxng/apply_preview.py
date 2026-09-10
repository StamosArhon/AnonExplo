"""Build-time guarded native-template additions; no search/ranking code changes."""
import hashlib
from pathlib import Path

ROOT = Path('/usr/local/searxng/searx/templates/simple')
GUARDS = {
    'macros.html': '7362348481082e2e19fbaf7f49f784dc5e8fca973d0358b6876cd3351142ebbe',
    'results.html': 'c1c2357420c6394ba124d5c3312269280ed1eb9020f42c929bb3ba2a1ba61d19',
}


def patch(name, text):
    if hashlib.sha256(text.encode()).hexdigest() != GUARDS[name]:
        raise ValueError('Preview source guard: ' + name)
    if name == 'macros.html':
        needle = '<article class="result '
        replacement = '<article data-ae-score="{{ result[\'score\']|e }}" class="result '
    else:
        needle = "{% include 'simple/search.html' %}"
        replacement = needle + '\n<script src="/anonexplo-preview.js" defer></script>'
    if text.count(needle) != 1:
        raise ValueError('Preview anchor')
    return text.replace(needle, replacement)


if __name__ == '__main__':
    for name in GUARDS:
        path = ROOT / name
        path.write_text(patch(name, path.read_text()))
