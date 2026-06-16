"""Internal service-to-service endpoints invoked by Inngest functions.

These endpoints carry out the heavy Python-side work (Deepgram, Fireworks,
Recall.ai, file extraction) that Inngest's JavaScript orchestration calls
into. Every request must carry the shared ``X-Internal-Token`` header.

Split from a single 1.7k-line module into per-domain routers; this package
re-exports the combined ``router`` plus a couple of names tests reach for.
"""

from fastapi import APIRouter

from app.api.v1.internal import bots, calendar, ingest, status, transcription
from app.api.v1.internal._common import _dedupe_zoom_google_rows, require_internal_token

router = APIRouter()
router.include_router(transcription.router)
router.include_router(bots.router)
router.include_router(ingest.router)
router.include_router(calendar.router)
router.include_router(status.router)

__all__ = ["router", "_dedupe_zoom_google_rows", "require_internal_token"]
