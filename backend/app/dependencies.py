from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.integrations.aws.cognito import CognitoClient, get_cognito_client
from app.integrations.supabase.auth import SupabaseAuthClient, get_supabase_auth_client
from app.models.user import User
from app.services.auth_service import AuthService


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_user(
    request: Request,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
    cognito: CognitoClient = Depends(get_cognito_client),
    supabase_auth: SupabaseAuthClient = Depends(get_supabase_auth_client),
) -> User:
    """Extract and verify the current user from the Authorization header.

    Routes to the appropriate auth provider:
    - Demo mode: locally-signed HS256 JWT
    - Supabase: when SUPABASE_URL is configured
    - Cognito: fallback (original behavior)
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.removeprefix("Bearer ")

    if settings.demo_mode:
        # Demo mode: verify token locally
        try:
            claims = jwt.decode(
                token, settings.demo_jwt_secret, algorithms=["HS256"]
            )
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        cognito_sub = claims.get("sub", "")
        result = await db.execute(
            select(User).where(User.cognito_sub == cognito_sub)
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

    elif settings.supabase_url:
        # Supabase Auth: verify Supabase JWT
        try:
            auth_service = AuthService(db=db, supabase_auth=supabase_auth)
            user = await auth_service.verify_and_get_user_supabase(token)
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    else:
        # Cognito: verify Cognito RS256 JWT
        try:
            auth_service = AuthService(db=db, cognito=cognito)
            user = await auth_service.verify_and_get_user(token)
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    # Set user_id on request state for audit logging middleware
    request.state.user_id = user.id

    return user


async def get_org_id(
    request: Request,
    x_org_id: str | None = Header(None),
) -> UUID:
    """Extract organization ID from request headers."""
    org_id = x_org_id or getattr(request.state, "org_id", None)
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Org-ID header is required",
        )
    try:
        return UUID(str(org_id))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid organization ID format",
        )


async def get_db_with_rls(
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_org_id),
    current_user: User = Depends(get_current_user),
) -> AsyncSession:
    """Provide a database session with Row-Level Security context set."""
    from app.core.security import verify_org_membership
    await verify_org_membership(db, current_user.id, org_id)
    if not settings.demo_mode:
        await db.execute(
            text("SET LOCAL app.current_org_id = :org_id"),
            {"org_id": str(org_id)},
        )
    return db
