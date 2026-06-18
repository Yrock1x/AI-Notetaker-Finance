// Package deepgram is a thin REST client for Deepgram speech-to-text plus the
// speaker-diarization post-processor. It ports app/integrations/deepgram
// (client.py + processor.py + config.py): the Python worker used the Deepgram
// Python SDK; here we call the documented REST endpoint directly
// (POST https://api.deepgram.com/v1/listen with the raw audio bytes), which has
// no SDK dependency and keeps the worker a single static binary.
package deepgram

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net/http"
	"net/url"
	"strconv"
	"time"
)

// TranscribeTimeout matches DEEPGRAM_TRANSCRIBE_TIMEOUT_SECONDS (30 min): covers
// a ~3-hour meeting at Deepgram's ~10x real-time without pinning a pipeline step
// forever.
const TranscribeTimeout = 30 * time.Minute

const listenURL = "https://api.deepgram.com/v1/listen"

// financialVocabulary mirrors FINANCIAL_VOCABULARY in
// app/integrations/deepgram/config.py — keyword boosting for IB/PE/VC terms.
var financialVocabulary = []string{
	"EBITDA", "EBIT", "LBO", "DCF", "IRR", "MOIC", "CoC",
	"revenue", "gross margin", "net income", "free cash flow",
	"enterprise value", "equity value", "debt-to-equity",
	"leverage ratio", "working capital", "capex", "opex",
	"ARR", "MRR", "churn rate", "CAC", "LTV", "NRR",
	"quality of earnings", "QoE", "add-back", "normalization",
	"management presentation", "CIM", "teaser", "LOI",
	"term sheet", "due diligence", "data room", "SPA",
	"representations and warranties", "indemnification",
	"pro forma", "run rate", "synergies", "accretion", "dilution",
}

// Segment is one speaker-attributed transcript span (ports the dicts returned by
// DiarizationProcessor.process_response).
type Segment struct {
	SpeakerLabel string
	SpeakerName  string
	Text         string
	StartTime    float64
	EndTime      float64
	Confidence   float64
	SegmentIndex int
}

// Client holds the API key. A zero-value APIKey means transcription is not
// configured (the caller should 500 before constructing a Client, mirroring the
// Python "DEEPGRAM_API_KEY is not configured" guard).
type Client struct {
	APIKey     string
	HTTPClient *http.Client
}

// New builds a client with the transcription timeout applied to its HTTP client.
func New(apiKey string) *Client {
	return &Client{APIKey: apiKey, HTTPClient: &http.Client{Timeout: TranscribeTimeout}}
}

// options reproduces DEEPGRAM_CONFIG as listen query params. nova-2 keyword
// boosting uses the repeatable `keywords` param.
func (c *Client) options() url.Values {
	q := url.Values{}
	q.Set("model", "nova-2")
	q.Set("language", "en")
	q.Set("smart_format", "true")
	q.Set("diarize", "true")
	q.Set("punctuate", "true")
	q.Set("paragraphs", "true")
	q.Set("utterances", "true")
	for _, kw := range financialVocabulary {
		q.Add("keywords", kw)
	}
	return q
}

// Transcribe POSTs the raw audio to Deepgram and returns the full JSON response
// (stored verbatim in transcripts.deepgram_response) plus the diarized segments.
// mimetype is sent as Content-Type (ports transcribe_bytes).
func (c *Client) Transcribe(ctx context.Context, audio []byte, mimetype string) (raw []byte, segments []Segment, err error) {
	ctx, cancel := context.WithTimeout(ctx, TranscribeTimeout)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, http.MethodPost,
		listenURL+"?"+c.options().Encode(), bytes.NewReader(audio))
	if err != nil {
		return nil, nil, err
	}
	req.Header.Set("Authorization", "Token "+c.APIKey)
	req.Header.Set("Content-Type", mimetype)

	hc := c.HTTPClient
	if hc == nil {
		hc = &http.Client{Timeout: TranscribeTimeout}
	}
	resp, err := hc.Do(req)
	if err != nil {
		return nil, nil, err
	}
	defer resp.Body.Close()
	raw, err = io.ReadAll(resp.Body)
	if err != nil {
		return nil, nil, err
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, nil, fmt.Errorf("deepgram returned %d: %s", resp.StatusCode, truncate(raw, 300))
	}

	segments, err = ProcessResponse(raw)
	if err != nil {
		return nil, nil, err
	}
	return raw, segments, nil
}

// dgWord is the subset of a Deepgram word object we read.
type dgWord struct {
	Word           string  `json:"word"`
	PunctuatedWord string  `json:"punctuated_word"`
	Start          float64 `json:"start"`
	End            float64 `json:"end"`
	Confidence     float64 `json:"confidence"`
	Speaker        *int    `json:"speaker"`
}

type dgResponse struct {
	Results struct {
		Channels []struct {
			Alternatives []struct {
				Words []dgWord `json:"words"`
			} `json:"alternatives"`
		} `json:"channels"`
	} `json:"results"`
}

// ProcessResponse parses a Deepgram response into speaker-attributed segments by
// grouping consecutive words that share the same `speaker` value (ports
// DiarizationProcessor.process_response + _build_segment). Exposed (and tested)
// independently of the network call.
func ProcessResponse(raw []byte) ([]Segment, error) {
	var r dgResponse
	if err := json.Unmarshal(raw, &r); err != nil {
		return nil, fmt.Errorf("decode deepgram response: %w", err)
	}
	if len(r.Results.Channels) == 0 || len(r.Results.Channels[0].Alternatives) == 0 {
		return []Segment{}, nil
	}
	words := r.Results.Channels[0].Alternatives[0].Words
	if len(words) == 0 {
		return []Segment{}, nil
	}

	var segments []Segment
	var current []dgWord
	var currentSpeaker *int
	sameSpeaker := func(a, b *int) bool {
		if a == nil || b == nil {
			return a == b
		}
		return *a == *b
	}

	for i := range words {
		sp := words[i].Speaker
		if !sameSpeaker(sp, currentSpeaker) && len(current) > 0 {
			segments = append(segments, buildSegment(current, len(segments)))
			current = nil
		}
		currentSpeaker = sp
		current = append(current, words[i])
	}
	if len(current) > 0 {
		segments = append(segments, buildSegment(current, len(segments)))
	}
	return segments, nil
}

func buildSegment(words []dgWord, index int) Segment {
	speakerID := 0
	if words[0].Speaker != nil {
		speakerID = *words[0].Speaker
	}
	label := "Speaker " + strconv.Itoa(speakerID)

	var buf bytes.Buffer
	var confSum float64
	for i := range words {
		if i > 0 {
			buf.WriteByte(' ')
		}
		w := words[i].PunctuatedWord
		if w == "" {
			w = words[i].Word
		}
		buf.WriteString(w)
		confSum += words[i].Confidence
	}
	avg := 0.0
	if len(words) > 0 {
		avg = confSum / float64(len(words))
	}

	return Segment{
		SpeakerLabel: label,
		SpeakerName:  label,
		Text:         buf.String(),
		StartTime:    words[0].Start,
		EndTime:      words[len(words)-1].End,
		Confidence:   round4(avg),
		SegmentIndex: index,
	}
}

// round4 matches Python round(x, 4).
func round4(x float64) float64 { return math.Round(x*1e4) / 1e4 }

func truncate(b []byte, n int) string {
	if len(b) <= n {
		return string(b)
	}
	return string(b[:n])
}
