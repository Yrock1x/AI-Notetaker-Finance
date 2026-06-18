// Package graph is a thin Microsoft Graph client for Teams call records +
// change-notification subscriptions (ports app/integrations/teams/graph_client.py
// get_call_record / subscribe_to_call_records / renew_subscription).
package graph

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

const baseURL = "https://graph.microsoft.com/v1.0"

// Client wraps Graph for one access token's worth of calls.
type Client struct {
	HTTPClient *http.Client
}

func New() *Client { return &Client{HTTPClient: &http.Client{Timeout: 30 * time.Second}} }

// HTTPError carries a non-2xx Graph response.
type HTTPError struct {
	Status int
	Body   string
}

func (e *HTTPError) Error() string { return fmt.Sprintf("graph returned %d: %s", e.Status, e.Body) }

func (c *Client) do(ctx context.Context, method, url, accessToken string, body any) ([]byte, error) {
	var rdr io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			return nil, err
		}
		rdr = bytes.NewReader(b)
	}
	req, err := http.NewRequestWithContext(ctx, method, url, rdr)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+accessToken)
	req.Header.Set("Content-Type", "application/json")
	hc := c.HTTPClient
	if hc == nil {
		hc = &http.Client{Timeout: 30 * time.Second}
	}
	resp, err := hc.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	data, _ := io.ReadAll(io.LimitReader(resp.Body, 16<<20))
	if resp.StatusCode >= 400 {
		b := string(data)
		if len(b) > 500 {
			b = b[:500]
		}
		return nil, &HTTPError{Status: resp.StatusCode, Body: b}
	}
	return data, nil
}

// GetCallRecord fetches a Teams call record with sessions+segments expanded.
func (c *Client) GetCallRecord(ctx context.Context, accessToken, callRecordID string) (map[string]any, error) {
	url := baseURL + "/communications/callRecords/" + callRecordID + "?$expand=sessions($expand=segments)"
	data, err := c.do(ctx, http.MethodGet, url, accessToken, nil)
	if err != nil {
		return nil, err
	}
	var out map[string]any
	return out, json.Unmarshal(data, &out)
}

// Subscription is the Graph subscription response we persist.
type Subscription struct {
	ID                 string `json:"id"`
	ExpirationDateTime string `json:"expirationDateTime"`
}

// SubscribeCallRecords creates a change-notification subscription for
// communications/callRecords (ports subscribe_to_call_records). expirationMinutes
// defaults to 4230 (~2.9 days, the callRecords max).
func (c *Client) SubscribeCallRecords(ctx context.Context, accessToken, notificationURL, clientState string, expirationMinutes int) (*Subscription, error) {
	if expirationMinutes <= 0 {
		expirationMinutes = 4230
	}
	exp := time.Now().UTC().Add(time.Duration(expirationMinutes) * time.Minute).Format(time.RFC3339)
	payload := map[string]any{
		"changeType":         "created",
		"notificationUrl":    notificationURL,
		"resource":           "communications/callRecords",
		"expirationDateTime": exp,
		"clientState":        clientState,
	}
	data, err := c.do(ctx, http.MethodPost, baseURL+"/subscriptions", accessToken, payload)
	if err != nil {
		return nil, err
	}
	var s Subscription
	return &s, json.Unmarshal(data, &s)
}

// RenewSubscription extends a subscription's expirationDateTime (ports
// renew_subscription).
func (c *Client) RenewSubscription(ctx context.Context, accessToken, subscriptionID string, expirationMinutes int) (*Subscription, error) {
	if expirationMinutes <= 0 {
		expirationMinutes = 4230
	}
	exp := time.Now().UTC().Add(time.Duration(expirationMinutes) * time.Minute).Format(time.RFC3339)
	data, err := c.do(ctx, http.MethodPatch, baseURL+"/subscriptions/"+subscriptionID, accessToken,
		map[string]any{"expirationDateTime": exp})
	if err != nil {
		return nil, err
	}
	var s Subscription
	return &s, json.Unmarshal(data, &s)
}
