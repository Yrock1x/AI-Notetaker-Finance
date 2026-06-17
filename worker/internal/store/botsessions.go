package store

import (
	"context"
	"database/sql"
	"errors"
	"strings"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/model"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/util"
)

const botSessionCols = "id, org_id, deal_id, meeting_id, platform, meeting_url, status, " +
	"scheduled_start, actual_start, actual_end, recording_file_key, recall_bot_id, " +
	"live_transcript_channel, consent_obtained, created_by, created_at, updated_at"

func scanBotSession(row interface{ Scan(...any) error }) (*model.MeetingBotSession, error) {
	var b model.MeetingBotSession
	err := row.Scan(&b.ID, &b.OrgID, &b.DealID, &b.MeetingID, &b.Platform, &b.MeetingURL,
		&b.Status, &b.ScheduledStart, &b.ActualStart, &b.ActualEnd, &b.RecordingFileKey,
		&b.RecallBotID, &b.LiveTranscriptChannel, &b.ConsentObtained, &b.CreatedBy,
		&b.CreatedAt, &b.UpdatedAt)
	return &b, err
}

// BotSessionFilters are the list query params (ports list_bot_sessions).
type BotSessionFilters struct {
	DealID string
	Status string
}

// ListBotSessions returns the principal's org-scoped bot sessions newest-first
// (ports list_bot_sessions). Every row is constrained to the caller's orgs.
func ListBotSessions(ctx context.Context, conn *sql.DB, p *Principal, f BotSessionFilters) ([]model.MeetingBotSession, error) {
	pred, args := p.OrgFilter("org_id")
	where := []string{pred}
	if f.DealID != "" {
		where = append(where, "deal_id = ?")
		args = append(args, f.DealID)
	}
	if f.Status != "" {
		where = append(where, "status = ?")
		args = append(args, f.Status)
	}
	q := "SELECT " + botSessionCols + " FROM meeting_bot_sessions WHERE " +
		strings.Join(where, " AND ") + " ORDER BY created_at DESC"
	rows, err := conn.QueryContext(ctx, q, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var items []model.MeetingBotSession
	for rows.Next() {
		b, err := scanBotSession(rows)
		if err != nil {
			return nil, err
		}
		items = append(items, *b)
	}
	return items, rows.Err()
}

// BotSessionCreate is the create payload.
type BotSessionCreate struct {
	DealID          string
	Platform        string
	MeetingURL      string
	ScheduledStart  *string
	ConsentObtained bool
}

// CreateBotSession inserts a "scheduled" bot session for a deal the principal can
// see (ports create_bot_session). The deal must be in one of the caller's orgs,
// else ErrNotFound — the new row inherits the deal's org_id (never the caller's).
//
// TODO(recall-phase): the Python worker stops at the DB write here; dispatching
// the Recall.ai bot happens out-of-band. When the Recall integration is ported,
// kick off the bot here and persist recall_bot_id / live_transcript_channel.
func CreateBotSession(ctx context.Context, conn *sql.DB, p *Principal, in BotSessionCreate) (*model.MeetingBotSession, error) {
	deal, err := ScopedDeal(ctx, conn, p, in.DealID)
	if err != nil {
		return nil, err
	}
	now, id := util.NowISO(), util.NewUUID()
	if _, err := conn.ExecContext(ctx,
		"INSERT INTO meeting_bot_sessions("+botSessionCols+") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
		id, deal.OrgID, deal.ID, nil, in.Platform, in.MeetingURL, "scheduled",
		in.ScheduledStart, nil, nil, nil, nil, nil, in.ConsentObtained, p.UserID, now, now,
	); err != nil {
		return nil, err
	}
	return getBotSession(ctx, conn, p, id)
}

// getBotSession fetches an org-scoped bot session by id, else ErrNotFound.
func getBotSession(ctx context.Context, conn *sql.DB, p *Principal, id string) (*model.MeetingBotSession, error) {
	pred, args := p.OrgFilter("org_id")
	q := "SELECT " + botSessionCols + " FROM meeting_bot_sessions WHERE id = ? AND " + pred
	b, err := scanBotSession(conn.QueryRowContext(ctx, q, append([]any{id}, args...)...))
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	return b, err
}

// CancelBotSession marks a bot session "cancelled" (ports cancel_bot_session).
// The row must be in one of the caller's orgs, else ErrNotFound (a foreign row is
// indistinguishable from a missing one).
//
// TODO(recall-phase): the Python worker only flips the status; when the Recall
// integration lands, also signal Recall.ai to stop/leave the live bot here.
func CancelBotSession(ctx context.Context, conn *sql.DB, p *Principal, id string) (*model.MeetingBotSession, error) {
	if _, err := getBotSession(ctx, conn, p, id); err != nil {
		return nil, err
	}
	if _, err := conn.ExecContext(ctx,
		"UPDATE meeting_bot_sessions SET status = ?, updated_at = ? WHERE id = ?",
		"cancelled", util.NowISO(), id); err != nil {
		return nil, err
	}
	return getBotSession(ctx, conn, p, id)
}
