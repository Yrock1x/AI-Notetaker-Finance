import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.dependencies import get_current_user, get_db
from app.models.org_membership import OrgMembership
from app.models.organization import Organization
from app.models.user import User
from app.schemas.user import UserResponse

router = APIRouter()


class DemoLoginRequest(BaseModel):
    email: str


class DemoRegisterRequest(BaseModel):
    email: str
    full_name: str
    org_name: str | None = None


class DemoLoginUserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    avatar_url: str | None = None
    org_id: str
    role: str
    is_active: bool
    created_at: str
    updated_at: str


class DemoLoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str
    user: DemoLoginUserResponse


@router.post("/demo-login", response_model=DemoLoginResponse)
async def demo_login(
    body: DemoLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> DemoLoginResponse:
    """Demo login endpoint — bypasses Cognito for demo/dev deployments.

    Only available when DEMO_MODE=true.
    """
    if not settings.demo_mode:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    # Look up user by email
    result = await db.execute(
        select(User).where(User.email == body.email)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No user found with that email. Try one of the seed users.",
        )

    # Look up user's first org membership
    mem_result = await db.execute(
        select(OrgMembership).where(OrgMembership.user_id == user.id)
    )
    membership = mem_result.scalars().first()
    org_id = str(membership.org_id) if membership else ""
    org_role = membership.role if membership else "member"

    # Issue a demo JWT
    now = datetime.now(timezone.utc)
    claims = {
        "sub": user.cognito_sub,
        "email": user.email,
        "name": user.full_name,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=24)).timestamp()),
    }
    access_token = jwt.encode(claims, settings.demo_jwt_secret, algorithm="HS256")

    return DemoLoginResponse(
        access_token=access_token,
        refresh_token="demo-refresh",
        expires_in=86400,
        token_type="Bearer",
        user=DemoLoginUserResponse(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            avatar_url=user.avatar_url,
            org_id=org_id,
            role=org_role,
            is_active=user.is_active,
            created_at=user.created_at.isoformat() if user.created_at else now.isoformat(),
            updated_at=user.updated_at.isoformat() if user.updated_at else now.isoformat(),
        ),
    )


@router.post("/demo-register", response_model=DemoLoginResponse)
async def demo_register(
    body: DemoRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> DemoLoginResponse:
    """Register a new user in demo mode.

    Creates a User, optionally creates an Organization, and returns a JWT.
    Only available when DEMO_MODE=true.
    """
    if not settings.demo_mode:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    # Check if email already exists
    existing = await db.execute(
        select(User).where(User.email == body.email)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists. Try logging in.",
        )

    now = datetime.now(timezone.utc)
    cognito_sub = f"demo-{uuid.uuid4().hex[:16]}"

    # Create the user
    user = User(
        id=uuid.uuid4(),
        cognito_sub=cognito_sub,
        email=body.email,
        full_name=body.full_name,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    # Create or join an organization
    org_name = body.org_name or f"{body.full_name.split()[0]}'s Organization"
    slug = re.sub(r"[^a-z0-9]+", "-", org_name.lower()).strip("-")

    # Check for slug collision and make unique
    slug_check = await db.execute(
        select(Organization).where(Organization.slug == slug)
    )
    if slug_check.scalar_one_or_none() is not None:
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    org = Organization(
        id=uuid.uuid4(),
        name=org_name,
        slug=slug,
        settings={},
    )
    db.add(org)
    await db.flush()

    # Add user as org owner
    membership = OrgMembership(
        id=uuid.uuid4(),
        org_id=org.id,
        user_id=user.id,
        role="owner",
    )
    db.add(membership)
    await db.flush()

    # Issue a demo JWT
    claims = {
        "sub": cognito_sub,
        "email": user.email,
        "name": user.full_name,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=24)).timestamp()),
    }
    access_token = jwt.encode(claims, settings.demo_jwt_secret, algorithm="HS256")

    return DemoLoginResponse(
        access_token=access_token,
        refresh_token="demo-refresh",
        expires_in=86400,
        token_type="Bearer",
        user=DemoLoginUserResponse(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            avatar_url=None,
            org_id=str(org.id),
            role="owner",
            is_active=True,
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
        ),
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Get the current authenticated user's profile."""
    return UserResponse.model_validate(current_user)


@router.post("/logout")
async def logout() -> dict:
    """Invalidate the current session.

    Note: JWT tokens are stateless — the client should discard the token.
    For full invalidation, Cognito's GlobalSignOut API can be used.
    """
    return {"message": "Logged out. Please discard your access token."}
