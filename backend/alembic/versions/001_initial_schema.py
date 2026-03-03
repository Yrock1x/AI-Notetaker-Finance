"""Initial schema for Deal Companion

Revision ID: 001
Revises: None
Create Date: 2026-02-24

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Enable required extensions
    # ------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ------------------------------------------------------------------
    # 1. users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("cognito_sub", sa.String, nullable=False, unique=True),
        sa.Column("email", sa.String, nullable=False, unique=True),
        sa.Column("full_name", sa.String, nullable=False),
        sa.Column("avatar_url", sa.String, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ------------------------------------------------------------------
    # 2. organizations
    # ------------------------------------------------------------------
    op.create_table(
        "organizations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("slug", sa.String, nullable=False, unique=True),
        sa.Column("domain", sa.String, nullable=True),
        sa.Column("settings", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ------------------------------------------------------------------
    # 3. org_memberships
    # ------------------------------------------------------------------
    op.create_table(
        "org_memberships",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String, nullable=False, server_default=sa.text("'member'")),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("org_id", "user_id", name="uq_org_memberships_org_user"),
    )

    # ------------------------------------------------------------------
    # 4. deals
    # ------------------------------------------------------------------
    op.create_table(
        "deals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("target_company", sa.String, nullable=True),
        sa.Column("deal_type", sa.String, nullable=False, server_default=sa.text("'general'")),
        sa.Column("stage", sa.String, nullable=True),
        sa.Column("status", sa.String, nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ------------------------------------------------------------------
    # 5. deal_memberships
    # ------------------------------------------------------------------
    op.create_table(
        "deal_memberships",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String, nullable=False, server_default=sa.text("'analyst'")),
        sa.Column("added_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("deal_id", "user_id", name="uq_deal_memberships_deal_user"),
    )

    # ------------------------------------------------------------------
    # 6. meetings
    # ------------------------------------------------------------------
    op.create_table(
        "meetings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("meeting_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer, nullable=True),
        sa.Column("source", sa.String, nullable=False, server_default=sa.text("'upload'")),
        sa.Column("source_url", sa.String, nullable=True),
        sa.Column("file_key", sa.String, nullable=True),
        sa.Column("status", sa.String, nullable=False, server_default=sa.text("'uploading'")),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ------------------------------------------------------------------
    # 7. meeting_participants
    # ------------------------------------------------------------------
    op.create_table(
        "meeting_participants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("meeting_id", UUID(as_uuid=True), sa.ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("speaker_label", sa.String, nullable=False),
        sa.Column("speaker_name", sa.String, nullable=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )

    # ------------------------------------------------------------------
    # 8. transcripts
    # ------------------------------------------------------------------
    op.create_table(
        "transcripts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("meeting_id", UUID(as_uuid=True), sa.ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("full_text", sa.Text, nullable=False),
        sa.Column("language", sa.String, nullable=False, server_default=sa.text("'en'")),
        sa.Column("deepgram_response", JSONB, nullable=True),
        sa.Column("word_count", sa.Integer, nullable=True),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ------------------------------------------------------------------
    # 9. transcript_segments
    # ------------------------------------------------------------------
    op.create_table(
        "transcript_segments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("transcript_id", UUID(as_uuid=True), sa.ForeignKey("transcripts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("meeting_id", UUID(as_uuid=True), sa.ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("speaker_label", sa.String, nullable=False),
        sa.Column("speaker_name", sa.String, nullable=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("start_time", sa.Float, nullable=False),
        sa.Column("end_time", sa.Float, nullable=False),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("segment_index", sa.Integer, nullable=False),
    )

    # ------------------------------------------------------------------
    # 10. documents
    # ------------------------------------------------------------------
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("document_type", sa.String, nullable=False),
        sa.Column("file_key", sa.String, nullable=False),
        sa.Column("file_size", sa.Integer, nullable=True),
        sa.Column("extracted_text", sa.Text, nullable=True),
        sa.Column("uploaded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ------------------------------------------------------------------
    # 11. analyses
    # ------------------------------------------------------------------
    op.create_table(
        "analyses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("meeting_id", UUID(as_uuid=True), sa.ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("call_type", sa.String, nullable=False),
        sa.Column("structured_output", JSONB, nullable=True),
        sa.Column("model_used", sa.String, nullable=False),
        sa.Column("prompt_version", sa.String, nullable=True),
        sa.Column("grounding_score", sa.Float, nullable=True),
        sa.Column("status", sa.String, nullable=False, server_default=sa.text("'running'")),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("requested_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ------------------------------------------------------------------
    # 12. embeddings
    # ------------------------------------------------------------------
    op.create_table(
        "embeddings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.String, nullable=False),
        sa.Column("source_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_text", sa.Text, nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ------------------------------------------------------------------
    # 13. audit_logs
    # ------------------------------------------------------------------
    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String, nullable=False),
        sa.Column("resource_type", sa.String, nullable=False),
        sa.Column("resource_id", UUID(as_uuid=True), nullable=True),
        sa.Column("details", JSONB, nullable=True),
        sa.Column("ip_address", sa.String, nullable=True),
        sa.Column("user_agent", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ------------------------------------------------------------------
    # 14. meeting_bot_sessions
    # ------------------------------------------------------------------
    op.create_table(
        "meeting_bot_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("platform", sa.String, nullable=False),
        sa.Column("meeting_url", sa.String, nullable=False),
        sa.Column("status", sa.String, nullable=False, server_default=sa.text("'scheduled'")),
        sa.Column("scheduled_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recording_file_key", sa.String, nullable=True),
        sa.Column("consent_obtained", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ------------------------------------------------------------------
    # 15. integration_credentials
    # ------------------------------------------------------------------
    op.create_table(
        "integration_credentials",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String, nullable=False),
        sa.Column("access_token_encrypted", sa.String, nullable=False),
        sa.Column("refresh_token_encrypted", sa.String, nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scopes", sa.String, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("org_id", "user_id", "platform", name="uq_integration_credentials_org_user_platform"),
    )

    # ==================================================================
    # INDEXES
    # ==================================================================

    # Composite indexes for multi-tenant queries: (org_id, deal_id)
    op.create_index("ix_meetings_org_deal", "meetings", ["org_id", "deal_id"])
    op.create_index("ix_documents_org_deal", "documents", ["org_id", "deal_id"])
    op.create_index("ix_embeddings_org_deal", "embeddings", ["org_id", "deal_id"])

    # GIN index on analyses.structured_output for JSONB queries
    op.execute(
        "CREATE INDEX ix_analyses_structured_output_gin ON analyses "
        "USING gin (structured_output)"
    )

    # Composite index for audit log lookups by org + time
    op.create_index("ix_audit_logs_org_created", "audit_logs", ["org_id", "created_at"])

    # HNSW index on embeddings.embedding for approximate nearest-neighbor search
    op.execute(
        "CREATE INDEX ix_embeddings_embedding_hnsw ON embeddings "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )

    # Additional useful indexes for common query patterns
    op.create_index("ix_deals_org_id", "deals", ["org_id"])
    op.create_index("ix_deals_status", "deals", ["status"])
    op.create_index("ix_meetings_status", "meetings", ["status"])
    op.create_index("ix_transcript_segments_transcript", "transcript_segments", ["transcript_id"])
    op.create_index("ix_transcript_segments_meeting", "transcript_segments", ["meeting_id"])
    op.create_index("ix_analyses_meeting", "analyses", ["meeting_id"])
    op.create_index("ix_meeting_bot_sessions_org", "meeting_bot_sessions", ["org_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_embeddings_source", "embeddings", ["source_type", "source_id"])

    # ==================================================================
    # ROW-LEVEL SECURITY (RLS)
    # ==================================================================

    # Tables that have an org_id column and need RLS policies
    rls_tables = [
        "organizations",
        "org_memberships",
        "deals",
        "deal_memberships",
        "meetings",
        "meeting_participants",
        "transcripts",
        "transcript_segments",
        "documents",
        "analyses",
        "embeddings",
        "audit_logs",
        "meeting_bot_sessions",
        "integration_credentials",
    ]

    for table in rls_tables:
        # Enable RLS on the table
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")

        # Determine the org_id reference: most tables have a direct org_id column.
        # meeting_participants and transcript_segments do not have org_id directly,
        # so we join through meetings / transcripts respectively.
        if table == "meeting_participants":
            op.execute(
                f"CREATE POLICY {table}_org_isolation ON {table} FOR ALL "
                f"USING (meeting_id IN ("
                f"  SELECT id FROM meetings "
                f"  WHERE org_id = current_setting('app.current_org_id', true)::uuid"
                f")) "
                f"WITH CHECK (meeting_id IN ("
                f"  SELECT id FROM meetings "
                f"  WHERE org_id = current_setting('app.current_org_id', true)::uuid"
                f"))"
            )
        elif table == "transcript_segments":
            op.execute(
                f"CREATE POLICY {table}_org_isolation ON {table} FOR ALL "
                f"USING (transcript_id IN ("
                f"  SELECT id FROM transcripts "
                f"  WHERE org_id = current_setting('app.current_org_id', true)::uuid"
                f")) "
                f"WITH CHECK (transcript_id IN ("
                f"  SELECT id FROM transcripts "
                f"  WHERE org_id = current_setting('app.current_org_id', true)::uuid"
                f"))"
            )
        elif table == "organizations":
            # For the organizations table itself, filter by its own id
            op.execute(
                f"CREATE POLICY {table}_org_isolation ON {table} FOR ALL "
                f"USING (id = current_setting('app.current_org_id', true)::uuid) "
                f"WITH CHECK (id = current_setting('app.current_org_id', true)::uuid)"
            )
        else:
            op.execute(
                f"CREATE POLICY {table}_org_isolation ON {table} FOR ALL "
                f"USING (org_id = current_setting('app.current_org_id', true)::uuid) "
                f"WITH CHECK (org_id = current_setting('app.current_org_id', true)::uuid)"
            )

    # The users table does NOT have org_id -- skip RLS entirely so all
    # authenticated roles can look up user profiles.


def downgrade() -> None:
    # ==================================================================
    # Drop RLS policies
    # ==================================================================
    rls_tables = [
        "integration_credentials",
        "meeting_bot_sessions",
        "audit_logs",
        "embeddings",
        "analyses",
        "documents",
        "transcript_segments",
        "transcripts",
        "meeting_participants",
        "meetings",
        "deal_memberships",
        "deals",
        "org_memberships",
        "organizations",
    ]

    for table in rls_tables:
        op.execute(f"DROP POLICY IF EXISTS {table}_org_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    # ==================================================================
    # Drop indexes (those created with raw SQL)
    # ==================================================================
    op.execute("DROP INDEX IF EXISTS ix_embeddings_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_analyses_structured_output_gin")

    # ==================================================================
    # Drop tables in reverse dependency order
    # ==================================================================
    op.drop_table("integration_credentials")
    op.drop_table("meeting_bot_sessions")
    op.drop_table("audit_logs")
    op.drop_table("embeddings")
    op.drop_table("analyses")
    op.drop_table("documents")
    op.drop_table("transcript_segments")
    op.drop_table("transcripts")
    op.drop_table("meeting_participants")
    op.drop_table("meetings")
    op.drop_table("deal_memberships")
    op.drop_table("deals")
    op.drop_table("org_memberships")
    op.drop_table("organizations")
    op.drop_table("users")
