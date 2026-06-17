package httpapi

import (
	"encoding/json"
	"errors"
	"net/http"
	"strconv"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/model"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/store"
	"github.com/go-chi/chi/v5"
)

// dealJSON is the wire shape (matches DealResponse in app/api/v1/store/deals.py).
type dealJSON struct {
	ID            string  `json:"id"`
	OrgID         string  `json:"org_id"`
	Name          string  `json:"name"`
	Description   *string `json:"description"`
	TargetCompany *string `json:"target_company"`
	DealType      string  `json:"deal_type"`
	Stage         *string `json:"stage"`
	Status        string  `json:"status"`
	CreatedBy     string  `json:"created_by"`
	CreatedAt     string  `json:"created_at"`
	UpdatedAt     string  `json:"updated_at"`
}

func toDealJSON(d *model.Deal) dealJSON {
	return dealJSON{d.ID, d.OrgID, d.Name, d.Description, d.TargetCompany, d.DealType,
		d.Stage, d.Status, d.CreatedBy, d.CreatedAt, d.UpdatedAt}
}

type paginated struct {
	Items   any     `json:"items"`
	Cursor  *string `json:"cursor"`
	HasMore bool    `json:"has_more"`
}

// storeError maps a store sentinel error to an HTTP response. Returns true if it
// handled (wrote) the error.
func storeError(w http.ResponseWriter, err error) bool {
	switch {
	case err == nil:
		return false
	case errors.Is(err, store.ErrNotFound):
		writeError(w, http.StatusNotFound, "Not found")
	case errors.Is(err, store.ErrAccessDenied):
		writeError(w, http.StatusForbidden, "Access denied")
	case errors.Is(err, store.ErrConflict):
		writeError(w, http.StatusConflict, "Already exists")
	default:
		writeError(w, http.StatusInternalServerError, "internal error")
	}
	return true
}

// RegisterDeals mounts the deals + members routes (all auth-required).
func (s *Server) RegisterDeals(r chi.Router) {
	r.Route("/deals", func(r chi.Router) {
		r.Get("/", s.listDeals)
		r.Post("/", s.createDeal)
		r.Get("/{dealID}", s.getDeal)
		r.Patch("/{dealID}", s.patchDeal)
		r.Delete("/{dealID}", s.deleteDeal)
		r.Get("/{dealID}/members", s.listDealMembers)
		r.Post("/{dealID}/members", s.addDealMember)
		r.Delete("/{dealID}/members/{userID}", s.removeDealMember)
	})
}

func (s *Server) listDeals(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	q := r.URL.Query()
	limit, _ := strconv.Atoi(q.Get("limit"))
	items, cursor, hasMore, err := store.ListDeals(r.Context(), s.DB, p, store.DealFilters{
		Status: q.Get("status"), DealType: q.Get("deal_type"), Q: q.Get("q"),
		Cursor: q.Get("cursor"), Limit: limit,
	})
	if storeError(w, err) {
		return
	}
	out := make([]dealJSON, 0, len(items))
	for i := range items {
		out = append(out, toDealJSON(&items[i]))
	}
	writeJSON(w, http.StatusOK, paginated{Items: out, Cursor: cursor, HasMore: hasMore})
}

func (s *Server) getDeal(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	d, err := store.ScopedDeal(r.Context(), s.DB, p, chi.URLParam(r, "dealID"))
	if storeError(w, err) {
		return
	}
	writeJSON(w, http.StatusOK, toDealJSON(d))
}

type dealCreateBody struct {
	OrgID         string  `json:"org_id"`
	Name          string  `json:"name"`
	Description   *string `json:"description"`
	TargetCompany *string `json:"target_company"`
	DealType      string  `json:"deal_type"`
	Stage         *string `json:"stage"`
	Status        string  `json:"status"`
}

func (s *Server) createDeal(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	var b dealCreateBody
	if err := json.NewDecoder(r.Body).Decode(&b); err != nil || b.OrgID == "" || b.Name == "" {
		writeError(w, http.StatusUnprocessableEntity, "org_id and name are required")
		return
	}
	if err := p.RequireOrg(b.OrgID); err != nil { // 403 on foreign org
		storeError(w, err)
		return
	}
	d, err := store.CreateDeal(r.Context(), s.DB, p, store.DealCreate{
		OrgID: b.OrgID, Name: b.Name, Description: b.Description, TargetCompany: b.TargetCompany,
		DealType: b.DealType, Stage: b.Stage, Status: b.Status,
	})
	if storeError(w, err) {
		return
	}
	writeJSON(w, http.StatusCreated, toDealJSON(d))
}

type dealPatchBody struct {
	Name          *string `json:"name"`
	Description    *string `json:"description"`
	TargetCompany *string `json:"target_company"`
	DealType      *string `json:"deal_type"`
	Stage         *string `json:"stage"`
	Status        *string `json:"status"`
}

func (s *Server) patchDeal(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	var b dealPatchBody
	if err := json.NewDecoder(r.Body).Decode(&b); err != nil {
		writeError(w, http.StatusUnprocessableEntity, "Invalid request body")
		return
	}
	d, err := store.UpdateDeal(r.Context(), s.DB, p, chi.URLParam(r, "dealID"), store.DealUpdate{
		Name: b.Name, Description: b.Description, TargetCompany: b.TargetCompany,
		DealType: b.DealType, Stage: b.Stage, Status: b.Status,
	})
	if storeError(w, err) {
		return
	}
	writeJSON(w, http.StatusOK, toDealJSON(d))
}

func (s *Server) deleteDeal(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	if storeError(w, store.SoftDeleteDeal(r.Context(), s.DB, p, chi.URLParam(r, "dealID"))) {
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

type memberJSON struct {
	UserID    string  `json:"user_id"`
	Role      string  `json:"role"`
	Email     *string `json:"email"`
	FullName  *string `json:"full_name"`
	AvatarURL *string `json:"avatar_url"`
}

func (s *Server) listDealMembers(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	if _, err := store.ScopedDeal(r.Context(), s.DB, p, chi.URLParam(r, "dealID")); storeError(w, err) {
		return
	}
	members, err := store.ListDealMembers(r.Context(), s.DB, chi.URLParam(r, "dealID"))
	if storeError(w, err) {
		return
	}
	out := make([]memberJSON, 0, len(members))
	for _, m := range members {
		out = append(out, memberJSON{m.UserID, m.Role, m.Email, m.FullName, m.AvatarURL})
	}
	writeJSON(w, http.StatusOK, out)
}

func (s *Server) addDealMember(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	deal, err := store.ScopedDeal(r.Context(), s.DB, p, chi.URLParam(r, "dealID"))
	if storeError(w, err) {
		return
	}
	var b struct {
		UserID string `json:"user_id"`
		Role   string `json:"role"`
	}
	if err := json.NewDecoder(r.Body).Decode(&b); err != nil || b.UserID == "" {
		writeError(w, http.StatusUnprocessableEntity, "user_id is required")
		return
	}
	m, err := store.AddDealMember(r.Context(), s.DB, deal, b.UserID, b.Role, p.UserID)
	if errors.Is(err, store.ErrNotFound) {
		writeError(w, http.StatusNotFound, "User is not a member of this org")
		return
	}
	if storeError(w, err) {
		return
	}
	writeJSON(w, http.StatusCreated, memberJSON{m.UserID, m.Role, m.Email, m.FullName, m.AvatarURL})
}

func (s *Server) removeDealMember(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	if _, err := store.ScopedDeal(r.Context(), s.DB, p, chi.URLParam(r, "dealID")); storeError(w, err) {
		return
	}
	if storeError(w, store.RemoveDealMember(r.Context(), s.DB, chi.URLParam(r, "dealID"), chi.URLParam(r, "userID"))) {
		return
	}
	w.WriteHeader(http.StatusNoContent)
}
