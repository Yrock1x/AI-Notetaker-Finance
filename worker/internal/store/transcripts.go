package store

import (
	"context"
	"database/sql"
	"errors"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/model"
)

// scopedMeetingID resolves a meeting the principal's org owns, returning its id,
// else ErrNotFound (ports scoped_meeting_or_404: a missing row or one in a
// foreign org is a 404). The org_id filter is the tenant guard — transcript /
// segment / participant / chat rows hang off a meeting and (for segments and
// participants) carry no org_id of their own, so a missing scope here would
// silently leak cross-tenant data.
func scopedMeetingID(ctx context.Context, conn *sql.DB, p *Principal, meetingID string) error {
	pred, args := p.OrgFilter("org_id")
	q := "SELECT id FROM meetings WHERE id = ? AND " + pred
	var id string
	err := conn.QueryRowContext(ctx, q, append([]any{meetingID}, args...)...).Scan(&id)
	if errors.Is(err, sql.ErrNoRows) {
		return ErrNotFound
	}
	return err
}

const transcriptCols = "id, org_id, meeting_id, full_text, language, word_count, confidence_score, created_at, updated_at"

func scanTranscript(row interface{ Scan(...any) error }) (*model.Transcript, error) {
	var t model.Transcript
	err := row.Scan(&t.ID, &t.OrgID, &t.MeetingID, &t.FullText, &t.Language,
		&t.WordCount, &t.ConfidenceScore, &t.CreatedAt, &t.UpdatedAt)
	return &t, err
}

// GetTranscript returns the meeting's transcript (ports get_transcript). The
// meeting is first org-scoped (ErrNotFound on a missing/foreign meeting); a
// scoped meeting with no transcript row also yields ErrNotFound.
func GetTranscript(ctx context.Context, conn *sql.DB, p *Principal, meetingID string) (*model.Transcript, error) {
	if err := scopedMeetingID(ctx, conn, p, meetingID); err != nil {
		return nil, err
	}
	q := "SELECT " + transcriptCols + " FROM transcripts WHERE meeting_id = ?"
	t, err := scanTranscript(conn.QueryRowContext(ctx, q, meetingID))
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	return t, err
}

const segmentCols = "id, transcript_id, meeting_id, speaker_label, speaker_name, text, start_time, end_time, confidence, segment_index, is_partial, created_at, updated_at"

func scanSegment(row interface{ Scan(...any) error }) (*model.TranscriptSegment, error) {
	var s model.TranscriptSegment
	err := row.Scan(&s.ID, &s.TranscriptID, &s.MeetingID, &s.SpeakerLabel, &s.SpeakerName,
		&s.Text, &s.StartTime, &s.EndTime, &s.Confidence, &s.SegmentIndex, &s.IsPartial,
		&s.CreatedAt, &s.UpdatedAt)
	return &s, err
}

// SegmentFilters are the list query params (ports list_transcript_segments).
type SegmentFilters struct {
	Speaker string
	Q       string
	Limit   int
}

// ListTranscriptSegments returns the meeting's finalized (non-partial) segments
// ordered by start_time (ports list_transcript_segments). The meeting is first
// org-scoped (ErrNotFound on a missing/foreign meeting).
func ListTranscriptSegments(ctx context.Context, conn *sql.DB, p *Principal, meetingID string, f SegmentFilters) ([]model.TranscriptSegment, error) {
	if err := scopedMeetingID(ctx, conn, p, meetingID); err != nil {
		return nil, err
	}
	where := "meeting_id = ? AND is_partial = 0"
	args := []any{meetingID}
	if f.Speaker != "" {
		where += " AND speaker_label = ?"
		args = append(args, f.Speaker)
	}
	if f.Q != "" {
		where += " AND text LIKE ?"
		args = append(args, "%"+f.Q+"%")
	}
	limit := f.Limit
	if limit < 1 || limit > 500 {
		limit = 200
	}
	q := "SELECT " + segmentCols + " FROM transcript_segments WHERE " + where + " ORDER BY start_time LIMIT ?"
	args = append(args, limit)

	rows, err := conn.QueryContext(ctx, q, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]model.TranscriptSegment, 0)
	for rows.Next() {
		s, err := scanSegment(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, *s)
	}
	return out, rows.Err()
}

const participantCols = "id, meeting_id, speaker_label, speaker_name, user_id, email_address, joined_at, left_at, created_at, updated_at"

func scanParticipant(row interface{ Scan(...any) error }) (*model.MeetingParticipant, error) {
	var pt model.MeetingParticipant
	err := row.Scan(&pt.ID, &pt.MeetingID, &pt.SpeakerLabel, &pt.SpeakerName, &pt.UserID,
		&pt.EmailAddress, &pt.JoinedAt, &pt.LeftAt, &pt.CreatedAt, &pt.UpdatedAt)
	return &pt, err
}

// ListParticipants returns the meeting's participants, NULL joined_at last then
// by joined_at (ports list_participants). The meeting is first org-scoped.
func ListParticipants(ctx context.Context, conn *sql.DB, p *Principal, meetingID string) ([]model.MeetingParticipant, error) {
	if err := scopedMeetingID(ctx, conn, p, meetingID); err != nil {
		return nil, err
	}
	q := "SELECT " + participantCols + " FROM meeting_participants WHERE meeting_id = ? " +
		"ORDER BY (joined_at IS NULL), joined_at"
	rows, err := conn.QueryContext(ctx, q, meetingID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]model.MeetingParticipant, 0)
	for rows.Next() {
		pt, err := scanParticipant(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, *pt)
	}
	return out, rows.Err()
}

const chatCols = "id, meeting_id, org_id, sender_name, sender_email, text, sent_at, created_at"

func scanChatMessage(row interface{ Scan(...any) error }) (*model.MeetingChatMessage, error) {
	var c model.MeetingChatMessage
	err := row.Scan(&c.ID, &c.MeetingID, &c.OrgID, &c.SenderName, &c.SenderEmail,
		&c.Text, &c.SentAt, &c.CreatedAt)
	return &c, err
}

// ListChat returns the meeting's chat messages ordered by sent_at, capped at 500
// (ports list_chat). The meeting is first org-scoped.
func ListChat(ctx context.Context, conn *sql.DB, p *Principal, meetingID string) ([]model.MeetingChatMessage, error) {
	if err := scopedMeetingID(ctx, conn, p, meetingID); err != nil {
		return nil, err
	}
	q := "SELECT " + chatCols + " FROM meeting_chat_messages WHERE meeting_id = ? ORDER BY sent_at LIMIT 500"
	rows, err := conn.QueryContext(ctx, q, meetingID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]model.MeetingChatMessage, 0)
	for rows.Next() {
		c, err := scanChatMessage(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, *c)
	}
	return out, rows.Err()
}
