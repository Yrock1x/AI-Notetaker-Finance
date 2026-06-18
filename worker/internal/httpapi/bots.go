package httpapi

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/integrations/recall"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/store"
	"github.com/go-chi/chi/v5"
)

// bots.go ports app/api/v1/internal/bots.py: the Recall.ai bot lifecycle
// (start / stop / auto-schedule-due / finalize), called by the Inngest pipeline
// behind the X-Internal-Token guard. NOT autonomously E2E-verifiable (needs a
// real Recall account + a live meeting) — covered by unit tests + review.

// RegisterBots mounts the /internal/bot/* routes (wire inside the /internal group).
func (s *Server) RegisterBots(r chi.Router) {
	r.Post("/bot/start", s.botStart)
	r.Post("/bot/stop", s.botStop)
	r.Post("/bot/auto-schedule-due", s.botAutoScheduleDue)
	r.Post("/bot/finalize", s.botFinalize)
}

// recallHTTPClient is the HTTP client the Recall calls use; a package var so
// tests can intercept the Recall REST API.
var recallHTTPClient = &http.Client{Timeout: 30 * time.Second}

func (s *Server) recallClient() *recall.Client {
	c := recall.New(s.Cfg.RecallAPIKey, s.Cfg.RecallRegion)
	c.HTTPClient = recallHTTPClient
	return c
}

type botRequest struct {
	SessionID string `json:"session_id"`
}

// POST /internal/bot/start
func (s *Server) botStart(w http.ResponseWriter, r *http.Request) {
	var body botRequest
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil || body.SessionID == "" {
		writeError(w, http.StatusUnprocessableEntity, "session_id is required")
		return
	}
	if s.Cfg.RecallAPIKey == "" {
		writeError(w, http.StatusInternalServerError, "RECALL_API_KEY not configured")
		return
	}
	bs, err := store.GetBotSession(r.Context(), s.DB, body.SessionID)
	if err == store.ErrNotFound {
		writeError(w, http.StatusNotFound, "Bot session not found")
		return
	}
	if storeError(w, err) {
		return
	}
	meetingID, err := store.EnsureBotMeeting(r.Context(), s.DB, bs)
	if storeError(w, err) {
		return
	}

	webhookURL := strings.TrimRight(s.Cfg.PublicAPIURL, "/") + "/api/v1/webhooks/recall"
	cfg := recall.CreateBotConfig{
		MeetingURL: bs.MeetingURL,
		BotName:    "CogniSuite Notetaker",
		RecordingConfig: map[string]any{
			"transcript":         map[string]any{"provider": map[string]any{"deepgram_streaming": map[string]any{}}},
			"participant_events": map[string]any{"provider": map[string]any{"meeting_platform": map[string]any{}}},
			"chat":               map[string]any{"provider": map[string]any{"meeting_platform": map[string]any{}}},
			"realtime_endpoints": []map[string]any{{
				"type": "webhook", "url": webhookURL,
				"events": []string{
					"transcript.data", "transcript.partial_data",
					"participant_events.join", "participant_events.leave",
					"participant_events.update", "participant_events.chat_message",
				},
			}},
		},
		Metadata: map[string]any{
			"session_id": bs.ID, "org_id": bs.OrgID, "deal_id": bs.DealID, "meeting_id": meetingID,
		},
	}
	botData, err := s.recallClient().CreateBot(r.Context(), cfg)
	if err != nil {
		_ = store.SetBotStatus(r.Context(), s.DB, bs.ID, "failed")
		writeError(w, http.StatusBadGateway, "Recall.ai rejected bot create: "+err.Error())
		return
	}
	recallBotID, _ := botData["id"].(string)
	if err := store.MarkBotJoining(r.Context(), s.DB, bs.ID, recallBotID, "transcripts:"+meetingID); storeError(w, err) {
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"session_id": bs.ID, "status": "joining", "recall_bot_id": recallBotID})
}

// POST /internal/bot/stop
func (s *Server) botStop(w http.ResponseWriter, r *http.Request) {
	var body botRequest
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil || body.SessionID == "" {
		writeError(w, http.StatusUnprocessableEntity, "session_id is required")
		return
	}
	bs, err := store.GetBotSession(r.Context(), s.DB, body.SessionID)
	if err == store.ErrNotFound {
		writeError(w, http.StatusNotFound, "Bot session not found")
		return
	}
	if storeError(w, err) {
		return
	}
	if s.Cfg.RecallAPIKey != "" && bs.RecallBotID != nil && *bs.RecallBotID != "" {
		// Best-effort leave; a failure here shouldn't block the status flip.
		_ = s.recallClient().LeaveBot(r.Context(), *bs.RecallBotID)
	}
	newStatus := "completed"
	if bs.Status == "scheduled" || bs.Status == "joining" {
		newStatus = "cancelled"
	}
	if err := store.SetBotStatus(r.Context(), s.DB, bs.ID, newStatus); storeError(w, err) {
		return
	}
	rb := ""
	if bs.RecallBotID != nil {
		rb = *bs.RecallBotID
	}
	writeJSON(w, http.StatusOK, map[string]any{"session_id": bs.ID, "status": newStatus, "recall_bot_id": rb})
}

// POST /internal/bot/auto-schedule-due
func (s *Server) botAutoScheduleDue(w http.ResponseWriter, r *http.Request) {
	scheduled, err := store.AutoScheduleDue(r.Context(), s.DB)
	if storeError(w, err) {
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"scheduled": scheduled})
}

// botFetchJSON GETs a (signed, no-auth) URL and decodes JSON into v.
func botFetchJSON(ctx context.Context, rawURL string, v any) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, rawURL, nil)
	if err != nil {
		return err
	}
	resp, err := oauthHTTPClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 64<<20))
	if resp.StatusCode >= 400 {
		return &recall.HTTPError{Status: resp.StatusCode, Body: truncateStr(string(body), 300)}
	}
	return json.Unmarshal(body, v)
}

func truncateStr(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n]
}

// recallTurn is one continuous speaker turn in the Recall transcript JSON.
type recallTurn struct {
	Participant struct {
		ID    any    `json:"id"`
		Name  string `json:"name"`
		Email string `json:"email"`
	} `json:"participant"`
	Words []struct {
		Text           string `json:"text"`
		StartTimestamp *struct {
			Relative float64 `json:"relative"`
		} `json:"start_timestamp"`
		EndTimestamp *struct {
			Relative float64 `json:"relative"`
		} `json:"end_timestamp"`
	} `json:"words"`
}

// POST /internal/bot/finalize — post-call pull of the authoritative transcript +
// participants from Recall's recording media_shortcuts (ports bot_finalize).
func (s *Server) botFinalize(w http.ResponseWriter, r *http.Request) {
	var body botRequest
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil || body.SessionID == "" {
		writeError(w, http.StatusUnprocessableEntity, "session_id is required")
		return
	}
	bs, err := store.GetBotSession(r.Context(), s.DB, body.SessionID)
	if err == store.ErrNotFound {
		writeError(w, http.StatusNotFound, "Bot session not found")
		return
	}
	if storeError(w, err) {
		return
	}
	if bs.RecallBotID == nil || *bs.RecallBotID == "" {
		writeError(w, http.StatusBadRequest, "Session has no recall_bot_id")
		return
	}
	if bs.MeetingID == nil || *bs.MeetingID == "" {
		writeError(w, http.StatusBadRequest, "Session has no meeting_id")
		return
	}
	meetingID := *bs.MeetingID
	if s.Cfg.RecallAPIKey == "" {
		writeError(w, http.StatusInternalServerError, "RECALL_API_KEY not configured")
		return
	}

	bot, err := s.recallClient().GetBot(r.Context(), *bs.RecallBotID)
	if err != nil {
		writeError(w, http.StatusBadGateway, "Recall.ai call failed: "+err.Error())
		return
	}
	transcriptURL, metaURL := recordingShortcutURLs(bot)
	if transcriptURL == "" {
		writeJSON(w, http.StatusOK, map[string]any{
			"meeting_id": meetingID, "transcript_id": nil, "segment_count": 0, "participant_count": 0,
		})
		return
	}

	var turns []recallTurn
	if err := botFetchJSON(r.Context(), transcriptURL, &turns); err != nil {
		writeError(w, http.StatusBadGateway, "Recall transcript fetch failed")
		return
	}

	var segments []store.TranscriptSegmentInput
	var fullParts []string
	wordCount := 0
	participantsByID := map[string]store.BotParticipant{}
	for idx, turn := range turns {
		var parts []string
		for _, wd := range turn.Words {
			if t := strings.TrimSpace(wd.Text); t != "" {
				parts = append(parts, t)
			}
		}
		text := strings.Join(parts, " ")
		pid := participantIDString(turn.Participant.ID, idx)
		if turn.Participant.ID != nil {
			var name, email *string
			if turn.Participant.Name != "" {
				n := turn.Participant.Name
				name = &n
			}
			if turn.Participant.Email != "" {
				e := turn.Participant.Email
				email = &e
			}
			label := turn.Participant.Name
			if label == "" {
				label = "Participant " + pid
			}
			participantsByID[pid] = store.BotParticipant{
				RecallParticipantID: pid, SpeakerLabel: label, SpeakerName: name, Email: email,
			}
		}
		if text == "" || len(turn.Words) == 0 {
			continue
		}
		fullParts = append(fullParts, text)
		wordCount += len(strings.Fields(text))
		var start, end float64
		if turn.Words[0].StartTimestamp != nil {
			start = turn.Words[0].StartTimestamp.Relative
		}
		if last := turn.Words[len(turn.Words)-1]; last.EndTimestamp != nil {
			end = last.EndTimestamp.Relative
		} else {
			end = start
		}
		label := turn.Participant.Name
		if label == "" {
			label = "Speaker " + pid
		}
		segments = append(segments, store.TranscriptSegmentInput{
			SpeakerLabel: label, SpeakerName: turn.Participant.Name, Text: text,
			StartTime: start, EndTime: end, SegmentIndex: idx,
		})
	}

	participants := make([]store.BotParticipant, 0, len(participantsByID))
	for _, p := range participantsByID {
		participants = append(participants, p)
	}
	transcriptID, segCount, err := store.SaveBotFinalize(r.Context(), s.DB, bs.OrgID, meetingID,
		strings.Join(fullParts, " "), wordCount, segments, participants)
	if storeError(w, err) {
		return
	}

	// Meeting title from metadata (only overwrites placeholders).
	if metaURL != "" {
		var meta struct {
			Title string `json:"title"`
		}
		if err := botFetchJSON(r.Context(), metaURL, &meta); err == nil && strings.TrimSpace(meta.Title) != "" {
			_ = store.UpdateMeetingTitleIfPlaceholder(r.Context(), s.DB, meetingID, strings.TrimSpace(meta.Title))
		}
	}
	// Flip to 'uploaded' so the downstream pipeline treats it as ready.
	_ = store.SetMeetingStatus(r.Context(), s.DB, meetingID, "uploaded", nil)

	var tid any
	if transcriptID != "" {
		tid = transcriptID
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"meeting_id": meetingID, "transcript_id": tid,
		"segment_count": segCount, "participant_count": len(participants),
	})
}

// recordingShortcutURLs pulls the transcript + meeting_metadata download URLs out
// of bot.recordings[0].media_shortcuts (the nested-map walk from bot_finalize).
func recordingShortcutURLs(bot map[string]any) (transcriptURL, metaURL string) {
	recs, _ := bot["recordings"].([]any)
	if len(recs) == 0 {
		return "", ""
	}
	rec, _ := recs[0].(map[string]any)
	shortcuts, _ := rec["media_shortcuts"].(map[string]any)
	return shortcutDownloadURL(shortcuts, "transcript"), shortcutDownloadURL(shortcuts, "meeting_metadata")
}

func shortcutDownloadURL(shortcuts map[string]any, key string) string {
	sc, _ := shortcuts[key].(map[string]any)
	data, _ := sc["data"].(map[string]any)
	url, _ := data["download_url"].(string)
	return url
}

func participantIDString(id any, fallbackIdx int) string {
	switch v := id.(type) {
	case string:
		return v
	case float64:
		return strconv.FormatInt(int64(v), 10) // Recall participant ids are integers
	default:
		return strconv.Itoa(fallbackIdx)
	}
}
