# DealWise AI - Project Guide

## Overview
Enterprise multi-tenant AI meeting intelligence platform for IB/PE/VC professionals.

## Tech Stack
- **Backend**: Python 3.11+ / FastAPI (async) / SQLAlchemy 2.0 / Celery + Redis
- **Frontend**: Next.js 15 / React 19 / TypeScript / Tailwind CSS / shadcn/ui
- **Database**: PostgreSQL 16 + pgvector (RLS for multi-tenancy)
- **AI**: Claude (analysis/Q&A), OpenAI (embeddings), Deepgram (transcription)
- **Auth**: AWS Cognito
- **Infra**: AWS (ECS, RDS, S3, ElastiCache, SQS) via Terraform

## Project Structure
```
backend/app/          - FastAPI application
  core/               - Config, database, security, middleware
  models/             - SQLAlchemy ORM models (13 tables)
  schemas/            - Pydantic v2 request/response schemas
  api/v1/             - Router stubs (all return 501 until implemented)
  services/           - Business logic layer (NotImplementedError stubs)
  llm/                - Multi-provider LLM abstraction + finance prompts
  tasks/              - Celery tasks + processing pipelines
  integrations/       - External service clients (Deepgram, Zoom, Teams, etc.)
  utils/              - Audio, file processing, time utilities
frontend/src/         - Next.js application
  app/                - App Router pages
  components/         - React components (layout, domain, shared, ui)
  hooks/              - React Query hooks
  stores/             - Zustand state stores
  lib/                - API client, auth, utils
  types/              - TypeScript types and enums
infrastructure/       - Terraform modules for AWS
```

## Key Patterns
- All API endpoints are stubs (HTTPException 501) — implement service layer first
- Services use constructor dependency injection (db, settings, llm_router)
- Celery pipelines chain: upload → transcribe → diarize → [embed + analyze] → notify
- RLS via `SET LOCAL app.current_org_id` in get_db_with_rls dependency
- Deal-level RBAC: lead > admin > analyst > viewer

## Running Locally
```bash
cd backend && docker compose up -d postgres redis minio
cd backend && uvicorn app.main:create_app --factory --port 8000 --reload
cd frontend && npm run dev
```
