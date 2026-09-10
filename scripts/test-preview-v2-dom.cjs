// Execute the shipped JS with authored DOM/transport fixtures; no network or history.
const {readFileSync} = require('node:fs');
const {runInNewContext} = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const source = readFileSync(path.join(__dirname, '../configs/preview/preview-v2.js'), 'utf8');
const tick = () => new Promise(resolve => setImmediate(resolve));
function fixture(options = {}) {
  const calls = [], elements = [], writes = [], waits = [], events = {};
  class Element {
    constructor(tag) { this.tag=tag;this.style={};this.children=[];elements.push(this); }
    append(...nodes) { for (const n of nodes) { n.parent=this;this.children.push(n); } }
    insertBefore(n, anchor) { n.remove();n.parent=this;this.children.splice(anchor?this.children.indexOf(anchor):this.children.length,0,n); }
    remove() { if(this.parent) {this.parent.children.splice(this.parent.children.indexOf(this),1);this.parent=null;} }
    setAttribute(k,v) {this[k]=v;}
    addEventListener(k,fn) {this[k]=fn;}
  }
  const urls = new Element('main');
  const native = Array.from({length:26},(_,i)=>{
    const n = new Element('article'); n.i=i;n.dataset={aeScore:'1'};
    n.matches=()=>!options.group;n.hasAttribute=()=>true;
    n.querySelector=s=>s==='h3 a'?{href:`https://other.example/${i}`}:{textContent:'Public authored fixture'};
    return n;
  });
  urls.append(...native);
  const meta = new URL('http://127.0.0.1:8085/search');
  meta.search = new URLSearchParams({q:'public fixture', categories:options.category||'general', pageno:'1', language:'el',time_range:'month',safesearch:'2'});
  const document = {getElementById:()=>urls,createElement:t=>new Element(t),querySelector:s=>{
    if(s==='input[name="q"]') return {value:'public fixture'};
    if(s.startsWith('link[')) return {href:meta.href};
    if(s==='#engines_msg .response-error') return options.nativeError?{}:null;
    return null;
  }};
  let searches=0;
  const context = {document, location:{href:'http://127.0.0.1:8085/search?q=public+fixture'},
    URL, URLSearchParams, AbortController, TextDecoder,
    window:{addEventListener:(k,fn)=>events[k]=fn},
    localStorage:{getItem:()=>options.remember?'on':null,setItem:(k,v)=>writes.push([k,v])},
    setTimeout:(fn,ms)=>{ if(ms===15000){waits.push(fn);if(!options.hold)queueMicrotask(fn);return 1;} return setTimeout(fn,ms); },clearTimeout,
    fetch:async (url,init)=>{
      calls.push({url,init});
      if(options.fail) throw Error('offline');
      let data;
      if(url.endsWith('/rank-v2')) {
        const body=JSON.parse(init.body);const count=body.results.length;
        data={version:2,order:[1,0,...Array.from({length:count-2},(_,i)=>i+2)],moved:2,added:count-body.native_count};
        if(options.invalid) data.order=[0,0];
      } else if(url.endsWith('/plan')) data={version:2,groups:options.cooldown?[]:[['example.org'],['second.example']]};
      else {
        searches++;
        const params=new URLSearchParams(init.body);
        assert.equal(params.get('language'),'el');assert.equal(params.get('time_range'),'month');assert.equal(params.get('safesearch'),'2');
        assert.equal(params.has('engines'),false);assert.equal(init.credentials,'same-origin');
        const host=searches===1?'example.org':'second.example';
        const good={url:`https://${host}/a`,title:'<img src=x onerror=alert(1)>',content:'Authored fixture'};
        data={unresponsive_engines:options.engineError?[['fixture','timeout']]:[],results:[good,good,
          {...good,url:'javascript:alert(1)'},{...good,url:`https://not${host}/a`},
          {...good,url:`https://${host}@evil.example/a`}]};
      }
      const raw=Buffer.from(JSON.stringify(data));let done=false;
      return {ok:true,body:{getReader:()=>({read:async()=>done?{done:true}:(done=true,{done:false,value:raw}),cancel:async()=>{}})}};
    }};
  runInNewContext(source,context);
  return {urls,native,calls,writes,waits,events,button:elements.find(e=>e.tag==='button'),
    get searches(){return searches;}, async settle(){for(let i=0;i<60;i++)await tick();}};
}
(async()=>{
  const f=fixture();assert.equal(f.calls.length,0);
  await f.button.click();
  assert.equal(f.searches,2);assert.equal(f.calls.filter(c=>c.url.endsWith('rank-v2')).length,2);
  assert.equal(f.urls.children.filter(n=>n.tag==='article').length,28);
  assert.deepEqual(f.urls.children.slice(-2).map(n=>n.i),[24,25]);
  assert.equal(f.writes[0][1],'on');
  await f.button.click();
  assert.deepEqual(f.urls.children.slice(1),f.native);
  await f.button.click();assert.equal(f.searches,2);assert.equal(f.calls.length,5);
  const remembered=fixture({remember:true});await remembered.settle();assert.equal(remembered.searches,2);
  for(const opt of [{fail:true},{invalid:true},{cooldown:true},{nativeError:true},{category:'news'}]) {
    const t=fixture(opt);await t.button.click();assert.equal(t.searches,0);
    await t.button.click();assert.deepEqual(t.urls.children.slice(1),t.native);
  }
  const degraded=fixture({engineError:true});await degraded.button.click();assert.equal(degraded.searches,1);
  const cancel=fixture({hold:true});const running=cancel.button.click();await cancel.settle();
  await cancel.button.click();await running;assert.equal(cancel.searches,0);assert.deepEqual(cancel.urls.children.slice(1),cancel.native);
  await cancel.button.click();assert.equal(cancel.searches,0);
  const tab=fixture({hold:true});const task=tab.button.click();await tab.settle();
  tab.events.storage({key:'anonexplo.preferredSources.v2',newValue:'off'});await task;assert.equal(tab.searches,0);
  assert.equal(fixture({group:true}).button,undefined);
  console.log('PASS: v2 remembered opt-in, bounded paced coverage, safe dedupe, filters, restore, cancellation, shared OFF, failure/no-retry.');
})().catch(e=>{console.error(e);process.exitCode=1;});
