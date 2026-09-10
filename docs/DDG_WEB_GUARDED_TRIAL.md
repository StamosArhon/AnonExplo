# Guarded VPN-only DDG Web Trial (2026-09-10)

Status: completed after a user-confirmed second preflight. One healthy fixture,
then a first-page timeout; stopped with no retry. Live modes are now retired.
Preparation and the first blocked preflight below are historical; final outcome
is recorded at the end of this report.

User explicitly approved the next suggested bounded live trial. Scope
stamos/ddg-web-guarded-trial from main a72c0d4. Production image, engine choices,
ranking, browser settings and Proton profile must remain unchanged.

## Frozen Before Evaluation

Three fresh synthetic public queries are defined in scripts/ddg_web_trial.py:

| ID | Public query | Expected domain |
| --- | --- | --- |
| web-library | Open Library borrowing ebooks | openlibrary.org |
| web-air | European Environment Agency air quality index | eea.europa.eu |
| web-observatory-el | Εθνικό Αστεροσκοπείο Αθηνών επίσημος ιστότοπος | noa.gr |

No match was found in existing repository fixtures. These are navigational
coverage probes, not a general relevance benchmark. Freeze this file and the
criteria in Git before the first live evaluation. Once observed, fixtures are
regression evidence and must not be reused as unseen holdouts.
The fixture/policy file SHA256 is
`e7ed615ba8de830dec6e09a506677d6be9db1518c4a6ee414e56486218a79175`;
both wrapper and runner refuse changed bytes.

Per-query acceptance: no engine errors, at least five results, expected domain
or a genuine subdomain in the first five. Stop immediately on an error, fewer
results or a missed target; no retry, no fallback, no fixture substitution.
At most three queries, first page only, unfiltered/all-language, SafeSearch=0,
20 seconds between completed queries. At most three guarded HTTP calls per
query. Emit only fixed fixture IDs, counts, latency, rank/boolean and allowlisted
error categories. Do not print or save titles, snippets, URLs, tokens or pages.
Per-call observations contain only ordinal, duration, HTTP status when returned
and a failure boolean, so the one-shot run can localize failure without retries.
No result site is fetched. A target-domain match is not a correctness grade.

## Preflight And Isolation

The new test-ddg-web-trial.ps1 defaults to network=none initialization and is
included in validate.ps1 -WebCandidate. Existing candidate/News diagnostic live
guards are unchanged. Only the new -Live path can perform this approved trial.

Before live dispatch, allow 10 seconds for in-flight requests to finish, then a
full 180-second cooldown window with no provider polling. Refuse unknown/long-ban
DDG error classes; compare local DDG error history and aggregate /stats HTML
before/after the wait and again after preflight. These snapshots stay in memory
and are never printed or persisted. Stable stats are not proof of inactivity;
the operator must avoid concurrent searches. Do not automatically repeat a
failed preflight or restart services to erase cooldowns.

ops-check verifies current Compose policy, healthy services, production image
manifest, localhost privacy headers, VPN namespace/resolver and distinct working
egress. Its known infrastructure checks contact example.com, public HTTPS and
api.ipify.org without search strings; no kill-switch drill or restart.

The trial container joins only the existing verified VPN namespace and mounts
its resolver read-only. No VPN key, production cache, Docker socket, listener or
host port. Non-root, read-only root/source/config mounts, dropped capabilities,
no-new-privileges, capped CPU/memory/pids, noexec capped /tmp and no Docker logs.
No test CA, DNS override, credential or image download; clear proxy environment.
The native client uses production's HTTP/2 setting and system trust. TLS fixtures
also use that client setting (the local server negotiates HTTP/1.1).

One module, Network, user agent and native suspension state are retained for the
whole trial. Network-client acquisition, guarded transport and native processor
error/cooldown handling are the offline-tested integration. Native logging and
exception metrics are disabled; a tiny in-memory container retains rows only
until metrics are computed. An empty ignored one-shot marker is created atomically
immediately before Docker dispatch; never delete it to rerun. No query payload
or result is stored in the marker. Interrupted/failed dispatch also consumes it.

This process cannot inherit production suspension state; cooldown preflight and
stop-on-degradation are mandatory. It does not enable the web engine in browsers,
repair DDG News, change timeouts or justify any production ranking deployment.

## Validation And Outcome

Full validate.ps1 -WebCandidate passed before live use: 139 Python test
executions, 20 negative Compose cases, seven negative identity cases plus equality,
source/binding checks, isolated managed build (production tag unchanged), native
privacy/settings/ranking, blocked egress, outage/recovery and cleanup. Offline
initialization was repeated after adding numeric-only call observations.
This code/fixture/policy state is committed before live evaluation; live outcome
will be appended before branch closeout. No live query has been sent at this stage.

### Attempt Outcome

Fixtures and criteria were committed/pushed at 959c664 before the first preflight.
The single approved preflight waited the full 10s + 180s, then refused because
the combined local error-history/aggregate-stats snapshot changed. It stopped
before ops-check, VPN attachment, one-shot marker creation or provider dispatch.
**Zero search queries sent; all three fixtures remain unseen.** No automatic
repeat, provider retry, new exit, restart, cache deletion or timeout change.

Read-only follow-up: two immediate /stats responses were byte-identical (16,709
characters); DDG web had no reported error entries and News retained three Timeout
entries. This does not reconstruct the earlier changed snapshot or establish a
quiet interval. The guard compared combined snapshots and did not attribute the
change to an engine, caller or browser. Do not blame browser activity as proven,
or label this a DDG candidate/provider failure. No result-quality finding exists.

The ignored attempt marker is absent because dispatch never began. The runner
and frozen fixtures remain ready for a manually authorized quiet-window preflight;
do not rerun automatically in this batch. Ask the operator for approximately four
minutes without browser searches. If the state changes again despite that window,
diagnose metadata stability/activity attribution without sending test queries.

Tooling and this blocked outcome accompany final commit/push, main merge and
scoped branch cleanup. No production deployment or installer/release applies.

### Confirmed Quiet-Window Evaluation

The user explicitly agreed to leave searches idle for a new window. Scope
stamos/ddg-web-quiet-window from ce6a103; frozen fixture/policy hash and source
guards unchanged. The 10s settling + 180s quiet/cooldown check passed this time.
ops-check verified three healthy services, the runtime image manifest, localhost
privacy headers, VPN namespace/local DNS, HTTPS and distinct host/search egress.
The trial used the existing VPN namespace with no restart or exit change.

| Fixture | Results | Expected site rank | Total time | Outcome |
| --- | ---: | ---: | ---: | --- |
| web-library | 10 | 1 | 1.226s | Accepted |
| web-air | 0 | none | 2.003s | Timeout; stopped |
| web-observatory-el | not sent | not evaluated | not evaluated | Remains unseen |

For the healthy fixture, first-page discovery returned HTTP 200 in 0.371s and
the result API returned HTTP 200 in 0.854s. For the second fixture, the initial
HTTP request failed with Timeout at 2.002s, before any downstream API or challenge
follow-up. Three HTTP calls total across two submitted queries, with 20s spacing;
no retries or remaining fixture dispatch. No live challenge path was exercised.

The first two fixtures are now observed regression evidence, not unseen holdouts.
The third remains unseen but is not authorization to resume this retired suite.
The empty ignored one-shot marker is preserved. Both the PowerShell -Live path
and direct Python --live entrypoint now refuse before networking. Offline startup,
policy, mock and TLS integration checks remain available.

Decision: keep production unchanged and DDG web opt-in. This is evidence that the
new adapter can work, not that it is reliable or improves general relevance. A
first-page timeout persisted despite the new adapter and guarded native-client
integration. This does not prove the failure's DNS/TLS/network cause or justify
a longer timeout, cookie persistence, retries or VPN exit rotation. It is not a
DDG News repair. Preserve the offline tests for genuinely new transport evidence;
do not continue equivalent live adapter trials or tune on failed fixtures.

Post-trial validation and Git closeout are recorded in IMPLEMENTATION_ROADMAP.md.
No production deployment, browser configuration change or installer/release.
