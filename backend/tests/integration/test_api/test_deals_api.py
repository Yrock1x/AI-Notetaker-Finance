"""Integration tests for the Deals API endpoints."""

import pytest


class TestHealthAPI:
    """Test the health check endpoints (these don't require auth or db)."""

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """GET /api/v1/health/ should return 200 with status healthy."""
        response = await client.get("/api/v1/health/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "dealwise-api"


class TestAuthAPI:
    """Test the auth endpoints."""

    @pytest.mark.asyncio
    async def test_get_me(self, client):
        """GET /api/v1/auth/me should return current user."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert "email" in data
        assert "full_name" in data
        assert data["email"] == "testuser@example.com"

    @pytest.mark.asyncio
    async def test_logout(self, client):
        """POST /api/v1/auth/logout should return message."""
        response = await client.post("/api/v1/auth/logout")
        assert response.status_code == 200
        assert "message" in response.json()
