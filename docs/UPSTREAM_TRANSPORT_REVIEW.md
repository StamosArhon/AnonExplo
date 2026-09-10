# Upstream Transport Review Batch (2026-09-10)

User approved three bundled steps: upstream review, isolated candidate comparison,
then validation/documentation/Git closeout. Branch stamos/upstream-transport-review
from main c70807d. No production update or new live provider trial.

## 1. Upstream Review

- Official curl_cffi latest release observed was
  [v0.16.3](https://github.com/lexiforest/curl_cffi/releases/tag/v0.16.3),
  published September 2. The
  [0.16.1 to 0.16.3 comparison](https://github.com/lexiforest/curl_cffi/compare/v0.16.1...v0.16.3)
  changes typing/platform handling and fingerprint options, including signed
  certificate timestamps and trust anchors. Session changes do not alter the
  reviewed async request/cleanup path; timeout option mapping is unchanged.
  The active-socket fix concerns Win64, not these Linux timing counters.
- SearXNG master observed at
  [ba055b3e09bc0bcdb3ccbb0857542219fd8f7eb7](https://github.com/searxng/searxng/commit/ba055b3e09bc0bcdb3ccbb0857542219fd8f7eb7)
  still [pins curl_cffi 0.16.1](https://github.com/searxng/searxng/blob/ba055b3e09bc0bcdb3ccbb0857542219fd8f7eb7/requirements.txt).
  Compared with our base revision, changes add Europe PMC engine/docs/settings,
  not a DDG/client timeout repair. No reason to add that provider in this scope.
- [curl 8.22.0](https://curl.se/ch/8.22.0.html) includes connection-time reporting
  changes associated with [explicit FTPS issue 22587](https://github.com/curl/curl/issues/22587).
  That is not proof of a fix for our HTTPS failure. curl_cffi 0.16.3 still targets
  curl 8.21 in its [build metadata](https://github.com/lexiforest/curl_cffi/blob/v0.16.3/Makefile),
  with curl-impersonate 2.2.2. Runtime verification below confirms 8.21.

No reviewed release note or source change establishes a fix for our observed
DDG timeout. This is a bounded review, not an exhaustive upstream security audit.

## 2. Frozen Offline Candidate

Compare curl_cffi 0.16.3 against production's 0.16.1 without replacing SearXNG,
its date repair, Docker images or installed packages. Native SearXNG source
guards remain identical. Separate exact session/utils fingerprints select the
candidate explicitly; production/default guards do not accept the new hashes.
Negative tests enforce profile separation and reject unknown profiles/sources.

The host's provisioning step downloads only the official x86_64 glibc wheel
listed by [PyPI version metadata](https://pypi.org/pypi/curl_cffi/0.16.3/json):

- curl_cffi-0.16.3-cp310-abi3-manylinux2014_x86_64.manylinux_2_17_x86_64.whl
- SHA256 a875a661e2f9a949be29454880bbb9553307a487c4c08819738298cf5c1622e2
- Cache: ignored build/transport-review; no host/production installation.

The wrapper verifies the wheel before mounting; the runner verifies it again
before extraction/import. Checksums verify the selected artifact's integrity,
not an independent security audit. No dependency resolver, install script or
runtime download. The image supplies unchanged dependencies. Extraction rejects
unexpected top-level paths, traversal, symlinks and oversized expanded contents.

Container remains network=none, non-root, read-only root and mounts, no ports,
no logs, dropped capabilities, no-new-privileges and capped resources. Only
/candidate has a 64MiB executable tmpfs for loading the native library; /tmp
remains noexec. This is a disposable offline-only exception, not a production
security change. No VPN key/cache mount, search query, TLS verification bypass,
provider fingerprint experiment or browser data. Only loopback fixtures execute.

Initial harness attempts failed before testing: the mount needed explicit exec,
then the initially selected musllinux wheel proved incompatible. Verified the
actual image is x86_64, glibc 2.41, regular CPython 3.14 (not free-threaded), then
selected the hash-pinned manylinux wheel. Its session/utils hashes match the
reviewed sources. Both downloaded artifacts remain ignored; neither is installed.
These are test-setup corrections, not product bugs or upstream search retries.

Commands (download is an explicit, separate step):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/provision-transport-review.ps1
powershell -ExecutionPolicy Bypass -File scripts/test-ddg-diagnostic.ps1 -TimeoutSemantics -ClientCandidate
powershell -ExecutionPolicy Bypass -File scripts/validate.ps1 -TransportCandidate
```

Normal validation never downloads a candidate and retains the production profile.
Optional -TransportCandidate requires the cached exact wheel, otherwise fails.
No candidate live mode exists; the historical fixture suites remain retired.

## Comparison And Deployment Decision

Candidate runtime: curl_cffi 0.16.3 / libcurl 8.21.0-IMPERSONATE / BoringSSL.
All 24 candidate tests passed: 11 timeout/caller/retry tests and 13 existing date
repair tests, plus native privacy settings checks. TLS stalls, cold and after a
successful transfer, again reported zero TCP/TLS completion and a first-byte
counter near the 0.3s timeout despite TCP acceptance and no server response.
HTTP success and withheld-response comparison behaved as before. Caller and
retry semantics remained unchanged. No counters were reinterpreted as success.

This is limited offline compatibility, not proof of live relevance, upstream
availability, or a safe full production upgrade. No demonstrated reliability
benefit: retain production 0.16.1 and its guarded date repair. Do not deploy the
candidate, compile a different TLS stack, or replay failed fixtures as an implied
continuation. No rollback needed because production was never replaced.

## 3. Validation And Closeout

Full validate.ps1 -TransportCandidate passed: 80 baseline Python test executions
(44 host, 12 historical candidate, 11 timeout semantics, 13 date repair), plus
24 executions against the new client. All 104 passed. Twenty negative Compose
cases, seven negative identity cases plus equality, source/binding checks,
isolated managed image build with production tag unchanged, native privacy/
settings/ranking, blocked direct egress, outage/recovery and cleanup passed.
Live-candidate and invalid-mode refusal checks passed before any Docker/HTTP work.
Read-only Docker metadata confirmed the same three production containers healthy.

Diff reviewed; no production config/image/Compose change or tracked artifact.
This tested report/tooling unit accompanies commit/push, fast-forward main merge
and local/remote scoped branch cleanup. No installer/release or production deploy.
All three batch steps are complete. Retain current production and this reusable
offline comparison for a relevant upstream fix; recurring probing is not added.
