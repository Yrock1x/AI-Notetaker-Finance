"""Unit tests for DeliverableService on the SQLite + local-storage layer.

Seeds a deal with a completed analysis and a document, fakes the LLM, and
asserts generate() renders a real .docx, writes it to the ``deliverables``
bucket on disk, and returns a signed download URL.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from app.db.engine import (
    configure_engine,
    create_db_engine,
    get_session_factory,
)
from app.db.models import (
    Analysis,
    Deal,
    Document,
    Meeting,
    Organization,
    Profile,
)
from app.db.schema import init_schema
from app.services.deliverable_service import DeliverableService
from app.storage import local


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Fresh DB + local storage pointed at a tmp dir, with settings patched."""
    from app.core.config import settings

    engine = create_db_engine(str(tmp_path / "deliv.db"))
    configure_engine(engine)
    init_schema(engine)

    monkeypatch.setattr(settings, "storage_root", str(tmp_path / "storage"), raising=False)
    monkeypatch.setattr(settings, "storage_signing_key", "k", raising=False)
    monkeypatch.setattr(settings, "public_api_url", "http://w", raising=False)

    yield settings
    engine.dispose()


class _FakeResponse:
    def __init__(self, content: str, model: str) -> None:
        self.content = content
        self.model = model


class _FakeRouter:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def complete(self, **kwargs):  # noqa: ANN003
        self.calls.append(kwargs)
        return _FakeResponse(
            content="# Investment Memo\n\n- Strong revenue growth\n\nGreat deal.",
            model="fake/model",
        )


def _seed():
    session = get_session_factory()()
    try:
        org = Organization(name="Acme", slug="acme")
        user = Profile(email="a@x.com", full_name="Analyst")
        session.add_all([org, user])
        session.flush()

        deal = Deal(org_id=org.id, name="Project X", created_by=user.id)
        session.add(deal)
        session.flush()

        meeting = Meeting(
            org_id=org.id,
            deal_id=deal.id,
            title="Kickoff",
            created_by=user.id,
        )
        session.add(meeting)
        session.flush()

        session.add(
            Analysis(
                org_id=org.id,
                meeting_id=meeting.id,
                call_type="management_presentation",
                structured_output={"summary": "Revenue up 20%", "risks": ["churn"]},
                model_used="fake/model",
                status="completed",
                version=1,
            )
        )
        session.add(
            Document(
                org_id=org.id,
                deal_id=deal.id,
                title="CIM",
                document_type="cim",
                file_key="deal/cim.pdf",
                extracted_text="The company sells widgets to enterprises.",
                uploaded_by=user.id,
            )
        )
        session.commit()
        return deal.id
    finally:
        session.close()


@pytest.mark.asyncio
async def test_generate_writes_docx_and_returns_signed_url(env):
    settings = env
    deal_id = _seed()

    router = _FakeRouter()
    session = get_session_factory()()
    try:
        service = DeliverableService(
            session=session, settings=settings, llm_router=router
        )
        result = await service.generate(
            deal_id=UUID(deal_id), deliverable_type="investment_memo"
        )
    finally:
        session.close()

    assert result["status"] == "ready"
    assert result["deliverable_type"] == "investment_memo"
    assert result["file_format"] == "docx"

    # file_key is scoped under the deal id.
    file_key = result["file_key"]
    assert file_key.startswith(f"{deal_id}/")
    assert file_key.endswith(".docx")

    # download URL is the public api url + signed storage path.
    download_url = result["download_url"]
    assert download_url
    assert download_url.startswith("http://w/api/v1/storage/deliverables/")
    assert "expires=" in download_url and "sig=" in download_url

    # The LLM was actually consulted.
    assert len(router.calls) == 1

    # The docx bytes were written to disk and form a valid zip/docx (PK header).
    data = local.read_bytes("deliverables", file_key)
    assert data[:2] == b"PK"
    assert len(data) > 0
