# worker (Go)

Go rewrite of the CogniSuite FastAPI worker (`../backend`). Single binary on the
worker-owned **SQLite + sqlite-vec** data layer, serving the **same HTTP
contract** so the unchanged Next.js frontend (Vercel) and the CogniVault partner
keep working. See the migration plan for scope, phasing, and the parity-gated
cutover.

## Status
Phase 1 — scaffold: config (+ H1 prod-secret fail-fast), SQLite+vec data layer,
chi router, `/api/v1/health` + `/api/v1/health/ready`. Subsequent phases add the
data layer/scope guards, auth, store CRUD, qa/analysis/deliverables, webhooks +
SSE, OAuth, and the `/partner/v1` surface (incl. server-side text search).

## Build & run (CGO — sqlite-vec is a C extension)
```bash
# uses the local Go toolchain
export PATH="$HOME/go-sdk/go/bin:$PATH" CGO_ENABLED=1
cd worker
go build ./...
SQLITE_DB_PATH=./dev.db STORAGE_ROOT=./dev-storage PORT=8081 go run ./cmd/worker
curl localhost:8081/api/v1/health
curl localhost:8081/api/v1/health/ready
```

## Layout
- `cmd/worker` — entrypoint (config → db → router → http server, graceful shutdown)
- `internal/config` — env loading + production validation (ports `app/core/config.py`)
- `internal/db` — SQLite open with sqlite-vec + the `vec0` table (ports `app/db/engine.py`, `vectors.py`)
- `internal/httpapi` — chi router + handlers (ports `app/api/v1/**`)
