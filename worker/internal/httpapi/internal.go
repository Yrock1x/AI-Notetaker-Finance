package httpapi

import (
	"context"
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/crypto/fernet"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/integrations/calendar"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/integrations/deepgram"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/integrations/oauth"
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

// Storage buckets the /internal handlers read from (port DOCUMENTS_BUCKET /
// MEETINGS_BUCKET in app/api/v1/internal/_common.py).
const (
	documentsBucket = "deal-documents"
	meetingsBucket  = "meeting-recordings"
)

// extMimetypes maps a recording's extension to a Deepgram-friendly mimetype
// (ports _EXT_MIMETYPES). Default audio/mp4.
var extMimetypes = map[string]string{
	"mp4": "audio/mp4", "m4a": "audio/mp4", "mp3": "audio/mpeg",
	"wav": "audio/wav", "webm": "audio/webm", "ogg": "audio/ogg",
	"flac": "audio/flac", "aac": "audio/aac",
}

func mimetypeForKey(fileKey string) string {
	ext := ""
	if i := strings.LastIndex(fileKey, "."); i >= 0 {
		ext = strings.ToLower(fileKey[i+1:])
	}
	if mt, ok := extMimetypes[ext]; ok {
		return mt
	}
	return "audio/mp4"
}

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
		r.Post("/meeting-status", s.internalMeetingStatus)
		r.Post("/transcribe", s.internalTranscribe)
		r.Post("/embed", s.internalEmbed)
		r.Post("/analyze", s.internalAnalyze)
		r.Post("/process-document", s.internalProcessDocument)
		r.Post("/calendar/sync", s.internalCalendarSync)
		r.Get("/calendar/list-active-integrations", s.internalCalendarListActiveIntegrations)
		r.Post("/zoom/ingest", s.internalZoomIngest)
		r.Post("/teams/ingest-call-record", s.internalTeamsIngest)
		r.Post("/microsoft/ensure-subscription", s.internalEnsureSubscription)
		s.RegisterBots(r)
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

	// The meeting must exist; org_id is derived from it (never the client),
	// matching the synchronous POST /meetings/{id}/analyses path.
	ref, err := store.GetEmbedMeetingRef(r.Context(), s.DB, body.MeetingID)
	if err == store.ErrNotFound {
		writeError(w, http.StatusNotFound, "Meeting not found")
		return
	}
	if storeError(w, err) {
		return
	}

	// The analysis service is already ported (runAnalysis): fetch transcript,
	// render the call-type prompt, call the LLM, parse, and persist an analyses
	// row. The Inngest pipeline's analyze step calls this with call_type
	// "summarization".
	a, err := s.runAnalysis(r.Context(), ref.OrgID, body.MeetingID, body.CallType, body.RequestedBy)
	if err != nil {
		s.writeAnalysisError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"analysis_id": a.ID, "status": a.Status})
}

// ---------------------------------------------------------------------------
// POST /internal/meeting-status  {meeting_id, status, error_message?} -> {ok}
// ---------------------------------------------------------------------------
func (s *Server) internalMeetingStatus(w http.ResponseWriter, r *http.Request) {
	var body struct {
		MeetingID    string  `json:"meeting_id"`
		Status       string  `json:"status"`
		ErrorMessage *string `json:"error_message"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil || body.MeetingID == "" || body.Status == "" {
		writeError(w, http.StatusUnprocessableEntity, "meeting_id and status are required")
		return
	}
	err := store.SetMeetingStatus(r.Context(), s.DB, body.MeetingID, body.Status, body.ErrorMessage)
	if err == store.ErrNotFound {
		writeError(w, http.StatusNotFound, "Meeting not found")
		return
	}
	if storeError(w, err) {
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"ok": true})
}

// ---------------------------------------------------------------------------
// POST /internal/transcribe  {meeting_id} -> {transcript_id, segment_count}
// ---------------------------------------------------------------------------
func (s *Server) internalTranscribe(w http.ResponseWriter, r *http.Request) {
	var body struct {
		MeetingID string `json:"meeting_id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil || body.MeetingID == "" {
		writeError(w, http.StatusUnprocessableEntity, "meeting_id is required")
		return
	}

	orgID, fileKey, err := store.MeetingFile(r.Context(), s.DB, body.MeetingID)
	if err == store.ErrNotFound {
		writeError(w, http.StatusNotFound, "Meeting not found")
		return
	}
	if storeError(w, err) {
		return
	}
	if fileKey == nil || *fileKey == "" {
		writeError(w, http.StatusBadRequest, "Meeting has no file_key")
		return
	}

	// Read the recording from local object storage (it lives on the worker disk;
	// no signed URL needed — Deepgram gets the bytes directly).
	path, err := storage.ObjectPath(s.Cfg.StorageRoot, meetingsBucket, *fileKey)
	if err != nil {
		writeError(w, http.StatusBadRequest, "Invalid meeting file_key")
		return
	}
	audio, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		writeError(w, http.StatusNotFound, "Meeting recording not found in storage")
		return
	}
	if err != nil {
		writeError(w, http.StatusInternalServerError, "internal error")
		return
	}

	if s.Cfg.DeepgramAPIKey == "" {
		writeError(w, http.StatusInternalServerError, "DEEPGRAM_API_KEY is not configured")
		return
	}
	rawResp, segments, err := deepgram.New(s.Cfg.DeepgramAPIKey).
		Transcribe(r.Context(), audio, mimetypeForKey(*fileKey))
	if err != nil {
		// Surface the real Deepgram error (status + body are embedded in err) so a
		// rejected recording is debuggable — the client still gets a generic 502.
		slog.Error("deepgram transcribe failed", "meeting_id", body.MeetingID,
			"mimetype", mimetypeForKey(*fileKey), "bytes", len(audio), "err", err)
		writeError(w, http.StatusBadGateway, "Transcription provider unavailable")
		return
	}

	// Build the transcript summary (full text, word count, mean confidence).
	in := store.TranscriptInput{
		OrgID: orgID, MeetingID: body.MeetingID, Language: "en",
		DeepgramResponse: rawResp,
		Segments:         make([]store.TranscriptSegmentInput, 0, len(segments)),
	}
	var parts []string
	var confSum float64
	confN := 0
	for _, seg := range segments {
		parts = append(parts, seg.Text)
		in.WordCount += len(strings.Fields(seg.Text))
		// Every processed segment carries a real (rounded) confidence — the
		// diarization processor never emits a missing value — so include them all
		// in the mean, matching Python's "confidence is not None" predicate exactly.
		confSum += seg.Confidence
		confN++
		in.Segments = append(in.Segments, store.TranscriptSegmentInput{
			SpeakerLabel: seg.SpeakerLabel, SpeakerName: seg.SpeakerName, Text: seg.Text,
			StartTime: seg.StartTime, EndTime: seg.EndTime, Confidence: seg.Confidence,
			SegmentIndex: seg.SegmentIndex,
		})
	}
	in.FullText = strings.Join(parts, " ")
	if confN > 0 {
		avg := confSum / float64(confN)
		in.ConfidenceScore = &avg
	}

	transcriptID, count, err := store.SaveTranscript(r.Context(), s.DB, in)
	if storeError(w, err) {
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"transcript_id": transcriptID, "segment_count": count})
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

// ---------------------------------------------------------------------------
// POST /internal/calendar/sync  {user_id, org_id, platform, lookahead_days?}
//
//	-> {platform, events_seen, meetings_upserted}
//
// ---------------------------------------------------------------------------
func (s *Server) internalCalendarSync(w http.ResponseWriter, r *http.Request) {
	var body struct {
		UserID        string `json:"user_id"`
		OrgID         string `json:"org_id"`
		Platform      string `json:"platform"`
		LookaheadDays int    `json:"lookahead_days"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil || body.UserID == "" || body.OrgID == "" || body.Platform == "" {
		writeError(w, http.StatusUnprocessableEntity, "user_id, org_id and platform are required")
		return
	}
	prov, ok := oauth.ByName(body.Platform)
	if !ok {
		writeError(w, http.StatusBadRequest, "Unsupported platform "+body.Platform)
		return
	}
	lookahead := body.LookaheadDays
	if lookahead <= 0 {
		lookahead = 14
	}
	fkey, err := fernet.ParseKey(s.Cfg.TokenEncryptionKey)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "token encryption is not configured")
		return
	}
	clientID, clientSecret := s.integrationClientCreds(body.Platform)
	access, err := store.GetValidAccessToken(r.Context(), s.DB, fkey, prov, clientID, clientSecret, oauthHTTPClient, body.OrgID, body.UserID, body.Platform)
	if err == store.ErrNotFound {
		writeError(w, http.StatusNotFound, "No active "+body.Platform+" credentials for user")
		return
	}
	if err != nil {
		slog.Error("calendar sync token error", "platform", body.Platform, "err", err)
		writeError(w, http.StatusBadGateway, "Calendar provider unavailable")
		return
	}

	now := time.Now().UTC()
	timeMax := now.Add(time.Duration(lookahead) * 24 * time.Hour)
	var events []calendar.SyncedMeeting
	var seen int
	switch body.Platform {
	case "zoom":
		events, seen, err = calendar.ListZoom(r.Context(), oauthHTTPClient, access)
	case "microsoft":
		events, seen, err = calendar.ListGraph(r.Context(), oauthHTTPClient, access, now, timeMax)
	case "google":
		events, seen, err = calendar.ListGoogle(r.Context(), oauthHTTPClient, access, now, timeMax)
	}
	if err != nil {
		slog.Error("calendar sync fetch error", "platform", body.Platform, "err", err)
		writeError(w, http.StatusBadGateway, "Calendar provider unavailable")
		return
	}

	inputs := make([]store.SyncedMeetingInput, 0, len(events))
	for i := range events {
		inputs = append(inputs, store.SyncedMeetingInput{
			Title: events[i].Title, MeetingDate: events[i].MeetingDate, Source: events[i].Source,
			SourceURL: events[i].SourceURL, ExternalEventID: events[i].ExternalEventID,
			BotEnabled: events[i].BotEnabled,
		})
	}
	upserted, err := store.UpsertSyncedMeetings(r.Context(), s.DB, body.OrgID, body.UserID, body.Platform, inputs)
	if storeError(w, err) {
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"platform": body.Platform, "events_seen": seen, "meetings_upserted": upserted,
	})
}

// recordingHTTPClient downloads provider recordings (up to ~10 min); a package
// var so tests can intercept it.
var recordingHTTPClient = &http.Client{Timeout: 10 * time.Minute}

// POST /internal/zoom/ingest  {zoom_meeting_id, download_url, topic?}
//
//	-> {meeting_id, status}. Attribute or create the meeting, download the
//	recording into storage, mark uploaded, fire meeting/uploaded (ports zoom_ingest).
func (s *Server) internalZoomIngest(w http.ResponseWriter, r *http.Request) {
	var body struct {
		ZoomMeetingID string `json:"zoom_meeting_id"`
		DownloadURL   string `json:"download_url"`
		Topic         string `json:"topic"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil || body.ZoomMeetingID == "" || body.DownloadURL == "" {
		writeError(w, http.StatusUnprocessableEntity, "zoom_meeting_id and download_url are required")
		return
	}

	match, err := store.FindZoomMeeting(r.Context(), s.DB, body.ZoomMeetingID)
	if storeError(w, err) {
		return
	}
	var meetingID, orgID, dealID string
	if match != nil {
		meetingID, orgID = match.ID, match.OrgID
		if match.DealID != nil {
			dealID = *match.DealID
		}
	} else {
		credOrg, credUser, ok, err := store.FirstActiveZoomCredential(r.Context(), s.DB)
		if storeError(w, err) {
			return
		}
		if !ok {
			writeJSON(w, http.StatusOK, map[string]any{"meeting_id": nil, "status": "no_credential"})
			return
		}
		orgID = credOrg
		title := body.Topic
		if title == "" {
			title = "Zoom recording"
		}
		meetingID, err = store.CreateZoomIngestMeeting(r.Context(), s.DB, orgID, title, credUser, body.ZoomMeetingID)
		if storeError(w, err) {
			return
		}
	}

	// Best-effort download auth (the org's zoom access token).
	authHeader := ""
	if enc, _ := store.ZoomAccessEncForOrg(r.Context(), s.DB, orgID); enc != "" {
		if fkey, err := fernet.ParseKey(s.Cfg.TokenEncryptionKey); err == nil {
			if tok, err := fkey.Decrypt(enc); err == nil {
				authHeader = "Bearer " + string(tok)
			}
		}
	}

	fileBytes, err := downloadRecording(r.Context(), body.DownloadURL, authHeader)
	if err != nil {
		slog.Error("zoom ingest download failed", "meeting_id", meetingID, "err", err)
		_ = store.SetMeetingStatus(r.Context(), s.DB, meetingID, "failed", nil)
		writeError(w, http.StatusBadGateway, "Zoom download failed")
		return
	}
	fileKey := "zoom/" + meetingID + ".mp4"
	if err := storage.SaveBytes(s.Cfg.StorageRoot, meetingsBucket, fileKey, fileBytes); err != nil {
		writeError(w, http.StatusInternalServerError, "failed to store recording")
		return
	}
	if storeError(w, store.SetMeetingUploaded(r.Context(), s.DB, meetingID, fileKey, body.DownloadURL)) {
		return
	}
	s.inngest().Send(r.Context(), "meeting/uploaded", map[string]any{"meeting_id": meetingID, "deal_id": dealID})
	writeJSON(w, http.StatusOK, map[string]any{"meeting_id": meetingID, "status": "uploaded"})
}

func downloadRecording(ctx context.Context, url, authHeader string) ([]byte, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, err
	}
	if authHeader != "" {
		req.Header.Set("Authorization", authHeader)
	}
	resp, err := recordingHTTPClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return nil, &recallStatusError{status: resp.StatusCode}
	}
	return io.ReadAll(io.LimitReader(resp.Body, 2<<30)) // 2 GiB cap
}

type recallStatusError struct{ status int }

func (e *recallStatusError) Error() string { return "download returned non-2xx" }

// GET /internal/calendar/list-active-integrations -> {integrations: [...]}
func (s *Server) internalCalendarListActiveIntegrations(w http.ResponseWriter, r *http.Request) {
	rows, err := store.ListActiveCalendarIntegrations(r.Context(), s.DB)
	if storeError(w, err) {
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"integrations": rows})
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
