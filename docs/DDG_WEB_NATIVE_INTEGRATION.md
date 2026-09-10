# Offline DDG Web Native Integration (2026-09-10)

Historical integration-stage record. The later separate trial wrapper and its
blocked preflight outcome are documented in DDG_WEB_GUARDED_TRIAL.md; the offline
test wrapper remains network-disabled and continues to refuse its -Live flag.

Approved batch on stamos/ddg-web-native-integration from main 088bfa6: implement
and test native networking/processor integration, fix demonstrated candidate gaps,
validate and close Git. No production update, live query, account or deployment.
This completes the next integration scope from GUARDED_DDG_WEB_CANDIDATE.md.

## Implemented Candidate

`ddg_web_integration.py` adds an offline-only processor subclass and transport.
Exact existing source checks remain, with additional hashes for the native
abstract processor, HTTP-error mapper and exception classes. The upstream web
source still requires explicit hash-pinned provisioning; no runtime download.

The subclass retains native OnlineProcessor.search, exception handling, result
extension and SuspendedStatus. Its isolated dispatch checks native suspension
before every request, including with a newly created processor using the same
network identity. It uses the guarded executor for request/response processing
instead of the pinned _send_http_request method: that method demonstrably drops
default_headers=False. No global monkeypatch or installed source repair is made.
The direct path explicitly forwards False to the actual client; other engines
and production processor behaviour are unchanged.

Native client acquisition and HTTP error mapping are reused. There is exactly
one transport attempt: Network.request's special ConnectionError retry is not
used by this candidate, and nonzero client retry configuration is rejected.
Native 429/403/HTTP-error/timeout handling still sets the corresponding cooldown.
Safety rejections become generic RequestException failures rather than healthy
empty results; native failure suspension applies. Unsupported page, SafeSearch,
time-range and explicit locale requests are declined, never silently weakened.
Only first-page, SafeSearch=0, no time range, locale=all is supported here.

Additional safeguards:

- The shared deadline is bounded by the native caller's remaining timeout and
  six seconds, with at most two seconds for first-page discovery. Async wait_for
  cancels over-budget work; the synchronous caller also requests future
  cancellation if it times out. Its 0.2s wait allowance is for cleanup, not more
  request budget. Cancellation is cooperative, not a guarantee under a frozen
  process/event loop; CPU parsing is not preempted.
- A native content callback caps retained decompressed body bytes at 1 MiB and
  aborts the transfer before retaining an excess chunk. The guarded parser's
  existing post-buffer text/challenge limits also remain. Headers, native TLS
  allocations and OS buffers are not covered by this body-byte cap.
- Client retries must be zero, discard_cookies must be enabled and the session
  cookie jar must be empty. Each request also sets discard_cookies=True. A
  contaminated jar is rejected, not silently cleared. Supplied Cookie/Auth/Host
  headers are filtered by the guarded executor. No cross-query token cache.
- Native error metrics are stubbed and logging disabled in the isolated runner;
  it emits only counts, test IDs and, on failure, allowlisted error classes/source
  locations. This is not a claim that production's native exception recorder is
  payload-free. A future trial must retain disabled logs/exception capture.

## Real TLS Test Boundary

`test-ddg-web-candidate.ps1 -Integration` runs the actual pinned client, native
processor lifecycle and exact upstream adapter in the existing hardened
network=none container. No VPN/key/live-cache mounts or host ports. A non-root
loopback TLS server listens on container port 443; Docker's existing unprivileged
port setting permits this with all capabilities dropped. A host that disallows
it must fail, not gain privilege automatically.

The installed OpenSSL creates a one-day synthetic DDG-host test certificate/key
only under capped /tmp tmpfs. Tests pass its CA path and exact DNS overrides
through a test-only get_client wrapper. TLS verification and hostname checking
remain enabled; allowed application URLs stay unchanged. Neither test CA nor DNS
overrides are added to production or the transport helper. No public DNS/HTTPS
requests are possible in this container. A separate negative test leaves the
fixture certificate untrusted and confirms failure before an HTTP request.

Tests inspect only synthetic in-memory request/response data; no provider
payloads are persisted. Existing client reuse is exercised across two queries,
including Set-Cookie from a DDG-domain fixture. No cookies, Authorization,
automatic Accept-Language or client-hint headers arrive in later fixture calls.
The known safe User-Agent remains. No result destination is fetched.

## Evidence And Corrections

Twenty integration tests now pass, covering real TLS normal/challenge results,
cookie/header isolation on client reuse, poisoned-cookie refusal, redirect
refusal, native 429/403/503 mapping, shared cooldown and simulated expiry without
reset, cancellation/connection closure, no ConnectionError retry, body limits
including gzip expansion and the exact boundary, unsupported filters and the
pinned processor's False-option omission. Two additional host tests cover valid
shorter and invalid request budgets. No live relevance evidence is produced.

Initial fixture attempts failed before requests because the installed curl
binding cannot accept CONNECT_TO tuple options. Switched the test-only routing
to supported RESOLVE entries and container-loopback 443, without weakening TLS
or container privileges. An added mock caller-cancellation test initially omitted
required transport arguments; corrected the harness. All 20 final tests pass.

## Readiness Decision

The previously missing offline integration gates now have executable evidence.
A **separately scoped, bounded VPN-only web trial is technically justified**,
not a production rollout or a fix for DDG News. It must use fresh frozen public
fixtures, manually verify existing DDG cooldowns before starting, avoid concurrent
searches, maintain the same network identity/native suspension state for the
whole trial, pace queries, and stop on the first degradation without retry/reset.
An isolated process still cannot automatically inherit production's suspension
state; no restart/new object may be used to evade a preceding provider cooldown.

The shipped wrapper still refuses -Live, including -Integration -Live. A trial
runner/preflight is a separate change, not a switch to bypass this guard. Scope
the trial to the supported unfiltered first-page mode; retain metrics-only
output and no payload capture. Freeze success/topicality criteria before sending
fixtures. Only healthy trial/relevance evidence can justify enabling the web
engine or a production image change. News, Startpage, weights, timeouts, browser
configuration and the Proton profile remain unchanged.

## Validation And Delivery

Full validate.ps1 -WebCandidate passed: 132 Python test executions (22 new),
20 negative Compose cases, seven negative identity cases plus equality,
source/binding checks, managed isolated build with production tag unchanged,
native privacy/settings/ranking, blocked egress, outage/recovery and cleanup.
-Integration -Live refusal passed; the unrelated old transport-version comparison
was not repeated. Docker metadata confirms the same three healthy production
services without restart. Reviewed code/docs accompany commit/push, main merge
and local/remote branch cleanup. No installer, release or production deployment
applies to this offline tooling.
