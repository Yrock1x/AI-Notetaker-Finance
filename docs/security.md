# Security

## Authentication

- AWS Cognito with JWT tokens
- SAML/SSO federation for enterprise clients
- MFA enforcement available per organization

## Authorization

### Three-Layer RBAC

1. **Organization membership** — Middleware verifies user belongs to org on every request
2. **Deal-level roles** — Service layer checks deal_memberships before any deal operation
3. **Row-Level Security** — PostgreSQL RLS policies filter by org_id as defense-in-depth

### Deal Roles

| Role | Read | Write | Delete | Manage Members | Run Analysis | Export |
|------|------|-------|--------|---------------|-------------|--------|
| Lead | Y | Y | Y | Y | Y | Y |
| Admin | Y | Y | N | Y | Y | Y |
| Analyst | Y | Y | N | N | Y | N |
| Viewer | Y | N | N | N | N | N |

## Data Isolation

- Strict organizational boundaries via RLS
- Deal-level access control via RBAC
- No cross-org data access possible at the database level

## Encryption

- TLS 1.2+ for all connections
- AES-256 encryption at rest (S3, RDS, ElastiCache)
- Integration tokens encrypted with Fernet symmetric encryption

## Audit Logging

- Every API request logged with user, action, resource, IP, timestamp
- Append-only audit_logs table
- Queryable via admin API

## Recording Consent

- Meeting bot announces presence and recording
- consent_obtained flag tracked per bot session
- Configurable consent policies per organization
