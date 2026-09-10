"""Deployed same-origin/Unix gateway checks. No provider queries or payload files."""
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None


opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())


def request(path, data=None, headers=None, method=None):
    req = urllib.request.Request('http://127.0.0.1:8085'+path, data=data,
        headers=headers or {'Content-Type':'application/json'}, method=method)
    try: response = opener.open(req, timeout=12)
    except urllib.error.HTTPError as error: response = error
    with response:
        assert response.headers['Cache-Control'] == 'no-store'
        assert response.headers['Referrer-Policy'] == 'no-referrer'
        return response.status, response.read(1048576)


def main():
    code, raw = request('/anonexplo-preview.js')
    expected = Path(__file__).resolve().parents[1]/'configs/preview/preview-v2.js'
    assert code == 200 and hashlib.sha256(raw).digest() == hashlib.sha256(expected.read_bytes()).digest()
    assert request('/')[0] == 200
    for endpoint in ('rank-v2','plan'):
        path='/anonexplo-preview/'+endpoint
        assert request(path)[0] == 405
        assert request(path, method='OPTIONS')[0] == 405
        assert request(path, b'{}', {'Content-Type':'text/plain'})[0] == 415
        assert request(path, b'{}', {'Content-Type':'application/json','Sec-Fetch-Site':'cross-site'})[0] == 403
    body={'query':'why is the sky blue Rayleigh scattering','native_count':2,'results':[
        {'url':'https://other.example/a','title':'Cake recipes','content':'Recipes for chocolate cake.','score':100},
        {'url':'https://other.example/b','title':'Why the sky is blue','content':'Rayleigh scattering by air molecules scatters blue light more strongly than red.','score':.01}]}
    code, raw=request('/anonexplo-preview/rank-v2',json.dumps(body).encode())
    result=json.loads(raw)
    assert code==200 and result['order']==[1,0] and result['added']==0 and result['version']==2
    code, raw=request('/anonexplo-preview/plan',b'{}')
    plan=json.loads(raw)
    assert code==200 and plan['version']==2 and len(plan['groups'])<=2
    assert sum(map(len,plan['groups']))<=18
    assert json.loads(request('/anonexplo-preview/plan',b'{}')[1])['groups']==[]
    print(json.dumps({'gateway_v2':True,'privacy_headers':True,'relevance_first':True,
                      'shared_budget':True,'model_seconds':result['seconds']}))


if __name__ == '__main__':
    try: main()
    except Exception: raise SystemExit('FAIL: v2 gateway check (payloads suppressed).')
