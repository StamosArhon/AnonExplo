"""Build-time, fail-closed repair of fingerprinted merge source and date macro.

No runtime imports, downloads or broad defaults_from behavior changes. Updating
the upstream image requires reviewing this repair and its regression tests.
"""
from hashlib import sha256
from pathlib import Path

SOURCE_SHA256 = "5c1be81f866473021370f3f92fc32173e2df30446191aa151d9358c1f4512cc7"
TEMPLATE_SHA256 = "56c42b5d38aeee3b47b2b04cca3da9e8b32b747addf216bf840215fae7a1f98d"
ANCHOR = "    # add engine to list of result-engines\n"
REPAIR = '''    # AnonExplo: preserve available dates across typed/legacy duplicates.
    # Both native defaults_from implementations leave explicit None unchanged.
    if origin.publishedDate is None and isinstance(other.publishedDate, datetime):
        origin.publishedDate = other.publishedDate
        origin.pubdate = other.publishedDate.strftime('%Y-%m-%d %H:%M:%S%z')

'''


def patched_source(source: bytes) -> bytes:
    if sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError("Upstream results.py fingerprint changed; review repair, do not bypass guard")
    text = source.decode("utf-8")
    if text.count(ANCHOR) != 1 or text.count("import warnings\n") != 1:
        raise ValueError("Unexpected source anchors")
    text = text.replace("import warnings\n", "import warnings\nfrom datetime import datetime\n", 1)
    return text.replace(ANCHOR, REPAIR + ANCHOR, 1).encode("utf-8")


def patched_template(source: bytes) -> bytes:
    if sha256(source).hexdigest() != TEMPLATE_SHA256:
        raise ValueError("Upstream macros.html fingerprint changed; review repair")
    anchor = b'{{ result.pubdate }}'
    if source.count(anchor) != 1:
        raise ValueError("Unexpected date template anchor")
    # LegacyResult.pubdate is a class default that shadows its dictionary key.
    # Explicit item lookup works for both native result types.
    return source.replace(anchor, b"{{ result['pubdate'] }}", 1)


if __name__ == "__main__":
    target = Path("/usr/local/searxng/searx/results.py")
    template = target.parent / "templates/simple/macros.html"
    repaired = patched_source(target.read_bytes())
    repaired_template = patched_template(template.read_bytes())
    compile(repaired, str(target), "exec")
    target.write_bytes(repaired)
    template.write_bytes(repaired_template)
    # Never leave pre-existing bytecode that could mask the patched source.
    for bytecode in (target.parent / "__pycache__").glob("results.*.pyc"):
        bytecode.unlink()
    print("Applied guarded publication-date merge repair.")
