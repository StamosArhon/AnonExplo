# Operations And Maintenance

## Start, Check, Recover

From the repo root on this provisioned PC:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-proton-search.ps1
powershell -ExecutionPolicy Bypass -File scripts/ops-check.ps1
```

Open http://127.0.0.1:8085. Only host-gateway, search-provider and search-vpn
should be running. Only port 8085 is published by AnonExplo. No LLM is required.
ops-check includes VPN egress checks; root health does not establish relevance.

After VPN container replacement, use start-proton-search.ps1 -Recreate.
It recreates the namespace clients and waits for health. Missing credentials
are an error, not a trigger for direct search. Do not restart to clear engine bans.

For a deliberate outage/recovery drill:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check-proton-search.ps1 -TestKillSwitch
```

This briefly interrupts searches; it does not change the PC's default route.

## New Machine

1. Run scripts/bootstrap.ps1 to create .env and the search cache directory.
2. Generate a separate Proton WireGuard configuration for that PC.
3. Import with scripts/import-proton-wireguard.ps1 -ConfigPath <downloaded.conf>.
   Never paste the key in commands/chat. Import stores only client key/address
   in restricted, ignored data/proton/wireguard/wg0.conf.
4. Validate, start with start-proton-search.ps1 -Build and verify with ops-check.ps1.
5. Configure the browser for http://127.0.0.1:8085/search?q=%s.

Windows .env selects both Compose files and proton-search; startup also selects
these explicitly. Base-only Compose is offline, not a usable privacy fallback.

## Windows Startup

setup-browser-search.ps1 -SkipBrowserConfiguration refreshes the hidden startup
helper without touching profiles. The existing AnonExplo SearXNG Startup task
uses that helper. Docker is started with docker desktop start --detach.
There is no Node redirector; Node is used only for optional browser setup.

The historical directory %LOCALAPPDATA%/AnonExplo/search-fallback is retained
because the existing task references it. No service on 8095 is required.

## Upgrade From The Legacy Stack

After pulling the removal change:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup-browser-search.ps1 -SkipBrowserConfiguration -NoStartNow
powershell -ExecutionPolicy Bypass -File scripts/remove-legacy-components.ps1
powershell -ExecutionPolicy Bypass -File scripts/ops-check.ps1
```

The migration verifies the reduced Compose policy, starts the search stack,
then removes only ui/backend/fetcher/model-backend containers selected by both
project and service labels. No generic docker prune or volume deletion.
It retires the exact AnonExplo redirector task/process and unused model network.

If Windows denies deleting the old admin-owned task, its user-owned launcher
is backed up and replaced with a no-op. Report this honestly: a harmless task
entry can remain although no redirector starts. An administrator may later
delete that exact task. Startup-folder fallback launchers are backed up/removed.

Credentials, .env, browser storage, search cache, volumes, model files and cached
Docker images are left intact. Old .env keys are inert. Source recovery is via
Git before this branch; do not use old startup instructions in historical docs.

## Validation And Quality

validate.ps1 uses anonexplo-validation on port 18085, internal-only SearXNG and a
tmpfs cache. It validates policies, scripts, offline helper tests, native UI,
privacy settings, direct-egress blocking and outage/recovery. Compose builds the
guarded SearXNG repair from its pinned base and runs native date regressions at
build time and again in the isolated runtime. No upstream search queries.
Its :validation image tag is separate from production. Deliberate deployment
requires a subsequent production build from the reviewed context. The live image
check compares Linux platform manifests, not provenance-sensitive OCI indexes;
missing Docker descriptor support fails closed rather than trusting a tag name.

Use test-browser-search.ps1 manually for paced public query fixtures through
the VPN. It stops on degradation. Never schedule repeated upstream tests or
collect browser history without an explicit scope.

## Maintenance And Rollback

Keep image digest pins. Evaluate candidate versions with isolated tests and
the bounded manual benchmark before updating the live stack. Preserve the
credential/DNS/network settings and cooldowns. Do not rotate exits as a retry.

Search now uses the local anonexplo/searxng:date-merge-v1 build, not SEARXNG_IMAGE.
The base digest and source fingerprints live in images/searxng. Do not update
them blindly: upstream may have fixed these bugs. See PUBLICATION_DATE_REPAIR.md
for exact scope, deployment and rollback; no custom image is pushed to a registry.

For rollback, use a reviewed Git branch and the prior pinned configuration,
not git reset --hard. Recreate only required services, verify the port binding
and VPN isolation, and account explicitly for old service startup dependencies.
Do not accidentally restore direct egress or old browser redirects.

Back up reviewed repository state and secure credentials separately; treat
.env and any user data as sensitive. No automatic backup destination is added.
