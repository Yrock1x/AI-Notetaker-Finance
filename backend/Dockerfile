# CogniSuite worker — FastAPI service over a worker-owned SQLite DB.
# Deploys to Fly.io via `fly deploy` (see fly.toml in the same dir).

FROM python:3.11-slim AS base

WORKDIR /app

# ffmpeg is kept because Deepgram orchestration + Recall bot recordings
# occasionally need audio re-encoding before we ship bytes onward.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

# Litestream — continuous SQLite backup to object storage. scripts/start.sh
# runs uvicorn under it when LITESTREAM_REPLICA_URL is set.
ARG LITESTREAM_VERSION=0.3.13
RUN curl -fsSL "https://github.com/benbjohnson/litestream/releases/download/v${LITESTREAM_VERSION}/litestream-v${LITESTREAM_VERSION}-linux-amd64.tar.gz" \
      | tar -xz -C /usr/local/bin litestream

# Install deps first, then source, so layer caching works when we only
# change app code.
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY app ./app
COPY alembic.ini litestream.yml ./
COPY scripts ./scripts
RUN chmod +x scripts/*.sh && mkdir -p /data/storage

# Runs as root so the mounted Fly volume at /data is writable (Fly mounts
# volumes root-owned). The container is a single trusted worker with no
# untrusted code execution; the trade-off is acceptable here.

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:${PORT:-8000}/api/v1/health || exit 1

# start.sh restores-from-backup-if-needed, runs `alembic upgrade head`, then
# launches a SINGLE uvicorn worker (under Litestream when configured).
# Single process is REQUIRED — in-process realtime pub/sub + single SQLite
# writer. Do NOT add --workers>1 or scale to >1 machine without distributed
# SQLite (Turso/LiteFS).
CMD ["sh", "/app/scripts/start.sh"]
