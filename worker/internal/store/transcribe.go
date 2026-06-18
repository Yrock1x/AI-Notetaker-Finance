package store

import (
	"context"
	"database/sql"
	"errors"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/util"
)

// MeetingFile returns a meeting's org_id + file_key for the transcribe path
// (ports the session.get(Meeting) + file_key read in transcribe_meeting). Not
// org-scoped: /internal/* is service-to-service (X-Internal-Token) and the
// meeting id comes from the worker's own Inngest pipeline. ErrNotFound if the
// meeting is missing.
func MeetingFile(ctx context.Context, conn *sql.DB, meetingID string) (orgID string, fileKey *string, err error) {
	err = conn.QueryRowContext(ctx,
		"SELECT org_id, file_key FROM meetings WHERE id = ?", meetingID).Scan(&orgID, &fileKey)
	if errors.Is(err, sql.ErrNoRows) {
		return "", nil, ErrNotFound
	}
	return orgID, fileKey, err
}

// SetMeetingStatus flips a meeting's status (and optionally records an error)
// as an Inngest pipeline step progresses or fails (ports set_meeting_status).
// ErrNotFound if the meeting doesn't exist.
func SetMeetingStatus(ctx context.Context, conn *sql.DB, meetingID, status string, errMsg *string) error {
	now := util.NowISO()
	var res sql.Result
	var err error
	if errMsg != nil {
		res, err = conn.ExecContext(ctx,
			"UPDATE meetings SET status = ?, error_message = ?, updated_at = ? WHERE id = ?",
			status, *errMsg, now, meetingID)
	} else {
		res, err = conn.ExecContext(ctx,
			"UPDATE meetings SET status = ?, updated_at = ? WHERE id = ?",
			status, now, meetingID)
	}
	if err != nil {
		return err
	}
	if n, _ := res.RowsAffected(); n == 0 {
		return ErrNotFound
	}
	return nil
}

// TranscriptSegmentInput is one finalized, speaker-attributed segment to persist
// (the store-layer mirror of deepgram.Segment, so the store doesn't depend on the
// integrations package).
type TranscriptSegmentInput struct {
	SpeakerLabel string
	SpeakerName  string
	Text         string
	StartTime    float64
	EndTime      float64
	Confidence   float64
	SegmentIndex int
}

// TranscriptInput is the full transcript write for a meeting.
type TranscriptInput struct {
	OrgID            string
	MeetingID        string
	FullText         string
	Language         string
	DeepgramResponse []byte // stored verbatim in the JSON column (nil -> NULL)
	WordCount        int
	ConfidenceScore  *float64
	Segments         []TranscriptSegmentInput
}

// SaveTranscript upserts the transcript row (keyed on the unique meeting_id),
// deletes any prior FINALIZED segments, and inserts the new finalized segments —
// all in one transaction so a partial write can't leave a half-replaced
// transcript (ports the transcript + segment writes in transcribe_meeting).
// Live-streamed partials (is_partial=1) are left untouched; the bot's matching
// recall_segment_id upserts replace them. Returns the transcript id + count.
func SaveTranscript(ctx context.Context, conn *sql.DB, in TranscriptInput) (string, int, error) {
	tx, err := conn.BeginTx(ctx, nil)
	if err != nil {
		return "", 0, err
	}
	defer func() { _ = tx.Rollback() }() // no-op once Commit succeeds

	now := util.NowISO()
	var dgResp any
	if len(in.DeepgramResponse) > 0 {
		dgResp = string(in.DeepgramResponse)
	}

	var transcriptID string
	err = tx.QueryRowContext(ctx,
		"SELECT id FROM transcripts WHERE meeting_id = ?", in.MeetingID).Scan(&transcriptID)
	switch {
	case errors.Is(err, sql.ErrNoRows):
		transcriptID = util.NewUUID()
		if _, err = tx.ExecContext(ctx,
			`INSERT INTO transcripts(id, org_id, meeting_id, full_text, language,
			    deepgram_response, word_count, confidence_score, created_at, updated_at)
			 VALUES (?,?,?,?,?,?,?,?,?,?)`,
			transcriptID, in.OrgID, in.MeetingID, in.FullText, in.Language,
			dgResp, in.WordCount, in.ConfidenceScore, now, now); err != nil {
			return "", 0, err
		}
	case err != nil:
		return "", 0, err
	default:
		if _, err = tx.ExecContext(ctx,
			`UPDATE transcripts SET full_text = ?, language = ?, deepgram_response = ?,
			    word_count = ?, confidence_score = ?, updated_at = ? WHERE id = ?`,
			in.FullText, in.Language, dgResp, in.WordCount, in.ConfidenceScore, now, transcriptID); err != nil {
			return "", 0, err
		}
	}

	if _, err = tx.ExecContext(ctx,
		"DELETE FROM transcript_segments WHERE meeting_id = ? AND is_partial = 0", in.MeetingID); err != nil {
		return "", 0, err
	}

	for i := range in.Segments {
		s := in.Segments[i]
		var name *string
		if s.SpeakerName != "" {
			name = &s.SpeakerName
		}
		if _, err = tx.ExecContext(ctx,
			`INSERT INTO transcript_segments(id, transcript_id, meeting_id, speaker_label,
			    speaker_name, text, start_time, end_time, confidence, segment_index,
			    is_partial, created_at, updated_at)
			 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)`,
			util.NewUUID(), transcriptID, in.MeetingID, s.SpeakerLabel, name, s.Text,
			s.StartTime, s.EndTime, s.Confidence, s.SegmentIndex, false, now, now); err != nil {
			return "", 0, err
		}
	}

	if err = tx.Commit(); err != nil {
		return "", 0, err
	}
	return transcriptID, len(in.Segments), nil
}
