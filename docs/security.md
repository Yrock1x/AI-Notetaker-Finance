# Security

## Authentication

- Self-issued **session JWTs** (HS256) carried in an httpOnly cookie, signed
  with `SESSION_JWT_SECRET`.
- Login via OAuth (Google / Microsoft) or email + password (Argon2id hashing),
  all handled by the worker (`app/api/v1/auth_native.py`, `app/auth/`).
- Password login + registration are rate-limited (slowapi) to blunt brute force.

## Authorization

### App-layer multi-tenancy (not RLS)

The data layer is SQLite, so tenant isolation is enforced **in app code**, not
Postgres Row-Level Security:

1. **Organization membership** — every handler that reads/writes a tenant-owned
   row goes through a scope guard in `app/db/scope.py` (`org_scoped` /
   `meeting_scoped` / `scoped_*_or_404` / `require_org` / `in_org`).
2. **Deal-level roles** — lead / admin / analyst / viewer, checked before deal
   operations.
3. **Static tripwire** — `tests/unit/test_scope_guard_lint.py` fails the build
   if a route handler queries a tenant model without a scope guard.

### Deal Roles

| Role    | Read | Write | Delete | Manage Members | Run Analysis | Export |
|---------|------|-------|--------|----------------|--------------|--------|
| Lead    | Y    | Y     | Y      | Y              | Y            | Y      |
| Admin   | Y    | Y     | N      | Y              | Y            | Y      |
| Analyst | Y    | Y     | N      | N              | Y            | N      |
| Viewer  | Y    | N     | N      | N              | N            | N      |

## File storage

- Files live under `STORAGE_ROOT`; access is gated by short-lived **HMAC-signed
  URLs** that bind the HTTP method (a GET-signed URL can't be replayed as a PUT).
- `STORAGE_SIGNING_KEY` is required in production and must be distinct from the
  session and internal-token secrets.

## Webhooks

- Zoom / Slack / Recall webhooks verify an HMAC signature **before** the body is
  parsed, and enforce a timestamp-freshness window + replay dedup.
- Internal endpoints (`/api/v1/internal/*`) require `X-Internal-Token`.

## Transport & headers

- TLS enforced (`force_https`); HSTS + CSP + `X-Content-Type-Options` /
  `X-Frame-Options` / `Referrer-Policy` set on every response in production.

## Encryption

- Integration OAuth tokens encrypted at rest with Fernet (`TOKEN_ENCRYPTION_KEY`).

## Production secret validation

The worker fails fast on boot in production if any of `SESSION_JWT_SECRET`,
`STORAGE_SIGNING_KEY`, `WORKER_INTERNAL_TOKEN`, `TOKEN_ENCRYPTION_KEY`,
`FIREWORKS_API_KEY` (and `RECALL_WEBHOOK_SECRET` when bots are enabled) is
missing, too short, or not distinct.

## Audit Logging

- API actions logged with user, action, resource, and timestamp to an
  append-only `audit_logs` table; queryable via the admin API.

## Recording Consent

- The meeting bot announces its presence; `consent_obtained` is tracked per bot
  session.
