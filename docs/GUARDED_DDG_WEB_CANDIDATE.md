# Guarded DDG Web Candidate (2026-09-10)

Approved batch: implement destination safeguards, test offline, assess live-trial
readiness. Scope stamos/guarded-ddg-web-candidate from main 637ade0. This is actual
experiment code, not a production adapter update or a DDG News timeout repair.

## Frozen Source And Isolation

`provision-ddg-web-review.ps1` explicitly downloads the official
[adapter at commit 765a999](https://github.com/searxng/searxng/blob/765a9999dfde789c3b194c2474f86f3212675c36/searx/engines/duckduckgo_web.py)
into ignored build/ddg-web-review. SHA256:
`e3cf8fe33807c62d504a2b39e790e38ce6353850a367816fbdcce6c441ee7f73`.
Mismatch refuses use, with no automatic replacement. No host import/install.

`test-ddg-web-candidate.ps1` verifies this source again and runs only mocks in
a disposable network=none container: non-root, read-only root/source mounts,
dropped capabilities, no-new-privileges, no Docker logs, capped memory/CPU/pids,
and capped noexec /tmp tmpfs. No ports, VPN namespace, credentials, production
cache or settings mount. Runtime downloading is absent. `-Live` refuses.
The Python runner also verifies source hashes before importing the upstream
module. Normal SearXNG import-time data caches can exist only in disposable /tmp;
the adapter's query/token/pagination cache is replaced with a no-op and its setup
function is never called. Logs are disabled; output contains counts/test IDs only.

## Implemented Boundary

`ddg_web_guard.py` wraps the real upstream request/response functions, replacing
only their transport, cache and challenge helper in the isolated module:

- First fetch must be HTTPS duckduckgo.com with path /; subsequent fetches must
  be HTTPS links.duckduckgo.com with path /d.js. No credentials, explicit ports,
  fragments, foreign hosts, malformed URLs, control/non-ASCII URL characters or
  backslashes. URLs are capped at 8,192 characters.
- Redirects disabled, TLS verification required, browser-profile default headers
  disabled. Outgoing header allowlist excludes Cookie, Authorization and Host;
  Referer is restricted to the DDG root. These are asserted mock call options,
  not yet proof of a real client's behaviour or session-cookie isolation.
- At most three calls: first-page HTML, API response, one challenge follow-up.
  No retry or second challenge. First page only, fresh module/instance per query;
  no query-bearing cache or pagination reuse.
- Six-second shared deadline with at most two seconds for the first fetch;
  remaining budget passed to later calls. Expired work rejects before a call
  and after transport/parsing. This does not implement cancellation of a real
  underlying client or preempt CPU parsing.
- Post-buffer response limit of 1 MiB of decoded text, not a streaming byte cap.
  Challenge text capped at 65,536 characters, 32 definitions/operations,
  512-character used function bodies, bounded numeric operands and exact-JS
  integer range. Only arithmetic and four fixed HTML-length mappings are used;
  no response JavaScript evaluation. This is a bounded pattern recognizer,
  not a complete JavaScript parser or proven coverage of live challenges.

## Evidence And Live-Trial Decision

Twelve pure guard tests plus eighteen exact-adapter mock tests cover destination
and parser rejection, valid synthetic results/challenges, header/redirect flags,
shared deadlines, empty results, no retries on errors/429, repeated challenges,
size bounds and no cache/reuse. Fixtures are synthetic in-memory responses, not
fetched provider payloads or new live holdouts. No browser history is used.

Decision: **not ready for a live trial yet**. Offline request/response behaviour
is testable, but this executor deliberately bypasses the native online processor.
The pinned processor does not forward the new default_headers option, and this
experiment does not implement native suspension/cooldown integration. Dropping
it into production would not reproduce the tested execution boundary.

Next coherent scope is an offline, exact-guarded processor/transport integration:
verify option forwarding (including False), session cookie isolation, actual
redirect refusal, response-size/cancellation behaviour and native cooldown/error
mapping without contacting providers. Only then decide on a separately scoped
VPN-only first-page web trial with fresh frozen fixtures, no concurrent searches,
normal cooldowns, pacing and stop-on-degradation. Do not retry retired News tests.

Even a successful web trial would not establish a News timeout fix or better
relevance. The upstream adapter still lacks SafeSearch/time-range/trait support;
retain user choices and do not silently ignore filters. No image/config/engine
enablement, timeout adjustment, VPN change or production restart in this batch.

## Validation And Delivery

Initial 56 host tests and 14 native adapter tests passed. Four additional native
boundary cases and stronger result assertions were then added. A separate source
inspection attempt failed because import-time caches had no writable /tmp;
switched to read-only source inspection, without relaxing the test container.
Full validate.ps1 -WebCandidate passed: 110 Python test executions (30 new),
20 negative Compose cases, seven negative identity cases plus equality,
source/binding checks, managed isolated build with production tag unchanged,
native privacy/settings/ranking, blocked egress, outage/recovery and cleanup.
Explicit -Live refusal passed. The old optional transport-version comparison
was not repeated. Reviewed tooling/docs accompany commit/push, main merge and
scoped branch cleanup. No installer or release applies to this intentionally
offline experiment.
