package llm

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strconv"
	"sync/atomic"
	"testing"
)

func TestComplete(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/chat/completions" {
			t.Errorf("unexpected path %s", r.URL.Path)
		}
		if r.Header.Get("Authorization") != "Bearer key123" {
			t.Errorf("missing auth header")
		}
		_, _ = w.Write([]byte(`{"choices":[{"message":{"content":"the answer"}}],"usage":{"prompt_tokens":3,"completion_tokens":2,"total_tokens":5}}`))
	}))
	defer srv.Close()

	c := New("key123", 5).WithBaseURL(srv.URL)
	resp, err := c.Complete(context.Background(), TaskGeneral, "sys", "user", CompleteOpts{})
	if err != nil {
		t.Fatalf("complete: %v", err)
	}
	if resp.Content != "the answer" || resp.Usage.TotalTokens != 5 {
		t.Fatalf("resp=%+v", resp)
	}
	if resp.Model != "accounts/fireworks/models/glm-5p1" {
		t.Fatalf("model=%s", resp.Model)
	}
}

func TestCompleteRetriesOn500(t *testing.T) {
	var calls int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		if atomic.AddInt32(&calls, 1) == 1 {
			w.WriteHeader(500)
			return
		}
		_, _ = w.Write([]byte(`{"choices":[{"message":{"content":"ok"}}],"usage":{}}`))
	}))
	defer srv.Close()

	c := New("k", 5).WithBaseURL(srv.URL)
	resp, err := c.Complete(context.Background(), TaskGeneral, "s", "u", CompleteOpts{})
	if err != nil {
		t.Fatalf("complete (with retry): %v", err)
	}
	if resp.Content != "ok" || atomic.LoadInt32(&calls) != 2 {
		t.Fatalf("calls=%d content=%q", calls, resp.Content)
	}
}

func TestEmbedBatchOrderAcrossBatches(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var body struct {
			Input []string `json:"input"`
		}
		_ = json.NewDecoder(r.Body).Decode(&body)
		if len(body.Input) > embedBatchSize {
			t.Errorf("batch too large: %d", len(body.Input))
		}
		// echo each input (a stringified index) as the embedding's first value
		out := struct {
			Data []map[string]any `json:"data"`
		}{}
		for _, s := range body.Input {
			f, _ := strconv.ParseFloat(s, 32)
			out.Data = append(out.Data, map[string]any{"embedding": []float32{float32(f), 9}})
		}
		_ = json.NewEncoder(w).Encode(out)
	}))
	defer srv.Close()

	c := New("k", 5).WithBaseURL(srv.URL)
	n := 130 // 3 batches: 64 + 64 + 2
	texts := make([]string, n)
	for i := range texts {
		texts[i] = fmt.Sprintf("%d", i)
	}
	vecs, err := c.EmbedBatch(context.Background(), texts)
	if err != nil {
		t.Fatalf("embed batch: %v", err)
	}
	if len(vecs) != n {
		t.Fatalf("got %d vectors, want %d", len(vecs), n)
	}
	for i, v := range vecs {
		if len(v) != 2 || int(v[0]) != i {
			t.Fatalf("vec[%d]=%v, want first=%d (order preserved across batches)", i, v, i)
		}
	}
}

func TestAnthropicWithoutPremiumErrors(t *testing.T) {
	t.Setenv("LLM_MODEL_FOR_GENERAL", "anthropic:claude-sonnet-4-6")
	t.Setenv("PREMIUM_LLM_ENABLED", "false")
	c := New("k", 5)
	if _, err := c.Complete(context.Background(), TaskGeneral, "s", "u", CompleteOpts{}); err == nil {
		t.Fatalf("expected error routing to anthropic with premium off")
	}
}
