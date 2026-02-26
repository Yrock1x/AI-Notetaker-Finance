from uuid import UUID

from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.integrations.aws.cognito import CognitoClient
from app.models.user import User

import structlog

logger = structlog.get_logger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession, cognito: CognitoClient) -> None:
        self.db = db
        self.cognito = cognito

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

        # Create new user
        user = User(
            cognito_sub=cognito_sub,
            email=email,
            full_name=name or email.split("@")[0],
            is_active=True,
        )
        self.db.add(user)
        await self.db.flush()

        logger.info("user_created", user_id=str(user.id), email=email)
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
