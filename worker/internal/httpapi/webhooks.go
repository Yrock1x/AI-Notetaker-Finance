package httpapi

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/integrations/inngest"
	"github.com/go-chi/chi/v5"
)

// webhooks.go ports app/api/v1/webhooks.py: the Zoom / Teams / Slack inbound
// webhooks. Each verifies its provider's HMAC signature (or clientState) against
// the RAW body before parsing untrusted JSON, handles the provider's
// challenge/validation handshake, then fires an Inngest event for real events.
// PUBLIC — the provider signature is the capability, so no requireAuth.

const webhookTimestampTolerance = 300 // seconds (5 min)

func (s *Server) inngest() *inngest.Sender { return inngest.New(s.Cfg.InngestEventKey) }

// replayCache is a bounded, TTL'd set of (provider,timestamp,signature) tuples to
// reject replays within the timestamp tolerance window (ports _is_replay).
type replayCache struct {
	mu   sync.Mutex
	seen map[string]time.Time
	max  int
	ttl  time.Duration
}

var webhookReplay = &replayCache{seen: map[string]time.Time{}, max: 10000, ttl: 2 * webhookTimestampTolerance * time.Second}

func (c *replayCache) isReplay(provider, signature, timestamp string) bool {
	if signature == "" || timestamp == "" {
		return false
	}
	key := provider + ":" + timestamp + ":" + signature
	c.mu.Lock()
	defer c.mu.Unlock()
	now := time.Now()
	for k, t := range c.seen {
		if now.Sub(t) > c.ttl {
			delete(c.seen, k)
		}
	}
	if _, ok := c.seen[key]; ok {
		return true
	}
	if len(c.seen) >= c.max {
		for k := range c.seen { // bound memory; evict one
			delete(c.seen, k)
			break
		}
	}
	c.seen[key] = now
	return false
}

func hmacSHA256Hex(secret, msg string) string {
	m := hmac.New(sha256.New, []byte(secret))
	m.Write([]byte(msg))
	return hex.EncodeToString(m.Sum(nil))
}

func absInt64(x int64) int64 {
	if x < 0 {
		return -x
	}
	return x
}

// RegisterWebhooks mounts the PUBLIC provider webhooks (wired outside requireAuth).
func (s *Server) RegisterWebhooks(r chi.Router) {
	r.Post("/webhooks/zoom", s.zoomWebhook)
	r.Post("/webhooks/teams", s.teamsWebhook)
	r.Post("/webhooks/slack/events", s.slackEvents)
	r.Post("/webhooks/slack/commands", s.slackCommands)
}

// ---- signature verification (returns 0,"" when valid) ----------------------

func (s *Server) verifyZoom(r *http.Request, rawBody []byte) (int, string) {
	ts := r.Header.Get("x-zm-request-timestamp")
	sig := r.Header.Get("x-zm-signature")
	if ts == "" || sig == "" {
		return http.StatusUnauthorized, "Missing Zoom signature headers"
	}
	tsi, err := strconv.ParseInt(ts, 10, 64)
	if err != nil {
		return http.StatusUnauthorized, "Invalid timestamp"
	}
	if absInt64(time.Now().Unix()-tsi) > webhookTimestampTolerance {
		return http.StatusUnauthorized, "Webhook timestamp expired"
	}
	expected := "v0=" + hmacSHA256Hex(s.Cfg.ZoomWebhookSecretToken, "v0:"+ts+":"+string(rawBody))
	if !hmac.Equal([]byte(expected), []byte(sig)) {
		return http.StatusUnauthorized, "Invalid Zoom signature"
	}
	if webhookReplay.isReplay("zoom", sig, ts) {
		return http.StatusConflict, "Replay detected"
	}
	return 0, ""
}

func (s *Server) verifySlack(r *http.Request, rawBody []byte) (int, string) {
	ts := r.Header.Get("X-Slack-Request-Timestamp")
	sig := r.Header.Get("X-Slack-Signature")
	if ts == "" || sig == "" {
		return http.StatusUnauthorized, "Missing Slack signature headers"
	}
	tsi, err := strconv.ParseInt(ts, 10, 64)
	if err != nil {
		return http.StatusUnauthorized, "Invalid timestamp"
	}
	if absInt64(time.Now().Unix()-tsi) > webhookTimestampTolerance {
		return http.StatusUnauthorized, "Webhook timestamp expired"
	}
	expected := "v0=" + hmacSHA256Hex(s.Cfg.SlackSigningSecret, "v0:"+ts+":"+string(rawBody))
	if !hmac.Equal([]byte(expected), []byte(sig)) {
		return http.StatusUnauthorized, "Invalid Slack signature"
	}
	if webhookReplay.isReplay("slack", sig, ts) {
		return http.StatusConflict, "Replay detected"
	}
	return 0, ""
}

// ---- handlers --------------------------------------------------------------

func (s *Server) zoomWebhook(w http.ResponseWriter, r *http.Request) {
	rawBody, _ := io.ReadAll(io.LimitReader(r.Body, 4<<20))
	if code, msg := s.verifyZoom(r, rawBody); code != 0 {
		writeError(w, code, msg)
		return
	}
	var body struct {
		Event   string `json:"event"`
		Payload struct {
			PlainToken string `json:"plainToken"`
			Object     struct {
				ID             json.Number `json:"id"`
				Topic          string      `json:"topic"`
				RecordingFiles []struct {
					RecordingType string `json:"recording_type"`
					FileType      string `json:"file_type"`
					DownloadURL   string `json:"download_url"`
				} `json:"recording_files"`
			} `json:"object"`
		} `json:"payload"`
	}
	_ = json.Unmarshal(rawBody, &body)

	if body.Event == "endpoint.url_validation" {
		writeJSON(w, http.StatusOK, map[string]string{
			"plainToken":     body.Payload.PlainToken,
			"encryptedToken": hmacSHA256Hex(s.Cfg.ZoomWebhookSecretToken, body.Payload.PlainToken),
		})
		return
	}
	if body.Event == "recording.completed" {
		downloadURL := ""
		for _, f := range body.Payload.Object.RecordingFiles {
			if f.RecordingType == "shared_screen_with_speaker_view" {
				downloadURL = f.DownloadURL
				break
			}
			if f.FileType == "MP4" {
				downloadURL = f.DownloadURL
			}
		}
		if downloadURL != "" {
			s.inngest().Send(r.Context(), "zoom/recording.completed", map[string]any{
				"zoom_meeting_id": body.Payload.Object.ID.String(),
				"download_url":    downloadURL,
				"topic":           body.Payload.Object.Topic,
			})
		}
	}
	writeJSON(w, http.StatusOK, map[string]any{"received": true})
}

func (s *Server) teamsWebhook(w http.ResponseWriter, r *http.Request) {
	// Subscription validation handshake — echo validationToken as plain text.
	if vt := r.URL.Query().Get("validationToken"); vt != "" {
		w.Header().Set("Content-Type", "text/plain")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(vt))
		return
	}
	rawBody, _ := io.ReadAll(io.LimitReader(r.Body, 4<<20))
	secret := s.Cfg.TeamsClientStateSecret()
	if secret == "" {
		writeError(w, http.StatusInternalServerError, "Teams webhook secret not configured")
		return
	}
	var body struct {
		Value []struct {
			ClientState string `json:"clientState"`
			Resource    string `json:"resource"`
			ChangeType  string `json:"changeType"`
			TenantID    string `json:"tenantId"`
		} `json:"value"`
	}
	_ = json.Unmarshal(rawBody, &body)

	for _, n := range body.Value {
		if !hmac.Equal([]byte(n.ClientState), []byte(secret)) {
			writeError(w, http.StatusUnauthorized, "Invalid Teams client state")
			return
		}
	}
	for _, n := range body.Value {
		if strings.Contains(n.Resource, "communications/callRecords") {
			id := extractCallRecordID(n.Resource)
			if id != "" {
				s.inngest().Send(r.Context(), "teams/call_record.created", map[string]any{
					"call_record_id": id, "tenant_id": n.TenantID,
				})
			}
		}
	}
	writeJSON(w, http.StatusOK, map[string]any{"received": true})
}

// extractCallRecordID pulls the id out of a Graph resource path like
// "communications/callRecords('<id>')" (ports the inline parse).
func extractCallRecordID(resource string) string {
	if i := strings.Index(resource, "('"); i >= 0 {
		if j := strings.Index(resource[i+2:], "')"); j >= 0 {
			return resource[i+2 : i+2+j]
		}
	}
	if i := strings.LastIndex(resource, "/"); i >= 0 {
		return resource[i+1:]
	}
	return ""
}

func (s *Server) slackEvents(w http.ResponseWriter, r *http.Request) {
	rawBody, _ := io.ReadAll(io.LimitReader(r.Body, 4<<20))
	if code, msg := s.verifySlack(r, rawBody); code != 0 {
		writeError(w, code, msg)
		return
	}
	var body struct {
		Type      string `json:"type"`
		Challenge string `json:"challenge"`
	}
	_ = json.Unmarshal(rawBody, &body)
	if body.Type == "url_verification" {
		writeJSON(w, http.StatusOK, map[string]string{"challenge": body.Challenge})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"received": true})
}

func (s *Server) slackCommands(w http.ResponseWriter, r *http.Request) {
	rawBody, _ := io.ReadAll(io.LimitReader(r.Body, 4<<20))
	if code, msg := s.verifySlack(r, rawBody); code != 0 {
		writeError(w, code, msg)
		return
	}
	form, _ := url.ParseQuery(string(rawBody))
	sub := "help"
	if fields := strings.Fields(form.Get("text")); len(fields) > 0 {
		sub = fields[0]
	}
	resp := func(text string) {
		writeJSON(w, http.StatusOK, map[string]string{"response_type": "ephemeral", "text": text})
	}
	switch sub {
	case "status":
		resp("Checking meeting processing status...")
	case "meetings":
		resp("Fetching recent meetings...")
	case "help":
		resp("*CogniSuite Commands:*\n• `/cognisuite status` — Show recent meeting processing status\n• `/cognisuite meetings` — List recent meetings\n• `/cognisuite help` — Show this help message")
	default:
		resp("Unknown command. Use `/cognisuite help` for usage.")
	}
}
