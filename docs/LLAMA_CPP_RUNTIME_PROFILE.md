# Llama.cpp Runtime Profile

## Chosen Baseline

The first concrete local model runtime profile for AnonExplo is `llama.cpp` in OpenAI-compatible server mode, using the CUDA container image for NVIDIA-backed local inference.

This profile was chosen because it:

- fits the target 4B to 8B GGUF quantized range well
- keeps the orchestrator adapter simple through an OpenAI-compatible API
- works cleanly with the repo's model-container isolation design
- is lighter and easier to reproduce locally than heavier serving stacks

## Default Profile Values

Tracked defaults in `.env.example` now assume:

- `MODEL_RUNTIME_PROFILE=llama.cpp-cuda`
- `MODEL_RUNTIME_IMAGE=ghcr.io/ggml-org/llama.cpp:server-cuda@sha256:59c2b6abd3c898e8f3b7beef3e2c871488d9a9783b6c6d766ffb1409e11c8044`
- `MODEL_NAME=qwen2.5-7b-instruct-q4_k_m`
- `MODEL_FILE_NAME=qwen2.5-7b-instruct-q4_k_m.gguf`
- `MODEL_CONTEXT_SIZE=4096`
- `MODEL_GPU_LAYERS=99`
- `MODEL_THREADS=8`
- `MODEL_BATCH_SIZE=512`
- `MODEL_RUNTIME_GPUS=all`

These defaults are intentionally conservative for the target workstation class and should be treated as a practical starting point, not as the only supported configuration.

## Provisioning Flow

1. Place a GGUF model file in `data/models/`.
2. Set `MODEL_FILE_NAME` to the exact filename.
3. Set `MODEL_NAME` to the identifier you want the backend and UI to display.
4. Review `MODEL_CONTEXT_SIZE`, `MODEL_GPU_LAYERS`, `MODEL_THREADS`, and `MODEL_BATCH_SIZE`.
5. Start the profile:

   ```powershell
   docker compose --profile llamacpp up -d model-backend
   ```

6. Verify the backend can see the runtime:

   ```powershell
   docker compose up -d backend
   Invoke-RestMethod http://127.0.0.1:8000/api/v1/model/models
   ```

## Recommended Model Class

For the current target hardware, start with a 4B to 8B instruct GGUF in a Q4-family quantization. A 7B-class instruct model is the most practical default for this repo at the moment because it gives a better baseline than tiny models without forcing the project into a heavier runtime stack.

## Notes

- The repo currently documents and validates the profile wiring and provisioning path. It does not ship model weights.
- The model container stays on the internal model network and is not meant to have direct egress.
- If a future branch introduces an additional runtime, keep the orchestrator adapter boundary intact instead of coupling the app to one backend.
