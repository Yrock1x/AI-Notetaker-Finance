FROM python:3.11-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy all source first (needed for pip install ".")
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir "."

# Create non-root user
RUN adduser --disabled-password --gecos "" appuser
USER appuser

EXPOSE 8000

CMD uvicorn app.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}
