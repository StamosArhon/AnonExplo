"""Temporary loopback visual fixture. No search, model calls or request logging.

Reads installed native templates/CSS via Docker once. Serves only explicit local
assets. Not a production service or Compose component. Stop with Ctrl+C.
"""
from pathlib import Path
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
CONTAINER='anonexplo-search-provider-1'

def docker(args, data=None):
    p=subprocess.run(['docker','exec','-i',CONTAINER]+args, input=data, capture_output=True, check=True)
    return p.stdout

html=docker(['/usr/local/searxng/.venv/bin/python','-'], (ROOT/'scripts/render-design-fixture.py').read_bytes()).decode()
css=docker(['cat','/usr/local/searxng/searx/static/themes/simple/sxng-ltr.min.css'])

MOCK=r'''<script>
const mode = new URL(location.href).searchParams.get('state') || 'success';
document.documentElement.classList.remove('no-js');
document.documentElement.classList.add('js');
if (new URL(location.href).searchParams.get('theme') === 'light') {
  document.documentElement.classList.remove('theme-dark'); document.documentElement.classList.add('theme-light');
}
Object.defineProperty(window, 'localStorage', {value:{getItem:()=>mode==='off'?'off':'on',setItem(){}}});
const originalTimer=window.setTimeout;
window.setTimeout=(fn,ms,...args)=>originalTimer(fn,ms===15000?0:ms,...args);
let extra=0;
window.fetch=async (path,options)=>{
  if(mode==='failure') throw Error('Authored failure fixture');
  if(mode==='loading') return new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(Error('cancelled'))));
  let result;
  if(path.endsWith('rank-v2')) {
    const body=JSON.parse(options.body);
    const n=body.native_count, total=body.results.length;
    result={version:2,order:[...Array.from({length:total-n},(_,i)=>n+i),...Array.from({length:n},(_,i)=>n-1-i)],moved:n,added:total-n};
  } else if(path.endsWith('/plan')) result={version:2,groups:[['example.org'],['example.com']]};
  else if(path==='/search') {
    extra++; result={unresponsive_engines:[],results:[{url:'https://'+(extra===1?'example.org':'example.com')+'/authored',
      title:extra===1?'The public-interest case for independent reporting':'Δημοσιογραφικές συνεργασίες πέρα από τα σύνορα',
      content:extra===1?'An authored preferred-source entry. Its source label, headline and description use the same visual hierarchy as ordinary search results.':''}]};
  } else throw Error('Fixture refuses unexpected request');
  return new Response(JSON.stringify(result),{headers:{'Content-Type':'application/json'}});
};
</script>'''

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        path=urlsplit(self.path).path
        content_type='text/html; charset=utf-8'
        if path=='/':
            content=html.replace('<script src="/anonexplo-preview.js"', MOCK+'<script src="/anonexplo-preview.js"').encode()
        elif path=='/gallery':
            content=('''<!doctype html><meta name="viewport" content="width=device-width"><style>body{margin:0;background:#111;color:white;font:14px system-ui}iframe{border:1px solid #555;display:block;margin:12px 0}h2{margin:16px}</style>
              <h2>Native layout · desktop 1280px</h2><iframe src="/?state=success" width="1280" height="900"></iframe>
              <h2>Native layout · tablet 768px</h2><iframe src="/?state=off&theme=light" width="768" height="900"></iframe>
              <h2>Native layout · mobile 390px</h2><iframe src="/?state=success" width="390" height="900"></iframe>''').encode()
        elif path=='/static/sxng-ltr.min.css': content,content_type=css,'text/css'
        elif path=='/anonexplo-search.css': content,content_type=(ROOT/'configs/preview/search.css').read_bytes(),'text/css'
        elif path=='/anonexplo-preview.js': content,content_type=(ROOT/'configs/preview/preview-v2.js').read_bytes(),'application/javascript'
        else:
            self.send_response(404);self.end_headers();return
        self.send_response(200);self.send_header('Content-Type',content_type)
        self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)

print('Authored native fixture ready: http://127.0.0.1:18086/ (no provider/model requests)',flush=True)
ThreadingHTTPServer(('127.0.0.1',18086),Handler).serve_forever()
