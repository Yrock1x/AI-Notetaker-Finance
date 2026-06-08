"""Store routers — REST endpoints over the worker-owned SQLite DB.

These replace the frontend's former direct-to-Supabase reads/writes. Every
endpoint depends on ``get_db`` (a transactional session) and ``get_principal``
(the caller's org memberships) and scopes queries via app/db/scope.py — there is
no RLS underneath, so scoping here is the only tenant boundary.
"""
