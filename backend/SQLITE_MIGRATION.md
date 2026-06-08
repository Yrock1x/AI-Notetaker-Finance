# SQLite Migration — Status & Cutover Runbook

This documents the Supabase → SQLite migration built per the approved plan
(`~/.claude/plans/i-recently-received-this-golden-pine.md`). The new stack was
built **additively** alongside the existing Supabase code, so the app keeps
running on Supabase until you deliberately cut over.

## What's done (built + tested)

All new code lives under `backend/app/db`, `backend/app/storage`,
`backend/app/realtime`, `backend/app/auth`, `backend/app/api/v1/store`,
`backend/app/api/v1/partner`. **112 backend unit tests pass.**

| WS | Area | Modules | Tests |
|----|------|---------|-------|
| 1 | Schema + engine + Alembic | `db/models.py`, `db/engine.py`, `db/base.py`, `db/migrations/` | schema builds via `alembic upgrade head` (20 tables + vec0) |
| 2 | Vector search (pgvector→sqlite-vec) | `db/vectors.py` | per-deal KNN, cosine, min-similarity |
| 3 | App-layer RLS | `db/scope.py` | cross-tenant isolation + denial |
| 4 | REST API (replaces browser→Supabase) | `api/v1/store/*` | deals, meetings, documents, transcripts, bot-sessions, orgs, dashboard, files |
| 5 | Auth (OAuth + session JWT) | `auth/*`, `api/v1/auth_native.py` | tokens, provisioning, cookie auth |
| 6 | Realtime (SSE + pub/sub) | `realtime/*` | pub/sub fan-out; SSE scoped; wired into recall webhook |
| 7 | Storage (filesystem + signed URLs) | `storage/local.py`, `api/v1/store/files.py` | save/read, sign/verify, path-traversal guard |
| 10 | Data migration | `db/migrate_from_supabase.py` | transform helpers tested |
| 11 | CogniVault partner API | `api/v1/partner/*` | M2M key auth, scopes, cross-tenant 404, search |
| 9 | Cheap-model meeting Q&A | `services/qa_service.py` | full-transcript path + RAG fallback |

Frontend: data hooks, auth, and live-transcript SSE migrated to the worker API
(cookie auth); `npm run type-check` passes. See "Remaining" for leftovers.

## New config (env vars)

```
SQLITE_DB_PATH=/data/app.db          # on the Fly volume
STORAGE_ROOT=/data/storage           # object storage root
STORAGE_SIGNING_KEY=<random secret>  # HMAC for signed URLs (distinct in prod)
SESSION_JWT_SECRET=<random secret>   # signs session cookies (distinct in prod)
SESSION_COOKIE_NAME=cogni_session
GOOGLE_CLIENT_ID/SECRET, MICROSOFT_CLIENT_ID/SECRET   # OAuth (already present)
```

Fly.io: attach a persistent volume mounted at `/data`, bump the instance to
≥1GB RAM, and **run a single instance** (in-process pub/sub + single SQLite
writer require it).

## Cutover procedure

Most of this is now wired into the deploy (`fly.toml`, `Dockerfile`,
`scripts/start.sh`, `litestream.yml`). The only manual steps are the ones that
need your credentials/console.

1. **Provision + secrets** (one-time):
   ```
   cd backend
   fly volumes create cogni_data --region iad --size 10
   fly secrets set SESSION_JWT_SECRET=... STORAGE_SIGNING_KEY=... \
       LITESTREAM_REPLICA_URL=s3://<bucket>/cogni/app.db \
       LITESTREAM_ACCESS_KEY_ID=... LITESTREAM_SECRET_ACCESS_KEY=... \
       <plus the existing FIREWORKS/DEEPGRAM/RECALL/INNGEST/OAuth/TOKEN_ENCRYPTION_KEY/WORKER_INTERNAL_TOKEN secrets>
   fly secrets set SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=...   # for the one-time import
   ```
2. **Deploy** → `fly deploy`. On boot, `start.sh` restores-from-backup-if-needed,
   runs `alembic upgrade head` (creates schema + vec0 on the volume), and starts a
   single worker under Litestream (continuous backup ON).
3. **Freeze writes** on the Supabase app (maintenance window).
4. **Import data** → `fly ssh console -C "/app/scripts/cutover.sh"` (copies all
   tables, embeddings→vec0, storage buckets→`/data/storage`; re-runnable).
5. **Verify** → per-table row counts (logged), a `POST /partner/v1/deals/{id}/search`,
   and `GET /api/v1/auth/login/google`.
6. **Flip the frontend** → set Vercel `NEXT_PUBLIC_API_URL` to the worker and
   redeploy; users re-consent OAuth on first login (new cookie).
7. **Rollback window** → keep Supabase read-only for a while. Backups are already
   running via Litestream (step 2).

## WS8 service-layer cutover — DONE

The synchronous LLM/pipeline + OAuth layer is now fully off Supabase
(**142 backend tests pass**; `grep` confirms no `supabase`/`get_service_supabase`
in the store/partner/service/internal/integration paths):

- `services/qa_service.py`, `analysis_service.py`, `deliverable_service.py`,
  `oauth_tokens.py` → SQLAlchemy `Session` (services flush; the request's get_db
  commits; error-state writes that must survive a rollback commit explicitly).
- `api/v1/internal.py` → transcribe (Deepgram `transcribe_bytes` from local
  storage, no signed URL), embed + process_document (Embedding + vec0 dual-write),
  analyze, bot lifecycle, zoom_ingest, calendar_sync, Teams/Graph handlers, and a
  new `POST /internal/meeting-status` for Inngest.
- `api/v1/qa.py`, `analysis.py`, `deliverables.py`, `integrations.py` → get_db +
  app-layer org scoping.
- Frontend `inngest/functions.ts` (status writes → `/internal/meeting-status`),
  `/api/inngest/send` (ownership check via worker session), and the leftover
  components/auth-callback are migrated.

A post-cutover review caught and we fixed two HIGH cross-tenant scoping
regressions (analysis + deliverables endpoints had dropped org checks) and a
legacy-`teams` token-refresh bug; regression tests added. A concurrency stress
test confirms WAL handles the live-transcript write pattern (~4k rows/s, no
locking).

## Remaining (minor / verify-in-staging)

1. **Real OAuth round-trip** — Google/Microsoft login/callback is implemented but
   only provider-mocked; verify against live providers in staging.
2. **Delete `frontend/src/lib/supabase/*`** — now orphaned (no consumers); remove
   along with the `@supabase/*` deps in a cleanup commit.
3. **`meetings_upload.py`** — superseded by `/storage/upload-ticket`; the frontend
   already uses the new path. Remove or repoint the old endpoint.
4. **Low-priority polish** from review: Teams calendar-match uses an exact
   timestamp compare (should be a ±30min window); a couple of stale
   "RLS"-referencing docstrings.

## Risks (from the plan — still apply)

Single owner/writer (no horizontal scale without distributed SQLite); backups
are now your responsibility (Litestream); tenant isolation is app-enforced
(audited — see the scope module + cross-tenant tests). See the plan's Risks
section before taking production traffic.
