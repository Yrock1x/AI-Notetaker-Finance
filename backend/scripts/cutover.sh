#!/usr/bin/env sh
# One-time data cutover: Supabase → SQLite.
#
# Run this ONCE, on a machine that has BOTH the SQLite volume mounted AND the
# Supabase secrets present (SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY), after
# freezing writes on the old app. On Fly:
#
#     fly ssh console -C "/app/scripts/cutover.sh"
#
# It is re-runnable: schema migration is idempotent and row inserts skip
# existing primary keys. Pass extra args through to the migrator, e.g.:
#
#     /app/scripts/cutover.sh --skip-storage
#     /app/scripts/cutover.sh --tables deals,meetings
set -eu

echo "[cutover] 1/3 alembic upgrade head"
alembic upgrade head

echo "[cutover] 2/3 migrating data from Supabase (tables + embeddings + storage)"
python -m app.db.migrate_from_supabase "$@"

echo "[cutover] 3/3 done. Review the per-table row counts logged above and"
echo "          spot-check: /api/v1/auth/login/google and a partner search."
