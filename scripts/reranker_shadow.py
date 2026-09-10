"""One-shot, explicitly approved public-fixture shadow evaluation; no live integration."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import re
import subprocess
import threading
import time
import urllib.request
import uuid

from reranker_gate import gated_order, preferred
from search_benchmark import NoRedirect, error_metrics, review_text

ROOT = Path(__file__).resolve().parents[1]
IMAGE = 'sha256:a1ecd793732ada795e0f2fb5162b126b748a982ca902a5a7513df946f2b5cb99'
RETIRED = False


def checked_domains(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 100:
        raise ValueError('domain count')
    if any(not isinstance(d, str) or len(d) > 253 or
           not re.fullmatch(r'[a-z0-9]+(?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9]+(?:[a-z0-9-]*[a-z0-9])?)+', d)
           for d in value):
        raise ValueError('domain format')
    return set(value)


def checked_scores(value, count):
    if not isinstance(value, list) or len(value) != count or any(
        type(v) not in (float, int) or not math.isfinite(v) or not 0 <= v <= 1 for v in value):
        raise ValueError('invalid scores')
    return value


def verify_model():
    # Reuse the exact provisioning manifest without executing its download path.
    manifest = (ROOT / 'scripts/provision-local-reranker.ps1').read_text()
    files = re.findall(r"    '([^']+)' = '([0-9a-f]{40,64})'", manifest)
    if len(files) != 7:
        raise ValueError('artifact manifest')
    directory = ROOT / 'data/models/bge-reranker-v2-m3'
    for name, expected in files:
        path = directory / name
        digest = hashlib.sha256() if len(expected) == 64 else hashlib.sha1()
        if len(expected) == 40:
            digest.update(f'blob {path.stat().st_size}\0'.encode('ascii'))
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024*1024), b''):
                digest.update(block)
        if digest.hexdigest() != expected:
            raise ValueError('artifact mismatch')
    return directory


def main(review):
    if RETIRED:
        raise ValueError('trial retired')
    domains = checked_domains(json.loads((ROOT / 'data/preferences/shadow-domains.json').read_text()))
    cases = json.loads((ROOT / 'scripts/reranker_shadow_fixtures.json').read_text(encoding='utf-8'))
    marker = ROOT / 'build/reranker-shadow.attempted'
    if marker.exists():
        raise ValueError('one attempt already consumed')
    model = verify_model()
    subprocess.run(['powershell', '-ExecutionPolicy', 'Bypass', '-File',
                    str(ROOT / 'scripts/ops-check.ps1')], check=True, timeout=120)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open('http://127.0.0.1:8085/config', timeout=10) as response:
        config = json.loads(response.read(1000001))
    active = {e['name'] for e in config['engines'] if e.get('enabled') and 'general' in e.get('categories', [])}
    if active != {'brave', 'yahoo', 'bing', 'wikipedia'}:
        raise ValueError('unexpected default recipients')
    name = 'anonexplo-shadow-' + uuid.uuid4().hex[:12]
    command = ['docker', 'run', '--rm', '-i', '--name', name, '--pull', 'never', '--network', 'none',
        '--read-only', '--user', '65534:65534', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
        '--log-driver', 'none', '--memory', '12g', '--cpus', '8', '--pids-limit', '256',
        '--tmpfs', '/tmp:rw,noexec,nosuid,size=256m,mode=1777',
        '--mount', f'type=bind,source={model},target=/model,readonly',
        '--mount', f'type=bind,source={ROOT / "scripts"},target=/trial,readonly',
        IMAGE, '/trial/reranker_shadow_worker.py']
    worker = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    messages = queue.Queue(maxsize=32)

    def receive():
        while True:
            line = worker.stdout.readline(16385)
            if not line or len(line) > 16384:
                messages.put(None)
                return
            messages.put(line)

    threading.Thread(target=receive, daemon=True).start()

    def message(timeout):
        value = messages.get(timeout=timeout)
        if value is None:
            raise ValueError('worker ended')
        return json.loads(value)

    try:
        start = time.monotonic()
        if message(120) != {'ready': True, 'network_none': True}:
            raise ValueError('worker not ready')
        print(json.dumps({'model_load_seconds': round(time.monotonic()-start, 3)}), flush=True)
        # Warm up without provider requests or private text.
        worker.stdin.write(b'[["water", "Water is a liquid."]]\n')
        worker.stdin.flush()
        checked_scores(message(15).get('scores'), 1)
        marker.parent.mkdir(exist_ok=True)
        with marker.open('x') as stream:
            stream.write('One approved attempt consumed; never erase to retry.\n')
        for number, case in enumerate(cases):
            if number:
                time.sleep(20)
            # Exact browser-style route, no cookies, engine/category overrides or query expansion.
            import urllib.parse
            url = 'http://127.0.0.1:8085/search?' + urllib.parse.urlencode({'q': case['query'], 'format': 'json'})
            request = urllib.request.Request(url, headers={'Accept-Language': 'en-US,en;q=0.9',
                                                          'User-Agent': 'AnonExplo-Synthetic-Benchmark/1'})
            start = time.monotonic()
            with opener.open(request, timeout=25) as response:
                raw = response.read(4000001)
            if len(raw) > 4000000:
                raise ValueError('response limit')
            payload = json.loads(raw)
            rows = payload.get('results', [])
            errors = error_metrics(payload.get('unresponsive_engines', []))
            if errors or not rows:
                print(json.dumps({'id': case['id'], 'stopped': True, 'errors': errors, 'results': len(rows)}), flush=True)
                return
            retrieval = round(time.monotonic()-start, 3)
            rows = rows[:24]
            pairs = [[case['query'], review_text(r.get('title'), 180) + ' ' + review_text(r.get('content'), 400)] for r in rows]
            worker.stdin.write(json.dumps(pairs, ensure_ascii=True).encode('ascii') + b'\n')
            worker.stdin.flush()
            scored = message(15)
            scores = checked_scores(scored.get('scores'), len(rows))
            order = gated_order(rows, scores, domains)
            matches = [i for i, r in enumerate(rows) if preferred(r.get('url'), domains)]
            moved = [i for i in matches if order.index(i) < i]
            print(json.dumps({'id': case['id'], 'retrieval_seconds': retrieval, 'model_seconds': scored['seconds'],
                'candidates': len(rows), 'preferred': len(matches), 'eligible_preferred': sum(scores[i] >= .8 for i in matches),
                'promoted': len(moved), 'native_top5': list(range(min(5, len(rows)))), 'shadow_top5': order[:5],
                'preferred_positions': matches, 'promoted_positions': moved}), flush=True)
            if review:
                # Bounded public-fixture evidence only, no URL/domain printing or disk output.
                selected = sorted(set(range(min(5, len(rows)))) | set(order[:5]) | set(matches))
                print(json.dumps({'id': case['id'], 'untrusted_review': [
                    {'position': i, 'shadow_position': order.index(i), 'preferred': i in matches,
                     'relevance': round(scores[i], 6), 'title': pairs[i][1][:180],
                     'text': pairs[i][1]} for i in selected]}, ensure_ascii=True), flush=True)
        print(json.dumps({'completed': len(cases), 'production_changed': False}), flush=True)
    finally:
        worker.stdin.close()
        # Exact, randomly named disposable test container only; never touch production.
        subprocess.run(['docker', 'stop', '-t', '1', name], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=15)
        try:
            worker.wait(timeout=10)
        except subprocess.TimeoutExpired:
            worker.kill()
            worker.wait(timeout=5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--review-public-fixtures', action='store_true')
    args = parser.parse_args()
    if not args.live:
        parser.exit(message='Offline by default; --live consumes one approved attempt.\n')
    try:
        main(args.review_public_fixtures)
    except Exception as error:
        print(json.dumps({'stopped': True, 'class': type(error).__name__, 'details_suppressed': True}), flush=True)
        raise SystemExit(2)
