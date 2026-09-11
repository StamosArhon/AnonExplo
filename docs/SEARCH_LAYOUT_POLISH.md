# Native search layout polish

## Direction and scope

User requested product-design-studio to refine the existing SearXNG browser UI.
The supplied screenshot and native theme were the visual references: an oversized
status block and stacked diagnostics displaced the first result. Selected a quiet
editorial direction, not a replacement UI or dashboard. No external inspiration
assets, fonts, packages, trackers or dependencies were needed.

- Results are the primary reading column; native diagnostics sit alongside on
  wide screens and below results/pagination below 1100px. Nothing is removed.
- Compact preferred-source control with a 44px toggle, short status summary,
  visible local-ranking/extra-VPN-query disclosure and native expandable privacy
  explanation. OFF restoration, saved choice and all request limits unchanged.
- Consistent source-first metadata, headline and snippet rhythm for native and
  additional results. Small preferred-source labels replace repetitive long
  attribution lines. Missing snippets get a truthful explanation, not invented text.
- Native theme colors, 16px default root (still browser-zoomable), 48rem maximum
  reading column, modest radii, visible keyboard focus and reduced-motion support.
  Dark/light preferences remain native; no forced theme or remote typography.
- Search filters wrap at small widths. Search/settings overlap at tablet width
  was caught during rendering and corrected. Media-specific result grids are
  excluded from the reading-column override.

## Implementation and boundaries

`configs/preview/search.css` is served locally at `/anonexplo-search.css`, loaded
by the already-present preview script. CSS is scoped to `ae-polished` native
results pages. No SearXNG image/template guard, ranking function, model, query,
source list, stored choice, provider setting or network boundary is changed.
The small DOM additions use createElement/textContent, not fetched HTML.

Deployment needs nginx configuration validation/reload only. Source/asset bind
mounts mean fresh pages see JS/CSS updates; existing tabs retain their loaded UI
until reloaded. No search/model/VPN restart, ban reset or browser profile edit.
Rollback is the previous versions of preview-v2.js/nginx-locations.conf from
9d7dec9, followed by nginx test/reload; the core search image remains unchanged.

## Visual verification

The design skill required a render/critique/revise pass, not just passing builds.
`render-design-fixture.py` renders the **installed native Jinja templates** with
authored English/Greek text. `design-fixture-server.py` temporarily serves those
templates/native CSS on 127.0.0.1:18086 with mocked model/search responses. No
production queries, result payloads, history, private sources or remote assets.
The fixture is developer-only, not a product service or deployed route.

Brave exposed no CDP endpoint; the browser skill's no-relaunch rule led to using
an isolated in-app browser test tab. Rendered dark success, dark loading/failure,
light OFF, expanded privacy and long Greek/missing-snippet states. Screenshots
inspected at desktop, tablet and mobile; DOM geometry checked at 320/390/768/1440
CSS pixels: no horizontal overflow, 44px toggle, diagnostics below on narrow
screens and alongside on desktop. Keyboard Tab reaches the privacy summary with
a visible outline. Loading cancellation restores six original fixture nodes.
Small text and tablet overlap were corrected after the initial screenshots.

Limits: not a full accessibility audit, actual Brave/device hardware test or
complete image/video layout evaluation. Native core JS is disabled in the visual
fixture so it cannot send searches; behavior regression tests run the actual
preview script separately. No claim of a ranking/coverage improvement here.

## Validation and delivery

Full validate.ps1 passed: 107 host tests, both preview DOM suites, Compose policy
and negative cases, managed image build with unchanged production tag, native
date/settings/privacy guards, blocked egress, outage/recovery and cleanup.
Final disclosure/CSS smoke assertions pass separately after visual edits.
Deployed with nginx test/reload only. All four container identities and health
unchanged; actual gateway JS/CSS byte equality, no-store/no-referrer, request
restrictions and existing local-ranker/budget smoke pass (two pairs 0.13s).
Temporary test tab closed, viewport override reset and fixture server stopped.
Reviewed/pushed scoped branch is merged to main and cleaned up at closeout.
No installer, image publication, provider query or model inference rebenchmark
was required by this presentation-only change.
