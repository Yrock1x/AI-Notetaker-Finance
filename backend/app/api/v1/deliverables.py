"""Deliverable endpoints — Supabase + LLM-router, no S3, no mocks.

The frontend lists prior deliverables directly from a Supabase table (a
future ``deliverables`` table, TBD — the current schema doesn't persist
them; we return just the freshly-generated ones). ``POST /generate`` runs
synchronously via ``DeliverableService`` and returns a signed Supabase
Storage URL. ``POST /chat`` is a simple LLM wrapper for the "refine this"
side-panel.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from supabase import Client

from app.api.v1.qa import _build_llm_router
from app.core.config import get_settings
from app.dependencies import AuthUser, get_current_user, get_user_supabase
from app.llm.router import TASK_GENERAL
from app.services.deliverable_service import DeliverableService

logger = structlog.get_logger(__name__)

router = APIRouter()


class GenerateRequest(BaseModel):
    type: str


class ChatRequest(BaseModel):
    message: str


TYPE_LABELS = {
    "investment_memo": "Investment Memo",
    "financial_model": "Financial Model",
    "ic_presentation": "IC Presentation",
}


@router.get("")
async def list_deliverables(
    deal_id: str,
    _user: AuthUser = Depends(get_current_user),
) -> dict:
    """Placeholder list — a future ``deliverables`` table will persist past
    generations. For now the UI just shows what it has locally cached.
    """
    return {"items": [], "deal_id": deal_id}


@router.post("/generate", status_code=201)
async def generate_deliverable(
    deal_id: str,
    payload: GenerateRequest,
    supabase: Client = Depends(get_user_supabase),
    _user: AuthUser = Depends(get_current_user),
) -> dict:
    if payload.type not in TYPE_LABELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported deliverable type: {payload.type}",
        )
    try:
        deal_uuid = UUID(deal_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid deal_id",
        ) from exc

    service = DeliverableService(
        supabase=supabase,
        settings=get_settings(),
        llm_router=_build_llm_router(),
    )
    try:
        return await service.generate(
            deal_id=deal_uuid, deliverable_type=payload.type
        )
    except Exception:
        logger.exception(
            "deliverable_generate_failed", deal_id=deal_id, type=payload.type
        )
        return {
            "id": str(uuid.uuid4()),
            "deal_id": deal_id,
            "title": (
                f"{TYPE_LABELS[payload.type]} - Generated "
                "(placeholder — generation failed)"
            ),
            "deliverable_type": payload.type,
            "file_format": "docx",
            "status": "failed",
            "download_url": "#",
            "created_at": datetime.now(UTC).isoformat(),
        }


_DELIVERABLE_SYSTEM_PROMPT = (
    "You are an expert AI assistant for investment banking and private equity "
    "professionals. You help create deal deliverables — investment memos, "
    "financial models, IC presentations, and other deal documents. You have "
    "deep expertise in financial analysis, valuation, market research, and "
    "professional document structuring.\n\n"
    "When the user describes a deliverable they want, help them refine the "
    "scope, suggest sections and structure, ask clarifying questions about "
    "audience and emphasis, and provide substantive content guidance. Be "
    "concise, professional, and actionable.\n\n"
    "Always respond in a helpful, structured way using markdown formatting "
    "where appropriate."
)


@router.post("/chat")
async def deliverable_chat(
    deal_id: str,
    payload: ChatRequest,
    _user: AuthUser = Depends(get_current_user),
) -> dict:
    llm_router = _build_llm_router()
    try:
        response = await llm_router.complete(
            task_type=TASK_GENERAL,
            system_prompt=_DELIVERABLE_SYSTEM_PROMPT,
            user_prompt=payload.message,
            max_tokens=2048,
            temperature=0.7,
        )
        content = response.content
    except Exception:
        logger.exception("deliverable_chat_failed")
        content = (
            "I couldn't reach the LLM right now. Try again in a moment; "
            "if this keeps happening, verify the Fireworks API key is set."
        )

    return {
        "id": str(uuid.uuid4()),
        "deal_id": deal_id,
        "role": "assistant",
        "content": content,
        "created_at": datetime.now(UTC).isoformat(),
    }
