"""Opt-in local reranking over a Unix socket only. No query/result persistence."""
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import re
import socket
import socketserver
import stat
import threading
import time
from http.server import BaseHTTPRequestHandler

from reranker_gate import gated_order, preferred

SOCKET = '/run/anonexplo-preview/model.sock'
LIMIT = 65536
DEADLINE = 4.0


def checked_domains(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 100:
        raise ValueError('domains')
    if any(not isinstance(d, str) or len(d) > 253 or not re.fullmatch(
        r'[a-z0-9]+(?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9]+(?:[a-z0-9-]*[a-z0-9])?)+', d) for d in value):
        raise ValueError('domains')
    return set(value)


def checked_request(data):
    if not isinstance(data, dict) or set(data) != {'query', 'results'}:
        raise ValueError('shape')
    q, rows = data['query'], data['results']
    if not isinstance(q, str) or not 1 <= len(q) <= 512:
        raise ValueError('query')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 24:
        raise ValueError('count')
    for r in rows:
        if not isinstance(r, dict) or set(r) != {'url', 'title', 'content', 'score'}:
            raise ValueError('row')
        if any(not isinstance(r[k], str) or len(r[k]) > n
               for k, n in [('url', 2048), ('title', 180), ('content', 400)]):
            raise ValueError('text')
        if type(r['score']) not in (int, float) or not math.isfinite(r['score']) or r['score'] < 0:
            raise ValueError('score')
    return q, rows


def evaluate(data, domains, score):
    q, rows = checked_request(data)
    native = list(range(len(rows)))
    if not any(preferred(r['url'], domains) for r in rows):
        return {'order': native, 'promoted': 0, 'status': 'no_preferred_matches'}
    values = score([[q, r['title'] + ' ' + r['content']] for r in rows])
    if len(values) != len(rows) or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in values):
        raise ValueError('model scores')
    order = gated_order(rows, values, domains)
    promoted = sum(order.index(i) < i for i in native if preferred(rows[i]['url'], domains))
    return {'order': order, 'promoted': promoted, 'status': 'applied' if promoted else 'no_safe_promotions'}


def verify_model(directory):
    manifest = Path('/trial/provision-local-reranker.ps1').read_text()
    files = re.findall(r"    '([^']+)' = '([0-9a-f]{40,64})'", manifest)
    if len(files) != 7:
        raise ValueError('manifest')
    for name, expected in files:
        path = directory / name
        digest = hashlib.sha256() if len(expected) == 64 else hashlib.sha1()
        if len(expected) == 40:
            digest.update(f'blob {path.stat().st_size}\0'.encode('ascii'))
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1048576), b''):
                digest.update(block)
        if digest.hexdigest() != expected:
            raise ValueError('artifact')


class Handler(BaseHTTPRequestHandler):
    # HTTP is transported only over AF_UNIX; the gateway is the sole browser entry.
    def log_message(self, *args):
        pass

    def setup(self):
        self.request.settimeout(2)
        super().setup()

    def reply(self, status, value):
        payload = json.dumps(value).encode('ascii')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        self.reply(200 if self.path == '/health' else 404, {'ready': self.path == '/health'})

    def do_POST(self):
        acquired = False
        try:
            if self.path != '/rank' or self.headers.get('Content-Type') != 'application/json' or self.headers.get('Transfer-Encoding'):
                self.reply(400, {'status': 'invalid_request'})
                return
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= LIMIT:
                self.reply(413, {'status': 'request_limit'})
                return
            # Reject overload before reading query data; never queue inference.
            acquired = self.server.inference_lock.acquire(blocking=False)
            if not acquired:
                self.reply(503, {'status': 'busy'})
                return
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError('short body')
            start = time.monotonic()
            result = evaluate(json.loads(raw), self.server.domains, self.server.score)
            elapsed = time.monotonic() - start
            if elapsed > DEADLINE:
                self.reply(504, {'status': 'deadline'})
            else:
                result['seconds'] = round(elapsed, 3)
                self.reply(200, result)
        except (BrokenPipeError, ConnectionResetError, socket.timeout):
            pass
        except Exception:
            try:
                self.reply(400, {'status': 'unavailable'})
            except OSError:
                pass
        finally:
            if acquired:
                self.server.inference_lock.release()


class Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
    # Pure policy tests can import on Windows without AF_UNIX. Instantiation
    # fails there: this is never allowed to fall back to a TCP listener.
    address_family = getattr(socket, 'AF_UNIX', None)
    daemon_threads = True
    request_queue_size = 4

    def __init__(self, *args, **kwargs):
        if self.address_family is None:
            raise RuntimeError('AF_UNIX required')
        self.slots = threading.BoundedSemaphore(8)
        super().__init__(*args, **kwargs)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()

    def handle_error(self, request, client_address):
        pass  # Never log payload-bearing exceptions.


def main():
    if {p.name for p in Path('/sys/class/net').iterdir()} != {'lo'}:
        raise ValueError('requires network none')
    directory = Path('/model')
    verify_model(directory)
    domains = checked_domains(json.loads(Path('/preferences/domains.json').read_text()))
    logging.disable(logging.CRITICAL)
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    torch.set_num_threads(8)
    tokenizer = AutoTokenizer.from_pretrained(directory, local_files_only=True, trust_remote_code=False)
    model = AutoModelForSequenceClassification.from_pretrained(directory, local_files_only=True,
        trust_remote_code=False, use_safetensors=True).eval()

    def score(pairs):
        inputs = tokenizer(pairs, padding=True, truncation=True, max_length=512, return_tensors='pt')
        with torch.inference_mode():
            return torch.sigmoid(model(**inputs).logits.flatten().float()).tolist()

    score([['water', 'Water is a liquid.']])
    path = Path(SOCKET)
    if path.exists():
        if not stat.S_ISSOCK(path.stat().st_mode):
            raise ValueError('unexpected socket path')
        path.unlink()
    with Server(SOCKET, Handler) as server:
        os.chmod(SOCKET, 0o666)
        server.inference_lock = threading.Lock()
        server.domains, server.score = domains, score
        server.serve_forever()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit(2)  # No exception details, queries or URLs in logs.
