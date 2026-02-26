# API Guide

## Base URL

All API endpoints are prefixed with `/api/v1`.

## Authentication

All endpoints (except health checks and webhooks) require a Bearer token in the Authorization header:

```
Authorization: Bearer <cognito-jwt-token>
```

## Organization Context

Most endpoints require an organization context via the `X-Org-ID` header:

```
X-Org-ID: <organization-uuid>
```

## Endpoint Groups

| Group | Prefix | Description |
|-------|--------|-------------|
| Health | `/health` | Health and readiness checks |
| Auth | `/auth` | Authentication callbacks and profile |
| Organizations | `/orgs` | Organization CRUD and membership |
| Deals | `/deals` | Deal workspaces and team management |
| Meetings | `/deals/{dealId}/meetings` | Meeting upload and management |
| Transcripts | `/meetings/{meetingId}/transcript` | Transcript viewing and search |
| Analysis | `/meetings/{meetingId}/analyses` | Finance-specific analysis |
| Documents | `/deals/{dealId}/documents` | Document upload and management |
| Q&A | `/deals/{dealId}/qa` | Deal-scoped RAG Q&A |
| Integrations | `/integrations` | Platform connections and bot sessions |
| Webhooks | `/webhooks` | External platform webhooks |
| Admin | `/admin` | User management, audit logs, settings |

## Pagination

All list endpoints use cursor-based pagination:

```
GET /api/v1/deals?cursor=<cursor>&limit=25

Response:
{
  "items": [...],
  "cursor": "next-page-cursor",
  "has_more": true
}
```

## Full API reference available at `/docs` (Swagger UI) when running locally.
