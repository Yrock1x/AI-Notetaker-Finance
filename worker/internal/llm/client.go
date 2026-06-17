package llm

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

const defaultBaseURL = "https://api.fireworks.ai/inference/v1"

const embedBatchSize = 64 // Fireworks embedding batch cap (matches Python)

// Usage mirrors the token counts in LLMResponse.usage.
type Usage struct {
	PromptTokens     int `json:"prompt_tokens"`
	CompletionTokens int `json:"completion_tokens"`
	TotalTokens      int `json:"total_tokens"`
}

// Response is the chat-completion result (ports LLMResponse minus raw_response).
type Response struct {
	Content string
	Model   string
	Usage   Usage
}

// CompleteOpts are optional generation params (defaults match Python).
type CompleteOpts struct {
	MaxTokens   int     // default 4096
	Temperature float64 // default 0.2
}

// Client is the task-aware Fireworks LLM client. Anthropic routing is gated off
// (PREMIUM_LLM_ENABLED) and not implemented — a task routed to anthropic while
// premium is off errors, exactly like the Python router.
type Client struct {
	apiKey   string
	baseURL  string
	sem      chan struct{} // global outbound-call cap
	embedSem chan struct{} // per-call embed-batch cap (4)
	http     *http.Client
}

// New builds a client. maxConcurrency<=0 defaults to 20 (FIREWORKS_MAX_CONCURRENCY).
func New(apiKey string, maxConcurrency int) *Client {
	if maxConcurrency <= 0 {
		maxConcurrency = 20
	}
	return &Client{
		apiKey:   apiKey,
		baseURL:  defaultBaseURL,
		sem:      make(chan struct{}, maxConcurrency),
		embedSem: make(chan struct{}, 4),
		http:     &http.Client{Timeout: 60 * time.Second},
	}
}

// WithBaseURL overrides the API base (used in tests).
func (c *Client) WithBaseURL(u string) *Client { c.baseURL = u; return c }

func isRetryable(status int, err error) bool {
	if err != nil {
		return true // network/timeout
	}
	return status == http.StatusTooManyRequests || status >= 500
}

// doWithRetry runs an HTTP POST with up to 3 attempts and exponential backoff
// (1,2,4s capped at 8) on 429/5xx/network — the global semaphore is held across
// the whole sequence (matches the Python provider).
func (c *Client) doWithRetry(ctx context.Context, path string, body any) ([]byte, error) {
	payload, err := json.Marshal(body)
	if err != nil {
		return nil, err
	}
	c.sem <- struct{}{}
	defer func() { <-c.sem }()

	var lastErr error
	backoff := time.Second
	for attempt := 0; attempt < 3; attempt++ {
		if attempt > 0 {
			select {
			case <-ctx.Done():
				return nil, ctx.Err()
			case <-time.After(backoff):
			}
			if backoff < 8*time.Second {
				backoff *= 2
			}
		}
		req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+path, bytes.NewReader(payload))
		if err != nil {
			return nil, err
		}
		req.Header.Set("Authorization", "Bearer "+c.apiKey)
		req.Header.Set("Content-Type", "application/json")
		resp, err := c.http.Do(req)
		if err != nil {
			lastErr = err
			continue
		}
		data, _ := io.ReadAll(resp.Body)
		resp.Body.Close()
		if resp.StatusCode >= 200 && resp.StatusCode < 300 {
			return data, nil
		}
		lastErr = fmt.Errorf("fireworks %s: status %d: %s", path, resp.StatusCode, truncate(data, 300))
		if !isRetryable(resp.StatusCode, nil) {
			return nil, lastErr
		}
	}
	return nil, lastErr
}

func truncate(b []byte, n int) string {
	if len(b) > n {
		return string(b[:n])
	}
	return string(b)
}

// Complete routes task→model and runs a Fireworks chat completion.
func (c *Client) Complete(ctx context.Context, task, systemPrompt, userPrompt string, opts CompleteOpts) (*Response, error) {
	provider, model, err := resolveModel(task)
	if err != nil {
		return nil, err
	}
	if provider == "anthropic" && !premiumEnabled() {
		return nil, fmt.Errorf("task %q routed to anthropic but PREMIUM_LLM_ENABLED is not true", task)
	}
	if provider != "fireworks" {
		return nil, fmt.Errorf("no provider registered for %q", provider)
	}
	if opts.MaxTokens == 0 {
		opts.MaxTokens = 4096
	}
	if opts.Temperature == 0 {
		opts.Temperature = 0.2
	}
	body := map[string]any{
		"model":       model,
		"max_tokens":  opts.MaxTokens,
		"temperature": opts.Temperature,
		"messages": []map[string]string{
			{"role": "system", "content": systemPrompt},
			{"role": "user", "content": userPrompt},
		},
	}
	data, err := c.doWithRetry(ctx, "/chat/completions", body)
	if err != nil {
		return nil, err
	}
	var parsed struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
		Usage Usage `json:"usage"`
	}
	if err := json.Unmarshal(data, &parsed); err != nil {
		return nil, err
	}
	content := ""
	if len(parsed.Choices) > 0 {
		content = parsed.Choices[0].Message.Content
	}
	return &Response{Content: content, Model: model, Usage: parsed.Usage}, nil
}

// Embed embeds a single text (768-dim).
func (c *Client) Embed(ctx context.Context, text string) ([]float32, error) {
	out, err := c.EmbedBatch(ctx, []string{text})
	if err != nil || len(out) == 0 {
		return nil, err
	}
	return out[0], nil
}

// EmbedBatch embeds texts in batches of 64, preserving order (ports
// FireworksEmbeddingProvider.embed_batch). Returns float32 vectors so they
// serialize identically to the stored sqlite-vec vectors.
func (c *Client) EmbedBatch(ctx context.Context, texts []string) ([][]float32, error) {
	if len(texts) == 0 {
		return nil, nil
	}
	_, model, err := resolveModel(TaskEmbedding)
	if err != nil {
		return nil, err
	}
	out := make([][]float32, len(texts))
	for start := 0; start < len(texts); start += embedBatchSize {
		end := start + embedBatchSize
		if end > len(texts) {
			end = len(texts)
		}
		batch := texts[start:end]
		c.embedSem <- struct{}{}
		data, err := c.doWithRetry(ctx, "/embeddings", map[string]any{"model": model, "input": batch})
		<-c.embedSem
		if err != nil {
			return nil, err
		}
		var parsed struct {
			Data []struct {
				Embedding []float32 `json:"embedding"`
			} `json:"data"`
		}
		if err := json.Unmarshal(data, &parsed); err != nil {
			return nil, err
		}
		if len(parsed.Data) != len(batch) {
			return nil, fmt.Errorf("fireworks embeddings: got %d vectors for %d inputs", len(parsed.Data), len(batch))
		}
		for i, row := range parsed.Data {
			out[start+i] = row.Embedding
		}
	}
	return out, nil
}
