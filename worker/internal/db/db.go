// Package db opens the worker-owned SQLite database with the sqlite-vec
// extension loaded (mirroring app/db/engine.py) and owns the schema migration
// (the exact DDL the Python worker produced — see schema.sql).
package db

import (
	"database/sql"
	_ "embed"
	"fmt"

	sqlite_vec "github.com/asg017/sqlite-vec-go-bindings/cgo"
	_ "github.com/mattn/go-sqlite3"
)

// EmbeddingDim must match the stored vectors (Fireworks nomic-embed-text-v1.5).
const EmbeddingDim = 768

//go:embed schema.sql
var schemaSQL string

// Open opens the SQLite database at path with sqlite-vec registered and the
// connection pragmas applied (WAL + many readers / one writer; busy_timeout
// handles writer contention; foreign_keys on).
func Open(path string) (*sql.DB, error) {
	sqlite_vec.Auto() // auto-load vec0 on every new connection (process-global)

	// _txlock=immediate: explicit transactions (BeginTx) take SQLite's write lock
	// at BEGIN rather than lazily on first write. This stops two concurrent
	// read-modify-write transactions (e.g. the live transcript upsert) from both
	// starting deferred, both reading, then deadlocking when each tries to upgrade
	// to the write lock — instead the second blocks at BEGIN and waits out
	// busy_timeout. Autocommit reads are unaffected (they never BEGIN).
	dsn := fmt.Sprintf("file:%s?_busy_timeout=5000&_journal_mode=WAL&_foreign_keys=on&_synchronous=NORMAL&_txlock=immediate", path)
	conn, err := sql.Open("sqlite3", dsn)
	if err != nil {
		return nil, fmt.Errorf("open sqlite: %w", err)
	}
	var vecVersion string
	if err := conn.QueryRow("select vec_version()").Scan(&vecVersion); err != nil {
		conn.Close()
		return nil, fmt.Errorf("sqlite-vec not loaded: %w", err)
	}
	return conn, nil
}

// Migrate applies the embedded schema (idempotent — IF NOT EXISTS). It is a
// no-op against the existing prod DB and builds a fresh dev/staging DB from zero.
// The vec0 virtual table is created here too (the extension is already loaded by
// Open).
func Migrate(conn *sql.DB) error {
	if _, err := conn.Exec(schemaSQL); err != nil {
		return fmt.Errorf("apply schema: %w", err)
	}
	return nil
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
