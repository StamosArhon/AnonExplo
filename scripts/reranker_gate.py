"""Pure optional preference policy. Never performs networking or persists inputs."""
import math
from urllib.parse import urlsplit


def preferred(url, domains):
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or parsed.username or parsed.password:
            return False
        host = (parsed.hostname or '').lower().rstrip('.')
        return any(host == d or host.endswith('.' + d) for d in domains)
    except (TypeError, ValueError):
        return False


def gated_order(results, relevance, domains, threshold=.8):
    original = list(range(len(results)))
    if len(relevance) != len(results) or any(type(v) not in (float, int) or not math.isfinite(v)
            or not 0 <= v <= 1 for v in relevance):
        return original
    if any(type(r.get('score')) not in (float, int) or not math.isfinite(r['score']) or r['score'] < 0 for r in results):
        return original
    order = original[:]
    for index in original:
        if relevance[index] < threshold or not preferred(results[index].get('url'), domains):
            continue
        position = order.index(index)
        # At most two places upward; never leapfrog a substantially more relevant result.
        for _ in range(2):
            if position == 0:
                break
            previous = order[position - 1]
            if relevance[previous] > relevance[index] + .05:
                break
            previous_boost = 1.15 if preferred(results[previous].get('url'), domains) and relevance[previous] >= threshold else 1
            if results[index]['score'] * 1.15 <= results[previous]['score'] * previous_boost:
                break
            order[position - 1], order[position] = order[position], order[position - 1]
            position -= 1
    return order
