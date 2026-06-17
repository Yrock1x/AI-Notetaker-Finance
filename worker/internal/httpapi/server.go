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
	"regexp"
	"time"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/config"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/db"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/llm"
	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/go-chi/cors"
)

// Server holds the shared dependencies handlers need.
type Server struct {
	Cfg *config.Config
	DB  *sql.DB
	LLM *llm.Client
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
	r.Use(s.cors())

	r.Route("/api/v1", func(r chi.Router) {
		r.Get("/health", s.health)
		r.Get("/health/ready", s.ready)

		r.Route("/auth", func(r chi.Router) {
			r.Post("/register", s.authRegister)
			r.Post("/login", s.authLogin)
			r.Post("/signout", s.authSignout)
			r.Get("/login/{provider}", s.oauthLogin)
			r.Get("/callback/{provider}", s.oauthCallback)
			r.With(s.requireAuth).Get("/session", s.authSession)
		})

		// Authed store CRUD. Each resource registers its own routes; more are
		// added here as later phases port them (meetings, documents, ...).
		r.Group(func(r chi.Router) {
			r.Use(s.requireAuth)
			s.RegisterDeals(r)
			s.RegisterMeetings(r)
			s.RegisterDocuments(r)
			s.RegisterTranscripts(r)
			s.RegisterBotSessions(r)
			s.RegisterOrgs(r)
			s.RegisterDashboard(r)
			s.RegisterUploadTicket(r)
			s.RegisterQA(r)
			s.RegisterAnalysis(r)
			s.RegisterCognivault(r)
			s.RegisterIntegrations(r)
		})

		// Signed object PUT/GET — NOT session-authed; a valid HMAC signature is
		// the capability, so these live outside the requireAuth group.
		s.RegisterStorageObjects(r)
		// Self-applying auth: internal (X-Internal-Token), deliverables (own
		// requireAuth group), realtime (SSE self-auths, webhook is public).
		s.RegisterInternal(r)
		s.RegisterDeliverables(r)
		s.RegisterRealtime(r)
	})

	// CogniVault partner API (M2M, partner-key auth) lives at /partner/v1, not
	// under /api/v1 — registered on the root router.
	s.RegisterPartner(r)
	return r
}

// cors mirrors the Python CORS config (app/main.py): the explicit origin list
// plus the preview regex, credentialed, with the verbs/headers the frontend uses.
func (s *Server) cors() func(http.Handler) http.Handler {
	allowed := map[string]bool{}
	for _, o := range s.Cfg.CORSOriginList() {
		allowed[o] = true
	}
	var re *regexp.Regexp
	if s.Cfg.CORSOriginRegex != "" {
		re = regexp.MustCompile(s.Cfg.CORSOriginRegex)
	}
	return cors.Handler(cors.Options{
		AllowOriginFunc: func(_ *http.Request, origin string) bool {
			return allowed[origin] || (re != nil && re.MatchString(origin))
		},
		AllowedMethods:   []string{"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"},
		AllowedHeaders:   []string{"Authorization", "Content-Type", "X-Internal-Token", "X-Requested-With"},
		AllowCredentials: true,
		MaxAge:           300,
	})
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
