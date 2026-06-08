"""WS5 auth tests: session tokens, first-login provisioning, cookie-based auth."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.provisioning import get_or_create_user
from app.auth.tokens import issue_session_token, verify_session_token
from app.core.config import settings
from app.db.engine import configure_engine, create_db_engine, get_session_factory
from app.db.models import OrgMembership, Organization, Profile
from app.db.schema import init_schema


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    monkeypatch.setattr(settings, "session_jwt_secret", "unit-test-secret")


@pytest.fixture()
def engine(tmp_path):
    eng = create_db_engine(str(tmp_path / "auth.db"))
    configure_engine(eng)
    init_schema(eng)
    yield eng
    eng.dispose()


# ---- tokens ---------------------------------------------------------------
def test_token_roundtrip():
    tok = issue_session_token("user-123", "a@b.com")
    claims = verify_session_token(tok)
    assert claims and claims["sub"] == "user-123" and claims["email"] == "a@b.com"


def test_token_tampered_rejected():
    tok = issue_session_token("user-123")
    assert verify_session_token(tok + "x") is None


def test_token_expired_rejected():
    tok = issue_session_token("user-123", ttl_seconds=-10)  # already expired
    assert verify_session_token(tok) is None


def test_wrong_secret_rejected(monkeypatch):
    tok = issue_session_token("user-123")
    monkeypatch.setattr(settings, "session_jwt_secret", "different-secret")
    assert verify_session_token(tok) is None


# ---- provisioning ---------------------------------------------------------
def test_first_login_creates_user_org_membership(engine):
    session = get_session_factory()()
    try:
        p = get_or_create_user(session, email="New.User@Example.com", full_name="New User")
        session.commit()
        # profile created
        assert p.email == "New.User@Example.com"
        # personal org + owner membership created
        mem = session.scalar(select(OrgMembership).where(OrgMembership.user_id == p.id))
        assert mem is not None and mem.role == "owner"
        org = session.get(Organization, mem.org_id)
        assert org is not None and org.slug
    finally:
        session.close()


def test_provisioning_idempotent_case_insensitive(engine):
    session = get_session_factory()()
    try:
        p1 = get_or_create_user(session, email="dup@example.com")
        session.commit()
        p2 = get_or_create_user(session, email="DUP@example.com")  # different case
        session.commit()
        assert p1.id == p2.id
        # exactly one profile + one org
        assert len(session.scalars(select(Profile)).all()) == 1
        assert len(session.scalars(select(Organization)).all()) == 1
    finally:
        session.close()


# ---- cookie-based auth end to end -----------------------------------------
def _app_with_real_auth():
    from app.api.v1 import auth_native
    from app.api.v1.store import deals

    app = FastAPI()
    app.include_router(auth_native.router, prefix="/auth")
    app.include_router(deals.router, prefix="/deals")
    return app


def test_session_cookie_authenticates(engine):
    # seed a user
    session = get_session_factory()()
    try:
        user = get_or_create_user(session, email="me@example.com", full_name="Me")
        session.commit()
        user_id = user.id
    finally:
        session.close()

    client = TestClient(_app_with_real_auth())
    # no cookie → unauthorized
    assert client.get("/auth/session").status_code == 401

    # with a valid session cookie → resolves the user, and store routes work
    client.cookies.set(settings.session_cookie_name, issue_session_token(user_id, "me@example.com"))
    sess = client.get("/auth/session")
    assert sess.status_code == 200, sess.text
    assert sess.json()["email"] == "me@example.com"
    # the same cookie authorizes a store endpoint (deals list, scoped to the user's org)
    assert client.get("/deals").status_code == 200


def test_unknown_provider_404():
    client = TestClient(_app_with_real_auth())
    assert client.get("/auth/login/myspace").status_code == 404


def test_signout_clears_cookie():
    client = TestClient(_app_with_real_auth())
    client.cookies.set(settings.session_cookie_name, "whatever")
    resp = client.post("/auth/signout")
    assert resp.status_code == 200 and resp.json()["ok"] is True
