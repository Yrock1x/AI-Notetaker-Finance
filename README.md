# CogniSuite

Meeting intelligence platform for investment banking, private equity, and
venture capital professionals.

## Architecture

- **Frontend** (Next.js 15 / React 19, Vercel): `frontend/` — UI. All CRUD goes
  through the worker's REST API (`/api/v1/store/*`) via `lib/worker-api.ts`
  (cookie-authenticated); no direct database access. Hosts the Inngest runtime
  at `/api/inngest` + the `/api/inngest/send` relay.
- **Worker** (Python / FastAPI, Fly.io): `backend/` — owns the data layer, OAuth
  + email/password login and self-issued session JWTs, LLM routing, webhook
  ingestion, signed-URL file storage, and the Recall.ai live-transcript webhook
  fanned out over SSE.
- **Data** (worker-owned **SQLite**, WAL): SQLAlchemy + Alembic. Vector search
  via `sqlite-vec`. Multi-tenancy is enforced in app code (`app/db/scope.py`),
  not Postgres RLS. Litestream streams continuous backups to S3.
- **Async** (Inngest): serverless queue + cron (replaced Celery + Redis).
- **LLM** (Fireworks by default, Claude opt-in): Llama 3.3 70B / DeepSeek V3 /
  nomic-embed. `PREMIUM_LLM_ENABLED=true` unlocks Claude per task.
- **Transcription** (Deepgram) and **meeting bots** (Recall.ai).

> Migrated off Supabase to the worker-owned SQLite stack — see
> `backend/SQLITE_MIGRATION.md`.

## Quick start

```bash
# 1. Worker (owns the SQLite DB + file storage)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
export SQLITE_DB_PATH=./dev.db STORAGE_ROOT=./dev-storage
alembic upgrade head               # creates the schema + vec0 table
uvicorn app.main:create_app --factory --port 8000 --reload
pytest                             # run the backend suite

# 2. Frontend
cd frontend && npm install
cp ../.env.example .env.local      # set NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                        # http://localhost:3000

# 3. Inngest dev server (optional — runs pipelines locally)
npx inngest-cli@latest dev -u http://localhost:3000/api/inngest
```

## Development URLs

- Frontend: http://localhost:3000
- Worker API docs: http://localhost:8000/docs
- Inngest dev UI: http://localhost:8288

## Project layout

```
backend/          FastAPI worker (SQLite data layer; + Dockerfile, fly.toml, litestream.yml)
frontend/         Next.js app
supabase/         LEGACY — source schema for the one-time import (retained for reference)
.env.example      Combined env for worker + frontend + Vercel/Fly
```

See [CLAUDE.md](./CLAUDE.md) for the full architectural guide and
[docs/](./docs) for architecture / deployment / development / security / API
references.

## Deploy

| Piece    | Destination   | Trigger                                          |
|----------|---------------|--------------------------------------------------|
| Frontend | Vercel        | git push to `main` (automatic)                   |
| Worker   | Fly.io        | `fly deploy` from `backend/` (single instance + volume; runs under Litestream) |
| Inngest  | Inngest cloud | sync endpoint → `https://<vercel>/api/inngest`   |
