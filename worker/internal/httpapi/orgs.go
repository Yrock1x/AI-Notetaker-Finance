package httpapi

import (
	"net/http"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/store"
	"github.com/go-chi/chi/v5"
)

// orgJSON is the wire shape (matches OrgResponse in app/api/v1/store/orgs.py).
type orgJSON struct {
	ID   string `json:"id"`
	Name string `json:"name"`
	Slug string `json:"slug"`
	Role string `json:"role"`
}

// orgMemberJSON is the wire shape (matches OrgMemberResponse in orgs.py).
type orgMemberJSON struct {
	UserID    string  `json:"user_id"`
	Role      string  `json:"role"`
	Email     *string `json:"email"`
	FullName  *string `json:"full_name"`
	AvatarURL *string `json:"avatar_url"`
}

// RegisterOrgs mounts the orgs routes (all auth-required). Flat chi patterns;
// the org path param is {orgID} everywhere.
func (s *Server) RegisterOrgs(r chi.Router) {
	r.Get("/orgs", s.listOrgs)
	r.Get("/orgs/{orgID}/members", s.listOrgMembers)
}

func (s *Server) listOrgs(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	orgs, err := store.ListOrgs(r.Context(), s.DB, p)
	if storeError(w, err) {
		return
	}
	out := make([]orgJSON, 0, len(orgs))
	for _, o := range orgs {
		out = append(out, orgJSON{o.ID, o.Name, o.Slug, o.Role})
	}
	writeJSON(w, http.StatusOK, out)
}

func (s *Server) listOrgMembers(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	orgID := chi.URLParam(r, "orgID")
	if err := p.RequireOrg(orgID); err != nil { // 403 on foreign/unknown org
		storeError(w, err)
		return
	}
	members, err := store.ListOrgMembers(r.Context(), s.DB, orgID)
	if storeError(w, err) {
		return
	}
	out := make([]orgMemberJSON, 0, len(members))
	for _, m := range members {
		out = append(out, orgMemberJSON{m.UserID, m.Role, m.Email, m.FullName, m.AvatarURL})
	}
	writeJSON(w, http.StatusOK, out)
}
