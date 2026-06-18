// Package recall is a thin client for the Recall.ai bot REST API (ports
// app/integrations/recall/client.py). An empty API key makes every call a
// no-op/error at the handler layer (the handlers guard on the key first).
package recall

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

const defaultRegion = "us-west-2"

// Client wraps the Recall REST API for one region.
type Client struct {
	APIKey     string
	BaseURL    string
	HTTPClient *http.Client
}

// New builds a client for the given region (default us-west-2).
func New(apiKey, region string) *Client {
	if region == "" {
		region = defaultRegion
	}
	return &Client{
		APIKey:     apiKey,
		BaseURL:    fmt.Sprintf("https://%s.recall.ai/api/v1", region),
		HTTPClient: &http.Client{Timeout: 30 * time.Second},
	}
}

func (c *Client) do(ctx context.Context, method, path string, body any) ([]byte, int, error) {
	var rdr io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			return nil, 0, err
		}
		rdr = bytes.NewReader(b)
	}
	req, err := http.NewRequestWithContext(ctx, method, c.BaseURL+path, rdr)
	if err != nil {
		return nil, 0, err
	}
	req.Header.Set("Authorization", "Token "+c.APIKey)
	req.Header.Set("Content-Type", "application/json")
	hc := c.HTTPClient
	if hc == nil {
		hc = &http.Client{Timeout: 30 * time.Second}
	}
	resp, err := hc.Do(req)
	if err != nil {
		return nil, 0, err
	}
	defer resp.Body.Close()
	data, _ := io.ReadAll(io.LimitReader(resp.Body, 16<<20))
	return data, resp.StatusCode, nil
}

// HTTPError carries a non-2xx Recall response.
type HTTPError struct {
	Status int
	Body   string
}

func (e *HTTPError) Error() string {
	return fmt.Sprintf("recall returned %d: %s", e.Status, e.Body)
}

// CreateBotConfig is the bot-create payload (recording_config + metadata are
// passed verbatim to Recall, like the Python client).
type CreateBotConfig struct {
	MeetingURL      string         `json:"meeting_url"`
	BotName         string         `json:"bot_name"`
	RecordingConfig map[string]any `json:"recording_config,omitempty"`
	Metadata        map[string]any `json:"metadata,omitempty"`
}

// CreateBot creates a bot that joins the meeting. Returns the raw bot JSON.
func (c *Client) CreateBot(ctx context.Context, cfg CreateBotConfig) (map[string]any, error) {
	data, status, err := c.do(ctx, http.MethodPost, "/bot", cfg)
	if err != nil {
		return nil, err
	}
	if status >= 400 {
		return nil, &HTTPError{Status: status, Body: truncate(data, 500)}
	}
	var out map[string]any
	if err := json.Unmarshal(data, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// LeaveBot tells Recall to have the bot leave the call (404 is tolerated).
func (c *Client) LeaveBot(ctx context.Context, botID string) error {
	data, status, err := c.do(ctx, http.MethodPost, "/bot/"+botID+"/leave_call", nil)
	if err != nil {
		return err
	}
	if status >= 400 && status != 404 {
		return &HTTPError{Status: status, Body: truncate(data, 500)}
	}
	return nil
}

// GetBot returns bot status + recordings (raw JSON).
func (c *Client) GetBot(ctx context.Context, botID string) (map[string]any, error) {
	data, status, err := c.do(ctx, http.MethodGet, "/bot/"+botID, nil)
	if err != nil {
		return nil, err
	}
	if status >= 400 {
		return nil, &HTTPError{Status: status, Body: truncate(data, 500)}
	}
	var out map[string]any
	if err := json.Unmarshal(data, &out); err != nil {
		return nil, err
	}
	return out, nil
}

func truncate(b []byte, n int) string {
	if len(b) <= n {
		return string(b)
	}
	return string(b[:n])
}
