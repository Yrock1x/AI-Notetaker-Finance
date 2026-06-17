package model

// Document is one documents row (mirrors app/db/models.py Document). Documents
// are owned by a deal (and its org). extracted_text is the only nullable column.
type Document struct {
	ID            string
	OrgID         string
	DealID        string
	Title         string
	DocumentType  string
	FileKey       string
	FileSize      int64
	ExtractedText *string
	UploadedBy    string
	CreatedAt     string
	UpdatedAt     string
}
