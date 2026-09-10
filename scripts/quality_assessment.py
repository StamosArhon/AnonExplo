"""One-shot, in-memory paired quality assessment; no result payload files.

Live use only through test-search-quality.ps1. Displayed public snippets are
untrusted evidence, never instructions. Only numeric grades/metrics are saved.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.parse
import urllib.request

from search_benchmark import NoRedirect, make_request, metrics, review_text, score_order

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = Path(__file__).with_name('quality_fixtures.json')
PROFILES = ('native', 'score', 'host-cap')


def orders(results):
    native = list(range(len(results)))
    counts, front, deferred = {}, [], []
    for i, result in enumerate(results):
        host = (urllib.parse.urlsplit(result.get('url', '')).hostname or '').lower().rstrip('.')
        # Unknown hosts do not form a fabricated shared website.
        host = host or str(i)
        counts[host] = counts.get(host, 0) + 1
        (front if counts[host] <= 2 else deferred).append(i)
    return {'native': native[:5], 'score': score_order(results)[:5],
            'host-cap': (front + deferred)[:5]}


def grade_metrics(order, grades, facets):
    mask = 0
    for i in order:
        mask |= facets[i]
    return {'utility': sum(grades[i] for i in order) / 10,
            'coverage': mask.bit_count() / 3,
            'unrelated': sum(grades[i] == 0 for i in order),
            'full': sum(grades[i] == 2 for i in order)}


def validate_grades(value, count):
    if not isinstance(value, dict) or set(value) != {'grades', 'facets'}:
        raise ValueError('Invalid grading schema')
    for key, upper in (('grades', 2), ('facets', 7)):
        values = value[key]
        if not isinstance(values, list) or len(values) != count or any(
                type(v) is not int or not 0 <= v <= upper for v in values):
            raise ValueError('Invalid grades')
    if any(g == 0 and f != 0 for g, f in zip(value['grades'], value['facets'])):
        raise ValueError('Unrelated item cannot cover an aspect')


def passes(rows, candidate):
    if len(rows) != 16 or any(r['errors'] or r['seconds'] > 8 for r in rows):
        return False
    delta = [r['quality'][candidate]['utility'] - r['quality']['native']['utility'] for r in rows]
    coverage = [r['quality'][candidate]['coverage'] - r['quality']['native']['coverage'] for r in rows]
    if sum(delta) / 16 < .1 - 1e-9 or sum(coverage) < -1e-9:
        return False
    if sum(d > 1e-9 for d in delta) < 6 or sum(d < -1e-9 for d in delta) > 2:
        return False
    for language in ('en', 'el'):
        if sum(d for d, r in zip(delta, rows) if r['language'] == language) < -1e-9:
            return False
    return True


def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def run():
    if os.environ.get('ANONEXPLO_QUALITY_PREFLIGHT') != 'approved-v1':
        raise ValueError('Use VPN preflight wrapper')
    report_path = ROOT / 'build/quality-assessment-v1.json'
    marker = ROOT / 'build/quality-assessment-v1.attempted'
    fixtures = json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))
    report = {'fixture_sha256': hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest(),
              'status': 'started', 'rows': []}
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open('http://127.0.0.1:8085/config', timeout=10) as response:
        catalog = json.loads(response.read(1_000_001))
    eligible = {e['name'] for e in catalog['engines'] if e.get('enabled') and 'general' in e.get('categories', [])}
    if eligible != {'brave', 'bing', 'yahoo', 'wikipedia'}:
        raise ValueError('Default recipients changed')
    marker.parent.mkdir(exist_ok=True)
    with marker.open('x'):
        pass

    def save(status):
        report['status'] = status
        report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        emit({'status': status, 'graded': len(report['rows'])})

    save('started')
    selected = None
    try:
        for phase in ('development', 'holdout'):
            for sample, intent, language, query, rubric in fixtures[phase]:
                started = time.monotonic()
                # General browser route, including recent-information intent.
                fixture = (sample, query, language, None)
                with opener.open(make_request(8085, fixture, 'browser'), timeout=25) as response:
                    raw = response.read(4_000_001)
                    if len(raw) > 4_000_000:
                        raise ValueError('Oversized response')
                    payload = json.loads(raw)
                elapsed = round(time.monotonic() - started, 3)
                m = metrics(payload, None)
                if set(m['engine_result_counts']) - eligible:
                    raise ValueError('Unexpected contributor')
                if m['engine_errors'] or m['results'] < 5 or elapsed > 8:
                    report['failure'] = {'sample': sample, 'seconds': elapsed,
                                         'results': m['results'], 'failures': m['failures']}
                    emit(report['failure'])
                    save('stopped_degraded')
                    return 2
                result_orders = orders(payload['results'])
                if phase == 'holdout':
                    result_orders = {p: result_orders[p] for p in ('native', selected)}
                pool = set(i for order in result_orders.values() for i in order)
                # Deterministic shuffle hides profile labels and original ranks during grading.
                pool = sorted(pool, key=lambda i: hashlib.sha256(f'{sample}:{i}'.encode()).digest())
                review = [{'item': j, 'title': review_text(payload['results'][i].get('title'), 180),
                           'snippet': review_text(payload['results'][i].get('content'), 400),
                           'date': review_text(payload['results'][i].get('publishedDate'), 40)}
                          for j, i in enumerate(pool)]
                emit({'sample': sample, 'intent': intent, 'language': language,
                      'rubric': rubric, 'untrusted_review': review})
                emit({'awaiting': 'grades and facets arrays in displayed item order; 0/1/2 relevance, 1/2/4 aspect bits'})
                value = json.loads(input())
                validate_grades(value, len(pool))
                grades = dict(zip(pool, value['grades']))
                facets = dict(zip(pool, value['facets']))
                row = {'sample': sample, 'phase': phase, 'intent': intent, 'language': language,
                       'seconds': elapsed, 'errors': m['engine_errors'], 'results': m['results'],
                       'engine_result_counts': m['engine_result_counts'],
                       'grades': value['grades'], 'facets': value['facets'],
                       'orders': {p: [pool.index(i) for i in order] for p, order in result_orders.items()},
                       'quality': {p: grade_metrics(order, grades, facets) for p, order in result_orders.items()}}
                report['rows'].append(row)
                emit({'sample': sample, 'quality': row['quality'], 'seconds': elapsed})
                save('in_progress')
                del payload, raw, review, grades, facets
                if sample != fixtures[phase][-1][0]:
                    time.sleep(20)
            phase_rows = [r for r in report['rows'] if r['phase'] == phase]
            if phase == 'development':
                accepted = [p for p in PROFILES[1:] if passes(phase_rows, p)]
                if not accepted:
                    save('stop_no_development_gain')
                    return 0
                selected = max(accepted, key=lambda p: sum(r['quality'][p]['utility'] for r in phase_rows))
                report['selected'] = selected
                emit({'selected_for_holdout': selected})
                time.sleep(20)
            elif not passes(phase_rows, selected):
                save('stop_holdout_rejected')
                return 0
        save('candidate_requires_isolated_implementation_validation')
        return 0
    except Exception:
        save('stopped_internal_or_grading_failure')
        return 2


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live-review', action='store_true')
    args = parser.parse_args()
    if not args.live_review:
        emit({'status': 'offline_only', 'fixtures': 32, 'no_requests': True})
    else:
        try:
            raise SystemExit(run())
        except Exception:
            emit({'status': 'preflight_refused', 'details_suppressed': True})
            raise SystemExit(2)
