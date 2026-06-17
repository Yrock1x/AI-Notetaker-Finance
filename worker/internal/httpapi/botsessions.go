package httpapi

import (
	"encoding/json"
	"net/http"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/model"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/store"
	"github.com/go-chi/chi/v5"
)

// botSessionJSON is the wire shape (matches BotSessionResponse in
// app/api/v1/store/bot_sessions.py).
type botSessionJSON struct {
	ID                    string  `json:"id"`
	OrgID                 string  `json:"org_id"`
	DealID                string  `json:"deal_id"`
	MeetingID             *string `json:"meeting_id"`
	Platform              string  `json:"platform"`
	MeetingURL            string  `json:"meeting_url"`
	Status                string  `json:"status"`
	ScheduledStart        *string `json:"scheduled_start"`
	ActualStart           *string `json:"actual_start"`
	ActualEnd             *string `json:"actual_end"`
	RecordingFileKey      *string `json:"recording_file_key"`
	RecallBotID           *string `json:"recall_bot_id"`
	LiveTranscriptChannel *string `json:"live_transcript_channel"`
	ConsentObtained       bool    `json:"consent_obtained"`
	CreatedBy             string  `json:"created_by"`
	CreatedAt             string  `json:"created_at"`
	UpdatedAt             string  `json:"updated_at"`
}

func toBotSessionJSON(b *model.MeetingBotSession) botSessionJSON {
	return botSessionJSON{b.ID, b.OrgID, b.DealID, b.MeetingID, b.Platform, b.MeetingURL,
		b.Status, b.ScheduledStart, b.ActualStart, b.ActualEnd, b.RecordingFileKey,
		b.RecallBotID, b.LiveTranscriptChannel, b.ConsentObtained, b.CreatedBy,
		b.CreatedAt, b.UpdatedAt}
}

// RegisterBotSessions mounts the meeting bot session routes (all auth-required).
// Flat patterns (not a Mount) so sibling resources can register routes under the
// shared prefixes. The session path param is {sessionID}.
func (s *Server) RegisterBotSessions(r chi.Router) {
	r.Get("/bot-sessions", s.listBotSessions)
	r.Post("/bot-sessions", s.createBotSession)
	r.Post("/bot-sessions/{sessionID}/cancel", s.cancelBotSession)
}

func (s *Server) listBotSessions(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	q := r.URL.Query()
	items, err := store.ListBotSessions(r.Context(), s.DB, p, store.BotSessionFilters{
		DealID: q.Get("deal_id"), Status: q.Get("status"),
	})
	if storeError(w, err) {
		return
	}
	out := make([]botSessionJSON, 0, len(items))
	for i := range items {
		out = append(out, toBotSessionJSON(&items[i]))
	}
	writeJSON(w, http.StatusOK, out)
}

type botSessionCreateBody struct {
	DealID          string  `json:"deal_id"`
	Platform        string  `json:"platform"`
	MeetingURL      string  `json:"meeting_url"`
	ScheduledStart  *string `json:"scheduled_start"`
	ConsentObtained bool    `json:"consent_obtained"`
}

func (s *Server) createBotSession(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	var b botSessionCreateBody
	if err := json.NewDecoder(r.Body).Decode(&b); err != nil || b.DealID == "" || b.Platform == "" || b.MeetingURL == "" {
		writeError(w, http.StatusUnprocessableEntity, "deal_id, platform and meeting_url are required")
		return
	}
	bs, err := store.CreateBotSession(r.Context(), s.DB, p, store.BotSessionCreate{
		DealID: b.DealID, Platform: b.Platform, MeetingURL: b.MeetingURL,
		ScheduledStart: b.ScheduledStart, ConsentObtained: b.ConsentObtained,
	})
	if storeError(w, err) {
		return
	}
	writeJSON(w, http.StatusCreated, toBotSessionJSON(bs))
}

func (s *Server) cancelBotSession(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	bs, err := store.CancelBotSession(r.Context(), s.DB, p, chi.URLParam(r, "sessionID"))
	if storeError(w, err) {
		return
	}
	writeJSON(w, http.StatusOK, toBotSessionJSON(bs))
}
