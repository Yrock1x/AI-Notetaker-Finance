package store

import (
	"context"
	"database/sql"
	"errors"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/model"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/util"
)

// dashboard.go ports app/api/v1/store/dashboard.py — the per-org activity feed
// and the per-deal extractions + action-items reads/writes. Every query is
// org-scoped via the Principal (OrgFilter / the scoped deal's org_id); a missing
// scope would leak another tenant's audit log, analyses, or action items.

// ListActivity returns the caller's 15 most recent audit_logs rows, projected
// with the actor's profile name and the deal's name (ports list_activity). The
// audit rows are org-scoped via OrgFilter; the profile/deal joins are outer
// (an audit row may have no user/deal, and either may be missing).
func ListActivity(ctx context.Context, conn *sql.DB, p *Principal) ([]model.ActivityRow, error) {
	pred, args := p.OrgFilter("a.org_id")
	q := `SELECT a.id, a.action, a.resource_type, a.resource_id, a.deal_id,
	             d.name, pr.full_name, a.created_at, a.details
	      FROM audit_logs a
	      LEFT JOIN profiles pr ON pr.id = a.user_id
	      LEFT JOIN deals d ON d.id = a.deal_id
	      WHERE ` + pred + `
	      ORDER BY a.created_at DESC
	      LIMIT 15`
	rows, err := conn.QueryContext(ctx, q, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]model.ActivityRow, 0, 15)
	for rows.Next() {
		var r model.ActivityRow
		if err := rows.Scan(&r.ID, &r.Action, &r.ResourceType, &r.ResourceID,
			&r.DealID, &r.DealName, &r.ActorName, &r.CreatedAt, &r.Details); err != nil {
			return nil, err
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

// ListExtractions returns the deal's completed analyses newest-first (ports
// list_extractions). The deal is scoped first (ErrNotFound for a foreign /
// missing / soft-deleted deal); the analyses are then restricted to meetings
// belonging to that deal, so they cannot escape the deal's org.
func ListExtractions(ctx context.Context, conn *sql.DB, p *Principal, dealID string) ([]model.ExtractionRow, error) {
	if _, err := ScopedDeal(ctx, conn, p, dealID); err != nil {
		return nil, err
	}
	q := `SELECT a.id, a.meeting_id, a.call_type, a.structured_output, a.created_at
	      FROM analyses a
	      JOIN meetings m ON m.id = a.meeting_id
	      WHERE m.deal_id = ? AND a.status = 'completed'
	      ORDER BY a.created_at DESC`
	rows, err := conn.QueryContext(ctx, q, dealID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []model.ExtractionRow
	for rows.Next() {
		var r model.ExtractionRow
		if err := rows.Scan(&r.ID, &r.MeetingID, &r.CallType, &r.StructuredOutput, &r.CreatedAt); err != nil {
			return nil, err
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

// ListActionItems returns the deal's action-item completions (ports
// list_action_items). The deal is scoped first; the rows are then filtered by
// deal_id, so they stay within the caller's org.
func ListActionItems(ctx context.Context, conn *sql.DB, p *Principal, dealID string) ([]model.ActionItem, error) {
	if _, err := ScopedDeal(ctx, conn, p, dealID); err != nil {
		return nil, err
	}
	q := `SELECT action_key, action_text, analysis_id, completed_by, completed_at
	      FROM action_item_completions WHERE deal_id = ?`
	rows, err := conn.QueryContext(ctx, q, dealID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []model.ActionItem
	for rows.Next() {
		var a model.ActionItem
		if err := rows.Scan(&a.ActionKey, &a.ActionText, &a.AnalysisID, &a.CompletedBy, &a.CompletedAt); err != nil {
			return nil, err
		}
		out = append(out, a)
	}
	return out, rows.Err()
}

// ActionItemCreate is the upsert payload (ports ActionItemCreate).
type ActionItemCreate struct {
	AnalysisID string
	ActionKey  string
	ActionText *string
}

// UpsertActionItem records (or re-records) an action-item completion on a deal
// (ports upsert_action_item). The deal is scoped first (ErrNotFound otherwise);
// the referenced analysis must belong to the same org (else ErrNotFound — no
// cross-tenant analysis ref). An existing row for (deal_id, action_key) is
// refreshed (analysis/text/completed_by + a new completed_at timestamp), else a
// new row is inserted. Returns the resulting row.
func UpsertActionItem(ctx context.Context, conn *sql.DB, p *Principal, dealID string, in ActionItemCreate) (*model.ActionItem, error) {
	deal, err := ScopedDeal(ctx, conn, p, dealID)
	if err != nil {
		return nil, err
	}

	// The referenced analysis must belong to the deal's org (no cross-tenant ref).
	var analysisOrg string
	err = conn.QueryRowContext(ctx,
		"SELECT org_id FROM analyses WHERE id = ?", in.AnalysisID).Scan(&analysisOrg)
	if errors.Is(err, sql.ErrNoRows) || (err == nil && analysisOrg != deal.OrgID) {
		return nil, ErrNotFound
	} else if err != nil {
		return nil, err
	}

	now := util.NowISO()
	var existingID string
	err = conn.QueryRowContext(ctx,
		"SELECT id FROM action_item_completions WHERE deal_id = ? AND action_key = ?",
		dealID, in.ActionKey).Scan(&existingID)
	switch {
	case err == nil:
		// Re-completing refreshes the latest action + timestamp (the column
		// default only fires on insert), mirroring the Python upsert.
		if _, err := conn.ExecContext(ctx,
			`UPDATE action_item_completions
			 SET analysis_id = ?, action_text = ?, completed_by = ?, completed_at = ?
			 WHERE id = ?`,
			in.AnalysisID, in.ActionText, p.UserID, now, existingID); err != nil {
			return nil, err
		}
	case errors.Is(err, sql.ErrNoRows):
		if _, err := conn.ExecContext(ctx,
			`INSERT INTO action_item_completions(
			    id, org_id, deal_id, analysis_id, action_key, action_text,
			    completed_by, completed_at, created_at)
			 VALUES (?,?,?,?,?,?,?,?,?)`,
			util.NewUUID(), deal.OrgID, dealID, in.AnalysisID, in.ActionKey,
			in.ActionText, p.UserID, now, now); err != nil {
			return nil, err
		}
	default:
		return nil, err
	}

	return &model.ActionItem{
		ActionKey:   in.ActionKey,
		ActionText:  in.ActionText,
		AnalysisID:  in.AnalysisID,
		CompletedBy: p.UserID,
		CompletedAt: now,
	}, nil
}

// DeleteActionItem removes an action-item completion (ports delete_action_item).
// The deal is scoped first; deleting a non-existent (deal_id, action_key) is a
// no-op (the Python handler 204s either way).
func DeleteActionItem(ctx context.Context, conn *sql.DB, p *Principal, dealID, actionKey string) error {
	if _, err := ScopedDeal(ctx, conn, p, dealID); err != nil {
		return err
	}
	_, err := conn.ExecContext(ctx,
		"DELETE FROM action_item_completions WHERE deal_id = ? AND action_key = ?",
		dealID, actionKey)
	return err
}
