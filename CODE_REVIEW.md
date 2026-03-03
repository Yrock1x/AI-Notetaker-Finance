# DealWise AI - Comprehensive Code Review

**Date**: 2026-02-28
**Scope**: Full codebase (~100+ files across backend, frontend, and infrastructure)
**Methodology**: Automated multi-agent review covering correctness, readability, performance, security, and error handling

---

## Summary

The codebase demonstrates a well-structured enterprise architecture with clean separation of concerns, but has **critical security gaps** in authentication enforcement, multi-tenancy isolation, and webhook validation that must be addressed before any production deployment. The infrastructure Terraform modules have wiring errors that will prevent deployment, and the frontend has fundamental auth flow issues.

**Total Issues Found**: 148
- **High Severity**: 38
- **Medium Severity**: 78
- **Low Severity**: 32

---

## Verdict: NEEDS CHANGES

Blocking issues exist across security, correctness, and deployment readiness. The top 20 issues below are prioritized by impact.

---

## Top 20 Critical Issues (Must Fix)

### 1. [HIGH] Admin endpoints have zero authorization enforcement
**File**: `backend/app/api/v1/admin.py`
**Issue**: All admin endpoints (`list_users`, `deactivate_user`, `query_audit_logs`, `get_org_settings`, `update_org_settings`) have docstrings claiming "Requires admin role" but none actually check it. Any authenticated user can deactivate other users, read audit logs, and modify org settings.
**Fix**: Add `await verify_org_membership(db, current_user.id, org_id, min_role=OrgRole.ADMIN)` at the start of each endpoint.

### 2. [HIGH] No org membership verification on X-Org-ID header
**File**: `backend/app/dependencies.py`
**Issue**: The `get_org_id` dependency trusts the `X-Org-ID` header without verifying the user belongs to that org. Any authenticated user can set this to any org's UUID. RLS is the sole defense -- if any RLS policy has a gap, data leaks across tenants.
**Fix**: After extracting `org_id`, call `verify_org_membership(db, current_user.id, org_id)` inside `get_db_with_rls`.

### 3. [HIGH] Celery tasks bypass RLS entirely
**File**: `backend/app/tasks/analysis.py`, `embedding.py`, `transcription.py`
**Issue**: All Celery tasks use `async_session_factory()` directly without setting `SET LOCAL app.current_org_id`. All RLS policies are bypassed in background tasks. A bug in any service method called from a task could expose/modify data belonging to other organizations.
**Fix**: Create a task-specific session helper that accepts `org_id` and sets the RLS variable.

### 4. [HIGH] Webhook signature verification is broken
**File**: `backend/app/api/v1/webhooks.py`
**Issue**: (a) `zoom_webhook_secret_token`, `slack_signing_secret`, and `teams_webhook_secret` are not defined in `Settings` -- accessing them raises `AttributeError` at runtime. (b) Zoom and Slack verification challenges are processed *before* signature verification, leaking signing capability. (c) Teams silently skips verification when the setting is missing.
**Fix**: Add webhook secret settings to `config.py`. Move signature verification before challenge handling.

### 5. [HIGH] OAuth callback requires bearer auth (will always 401)
**File**: `backend/app/api/v1/integrations.py`
**Issue**: The `oauth_callback` endpoint requires `get_current_user` authentication, but OAuth callbacks from external providers are redirects that won't carry a Bearer token. Every callback will fail with 401.
**Fix**: Remove `get_current_user` dependency; validate the `state` parameter to identify the user/org.

### 6. [HIGH] OAuth state token never validated (CSRF vulnerability)
**File**: `backend/app/services/integration_service.py`
**Issue**: `initiate_oauth` generates a `state` token but never stores it. `handle_oauth_callback` receives `state` but never validates it. An attacker can craft a malicious callback URL with arbitrary state. Additionally, the authorization `code` is stored directly as the encrypted token instead of being exchanged at the token endpoint.
**Fix**: Store state in Redis/DB during `initiate_oauth`, validate in callback. Implement the actual OAuth token exchange.

### 7. [HIGH] Systematic lack of tenant scoping on entity lookups
**Files**: `analysis_service.py`, `meeting_service.py`, `document_service.py`, `bot_service.py`, `transcript_service.py`
**Issue**: `get_analysis`, `get_meeting`, `get_document`, `get_session`, and `get_transcript_by_id` all query by primary key without `org_id` filtering. While RLS provides a safety net, the service layer should enforce tenant isolation explicitly.
**Fix**: Add `org_id` as a required parameter to all single-entity lookups.

### 8. [HIGH] Prompt injection via str.format() in LLM prompts
**File**: `backend/app/llm/prompts/base.py`
**Issue**: `render()` uses Python `str.format(**kwargs)` to interpolate user-supplied content (transcripts, questions). Format string syntax like `{__class__}` in a transcript will crash or leak state. Adversarial content is injected directly into prompts with no sanitization.
**Fix**: Escape `{` and `}` in user content before `.format()`. Consider using separate message roles for user content.

### 9. [HIGH] Demo mode exploitable in production
**Files**: `backend/app/core/config.py`, `backend/app/api/v1/auth.py`
**Issue**: `demo_mode` can be enabled in production with a known default JWT secret (`"demo-secret-change-in-production"`), allowing trivial authentication bypass.
**Fix**: Add a validator that raises an error if `demo_mode=True` and `app_env=="production"` or if the JWT secret is the default.

### 10. [HIGH] Frontend auth tokens stored in localStorage (XSS risk)
**File**: `frontend/src/stores/auth-store.ts`
**Issue**: Access and refresh tokens are stored in `localStorage`, accessible to any JavaScript on the page. The refresh token is long-lived and should never sit in `localStorage`.
**Fix**: Store refresh tokens in `httpOnly` cookies. Keep access tokens in memory only.

### 11. [HIGH] No token refresh flow -- expired tokens immediately log users out
**File**: `frontend/src/lib/api-client.ts`
**Issue**: The 401 interceptor clears tokens and redirects to `/login` immediately without attempting token refresh. Every access token expiration destroys the session despite refresh tokens being available.
**Fix**: Implement a silent refresh flow on 401 before falling back to logout.

### 12. [HIGH] Terraform modules have wiring errors preventing deployment
**Files**: All `infrastructure/terraform/environments/*/main.tf`
**Issue**: `certificate_arn` and `s3_bucket_arn` are not passed to the ECS module; `auth_token` is not passed to ElastiCache. `terraform plan` will fail for all environments.
**Fix**: Wire missing module outputs/variables across all three environments.

### 13. [HIGH] Celery task dispatched before DB commit (race condition)
**File**: `backend/app/api/v1/analysis.py`
**Issue**: The Celery task is dispatched via `.delay()` before the DB transaction commits. The worker will try to find a record that hasn't been committed yet, causing intermittent `NotFound` errors.
**Fix**: Use `after_commit` hooks or explicitly `await db.commit()` before `.delay()`.

### 14. [HIGH] Middleware ordering is inverted
**File**: `backend/app/main.py`
**Issue**: FastAPI's `add_middleware` stacks in reverse order. `RequestIDMiddleware` runs last (innermost), so request IDs are not available to `RequestLoggingMiddleware` or `AuditLogMiddleware`.
**Fix**: Reverse the middleware registration order so `RequestIDMiddleware` is added last (outermost).

### 15. [HIGH] Audit logging never fires
**File**: `backend/app/core/middleware.py`
**Issue**: `AuditLogMiddleware` reads `request.state.user_id`, but nothing in the codebase ever sets it. The audit log condition always evaluates to true for the "skip" path, so no audit entries are ever recorded.
**Fix**: Set `request.state.user_id = user.id` in the `get_current_user` dependency after successful authentication.

### 16. [HIGH] Upload confirmation endpoints lack authorization
**Files**: `backend/app/api/v1/documents.py`, `backend/app/api/v1/meetings.py`
**Issue**: `confirm_document_upload` and `confirm_meeting_upload` perform no deal access checks. Any authenticated user can confirm uploads and trigger processing pipelines for deals they don't belong to.
**Fix**: Add deal access verification before confirming uploads.

### 17. [HIGH] Embedding reindex can cause partial data loss
**File**: `backend/app/tasks/embedding.py`
**Issue**: `reindex_deal` deletes all existing embeddings first, commits, then re-generates. If re-embedding fails partway through, the deal is left with partially deleted embeddings.
**Fix**: Use a version-swap strategy or wrap deletion and re-creation in a single transaction.

### 18. [HIGH] Financial figure validation produces false positives
**File**: `backend/app/llm/guardrails.py`
**Issue**: `validate_financial_figures` normalizes the entire source text before checking if a figure is present. This creates false positives: `"$501"` matches in normalized `"$50millionand$10billion"` because `501` appears as a substring.
**Fix**: Extract figures from source text using the same regex and compare figure-to-figure.

### 19. [HIGH] WebSocket client sends no authentication
**File**: `frontend/src/lib/websocket.ts`
**Issue**: The WebSocket `connect()` method creates a connection with no authentication token. Anyone who knows the URL could connect and receive real-time events.
**Fix**: Send the access token as a query parameter or in an initial auth message.

### 20. [HIGH] No auth guard on protected pages
**File**: `frontend/src/app/(app)/layout.tsx`
**Issue**: The app layout has no authentication guard. Unauthenticated users can visit any protected page. The full UI renders before API 401s eventually trigger a redirect.
**Fix**: Add a client-side auth guard or Next.js middleware that redirects to `/login` before rendering.

---

## Additional Issues by Area

### Backend Core (config, database, security, middleware)

| # | Sev | File | Issue |
|---|-----|------|-------|
| 21 | MED | `dependencies.py` | JWT error details leak to client (`f"Invalid demo token: {e}"`) -- aids token forgery |
| 22 | MED | `database.py` | `SET LOCAL` RLS variable could be lost if session triggers implicit commit |
| 23 | MED | `database.py` | `get_db()` duplicated in both `database.py` and `dependencies.py` |
| 24 | MED | `exceptions.py` | Custom `ValidationError` shadows Pydantic's `ValidationError` |
| 25 | MED | `exceptions.py` | Global `Exception` handler may catch `HTTPException`, converting 4xx to 500s |
| 26 | MED | `events.py` | `EventBus.publish` awaits handlers sequentially; exception in one skips the rest |
| 27 | MED | `middleware.py` | `AuditLogMiddleware` uses separate DB session -- logs actions that rolled back |
| 28 | MED | `middleware.py` | `OrgContextMiddleware` silently swallows malformed UUID, giving misleading error |
| 29 | MED | `security.py` | 403 on non-member reveals resource existence; should be 404 |
| 30 | MED | `main.py` | Database engine connection pool never closed on shutdown |
| 31 | LOW | `middleware.py` | `RequestIDMiddleware` leaks contextvars if `call_next` raises |
| 32 | LOW | `logging.py` | Return type annotation `BoundLogger` is wrong (should be `BoundLoggerLazyProxy`) |

### Backend Models & Schemas

| # | Sev | File | Issue |
|---|-----|------|-------|
| 33 | HIGH | `embedding.py` | `Vector(EMBEDDING_DIMENSIONS) if Vector else None` silently breaks without pgvector |
| 34 | HIGH | `base.py` | `OrgScopedMixin.org_id` has no FK; child re-declarations silently override it |
| 35 | HIGH | All models | Pervasive lack of enum validation -- roles, statuses, types are unconstrained strings |
| 36 | HIGH | `user.py` | `lazy="selectin"` on memberships fires extra queries on every user load |
| 37 | HIGH | `integration_credential.py` | `*_encrypted` columns are plain Text with no encryption mechanism |
| 38 | MED | `embedding.py` | Missing HNSW/IVFFlat vector index for similarity search (brute-force scan) |
| 39 | MED | `embedding.py` | Missing index on `(source_type, source_id)` |
| 40 | MED | `org_membership.py` | Missing individual index on `user_id` |
| 41 | MED | `deal_membership.py` | Missing individual index on `user_id` |
| 42 | MED | `transcript_segment.py` | Missing composite index on `(transcript_id, segment_index)` |
| 43 | MED | `schemas/common.py` | `CursorParams.limit` has no upper bound -- clients can request millions of rows |
| 44 | MED | `schemas/organization.py` | `OrgUpdate.settings` accepts arbitrary dict with no size constraint |
| 45 | MED | `schemas/organization.py` | `OrgMemberCreate.role` is free-form string, not validated against OrgRole |
| 46 | MED | `schemas/deal.py` | `DealCreate.deal_type`, `DealMemberCreate.role` are unvalidated strings |
| 47 | MED | `schemas/transcript.py` | `TranscriptResponse.full_text` returns multi-MB text in every response |
| 48 | MED | `schemas/meeting.py` | `MeetingCreate.source` is unvalidated string |

### Backend API Routes

| # | Sev | File | Issue |
|---|-----|------|-------|
| 49 | HIGH | `deals.py` | Pagination params `cursor`/`limit` accepted but silently ignored |
| 50 | HIGH | `meetings.py` | `list_meetings` has no deal access check -- any org member can list any deal's meetings |
| 51 | MED | `admin.py` | `list_users` cursor parameter accepted but never used in query |
| 52 | MED | `admin.py` | `deactivate_user` doesn't prevent self-deactivation |
| 53 | MED | `analysis.py` | `get_analysis` doesn't verify analysis belongs to the specified meeting |
| 54 | MED | `documents.py` | `get_document`/`download_document` don't verify document belongs to deal |
| 55 | MED | `meetings.py` | `get_meeting`/`update_meeting`/`delete_meeting` don't verify meeting belongs to deal |
| 56 | MED | `orgs.py` | No limit on org creation -- user can create thousands |
| 57 | MED | `orgs.py` | `remove_org_member` allows removing last owner |
| 58 | MED | `health.py` | Readiness check leaks raw DB error messages |
| 59 | MED | `integrations.py` | `cancel_bot_session` has no ownership check |
| 60 | MED | `webhooks.py` | Slack commands echo unrecognized subcommand -- reflected content injection |

### Backend Services

| # | Sev | File | Issue |
|---|-----|------|-------|
| 61 | HIGH | `auth_service.py` | New user created without org assignment -- floats outside tenant boundaries |
| 62 | MED | `analysis_service.py` | `_parse_llm_output` marks analysis "completed" even when JSON parse fails |
| 63 | MED | `analysis_service.py` | Race condition on `_next_version` -- no unique constraint protection |
| 64 | MED | `audit_service.py` | Cursor pagination unstable on `created_at` (duplicates skipped) |
| 65 | MED | `auth_service.py` | Race condition on `get_or_create_user` -- concurrent first logins crash |
| 66 | MED | `bot_service.py` | No state machine validation on status transitions |
| 67 | MED | `deal_service.py` | `update_deal` can't set fields to `None` (uses `is not None` check) |
| 68 | MED | `deal_service.py` | Search uses raw `%` wildcards with user input (LIKE injection) |
| 69 | MED | `embedding_service.py` | `store_embeddings` adds rows one at a time (should bulk insert) |
| 70 | MED | `embedding_service.py` | No retry logic around external embedding API calls |
| 71 | MED | `integration_service.py` | `_get_client_id` returns empty string for unconfigured platforms |
| 72 | MED | `meeting_service.py` | `delete_meeting` doesn't cascade-delete S3 artifacts |
| 73 | MED | `org_service.py` | `create_org` slug uniqueness check is racy |
| 74 | MED | `qa_service.py` | Grounding check exception silently swallowed |
| 75 | MED | `qa_service.py` | User question passed unsanitized to LLM prompt |
| 76 | MED | `transcript_service.py` | Search vulnerable to SQL LIKE wildcard injection |
| 77 | MED | `transcript_service.py` | `store_segments` inserts one at a time (should bulk insert) |
| 78 | MED | Cross-cutting | No DB error handling at service layer (IntegrityError, deadlocks) |

### Backend LLM Module

| # | Sev | File | Issue |
|---|-----|------|-------|
| 79 | HIGH | `claude_provider.py`, `openai_provider.py` | API keys stored as public instance attributes |
| 80 | MED | `router.py` | No retry/fallback logic for rate limits or transient failures |
| 81 | MED | `chunking.py` | Token estimation underestimates for financial text (uses `split() * 4/3`) |
| 82 | MED | `chunking.py` | `char_start` uses `text.find()` -- returns first occurrence for duplicates |
| 83 | MED | `guardrails.py` | `check_and_flag` runs validations twice (redundant with `calculate_grounding_score`) |
| 84 | MED | `prompts/base.py` | `output_schema` defined but never included in prompt or API call |
| 85 | MED | `prompts/summarization.py` | Wrong attribute name in loader (`SUMMARIZATION` vs `MEETING_SUMMARIZATION`) -- runtime crash |
| 86 | MED | `prompts/summarization.py` | Missing required template variables `meeting_type` and `deal_name` |
| 87 | MED | Cross-cutting | No LLM response caching -- duplicate analyses make full API calls |

### Backend Tasks & Integrations

| # | Sev | File | Issue |
|---|-----|------|-------|
| 88 | HIGH | `base.py` | `autoretry_for=(Exception,)` retries non-transient errors (ValueError, KeyError) |
| 89 | HIGH | `embedding.py` | `reindex_deal` instantiates new provider per meeting/document (should reuse) |
| 90 | HIGH | `cognito.py` | JWKS cache has race condition -- concurrent refresh under asyncio |
| 91 | MED | `analysis.py` | Empty API key silently passed to provider -- confusing 401 instead of config error |
| 92 | MED | `pipelines.py` | Chord failure sends no notification -- user never knows processing failed |
| 93 | MED | `meeting_bot.py` | `NotImplementedError` triggers retries due to `autoretry_for=(Exception,)` |
| 94 | MED | `s3.py` | `generate_presigned_upload_url` allows any content type (no validation) |
| 95 | MED | `file_processing.py` | `validate_file_type` relies on spoofable `Content-Type` header only |
| 96 | MED | `audio.py` | Output path has no directory validation (path traversal possible) |
| 97 | MED | `cognito.py` | `verify_token` doesn't validate `client_id` for access tokens |
| 98 | MED | `cognito.py` | New `httpx.AsyncClient` created per call (no connection reuse) |
| 99 | MED | `slack/notifications.py` | Bot token stored as plain instance attribute |
| 100 | MED | Cross-cutting | `_run_async()` copy-pasted in 3 files (should be shared) |
| 101 | MED | Cross-cutting | No task sets meeting status to "failed" on permanent failure |

### Frontend Pages & Components

| # | Sev | File | Issue |
|---|-----|------|-------|
| 102 | HIGH | `page.tsx` (root) | Checks `localStorage "auth_tokens"` but store writes `"access_token"` -- key mismatch |
| 103 | HIGH | `deals/[dealId]/team/page.tsx` | Remove member has no confirmation dialog -- destructive one-click action |
| 104 | MED | `callback/page.tsx` | OAuth callback runs twice in React Strict Mode (auth code is single-use) |
| 105 | MED | `settings/page.tsx` | Theme selector updates state but nothing applies the theme to the DOM |
| 106 | MED | `deals/page.tsx` | Search triggers API request on every keystroke (no debounce) |
| 107 | MED | `deals/[dealId]/settings/page.tsx` | `mutateAsync` calls have no try/catch -- errors silently lost |
| 108 | MED | `admin/settings/page.tsx` | Settings displayed as read-only JSON with non-functional save button |
| 109 | MED | `admin/audit/page.tsx` | Uses raw fetch instead of React Query; errors silently swallowed |
| 110 | MED | `integrations/page.tsx` | Connect/disconnect have empty catch blocks |
| 111 | MED | `integrations/page.tsx` | `authorization_url` redirected to without URL validation |
| 112 | MED | `meetings/upload-dialog.tsx` | File type not validated on drag-and-drop (bypasses `accept` attribute) |
| 113 | MED | `meetings/upload-dialog.tsx` | S3 upload `fetch` response not checked for errors |
| 114 | MED | `documents/document-upload.tsx` | Same S3 upload response issue |
| 115 | MED | `transcripts/transcript-viewer.tsx` | Speaker color mutation during render (React anti-pattern) |
| 116 | MED | `qa/qa-chat.tsx` | No auto-scroll to bottom when new messages arrive |
| 117 | MED | `shared/error-boundary.tsx` | `ErrorBoundary` defined but never used anywhere |

### Frontend Stores, Lib & Types

| # | Sev | File | Issue |
|---|-----|------|-------|
| 118 | MED | `auth-store.ts` | No session hydration on page reload -- `isLoading` stays `true` forever |
| 119 | MED | `auth-store.ts` | `logout()` doesn't clear React Query cache or disconnect WebSocket |
| 120 | MED | `org-store.ts` | `setCurrentOrg` doesn't update localStorage `org_id` -- API sends stale header |
| 121 | MED | `api-client.ts` | 401 handler clears localStorage but not Zustand state (split-brain) |
| 122 | MED | `api-client.ts` | Network errors (timeout, DNS) silently rejected with no user feedback |
| 123 | MED | `websocket.ts` | `shouldReconnect` never reset after disconnect/reconnect cycle |
| 124 | MED | `constants.ts` | `MeetingStatus` enum missing pipeline states (transcribing, analyzing, ready) |
| 125 | MED | `constants.ts` | `DealRole` enum has 3 values but CLAUDE.md specifies 4 (lead > admin > analyst > viewer) |
| 126 | MED | `models.ts` | `Meeting.source` and `Meeting.status` typed as `string` instead of enums |
| 127 | MED | `api.ts` | `DealFilters` uses offset pagination but `PaginatedResponse` uses cursor pagination |
| 128 | MED | `hooks/use-auth.ts` | Seven separate `useAuthStore` subscriptions cause excessive re-renders |
| 129 | LOW | `auth.ts` | Token cleanup duplicated in 3 files (auth.ts, auth-store.ts, api-client.ts) |
| 130 | LOW | `utils.ts` | `formatDuration` doesn't floor fractional seconds |
| 131 | LOW | `ui-store.ts` | Theme preference not persisted to localStorage |

### Infrastructure

| # | Sev | File | Issue |
|---|-----|------|-------|
| 132 | HIGH | `modules/ecs/main.tf` | Worker Celery app path is `dealwise.celery` but code uses `app.tasks.celery_app` |
| 133 | HIGH | `modules/ecs/main.tf` | No auto-scaling for ECS services |
| 134 | HIGH | `Dockerfile` | `COPY . .` before `pip install` breaks Docker layer caching |
| 135 | HIGH | `Dockerfile.worker` | Editable install without source code present -- build will fail |
| 136 | MED | `modules/networking/` | Single NAT gateway -- AZ failure kills private subnet connectivity |
| 137 | MED | `modules/ecs/main.tf` | No ALB deletion protection for production |
| 138 | MED | `modules/ecs/main.tf` | API and worker share same CPU/memory despite different workloads |
| 139 | MED | `modules/cognito/main.tf` | MFA is `OPTIONAL` for prod (should be `ON` for financial platform) |
| 140 | MED | `modules/sqs/main.tf` | No encryption on queues containing sensitive meeting data |
| 141 | MED | `modules/s3/main.tf` | No TLS-only bucket policy |
| 142 | MED | `modules/monitoring/main.tf` | SNS alarm topic has no subscriptions -- alarms go nowhere |
| 143 | MED | `modules/monitoring/main.tf` | ALB 5xx alarm has no dimensions -- monitors all ALBs in region |
| 144 | MED | `modules/secrets/main.tf` | Creates `assemblyai-api-key` but project uses Deepgram |
| 145 | MED | `Dockerfile` | Container runs as root (no USER directive) |
| 146 | MED | `docker-compose.yml` | Flower dashboard exposed with no authentication |
| 147 | MED | `ci.yml` | Backend tests run without PostgreSQL/Redis services |
| 148 | MED | `alembic.ini` | Database credentials hardcoded in version-controlled file |

---

## Recommended Fix Priority

### Phase 1: Security (Week 1)
1. Admin authorization enforcement (#1)
2. Org membership verification on X-Org-ID (#2)
3. Celery task RLS context (#3)
4. Webhook secret settings and signature verification (#4)
5. OAuth callback auth removal and state validation (#5, #6)
6. Tenant scoping on entity lookups (#7)
7. Prompt injection protection (#8)
8. Demo mode production guard (#9)
9. Upload confirmation authorization (#16)
10. Deal access checks on meetings listing (#50)

### Phase 2: Correctness (Week 2)
1. Middleware ordering fix (#14)
2. Audit logging activation (#15)
3. Celery task before commit race condition (#13)
4. Terraform module wiring (#12)
5. Docker build fixes (#134, #135)
6. ECS worker Celery path fix (#132)
7. Auth store hydration and token refresh (#11, #118)
8. Root page token key mismatch (#102)
9. Summarization prompt loader crash (#85, #86)
10. Enum validation across models/schemas (#35)

### Phase 3: Reliability & Performance (Week 3)
1. ECS auto-scaling (#133)
2. Vector index for embeddings (#38)
3. Lazy loading strategy for relationships (#36)
4. Bulk insert for segments/embeddings (#69, #77)
5. LLM retry logic (#80)
6. Pagination implementation (#49)
7. Error boundaries and error handling (#117, #107, #108)
8. Monitoring alarm dimensions and subscriptions (#142, #143)
9. NAT gateway redundancy (#136)
10. Frontend debouncing and performance (#106, #128)
