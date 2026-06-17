package store

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/model"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/util"
)

// qa.go ports the qa_interactions reads/writes (app/api/v1/qa.py persistence +
// history). Every query is org-scoped via the Principal / the scoped deal's
// org_id; a missing scope would leak another tenant's Q&A history. The deal
// itself is org-checked by the caller (ScopedDeal) before any of these run.

// DealOrgIDScoped returns the deal's org_id only when the principal belongs to
// it, else ErrNotFound — a foreign/missing/soft-deleted deal is a 404 (ports the
// _require_deal_access guard in app/api/v1/qa.py).
func DealOrgIDScoped(ctx context.Context, conn *sql.DB, p *Principal, dealID string) (string, error) {
	d, err := ScopedDeal(ctx, conn, p, dealID)
	if err != nil {
		return "", err
	}
	return d.OrgID, nil
}

// MeetingsInDeal reports whether every meetingID belongs to dealID (ports
// _require_meetings_in_deal). The deal is already org-checked by the caller, so
// child-of-deal membership is enough to keep the scope tenant-safe. Returns
// ErrNotFound if any requested meeting is missing or belongs to another deal.
func MeetingsInDeal(ctx context.Context, conn *sql.DB, dealID string, meetingIDs []string) error {
	if len(meetingIDs) == 0 {
		return nil
	}
	ph := make([]string, len(meetingIDs))
	args := make([]any, 0, len(meetingIDs)+1)
	args = append(args, dealID)
	for i, m := range meetingIDs {
		ph[i] = "?"
		args = append(args, m)
	}
	rows, err := conn.QueryContext(ctx,
		"SELECT id FROM meetings WHERE deal_id = ? AND id IN ("+joinComma(ph)+")", args...)
	if err != nil {
		return err
	}
	defer rows.Close()
	valid := map[string]bool{}
	for rows.Next() {
		var id string
		if err := rows.Scan(&id); err != nil {
			return err
		}
		valid[id] = true
	}
	if err := rows.Err(); err != nil {
		return err
	}
	for _, m := range meetingIDs {
		if !valid[m] {
			return ErrNotFound
		}
	}
	return nil
}

func joinComma(xs []string) string {
	out := ""
	for i, x := range xs {
		if i > 0 {
			out += ","
		}
		out += x
	}
	return out
}

// QAPersist is the payload for recording a Q&A interaction.
type QAPersist struct {
	OrgID          string
	DealID         string
	MeetingID      *string
	UserID         string
	Question       string
	Answer         string
	Citations      []model.QACitation
	GroundingScore *float64
	ModelUsed      string
}

// CreateQAInteraction inserts a qa_interactions row and returns it (ports
// _persist_interaction). Citations are stored as JSON in the canonical
// {source_type, source_id, text_excerpt, timestamp} shape. The caller is
// responsible for org-scoping (OrgID is derived from the already-scoped deal).
func CreateQAInteraction(ctx context.Context, conn *sql.DB, in QAPersist) (*model.QAInteraction, error) {
	citations := in.Citations
	if citations == nil {
		citations = []model.QACitation{}
	}
	blob, err := json.Marshal(citations)
	if err != nil {
		return nil, err
	}
	id := util.NewUUID()
	now := util.NowISO()
	_, err = conn.ExecContext(ctx,
		`INSERT INTO qa_interactions(
		    id, org_id, deal_id, meeting_id, user_id, question, answer,
		    citations, grounding_score, model_used, created_at)
		 VALUES (?,?,?,?,?,?,?,?,?,?,?)`,
		id, in.OrgID, in.DealID, in.MeetingID, in.UserID, in.Question, in.Answer,
		string(blob), in.GroundingScore, in.ModelUsed, now)
	if err != nil {
		return nil, err
	}
	return &model.QAInteraction{
		ID: id, OrgID: in.OrgID, DealID: in.DealID, MeetingID: in.MeetingID,
		UserID: in.UserID, Question: in.Question, Answer: in.Answer,
		Citations: citations, GroundingScore: in.GroundingScore,
		ModelUsed: in.ModelUsed, CreatedAt: now,
	}, nil
}

// scanQAInteraction reads a full qa_interactions row, tolerating legacy citation
// JSON: extra keys (chunk_id/relevance/metadata) are ignored on decode so the
// history endpoint never fails on older rows (mirrors the Citation schema's
// extra="ignore").
func scanQAInteraction(row interface{ Scan(...any) error }) (*model.QAInteraction, error) {
	var q model.QAInteraction
	var citations []byte
	if err := row.Scan(&q.ID, &q.OrgID, &q.DealID, &q.MeetingID, &q.UserID,
		&q.Question, &q.Answer, &citations, &q.GroundingScore, &q.ModelUsed, &q.CreatedAt); err != nil {
		return nil, err
	}
	if len(citations) > 0 {
		_ = json.Unmarshal(citations, &q.Citations)
	}
	if q.Citations == nil {
		q.Citations = []model.QACitation{}
	}
	return &q, nil
}

const qaCols = "id, org_id, deal_id, meeting_id, user_id, question, answer, citations, grounding_score, model_used, created_at"

// GetQAInteraction returns a single interaction scoped to a deal, else
// ErrNotFound (ports get_qa_interaction). The deal must already be org-checked
// by the caller; the deal_id filter keeps the row within the caller's tenant.
func GetQAInteraction(ctx context.Context, conn *sql.DB, dealID, interactionID string) (*model.QAInteraction, error) {
	q, err := scanQAInteraction(conn.QueryRowContext(ctx,
		"SELECT "+qaCols+" FROM qa_interactions WHERE id = ? AND deal_id = ?",
		interactionID, dealID))
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	return q, err
}

// ListQAHistory returns a deal's Q&A history newest-first with a composite
// (created_at|id) cursor (ports get_qa_history). The deal must already be
// org-checked by the caller; the deal_id filter keeps the page within the
// caller's tenant. limit is clamped to 1..100; the cursor falls back to the
// legacy created_at-only form for older URLs.
func ListQAHistory(ctx context.Context, conn *sql.DB, dealID, cursor string, limit int) (items []model.QAInteraction, nextCursor *string, hasMore bool, err error) {
	if limit < 1 || limit > 100 {
		limit = 25
	}
	where := "deal_id = ?"
	args := []any{dealID}
	if cursor != "" {
		// Composite (created_at, id) cursor — see ListDeals; falls back to the
		// legacy created_at-only cursor for older URLs.
		if i := lastIndexByte(cursor, '|'); i >= 0 {
			where += " AND (created_at, id) < (?, ?)"
			args = append(args, cursor[:i], cursor[i+1:])
		} else {
			where += " AND created_at < ?"
			args = append(args, cursor)
		}
	}
	q := "SELECT " + qaCols + " FROM qa_interactions WHERE " + where +
		" ORDER BY created_at DESC, id DESC LIMIT ?"
	args = append(args, limit+1)

	rows, err := conn.QueryContext(ctx, q, args...)
	if err != nil {
		return nil, nil, false, err
	}
	defer rows.Close()
	out := make([]model.QAInteraction, 0, limit)
	for rows.Next() {
		r, err := scanQAInteraction(rows)
		if err != nil {
			return nil, nil, false, err
		}
		out = append(out, *r)
	}
	if err := rows.Err(); err != nil {
		return nil, nil, false, err
	}

	hasMore = len(out) > limit
	if hasMore {
		out = out[:limit]
	}
	if hasMore && len(out) > 0 {
		last := out[len(out)-1]
		c := last.CreatedAt + "|" + last.ID
		nextCursor = &c
	}
	return out, nextCursor, hasMore, nil
}

func lastIndexByte(s string, b byte) int {
	for i := len(s) - 1; i >= 0; i-- {
		if s[i] == b {
			return i
		}
	}
	return -1
}

// QASegment carries the transcript-segment fields the Q&A service needs:
// speaker-attributed text (for full-transcript stuffing) plus the segment id +
// start_time (for citation enrichment and the per-meeting RAG allowlist).
type QASegment struct {
	ID           string
	SpeakerLabel string
	SpeakerName  *string
	Text         string
	StartTime    float64
}

// MeetingFinalizedSegments returns a meeting's finalized (non-partial) transcript
// segments ordered by start_time. Live partials are excluded (they are not
// embedded). Tenant isolation is via the parent meeting, which the caller
// org-scopes before calling this.
func MeetingFinalizedSegments(ctx context.Context, conn *sql.DB, meetingID string) ([]QASegment, error) {
	rows, err := conn.QueryContext(ctx,
		`SELECT id, speaker_label, speaker_name, text, start_time
		 FROM transcript_segments
		 WHERE meeting_id = ? AND is_partial = 0
		 ORDER BY start_time`, meetingID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []QASegment
	for rows.Next() {
		var s QASegment
		if err := rows.Scan(&s.ID, &s.SpeakerLabel, &s.SpeakerName, &s.Text, &s.StartTime); err != nil {
			return nil, err
		}
		out = append(out, s)
	}
	return out, rows.Err()
}

// MeetingSegmentIDs returns the ids of every finalized transcript segment across
// the given meetings (ports the source_id allowlist in QAService._ask_rag).
// Transcript embeddings store source_id = TranscriptSegment.id (not the meeting
// id), so the RAG matcher allowlist is segment ids, not meeting ids.
func MeetingSegmentIDs(ctx context.Context, conn *sql.DB, meetingIDs []string) ([]string, error) {
	if len(meetingIDs) == 0 {
		return nil, nil
	}
	ph := make([]string, len(meetingIDs))
	args := make([]any, len(meetingIDs))
	for i, m := range meetingIDs {
		ph[i] = "?"
		args[i] = m
	}
	rows, err := conn.QueryContext(ctx,
		"SELECT id FROM transcript_segments WHERE is_partial = 0 AND meeting_id IN ("+joinComma(ph)+")", args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []string
	for rows.Next() {
		var id string
		if err := rows.Scan(&id); err != nil {
			return nil, err
		}
		out = append(out, id)
	}
	return out, rows.Err()
}

// SegmentMeta is a transcript-segment's meeting_id + start_time, used to enrich
// transcript citations with a link target (ports the seg_rows enrichment query).
type SegmentMeta struct {
	MeetingID string
	StartTime float64
}

// SegmentsMeta resolves segment ids to their meeting_id + start_time in one query
// (ports the batched citation-enrichment query in QAService._ask_rag).
func SegmentsMeta(ctx context.Context, conn *sql.DB, segmentIDs []string) (map[string]SegmentMeta, error) {
	out := map[string]SegmentMeta{}
	if len(segmentIDs) == 0 {
		return out, nil
	}
	ph := make([]string, len(segmentIDs))
	args := make([]any, len(segmentIDs))
	for i, id := range segmentIDs {
		ph[i] = "?"
		args[i] = id
	}
	rows, err := conn.QueryContext(ctx,
		"SELECT id, meeting_id, start_time FROM transcript_segments WHERE id IN ("+joinComma(ph)+")", args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	for rows.Next() {
		var id string
		var meta SegmentMeta
		if err := rows.Scan(&id, &meta.MeetingID, &meta.StartTime); err != nil {
			return nil, err
		}
		out[id] = meta
	}
	return out, rows.Err()
}

// QADocBlock is a document's extracted text for full-corpus stuffing.
type QADocBlock struct {
	ID            string
	Title         string
	ExtractedText *string
}

// DealDocuments returns a deal's documents (id, title, extracted_text) for the
// full-corpus Q&A path (ports the document half of _fetch_deal_corpus). Tenant
// isolation is via the deal, which the caller org-scopes first.
func DealDocuments(ctx context.Context, conn *sql.DB, dealID string) ([]QADocBlock, error) {
	rows, err := conn.QueryContext(ctx,
		"SELECT id, title, extracted_text FROM documents WHERE deal_id = ?", dealID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []QADocBlock
	for rows.Next() {
		var d QADocBlock
		if err := rows.Scan(&d.ID, &d.Title, &d.ExtractedText); err != nil {
			return nil, err
		}
		out = append(out, d)
	}
	return out, rows.Err()
}

// QAMeetingRow is a meeting's id/title/date for the full-corpus Q&A path.
type QAMeetingRow struct {
	ID          string
	Title       string
	MeetingDate *string
	CreatedAt   string
}

// DealMeetingsForCorpus returns a deal's meetings ordered by (meeting_date,
// created_at) for the full-corpus Q&A path (ports the meeting half of
// _fetch_deal_corpus). When meetingIDs is non-empty the result is narrowed to
// those meetings. Tenant isolation is via the deal, which the caller org-scopes
// first.
func DealMeetingsForCorpus(ctx context.Context, conn *sql.DB, dealID string, meetingIDs []string) ([]QAMeetingRow, error) {
	where := "deal_id = ?"
	args := []any{dealID}
	if len(meetingIDs) > 0 {
		ph := make([]string, len(meetingIDs))
		for i, m := range meetingIDs {
			ph[i] = "?"
			args = append(args, m)
		}
		where += " AND id IN (" + joinComma(ph) + ")"
	}
	rows, err := conn.QueryContext(ctx,
		"SELECT id, title, meeting_date, created_at FROM meetings WHERE "+where+
			" ORDER BY meeting_date, created_at", args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []QAMeetingRow
	for rows.Next() {
		var m QAMeetingRow
		if err := rows.Scan(&m.ID, &m.Title, &m.MeetingDate, &m.CreatedAt); err != nil {
			return nil, err
		}
		out = append(out, m)
	}
	return out, rows.Err()
}
