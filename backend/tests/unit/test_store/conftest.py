"""Shared harness for store-router tests.

Builds a fresh file-backed SQLite DB per test, points the global engine at it,
and gives each test a TestClient whose ``get_current_user`` is overridden to a
chosen seeded user. Routers use the real ``get_db``/``get_principal``, so scoping
is exercised for real.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.store._common import access_denied_handler
from app.db.engine import configure_engine, create_db_engine, get_session_factory
from app.db.models import Deal, DealMembership, Organization, OrgMembership, Profile
from app.db.schema import init_schema
from app.db.scope import AccessDenied
from app.dependencies import AuthUser, get_current_user


class Seed:
    """Identifiers for two isolated tenants, for cross-tenant tests."""

    def __init__(self) -> None:
        # org A
        self.org_a: str = ""
        self.user_a: str = ""
        self.deal_a: str = ""
        # org B
        self.org_b: str = ""
        self.user_b: str = ""
        self.deal_b: str = ""
        # a user with no memberships
        self.user_none: str = ""


@pytest.fixture()
def db(tmp_path):
    engine = create_db_engine(str(tmp_path / "store.db"))
    configure_engine(engine)
    init_schema(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def seed(db) -> Seed:
    s = Seed()
    session = get_session_factory()()
    try:
        def make_tenant(slug: str):
            org = Organization(name=slug, slug=slug)
            user = Profile(email=f"{slug}@x.com", full_name=slug.upper())
            session.add_all([org, user])
            session.flush()
            session.add(OrgMembership(org_id=org.id, user_id=user.id, role="owner"))
            deal = Deal(org_id=org.id, name=f"{slug} deal", created_by=user.id)
            session.add(deal)
            session.flush()
            session.add(
                DealMembership(deal_id=deal.id, user_id=user.id, org_id=org.id, role="lead")
            )
            return org.id, user.id, deal.id

        s.org_a, s.user_a, s.deal_a = make_tenant("orga")
        s.org_b, s.user_b, s.deal_b = make_tenant("orgb")
        nobody = Profile(email="nobody@x.com", full_name="Nobody")
        session.add(nobody)
        session.flush()
        s.user_none = nobody.id
        session.commit()
    finally:
        session.close()
    return s


@pytest.fixture()
def make_client(db):
    """Returns a factory: make_client(routers, user_id) -> TestClient.

    ``routers`` is a list of (prefix, APIRouter).
    """
    clients: list[TestClient] = []

    def _factory(routers, user_id: str) -> TestClient:
        app = FastAPI()
        app.add_exception_handler(AccessDenied, access_denied_handler)
        for prefix, r in routers:
            app.include_router(r, prefix=prefix)

        def _fake_user() -> AuthUser:
            return AuthUser(id=UUID(user_id), email=None, raw_claims={"sub": user_id})

        app.dependency_overrides[get_current_user] = _fake_user
        c = TestClient(app)
        clients.append(c)
        return c

    yield _factory
    for c in clients:
        c.close()
