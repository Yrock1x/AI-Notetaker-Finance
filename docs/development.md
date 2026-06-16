# Development Guide

## Prerequisites

- Python 3.11+
- Node.js 20+

No Docker/Postgres/Redis needed — the data layer is a local SQLite file.

## Quick Start

```bash
# 1. Worker (owns the SQLite DB + file storage)
cd backend
python -m venv .venv
source .venv/bin/activate          # or .venv/Scripts/activate on Windows
pip install -e ".[dev]"
export SQLITE_DB_PATH=./dev.db STORAGE_ROOT=./dev-storage
alembic upgrade head               # creates the schema + vec0 table
uvicorn app.main:create_app --factory --port 8000 --reload

# 2. Frontend
cd frontend
npm install
cp ../.env.example .env.local      # set NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev

# 3. Inngest dev server (optional — runs pipelines locally)
npx inngest-cli@latest dev -u http://localhost:3000/api/inngest
```

## Local Services

| Service        | URL                       |
|----------------|---------------------------|
| Worker API     | http://localhost:8000     |
| API Docs       | http://localhost:8000/docs |
| Frontend       | http://localhost:3000     |
| Inngest dev UI | http://localhost:8288     |

## Running Tests

```bash
# Backend
cd backend
pytest                  # full unit suite

# Frontend
cd frontend
npm run type-check
npm test
```

## Code Quality

```bash
# Backend (CI gates `ruff check app` + `mypy app`)
cd backend
ruff check app
ruff format app
mypy app --ignore-missing-imports

# Frontend
cd frontend
npm run lint
```

> macOS external-volume note: AppleDouble `._*` files can break Alembic with a
> "null bytes" error — `find app/db/migrations/versions -name '._*' -delete`
> first if you hit it.
