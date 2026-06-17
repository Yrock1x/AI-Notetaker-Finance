package httpapi

import (
	"encoding/json"
	"errors"
	"net/http"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/model"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/store"
	"github.com/go-chi/chi/v5"
)

// meetingJSON is the wire shape (matches MeetingResponse in
// app/api/v1/store/meetings.py). meeting_date / created_at / updated_at are
// emitted as the stored ISO-8601 strings.
type meetingJSON struct {
	ID               string  `json:"id"`
	OrgID            string  `json:"org_id"`
	DealID           *string `json:"deal_id"`
	Title            string  `json:"title"`
	MeetingDate      *string `json:"meeting_date"`
	DurationSeconds  *int64  `json:"duration_seconds"`
	Source           string  `json:"source"`
	SourceURL        *string `json:"source_url"`
	FileKey          *string `json:"file_key"`
	Status           string  `json:"status"`
	ErrorMessage     *string `json:"error_message"`
	BotEnabled       bool    `json:"bot_enabled"`
	ExternalEventID  *string `json:"external_event_id"`
	ExternalProvider *string `json:"external_provider"`
	CreatedBy        string  `json:"created_by"`
	CreatedAt        string  `json:"created_at"`
	UpdatedAt        string  `json:"updated_at"`
}

func toMeetingJSON(m *model.Meeting) meetingJSON {
	return meetingJSON{
		ID: m.ID, OrgID: m.OrgID, DealID: m.DealID, Title: m.Title,
		MeetingDate: m.MeetingDate, DurationSeconds: m.DurationSeconds,
		Source: m.Source, SourceURL: m.SourceURL, FileKey: m.FileKey,
		Status: m.Status, ErrorMessage: m.ErrorMessage, BotEnabled: m.BotEnabled,
		ExternalEventID: m.ExternalEventID, ExternalProvider: m.ExternalProvider,
		CreatedBy: m.CreatedBy, CreatedAt: m.CreatedAt, UpdatedAt: m.UpdatedAt,
	}
}

// RegisterMeetings mounts the meetings routes (all auth-required). Flat chi
// patterns sharing the /deals/{dealID}/... and /meetings/{meetingID} prefixes
// with the other resources; param names match the rest of the worker.
func (s *Server) RegisterMeetings(r chi.Router) {
	r.Get("/deals/{dealID}/meetings", s.listDealMeetings)
	r.Post("/deals/{dealID}/meetings", s.createMeeting)
	r.Get("/meetings/{meetingID}", s.getMeeting)
	r.Patch("/meetings/{meetingID}", s.patchMeeting)
}

func (s *Server) listDealMeetings(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	dealID := chi.URLParam(r, "dealID")
	if _, err := store.ScopedDeal(r.Context(), s.DB, p, dealID); storeError(w, err) {
		return
	}
	items, err := store.ListDealMeetings(r.Context(), s.DB, p, dealID)
	if storeError(w, err) {
		return
	}
	out := make([]meetingJSON, 0, len(items))
	for i := range items {
		out = append(out, toMeetingJSON(&items[i]))
	}
	writeJSON(w, http.StatusOK, out)
}

type meetingCreateBody struct {
	Title           string  `json:"title"`
	Source          string  `json:"source"`
	FileKey         *string `json:"file_key"`
	SourceURL       *string `json:"source_url"`
	MeetingDate     *string `json:"meeting_date"`
	DurationSeconds *int64  `json:"duration_seconds"`
	BotEnabled      *bool   `json:"bot_enabled"`
}

func (s *Server) createMeeting(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	deal, err := store.ScopedDeal(r.Context(), s.DB, p, chi.URLParam(r, "dealID"))
	if storeError(w, err) {
		return
	}
	var b meetingCreateBody
	if err := json.NewDecoder(r.Body).Decode(&b); err != nil || b.Title == "" {
		writeError(w, http.StatusUnprocessableEntity, "title is required")
		return
	}
	botEnabled := true // MeetingCreate default
	if b.BotEnabled != nil {
		botEnabled = *b.BotEnabled
	}
	m, err := store.CreateMeeting(r.Context(), s.DB, p, deal, store.MeetingCreate{
		Title: b.Title, Source: b.Source, FileKey: b.FileKey, SourceURL: b.SourceURL,
		MeetingDate: b.MeetingDate, DurationSeconds: b.DurationSeconds, BotEnabled: botEnabled,
	})
	if storeError(w, err) {
		return
	}
	writeJSON(w, http.StatusCreated, toMeetingJSON(m))
}

func (s *Server) getMeeting(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	m, err := store.ScopedMeeting(r.Context(), s.DB, p, chi.URLParam(r, "meetingID"))
	if storeError(w, err) {
		return
	}
	writeJSON(w, http.StatusOK, toMeetingJSON(m))
}

func (s *Server) patchMeeting(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())

	// Decode twice: once into a typed struct for the values, once into a raw
	// map so we can honour exclude_unset — meeting_date/deal_id may be present
	// with an explicit null (→ SQL NULL) vs. absent (→ unchanged).
	var raw map[string]json.RawMessage
	if err := json.NewDecoder(r.Body).Decode(&raw); err != nil {
		writeError(w, http.StatusUnprocessableEntity, "Invalid request body")
		return
	}
	var b struct {
		Title       *string `json:"title"`
		MeetingDate *string `json:"meeting_date"`
		BotEnabled  *bool   `json:"bot_enabled"`
		DealID      *string `json:"deal_id"`
	}
	// Re-marshal the raw map so the typed decode sees the same payload.
	if buf, err := json.Marshal(raw); err == nil {
		_ = json.Unmarshal(buf, &b)
	}
	_, mdSet := raw["meeting_date"]
	_, dealSet := raw["deal_id"]

	m, err := store.UpdateMeeting(r.Context(), s.DB, p, chi.URLParam(r, "meetingID"), store.MeetingUpdate{
		Title:          b.Title,
		BotEnabled:     b.BotEnabled,
		MeetingDate:    b.MeetingDate,
		MeetingDateSet: mdSet,
		DealID:         b.DealID,
		DealIDSet:      dealSet,
	})
	if errors.Is(err, store.ErrCrossOrg) {
		writeError(w, http.StatusBadRequest, "Cross-org deal")
		return
	}
	if storeError(w, err) {
		return
	}
	writeJSON(w, http.StatusOK, toMeetingJSON(m))
}
