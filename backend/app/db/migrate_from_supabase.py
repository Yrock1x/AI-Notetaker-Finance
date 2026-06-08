"""One-shot data migration: Supabase/Postgres → worker-owned SQLite.

Run AFTER `alembic upgrade head` has created the SQLite schema. Reads every
table from Supabase via the service-role client, transforms Postgres types to the
SQLite conventions, inserts via the ORM in FK-dependency order, copies the
pgvector embeddings into the vec0 table, and copies storage objects to disk.

Usage:
    python -m app.db.migrate_from_supabase           # full run
    python -m app.db.migrate_from_supabase --tables deals,meetings
    python -m app.db.migrate_from_supabase --skip-storage

This is intentionally idempotent-ish (insert-or-ignore on PK) so a failed run can
be re-attempted. It is NOT meant to run continuously — freeze writes, run it
once at cutover, verify, then flip the frontend.
"""

from __future__ import annotations

import argparse
import json

import structlog

logger = structlog.get_logger(__name__)

# FK-dependency order: parents before children.
TABLE_ORDER = [
    "organizations",
    "profiles",
    "org_memberships",
    "deals",
    "deal_memberships",
    "meetings",
    "meeting_participants",
    "meeting_bot_sessions",
    "transcripts",
    "transcript_segments",
    "documents",
    "analyses",
    "embeddings",
    "qa_interactions",
    "integration_credentials",
    "audit_logs",
    "graph_subscriptions",
    "meeting_chat_messages",
    "action_item_completions",
]

# Supabase Storage buckets to mirror to the local filesystem.
STORAGE_BUCKETS = ["meeting-recordings", "deal-documents", "deliverables"]


# ---------------------------------------------------------------------------
# Pure transform helpers (unit-tested)
# ---------------------------------------------------------------------------
def normalize_value(column: str, value):
    """Map one Postgres value to its SQLite-stored form.

    - jsonb dict/list pass through (SQLAlchemy JSON handles serialization)
    - the embeddings ``metadata`` column maps to the ORM attr ``metadata_json``
    - everything else (uuid as text, timestamptz as ISO string, bool, numbers)
      passes through unchanged because the Supabase REST client already returns
      them as JSON-native types.
    """
    return value


def parse_pgvector(raw) -> list[float] | None:
    """Parse a pgvector value (list, or a '[1,2,3]' string) into a float list."""
    if raw is None:
        return None
    if isinstance(raw, list):
        return [float(x) for x in raw]
    if isinstance(raw, str):
        raw = raw.strip()
        if raw.startswith("[") and raw.endswith("]"):
            inner = raw[1:-1].strip()
            if not inner:
                return []
            return [float(x) for x in inner.split(",")]
    raise ValueError(f"Unrecognized pgvector value: {raw!r}")


def row_to_model_kwargs(table: str, row: dict) -> dict:
    """Translate a Supabase row dict into ORM constructor kwargs."""
    out = dict(row)
    if table == "embeddings":
        # vector goes to the vec0 table separately; "metadata" → metadata_json
        out.pop("embedding", None)
        if "metadata" in out:
            out["metadata_json"] = out.pop("metadata")
    return out


# ---------------------------------------------------------------------------
# Migration runner (requires live Supabase + configured SQLite engine)
# ---------------------------------------------------------------------------
def _model_for(table: str):
    from app.db import models as m

    mapping = {
        "organizations": m.Organization,
        "profiles": m.Profile,
        "org_memberships": m.OrgMembership,
        "deals": m.Deal,
        "deal_memberships": m.DealMembership,
        "meetings": m.Meeting,
        "meeting_participants": m.MeetingParticipant,
        "meeting_bot_sessions": m.MeetingBotSession,
        "transcripts": m.Transcript,
        "transcript_segments": m.TranscriptSegment,
        "documents": m.Document,
        "analyses": m.Analysis,
        "embeddings": m.Embedding,
        "qa_interactions": m.QAInteraction,
        "integration_credentials": m.IntegrationCredential,
        "audit_logs": m.AuditLog,
        "graph_subscriptions": m.GraphSubscription,
        "meeting_chat_messages": m.MeetingChatMessage,
        "action_item_completions": m.ActionItemCompletion,
    }
    return mapping[table]


def _fetch_all(supabase, table: str, page: int = 1000):
    """Page through a Supabase table with the service-role client."""
    rows: list[dict] = []
    start = 0
    while True:
        resp = (
            supabase.table(table)
            .select("*")
            .range(start, start + page - 1)
            .execute()
        )
        batch = resp.data or []
        rows.extend(batch)
        if len(batch) < page:
            break
        start += page
    return rows


def migrate_table(supabase, session, table: str) -> int:
    from app.db.vectors import upsert_vector

    model = _model_for(table)
    rows = _fetch_all(supabase, table)
    count = 0
    for row in rows:
        kwargs = row_to_model_kwargs(table, row)
        existing = session.get(model, row.get("id"))
        if existing is None:
            session.add(model(**kwargs))
        if table == "embeddings":
            vec = parse_pgvector(row.get("embedding"))
            if vec:
                upsert_vector(
                    session, embedding_id=row["id"], deal_id=row["deal_id"], vector=vec
                )
        count += 1
    session.commit()
    logger.info("migrated_table", table=table, rows=count)
    return count


def migrate_storage(supabase) -> int:
    from app.storage.local import save_bytes

    copied = 0
    for bucket in STORAGE_BUCKETS:
        try:
            objects = supabase.storage.from_(bucket).list()
        except Exception as exc:  # noqa: BLE001
            logger.warning("storage_list_failed", bucket=bucket, error=str(exc))
            continue
        for obj in objects or []:
            key = obj.get("name")
            if not key:
                continue
            try:
                data = supabase.storage.from_(bucket).download(key)
                save_bytes(bucket, key, bytes(data))
                copied += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("storage_copy_failed", bucket=bucket, key=key, error=str(exc))
    logger.info("migrated_storage", objects=copied)
    return copied


def run(tables: list[str] | None = None, skip_storage: bool = False) -> dict:
    from app.dependencies import get_service_supabase
    from app.db.engine import get_session_factory

    supabase = get_service_supabase()
    session = get_session_factory()()
    summary: dict[str, int] = {}
    try:
        for table in tables or TABLE_ORDER:
            summary[table] = migrate_table(supabase, session, table)
        if not skip_storage:
            summary["_storage_objects"] = migrate_storage(supabase)
    finally:
        session.close()
    logger.info("migration_complete", summary=json.dumps(summary))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate Supabase data into SQLite")
    parser.add_argument("--tables", help="comma-separated subset of tables")
    parser.add_argument("--skip-storage", action="store_true")
    args = parser.parse_args()
    tables = args.tables.split(",") if args.tables else None
    run(tables=tables, skip_storage=args.skip_storage)


if __name__ == "__main__":
    main()
