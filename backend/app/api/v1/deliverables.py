"""Deliverable endpoints — SQLite + local storage + LLM-router, no S3, no mocks.

The frontend lists prior deliverables directly (a future ``deliverables``
table, TBD — the current schema doesn't persist them; we return just the
freshly-generated ones). ``POST /generate`` runs synchronously via
``DeliverableService`` and returns an HMAC-signed local-storage download URL.
``POST /chat`` is a simple LLM wrapper for the "refine this" side-panel.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.deps import get_db, get_principal
from app.db.scope import Principal, deal_org_id
from app.dependencies import (
    get_llm_router,
)
from app.llm.router import TASK_GENERAL
from app.services.deliverable_service import DeliverableService

logger = structlog.get_logger(__name__)

router = APIRouter()


def _require_deal_access(session: Session, principal: Principal, deal_id: str) -> None:
    org_id = deal_org_id(session, deal_id)
    if org_id is None or not principal.in_org(org_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")


class GenerateRequest(BaseModel):
    type: str


class ChatRequest(BaseModel):
    message: str


TYPE_LABELS = {
    "investment_memo": "Investment Memo",
    "financial_model": "Financial Model",
    "ic_presentation": "IC Presentation",
}


@router.post("/generate", status_code=201)
async def generate_deliverable(
    deal_id: str,
    payload: GenerateRequest,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
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
    _require_deal_access(session, principal, deal_id)

    service = DeliverableService(
        session=session,
        settings=get_settings(),
        llm_router=get_llm_router(),
    )
    try:
        return await service.generate(
            deal_id=deal_uuid, deliverable_type=payload.type
        )
    except Exception as exc:
        logger.exception(
            "deliverable_generate_failed", deal_id=deal_id, type=payload.type
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                f"Failed to generate {TYPE_LABELS[payload.type]}. "
                "The LLM or storage upload errored — try again in a moment."
            ),
        ) from exc


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
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> dict:
    _require_deal_access(session, principal, deal_id)
    llm_router = get_llm_router()
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
