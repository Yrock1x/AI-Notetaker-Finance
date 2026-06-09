# CogniSuite - Project Guide

## Overview
Enterprise multi-tenant AI meeting intelligence platform for IB/PE/VC professionals.

> **Migration status**: the data layer has moved off Supabase to a worker-owned
> SQLite stack (see `backend/SQLITE_MIGRATION.md`). The app code now runs on the
> new stack; Supabase is retained only as the one-time import source and a
> rollback-window auth fallback (gated by `LEGACY_SUPABASE_AUTH_ENABLED`, default
> on until the production cutover). The sections below describe the new
> architecture.

## Stack
- **Frontend**: Next.js 15 / React 19 / TypeScript / Tailwind / shadcn-style UI
  - All CRUD goes through the worker's REST API (`/api/v1/store/*`) via
    `lib/worker-api.ts`, cookie-authenticated (`credentials: include`). No
    direct database access from the browser.
  - React Query for server state, Zustand for lightweight client state
  - Hosts Inngest function runtime + `/api/inngest/send` relay
  - Deployed to **Vercel** (git-integrated, no GitHub Action needed)
- **Worker (Python/FastAPI)**: owns the data layer (SQLAlchemy + SQLite) and
  serves all reads/writes, OAuth login + session, LLM calls, webhook ingestion,
  signed-URL file storage, and the live-transcript webhook from Recall.ai
  - Deployed to **Fly.io** (single instance + attached volume; Litestream
    streams continuous backups to S3). See `backend/fly.toml`, `litestream.yml`,
    `scripts/start.sh`.
- **Data**: worker-owned **SQLite** (WAL mode) via SQLAlchemy + Alembic.
  - **Vector search**: `sqlite-vec` (vec0 virtual table) replaces pgvector —
    `app/db/vectors.py`.
  - **Multi-tenancy**: enforced in app code (`app/db/scope.py` —
    `org_scoped`/`meeting_scoped`/`require_org`), NOT Postgres RLS. A static
    tripwire (`tests/unit/test_scope_guard_lint.py`) guards against regressions.
  - **Auth**: self-issued session JWTs (HS256) in an httpOnly cookie; OAuth
    login/callback handled by the worker (`app/api/v1/auth_native.py`,
    `app/auth/`).
  - **Storage**: filesystem under `STORAGE_ROOT` with HMAC-signed upload/download
    URLs (`app/storage/local.py`, `app/api/v1/store/files.py`).
  - **Realtime**: in-process pub/sub + SSE (`app/realtime/`) replaces Supabase
    Realtime (requires the single-instance deployment).
- **Async jobs**: **Inngest** (serverless queue/cron). Replaced Celery + Redis.
- **LLM**: **Fireworks** (Llama 3.3 70B / DeepSeek V3 / nomic-embed) by default.
  Claude opt-in via `PREMIUM_LLM_ENABLED=true` + per-task env overrides.
- **Transcription**: Deepgram (unchanged).
- **Meeting bots**: Recall.ai (unchanged). Streams partial + finalized segments
  to the worker's webhook for live transcription, fanned out over SSE.

## Project Structure
```
backend/                      — slim FastAPI worker
  app/
    main.py                     FastAPI factory
    dependencies.py             request auth (session JWT, Supabase fallback) +
                                LLM router DI
    core/                       config, logging, exceptions
    db/                         SQLAlchemy models, engine, scope (app-layer RLS),
                                vectors (sqlite-vec), migrations (Alembic),
                                migrate_from_supabase (one-time import)
    auth/                       session tokens + first-login provisioning
    storage/                    local.py (filesystem + HMAC signed URLs)
    realtime/                   pubsub.py + sse.py (replaces Supabase Realtime)
    api/v1/                     auth_native, health, analysis, qa, deliverables,
                                integrations, webhooks, recall_webhooks, internal
      store/                    REST CRUD (deals, meetings, documents,
                                transcripts, bot_sessions, orgs, dashboard, files)
      partner/                  CogniVault M2M partner API (/partner/v1)
    services/                   qa_service, analysis_service, deliverable_service,
                                oauth_tokens
    llm/                        router + fireworks_provider + prompts
    integrations/               deepgram, recall, zoom, teams, microsoft,
                                google, slack
    utils/                      file_processing (pdf/docx/xlsx text extraction)
  Dockerfile                    Fly.io deployment image (runs under Litestream)

frontend/                      — Next.js app
  src/
    middleware.ts               session refresh + unauthenticated redirect
    app/
      (auth)/login              OAuth sign-in (Google / Microsoft)
      auth/callback/route.ts    code-for-session exchange
      (app)/                    authed pages — deals, meetings, etc.
        deals/[id]/meetings/[id]/live   live-transcription panel
      api/inngest/              Inngest runtime (/) + send relay (/send)
    lib/
      worker-api.ts             cookie-authed fetch client for the worker REST API
      inngest/                  client.ts, functions.ts (pipelines)
      api-client.ts             legacy axios client (LLM/Q&A endpoints)
      auth.ts                   OAuth login + signout helpers over the worker API
    hooks/                      React Query hooks — all call the worker REST API
    stores/                     Zustand (auth-store shim, org-store, ui-store)

supabase/                       LEGACY — source schema for the one-time import;
                                retained until the cutover + rollback window close
  migrations/0001_initial.sql   16 tables, RLS policies, match_embeddings RPC
  seed.sql                      local-dev seed
  config.toml                   `supabase start` config (Auth providers, ports)
```

## Key Patterns
- **Frontend talks only to the worker.** All CRUD goes through the worker's
  `/api/v1/store/*` REST API (cookie-authenticated), never a database directly.
  Tenant scoping is enforced server-side in `app/db/scope.py`.
- **App-layer multi-tenancy.** Every handler that reads/writes a tenant-owned
  row must go through a scope guard (`org_scoped`/`meeting_scoped`/
  `scoped_*_or_404`/`require_org`/`in_org`). `tests/unit/test_scope_guard_lint.py`
  fails the build if a handler queries a tenant model without one.
- **Async work** fires Inngest events. Client-triggered events route through
  `/api/inngest/send` (session-authenticated). Inngest functions orchestrate
  steps and call back into the FastAPI worker's `/api/v1/internal/*` endpoints
  (guarded by `X-Internal-Token`) for LLM / Deepgram / Recall work.
- **Live transcription**: Recall.ai → `POST /api/v1/webhooks/recall/transcript`
  on the worker → worker UPSERTs into `transcript_segments` → in-process pub/sub
  publishes the event → SSE (`GET /api/v1/meetings/{id}/stream`) fans it out to
  the Live page. Partials carry `is_partial=true`; UPSERT on `recall_segment_id`
  replaces them in place.
- **LLM routing**: every call goes through `LLMRouter.complete(task_type, ...)`.
  Task → model map in `backend/app/llm/router.py`. Override any row via
  `LLM_MODEL_FOR_<TASK>=<provider>:<model>`. Claude requires
  `PREMIUM_LLM_ENABLED=true` to ever be picked.

## Running Locally
```bash
# 1. Worker (owns the SQLite DB + storage)
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
export SQLITE_DB_PATH=./dev.db STORAGE_ROOT=./dev-storage
alembic upgrade head               # creates the schema + vec0 table
uvicorn app.main:create_app --factory --port 8000 --reload
pytest                             # run the backend suite

# 2. Frontend
cd frontend && npm install
cp ../.env.example .env.local      # set NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                        # http://localhost:3000
npm run type-check

# 3. Inngest dev server (optional — run pipelines locally)
npx inngest-cli@latest dev -u http://localhost:3000/api/inngest
```

## Deploy
- **Frontend → Vercel**: push to `main`; Vercel auto-builds. Set env:
  `NEXT_PUBLIC_API_URL` (the worker's public URL), `INNGEST_EVENT_KEY`,
  `INNGEST_SIGNING_KEY`, `WORKER_INTERNAL_TOKEN`.
- **Worker → Fly.io**: `fly deploy` from `backend/`. Single instance with an
  attached volume mounted at `/data` (SQLite + storage); `scripts/start.sh`
  restores-from-backup-if-needed, runs `alembic upgrade head`, and starts the
  worker under Litestream (continuous S3 backup). Set the non-`NEXT_PUBLIC_*`
  vars from `.env.example` plus `SESSION_JWT_SECRET`, `STORAGE_SIGNING_KEY`, and
  the `LITESTREAM_*` secrets via `fly secrets set`. `PUBLIC_API_URL` must be the
  worker's public domain; OAuth redirect URIs + Graph notification URLs build
  from it. See `backend/SQLITE_MIGRATION.md` for the cutover runbook.
- **Inngest dashboard**: sync endpoint → `https://<vercel>/api/inngest`.
