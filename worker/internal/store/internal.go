package store

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/llm"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/model"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/util"
)

// GetEmbedMeetingRef fetches a meeting's tenant keys by primary key (ports
// session.get(Meeting, id) in the /internal handlers). The /internal/* surface
// is X-Internal-Token authed (a trusted server-to-server caller), so there is no
// Principal to scope by here; the returned org_id/deal_id ARE the tenant boundary
// every derived write is then constrained to. ErrNotFound if the meeting is
// missing.
func GetEmbedMeetingRef(ctx context.Context, conn *sql.DB, meetingID string) (*model.EmbedMeetingRef, error) {
	var m model.EmbedMeetingRef
	err := conn.QueryRowContext(ctx,
		"SELECT id, org_id, deal_id FROM meetings WHERE id = ?", meetingID).
		Scan(&m.ID, &m.OrgID, &m.DealID)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, err
	}
	return &m, nil
}

// FinalizedSegments returns the meeting's finalized (non-partial) transcript
// segments ordered by start_time, in the shape the transcript chunker consumes
// (ports the seg_rows query in embed_meeting). No Principal: the caller already
// resolved the meeting ref; segments carry no org_id of their own, so the
// meeting_id from that ref is the tenant boundary.
func FinalizedSegments(ctx context.Context, conn *sql.DB, meetingID string) ([]llm.Segment, error) {
	rows, err := conn.QueryContext(ctx,
		`SELECT id, speaker_label, speaker_name, text, start_time, end_time
		 FROM transcript_segments
		 WHERE meeting_id = ? AND is_partial = 0
		 ORDER BY start_time`, meetingID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]llm.Segment, 0)
	for rows.Next() {
		var s llm.Segment
		var speakerName *string
		if err := rows.Scan(&s.ID, &s.SpeakerLabel, &speakerName, &s.Text, &s.StartTime, &s.EndTime); err != nil {
			return nil, err
		}
		if speakerName != nil {
			s.SpeakerName = *speakerName
		}
		out = append(out, s)
	}
	return out, rows.Err()
}

// SetDocumentExtractedText writes the extracted text onto a document and commits
// it on its own — mirroring the Python handler that commits the text BEFORE the
// embedding network call so the single SQLite writer lock isn't held across the
// LLM round-trip (which would stall the live-transcript write path).
func SetDocumentExtractedText(ctx context.Context, conn *sql.DB, documentID, extracted string) error {
	_, err := conn.ExecContext(ctx,
		"UPDATE documents SET extracted_text = ?, updated_at = ? WHERE id = ?",
		extracted, util.NowISO(), documentID)
	return err
}

// ReplaceEmbeddings atomically replaces the prior embeddings for (sourceType,
// sourceIDs) with a fresh set: it deletes the prior rows + their vectors, inserts
// the new embeddings rows, and upserts each vector. Mirrors the
// delete-prior-then-insert flow in embed_meeting / process_document. orgID +
// dealID are the meeting's/document's own tenant keys (never caller-supplied), so
// every written row stays inside the source's tenant. Runs in one transaction so
// a re-run can't leave the rows and vectors out of sync. Returns the count of
// embeddings written.
//
// The caller passes chunks (with .Text/.Index/.SourceID/.Metadata) paired
// positionally with their vectors. priorSourceIDs is the allowlist of source_ids
// whose existing embeddings should be cleared first (the meeting's segment ids,
// or the single document id).
func ReplaceEmbeddings(
	ctx context.Context,
	conn *sql.DB,
	orgID, dealID, sourceType string,
	priorSourceIDs []string,
	chunks []llm.Chunk,
	vectors [][]float32,
) (int, error) {
	tx, err := conn.BeginTx(ctx, nil)
	if err != nil {
		return 0, err
	}
	defer func() { _ = tx.Rollback() }()

	// 1. Delete prior embeddings (rows + vectors) for these sources.
	if len(priorSourceIDs) > 0 {
		priorIDs, err := priorEmbeddingIDs(ctx, tx, sourceType, priorSourceIDs)
		if err != nil {
			return 0, err
		}
		for _, eid := range priorIDs {
			if _, err := tx.ExecContext(ctx, "DELETE FROM "+vecTable+" WHERE embedding_id = ?", eid); err != nil {
				return 0, err
			}
			if _, err := tx.ExecContext(ctx, "DELETE FROM embeddings WHERE id = ?", eid); err != nil {
				return 0, err
			}
		}
	}

	// 2. Insert the fresh embeddings rows + their vectors.
	now := util.NowISO()
	count := 0
	for i, c := range chunks {
		id := util.NewUUID()
		meta := c.Metadata
		if meta == nil {
			meta = map[string]any{}
		}
		metaJSON, err := json.Marshal(meta)
		if err != nil {
			return 0, err
		}
		sourceID := c.SourceID
		if _, err := tx.ExecContext(ctx,
			`INSERT INTO embeddings(id, org_id, deal_id, source_type, source_id, chunk_text, chunk_index, metadata, created_at)
			 VALUES (?,?,?,?,?,?,?,?,?)`,
			id, orgID, dealID, sourceType, sourceID, c.Text, c.Index, string(metaJSON), now); err != nil {
			return 0, err
		}
		if i < len(vectors) {
			if err := UpsertVector(ctx, tx, id, dealID, vectors[i]); err != nil {
				return 0, err
			}
		}
		count++
	}

	if err := tx.Commit(); err != nil {
		return 0, err
	}
	return count, nil
}

// priorEmbeddingIDs returns the ids of existing embeddings for (sourceType,
// sourceIDs).
func priorEmbeddingIDs(ctx context.Context, tx *sql.Tx, sourceType string, sourceIDs []string) ([]string, error) {
	ph := make([]string, len(sourceIDs))
	args := make([]any, 0, len(sourceIDs)+1)
	args = append(args, sourceType)
	for i, sid := range sourceIDs {
		ph[i] = "?"
		args = append(args, sid)
	}
	rows, err := tx.QueryContext(ctx,
		"SELECT id FROM embeddings WHERE source_type = ? AND source_id IN ("+joinComma(ph)+")", args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var ids []string
	for rows.Next() {
		var id string
		if err := rows.Scan(&id); err != nil {
			return nil, err
		}
		ids = append(ids, id)
	}
	return ids, rows.Err()
}
