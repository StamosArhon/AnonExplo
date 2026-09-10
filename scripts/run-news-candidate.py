"""One bounded live trial in a disposable container; no listener or files.

Invoked only by test-news-candidate.ps1 -Live after operator cooldown review.
Production configuration is mounted read-only; three News adapters plus their
disabled web-network dependencies are loaded. The client selects only News.
Flask's in-process client exercises native parsing,
processor deadlines, suspension, merging, plugins and JSON serialization.
"""
import argparse
import json
import logging
import os
import secrets
import time
from unittest.mock import patch

from news_candidate import FIXTURES, NEWS_ENGINES, news_score_candidate, token_candidate, verify_sources
from search_benchmark import metrics, freshness_metrics, top5_review


def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def main(review=False, self_check=False):
    # No raw exceptions, tokens, response pages or URL-bearing logs. Container
    # also has logging driver 'none'; only explicitly sanitized stdout is shown.
    logging.disable(logging.CRITICAL)
    verify_sources()
    os.environ['SEARXNG_SECRET'] = secrets.token_hex(32)
    import searx
    chosen = [e for e in searx.settings['engines'] if e['name'] in NEWS_ENGINES]
    assert {e['name'] for e in chosen} == NEWS_ENGINES
    assert all(e.get('timeout') == 6 for e in chosen)
    assert searx.settings['outgoing']['max_request_timeout'] == 8
    assert searx.settings['search']['suspended_times']['SearxEngineTooManyRequests'] <= 180
    # News adapters reference the web adapters' native shared network objects.
    # Load these dependencies disabled; the request selects only News.
    dependencies = [dict(e, disabled=True) for e in searx.settings['engines'] if e['name'] in ('brave', 'duckduckgo')]
    assert {e['name'] for e in dependencies} == {'brave', 'duckduckgo'}
    searx.settings['engines'] = dependencies + chosen
    from searx.webapp import app
    from searx.engines import engines
    from searx.results import ResultContainer
    assert set(engines) == NEWS_ENGINES | {'brave', 'duckduckgo'}
    assert all(not hasattr(e, 'init') for e in engines.values())
    with app.test_client(use_cookies=False) as client:
        catalogue = client.get('/config').get_json()
        assert {e['name'] for e in catalogue['engines'] if e['enabled']} == NEWS_ENGINES
        assert client.get('/').status_code == 200
    emit({'status': 'candidate_initialized', 'news_engines': sorted(NEWS_ENGINES), 'no_listener': True})
    if self_check:
        return 0
    ddg = engines['duckduckgo news']
    brave = engines['brave.news']
    candidate_fetch = token_candidate(ddg)
    original_get, original_cache = ddg.get, ddg.get_vqd
    original_brave_response = brave.response
    original_order = ResultContainer.get_ordered_results
    stages = []
    captured = {}

    def cache_read(*args, **kwargs):
        value = original_cache(*args, **kwargs)
        stages.append({'stage': 'token_cache', 'hit': bool(value)})
        return value

    def token_get(*args, **kwargs):
        started = time.monotonic()
        row = {'stage': 'token_http', 'budget_seconds': kwargs.get('timeout')}
        try:
            response = original_get(*args, **kwargs)
            row['status_code'] = response.status_code
            row['status'] = 'returned'
            return response
        except Exception as exc:
            row['status'] = 'timeout' if type(exc).__name__ == 'Timeout' else 'failed'
            raise
        finally:
            row['seconds'] = round(time.monotonic() - started, 2)
            stages.append(row)

    def brave_response(response):
        # Inspect standard date markup only, in memory. Do not invent dates
        # from text, URLs, script blobs or retrieval time; do not fetch articles.
        from lxml import html
        dom = html.fromstring(response.text)
        nodes = dom.xpath("//div[@data-type='news']")
        captured['brave_markup'] = {
            'news_nodes': len(nodes),
            'nodes_with_time': sum(bool(n.xpath('.//time')) for n in nodes),
            'nodes_with_datetime': sum(bool(n.xpath('.//*[@datetime]')) for n in nodes),
        }
        return original_brave_response(response)

    def order(container):
        native = original_order(container)
        candidate = news_score_candidate(container, native)
        captured['native'] = list(native)
        captured['candidate'] = list(candidate)
        return candidate

    def rows_for_review(rows):
        return [{'title': r.title, 'content': r.content, 'engines': sorted(r.engines),
                 'publishedDate': r.publishedDate.isoformat() if r.publishedDate else None}
                for r in rows]

    with patch.object(ddg, 'fetch_vqd', candidate_fetch), patch.object(ddg, 'get', token_get), \
         patch.object(ddg, 'get_vqd', cache_read), patch.object(brave, 'response', brave_response), \
         patch.object(ResultContainer, 'get_ordered_results', order), app.test_client(use_cookies=False) as client:
        for index, (sample, query, rubric) in enumerate(FIXTURES):
            stages.clear()
            captured.clear()
            started = time.monotonic()
            response = client.get('/search', query_string={'q': query, 'categories': 'news', 'format': 'json'},
                                  headers={'Accept-Language': 'en-US,en;q=0.9'}, follow_redirects=False)
            if response.status_code != 200 or not response.is_json:
                emit({'sample': sample, 'status': 'local_request_failed', 'stopped': True})
                return 2
            payload = response.get_json()
            row = {'sample': sample, **metrics(payload, None), 'seconds': round(time.monotonic() - started, 2),
                   'ddg_stages': list(stages), 'brave_markup': captured.get('brave_markup')}
            for key in ('expected_top5', 'expected_rank', 'reciprocal_rank'):
                row.pop(key)
            assert set(row['engine_result_counts']) <= NEWS_ENGINES
            healthy = not row['engine_errors'] and row['results'] and len(row['engine_result_counts']) == 3
            # A tmpfs cache and four distinct queries should prove cold fetches.
            cold = any(s['stage'] == 'token_cache' and not s['hit'] for s in stages)
            healthy = healthy and cold
            if healthy:
                native, candidate = captured['native'], captured['candidate']
                before, after = rows_for_review(native), rows_for_review(candidate)
                row['ranking'] = {'top5_members_replaced': len({id(r) for r in candidate[:5]} - {id(r) for r in native[:5]}),
                                  'native': freshness_metrics(before), 'candidate': freshness_metrics(after)}
                if review:
                    row['untrusted_native_review'] = top5_review({'results': before})
                    row['untrusted_candidate_review'] = top5_review({'results': after})
                    row['rubric'] = rubric
            emit(row)
            if not healthy:
                emit({'status': 'degraded_or_incomplete', 'stopped': True, 'ranking_comparison_skipped': True})
                return 2
            if index + 1 < len(FIXTURES):
                time.sleep(20)
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review-top5', action='store_true')
    parser.add_argument('--self-check', action='store_true', help='Initialize and check local routes only; no queries.')
    args = parser.parse_args()
    try:
        code = main(args.review_top5, args.self_check)
    except Exception as exc:
        # Report only our own line numbers, never exception text or upstream
        # frames/URLs. Sufficient to diagnose harness failures without payloads.
        import traceback
        lines = [f.lineno for f in traceback.extract_tb(exc.__traceback__) if f.filename == __file__]
        emit({'status': 'candidate_internal_failure', 'stopped': True, 'candidate_lines': lines})
        if args.self_check:
            # Offline initialization has no query, response or production key.
            traceback.print_exc()
        code = 2
    raise SystemExit(code)
