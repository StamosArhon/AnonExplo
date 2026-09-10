"""Unix-only transport failures tested with an injected scorer, not providers."""
import json
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from preview_server import Server, Handler


class Transport(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = self.temp.name + '/test.sock'
        self.server = Server(self.path, Handler)
        self.server.inference_lock = threading.Lock()
        self.server.domains = {'example.org'}
        self.server.score = lambda pairs: [.95]*len(pairs)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.temp.cleanup()

    def send(self, header, body=b''):
        with socket.socket(socket.AF_UNIX) as s:
            s.settimeout(3); s.connect(self.path); s.sendall(header+body)
            raw=b''
            while chunk:=s.recv(4096): raw+=chunk
        h,b=raw.split(b'\r\n\r\n',1)
        return int(h.split()[1]),json.loads(b)

    def post(self):
        raw=json.dumps({'query':'fixture','results':[{'url':'https://example.org','title':'fixture','content':'fixture','score':1}]}).encode()
        return self.send(f'POST /rank HTTP/1.0\r\nContent-Type: application/json\r\nContent-Length: {len(raw)}\r\n\r\n'.encode(),raw)

    def test_busy_does_not_call_model(self):
        self.server.inference_lock.acquire()
        try: self.assertEqual(self.post()[0],503)
        finally: self.server.inference_lock.release()

    def test_deadline_keeps_order_out_of_response(self):
        def slow(pairs): time.sleep(.02); return [.95]
        self.server.score=slow
        with patch('preview_server.DEADLINE', .001):
            code,value=self.post()
        self.assertEqual(code,504); self.assertNotIn('order',value)

    def test_length_limit(self):
        self.assertEqual(self.send(b'POST /rank HTTP/1.0\r\nContent-Type: application/json\r\nContent-Length: 65537\r\n\r\n')[0],413)

    def test_chunked_rejected(self):
        self.assertEqual(self.send(b'POST /rank HTTP/1.0\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n')[0],400)

    def test_model_exception_has_no_details(self):
        def fail(pairs): raise ValueError('sensitive test detail')
        self.server.score=fail
        code,value=self.post()
        self.assertEqual(code,400); self.assertEqual(value,{'status':'unavailable'})

    def test_health(self):
        self.assertEqual(self.send(b'GET /health HTTP/1.0\r\n\r\n'),(200,{'ready':True}))


if __name__=='__main__': unittest.main()
