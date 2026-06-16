#!/usr/bin/env sh
# Container entrypoint for the SQLite-backed worker.
#
# 1. Ensure the data dirs exist on the mounted volume.
# 2. If a Litestream replica is configured and the DB is missing (fresh
#    machine / lost volume), restore it from the backup.
# 3. Apply schema migrations (idempotent — no-ops when already at head).
# 4. Launch a SINGLE uvicorn worker. Single process is REQUIRED: the realtime
#    pub/sub is in-process (SSE subscribers must share the process that the
#    webhook writes happen in) and SQLite has one writer. Horizontal scale
#    needs distributed SQLite (Turso/LiteFS), not more workers.
#    When a Litestream replica is configured, run uvicorn UNDER litestream so
#    the DB is continuously backed up.
set -eu

DB="${SQLITE_DB_PATH:-/data/app.db}"
mkdir -p "$(dirname "$DB")" "${STORAGE_ROOT:-/data/storage}"

LS_CONFIG="/app/litestream.yml"

if [ -n "${LITESTREAM_REPLICA_URL:-}" ] && [ ! -f "$DB" ]; then
  echo "[start] DB missing — attempting Litestream restore"
  # -if-replica-exists makes a genuine first boot (no replica/generation in the
  # bucket) a no-op exit 0. ANY other non-zero exit is a real failure (S3
  # unreachable, bad credentials, corrupt/partial snapshot) — we MUST abort
  # rather than fall through to `alembic upgrade head` on an empty DB, because
  # `litestream replicate` below would then stream that empty DB over the only
  # good backup (silent total data loss during disaster recovery).
  if ! litestream restore -if-replica-exists -config "$LS_CONFIG" "$DB"; then
    echo "[start] FATAL: litestream restore failed while a replica is configured." >&2
    echo "[start] Refusing to boot on an empty DB (would clobber the good backup). Check LITESTREAM_* creds / S3 reachability." >&2
    exit 1
  fi
  if [ -f "$DB" ]; then
    echo "[start] restored DB from Litestream replica"
  else
    echo "[start] no replica found in bucket (genuine first boot) — continuing with a fresh DB"
  fi
fi

echo "[start] alembic upgrade head"
alembic upgrade head

RUN_CMD="uvicorn app.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8000} --workers 1"

if [ -n "${LITESTREAM_REPLICA_URL:-}" ]; then
  echo "[start] launching under Litestream (continuous backup ON)"
  exec litestream replicate -config "$LS_CONFIG" -exec "$RUN_CMD"
else
  echo "[start] launching uvicorn (NO Litestream replica configured — backups OFF)"
  exec $RUN_CMD
fi
