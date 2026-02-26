"""
Database seed script for DealWise AI.

Populates the development database with realistic sample data:
  - 2 organizations
  - 4 users with org memberships
  - 3 deals with deal memberships
  - Meetings and documents per deal

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
    Deal,
    DealMembership,
    Document,
    Meeting,
    Organization,
    OrgMembership,
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
    # Org 1 - Meridian Capital: all four users
    OrgMembership(org_id=ORG1_ID, user_id=USER_SARAH_ID,   role="owner"),
    OrgMembership(org_id=ORG1_ID, user_id=USER_MICHAEL_ID, role="admin"),
    OrgMembership(org_id=ORG1_ID, user_id=USER_EMILY_ID,   role="member"),
    OrgMembership(org_id=ORG1_ID, user_id=USER_JAMES_ID,   role="member"),
    # Org 2 - Apex Growth: Sarah and James
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
        status="closed",
        created_by=USER_SARAH_ID,
    ),
]

# ── Deal Memberships ─────────────────────────────────────────────────────
DEAL_MEMBERSHIPS = [
    # Project Atlas
    DealMembership(
        deal_id=DEAL_ATLAS_ID, user_id=USER_SARAH_ID, org_id=ORG1_ID,
        role=DealRole.LEAD, added_by=USER_SARAH_ID,
    ),
    DealMembership(
        deal_id=DEAL_ATLAS_ID, user_id=USER_MICHAEL_ID, org_id=ORG1_ID,
        role=DealRole.ADMIN, added_by=USER_SARAH_ID,
    ),
    DealMembership(
        deal_id=DEAL_ATLAS_ID, user_id=USER_EMILY_ID, org_id=ORG1_ID,
        role=DealRole.ANALYST, added_by=USER_SARAH_ID,
    ),
    DealMembership(
        deal_id=DEAL_ATLAS_ID, user_id=USER_JAMES_ID, org_id=ORG1_ID,
        role=DealRole.VIEWER, added_by=USER_MICHAEL_ID,
    ),
    # Project Beacon
    DealMembership(
        deal_id=DEAL_BEACON_ID, user_id=USER_MICHAEL_ID, org_id=ORG1_ID,
        role=DealRole.LEAD, added_by=USER_MICHAEL_ID,
    ),
    DealMembership(
        deal_id=DEAL_BEACON_ID, user_id=USER_EMILY_ID, org_id=ORG1_ID,
        role=DealRole.ANALYST, added_by=USER_MICHAEL_ID,
    ),
    # Project Cipher
    DealMembership(
        deal_id=DEAL_CIPHER_ID, user_id=USER_SARAH_ID, org_id=ORG1_ID,
        role=DealRole.LEAD, added_by=USER_SARAH_ID,
    ),
]

# ── Meetings ─────────────────────────────────────────────────────────────
MEETINGS = [
    # --- Project Atlas meetings ---
    Meeting(
        deal_id=DEAL_ATLAS_ID, org_id=ORG1_ID,
        title="TechCorp Management Presentation",
        meeting_date=_ts(days_offset=0, hours_offset=10),
        duration_seconds=5400,  # 90 min
        source="zoom",
        status="ready",
        created_by=USER_SARAH_ID,
    ),
    Meeting(
        deal_id=DEAL_ATLAS_ID, org_id=ORG1_ID,
        title="TechCorp Financial Due Diligence - Day 1",
        meeting_date=_ts(days_offset=2, hours_offset=9),
        duration_seconds=7200,  # 120 min
        source="teams",
        status="ready",
        created_by=USER_EMILY_ID,
    ),
    Meeting(
        deal_id=DEAL_ATLAS_ID, org_id=ORG1_ID,
        title="Atlas Deal Team Sync - Valuation Review",
        meeting_date=_ts(days_offset=5, hours_offset=14),
        duration_seconds=3600,  # 60 min
        source="zoom",
        status="ready",
        created_by=USER_MICHAEL_ID,
    ),
    Meeting(
        deal_id=DEAL_ATLAS_ID, org_id=ORG1_ID,
        title="TechCorp CTO Technical Deep-Dive",
        meeting_date=_ts(days_offset=7, hours_offset=11),
        duration_seconds=4500,  # 75 min
        source="zoom",
        status="transcribing",
        created_by=USER_SARAH_ID,
    ),
    # --- Project Beacon meetings ---
    Meeting(
        deal_id=DEAL_BEACON_ID, org_id=ORG1_ID,
        title="GreenEnergy Co Introductory Call",
        meeting_date=_ts(days_offset=1, hours_offset=15),
        duration_seconds=2700,  # 45 min
        source="zoom",
        status="ready",
        created_by=USER_MICHAEL_ID,
    ),
    Meeting(
        deal_id=DEAL_BEACON_ID, org_id=ORG1_ID,
        title="GreenEnergy Co - Market Analysis Discussion",
        meeting_date=_ts(days_offset=4, hours_offset=10),
        duration_seconds=3600,  # 60 min
        source="teams",
        status="ready",
        created_by=USER_EMILY_ID,
    ),
    Meeting(
        deal_id=DEAL_BEACON_ID, org_id=ORG1_ID,
        title="Beacon Investment Committee Pre-Read",
        meeting_date=_ts(days_offset=8, hours_offset=16),
        duration_seconds=1800,  # 30 min
        source="upload",
        status="analyzing",
        created_by=USER_MICHAEL_ID,
    ),
    # --- Project Cipher meetings ---
    Meeting(
        deal_id=DEAL_CIPHER_ID, org_id=ORG1_ID,
        title="DataFlow Analytics - Founder Pitch",
        meeting_date=_ts(days_offset=-30, hours_offset=10),
        duration_seconds=3600,  # 60 min
        source="zoom",
        status="ready",
        created_by=USER_SARAH_ID,
    ),
    Meeting(
        deal_id=DEAL_CIPHER_ID, org_id=ORG1_ID,
        title="DataFlow Series B Term Sheet Negotiation",
        meeting_date=_ts(days_offset=-20, hours_offset=14),
        duration_seconds=5400,  # 90 min
        source="zoom",
        status="ready",
        created_by=USER_SARAH_ID,
    ),
]

# ── Documents ────────────────────────────────────────────────────────────
DOCUMENTS = [
    # --- Project Atlas documents ---
    Document(
        deal_id=DEAL_ATLAS_ID, org_id=ORG1_ID,
        title="TechCorp - Confidential Information Memorandum",
        document_type="pdf",
        file_key="orgs/meridian-capital/deals/atlas/docs/techcorp_cim_2025.pdf",
        file_size=4_850_000,
        uploaded_by=USER_SARAH_ID,
    ),
    Document(
        deal_id=DEAL_ATLAS_ID, org_id=ORG1_ID,
        title="TechCorp - Financial Model v3.2",
        document_type="xlsx",
        file_key="orgs/meridian-capital/deals/atlas/docs/techcorp_financial_model_v3.2.xlsx",
        file_size=2_100_000,
        uploaded_by=USER_EMILY_ID,
    ),
    Document(
        deal_id=DEAL_ATLAS_ID, org_id=ORG1_ID,
        title="Project Atlas - Investment Committee Deck",
        document_type="pptx",
        file_key="orgs/meridian-capital/deals/atlas/docs/atlas_ic_deck_final.pptx",
        file_size=8_750_000,
        uploaded_by=USER_MICHAEL_ID,
    ),
    Document(
        deal_id=DEAL_ATLAS_ID, org_id=ORG1_ID,
        title="TechCorp - Quality of Earnings Report (Draft)",
        document_type="pdf",
        file_key="orgs/meridian-capital/deals/atlas/docs/techcorp_qoe_draft.pdf",
        file_size=3_200_000,
        uploaded_by=USER_EMILY_ID,
    ),
    # --- Project Beacon documents ---
    Document(
        deal_id=DEAL_BEACON_ID, org_id=ORG1_ID,
        title="GreenEnergy Co - Company Overview Pitch Deck",
        document_type="pptx",
        file_key="orgs/meridian-capital/deals/beacon/docs/greenenergy_pitch_deck.pptx",
        file_size=6_400_000,
        uploaded_by=USER_MICHAEL_ID,
    ),
    Document(
        deal_id=DEAL_BEACON_ID, org_id=ORG1_ID,
        title="GreenEnergy Co - 3-Year Financial Projections",
        document_type="xlsx",
        file_key="orgs/meridian-capital/deals/beacon/docs/greenenergy_projections_2025_2028.xlsx",
        file_size=1_350_000,
        uploaded_by=USER_EMILY_ID,
    ),
    Document(
        deal_id=DEAL_BEACON_ID, org_id=ORG1_ID,
        title="Commercial Solar Market Research Report",
        document_type="pdf",
        file_key="orgs/meridian-capital/deals/beacon/docs/solar_market_research_2025.pdf",
        file_size=5_600_000,
        uploaded_by=USER_EMILY_ID,
    ),
    # --- Project Cipher documents ---
    Document(
        deal_id=DEAL_CIPHER_ID, org_id=ORG1_ID,
        title="DataFlow Analytics - Series B Pitch Deck",
        document_type="pptx",
        file_key="orgs/meridian-capital/deals/cipher/docs/dataflow_series_b_deck.pptx",
        file_size=5_200_000,
        uploaded_by=USER_SARAH_ID,
    ),
    Document(
        deal_id=DEAL_CIPHER_ID, org_id=ORG1_ID,
        title="DataFlow Analytics - Executed Term Sheet",
        document_type="pdf",
        file_key="orgs/meridian-capital/deals/cipher/docs/dataflow_term_sheet_executed.pdf",
        file_size=420_000,
        uploaded_by=USER_SARAH_ID,
    ),
    Document(
        deal_id=DEAL_CIPHER_ID, org_id=ORG1_ID,
        title="DataFlow Analytics - Product Roadmap & TAM Analysis",
        document_type="pdf",
        file_key="orgs/meridian-capital/deals/cipher/docs/dataflow_product_tam_analysis.pdf",
        file_size=1_800_000,
        uploaded_by=USER_SARAH_ID,
    ),
]


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
        print(f"[seed]   Organizations : {len(ORGANIZATIONS)}")
        print(f"[seed]   Users         : {len(USERS)}")
        print(f"[seed]   Org Members   : {len(ORG_MEMBERSHIPS)}")
        print(f"[seed]   Deals         : {len(DEALS)}")
        print(f"[seed]   Deal Members  : {len(DEAL_MEMBERSHIPS)}")
        print(f"[seed]   Meetings      : {len(MEETINGS)}")
        print(f"[seed]   Documents     : {len(DOCUMENTS)}")


if __name__ == "__main__":
    asyncio.run(seed())
