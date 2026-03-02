from uuid import UUID

from jose import JWTError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.integrations.aws.cognito import CognitoClient
from app.integrations.supabase.auth import SupabaseAuthClient
from app.models.user import User

import structlog

logger = structlog.get_logger(__name__)


class AuthService:
    def __init__(
        self,
        db: AsyncSession,
        cognito: CognitoClient | None = None,
        supabase_auth: SupabaseAuthClient | None = None,
    ) -> None:
        self.db = db
        self.cognito = cognito
        self.supabase_auth = supabase_auth

    async def verify_and_get_user(self, token: str) -> User:
        """Verify a Cognito JWT token and return the corresponding local user.

        Creates the user locally if they don't exist yet (first login).
        """
        claims = await self.cognito.verify_token(token)

        cognito_sub = claims.get("sub")
        email = claims.get("email", "")
        name = claims.get("name", claims.get("cognito:username", ""))

        if not cognito_sub:
            raise JWTError("Token missing 'sub' claim")

        user = await self.get_or_create_user(cognito_sub, email, name)
        return user

    async def verify_and_get_user_supabase(self, token: str) -> User:
        """Verify a Supabase JWT token and return the corresponding local user.

        Creates the user locally if they don't exist yet (first login).
        """
        claims = await self.supabase_auth.verify_token(token)
        user_info = self.supabase_auth.extract_user_info(claims)

        sub = user_info["sub"]
        email = user_info["email"]
        name = user_info["name"]

        if not sub:
            raise JWTError("Token missing 'sub' claim")

        user = await self.get_or_create_user(sub, email, name)
        return user

    async def get_or_create_user(self, cognito_sub: str, email: str, name: str) -> User:
        """Get existing user by cognito_sub, or create a new one."""
        stmt = select(User).where(User.cognito_sub == cognito_sub)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is not None:
            # Update email/name if changed in Cognito
            changed = False
            if email and user.email != email:
                user.email = email
                changed = True
            if name and user.full_name != name:
                user.full_name = name
                changed = True
            if changed:
                await self.db.flush()
            return user

        # Create new user — inactive until org assignment
        user = User(
            cognito_sub=cognito_sub,
            email=email,
            full_name=name or email.split("@")[0],
            is_active=False,  # Pending org assignment
        )
        try:
            self.db.add(user)
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            # Concurrent insert race — retry the lookup
            result = await self.db.execute(
                select(User).where(User.cognito_sub == cognito_sub)
            )
            user = result.scalar_one_or_none()
            if user is None:
                raise  # Re-raise if still not found
            return user

        logger.info("user_created", user_id=str(user.id), email=email, is_active=False)
        return user

    async def get_user_by_id(self, user_id: UUID) -> User:
        """Get a user by their internal ID."""
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            raise NotFoundError("User", str(user_id))
        return user

    async def get_user_by_email(self, email: str) -> User | None:
        """Get a user by email address."""
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def deactivate_user(self, user_id: UUID) -> User:
        """Deactivate a user account."""
        user = await self.get_user_by_id(user_id)
        user.is_active = False
        await self.db.flush()
        logger.info("user_deactivated", user_id=str(user_id))
        return user
