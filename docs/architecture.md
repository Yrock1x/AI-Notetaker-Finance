# Architecture

## Overview

CogniSuite is a multi-tenant meeting intelligence platform built as a monorepo.
The data layer is **worker-owned SQLite** (migrated off Supabase — see
`backend/SQLITE_MIGRATION.md`).

## Stack

- **Worker**: Python / FastAPI, synchronous SQLAlchemy on SQLite (WAL mode)
- **Frontend**: Next.js 15 (React 19) with App Router; talks only to the worker
  REST API (`/api/v1/store/*`) via a cookie-authenticated fetch client
- **Database**: SQLite (WAL) + Alembic migrations; `sqlite-vec` (vec0 virtual
  table) for vector search
- **Async**: Inngest (serverless queue + cron) — replaced Celery + Redis
- **Storage**: local filesystem under `STORAGE_ROOT`, served via HMAC-signed,
  method-bound upload/download URLs
- **Auth**: self-issued session JWTs (HS256) in an httpOnly cookie; OAuth
  (Google / Microsoft) + email/password (Argon2id) handled by the worker
- **Realtime**: in-process pub/sub + SSE (requires the single-instance worker)
- **AI**: Fireworks (Llama 3.3 70B / DeepSeek V3 / nomic-embed) by default,
  Claude opt-in (`PREMIUM_LLM_ENABLED`); Deepgram (transcription); Recall.ai
  (meeting bots)

## Data Flow

```
Upload / bot recording → worker storage → Inngest pipeline:
  transcribe (Deepgram) → embed (Fireworks → sqlite-vec) → analyze (LLM router)
Live bot: Recall.ai → POST /api/v1/webhooks/recall/transcript → UPSERT
  transcript_segments → in-process pub/sub → SSE → Live page
```

Inngest functions orchestrate steps and call back into the worker's
`/api/v1/internal/*` endpoints (guarded by `X-Internal-Token`) for the LLM /
Deepgram / Recall work.

## Multi-Tenancy

- Enforced **in app code**, not Postgres RLS: every handler reading/writing a
  tenant-owned row goes through a scope guard in `app/db/scope.py`
  (`org_scoped` / `meeting_scoped` / `scoped_*_or_404` / `require_org` / `in_org`).
- A static AST tripwire (`tests/unit/test_scope_guard_lint.py`) fails the build
  if a route handler queries a tenant model without a scope guard.
- Deal-level RBAC (lead / admin / analyst / viewer) layered on top.

## Key Design Decisions

The single-instance deployment is intentional: in-process realtime pub/sub and
a single SQLite writer require one process. Horizontal scale would need
distributed SQLite (Turso / LiteFS), not more workers. See
`backend/SQLITE_MIGRATION.md` for the migration rationale and cutover runbook.
