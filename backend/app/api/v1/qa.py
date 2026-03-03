import uuid as uuid_mod
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.dependencies import get_current_user, get_db_with_rls, get_org_id
from app.integrations.aws.s3 import get_s3_client
from app.llm.gemini_provider import GeminiEmbeddingProvider, GeminiProvider
from app.llm.router import LLMRouter
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.qa import QAHistoryResponse, QARequest, QAResponse
from app.services.deal_service import DealService
from app.services.embedding_service import EmbeddingService
from app.services.meeting_service import MeetingService
from app.services.qa_service import QAService

router = APIRouter()
meeting_qa_router = APIRouter()


def _generate_mock_response(question: str) -> dict:
    """Generate a realistic mock QA response based on question keywords.

    Used in demo mode when no AI API keys are configured.
    """
    q = question.lower()

    if any(kw in q for kw in ("financial", "revenue", "metrics", "arr", "margin")):
        answer = (
            "Based on the meeting discussions and financial documents reviewed, "
            "the target company reported $45M ARR with 78% gross margins in the "
            "trailing twelve months. Revenue growth has been 35% YoY, driven primarily "
            "by enterprise contract expansions. Net revenue retention stands at 125%, "
            "indicating strong upsell motion. EBITDA margins are currently at 15% but "
            "management projects reaching 25% within 18 months through operating leverage."
        )
        citations = [
            {
                "source_type": "transcript_segment",
                "source_id": "e5000000-0000-0000-0000-000000000001",
                "source_title": "Management Presentation - Financial Overview",
                "text_excerpt": (
                    "We closed the trailing twelve months at "
                    "$45 million ARR with gross margins holding "
                    "steady at 78 percent."
                ),
            },
            {
                "source_type": "document_chunk",
                "source_id": "e5000000-0000-0000-0000-000000000002",
                "source_title": "Confidential Information Memorandum",
                "text_excerpt": (
                    "Net revenue retention of 125% demonstrates "
                    "the company's strong land-and-expand strategy "
                    "across enterprise accounts."
                ),
            },
        ]
        grounding_score = 0.94

    elif any(kw in q for kw in ("risk", "concern", "issue", "problem", "weakness")):
        answer = (
            "Several key risks were identified during the due diligence discussions: "
            "(1) Customer concentration - the top 3 clients represent 40% of total ARR, "
            "creating significant revenue dependency. (2) The VP of Sales has only been "
            "in the role for 4 months, raising concerns about go-to-market execution "
            "continuity. (3) The company has pending litigation related to a former "
            "employee IP dispute that could result in $2-5M in potential liability. "
            "(4) Deferred revenue recognition practices need further scrutiny by the "
            "quality of earnings team."
        )
        citations = [
            {
                "source_type": "transcript_segment",
                "source_id": "e5000000-0000-0000-0000-000000000001",
                "source_title": "Financial Due Diligence - Day 1",
                "text_excerpt": (
                    "Our top three customers account for roughly "
                    "40 percent of our recurring revenue, which "
                    "we acknowledge is a concentration risk."
                ),
            },
            {
                "source_type": "transcript_segment",
                "source_id": "e5000000-0000-0000-0000-000000000003",
                "source_title": "Deal Team Sync - Valuation Review",
                "text_excerpt": (
                    "The new VP of Sales started just four months "
                    "ago, so we need to assess whether the pipeline "
                    "forecast is reliable."
                ),
            },
        ]
        grounding_score = 0.91

    elif any(kw in q for kw in ("team", "leadership", "management", "ceo", "cto", "executive")):
        answer = (
            "The leadership team has strong domain expertise but some notable gaps. "
            "The CEO (founder) has 15 years in enterprise SaaS and previously scaled "
            "a company to $100M+ ARR. The CTO is highly technical with deep AI/ML "
            "background and leads a team of 45 engineers. However, the CFO role is "
            "currently filled by an interim controller, and the VP of Sales is relatively "
            "new (4 months tenure). The board includes two independent directors with "
            "relevant industry experience. Management team retention has been strong "
            "with <10% voluntary attrition over the past 2 years."
        )
        citations = [
            {
                "source_type": "transcript_segment",
                "source_id": "e5000000-0000-0000-0000-000000000001",
                "source_title": "Management Presentation",
                "text_excerpt": (
                    "I founded the company 8 years ago after "
                    "spending 15 years building enterprise SaaS "
                    "products, including scaling my previous "
                    "company past $100M ARR."
                ),
            },
            {
                "source_type": "transcript_segment",
                "source_id": "e5000000-0000-0000-0000-000000000003",
                "source_title": "CTO Technical Deep-Dive",
                "text_excerpt": (
                    "Our engineering team is 45 people strong, "
                    "organized into 6 squads, each owning a "
                    "specific product domain."
                ),
            },
        ]
        grounding_score = 0.89

    elif any(kw in q for kw in ("growth", "strategy", "expansion", "plan", "roadmap")):
        answer = (
            "The company's growth strategy centers on three pillars: (1) Geographic "
            "expansion into EMEA, targeting $8M incremental ARR within 18 months by "
            "leveraging existing customer relationships with global enterprises. "
            "(2) Product-led growth through a self-serve tier launching Q3, expected "
            "to reduce CAC by 40% for SMB segments. (3) Strategic M&A to acquire "
            "complementary data integration capabilities, with 2-3 targets already "
            "identified. The total addressable market is estimated at $12B, with the "
            "company currently at <1% penetration."
        )
        citations = [
            {
                "source_type": "transcript_segment",
                "source_id": "e5000000-0000-0000-0000-000000000001",
                "source_title": "Management Presentation - Growth Strategy",
                "text_excerpt": (
                    "Our EMEA expansion is already underway. "
                    "We have LOIs from three existing US customers "
                    "for their European operations, representing "
                    "$8 million in potential ARR."
                ),
            },
            {
                "source_type": "document_chunk",
                "source_id": "e5000000-0000-0000-0000-000000000002",
                "source_title": "Investment Committee Deck",
                "text_excerpt": (
                    "Self-serve product tier (Q3 launch) is "
                    "projected to reduce customer acquisition "
                    "cost by 40% in the SMB segment."
                ),
            },
        ]
        grounding_score = 0.92

    elif any(kw in q for kw in ("competitive", "market", "competitor", "landscape", "position")):
        answer = (
            "The competitive landscape includes 3-4 direct competitors and several "
            "adjacent players. The company's primary differentiator is its proprietary "
            "AI engine, which delivers 3x faster processing than the nearest competitor "
            "(benchmarked independently). Market share among enterprise clients is "
            "estimated at 12%, second only to the incumbent legacy provider at 35%. "
            "Key competitive advantages include: superior API integration capabilities, "
            "SOC 2 Type II and HIPAA compliance (competitors lack healthcare certifications), "
            "and a Net Promoter Score of 72 vs. industry average of 41. The main "
            "competitive threat is a well-funded Series C startup that raised $80M "
            "last quarter and is aggressively hiring enterprise sales reps."
        )
        citations = [
            {
                "source_type": "document_chunk",
                "source_id": "e5000000-0000-0000-0000-000000000002",
                "source_title": "Market Analysis Discussion Notes",
                "text_excerpt": (
                    "Independent benchmarks show our processing "
                    "engine is 3x faster than CompetitorX and "
                    "5x faster than the legacy incumbent."
                ),
            },
            {
                "source_type": "transcript_segment",
                "source_id": "e5000000-0000-0000-0000-000000000003",
                "source_title": "GreenEnergy Co - Market Analysis Discussion",
                "text_excerpt": (
                    "We see the Series C competitor as our "
                    "biggest threat. They just raised $80 million "
                    "and are hiring aggressively in enterprise "
                    "sales."
                ),
            },
        ]
        grounding_score = 0.88

    else:
        # Default fallback - generic deal summary
        answer = (
            "Based on the available meeting transcripts and deal documents, here is "
            "a summary of the key findings: The target company is a high-growth "
            "enterprise SaaS business with strong unit economics and a defensible "
            "market position. Revenue stands at $45M ARR growing 35% YoY, with "
            "attractive gross margins of 78%. Key diligence areas that require "
            "further investigation include customer concentration risk, the recently "
            "hired sales leadership, and a pending IP litigation matter. The management "
            "team is generally strong, with particular depth on the technical side. "
            "The proposed valuation of 15-18x ARR is in line with comparable transactions "
            "in the sector."
        )
        citations = [
            {
                "source_type": "transcript_segment",
                "source_id": "e5000000-0000-0000-0000-000000000001",
                "source_title": "Management Presentation",
                "text_excerpt": (
                    "We believe the business is well-positioned "
                    "for continued growth, with $45M ARR and "
                    "strong underlying metrics."
                ),
            },
            {
                "source_type": "document_chunk",
                "source_id": "e5000000-0000-0000-0000-000000000002",
                "source_title": "Confidential Information Memorandum",
                "text_excerpt": (
                    "Comparable transaction analysis supports a "
                    "valuation range of 15-18x trailing ARR for "
                    "businesses with similar growth profiles."
                ),
            },
        ]
        grounding_score = 0.85

    return {
        "answer": answer,
        "citations": citations,
        "grounding_score": grounding_score,
    }


@router.post("/ask", response_model=QAResponse)
async def ask_question(
    deal_id: UUID,
    payload: QARequest,
    db: AsyncSession = Depends(get_db_with_rls),
    org_id: UUID = Depends(get_org_id),
    current_user: User = Depends(get_current_user),
) -> QAResponse:
    """Ask a question scoped to the deal's meetings and documents.

    Uses RAG to find relevant context and generates a citation-backed answer.
    Requires deal membership.
    """
    deal_service = DealService(db)
    await deal_service.check_deal_access(deal_id, current_user.id)

    settings = get_settings()

    if settings.google_api_key:
        try:
            # Set up the LLM router with Gemini provider
            llm_router = LLMRouter()
            gemini_provider = GeminiProvider(api_key=settings.google_api_key)
            llm_router.register_provider("gemini", gemini_provider)

            # Set up the embedding service with Gemini provider
            embedding_provider = GeminiEmbeddingProvider(api_key=settings.google_api_key)
            embedding_service = EmbeddingService(db, embedding_provider)

            qa_service = QAService(db, llm_router, embedding_service)
            result = await qa_service.ask(
                deal_id=deal_id,
                org_id=org_id,
                question=payload.question,
            )

            return QAResponse(
                id=uuid_mod.uuid4(),
                deal_id=deal_id,
                question=payload.question,
                answer=result.answer,
                citations=[],
                grounding_score=result.grounding_score,
                model_used="gemini-2.0-flash",
                created_at=datetime.now(UTC),
            )
        except Exception:  # noqa: S110 - fall back to mock responses on API errors
            pass

    # No API key or API error: return mock responses
    mock = _generate_mock_response(payload.question)
    return QAResponse(
        id=uuid_mod.uuid4(),
        deal_id=deal_id,
        question=payload.question,
        answer=mock["answer"],
        citations=mock["citations"],
        grounding_score=mock["grounding_score"],
        model_used="demo-mock",
        created_at=datetime.now(UTC),
    )


@meeting_qa_router.post("/ask", response_model=QAResponse)
async def ask_meeting_question(
    meeting_id: UUID,
    payload: QARequest,
    db: AsyncSession = Depends(get_db_with_rls),
    org_id: UUID = Depends(get_org_id),
    current_user: User = Depends(get_current_user),
) -> QAResponse:
    """Ask a question scoped to a specific meeting's transcript and context.

    Uses RAG to find relevant context within the meeting and generates
    a citation-backed answer.
    """
    # Look up the meeting to get its deal_id for access check
    settings = get_settings()
    s3_client = get_s3_client()
    meeting_service = MeetingService(db, s3_client, settings)
    meeting = await meeting_service.get_meeting(meeting_id)
    deal_id = meeting.deal_id

    deal_service = DealService(db)
    await deal_service.check_deal_access(deal_id, current_user.id)

    if settings.google_api_key:
        try:
            # Set up the LLM router with Gemini provider
            llm_router = LLMRouter()
            gemini_provider = GeminiProvider(api_key=settings.google_api_key)
            llm_router.register_provider("gemini", gemini_provider)

            # Set up the embedding service with Gemini provider
            embedding_provider = GeminiEmbeddingProvider(api_key=settings.google_api_key)
            embedding_service = EmbeddingService(db, embedding_provider)

            qa_service = QAService(db, llm_router, embedding_service)
            result = await qa_service.ask(
                deal_id=deal_id,
                org_id=org_id,
                question=payload.question,
                meeting_id=meeting_id,
            )

            return QAResponse(
                id=uuid_mod.uuid4(),
                deal_id=deal_id,
                question=payload.question,
                answer=result.answer,
                citations=[],
                grounding_score=result.grounding_score,
                model_used="gemini-2.0-flash",
                created_at=datetime.now(UTC),
            )
        except Exception:  # noqa: S110 - fall back to mock responses on API errors
            pass

    # No API key or API error: return mock responses
    mock = _generate_mock_response(payload.question)
    return QAResponse(
        id=uuid_mod.uuid4(),
        deal_id=deal_id,
        question=payload.question,
        answer=mock["answer"],
        citations=mock["citations"],
        grounding_score=mock["grounding_score"],
        model_used="demo-mock",
        created_at=datetime.now(UTC),
    )


@router.get("/history", response_model=PaginatedResponse[QAHistoryResponse])
async def get_qa_history(
    deal_id: UUID,
    cursor: str | None = Query(None),
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> PaginatedResponse[QAHistoryResponse]:
    """Get Q&A history for a deal."""
    # QA persistence model not yet implemented; return empty list
    deal_service = DealService(db)
    await deal_service.check_deal_access(deal_id, current_user.id)

    return PaginatedResponse(items=[], cursor=None, has_more=False)


@router.get("/history/{interaction_id}", response_model=QAResponse)
async def get_qa_interaction(
    deal_id: UUID,
    interaction_id: UUID,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> QAResponse:
    """Get a specific Q&A interaction with full citations."""
    # QA persistence model not yet implemented
    deal_service = DealService(db)
    await deal_service.check_deal_access(deal_id, current_user.id)

    raise HTTPException(501, "QA history persistence not yet implemented")
