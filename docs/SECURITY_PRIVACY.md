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
- All service images are digest-pinned; capabilities are dropped and
  no-new-privileges is required. The gateway runs as uid/gid 101.
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

Gluetun contacts its configured DNS/health/blocklist/public-IP services; these
are infrastructure requests, not search strings. DNS-over-TLS uses Cloudflare
through the VPN; checks use example.com and api.ipify.org. No zero-third-party-
contact promise. Docker isolation is defense in depth, not protection against
every host compromise. Preserve host firewall policy and review pinned updates.
