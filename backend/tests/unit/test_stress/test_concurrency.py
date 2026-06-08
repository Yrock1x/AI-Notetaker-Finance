"""Concurrency / stress tests for the SQLite data layer.

These exercise the data layer the way production does: a synchronous SQLAlchemy
engine (WAL, busy_timeout=5000) shared across many threads, each thread using its
OWN session from ``get_session_factory()`` -- mirroring FastAPI running sync
handlers in a threadpool.

The hot path under test is the live-transcript writer: many small inserts on
``transcript_segments`` for a single meeting, while readers query the same table.

The risk being proven absent is "database is locked" (sqlite3.OperationalError)
and lost writes under concurrent writers + readers.

Run with ``-s`` to see the timing logs from Test D.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app.db.base import gen_uuid
from app.db.engine import configure_engine, create_db_engine, get_session_factory
from app.db.models import (
    Deal,
    Embedding,
    Meeting,
    Organization,
    Profile,
    TranscriptSegment,
)
from app.db.schema import init_schema
from app.db.vectors import match_embeddings_for_deal, upsert_vector


# ---------------------------------------------------------------------------
# fixture: ONE file-backed engine + a seeded org/profile/deal/meeting
# ---------------------------------------------------------------------------
@pytest.fixture()
def seeded(tmp_path):
    """A single shared engine (file-backed so WAL + multi-connection is real)
    plus a seeded Org/Profile/Deal/Meeting. Yields the ids the tests need.
    """
    engine = create_db_engine(str(tmp_path / "stress.db"))
    configure_engine(engine)
    init_schema(engine)

    factory = get_session_factory()
    s = factory()
    try:
        org = Organization(name="acme", slug="acme")
        user = Profile(email="seed@example.com", full_name="seed")
        s.add_all([org, user])
        s.flush()
        deal = Deal(org_id=org.id, name="acme deal", created_by=user.id)
        s.add(deal)
        s.flush()
        meeting = Meeting(
            org_id=org.id,
            deal_id=deal.id,
            title="live call",
            created_by=user.id,
            status="recording",
        )
        s.add(meeting)
        s.commit()
        ids = {
            "org_id": org.id,
            "user_id": user.id,
            "deal_id": deal.id,
            "meeting_id": meeting.id,
        }
    finally:
        s.close()

    try:
        yield ids
    finally:
        engine.dispose()


def _is_locked_error(exc: BaseException) -> bool:
    """True if the exception is a SQLite 'database is locked' error."""
    msg = str(exc).lower()
    if "database is locked" in msg or "database table is locked" in msg:
        return True
    if isinstance(exc, (OperationalError, sqlite3.OperationalError)):
        return "locked" in msg
    return False


def _make_segment(meeting_id: str, index: int) -> TranscriptSegment:
    return TranscriptSegment(
        meeting_id=meeting_id,
        speaker_label=f"S{index % 3}",
        speaker_name=f"Speaker {index % 3}",
        text=f"segment text number {index}",
        start_time=float(index),
        end_time=float(index) + 0.9,
        confidence=0.95,
        segment_index=index,
        is_partial=False,
        recall_segment_id=f"recall-{index}",
    )


# ---------------------------------------------------------------------------
# Test A: concurrent writers
# ---------------------------------------------------------------------------
def test_concurrent_writers_no_lost_writes(seeded):
    meeting_id = seeded["meeting_id"]
    factory = get_session_factory()

    n_workers = 8
    total_rows = 400
    per_worker = total_rows // n_workers  # 50 each
    assert per_worker * n_workers == total_rows

    errors: list[BaseException] = []

    def writer(worker_idx: int) -> None:
        session = factory()
        try:
            base = worker_idx * per_worker
            for i in range(per_worker):
                session.add(_make_segment(meeting_id, base + i))
                # commit each row individually -> maximally contended, like the
                # live-transcript path that UPSERTs one segment per webhook.
                session.commit()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)
            session.rollback()
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        futures = [pool.submit(writer, w) for w in range(n_workers)]
        for f in as_completed(futures):
            f.result()

    locked = [e for e in errors if _is_locked_error(e)]
    assert not locked, f"database-is-locked errors under concurrent writers: {locked}"
    assert not errors, f"unexpected writer errors: {errors!r}"

    verify = factory()
    try:
        count = verify.scalar(
            select(func.count())
            .select_from(TranscriptSegment)
            .where(TranscriptSegment.meeting_id == meeting_id)
        )
    finally:
        verify.close()
    assert count == total_rows, f"lost writes: expected {total_rows}, got {count}"


# ---------------------------------------------------------------------------
# Test B: writers + readers concurrently
# ---------------------------------------------------------------------------
def test_writers_and_readers_concurrent(seeded):
    meeting_id = seeded["meeting_id"]
    factory = get_session_factory()

    n_writers = 6
    n_readers = 4
    total_rows = 300
    per_writer = total_rows // n_writers  # 50 each
    assert per_writer * n_writers == total_rows

    errors: list[BaseException] = []
    stop = threading.Event()
    read_iterations = [0]
    read_lock = threading.Lock()

    def writer(worker_idx: int) -> None:
        session = factory()
        try:
            base = worker_idx * per_writer
            for i in range(per_writer):
                session.add(_make_segment(meeting_id, base + i))
                session.commit()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)
            session.rollback()
        finally:
            session.close()

    def reader() -> None:
        # Fresh session per loop iteration, like a new request hitting a
        # threadpool worker.
        try:
            while not stop.is_set():
                session = factory()
                try:
                    cnt = session.scalar(
                        select(func.count())
                        .select_from(TranscriptSegment)
                        .where(TranscriptSegment.meeting_id == meeting_id)
                    )
                    # Also exercise a list/order query (the live panel does this).
                    rows = (
                        session.execute(
                            select(TranscriptSegment.id)
                            .where(TranscriptSegment.meeting_id == meeting_id)
                            .order_by(TranscriptSegment.start_time)
                            .limit(50)
                        )
                        .scalars()
                        .all()
                    )
                    assert cnt is not None
                    assert len(rows) <= 50
                    with read_lock:
                        read_iterations[0] += 1
                finally:
                    session.close()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    with ThreadPoolExecutor(max_workers=n_writers + n_readers) as pool:
        reader_futures = [pool.submit(reader) for _ in range(n_readers)]
        writer_futures = [pool.submit(writer, w) for w in range(n_writers)]
        for f in as_completed(writer_futures):
            f.result()
        stop.set()
        for f in as_completed(reader_futures):
            f.result()

    locked = [e for e in errors if _is_locked_error(e)]
    assert not locked, f"database-is-locked errors with writers+readers: {locked}"
    assert not errors, f"unexpected errors with writers+readers: {errors!r}"
    assert read_iterations[0] > 0, "readers never ran a query"

    verify = factory()
    try:
        count = verify.scalar(
            select(func.count())
            .select_from(TranscriptSegment)
            .where(TranscriptSegment.meeting_id == meeting_id)
        )
    finally:
        verify.close()
    assert count == total_rows, f"lost writes: expected {total_rows}, got {count}"


# ---------------------------------------------------------------------------
# Test C: concurrent embeddings + vector upserts, then KNN search
# ---------------------------------------------------------------------------
def _unit_vector(dim: int, hot: int) -> list[float]:
    v = [0.0] * dim
    v[hot % dim] = 1.0
    return v


def test_concurrent_embeddings_and_vector_search(seeded):
    org_id = seeded["org_id"]
    deal_id = seeded["deal_id"]
    factory = get_session_factory()

    n_workers = 6
    per_worker = 10
    total = n_workers * per_worker  # 60

    errors: list[BaseException] = []

    def inserter(worker_idx: int) -> None:
        session = factory()
        try:
            for i in range(per_worker):
                hot = (worker_idx * per_worker + i) % 768
                emb = Embedding(
                    org_id=org_id,
                    deal_id=deal_id,
                    source_type="transcript_segment",
                    source_id=gen_uuid(),
                    chunk_text=f"chunk w{worker_idx} i{i} hot{hot}",
                    chunk_index=i,
                    metadata_json={"hot": hot},
                )
                session.add(emb)
                session.flush()  # populate emb.id
                upsert_vector(
                    session,
                    embedding_id=emb.id,
                    deal_id=deal_id,
                    vector=_unit_vector(768, hot),
                )
                session.commit()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)
            session.rollback()
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        futures = [pool.submit(inserter, w) for w in range(n_workers)]
        for f in as_completed(futures):
            f.result()

    locked = [e for e in errors if _is_locked_error(e)]
    assert not locked, f"database-is-locked errors during embedding inserts: {locked}"
    assert not errors, f"unexpected errors during embedding inserts: {errors!r}"

    verify = factory()
    try:
        emb_count = verify.scalar(
            select(func.count())
            .select_from(Embedding)
            .where(Embedding.deal_id == deal_id)
        )
        assert emb_count == total, f"expected {total} embeddings, got {emb_count}"

        # Each hot axis 0..total-1 is distinct; querying axis 0 must return a
        # perfect hit, and a broad top_k must see every vector we inserted.
        hits = match_embeddings_for_deal(
            verify,
            deal_id=deal_id,
            query_vector=_unit_vector(768, 0),
            top_k=total,
            min_similarity=-1.0,  # don't filter; we want to count all stored vectors
        )
        assert len(hits) == total, f"expected {total} KNN hits, got {len(hits)}"
        # Best hit is the axis-0 vector (cosine sim ~1.0).
        assert hits[0]["similarity"] > 0.99
    finally:
        verify.close()


# ---------------------------------------------------------------------------
# Test D: write throughput smoke check
# ---------------------------------------------------------------------------
def test_write_throughput_under_bound(seeded, capsys):
    meeting_id = seeded["meeting_id"]
    factory = get_session_factory()

    n_workers = 8
    total_rows = 500
    per_worker = total_rows // n_workers
    remainder = total_rows - per_worker * n_workers  # spread leftover onto worker 0

    errors: list[BaseException] = []

    def writer(worker_idx: int) -> None:
        count = per_worker + (remainder if worker_idx == 0 else 0)
        base = worker_idx * 10_000  # disjoint segment_index ranges
        session = factory()
        try:
            for i in range(count):
                session.add(_make_segment(meeting_id, base + i))
                session.commit()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)
            session.rollback()
        finally:
            session.close()

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        futures = [pool.submit(writer, w) for w in range(n_workers)]
        for f in as_completed(futures):
            f.result()
    elapsed = time.perf_counter() - start

    locked = [e for e in errors if _is_locked_error(e)]
    assert not locked, f"database-is-locked errors during throughput run: {locked}"
    assert not errors, f"unexpected errors during throughput run: {errors!r}"

    verify = factory()
    try:
        count = verify.scalar(
            select(func.count())
            .select_from(TranscriptSegment)
            .where(TranscriptSegment.meeting_id == meeting_id)
        )
    finally:
        verify.close()
    assert count == total_rows, f"lost writes: expected {total_rows}, got {count}"

    rate = total_rows / elapsed if elapsed else float("inf")
    with capsys.disabled():
        print(
            f"\n[throughput] inserted {total_rows} segments via {n_workers} "
            f"concurrent writers in {elapsed:.3f}s ({rate:.0f} rows/s)"
        )

    assert elapsed < 10.0, f"throughput too slow: {elapsed:.3f}s for {total_rows} rows"
