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

Provisioning/build complete; frozen offline evaluation and full validation pending.
No production integration, restart or search engine changes.
