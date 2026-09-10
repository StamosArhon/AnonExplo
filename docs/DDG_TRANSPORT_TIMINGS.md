# Bounded DDG Transport Timings (2026-09-10)

Approved batch step two, branch stamos/ddg-transport-timings from main 92202a1.
Step one fixed platform-manifest checks and isolated validation builds, without
restarting production. This step observes existing DDG transport behavior; any
search fix remains conditional on evidence and validation.

## Frozen Diagnostic

Maximum two new public fixtures: transport-battery (sodium ion battery recycling
research), transport-wetlands (Mediterranean wetland restoration research).
Only DDG News; one request per fixture, 20s spacing, first degradation stops the
run and forbids retry. No previous failed fixtures or private browser data.

The explicit -Transport mode uses the existing disposable same-image wrapper,
10s settling + 180s stable DDG error-history preflight, verified VPN namespace
and read-only resolver, no listener/ports, uid65534, read-only root, capped tmpfs/
resources, disabled logs and no production cache/key. Historical -Live without
-Transport remains refused. No retry, token/engine timeout, fingerprint, TLS
verification, DNS, HTTP version, provider, ranking or production change.

The installed curl_cffi session source SHA256 is guarded:
322ed676e7a9e666858bca7b281b314d47dae8a07902b2f3e705869f88fa7171.
Native async request and response-parsing hooks observe numeric curl error codes
and ten allowlisted libcurl counters before native handle cleanup, including on
failure. No debug/content callbacks, body, header, token, IP address or URL is
recorded. URL path is mapped in memory only to token/news/other stage labels.
No argument/return/exception mutation; an offline fake-transfer binding probe
exercises both success and timeout with the actual installed class hooks.

Counters are cumulative from transfer start, not independent phase durations:
[DNS completion](https://curl.se/libcurl/c/CURLINFO_NAMELOOKUP_TIME.html),
[TLS completion](https://curl.se/libcurl/c/CURLINFO_APPCONNECT_TIME.html),
[first response byte](https://curl.se/libcurl/c/CURLINFO_STARTTRANSFER_TIME.html).
Zero or missing counters require care with cached DNS/connection reuse; they are
not alone proof of a DNS fault. Connection count, status and downloaded byte
count help interpretation but do not identify server intent or prove blocking.
The trace remains capped/locked and metrics-only. Native internal retries and
synchronous-vs-transport timeout behavior are unchanged. One-second post-response
observation grace does not extend the native network budget.

## Observations And Decision

The single live run passed cooldown and production/VPN checks. No repeated
fixtures, operator retries, cache resets, exit rotation or production changes.

| Sample / endpoint | DNS | TCP | TLS | First-byte counter | Total | HTTP / bytes |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| battery / token | .142537 | .173333 | .268657 | .351302 | .377530 | 200 / 6261 |
| battery / news | .128577 | .163231 | .258981 | .610842 | .611007 | 200 / 5473 |
| wetlands / token | .000652 | 0 | 0 | 2.001725 | 2.001730 | 0 / 0 |

All timings are seconds. Each transfer reported one new connection, zero
redirects and zero OS errno. Battery: cold token cache, parsed token present,
23 news rows, no engine errors, native web response 1.000s. Wetlands: cold cache,
curl code 28 / native Timeout at 2.003s against the unchanged 2s transport limit
(caller wait 2.199s). Web response 2.025s, zero rows, one engine error. No token
parse completion or downstream news request. The run stopped at this failure.

The failure records a short DNS timing but no positive TCP/TLS completion
counters. The first-byte counter near the timeout is inconsistent with treating
it as evidence of a completed HTTP response: status and downloaded bytes are
zero. Preserve the raw numeric evidence; do not infer successful TLS, a server
response, deliberate blocking, a bad DNS resolver or a particular network hop.
This identifies another token-fetch timeout, not its precise underlying cause.
The successful sample establishes that the same path can work, not reliability.

Follow-up: OFFLINE_TIMEOUT_SEMANTICS.md reproduces this counter pattern with a
controlled loopback TLS-handshake stall in the same pinned client. TCP was
accepted and no response was sent. This strengthens the warning against reading
these failure counters literally; it does not uniquely diagnose the live failure.

Approved batch step three is an explicit no-change decision: these observations
do not validate a timeout increase, provider swap, retry, HTTP/TLS change or VPN
rotation. No speculative production search fix is shipped. Existing cooldowns,
engine mix, browser endpoint and VPN-only egress remain unchanged. The completed
PowerShell diagnostic's -Live mode now refuses for both fixture sets; default
and -Transport offline source/binding checks remain available. Do not invoke the
historical Python runner directly to repeat the live suite.

## Validation And Closeout

Full scripts/validate.ps1 passed: 66 Python tests (41 host, 12 historical
candidate, 13 date regressions), 20 negative Compose cases, seven negative
identity cases plus matching identity, offline source/hook checks and fake
success/timeout bindings. Managed validation image built without changing the
production tag. Native settings, privacy headers, ranking characterization,
blocked direct egress, isolated outage/recovery and cleanup passed. Retired live
mode refusal was verified before any HTTP/Docker work. Final live ops-check
passed: three healthy services and VPN/DNS/distinct-egress isolation.

This reviewed tooling/documentation unit accompanies branch push, fast-forward
merge and local/remote branch cleanup. No production container replacement,
provider tuning or desktop release is needed. The approved four-step batch is
complete, including its evidence-based decision not to ship a speculative fix.
The live diagnostic's nonzero exit is its intended stop-on-degradation outcome,
not a successful reliability test. Do not claim the intermittent search issue is
fixed. No response content, query history, tokens or network addresses retained.
