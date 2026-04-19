# CogniSuite worker — slim FastAPI service for LLM + webhook work.
# Deploys to Fly.io via `fly deploy` (see fly.toml in the same dir).

FROM python:3.11-slim AS base

WORKDIR /app

# ffmpeg is kept because Deepgram orchestration + Recall bot recordings
# occasionally need audio re-encoding before we ship bytes onward.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

# Install deps first, then source, so layer caching works when we only
# change app code.
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY app ./app

RUN adduser --disabled-password --gecos "" appuser
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:${PORT:-8000}/api/v1/health || exit 1

CMD ["sh", "-c", "uvicorn app.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}"]
