/* Explicit, remembered opt-in. Queries/results live only in this page's memory. */
(() => {
  'use strict';
  const urls = document.getElementById('urls');
  const input = document.querySelector('input[name="q"]');
  if (!urls || !input) return;
  const all = [...urls.children];
  if (!all.length || !all.every(n => n.matches('article.result-default'))) return;
  const native = all.slice(0, 24);
  const query = input.value;
  const rows = native.map(n => ({url: n.querySelector('h3 a')?.href || '',
    title: (n.querySelector('h3')?.textContent || '').trim().slice(0, 180),
    content: (n.querySelector('.content')?.textContent || '').trim().slice(0, 400),
    score: n.hasAttribute('data-ae-score') ? Number(n.dataset.aeScore) : NaN}));
  if (!query || query.length > 512 || rows.some(r => !Number.isFinite(r.score) || r.score < 0 || !r.url)) return;
  const key = 'anonexplo.preferredSources.v2';
  const panel = document.createElement('div');
  panel.id = 'ae-preview';
  panel.style.cssText = 'margin:1rem 0;padding:.8rem;border:1px solid #777;border-radius:.5rem';
  const button = document.createElement('button');
  button.type = 'button';
  const status = document.createElement('span');
  status.setAttribute('role', 'status');
  status.style.marginInlineStart = '.75rem';
  const explanation = document.createElement('p');
  explanation.textContent = 'ON: rank locally and search preferred sites too (up to 2 extra searches through your search VPN). Providers see the query and site filters. Only this ON/OFF choice is saved in this browser.';
  panel.append(button, status, explanation);
  // Stay inside the native results grid column, not a new grid sibling.
  urls.insertBefore(panel, all[0]);
  let enabled = false, attempted = false, pending = false, cached = null, controller = null;
  let activeNodes = [...native];
  function label() {
    button.textContent = `Preferred sources: ${enabled ? 'ON' : 'OFF'}`;
    button.setAttribute('aria-pressed', String(enabled));
  }
  function arrange(order, nodes) {
    for (const n of activeNodes.slice(native.length)) n.remove();
    activeNodes = nodes;
    for (const i of order) urls.insertBefore(nodes[i], all[24] || null);
  }
  function restore() { arrange(native.map((_, i) => i), [...native]); }
  function display(result) {
    if (!enabled) return;
    arrange(result.order, result.nodes);
    status.textContent = result.message;
  }
  async function request(path, body, signal, search = false) {
    const timeout = new AbortController();
    const abort = () => timeout.abort();
    signal.addEventListener('abort', abort, {once: true});
    const timer = setTimeout(abort, search ? 12000 : 10000);
    let reader;
    try {
      if (signal.aborted) throw Error('cancelled');
      const response = await fetch(path, {method: 'POST',
        headers: {'Content-Type': search ? 'application/x-www-form-urlencoded' : 'application/json'},
        credentials: search ? 'same-origin' : 'omit', cache: 'no-store', redirect: 'error',
        referrerPolicy: 'no-referrer', signal: timeout.signal, body});
      if (!response.ok) throw Error('unavailable');
      reader = response.body.getReader();
      const decoder = new TextDecoder();
      let text = '', size = 0;
      while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > 1048576) throw Error('response limit');
        text += decoder.decode(value, {stream: true});
      }
      return JSON.parse(text + decoder.decode());
    } finally {
      if (reader) await reader.cancel().catch(() => {});
      clearTimeout(timer);
      signal.removeEventListener('abort', abort);
    }
  }
  function pause(signal) {
    return new Promise((resolve, reject) => {
      if (signal.aborted) { reject(Error('cancelled')); return; }
      const abort = () => { clearTimeout(timer); reject(Error('cancelled')); };
      const timer = setTimeout(() => { signal.removeEventListener('abort', abort); resolve(); }, 15000);
      signal.addEventListener('abort', abort, {once: true});
    });
  }
  function canonical(value) {
    try {
      const u = new URL(value);
      if (!['https:', 'http:'].includes(u.protocol) || u.username || u.password) return null;
      u.hash = '';
      // Do not strip arbitrary query parameters which can identify distinct articles.
      u.hostname = u.hostname.replace(/^www\./, '');
      u.pathname = u.pathname.replace(/\/$/, '') || '/';
      return u.href;
    } catch (_) { return null; }
  }
  function matches(value, domains) {
    const url = canonical(value);
    if (!url) return false;
    const host = new URL(url).hostname;
    return domains.some(d => host === d || host.endsWith('.' + d));
  }
  function coverageParameters() {
    // Rendered RSS metadata contains the effective native POST/cookie filters.
    const link = document.querySelector('link[rel="alternate"][type="application/rss+xml"]');
    if (!link) return null;
    const p = new URL(link.href, location.href).searchParams;
    const current = new URL(location.href).searchParams;
    if (p.get('q') !== query || p.get('categories') !== 'general' || p.get('pageno') !== '1' ||
        current.has('engines') || /(^|\s)[!:]|\b(?:site|inurl|intitle|filetype):/i.test(query) ||
        document.querySelector('#engines_msg .response-error')) return null;
    const result = new URLSearchParams({format: 'json', categories: 'general', pageno: '1'});
    for (const name of ['language', 'time_range', 'safesearch']) {
      if (!p.has(name)) return null;
      result.set(name, p.get(name));
    }
    return result;
  }
  function nodeFor(row) {
    const article = document.createElement('article');
    article.className = 'result result-default';
    const heading = document.createElement('h3');
    const link = document.createElement('a');
    link.href = row.url;
    link.rel = 'noopener noreferrer';
    link.textContent = row.title;
    heading.append(link);
    const content = document.createElement('p');
    content.className = 'content';
    content.textContent = row.content;
    const attribution = document.createElement('p');
    attribution.textContent = `${new URL(row.url).hostname} · Additional preferred-source search`;
    article.append(heading, content, attribution);
    return article;
  }
  async function rank(candidates, nodes, signal, note) {
    const r = await request('/anonexplo-preview/rank-v2', JSON.stringify({query, results: candidates, native_count: native.length}), signal);
    if (signal.aborted) throw Error('cancelled');
    if (r.version !== 2 || !Array.isArray(r.order) || new Set(r.order).size !== r.order.length ||
        !r.order.every(i => Number.isInteger(i) && i >= 0 && i < nodes.length) ||
        !native.every((_, i) => r.order.includes(i)) || !Number.isInteger(r.added) ||
        r.added !== r.order.filter(i => i >= native.length).length || !Number.isInteger(r.moved)) throw Error('invalid');
    cached = {order: r.order, nodes, message: `${r.moved} original result(s) moved · ${r.added} relevant addition(s). ${note} OFF restores the original page.`};
    display(cached);
  }
  async function run() {
    pending = true;
    controller = new AbortController();
    const signal = controller.signal;
    status.textContent = 'Ranking locally… Original results remain available.';
    try {
      await rank(rows, [...native], signal, 'Checking extra-source availability.');
      const params = coverageParameters();
      if (!params) { cached.message = 'Local relevance ranking applied. Extra searches skipped: restricted query, later page, category or engine errors. OFF restores the original page.'; display(cached); return; }
      const plan = await request('/anonexplo-preview/plan', '{}', signal);
      if (signal.aborted) return;
      if (plan.version !== 2 || !Array.isArray(plan.groups) || plan.groups.length > 2 ||
          !plan.groups.every(g => Array.isArray(g) && g.length > 0 && g.length <= 9 && g.every(d =>
            typeof d === 'string' && d.length <= 253 && /^[a-z0-9]+(?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9]+(?:[a-z0-9-]*[a-z0-9])?)+$/.test(d)))) throw Error('invalid plan');
      if (!plan.groups.length) { cached.message = 'Local ranking applied. Extra searches skipped by the shared request limit; no automatic retry. OFF restores the original page.'; display(cached); return; }
      const seen = new Set(all.map(n => canonical(n.querySelector('h3 a')?.href)));
      const additions = [];
      let searches = 0;
      for (const group of plan.groups) {
        // Pace even the first extra search after the original response.
        status.textContent = `Local ranking applied. Waiting briefly before preferred-source search ${searches+1}/${plan.groups.length}…`;
        await pause(signal);
        if (signal.aborted) return;
        params.set('q', `${query} (${group.map(d => 'site:' + d).join(' OR ')})`);
        const response = await request('/search', params.toString(), signal, true);
        searches++;
        if (signal.aborted) return;
        if (!Array.isArray(response.results) || !Array.isArray(response.unresponsive_engines) || response.unresponsive_engines.length) throw Error('engine failure');
        let perGroup = 0;
        for (const r of response.results.slice(0, 100)) {
          if (perGroup >= 4) break;
          if (!r || typeof r.url !== 'string' || r.url.length > 2048 ||
              typeof r.title !== 'string' || typeof r.content !== 'string' ||
              (r.template && r.template !== 'default.html') || !matches(r.url, group)) continue;
          const id = canonical(r.url);
          if (seen.has(id)) continue;
          seen.add(id);
          additions.push({url: r.url, title: r.title.slice(0, 180), content: r.content.slice(0, 400), score: 0});
          perGroup++;
        }
      }
      if (additions.length) await rank([...rows, ...additions], [...native, ...additions.map(nodeFor)], signal, `${searches} extra search(es) completed.`);
      else { cached.message = `Local ranking applied. ${searches} extra search(es), no new matching links found. OFF restores the original page.`; display(cached); }
    } catch (_) {
      if (signal.aborted) return;
      if (!cached) restore();
      const message = cached ? 'Local ranking retained. Extra search or final ranking unavailable; stopped without retries.' : 'Local ranking unavailable; original page retained. No extra searches sent.';
      if (cached) cached.message = message;
      status.textContent = message;
    } finally {
      pending = false;
    }
  }
  async function setEnabled(value, persist) {
    enabled = value;
    if (persist) { try { localStorage.setItem(key, enabled ? 'on' : 'off'); } catch (_) { /* Storage may be disabled. */ } }
    label();
    if (!enabled) {
      if (pending && cached) cached.message = 'Completed local ranking retained; remaining extra work cancelled. No retry on this page.';
      controller?.abort();
      restore();
      status.textContent = 'Original page restored. No further extra searches will be sent.';
      return;
    }
    if (attempted) {
      if (cached) display(cached);
      else status.textContent = 'Original results retained; this page already attempted refinement. No retry.';
      return;
    }
    attempted = true;
    await run();
  }
  button.addEventListener('click', () => setEnabled(!enabled, true));
  window.addEventListener('pagehide', () => controller?.abort());
  window.addEventListener('storage', e => {
    // Other tabs turning OFF cancel this page too. ON affects the next search.
    if (e.key === key && e.newValue !== 'on') void setEnabled(false, false);
  });
  label();
  status.textContent = 'OFF: original SearXNG results. Enable to try local ranking and extra coverage.';
  try { if (localStorage.getItem(key) === 'on') void setEnabled(true, false); } catch (_) { /* Default OFF. */ }
})();
