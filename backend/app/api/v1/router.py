from fastapi import APIRouter

from app.api.v1 import (
    analysis,
    auth,
    auth_native,
    deliverables,
    health,
    integrations,
    internal,
    meetings_upload,
    qa,
    recall_webhooks,
    webhooks,
)
from app.api.v1.qa import meeting_qa_router

api_router = APIRouter()

# Identity — only /me and /logout remain; sign-in is handled by Supabase Auth
# directly from the frontend. The worker just verifies the JWT.
api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
# Self-hosted OAuth login + session (replaces Supabase Auth).
api_router.include_router(auth_native.router, prefix="/auth", tags=["Authentication"])

# Server-mediated actions (need secret API keys or service-role writes).
api_router.include_router(
    meetings_upload.router,
    prefix="/meetings",
    tags=["Meetings"],
)
api_router.include_router(
    analysis.router,
    prefix="/meetings/{meeting_id}/analyses",
    tags=["Analysis"],
)
api_router.include_router(
    deliverables.router,
    prefix="/deals/{deal_id}/deliverables",
    tags=["Deliverables"],
)
api_router.include_router(qa.router, prefix="/deals/{deal_id}/qa", tags=["Q&A"])
api_router.include_router(
    meeting_qa_router, prefix="/meetings/{meeting_id}/qa", tags=["Q&A"]
)

# Integrations (OAuth + meeting-bot scheduling).
api_router.include_router(
    integrations.router, prefix="/integrations", tags=["Integrations"]
)

# Inbound webhooks.
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
api_router.include_router(
    recall_webhooks.router,
    prefix="/webhooks/recall",
    tags=["Webhooks", "Live Transcription"],
)

# Store endpoints — REST over the worker-owned SQLite DB (replaces the
# frontend's former direct-to-Supabase reads/writes). Additive during migration.
from app.api.v1.store.router import store_router  # noqa: E402
from app.realtime.sse import router as sse_router  # noqa: E402

api_router.include_router(store_router)
api_router.include_router(sse_router, tags=["Realtime"])

# Service-to-service endpoints — Inngest calls these with X-Internal-Token.
api_router.include_router(internal.router, prefix="/internal", tags=["Internal"])
