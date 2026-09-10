# Local relevance-gated preference trial

User explicitly approved trying a local model to prevent unrelated preferred-site
promotions. New scope stamos/local-reranker-trial from f2d6691. This is distinct
from the closed ordering-policy study. No legacy UI, query history or production
model endpoint is restored; browser search remains unchanged during evaluation.

Candidate: BAAI/bge-reranker-v2-m3, Apache-2.0, official revision
953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e. Official model card:
https://huggingface.co/BAAI/bge-reranker-v2-m3 . It supports local Transformers
sequence-classification inference; sigmoid scores are NOT calibrated probabilities
of relevance or truth. Greek suitability must be tested, not inferred from the
multilingual label. The safetensors artifact is 2,271,071,852 bytes (~2.27 GB).

## Provisioning and isolation

provision-local-reranker.ps1 downloads only explicitly allowlisted files from
the pinned official revision. LFS objects get SHA256 verification; small files
get Git-blob SHA1 verification against official metadata. Partial or mismatching
existing files cause refusal, never silent overwrite. Model files stay ignored
under data/models. The explicit -Build step uses a digest-pinned Python image,
official PyTorch CPU packages and PyPI. Top-level versions are exact; initial
transitive resolution is captured in the image's /opt/runtime-versions.txt.
An image digest/complete dependency lock is required before production adoption.

CPU trial image is separate from the production SearXNG image. This PC has about
128 GiB RAM and RTX 5090 32 GiB; GPU inference is not configured in this initial
CPU trial. No host Python packages or GPU drivers are changed.

test-local-reranker.ps1 runs network=none, no ports, non-root, read-only root and
model/script mounts, all capabilities dropped, no-new-privileges, 12 GiB RAM,
8 CPUs, 256 PIDs, bounded tmpfs, no Docker logs. Offline flags and local_files_only
are enforced; trust_remote_code=False and safetensors only. Runner asserts only
loopback network interface and failed public-IP connection. No VPN/key/cache
mount, browser data, upstream query, fetched page or user domain list is used.
Outputs are case IDs, scores and timings only. No remote AI API exists.

## Frozen functional evaluation

Freeze scripts/reranker_fixtures.json before scoring. Four development and four
holdout cases, equal EN/EL. Each has one relevant synthetic snippet, three
negative/adjacent-topic/adversarial snippets, including attempted ranking
instructions. These are controlled function tests, not real-world relevance
validation or factual verification. All threshold/policy choices are fixed before
evaluation; no tuning on observed holdout. A score >=0.8 makes a result eligible,
not guaranteed relevant. Required: positive top-ranked in all eight cases, zero
negative snippets >=0.8, at least six eligible positives, and warm CPU batch of
24 pairs <=2s. Failure means do not integrate this candidate configuration.
Passing only permits a later bounded real-result evaluation, not deployment.

Pure optional policy in reranker_gate.py: only preferred hosts with score >=0.8
may receive 15% native-score boost, at most two upward positions, never crossing
a result with model score more than 0.05 higher. Invalid/missing model scores
leave order unchanged. No result is deleted, rewritten or independently fetched.
The user's preferred domains must remain local, not embedded in this repository
or sent to providers. No private list is installed or active in this trial.

## Outcome

Frozen fixtures/policy committed and pushed at 41a413f before evaluation.
Fixture SHA256: 9c83e4d83b354561381d38559228ebb82b46f3565297756f9994d099009f0e6d.

| Case | Relevant score | Largest negative score | Eligible positive |
| --- | ---: | ---: | --- |
| dev-en-dns | 0.978063 | 0.000821 | yes |
| dev-el-water | 0.989685 | 0.000029 | yes |
| dev-en-port | 0.955227 | 0.029528 | yes |
| dev-el-licence | 0.985977 | 0.008520 | yes |
| test-en-battery | 0.006515 | 0.000411 | no |
| test-el-relative | 0.855054 | 0.001394 | yes |
| test-en-news | 0.923590 | 0.003511 | yes |
| test-el-certificate | 0.996475 | 0.076241 | yes |

Relevant snippet top-ranked 8/8; zero of 24 negatives crossed 0.8. Seven of eight
positives eligible, including all four Greek positives. The cold-battery positive
was strongly under-scored despite being correctly ordered relative to negatives:
this shows why an absolute score is not a probability and conservative gating can
miss genuinely useful preferred pages. No threshold was changed after inspection.
The four holdouts are now observed regression fixtures, not fresh validation.
This tiny authored suite does not establish real-result false-positive rates or
resistance to arbitrary adversarial content.

Warm four-pair times 0.242–0.346s; warm batch of 24 short pairs 1.559s on CPU.
CPU functional/latency gate passed. Longer snippets, 512-token batches, cold start,
concurrent searches and real-result performance remain unmeasured. No GPU trial.
Loopback-only interface and failed public-IP connection checks passed in the actual
inference container. Runtime dependency capture: RERANKER_RUNTIME_VERSIONS.txt.
Local evaluated image index: sha256:a1ecd793732ada795e0f2fb5162b126b748a982ca902a5a7513df946f2b5cb99;
platform manifest: sha256:cb292e14b807bebf61dfd564272937f329ef87d25a547ee6d122334cfbef6955.
These are provenance records, not an immutable registry publication.

Decision: promising enough for separately bounded real-result shadow evaluation;
NOT approved as a production relevance filter from synthetic evidence alone.
Future integration needs full artifact/runtime verification, disabled-by-default
local configuration, a fixed request/time budget and unchanged-order fallback on
failure. Keep preferred domains local; no model on an egress-capable network.
No production integration, restart or search-engine changes. Model artifacts and
the trial image remain locally available; no permanent model process is running.
Full validate.ps1 passed: 127 Python test executions (91 host, 12 historical
News, 11 timeout semantics, 13 date), 20 negative Compose cases, seven negative
image-identity cases plus equality, managed isolated search-image build, native
privacy/settings/ranking, blocked direct egress and outage/recovery cleanup.
The separately managed reranker image was built successfully during explicit
provisioning and exercised in the actual model trial. Optional unrelated retired
DDG candidate suites not repeated. Reviewed tooling/docs accompany commit/push,
main merge and scoped local/remote branch cleanup. No production deployment or
installer/release applies to this isolated experiment.
