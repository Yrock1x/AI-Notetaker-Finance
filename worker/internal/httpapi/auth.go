package httpapi

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/auth"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/store"
)

// ---- request/response shapes (match app/api/v1/auth_native.py) -------------

type registerRequest struct {
	Email    string  `json:"email"`
	Password string  `json:"password"`
	FullName *string `json:"full_name"`
}

type loginRequest struct {
	Email    string `json:"email"`
	Password string `json:"password"`
}

type sessionResponse struct {
	ID        string  `json:"id"`
	Email     string  `json:"email"`
	FullName  string  `json:"full_name"`
	AvatarURL *string `json:"avatar_url"`
}

// ---- auth context ----------------------------------------------------------

type ctxKey int

const (
	ctxAuthUser ctxKey = iota
	ctxPrincipal
)

// AuthUser mirrors app/dependencies.py AuthUser (id + email).
type AuthUser struct {
	ID    string
	Email string
}

func authUserFromCtx(ctx context.Context) *AuthUser {
	v, _ := ctx.Value(ctxAuthUser).(*AuthUser)
	return v
}

func principalFromCtx(ctx context.Context) *store.Principal {
	v, _ := ctx.Value(ctxPrincipal).(*store.Principal)
	return v
}

// ---- error helper (FastAPI-shaped {"detail": ...}) -------------------------

func writeError(w http.ResponseWriter, status int, detail string) {
	writeJSON(w, status, map[string]string{"detail": detail})
}

// ---- cookies ---------------------------------------------------------------

func (s *Server) cookieSameSite() http.SameSite {
	if s.Cfg.IsProduction() {
		return http.SameSiteNoneMode // cross-site (vercel <-> railway) needs None+Secure
	}
	return http.SameSiteLaxMode
}

func (s *Server) setSessionCookie(w http.ResponseWriter, token string) {
	http.SetCookie(w, &http.Cookie{
		Name:     s.Cfg.SessionCookieName,
		Value:    token,
		Path:     "/",
		MaxAge:   int(auth.DefaultTTL.Seconds()),
		HttpOnly: true,
		Secure:   s.Cfg.IsProduction(),
		SameSite: s.cookieSameSite(),
	})
}

func (s *Server) clearSessionCookie(w http.ResponseWriter) {
	http.SetCookie(w, &http.Cookie{
		Name:     s.Cfg.SessionCookieName,
		Value:    "",
		Path:     "/",
		MaxAge:   -1,
		HttpOnly: true,
		Secure:   s.Cfg.IsProduction(),
		SameSite: s.cookieSameSite(),
	})
}

// ---- middleware ------------------------------------------------------------

// requireAuth resolves the caller from a Bearer token or the session cookie
// (ports get_current_user), loads the Principal, and stashes both in context.
// 401 if the token is missing/invalid.
func (s *Server) requireAuth(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		secret, err := s.Cfg.SessionSigningSecret()
		if err != nil {
			writeError(w, http.StatusInternalServerError, "auth not configured")
			return
		}
		token := ""
		if h := r.Header.Get("Authorization"); strings.HasPrefix(h, "Bearer ") {
			token = strings.TrimSpace(strings.TrimPrefix(h, "Bearer "))
		} else if c, errc := r.Cookie(s.Cfg.SessionCookieName); errc == nil {
			token = c.Value
		}
		if token == "" {
			writeError(w, http.StatusUnauthorized, "Not authenticated")
			return
		}
		claims, err := auth.VerifySessionToken(secret, token)
		if err != nil {
			writeError(w, http.StatusUnauthorized, "Not authenticated")
			return
		}
		principal, err := store.LoadPrincipal(r.Context(), s.DB, claims.Subject)
		if err != nil {
			writeError(w, http.StatusInternalServerError, "failed to load principal")
			return
		}
		ctx := context.WithValue(r.Context(), ctxAuthUser, &AuthUser{ID: claims.Subject, Email: claims.Email})
		ctx = context.WithValue(ctx, ctxPrincipal, principal)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

// ---- handlers --------------------------------------------------------------

func (s *Server) issueSessionFor(w http.ResponseWriter, id, email string) bool {
	secret, err := s.Cfg.SessionSigningSecret()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "auth not configured")
		return false
	}
	token, err := auth.IssueSessionToken(secret, id, email, auth.DefaultTTL)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "failed to issue session")
		return false
	}
	s.setSessionCookie(w, token)
	return true
}

func normalizeEmail(raw string) (string, bool) {
	email := strings.TrimSpace(raw)
	local, domain, found := strings.Cut(email, "@")
	if !found || local == "" || domain == "" || len(email) > 320 {
		return "", false
	}
	return email, true
}

// POST /api/v1/auth/register
func (s *Server) authRegister(w http.ResponseWriter, r *http.Request) {
	var body registerRequest
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeError(w, http.StatusUnprocessableEntity, "Invalid request body")
		return
	}
	email, ok := normalizeEmail(body.Email)
	if !ok {
		writeError(w, http.StatusUnprocessableEntity, "Enter a valid email address.")
		return
	}
	if l := len(body.Password); l < auth.MinPasswordLength || l > auth.MaxPasswordLength {
		writeError(w, http.StatusUnprocessableEntity, "Password must be between 8 and 128 characters.")
		return
	}

	ctx := r.Context()
	existing, err := store.GetProfileByEmail(ctx, s.DB, email)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "registration failed")
		return
	}
	if existing != nil {
		writeError(w, http.StatusConflict, "An account with this email already exists. Try signing in instead.")
		return
	}

	hash, err := auth.HashPassword(body.Password)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "registration failed")
		return
	}

	tx, err := s.DB.BeginTx(ctx, nil)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "registration failed")
		return
	}
	defer tx.Rollback()
	profile, err := store.GetOrCreateUser(ctx, tx, email, body.FullName, nil)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "registration failed")
		return
	}
	if err := store.SetPasswordHash(ctx, tx, profile.ID, hash); err != nil {
		writeError(w, http.StatusInternalServerError, "registration failed")
		return
	}
	if err := tx.Commit(); err != nil {
		writeError(w, http.StatusConflict, "An account with this email already exists. Try signing in instead.")
		return
	}

	if !s.issueSessionFor(w, profile.ID, profile.Email) {
		return
	}
	writeJSON(w, http.StatusOK, sessionResponse{ID: profile.ID, Email: profile.Email, FullName: profile.FullName, AvatarURL: profile.AvatarURL})
}

// POST /api/v1/auth/login
func (s *Server) authLogin(w http.ResponseWriter, r *http.Request) {
	var body loginRequest
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeError(w, http.StatusUnprocessableEntity, "Invalid request body")
		return
	}
	email, ok := normalizeEmail(body.Email)
	if !ok {
		writeError(w, http.StatusUnprocessableEntity, "Enter a valid email address.")
		return
	}
	profile, err := store.GetProfileByEmail(r.Context(), s.DB, email)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "login failed")
		return
	}
	if profile == nil {
		writeError(w, http.StatusUnauthorized, "Invalid email or password.")
		return
	}
	if profile.PasswordHash == nil {
		writeError(w, http.StatusForbidden, "This account uses Google or Microsoft sign-in. Please use those buttons.")
		return
	}
	if !auth.VerifyPassword(body.Password, *profile.PasswordHash) {
		writeError(w, http.StatusUnauthorized, "Invalid email or password.")
		return
	}
	if !profile.IsActive {
		writeError(w, http.StatusForbidden, "This account has been disabled.")
		return
	}
	if !s.issueSessionFor(w, profile.ID, profile.Email) {
		return
	}
	writeJSON(w, http.StatusOK, sessionResponse{ID: profile.ID, Email: profile.Email, FullName: profile.FullName, AvatarURL: profile.AvatarURL})
}

// GET /api/v1/auth/session
func (s *Server) authSession(w http.ResponseWriter, r *http.Request) {
	u := authUserFromCtx(r.Context())
	profile, err := store.GetProfileByID(r.Context(), s.DB, u.ID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "session lookup failed")
		return
	}
	if profile == nil {
		writeError(w, http.StatusNotFound, "Profile not found")
		return
	}
	writeJSON(w, http.StatusOK, sessionResponse{ID: profile.ID, Email: profile.Email, FullName: profile.FullName, AvatarURL: profile.AvatarURL})
}

// POST /api/v1/auth/signout
func (s *Server) authSignout(w http.ResponseWriter, _ *http.Request) {
	s.clearSessionCookie(w)
	writeJSON(w, http.StatusOK, map[string]bool{"ok": true})
}

// OAuth login/callback (Google/Microsoft) live in oauth.go.
