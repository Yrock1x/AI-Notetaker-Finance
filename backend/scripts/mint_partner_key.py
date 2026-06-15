"""Mint a partner API key for an org — the M2M credential CogniVault uses to PULL
shared deal data from ``/partner/v1``.

There is no UI for this (keys are rare, ops-issued). Run from ``backend/`` with the
worker's env (so SQLITE_DB_PATH points at the right database):

    python -m scripts.mint_partner_key --org <org_id> --name "CogniVault Production"
    # optional: --scopes deals:read,documents:read,transcripts:read,search

Only the sha256 hash is persisted; the RAW key is printed ONCE — hand it to
CogniVault, which sends it as ``Authorization: Bearer <raw_key>``.
"""

from __future__ import annotations

import argparse
import hashlib
import secrets

from app.db.engine import get_session_factory
from app.db.models import Organization, PartnerApiKey

# What a CogniVault key needs to ingest a shared deal: read deals/documents/
# transcripts(+analyses) and run vector search. No write scopes by default.
DEFAULT_SCOPES = ["deals:read", "documents:read", "transcripts:read", "search"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Mint a CogniVault partner API key")
    parser.add_argument("--org", required=True, help="organizations.id to scope the key to")
    parser.add_argument("--name", default="CogniVault", help="friendly key name")
    parser.add_argument(
        "--scopes",
        default=",".join(DEFAULT_SCOPES),
        help="comma-separated partner scopes",
    )
    args = parser.parse_args()

    scopes = [s.strip() for s in args.scopes.split(",") if s.strip()]
    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    session = get_session_factory()()
    try:
        if session.get(Organization, args.org) is None:
            raise SystemExit(f"No organization with id={args.org}")
        key = PartnerApiKey(
            org_id=args.org,
            name=args.name,
            key_hash=key_hash,
            scopes=scopes,
            is_active=True,
        )
        session.add(key)
        session.commit()
        print("Partner API key minted.")
        print(f"  org_id : {args.org}")
        print(f"  key_id : {key.id}")
        print(f"  scopes : {scopes}")
        print()
        print("RAW KEY (shown once — give to CogniVault as a Bearer token):")
        print(f"  {raw_key}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
