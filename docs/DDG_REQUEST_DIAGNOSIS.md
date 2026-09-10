# DuckDuckGo News Request Diagnosis (2026-09-10)

## Scope And Frozen Inputs

User approved diagnosis, not a production fix or timeout/ranking change. New
branch stamos/ddg-request-diagnosis from main 25a8425. Do not rerun the retired
candidate suite or reuse its failed fixtures. This diagnostic observes the
unchanged native adapter in the currently deployed date-repaired image.

Two new public inputs fixed before querying: ddg-wind (offshore wind maintenance
research), ddg-heat-el (Greek urban heat island reporting). Maximum one request
per fixture, 20s spacing after a healthy response, stop at first empty/error.
Only the explicit duckduckgo news engine selector is sent; no category union,
other providers, article fetches, user queries or browser history. These are
diagnostic fixtures, not a relevance benchmark. No operator retries.

## Safety And Interpretation

Default test-ddg-diagnostic.ps1 has network=none and initializes the native app
without searching. After the completed run below, -Live now refuses immediately
to prevent repeating its failed fixture. The completed live run checked DDG history,
allows 10s settling, waits 180s and refuses changed or unreviewed error states.
VPN/image health must pass. Unchanged history is not proof of inactivity or no
upstream block: avoid concurrent searches. Native suspension/cache is separate
in the disposable process, never reset or relaunch it to retry a failure.

The temporary container uses the same local image, no listener/ports, readonly
root, uid65534, dropped capabilities, resource limits and disabled Docker logs.
Only scripts/settings/resolver are mounted read-only; cache/temp are tmpfs.
No production cache, secret, worker change, restart, exit rotation or host-route
change. Source hashes guard adapter/processor/network compatibility.

The trace wraps native calls without changing their parameters or return values:
token cache hit, token HTTP status/duration, parsed-token-present boolean, request
preparation, news HTTP status/duration, native timeout calculations and news
parsing. No token value, URL, request/response headers/body, result text, browser
data or raw exception is printed/persisted. Tests verify argument/return/exception
identity and redaction. Trace is capped at 40 events and snapshots are locked.

Native six-second engine budget and two-second token limit are unchanged.
The synchronous network waiter subtracts elapsed engine time and adds native
0.2s overhead; the transport receives its original timeout. The network future
is not explicitly cancelled by request() when its synchronous waiter times out.
Native internal connection retries are not changed. A one-second observation
grace after a degraded web response does not extend any network deadline or send
another query; disposal stops the diagnostic process afterwards.

A news_http failure after token_parse present=true distinguishes downstream
waiting from token acquisition or JSON parsing. It does not alone distinguish
DNS, TCP, TLS, server throttling, routing or read stalls. No packet/content trace
or unsupported transport diagnosis is implied. Healthy samples cannot establish
that intermittent failures are fixed.

## Results And Validation

Offline preparation passed 37 host tests (32 existing + five trace tests) and
network-disabled native initialization on the deployed repair image. One live
run then passed its complete cooldown and VPN/image preflight. No production
services were restarted, reconfigured or patched.

| Measurement | ddg-wind |
| --- | --- |
| Native web response | HTTP 200, 2.038s, zero rows, one engine error |
| Token cache | Miss |
| Token HTTP transport budget | 2.000s |
| Native synchronous waiter budget | 2.199s |
| Token HTTP outcome | Timeout in 2.002s; no response returned |
| Parsed token / downstream HTTP / News parsing | Never reached |

Stopped at the first degradation. ddg-heat-el was not sent and remains unseen.
No failed fixture retried, no token/result body persisted. The disposable
container was automatically removed. Its live mode is now refused immediately;
offline initialization/tests remain usable, not a new live retry facility.

This sample establishes a token-fetch timeout, not a downstream news timeout.
It failed near the transport's two-second limit, before the longer synchronous
waiter deadline; this timing is consistent with the transport timeout, not proof
of which DNS/connect/TLS/server-read phase exhausted it. Token parsing never got
a response. The earlier coral trial timed out after token-page HTTP returned
200 in 0.25s, without a parsed-token flag. Do not collapse those distinct traces
into one diagnosis or assert the exact prior downstream failure stage.

No fix is demonstrated. Raising the token limit could permit a slower fetch,
but would consume the same shared six-second engine budget and cannot be claimed
to cure the earlier post-token failure. A future separately approved diagnostic
should instrument transport phase timings/error codes for one fresh public
fixture, with no headers/body/URL logging, retries or production modification.
Only after that evidence should a narrowly scoped adapter/config candidate be
proposed. Do not keep repeating this suite or clear suspensions to get a success.

Final full validation passed: 62 Python tests (37 host, 12 historical candidate,
13 native date), 18 negative Compose cases, managed image build, new offline
diagnostic initialization, native ranking/privacy/offline-egress/recovery checks.
Temporary validation resources cleaned up; completed-live refusal verified.
No production service changes or installable release apply.

## Separate Health-Checker Finding

The cached validation build changed the local OCI image-index digest because
its provenance attestation changed. The platform manifest remained identical:
sha256:1f98d2d96d53e188a371cd13e3e439c94aafca027dbfc1ef8179977ad5d6396a.
Verified independently from the running container's ImageManifestDescriptor and
docker image inspect --platform linux/amd64 on the rebuilt tag. The prior index
ID was no longer available to image inspect; no retag/restart was attempted.

ops-check.ps1 compares the top-level image ID, so its final invocation now fails
despite identical runtime manifests. Direct check-proton-search.ps1 and the
native localhost HTTP/privacy checks pass; the running container remains healthy.
This is a confirmed metadata-only false alarm, not a DDG cause or changed search
software. No code fix was authorized by this diagnostic scope. A new maintenance
scope should compare the appropriate platform manifest and isolate validation
image tags before further live diagnostics; do not restart to satisfy the check
or weaken it to a tag-name-only comparison. Git closeout is recorded in roadmap.
