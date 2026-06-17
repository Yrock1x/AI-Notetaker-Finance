// Package httpapi builds the worker's HTTP surface. The routes + JSON shapes must
// stay byte-for-byte compatible with the Python worker (app/api/v1/**) so the
// unchanged Next.js frontend and the CogniVault partner keep working.
package httpapi

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/config"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/db"
	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
)

// Server holds the shared dependencies handlers need.
type Server struct {
	Cfg *config.Config
	DB  *sql.DB
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

// Router wires the full HTTP surface. Phase 1 mounts health only; subsequent
// phases add auth, store CRUD, qa, analysis, deliverables, webhooks, internal,
// and the /partner/v1 surface under the same prefixes the Python worker uses.
func (s *Server) Router() http.Handler {
	r := chi.NewRouter()
	r.Use(middleware.RequestID)
	r.Use(middleware.RealIP)
	r.Use(middleware.Recoverer)

	r.Route("/api/v1", func(r chi.Router) {
		r.Get("/health", s.health)
		r.Get("/health/ready", s.ready)
	})
	return r
}

// GET /api/v1/health — liveness. Matches app/api/v1/health.py exactly.
func (s *Server) health(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{
		"status":  "healthy",
		"service": "cognisuite-worker",
	})
}

// GET /api/v1/health/ready — readiness: sqlite (+ vec) reachable and storage
// writable. 503 if any check fails. Matches the Python readiness JSON shape.
func (s *Server) ready(w http.ResponseWriter, _ *http.Request) {
	checks := map[string]string{}
	ok := true

	if err := db.Ping(s.DB); err != nil {
		checks["sqlite"] = "error"
		ok = false
	} else {
		checks["sqlite"] = "ok"
	}

	if err := storageWritable(s.Cfg.StorageRoot); err != nil {
		checks["storage"] = "error"
		ok = false
	} else {
		checks["storage"] = "ok"
	}

	status := "ready"
	code := http.StatusOK
	if !ok {
		status = "unhealthy"
		code = http.StatusServiceUnavailable
	}
	writeJSON(w, code, map[string]any{"status": status, "checks": checks})
}

func storageWritable(root string) error {
	if err := os.MkdirAll(root, 0o755); err != nil {
		return err
	}
	probe := filepath.Join(root, ".readiness-probe")
	if err := os.WriteFile(probe, []byte("ok"), 0o600); err != nil {
		return err
	}
	return os.Remove(probe)
}

// DefaultTimeouts returns http.Server timeouts. SSE streaming endpoints (added in
// a later phase) will be mounted on a handler whose WriteTimeout is disabled.
func DefaultTimeouts() (read, write, idle time.Duration) {
	return 15 * time.Second, 30 * time.Second, 60 * time.Second
}
