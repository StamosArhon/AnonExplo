"""Disposable network-none stdio scorer. No result text is emitted or saved."""
import json
import logging
from pathlib import Path
import sys
import time


def checked_pairs(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 24:
        raise ValueError('pair count')
    if any(not isinstance(p, list) or len(p) != 2 or
           any(not isinstance(s, str) or len(s) > 600 for s in p) for p in value):
        raise ValueError('pair shape')
    return value


def main():
    if set(p.name for p in Path('/sys/class/net').iterdir()) != {'lo'}:
        raise ValueError('network boundary')
    logging.disable(logging.CRITICAL)
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    torch.set_num_threads(8)
    tokenizer = AutoTokenizer.from_pretrained('/model', local_files_only=True, trust_remote_code=False)
    model = AutoModelForSequenceClassification.from_pretrained('/model', local_files_only=True,
        trust_remote_code=False, use_safetensors=True).eval()
    print(json.dumps({'ready': True, 'network_none': True}), flush=True)
    while True:
        raw = sys.stdin.buffer.readline(131073)
        if not raw:
            break
        if len(raw) > 131072 or not raw.endswith(b'\n'):
            raise ValueError('input limit')
        pairs = checked_pairs(json.loads(raw))
        start = time.monotonic()
        inputs = tokenizer(pairs, padding=True, truncation=True, max_length=512, return_tensors='pt')
        with torch.inference_mode():
            values = torch.sigmoid(model(**inputs).logits.flatten().float()).tolist()
        print(json.dumps({'scores': values, 'seconds': round(time.monotonic()-start, 3)}), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'error': type(error).__name__}), flush=True)
        raise SystemExit(2)
