# Guarded VPN-only DDG Web Trial (2026-09-10)

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
