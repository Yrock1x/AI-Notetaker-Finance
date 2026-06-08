"""First-login user provisioning.

Replicates the old Postgres triggers (handle_new_auth_user + 0003 auto-org):
on first login create the profile, a personal organization, and an owner
membership. Idempotent on email.
"""

from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Organization, OrgMembership, Profile


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "org"


def _unique_slug(session: Session, base: str) -> str:
    slug = _slugify(base)
    candidate = slug
    n = 1
    while session.scalar(select(Organization.id).where(Organization.slug == candidate)):
        n += 1
        candidate = f"{slug}-{n}"
    return candidate


def get_or_create_user(
    session: Session,
    *,
    email: str,
    full_name: str | None = None,
    avatar_url: str | None = None,
) -> Profile:
    """Return the existing profile for ``email`` or create one (+ personal org)."""
    existing = session.scalar(
        select(Profile).where(func.lower(Profile.email) == email.lower())
    )
    if existing:
        return existing

    name = full_name or email.split("@", 1)[0]
    profile = Profile(email=email, full_name=name, avatar_url=avatar_url)
    session.add(profile)
    session.flush()

    org = Organization(
        name=f"{name}'s Organization",
        slug=_unique_slug(session, email.split("@", 1)[0]),
    )
    session.add(org)
    session.flush()

    session.add(OrgMembership(org_id=org.id, user_id=profile.id, role="owner"))
    session.flush()
    return profile
