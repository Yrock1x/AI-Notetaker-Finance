package httpapi

import (
	"encoding/json"
	"net/http"
	"os"
	"strings"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/llm"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/storage"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/store"
	"github.com/go-chi/chi/v5"
)

// Chunker windows match TranscriptChunker/DocumentChunker (max 500 / overlap 50).
const (
	chunkMaxTokens = 500
	chunkOverlap   = 50
)

// The /internal/process-document handler reads from this bucket (ports
// DOCUMENTS_BUCKET in app/api/v1/internal/_common.py).
const documentsBucket = "deal-documents"

// requireInternalToken is the service-to-service auth guard (ports
// require_internal_token in app/api/v1/internal/_common.py): 500 if
// WORKER_INTERNAL_TOKEN is unset, 401 if the X-Internal-Token header doesn't
// match. NOT requireAuth — the /internal/* surface is called only by the worker's
// own Inngest functions, not the browser.
func (s *Server) requireInternalToken(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if s.Cfg.WorkerInternalToken == "" {
			writeError(w, http.StatusInternalServerError, "WORKER_INTERNAL_TOKEN is not configured")
			return
		}
		if r.Header.Get("X-Internal-Token") != s.Cfg.WorkerInternalToken {
			writeError(w, http.StatusUnauthorized, "Invalid or missing X-Internal-Token")
			return
		}
		next.ServeHTTP(w, r)
	})
}

// llmError maps an llm.Client error to a 502 (the embedding/completion provider
// is a downstream dependency).
func llmError(w http.ResponseWriter, err error) bool {
	if err == nil {
		return false
	}
	writeError(w, http.StatusBadGateway, "LLM provider unavailable")
	return true
}

// RegisterInternal mounts /api/v1/internal/* behind the X-Internal-Token guard.
// Mounted on the /api/v1 router (the orchestrator wires this; it does NOT live in
// the requireAuth group). Flat patterns under an /internal route group.
func (s *Server) RegisterInternal(r chi.Router) {
	r.Route("/internal", func(r chi.Router) {
		r.Use(s.requireInternalToken)
		r.Post("/embed", s.internalEmbed)
		r.Post("/analyze", s.internalAnalyze)
		r.Post("/process-document", s.internalProcessDocument)
	})
}

// ---------------------------------------------------------------------------
// POST /internal/embed  {meeting_id} -> {count}
// ---------------------------------------------------------------------------
func (s *Server) internalEmbed(w http.ResponseWriter, r *http.Request) {
	var body struct {
		MeetingID string `json:"meeting_id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil || body.MeetingID == "" {
		writeError(w, http.StatusUnprocessableEntity, "meeting_id is required")
		return
	}

	meeting, err := store.GetEmbedMeetingRef(r.Context(), s.DB, body.MeetingID)
	if err == store.ErrNotFound {
		writeError(w, http.StatusNotFound, "Meeting not found")
		return
	}
	if storeError(w, err) {
		return
	}
	if meeting.DealID == nil || *meeting.DealID == "" {
		writeError(w, http.StatusBadRequest, "Meeting has no deal_id")
		return
	}
	dealID := *meeting.DealID

	segments, err := store.FinalizedSegments(r.Context(), s.DB, meeting.ID)
	if storeError(w, err) {
		return
	}
	if len(segments) == 0 {
		writeJSON(w, http.StatusOK, map[string]any{"count": 0})
		return
	}

	chunks := llm.ChunkSegments(segments, chunkMaxTokens, chunkOverlap)
	if len(chunks) == 0 {
		writeJSON(w, http.StatusOK, map[string]any{"count": 0})
		return
	}
	// A transcript_segment chunk's source_id is the first segment id in the
	// window; Python falls back to the meeting id when a chunk has no segments.
	texts := make([]string, len(chunks))
	for i := range chunks {
		texts[i] = chunks[i].Text
		if chunks[i].SourceID == "" {
			chunks[i].SourceID = meeting.ID
		}
	}

	if s.LLM == nil {
		writeError(w, http.StatusServiceUnavailable, "Embedding is not available")
		return
	}
	vectors, err := s.LLM.EmbedBatch(r.Context(), texts)
	if llmError(w, err) {
		return
	}

	// Clear prior embeddings for THIS meeting's segment ids, then write fresh
	// rows + vectors — all scoped to the meeting's own org_id/deal_id.
	priorSourceIDs := make([]string, len(segments))
	for i := range segments {
		priorSourceIDs[i] = segments[i].ID
	}
	count, err := store.ReplaceEmbeddings(
		r.Context(), s.DB, meeting.OrgID, dealID, "transcript_segment",
		priorSourceIDs, chunks, vectors,
	)
	if storeError(w, err) {
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"count": count})
}

// ---------------------------------------------------------------------------
// POST /internal/analyze  {meeting_id, call_type?, requested_by?} -> {analysis_id, status}
// ---------------------------------------------------------------------------
func (s *Server) internalAnalyze(w http.ResponseWriter, r *http.Request) {
	var body struct {
		MeetingID   string  `json:"meeting_id"`
		CallType    string  `json:"call_type"`
		RequestedBy *string `json:"requested_by"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil || body.MeetingID == "" {
		writeError(w, http.StatusUnprocessableEntity, "meeting_id is required")
		return
	}
	if body.CallType == "" {
		body.CallType = "summarization"
	}

	// The meeting must exist (ports session.get(Meeting, id) -> 404).
	if _, err := store.GetEmbedMeetingRef(r.Context(), s.DB, body.MeetingID); err == store.ErrNotFound {
		writeError(w, http.StatusNotFound, "Meeting not found")
		return
	} else if storeError(w, err) {
		return
	}

	// TODO(port): delegate to the analysis service once app/services/
	// analysis_service.py is ported to Go (it runs the LLM, persists an
	// `analyses` row, and returns {id, status}). Until then this endpoint is a
	// stub so the route + auth + request contract are wired, but no analysis is
	// produced.
	writeError(w, http.StatusNotImplemented, "analysis service not yet ported to Go")
}

// ---------------------------------------------------------------------------
// POST /internal/process-document  {document_id} -> {embedding_count}
// ---------------------------------------------------------------------------
func (s *Server) internalProcessDocument(w http.ResponseWriter, r *http.Request) {
	var body struct {
		DocumentID string `json:"document_id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil || body.DocumentID == "" {
		writeError(w, http.StatusUnprocessableEntity, "document_id is required")
		return
	}

	doc, err := store.ScopedDocumentByID(r.Context(), s.DB, body.DocumentID)
	if err == store.ErrNotFound {
		writeError(w, http.StatusNotFound, "Document not found")
		return
	}
	if storeError(w, err) {
		return
	}

	// Read the document bytes from local object storage.
	path, err := storage.ObjectPath(s.Cfg.StorageRoot, documentsBucket, doc.FileKey)
	if err != nil {
		writeError(w, http.StatusBadRequest, "Invalid document file_key")
		return
	}
	fileBytes, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		writeError(w, http.StatusNotFound, "Document not found in storage")
		return
	}
	if err != nil {
		writeError(w, http.StatusInternalServerError, "internal error")
		return
	}

	extracted := extractDocumentText(strings.ToLower(doc.DocumentType), fileBytes)
	if strings.TrimSpace(extracted) == "" {
		// Persist the empty extraction (matches Python: doc.extracted_text = "").
		if storeError(w, store.SetDocumentExtractedText(r.Context(), s.DB, doc.ID, "")) {
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{"embedding_count": 0})
		return
	}

	// Commit the extracted text BEFORE the embedding network call so the single
	// SQLite writer lock isn't held across EmbedBatch (mirrors the Python note —
	// holding it would stall the live-transcript write path).
	if storeError(w, store.SetDocumentExtractedText(r.Context(), s.DB, doc.ID, extracted)) {
		return
	}

	chunks := llm.ChunkText(extracted, doc.ID, chunkMaxTokens, chunkOverlap)
	if len(chunks) == 0 {
		writeJSON(w, http.StatusOK, map[string]any{"embedding_count": 0})
		return
	}
	texts := make([]string, len(chunks))
	for i := range chunks {
		texts[i] = chunks[i].Text
	}

	if s.LLM == nil {
		writeError(w, http.StatusServiceUnavailable, "Embedding is not available")
		return
	}
	vectors, err := s.LLM.EmbedBatch(r.Context(), texts)
	if llmError(w, err) {
		return
	}

	// Replace prior embeddings for THIS document (rows + vectors), scoped to the
	// document's own org_id/deal_id.
	count, err := store.ReplaceEmbeddings(
		r.Context(), s.DB, doc.OrgID, doc.DealID, "document_chunk",
		[]string{doc.ID}, chunks, vectors,
	)
	if storeError(w, err) {
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"embedding_count": count})
}

// extractDocumentText extracts UTF-8 text from a document's bytes. Plaintext
// files (and unknown types) are decoded directly; binary formats (pdf/docx/xlsx)
// are STUBBED — porting the heavy extractors (app/utils/file_processing.py:
// pdfplumber / python-docx / openpyxl) is out of scope for this area, so for
// those we fall back to nothing and the document yields zero embeddings until the
// extractors are ported. The embed path itself is fully implemented.
func extractDocumentText(dtype string, b []byte) string {
	switch dtype {
	case "pdf", "docx", "doc", "xlsx", "xls":
		// TODO(port): wire app/utils/file_processing.py extractors. Until then a
		// binary document produces no extractable text.
		return ""
	default:
		return string(b) // plaintext / unknown — best-effort UTF-8 decode
	}
}
