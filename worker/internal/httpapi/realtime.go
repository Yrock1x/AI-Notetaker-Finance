package httpapi

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/realtime"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/store"
	"github.com/go-chi/chi/v5"
)

// RegisterRealtime mounts the live-meeting SSE stream (session-authed) and the
// public Recall webhook. The SSE route goes behind requireAuth; the webhook is
// public (its capability is the Recall signature, verified in-handler), so it is
// registered on a sibling router without the auth middleware.
//
// Ports app/realtime/sse.py + app/api/v1/recall_webhooks.py. Flat chi patterns
// keep {meetingID} consistent with the rest of /api/v1.
func (s *Server) RegisterRealtime(r chi.Router) {
	r.With(s.requireAuth).Get("/meetings/{meetingID}/stream", s.streamMeeting)
	// Public: no requireAuth. Both paths the Python router exposes
	// (back-compat /transcript kept for old Recall webhook URLs).
	r.Post("/webhooks/recall", s.recallWebhook)
	r.Post("/webhooks/recall/transcript", s.recallWebhook)
}

// ---------------------------------------------------------------------------
// SSE: GET /meetings/{meetingID}/stream
// ---------------------------------------------------------------------------

// heartbeatInterval keeps proxies/load balancers from closing an otherwise idle
// connection (ports HEARTBEAT_INTERVAL).
const heartbeatInterval = 15 * time.Second

func (s *Server) streamMeeting(w http.ResponseWriter, r *http.Request) {
	// Scope check BEFORE the stream opens: a cross-tenant request fails fast with
	// 404 rather than opening an empty stream (ports scoped_meeting_or_404 in
	// sse.py). org_id on the meeting is the tenant guard.
	p := principalFromCtx(r.Context())
	if _, err := store.ScopedMeeting(r.Context(), s.DB, p, chi.URLParam(r, "meetingID")); storeError(w, err) {
		return
	}

	flusher, ok := w.(http.Flusher)
	if !ok {
		writeError(w, http.StatusInternalServerError, "streaming unsupported")
		return
	}

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("X-Accel-Buffering", "no") // disable proxy buffering of the stream
	w.WriteHeader(http.StatusOK)

	sub := realtime.Default.Subscribe(realtime.MeetingTopic(chi.URLParam(r, "meetingID")))
	defer realtime.Default.Unsubscribe(sub)

	// Initial comment flushes headers and confirms the stream is open.
	if _, err := io.WriteString(w, ": connected\n\n"); err != nil {
		return
	}
	flusher.Flush()

	ticker := time.NewTicker(heartbeatInterval)
	defer ticker.Stop()
	ctx := r.Context()

	for {
		select {
		case <-ctx.Done(): // client disconnected
			return
		case <-ticker.C:
			if _, err := io.WriteString(w, ": heartbeat\n\n"); err != nil {
				return
			}
			flusher.Flush()
		case ev := <-sub.C:
			data, err := json.Marshal(ev)
			if err != nil {
				continue
			}
			if _, err := fmt.Fprintf(w, "data: %s\n\n", data); err != nil {
				return
			}
			flusher.Flush()
			// Reset the heartbeat clock: a real event already keeps the
			// connection warm, no need for an immediate redundant comment.
			ticker.Reset(heartbeatInterval)
		}
	}
}

// ---------------------------------------------------------------------------
// Webhook: POST /webhooks/recall  (PUBLIC)
// ---------------------------------------------------------------------------

// Reject Svix-signed webhooks whose timestamp is too far from now, bounding the
// replay window even after the dedup LRU is cleared by a restart (ports
// _RECALL_TIMESTAMP_TOLERANCE).
const recallTimestampTolerance = 300 // seconds

// replay-dedup LRU (ports the _SEEN_WEBHOOK_IDS / _is_replay machinery).
const (
	seenMaxSize    = 10000
	seenTTLSeconds = 600
)

type seenIDs struct {
	mu    sync.Mutex
	order []string
	at    map[string]int64
}

var recallSeen = &seenIDs{at: make(map[string]int64)}

// isReplay records msg_id and reports whether it was already seen within the TTL
// (ports _is_replay). Empty ids (legacy x-recall-signature events have none) are
// never treated as replays — those rely on the idempotent UPSERT downstream.
func (s *seenIDs) isReplay(msgID string) bool {
	if msgID == "" {
		return false
	}
	now := time.Now().Unix()
	s.mu.Lock()
	defer s.mu.Unlock()
	// Evict expired entries from the head.
	for len(s.order) > 0 {
		oldest := s.order[0]
		if now-s.at[oldest] > seenTTLSeconds {
			s.order = s.order[1:]
			delete(s.at, oldest)
		} else {
			break
		}
	}
	if _, ok := s.at[msgID]; ok {
		return true
	}
	if len(s.order) >= seenMaxSize {
		oldest := s.order[0]
		s.order = s.order[1:]
		delete(s.at, oldest)
	}
	s.order = append(s.order, msgID)
	s.at[msgID] = now
	return false
}

// recallSecretBytes decodes RECALL_WEBHOOK_SECRET for Svix HMAC verification: the
// dashboard secret is url-safe base64 (optionally `whsec_`-prefixed); fall back to
// the raw bytes if it isn't valid base64 (ports _secret_bytes).
func (s *Server) recallSecretBytes() []byte {
	raw := s.Cfg.RecallWebhookSecret
	raw = strings.TrimPrefix(raw, "whsec_")
	if pad := len(raw) % 4; pad != 0 {
		raw += strings.Repeat("=", 4-pad)
	}
	if b, err := base64.URLEncoding.DecodeString(raw); err == nil {
		return b
	}
	return []byte(s.Cfg.RecallWebhookSecret)
}

// verifySvix checks a Standard-Webhooks / Svix signature over `id.timestamp.body`
// (ports _verify_svix). The header is one or more space-separated "v1,<sig>" pairs.
func (s *Server) verifySvix(rawBody []byte, id, ts, sig string) bool {
	mac := hmac.New(sha256.New, s.recallSecretBytes())
	mac.Write([]byte(id + "." + ts + "."))
	mac.Write(rawBody)
	expected := base64.StdEncoding.EncodeToString(mac.Sum(nil))
	for _, part := range strings.Split(sig, " ") {
		_, got, found := strings.Cut(part, ",")
		if found && got != "" && hmac.Equal([]byte(expected), []byte(got)) {
			return true
		}
	}
	return false
}

// verifyRecallSignature ports _verify_recall_signature. Returns an HTTP status +
// detail to reject with, or (0, "") to accept. When the secret is empty we accept
// unsigned webhooks (dev). Svix headers take precedence (with a freshness check),
// else the legacy x-recall-signature hex HMAC, else reject.
func (s *Server) verifyRecallSignature(rawBody []byte, xRecallSig, svixID, svixTS, svixSig string) (int, string) {
	if s.Cfg.RecallWebhookSecret == "" {
		return 0, ""
	}
	if svixID != "" && svixTS != "" && svixSig != "" {
		ts, err := strconv.ParseInt(svixTS, 10, 64)
		if err != nil {
			return http.StatusUnauthorized, "Invalid Recall webhook timestamp"
		}
		if skew := time.Now().Unix() - ts; skew < 0 {
			skew = -skew
			if skew > recallTimestampTolerance {
				return http.StatusUnauthorized, "Recall webhook timestamp expired"
			}
		} else if skew > recallTimestampTolerance {
			return http.StatusUnauthorized, "Recall webhook timestamp expired"
		}
		if s.verifySvix(rawBody, svixID, svixTS, svixSig) {
			return 0, ""
		}
		return http.StatusUnauthorized, "Invalid Svix signature"
	}
	if xRecallSig != "" {
		mac := hmac.New(sha256.New, []byte(s.Cfg.RecallWebhookSecret))
		mac.Write(rawBody)
		expected := hex.EncodeToString(mac.Sum(nil))
		if hmac.Equal([]byte(expected), []byte(xRecallSig)) {
			return 0, ""
		}
		return http.StatusUnauthorized, "Invalid Recall signature"
	}
	return http.StatusUnauthorized, "Missing Recall signature header"
}

func ack(w http.ResponseWriter, v map[string]any) { writeJSON(w, http.StatusOK, v) }

// recallWebhook is the unified Recall.ai webhook handler. Within this AREA it
// verifies the signature, dedupes replays, and handles transcript.data /
// transcript.partial_data (map bot_id→meeting, UPSERT transcript_segments keyed
// on recall_segment_id, publish a transcript_segment event). All other event
// types are ACKed (handled:false) — the bot-lifecycle / participant / chat
// branches in the Python handler are out of this area's scope.
func (s *Server) recallWebhook(w http.ResponseWriter, r *http.Request) {
	rawBody, err := io.ReadAll(r.Body)
	if err != nil {
		writeError(w, http.StatusBadRequest, "Invalid body")
		return
	}

	// The dashboard uses Standard-Webhooks `webhook-*` headers; realtime
	// endpoints may use `svix-*`. Collapse both into one triple before verifying.
	xRecallSig := r.Header.Get("X-Recall-Signature")
	msgID := firstNonEmpty(r.Header.Get("Svix-Id"), r.Header.Get("Webhook-Id"))
	msgTS := firstNonEmpty(r.Header.Get("Svix-Timestamp"), r.Header.Get("Webhook-Timestamp"))
	msgSig := firstNonEmpty(r.Header.Get("Svix-Signature"), r.Header.Get("Webhook-Signature"))

	if code, detail := s.verifyRecallSignature(rawBody, xRecallSig, msgID, msgTS, msgSig); code != 0 {
		writeError(w, code, detail)
		return
	}

	// Reject replays of dashboard-signed webhooks (which carry a unique id).
	// Returning 200 stops Recall from retrying.
	if recallSeen.isReplay(msgID) {
		ack(w, map[string]any{"received": true, "handled": false, "reason": "replay"})
		return
	}

	var payload struct {
		Event string          `json:"event"`
		Data  json.RawMessage `json:"data"`
	}
	if err := json.Unmarshal(rawBody, &payload); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid JSON")
		return
	}

	if payload.Event == "transcript.data" || payload.Event == "transcript.partial_data" {
		s.handleRecallTranscript(w, r, payload.Event, payload.Data)
		return
	}
	// Other event types (transcript.*, bot.*, participant*, chat*, recording.* …)
	// are outside this area's scope — ACK without handling.
	ack(w, map[string]any{"received": true, "handled": false, "event": payload.Event})
}

// recallTranscriptData is the realtime_endpoints transcript payload shape (ports
// the `data.bot` / `data.data` branch of _handle_transcript). The legacy per-bot
// shape (data.bot_id / data.segment) is also accepted.
type recallTranscriptData struct {
	Bot struct {
		ID string `json:"id"`
	} `json:"bot"`
	BotID string `json:"bot_id"`
	Data  *struct {
		Participant struct {
			ID   any     `json:"id"`
			Name *string `json:"name"`
		} `json:"participant"`
		Words []struct {
			Text           string `json:"text"`
			StartTimestamp *struct {
				Relative *float64 `json:"relative"`
			} `json:"start_timestamp"`
			EndTimestamp *struct {
				Relative *float64 `json:"relative"`
			} `json:"end_timestamp"`
		} `json:"words"`
	} `json:"data"`
	Segment *struct {
		ID         string   `json:"id"`
		Speaker    *string  `json:"speaker"`
		Text       *string  `json:"text"`
		StartTime  *float64 `json:"start_time"`
		EndTime    *float64 `json:"end_time"`
		Confidence *float64 `json:"confidence"`
		Index      *int     `json:"index"`
	} `json:"segment"`
}

func (s *Server) handleRecallTranscript(w http.ResponseWriter, r *http.Request, event string, raw json.RawMessage) {
	isPartial := strings.HasSuffix(event, ".partial") || strings.HasSuffix(event, ".partial_data")

	var d recallTranscriptData
	if err := json.Unmarshal(raw, &d); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid JSON")
		return
	}
	botID := d.Bot.ID
	if botID == "" {
		botID = d.BotID
	}

	meetingID, err := store.MeetingIDForBot(r.Context(), s.DB, botID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "internal error")
		return
	}
	if meetingID == "" {
		ack(w, map[string]any{"received": true, "handled": false, "reason": "unknown_bot"})
		return
	}

	var row store.SegmentUpsert
	if d.Data != nil {
		words := d.Data.Words
		if len(words) == 0 {
			ack(w, map[string]any{"received": true, "handled": false, "reason": "empty_words"})
			return
		}
		parts := make([]string, 0, len(words))
		for _, wd := range words {
			if t := strings.TrimSpace(wd.Text); t != "" {
				parts = append(parts, t)
			}
		}
		text := strings.Join(parts, " ")
		var first, last float64
		if w0 := words[0].StartTimestamp; w0 != nil && w0.Relative != nil {
			first = *w0.Relative
		}
		last = first
		if wl := words[len(words)-1].EndTimestamp; wl != nil && wl.Relative != nil {
			last = *wl.Relative
		}
		// Realtime payload has no stable segment id; build a deterministic one so
		// partial→final upserts collapse in place (ports the f-string id).
		pid := "?"
		if d.Data.Participant.ID != nil {
			pid = fmt.Sprint(d.Data.Participant.ID)
		}
		segmentID := fmt.Sprintf("%s:%s:%.3f", botID, pid, first)
		name := d.Data.Participant.Name
		label := "Speaker"
		if name != nil && *name != "" {
			label = *name
		}
		row = store.SegmentUpsert{
			MeetingID: meetingID, RecallSegmentID: segmentID,
			SpeakerLabel: label, SpeakerName: name, Text: text,
			StartTime: first, EndTime: last, Confidence: nil,
			SegmentIndex: 0, IsPartial: isPartial,
		}
	} else {
		if d.Segment == nil || d.Segment.ID == "" {
			writeError(w, http.StatusBadRequest, "Segment missing id")
			return
		}
		label := "Speaker"
		if d.Segment.Speaker != nil && *d.Segment.Speaker != "" {
			label = *d.Segment.Speaker
		}
		row = store.SegmentUpsert{
			MeetingID: meetingID, RecallSegmentID: d.Segment.ID,
			SpeakerLabel: label, SpeakerName: nil, Text: derefStr(d.Segment.Text),
			StartTime: derefFloat(d.Segment.StartTime), EndTime: derefFloat(d.Segment.EndTime),
			Confidence: d.Segment.Confidence, SegmentIndex: derefInt(d.Segment.Index),
			IsPartial: isPartial,
		}
	}

	if err := store.UpsertTranscriptSegment(r.Context(), s.DB, row); err != nil {
		writeError(w, http.StatusInternalServerError, "internal error")
		return
	}

	// Broadcast to the in-process pub/sub so the SSE stream delivers the live
	// segment. The published payload matches the Python `row` dict keys.
	realtime.Default.PublishMeetingEvent(meetingID, "transcript_segment", map[string]any{
		"meeting_id":        row.MeetingID,
		"recall_segment_id": row.RecallSegmentID,
		"speaker_label":     row.SpeakerLabel,
		"speaker_name":      row.SpeakerName,
		"text":              row.Text,
		"start_time":        row.StartTime,
		"end_time":          row.EndTime,
		"confidence":        row.Confidence,
		"segment_index":     row.SegmentIndex,
		"is_partial":        row.IsPartial,
	})

	ack(w, map[string]any{"received": true, "handled": true, "is_partial": isPartial})
}

// ---- small helpers ---------------------------------------------------------

func firstNonEmpty(vals ...string) string {
	for _, v := range vals {
		if v != "" {
			return v
		}
	}
	return ""
}

func derefStr(p *string) string {
	if p == nil {
		return ""
	}
	return *p
}

func derefFloat(p *float64) float64 {
	if p == nil {
		return 0
	}
	return *p
}

func derefInt(p *int) int {
	if p == nil {
		return 0
	}
	return *p
}
