from __future__ import annotations


class ZoomOAuth:
    """Handles Zoom OAuth 2.0 authentication flow."""

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str) -> None:
        """Initialize the Zoom OAuth client with app credentials."""
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def get_authorization_url(self, state: str) -> str:
        """Generate the Zoom OAuth authorization URL for user consent."""
        raise NotImplementedError

    async def exchange_code(self, code: str) -> dict:
        """Exchange an authorization code for access and refresh tokens."""
        raise NotImplementedError

    async def refresh_token(self, refresh_token: str) -> dict:
        """Refresh an expired access token using a refresh token."""
        raise NotImplementedError
