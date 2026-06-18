package store

import (
	"context"
	"database/sql"
	"errors"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/util"
)

// SyncedMeetingInput is one calendar event to upsert into meetings (the store
// mirror of calendar.SyncedMeeting, so store doesn't import the calendar pkg).
type SyncedMeetingInput struct {
	Title           string
	MeetingDate     string
	Source          string
	SourceURL       *string
	ExternalEventID string
	BotEnabled      bool
}

// UpsertSyncedMeetings upserts calendar-synced meetings keyed on
// (org_id, external_provider, external_event_id) — the partial unique index
// (ports the per-row select-then-insert/update in calendar_sync). On an existing
// row it refreshes provider-owned fields but PRESERVES the user's bot_enabled
// toggle + deal_id assignment. Returns the number of rows touched.
func UpsertSyncedMeetings(ctx context.Context, conn *sql.DB, orgID, userID, provider string, rows []SyncedMeetingInput) (int, error) {
	n := 0
	for i := range rows {
		r := rows[i]
		now := util.NowISO()
		var existingID string
		err := conn.QueryRowContext(ctx,
			`SELECT id FROM meetings WHERE org_id=? AND external_provider=? AND external_event_id=? LIMIT 1`,
			orgID, provider, r.ExternalEventID).Scan(&existingID)
		switch {
		case errors.Is(err, sql.ErrNoRows):
			if _, err := conn.ExecContext(ctx,
				"INSERT INTO meetings("+meetingCols+") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
				util.NewUUID(), orgID, nil, r.Title, r.MeetingDate, nil, r.Source,
				r.SourceURL, nil, "uploading", nil, r.BotEnabled, r.ExternalEventID,
				provider, userID, now, now); err != nil {
				return n, err
			}
		case err != nil:
			return n, err
		default:
			// Refresh provider-owned fields; never clobber bot_enabled / deal_id.
			if _, err := conn.ExecContext(ctx,
				`UPDATE meetings SET title=?, meeting_date=?, source=?, source_url=?,
				    status=?, updated_at=? WHERE id=?`,
				r.Title, r.MeetingDate, r.Source, r.SourceURL, "uploading", now, existingID); err != nil {
				return n, err
			}
		}
		n++
	}
	return n, nil
}
