package httpapi

import (
	"encoding/json"
	"net/http"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/model"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/store"
	"github.com/go-chi/chi/v5"
)

// documentJSON is the wire shape (matches DocumentResponse in
// app/api/v1/store/documents.py). Used for list + create responses.
type documentJSON struct {
	ID           string `json:"id"`
	OrgID        string `json:"org_id"`
	DealID       string `json:"deal_id"`
	Title        string `json:"title"`
	DocumentType string `json:"document_type"`
	FileKey      string `json:"file_key"`
	FileSize     int64  `json:"file_size"`
	UploadedBy   string `json:"uploaded_by"`
	CreatedAt    string `json:"created_at"`
	UpdatedAt    string `json:"updated_at"`
}

func toDocumentJSON(d *model.Document) documentJSON {
	return documentJSON{d.ID, d.OrgID, d.DealID, d.Title, d.DocumentType, d.FileKey,
		d.FileSize, d.UploadedBy, d.CreatedAt, d.UpdatedAt}
}

// documentDetailJSON matches DocumentDetailResponse (DocumentResponse +
// extracted_text). Used for the single-get response.
type documentDetailJSON struct {
	documentJSON
	ExtractedText *string `json:"extracted_text"`
}

func toDocumentDetailJSON(d *model.Document) documentDetailJSON {
	return documentDetailJSON{toDocumentJSON(d), d.ExtractedText}
}

// RegisterDocuments mounts the documents routes (all auth-required). Flat chi
// patterns sharing the /deals/{dealID}/... prefix with the deals resource.
func (s *Server) RegisterDocuments(r chi.Router) {
	r.Get("/deals/{dealID}/documents", s.listDocuments)
	r.Post("/deals/{dealID}/documents", s.createDocument)
	r.Get("/documents/{documentID}", s.getDocument)
}

func (s *Server) listDocuments(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	// Gate on the parent deal: ScopedDeal 404s a missing/foreign deal.
	if _, err := store.ScopedDeal(r.Context(), s.DB, p, chi.URLParam(r, "dealID")); storeError(w, err) {
		return
	}
	docs, err := store.ListDocuments(r.Context(), s.DB, chi.URLParam(r, "dealID"))
	if storeError(w, err) {
		return
	}
	out := make([]documentJSON, 0, len(docs))
	for i := range docs {
		out = append(out, toDocumentJSON(&docs[i]))
	}
	writeJSON(w, http.StatusOK, out)
}

func (s *Server) getDocument(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	d, err := store.ScopedDocument(r.Context(), s.DB, p, chi.URLParam(r, "documentID"))
	if storeError(w, err) {
		return
	}
	writeJSON(w, http.StatusOK, toDocumentDetailJSON(d))
}

type documentCreateBody struct {
	Title        string `json:"title"`
	DocumentType string `json:"document_type"`
	FileKey      string `json:"file_key"`
	FileSize     int64  `json:"file_size"`
}

func (s *Server) createDocument(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	deal, err := store.ScopedDeal(r.Context(), s.DB, p, chi.URLParam(r, "dealID"))
	if storeError(w, err) {
		return
	}
	var b documentCreateBody
	if err := json.NewDecoder(r.Body).Decode(&b); err != nil || b.Title == "" || b.DocumentType == "" || b.FileKey == "" {
		writeError(w, http.StatusUnprocessableEntity, "title, document_type and file_key are required")
		return
	}
	doc, err := store.CreateDocument(r.Context(), s.DB, deal, p.UserID, store.DocumentCreate{
		Title: b.Title, DocumentType: b.DocumentType, FileKey: b.FileKey, FileSize: b.FileSize,
	})
	if storeError(w, err) {
		return
	}
	writeJSON(w, http.StatusCreated, toDocumentJSON(doc))
}
