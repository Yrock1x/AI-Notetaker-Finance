# Development Guide

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose
- ffmpeg (for audio extraction)

## Quick Start

```bash
# One-command setup
./scripts/setup-dev.sh

# Or manually:

# 1. Start infrastructure
cd backend && docker compose up -d postgres redis minio

# 2. Backend
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv/Scripts/activate on Windows
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:create_app --factory --port 8000 --reload

# 3. Celery worker
cd backend
celery -A app.tasks.celery_app worker --loglevel=info

# 4. Frontend
cd frontend
npm install
npm run dev
```

## Local Services

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Frontend | http://localhost:3000 |
| Flower | http://localhost:5555 |
| MinIO Console | http://localhost:9001 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

## Running Tests

```bash
cd backend
pytest tests/ -v
pytest tests/unit/ -v  # unit tests only
pytest tests/integration/ -v  # integration tests only
```

## Code Quality

```bash
cd backend
ruff check .  # linting
ruff format .  # formatting
mypy app/  # type checking
```
