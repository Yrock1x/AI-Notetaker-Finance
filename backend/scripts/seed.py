"""
Database seed script for Deal Companion.

Populates the development database with realistic sample data:
  - 2 organizations
  - 4 users with org memberships
  - 3 deals with deal memberships
  - Meetings, transcripts, segments, analyses, participants, and documents

Idempotent: checks for existing data before inserting.
Usage:  python -m scripts.seed   (from the backend/ directory)
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.database import async_session_factory
from app.core.security import DealRole
from app.models import (
    Analysis,
    Deal,
    DealMembership,
    Document,
    Meeting,
    MeetingParticipant,
    Organization,
    OrgMembership,
    Transcript,
    TranscriptSegment,
    User,
)

# ---------------------------------------------------------------------------
# Deterministic UUIDs so the script is truly idempotent and relationships
# can be wired up before any database round-trip.
# ---------------------------------------------------------------------------
ORG1_ID = uuid.UUID("a1000000-0000-0000-0000-000000000001")
ORG2_ID = uuid.UUID("a1000000-0000-0000-0000-000000000002")

USER_SARAH_ID   = uuid.UUID("b2000000-0000-0000-0000-000000000001")
USER_MICHAEL_ID = uuid.UUID("b2000000-0000-0000-0000-000000000002")
USER_EMILY_ID   = uuid.UUID("b2000000-0000-0000-0000-000000000003")
USER_JAMES_ID   = uuid.UUID("b2000000-0000-0000-0000-000000000004")

DEAL_ATLAS_ID   = uuid.UUID("c3000000-0000-0000-0000-000000000001")
DEAL_BEACON_ID  = uuid.UUID("c3000000-0000-0000-0000-000000000002")
DEAL_CIPHER_ID  = uuid.UUID("c3000000-0000-0000-0000-000000000003")

# Meeting UUIDs
MTG_ATLAS_1 = uuid.UUID("d4000000-0000-0000-0000-000000000001")
MTG_ATLAS_2 = uuid.UUID("d4000000-0000-0000-0000-000000000002")
MTG_ATLAS_3 = uuid.UUID("d4000000-0000-0000-0000-000000000003")
MTG_ATLAS_4 = uuid.UUID("d4000000-0000-0000-0000-000000000004")
MTG_BEACON_1 = uuid.UUID("d4000000-0000-0000-0000-000000000005")
MTG_BEACON_2 = uuid.UUID("d4000000-0000-0000-0000-000000000006")
MTG_BEACON_3 = uuid.UUID("d4000000-0000-0000-0000-000000000007")
MTG_CIPHER_1 = uuid.UUID("d4000000-0000-0000-0000-000000000008")
MTG_CIPHER_2 = uuid.UUID("d4000000-0000-0000-0000-000000000009")

# Transcript UUIDs
TXN_ATLAS_1 = uuid.UUID("e5000000-0000-0000-0000-000000000001")
TXN_ATLAS_2 = uuid.UUID("e5000000-0000-0000-0000-000000000002")
TXN_ATLAS_3 = uuid.UUID("e5000000-0000-0000-0000-000000000003")
TXN_BEACON_1 = uuid.UUID("e5000000-0000-0000-0000-000000000005")
TXN_BEACON_2 = uuid.UUID("e5000000-0000-0000-0000-000000000006")
TXN_CIPHER_1 = uuid.UUID("e5000000-0000-0000-0000-000000000008")
TXN_CIPHER_2 = uuid.UUID("e5000000-0000-0000-0000-000000000009")

# Analysis UUIDs
ANL_ATLAS_1 = uuid.UUID("f6000000-0000-0000-0000-000000000001")
ANL_ATLAS_2 = uuid.UUID("f6000000-0000-0000-0000-000000000002")
ANL_ATLAS_3 = uuid.UUID("f6000000-0000-0000-0000-000000000003")
ANL_BEACON_1 = uuid.UUID("f6000000-0000-0000-0000-000000000005")
ANL_BEACON_2 = uuid.UUID("f6000000-0000-0000-0000-000000000006")
ANL_CIPHER_1 = uuid.UUID("f6000000-0000-0000-0000-000000000008")
ANL_CIPHER_2 = uuid.UUID("f6000000-0000-0000-0000-000000000009")

# Base timestamp for seed data - two weeks ago
BASE_DATE = datetime.now(timezone.utc) - timedelta(days=14)


def _ts(days_offset: int = 0, hours_offset: int = 0) -> datetime:
    """Return a timezone-aware timestamp relative to BASE_DATE."""
    return BASE_DATE + timedelta(days=days_offset, hours=hours_offset)


# ── Organizations ─────────────────────────────────────────────────────────
ORGANIZATIONS = [
    Organization(
        id=ORG1_ID,
        name="Meridian Capital Partners",
        slug="meridian-capital",
        domain="meridiancapital.com",
        settings={
            "default_deal_type": "m_and_a",
            "ai_features_enabled": True,
            "max_seats": 25,
        },
    ),
    Organization(
        id=ORG2_ID,
        name="Apex Growth Equity",
        slug="apex-growth",
        domain="apexgrowth.com",
        settings={
            "default_deal_type": "pe",
            "ai_features_enabled": True,
            "max_seats": 15,
        },
    ),
]

# ── Users ─────────────────────────────────────────────────────────────────
USERS = [
    User(
        id=USER_SARAH_ID,
        cognito_sub="seed-cognito-sarah-chen-001",
        email="sarah.chen@meridiancapital.com",
        full_name="Sarah Chen",
        avatar_url=None,
        is_active=True,
    ),
    User(
        id=USER_MICHAEL_ID,
        cognito_sub="seed-cognito-michael-torres-002",
        email="michael.torres@meridiancapital.com",
        full_name="Michael Torres",
        avatar_url=None,
        is_active=True,
    ),
    User(
        id=USER_EMILY_ID,
        cognito_sub="seed-cognito-emily-park-003",
        email="emily.park@meridiancapital.com",
        full_name="Emily Park",
        avatar_url=None,
        is_active=True,
    ),
    User(
        id=USER_JAMES_ID,
        cognito_sub="seed-cognito-james-whitfield-004",
        email="james.whitfield@meridiancapital.com",
        full_name="James Whitfield",
        avatar_url=None,
        is_active=True,
    ),
]

# ── Org Memberships ──────────────────────────────────────────────────────
ORG_MEMBERSHIPS = [
    OrgMembership(org_id=ORG1_ID, user_id=USER_SARAH_ID,   role="owner"),
    OrgMembership(org_id=ORG1_ID, user_id=USER_MICHAEL_ID, role="admin"),
    OrgMembership(org_id=ORG1_ID, user_id=USER_EMILY_ID,   role="member"),
    OrgMembership(org_id=ORG1_ID, user_id=USER_JAMES_ID,   role="member"),
    OrgMembership(org_id=ORG2_ID, user_id=USER_SARAH_ID,   role="owner"),
    OrgMembership(org_id=ORG2_ID, user_id=USER_JAMES_ID,   role="member"),
]

# ── Deals ────────────────────────────────────────────────────────────────
DEALS = [
    Deal(
        id=DEAL_ATLAS_ID,
        org_id=ORG1_ID,
        name="Project Atlas",
        description=(
            "Strategic acquisition of TechCorp Inc., a leading enterprise SaaS "
            "platform with $45M ARR. Target valuation ~$250M. Acquiring to "
            "expand Meridian portfolio presence in vertical SaaS."
        ),
        target_company="TechCorp Inc.",
        deal_type="m_and_a",
        stage="due_diligence",
        status="active",
        created_by=USER_SARAH_ID,
    ),
    Deal(
        id=DEAL_BEACON_ID,
        org_id=ORG1_ID,
        name="Project Beacon",
        description=(
            "Growth equity investment in GreenEnergy Co, a Series C clean-tech "
            "company specializing in commercial solar panel manufacturing. "
            "Targeting $75M minority stake to fund international expansion."
        ),
        target_company="GreenEnergy Co",
        deal_type="pe",
        stage="preliminary_review",
        status="active",
        created_by=USER_MICHAEL_ID,
    ),
    Deal(
        id=DEAL_CIPHER_ID,
        org_id=ORG1_ID,
        name="Project Cipher",
        description=(
            "Series B financing for DataFlow Analytics, an AI-powered business "
            "intelligence startup. $30M round led by Meridian. Company has "
            "demonstrated 3x YoY revenue growth with 120% net dollar retention."
        ),
        target_company="DataFlow Analytics",
        deal_type="vc",
        stage="closed",
        status="closed_won",
        created_by=USER_SARAH_ID,
    ),
]

# ── Deal Memberships ─────────────────────────────────────────────────────
DEAL_MEMBERSHIPS = [
    # Project Atlas
    DealMembership(deal_id=DEAL_ATLAS_ID, user_id=USER_SARAH_ID, org_id=ORG1_ID, role=DealRole.LEAD, added_by=USER_SARAH_ID),
    DealMembership(deal_id=DEAL_ATLAS_ID, user_id=USER_MICHAEL_ID, org_id=ORG1_ID, role=DealRole.ADMIN, added_by=USER_SARAH_ID),
    DealMembership(deal_id=DEAL_ATLAS_ID, user_id=USER_EMILY_ID, org_id=ORG1_ID, role=DealRole.ANALYST, added_by=USER_SARAH_ID),
    DealMembership(deal_id=DEAL_ATLAS_ID, user_id=USER_JAMES_ID, org_id=ORG1_ID, role=DealRole.VIEWER, added_by=USER_MICHAEL_ID),
    # Project Beacon
    DealMembership(deal_id=DEAL_BEACON_ID, user_id=USER_MICHAEL_ID, org_id=ORG1_ID, role=DealRole.LEAD, added_by=USER_MICHAEL_ID),
    DealMembership(deal_id=DEAL_BEACON_ID, user_id=USER_EMILY_ID, org_id=ORG1_ID, role=DealRole.ANALYST, added_by=USER_MICHAEL_ID),
    DealMembership(deal_id=DEAL_BEACON_ID, user_id=USER_SARAH_ID, org_id=ORG1_ID, role=DealRole.ADMIN, added_by=USER_MICHAEL_ID),
    # Project Cipher
    DealMembership(deal_id=DEAL_CIPHER_ID, user_id=USER_SARAH_ID, org_id=ORG1_ID, role=DealRole.LEAD, added_by=USER_SARAH_ID),
    DealMembership(deal_id=DEAL_CIPHER_ID, user_id=USER_MICHAEL_ID, org_id=ORG1_ID, role=DealRole.ADMIN, added_by=USER_SARAH_ID),
    DealMembership(deal_id=DEAL_CIPHER_ID, user_id=USER_EMILY_ID, org_id=ORG1_ID, role=DealRole.ANALYST, added_by=USER_SARAH_ID),
    DealMembership(deal_id=DEAL_CIPHER_ID, user_id=USER_JAMES_ID, org_id=ORG1_ID, role=DealRole.VIEWER, added_by=USER_SARAH_ID),
]

# ── Meetings ─────────────────────────────────────────────────────────────
MEETINGS = [
    # --- Project Atlas meetings ---
    Meeting(
        id=MTG_ATLAS_1, deal_id=DEAL_ATLAS_ID, org_id=ORG1_ID,
        title="TechCorp Management Presentation",
        meeting_date=_ts(days_offset=0, hours_offset=10),
        duration_seconds=5400,
        source="zoom", status="ready", created_by=USER_SARAH_ID,
    ),
    Meeting(
        id=MTG_ATLAS_2, deal_id=DEAL_ATLAS_ID, org_id=ORG1_ID,
        title="TechCorp Financial Due Diligence - Day 1",
        meeting_date=_ts(days_offset=2, hours_offset=9),
        duration_seconds=7200,
        source="teams", status="ready", created_by=USER_EMILY_ID,
    ),
    Meeting(
        id=MTG_ATLAS_3, deal_id=DEAL_ATLAS_ID, org_id=ORG1_ID,
        title="Atlas Deal Team Sync - Valuation Review",
        meeting_date=_ts(days_offset=5, hours_offset=14),
        duration_seconds=3600,
        source="zoom", status="ready", created_by=USER_MICHAEL_ID,
    ),
    Meeting(
        id=MTG_ATLAS_4, deal_id=DEAL_ATLAS_ID, org_id=ORG1_ID,
        title="TechCorp CTO Technical Deep-Dive",
        meeting_date=_ts(days_offset=7, hours_offset=11),
        duration_seconds=4500,
        source="zoom", status="transcribing", created_by=USER_SARAH_ID,
    ),
    # --- Project Beacon meetings ---
    Meeting(
        id=MTG_BEACON_1, deal_id=DEAL_BEACON_ID, org_id=ORG1_ID,
        title="GreenEnergy Co Introductory Call",
        meeting_date=_ts(days_offset=1, hours_offset=15),
        duration_seconds=2700,
        source="zoom", status="ready", created_by=USER_MICHAEL_ID,
    ),
    Meeting(
        id=MTG_BEACON_2, deal_id=DEAL_BEACON_ID, org_id=ORG1_ID,
        title="GreenEnergy Co - Market Analysis Discussion",
        meeting_date=_ts(days_offset=4, hours_offset=10),
        duration_seconds=3600,
        source="teams", status="ready", created_by=USER_EMILY_ID,
    ),
    Meeting(
        id=MTG_BEACON_3, deal_id=DEAL_BEACON_ID, org_id=ORG1_ID,
        title="Beacon Investment Committee Pre-Read",
        meeting_date=_ts(days_offset=8, hours_offset=16),
        duration_seconds=1800,
        source="upload", status="analyzing", created_by=USER_MICHAEL_ID,
    ),
    # --- Project Cipher meetings ---
    Meeting(
        id=MTG_CIPHER_1, deal_id=DEAL_CIPHER_ID, org_id=ORG1_ID,
        title="DataFlow Analytics - Founder Pitch",
        meeting_date=_ts(days_offset=-30, hours_offset=10),
        duration_seconds=3600,
        source="zoom", status="ready", created_by=USER_SARAH_ID,
    ),
    Meeting(
        id=MTG_CIPHER_2, deal_id=DEAL_CIPHER_ID, org_id=ORG1_ID,
        title="DataFlow Series B Term Sheet Negotiation",
        meeting_date=_ts(days_offset=-20, hours_offset=14),
        duration_seconds=5400,
        source="zoom", status="ready", created_by=USER_SARAH_ID,
    ),
]

# ── Documents ────────────────────────────────────────────────────────────
DOCUMENTS = [
    Document(deal_id=DEAL_ATLAS_ID, org_id=ORG1_ID, title="TechCorp - Confidential Information Memorandum", document_type="pdf", file_key="orgs/meridian-capital/deals/atlas/docs/techcorp_cim_2025.pdf", file_size=4_850_000, uploaded_by=USER_SARAH_ID),
    Document(deal_id=DEAL_ATLAS_ID, org_id=ORG1_ID, title="TechCorp - Financial Model v3.2", document_type="xlsx", file_key="orgs/meridian-capital/deals/atlas/docs/techcorp_financial_model_v3.2.xlsx", file_size=2_100_000, uploaded_by=USER_EMILY_ID),
    Document(deal_id=DEAL_ATLAS_ID, org_id=ORG1_ID, title="Project Atlas - Investment Committee Deck", document_type="pptx", file_key="orgs/meridian-capital/deals/atlas/docs/atlas_ic_deck_final.pptx", file_size=8_750_000, uploaded_by=USER_MICHAEL_ID),
    Document(deal_id=DEAL_ATLAS_ID, org_id=ORG1_ID, title="TechCorp - Quality of Earnings Report (Draft)", document_type="pdf", file_key="orgs/meridian-capital/deals/atlas/docs/techcorp_qoe_draft.pdf", file_size=3_200_000, uploaded_by=USER_EMILY_ID),
    Document(deal_id=DEAL_BEACON_ID, org_id=ORG1_ID, title="GreenEnergy Co - Company Overview Pitch Deck", document_type="pptx", file_key="orgs/meridian-capital/deals/beacon/docs/greenenergy_pitch_deck.pptx", file_size=6_400_000, uploaded_by=USER_MICHAEL_ID),
    Document(deal_id=DEAL_BEACON_ID, org_id=ORG1_ID, title="GreenEnergy Co - 3-Year Financial Projections", document_type="xlsx", file_key="orgs/meridian-capital/deals/beacon/docs/greenenergy_projections_2025_2028.xlsx", file_size=1_350_000, uploaded_by=USER_EMILY_ID),
    Document(deal_id=DEAL_BEACON_ID, org_id=ORG1_ID, title="Commercial Solar Market Research Report", document_type="pdf", file_key="orgs/meridian-capital/deals/beacon/docs/solar_market_research_2025.pdf", file_size=5_600_000, uploaded_by=USER_EMILY_ID),
    Document(deal_id=DEAL_CIPHER_ID, org_id=ORG1_ID, title="DataFlow Analytics - Series B Pitch Deck", document_type="pptx", file_key="orgs/meridian-capital/deals/cipher/docs/dataflow_series_b_deck.pptx", file_size=5_200_000, uploaded_by=USER_SARAH_ID),
    Document(deal_id=DEAL_CIPHER_ID, org_id=ORG1_ID, title="DataFlow Analytics - Executed Term Sheet", document_type="pdf", file_key="orgs/meridian-capital/deals/cipher/docs/dataflow_term_sheet_executed.pdf", file_size=420_000, uploaded_by=USER_SARAH_ID),
    Document(deal_id=DEAL_CIPHER_ID, org_id=ORG1_ID, title="DataFlow Analytics - Product Roadmap & TAM Analysis", document_type="pdf", file_key="orgs/meridian-capital/deals/cipher/docs/dataflow_product_tam_analysis.pdf", file_size=1_800_000, uploaded_by=USER_SARAH_ID),
]

# ── Meeting Participants ─────────────────────────────────────────────────
PARTICIPANTS = [
    # Atlas Meeting 1 - Management Presentation
    MeetingParticipant(meeting_id=MTG_ATLAS_1, speaker_label="Speaker 0", speaker_name="Sarah Chen", user_id=USER_SARAH_ID),
    MeetingParticipant(meeting_id=MTG_ATLAS_1, speaker_label="Speaker 1", speaker_name="David Kim"),
    MeetingParticipant(meeting_id=MTG_ATLAS_1, speaker_label="Speaker 2", speaker_name="Lisa Wang"),
    MeetingParticipant(meeting_id=MTG_ATLAS_1, speaker_label="Speaker 3", speaker_name="Emily Park", user_id=USER_EMILY_ID),
    # Atlas Meeting 2 - Financial DD
    MeetingParticipant(meeting_id=MTG_ATLAS_2, speaker_label="Speaker 0", speaker_name="Emily Park", user_id=USER_EMILY_ID),
    MeetingParticipant(meeting_id=MTG_ATLAS_2, speaker_label="Speaker 1", speaker_name="Robert Chen"),
    MeetingParticipant(meeting_id=MTG_ATLAS_2, speaker_label="Speaker 2", speaker_name="Amanda Foster"),
    # Atlas Meeting 3 - Valuation Review
    MeetingParticipant(meeting_id=MTG_ATLAS_3, speaker_label="Speaker 0", speaker_name="Michael Torres", user_id=USER_MICHAEL_ID),
    MeetingParticipant(meeting_id=MTG_ATLAS_3, speaker_label="Speaker 1", speaker_name="Sarah Chen", user_id=USER_SARAH_ID),
    MeetingParticipant(meeting_id=MTG_ATLAS_3, speaker_label="Speaker 2", speaker_name="Emily Park", user_id=USER_EMILY_ID),
    # Beacon Meeting 1 - Introductory Call
    MeetingParticipant(meeting_id=MTG_BEACON_1, speaker_label="Speaker 0", speaker_name="Michael Torres", user_id=USER_MICHAEL_ID),
    MeetingParticipant(meeting_id=MTG_BEACON_1, speaker_label="Speaker 1", speaker_name="Rachel Martinez"),
    MeetingParticipant(meeting_id=MTG_BEACON_1, speaker_label="Speaker 2", speaker_name="Tom Henderson"),
    # Beacon Meeting 2 - Market Analysis
    MeetingParticipant(meeting_id=MTG_BEACON_2, speaker_label="Speaker 0", speaker_name="Emily Park", user_id=USER_EMILY_ID),
    MeetingParticipant(meeting_id=MTG_BEACON_2, speaker_label="Speaker 1", speaker_name="Rachel Martinez"),
    MeetingParticipant(meeting_id=MTG_BEACON_2, speaker_label="Speaker 2", speaker_name="Michael Torres", user_id=USER_MICHAEL_ID),
    # Cipher Meeting 1 - Founder Pitch
    MeetingParticipant(meeting_id=MTG_CIPHER_1, speaker_label="Speaker 0", speaker_name="Sarah Chen", user_id=USER_SARAH_ID),
    MeetingParticipant(meeting_id=MTG_CIPHER_1, speaker_label="Speaker 1", speaker_name="Alex Rivera"),
    MeetingParticipant(meeting_id=MTG_CIPHER_1, speaker_label="Speaker 2", speaker_name="Priya Sharma"),
    # Cipher Meeting 2 - Term Sheet
    MeetingParticipant(meeting_id=MTG_CIPHER_2, speaker_label="Speaker 0", speaker_name="Sarah Chen", user_id=USER_SARAH_ID),
    MeetingParticipant(meeting_id=MTG_CIPHER_2, speaker_label="Speaker 1", speaker_name="Alex Rivera"),
    MeetingParticipant(meeting_id=MTG_CIPHER_2, speaker_label="Speaker 2", speaker_name="James Whitfield", user_id=USER_JAMES_ID),
]


# ── Transcript Segment Data ─────────────────────────────────────────────

def _atlas_mgmt_pres_segments():
    return [
        {"speaker_label": "Speaker 0", "speaker_name": "Sarah Chen", "text": "Good morning everyone, thank you for joining. We're here today to hear TechCorp's management presentation. David, Lisa, thank you for making time for us.", "start_time": 0.0, "end_time": 12.5, "confidence": 0.96, "segment_index": 0},
        {"speaker_label": "Speaker 1", "speaker_name": "David Kim", "text": "Thank you Sarah. We're excited to walk you through TechCorp's business, our growth trajectory, and why we believe this is the right time for a strategic partnership.", "start_time": 13.0, "end_time": 24.3, "confidence": 0.95, "segment_index": 1},
        {"speaker_label": "Speaker 1", "speaker_name": "David Kim", "text": "Let me start with an overview. TechCorp is an enterprise SaaS platform focused on supply chain management for mid-market manufacturers. We currently serve over 340 enterprise clients with an ARR of $45 million as of last quarter.", "start_time": 25.0, "end_time": 42.8, "confidence": 0.97, "segment_index": 2},
        {"speaker_label": "Speaker 2", "speaker_name": "Lisa Wang", "text": "If I can add some color to the financial picture, our gross margins are at 78% and have been improving quarter over quarter. We've seen net revenue retention of 118% driven by our platform expansion strategy with existing clients.", "start_time": 43.5, "end_time": 61.2, "confidence": 0.94, "segment_index": 3},
        {"speaker_label": "Speaker 0", "speaker_name": "Sarah Chen", "text": "That's impressive retention. Can you walk us through the key drivers of the expansion revenue? Are these seat-based expansions or module additions?", "start_time": 62.0, "end_time": 72.5, "confidence": 0.98, "segment_index": 4},
        {"speaker_label": "Speaker 1", "speaker_name": "David Kim", "text": "Great question. It's primarily module-based expansion. When clients onboard, they typically start with our core supply chain visibility module. Over the first 12 to 18 months, about 65% of them add our predictive analytics and demand forecasting modules, which roughly doubles their ACV.", "start_time": 73.0, "end_time": 95.7, "confidence": 0.96, "segment_index": 5},
        {"speaker_label": "Speaker 3", "speaker_name": "Emily Park", "text": "David, what does the competitive landscape look like? Who are you losing deals to, and how do win rates trend?", "start_time": 96.5, "end_time": 105.2, "confidence": 0.95, "segment_index": 6},
        {"speaker_label": "Speaker 1", "speaker_name": "David Kim", "text": "Our primary competitors are Oracle SCM Cloud and SAP IBP in the enterprise segment, and Kinaxis and Blue Yonder in the mid-market. Our win rate against these competitors has been around 42% in competitive deals, up from 35% two years ago. Our key differentiator is our AI-driven demand sensing, which consistently outperforms in proof-of-concept evaluations.", "start_time": 106.0, "end_time": 136.4, "confidence": 0.93, "segment_index": 7},
        {"speaker_label": "Speaker 2", "speaker_name": "Lisa Wang", "text": "On the financial side, I want to highlight our unit economics. Our CAC payback period is 14 months, LTV to CAC ratio is 5.2x, and we've achieved Rule of 40 compliance for the past three consecutive quarters, combining our 28% growth rate with 15% free cash flow margin.", "start_time": 137.0, "end_time": 162.8, "confidence": 0.95, "segment_index": 8},
        {"speaker_label": "Speaker 0", "speaker_name": "Sarah Chen", "text": "Those are strong unit economics. Lisa, can you elaborate on the path to profitability? What does the cost structure look like, and where are the key leverage points?", "start_time": 163.5, "end_time": 176.3, "confidence": 0.97, "segment_index": 9},
        {"speaker_label": "Speaker 2", "speaker_name": "Lisa Wang", "text": "Sure. Our biggest cost center is R&D at about 32% of revenue, followed by sales and marketing at 28%. We expect R&D to normalize to about 25% as we complete our platform migration to microservices. Sales efficiency is improving as the brand gets stronger in our target verticals. We believe we can reach 20% EBITDA margins within 18 months.", "start_time": 177.0, "end_time": 210.5, "confidence": 0.94, "segment_index": 10},
        {"speaker_label": "Speaker 1", "speaker_name": "David Kim", "text": "I also want to touch on our product roadmap. We're investing heavily in generative AI capabilities for automated report generation and anomaly detection. Early beta results show that clients using these features see a 40% reduction in manual supply chain disruption response time.", "start_time": 211.0, "end_time": 236.2, "confidence": 0.96, "segment_index": 11},
        {"speaker_label": "Speaker 3", "speaker_name": "Emily Park", "text": "What's the customer concentration risk? How much of your ARR comes from the top 10 accounts?", "start_time": 237.0, "end_time": 244.5, "confidence": 0.98, "segment_index": 12},
        {"speaker_label": "Speaker 2", "speaker_name": "Lisa Wang", "text": "Top 10 accounts represent about 22% of our total ARR, with our largest single customer at 3.8%. We've been intentionally diversifying our customer base over the past two years. No single industry vertical represents more than 30% of revenue.", "start_time": 245.0, "end_time": 266.3, "confidence": 0.95, "segment_index": 13},
        {"speaker_label": "Speaker 0", "speaker_name": "Sarah Chen", "text": "This is very helpful. Let's talk about the team. What does the leadership bench look like, and are there any key person dependencies we should be aware of?", "start_time": 267.0, "end_time": 278.8, "confidence": 0.97, "segment_index": 14},
        {"speaker_label": "Speaker 1", "speaker_name": "David Kim", "text": "We have a strong leadership team with an average tenure of four years. Our VP of Engineering, CTO, and VP of Product have all been with us since Series A. We recently brought on a new CMO from Salesforce who has been instrumental in repositioning our brand. The only area I'd flag is that our VP of Sales is relatively new, about 8 months in, and we're still building out the enterprise sales team.", "start_time": 279.5, "end_time": 315.7, "confidence": 0.93, "segment_index": 15},
    ]


def _atlas_financial_dd_segments():
    return [
        {"speaker_label": "Speaker 0", "speaker_name": "Emily Park", "text": "Let's dive into the financials. Robert, we've reviewed the historical P&L data you shared. Can you walk us through the revenue recognition methodology?", "start_time": 0.0, "end_time": 14.2, "confidence": 0.96, "segment_index": 0},
        {"speaker_label": "Speaker 1", "speaker_name": "Robert Chen", "text": "Of course. We follow ASC 606 for revenue recognition. Our contracts are typically annual subscriptions billed upfront or quarterly. Revenue is recognized ratably over the contract period. Professional services revenue, which represents about 12% of total revenue, is recognized as services are performed.", "start_time": 15.0, "end_time": 38.6, "confidence": 0.97, "segment_index": 1},
        {"speaker_label": "Speaker 2", "speaker_name": "Amanda Foster", "text": "I want to highlight an important adjustment we identified. There are approximately $2.3 million in non-recurring expenses related to the office relocation and a one-time ERP implementation that should be normalized out of the EBITDA figure.", "start_time": 39.0, "end_time": 57.4, "confidence": 0.95, "segment_index": 2},
        {"speaker_label": "Speaker 0", "speaker_name": "Emily Park", "text": "Can we see a bridge from reported EBITDA to adjusted EBITDA? I want to make sure we're capturing all the add-backs correctly.", "start_time": 58.0, "end_time": 68.1, "confidence": 0.98, "segment_index": 3},
        {"speaker_label": "Speaker 1", "speaker_name": "Robert Chen", "text": "Absolutely. Starting from reported EBITDA of $4.8 million, we add back the $2.3 million in one-time items, $850K in stock-based compensation true-ups, and $400K in founder bonuses that are above market. That gets us to an adjusted EBITDA of approximately $8.35 million, or about an 18.5% adjusted EBITDA margin.", "start_time": 69.0, "end_time": 98.5, "confidence": 0.94, "segment_index": 4},
        {"speaker_label": "Speaker 0", "speaker_name": "Emily Park", "text": "That's helpful. Let me also ask about the deferred revenue balance. It looks like it grew 35% year over year. Is that entirely from new bookings, or is there a pricing component?", "start_time": 99.0, "end_time": 113.7, "confidence": 0.96, "segment_index": 5},
        {"speaker_label": "Speaker 1", "speaker_name": "Robert Chen", "text": "It's a combination. About 60% of the growth is from new customer acquisitions, 25% from expansion within existing accounts, and the remaining 15% is from a price increase we implemented in Q3 last year, roughly 8% across the board on renewals.", "start_time": 114.5, "end_time": 137.2, "confidence": 0.95, "segment_index": 6},
        {"speaker_label": "Speaker 2", "speaker_name": "Amanda Foster", "text": "One area that needs further diligence is the accounts receivable aging. We noticed that DSO increased from 38 days to 52 days in the last two quarters. Robert, can you explain what's driving that?", "start_time": 138.0, "end_time": 155.8, "confidence": 0.93, "segment_index": 7},
        {"speaker_label": "Speaker 1", "speaker_name": "Robert Chen", "text": "Yes, that's primarily due to two large enterprise deals that have extended payment terms of net-90 as part of their negotiated contracts. These are both Fortune 500 companies with strong credit profiles. We don't see collectibility risk, but I understand the optics. Excluding those two contracts, our DSO is actually 41 days, which is in line with historical trends.", "start_time": 156.5, "end_time": 186.3, "confidence": 0.94, "segment_index": 8},
        {"speaker_label": "Speaker 0", "speaker_name": "Emily Park", "text": "Let's move to the balance sheet. Cash position is $18.2 million. Are there any outstanding credit facilities or debt obligations we should know about?", "start_time": 187.0, "end_time": 199.4, "confidence": 0.97, "segment_index": 9},
        {"speaker_label": "Speaker 1", "speaker_name": "Robert Chen", "text": "We have a $10 million revolving credit facility with Silicon Valley Bank, of which $3 million is currently drawn. The interest rate is SOFR plus 200 basis points. No other material debt. We also have standard capital lease obligations for our server infrastructure totaling about $1.2 million.", "start_time": 200.0, "end_time": 224.6, "confidence": 0.96, "segment_index": 10},
    ]


def _atlas_valuation_segments():
    return [
        {"speaker_label": "Speaker 0", "speaker_name": "Michael Torres", "text": "Alright team, let's review where we are on the Atlas valuation. Emily, can you walk us through the updated model?", "start_time": 0.0, "end_time": 10.5, "confidence": 0.97, "segment_index": 0},
        {"speaker_label": "Speaker 2", "speaker_name": "Emily Park", "text": "Sure. Based on the financial DD findings, I've built out three scenarios. Our base case assumes 25% revenue growth, gross margin improvement to 80%, and operating leverage bringing EBITDA margins to 22% by year three. That gives us an implied TEV of $225 million to $260 million on a DCF basis.", "start_time": 11.0, "end_time": 38.4, "confidence": 0.95, "segment_index": 1},
        {"speaker_label": "Speaker 1", "speaker_name": "Sarah Chen", "text": "And on a comps basis? Where does that put us relative to the peer set?", "start_time": 39.0, "end_time": 45.2, "confidence": 0.98, "segment_index": 2},
        {"speaker_label": "Speaker 2", "speaker_name": "Emily Park", "text": "Looking at public SaaS comps in the supply chain vertical, the median EV to NTM revenue multiple is 7.2x. Applying that to TechCorp's forward revenue estimate of $56 million gives us $403 million on the high end. But I think we should apply a 25 to 30% private company discount, which brings us to the $280 to $310 million range.", "start_time": 46.0, "end_time": 74.8, "confidence": 0.94, "segment_index": 3},
        {"speaker_label": "Speaker 0", "speaker_name": "Michael Torres", "text": "That's a wide range. Sarah, based on your conversations with the founders, where do you think they're anchored on price?", "start_time": 75.5, "end_time": 85.3, "confidence": 0.96, "segment_index": 4},
        {"speaker_label": "Speaker 1", "speaker_name": "Sarah Chen", "text": "David hinted at $250 million as their floor. They received an IOI from a strategic buyer at what I believe was in the $270 million range, but they preferred our partnership structure. I think we can close at $245 to $255 million if we offer favorable terms on the earnout structure.", "start_time": 86.0, "end_time": 112.7, "confidence": 0.93, "segment_index": 5},
        {"speaker_label": "Speaker 0", "speaker_name": "Michael Torres", "text": "That would be roughly 5.5x NTM revenue, which is attractive for a business with these unit economics. Let's structure the earnout around hitting $60 million ARR within 24 months. That aligns incentives and bridges the valuation gap.", "start_time": 113.5, "end_time": 133.2, "confidence": 0.95, "segment_index": 6},
        {"speaker_label": "Speaker 2", "speaker_name": "Emily Park", "text": "I'll update the model with that structure. One thing I want to flag is the working capital adjustment. Based on my DD, I think we should target a net working capital peg of $4.5 million, which is roughly at the trailing 12-month average. Any deviation should be dollar-for-dollar adjusted at close.", "start_time": 134.0, "end_time": 158.6, "confidence": 0.94, "segment_index": 7},
        {"speaker_label": "Speaker 1", "speaker_name": "Sarah Chen", "text": "Agreed. Let's also make sure our LOI includes standard rep and warranty insurance. I want to keep the indemnification basket clean. Michael, can you coordinate with legal on the draft?", "start_time": 159.0, "end_time": 174.4, "confidence": 0.97, "segment_index": 8},
        {"speaker_label": "Speaker 0", "speaker_name": "Michael Torres", "text": "Will do. I'll have a draft LOI ready by Thursday. Emily, please finalize the sensitivity analysis and have the IC memo updated by end of week. Let's target the Investment Committee meeting for next Tuesday.", "start_time": 175.0, "end_time": 194.8, "confidence": 0.96, "segment_index": 9},
    ]


def _beacon_intro_segments():
    return [
        {"speaker_label": "Speaker 0", "speaker_name": "Michael Torres", "text": "Rachel, Tom, thank you for taking the time today. We've been tracking GreenEnergy's progress in the commercial solar space and we're very interested in learning more.", "start_time": 0.0, "end_time": 13.5, "confidence": 0.96, "segment_index": 0},
        {"speaker_label": "Speaker 1", "speaker_name": "Rachel Martinez", "text": "Thank you Michael. We're excited about the conversation. GreenEnergy is at an inflection point. We've grown from $28 million to $85 million in revenue over the past three years, and we see a clear path to $200 million within the next 24 months with the right capital partner.", "start_time": 14.0, "end_time": 35.7, "confidence": 0.95, "segment_index": 1},
        {"speaker_label": "Speaker 2", "speaker_name": "Tom Henderson", "text": "From an operations perspective, we've just completed our second manufacturing facility in Arizona which doubles our production capacity to 2.4 gigawatts annually. The IRA tax credits have been a significant tailwind, and our order backlog is at an all-time high of $120 million.", "start_time": 36.5, "end_time": 60.2, "confidence": 0.94, "segment_index": 2},
        {"speaker_label": "Speaker 0", "speaker_name": "Michael Torres", "text": "That's impressive growth. Can you help us understand the unit economics of your manufacturing? What are your fully loaded costs per watt, and how does that compare to Chinese imports?", "start_time": 61.0, "end_time": 74.8, "confidence": 0.97, "segment_index": 3},
        {"speaker_label": "Speaker 1", "speaker_name": "Rachel Martinez", "text": "Our current cost per watt for our premium commercial panels is $0.32, compared to about $0.22 for Chinese imports. However, with the Section 45X manufacturing credit, our effective cost drops to $0.25. Our panels also carry a 30-year performance warranty and higher efficiency ratings, which justifies a 15 to 20% price premium with commercial customers.", "start_time": 75.5, "end_time": 108.3, "confidence": 0.93, "segment_index": 4},
        {"speaker_label": "Speaker 0", "speaker_name": "Michael Torres", "text": "What does the competitive landscape look like domestically? And how protected are you if the IRA incentives change?", "start_time": 109.0, "end_time": 118.5, "confidence": 0.96, "segment_index": 5},
        {"speaker_label": "Speaker 2", "speaker_name": "Tom Henderson", "text": "There are about six domestic competitors of scale. Our differentiation is in the commercial and industrial segment specifically, where we have the highest efficiency panels for rooftop installations. Regarding the IRA, we model scenarios with and without the credits. Even without IRA support, we'd still be profitable at current volumes, though margins would compress from 35% to about 22%.", "start_time": 119.0, "end_time": 152.4, "confidence": 0.94, "segment_index": 6},
        {"speaker_label": "Speaker 0", "speaker_name": "Michael Torres", "text": "How are you thinking about the $75 million raise? What's the intended use of funds?", "start_time": 153.0, "end_time": 161.2, "confidence": 0.98, "segment_index": 7},
        {"speaker_label": "Speaker 1", "speaker_name": "Rachel Martinez", "text": "Three primary uses. First, $30 million for our third manufacturing facility in North Carolina which will add another 1.5 gigawatts of capacity. Second, $25 million for international expansion, starting with Germany and Australia where we already have LOIs. And third, $20 million for working capital to support the growing order backlog.", "start_time": 162.0, "end_time": 192.7, "confidence": 0.95, "segment_index": 8},
    ]


def _beacon_market_analysis_segments():
    return [
        {"speaker_label": "Speaker 0", "speaker_name": "Emily Park", "text": "I've completed the initial market sizing analysis for the commercial solar segment. Rachel, I'd like to walk through our findings and get your perspective on a few assumptions.", "start_time": 0.0, "end_time": 14.3, "confidence": 0.96, "segment_index": 0},
        {"speaker_label": "Speaker 1", "speaker_name": "Rachel Martinez", "text": "Of course. We've done extensive market research internally as well, so happy to compare notes.", "start_time": 15.0, "end_time": 22.5, "confidence": 0.97, "segment_index": 1},
        {"speaker_label": "Speaker 0", "speaker_name": "Emily Park", "text": "Our estimate for the total US commercial solar TAM is approximately $18 billion by 2027, growing at a 22% CAGR. We estimate GreenEnergy's serviceable addressable market at about $4.2 billion, focused on the premium commercial rooftop segment. Does that align with your internal estimates?", "start_time": 23.0, "end_time": 47.8, "confidence": 0.94, "segment_index": 2},
        {"speaker_label": "Speaker 1", "speaker_name": "Rachel Martinez", "text": "That's very close to our numbers. We have the TAM at $19 billion and our SAM slightly higher at $4.8 billion because we include the emerging agrivoltaics segment, which we see as a natural extension of our commercial panel technology.", "start_time": 48.5, "end_time": 68.3, "confidence": 0.95, "segment_index": 3},
        {"speaker_label": "Speaker 2", "speaker_name": "Michael Torres", "text": "Emily, what's the market share trajectory look like? If they hit the $200 million revenue target, what does that imply for market position?", "start_time": 69.0, "end_time": 79.2, "confidence": 0.96, "segment_index": 4},
        {"speaker_label": "Speaker 0", "speaker_name": "Emily Park", "text": "At $200 million revenue, GreenEnergy would hold roughly a 4.2% share of the SAM. Top three competitors currently hold about 35% combined, so there's significant room for share gains. The fragmented nature of the market is actually an advantage here.", "start_time": 80.0, "end_time": 99.6, "confidence": 0.95, "segment_index": 5},
        {"speaker_label": "Speaker 1", "speaker_name": "Rachel Martinez", "text": "One dynamic I want to highlight is the domestic content bonus under the IRA. Projects using domestically manufactured panels qualify for an additional 10% investment tax credit. This is shifting procurement decisions in our favor. We've seen a 40% increase in inbound inquiries since the domestic content guidance was finalized.", "start_time": 100.0, "end_time": 128.4, "confidence": 0.93, "segment_index": 6},
    ]


def _cipher_founder_pitch_segments():
    return [
        {"speaker_label": "Speaker 0", "speaker_name": "Sarah Chen", "text": "Alex, Priya, welcome. We've been impressed by what we've seen in DataFlow's growth metrics. Let's hear the full story.", "start_time": 0.0, "end_time": 11.2, "confidence": 0.97, "segment_index": 0},
        {"speaker_label": "Speaker 1", "speaker_name": "Alex Rivera", "text": "Thank you Sarah. DataFlow was born out of a frustration Priya and I experienced as data engineers at Stripe. Enterprise BI tools were either too rigid or too complex. We built DataFlow to be the middle ground: AI-powered analytics that any business user can operate without writing SQL.", "start_time": 12.0, "end_time": 36.5, "confidence": 0.95, "segment_index": 1},
        {"speaker_label": "Speaker 2", "speaker_name": "Priya Sharma", "text": "From a technical perspective, our core innovation is what we call semantic data layers. We use large language models to build an understanding of a company's data schema, relationships, and business terminology. Users can then ask questions in natural language, and our system translates that into optimized SQL queries.", "start_time": 37.0, "end_time": 62.8, "confidence": 0.94, "segment_index": 2},
        {"speaker_label": "Speaker 0", "speaker_name": "Sarah Chen", "text": "What do the growth numbers look like? Where are you on ARR, and what's the growth trajectory?", "start_time": 63.5, "end_time": 71.3, "confidence": 0.98, "segment_index": 3},
        {"speaker_label": "Speaker 1", "speaker_name": "Alex Rivera", "text": "We closed last quarter at $12.5 million ARR, up from $4.1 million a year ago. That's roughly 3x year-over-year growth. Our net dollar retention is 120%, meaning existing customers are expanding significantly. We have 180 paying customers across financial services, healthcare, and e-commerce.", "start_time": 72.0, "end_time": 98.4, "confidence": 0.96, "segment_index": 4},
        {"speaker_label": "Speaker 2", "speaker_name": "Priya Sharma", "text": "What makes us confident in the durability of this growth is our product-led motion. About 60% of our new customers come through self-serve trials. The average time from signup to paid conversion is 11 days, and our free-to-paid conversion rate is 18%, which is best-in-class for our category.", "start_time": 99.0, "end_time": 123.7, "confidence": 0.95, "segment_index": 5},
        {"speaker_label": "Speaker 0", "speaker_name": "Sarah Chen", "text": "Impressive metrics. Walk me through the $30 million round. What are the terms you're targeting, and how will you deploy the capital?", "start_time": 124.5, "end_time": 135.2, "confidence": 0.97, "segment_index": 6},
        {"speaker_label": "Speaker 1", "speaker_name": "Alex Rivera", "text": "We're targeting a $150 million pre-money valuation for this round. We plan to use the capital primarily for go-to-market expansion. Specifically, $15 million for building out our enterprise sales team, $8 million for international expansion starting with the UK and Germany, and $7 million for continued R&D investment in our AI capabilities.", "start_time": 136.0, "end_time": 165.3, "confidence": 0.94, "segment_index": 7},
    ]


def _cipher_term_sheet_segments():
    return [
        {"speaker_label": "Speaker 0", "speaker_name": "Sarah Chen", "text": "Alex, we've reviewed the term sheet draft. I want to walk through a few key provisions and see where we can find alignment.", "start_time": 0.0, "end_time": 11.8, "confidence": 0.96, "segment_index": 0},
        {"speaker_label": "Speaker 1", "speaker_name": "Alex Rivera", "text": "Sounds good. We're largely comfortable with the structure. Let me highlight our two main areas of focus: the anti-dilution mechanism and the board composition.", "start_time": 12.5, "end_time": 24.3, "confidence": 0.97, "segment_index": 1},
        {"speaker_label": "Speaker 0", "speaker_name": "Sarah Chen", "text": "On anti-dilution, we proposed broad-based weighted average, which is industry standard for Series B rounds. We're comfortable maintaining that. On board composition, we'd like one Meridian board seat, with the remaining four seats split between two founder seats, one independent, and one for the existing Series A investor.", "start_time": 25.0, "end_time": 52.6, "confidence": 0.95, "segment_index": 2},
        {"speaker_label": "Speaker 1", "speaker_name": "Alex Rivera", "text": "That board structure works for us. The one thing I want to negotiate is the protective provisions. Specifically, I'd like to raise the threshold for transactions requiring investor approval from $500K to $2 million. At our current revenue run rate, $500K is an operational expense level that we shouldn't need board approval for.", "start_time": 53.0, "end_time": 80.4, "confidence": 0.94, "segment_index": 3},
        {"speaker_label": "Speaker 2", "speaker_name": "James Whitfield", "text": "From a governance perspective, I think $1 million is a reasonable middle ground. That gives you operational flexibility while maintaining appropriate oversight for our investment.", "start_time": 81.0, "end_time": 95.7, "confidence": 0.96, "segment_index": 4},
        {"speaker_label": "Speaker 0", "speaker_name": "Sarah Chen", "text": "I agree with James on the $1 million threshold. Alex, can you live with that?", "start_time": 96.0, "end_time": 103.2, "confidence": 0.98, "segment_index": 5},
        {"speaker_label": "Speaker 1", "speaker_name": "Alex Rivera", "text": "Yes, $1 million works for us. Let's also discuss the information rights. We're prepared to provide quarterly financials and annual audited statements. We'd prefer to push the monthly financial package requirement to after we hit $25 million ARR, when we'll have the finance team infrastructure to support that cadence.", "start_time": 104.0, "end_time": 132.5, "confidence": 0.93, "segment_index": 6},
        {"speaker_label": "Speaker 0", "speaker_name": "Sarah Chen", "text": "That's reasonable. Let's document quarterly financials now with monthly reporting kicking in at $25 million ARR or 18 months post-close, whichever comes first. I think we have the framework of a deal here. I'll have our counsel draft the final term sheet incorporating these changes, and we can target signing by end of next week.", "start_time": 133.0, "end_time": 162.8, "confidence": 0.95, "segment_index": 7},
    ]


# ── Analysis Structured Output ───────────────────────────────────────────

ANALYSIS_ATLAS_MGMT_PRES = {
    "summary": "TechCorp management presented a compelling overview of their enterprise SaaS platform for supply chain management. Key highlights include $45M ARR with 78% gross margins and 118% net revenue retention. The company demonstrated strong unit economics with a 14-month CAC payback and 5.2x LTV/CAC ratio. Management outlined a clear path to 20% EBITDA margins within 18 months through R&D normalization and sales efficiency improvements.",
    "key_takeaways": ["ARR of $45M with 78% gross margins and improving", "Net revenue retention of 118% driven by module-based expansion", "Win rate of 42% against Oracle, SAP, Kinaxis, and Blue Yonder", "CAC payback of 14 months with 5.2x LTV/CAC ratio", "Customer concentration manageable: top 10 accounts at 22% of ARR", "Strong leadership team with average 4-year tenure, new VP Sales a potential risk", "AI product roadmap showing 40% improvement in supply chain response times"],
    "risks_identified": ["New VP of Sales (8 months) still building enterprise team", "R&D spend at 32% of revenue is above peer median", "Competitive pressure from Oracle SCM Cloud and SAP IBP in enterprise segment", "Product roadmap heavily dependent on generative AI capabilities"],
    "action_items": [{"item": "Request customer reference calls for top 5 accounts", "owner": "Emily Park", "due": "Next week"}, {"item": "Evaluate VP of Sales pipeline and quota attainment data", "owner": "Michael Torres", "due": "Before LOI"}, {"item": "Commission independent technical assessment of AI roadmap", "owner": "Sarah Chen", "due": "During DD"}, {"item": "Benchmark R&D spend against peer set for normalization analysis", "owner": "Emily Park", "due": "This week"}],
    "sentiment": "positive",
    "confidence_score": 0.88,
}

ANALYSIS_ATLAS_FIN_DD = {
    "summary": "Financial due diligence session covered TechCorp's revenue recognition practices (ASC 606), adjusted EBITDA bridge, and balance sheet composition. Adjusted EBITDA of $8.35M (18.5% margin) after normalizing $2.3M in one-time charges and $1.25M in other add-backs. Deferred revenue growth of 35% YoY from new customer acquisition (60%), expansion (25%), and pricing (15%). DSO increase from 38 to 52 days explained by two large enterprise contracts with net-90 terms.",
    "key_takeaways": ["Adjusted EBITDA of $8.35M representing 18.5% margin", "Non-recurring items of $2.3M (relocation + ERP) to normalize", "Deferred revenue growth of 35% YoY shows strong forward visibility", "Price increase of ~8% on renewals in Q3 with minimal churn impact", "Cash position of $18.2M with $3M drawn on $10M revolver", "DSO increase to 52 days driven by two Fortune 500 contracts, normalized DSO at 41 days"],
    "risks_identified": ["Stock-based compensation true-up of $850K may recur", "Working capital volatility from large enterprise payment terms", "Capital lease obligations of $1.2M for server infrastructure", "Founder bonus add-back of $400K requires market compensation benchmarking"],
    "action_items": [{"item": "Verify SBC add-back methodology with independent auditor", "owner": "Emily Park", "due": "This week"}, {"item": "Request aged AR detail for last 4 quarters", "owner": "Emily Park", "due": "Next session"}, {"item": "Analyze net working capital seasonality for peg determination", "owner": "Emily Park", "due": "Before valuation"}, {"item": "Review capital lease terms and cloud migration timeline", "owner": "Michael Torres", "due": "Next week"}],
    "financial_highlights": {"reported_ebitda": 4800000, "adjusted_ebitda": 8350000, "adjusted_ebitda_margin": 0.185, "cash_position": 18200000, "drawn_credit": 3000000, "deferred_revenue_growth_yoy": 0.35, "dso_reported": 52, "dso_normalized": 41},
    "sentiment": "neutral",
    "confidence_score": 0.92,
}

ANALYSIS_ATLAS_VALUATION = {
    "summary": "Internal valuation review for Project Atlas. DCF analysis suggests TEV range of $225-260M under base case assumptions (25% revenue growth, 80% gross margin, 22% EBITDA by Y3). Public comps analysis at 7.2x NTM revenue with 25-30% private company discount implies $280-310M. Team consensus on targeting $245-255M with earnout structure tied to $60M ARR milestone within 24 months.",
    "key_takeaways": ["DCF base case implies $225-260M TEV", "Public comps suggest $280-310M after private company discount", "Target offer range of $245-255M (5.5x NTM revenue)", "Earnout structure: additional consideration tied to $60M ARR in 24 months", "Working capital peg at $4.5M (trailing 12-month average)", "LOI draft targeted for Thursday, IC meeting next Tuesday"],
    "risks_identified": ["Competing IOI from strategic buyer at ~$270M", "Wide valuation range between DCF and comps methodologies", "Earnout achievement dependent on VP Sales execution"],
    "action_items": [{"item": "Draft LOI with proposed terms", "owner": "Michael Torres", "due": "Thursday"}, {"item": "Finalize sensitivity analysis", "owner": "Emily Park", "due": "End of week"}, {"item": "Update IC memo with latest valuation analysis", "owner": "Emily Park", "due": "End of week"}, {"item": "Coordinate with legal on R&W insurance and LOI draft", "owner": "Michael Torres", "due": "This week"}],
    "valuation_summary": {"dcf_low": 225000000, "dcf_high": 260000000, "comps_implied": 403000000, "private_discount": "25-30%", "target_offer_low": 245000000, "target_offer_high": 255000000, "implied_multiple": "5.5x NTM Revenue"},
    "sentiment": "positive",
    "confidence_score": 0.90,
}

ANALYSIS_BEACON_INTRO = {
    "summary": "Introductory call with GreenEnergy Co leadership. The company has grown from $28M to $85M revenue in three years and targets $200M within 24 months. Key competitive advantage is their US-manufactured premium commercial solar panels at $0.32/watt ($0.25/watt after IRA Section 45X credits). Production capacity of 2.4 GW annually with $120M order backlog.",
    "key_takeaways": ["Revenue growth from $28M to $85M over 3 years", "Path to $200M revenue within 24 months", "Cost per watt of $0.32 ($0.25 after IRA credits) vs $0.22 Chinese imports", "2.4 GW annual production capacity from two facilities", "$120M order backlog at all-time high", "35% gross margins (22% without IRA incentives)", "$75M raise for manufacturing expansion, international, and working capital"],
    "risks_identified": ["Dependence on IRA Section 45X manufacturing credits for margin competitiveness", "Cost premium vs Chinese imports (31% higher before credits)", "International expansion execution risk (Germany and Australia)", "Capital-intensive manufacturing model requires continued investment"],
    "action_items": [{"item": "Request detailed financial model and 3-year projections", "owner": "Emily Park", "due": "This week"}, {"item": "Analyze IRA credit sensitivity scenarios", "owner": "Emily Park", "due": "Next week"}, {"item": "Schedule facility tour at Arizona manufacturing plant", "owner": "Michael Torres", "due": "Within 2 weeks"}, {"item": "Review order backlog composition and customer credit quality", "owner": "Emily Park", "due": "Next session"}],
    "sentiment": "positive",
    "confidence_score": 0.85,
}

ANALYSIS_BEACON_MARKET = {
    "summary": "Market analysis discussion for the commercial solar segment supporting the Project Beacon investment thesis. US commercial solar TAM estimated at $18-19B by 2027 with 22% CAGR. GreenEnergy's SAM of $4.2-4.8B in premium commercial rooftop segment. At $200M revenue target, GreenEnergy would hold ~4.2% market share in a fragmented market.",
    "key_takeaways": ["US commercial solar TAM of $18-19B by 2027 (22% CAGR)", "GreenEnergy SAM of $4.2-4.8B (premium commercial rooftop + agrivoltaics)", "Fragmented market with top 3 at 35% share - room for gains", "$200M revenue implies ~4.2% SAM share", "IRA domestic content bonus (10% additional ITC) driving demand", "40% increase in inbound inquiries post IRA guidance"],
    "risks_identified": ["Agrivoltaics segment in SAM is emerging and unproven at scale", "Policy risk if IRA domestic content provisions change", "Six domestic competitors of scale could increase pricing pressure"],
    "action_items": [{"item": "Build detailed competitive positioning matrix", "owner": "Emily Park", "due": "This week"}, {"item": "Model IRA policy change scenarios on GreenEnergy margins", "owner": "Emily Park", "due": "Before IC"}, {"item": "Assess agrivoltaics TAM independently", "owner": "Emily Park", "due": "Next week"}],
    "sentiment": "positive",
    "confidence_score": 0.87,
}

ANALYSIS_CIPHER_PITCH = {
    "summary": "DataFlow Analytics founder pitch for Series B financing. AI-powered BI platform using semantic data layers and natural language query capabilities. Current ARR of $12.5M (3x YoY growth) with 120% net dollar retention. Strong PLG motion with 60% self-serve acquisition and 18% free-to-paid conversion rate. Seeking $30M at $150M pre-money valuation.",
    "key_takeaways": ["ARR of $12.5M with 3x YoY growth", "Net dollar retention of 120%", "180 paying customers across three key verticals", "Product-led growth: 60% self-serve acquisition", "11-day average signup-to-paid conversion", "18% free-to-paid conversion rate (best-in-class)", "$30M raise at $150M pre-money (12x ARR)"],
    "risks_identified": ["12x ARR multiple is aggressive for current growth stage", "Enterprise sales team not yet built (primary use of funds)", "Competitive threat from established BI players adding AI features", "International expansion to UK/Germany adds execution complexity"],
    "action_items": [{"item": "Deep-dive on product demo and technical architecture", "owner": "Sarah Chen", "due": "This week"}, {"item": "Customer reference calls with 3-5 enterprise accounts", "owner": "Emily Park", "due": "Within 2 weeks"}, {"item": "Competitive analysis: Tableau AI, Power BI Copilot, Looker", "owner": "Emily Park", "due": "Before term sheet"}, {"item": "Model valuation sensitivity at $120-180M pre-money range", "owner": "Emily Park", "due": "This week"}],
    "sentiment": "positive",
    "confidence_score": 0.86,
}

ANALYSIS_CIPHER_TERM_SHEET = {
    "summary": "Series B term sheet negotiation with DataFlow Analytics. Key terms agreed: broad-based weighted average anti-dilution, 5-person board (2 founder, 1 Meridian, 1 Series A, 1 independent), $1M transaction approval threshold. Information rights include quarterly financials now with monthly reporting at $25M ARR or 18 months post-close.",
    "key_takeaways": ["Anti-dilution: Broad-based weighted average (industry standard)", "Board: 5 seats (2 founder, 1 Meridian, 1 Series A, 1 independent)", "Transaction threshold: $1M (compromise between $500K and $2M)", "Information rights: Quarterly now, monthly at $25M ARR or 18 months", "Final term sheet signing targeted for end of next week"],
    "risks_identified": ["Monthly reporting delay until $25M ARR may limit visibility during critical growth phase", "Five-person board with only one Meridian seat limits governance control"],
    "action_items": [{"item": "Draft final term sheet incorporating negotiated changes", "owner": "Sarah Chen", "due": "End of next week"}, {"item": "Engage external counsel for definitive documentation", "owner": "Sarah Chen", "due": "Post signing"}, {"item": "Prepare internal approval memo for partnership committee", "owner": "James Whitfield", "due": "Before signing"}],
    "sentiment": "positive",
    "confidence_score": 0.93,
}


# ── Build helpers ────────────────────────────────────────────────────────

def _build_full_text(segments):
    lines = []
    for seg in segments:
        name = seg.get("speaker_name") or seg["speaker_label"]
        lines.append(f"[{name}]: {seg['text']}")
    return "\n\n".join(lines)


def _build_transcript_data():
    atlas_1_segs = _atlas_mgmt_pres_segments()
    atlas_2_segs = _atlas_financial_dd_segments()
    atlas_3_segs = _atlas_valuation_segments()
    beacon_1_segs = _beacon_intro_segments()
    beacon_2_segs = _beacon_market_analysis_segments()
    cipher_1_segs = _cipher_founder_pitch_segments()
    cipher_2_segs = _cipher_term_sheet_segments()

    transcripts = [
        Transcript(id=TXN_ATLAS_1, meeting_id=MTG_ATLAS_1, org_id=ORG1_ID, full_text=_build_full_text(atlas_1_segs), language="en", word_count=sum(len(s["text"].split()) for s in atlas_1_segs), confidence_score=0.95),
        Transcript(id=TXN_ATLAS_2, meeting_id=MTG_ATLAS_2, org_id=ORG1_ID, full_text=_build_full_text(atlas_2_segs), language="en", word_count=sum(len(s["text"].split()) for s in atlas_2_segs), confidence_score=0.96),
        Transcript(id=TXN_ATLAS_3, meeting_id=MTG_ATLAS_3, org_id=ORG1_ID, full_text=_build_full_text(atlas_3_segs), language="en", word_count=sum(len(s["text"].split()) for s in atlas_3_segs), confidence_score=0.95),
        Transcript(id=TXN_BEACON_1, meeting_id=MTG_BEACON_1, org_id=ORG1_ID, full_text=_build_full_text(beacon_1_segs), language="en", word_count=sum(len(s["text"].split()) for s in beacon_1_segs), confidence_score=0.94),
        Transcript(id=TXN_BEACON_2, meeting_id=MTG_BEACON_2, org_id=ORG1_ID, full_text=_build_full_text(beacon_2_segs), language="en", word_count=sum(len(s["text"].split()) for s in beacon_2_segs), confidence_score=0.95),
        Transcript(id=TXN_CIPHER_1, meeting_id=MTG_CIPHER_1, org_id=ORG1_ID, full_text=_build_full_text(cipher_1_segs), language="en", word_count=sum(len(s["text"].split()) for s in cipher_1_segs), confidence_score=0.95),
        Transcript(id=TXN_CIPHER_2, meeting_id=MTG_CIPHER_2, org_id=ORG1_ID, full_text=_build_full_text(cipher_2_segs), language="en", word_count=sum(len(s["text"].split()) for s in cipher_2_segs), confidence_score=0.96),
    ]

    segment_sets = [
        (TXN_ATLAS_1, MTG_ATLAS_1, atlas_1_segs),
        (TXN_ATLAS_2, MTG_ATLAS_2, atlas_2_segs),
        (TXN_ATLAS_3, MTG_ATLAS_3, atlas_3_segs),
        (TXN_BEACON_1, MTG_BEACON_1, beacon_1_segs),
        (TXN_BEACON_2, MTG_BEACON_2, beacon_2_segs),
        (TXN_CIPHER_1, MTG_CIPHER_1, cipher_1_segs),
        (TXN_CIPHER_2, MTG_CIPHER_2, cipher_2_segs),
    ]

    segments = []
    for txn_id, mtg_id, segs in segment_sets:
        for seg in segs:
            segments.append(TranscriptSegment(
                transcript_id=txn_id, meeting_id=mtg_id,
                speaker_label=seg["speaker_label"], speaker_name=seg.get("speaker_name"),
                text=seg["text"], start_time=seg["start_time"], end_time=seg["end_time"],
                confidence=seg.get("confidence"), segment_index=seg["segment_index"],
            ))

    analyses = [
        Analysis(id=ANL_ATLAS_1, meeting_id=MTG_ATLAS_1, org_id=ORG1_ID, call_type="management_presentation", structured_output=ANALYSIS_ATLAS_MGMT_PRES, model_used="claude-sonnet-4-20250514", prompt_version="v1", status="completed", requested_by=USER_SARAH_ID, version=1, grounding_score=0.88),
        Analysis(id=ANL_ATLAS_2, meeting_id=MTG_ATLAS_2, org_id=ORG1_ID, call_type="financial_review", structured_output=ANALYSIS_ATLAS_FIN_DD, model_used="claude-sonnet-4-20250514", prompt_version="v1", status="completed", requested_by=USER_EMILY_ID, version=1, grounding_score=0.92),
        Analysis(id=ANL_ATLAS_3, meeting_id=MTG_ATLAS_3, org_id=ORG1_ID, call_type="summarization", structured_output=ANALYSIS_ATLAS_VALUATION, model_used="claude-sonnet-4-20250514", prompt_version="v1", status="completed", requested_by=USER_MICHAEL_ID, version=1, grounding_score=0.90),
        Analysis(id=ANL_BEACON_1, meeting_id=MTG_BEACON_1, org_id=ORG1_ID, call_type="management_presentation", structured_output=ANALYSIS_BEACON_INTRO, model_used="claude-sonnet-4-20250514", prompt_version="v1", status="completed", requested_by=USER_MICHAEL_ID, version=1, grounding_score=0.85),
        Analysis(id=ANL_BEACON_2, meeting_id=MTG_BEACON_2, org_id=ORG1_ID, call_type="diligence", structured_output=ANALYSIS_BEACON_MARKET, model_used="claude-sonnet-4-20250514", prompt_version="v1", status="completed", requested_by=USER_EMILY_ID, version=1, grounding_score=0.87),
        Analysis(id=ANL_CIPHER_1, meeting_id=MTG_CIPHER_1, org_id=ORG1_ID, call_type="management_presentation", structured_output=ANALYSIS_CIPHER_PITCH, model_used="claude-sonnet-4-20250514", prompt_version="v1", status="completed", requested_by=USER_SARAH_ID, version=1, grounding_score=0.86),
        Analysis(id=ANL_CIPHER_2, meeting_id=MTG_CIPHER_2, org_id=ORG1_ID, call_type="summarization", structured_output=ANALYSIS_CIPHER_TERM_SHEET, model_used="claude-sonnet-4-20250514", prompt_version="v1", status="completed", requested_by=USER_SARAH_ID, version=1, grounding_score=0.93),
    ]

    return transcripts, segments, analyses


# ---------------------------------------------------------------------------
# Seed runner
# ---------------------------------------------------------------------------

async def seed() -> None:
    """Insert seed data into the database. Skip if already seeded."""
    async with async_session_factory() as session:
        # ── Idempotency check ────────────────────────────────────────
        existing = await session.execute(
            select(Organization).where(Organization.id == ORG1_ID)
        )
        if existing.scalar_one_or_none() is not None:
            print("[seed] Seed data already exists -- skipping.")
            print("[seed] To re-seed, delete existing seed records first.")
            return

        # ── Organizations ────────────────────────────────────────────
        print("[seed] Creating organizations ...")
        for org in ORGANIZATIONS:
            session.add(org)
            print(f"       + {org.name}")
        await session.flush()

        # ── Users ────────────────────────────────────────────────────
        print("[seed] Creating users ...")
        for user in USERS:
            session.add(user)
            print(f"       + {user.full_name} <{user.email}>")
        await session.flush()

        # ── Org Memberships ──────────────────────────────────────────
        print("[seed] Creating org memberships ...")
        for mem in ORG_MEMBERSHIPS:
            session.add(mem)
        print(f"       + {len(ORG_MEMBERSHIPS)} memberships")
        await session.flush()

        # ── Deals ────────────────────────────────────────────────────
        print("[seed] Creating deals ...")
        for deal in DEALS:
            session.add(deal)
            print(f"       + {deal.name} ({deal.deal_type}, {deal.status})")
        await session.flush()

        # ── Deal Memberships ─────────────────────────────────────────
        print("[seed] Creating deal memberships ...")
        for dm in DEAL_MEMBERSHIPS:
            session.add(dm)
        print(f"       + {len(DEAL_MEMBERSHIPS)} deal memberships")
        await session.flush()

        # ── Meetings ─────────────────────────────────────────────────
        print("[seed] Creating meetings ...")
        for mtg in MEETINGS:
            session.add(mtg)
            print(f"       + {mtg.title} ({mtg.duration_seconds // 60} min)")
        await session.flush()

        # ── Meeting Participants ─────────────────────────────────────
        print("[seed] Creating meeting participants ...")
        for p in PARTICIPANTS:
            session.add(p)
        print(f"       + {len(PARTICIPANTS)} participants")
        await session.flush()

        # ── Transcripts, Segments, and Analyses ──────────────────────
        transcripts, segments, analyses = _build_transcript_data()

        print("[seed] Creating transcripts ...")
        for t in transcripts:
            session.add(t)
            print(f"       + Transcript for meeting {t.meeting_id} ({t.word_count} words)")
        await session.flush()

        print("[seed] Creating transcript segments ...")
        for seg in segments:
            session.add(seg)
        print(f"       + {len(segments)} segments")
        await session.flush()

        print("[seed] Creating analyses ...")
        for a in analyses:
            session.add(a)
            print(f"       + {a.call_type} analysis for meeting {a.meeting_id}")
        await session.flush()

        # ── Documents ────────────────────────────────────────────────
        print("[seed] Creating documents ...")
        for doc in DOCUMENTS:
            session.add(doc)
            size_mb = doc.file_size / 1_000_000
            print(f"       + {doc.title} ({doc.document_type}, {size_mb:.1f} MB)")
        await session.flush()

        # ── Commit ───────────────────────────────────────────────────
        await session.commit()
        print()
        print("[seed] === Seed complete ===")
        print(f"[seed]   Organizations      : {len(ORGANIZATIONS)}")
        print(f"[seed]   Users              : {len(USERS)}")
        print(f"[seed]   Org Members        : {len(ORG_MEMBERSHIPS)}")
        print(f"[seed]   Deals              : {len(DEALS)}")
        print(f"[seed]   Deal Members       : {len(DEAL_MEMBERSHIPS)}")
        print(f"[seed]   Meetings           : {len(MEETINGS)}")
        print(f"[seed]   Participants       : {len(PARTICIPANTS)}")
        print(f"[seed]   Transcripts        : {len(transcripts)}")
        print(f"[seed]   Transcript Segments: {len(segments)}")
        print(f"[seed]   Analyses           : {len(analyses)}")
        print(f"[seed]   Documents          : {len(DOCUMENTS)}")


async def clear_seed_data() -> None:
    """Delete all seed data so the seed can be re-run."""
    async with async_session_factory() as session:
        from sqlalchemy import delete
        print("[seed] Clearing existing seed data ...")
        # Delete in reverse dependency order
        await session.execute(delete(TranscriptSegment))
        await session.execute(delete(Analysis))
        await session.execute(delete(Transcript))
        await session.execute(delete(MeetingParticipant))
        await session.execute(delete(Document))
        await session.execute(delete(Meeting))
        await session.execute(delete(DealMembership))
        await session.execute(delete(Deal))
        await session.execute(delete(OrgMembership))
        await session.execute(delete(User))
        await session.execute(delete(Organization))
        await session.commit()
        print("[seed] All seed data cleared.")


if __name__ == "__main__":
    import sys
    if "--force" in sys.argv:
        asyncio.run(clear_seed_data())
    asyncio.run(seed())
