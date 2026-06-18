package store

import (
	"context"
	"database/sql"
	"errors"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/util"
)

// teamsingest.go ports the DB side of teams_ingest_call_record +
// ensure_microsoft_subscription (app/api/v1/internal/{ingest,calendar}.py).

// FirstActiveMicrosoftCredential returns any active microsoft/teams credential's
// (org,user). The stored platform may be 'teams'; both map to 'microsoft' OAuth.
func FirstActiveMicrosoftCredential(ctx context.Context, conn *sql.DB) (orgID, userID, platform string, ok bool, err error) {
	err = conn.QueryRowContext(ctx,
		"SELECT org_id, user_id, platform FROM integration_credentials WHERE platform IN ('microsoft','teams') AND is_active=1 LIMIT 1").
		Scan(&orgID, &userID, &platform)
	if errors.Is(err, sql.ErrNoRows) {
		return "", "", "", false, nil
	}
	if err != nil {
		return "", "", "", false, err
	}
	if platform == "teams" {
		platform = "microsoft"
	}
	return orgID, userID, platform, true, nil
}

// MatchMicrosoftMeeting finds a microsoft-synced meeting in a time window (ports
// the ±30min match in teams_ingest). ok=false if none.
func MatchMicrosoftMeeting(ctx context.Context, conn *sql.DB, orgID, windowStart, windowEnd string) (string, bool, error) {
	var id string
	err := conn.QueryRowContext(ctx,
		`SELECT id FROM meetings WHERE org_id=? AND external_provider='microsoft'
		   AND meeting_date >= ? AND meeting_date <= ? ORDER BY meeting_date LIMIT 1`,
		orgID, windowStart, windowEnd).Scan(&id)
	if errors.Is(err, sql.ErrNoRows) {
		return "", false, nil
	}
	if err != nil {
		return "", false, err
	}
	return id, true, nil
}

// CreateTeamsMeeting inserts an unassigned teams call meeting (status uploaded).
func CreateTeamsMeeting(ctx context.Context, conn *sql.DB, orgID, title, createdBy, eventID string) (string, error) {
	id, now := util.NewUUID(), util.NowISO()
	_, err := conn.ExecContext(ctx,
		"INSERT INTO meetings("+meetingCols+") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
		id, orgID, nil, title, nil, nil, "teams", nil, nil, "uploaded", nil, true,
		eventID, "microsoft", createdBy, now, now)
	return id, err
}

// UpsertTeamsParticipant upserts a participant on (meeting_id, recall_participant_id)
// (ports the participant loop). externalID is stored in recall_participant_id.
func UpsertTeamsParticipant(ctx context.Context, conn *sql.DB, meetingID, speakerLabel string, speakerName, email, externalID *string) error {
	now := util.NowISO()
	if externalID != nil {
		var existing string
		err := conn.QueryRowContext(ctx,
			"SELECT id FROM meeting_participants WHERE meeting_id=? AND recall_participant_id=? LIMIT 1",
			meetingID, *externalID).Scan(&existing)
		if err == nil {
			_, err = conn.ExecContext(ctx,
				"UPDATE meeting_participants SET speaker_label=?, speaker_name=?, email_address=?, updated_at=? WHERE id=?",
				speakerLabel, speakerName, email, now, existing)
			return err
		}
		if !errors.Is(err, sql.ErrNoRows) {
			return err
		}
	}
	_, err := conn.ExecContext(ctx,
		`INSERT INTO meeting_participants(id, meeting_id, speaker_label, speaker_name, email_address, recall_participant_id, created_at, updated_at)
		 VALUES (?,?,?,?,?,?,?,?)`,
		util.NewUUID(), meetingID, speakerLabel, speakerName, email, externalID, now, now)
	return err
}

// GraphSub is one graph_subscriptions row.
type GraphSub struct {
	ID              string
	OrgID           string
	UserID          string
	Resource        string
	ClientState     string
	NotificationURL string
	Expiration      string
}

// ActiveGraphSubscription returns the active subscription for (user,resource), or
// nil. Ports the existing-subscription lookup in ensure_microsoft_subscription.
func ActiveGraphSubscription(ctx context.Context, conn *sql.DB, userID, resource string) (*GraphSub, error) {
	var s GraphSub
	err := conn.QueryRowContext(ctx,
		`SELECT id, org_id, user_id, resource, client_state, notification_url, expiration
		 FROM graph_subscriptions WHERE user_id=? AND resource=? AND is_active=1 LIMIT 1`,
		userID, resource).Scan(&s.ID, &s.OrgID, &s.UserID, &s.Resource, &s.ClientState, &s.NotificationURL, &s.Expiration)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &s, nil
}

// UpsertGraphSubscription inserts or refreshes a subscription row keyed on its
// Graph id (ports the session.get(GraphSubscription, id) upsert).
func UpsertGraphSubscription(ctx context.Context, conn *sql.DB, s GraphSub) error {
	now := util.NowISO()
	var existing string
	err := conn.QueryRowContext(ctx, "SELECT id FROM graph_subscriptions WHERE id=?", s.ID).Scan(&existing)
	switch {
	case errors.Is(err, sql.ErrNoRows):
		_, err = conn.ExecContext(ctx,
			`INSERT INTO graph_subscriptions(id, org_id, user_id, resource, client_state, notification_url, expiration, is_active, created_at, updated_at)
			 VALUES (?,?,?,?,?,?,?,?,?,?)`,
			s.ID, s.OrgID, s.UserID, s.Resource, s.ClientState, s.NotificationURL, s.Expiration, true, now, now)
		return err
	case err != nil:
		return err
	default:
		_, err = conn.ExecContext(ctx,
			`UPDATE graph_subscriptions SET org_id=?, user_id=?, resource=?, client_state=?, notification_url=?, expiration=?, is_active=1, updated_at=? WHERE id=?`,
			s.OrgID, s.UserID, s.Resource, s.ClientState, s.NotificationURL, s.Expiration, now, s.ID)
		return err
	}
}

// UpdateGraphSubscriptionExpiration sets a renewed expiration.
func UpdateGraphSubscriptionExpiration(ctx context.Context, conn *sql.DB, id, expiration string) error {
	_, err := conn.ExecContext(ctx,
		"UPDATE graph_subscriptions SET expiration=?, updated_at=? WHERE id=?", expiration, util.NowISO(), id)
	return err
}

// DeactivateGraphSubscription marks a subscription inactive (so the next run
// re-creates it).
func DeactivateGraphSubscription(ctx context.Context, conn *sql.DB, id string) error {
	_, err := conn.ExecContext(ctx,
		"UPDATE graph_subscriptions SET is_active=0, updated_at=? WHERE id=?", util.NowISO(), id)
	return err
}
