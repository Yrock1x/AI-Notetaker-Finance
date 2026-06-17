// Package util holds small cross-cutting helpers (ids, timestamps) that mirror
// the Python worker's app/db/base.py so IDs and timestamps are format-compatible
// with rows the Python worker wrote.
package util

import (
	"crypto/rand"
	"fmt"
	"time"
)

// NewUUID returns a random UUID v4 as a lowercase hyphenated string — matches
// Python's str(uuid.uuid4()).
func NewUUID() string {
	var b [16]byte
	_, _ = rand.Read(b[:])
	b[6] = (b[6] & 0x0f) | 0x40 // version 4
	b[8] = (b[8] & 0x3f) | 0x80 // variant 10
	return fmt.Sprintf("%x-%x-%x-%x-%x", b[0:4], b[4:6], b[6:8], b[8:10], b[10:16])
}

// NowISO returns the current UTC time as ISO-8601 with microseconds and a
// +00:00 offset, matching Python's datetime.now(UTC).isoformat() — e.g.
// "2026-06-17T03:49:45.939197+00:00". Lexicographically ordered, which the
// composite (created_at,id) cursors rely on.
func NowISO() string {
	return time.Now().UTC().Format("2006-01-02T15:04:05.000000-07:00")
}
