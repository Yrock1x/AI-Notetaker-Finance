from __future__ import annotations

import time
from functools import lru_cache

import httpx
from jose import JWTError, jwt

from app.core.config import settings


class CognitoClient:
    """Client for AWS Cognito user pool operations."""

    def __init__(
        self,
        user_pool_id: str | None = None,
        app_client_id: str | None = None,
        region: str | None = None,
    ) -> None:
        self.user_pool_id = user_pool_id or settings.cognito_user_pool_id
        self.app_client_id = app_client_id or settings.cognito_app_client_id
        self.region = region or settings.aws_region
        self._jwks_cache: dict | None = None
        self._jwks_cache_time: float = 0
        self._jwks_cache_ttl: float = 3600  # 1 hour

    def get_jwks_url(self) -> str:
        """Return the JSON Web Key Set URL for the configured user pool."""
        return (
            f"https://cognito-idp.{self.region}.amazonaws.com/"
            f"{self.user_pool_id}/.well-known/jwks.json"
        )

    @property
    def _issuer(self) -> str:
        return f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}"

    async def _get_jwks(self) -> dict:
        """Fetch and cache the JWKS from Cognito."""
        now = time.time()
        if self._jwks_cache and (now - self._jwks_cache_time) < self._jwks_cache_ttl:
            return self._jwks_cache

        async with httpx.AsyncClient() as client:
            response = await client.get(self.get_jwks_url())
            response.raise_for_status()
            self._jwks_cache = response.json()
            self._jwks_cache_time = now
            return self._jwks_cache

    async def _get_signing_key(self, token: str) -> dict:
        """Find the correct signing key from JWKS based on the token's kid header."""
        headers = jwt.get_unverified_headers(token)
        kid = headers.get("kid")
        if not kid:
            raise JWTError("Token missing 'kid' header")

        jwks = await self._get_jwks()
        for key in jwks.get("keys", []):
            if key["kid"] == kid:
                return key

        raise JWTError(f"Public key not found for kid: {kid}")

    async def verify_token(self, token: str) -> dict:
        """Verify and decode a Cognito JWT token.

        Validates the token signature, expiration, issuer, and audience.
        Returns the decoded claims dict.
        """
        signing_key = await self._get_signing_key(token)

        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=self.app_client_id,
            issuer=self._issuer,
            options={"verify_at_hash": False},
        )

        token_use = claims.get("token_use")
        if token_use not in ("id", "access"):
            raise JWTError(f"Invalid token_use: {token_use}")

        return claims

    async def get_user(self, access_token: str) -> dict:
        """Retrieve user attributes from Cognito using an access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://cognito-idp.{self.region}.amazonaws.com/",
                headers={
                    "Content-Type": "application/x-amz-json-1.1",
                    "X-Amz-Target": "AWSCognitoIdentityProviderService.GetUser",
                },
                json={"AccessToken": access_token},
            )
            response.raise_for_status()
            data = response.json()

            attrs = {}
            for attr in data.get("UserAttributes", []):
                attrs[attr["Name"]] = attr["Value"]

            return {
                "username": data.get("Username"),
                "email": attrs.get("email"),
                "name": attrs.get("name", attrs.get("given_name", "")),
                "sub": attrs.get("sub"),
                "email_verified": attrs.get("email_verified") == "true",
            }


@lru_cache
def get_cognito_client() -> CognitoClient:
    return CognitoClient()
