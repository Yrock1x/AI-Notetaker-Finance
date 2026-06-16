"""Tests for the migrated OAuth credential layer and the new
``/internal/meeting-status`` endpoint, all against the SQLite engine.

``app/services/oauth_tokens.py`` now takes a SQLAlchemy ``Session`` instead of
a Supabase client. These tests seed an Org/Profile, then exercise
save/list/deactivate/get-valid-token directly, plus drive the meeting-status
endpoint through a ``TestClient`` with ``get_db`` pointed at a throwaway engine.
"""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.engine import configure_engine, create_db_engine, get_session_factory
from app.db.models import Deal, Meeting, Organization, Profile
from app.db.schema import init_schema
from app.main import create_app

INTERNAL_TOKEN = "t"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def engine(tmp_path):
    eng = create_db_engine(str(tmp_path / "test.db"))
    configure_engine(eng)
    init_schema(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    s = get_session_factory()()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    monkeypatch.setattr(settings, "worker_internal_token", INTERNAL_TOKEN)
    monkeypatch.setattr(
        settings, "token_encryption_key", Fernet.generate_key().decode()
    )


@pytest.fixture()
def client(engine):
    app = create_app()

    def _override_get_db():
        session = get_session_factory()()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    from app.db.engine import get_db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------
def _seed_org_user(session, *, slug: str = "acme"):
    org = Organization(name=slug, slug=slug)
    user = Profile(email=f"{slug}@example.com", full_name=slug)
    session.add_all([org, user])
    session.flush()
    return org, user


def _seed_meeting(session, org, user, **kw):
    deal = Deal(org_id=org.id, name="d", created_by=user.id)
    session.add(deal)
    session.flush()
    m = Meeting(
        org_id=org.id,
        deal_id=deal.id,
        title=kw.pop("title", "Test meeting"),
        created_by=user.id,
        status=kw.pop("status", "uploading"),
        **kw,
    )
    session.add(m)
    session.flush()
    return m


# ---------------------------------------------------------------------------
# oauth_tokens
# ---------------------------------------------------------------------------
async def test_save_and_get_valid_access_token_roundtrip(db):
    from uuid import UUID

    from app.services.oauth_tokens import (
        get_valid_access_token,
        save_credentials,
    )

    org, user = _seed_org_user(db)
    org_id = UUID(org.id)
    user_id = UUID(user.id)

    save_credentials(
        db,
        org_id=org_id,
        user_id=user_id,
        platform="zoom",
        access_token="secret-access",
        refresh_token="secret-refresh",
        expires_in_seconds=3600,  # well beyond the 60s refresh window
        scopes="meeting:read",
    )
    db.commit()

    # Non-expired token is returned without any refresh call.
    token = await get_valid_access_token(
        db, org_id=org_id, user_id=user_id, platform="zoom"
    )
    assert token == "secret-access"


def test_list_user_integrations_shape(db):
    from uuid import UUID

    from app.services.oauth_tokens import (
        list_user_integrations,
        save_credentials,
    )

    org, user = _seed_org_user(db, slug="lister")
    save_credentials(
        db,
        org_id=UUID(org.id),
        user_id=UUID(user.id),
        platform="google",
        access_token="a",
        refresh_token="r",
        expires_in_seconds=3600,
        scopes="calendar",
    )
    db.commit()

    rows = list_user_integrations(db, user_id=UUID(user.id))
    assert len(rows) == 1
    row = rows[0]
    assert row["platform"] == "google"
    assert row["is_active"] is True
    assert row["scopes"] == "calendar"
    assert "connected_at" in row
    assert "token_expires_at" in row


def test_deactivate_credentials_hides_integration(db):
    from uuid import UUID

    from app.services.oauth_tokens import (
        deactivate_credentials,
        list_user_integrations,
        save_credentials,
    )

    org, user = _seed_org_user(db, slug="off")
    save_credentials(
        db,
        org_id=UUID(org.id),
        user_id=UUID(user.id),
        platform="microsoft",
        access_token="a",
        refresh_token="r",
        expires_in_seconds=3600,
        scopes=None,
    )
    db.commit()
    assert list_user_integrations(db, user_id=UUID(user.id))

    deactivate_credentials(
        db, org_id=UUID(org.id), user_id=UUID(user.id), platform="microsoft"
    )
    db.commit()
    assert list_user_integrations(db, user_id=UUID(user.id)) == []


def test_save_credentials_upserts_in_place(db):
    from uuid import UUID

    from sqlalchemy import select

    from app.db.models import IntegrationCredential
    from app.services.oauth_tokens import decrypt_token, save_credentials

    org, user = _seed_org_user(db, slug="upsert")
    org_id, user_id = UUID(org.id), UUID(user.id)
    for tok in ("first", "second"):
        save_credentials(
            db,
            org_id=org_id,
            user_id=user_id,
            platform="zoom",
            access_token=tok,
            refresh_token="r",
            expires_in_seconds=3600,
            scopes=None,
        )
    db.commit()

    rows = db.scalars(
        select(IntegrationCredential).where(
            IntegrationCredential.user_id == user.id
        )
    ).all()
    assert len(rows) == 1
    assert decrypt_token(rows[0].access_token_encrypted) == "second"


# ---------------------------------------------------------------------------
# /internal/meeting-status
# ---------------------------------------------------------------------------
def _headers() -> dict[str, str]:
    return {"X-Internal-Token": INTERNAL_TOKEN}


def test_meeting_status_flips_status(client, db):
    org, user = _seed_org_user(db, slug="status")
    meeting = _seed_meeting(db, org, user, status="uploading")
    db.commit()

    resp = client.post(
        "/api/v1/internal/meeting-status",
        json={
            "meeting_id": meeting.id,
            "status": "failed",
            "error_message": "boom",
        },
        headers=_headers(),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"ok": True}

    db.expire_all()
    refreshed = db.get(Meeting, meeting.id)
    assert refreshed.status == "failed"
    assert refreshed.error_message == "boom"


def test_meeting_status_unknown_meeting_404(client, db):
    resp = client.post(
        "/api/v1/internal/meeting-status",
        json={"meeting_id": "does-not-exist", "status": "uploaded"},
        headers=_headers(),
    )
    assert resp.status_code == 404


def test_meeting_status_missing_token_401(client, db):
    org, user = _seed_org_user(db, slug="notoken")
    meeting = _seed_meeting(db, org, user)
    db.commit()
    resp = client.post(
        "/api/v1/internal/meeting-status",
        json={"meeting_id": meeting.id, "status": "uploaded"},
    )
    assert resp.status_code == 401
