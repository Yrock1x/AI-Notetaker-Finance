package httpapi

import (
	"database/sql"
	"encoding/json"
	"net/http"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/store"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/util"
	"github.com/go-chi/chi/v5"
)

// shareableScopes mirrors app/integrations/cognivault SHAREABLE_SCOPES.
var shareableScopes = map[string]bool{"documents": true, "transcripts": true, "analyses": true, "search": true}

type vdrConnectionJSON struct {
	Connected   bool     `json:"connected"`
	Status      *string  `json:"status"`
	VdrID       *string  `json:"vdr_id"`
	VdrName     *string  `json:"vdr_name"`
	ShareScopes []string `json:"share_scopes"`
	ConnectedAt *string  `json:"connected_at"`
}

// RegisterCognivault mounts /cognivault/* (auth-required; wire in the requireAuth group).
func (s *Server) RegisterCognivault(r chi.Router) {
	r.Get("/cognivault/deals/{dealID}/connection", s.cognivaultGetConnection)
	r.Post("/cognivault/deals/{dealID}/connect", s.cognivaultConnect)
	r.Patch("/cognivault/deals/{dealID}/connection", s.cognivaultPatch)
	r.Delete("/cognivault/deals/{dealID}/connection", s.cognivaultDisconnect)
}

func (s *Server) cognivaultGetConnection(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	if _, err := store.ScopedDeal(r.Context(), s.DB, p, chi.URLParam(r, "dealID")); storeError(w, err) {
		return
	}
	var status, vdrID string
	var vdrName, connectedAt *string
	var scopes []byte
	err := s.DB.QueryRowContext(r.Context(),
		"SELECT status, vdr_id, vdr_name, share_scopes, connected_at FROM deal_vdr_connections WHERE deal_id = ? AND status = 'active'",
		chi.URLParam(r, "dealID")).Scan(&status, &vdrID, &vdrName, &scopes, &connectedAt)
	if err == sql.ErrNoRows {
		writeJSON(w, http.StatusOK, vdrConnectionJSON{Connected: false, ShareScopes: []string{}})
		return
	}
	if storeError(w, err) {
		return
	}
	var ss []string
	_ = json.Unmarshal(scopes, &ss)
	if ss == nil {
		ss = []string{}
	}
	writeJSON(w, http.StatusOK, vdrConnectionJSON{Connected: true, Status: &status, VdrID: &vdrID, VdrName: vdrName, ShareScopes: ss, ConnectedAt: connectedAt})
}

func (s *Server) cognivaultConnect(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	if _, err := store.ScopedDeal(r.Context(), s.DB, p, chi.URLParam(r, "dealID")); storeError(w, err) {
		return
	}
	if s.Cfg.CognivaultClientID == "" {
		writeError(w, http.StatusInternalServerError, "CogniVault OAuth is not configured")
		return
	}
	// Full OAuth authorize-URL construction is ported when creds are configured.
	writeError(w, http.StatusInternalServerError, "CogniVault OAuth is not configured")
}

func (s *Server) cognivaultPatch(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	deal, err := store.ScopedDeal(r.Context(), s.DB, p, chi.URLParam(r, "dealID"))
	if storeError(w, err) {
		return
	}
	var b struct {
		ShareScopes []string `json:"share_scopes"`
	}
	if err := json.NewDecoder(r.Body).Decode(&b); err != nil {
		writeError(w, http.StatusUnprocessableEntity, "Invalid request body")
		return
	}
	for _, sc := range b.ShareScopes {
		if !shareableScopes[sc] {
			writeError(w, http.StatusUnprocessableEntity, "Invalid share scope: "+sc)
			return
		}
	}
	scopesJSON, _ := json.Marshal(b.ShareScopes)
	res, err := s.DB.ExecContext(r.Context(),
		"UPDATE deal_vdr_connections SET share_scopes = ?, updated_at = ? WHERE deal_id = ? AND status = 'active'",
		string(scopesJSON), util.NowISO(), deal.ID)
	if storeError(w, err) {
		return
	}
	if n, _ := res.RowsAffected(); n == 0 {
		writeError(w, http.StatusNotFound, "No active connection")
		return
	}
	s.cognivaultGetConnection(w, r)
}

func (s *Server) cognivaultDisconnect(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	deal, err := store.ScopedDeal(r.Context(), s.DB, p, chi.URLParam(r, "dealID"))
	if storeError(w, err) {
		return
	}
	now := util.NowISO()
	_, err = s.DB.ExecContext(r.Context(),
		"UPDATE deal_vdr_connections SET status = 'revoked', revoked_at = ?, updated_at = ? WHERE deal_id = ? AND status = 'active'",
		now, now, deal.ID)
	if storeError(w, err) {
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

// RegisterIntegrations mounts /integrations/* (auth-required). Prod has no OAuth
// provider creds, so connect reports "not configured"; the list reads the org's
// integration_credentials so the integrations page renders.
func (s *Server) RegisterIntegrations(r chi.Router) {
	r.Get("/integrations", s.integrationsList)
	r.Post("/integrations/{platform}/connect", s.integrationsConnect)
	r.Delete("/integrations/{platform}/disconnect", s.integrationsDisconnect)
}

func (s *Server) integrationsList(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	pred, args := p.OrgFilter("org_id")
	rows, err := s.DB.QueryContext(r.Context(),
		"SELECT platform, is_active FROM integration_credentials WHERE "+pred, args...)
	if storeError(w, err) {
		return
	}
	defer rows.Close()
	out := []map[string]any{}
	for rows.Next() {
		var platform string
		var active bool
		if err := rows.Scan(&platform, &active); err != nil {
			storeError(w, err)
			return
		}
		status := "disconnected"
		if active {
			status = "connected"
		}
		out = append(out, map[string]any{"platform": platform, "status": status})
	}
	writeJSON(w, http.StatusOK, out)
}

func (s *Server) integrationsConnect(w http.ResponseWriter, r *http.Request) {
	writeError(w, http.StatusServiceUnavailable, chi.URLParam(r, "platform")+" integration is not configured")
}

func (s *Server) integrationsDisconnect(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	pred, args := p.OrgFilter("org_id")
	all := append([]any{chi.URLParam(r, "platform")}, args...)
	_, err := s.DB.ExecContext(r.Context(),
		"UPDATE integration_credentials SET is_active = 0 WHERE platform = ? AND "+pred, all...)
	if storeError(w, err) {
		return
	}
	w.WriteHeader(http.StatusNoContent)
}
