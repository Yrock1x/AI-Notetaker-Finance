package store

import (
	"context"
	"database/sql"
	"errors"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/util"
)

// zoomingest.go ports the DB side of app/api/v1/internal/ingest.zoom_ingest:
// attribute a Zoom recording to an existing calendar-synced meeting (or create
// an unassigned one), then mark it uploaded once the recording is downloaded.

// ZoomMeetingMatch is an existing zoom-synced meeting for a recording.
type ZoomMeetingMatch struct {
	ID     string
	OrgID  string
	DealID *string
}

// FindZoomMeeting finds the meetings row for a Zoom external event id.
func FindZoomMeeting(ctx context.Context, conn *sql.DB, eventID string) (*ZoomMeetingMatch, error) {
	var m ZoomMeetingMatch
	err := conn.QueryRowContext(ctx,
		"SELECT id, org_id, deal_id FROM meetings WHERE external_provider='zoom' AND external_event_id=? LIMIT 1",
		eventID).Scan(&m.ID, &m.OrgID, &m.DealID)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &m, nil
}

// FirstActiveZoomCredential returns any active zoom credential's (org,user) so an
// unassigned recording can be bound to an org (ports the cred lookup). ok=false
// when none exists -> the caller responds "no_credential".
func FirstActiveZoomCredential(ctx context.Context, conn *sql.DB) (orgID, userID string, ok bool, err error) {
	err = conn.QueryRowContext(ctx,
		"SELECT org_id, user_id FROM integration_credentials WHERE platform='zoom' AND is_active=1 LIMIT 1").
		Scan(&orgID, &userID)
	if errors.Is(err, sql.ErrNoRows) {
		return "", "", false, nil
	}
	if err != nil {
		return "", "", false, err
	}
	return orgID, userID, true, nil
}

// ZoomAccessEncForOrg returns the org's active zoom access_token_encrypted (or ""
// when none), for the recording download auth header.
func ZoomAccessEncForOrg(ctx context.Context, conn *sql.DB, orgID string) (string, error) {
	var enc sql.NullString
	err := conn.QueryRowContext(ctx,
		"SELECT access_token_encrypted FROM integration_credentials WHERE platform='zoom' AND is_active=1 AND org_id=? LIMIT 1",
		orgID).Scan(&enc)
	if errors.Is(err, sql.ErrNoRows) {
		return "", nil
	}
	if err != nil {
		return "", err
	}
	return enc.String, nil
}

// CreateZoomIngestMeeting inserts an unassigned (deal_id NULL) zoom meeting for a
// recording with no calendar match.
func CreateZoomIngestMeeting(ctx context.Context, conn *sql.DB, orgID, title, createdBy, eventID string) (string, error) {
	id, now := util.NewUUID(), util.NowISO()
	_, err := conn.ExecContext(ctx,
		"INSERT INTO meetings("+meetingCols+") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
		id, orgID, nil, title, nil, nil, "zoom", nil, nil, "uploading", nil, true,
		eventID, "zoom", createdBy, now, now)
	return id, err
}

// SetMeetingUploaded marks a meeting uploaded with its stored recording (ports
// the final status flip in zoom_ingest).
func SetMeetingUploaded(ctx context.Context, conn *sql.DB, meetingID, fileKey, sourceURL string) error {
	_, err := conn.ExecContext(ctx,
		"UPDATE meetings SET file_key=?, status='uploaded', source_url=?, updated_at=? WHERE id=?",
		fileKey, sourceURL, util.NowISO(), meetingID)
	return err
}
