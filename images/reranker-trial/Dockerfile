FROM python:3.12-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2
# Explicit provisioning/build step only. Inference always uses --network none.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.14.0 \
    && pip install --no-cache-dir transformers==5.17.0 safetensors==0.8.0 \
    && pip freeze > /opt/runtime-versions.txt
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 HF_HOME=/tmp/hf
USER 65534:65534
WORKDIR /tmp
ENTRYPOINT ["python"]
