from fastapi import APIRouter

from app.api.v1 import (
    admin,
    analysis,
    auth,
    deals,
    documents,
    health,
    integrations,
    meetings,
    orgs,
    qa,
    transcripts,
    webhooks,
)
from app.api.v1.qa import meeting_qa_router

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(orgs.router, prefix="/orgs", tags=["Organizations"])
api_router.include_router(deals.router, prefix="/deals", tags=["Deals"])
api_router.include_router(meetings.router, prefix="/deals/{deal_id}/meetings", tags=["Meetings"])
api_router.include_router(transcripts.router, prefix="/meetings/{meeting_id}/transcript", tags=["Transcripts"])
api_router.include_router(analysis.router, prefix="/meetings/{meeting_id}/analyses", tags=["Analysis"])
api_router.include_router(documents.router, prefix="/deals/{deal_id}/documents", tags=["Documents"])
api_router.include_router(qa.router, prefix="/deals/{deal_id}/qa", tags=["Q&A"])
api_router.include_router(meeting_qa_router, prefix="/meetings/{meeting_id}/qa", tags=["Q&A"])
api_router.include_router(integrations.router, prefix="/integrations", tags=["Integrations"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
