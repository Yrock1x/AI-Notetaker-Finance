// Package inngest fires events into Inngest's ingestion API (a plain JSON POST
// to https://inn.gs/e/{event_key}) — ports app/integrations/inngest.py. The
// worker fires events when a provider webhook arrives or a bot finishes; the
// Inngest functions (TypeScript on Vercel) orchestrate the pipeline from there.
package inngest

import (
	"bytes"
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"time"
)

const ingestBaseURL = "https://inn.gs/e"

// Sender posts events. A zero EventKey makes Send a logged no-op (matching the
// Python "no key -> drop" behaviour) so webhook handlers can still ack.
type Sender struct {
	EventKey   string
	HTTPClient *http.Client
}

// New builds a Sender with a 5s timeout (webhook handlers must ack quickly).
func New(eventKey string) *Sender {
	return &Sender{EventKey: eventKey, HTTPClient: &http.Client{Timeout: 5 * time.Second}}
}

// Send fires one event. Failures are logged, never returned as fatal — the
// caller (a webhook handler) should still 200 the provider so it doesn't retry
// forever; Inngest has its own durability for events that do land.
func (s *Sender) Send(ctx context.Context, name string, data map[string]any) {
	if s.EventKey == "" {
		slog.Warn("inngest event dropped: no key", "event", name)
		return
	}
	payload, err := json.Marshal(map[string]any{"name": name, "data": data})
	if err != nil {
		slog.Error("inngest event marshal failed", "event", name, "err", err)
		return
	}
	hc := s.HTTPClient
	if hc == nil {
		hc = &http.Client{Timeout: 5 * time.Second}
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, ingestBaseURL+"/"+s.EventKey, bytes.NewReader(payload))
	if err != nil {
		slog.Error("inngest event request failed", "event", name, "err", err)
		return
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := hc.Do(req)
	if err != nil {
		slog.Error("inngest event send error", "event", name, "err", err)
		return
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		slog.Error("inngest event send failed", "event", name, "status", resp.StatusCode)
		return
	}
	slog.Info("inngest event sent", "event", name)
}
