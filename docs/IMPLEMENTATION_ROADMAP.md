# Implementation Roadmap

## Project Objective

Build a reusable, privacy-first Git repository for a self-hosted local-LLM system that can be reproduced across machines with minimal manual work. The runtime stack must keep the model backend and search provider replaceable through configuration, not large code rewrites.

## Architecture Overview

The current design uses five logical boundaries:

1. a local custom UI
2. an orchestrator backend
3. a model backend on an internal non-egress network
4. a search provider or anonymizer service
5. a fetch or read service for article text extraction

Docker Compose is the initial orchestration layer. Only the localhost gateway is published to `127.0.0.1`. Services that need outbound internet access join a dedicated egress-capable network. The model backend remains on an internal-only network.

## Milestones / Phases

1. `foundation-bootstrap`
   - establish repo protocol, continuity docs, architecture, security docs, Docker foundation, and initial provider scaffolding
2. `grounding-vertical-slice`
   - add a working search to fetch to grounded-context backend flow with richer error handling and a grounded-answer path
3. `local-model-integration`
   - integrate and validate one concrete local model runtime profile end to end on the target hardware
4. `ui-workbench`
   - improve the local UX for model selection, grounding visibility, and failure states
5. `provider-expansion`
   - add at least one additional model adapter and one additional search or anonymizer adapter
6. `ui-declutter-history`
   - move optional instructions and stack diagnostics into dedicated modal surfaces, add browser-local direct chat history controls, and make direct versus grounded behavior explicit in the UI
7. `ops-hardening`
   - tighten observability, host firewall guidance, backup, update, and maintenance flows
8. `grounding-quality-tuning`
   - tune SearXNG defaults, grounded-source selection, and answer-citation behavior for better day-to-day grounded responses
9. `fetcher-resilience`
   - improve fetch success on hostile publishers, preserve explicit provenance, and add better operator guidance for fetch-path edge cases
10. `fetcher-secondary-reader-strategy`
   - decide whether to add an opt-in secondary reader path for blocked publishers without weakening the privacy model
   - resolved by decision: keep direct HTML fetches plus explicit snippet fallback as the steady-state design for now

## Current Phase

- Active phase: `post-roadmap-enhancement`
- Goal: maintain the current baseline, validate regressions, and land tightly scoped improvements without reopening the completed core roadmap, while the current branch focuses on explicit machine-handoff documentation and remote-sync verification

## Active Branch

- `stamos/repo-handoff-sync`

## Completed Work

- Established the project repo as a Git repository with a private GitHub remote under `StamosArhon/AnonExplo`.
- Defined the repo operating protocol in `AGENTS.md`.
- Created the continuity documents and the first architecture and security baselines.
- Added an initial Docker Compose skeleton with internal and egress network separation.
- Added minimal UI, orchestrator, and fetcher code to make the architecture concrete and reviewable.
- Added bootstrap and validation scripts and confirmed they run on the current development machine.
- Implemented a structured grounding pipeline that deduplicates search hits, selects sources, fetches article text, and reports per-source failures.
- Added a grounded-answer backend path that passes bounded fetched source text into the configured local model.
- Upgraded the local UI to show grounded answers, source status, and the exact source text slices used for grounding.
- Finalized the first concrete `llama.cpp` CUDA runtime profile and documented its provisioning flow.
- Tightened the base-stack validation to cover the grounded slice, the llama.cpp profile config, and the local Docker stack wiring.
- Added a runtime-readiness probe that distinguishes a healthy backend from a missing or misconfigured local model runtime.
- Added a model-runtime endpoint and surfaced runtime readiness in the local UI status view.
- Added a Docker healthcheck plus stable runtime aliasing for the `llama.cpp` profile so the backend, runtime, and UI share the same model identifier.
- Added `scripts/provision-default-model.ps1` to download the default GGUF into `data/models/` and verify its SHA256.
- Validated the default `QuantFactory/Qwen2.5-7B-Instruct-GGUF` Q4_K_M artifact end to end on the current development machine with the repo-managed validation flow.
- Added request-level model selection in the backend for direct chat and grounded-answer calls, validated against the runtime-advertised model catalog when available.
- Reworked the static local UI into a clearer workbench with a global model selector, runtime snapshot, provider summary, better source inspection, and more structured failure cards.
- Stabilized unsupported model-override failures so the backend returns structured selection and runtime details without falling back to a second selector call.
- Added a second model adapter for native Ollama runtimes while keeping the same orchestration contract used by the existing OpenAI-compatible runtime path.
- Added a second search adapter for YaCy so the backend can query either SearXNG or YaCy through the same grounded-search pipeline.
- Removed the backend's hard Compose dependency on a fixed `search-provider` service name so search-provider switching stays config-driven.
- Added a dedicated localhost gateway service so the UI and backend are reachable from the Windows host while the app services themselves stay on internal Docker networks.
- Tightened validation to check real host reachability on `127.0.0.1:3000` and `127.0.0.1:8000`, not just Docker's intended port-binding metadata.
- Added a localhost-only standalone SearXNG browser route through the host gateway so users can switch between direct SearXNG use and the grounded LLM workflow without exposing the search container directly.
- Refreshed the local UI into a calmer sidebar-and-editorial shell that maps to the real workspaces the repo supports instead of pretending to have persisted chat sessions.
- Added in-tab conversation-style rendering for direct chat and grounded answers while keeping persistent browser storage limited to the selected model id.
- Added UI config support for the standalone SearXNG browser URL so the local shell does not hardcode that route.
- Added a follow-on UI cleanup pass that moves optional instructions and stack diagnostics into dedicated modal surfaces instead of leaving them inside the main chat area.
- Added browser-local direct chat history with a new-chat action, per-entry delete, and full purge controls.
- Made the UI mode boundary explicit so Direct Chat is clearly model only while Grounded Answer is the search plus fetch plus model path.
- Extended grounded-answer requests to accept their own saved browser-local instruction block after the backend assembles grounded source context.
- Added a stricter Compose-policy validation pass that checks localhost-only publication, expected network membership, digest-pinned third-party images, local-only CORS origins, and default container hardening settings before a branch is declared ready.
- Added `scripts/ops-check.ps1` as a lightweight day-to-day health check for the running local stack.
- Added an operations and maintenance guide covering startup, update, recovery, Windows-host firewall guidance, and local backup notes.
- Suppressed routine access logging in the repo-managed UI, backend, fetcher, and localhost gateway services where practical.
- Hardened the bundled SearXNG service with a read-only root filesystem and a healthcheck so validation can treat it as a real service dependency rather than a process that merely stays running.
- Added env-driven SearXNG query tuning for categories, language, optional time range, and optional engine selection so grounded current-events queries are less generic by default.
- Reworked grounded-source selection to rank results by query relevance, preserve domain diversity where practical, and keep trying later candidates when earlier fetches fail.
- Strengthened the grounded model prompt so the model cites source IDs, avoids prior-knowledge or knowledge-cutoff language, and reports insufficiency from the supplied material instead of guessing.
- Added an explicit `context_mode` to grounding summaries so the backend and UI can distinguish fetched article text from search-snippet fallback.
- Added a bounded search-snippet fallback path so grounded answers can stay source-derived even when article fetches fail, instead of silently drifting to model prior knowledge.
- Fixed the fetcher's response typing so successful fetches no longer fail FastAPI response validation when integer count fields are returned.
- Increased the localhost gateway timeout for backend requests so heavier grounded answer calls are less likely to die at the proxy before the backend finishes.
- Updated the UI to surface grounding context mode and to show when a grounded answer used snippet fallback instead of fetched article text.
- Added structured fetcher failure codes and metadata so blocked, rate-limited, and generic upstream failures stay distinguishable across the fetcher, backend, and UI.
- Added fetcher-side thin-content classification so paywall shells or otherwise low-value extracts can be rejected instead of being treated as usable grounding context.
- Reworked fetch retries so later candidates are still tried after thin-content or generic fetch failures, while later URLs from the same domain are skipped after explicit robot-policy, forbidden, or rate-limited responses.
- Added fetch-quality and error provenance to the UI's fetch inspector and grounded-source details so operators can see method, quality, warning, and upstream-status signals without opening container logs.
- Added tracked fetcher tuning keys for minimum content size, minimum word count, and accept-language so the new behavior is reproducible across machines.
- Closed `fetcher-secondary-reader-strategy` by decision: the current baseline will keep direct HTML fetches plus explicit snippet fallback instead of adding a secondary reader path.
- Tightened browser-local history labeling so the UI now makes direct-chat persistence unmistakably device-local, purgeable, and non-server-side.
- Completed the initial roadmap baseline so future work can be treated as post-roadmap enhancement rather than unfinished core setup.
- Reworked grounded answers so cited source IDs render as inline source pills with hover tooltips instead of forcing a large grounding-details block into the main chat surface.
- Added a retractable right-side source drawer for grounded answers so the full source list, source status, and snippets are available on demand without cluttering the conversation thread.
- Tightened the sidebar history presentation into compact direct-chat cards with integrated per-entry delete controls instead of a split or awkward row layout.
- Refined the grounded citation treatment into discreet superscript-style source references and restyled the active history card so the sidebar no longer uses an ambiguous bright highlight block.
- Added an explicit opt-in Wikimedia fetch path that uses the official MediaWiki Parse API for supported Wikimedia article URLs instead of a hidden scraping workaround.
- Added fetcher config scaffolding for `FETCH_WIKIMEDIA_API_ENABLED` and `FETCH_WIKIMEDIA_API_USER_AGENT` so Wikimedia support remains operator-controlled and reproducible across machines.
- Added config-driven preferred-domain search ranking so grounded answers can modestly favor already-returned Wikipedia or Wikimedia results when they are relevant, without forcing a Wikipedia-only search mode.
- Tightened the local UI polish pass so direct-chat history actions live together in the sidebar, history cards are more legible, and grounded-answer source controls stay quiet and non-duplicated.
- Reworked fetched grounding-context assembly so long articles now contribute query-relevant excerpts instead of only the document head, reducing vague answers when the answer sits deeper in the fetched page.
- Tightened grounded-answer prompting so the model is explicitly asked to answer directly in the first sentence, prefer concrete dates or facts when available, and keep citations in a canonical end-of-sentence form.
- Added backend-side grounded-answer citation normalization so grouped or repeated model citations are rewritten into a consistent `[S1][S2]` shape before any client renders them.
- Hardened the UI citation renderer with the same canonicalization fallback so existing or drifted model outputs still render discreet superscript source pills consistently.
- Restyled grounded source-tooltips into shorter anchored previews tied to the source pill instead of large centered popovers that fought with the reading column.
- Added a hybrid grounding mode that keeps fetched article text primary while appending bounded snippet fallback context from selected sources whose fetches failed.
- Updated the UI context labels and source-drawer copy so grounded answers can explicitly show `fetched_plus_snippets` instead of pretending every mixed-evidence answer is purely fetched or purely snippet-backed.
- Kept grounded-answer citation pills visually inline by removing whitespace-driven layout drift from the rich-answer renderer.
- Moved source-preview hover cards into a shared floating overlay outside the clipped scroll shell so previews stay readable near viewport edges instead of being cut off by container overflow.
- Tightened grounded-answer quality for current-events prompts by normalizing query and source term variants symmetrically, reducing over-aggressive live-page head bias, and filtering failed-source snippet fallback down to strongly query-matched snippets only.
- Updated excerpt assembly so clearly multi-part questions do not short-circuit to one high-scoring paragraph when separate passages are needed to answer both parts of the query.
- Reworked the fetcher so oversized live pages can fall back to explicit bounded partial extraction instead of hard-failing at the raw response-size limit, with `direct_html_partial` and operator-visible warnings.
- Changed long extracted documents to retain both the head and tail when truncation is required, which helps current-event pages whose most relevant updates sit later in the article.
- Tightened current-events source ranking so snippet fallback is filtered through the same strong-query matching path and same-domain non-live coverage can outrank a live page when the scores are close and the query did not explicitly ask for live coverage.
- Split the backend-to-fetcher timeout from the fetcher-to-publisher timeout through `FETCHER_CLIENT_TIMEOUT_SECONDS` so structured fetcher failures survive slow upstream requests instead of collapsing into an empty backend timeout message.
- Added a repo-root `HANDOFF.md` branch workflow document that records the audited Git baseline, local-only migration assumptions, and the exact next recommended project step for a machine transition without relying on chat history.

## In-Progress Work

- `stamos/repo-handoff-sync` is documenting the audited repo baseline for machine migration and preserving that handoff context in Git without merging it into `main`.

## Open Questions / Blockers

- The repo now validates a real GGUF load and chat probe, but it still does not record benchmark-style throughput numbers or token/sec measurements for the target hardware.
- Existing local `.env` files created before this branch may need a manual refresh of the model-runtime keys if they still contain placeholder values.
- Existing local `.env` files may also still carry the older `SEARCH_RESULT_LIMIT` value and may be missing the newer SearXNG tuning keys if they were created before this branch.
- The standalone SearXNG browser route is intentionally specific to the bundled repo-managed `search-provider` service. If the backend is pointed at YaCy or another search provider, that does not automatically change the standalone browser endpoint.
- Windows-host firewall guidance is now documented, but not automated or enforced outside the existing Docker network and localhost-binding model.
- Direct chat history now lives in browser local storage by design. The current decision is to keep explicit labeling plus delete and purge controls rather than adding an opt-out or export path to the baseline.
- The refreshed UI shell has been validated through the repo build and smoke path, but it still does not have browser-automation coverage for interaction regressions.
- The repo now supports YaCy and native Ollama at the backend boundary, but the default validated Docker path is still the existing `llama.cpp` plus SearXNG stack rather than a fully validated alternate-provider Compose profile.
- Some publishers, especially Wikipedia and other anti-bot-protected sites, can still reject direct HTML fetches from the containerized fetcher.
- The repo still does not include a secondary reader path or publisher-specific bypass. That remains a deliberate baseline decision, and the current fallback stays explicit snippet-grounding whenever direct fetches or official API paths are unavailable.
- Wikimedia support now exists as an explicit official API integration path, but it remains disabled until the operator sets both `FETCH_WIKIMEDIA_API_ENABLED=true` and a real contactable `FETCH_WIKIMEDIA_API_USER_AGENT` in `.env`.
- The current validation path covers the Wikimedia route through containerized unit tests and build validation, but it does not run a live external Wikimedia smoke request with a fake contact string.
- Heavier grounded requests now survive the localhost gateway, but the repo still does not record performance baselines for search-plus-fetch-plus-model latency on the target hardware.
- The citation and tooltip refinements now reduce formatting drift, but the repo still does not have browser-automation coverage for grounded-answer rendering regressions.
- Ambiguous recency wording such as `latest phase` can still pull a mix of current-coverage and historical-timeline sources; future tuning may need stronger recency or event-disambiguation heuristics in the ranking layer.
- Mixed fetched-plus-snippet context improves partial-evidence coverage, but live-news ranking can still surface contradictory or noisy sources, especially on evolving geopolitical topics.
- The grounded search and grounded answer endpoints still use env-backed context limits rather than per-request overrides, so live tuning remains an operator configuration task instead of a request-level control.
- Multi-part grounded answers on fast-moving current-events topics are better than before, but the model can still sometimes under-answer the second clause of a compound question even when the fetched source set contains partial supporting material.
- Machine migration still requires out-of-band handling for `.env`, local model files, Docker state, and browser-local UI history because those are intentionally not tracked by Git.
- `scripts/validate.ps1` could not complete on 2026-04-27 during the handoff branch because Docker Desktop was not running on the current machine. The repo itself was still clean at audit time, but full Compose validation must be rerun on the next machine.

## Decisions Made And Why

- Docker Compose is the initial orchestration layer because it is repo-managed, portable, and easy to reproduce on local machines.
- The orchestrator owns provider routing so the UI never talks directly to model, search, or fetch services.
- The model runtime is treated as an OpenAI-compatible endpoint by default because that interface keeps future runtime swaps easier.
- The fetch pipeline is a separate service so search results can be converted into readable source text without giving the model runtime internet access.
- The initial UI is a static local app with no external assets or CDN dependencies to preserve privacy and keep setup light.
- Grounded answers are built from bounded fetched source text, with per-source selection and error reporting exposed to the UI.
- `llama.cpp` CUDA server mode is the first concrete runtime profile because it fits the target hardware and keeps the backend adapter boundary clean.
- Bootstrap now generates a local SearXNG secret for new environments instead of relying on the insecure default.
- The default local model artifact is pinned by source URL, filename, and SHA256 so provisioning is explicit and repeatable.
- The backend health surface now distinguishes backend availability from model-runtime readiness so failures are easier to understand locally.
- The `llama.cpp` runtime command now sets an explicit alias matching `MODEL_NAME` to keep model discovery stable across backend, runtime, and UI.
- The local workbench can request a runtime-advertised model override per chat or grounded-answer call without changing the global backend configuration.
- Provider expansion is being done through adapters plus env-driven factories first, before adding more runtime-specific orchestration profiles, so the backend boundary stays cleaner than the Compose implementation details.
- Docker Desktop on this machine did not reliably expose published ports for services attached only to `internal: true` bridge networks, so host access now goes through a dedicated localhost gateway instead of direct publishing on the UI and backend containers.
- Standalone access to the bundled SearXNG web UI should use the same localhost gateway pattern as the UI and backend so the search container itself can stay unpublished on the host.
- The UI can adopt a conversation-style shell as long as that presentation does not imply or introduce persistent local chat history without a deliberate privacy review.
- Browser-local persistence is acceptable only for the selected model id, saved instruction text, and direct chat history on the same workstation; grounded source bundles and fetch output remain transient by default.
- The UI must keep Direct Chat and Grounded Answer explicit because only Grounded Answer uses SearXNG plus fetched source text.
- The repo's Compose security model is now treated as enforceable policy in validation, not just as a documentation recommendation.
- Quiet operational logging is preferred by default, so repo-managed services now suppress routine access logs where practical and surface only startup or error information unless an operator opts into deeper inspection.
- Grounded search quality should be improved first through config-driven provider tuning, ranked source selection, and better prompts before adding heavier architectural changes.
- Fetched article text remains the preferred grounding source, but explicit bounded search-snippet fallback is acceptable when article fetches fail, as long as the response surface keeps that context mode visible.
- The localhost gateway should tolerate longer-running grounded-answer calls so the proxy does not fail before the backend has finished search, fetch, and model synthesis.
- Fetch resilience should improve operator clarity first through structured failure classification, thin-content detection, and domain-aware retry behavior before the repo adds any privacy-altering secondary reader strategy.
- Wikimedia or similarly protected publishers should not receive a hidden special-case bypass until the privacy and maintenance tradeoffs of that path are explicitly reviewed.
- Browser-local direct chat history is considered sufficiently controlled in the baseline when it is clearly labeled as device-local and purgeable; opt-out or export should be treated as later convenience features, not core privacy fixes.
- The grounded-answer UI should surface provenance as inline citation pills plus an on-demand source drawer, not as a permanently expanded diagnostics block inside the main conversation area.
- Those inline citations should stay discreet and superscript-like rather than appearing as large in-line buttons that interrupt reading flow.
- Wikimedia support should use the official Parse API for supported Wikimedia article URLs and must require an operator-supplied descriptive user-agent before the opt-in path is enabled.
- Any future changes to the Wikimedia-specific path should keep it explicit, opt-in, and based on an official Wikimedia interface rather than a robot-policy bypass.
- Preferred-domain search tuning should live in the backend's source-ranking stage and stay modest, config-driven, and optional rather than becoming a hidden second search path or a hard-coded encyclopedia mode.
- The UI should keep local-history actions and grounded-source controls structurally simple: grouped history controls in the sidebar, superscript source references in answers, and a single on-demand source drawer rather than duplicated source buttons across the workspace.
- Grounded context selection should prefer query-relevant excerpts from fetched documents rather than blindly truncating from the top of each article, because small local models answer more directly when the supplied evidence is tighter.
- Citation normalization belongs in the backend first, with a matching UI fallback, so every client benefits from consistent `[S1][S2]` rendering and the UI does not depend on one model's exact citation habits.
- When some selected sources fetch cleanly and others fail, the backend should preserve the successful fetched text and append bounded snippet fallback from the failed sources instead of forcing an all-or-nothing choice between fetched-only and snippet-only grounding.
- Query-term normalization should be symmetric between the user query and source text. Canonicalizing only one side led to weaker matching for variants such as `USA` versus `U.S.` or `Iranian-American` versus `Iran` and `United States`.
- Multi-part grounded questions should prefer bounded multi-passage excerpts over a single-passage shortcut when one paragraph does not cover the full question.
- The backend-to-fetcher timeout must stay separate from the fetcher-to-publisher timeout and should remain slightly higher, so the backend receives structured fetcher errors instead of masking them with a generic orchestration timeout.
- For live current-events pages, bounded partial HTML extraction with explicit warnings is preferable to a hard failure when the page is already large enough to contain usable grounded text near the front of the document.

## Security / Privacy Assumptions

- This system is for local use and is not intended for public internet exposure.
- Published ports must bind to `127.0.0.1` by default.
- The model runtime should not have outbound internet access.
- Search and fetch services are the only default services expected to need egress.
- Secrets stay in untracked local files or in the operator environment, never in Git.
- Logs should remain minimal and must not become a quiet store of prompts or fetched content.
- Browser-local direct chat history is an intentional workstation-local privacy tradeoff and must stay purgeable from the UI.
- The host's primary exposure control is still localhost-only port binding plus Docker network separation; Windows Firewall is a supporting control rather than a replacement for that model.
- Search-snippet fallback is acceptable only as an explicit, bounded grounded mode; it must not silently become unbounded web-search context or a hidden substitute for fetcher isolation.
- Hybrid fetched-plus-snippet grounding is acceptable when it is explicit in `context_mode`, bounded by the same context limits, and keeps fetched text preferred over snippet summaries.

## Validation Status

- `scripts/validate.ps1`: passed on 2026-04-14 during the `fetcher-resilience` branch
- `scripts/validate.ps1 -RequireModelRuntime`: passed on 2026-04-14 during the `fetcher-resilience` branch
- `scripts/validate.ps1`: passed on 2026-04-14 during the `roadmap-closeout` branch
- `scripts/validate.ps1 -RequireModelRuntime`: passed on 2026-04-14 during the `roadmap-closeout` branch
- `scripts/validate.ps1`: passed on 2026-04-14 during the `answer-surface-refresh` branch
- `scripts/validate.ps1`: passed on 2026-04-14 during the `wikimedia-official-api-path` branch
- `scripts/validate.ps1`: passed on 2026-04-14 during the `wikipedia-search-tuning` branch
- `scripts/validate.ps1`: passed on 2026-04-22 during the `ui-polish-pass` branch
- `scripts/validate.ps1`: passed on 2026-04-22 during `stamos/grounded-answer-consistency`
- `docker compose run --rm --no-deps backend python -m unittest discover -s tests -p "test_*.py"`: passed on 2026-04-22 during `stamos/grounded-answer-consistency`
- `python -m py_compile apps/ui/server.py`: passed on 2026-04-22 during `stamos/grounded-answer-consistency`
- `node --check apps/ui/static/app.js`: passed on 2026-04-22 during `stamos/grounded-answer-consistency`
- `docker compose run --rm --no-deps backend python -m unittest discover -s tests -p "test_*.py"`: passed on 2026-04-22 during `stamos/hybrid-grounding-context`
- `node --check apps/ui/static/app.js`: passed on 2026-04-22 during `stamos/hybrid-grounding-context`
- `scripts/validate.ps1`: passed on 2026-04-22 during `stamos/hybrid-grounding-context`
- `node --check apps/ui/static/app.js`: passed on 2026-04-22 during `stamos/citation-inline-layout-fix`
- `scripts/validate.ps1`: passed on 2026-04-22 during `stamos/citation-inline-layout-fix`
- `scripts/validate.ps1`: passed on 2026-04-22 during `stamos/grounded-answer-quality-pass`
- `docker compose run --rm --no-deps backend python -m unittest discover -s tests -p "test_*.py"`: passed on 2026-04-22 during `stamos/grounded-answer-quality-pass`
- `python -m py_compile apps/backend/app/grounding.py`: passed on 2026-04-22 during `stamos/grounded-answer-quality-pass`
- `scripts/ops-check.ps1`: passed on 2026-04-22 against the running local stack during `stamos/grounded-answer-quality-pass`
- `python -m py_compile apps/backend/app/config.py apps/backend/app/main.py apps/backend/app/providers.py`: passed on 2026-04-22 during `stamos/live-source-fetch-tuning`
- `docker compose run --rm --no-deps backend python -m unittest discover -s tests -p "test_*.py"`: passed on 2026-04-22 during `stamos/live-source-fetch-tuning`
- `docker compose run --rm --no-deps fetcher python -m unittest discover -s tests -p "test_*.py"`: passed on 2026-04-22 during `stamos/live-source-fetch-tuning`
- `scripts/ops-check.ps1`: passed on 2026-04-22 against the running local stack during `stamos/live-source-fetch-tuning`
- `scripts/validate.ps1`: passed on 2026-04-22 during `stamos/live-source-fetch-tuning`
- `scripts/validate.ps1`: passed on 2026-04-22 during `stamos/roadmap-closeout-sync`
- `git status --short --branch`: showed a clean `main...origin/main` baseline on 2026-04-27 before the handoff branch was created
- `git branch -vv`: showed only `main` tracking `origin/main` on 2026-04-27 before the handoff branch was created
- `git stash list`: empty on 2026-04-27 during the handoff audit
- `scripts/validate.ps1`: attempted on 2026-04-27 during `stamos/repo-handoff-sync` but did not complete because the Docker daemon was unavailable on the current machine
- Validation included:
  - `docker compose config`
  - `docker compose --profile llamacpp config`
  - Compose-policy checks for localhost-only publication, expected network membership, healthchecks, read-only root filesystems, dropped capabilities, no-new-privileges, digest-pinned third-party images, and local-only CORS origins
  - Docker builds for `ui`, `backend`, and `fetcher`
  - backend unit tests in the backend container, including search-tuning, ranked-source retry, snippet-fallback coverage, structured fetcher errors, thin-content retries, and blocked-domain skip behavior
  - fetcher unit tests in the fetcher container, including typed integer field coverage for the fetch API response, thin-content classification, and structured blocked-policy errors
  - `python -m py_compile apps/ui/server.py`
  - `node --check apps/ui/static/app.js`
  - base-stack smoke validation for `ui`, `backend`, `fetcher`, and `search-provider`
  - container health and localhost port-binding inspection for the base stack
  - Windows host reachability checks for the standalone SearXNG UI on the localhost gateway
  - UI image rebuild with the refreshed static shell, context-mode status, and updated config payload
  - checksum verification for the default GGUF artifact
  - `llama.cpp` runtime startup with the pinned default GGUF
  - backend runtime-readiness probe against the live model service
  - a minimal OpenAI-compatible chat-completions probe against the live model runtime
  - a manual live grounded-answer check on 2026-04-14 that returned a sourced answer for the query `When did the first israel-usa attack on Iran take place in 2026?` using the local SearXNG plus fetch pipeline
- `scripts/bootstrap.ps1`: passed on 2026-04-13 and created the expected local `.env` plus data directories
- `scripts/provision-default-model.ps1`: passed on 2026-04-13 and downloaded the default GGUF to `data/models/`
- `docker compose run --rm --no-deps backend python -m unittest discover -s tests -p "test_*.py"`: passed on 2026-04-14 with coverage for `openai_compatible`, `ollama`, `searxng`, `yacy`, ranked-source retries, structured fetcher errors, blocked-domain skip behavior, and snippet-grounded fallback
- `docker compose run --rm --no-deps fetcher python -m unittest discover -s tests -p "test_*.py"`: passed on 2026-04-14 with coverage for extraction quality classification, structured blocked-policy errors, and typed fetch response fields
- `docker compose run --rm --no-deps fetcher python -m unittest discover -s tests -p "test_*.py"`: passed on 2026-04-14 after the Wikimedia branch build with added coverage for Wikimedia title extraction, opt-in route selection, Parse API content parsing, and required user-agent enforcement
- `docker compose up -d --build host-gateway ui backend fetcher search-provider`: reached the UI on `http://127.0.0.1:3000`, the backend health endpoint on `http://127.0.0.1:8000/api/v1/health`, and the standalone SearXNG UI on `http://127.0.0.1:8085` from the Windows host on 2026-04-14 before the validation script's cleanup step
- Manual live grounded-search check on 2026-04-14 for `What is the Twelve-Day War?`: selected `en.wikipedia.org` as `S1`, fetched it via `wikimedia_parse_api`, and returned `fetched_text` grounding context alongside other fetched sources
- Manual live grounded-answer check on 2026-04-22 for `When did the latest phase of the Israel-Iran war begin?`: returned a direct first-sentence answer with canonicalized citations such as `[S4][S1][S2][S3]` and used query-relevant fetched excerpts from BBC, Wikimedia, and Britannica sources
- Manual live grounded-answer check on 2026-04-22 for `Are the straits of hormuz open and what is happening with Iran-US negotiations for an ending to the war?`: reproduced the partial-fetch scenario, returned `fetched_plus_snippets`, and no longer fell back to the generic `insufficient_sources` path
- Manual live grounded-search check on 2026-04-22 for `Are the Straits of Hormuz open? And what is the current state of the Iranian-American peace talks?`: after the quality pass, selected query-relevant NBC, CBS, and Democracy Now excerpts, kept total grounding context near 2k chars, and filtered failed-source snippet fallback to the stronger remaining evidence
- Manual live grounded-answer check on 2026-04-22 for `Are the Straits of Hormuz open? And what is the current state of the Iranian-American peace talks?`: returned a direct sourced answer instead of the earlier vague fallback behavior, with runtime ready and `fetched_plus_snippets` grounding
- Manual live fetch check on 2026-04-22 for `https://www.cnn.com/2026/04/22/world/live-news/iran-war-us-trump-blockade-ceasefire`: returned `direct_html_partial` with usable extracted text and an explicit configured-size-limit warning instead of failing with `response_too_large`
- Manual live fetch check on 2026-04-22 for `https://www.npr.org/2026/04/22/nx-s1-5795405/iran-middle-east-updates`: returned a clear fetch timeout message through the backend path instead of the earlier empty `Fetch request failed:` error
- Manual live grounded-answer check on 2026-04-22 for `Are the Straits of Hormuz open? And what is the current state of the Iranian-American peace talks?`: after the live-source tuning pass, returned `grounded` with `fetched_text`, selected three fetched live sources, and no fetch failures, though the answer still favored the first clause more strongly than the second

## Exact Next Steps

1. On the next machine, restore `.env` and the local GGUF model file out of band or recreate them from the repo-managed provisioning path.
2. Validate the stack on the next machine with `scripts/validate.ps1`, and use `-RequireModelRuntime` if the model is already provisioned there.
3. Start a focused follow-on milestone for multi-part grounded-answer coverage so live current-events answers handle both clauses of compound questions more consistently.
4. Keep validating the current baseline against real live-news queries on the target hardware, especially large pages, slow publishers, and mixed multi-source questions.
5. If Wikimedia support is enabled on a local machine, set a real contactable `FETCH_WIKIMEDIA_API_USER_AGENT` in `.env` before relying on it for live grounding.
6. Use `SEARCH_PREFERRED_DOMAINS` and `SEARCH_PREFERRED_DOMAIN_BOOST` for operator-level tuning before adding a heavier Wikipedia-specific search strategy.

## Handoff Notes For A Fresh Codex Thread

- Read `AGENTS.md` first.
- Then read this roadmap and `docs/INSTRUCTIONS_AND_NOTES.md`.
- The repo now includes a real grounded-answer vertical slice plus a validated `llama.cpp` runtime path with a tracked default GGUF source and checksum.
- The grounding flow is intentionally bounded and transparent: search, source selection, fetch, source packaging, and model synthesis are all visible in the UI and backend responses.
- Grounded-source selection can now apply a modest preferred-domain bias from config, with Wikipedia and Wikimedia as the default example in `.env.example`.
- Grounding summaries now expose `context_mode`, and the UI uses it to distinguish fetched article text from explicit snippet-fallback grounding.
- The most recently merged enhancement extends that model with `fetched_plus_snippets`, which keeps fetched article text primary while carrying forward bounded snippet fallback from failed selected sources.
- The backend and UI now expose model-runtime readiness separately from general backend health, which future branches should preserve.
- The static UI now uses backend-provided runtime and model-catalog state to drive a browser-local model selector for chat and grounded-answer requests.
- The UI shell now uses workspace navigation plus in-tab conversation-style rendering for direct chat and grounded answers.
- Direct chat history, the selected model id, and saved direct-chat or grounded-answer instructions are now stored in browser local storage; grounded details and fetch results remain transient.
- Grounded answers now render source IDs as inline citation pills with hover tooltips and open a dedicated right-side source drawer for deeper inspection instead of using a large grounding-details block in the main thread.
- The most recently merged enhancement is a UI-only follow-up to that answer surface: the backend already returned normalized inline citations for the reported repro, and the UI now keeps those citations visually inline while floating source previews outside the clipped scroll shell.
- Direct Chat does not call SearXNG or the fetcher. Grounded Answer is the explicit search plus fetch plus model workflow and should stay clearly documented in future branches.
- Grounded Answer now ranks search results, retries later candidates after fetch failures, classifies thin page extractions, skips later URLs from domains that have already returned explicit robot-policy or similar blocking responses, and may fall back to search snippets when publishers block fetches. That fallback is intentional and must stay explicit in both API responses and UI copy.
- The most recently merged enhancement also keeps mixed evidence explicit by appending failed-source snippet fallback to fetched grounding context instead of discarding that snippet evidence when only part of the selected source set is fetchable.
- The fetcher, backend, and UI now share structured fetch provenance such as `blocked_by_remote_policy`, `content_too_thin`, `upstream_status`, and retryability hints.
- The most recently merged enhancement adds query-aware excerpt selection from fetched documents, direct-answer-first grounded prompting, and backend citation normalization with a matching UI fallback for grouped citations.
- The current working quality pass extends that answer-quality layer with symmetric query/source canonicalization, multi-part query handling in excerpt selection, and stricter failed-snippet filtering for noisy live-news result sets.
- The repo now includes `docs/OPERATIONS_AND_MAINTENANCE.md` plus `scripts/ops-check.ps1` for local maintenance and recovery work.
- `scripts/validate.ps1` now enforces the intended Compose security model instead of treating it as documentation only.
- Repo-managed services keep routine access logging quiet by default, so operators should use targeted `docker compose logs --tail=...` calls when they need deeper inspection.
- The backend now supports `openai_compatible` and `ollama` model adapters plus `searxng` and `yacy` search adapters through env-driven factories.
- The repo now supports two localhost-only browser modes at once: the main AnonExplo UI on port `3000` and the bundled standalone SearXNG UI on port `8085`, both through the same low-privilege host gateway.
- The localhost gateway now allows longer backend request times so heavier grounded calls do not fail at the proxy first.
- This repo intentionally still does not add a hidden special-case Wikipedia or third-party reader bypass after earlier direct HTML Wikimedia fetch attempts returned robot-policy `403` responses from inside the fetcher container. Wikimedia support now uses an explicit opt-in Parse API path and requires an operator-supplied contactable user-agent string.
- The initial roadmap is now complete on `main`.
- Future threads should start from `main` and treat new work as post-roadmap enhancement rather than unfinished baseline setup.
