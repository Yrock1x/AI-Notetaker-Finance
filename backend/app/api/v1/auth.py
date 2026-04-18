"""Minimal auth router. Sign-in happens in the browser via Supabase Auth
(Google / Microsoft OAuth). The worker only exposes identity introspection
and a convenience logout that clears any worker-set cookies (there aren't
any today — Supabase owns the session cookie — but we keep the endpoint for
future use)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import AuthUser, get_current_user

router = APIRouter()


@router.get("/me")
async def me(current_user: AuthUser = Depends(get_current_user)) -> dict:
    """Return the decoded Supabase JWT claims for the current caller.

    Frontends usually call ``supabase.auth.getUser()`` directly and don't
    need this endpoint — it exists to let server-side integrations verify
    a bearer token against the worker's JWKS cache.
    """
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "claims": current_user.raw_claims,
    }


@router.post("/logout")
async def logout() -> dict:
    """No-op on the worker — call ``supabase.auth.signOut()`` in the client.

    Returned for symmetry so frontends can hit a single ``/auth/logout``
    that closes both the Supabase session (client-side) and any worker
    session we might add later.
    """
    return {"message": "Signed out via Supabase."}
