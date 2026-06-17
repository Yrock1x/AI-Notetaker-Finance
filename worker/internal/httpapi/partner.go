package httpapi

import (
	"context"
	"database/sql"
	"encoding/json"
	"net/http"
	"strings"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/db"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/store"
	"github.com/go-chi/chi/v5"
)

type partnerCtxKey int

const ctxPartnerKey partnerCtxKey = 0

func partnerKeyFromCtx(ctx context.Context) *store.PartnerKey {
	v, _ := ctx.Value(ctxPartnerKey).(*store.PartnerKey)
	return v
}

// partnerAuth authenticates a partner request (Authorization: Bearer <raw key>)
// and stashes the key in context (ports get_partner_context).
func (s *Server) partnerAuth(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		authz := r.Header.Get("Authorization")
		if authz == "" {
			writeError(w, http.StatusUnauthorized, "Missing Authorization header")
			return
		}
		scheme, raw, _ := strings.Cut(authz, " ")
		if !strings.EqualFold(scheme, "bearer") || strings.TrimSpace(raw) == "" {
			writeError(w, http.StatusUnauthorized, "Invalid Authorization header")
			return
		}
		key, err := store.GetActivePartnerKey(r.Context(), s.DB, store.HashPartnerKey(strings.TrimSpace(raw)))
		if err != nil {
			writeError(w, http.StatusInternalServerError, "auth failed")
			return
		}
		if key == nil {
			writeError(w, http.StatusUnauthorized, "Invalid API key")
			return
		}
		store.BumpPartnerKeyUsed(r.Context(), s.DB, key.ID)
		next.ServeHTTP(w, r.WithContext(context.WithValue(r.Context(), ctxPartnerKey, key)))
	})
}

func requireScope(w http.ResponseWriter, k *store.PartnerKey, scope string) bool {
	if !k.HasScope(scope) {
		writeError(w, http.StatusForbidden, "Missing required scope: "+scope)
		return false
	}
	return true
}

func requireShare(w http.ResponseWriter, c *store.VdrConnection, category string) bool {
	if !c.HasShareScope(category) {
		writeError(w, http.StatusForbidden, "Resource not shared for this deal: "+category)
		return false
	}
	return true
}

// RegisterPartner mounts /partner/v1/* at the ROOT router (not under /api/v1),
// behind partner-key auth.
func (s *Server) RegisterPartner(r chi.Router) {
	r.Route("/partner/v1", func(r chi.Router) {
		r.Use(s.partnerAuth)
		r.Get("/deals", s.partnerListDeals)
		r.Post("/deals", s.partnerCreateDeal)
		r.Get("/deals/{dealID}", s.partnerGetDeal)
		r.Get("/deals/{dealID}/documents", s.partnerListDocuments)
		r.Post("/deals/{dealID}/documents", s.partnerCreateDocument)
		r.Get("/meetings/{meetingID}/transcript", s.partnerGetTranscript)
		r.Get("/meetings/{meetingID}/analyses", s.partnerListAnalyses)
		r.Post("/deals/{dealID}/search", s.partnerSearch)
	})
}

type partnerDealJSON struct {
	dealJSON
	VdrID        string   `json:"vdr_id"`
	SharedScopes []string `json:"shared_scopes"`
}

func toPartnerDeal(d *dealJSON, c *store.VdrConnection) partnerDealJSON {
	scopes := c.ShareScopes
	if scopes == nil {
		scopes = []string{}
	}
	return partnerDealJSON{dealJSON: *d, VdrID: c.VdrID, SharedScopes: scopes}
}

func (s *Server) partnerListDeals(w http.ResponseWriter, r *http.Request) {
	k := partnerKeyFromCtx(r.Context())
	if !requireScope(w, k, "deals:read") {
		return
	}
	deals, conns, err := store.PartnerListConnectedDeals(r.Context(), s.DB, k.OrgID)
	if storeError(w, err) {
		return
	}
	out := make([]partnerDealJSON, 0, len(deals))
	for i := range deals {
		dj := toDealJSON(&deals[i])
		out = append(out, toPartnerDeal(&dj, conns[deals[i].ID]))
	}
	// Best-effort partner audit trail (ports record_audit); a failed audit write
	// must not fail the read, so the error is ignored.
	_ = store.RecordAudit(r.Context(), s.DB, store.Audit{
		OrgID: k.OrgID, Action: "list", ResourceType: "partner",
		Details: map[string]any{"resource": "deals", "count": len(out)},
	})
	writeJSON(w, http.StatusOK, out)
}

func (s *Server) partnerGetDeal(w http.ResponseWriter, r *http.Request) {
	k := partnerKeyFromCtx(r.Context())
	if !requireScope(w, k, "deals:read") {
		return
	}
	d, c, err := store.PartnerScopedDeal(r.Context(), s.DB, k.OrgID, chi.URLParam(r, "dealID"))
	if storeError(w, err) {
		return
	}
	did := d.ID
	_ = store.RecordAudit(r.Context(), s.DB, store.Audit{
		OrgID: k.OrgID, Action: "read", ResourceType: "partner",
		ResourceID: &did, DealID: &did,
		Details: map[string]any{"resource": "deal"},
	})
	dj := toDealJSON(d)
	writeJSON(w, http.StatusOK, toPartnerDeal(&dj, c))
}

func (s *Server) partnerCreateDeal(w http.ResponseWriter, r *http.Request) {
	k := partnerKeyFromCtx(r.Context())
	if !requireScope(w, k, "deals:write") {
		return
	}
	var b dealCreateBody
	if err := json.NewDecoder(r.Body).Decode(&b); err != nil || b.Name == "" {
		writeError(w, http.StatusUnprocessableEntity, "name is required")
		return
	}
	p := &store.Principal{UserID: "partner:" + k.ID, OrgIDs: []string{k.OrgID}}
	d, err := store.CreateDeal(r.Context(), s.DB, p, store.DealCreate{
		OrgID: k.OrgID, Name: b.Name, Description: b.Description, TargetCompany: b.TargetCompany,
		DealType: b.DealType, Stage: b.Stage, Status: b.Status,
	})
	if storeError(w, err) {
		return
	}
	writeJSON(w, http.StatusCreated, toDealJSON(d))
}

func (s *Server) partnerListDocuments(w http.ResponseWriter, r *http.Request) {
	k := partnerKeyFromCtx(r.Context())
	if !requireScope(w, k, "documents:read") {
		return
	}
	_, c, err := store.PartnerScopedDeal(r.Context(), s.DB, k.OrgID, chi.URLParam(r, "dealID"))
	if storeError(w, err) {
		return
	}
	if !requireShare(w, c, "documents") {
		return
	}
	rows, err := s.DB.QueryContext(r.Context(),
		`SELECT id, org_id, deal_id, title, document_type, file_key, file_size, extracted_text, uploaded_by, created_at, updated_at
		 FROM documents WHERE deal_id = ? AND org_id = ? ORDER BY created_at DESC`,
		chi.URLParam(r, "dealID"), k.OrgID)
	if storeError(w, err) {
		return
	}
	defer rows.Close()
	out := []map[string]any{}
	for rows.Next() {
		var id, orgID, dealID, title, docType, fileKey, uploadedBy, createdAt, updatedAt string
		var fileSize int64
		var extracted *string
		if err := rows.Scan(&id, &orgID, &dealID, &title, &docType, &fileKey, &fileSize, &extracted, &uploadedBy, &createdAt, &updatedAt); err != nil {
			storeError(w, err)
			return
		}
		out = append(out, map[string]any{"id": id, "org_id": orgID, "deal_id": dealID, "title": title,
			"document_type": docType, "file_key": fileKey, "file_size": fileSize, "extracted_text": extracted,
			"uploaded_by": uploadedBy, "created_at": createdAt, "updated_at": updatedAt})
	}
	did := chi.URLParam(r, "dealID")
	_ = store.RecordAudit(r.Context(), s.DB, store.Audit{
		OrgID: k.OrgID, Action: "list", ResourceType: "partner",
		ResourceID: &did, DealID: &did,
		Details: map[string]any{"resource": "documents", "count": len(out)},
	})
	writeJSON(w, http.StatusOK, out)
}

func (s *Server) partnerCreateDocument(w http.ResponseWriter, r *http.Request) {
	k := partnerKeyFromCtx(r.Context())
	if !requireScope(w, k, "documents:write") {
		return
	}
	// write endpoints use the org-scoped deal (no share gate), like the Python API
	d, _, err := store.PartnerScopedDeal(r.Context(), s.DB, k.OrgID, chi.URLParam(r, "dealID"))
	if storeError(w, err) {
		return
	}
	var b struct {
		Title         string  `json:"title"`
		DocumentType  string  `json:"document_type"`
		FileKey       string  `json:"file_key"`
		FileSize      int64   `json:"file_size"`
		ExtractedText *string `json:"extracted_text"`
	}
	if err := json.NewDecoder(r.Body).Decode(&b); err != nil || b.Title == "" {
		writeError(w, http.StatusUnprocessableEntity, "title is required")
		return
	}
	id, createdAt, uploadedBy, err := store.CreatePartnerDocument(r.Context(), s.DB, d.OrgID, d.ID, b.Title, b.DocumentType, b.FileKey, b.FileSize, b.ExtractedText)
	if storeError(w, err) {
		return
	}
	docID, did := id, d.ID
	_ = store.RecordAudit(r.Context(), s.DB, store.Audit{
		OrgID: d.OrgID, Action: "create", ResourceType: "partner",
		ResourceID: &docID, DealID: &did,
		Details: map[string]any{"resource": "document", "title": b.Title},
	})
	writeJSON(w, http.StatusCreated, map[string]any{"id": id, "org_id": d.OrgID, "deal_id": d.ID,
		"title": b.Title, "document_type": b.DocumentType, "file_key": b.FileKey, "file_size": b.FileSize,
		"extracted_text": b.ExtractedText, "uploaded_by": uploadedBy, "created_at": createdAt, "updated_at": createdAt})
}

func (s *Server) partnerGetTranscript(w http.ResponseWriter, r *http.Request) {
	k := partnerKeyFromCtx(r.Context())
	if !requireScope(w, k, "transcripts:read") {
		return
	}
	_, c, err := store.PartnerScopedMeeting(r.Context(), s.DB, k.OrgID, chi.URLParam(r, "meetingID"))
	if storeError(w, err) {
		return
	}
	if !requireShare(w, c, "transcripts") {
		return
	}
	var t struct {
		id, orgID, meetingID, fullText, language, createdAt, updatedAt string
		wordCount                                                      int
		confidence                                                     *float64
	}
	err = s.DB.QueryRowContext(r.Context(),
		"SELECT id, org_id, meeting_id, full_text, language, word_count, confidence_score, created_at, updated_at FROM transcripts WHERE meeting_id = ? AND org_id = ?",
		chi.URLParam(r, "meetingID"), k.OrgID).
		Scan(&t.id, &t.orgID, &t.meetingID, &t.fullText, &t.language, &t.wordCount, &t.confidence, &t.createdAt, &t.updatedAt)
	if err == sql.ErrNoRows {
		writeError(w, http.StatusNotFound, "Transcript not found")
		return
	}
	if storeError(w, err) {
		return
	}
	tid := t.id
	_ = store.RecordAudit(r.Context(), s.DB, store.Audit{
		OrgID: k.OrgID, Action: "read", ResourceType: "partner",
		ResourceID: &tid,
		Details: map[string]any{"resource": "transcript", "meeting_id": chi.URLParam(r, "meetingID")},
	})
	writeJSON(w, http.StatusOK, map[string]any{"id": t.id, "org_id": t.orgID, "meeting_id": t.meetingID,
		"full_text": t.fullText, "language": t.language, "word_count": t.wordCount,
		"confidence_score": t.confidence, "created_at": t.createdAt, "updated_at": t.updatedAt})
}

func (s *Server) partnerListAnalyses(w http.ResponseWriter, r *http.Request) {
	k := partnerKeyFromCtx(r.Context())
	if !requireScope(w, k, "transcripts:read") {
		return
	}
	_, c, err := store.PartnerScopedMeeting(r.Context(), s.DB, k.OrgID, chi.URLParam(r, "meetingID"))
	if storeError(w, err) {
		return
	}
	if !requireShare(w, c, "analyses") {
		return
	}
	rows, err := s.DB.QueryContext(r.Context(),
		`SELECT id, org_id, meeting_id, call_type, structured_output, model_used, prompt_version, grounding_score, status, version, created_at, updated_at
		 FROM analyses WHERE meeting_id = ? AND org_id = ? AND status = 'completed' ORDER BY created_at DESC`,
		chi.URLParam(r, "meetingID"), k.OrgID)
	if storeError(w, err) {
		return
	}
	defer rows.Close()
	out := []map[string]any{}
	for rows.Next() {
		var id, orgID, meetingID, callType, modelUsed, promptVer, status, createdAt, updatedAt string
		var structured []byte
		var grounding *float64
		var version int
		if err := rows.Scan(&id, &orgID, &meetingID, &callType, &structured, &modelUsed, &promptVer, &grounding, &status, &version, &createdAt, &updatedAt); err != nil {
			storeError(w, err)
			return
		}
		var so any
		if len(structured) > 0 {
			_ = json.Unmarshal(structured, &so)
		}
		out = append(out, map[string]any{"id": id, "org_id": orgID, "meeting_id": meetingID, "call_type": callType,
			"structured_output": so, "model_used": modelUsed, "prompt_version": promptVer, "grounding_score": grounding,
			"status": status, "version": version, "created_at": createdAt, "updated_at": updatedAt})
	}
	_ = store.RecordAudit(r.Context(), s.DB, store.Audit{
		OrgID: k.OrgID, Action: "list", ResourceType: "partner",
		Details: map[string]any{"resource": "analyses", "meeting_id": chi.URLParam(r, "meetingID"), "count": len(out)},
	})
	writeJSON(w, http.StatusOK, out)
}

type searchHitJSON struct {
	ID         string         `json:"id"`
	SourceType string         `json:"source_type"`
	SourceID   string         `json:"source_id"`
	ChunkText  string         `json:"chunk_text"`
	Similarity float64        `json:"similarity"`
	Metadata   map[string]any `json:"metadata"`
}

// partnerSearch is the CogniVault unblock: the caller sends `query` (text, which
// we embed server-side — the recommended path) OR a raw `query_vector`. Exactly
// one. Then per-deal cosine KNN.
func (s *Server) partnerSearch(w http.ResponseWriter, r *http.Request) {
	k := partnerKeyFromCtx(r.Context())
	if !requireScope(w, k, "search") {
		return
	}
	_, c, err := store.PartnerScopedDeal(r.Context(), s.DB, k.OrgID, chi.URLParam(r, "dealID"))
	if storeError(w, err) {
		return
	}
	if !requireShare(w, c, "search") {
		return
	}
	var b struct {
		Query       string    `json:"query"`
		QueryVector []float32 `json:"query_vector"`
		TopK        int       `json:"top_k"`
	}
	if err := json.NewDecoder(r.Body).Decode(&b); err != nil {
		writeError(w, http.StatusUnprocessableEntity, "Invalid request body")
		return
	}
	hasText := strings.TrimSpace(b.Query) != ""
	hasVec := b.QueryVector != nil
	if hasText == hasVec {
		writeError(w, http.StatusUnprocessableEntity, "provide exactly one of 'query' or 'query_vector'")
		return
	}
	vec := b.QueryVector
	if hasText {
		if s.LLM == nil {
			writeError(w, http.StatusServiceUnavailable, "Search is not available")
			return
		}
		v, err := s.LLM.Embed(r.Context(), b.Query)
		if err != nil {
			writeError(w, http.StatusBadGateway, "Embedding provider unavailable")
			return
		}
		vec = v
	} else if len(b.QueryVector) != db.EmbeddingDim {
		writeError(w, http.StatusUnprocessableEntity, "query_vector must be exactly 768 floats")
		return
	}
	topK := b.TopK
	if topK <= 0 || topK > 100 {
		topK = 15
	}
	hits, err := store.MatchEmbeddingsForDeal(r.Context(), s.DB, chi.URLParam(r, "dealID"), vec, topK, 0.3, nil)
	if storeError(w, err) {
		return
	}
	out := make([]searchHitJSON, 0, len(hits))
	for _, h := range hits {
		md := h.Metadata
		if md == nil {
			md = map[string]any{}
		}
		out = append(out, searchHitJSON{h.ID, h.SourceType, h.SourceID, h.ChunkText, h.Similarity, md})
	}
	did := chi.URLParam(r, "dealID")
	_ = store.RecordAudit(r.Context(), s.DB, store.Audit{
		OrgID: k.OrgID, Action: "search", ResourceType: "partner",
		ResourceID: &did, DealID: &did,
		Details: map[string]any{"resource": "search", "hits": len(out)},
	})
	writeJSON(w, http.StatusOK, out)
}
