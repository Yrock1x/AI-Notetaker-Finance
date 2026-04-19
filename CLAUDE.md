# CogniSuite - Project Guide

## Overview
Enterprise multi-tenant AI meeting intelligence platform for IB/PE/VC professionals.

## Stack
- **Frontend**: Next.js 15 / React 19 / TypeScript / Tailwind / shadcn-style UI
  - Direct Supabase via `@supabase/ssr` + `@supabase/supabase-js` for CRUD
  - React Query for server state, Zustand for lightweight client state
  - Hosts Inngest function runtime + `/api/inngest/send` relay
  - Deployed to **Vercel** (git-integrated, no GitHub Action needed)
- **Worker (Python/FastAPI)**: slim service for LLM calls, webhook ingestion,
  Supabase Storage signed uploads, live-transcript webhook from Recall.ai
  - Deployed to **Fly.io** via `flyctl deploy` (see `.github/workflows/fly-deploy.yml`)
- **Data**: Supabase — Postgres + pgvector + Auth (Google/Microsoft OAuth) +
  Storage + Realtime. RLS is the primary multi-tenancy enforcement.
- **Async jobs**: **Inngest** (serverless queue/cron). Replaced Celery + Redis.
- **LLM**: **Fireworks** (Llama 3.3 70B / DeepSeek V3 / nomic-embed) by default.
  Claude opt-in via `PREMIUM_LLM_ENABLED=true` + per-task env overrides.
- **Transcription**: Deepgram (unchanged).
- **Meeting bots**: Recall.ai (unchanged). Streams partial + finalized
  segments to the worker's webhook for live transcription via Supabase Realtime.

## Project Structure
```
backend/                      — slim FastAPI worker
  app/
    main.py                     FastAPI factory
    dependencies.py             Supabase JWT verifier + client DI
    core/                       config, logging, exceptions
    api/v1/                     auth, health, meetings_upload, analysis,
                                qa, deliverables, integrations (stubs),
                                webhooks, recall_webhooks
    services/                   qa_service, analysis_service, deliverable_service
    llm/                        router + fireworks_provider + prompts
    integrations/               deepgram, recall, zoom, teams, slack, outlook
    utils/                      file_processing (pdf/docx/xlsx text extraction)
  Dockerfile                    Fly.io deployment image
  fly.toml                      Fly config

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
      supabase/                 browser.ts, server.ts, middleware.ts
      inngest/                  client.ts, functions.ts (pipelines)
      api-client.ts             worker-only HTTP client
      auth.ts                   thin helpers over the browser client
    hooks/                      React Query hooks — most call Supabase directly
    stores/                     Zustand (auth-store shim, org-store, ui-store)

supabase/
  migrations/0001_initial.sql   16 tables, RLS policies, match_embeddings RPC
  seed.sql                      local-dev seed
  config.toml                   `supabase start` config (Auth providers, ports)
```

## Key Patterns
- **Frontend reads/writes Supabase directly.** No backend CRUD endpoints for
  deals, meetings, documents, memberships. RLS enforces org scoping.
- **Worker endpoints** exist only for requests needing a server secret
  (Fireworks/Claude/Deepgram), signed Supabase Storage upload URLs,
  webhook ingestion, or synchronous LLM work (Q&A, analyses, deliverables).
- **Async work** fires Inngest events. Client-triggered events route through
  `/api/inngest/send` (session-authenticated). Inngest functions orchestrate
  steps and call back into the FastAPI worker for LLM / Deepgram / Recall work.
- **Live transcription**: Recall.ai → `POST /api/v1/webhooks/recall/transcript`
  on the worker → worker UPSERTs into `transcript_segments` (service role)
  → Supabase Realtime broadcasts → Live page renders. Partials carry
  `is_partial=true`; UPSERT on `recall_segment_id` replaces them in place.
- **LLM routing**: every call goes through `LLMRouter.complete(task_type, ...)`.
  Task → model map in `backend/app/llm/router.py`. Override any row via
  `LLM_MODEL_FOR_<TASK>=<provider>:<model>`. Claude requires
  `PREMIUM_LLM_ENABLED=true` to ever be picked.

## Running Locally
```bash
# 1. Supabase stack
supabase start
supabase db reset                 # applies migrations
# create a user via http://localhost:54323, then:
supabase db execute -f supabase/seed.sql

# 2. Worker
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:create_app --factory --port 8000 --reload

# 3. Frontend
cd frontend && npm install
cp ../.env.example .env.local     # fill in Supabase + worker URLs
npm run dev                       # http://localhost:3000

# 4. Inngest dev server (optional — run pipelines locally)
npx inngest-cli@latest dev -u http://localhost:3000/api/inngest
```

## Deploy
- **Frontend → Vercel**: push to `main`; Vercel auto-builds. Set env:
  `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`,
  `NEXT_PUBLIC_API_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `INNGEST_EVENT_KEY`,
  `INNGEST_SIGNING_KEY`, `WORKER_INTERNAL_TOKEN`.
- **Worker → Fly.io**: `.github/workflows/fly-deploy.yml` runs on `backend/**`
  changes. `fly secrets set` everything in `.env.example` (minus `NEXT_PUBLIC_*`).
- **Supabase**: `supabase link` then `supabase db push` applies migrations.
- **Inngest dashboard**: sync endpoint → `https://<vercel>/api/inngest`.
