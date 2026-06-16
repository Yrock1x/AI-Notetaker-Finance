"""Email/password (local account) auth: hashing, register, login, OAuth linking."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.passwords import hash_password, verify_password
from app.auth.provisioning import get_or_create_user
from app.core.config import settings
from app.db.engine import configure_engine, create_db_engine, get_session_factory
from app.db.models import Profile
from app.db.schema import init_schema


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    monkeypatch.setattr(settings, "session_jwt_secret", "unit-test-secret")


@pytest.fixture()
def engine(tmp_path):
    eng = create_db_engine(str(tmp_path / "pw.db"))
    configure_engine(eng)
    init_schema(eng)
    yield eng
    eng.dispose()


def _app():
    from app.api.v1 import auth_native

    app = FastAPI()
    app.include_router(auth_native.router, prefix="/auth")
    return app


def _register(client, email, password="longenough1", **extra):
    return client.post("/auth/register", json={"email": email, "password": password, **extra})


def _login(client, email, password="longenough1"):
    return client.post("/auth/login", json={"email": email, "password": password})


# ---- hashing --------------------------------------------------------------
def test_hash_roundtrip():
    h = hash_password("correct horse battery staple")
    assert h != "correct horse battery staple"  # not plaintext
    assert verify_password("correct horse battery staple", h) is True
    assert verify_password("wrong", h) is False


def test_verify_malformed_hash_is_false():
    # Never raises on a garbage/legacy hash — just "no match".
    assert verify_password("anything", "not-a-real-argon2-hash") is False


# ---- register -------------------------------------------------------------
def test_register_creates_account_and_authenticates(engine):
    client = TestClient(_app())
    resp = _register(client, "New@Example.com", "hunter2hunter2", full_name="New U")
    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == "New@Example.com"
    # The response set the session cookie → the user is immediately signed in.
    assert settings.session_cookie_name in resp.cookies
    sess = client.get("/auth/session")
    assert sess.status_code == 200 and sess.json()["email"] == "New@Example.com"

    # Password is stored hashed, not in plaintext.
    s = get_session_factory()()
    try:
        p = s.scalar(select(Profile).where(Profile.email == "New@Example.com"))
        assert p is not None
        assert p.password_hash and p.password_hash != "hunter2hunter2"
    finally:
        s.close()


def test_register_rejects_short_password(engine):
    client = TestClient(_app())
    assert _register(client, "a@b.com", "short").status_code == 422


def test_register_rejects_bad_email(engine):
    client = TestClient(_app())
    assert _register(client, "nope").status_code == 422


def test_register_duplicate_email_conflicts(engine):
    client = TestClient(_app())
    assert _register(client, "dup@example.com").status_code == 200
    # Same email (any case) → 409, and no second account is created.
    assert _register(client, "DUP@example.com", "other12345").status_code == 409


def test_register_blocks_password_on_existing_oauth_account(engine):
    # An OAuth-provisioned account (no password) must not get a password set via
    # /register — that would be takeover without proof of email ownership.
    s = get_session_factory()()
    try:
        get_or_create_user(s, email="oauth@example.com", full_name="OAuth User")
        s.commit()
    finally:
        s.close()

    client = TestClient(_app())
    assert _register(client, "oauth@example.com").status_code == 409


# ---- login ----------------------------------------------------------------
def test_login_success(engine):
    client = TestClient(_app())
    _register(client, "me@example.com")
    client.cookies.clear()  # drop the auto-login cookie; log in fresh

    resp = _login(client, "me@example.com")
    assert resp.status_code == 200, resp.text
    assert settings.session_cookie_name in resp.cookies
    assert client.get("/auth/session").status_code == 200


def test_login_wrong_password_401(engine):
    client = TestClient(_app())
    _register(client, "me@example.com")
    client.cookies.clear()
    assert _login(client, "me@example.com", "WRONGwrong1").status_code == 401


def test_login_unknown_email_401(engine):
    client = TestClient(_app())
    assert _login(client, "ghost@example.com").status_code == 401


def test_login_case_insensitive_email(engine):
    client = TestClient(_app())
    _register(client, "Me@Example.com")
    client.cookies.clear()
    assert _login(client, "me@example.com").status_code == 200


def test_login_oauth_only_account_gets_hint(engine):
    # Account exists via OAuth (no password) → 403 nudging to the provider button.
    s = get_session_factory()()
    try:
        get_or_create_user(s, email="oauth@example.com")
        s.commit()
    finally:
        s.close()
    client = TestClient(_app())
    resp = _login(client, "oauth@example.com")
    assert resp.status_code == 403
    assert "google" in resp.json()["detail"].lower()


def test_password_signup_then_oauth_links_same_account(engine):
    # Register with a password, then simulate an OAuth login for the same email:
    # provisioning must return the SAME profile (link by email), not a duplicate.
    client = TestClient(_app())
    reg = _register(client, "shared@example.com")
    password_id = reg.json()["id"]

    s = get_session_factory()()
    try:
        oauth_profile = get_or_create_user(s, email="SHARED@example.com")
        s.commit()
        assert oauth_profile.id == password_id
        assert len(s.scalars(select(Profile)).all()) == 1
    finally:
        s.close()
