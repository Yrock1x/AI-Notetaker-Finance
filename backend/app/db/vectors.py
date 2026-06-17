"""vec0 virtual table for embeddings + server-side KNN search.

Replaces pgvector and the ``match_embeddings_for_deal`` RPC. The 768-dim vectors
live in a vec0 virtual table keyed by ``embeddings.id`` and partitioned by
``deal_id`` so per-deal KNN is efficient. Cosine distance; similarity = 1 - dist.

The normal ``embeddings`` row (chunk_text, metadata, etc.) lives in the ORM
table; this module owns only the vector + the search.
"""

from __future__ import annotations

import sqlite_vec  # type: ignore[import-untyped]  # no stubs / py.typed marker
from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.db.models import Embedding

EMBEDDING_DIM = 768
VEC_TABLE = "vec_embeddings"

_CREATE_VEC_TABLE = f"""
CREATE VIRTUAL TABLE IF NOT EXISTS {VEC_TABLE} USING vec0(
    embedding_id TEXT PRIMARY KEY,
    deal_id TEXT PARTITION KEY,
    embedding FLOAT[{EMBEDDING_DIM}] distance_metric=cosine
)
"""


def create_vec_table(target: Session | Connection) -> None:
    """Create the vec0 virtual table (idempotent). Call once at schema init."""
    target.execute(text(_CREATE_VEC_TABLE))


def upsert_vector(
    session: Session, *, embedding_id: str, deal_id: str, vector: list[float]
) -> None:
    """Insert/replace the vector for an embeddings row."""
    blob = sqlite_vec.serialize_float32(vector)
    session.execute(
        text(f"DELETE FROM {VEC_TABLE} WHERE embedding_id = :id"),  # noqa: S608 — constant table name, bound params
        {"id": embedding_id},
    )
    session.execute(
        text(
            f"INSERT INTO {VEC_TABLE}(embedding_id, deal_id, embedding) "  # noqa: S608 — constant table name, bound params
            "VALUES (:id, :deal, :emb)"
        ),
        {"id": embedding_id, "deal": deal_id, "emb": blob},
    )


def delete_vectors(session: Session, embedding_ids: list[str]) -> None:
    if not embedding_ids:
        return
    stmt = text(
        f"DELETE FROM {VEC_TABLE} WHERE embedding_id IN :ids"  # noqa: S608 — constant table name, bound params
    ).bindparams(bindparam("ids", expanding=True))
    session.execute(stmt, {"ids": embedding_ids})


def match_embeddings_for_deal(
    session: Session,
    *,
    deal_id: str,
    query_vector: list[float],
    top_k: int = 15,
    min_similarity: float = 0.3,
    source_ids: list[str] | None = None,
) -> list[dict]:
    """Cosine KNN over a deal's embeddings.

    Returns the same shape the old Postgres RPC did:
    ``{id, source_type, source_id, chunk_text, similarity, metadata}``.

    ``source_ids`` optionally restricts results to embeddings whose
    ``source_id`` is in the allowlist (used to scope Q&A to a subset of
    meetings — the allowlist is that subset's transcript-segment ids). vec0's
    partitioned KNN can't join an arbitrary IN-list, so we over-fetch on the
    ``deal_id`` partition and filter the hydrated rows, then truncate to
    ``top_k``.
    """
    blob = sqlite_vec.serialize_float32(query_vector)
    # Over-fetch when filtering by source so enough candidates survive the
    # allowlist to still return up to top_k.
    knn_k = top_k * 4 if source_ids is not None else top_k
    source_id_set = set(source_ids) if source_ids is not None else None
    knn = session.execute(
        text(
            "SELECT embedding_id, distance "  # noqa: S608 — constant table name, bound params
            f"FROM {VEC_TABLE} "
            "WHERE deal_id = :deal_id AND embedding MATCH :q AND k = :k "
            "ORDER BY distance"
        ),
        {"deal_id": str(deal_id), "q": blob, "k": knn_k},
    ).all()
    if not knn:
        return []

    sim_by_id = {row[0]: 1.0 - float(row[1]) for row in knn}
    ids = list(sim_by_id.keys())

    rows = session.query(Embedding).filter(Embedding.id.in_(ids)).all()
    by_id = {r.id: r for r in rows}

    out: list[dict] = []
    for emb_id in ids:  # preserve KNN order (closest first)
        similarity = sim_by_id[emb_id]
        if similarity < min_similarity:
            continue
        row = by_id.get(emb_id)
        if row is None:
            continue
        if source_id_set is not None and row.source_id not in source_id_set:
            continue
        out.append(
            {
                "id": row.id,
                "source_type": row.source_type,
                "source_id": row.source_id,
                "chunk_text": row.chunk_text,
                "similarity": similarity,
                "metadata": row.metadata_json or {},
            }
        )
        if len(out) >= top_k:
            break
    return out
