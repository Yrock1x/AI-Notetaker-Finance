package store

import (
	"context"
	"database/sql"
	"errors"
	"strings"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/model"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/util"
)

// ErrCrossOrg is returned when a meeting would be reassigned to a deal in a
// different org than the meeting itself; the handler maps it to 400 (ports the
// "Cross-org deal" HTTPException in update_meeting). It is meetings-specific, so
// it is NOT in the shared storeError() switch — handlers check it explicitly.
var ErrCrossOrg = errors.New("cross-org deal")

const meetingCols = "id, org_id, deal_id, title, meeting_date, duration_seconds, source, source_url, file_key, status, error_message, bot_enabled, external_event_id, external_provider, created_by, created_at, updated_at"

func scanMeeting(row interface{ Scan(...any) error }) (*model.Meeting, error) {
	var m model.Meeting
	err := row.Scan(&m.ID, &m.OrgID, &m.DealID, &m.Title, &m.MeetingDate,
		&m.DurationSeconds, &m.Source, &m.SourceURL, &m.FileKey, &m.Status,
		&m.ErrorMessage, &m.BotEnabled, &m.ExternalEventID, &m.ExternalProvider,
		&m.CreatedBy, &m.CreatedAt, &m.UpdatedAt)
	return &m, err
}

// ScopedMeeting returns a meeting owned by one of the principal's orgs, else
// ErrNotFound (ports scoped_meeting_or_404). A foreign/missing row is
// indistinguishable — both 404.
func ScopedMeeting(ctx context.Context, conn *sql.DB, p *Principal, meetingID string) (*model.Meeting, error) {
	pred, args := p.OrgFilter("org_id")
	q := "SELECT " + meetingCols + " FROM meetings WHERE id = ? AND " + pred
	m, err := scanMeeting(conn.QueryRowContext(ctx, q, append([]any{meetingID}, args...)...))
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	return m, err
}

// ListDealMeetings returns every meeting under a deal, newest-first (ports
// list_deal_meetings). The caller must have already ScopedDeal'd dealID; the
// query is additionally org-scoped here as defence-in-depth so a meeting can
// never leak across tenants even if the deal guard is skipped.
func ListDealMeetings(ctx context.Context, conn *sql.DB, p *Principal, dealID string) ([]model.Meeting, error) {
	pred, args := p.OrgFilter("org_id")
	q := "SELECT " + meetingCols + " FROM meetings WHERE deal_id = ? AND " + pred +
		" ORDER BY created_at DESC"
	rows, err := conn.QueryContext(ctx, q, append([]any{dealID}, args...)...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	items := make([]model.Meeting, 0)
	for rows.Next() {
		m, err := scanMeeting(rows)
		if err != nil {
			return nil, err
		}
		items = append(items, *m)
	}
	return items, rows.Err()
}

// MeetingCreate is the create payload (ports MeetingCreate). Defaults
// (source="upload", status="uploading", bot_enabled=true) are applied here.
type MeetingCreate struct {
	Title           string
	Source          string
	FileKey         *string
	SourceURL       *string
	MeetingDate     *string
	DurationSeconds *int64
	BotEnabled      bool
}

// CreateMeeting inserts a meeting under a scoped deal (ports create_meeting).
// org_id is inherited from the deal — never from the client — so a meeting can
// only ever be created in the deal's own tenant.
func CreateMeeting(ctx context.Context, conn *sql.DB, p *Principal, deal *model.Deal, in MeetingCreate) (*model.Meeting, error) {
	now, id := util.NowISO(), util.NewUUID()
	source := in.Source
	if source == "" {
		source = "upload"
	}
	if _, err := conn.ExecContext(ctx,
		"INSERT INTO meetings("+meetingCols+") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
		id, deal.OrgID, deal.ID, in.Title, in.MeetingDate, in.DurationSeconds, source,
		in.SourceURL, in.FileKey, "uploading", nil, in.BotEnabled, nil, nil,
		p.UserID, now, now); err != nil {
		return nil, err
	}
	return ScopedMeeting(ctx, conn, p, id)
}

// MeetingUpdate carries the patchable fields. A nil pointer means "field absent
// from the request body" (the exclude_unset semantics); a present-but-null
// meeting_date/deal_id is expressed via the *Set flags so we can write SQL NULL.
type MeetingUpdate struct {
	Title          *string
	BotEnabled     *bool
	MeetingDate    *string
	MeetingDateSet bool // meeting_date was present in the body (value may be null)
	DealID         *string
	DealIDSet      bool // deal_id was present in the body (value may be null)
}

// UpdateMeeting patches the supplied fields on a scoped meeting (ports
// update_meeting). A client-supplied deal_id must resolve to a deal in the SAME
// org as the meeting, else ErrCrossOrg (400) — never let a meeting be reassigned
// into another tenant's deal (IDOR). Returns ErrNotFound if the target deal is
// missing/foreign.
func UpdateMeeting(ctx context.Context, conn *sql.DB, p *Principal, meetingID string, u MeetingUpdate) (*model.Meeting, error) {
	meeting, err := ScopedMeeting(ctx, conn, p, meetingID)
	if err != nil {
		return nil, err
	}

	// Reassigning to a deal: it must be visible to the principal AND share the
	// meeting's org.
	if u.DealIDSet && u.DealID != nil {
		target, err := ScopedDeal(ctx, conn, p, *u.DealID)
		if err != nil {
			return nil, err
		}
		if target.OrgID != meeting.OrgID {
			return nil, ErrCrossOrg
		}
	}

	var sets []string
	var args []any
	add := func(col string, v any) { sets = append(sets, col+" = ?"); args = append(args, v) }
	if u.Title != nil {
		add("title", *u.Title)
	}
	if u.BotEnabled != nil {
		add("bot_enabled", *u.BotEnabled)
	}
	if u.MeetingDateSet {
		add("meeting_date", u.MeetingDate) // *string -> NULL when nil
	}
	if u.DealIDSet {
		add("deal_id", u.DealID) // *string -> NULL when nil
	}
	if len(sets) > 0 {
		add("updated_at", util.NowISO())
		args = append(args, meetingID)
		if _, err := conn.ExecContext(ctx,
			"UPDATE meetings SET "+strings.Join(sets, ", ")+" WHERE id = ?", args...); err != nil {
			return nil, err
		}
	}
	return ScopedMeeting(ctx, conn, p, meetingID)
}
