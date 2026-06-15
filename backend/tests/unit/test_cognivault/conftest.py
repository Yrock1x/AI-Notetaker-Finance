"""Harness for the CogniVault "Connect a deal to a VDR" flow.

Fresh file-backed SQLite per test, one tenant (org A) with a deal, plus a user with
no membership for the access-control tests. The client overrides ``get_current_user``
(the routers use the real ``get_principal`` / ``scoped_deal_or_404``). CogniVault OAuth
config is set on ``settings`` so ``is_configured()`` is true.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.cognivault import router as cognivault_router
from app.core.config import settings
from app.db.engine import configure_engine, create_db_engine, get_session_factory
from app.db.models import Deal, DealMembership, Organization, OrgMembership, Profile
from app.db.schema import init_schema
from app.dependencies import AuthUser, get_current_user

PREFIX = "/api/v1/cognivault"


class Seed:
    def __init__(self) -> None:
        self.org_a: str = ""
        self.user_a: str = ""
        self.deal_a: str = ""
        self.user_none: str = ""


@pytest.fixture()
def db(tmp_path):
    engine = create_db_engine(str(tmp_path / "cognivault.db"))
    configure_engine(engine)
    init_schema(engine)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def cognivault_config(monkeypatch):
    """Make the CogniVault OAuth client appear configured."""
    monkeypatch.setattr(settings, "cognivault_client_id", "cogniscribe-client")
    monkeypatch.setattr(settings, "cognivault_client_secret", "shh")
    monkeypatch.setattr(
        settings, "cognivault_authorize_url", "https://vault.example.com/oauth/authorize"
    )
    monkeypatch.setattr(
        settings, "cognivault_token_url", "https://vault.example.com/oauth/token"
    )
    monkeypatch.setattr(settings, "public_api_url", "https://worker.example.com")
    monkeypatch.setattr(settings, "frontend_url", "https://app.example.com")
    monkeypatch.setattr(settings, "worker_internal_token", "state-signing-secret")


@pytest.fixture()
def seed(db) -> Seed:
    s = Seed()
    session = get_session_factory()()
    try:
        org = Organization(name="orga", slug="orga")
        user = Profile(email="orga@x.com", full_name="OrgA Owner")
        session.add_all([org, user])
        session.flush()
        session.add(OrgMembership(org_id=org.id, user_id=user.id, role="owner"))
        deal = Deal(org_id=org.id, name="orga deal", created_by=user.id)
        session.add(deal)
        session.flush()
        session.add(
            DealMembership(deal_id=deal.id, user_id=user.id, org_id=org.id, role="lead")
        )
        nobody = Profile(email="nobody@x.com", full_name="Nobody")
        session.add(nobody)
        session.flush()
        s.org_a, s.user_a, s.deal_a, s.user_none = org.id, user.id, deal.id, nobody.id
        session.commit()
    finally:
        session.close()
    return s


@pytest.fixture()
def make_client(db):
    clients: list[TestClient] = []

    def _factory(user_id: str) -> TestClient:
        app = FastAPI(redirect_slashes=False)
        app.include_router(cognivault_router, prefix=PREFIX)

        def _fake_user() -> AuthUser:
            return AuthUser(id=UUID(user_id), email=None, raw_claims={"sub": user_id})

        app.dependency_overrides[get_current_user] = _fake_user
        c = TestClient(app)
        clients.append(c)
        return c

    yield _factory
    for c in clients:
        c.close()
