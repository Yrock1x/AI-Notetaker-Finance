// Package db opens the worker-owned SQLite database with the sqlite-vec
// extension loaded, mirroring app/db/engine.py (WAL, busy_timeout, foreign_keys)
// and the vec0 virtual table from app/db/vectors.py.
package db

import (
	"database/sql"
	"fmt"

	sqlite_vec "github.com/asg017/sqlite-vec-go-bindings/cgo"
	_ "github.com/mattn/go-sqlite3"
)

// EmbeddingDim must match the stored vectors (Fireworks nomic-embed-text-v1.5).
const EmbeddingDim = 768

// CreateVecTableSQL is the EXACT vec0 DDL from the Python worker
// (app/db/vectors.py) — cosine KNN, partitioned per deal for efficient scoping.
const CreateVecTableSQL = `CREATE VIRTUAL TABLE IF NOT EXISTS vec_embeddings USING vec0(
	embedding_id TEXT PRIMARY KEY,
	deal_id TEXT PARTITION KEY,
	embedding FLOAT[768] distance_metric=cosine
)`

// Open opens the SQLite database at path with sqlite-vec registered, applies the
// connection pragmas, verifies the extension, and ensures the vec0 table exists.
//
// SQLite has a single writer; with WAL, many readers + one writer coexist. We do
// not cap MaxOpenConns to 1 (that would serialize reads); the busy_timeout pragma
// handles writer contention.
func Open(path string) (*sql.DB, error) {
	// Register vec0 to auto-load on every new connection (process-global).
	sqlite_vec.Auto()

	// _busy_timeout + _journal_mode + _foreign_keys are honoured by mattn's DSN.
	dsn := fmt.Sprintf("file:%s?_busy_timeout=5000&_journal_mode=WAL&_foreign_keys=on&_synchronous=NORMAL", path)
	conn, err := sql.Open("sqlite3", dsn)
	if err != nil {
		return nil, fmt.Errorf("open sqlite: %w", err)
	}

	var vecVersion string
	if err := conn.QueryRow("select vec_version()").Scan(&vecVersion); err != nil {
		conn.Close()
		return nil, fmt.Errorf("sqlite-vec not loaded: %w", err)
	}

	if _, err := conn.Exec(CreateVecTableSQL); err != nil {
		conn.Close()
		return nil, fmt.Errorf("ensure vec_embeddings: %w", err)
	}

	return conn, nil
}

// Ping verifies the DB and the vec extension are responsive (used by readiness).
func Ping(conn *sql.DB) error {
	var one int
	if err := conn.QueryRow("select 1").Scan(&one); err != nil {
		return err
	}
	var v string
	return conn.QueryRow("select vec_version()").Scan(&v)
}
