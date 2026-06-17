package store

import (
	"context"
	"database/sql"
	"errors"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/util"
)

// MeetingIDForBot maps a Recall bot_id to its meeting via meeting_bot_sessions
// (ports _session_for_bot + the meeting_id read). Returns ("", nil) when no bot
// session matches or the session has no meeting — both are non-fatal "unknown
// bot" cases the webhook ACKs without error.
//
// This is the live-ingest path and is keyed by the bot id Recall owns, so it is
// not org-scoped through a Principal — the webhook is unauthenticated machine
// traffic, and the meeting it resolves is whatever the bot was booked into. The
// SSE side enforces tenant isolation before any of these rows are streamed.
func MeetingIDForBot(ctx context.Context, conn *sql.DB, botID string) (string, error) {
	if botID == "" {
		return "", nil
	}
	var meetingID sql.NullString
	err := conn.QueryRowContext(ctx,
		`SELECT meeting_id FROM meeting_bot_sessions WHERE recall_bot_id = ? LIMIT 1`, botID).
		Scan(&meetingID)
	if errors.Is(err, sql.ErrNoRows) {
		return "", nil
	}
	if err != nil {
		return "", err
	}
	return meetingID.String, nil
}

// SegmentUpsert is the normalized transcript-segment row written by the Recall
// webhook (ports the `row` dict in recall_webhooks._handle_transcript).
type SegmentUpsert struct {
	MeetingID       string
	RecallSegmentID string
	SpeakerLabel    string
	SpeakerName     *string
	Text            string
	StartTime       float64
	EndTime         float64
	Confidence      *float64
	SegmentIndex    int
	IsPartial       bool
}

// UpsertTranscriptSegment inserts or replaces a transcript_segments row keyed on
// recall_segment_id (ports the SELECT→update-or-insert in _handle_transcript), so
// a partial gets replaced in place by its finalized text instead of inserting a
// new row. transcript_segments has a partial unique index on recall_segment_id.
func UpsertTranscriptSegment(ctx context.Context, conn *sql.DB, row SegmentUpsert) error {
	now := util.NowISO()
	// Serialize the read-modify-write in one transaction: two concurrent webhook
	// deliveries for the same recall_segment_id must not both observe "no row" and
	// double-insert (the partial unique index would reject the loser, surfacing a
	// 500 on otherwise-valid live traffic). With _txlock=immediate the write lock
	// is taken at BEGIN, so the second caller waits out busy_timeout for the first
	// to commit instead of racing it.
	tx, err := conn.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback() }() // no-op once Commit has succeeded

	var existingID string
	err = tx.QueryRowContext(ctx,
		`SELECT id FROM transcript_segments WHERE recall_segment_id = ? LIMIT 1`,
		row.RecallSegmentID).Scan(&existingID)
	switch {
	case errors.Is(err, sql.ErrNoRows):
		if _, err = tx.ExecContext(ctx,
			`INSERT INTO transcript_segments
			   (id, meeting_id, recall_segment_id, speaker_label, speaker_name, text,
			    start_time, end_time, confidence, segment_index, is_partial, created_at, updated_at)
			 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)`,
			util.NewUUID(), row.MeetingID, row.RecallSegmentID, row.SpeakerLabel, row.SpeakerName,
			row.Text, row.StartTime, row.EndTime, row.Confidence, row.SegmentIndex, row.IsPartial, now, now); err != nil {
			return err
		}
	case err != nil:
		return err
	default:
		if _, err = tx.ExecContext(ctx,
			`UPDATE transcript_segments
			   SET meeting_id = ?, speaker_label = ?, speaker_name = ?, text = ?,
			       start_time = ?, end_time = ?, confidence = ?, segment_index = ?,
			       is_partial = ?, updated_at = ?
			 WHERE id = ?`,
			row.MeetingID, row.SpeakerLabel, row.SpeakerName, row.Text,
			row.StartTime, row.EndTime, row.Confidence, row.SegmentIndex, row.IsPartial, now, existingID); err != nil {
			return err
		}
	}
	return tx.Commit()
}
