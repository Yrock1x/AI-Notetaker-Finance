import random
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


class ChatRequest(BaseModel):
    message: str


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


# ---------------------------------------------------------------------------
# Deliverable AI Chat – mock responses for demo
# ---------------------------------------------------------------------------

_CHAT_RESPONSES: dict[str, list[str]] = {
    "memo": [
        "I can draft an investment memo for this deal. Based on the meeting transcripts, I'll include:\n\n"
        "• **Executive Summary** – key thesis and recommendation\n"
        "• **Company Overview** – business model, market position, competitive moats\n"
        "• **Financial Analysis** – revenue trends, margins, and projections\n"
        "• **Risk Factors** – regulatory, market, and execution risks\n"
        "• **Valuation** – comparable analysis and DCF summary\n\n"
        "Would you like me to emphasize any particular section or adjust the tone (e.g., more conservative, growth-oriented)?",
    ],
    "model": [
        "I'll build a financial model in Excel with the following tabs:\n\n"
        "• **Assumptions** – key drivers you can toggle\n"
        "• **Income Statement** – 5-year projections\n"
        "• **Balance Sheet** – working capital and debt schedule\n"
        "• **Cash Flow** – FCF and returns analysis\n"
        "• **Sensitivity Tables** – on revenue growth and margins\n\n"
        "From the transcripts, management guided 15-20% revenue growth. Should I use the midpoint or build bear/base/bull scenarios?",
    ],
    "presentation": [
        "I can create an IC presentation deck. Based on the deal materials, here's the proposed outline:\n\n"
        "1. **Deal Overview** (1 slide)\n"
        "2. **Investment Thesis** (2 slides)\n"
        "3. **Market & Competitive Landscape** (2 slides)\n"
        "4. **Financial Summary & Projections** (3 slides)\n"
        "5. **Key Risks & Mitigants** (1 slide)\n"
        "6. **Proposed Terms & Next Steps** (1 slide)\n\n"
        "Should I match the style of your uploaded template, or use a clean default layout?",
    ],
    "default": [
        "I understand. I can help you refine the deliverable. Here are a few things I can adjust:\n\n"
        "• **Scope** – which sections to include or exclude\n"
        "• **Depth** – high-level summary vs. detailed analysis\n"
        "• **Tone** – formal IC presentation vs. working draft\n"
        "• **Data sources** – which meetings and documents to pull from\n\n"
        "Tell me more about what you're looking for and I'll tailor the output accordingly.",
        "Got it. I'll incorporate that into the deliverable. A few clarifying questions:\n\n"
        "1. What's the target audience — IC members, co-investors, or internal team?\n"
        "2. Do you want me to include sensitivity analysis?\n"
        "3. Any specific metrics or KPIs management highlighted that should be front and center?\n\n"
        "Feel free to share any additional context and I'll make sure the final output reflects your requirements.",
        "Absolutely. I'll factor that in. Based on the 3 meetings recorded so far, I have solid data on:\n\n"
        "• Management's growth guidance and margin expectations\n"
        "• Competitive positioning discussed in the industry overview session\n"
        "• Key risks flagged by the due diligence team\n\n"
        "I can weave all of this into the deliverable. Would you like a draft outline before I generate the full document?",
    ],
}


def _pick_mock_response(message: str) -> str:
    msg = message.lower()
    if any(w in msg for w in ("memo", "write-up", "writeup", "investment")):
        pool = _CHAT_RESPONSES["memo"]
    elif any(w in msg for w in ("model", "excel", "financial", "spreadsheet", "fcf")):
        pool = _CHAT_RESPONSES["model"]
    elif any(
        w in msg
        for w in ("presentation", "deck", "ppt", "slide", "powerpoint", "ic ")
    ):
        pool = _CHAT_RESPONSES["presentation"]
    else:
        pool = _CHAT_RESPONSES["default"]
    return random.choice(pool)


@router.post("/chat")
async def deliverable_chat(
    deal_id: str,
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "deal_id": str(deal_id),
        "role": "assistant",
        "content": _pick_mock_response(payload.message),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
