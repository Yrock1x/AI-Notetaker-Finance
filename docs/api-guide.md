# API Guide

## Base URL

All worker endpoints are prefixed with `/api/v1`. The CogniVault partner API
lives under `/partner/v1`.

## Authentication

The frontend authenticates with the worker via the **session cookie**
(`cogni_session`, set at login and sent automatically with `credentials:
include`). A self-issued session JWT may also be passed as a Bearer token:

```
Authorization: Bearer <session-jwt>
```

The caller's organization(s) are derived from the authenticated principal's
memberships — there is no `X-Org-ID` header; tenant scoping is enforced
server-side in `app/db/scope.py`.

Internal pipeline endpoints (`/api/v1/internal/*`) require `X-Internal-Token`
instead, and the partner API uses a per-partner API key.

## Endpoint Groups

| Group         | Prefix                              | Description                          |
|---------------|-------------------------------------|--------------------------------------|
| Health        | `/health`                           | Health + readiness checks            |
| Auth          | `/auth`                             | OAuth + email/password login, session |
| Store (CRUD)  | `/store/*`, `/deals`, `/meetings`…  | Deals, meetings, documents, transcripts, bot sessions, orgs, dashboard, files |
| Analysis      | `/meetings/{meetingId}/analyses`    | Finance-specific analysis            |
| Q&A           | `/deals/{dealId}/qa`                | Deal-scoped RAG Q&A                  |
| Deliverables  | `/deals/{dealId}/deliverables`      | On-demand deliverable generation     |
| Integrations  | `/integrations`                     | OAuth connections + bot sessions     |
| Realtime      | `/meetings/{id}/stream`             | SSE stream of live-meeting events    |
| Webhooks      | `/webhooks`, `/webhooks/recall`     | Zoom / Teams / Slack / Recall.ai     |
| Internal      | `/internal/*`                       | Inngest → worker (X-Internal-Token)  |
| Partner       | `/partner/v1`                       | CogniVault M2M API (API-key auth)    |

## File upload / download

Uploads are not posted to the API directly: request a signed upload ticket
(`POST /storage/upload-ticket`), `PUT` the bytes at the returned HMAC-signed
URL, then create the row. Downloads use a method-bound signed `GET` URL.

## Pagination

List endpoints use cursor-based pagination:

```
GET /api/v1/deals?cursor=<cursor>&limit=25
→ { "items": [...], "cursor": "next-page-cursor", "has_more": true }
```

## Full reference

Swagger UI is available at `/docs` when running the worker locally (disabled in
production).
