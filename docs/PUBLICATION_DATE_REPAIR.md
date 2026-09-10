# Publication-Date Repair (2026-09-10)

## Scope

AnonExplo's native SearXNG result merger discarded an incoming publication date
when the retained duplicate had publishedDate=None. Both cross-type and same-type
MainResult/LegacyResult pairs reproduce this: defaults_from fills UNSET fields,
not explicit None, despite its docstring. The original-image regression fails
in all four pairings. This is not proof that every missing date has this cause.

The repair copies only an incoming datetime when the retained date is None.
Existing dates win, including conflicts; absent/invalid incoming values are not
parsed or invented. Naive/aware datetimes retain their original timezone semantics.
pubdate is derived from the copied datetime using native formatting, not stale
incoming display text. No change to title/content merging, URLs, engine names,
positions, scores, thumbnail grouping, settings or network routing.

Native HTML also used result.pubdate, which resolves LegacyResult's empty class
default instead of its dictionary key. The guarded macro changes only that
lookup to result['pubdate']; both types support item access. This keeps the HTML
datetime attribute aligned with result metadata, including already-dated legacy
results. Native JSON serialization retains the datetime and attribution.

No ranking improvement, new date extraction, provider reliability improvement,
time-filter support, AI, account/API or additional upstream request is claimed.

## Packaging And Guards

- Compose builds local tag anonexplo/searxng:date-merge-v1 from images/searxng.
  No registry push/pull of the derived tag. It is a local tag, not an immutable
  registry digest. ops-check verifies the deployed platform manifest matches the
  local tag's matching platform manifest; provenance-only index changes are irrelevant.
- Base: searxng/searxng:latest at sha256:
  3547509b419cd6a67333d6d68bd1ffad8d46d3669d82e7a7bd538f7b45827432.
- Original results.py SHA256:
  5c1be81f866473021370f3f92fc32173e2df30446191aa151d9358c1f4512cc7.
- Original simple/macros.html SHA256:
  56c42b5d38aeee3b47b2b04cca3da9e8b32b747addf216bf840215fae7a1f98d.
- Exact fingerprints/anchors fail closed before edits. Both guarded transformations
  must succeed. Patching an already-patched or unknown source fails. Matching
  stale results bytecode is removed inside the image build only.
- The context allowlists only Dockerfile, repair and tests; no repo data/.env,
  VPN secrets, caches, histories or experiment payloads. RUN networking is none.
  Existing upstream entrypoint/user/runtime behavior remains unchanged.
- SEARXNG_IMAGE in existing .env files is inert, so an old pin cannot silently
  skip the repair. No secret-bearing .env file is rewritten. Gateway/VPN retain
  their original pins. No additional service, capability, network or port.
- Historical News candidate -Live now refuses immediately. Offline tests remain
  on the original image and are not proof of a production timeout/ranking fix.

## Verification

13 deterministic date tests cover four type pairs, both arrival orders through
the real ResultContainer, existing/conflicting/invalid dates, repeated merges,
naive/aware timestamps, immutable incoming data, native HTML date markup, native
JSON and source guards. Differential tests compare every other result field and
ordered row against the original merge function. Existing native ranking
characterization remains unchanged. No provider calls or result payload files.

Full validate.ps1 also covers 32 benchmark tests, 12 historical candidate tests,
18 negative Compose cases, startup syntax, build, isolated native UI/settings/
privacy headers, localhost-only publication, direct-egress block and recovery.
See the current roadmap for actual run/deployment status, not assumed completion.

## Deploy And Roll Back

1. Run scripts/validate.ps1; it builds/exercises the separate :validation image
   without live credentials/cache or production-tag changes. Keep the previous
   image cached. For a deliberate deployment, then build the production image
   from the same reviewed context with docker compose build search-provider.
2. Review prior error classes/cooldowns and avoid concurrent browser searches.
   Never use a deployment restart to clear a provider block. A stable aggregate
   history is not proof that no queries occurred or every upstream block expired.
3. With the existing VPN healthy, replace only the search service:

   ```powershell
   docker compose -f docker-compose.yml -f docker-compose.proton-search.yml --profile proton-search up -d --no-deps --no-build --wait --wait-timeout 120 search-provider
   powershell -ExecutionPolicy Bypass -File scripts/ops-check.ps1
   ```

   The gateway may briefly return its local privacy-preserving 503; do not replace
   the VPN or gateway for this repair. There is no installer/release artifact.

4. Rollback is a reviewed fresh Git branch restoring the pre-repair Compose,
   policy/validator/ops assumptions from main commit 15159dd, while retaining the
   Proton overlay, localhost binding, current settings and credentials. Review
   the diff and validate the original pinned image, then replace only search as
   above. Do not use reset --hard, edit secrets, restore legacy components, or
   merely retag the upstream image as the repair (that would mislabel its state).

For later upstream upgrades, inspect whether these bugs are fixed. Remove the
repair when native tests pass; otherwise deliberately review the new source and
guards. Never adjust fingerprints just to make a failing build pass.
