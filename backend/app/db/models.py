"""SQLAlchemy models — the former Postgres schema, consolidated.

This is the cumulative result of supabase/migrations/0001..0011 expressed as one
SQLite schema (SQLite starts fresh, so there's no need to replay the deltas).

Notes:
- ``profiles`` is now the user table itself (no external auth.users). Auth fields
  for self-hosted OAuth are added in the auth workstream.
- The 768-dim embedding vector is NOT a column here; it lives in a vec0 virtual
  table (see app/db/vectors.py). The ``embeddings`` row holds everything else.
- Org/tenant isolation is enforced in app code (app/db/scope.py), not RLS.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    text as sa_text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, CreatedAt, Timestamps, UUIDPrimaryKey, utcnow_iso


# ---------------------------------------------------------------------------
# profiles / organizations / memberships
# ---------------------------------------------------------------------------
class Profile(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "profiles"

    email: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False, default="")
    avatar_url: Mapped[str | None] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        # case-insensitive unique email (replaces lower(email) unique index)
        Index("profiles_email_key", sa_text("lower(email)"), unique=True),
    )


class Organization(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False)
    domain: Mapped[str | None] = mapped_column(String)
    settings: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (UniqueConstraint("slug", name="organizations_slug_key"),)


class OrgMembership(UUIDPrimaryKey, Base):
    __tablename__ = "org_memberships"

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String, nullable=False, default="member")
    joined_at: Mapped[str] = mapped_column(String, nullable=False, default=utcnow_iso)

    __table_args__ = (
        CheckConstraint("role in ('owner','admin','member')", name="org_memberships_role_chk"),
        UniqueConstraint("org_id", "user_id", name="org_memberships_unique"),
        Index("org_memberships_user", "user_id"),
    )


# ---------------------------------------------------------------------------
# deals / deal_memberships
# ---------------------------------------------------------------------------
class Deal(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "deals"

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    target_company: Mapped[str | None] = mapped_column(String)
    deal_type: Mapped[str] = mapped_column(String, nullable=False, default="general")
    stage: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    created_by: Mapped[str] = mapped_column(
        ForeignKey("profiles.id"), nullable=False
    )
    deleted_at: Mapped[str | None] = mapped_column(String)

    __table_args__ = (
        Index("deals_org", "org_id"),
        Index("deals_org_created", "org_id", "created_at"),
    )


class DealMembership(UUIDPrimaryKey, Base):
    __tablename__ = "deal_memberships"

    deal_id: Mapped[str] = mapped_column(
        ForeignKey("deals.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String, nullable=False, default="analyst")
    added_by: Mapped[str | None] = mapped_column(ForeignKey("profiles.id"))
    added_at: Mapped[str] = mapped_column(String, nullable=False, default=utcnow_iso)

    __table_args__ = (
        CheckConstraint(
            "role in ('lead','admin','analyst','viewer')", name="deal_memberships_role_chk"
        ),
        UniqueConstraint("deal_id", "user_id", name="deal_memberships_unique"),
        Index("deal_memberships_user", "user_id"),
    )


# ---------------------------------------------------------------------------
# meetings / participants / bot sessions
# ---------------------------------------------------------------------------
class Meeting(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "meetings"

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    # nullable as of migration 0005 (calendar events before deal assignment)
    deal_id: Mapped[str | None] = mapped_column(
        ForeignKey("deals.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    meeting_date: Mapped[str | None] = mapped_column(String)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String, nullable=False, default="upload")
    source_url: Mapped[str | None] = mapped_column(String)
    file_key: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False, default="uploading")
    error_message: Mapped[str | None] = mapped_column(Text)
    bot_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # calendar sync (0005)
    external_event_id: Mapped[str | None] = mapped_column(String)
    external_provider: Mapped[str | None] = mapped_column(String)
    created_by: Mapped[str] = mapped_column(ForeignKey("profiles.id"), nullable=False)

    __table_args__ = (
        Index("meetings_deal", "deal_id"),
        Index("meetings_org_status", "org_id", "status"),
        Index("meetings_org_date", "org_id", "meeting_date"),
        Index(
            "meetings_external_event_unique",
            "org_id",
            "external_provider",
            "external_event_id",
            unique=True,
            sqlite_where=sa_text("external_event_id is not null"),
        ),
    )


class MeetingParticipant(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "meeting_participants"

    meeting_id: Mapped[str] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    speaker_label: Mapped[str] = mapped_column(String, nullable=False)
    speaker_name: Mapped[str | None] = mapped_column(String)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("profiles.id"))
    # Recall bot capture (0006)
    recall_participant_id: Mapped[str | None] = mapped_column(String)
    email_address: Mapped[str | None] = mapped_column(String)
    joined_at: Mapped[str | None] = mapped_column(String)
    left_at: Mapped[str | None] = mapped_column(String)

    __table_args__ = (
        Index("meeting_participants_meeting", "meeting_id"),
        Index(
            "meeting_participants_recall_unique",
            "meeting_id",
            "recall_participant_id",
            unique=True,
            sqlite_where=sa_text("recall_participant_id is not null"),
        ),
    )


class MeetingBotSession(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "meeting_bot_sessions"

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    deal_id: Mapped[str] = mapped_column(
        ForeignKey("deals.id", ondelete="CASCADE"), nullable=False
    )
    meeting_id: Mapped[str | None] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE")
    )
    platform: Mapped[str] = mapped_column(String, nullable=False)
    meeting_url: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="scheduled")
    scheduled_start: Mapped[str | None] = mapped_column(String)
    actual_start: Mapped[str | None] = mapped_column(String)
    actual_end: Mapped[str | None] = mapped_column(String)
    recording_file_key: Mapped[str | None] = mapped_column(String)
    recall_bot_id: Mapped[str | None] = mapped_column(String)
    live_transcript_channel: Mapped[str | None] = mapped_column(String)
    consent_obtained: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[str] = mapped_column(ForeignKey("profiles.id"), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "platform in ('zoom','teams','google_meet')", name="bot_sessions_platform_chk"
        ),
        CheckConstraint(
            "status in ('scheduled','joining','recording','completed','failed','cancelled')",
            name="bot_sessions_status_chk",
        ),
        Index("meeting_bot_sessions_deal", "deal_id"),
        Index("meeting_bot_sessions_status", "org_id", "status"),
    )


# ---------------------------------------------------------------------------
# transcripts / segments
# ---------------------------------------------------------------------------
class Transcript(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "transcripts"

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    meeting_id: Mapped[str] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    full_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    language: Mapped[str] = mapped_column(String, nullable=False, default="en")
    deepgram_response: Mapped[dict | None] = mapped_column(JSON)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence_score: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (
        UniqueConstraint("meeting_id", name="transcripts_meeting_unique"),
        Index("transcripts_org", "org_id"),
    )


class TranscriptSegment(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "transcript_segments"

    transcript_id: Mapped[str | None] = mapped_column(
        ForeignKey("transcripts.id", ondelete="CASCADE")
    )
    meeting_id: Mapped[str] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    speaker_label: Mapped[str] = mapped_column(String, nullable=False)
    speaker_name: Mapped[str | None] = mapped_column(String)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    segment_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_partial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    recall_segment_id: Mapped[str | None] = mapped_column(String)

    __table_args__ = (
        Index(
            "transcript_segments_recall_key",
            "recall_segment_id",
            unique=True,
            sqlite_where=sa_text("recall_segment_id is not null"),
        ),
        Index("transcript_segments_meeting", "meeting_id"),
        Index("transcript_segments_order", "meeting_id", "start_time"),
    )


# ---------------------------------------------------------------------------
# documents
# ---------------------------------------------------------------------------
class Document(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "documents"

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    deal_id: Mapped[str] = mapped_column(
        ForeignKey("deals.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    document_type: Mapped[str] = mapped_column(String, nullable=False)
    file_key: Mapped[str] = mapped_column(String, nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    uploaded_by: Mapped[str] = mapped_column(ForeignKey("profiles.id"), nullable=False)

    __table_args__ = (
        Index("documents_deal", "deal_id"),
        Index("documents_org", "org_id"),
    )


# ---------------------------------------------------------------------------
# analyses
# ---------------------------------------------------------------------------
class Analysis(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "analyses"

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    meeting_id: Mapped[str] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    call_type: Mapped[str] = mapped_column(String, nullable=False)
    structured_output: Mapped[dict | None] = mapped_column(JSON)
    model_used: Mapped[str] = mapped_column(String, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String, nullable=False, default="v1")
    grounding_score: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, nullable=False, default="running")
    error_message: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[str | None] = mapped_column(ForeignKey("profiles.id"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        CheckConstraint(
            "status in ('queued','running','completed','failed','partial')",
            name="analyses_status_chk",
        ),
        Index("analyses_meeting", "meeting_id"),
        Index("analyses_org", "org_id"),
    )


# ---------------------------------------------------------------------------
# embeddings (vector lives in the vec0 table; see app/db/vectors.py)
# ---------------------------------------------------------------------------
class Embedding(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "embeddings"

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    deal_id: Mapped[str] = mapped_column(
        ForeignKey("deals.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    source_id: Mapped[str] = mapped_column(String, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_json: Mapped[dict] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )

    __table_args__ = (
        CheckConstraint(
            "source_type in ('transcript_segment','document_chunk')",
            name="embeddings_source_type_chk",
        ),
        Index("embeddings_deal", "deal_id"),
        Index("embeddings_source", "source_type", "source_id"),
    )


# ---------------------------------------------------------------------------
# qa_interactions
# ---------------------------------------------------------------------------
class QAInteraction(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "qa_interactions"

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    deal_id: Mapped[str] = mapped_column(
        ForeignKey("deals.id", ondelete="CASCADE"), nullable=False
    )
    meeting_id: Mapped[str | None] = mapped_column(
        ForeignKey("meetings.id", ondelete="SET NULL")
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    grounding_score: Mapped[float | None] = mapped_column(Float)
    model_used: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (Index("qa_interactions_deal", "deal_id", "created_at"),)


# ---------------------------------------------------------------------------
# integration_credentials
# ---------------------------------------------------------------------------
class IntegrationCredential(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "integration_credentials"

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String, nullable=False)
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text)
    token_expires_at: Mapped[str | None] = mapped_column(String)
    scopes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint(
            "platform in ('zoom','microsoft','google','slack','teams','outlook')",
            name="integration_credentials_platform_chk",
        ),
        UniqueConstraint(
            "org_id", "user_id", "platform", name="integration_credentials_unique"
        ),
    )


# ---------------------------------------------------------------------------
# audit_logs
# ---------------------------------------------------------------------------
class AuditLog(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "audit_logs"

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL")
    )
    deal_id: Mapped[str | None] = mapped_column(
        ForeignKey("deals.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String, nullable=False)
    resource_type: Mapped[str] = mapped_column(String, nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String)
    details: Mapped[dict | None] = mapped_column(JSON)
    ip_address: Mapped[str | None] = mapped_column(String)
    user_agent: Mapped[str | None] = mapped_column(String)

    __table_args__ = (
        Index("audit_logs_org_created", "org_id", "created_at"),
        Index("audit_logs_user", "user_id", "created_at"),
        Index("audit_logs_resource", "resource_type", "resource_id"),
    )


# ---------------------------------------------------------------------------
# graph_subscriptions (Microsoft Graph change subscriptions — 0007)
# ---------------------------------------------------------------------------
class GraphSubscription(Timestamps, Base):
    __tablename__ = "graph_subscriptions"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # Graph subscription id
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    resource: Mapped[str] = mapped_column(String, nullable=False)
    client_state: Mapped[str] = mapped_column(String, nullable=False)
    notification_url: Mapped[str] = mapped_column(String, nullable=False)
    expiration: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("graph_subscriptions_user", "user_id"),
        Index(
            "graph_subscriptions_expiry",
            "expiration",
            sqlite_where=sa_text("is_active = 1"),
        ),
    )


# ---------------------------------------------------------------------------
# meeting_chat_messages (Recall chat capture — 0006)
# ---------------------------------------------------------------------------
class MeetingChatMessage(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "meeting_chat_messages"

    meeting_id: Mapped[str] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    sender_name: Mapped[str | None] = mapped_column(String)
    sender_email: Mapped[str | None] = mapped_column(String)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[str] = mapped_column(String, nullable=False)
    recall_message_id: Mapped[str | None] = mapped_column(String)

    __table_args__ = (
        UniqueConstraint("recall_message_id", name="meeting_chat_messages_recall_unique"),
        Index("meeting_chat_messages_meeting", "meeting_id", "sent_at"),
    )


# ---------------------------------------------------------------------------
# action_item_completions (0011)
# ---------------------------------------------------------------------------
class ActionItemCompletion(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "action_item_completions"

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    deal_id: Mapped[str] = mapped_column(
        ForeignKey("deals.id", ondelete="CASCADE"), nullable=False
    )
    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False
    )
    action_key: Mapped[str] = mapped_column(String, nullable=False)
    action_text: Mapped[str | None] = mapped_column(Text)
    completed_by: Mapped[str] = mapped_column(ForeignKey("profiles.id"), nullable=False)
    completed_at: Mapped[str] = mapped_column(String, nullable=False, default=utcnow_iso)

    __table_args__ = (
        UniqueConstraint("deal_id", "action_key", name="action_item_completions_unique"),
        Index("action_item_completions_deal", "deal_id"),
    )


# ---------------------------------------------------------------------------
# partner_api_keys (CogniVault M2M integration — WS11)
# ---------------------------------------------------------------------------
class PartnerApiKey(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "partner_api_keys"

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    key_hash: Mapped[str] = mapped_column(String, nullable=False)  # sha256 of the key
    scopes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_used_at: Mapped[str | None] = mapped_column(String)

    __table_args__ = (
        UniqueConstraint("key_hash", name="partner_api_keys_hash_unique"),
        Index("partner_api_keys_org", "org_id"),
    )
