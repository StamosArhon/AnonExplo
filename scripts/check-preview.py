"""Post-deployment synthetic gateway smoke; no provider searches or saved payloads."""
import json
from pathlib import Path
import urllib.error
import urllib.request
from search_benchmark import NoRedirect

ROOT = Path(__file__).resolve().parents[1]
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())


def call(path, body=None, method=None, headers=None):
    request = urllib.request.Request('http://127.0.0.1:8085'+path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method, headers=headers or {})
    try:
        response = opener.open(request, timeout=8)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        assert response.headers.get('Cache-Control') == 'no-store'
        assert response.headers.get('Referrer-Policy') == 'no-referrer'
        return response.status, response.read(131072)


def main():
    code, script = call('/anonexplo-preview.js')
    assert code == 200 and b'Preferred sources: OFF' in script
    assert call('/')[0] == 200
    assert call('/anonexplo-preview/rank', method='GET')[0] == 405
    assert call('/anonexplo-preview/rank', {}, 'OPTIONS')[0] == 405
    assert call('/anonexplo-preview/rank', {}, 'POST', {'Content-Type':'text/plain'})[0] == 415
    assert call('/anonexplo-preview/rank', {}, 'POST', {'Content-Type':'application/json','Sec-Fetch-Site':'cross-site'})[0] == 403
    domains=json.loads((ROOT/'data/preferences/shadow-domains.json').read_text())
    body={'query':'why is the sky blue Rayleigh scattering','results':[
        {'url':'https://other.example/a','title':'Blue colour','content':'Blue is a colour used in art.','score':1.05},
        {'url':'https://'+domains[0]+'/synthetic-local-test','title':'Why the sky is blue','content':'Rayleigh scattering by molecules in the atmosphere scatters short blue wavelengths more strongly than red light.','score':1}
    ]}
    # URL is only a local preference identifier; neither this test nor model fetches it.
    code,raw=call('/anonexplo-preview/rank',body,'POST',{'Content-Type':'application/json'})
    value=json.loads(raw)
    assert code==200 and value['order']==[1,0] and value['promoted']==1
    print(json.dumps({'gateway_model_promotion':True,'seconds':value['seconds']}))
    body['results'][1].update(title='Cake recipes',content='Recipes for baking chocolate cakes.')
    code,raw=call('/anonexplo-preview/rank',body,'POST',{'Content-Type':'application/json'})
    assert code==200 and json.loads(raw)['order']==[0,1]
    print('PASS: gateway assets, privacy headers, request restrictions, actual offline relevance gate and original-order retention.')


if __name__=='__main__':
    try: main()
    except Exception as error:
        print(json.dumps({'failed':type(error).__name__,'details_suppressed':True}))
        raise SystemExit(2)
