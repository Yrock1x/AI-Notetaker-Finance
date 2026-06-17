package httpapi

import (
	"net/http"
	"strconv"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/model"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/store"
	"github.com/go-chi/chi/v5"
)

// ---- wire shapes (match the *Response models in store/transcripts.py) ------

// transcriptJSON matches TranscriptResponse.
type transcriptJSON struct {
	ID              string   `json:"id"`
	FullText        string   `json:"full_text"`
	Language        string   `json:"language"`
	WordCount       int      `json:"word_count"`
	ConfidenceScore *float64 `json:"confidence_score"`
	CreatedAt       string   `json:"created_at"`
}

func toTranscriptJSON(t *model.Transcript) transcriptJSON {
	return transcriptJSON{t.ID, t.FullText, t.Language, t.WordCount, t.ConfidenceScore, t.CreatedAt}
}

// segmentJSON matches SegmentResponse.
type segmentJSON struct {
	ID           string   `json:"id"`
	MeetingID    string   `json:"meeting_id"`
	SpeakerLabel string   `json:"speaker_label"`
	SpeakerName  *string  `json:"speaker_name"`
	Text         string   `json:"text"`
	StartTime    float64  `json:"start_time"`
	EndTime      float64  `json:"end_time"`
	Confidence   *float64 `json:"confidence"`
	SegmentIndex int      `json:"segment_index"`
	IsPartial    bool     `json:"is_partial"`
}

func toSegmentJSON(s *model.TranscriptSegment) segmentJSON {
	return segmentJSON{s.ID, s.MeetingID, s.SpeakerLabel, s.SpeakerName, s.Text,
		s.StartTime, s.EndTime, s.Confidence, s.SegmentIndex, s.IsPartial}
}

// participantJSON matches ParticipantResponse.
type participantJSON struct {
	ID           string  `json:"id"`
	MeetingID    string  `json:"meeting_id"`
	SpeakerLabel string  `json:"speaker_label"`
	SpeakerName  *string `json:"speaker_name"`
	UserID       *string `json:"user_id"`
	EmailAddress *string `json:"email_address"`
	JoinedAt     *string `json:"joined_at"`
	LeftAt       *string `json:"left_at"`
}

func toParticipantJSON(p *model.MeetingParticipant) participantJSON {
	return participantJSON{p.ID, p.MeetingID, p.SpeakerLabel, p.SpeakerName, p.UserID,
		p.EmailAddress, p.JoinedAt, p.LeftAt}
}

// chatMessageJSON matches ChatMessageResponse.
type chatMessageJSON struct {
	ID          string  `json:"id"`
	MeetingID   string  `json:"meeting_id"`
	SenderName  *string `json:"sender_name"`
	SenderEmail *string `json:"sender_email"`
	Text        string  `json:"text"`
	SentAt      string  `json:"sent_at"`
}

func toChatMessageJSON(c *model.MeetingChatMessage) chatMessageJSON {
	return chatMessageJSON{c.ID, c.MeetingID, c.SenderName, c.SenderEmail, c.Text, c.SentAt}
}

// RegisterTranscripts mounts the read-only transcript / segments / participants /
// chat routes (all auth-required). Flat patterns under the shared
// /meetings/{meetingID}/... prefix; the meeting path param is {meetingID}.
func (s *Server) RegisterTranscripts(r chi.Router) {
	r.Get("/meetings/{meetingID}/transcript", s.getTranscript)
	r.Get("/meetings/{meetingID}/transcript-segments", s.listTranscriptSegments)
	r.Get("/meetings/{meetingID}/participants", s.listParticipants)
	r.Get("/meetings/{meetingID}/chat", s.listChat)
}

func (s *Server) getTranscript(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	t, err := store.GetTranscript(r.Context(), s.DB, p, chi.URLParam(r, "meetingID"))
	if storeError(w, err) {
		return
	}
	writeJSON(w, http.StatusOK, toTranscriptJSON(t))
}

func (s *Server) listTranscriptSegments(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	q := r.URL.Query()
	limit, _ := strconv.Atoi(q.Get("limit"))
	items, err := store.ListTranscriptSegments(r.Context(), s.DB, p, chi.URLParam(r, "meetingID"), store.SegmentFilters{
		Speaker: q.Get("speaker"), Q: q.Get("q"), Limit: limit,
	})
	if storeError(w, err) {
		return
	}
	out := make([]segmentJSON, 0, len(items))
	for i := range items {
		out = append(out, toSegmentJSON(&items[i]))
	}
	writeJSON(w, http.StatusOK, out)
}

func (s *Server) listParticipants(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	items, err := store.ListParticipants(r.Context(), s.DB, p, chi.URLParam(r, "meetingID"))
	if storeError(w, err) {
		return
	}
	out := make([]participantJSON, 0, len(items))
	for i := range items {
		out = append(out, toParticipantJSON(&items[i]))
	}
	writeJSON(w, http.StatusOK, out)
}

func (s *Server) listChat(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	items, err := store.ListChat(r.Context(), s.DB, p, chi.URLParam(r, "meetingID"))
	if storeError(w, err) {
		return
	}
	out := make([]chatMessageJSON, 0, len(items))
	for i := range items {
		out = append(out, toChatMessageJSON(&items[i]))
	}
	writeJSON(w, http.StatusOK, out)
}
