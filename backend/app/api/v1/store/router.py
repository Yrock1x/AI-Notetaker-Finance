"""Aggregates the store routers (REST over the worker-owned SQLite DB).

Mounted under /api/v1 alongside the existing Supabase-backed routers during the
migration. ``deals`` uses relative paths (mounted at /deals); the others declare
full absolute paths and mount at the root.
"""

from fastapi import APIRouter

from app.api.v1.store import (
    bot_sessions,
    dashboard,
    deals,
    documents,
    files,
    meetings,
    orgs,
    transcripts,
)

store_router = APIRouter()

store_router.include_router(deals.router, prefix="/deals", tags=["Deals"])
store_router.include_router(meetings.router, tags=["Meetings"])
store_router.include_router(documents.router, tags=["Documents"])
store_router.include_router(transcripts.router, tags=["Transcripts"])
store_router.include_router(bot_sessions.router, tags=["Bot Sessions"])
store_router.include_router(orgs.router, tags=["Organizations"])
store_router.include_router(dashboard.router, tags=["Dashboard"])
store_router.include_router(files.router, tags=["Storage"])
