package httpapi

import (
	"encoding/json"
	"io"
	"net/http"
	"path/filepath"
	"strconv"
	"time"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/storage"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/store"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/util"
	"github.com/go-chi/chi/v5"
)

// Buckets the frontend may upload into directly (deliverables are server-side).
var uploadableBuckets = map[string]bool{"deal-documents": true, "meeting-recordings": true}

const maxUploadBytes = 5 * 1024 * 1024 * 1024 // 5 GB

// RegisterUploadTicket mounts POST /storage/upload-ticket (auth-required).
func (s *Server) RegisterUploadTicket(r chi.Router) {
	r.Post("/storage/upload-ticket", s.createUploadTicket)
}

// RegisterStorageObjects mounts the signed PUT/GET of objects. These are NOT
// session-authed: a valid signature is itself the capability, so they are
// registered OUTSIDE the requireAuth group. The key may contain "/" so it is a
// trailing wildcard.
func (s *Server) RegisterStorageObjects(r chi.Router) {
	r.Put("/storage/{bucket}/*", s.putObject)
	r.Get("/storage/{bucket}/*", s.getObject)
}

func (s *Server) createUploadTicket(w http.ResponseWriter, r *http.Request) {
	p := principalFromCtx(r.Context())
	var b struct {
		Bucket   string `json:"bucket"`
		DealID   string `json:"deal_id"`
		Filename string `json:"filename"`
	}
	if err := json.NewDecoder(r.Body).Decode(&b); err != nil {
		writeError(w, http.StatusUnprocessableEntity, "Invalid request body")
		return
	}
	if !storage.Buckets[b.Bucket] {
		writeError(w, http.StatusBadRequest, "Unknown bucket")
		return
	}
	if !uploadableBuckets[b.Bucket] {
		writeError(w, http.StatusBadRequest, "Uploads not allowed for this bucket")
		return
	}
	if _, err := store.ScopedDeal(r.Context(), s.DB, p, b.DealID); storeError(w, err) {
		return
	}
	key := b.DealID + "/" + util.NewUUID() + filepath.Ext(b.Filename)
	writeJSON(w, http.StatusOK, map[string]any{
		"bucket":     b.Bucket,
		"key":        key,
		"upload_url": storage.MakeSignedURL(s.Cfg.StorageSigningKeyOrFallback(), b.Bucket, key, "PUT", 3600*time.Second),
		"method":     "PUT",
	})
}

func (s *Server) putObject(w http.ResponseWriter, r *http.Request) {
	bucket, key := chi.URLParam(r, "bucket"), chi.URLParam(r, "*")
	expires, _ := strconv.ParseInt(r.URL.Query().Get("expires"), 10, 64)
	sig := r.URL.Query().Get("sig")
	if !storage.Verify(s.Cfg.StorageSigningKeyOrFallback(), "PUT", bucket, key, expires, sig) {
		writeError(w, http.StatusForbidden, "Invalid or expired signature")
		return
	}
	if cl := r.Header.Get("Content-Length"); cl != "" {
		if n, err := strconv.ParseInt(cl, 10, 64); err == nil && n > maxUploadBytes {
			writeError(w, http.StatusRequestEntityTooLarge, "Upload exceeds maximum allowed size")
			return
		}
	}
	data, err := io.ReadAll(io.LimitReader(r.Body, maxUploadBytes+1))
	if err != nil {
		writeError(w, http.StatusInternalServerError, "read failed")
		return
	}
	if int64(len(data)) > maxUploadBytes {
		writeError(w, http.StatusRequestEntityTooLarge, "Upload exceeds maximum allowed size")
		return
	}
	if err := storage.SaveBytes(s.Cfg.StorageRoot, bucket, key, data); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid object")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"ok": true, "key": key})
}

func (s *Server) getObject(w http.ResponseWriter, r *http.Request) {
	bucket, key := chi.URLParam(r, "bucket"), chi.URLParam(r, "*")
	expires, _ := strconv.ParseInt(r.URL.Query().Get("expires"), 10, 64)
	sig := r.URL.Query().Get("sig")
	if !storage.Verify(s.Cfg.StorageSigningKeyOrFallback(), "GET", bucket, key, expires, sig) {
		writeError(w, http.StatusForbidden, "Invalid or expired signature")
		return
	}
	if !storage.Exists(s.Cfg.StorageRoot, bucket, key) {
		writeError(w, http.StatusNotFound, "Not found")
		return
	}
	path, err := storage.ObjectPath(s.Cfg.StorageRoot, bucket, key)
	if err != nil {
		writeError(w, http.StatusForbidden, "Invalid or expired signature")
		return
	}
	w.Header().Set("Content-Type", "application/octet-stream")
	http.ServeFile(w, r, path)
}
