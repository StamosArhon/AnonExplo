# Offline Timeout Semantics (2026-09-10)

Scope: stamos/offline-timeout-semantics from main 2243b6b. User approved the
offline client review following the completed transport batch. No upstream
searches, VPN changes, production restart, token/cache inspection or deployment.

## Reproduction Boundary

Run `powershell -ExecutionPolicy Bypass -File scripts/test-ddg-diagnostic.ps1 -TimeoutSemantics`.
The existing hardened disposable wrapper enforces network=none, no published
ports, non-root, read-only mounts/root, capped tmpfs/resources, no container logs,
and no production cache or credential. Live modes remain refused. This mode
cannot be combined with -Transport. Validation uses the separate validation tag.

Tests use mock futures/clients and an ephemeral server bound only to loopback
inside the network-disabled container. It either serves a fixed two-byte HTTP
response or accepts TCP and sends nothing. It is not a new application service.
No DNS lookup of a public hostname, external request, certificate download or
TLS-verification bypass. Mock example.invalid calls are never executed.
Payloads, listener addresses, exception messages and request headers are not
printed or saved; only test IDs/counts and allowlisted numeric counters appear.

Installed curl_cffi 0.16.1 uses libcurl/8.21.0-IMPERSONATE. Exact source guards
cover native adapter/processor/network, session, client, network retry and curl
option mapping. Review guards on upstream updates; never blindly replace them.
Production still uses the existing digest-pinned base plus date-only repair.

## Confirmed Findings

1. Scalar non-streaming timeout becomes libcurl TIMEOUT_MS, a whole-transfer
   budget, not a dedicated DNS, TCP or TLS timer. DDG token fetch explicitly uses
   2s. A larger global engine timeout does not replace that explicit value.
2. SearXNG's synchronous caller waits for transport budget + 0.2s minus elapsed
   engine time. Example: 1.5s already spent gives a 4.7s caller wait but still a
   6s downstream transport budget. An already-expired caller wait is not clamped.
3. The caller timeout handler raises a new Timeout without explicitly cancelling
   its future. A native transport Timeout preserves its object/code. This is a
   lifecycle concern, not proof that pending work caused the observed live error:
   the previous trace contained native curl code 28 at the 2s transport limit.
4. With Network retries=0, a Timeout is attempted once in the mocked path. A
   ConnectionError has one special native retry even with retries=0. The client
   factory's curl_cffi retry count is zero. Tests add no retries; never describe
   the entire native stack as retry-free.
5. The same pinned client's TLS-handshake stall reproduces the live trace's
   misleading counters without DuckDuckGo, Proton or DNS in the experiment.

| Controlled local case | TCP accepted by server | TCP counter | First-byte counter | HTTP / downloaded bytes |
| --- | --- | --- | --- | --- |
| Successful HTTP | yes | positive | positive | 200 / 2 |
| HTTP response withheld | yes | positive | zero | 0 / 0 |
| TLS handshake withheld, cold client | yes | zero | near 0.3s timeout | 0 / 0 |
| TLS handshake withheld after successful handle use | yes | zero | near 0.3s timeout | 0 / 0 |

Both TLS cases sent no response bytes from the local server. The contradictory
counters therefore do not establish failed TCP or receipt of an HTTP response.
The cold case also shows prior handle use is not required for this pattern.
This supports TLS-handshake stalling as a possible explanation for the live
sample, not a unique diagnosis or proof of filtering/server intent. Local HTTP
is a comparison fixture, not a proposed downgrade for real search traffic.

## Decision And Next Step

No production timeout, cancellation, transport fingerprint, HTTP version, DNS,
VPN, provider or ranking change is justified by this review alone. In particular,
do not disable TLS verification, increase global timeouts, rotate exits or replay
the failed search fixtures. The existing search endpoint and egress isolation
stay intact; no user-history collection or API account is introduced.

Before any new live experiment, the useful next scope is to determine whether
the misleading failure counters are specific to this pinned transport build,
using an upstream source/release review and offline compatibility tests. A
version change would require a separate guarded image-update/rollback scope,
including review of the date repair. No upgrade is authorized or shipped here.

## Validation And Handoff

Initial offline run passed all four local transfer cases and five caller tests,
but the two retry tests failed because Network instance methods are read-only.
Corrected the test-only class mock; all 11 tests then passed. No production fix
or upstream retry was used to remedy this harness error. Tests now explicitly
assert the counter pattern and server acceptance, not just that a timeout occurs.

Full scripts/validate.ps1 passed: 77 Python tests (41 host, 12 historical
candidate, 11 timeout semantics, 13 date repair), 20 negative Compose cases,
seven negative identity cases plus positive equality, native source/binding
checks, isolated managed build with production tag unchanged, privacy/settings,
blocked direct egress, local outage/recovery and cleanup. Live/mixed-mode refusal
checks passed before Docker/HTTP work. Read-only Docker metadata showed all
three production containers still healthy; no production HTTP probe was needed.

Reviewed tests/docs accompany commit/push, fast-forward main merge and scoped
local/remote branch cleanup. No installer/release or production deployment
applies. The offline investigation is complete; live DDG reliability remains
unresolved, and any image update or fresh live experiment needs its own scope.
