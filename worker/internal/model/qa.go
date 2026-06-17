package model

// QAInteraction is one qa_interactions row (ports app/db/models.py
// QAInteraction). One per question asked against a deal (optionally scoped to a
// meeting). citations is persisted as JSON in the canonical Citation shape
// (source_type, source_id, text_excerpt, timestamp). Nullable columns are
// pointer types. created_at is an ISO-8601 string (CreatedAt mixin).
type QAInteraction struct {
	ID             string
	OrgID          string
	DealID         string
	MeetingID      *string
	UserID         string
	Question       string
	Answer         string
	Citations      []QACitation
	GroundingScore *float64
	ModelUsed      string
	CreatedAt      string
}

// QACitation is the CANONICAL persisted + returned citation shape. The Python
// schema (app/schemas/qa.py Citation) forbids the richer chunk_id/relevance/
// metadata keys — those were a persistence bug. SourceType is
// transcript_segment | document_chunk; Timestamp is the segment start time for
// transcript citations (null otherwise).
type QACitation struct {
	SourceType  string   `json:"source_type"`
	SourceID    string   `json:"source_id"`
	TextExcerpt string   `json:"text_excerpt"`
	Timestamp   *float64 `json:"timestamp"`
}
