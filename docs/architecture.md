# Architecture

## Overview

DealWise AI is a multi-tenant meeting intelligence platform built as a monorepo.

## Stack

- **Backend**: Python (FastAPI) with async SQLAlchemy
- **Frontend**: Next.js 15 (React 19) with App Router
- **Database**: PostgreSQL 16 + pgvector
- **Cache/Queue**: Redis + Celery
- **Storage**: AWS S3
- **Auth**: AWS Cognito
- **AI**: Claude (analysis), OpenAI (embeddings), Deepgram (transcription)

## Data Flow

```
Meeting Upload → S3 → Celery Pipeline:
  validate → extract_audio → transcribe (Deepgram) → diarize
    → [embed (OpenAI) + analyze (Claude)] → notify
```

## Multi-Tenancy

- Organization-level tenancy with PostgreSQL Row-Level Security
- Deal-level RBAC (lead/admin/analyst/viewer)
- RLS context set per-request via `SET LOCAL app.current_org_id`

## Key Design Decisions

See the plan file for detailed architectural decisions and tradeoffs.
