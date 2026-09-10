"""Frozen synthetic-only offline model test. Emits no query or result text."""
import hashlib
import json
import logging
from pathlib import Path
import socket
import time

logging.disable(logging.CRITICAL)
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


def main():
    # Assert no non-loopback interfaces in addition to Docker --network none.
    assert set(p.name for p in Path('/sys/class/net').iterdir()) <= {'lo'}
    try:
        with socket.create_connection(('1.1.1.1', 443), timeout=1):
            raise RuntimeError('Unexpected egress')
    except OSError:
        pass
    torch.set_num_threads(8)
    fixture_path = Path('/trial/reranker_fixtures.json')
    cases = json.loads(fixture_path.read_text())
    model_dir = '/model'
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True, trust_remote_code=False)
    model = AutoModelForSequenceClassification.from_pretrained(model_dir,
        local_files_only=True, trust_remote_code=False, use_safetensors=True).eval()

    def score(pairs):
        inputs = tokenizer(pairs, padding=True, truncation=True, max_length=512, return_tensors='pt')
        with torch.inference_mode():
            return torch.sigmoid(model(**inputs).logits.flatten().float()).tolist()

    score([[cases[0]['query'], cases[0]['documents'][0]]])
    observations = []
    for case in cases:
        start = time.monotonic()
        values = score([[case['query'], document] for document in case['documents']])
        row = {'id': case['id'], 'split': case['split'], 'language': case['language'],
               'scores': [round(v, 6) for v in values], 'seconds': round(time.monotonic()-start, 3),
               'correct_top': max(range(len(values)), key=values.__getitem__) == 0,
               'positive_eligible': values[0] >= .8,
               'false_boosts': sum(v >= .8 for v in values[1:])}
        print(json.dumps(row), flush=True)
        observations.append(row)
    pairs = [[cases[i % len(cases)]['query'], cases[i % len(cases)]['documents'][0]] for i in range(24)]
    start = time.monotonic()
    score(pairs)
    batch_seconds = time.monotonic()-start
    accepted = all(r['correct_top'] and not r['false_boosts'] for r in observations) and sum(r['positive_eligible'] for r in observations) >= 6 and batch_seconds <= 2
    print(json.dumps({'status': 'offline_trial_completed', 'fixture_sha256': hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
        'cpu_batch24_seconds': round(batch_seconds, 3), 'accepted_for_further_evaluation': accepted,
        'production_integrated': False, 'network_none': True}), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status': 'failed', 'class': type(error).__name__, 'details_suppressed': True}), flush=True)
        raise SystemExit(2)
