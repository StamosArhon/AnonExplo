/* Native-page, opt-in same-response comparison. No storage or external requests. */
(() => {
  'use strict';
  const urls = document.getElementById('urls');
  const input = document.querySelector('input[name="q"]');
  if (!urls || !input) return;
  const all = [...urls.children];
  // Do not move results across native media/template groups.
  if (!all.length || !all.every(n => n.matches('article.result-default'))) return;
  const nodes = all.slice(0, 24);
  const query = input.value;
  const rows = nodes.map(n => ({
    url: n.querySelector('h3 a')?.href || '',
    title: (n.querySelector('h3')?.textContent || '').trim().slice(0, 180),
    content: (n.querySelector('.content')?.textContent || '').trim().slice(0, 400),
    score: n.hasAttribute('data-ae-score') ? Number(n.dataset.aeScore) : NaN
  }));
  if (!query || query.length > 512 || rows.some(r => !Number.isFinite(r.score) || r.score < 0 || !r.url)) return;
  const panel = document.createElement('div');
  panel.id = 'ae-preview';
  panel.style.cssText = 'margin:1rem 0;padding:.8rem;border:1px solid #777;border-radius:.5rem';
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = 'Preferred sources: OFF';
  button.setAttribute('aria-pressed', 'false');
  const status = document.createElement('span');
  status.setAttribute('role', 'status');
  status.style.marginInlineStart = '.75rem';
  status.textContent = 'Local preview · first 24 results · toggle to compare this same page.';
  panel.append(button, status);
  urls.before(panel);
  let cached = null;
  let enabled = false;
  function arrange(order) {
    // Preserve element identity, handlers and the unscored tail.
    const anchor = all[24] || null;
    for (const i of order) urls.insertBefore(nodes[i], anchor);
  }
  function show(result) {
    arrange(result.order);
    enabled = true;
    button.textContent = 'Preferred sources: ON';
    button.setAttribute('aria-pressed', 'true');
    status.textContent = result.promoted ? `${result.promoted} preferred result(s) promoted · ${result.seconds}s · toggle OFF to compare.` :
      (result.status === 'no_preferred_matches' ? 'Unchanged: no preferred sites in these results.' : 'Unchanged: no relevance-qualified promotions.');
  }
  button.addEventListener('click', async () => {
    if (enabled) {
      arrange(nodes.map((_, i) => i));
      enabled = false;
      button.textContent = 'Preferred sources: OFF';
      button.setAttribute('aria-pressed', 'false');
      status.textContent = 'Original SearXNG order restored. No new search sent.';
      return;
    }
    if (cached) { show(cached); return; }
    button.disabled = true;
    status.textContent = 'Checking relevance locally… Original results remain available.';
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 5000);
    try {
      const response = await fetch('/anonexplo-preview/rank', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        credentials: 'omit', cache: 'no-store', redirect: 'error', referrerPolicy: 'no-referrer',
        signal: controller.signal, body: JSON.stringify({query, results: rows})
      });
      if (!response.ok) throw new Error('unavailable');
      const result = await response.json();
      if (!Array.isArray(result.order) || result.order.length !== nodes.length ||
          new Set(result.order).size !== nodes.length ||
          !result.order.every(i => Number.isInteger(i) && i >= 0 && i < nodes.length) ||
          !Number.isInteger(result.promoted) || !Number.isFinite(result.seconds)) throw new Error('invalid');
      cached = result;
      show(result);
    } catch (_) {
      arrange(nodes.map((_, i) => i));
      status.textContent = 'Preview unavailable, busy or too slow. Original order retained.';
    } finally {
      clearTimeout(timer);
      button.disabled = false;
    }
  });
})();
