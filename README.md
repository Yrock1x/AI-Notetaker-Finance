# CogniSuite

Meeting intelligence platform for investment banking, private equity, and
venture capital professionals.

## Architecture

- **Frontend** (Next.js 15, Vercel): `frontend/` — UI, Supabase-direct CRUD,
  Inngest runtime at `/api/inngest`.
- **Worker** (FastAPI, Fly.io): `backend/` — LLM routing, signed Supabase
  Storage uploads, Recall.ai live-transcript webhook, webhook signature
  verification.
- **Data** (Supabase): `supabase/` — Postgres + pgvector, Auth (Google /
  Microsoft OAuth), Storage, Realtime. Row-level security enforces
  multi-tenancy.
- **Async** (Inngest): serverless queue + cron, replaces Celery + Redis.
- **LLM** (Fireworks by default, Claude opt-in): Llama 3.3 70B / DeepSeek V3
  / nomic-embed. `PREMIUM_LLM_ENABLED=true` unlocks Claude per task.
- **Transcription** (Deepgram) and **meeting bots** (Recall.ai) unchanged.

## Quick start

```bash
# 1. Supabase
supabase start
supabase db reset                 # applies migrations + RLS
# sign up a dev user at http://localhost:54323, then:
supabase db execute -f supabase/seed.sql

# 2. Worker
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp ../.env.example ../.env        # fill in Supabase + LLM keys
uvicorn app.main:create_app --factory --port 8000 --reload

# 3. Frontend
cd frontend
npm install
cp ../.env.example .env.local     # same file, different location
npm run dev                       # http://localhost:3000

# 4. Inngest dev server (optional — runs pipelines locally)
npx inngest-cli@latest dev -u http://localhost:3000/api/inngest
```

## Development URLs

- Frontend: http://localhost:3000
- Worker API docs: http://localhost:8000/docs
- Supabase Studio: http://localhost:54323
- Inngest dev UI: http://localhost:8288

## Project layout

```
backend/          FastAPI worker (+ Dockerfile, fly.toml)
frontend/         Next.js app
supabase/         SQL migrations + local-dev config
.env.example      Combined env for worker + frontend + Vercel/Fly
```

See [CLAUDE.md](./CLAUDE.md) for the full architectural guide.

## Deploy

| Piece   | Destination | Trigger                                    |
|---------|-------------|--------------------------------------------|
| Frontend| Vercel      | git push to `main` (automatic)             |
| Worker  | Fly.io      | `.github/workflows/fly-deploy.yml`         |
| Schema  | Supabase    | `supabase db push` after `supabase link`   |
| Inngest | Inngest cloud | sync endpoint → `https://<vercel>/api/inngest` |
