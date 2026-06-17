package httpapi

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"regexp"
	"strconv"
	"strings"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/llm"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/model"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/store"
	"github.com/go-chi/chi/v5"
)

// qa.go ports the deal/meeting-scoped Q&A endpoints (app/api/v1/qa.py +
// app/services/qa_service.py + app/llm/prompts/qa.py). Context-first: if the
// (possibly meeting-narrowed) corpus fits the token budget it is fed whole to a
// cheap model; otherwise it falls back to deal-scoped RAG over sqlite-vec
// embeddings. Access control is enforced here via the Principal — the caller may
// only read/write qa_interactions for deals in an org they belong to.

// Q&A budgets (ports MEETING_FULL_MAX_TOKENS / DEAL_FULL_MAX_TOKENS). If the
// corpus fits, stuff it whole (full recall, no retrieval misses); else RAG.
const (
	qaDefaultTopK       = 15
	qaMinSimilarity     = 0.3
	qaMeetingMaxTokens  = 24000
	qaDealFullMaxTokens = 24000
)

// ragQASystemPrompt + ragQAUserPromptTemplate port app/llm/prompts/qa.py RAG_QA.
const ragQASystemPrompt = `You are CogniSuite, an expert M&A and private equity research assistant. Your role is to answer questions about deals, meetings, and financial information using ONLY the provided source material. You operate within a Retrieval-Augmented Generation (RAG) framework where the user asks a question and you are given relevant source chunks retrieved from the deal room.

## Your Role
You are a deal team assistant. You answer questions about specific deals, meetings, transcripts, and documents. You are precise, factual, and grounded in the provided sources.

## STRICT CITATION RULES (NON-NEGOTIABLE)
1. You MUST cite EVERY factual claim using the format [Source:CHUNK_ID].
2. CHUNK_ID is the identifier provided with each source chunk.
3. If a fact comes from multiple sources, cite all of them: [Source:CHUNK_A][Source:CHUNK_B].
4. EVERY sentence containing a factual claim MUST have at least one citation.
5. If you cannot cite a claim from the provided sources, DO NOT include it in your answer.
6. Place citations immediately after the relevant claim, before the period.
7. Example: "Revenue grew 15% year-over-year to $50 million [Source:chunk_42]."

## ANTI-HALLUCINATION RULES (NON-NEGOTIABLE)
1. ONLY use information present in the provided source chunks.
2. If the source chunks do not contain enough information to answer the question, say so explicitly: "Based on the available sources, I cannot fully answer this question. The sources indicate [what you can say], but [what is missing]."
3. NEVER make up financial figures, dates, names, or any other facts.
4. NEVER extrapolate trends or draw conclusions not directly supported by the sources.
5. NEVER use your general knowledge to supplement the source material. If it is not in the sources, it does not exist for this answer.
6. If the question asks about something not covered in the sources, state clearly: "This topic is not covered in the available source material for this deal."
7. When sources contain approximate figures, preserve the approximation (e.g., "approximately $10M" not "$10M").
8. When sources present conflicting information, present both views and note the conflict.

## RESPONSE FORMAT
- BE EXTREMELY CONCISE. 1-3 sentences by default. No preamble, no "Based on the
  sources…", no disclaimers, no confidence notes, no restating of the question.
- For list-style questions, use a bullet list — nothing else above or below it.
- Only expand beyond 3 sentences if the user explicitly asks for detail
  ("summarize in depth", "explain", "walk me through…").
- Present numbers inline exactly as stated in the sources.
- Never volunteer tangential information. Answer only what was asked.

## DEAL CONTEXT AWARENESS
- You understand M&A terminology: LOI, IC memo, QoE, CIM, management presentation, data room, etc.
- You understand financial metrics: EBITDA, revenue, margins, multiples, IRR, MOIC, etc.
- You understand deal process: screening, diligence, signing, closing, integration.
- Use this domain knowledge to interpret questions correctly, but only answer using the provided sources.`

const ragQAUserPromptTemplate = `Answer the following question using ONLY the provided source material. Cite every factual claim.

## Question
%s

## Source Material
%s

## Instructions
1. Read the question carefully and identify what specific information is being requested.
2. Search the source material for relevant information.
3. Construct a clear, well-cited answer using ONLY the source material.
4. If the sources do not contain enough information, state this explicitly.
5. Cite every factual claim using [Source:CHUNK_ID] format.

## Answer`

// RegisterQA mounts the deal + meeting scoped Q&A routes (all auth-required).
// Flat chi patterns ({dealID},{meetingID}) so other resources can register
// sibling routes under the shared prefixes.
func (s *Server) RegisterQA(r chi.Router) {
	r.Post("/deals/{dealID}/qa/ask", s.qaAsk)
	r.Get("/deals/{dealID}/qa/history", s.qaHistory)
	r.Get("/deals/{dealID}/qa/history/{interactionID}", s.qaGetInteraction)
	r.Post("/meetings/{meetingID}/qa/ask", s.qaAskMeeting)
	r.Get("/meetings/{meetingID}/qa/history", s.qaMeetingHistory)
}

// ---- wire shapes -----------------------------------------------------------

type qaAskBody struct {
	Question   string   `json:"question"`
	MeetingIDs []string `json:"meeting_ids"`
}

// qaCitationJSON is the canonical persisted + returned citation shape
// (app/schemas/qa.py Citation). Extra keys (chunk_id/relevance/metadata) are
// forbidden — persisting them was a bug.
type qaCitationJSON struct {
	SourceType  string   `json:"source_type"`
	SourceID    string   `json:"source_id"`
	TextExcerpt string   `json:"text_excerpt"`
	Timestamp   *float64 `json:"timestamp"`
}

type qaResponseJSON struct {
	ID             string           `json:"id"`
	DealID         string           `json:"deal_id"`
	Question       string           `json:"question"`
	Answer         string           `json:"answer"`
	Citations      []qaCitationJSON `json:"citations"`
	GroundingScore *float64         `json:"grounding_score"`
	ModelUsed      string           `json:"model_used"`
	CreatedAt      string           `json:"created_at"`
}

type qaHistoryItemJSON struct {
	ID             string           `json:"id"`
	Question       string           `json:"question"`
	Answer         string           `json:"answer"`
	Citations      []qaCitationJSON `json:"citations"`
	GroundingScore *float64         `json:"grounding_score"`
	CreatedAt      string           `json:"created_at"`
}

func toCitationJSON(c model.QACitation) qaCitationJSON {
	return qaCitationJSON{SourceType: c.SourceType, SourceID: c.SourceID,
		TextExcerpt: c.TextExcerpt, Timestamp: c.Timestamp}
}

func toCitationsJSON(cs []model.QACitation) []qaCitationJSON {
	out := make([]qaCitationJSON, 0, len(cs))
	for _, c := range cs {
		out = append(out, toCitationJSON(c))
	}
	return out
}

// LLM provider errors map to a 502 via the shared llmError helper (internal.go),
// matching _llm_provider_http_error.

// ---- handlers --------------------------------------------------------------

// qaAsk answers a question scoped to a deal, optionally narrowed to a subset of
// its meetings (ports ask_question).
func (s *Server) qaAsk(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	dealID := chi.URLParam(r, "dealID")

	// Authorize BEFORE running the billed embed + RAG + LLM pipeline.
	orgID, err := store.DealOrgIDScoped(r.Context(), s.DB, p, dealID)
	if storeError(w, err) {
		return
	}
	var b qaAskBody
	if err := json.NewDecoder(r.Body).Decode(&b); err != nil || strings.TrimSpace(b.Question) == "" {
		writeError(w, http.StatusUnprocessableEntity, "question is required")
		return
	}
	// Validate any meeting-scope narrowing belongs to THIS deal before spending tokens.
	if len(b.MeetingIDs) > 0 {
		if err := store.MeetingsInDeal(r.Context(), s.DB, dealID, b.MeetingIDs); err != nil {
			if errors.Is(err, store.ErrNotFound) {
				writeError(w, http.StatusNotFound, "Meeting not found")
				return
			}
			storeError(w, err)
			return
		}
	}

	result, err := s.qaAskDeal(r.Context(), dealID, b.Question, b.MeetingIDs)
	if llmError(w, err) {
		return
	}

	citations := result.citations
	interaction, err := store.CreateQAInteraction(r.Context(), s.DB, store.QAPersist{
		OrgID: orgID, DealID: dealID, MeetingID: nil, UserID: p.UserID,
		Question: b.Question, Answer: result.answer, Citations: citations,
		GroundingScore: result.groundingScore, ModelUsed: "llm-router",
	})
	if storeError(w, err) {
		return
	}
	writeJSON(w, http.StatusOK, qaResponseJSON{
		ID: interaction.ID, DealID: dealID, Question: b.Question, Answer: result.answer,
		Citations: toCitationsJSON(citations), GroundingScore: result.groundingScore,
		ModelUsed: interaction.ModelUsed, CreatedAt: interaction.CreatedAt,
	})
}

// qaAskMeeting answers a question scoped to a single meeting (ports
// ask_meeting_question).
func (s *Server) qaAskMeeting(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	meetingID := chi.URLParam(r, "meetingID")

	// Resolve + org-scope the meeting; it must belong to a deal.
	var orgID string
	var dealID *string
	err := s.DB.QueryRowContext(r.Context(),
		"SELECT org_id, deal_id FROM meetings WHERE id = ?", meetingID).Scan(&orgID, &dealID)
	if errors.Is(err, sql.ErrNoRows) || (err == nil && (!p.InOrg(orgID) || dealID == nil)) {
		writeError(w, http.StatusNotFound, "Meeting not found")
		return
	}
	if storeError(w, err) {
		return
	}

	var b qaAskBody
	if err := json.NewDecoder(r.Body).Decode(&b); err != nil || strings.TrimSpace(b.Question) == "" {
		writeError(w, http.StatusUnprocessableEntity, "question is required")
		return
	}

	result, err := s.qaAskMeetingScoped(r.Context(), *dealID, meetingID, b.Question)
	if llmError(w, err) {
		return
	}

	citations := result.citations
	interaction, err := store.CreateQAInteraction(r.Context(), s.DB, store.QAPersist{
		OrgID: orgID, DealID: *dealID, MeetingID: &meetingID, UserID: p.UserID,
		Question: b.Question, Answer: result.answer, Citations: citations,
		GroundingScore: result.groundingScore, ModelUsed: "llm-router",
	})
	if storeError(w, err) {
		return
	}
	writeJSON(w, http.StatusOK, qaResponseJSON{
		ID: interaction.ID, DealID: *dealID, Question: b.Question, Answer: result.answer,
		Citations: toCitationsJSON(citations), GroundingScore: result.groundingScore,
		ModelUsed: interaction.ModelUsed, CreatedAt: interaction.CreatedAt,
	})
}

// qaHistory returns a deal's Q&A history, cursor-paginated (ports get_qa_history).
func (s *Server) qaHistory(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	dealID := chi.URLParam(r, "dealID")
	if _, err := store.DealOrgIDScoped(r.Context(), s.DB, p, dealID); storeError(w, err) {
		return
	}
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	items, cursor, hasMore, err := store.ListQAHistory(r.Context(), s.DB, dealID, r.URL.Query().Get("cursor"), limit)
	if storeError(w, err) {
		return
	}
	out := make([]qaHistoryItemJSON, 0, len(items))
	for i := range items {
		out = append(out, qaHistoryItemJSON{
			ID: items[i].ID, Question: items[i].Question, Answer: items[i].Answer,
			Citations: toCitationsJSON(items[i].Citations), GroundingScore: items[i].GroundingScore,
			CreatedAt: items[i].CreatedAt,
		})
	}
	writeJSON(w, http.StatusOK, paginated{Items: out, Cursor: cursor, HasMore: hasMore})
}

// qaMeetingHistory returns the meeting's deal's Q&A history (ports the
// meeting_qa_router history — same deal-scoped list, reached via the meeting).
func (s *Server) qaMeetingHistory(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	meetingID := chi.URLParam(r, "meetingID")
	m, err := store.ScopedMeeting(r.Context(), s.DB, p, meetingID)
	if storeError(w, err) {
		return
	}
	if m.DealID == nil {
		writeError(w, http.StatusNotFound, "Meeting not found")
		return
	}
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	items, cursor, hasMore, err := store.ListQAHistory(r.Context(), s.DB, *m.DealID, r.URL.Query().Get("cursor"), limit)
	if storeError(w, err) {
		return
	}
	out := make([]qaHistoryItemJSON, 0, len(items))
	for i := range items {
		out = append(out, qaHistoryItemJSON{
			ID: items[i].ID, Question: items[i].Question, Answer: items[i].Answer,
			Citations: toCitationsJSON(items[i].Citations), GroundingScore: items[i].GroundingScore,
			CreatedAt: items[i].CreatedAt,
		})
	}
	writeJSON(w, http.StatusOK, paginated{Items: out, Cursor: cursor, HasMore: hasMore})
}

// qaGetInteraction fetches a single Q&A interaction (ports get_qa_interaction).
func (s *Server) qaGetInteraction(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	dealID := chi.URLParam(r, "dealID")
	if _, err := store.DealOrgIDScoped(r.Context(), s.DB, p, dealID); storeError(w, err) {
		return
	}
	row, err := store.GetQAInteraction(r.Context(), s.DB, dealID, chi.URLParam(r, "interactionID"))
	if errors.Is(err, store.ErrNotFound) {
		writeError(w, http.StatusNotFound, "Q&A interaction not found")
		return
	}
	if storeError(w, err) {
		return
	}
	writeJSON(w, http.StatusOK, qaResponseJSON{
		ID: row.ID, DealID: dealID, Question: row.Question, Answer: row.Answer,
		Citations: toCitationsJSON(row.Citations), GroundingScore: row.GroundingScore,
		ModelUsed: row.ModelUsed, CreatedAt: row.CreatedAt,
	})
}

// ---- Q&A pipeline (ports QAService) ----------------------------------------

// qaSource is one source "chunk" fed to the shared synthesis path.
type qaSource struct {
	sourceType string
	sourceID   string
	text       string
	startTime  *float64 // transcript citation timestamp, when known
}

type qaResult struct {
	answer         string
	citations      []model.QACitation
	groundingScore *float64
}

// qaAskDeal answers a deal-scoped question, context-first (ports QAService.ask).
func (s *Server) qaAskDeal(ctx context.Context, dealID, question string, meetingIDs []string) (qaResult, error) {
	blocks, totalTokens, err := s.fetchDealCorpus(ctx, dealID, meetingIDs)
	if err != nil {
		return qaResult{}, err
	}
	if len(blocks) > 0 && totalTokens <= qaDealFullMaxTokens {
		// One source per meeting/document so the model can cite which one a fact
		// came from; reuse the shared synthesis path.
		return s.synthesize(ctx, question, blocks, llm.TaskQAMeeting)
	}
	return s.askRAG(ctx, dealID, question, qaDefaultTopK, meetingIDs)
}

// qaAskMeetingScoped answers a single-meeting question (ports ask_meeting): stuff
// the transcript if it fits, else RAG scoped to that meeting's segments.
func (s *Server) qaAskMeetingScoped(ctx context.Context, dealID, meetingID, question string) (qaResult, error) {
	transcript, err := s.fetchMeetingTranscript(ctx, meetingID)
	if err != nil {
		return qaResult{}, err
	}
	tokens := llm.EstimateTokens(transcript)
	if strings.TrimSpace(transcript) == "" || tokens > qaMeetingMaxTokens {
		// Too big / not yet transcribed → RAG scoped to this one meeting.
		return s.askRAG(ctx, dealID, question, qaDefaultTopK, []string{meetingID})
	}
	blocks := []qaSource{{sourceType: "transcript_segment", sourceID: meetingID, text: transcript}}
	return s.synthesize(ctx, question, blocks, llm.TaskQAMeeting)
}

// askRAG embeds the question, KNN over the deal's embeddings, synthesizes (ports
// _ask_rag). meetingIDs (when set) restricts the KNN to those meetings'
// transcript-segment embeddings.
func (s *Server) askRAG(ctx context.Context, dealID, question string, topK int, meetingIDs []string) (qaResult, error) {
	var sourceIDs []string
	if len(meetingIDs) > 0 {
		ids, err := store.MeetingSegmentIDs(ctx, s.DB, meetingIDs)
		if err != nil {
			return qaResult{}, err
		}
		if len(ids) == 0 {
			return qaResult{answer: "I could not find any transcript text for the selected meeting(s) to answer this question."}, nil
		}
		sourceIDs = ids
	}

	if s.LLM == nil {
		return qaResult{}, fmt.Errorf("LLM client not configured")
	}
	queryVec, err := s.LLM.Embed(ctx, question)
	if err != nil {
		return qaResult{}, err
	}
	hits, err := store.MatchEmbeddingsForDeal(ctx, s.DB, dealID, queryVec, topK, qaMinSimilarity, sourceIDs)
	if err != nil {
		return qaResult{}, err
	}
	if len(hits) == 0 {
		return qaResult{answer: "I could not find any relevant information in the deal's source material to answer this question."}, nil
	}

	blocks := make([]qaSource, 0, len(hits))
	var tsIDs []string
	for _, h := range hits {
		blocks = append(blocks, qaSource{sourceType: h.SourceType, sourceID: h.SourceID, text: h.ChunkText})
		if h.SourceType == "transcript_segment" {
			tsIDs = append(tsIDs, h.SourceID)
		}
	}
	// Enrich transcript citations with start_time (the frontend builds a direct
	// link to the moment) in one batched query.
	if len(tsIDs) > 0 {
		meta, err := store.SegmentsMeta(ctx, s.DB, tsIDs)
		if err != nil {
			return qaResult{}, err
		}
		for i := range blocks {
			if blocks[i].sourceType != "transcript_segment" {
				continue
			}
			if m, ok := meta[blocks[i].sourceID]; ok {
				st := m.StartTime
				blocks[i].startTime = &st
			}
		}
	}

	return s.synthesize(ctx, question, blocks, llm.TaskQARAG)
}

// synthesize renders the RAG prompt over the sources, calls the task-routed LLM,
// and parses citations (ports _synthesize + _map_citations). Grounding scoring is
// not ported; grounding_score is left null (the column is nullable).
func (s *Server) synthesize(ctx context.Context, question string, sources []qaSource, task string) (qaResult, error) {
	if s.LLM == nil {
		return qaResult{}, fmt.Errorf("LLM client not configured")
	}
	userPrompt := fmt.Sprintf(ragQAUserPromptTemplate, question, formatContext(sources))
	resp, err := s.LLM.Complete(ctx, task, ragQASystemPrompt, userPrompt, llm.CompleteOpts{
		MaxTokens: 4096, Temperature: 0.0,
	})
	if err != nil {
		return qaResult{}, err
	}

	answer, rawCitations := parseQAResponse(resp.Content)
	citations := mapCitations(rawCitations, sources)
	return qaResult{answer: answer, citations: citations}, nil
}

// formatContext renders sources into [CHUNK_ID: chunk_N] headed sections (ports
// _format_context). The chunk_N id is the source's index, which mapCitations
// resolves back when parsing the model's [chunk_id] references.
func formatContext(sources []qaSource) string {
	sections := make([]string, 0, len(sources))
	for i, src := range sources {
		header := fmt.Sprintf("[CHUNK_ID: chunk_%d] [Type: %s]", i, src.sourceType)
		if src.startTime != nil {
			header += fmt.Sprintf(" [Time: %.1fs]", *src.startTime)
		}
		sections = append(sections, header+"\n"+src.text)
	}
	return strings.Join(sections, "\n\n---\n\n")
}

var qaFenceRe = regexp.MustCompile("(?s)```(?:json)?\\s*\\n(.*?)\\n```")

type qaRawCitation struct {
	ChunkID string `json:"chunk_id"`
}

// parseQAResponse extracts the JSON {answer, citations_used} from the model
// output (ports _parse_response + the citation parsing). On a non-JSON reply the
// whole content is the answer and there are no parsed citations.
func parseQAResponse(content string) (answer string, citations []qaRawCitation) {
	text := strings.TrimSpace(content)
	if strings.Contains(text, "```") {
		if m := qaFenceRe.FindStringSubmatch(text); m != nil {
			text = strings.TrimSpace(m[1])
		}
	}
	var parsed struct {
		Answer        string          `json:"answer"`
		CitationsUsed []qaRawCitation `json:"citations_used"`
	}
	if err := json.Unmarshal([]byte(text), &parsed); err != nil || parsed.Answer == "" {
		return content, nil
	}
	return parsed.Answer, parsed.CitationsUsed
}

// mapCitations resolves the model's [chunk_id] references back to the source
// chunks and returns canonical citations (ports _map_citations). The text
// excerpt is truncated to 200 chars; timestamp comes from transcript enrichment.
func mapCitations(raw []qaRawCitation, sources []qaSource) []model.QACitation {
	byChunk := make(map[string]qaSource, len(sources))
	for i, src := range sources {
		byChunk[fmt.Sprintf("chunk_%d", i)] = src
	}
	out := make([]model.QACitation, 0, len(raw))
	for _, c := range raw {
		src, ok := byChunk[c.ChunkID]
		if !ok {
			continue
		}
		out = append(out, model.QACitation{
			SourceType:  src.sourceType,
			SourceID:    src.sourceID,
			TextExcerpt: truncateRunes(src.text, 200),
			Timestamp:   src.startTime,
		})
	}
	return out
}

func truncateRunes(s string, n int) string {
	r := []rune(s)
	if len(r) <= n {
		return s
	}
	return string(r[:n])
}

// ---- corpus helpers (ports _fetch_deal_corpus / _fetch_meeting_transcript) --

// fetchDealCorpus builds the deal's Q&A corpus as per-source blocks (every
// meeting's finalized transcript + every document's extracted text), with the
// total estimated token count (ports _fetch_deal_corpus). When meetingIDs is
// non-empty the corpus is narrowed to those meetings and documents are skipped.
func (s *Server) fetchDealCorpus(ctx context.Context, dealID string, meetingIDs []string) ([]qaSource, int, error) {
	var blocks []qaSource
	total := 0

	meetings, err := store.DealMeetingsForCorpus(ctx, s.DB, dealID, meetingIDs)
	if err != nil {
		return nil, 0, err
	}
	for _, m := range meetings {
		text, err := s.fetchMeetingTranscript(ctx, m.ID)
		if err != nil {
			return nil, 0, err
		}
		if strings.TrimSpace(text) == "" {
			continue
		}
		title := m.Title
		if title == "" {
			title = "Untitled"
		}
		label := "Meeting: " + title
		when := m.CreatedAt
		if m.MeetingDate != nil && *m.MeetingDate != "" {
			when = *m.MeetingDate
		}
		if when != "" {
			label += " (" + when + ")"
		}
		body := "## " + label + "\n" + text
		blocks = append(blocks, qaSource{sourceType: "transcript_segment", sourceID: m.ID, text: body})
		total += llm.EstimateTokens(text)
	}

	// Deal-wide documents only when not narrowed to a meeting subset.
	if len(meetingIDs) == 0 {
		docs, err := store.DealDocuments(ctx, s.DB, dealID)
		if err != nil {
			return nil, 0, err
		}
		for _, d := range docs {
			text := ""
			if d.ExtractedText != nil {
				text = strings.TrimSpace(*d.ExtractedText)
			}
			if text == "" {
				continue
			}
			title := d.Title
			if title == "" {
				title = "Untitled"
			}
			body := "## Document: " + title + "\n" + text
			blocks = append(blocks, qaSource{sourceType: "document_chunk", sourceID: d.ID, text: body})
			total += llm.EstimateTokens(text)
		}
	}

	return blocks, total, nil
}

// fetchMeetingTranscript returns a meeting's finalized transcript as
// speaker-attributed lines (ports _fetch_meeting_transcript).
func (s *Server) fetchMeetingTranscript(ctx context.Context, meetingID string) (string, error) {
	segs, err := store.MeetingFinalizedSegments(ctx, s.DB, meetingID)
	if err != nil {
		return "", err
	}
	lines := make([]string, 0, len(segs))
	for _, seg := range segs {
		label := "Speaker"
		if seg.SpeakerName != nil && *seg.SpeakerName != "" {
			label = *seg.SpeakerName
		} else if seg.SpeakerLabel != "" {
			label = seg.SpeakerLabel
		}
		lines = append(lines, label+": "+strings.TrimSpace(seg.Text))
	}
	return strings.Join(lines, "\n"), nil
}
