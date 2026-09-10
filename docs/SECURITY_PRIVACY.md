# Security And Privacy

## Scope And Limits

Single-user local SearXNG browser search; not public hosting. The main risks are
unintended network exposure, query retention in logs/browser history, and bypass
of VPN-only egress. The old chatbot/backend/fetcher/model services are removed.

Upstream engines receive the query and may retain it. Identifying query content
can identify a user despite a VPN. Brave GET query URLs may be stored in browser
history/sync; no-store does not erase that. Clicked result websites and external
media opened in the browser use normal host networking.

## Enforced Boundaries

- Only host-gateway publishes a port: 127.0.0.1:8085 by default. Old UI/backend
  ports are removed, not merely hidden in documentation.
- Search shares the VPN namespace with an explicit read-only resolver pointing
  to 127.0.0.1. The base configuration has no direct search egress at all.
- Gluetun retains its firewall and only NET_ADMIN, /dev/net/tun, read-only root,
  explicit writable runtime mounts and namespace-local control API :8000.
  Existing root identity is required by this pinned image's read-only setup.
- Gateway/VPN images and the search build's upstream base are digest-pinned.
  The derived search image is a local versioned tag, not a registry digest pin;
  exact source guards and build/runtime tests verify its two-file repair. Its
  tiny allowlisted context excludes credentials/data, build RUN networking is
  disabled, and no runtime patch/download step is added. Normal base-image
  resolution can contact Docker's registry, never with search data.
  Capabilities are dropped; no-new-privileges is required. Gateway uid/gid is 101.
- No new engine, account/API key, telemetry, CDN or remote NLP service is added.
- Any future model must be internal-only and separately provisioned/evaluated;
  local result refinement does not require a separate interface.

## Browser And Logging Safeguards

Autocomplete and external favicon resolution are locked off; SearXNG image proxy
is locked on and query-in-title off. Saved cookies cannot weaken these defaults.
Language, engine selection, SafeSearch and appearance remain configurable.
Proxied thumbnails use SearXNG's VPN egress; image hosts still receive requests.

Search responses/errors carry no-store/no-referrer. Gateway access logs and
search-vhost request-error logs are disabled, proxy result buffering/temp files
are disabled, and form bodies are bounded. This is not a claim that every
possible application exception is query-free: never enable debug request dumps
for routine diagnosis. Use local status checks and native aggregate engine stats.

## Secrets And Data

- Never commit .env, credentials, model files, browser history/cookies, queries
  or result payloads. Do not print full Compose JSON or secret files.
- The per-PC WireGuard identity is separate from the homeserver. Restricted,
  ignored data/proton/wireguard/wg0.conf is mounted read-only, not put in env.
- Existing .env, search cache, browser-local legacy chat data, volumes and cached
  images are preserved by the removal workflow. They are not claimed erased.
- Retired source code is recoverable from Git before the removal branch.
- Legacy helper retirement checks exact task action/process paths. If task ACLs
  prohibit deletion, replace only its user-owned launcher with a backed-up no-op.

## Verification

validate.ps1 checks offline Compose policies (including negative regressions),
the exact service/port topology, native settings/headers, direct-egress blocking
in the offline base, and local outage/recovery. Its separate project/port/tmpfs
cache never mounts the live cache or VPN key. No upstream search queries are
part of deterministic validation.

check-proton-search.ps1 verifies live namespace/DNS/HTTPS/distinct egress; its
explicit -TestKillSwitch drill temporarily stops VPN and recreates namespace
clients during recovery. Root health is not proof of upstream search quality.
Manual benchmarks use fixed public fixtures and default to bounded metrics.
The explicit -ReviewTop5 option also displays bounded titles/snippets for those
public fixtures. Such text is untrusted; do not record transcripts or persist
payloads. Commit only fixture rubrics, grades and aggregate findings. No browser
data is accessed and no result pages are fetched. Engine-specific diagnostics
omit category selectors to prevent SearXNG unioning unintended recipients.
Same-response score replay is diagnostic-only and makes no additional requests.
The existing DuckDuckGo token cache has secret-hashed query/UA keys and expiring
token values; it is not plaintext history, nor does expiry guarantee secure
erasure. This scope did not inspect/cache-dump, delete or add to its design.

The historical News candidate (live mode now refused) uses a separate tmpfs
cache, never the production cache or key. Logs are disabled and stage diagnostics
omit tokens, queries and URLs. Its default offline test has network=none; the
previous explicit live trial shared only VPN networking and opened no listener.
Suspension state is process-local:
review cooldowns before a trial and never recreate it to retry a failed provider.
Tmpfs disposal is not a guarantee of secure erasure from host memory or swap.

The optional transport-version review also has network=none and no host ports.
An explicitly provisioned, hash-verified official wheel is mounted read-only and
extracted to capped /candidate tmpfs with executable mappings for its native
library. /tmp remains noexec; production never gets this mount or client overlay.
Exact profile/source and artifact hashes are checked before use. No host package
installation, runtime download, credential/cache sharing or payload capture.
See UPSTREAM_TRANSPORT_REVIEW.md; this candidate is not a deployed upgrade.

The guarded DDG web experiment imports explicitly provisioned, hash-pinned source
only in a non-root network-disabled container. It substitutes a no-op query
cache and mock transport, restricts requested HTTPS hosts/paths, disables redirect
options, filters headers and bounds challenge parsing/request counts/deadlines.
No response JavaScript execution, credentials, production cache or listeners.
The subsequent -Integration suite exercises real native client/processor code
against container-loopback TLS with an ephemeral test CA and test-only DNS
overrides, no host ports or public networking. It verifies cookie isolation,
redirect refusal, native cooldowns and cancellation; the integration helper adds
a decompressed-body callback cap, not a cap on headers/native/OS allocations.
Logs/exception metrics stay disabled for this experiment. Test CA/DNS overrides
must never be used for live requests. Live mode refuses; do not deploy these
helpers. See DDG_WEB_NATIVE_INTEGRATION.md for boundaries and trial prerequisites.

Gluetun contacts its configured DNS/health/blocklist/public-IP services; these
are infrastructure requests, not search strings. DNS-over-TLS uses Cloudflare
through the VPN; checks use example.com and api.ipify.org. No zero-third-party-
contact promise. Docker isolation is defense in depth, not protection against
every host compromise. Preserve host firewall policy and review pinned updates.
