# CogniSuite — Migration to Supabase + Vercel + Fireworks

## Context

You want to simplify the platform by dropping the AWS Terraform footprint in
favor of managed services. The current stack (FastAPI on ECS + RDS + Cognito
+ ElastiCache + S3 + SQS + Celery workers, all glued together with Terraform)
has a lot of infrastructure that a seed-stage product doesn't need. The move:

- **Supabase** replaces Postgres + Auth + Storage (and makes RLS the primary
  multi-tenancy mechanism, which your RLS-based design already assumes).
- **Vercel** hosts the existing Next.js 15 frontend.
- **Fly.io** hosts a slim FastAPI worker — only for LLM calls, Deepgram
  orchestration, Recall webhooks, and deliverable generation. Everything
  else is deleted.
- **Inngest** runs the async pipeline (transcribe → diarize → embed + analyze
  → notify). Replaces Celery + Redis.
- **Fireworks** becomes the default LLM for all tasks. Claude remains a
  pluggable option but is off by default — flipped on per-task via an env
  flag so you can opt back into premium quality when needed without code
  changes.
- **Deepgram** and **Recall.ai** stay exactly as they are.

You confirmed: fresh schema (no prod data), you'll supply all account credentials
via `.env`, and I'm making the rest of the calls.

---

## Target architecture

```
┌────────────────────┐      ┌──────────────────────┐
│  Next.js (Vercel)  │ ───► │  Supabase            │
│                    │      │  • Postgres+pgvector │
│  • UI              │      │  • Auth (Google+MS)  │
│  • supabase-js     │ ───► │  • Storage           │
│    direct CRUD     │      │  • Realtime  ◄───────┼── live transcript
│  • Realtime sub    │ ◄─── │  • RLS policies      │
└────────┬───────────┘      └──────────▲───────────┘
         │                             │ (server-role insert)
         │ (Bearer = Supabase JWT)     │
         ▼                             │
┌────────────────────┐      ┌──────────┴────────────┐
│  FastAPI (Fly.io)  │ ───► │  Inngest               │
│                    │ ───► │  serverless jobs       │
│  • LLM endpoints   │      │  • post-meeting pipe   │
│  • upload tickets  │ ◄─── │  • recall event bus    │
│  • Recall webhooks │      │  • calendar sync (cron)│
│    (partial + final│      └─────────────┬──────────┘
│     transcripts)   │                    │
│  • deliverables    │                    ▼
└────┬──────────────┬┘             ┌──────────────┐
     │              │              │  Fireworks   │
     ▼              ▼              │  (default)   │
┌──────────┐  ┌──────────┐         │  Claude opt. │
│ Deepgram │  │  Recall  │         └──────────────┘
└──────────┘  │  (w/ real│
              │   -time) │
              └──────────┘
```

**Auth flow:** browser → Supabase Auth (Google/MS OAuth) → receives Supabase
JWT → sends as `Authorization: Bearer` to FastAPI. FastAPI verifies the JWT
against Supabase's JWKS, extracts `sub` (user_id) and the user's active
`org_id` from a `user_org_memberships` view or JWT custom claim.

**Data flow:** frontend does all read + trivial write operations directly
against Supabase (RLS-scoped). FastAPI is only touched when a request needs
a secret (Fireworks/Claude/Deepgram API keys), signed URLs beyond Supabase's,
or async dispatch.

---

## Locked-in decisions

- **LLM routing policy** — a task → model table in
  [backend/app/llm/router.py](backend/app/llm/router.py). Default rows all
  point to Fireworks models. `PREMIUM_LLM_ENABLED=false` gates whether any
  Claude model is ever picked. Individual per-task overrides via env:
  `LLM_MODEL_FOR_IC_MEMO=anthropic:claude-sonnet-4-6` etc. **Answer to "what
  does Claude budget mean":** I default to zero Claude spend; you flip the
  env flag later if IC memos feel weak.

- **Branch strategy** — rip-and-replace on `main`, but split across one PR
  per phase below so each is independently revertable. No long-lived branch.

- **Embeddings** — Fireworks `nomic-ai/nomic-embed-text-v1.5` (768-dim).
  Requires a one-time re-embed (no prod data → n/a for us).

- **Live transcription is in scope.** Recall.ai streams partial +
  finalized transcript events to a webhook on the worker; the worker writes
  them to `transcript_segments` (with `is_partial` flag) using the Supabase
  service-role key; the frontend subscribes via Supabase Realtime and
  renders them as they arrive. No custom WebSocket server.

- **Rate limiting** — drop the in-memory/Redis middleware; use Supabase's
  built-in limits for direct queries and Fly.io concurrency caps for the
  FastAPI worker. Re-add explicit rate limiting only if/when abuse appears.

---

## What survives, what dies

### Keeps + adapts
- `backend/app/services/deliverable_service.py` — LLM-driven docx generation
- `backend/app/services/qa_service.py` — RAG + citation extraction
- `backend/app/services/analysis_service.py` — call-type prompt routing
- `backend/app/llm/` (router, chunking, guardrails, prompts) + new
  `fireworks_provider.py`
- `backend/app/integrations/deepgram/` (unchanged)
- `backend/app/integrations/recall/` (unchanged)
- `backend/app/integrations/zoom/`, `teams/`, `slack/`, `outlook/` — OAuth
  flows move to Supabase-stored encrypted tokens; HMAC webhook verification
  in [backend/app/api/v1/webhooks.py:20-67](backend/app/api/v1/webhooks.py#L20-L67) is reused as-is
- `backend/app/tasks/meeting_bot.py` logic — ported into Inngest functions
- `backend/app/utils/file_processing.py` — pdf/docx/xlsx extractors

### Deletes
- All AWS Terraform modules except README. Remove
  [infrastructure/terraform/](infrastructure/terraform/) directory entirely.
- `.github/workflows/deploy-prod.yml`, `deploy-dev.yml`, secrets-populate
  script — replaced by Vercel + Fly.io deploy.
- `backend/app/integrations/aws/` (cognito, s3, sqs clients)
- `backend/app/integrations/supabase/auth.py` (moves to frontend)
- `backend/app/services/{auth,org,deal,meeting,document,bot,audit,integration,transcript,embedding}_service.py`
  — replaced by direct `supabase-js` calls in the frontend
- `backend/app/api/v1/{orgs,deals,meetings,documents,transcripts,admin}.py`
  and most of `integrations.py` + `auth.py` — frontend goes direct to Supabase
- `backend/app/tasks/celery_app.py` and all `backend/app/tasks/*.py` except
  the logic we port into Inngest
- `backend/app/core/rate_limit.py`, `dependencies.py` auth block,
  `core/middleware.py` audit+request-id (Inngest + Supabase have their own
  tracing)
- `backend/alembic/` — replaced by `supabase/migrations/*.sql`
- `backend/Dockerfile.worker`, `docker-compose.yml`
- Frontend: `src/lib/auth.ts` (custom Supabase wrapper), Cognito callback
  page, demo-login SEED_USERS, `src/stores/auth-store.ts` (replaced by
  Supabase hook)

---

## Phased execution

Each phase is one PR, independently revertable.

### Phase 0 — Accounts & env (you do this)
- Sign up / create projects: Supabase, Vercel, Fly.io, Inngest, Fireworks.
- Create Supabase Auth providers: Google, Microsoft.
- Drop credentials into a single `.env.example` (schema below) which I'll
  commit; you copy to `.env` locally.

### Phase 1 — Supabase schema + RLS
- Port current SQLAlchemy models → `supabase/migrations/0001_initial.sql`.
  Add pgvector extension. Tables are the same 16 we have today plus:
  - `transcript_segments.is_partial boolean not null default false` — flag
    for live-streamed partials (Phase 5.5 uses this)
  - `transcript_segments.recall_segment_id text unique` — idempotency key
    for Recall's streaming event retries
  - `meeting_bot_sessions.live_transcript_channel text` — denormalized
    Supabase Realtime channel name so the frontend knows where to subscribe
- Rewrite RLS. Replace `SET LOCAL app.current_org_id` with policies like
  `USING (org_id IN (SELECT org_id FROM org_memberships WHERE user_id = auth.uid()))`.
- Add a `user_org_memberships` SECURITY DEFINER function that returns the
  active org for the JWT user — used by both RLS policies and the FastAPI
  worker for org-scoped queries.
- Enable Supabase Realtime on `transcript_segments` (postgres changes).
  RLS policies automatically apply to the Realtime stream — users only see
  segments for meetings in their org.
- Seed one test user + org for local dev via a `supabase/seed.sql`.

### Phase 2 — Supabase Auth on the frontend
- `npm i @supabase/supabase-js @supabase/ssr`
- Replace [frontend/src/lib/auth.ts](frontend/src/lib/auth.ts) with a
  Supabase SSR client factory.
- Replace the login page SSO button + Cognito callback with Supabase Auth UI
  or a minimal OAuth-redirect implementation.
- Replace [frontend/src/stores/auth-store.ts](frontend/src/stores/auth-store.ts)
  with a `useSupabaseSession` hook wrapping `supabase.auth.getSession()` +
  `onAuthStateChange`.
- Delete `/auth/cognito/*` endpoints + callback page + seed-user login.
- `X-Org-ID` header is gone — server reads org membership from the user's
  JWT + `user_org_memberships`.

### Phase 3 — Frontend direct-to-Supabase CRUD
- Rewrite each React Query hook in [frontend/src/hooks/](frontend/src/hooks/)
  to call `supabase.from('table').select()` / `.insert()` / etc. — except
  `use-qa`, `use-deliverables`, `use-analysis` which still hit the worker.
- Delete `apiClient` usage for CRUD. Keep a trimmed `apiClient` only for
  worker endpoints (LLM, uploads, webhooks).
- Files: `use-deals.ts`, `use-meetings.ts`, `use-documents.ts`,
  `use-transcripts.ts`, `use-org.ts`, `use-bot-sessions.ts`, `use-calendar.ts`.

### Phase 4 — Slim FastAPI worker
- Collapse [backend/app/api/v1/router.py](backend/app/api/v1/router.py) to
  only: `/health`, `/qa`, `/analyses`, `/deliverables`, `/meetings/upload-ticket`
  (returns Supabase Storage signed upload URL), `/webhooks/{zoom,teams,slack}`,
  `/integrations/{platform}/{connect,callback,disconnect}`.
- Replace [backend/app/dependencies.py](backend/app/dependencies.py)
  `get_current_user` with a Supabase JWT verifier (RS256, Supabase-issued
  JWKS at `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`).
- Replace [backend/app/dependencies.py](backend/app/dependencies.py)
  `get_db_with_rls` with a postgrest/async-pg session that sets
  `request.jwt.claims` and lets Supabase RLS do the rest.
- Add a `Dockerfile` for Fly.io + a `fly.toml` at `backend/`. Single process,
  no worker container.

### Phase 5 — Inngest pipeline
- `npm i inngest` in a small Next.js API route at
  `frontend/src/app/api/inngest/route.ts` that serves the Inngest functions.
  Alternatively run Inngest as a sibling service on Fly — pick Next.js for
  simpler env sharing.
- Port these Celery chains to Inngest functions:
  - `meeting/uploaded` → validate → transcribe (Deepgram) → diarize →
    parallel(embed, analyze) → notify. Mirrors today's
    [backend/app/tasks/pipelines.py](backend/app/tasks/pipelines.py).
  - `zoom.recording.completed` → download → enqueue `meeting/uploaded`
  - `teams.call_record_created` → fetch via Graph → enqueue
  - `cron` every 15 min → `sync_outlook_calendars` (fan-out per credential)
  - `bot.scheduled` → `start_bot_session` → `stop_bot_session` →
    `process_bot_recording`
- Inngest functions invoke the FastAPI worker via HTTP for the heavy
  Python-side work (prompt rendering, Deepgram SDK call). Keeps Python
  logic in Python; Inngest is purely orchestration.

### Phase 5.5 — Live transcription
- Configure Recall bot creation to request real-time transcription:
  `recording_config.transcript.provider = 'deepgram'`, send events to
  `https://<worker>/webhooks/recall/transcript`. Recall streams partial +
  finalized segments via signed webhooks.
- **Worker endpoint** at `backend/app/api/v1/recall_webhooks.py`:
  verifies Recall's signature, upserts into `transcript_segments` keyed on
  `recall_segment_id`, using the Supabase service-role key (bypasses RLS —
  the worker is trusted server-side). Partials carry `is_partial=true`;
  the finalized segment with the same `recall_segment_id` replaces the
  partial via UPSERT. Each write generates a Postgres NOTIFY that Supabase
  Realtime broadcasts to subscribed clients.
- **Frontend live panel** at
  `frontend/src/app/(app)/deals/[dealId]/meetings/[meetingId]/live/page.tsx`
  (also exposed as a "Live" tab on the existing meeting detail page — only
  visible while `meeting_bot_sessions.status = 'recording'`):
  - subscribes via `supabase.channel('transcripts:meeting_id=<id>').on(
    'postgres_changes', { event: '*', schema: 'public',
    table: 'transcript_segments', filter: 'meeting_id=eq.<id>' }, ...)`
  - renders a scrolling list; partials styled italic/gray, finalized
    segments replace them in place by `recall_segment_id`
  - auto-scrolls to bottom unless the user has scrolled up
  - shows speaker labels (Recall provides diarization in the streaming
    payload)
- **Lifecycle handoff:** when the bot emits `meeting_ended`, the worker
  flips `meeting_bot_sessions.status` to `completed`, which unmounts the
  Live tab and unlocks the normal post-meeting pipeline (Inngest:
  transcribe → diarize → embed + analyze → notify). The post-pipeline
  writes the final, cleaned transcript to `transcripts.raw_response` and
  may replace the streamed segments with the finalized Deepgram output
  (gated by a flag — low priority, streamed output is usually fine).
- **Backpressure / reliability:**
  - Worker debounces NOTIFY storms by coalescing rapid partials for the
    same `recall_segment_id` server-side before writing (50ms window).
  - If the worker is down, Recall retries with exponential backoff; no
    data loss on finalized segments (those are the durable ones).
  - Live panel gracefully handles disconnection — Supabase Realtime
    auto-reconnects.
- **Playback latency target:** <2s end-to-end (speaker utterance →
  text on screen). Recall+Deepgram streaming alone is ~800ms.

### Phase 6 — Fireworks LLM provider
- New `backend/app/llm/fireworks_provider.py` implementing the same
  interface as `gemini_provider.py` — it's OpenAI-compatible
  (`https://api.fireworks.ai/inference/v1`), so ~60 lines.
- Add a `TASK_MODEL_MAP` in
  [backend/app/llm/router.py](backend/app/llm/router.py):
  ```
  summarization:  fireworks/accounts/fireworks/models/llama-v3p3-70b-instruct
  action_items:   fireworks/accounts/fireworks/models/llama-v3p3-70b-instruct
  qa_rag:         fireworks/accounts/fireworks/models/deepseek-v3
  ic_memo:        fireworks/accounts/fireworks/models/deepseek-v3
  embedding:      fireworks/nomic-ai/nomic-embed-text-v1.5
  ```
  Each row overridable by env: `LLM_MODEL_FOR_IC_MEMO=...`.
- `PREMIUM_LLM_ENABLED=false` — attempting to route to a Claude model while
  this is unset raises at call time (never silently uses Claude).
- Migrate [backend/app/services/embedding_service.py](backend/app/services/embedding_service.py)
  from Gemini → Fireworks nomic (same 1536? no — 768 dims; update the
  pgvector column type in Phase 1 migration).

### Phase 7 — Delete AWS + Terraform + Celery
- Remove `infrastructure/terraform/` entirely.
- Remove `backend/alembic/`, `backend/app/integrations/aws/`,
  `backend/app/tasks/` (except what was ported).
- Remove `.github/workflows/deploy-{prod,dev}.yml`. Replace with a single
  `fly-deploy.yml` for the worker.
- Vercel auto-deploys the frontend on push; no workflow needed.

### Phase 8 — Deploy + cutover
- `fly launch` → worker live at `cognisuite-worker.fly.dev`.
- Vercel project → points `NEXT_PUBLIC_API_URL` at the Fly URL.
- Supabase Auth: set redirect URLs to Vercel preview + prod domains.
- Inngest: sync endpoint URL in Inngest dashboard.
- Smoke test the golden path (see Verification below). Cut DNS over.

---

## `.env.example` (complete, after migration)

```bash
# --- Supabase ---
SUPABASE_URL=                        # https://xxxx.supabase.co
SUPABASE_ANON_KEY=                   # public key used by frontend
SUPABASE_SERVICE_ROLE_KEY=           # server-only, bypasses RLS
SUPABASE_JWT_JWKS_URL=               # ${SUPABASE_URL}/auth/v1/.well-known/jwks.json

# Frontend also needs the public values (NEXT_PUBLIC_ prefix)
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_API_URL=                 # FastAPI worker (Fly) — e.g. https://cognisuite-worker.fly.dev

# --- LLM: Fireworks (default) ---
FIREWORKS_API_KEY=
# Per-task overrides (optional — sensible defaults in llm/router.py)
LLM_MODEL_FOR_SUMMARIZATION=
LLM_MODEL_FOR_ACTION_ITEMS=
LLM_MODEL_FOR_QA_RAG=
LLM_MODEL_FOR_IC_MEMO=
LLM_MODEL_FOR_EMBEDDING=

# --- LLM: Claude (opt-in only) ---
PREMIUM_LLM_ENABLED=false            # must be "true" to route any task to Claude
ANTHROPIC_API_KEY=                   # only needed if PREMIUM_LLM_ENABLED=true

# --- Transcription & bots ---
DEEPGRAM_API_KEY=
RECALL_API_KEY=

# --- Async jobs ---
INNGEST_EVENT_KEY=
INNGEST_SIGNING_KEY=

# --- Integrations (OAuth clients for Zoom/Teams/Slack/Outlook) ---
ZOOM_CLIENT_ID=
ZOOM_CLIENT_SECRET=
ZOOM_WEBHOOK_SECRET_TOKEN=
TEAMS_CLIENT_ID=
TEAMS_CLIENT_SECRET=
TEAMS_WEBHOOK_SECRET=
SLACK_CLIENT_ID=
SLACK_CLIENT_SECRET=
SLACK_SIGNING_SECRET=
OUTLOOK_CLIENT_ID=
OUTLOOK_CLIENT_SECRET=

# --- Worker crypto ---
TOKEN_ENCRYPTION_KEY=                # Fernet key for stored OAuth refresh tokens

# --- Observability (optional) ---
SENTRY_DSN=
NEXT_PUBLIC_SENTRY_DSN=

# --- Runtime ---
APP_ENV=development                  # development | staging | production
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:3000,https://cognisuite.vercel.app
```

---

## Critical files to modify

Backend:
- [backend/app/core/config.py](backend/app/core/config.py) — trim to above env
- [backend/app/dependencies.py](backend/app/dependencies.py) — Supabase JWT verify
- [backend/app/api/v1/router.py](backend/app/api/v1/router.py) — trim endpoints
- [backend/app/llm/router.py](backend/app/llm/router.py) — task → model map
- **New:** `backend/app/llm/fireworks_provider.py`
- **New:** `backend/app/api/v1/recall_webhooks.py` — live transcript ingest
- **New:** `backend/fly.toml`, updated `backend/Dockerfile`

Frontend:
- [frontend/src/lib/auth.ts](frontend/src/lib/auth.ts) — Supabase SSR client
- [frontend/src/lib/api-client.ts](frontend/src/lib/api-client.ts) — trim to
  worker-only
- [frontend/src/stores/auth-store.ts](frontend/src/stores/auth-store.ts) —
  replace with Supabase session hook
- [frontend/src/app/(auth)/login/page.tsx](frontend/src/app/(auth)/login/page.tsx) —
  single SSO button, no demo seed users
- All files in [frontend/src/hooks/](frontend/src/hooks/) — direct Supabase
- **New:** `frontend/src/app/api/inngest/route.ts`
- **New:** `frontend/src/app/(app)/deals/[dealId]/meetings/[meetingId]/live/page.tsx`
  — live transcript panel (Supabase Realtime subscription)
- **New:** `frontend/src/hooks/use-live-transcript.ts` — subscription hook

Infrastructure:
- **Delete:** [infrastructure/terraform/](infrastructure/terraform/)
- **New:** `supabase/migrations/0001_initial.sql`, `supabase/seed.sql`,
  `supabase/config.toml`

---

## Verification (end-to-end)

Each item must pass before the next phase ships.

1. **Local Supabase** — `supabase start`, `supabase db reset`, schema +
   seed apply clean. `psql` confirms RLS policies exist for every table.
2. **Frontend auth** — `npm run dev`, log in with Google, see dashboard.
   `localStorage` has no `refresh_token` (Supabase uses httpOnly cookies
   via `@supabase/ssr`).
3. **Direct CRUD via RLS** — create a deal in the UI while logged in as
   user A, switch to user B (different org) → `select * from deals` returns
   zero. User A sees only their deal.
4. **FastAPI worker** — `fly deploy`, `/health` returns 200. Bearer a
   Supabase access token → `/qa` returns a cited answer.
5. **Inngest pipeline** — upload a sample `.mp3`, watch Inngest dashboard
   show `transcribe → diarize → embed + analyze → notify` all green.
   Transcript + analysis appear in the UI.
5b. **Live transcription** — schedule a bot for a test Zoom/Meet URL; open
   the Live tab on the meeting detail page; speak into the call; words
   appear within ~2s; partials visibly replace themselves with finalized
   text. When you end the meeting, the Live tab hides and the normal
   Transcript tab populates once the Inngest post-pipeline finishes.
6. **Fireworks routing** — `LOG_LEVEL=DEBUG` shows `model=accounts/fireworks/...`
   on every LLM call. `PREMIUM_LLM_ENABLED=false` + env override to Claude →
   request is rejected at router before any network call.
7. **Webhook intake** — post a fabricated Zoom `recording.completed` with
   valid HMAC → Inngest event fires → meeting row appears.
8. **Rollback drill** — revert the Phase 5 (Inngest) PR on a branch, confirm
   the worker still serves synchronous endpoints (just no async). Each
   phase is this reversible.

---

## Rollback path

Because each phase is a single PR:
- Revert any single PR and the stack still functions for everything that
  didn't depend on it.
- The highest-risk revert is Phase 1 (Supabase schema): to roll back you'd
  need to `supabase db reset` to a prior migration. Since this is a fresh
  schema (no prod data), a reset is free.
- Nothing in this plan requires a data migration, a feature flag, or a
  coordinated DNS cutover until Phase 8.

---

## Out of scope (deliberately deferred)

- SAML/enterprise SSO (only Google + Microsoft at launch)
- Frontend E2E tests (Playwright — separate PR after cutover)
- CloudFront/WAF — Vercel handles edge caching + basic DDoS
- Analytics (PostHog, etc.)
- Replacing live-streamed segments with the cleaner post-pipeline Deepgram
  output (gated behind a flag; the streamed segments are usually good
  enough)
