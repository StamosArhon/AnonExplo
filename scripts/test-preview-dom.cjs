// Execute the actual browser script with a minimal DOM; no browser/user data.
const {readFileSync} = require('node:fs');
const {runInNewContext} = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const source = readFileSync(path.join(__dirname, '../configs/preview/preview.js'), 'utf8');
function fixture(count=3, mode='ok') {
  let fetches = 0;
  const elements = [];
  const nodes = Array.from({length:count}, (_,i) => ({i, dataset:{aeScore:'1'},
    matches: () => mode !== 'group', hasAttribute: () => true,
    querySelector: s => s === 'h3 a' ? {href:`https://example.org/${i}`} : {textContent:'Public test'}
  }));
  const urls = {children:[...nodes], before: p => {}, insertBefore(n, anchor) {
    this.children.splice(this.children.indexOf(n),1);
    this.children.splice(anchor ? this.children.indexOf(anchor) : this.children.length,0,n);
  }};
  const document = {getElementById: () => urls, querySelector: () => ({value:'Public fixture'}),
    createElement: tag => { const e = {tag,style:{},setAttribute(k,v){this[k]=v},append(){},addEventListener(k,fn){this.click=fn}}; elements.push(e);return e; }};
  const context = {document, AbortController, setTimeout, clearTimeout, fetch: async () => {
    fetches++;
    if (mode === 'failure') throw Error('offline');
    return {ok:true, json:async()=>({order: mode==='invalid'?[0,0,0]:[1,0,...Array.from({length:Math.min(count,24)-2},(_,i)=>i+2)],promoted:1,seconds:.5,status:'applied'})};
  }};
  runInNewContext(source, context);
  return {urls,nodes,button:elements.find(e=>e.tag==='button'),get fetches(){return fetches}};
}
(async()=>{
  const f=fixture(26);
  assert.equal(f.fetches,0);
  await f.button.click();
  assert.equal(f.fetches,1);
  assert.deepEqual(f.urls.children.slice(0,3).map(n=>n.i),[1,0,2]);
  assert.deepEqual(f.urls.children.slice(24).map(n=>n.i),[24,25]);
  await f.button.click();
  assert.deepEqual(f.urls.children.map(n=>n.i),f.nodes.map(n=>n.i));
  await f.button.click();
  assert.equal(f.fetches,1);
  for(const mode of ['failure','invalid']) {
    const t=fixture(3,mode);await t.button.click();
    assert.deepEqual(t.urls.children.map(n=>n.i),[0,1,2]);
    assert.equal(t.button['aria-pressed'],'false');
    assert.equal(t.button.disabled,false);
  }
  assert.equal(fixture(3,'group').button,undefined);
  console.log('PASS: preview DOM opt-in, reorder, tail, restore, cached toggle, failures and group protection.');
})().catch(()=>{process.exitCode=1;console.error('FAIL: preview DOM tests');});
