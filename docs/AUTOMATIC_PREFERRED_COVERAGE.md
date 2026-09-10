# Remembered preferred-source coverage (v2)

## Approved scope

The user accepted automatic supplementary searches **when Preferred sources is
ON**, after discussing that missing sites cannot be recovered by reranking alone.
This is a separately scoped exception to the prohibition on hidden expansion:
the native page explains the extra searches and upstream disclosure. OFF is the
initial default. Only the ON/OFF boolean is saved in browser localStorage; no
query, result, model score or browsing history is persisted by this feature.

No new provider, account, remote model, page fetcher or standalone interface.
Native search/VPN configuration and cooldowns are unchanged. Existing private
domains remain in the ignored local preferences file, not in source code.

## Behavior and bounds

1. Native results appear normally. ON first ranks the first 24 flat General-style
   result nodes with the existing network-none multilingual model. Results are
   ordered by model relevance, with a +0.02 preferred-site advantage only at
   relevance >=0.8. This supersedes v1's native-score percentage/two-position cap.
   The score is heuristic, not calibrated probability or a factual-truth test.
2. Eligible first-page General searches may then issue at most **two extra
   SearXNG searches**, each containing up to nine preferred-domain `site:` filters
   joined by `OR`. Each SearXNG search can contact multiple configured engines.
   The original query is not translated, paraphrased or sent to a remote model.
   Native language, time and SafeSearch filters come from rendered RSS metadata;
   existing search cookies are forwarded only to same-origin SearXNG. No explicit
   engine selector is combined with categories. Custom engine/bang/site queries,
   later pages, non-General categories and native engine errors skip expansion.
3. There is a 15-second delay before each extra request. The model process grants
   at most one two-search allowance per 60 seconds across tabs, in memory only.
   No queue or scheduled retry. More than 18 configured domains disables coverage
   rather than silently truncating the list. An allowance is a local rate-limit
   decision, not a provider credential/token. Reloads do not reset that process.
4. Up to four unique candidates per group, eight total, are filtered to actual
   preferred HTTP(S) hostnames. Userinfo/lookalike hosts, duplicate native/tail
   links and unsupported templates are rejected. No target article is fetched.
   At most 32 title/snippet pairs are ranked locally in eight-pair microbatches.
   Additional results require relevance >=0.8; every original candidate remains.
   Unscored native results beyond 24 stay in their original tail order.
5. OFF cancels pending work, removes additions and restores original DOM nodes.
   Already-dispatched server-side searches/inference may still finish. Re-enabling
   on the same page reuses completed in-memory results and never repeats searches.
   Other tabs turning OFF cancel this page too; another tab turning ON does not
   retroactively dispatch work here. A new page honors the remembered setting.

Any native/supplementary engine error stops coverage, without retries. Late,
invalid, busy or failed model calls retain the most recent successful local
ordering, or native order if initial ranking failed. No initial model success
means no supplementary queries. Partial supplemental responses are discarded.
The status explains skipped searches, failures and additions; OFF always works.

## Privacy and isolation

The browser POSTs supplemental queries only to existing localhost `/search`;
provider egress remains SearXNG -> existing Proton namespace. Providers can see
and retain both query text and preferred-domain filters. A VPN does not remove
that disclosure or make identifying query text anonymous. Opened links still
use ordinary browser networking. localStorage retains only the preference bit.

`/anonexplo-preview/rank-v2` and `/plan` use the existing gateway/Unix socket.
No model network or listener port. POST/JSON, cross-site/method/host restrictions,
quiet logs, no-store/no-referrer and 64KiB in-memory request limits remain.
Browser JSON responses are streamed with a 1MiB cap. Per-call browser timeouts
are 10s for model/plan and 12s for supplemental search; the v2 server refuses
inference results after 8s (in-flight computation is not forcibly killed).
Model/artifact pins, explicit provisioning, non-root/read-only resource policy
and disabled telemetry remain unchanged. No query-bearing disk cache added.

## Operator support and deployment

Brave documents `site:` and `OR`, but describes search operators as experimental:
https://search.brave.com/help/operators . Other configured engines may interpret
combinations differently. Post-filtering prevents off-list admission; it cannot
force indexing, exhaust a site's coverage or guarantee any particular article.
Two grouped searches are a bounded coverage attempt, not a per-site crawl.

Versioned endpoints and `preview-v2.js` preserve already-open v1 pages. The old
`preview.js` and `/rank` remain for compatibility/rollback, not a separate UI.
After validation, `scripts/deploy-preview-update.ps1` replaces only the separate
model container, tests/reloads nginx and verifies unchanged core container IDs.
It does not restart SearXNG/VPN, reset bans or issue provider searches.
Rollback can select `preview.js` in nginx-locations.conf and reload nginx;
ordinary native search also works with the separate model stopped.

## Validation

- 107 host tests, including eight new ranking/admission/bounds/shared-budget tests.
- Actual v2 JS in a synthetic DOM: default/remembered choice, two-search cap,
  pacing, safe URL/deduplication, effective filters, restoration/unscored tail,
  cancellation, cross-tab OFF, malformed/busy/failure and no retries.
- Eight real Unix transport tests. Network-none actual model: 32 longer authored
  pairs in 3.809s, four relevant additions admitted, four irrelevant additions
  rejected, all 24 original candidates retained. This is not a broad benchmark.
- Full isolated validator passed: Compose policies, managed image build (live
  image tag unchanged), historical regression suites, native settings/date guards,
  privacy, blocked egress, outage/recovery and isolated cleanup.
- Deployment, updated gateway smoke and bounded browser/live coverage verification
  pending at implementation checkpoint. Do not claim live coverage or quality
  improvement based on deterministic fixtures alone.

One fresh functional browser fixture, fixed before dispatch: `cross border
investigative journalism`, General/Anytime/auto, one native search and at most the
two automatic follow-ups. Check UI state, provider-error stop, bounded dispatch,
addition counts and exact OFF restoration. No article text, query response or
browser history stored. This is an integration check, not a quality holdout;
stop on degradation, no retry or replacement fixture in this scope.
