import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db_with_rls
from app.models.user import User

router = APIRouter()


class GenerateRequest(BaseModel):
    type: str


MOCK_DELIVERABLES = [
    {
        "id": "e0000000-0000-0000-0000-000000000001",
        "title": "Investment Memo - Q4 Analysis",
        "deliverable_type": "investment_memo",
        "file_format": "docx",
        "status": "ready",
        "download_url": "#",
        "created_at": "2026-02-15T10:30:00Z",
    },
    {
        "id": "e0000000-0000-0000-0000-000000000002",
        "title": "Financial Model v2.1",
        "deliverable_type": "financial_model",
        "file_format": "xlsx",
        "status": "ready",
        "download_url": "#",
        "created_at": "2026-02-20T14:00:00Z",
    },
]

TYPE_LABELS = {
    "investment_memo": "Investment Memo",
    "financial_model": "Financial Model",
    "ic_presentation": "IC Presentation",
}

TYPE_FORMATS = {
    "investment_memo": "docx",
    "financial_model": "xlsx",
    "ic_presentation": "pptx",
}


@router.get("")
async def list_deliverables(
    deal_id: str,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> dict:
    items = [{**d, "deal_id": str(deal_id)} for d in MOCK_DELIVERABLES]
    return {"items": items}


@router.post("/generate", status_code=201)
async def generate_deliverable(
    deal_id: str,
    payload: GenerateRequest,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> dict:
    label = TYPE_LABELS.get(payload.type, payload.type)
    fmt = TYPE_FORMATS.get(payload.type, "docx")
    return {
        "id": str(uuid.uuid4()),
        "deal_id": str(deal_id),
        "title": f"{label} - Generated",
        "deliverable_type": payload.type,
        "file_format": fmt,
        "status": "ready",
        "download_url": "#",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
