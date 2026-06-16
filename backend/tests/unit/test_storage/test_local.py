"""Unit tests for the local filesystem object store + URL signing."""

from __future__ import annotations

import time

import pytest

from app.storage import local


@pytest.fixture(autouse=True)
def _storage_env(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "storage_root", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "storage_signing_key", "testkey", raising=False)
    yield


def test_save_read_delete_exists_roundtrip():
    bucket, key, data = "deal-documents", "deal1/file.txt", b"hello world"

    assert local.exists(bucket, key) is False
    local.save_bytes(bucket, key, data)
    assert local.exists(bucket, key) is True
    assert local.read_bytes(bucket, key) == data

    local.delete(bucket, key)
    assert local.exists(bucket, key) is False
    # deleting a missing object is a no-op
    local.delete(bucket, key)


def test_safe_path_rejects_traversal():
    with pytest.raises(ValueError):
        local._safe_path("deal-documents", "../etc/passwd")
    with pytest.raises(ValueError):
        local._safe_path("deal-documents", "/abs/path")


def test_safe_path_rejects_bad_bucket():
    with pytest.raises(ValueError):
        local._safe_path("not-a-bucket", "ok/key.txt")


def test_sign_then_verify_valid():
    exp = int(time.time()) + 60
    sig = local.sign("GET", "deliverables", "d1/x.pdf", exp)
    assert local.verify("GET", "deliverables", "d1/x.pdf", exp, sig) is True


def test_tampered_sig_fails():
    exp = int(time.time()) + 60
    sig = local.sign("GET", "deliverables", "d1/x.pdf", exp)
    assert local.verify("GET", "deliverables", "d1/x.pdf", exp, sig + "00") is False
    # wrong key path
    assert local.verify("GET", "deliverables", "d1/other.pdf", exp, sig) is False


def test_method_binding_prevents_get_sig_replayed_as_put():
    # A signature minted for GET (download) must not validate a PUT (overwrite).
    exp = int(time.time()) + 60
    get_sig = local.sign("GET", "deliverables", "d1/x.pdf", exp)
    assert local.verify("PUT", "deliverables", "d1/x.pdf", exp, get_sig) is False


def test_expired_url_fails():
    exp = int(time.time()) - 1
    sig = local.sign("GET", "deliverables", "d1/x.pdf", exp)
    assert local.verify("GET", "deliverables", "d1/x.pdf", exp, sig) is False


def test_make_signed_url_format():
    url = local.make_signed_url("deal-documents", "deal1/abc.txt", ttl_seconds=120)
    assert url.startswith("/api/v1/storage/deal-documents/deal1/abc.txt?")
    assert "expires=" in url
    assert "sig=" in url
