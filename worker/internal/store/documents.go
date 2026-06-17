package store

import (
	"context"
	"database/sql"
	"errors"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/model"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/util"
)

const documentCols = "id, org_id, deal_id, title, document_type, file_key, file_size, extracted_text, uploaded_by, created_at, updated_at"

func scanDocument(row interface{ Scan(...any) error }) (*model.Document, error) {
	var d model.Document
	err := row.Scan(&d.ID, &d.OrgID, &d.DealID, &d.Title, &d.DocumentType, &d.FileKey,
		&d.FileSize, &d.ExtractedText, &d.UploadedBy, &d.CreatedAt, &d.UpdatedAt)
	return &d, err
}

// ListDocuments returns the documents for a deal, newest-first (ports
// list_documents). The caller must have already verified the deal is in the
// principal's org (via ScopedDeal) — list/create are gated on the parent deal.
func ListDocuments(ctx context.Context, conn *sql.DB, dealID string) ([]model.Document, error) {
	rows, err := conn.QueryContext(ctx,
		"SELECT "+documentCols+" FROM documents WHERE deal_id = ? ORDER BY created_at DESC", dealID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []model.Document
	for rows.Next() {
		d, err := scanDocument(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, *d)
	}
	return out, rows.Err()
}

// ScopedDocument returns a document the principal's org owns, else ErrNotFound
// (ports get_document: a missing row or one in a foreign org is a 404). The
// org_id filter is the tenant guard — a missing scope would leak cross-tenant.
func ScopedDocument(ctx context.Context, conn *sql.DB, p *Principal, documentID string) (*model.Document, error) {
	pred, args := p.OrgFilter("org_id")
	q := "SELECT " + documentCols + " FROM documents WHERE id = ? AND " + pred
	d, err := scanDocument(conn.QueryRowContext(ctx, q, append([]any{documentID}, args...)...))
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	return d, err
}

// DocumentCreate is the create payload (ports DocumentCreate).
type DocumentCreate struct {
	Title        string
	DocumentType string
	FileKey      string
	FileSize     int64
}

// CreateDocument inserts a document under the given deal. The caller must have
// already resolved the deal via ScopedDeal so org_id/deal_id are trusted.
func CreateDocument(ctx context.Context, conn *sql.DB, deal *model.Deal, uploadedBy string, in DocumentCreate) (*model.Document, error) {
	now, id := util.NowISO(), util.NewUUID()
	if _, err := conn.ExecContext(ctx,
		"INSERT INTO documents("+documentCols+") VALUES (?,?,?,?,?,?,?,?,?,?,?)",
		id, deal.OrgID, deal.ID, in.Title, in.DocumentType, in.FileKey, in.FileSize, nil, uploadedBy, now, now); err != nil {
		return nil, err
	}
	return ScopedDocumentByID(ctx, conn, id)
}

// ScopedDocumentByID re-reads a freshly written document by id (no scope filter;
// only called with an id the worker just inserted into a scoped deal).
func ScopedDocumentByID(ctx context.Context, conn *sql.DB, id string) (*model.Document, error) {
	d, err := scanDocument(conn.QueryRowContext(ctx,
		"SELECT "+documentCols+" FROM documents WHERE id = ?", id))
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	return d, err
}
