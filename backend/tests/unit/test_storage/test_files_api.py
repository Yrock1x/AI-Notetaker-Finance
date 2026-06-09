"""Integration tests for the storage HTTP endpoints."""

from __future__ import annotations

from urllib.parse import urlparse

import pytest

from app.api.v1.store import files
from app.storage import local


@pytest.fixture(autouse=True)
def _storage_env(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "storage_root", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "storage_signing_key", "testkey", raising=False)
    yield


def _client(make_client, user_id):
    return make_client([("", files.router)], user_id)


def _route(url: str) -> str:
    """Translate a worker-absolute signed URL to the router's mount path.

    The router is mounted at prefix "" in these tests, but make_signed_url
    bakes in the real "/api/v1" prefix the worker uses in production.
    """
    return url.replace("/api/v1", "", 1)


def test_upload_ticket_for_own_deal(make_client, seed):
    c = _client(make_client, seed.user_a)
    resp = c.post(
        "/storage/upload-ticket",
        json={"bucket": "deal-documents", "deal_id": seed.deal_a, "filename": "memo.pdf"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["bucket"] == "deal-documents"
    assert body["method"] == "PUT"
    assert body["key"].startswith(f"{seed.deal_a}/")
    assert body["key"].endswith(".pdf")
    assert body["upload_url"].startswith("/api/v1/storage/deal-documents/")


def test_upload_ticket_other_tenant_deal_404(make_client, seed):
    c = _client(make_client, seed.user_a)
    resp = c.post(
        "/storage/upload-ticket",
        json={"bucket": "deal-documents", "deal_id": seed.deal_b, "filename": "memo.pdf"},
    )
    assert resp.status_code == 404, resp.text


def test_put_then_get_roundtrip(make_client, seed):
    c = _client(make_client, seed.user_a)
    ticket = c.post(
        "/storage/upload-ticket",
        json={"bucket": "deal-documents", "deal_id": seed.deal_a, "filename": "memo.txt"},
    ).json()

    payload = b"some file bytes"
    put_resp = c.put(_route(ticket["upload_url"]), content=payload)
    assert put_resp.status_code == 200, put_resp.text
    assert put_resp.json()["ok"] is True

    # build a fresh signed GET url for the same object
    get_url = local.make_signed_url("deal-documents", ticket["key"])
    get_resp = c.get(_route(get_url))
    assert get_resp.status_code == 200, get_resp.text
    assert get_resp.content == payload


def test_put_with_bad_sig_403(make_client, seed):
    c = _client(make_client, seed.user_a)
    ticket = c.post(
        "/storage/upload-ticket",
        json={"bucket": "deal-documents", "deal_id": seed.deal_a, "filename": "memo.txt"},
    ).json()

    parsed = urlparse(_route(ticket["upload_url"]))
    bad_url = f"{parsed.path}?{parsed.query}TAMPER"
    resp = c.put(bad_url, content=b"x")
    assert resp.status_code == 403, resp.text


def test_get_with_bad_sig_403(make_client, seed):
    # write a real object first
    c = _client(make_client, seed.user_a)
    ticket = c.post(
        "/storage/upload-ticket",
        json={"bucket": "deal-documents", "deal_id": seed.deal_a, "filename": "memo.txt"},
    ).json()
    c.put(_route(ticket["upload_url"]), content=b"hi")

    good = local.make_signed_url("deal-documents", ticket["key"])
    resp = c.get(_route(good) + "TAMPER")
    assert resp.status_code == 403, resp.text


def test_put_rejects_oversize_upload(make_client, seed, monkeypatch):
    """Regression: the per-object size cap is enforced at the PUT ingress point
    (it used to live on the now-removed /meetings/upload-ticket endpoint, where
    the real upload path never hit it). A valid signature must not let a holder
    stream an unbounded body in."""
    monkeypatch.setattr(files, "MAX_UPLOAD_SIZE_BYTES", 8, raising=True)
    c = _client(make_client, seed.user_a)
    ticket = c.post(
        "/storage/upload-ticket",
        json={"bucket": "meeting-recordings", "deal_id": seed.deal_a, "filename": "big.mp4"},
    ).json()

    resp = c.put(_route(ticket["upload_url"]), content=b"way too many bytes")
    assert resp.status_code == 413, resp.text

    # An at-or-under-cap body still succeeds with the same (valid) signature.
    ok = c.put(_route(ticket["upload_url"]), content=b"smol")
    assert ok.status_code == 200, ok.text
