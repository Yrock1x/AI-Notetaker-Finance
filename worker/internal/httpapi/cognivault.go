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

// The /integrations/* OAuth connect / callback / disconnect handlers live in
// integrations.go.
