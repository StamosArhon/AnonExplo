"""Network-none real model + Unix transport smoke with public authored fixtures."""
import json
import socket
import subprocess
import sys
import time
from pathlib import Path


def request(method, body=None, content_type='application/json', path='/rank'):
    raw = json.dumps(body).encode() if body is not None else b''
    with socket.socket(socket.AF_UNIX) as conn:
        conn.settimeout(12)
        conn.connect('/run/anonexplo-preview/model.sock')
        header = f'{method} {path} HTTP/1.0\r\nContent-Type: {content_type}\r\nContent-Length: {len(raw)}\r\n\r\n'.encode()
        conn.sendall(header+raw)
        chunks = []
        while chunk := conn.recv(4096):
            chunks.append(chunk)
        head, payload = b''.join(chunks).split(b'\r\n\r\n',1)
        return int(head.split()[1]), json.loads(payload)


subprocess.run([sys.executable, '/trial/test_preview_transport.py'], check=True)
worker = subprocess.Popen([sys.executable, '/trial/preview_server.py'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    start = time.monotonic()
    while not Path('/run/anonexplo-preview/model.sock').exists():
        if worker.poll() is not None or time.monotonic()-start > 90:
            raise RuntimeError('worker startup')
        time.sleep(.2)
    body = {'query':'why is the sky blue Rayleigh scattering', 'results': [
        {'url':'https://other.example/a','score':1.05,'title':'Blue colour','content':'Blue is a colour used in art.'},
        {'url':'https://example.org/b','score':1,'title':'Why the sky is blue','content':'Rayleigh scattering by molecules in the atmosphere scatters short blue wavelengths more strongly than red light.'}]}
    code, value = request('POST',body)
    assert code == 200 and value['order'] == [1,0], (code,value)
    print(json.dumps({'synthetic_promotion':True,'seconds':value['seconds']}),flush=True)
    body['results'][1]['content']='Recipes for baking chocolate cakes.'
    body['results'][1]['title']='Cake recipes'
    code,value=request('POST',body)
    assert code==200 and value['order']==[0,1]
    assert request('POST',{},'text/plain')[0]==400
    assert request('POST',{})[0]==400
    assert request('GET')[0]==404
    body['results'][1]['url']='https://elsewhere.example/b'
    code,value=request('POST',body)
    assert code==200 and value['status']=='no_preferred_matches'
    # Full new request budget, longer authored snippets, no fetched payloads.
    original = {'url':'https://other.example/a','score':10,'title':'Cake recipes',
                'content':('Recipes for baking chocolate cakes. '*12)[:400]}
    relevant = {'url':'https://example.org/b','score':0,'title':'Why the sky is blue',
                'content':('Rayleigh scattering by air molecules scatters short blue wavelengths more strongly than red light. '*5)[:400]}
    expanded = {'query':'why is the sky blue Rayleigh scattering', 'native_count':24,
                'results':[original]*24+[relevant]*4+[dict(original, url='https://example.org/c')]*4}
    code,value=request('POST',expanded,path='/rank-v2')
    assert code==200 and value['added']==4 and value['order'][:4]==[24,25,26,27]
    assert all(i in value['order'] for i in range(24))
    print(json.dumps({'v2_full_budget':32,'relevant_additions':4,'irrelevant_rejected':4,'seconds':value['seconds']}),flush=True)
    assert {p.name for p in Path('/sys/class/net').iterdir()}=={'lo'}
    print('PASS: real offline model, Unix transport, irrelevant preference, invalid input, no-match and network boundary.',flush=True)
finally:
    worker.terminate()
    try: worker.wait(timeout=10)
    except subprocess.TimeoutExpired:
        worker.kill();worker.wait(timeout=5)
