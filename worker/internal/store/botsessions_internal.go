package store

import (
	"context"
	"database/sql"
	"errors"
	"time"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/model"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/util"
)

// botsessions_internal.go ports the unscoped (service-to-service) bot-session
// operations the /internal/bot/* handlers need — the get/update/finalize the
// Inngest pipeline calls by session id (no Principal, like the rest of /internal).

// GetBotSession returns a bot session by id, unscoped (ports session.get).
func GetBotSession(ctx context.Context, conn *sql.DB, id string) (*model.MeetingBotSession, error) {
	q := "SELECT " + botSessionCols + " FROM meeting_bot_sessions WHERE id = ?"
	b, err := scanBotSession(conn.QueryRowContext(ctx, q, id))
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	return b, err
}

var botPlatformSource = map[string]string{"zoom": "zoom", "teams": "teams", "google_meet": "meet"}
var botPlatformLabel = map[string]string{"zoom": "Zoom call", "teams": "Teams meeting", "google_meet": "Google Meet"}

// EnsureBotMeeting makes sure the session has a meetings row (ports the
// meeting-creation block in bot_start). Returns the meeting id; creates a
// 'scheduled' fallback meeting + links it when the session has none.
func EnsureBotMeeting(ctx context.Context, conn *sql.DB, bs *model.MeetingBotSession) (string, error) {
	if bs.MeetingID != nil && *bs.MeetingID != "" {
		return *bs.MeetingID, nil
	}
	source := botPlatformSource[bs.Platform]
	if source == "" {
		source = "upload"
	}
	label := botPlatformLabel[bs.Platform]
	if label == "" {
		label = "Live meeting"
	}
	title := label + " — " + time.Now().Format("Jan 2, 3:04 PM")
	now := util.NowISO()
	id := util.NewUUID()
	if _, err := conn.ExecContext(ctx,
		"INSERT INTO meetings("+meetingCols+") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
		id, bs.OrgID, bs.DealID, title, nil, nil, source, bs.MeetingURL, nil,
		"scheduled", nil, true, nil, nil, bs.CreatedBy, now, now); err != nil {
		return "", err
	}
	if _, err := conn.ExecContext(ctx,
		"UPDATE meeting_bot_sessions SET meeting_id=?, updated_at=? WHERE id=?", id, now, bs.ID); err != nil {
		return "", err
	}
	bs.MeetingID = &id
	return id, nil
}

// MarkBotJoining records a successful Recall create_bot (ports the post-create
// session writes): status=joining, recall_bot_id, live_transcript_channel.
func MarkBotJoining(ctx context.Context, conn *sql.DB, sessionID, recallBotID, channel string) error {
	_, err := conn.ExecContext(ctx,
		"UPDATE meeting_bot_sessions SET status='joining', recall_bot_id=?, live_transcript_channel=?, updated_at=? WHERE id=?",
		recallBotID, channel, util.NowISO(), sessionID)
	return err
}

// SetBotStatus flips a bot session's status (failed / cancelled / completed).
func SetBotStatus(ctx context.Context, conn *sql.DB, sessionID, status string) error {
	_, err := conn.ExecContext(ctx,
		"UPDATE meeting_bot_sessions SET status=?, updated_at=? WHERE id=?",
		status, util.NowISO(), sessionID)
	return err
}

// ScheduledBot is one auto-scheduled session (ports the scheduled[] dicts).
type ScheduledBot struct {
	SessionID string  `json:"session_id"`
	MeetingID string  `json:"meeting_id"`
	DealID    *string `json:"deal_id"`
}

var sourceToBotPlatform = map[string]string{"zoom": "zoom", "teams": "teams", "meet": "google_meet", "google_meet": "google_meet"}

// AutoScheduleDue finds calendar-synced meetings about to start (bot_enabled,
// status='uploading', has deal+url, meeting_date in [-15m,+10m]) and creates a
// 'scheduled' bot session for each not already covered (ports bot_auto_schedule_due).
func AutoScheduleDue(ctx context.Context, conn *sql.DB) ([]ScheduledBot, error) {
	now := time.Now().UTC()
	windowStart := now.Add(-15 * time.Minute).Format(time.RFC3339)
	windowEnd := now.Add(10 * time.Minute).Format(time.RFC3339)

	rows, err := conn.QueryContext(ctx,
		`SELECT id, org_id, deal_id, source, source_url, meeting_date, created_by
		 FROM meetings
		 WHERE bot_enabled=1 AND status='uploading' AND deal_id IS NOT NULL
		   AND source_url IS NOT NULL AND meeting_date >= ? AND meeting_date <= ?`,
		windowStart, windowEnd)
	if err != nil {
		return nil, err
	}
	type cand struct {
		id, orgID, source, createdBy string
		dealID, sourceURL, mDate     *string
	}
	var cands []cand
	for rows.Next() {
		var c cand
		if err := rows.Scan(&c.id, &c.orgID, &c.dealID, &c.source, &c.sourceURL, &c.mDate, &c.createdBy); err != nil {
			rows.Close()
			return nil, err
		}
		cands = append(cands, c)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}

	scheduled := []ScheduledBot{}
	for _, c := range cands {
		platform := sourceToBotPlatform[c.source]
		if platform == "" {
			continue
		}
		var existing string
		err := conn.QueryRowContext(ctx,
			`SELECT id FROM meeting_bot_sessions WHERE meeting_id=? AND status IN ('scheduled','joining','recording','completed') LIMIT 1`,
			c.id).Scan(&existing)
		if err == nil {
			continue // already covered
		}
		if !errors.Is(err, sql.ErrNoRows) {
			return nil, err
		}
		sid := util.NewUUID()
		nowISO := util.NowISO()
		url := ""
		if c.sourceURL != nil {
			url = *c.sourceURL
		}
		if _, err := conn.ExecContext(ctx,
			`INSERT INTO meeting_bot_sessions(id, org_id, deal_id, meeting_id, platform,
			    meeting_url, status, scheduled_start, consent_obtained, created_by, created_at, updated_at)
			 VALUES (?,?,?,?,?,?,?,?,?,?,?,?)`,
			sid, c.orgID, c.dealID, c.id, platform, url, "scheduled", c.mDate, false, c.createdBy, nowISO, nowISO); err != nil {
			return nil, err
		}
		scheduled = append(scheduled, ScheduledBot{SessionID: sid, MeetingID: c.id, DealID: c.dealID})
	}
	return scheduled, nil
}

// BotParticipant is a recall-sourced participant to persist.
type BotParticipant struct {
	RecallParticipantID string
	SpeakerLabel        string
	SpeakerName         *string
	Email               *string
}

// SaveBotFinalize writes the post-call transcript + finalized segments +
// rebuilt recall participants in one transaction (ports the bot_finalize writes;
// segment confidence is NULL since Recall doesn't report per-turn confidence).
// Returns (transcriptID, segmentCount).
func SaveBotFinalize(ctx context.Context, conn *sql.DB, orgID, meetingID, fullText string, wordCount int, segments []TranscriptSegmentInput, participants []BotParticipant) (string, int, error) {
	tx, err := conn.BeginTx(ctx, nil)
	if err != nil {
		return "", 0, err
	}
	defer func() { _ = tx.Rollback() }()
	now := util.NowISO()

	var transcriptID string
	if len(segments) > 0 {
		err = tx.QueryRowContext(ctx, "SELECT id FROM transcripts WHERE meeting_id=?", meetingID).Scan(&transcriptID)
		switch {
		case errors.Is(err, sql.ErrNoRows):
			transcriptID = util.NewUUID()
			if _, err = tx.ExecContext(ctx,
				`INSERT INTO transcripts(id, org_id, meeting_id, full_text, language, word_count, created_at, updated_at)
				 VALUES (?,?,?,?,?,?,?,?)`,
				transcriptID, orgID, meetingID, fullText, "en", wordCount, now, now); err != nil {
				return "", 0, err
			}
		case err != nil:
			return "", 0, err
		default:
			if _, err = tx.ExecContext(ctx,
				"UPDATE transcripts SET full_text=?, language='en', word_count=?, updated_at=? WHERE id=?",
				fullText, wordCount, now, transcriptID); err != nil {
				return "", 0, err
			}
		}
		if _, err = tx.ExecContext(ctx,
			"DELETE FROM transcript_segments WHERE meeting_id=? AND is_partial=0", meetingID); err != nil {
			return "", 0, err
		}
		for i := range segments {
			s := segments[i]
			var name *string
			if s.SpeakerName != "" {
				name = &s.SpeakerName
			}
			if _, err = tx.ExecContext(ctx,
				`INSERT INTO transcript_segments(id, transcript_id, meeting_id, speaker_label,
				    speaker_name, text, start_time, end_time, confidence, segment_index, is_partial, created_at, updated_at)
				 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)`,
				util.NewUUID(), transcriptID, meetingID, s.SpeakerLabel, name, s.Text,
				s.StartTime, s.EndTime, nil, s.SegmentIndex, false, now, now); err != nil {
				return "", 0, err
			}
		}
	}

	if len(participants) > 0 {
		if _, err = tx.ExecContext(ctx,
			"DELETE FROM meeting_participants WHERE meeting_id=? AND recall_participant_id IS NOT NULL", meetingID); err != nil {
			return "", 0, err
		}
		for i := range participants {
			p := participants[i]
			if _, err = tx.ExecContext(ctx,
				`INSERT INTO meeting_participants(id, meeting_id, speaker_label, speaker_name,
				    recall_participant_id, email_address, created_at, updated_at)
				 VALUES (?,?,?,?,?,?,?,?)`,
				util.NewUUID(), meetingID, p.SpeakerLabel, p.SpeakerName, p.RecallParticipantID, p.Email, now, now); err != nil {
				return "", 0, err
			}
		}
	}

	if err = tx.Commit(); err != nil {
		return "", 0, err
	}
	return transcriptID, len(segments), nil
}

// UpdateMeetingTitleIfPlaceholder overwrites a meeting's title with realTitle
// ONLY when the current title is an auto-generated placeholder (ports the
// title-replace guard in bot_finalize) — never the user's chosen title.
func UpdateMeetingTitleIfPlaceholder(ctx context.Context, conn *sql.DB, meetingID, realTitle string) error {
	var cur string
	if err := conn.QueryRowContext(ctx, "SELECT title FROM meetings WHERE id=?", meetingID).Scan(&cur); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil
		}
		return err
	}
	placeholders := []string{"Bot meeting — ", "Live meeting — ", "Zoom call — ", "Teams meeting — ", "Google Meet — "}
	isPlaceholder := false
	for _, p := range placeholders {
		if len(cur) >= len(p) && cur[:len(p)] == p {
			isPlaceholder = true
			break
		}
	}
	if !isPlaceholder {
		return nil
	}
	_, err := conn.ExecContext(ctx,
		"UPDATE meetings SET title=?, updated_at=? WHERE id=?", realTitle, util.NowISO(), meetingID)
	return err
}
