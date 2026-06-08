"""Tests for the pure transform helpers in the Supabase→SQLite migration."""

from __future__ import annotations

import pytest

from app.db.migrate_from_supabase import (
    TABLE_ORDER,
    parse_pgvector,
    row_to_model_kwargs,
)


def test_table_order_parents_before_children():
    # a few critical ordering invariants
    assert TABLE_ORDER.index("organizations") < TABLE_ORDER.index("deals")
    assert TABLE_ORDER.index("deals") < TABLE_ORDER.index("meetings")
    assert TABLE_ORDER.index("meetings") < TABLE_ORDER.index("transcript_segments")
    assert TABLE_ORDER.index("analyses") < TABLE_ORDER.index("action_item_completions")


def test_parse_pgvector_from_list():
    assert parse_pgvector([1, 2, 3]) == [1.0, 2.0, 3.0]


def test_parse_pgvector_from_string():
    assert parse_pgvector("[0.5, -1, 2.25]") == [0.5, -1.0, 2.25]


def test_parse_pgvector_empty_and_none():
    assert parse_pgvector(None) is None
    assert parse_pgvector("[]") == []


def test_parse_pgvector_bad_value():
    with pytest.raises(ValueError):
        parse_pgvector(42)


def test_embeddings_row_maps_metadata_and_drops_vector():
    row = {
        "id": "e1",
        "deal_id": "d1",
        "org_id": "o1",
        "source_type": "document_chunk",
        "source_id": "s1",
        "chunk_text": "hi",
        "embedding": [1, 2, 3],
        "metadata": {"page": 2},
    }
    kwargs = row_to_model_kwargs("embeddings", row)
    assert "embedding" not in kwargs  # vector handled separately
    assert "metadata" not in kwargs
    assert kwargs["metadata_json"] == {"page": 2}


def test_non_embedding_row_passthrough():
    row = {"id": "d1", "org_id": "o1", "name": "Acme"}
    assert row_to_model_kwargs("deals", row) == row
