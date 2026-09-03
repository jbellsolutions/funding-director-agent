# Reviewed Hermes Agent v0.21.0 release. The tag is readable and the digest
# makes every build use the exact same upstream image.
FROM nousresearch/hermes-agent:v2026.8.31@sha256:64923faeae267792bf9bf87fe3b4c4869e35004e360c7df01730ad801b74d524

USER root

# Live voice stack.
RUN uv pip install --python /opt/hermes/.venv/bin/python --no-cache \
      faster-whisper==1.2.1 \
      edge-tts==7.2.7

# The browser router source is byte-for-byte identical to the active live copy.
COPY files/local-packages/super-browser /opt/super-browser
RUN uv venv --python /opt/hermes/.venv/bin/python /opt/super-browser/.venv \
    && uv pip install --no-config --python /opt/super-browser/.venv/bin/python \
         --require-hashes --no-cache \
         -r /opt/super-browser/requirements-runtime.lock \
    && PLAYWRIGHT_BROWSERS_PATH=/opt/playwright \
         /opt/super-browser/.venv/bin/python -m playwright install --with-deps chromium \
    && chmod +x /opt/super-browser/mcp/super-browser-server

# Deterministic funding case, underwriting, approval, CRM, and submission core.
COPY files/local-packages/funding-director/src /opt/funding-director/src

ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
