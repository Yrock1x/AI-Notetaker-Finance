"""Worker-owned SQLite data layer (migration target, replaces Supabase/Postgres).

Modules:
- ``base``    — declarative base + shared column helpers
- ``engine``  — SQLite engine/session, WAL + sqlite-vec loading, FastAPI dep
- ``models``  — SQLAlchemy models for every table (the former Postgres schema)
- ``vectors`` — vec0 virtual table + ``match_embeddings_for_deal`` equivalent
- ``scope``   — app-layer RLS: org/membership scoping (replaces Postgres RLS)
"""
