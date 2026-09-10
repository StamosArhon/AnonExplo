"""Bounded local policy. No networking, query cache or persistent state."""
import math
import threading
import time
from reranker_gate import preferred


class CoverageBudget:
    """One two-search allowance per minute across tabs; no queued allowances."""
    def __init__(self):
        self.lock = threading.Lock()
        self.next_at = 0.0

    def plan(self, domains, now=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            if now < self.next_at:
                return {'version': 2, 'groups': [], 'status': 'cooldown'}
            # No silently truncated personal lists or unbounded query fan-out.
            if not 1 <= len(domains) <= 18:
                return {'version': 2, 'groups': [], 'status': 'source_limit'}
            self.next_at = now + 60
            values = sorted(domains)
            return {'version': 2, 'groups': [values[i:i+9] for i in range(0, len(values), 9)],
                    'status': 'ready', 'spacing_ms': 15000}


def relevance_order(rows, values, domains, native_count):
    if len(values) != len(rows) or any(type(v) not in (int, float) or
            not math.isfinite(v) or not 0 <= v <= 1 for v in values):
        raise ValueError('model scores')
    # Keep every native result; admit new results only above the relevance gate.
    eligible = [i for i in range(len(rows)) if i < native_count or
                (values[i] >= .8 and preferred(rows[i]['url'], domains))]
    adjusted = [v + (.02 if v >= .8 and preferred(rows[i]['url'], domains) else 0)
                for i, v in enumerate(values)]
    order = sorted(eligible, key=lambda i: (-adjusted[i], i))
    return {'order': order, 'added': sum(i >= native_count for i in order),
            'moved': sum(order.index(i) != i for i in range(native_count)),
            'status': 'relevance_ranked', 'version': 2}
