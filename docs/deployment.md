# Deployment Guide

Two deploy targets: the **worker** (Fly.io) and the **frontend** (Vercel).
Inngest is configured via its dashboard. There is no AWS/Terraform footprint.

## Worker → Fly.io

- Built from `backend/Dockerfile`; config in `backend/fly.toml`.
- **Single instance** with an attached volume mounted at `/data` (holds the
  SQLite DB + file storage). Single process is required (in-process SSE pub/sub
  + single SQLite writer).
- `scripts/start.sh` is the entrypoint: restore-from-Litestream-if-the-DB-is-
  missing → `alembic upgrade head` → launch uvicorn under `litestream replicate`
  (continuous backup to S3).

```bash
cd backend
fly deploy
```

Set secrets via `fly secrets set` (non-`NEXT_PUBLIC_*` vars from `.env.example`):

- `SESSION_JWT_SECRET`, `STORAGE_SIGNING_KEY`, `WORKER_INTERNAL_TOKEN`
  (must be distinct, ≥32 chars — the worker fails fast in production otherwise)
- `TOKEN_ENCRYPTION_KEY` (Fernet), `FIREWORKS_API_KEY`
- `RECALL_API_KEY` + `RECALL_WEBHOOK_SECRET`, `DEEPGRAM_API_KEY`
- OAuth client secrets (Zoom / Microsoft / Google), `SLACK_SIGNING_SECRET`
- `LITESTREAM_REPLICA_URL` + replica credentials (S3 / R2 / etc.)
- `PUBLIC_API_URL` — the worker's public domain (OAuth redirect + Graph
  notification URLs are built from it)

## Frontend → Vercel

Git-integrated: push to `main` and Vercel auto-builds. Env:
`NEXT_PUBLIC_API_URL` (the worker's public URL), `INNGEST_EVENT_KEY`,
`INNGEST_SIGNING_KEY`, `WORKER_INTERNAL_TOKEN`.

## Inngest

Point the Inngest dashboard sync endpoint at `https://<vercel>/api/inngest`.

## CI/CD

`.github/workflows/ci.yml` runs the backend suite (ruff + mypy + full pytest)
and the frontend checks (type-check + vitest + lint + build) on every PR.
`.github/workflows/fly-deploy.yml` handles the worker deploy.

See `backend/SQLITE_MIGRATION.md` for the cutover/rollback runbook.
