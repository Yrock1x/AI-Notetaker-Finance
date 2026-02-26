# DealWise AI — Full Codebase Review

## Summary

The codebase is architecturally well-designed with strong domain modeling, a clean service layer, and comprehensive feature coverage across ~272 files. However, it has **critical security gaps** that must be fixed before any production deployment — particularly around authorization enforcement, webhook verification, encryption, and infrastructure hardening. The code reads as a feature-complete prototype that needs a dedicated security pass.

---

## Issues

### CRITICAL (Must fix before production)

- **[severity: high] Security — RLS policies missing WITH CHECK clause.** The Alembic migration (`001_initial_schema.py`) creates Row-Level Security policies with only a `USING` clause (read filtering) but no `WITH CHECK` clause. This means users can INSERT/UPDATE rows into other organizations' data. Fix: add `WITH CHECK (org_id = current_setting('app.current_org_id')::uuid)` to all RLS policies.

- **[severity: high] Security — Missing authorization on organization endpoints.** All endpoints in `api/v1/orgs.py` (get org, update org, list/add/update/remove members) perform no role-based access checks. Any authenticated user can enumerate orgs, add members, and escalate roles. Fix: add `verify_org_membership()` with appropriate `min_role` to each endpoint.

- **[severity: high] Security — Webhook signature verification not implemented.** Zoom webhook handler (`integrations/zoom/webhooks.py`) has `verify_signature()` as a `NotImplementedError` stub. The API webhook endpoints (`api/v1/webhooks.py`) for Zoom, Teams, and Slack process events without HMAC signature verification. Attackers can forge webhook events to trigger Celery pipelines. Fix: implement HMAC-SHA256 verification for all webhook sources.

- **[severity: high] Security — Missing deal-level access checks in Transcript and Document services.** `TranscriptService.get_transcript()`, `get_segments()`, `search_transcript()`, and `DocumentService.get_document()`, `generate_download_url()`, `delete_document()` perform no authorization checks. Any authenticated user can access any transcript/document by ID. Fix: add user/org/deal membership verification to all read/write methods.

- **[severity: high] Security — ALB configured with HTTP only, no HTTPS.** The ECS Terraform module (`modules/ecs/main.tf`) creates an ALB listener on port 80 (HTTP) with no HTTPS listener or redirect. All API traffic including JWT tokens and deal data transmits in plaintext. Fix: add ACM certificate, HTTPS listener on 443, and HTTP→HTTPS redirect.

- **[severity: high] Security — ElastiCache Redis deployed without encryption or AUTH.** Redis cluster (`modules/elasticache/main.tf`) has no transit encryption, at-rest encryption, or auth token. Celery task payloads containing transcript data are unprotected. Fix: enable `transit_encryption_enabled`, `at_rest_encryption_enabled`, and set `auth_token`.

- **[severity: high] Security — Token encryption is stubbed out.** `IntegrationService._encrypt_token()` uses SHA256 hashing instead of encryption (cannot be reversed to use tokens). The `token_encryption_key` config defaults to empty string with no production validation. Fix: implement Fernet encryption and add production validation for the key.

- **[severity: high] Security — Mock authentication shipped without environment guard.** `frontend/src/app/(auth)/login/page.tsx` contains hardcoded mock tokens (`dev-token`, `dev-refresh`) with no environment check. If deployed to production, anyone can authenticate. Fix: guard mock login behind `process.env.NODE_ENV === 'development'`.

- **[severity: high] Security — Command injection in audio processing.** `utils/audio.py` passes user-controlled file paths directly to `ffmpeg` subprocess without validation or escaping. Fix: validate paths against allowed directories, use `pathlib`, and sanitize with `shlex.quote()`.

- **[severity: high] Security — Missing ECS task role IAM policies.** The ECS task role (`modules/ecs/main.tf`) has no attached policies. Tasks cannot access S3, Secrets Manager, or other AWS services, causing production failures. Fix: attach policies for S3, Secrets Manager, KMS, and CloudWatch Logs.

### HIGH (Fix before production or early deployment)

- **[severity: high] Security — Missing org membership verification for deal creation.** `api/v1/deals.py` creates deals using `org_id` from header without verifying the user belongs to that org. Users can create deals in arbitrary organizations. Fix: add org membership check in the create deal endpoint.

- **[severity: high] Security — File upload content-type not validated.** `api/v1/documents.py` and `api/v1/meetings.py` accept arbitrary MIME types and filenames without whitelisting. Malicious files can bypass downstream processing. Fix: whitelist allowed content types and validate file extensions.

- **[severity: high] Security — Presigned S3 URLs logged in plaintext.** `integrations/deepgram/client.py` logs the full `audio_url` parameter which may contain presigned S3 URLs with temporary credentials. Fix: sanitize URLs before logging, log only bucket/key.

- **[severity: high] Security — Prompt injection in LLM templates.** `llm/prompts/summarization.py` (and other prompt templates) interpolate transcript text directly into prompts without any injection boundaries. Malicious transcript content can override system instructions. Fix: wrap user content in explicit boundary markers (e.g., `<user_transcript>` tags) and instruct the model to treat content within as data only.

- **[severity: high] Correctness — Model/migration schema mismatches.** Three conflicts: (1) `Deal.created_by` and `Meeting.created_by` are `nullable=False` in models but `SET NULL` on delete in migration; (2) `Embedding.embedding` is `nullable=True` in model but `nullable=False` in migration; (3) `Analysis.error_message` exists in model but not in migration. Fix: align model definitions with migration schema.

- **[severity: high] Correctness — TOCTOU race condition on last-lead/owner removal.** `DealService.remove_member()` and `OrgService.remove_member()` check lead/owner count then delete in separate operations. Concurrent requests can both pass the check. Fix: use database-level constraints or `SELECT ... FOR UPDATE` locking.

- **[severity: high] Error Handling — Generic exception handler suppresses all errors.** `core/exceptions.py` catches all `Exception` types and returns a generic 500 without logging the actual error. Fix: add `logger.exception()` before returning the response.

- **[severity: high] Security — Auth tokens stored in localStorage.** Frontend stores JWT tokens in localStorage (`auth-store.ts`, `api-client.ts`), which is accessible via XSS. Fix: use httpOnly cookies or implement a BFF (Backend-for-Frontend) pattern for token management.

### MEDIUM

- **[severity: medium] Security — CORS allows all headers with credentials.** `main.py` configures `allow_headers=["*"]` combined with `allow_credentials=True`. Fix: restrict to explicitly needed headers (`Content-Type`, `Authorization`, `X-Org-ID`).

- **[severity: medium] Security — X-Forwarded-For header spoofing.** `core/middleware.py` trusts `X-Forwarded-For` without verifying the request came from a trusted proxy. Audit logs can record false IPs. Fix: only trust the header from configured trusted proxy IPs.

- **[severity: medium] Security — OAuth state token not validated.** `IntegrationService.initiate_oauth()` generates a state token but `handle_oauth_callback()` never validates it, breaking CSRF protection. Fix: store state in Redis with TTL and validate on callback.

- **[severity: medium] Security — SQS queues without KMS encryption.** Processing queue payloads stored unencrypted at rest. Fix: add `sqs_managed_sse_enabled = true` or use KMS.

- **[severity: medium] Security — RDS without SSL enforcement.** Database connections can be made without TLS. Fix: set `sslmode=require` in connection strings and enforce in RDS parameter group.

- **[severity: medium] Security — Health check endpoint leaks error details.** `api/v1/health.py` returns raw exception messages in readiness check, potentially exposing connection strings. Fix: return only status without error details.

- **[severity: medium] Correctness — RLS UUID casting can throw on NULL.** If `app.current_org_id` is not set, `::uuid` cast fails with an exception instead of safely returning no rows. Fix: use `COALESCE(current_setting('app.current_org_id', true), '00000000-...')::uuid`.

- **[severity: medium] Correctness — Duplicate `get_db()` function.** Defined identically in both `core/database.py` and `dependencies.py`. Fix: remove the duplicate, import from a single location.

- **[severity: medium] Correctness — Unvalidated Deepgram API response structure.** `deepgram/processor.py` assumes specific JSON structure with no validation. API changes could cause silent data loss. Fix: add response schema validation.

- **[severity: medium] Performance — Missing composite indexes on membership tables.** `org_membership(user_id, org_id)` and `deal_membership(user_id, deal_id)` have no composite indexes despite being queried on every request. Fix: add indexes in migration.

- **[severity: medium] Performance — Deal list queries without indexes on filter columns.** `deals(status)`, `deals(deal_type)`, and ILIKE searches have no supporting indexes. Fix: add indexes and consider pg_trgm for text search.

- **[severity: medium] Correctness — Race condition in embedding reindex task.** `tasks/embedding.py` deletes all embeddings then re-creates them in separate sessions. Concurrent operations can cause duplicates or lost embeddings. Fix: use row-level locking or a reindexing state flag.

- **[severity: medium] Security — No rate limiting on expensive endpoints.** QA ask endpoint (LLM calls), upload confirmation (Celery pipelines), and auth endpoints have no rate limiting. Fix: implement Redis-based rate limiting middleware.

- **[severity: medium] Error Handling — Silent error swallowing in frontend.** Multiple admin pages (`admin/settings`, `admin/users`, `integrations`) have empty catch blocks that silently fail. Fix: add error state UI and user feedback.

- **[severity: medium] Security — Unvalidated WebSocket JSON parsing.** `lib/websocket.ts` parses incoming messages without schema validation. Handlers receive arbitrary objects. Fix: add Zod or similar runtime validation.

### LOW

- **[severity: low] Correctness — Analysis `structured_output` nullability mismatch.** Model allows NULL but migration requires NOT NULL. Fix: align.

- **[severity: low] Correctness — Missing model relationships.** `DealMembership.added_by`, `Analysis.requested_by`, and `Meeting.organization` have no ORM relationship definitions. Fix: add relationships if navigation is needed.

- **[severity: low] Correctness — Fragile email parsing.** `AuthService` falls back to `email.split("@")[0]` without checking if `@` exists. Fix: add guard.

- **[severity: low] Correctness — `parseFloat` without NaN check in deal form.** `deal-form.tsx` converts deal size string without validating the result isn't NaN. Fix: add validation.

- **[severity: low] Readability — Breadcrumb generates invalid links.** `breadcrumbs.tsx` creates links like `/deals/[dealId]` for dynamic segments. Fix: skip linking for dynamic path segments.

- **[severity: low] Correctness — Docker Compose uses hardcoded weak credentials.** PostgreSQL password "localdev" and MinIO "minioadmin" in `docker-compose.yml`. Fix: use `.env` file.

- **[severity: low] Correctness — Deterministic seed UUIDs.** `scripts/seed.py` uses predictable UUIDs that could be exploited if seed runs in non-dev environments. Fix: document as dev-only.

- **[severity: low] Correctness — ECS uses `latest` Docker tag.** Dev and prod variables default to `:latest` tag. Fix: require specific version tags.

- **[severity: low] Validation — Missing schema validation for enum fields.** `DealMemberCreate.role`, `AnalysisRequest.call_type`, `DocumentCreate.document_type`, and `MeetingCreate.source` accept arbitrary strings without enum validation. Fix: add Pydantic enum validators or `Field(pattern=...)`.

- **[severity: low] Error Handling — Missing request_id in error responses.** Exception handlers don't include correlation IDs for client debugging. Fix: add `request_id` from request state.

- **[severity: low] Observability — SQL logs suppressed in all environments.** `core/logging.py` sets SQLAlchemy to WARNING even in development. Fix: conditionally set based on environment.

---

## Verdict

**NEEDS CHANGES** — There are 10 critical blocking issues and 8 high-severity issues that must be resolved before production deployment. The most urgent are:

1. **RLS write vulnerability** (missing WITH CHECK) — allows cross-org data injection
2. **Missing authorization** on org endpoints, transcript/document services, and deal creation
3. **Webhook forgery** — no signature verification on any webhook handler
4. **Infrastructure encryption** — ALB without HTTPS, Redis without AUTH/encryption
5. **Token/credential management** — encryption stubbed, mock auth unguarded, tokens in localStorage

The codebase demonstrates strong domain knowledge and clean architecture. Once the security layer is hardened, this would be a solid foundation for a production financial platform.
