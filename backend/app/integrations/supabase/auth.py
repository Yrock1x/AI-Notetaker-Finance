from __future__ import annotations

import time
from functools import lru_cache

import httpx
from jose import JWTError, jwt

from app.core.config import settings


class SupabaseAuthClient:
    """Client for Supabase Auth JWT verification."""

    def __init__(
        self,
        supabase_url: str | None = None,
        supabase_jwt_secret: str | None = None,
    ) -> None:
        self.supabase_url = (supabase_url or settings.supabase_url).rstrip("/")
        self.jwt_secret = supabase_jwt_secret or settings.supabase_jwt_secret
        self._jwks_cache: dict | None = None
        self._jwks_cache_time: float = 0
        self._jwks_cache_ttl: float = 3600  # 1 hour

    def get_jwks_url(self) -> str:
        """Return the JWKS URL for the Supabase project."""
        return f"{self.supabase_url}/auth/v1/.well-known/jwks.json"

    @property
    def _issuer(self) -> str:
        return f"{self.supabase_url}/auth/v1"

    async def _get_jwks(self) -> dict:
        """Fetch and cache the JWKS from Supabase."""
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
        """Verify and decode a Supabase Auth JWT token.

        If a JWT secret is configured, uses HS256 verification (faster, no network).
        Otherwise, fetches JWKS and uses RS256 verification.

        Returns the decoded claims dict.
        """
        if self.jwt_secret:
            # Offline verification using the Supabase JWT secret (HS256)
            claims = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
        else:
            # Online verification using JWKS (RS256)
            signing_key = await self._get_signing_key(token)
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                issuer=self._issuer,
                options={"verify_aud": False},
            )

        return claims

    def extract_user_info(self, claims: dict) -> dict:
        """Extract normalized user info from Supabase JWT claims."""
        user_metadata = claims.get("user_metadata", {})
        return {
            "sub": claims.get("sub", ""),
            "email": claims.get("email", ""),
            "name": (
                user_metadata.get("full_name")
                or user_metadata.get("name")
                or claims.get("email", "").split("@")[0]
            ),
        }


@lru_cache
def get_supabase_auth_client() -> SupabaseAuthClient:
    return SupabaseAuthClient()
