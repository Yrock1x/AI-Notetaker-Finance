package model

// Embedding is one embeddings row (mirrors app/db/models.py Embedding). It owns
// the chunk text + metadata; the 768-dim vector lives in the vec_embeddings
// virtual table keyed by Embedding.ID. Embeddings are owned by a deal (and its
// org). source_type is one of: transcript_segment, document_chunk.
type Embedding struct {
	ID         string
	OrgID      string
	DealID     string
	SourceType string
	SourceID   string
	ChunkText  string
	ChunkIndex int
	Metadata   map[string]any
	CreatedAt  string
}

// EmbedMeetingRef is the minimal meeting row the /internal/embed + /internal/
// analyze handlers need: the tenant keys (org_id, deal_id) the derived rows are
// scoped to. deal_id is nullable — a meeting may not be attached to a deal yet.
type EmbedMeetingRef struct {
	ID     string
	OrgID  string
	DealID *string
}
