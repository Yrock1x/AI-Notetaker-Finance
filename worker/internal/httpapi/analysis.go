package httpapi

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/llm"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/model"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/store"
	"github.com/go-chi/chi/v5"
)

// analysisJSON is the wire shape (matches AnalysisResponse in
// app/schemas/analysis.py). structured_output is the parsed JSON object (or null);
// created_at / updated_at are the stored ISO-8601 strings, round-tripped verbatim.
type analysisJSON struct {
	ID               string   `json:"id"`
	MeetingID        string   `json:"meeting_id"`
	CallType         string   `json:"call_type"`
	StructuredOutput any      `json:"structured_output"`
	ModelUsed        string   `json:"model_used"`
	PromptVersion    string   `json:"prompt_version"`
	GroundingScore   *float64 `json:"grounding_score"`
	Status           string   `json:"status"`
	ErrorMessage     *string  `json:"error_message"`
	RequestedBy      *string  `json:"requested_by"`
	Version          int      `json:"version"`
	CreatedAt        string   `json:"created_at"`
	UpdatedAt        string   `json:"updated_at"`
}

func toAnalysisJSON(a *model.Analysis) analysisJSON {
	var so any
	if len(a.StructuredOutput) > 0 {
		_ = json.Unmarshal(a.StructuredOutput, &so)
	}
	return analysisJSON{
		ID: a.ID, MeetingID: a.MeetingID, CallType: a.CallType, StructuredOutput: so,
		ModelUsed: a.ModelUsed, PromptVersion: a.PromptVersion, GroundingScore: a.GroundingScore,
		Status: a.Status, ErrorMessage: a.ErrorMessage, RequestedBy: a.RequestedBy,
		Version: a.Version, CreatedAt: a.CreatedAt, UpdatedAt: a.UpdatedAt,
	}
}

// RegisterAnalysis mounts the meeting-analysis routes (all auth-required). Flat
// chi patterns under the shared /meetings/{meetingID}/... prefix so other
// resources can register sibling routes. The orchestrator wires this into the
// authed store group in server.go (alongside RegisterDeals/RegisterMeetings/...).
func (s *Server) RegisterAnalysis(r chi.Router) {
	r.Get("/meetings/{meetingID}/analyses", s.listMeetingAnalyses)
	r.Post("/meetings/{meetingID}/analyses", s.runMeetingAnalysis)
	r.Get("/meetings/{meetingID}/analyses/latest", s.getLatestMeetingAnalysis)
	r.Get("/meetings/{meetingID}/analyses/{analysisID}", s.getMeetingAnalysis)
	r.Post("/meetings/{meetingID}/analyses/{analysisID}/rerun", s.rerunMeetingAnalysis)
}

// GET /api/v1/meetings/{meetingID}/analyses
func (s *Server) listMeetingAnalyses(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	meetingID := chi.URLParam(r, "meetingID")
	if _, err := store.RequireMeetingOrg(r.Context(), s.DB, p, meetingID); storeError(w, err) {
		return
	}
	rows, err := store.ListAnalyses(r.Context(), s.DB, p, meetingID)
	if storeError(w, err) {
		return
	}
	out := make([]analysisJSON, 0, len(rows))
	for i := range rows {
		out = append(out, toAnalysisJSON(&rows[i]))
	}
	writeJSON(w, http.StatusOK, out)
}

// GET /api/v1/meetings/{meetingID}/analyses/latest
func (s *Server) getLatestMeetingAnalysis(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	meetingID := chi.URLParam(r, "meetingID")
	if _, err := store.RequireMeetingOrg(r.Context(), s.DB, p, meetingID); storeError(w, err) {
		return
	}
	rows, err := store.ListAnalyses(r.Context(), s.DB, p, meetingID)
	if storeError(w, err) {
		return
	}
	if len(rows) == 0 {
		writeError(w, http.StatusNotFound, "No analyses found")
		return
	}
	writeJSON(w, http.StatusOK, toAnalysisJSON(&rows[0]))
}

// GET /api/v1/meetings/{meetingID}/analyses/{analysisID}
func (s *Server) getMeetingAnalysis(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	meetingID := chi.URLParam(r, "meetingID")
	if _, err := store.RequireMeetingOrg(r.Context(), s.DB, p, meetingID); storeError(w, err) {
		return
	}
	a, err := store.GetAnalysis(r.Context(), s.DB, p, chi.URLParam(r, "analysisID"))
	if storeError(w, err) {
		return
	}
	if a.MeetingID != meetingID {
		writeError(w, http.StatusNotFound, "Analysis not in meeting")
		return
	}
	writeJSON(w, http.StatusOK, toAnalysisJSON(a))
}

type analysisRequest struct {
	CallType string `json:"call_type"`
}

// POST /api/v1/meetings/{meetingID}/analyses — runs synchronously and returns
// the resulting row with 202 (ports run_analysis). The org is derived from the
// meeting (never the client); the body's call_type selects the prompt.
func (s *Server) runMeetingAnalysis(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	u := authUserFromCtx(r.Context())
	meetingID := chi.URLParam(r, "meetingID")
	orgID, err := store.RequireMeetingOrg(r.Context(), s.DB, p, meetingID)
	if storeError(w, err) {
		return
	}

	var body analysisRequest
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeError(w, http.StatusUnprocessableEntity, "Invalid request body")
		return
	}
	callType := body.CallType
	if callType == "" {
		callType = "general"
	}

	var requestedBy *string
	if u != nil && u.ID != "" {
		requestedBy = &u.ID
	}

	a, err := s.runAnalysis(r.Context(), orgID, meetingID, callType, requestedBy)
	if err != nil {
		s.writeAnalysisError(w, err)
		return
	}
	writeJSON(w, http.StatusAccepted, toAnalysisJSON(a))
}

// POST /api/v1/meetings/{meetingID}/analyses/{analysisID}/rerun — re-runs an
// existing analysis with the same call_type and returns the new row with 201
// (ports rerun_analysis). The original is confirmed to belong to this org-scoped
// meeting BEFORE the billed LLM rerun.
func (s *Server) rerunMeetingAnalysis(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	meetingID := chi.URLParam(r, "meetingID")
	orgID, err := store.RequireMeetingOrg(r.Context(), s.DB, p, meetingID)
	if storeError(w, err) {
		return
	}
	original, err := store.GetAnalysis(r.Context(), s.DB, p, chi.URLParam(r, "analysisID"))
	if storeError(w, err) {
		return
	}
	if original.MeetingID != meetingID {
		writeError(w, http.StatusNotFound, "Analysis not in meeting")
		return
	}

	a, err := s.runAnalysis(r.Context(), orgID, original.MeetingID, original.CallType, original.RequestedBy)
	if err != nil {
		s.writeAnalysisError(w, err)
		return
	}
	writeJSON(w, http.StatusCreated, toAnalysisJSON(a))
}

// ---- service core ----------------------------------------------------------

func (s *Server) writeAnalysisError(w http.ResponseWriter, err error) {
	// An LLM provider failure is an upstream/gateway error (502); any other
	// run failure (unknown call_type, transcript/DB error) re-raises as a 500,
	// matching the Python service (bare raise → FastAPI 500). In both cases the
	// analyses row was already fail-stamped inside runAnalysis.
	if isLLMError(err) {
		writeError(w, http.StatusBadGateway, "Analysis provider unavailable")
		return
	}
	writeError(w, http.StatusInternalServerError, "Analysis failed")
}

// analysisError is a plain run-failure (e.g. unknown call_type) that, like the
// Python service's bare re-raise, surfaces to the client as a 500.
type analysisError struct{ msg string }

func (e *analysisError) Error() string { return e.msg }

// llmErr marks errors that originate from the LLM provider call so the handler
// can map them to 502 (everything else maps to 500).
type llmErr struct{ err error }

func (e *llmErr) Error() string { return e.err.Error() }
func (e *llmErr) Unwrap() error { return e.err }

func isLLMError(err error) bool {
	_, ok := err.(*llmErr)
	return ok
}

// runAnalysis ports AnalysisService.run_analysis: pick the next version, insert a
// "running" row, then (inside the equivalent of the Python try/except) fetch the
// transcript, render the call-type prompt, call the LLM, parse the structured
// output, and stamp the result onto the row. ANY failure after the row exists —
// including an unknown call_type — fail-stamps the row (a separate UPDATE that
// survives, mirroring the Python commit-on-failure) and returns the error.
func (s *Server) runAnalysis(ctx context.Context, orgID, meetingID, callType string, requestedBy *string) (*model.Analysis, error) {
	// prompt_version defaults to "v1" on the initial row (matches the Python
	// Analysis(prompt_version="v1") before the real template version is known).
	promptVersion := "v1"
	if pr, ok := analysisPrompts[callType]; ok {
		promptVersion = pr.version
	}

	version, err := store.NextAnalysisVersion(ctx, s.DB, meetingID, callType)
	if err != nil {
		return nil, err
	}
	row, err := store.InsertRunningAnalysis(ctx, s.DB, store.AnalysisInsert{
		OrgID: orgID, MeetingID: meetingID, CallType: callType,
		PromptVersion: promptVersion, Version: version, RequestedBy: requestedBy,
	})
	if err != nil {
		return nil, err
	}

	result, runErr := s.executeAnalysis(ctx, row.ID, meetingID, callType)
	if runErr != nil {
		// Fail-stamp so the row doesn't stay stuck in "running" (ports the
		// except branch's committed status="failed" + error_message).
		_ = store.FailAnalysis(ctx, s.DB, row.ID, runErr.Error())
		return nil, runErr
	}
	return result, nil
}

func (s *Server) executeAnalysis(ctx context.Context, analysisID, meetingID, callType string) (*model.Analysis, error) {
	prompt, ok := analysisPrompts[callType]
	if !ok {
		// Mirrors _load_prompt raising ValueError("Unknown call type: ...")
		// inside run_analysis's try block.
		return nil, &analysisError{msg: "Unknown call type: " + callType}
	}
	if s.LLM == nil {
		return nil, &analysisError{msg: "LLM router is not configured"}
	}

	transcript, err := store.FetchTranscriptText(ctx, s.DB, meetingID)
	if err != nil {
		return nil, err
	}

	userPrompt := strings.ReplaceAll(prompt.user, "{transcript}", transcript)
	if callType == "summarization" {
		dealName, err := store.MeetingDealName(ctx, s.DB, meetingID)
		if err != nil {
			return nil, err
		}
		userPrompt = strings.ReplaceAll(userPrompt, "{deal_name}", dealName)
		userPrompt = strings.ReplaceAll(userPrompt, "{meeting_type}", callType)
	}

	task := llm.TaskICMemo
	if callType == "summarization" {
		task = llm.TaskSummarization
	}

	resp, err := s.LLM.Complete(ctx, task, prompt.system, userPrompt, llm.CompleteOpts{
		// Fireworks rejects max_tokens > 4096 without stream=true; 4096 is plenty
		// for an IC memo / summary (matches the Python service).
		MaxTokens:   4096,
		Temperature: 0.0,
	})
	if err != nil {
		// Tag provider failures so the handler maps them to 502.
		return nil, &llmErr{err: err}
	}

	parsed, parseFailed := parseLLMOutput(resp.Content)
	status := "completed"
	if parseFailed {
		status = "partial"
	}
	return store.CompleteAnalysis(ctx, s.DB, analysisID, parsed, resp.Model, prompt.version, status)
}

// parseLLMOutput strips a leading/trailing ```json fence (ports
// AnalysisService._parse_llm_output) and returns the JSON bytes to store. On a
// JSON decode error it returns {"raw_output": <original>, "parse_error": true}
// and reports parseFailed=true so the caller marks the row "partial".
func parseLLMOutput(content string) (jsonBytes []byte, parseFailed bool) {
	text := strings.TrimSpace(content)
	if strings.HasPrefix(text, "```") {
		var kept []string
		for _, ln := range strings.Split(text, "\n") {
			if strings.HasPrefix(strings.TrimSpace(ln), "```") {
				continue
			}
			kept = append(kept, ln)
		}
		text = strings.TrimSpace(strings.Join(kept, "\n"))
	}
	var probe any
	if err := json.Unmarshal([]byte(text), &probe); err != nil {
		fallback, _ := json.Marshal(map[string]any{"raw_output": content, "parse_error": true})
		return fallback, true
	}
	// Re-marshal the parsed value so what we store is canonical JSON bytes
	// (the fence-stripped text already validated).
	out, err := json.Marshal(probe)
	if err != nil {
		fallback, _ := json.Marshal(map[string]any{"raw_output": content, "parse_error": true})
		return fallback, true
	}
	return out, false
}
