# Llama.cpp Runtime Profile

## Chosen Baseline

The first concrete local model runtime profile for AnonExplo is `llama.cpp` in OpenAI-compatible server mode, using the CUDA container image for NVIDIA-backed local inference.

This profile was chosen because it:

- fits the target 4B to 8B GGUF quantized range well
- keeps the orchestrator adapter simple through an OpenAI-compatible API
- works cleanly with the repo's model-container isolation design
- is lighter and easier to reproduce locally than heavier serving stacks

## Validated Default Artifact

The current validated default model path is:

- source repo: `QuantFactory/Qwen2.5-7B-Instruct-GGUF`
- file: `Qwen2.5-7B-Instruct.Q4_K_M.gguf`
- sha256: `4e9221217000d0fc8f5ffdbae51a7201fcc3613de18ff1b1cd8c7c01f924437b`
- local storage path: `data/models/Qwen2.5-7B-Instruct.Q4_K_M.gguf`
- configured model id: `qwen2.5-7b-instruct-q4_k_m`

This keeps the host-side provisioning step explicit while giving the backend and UI a stable model identifier through the `--alias` flag in the Compose profile.

## Default Profile Values

Tracked defaults in `.env.example` now assume:

- `MODEL_RUNTIME_PROFILE=llama.cpp-cuda`
- `MODEL_RUNTIME_IMAGE=ghcr.io/ggml-org/llama.cpp:server-cuda@sha256:59c2b6abd3c898e8f3b7beef3e2c871488d9a9783b6c6d766ffb1409e11c8044`
- `MODEL_NAME=qwen2.5-7b-instruct-q4_k_m`
- `MODEL_FILE_NAME=Qwen2.5-7B-Instruct.Q4_K_M.gguf`
- `MODEL_FILE_SHA256=4e9221217000d0fc8f5ffdbae51a7201fcc3613de18ff1b1cd8c7c01f924437b`
- `MODEL_SOURCE_URL=https://huggingface.co/QuantFactory/Qwen2.5-7B-Instruct-GGUF/resolve/main/Qwen2.5-7B-Instruct.Q4_K_M.gguf?download=true`
- `MODEL_PROBE_TIMEOUT_SECONDS=5`
- `MODEL_CONTEXT_SIZE=4096`
- `MODEL_GPU_LAYERS=99`
- `MODEL_THREADS=8`
- `MODEL_BATCH_SIZE=512`
- `MODEL_RUNTIME_GPUS=all`

These defaults are intentionally conservative for the target workstation class and should be treated as a practical starting point, not as the only supported configuration.

## Provisioning Flow

1. Bootstrap local files:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/bootstrap.ps1
   ```

2. Review `.env`.
   If it predates the current template and still contains placeholder model settings, copy the current runtime keys from `.env.example`.

3. Provision the default GGUF on the host:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/provision-default-model.ps1
   ```

4. Run the full repo validation, including the model runtime probe:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/validate.ps1 -RequireModelRuntime
   ```

5. Start the runtime profile:

   ```powershell
   docker compose --profile llamacpp up -d model-backend
   ```

6. Start the rest of the stack:

   ```powershell
   docker compose up --build ui backend fetcher search-provider
   ```

## Operational Notes

- The first cold start on the target workstation can take several minutes while `llama.cpp` loads tensors and initializes the GPU-backed context.
- The Compose healthcheck and validation script are intentionally tuned for that slower first-load path.
- The model container stays on the internal model network and does not need direct internet access.
- The provisioning flow downloads the GGUF on the host; runtime downloads inside the model container are not part of the supported path.

## Recommended Model Class

For the current target hardware, start with a 4B to 8B instruct GGUF in a Q4-family quantization. A 7B-class instruct model remains the most practical default for this repo at the moment because it gives a better baseline than tiny models without forcing the project into a heavier runtime stack.

## Notes

- The repo now validates the profile wiring, checksum, startup, `/v1/models` readiness, and a minimal chat-completions probe. It still does not ship model weights.
- If a future branch introduces an additional runtime, keep the orchestrator adapter boundary intact instead of coupling the app to one backend.
