package httpapi

import (
	"encoding/json"
	"net/http"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/model"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/store"
	"github.com/go-chi/chi/v5"
)

// dashboard.go ports app/api/v1/store/dashboard.py: the org activity feed and
// the per-deal extractions + action-items endpoints. JSON tags match the
// *Response models in dashboard.py field-for-field so the Go worker is a
// drop-in for the unchanged frontend.

// jsonOrNull turns a *string holding stored JSON text into a value the encoder
// emits verbatim (the parsed object/array), matching Python's dict|None fields.
// A nil pointer (NULL column) or unparseable text becomes JSON null.
func jsonOrNull(raw *string) json.RawMessage {
	if raw == nil || *raw == "" {
		return json.RawMessage("null")
	}
	msg := json.RawMessage(*raw)
	if !json.Valid(msg) {
		return json.RawMessage("null")
	}
	return msg
}

// activityJSON matches ActivityResponse.
type activityJSON struct {
	ID           string          `json:"id"`
	Action       string          `json:"action"`
	ResourceType string          `json:"resource_type"`
	ResourceID   *string         `json:"resource_id"`
	DealID       *string         `json:"deal_id"`
	DealName     *string         `json:"deal_name"`
	ActorName    *string         `json:"actor_name"`
	CreatedAt    string          `json:"created_at"`
	Details      json.RawMessage `json:"details"`
}

func toActivityJSON(r *model.ActivityRow) activityJSON {
	return activityJSON{
		ID: r.ID, Action: r.Action, ResourceType: r.ResourceType, ResourceID: r.ResourceID,
		DealID: r.DealID, DealName: r.DealName, ActorName: r.ActorName,
		CreatedAt: r.CreatedAt, Details: jsonOrNull(r.Details),
	}
}

// extractionJSON matches ExtractionResponse.
type extractionJSON struct {
	ID               string          `json:"id"`
	MeetingID        string          `json:"meeting_id"`
	CallType         string          `json:"call_type"`
	StructuredOutput json.RawMessage `json:"structured_output"`
	CreatedAt        string          `json:"created_at"`
}

func toExtractionJSON(r *model.ExtractionRow) extractionJSON {
	return extractionJSON{
		ID: r.ID, MeetingID: r.MeetingID, CallType: r.CallType,
		StructuredOutput: jsonOrNull(r.StructuredOutput), CreatedAt: r.CreatedAt,
	}
}

// actionItemJSON matches ActionItemResponse.
type actionItemJSON struct {
	ActionKey   string  `json:"action_key"`
	ActionText  *string `json:"action_text"`
	AnalysisID  string  `json:"analysis_id"`
	CompletedBy string  `json:"completed_by"`
	CompletedAt string  `json:"completed_at"`
}

func toActionItemJSON(a *model.ActionItem) actionItemJSON {
	return actionItemJSON{
		ActionKey: a.ActionKey, ActionText: a.ActionText, AnalysisID: a.AnalysisID,
		CompletedBy: a.CompletedBy, CompletedAt: a.CompletedAt,
	}
}

// RegisterDashboard mounts the dashboard activity feed + per-deal extractions
// and action-items routes (all auth-required). Flat chi patterns sharing the
// {dealID} param name with the other /deals/{dealID}/... resources.
func (s *Server) RegisterDashboard(r chi.Router) {
	r.Get("/dashboard/activity", s.listActivity)
	r.Get("/deals/{dealID}/extractions", s.listExtractions)
	r.Get("/deals/{dealID}/action-items", s.listActionItems)
	r.Post("/deals/{dealID}/action-items", s.upsertActionItem)
	r.Delete("/deals/{dealID}/action-items/{actionKey}", s.deleteActionItem)
}

func (s *Server) listActivity(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	rows, err := store.ListActivity(r.Context(), s.DB, p)
	if storeError(w, err) {
		return
	}
	out := make([]activityJSON, 0, len(rows))
	for i := range rows {
		out = append(out, toActivityJSON(&rows[i]))
	}
	writeJSON(w, http.StatusOK, out)
}

func (s *Server) listExtractions(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	rows, err := store.ListExtractions(r.Context(), s.DB, p, chi.URLParam(r, "dealID"))
	if storeError(w, err) {
		return
	}
	out := make([]extractionJSON, 0, len(rows))
	for i := range rows {
		out = append(out, toExtractionJSON(&rows[i]))
	}
	writeJSON(w, http.StatusOK, out)
}

func (s *Server) listActionItems(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	rows, err := store.ListActionItems(r.Context(), s.DB, p, chi.URLParam(r, "dealID"))
	if storeError(w, err) {
		return
	}
	out := make([]actionItemJSON, 0, len(rows))
	for i := range rows {
		out = append(out, toActionItemJSON(&rows[i]))
	}
	writeJSON(w, http.StatusOK, out)
}

type actionItemCreateBody struct {
	AnalysisID string  `json:"analysis_id"`
	ActionKey  string  `json:"action_key"`
	ActionText *string `json:"action_text"`
}

func (s *Server) upsertActionItem(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	var b actionItemCreateBody
	if err := json.NewDecoder(r.Body).Decode(&b); err != nil || b.AnalysisID == "" || b.ActionKey == "" {
		writeError(w, http.StatusUnprocessableEntity, "analysis_id and action_key are required")
		return
	}
	item, err := store.UpsertActionItem(r.Context(), s.DB, p, chi.URLParam(r, "dealID"), store.ActionItemCreate{
		AnalysisID: b.AnalysisID, ActionKey: b.ActionKey, ActionText: b.ActionText,
	})
	if storeError(w, err) {
		return
	}
	writeJSON(w, http.StatusCreated, toActionItemJSON(item))
}

// deleteActionItem removes an action-item completion (ports delete_action_item).
// 204 whether or not the (deal, action_key) existed, matching the Python handler.
func (s *Server) deleteActionItem(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	err := store.DeleteActionItem(r.Context(), s.DB, p,
		chi.URLParam(r, "dealID"), chi.URLParam(r, "actionKey"))
	if storeError(w, err) {
		return
	}
	w.WriteHeader(http.StatusNoContent)
}
