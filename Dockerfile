FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt && \
    /opt/venv/bin/pip install --no-cache-dir pytest-cov

FROM python:3.11-slim AS runtime

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8001

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    poppler-utils \
    curl \
    tini && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd --system app && useradd --system --gid app --create-home app

COPY --from=builder /opt/venv /opt/venv

# Source code
COPY src/ src/
COPY scripts/quality_review.py scripts/quality_review.py
COPY scripts/extract_frame_overlays.py scripts/extract_frame_overlays.py
COPY scripts/verify_composite.py scripts/verify_composite.py

# All config files
COPY config/ config/

# Root files
COPY favicon.ico favicon.ico
COPY .env.example .env.example

# Create runtime directories
RUN mkdir -p data tmp "Output Covers" "Input Covers"

RUN chown -R app:app /app

USER app

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT}/api/health" || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sh", "-c", "exec python3 scripts/quality_review.py --serve --host ${HOST:-0.0.0.0} --port ${PORT:-8001} --output-dir \"Output Covers\""]
