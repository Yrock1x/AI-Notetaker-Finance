// Package store is the data-access layer. scope.go ports app/db/scope.py — the
// app-layer multi-tenancy that replaces Postgres RLS. EVERY query that touches a
// tenant-owned row must be constrained to the caller's orgs via a Principal;
// missing scope = a silent cross-tenant data leak, so this is the single most
// safety-critical file in the worker.
package store

import (
	"context"
	"database/sql"
	"errors"
	"strings"
)

// ErrAccessDenied is returned by the Require* guards; handlers map it to 403.
var ErrAccessDenied = errors.New("access denied")

// ErrNotFound is returned by scoped lookups for a missing/foreign/deleted row;
// handlers map it to 404 (a foreign row is indistinguishable from a missing one).
var ErrNotFound = errors.New("not found")

// ErrConflict is returned on a uniqueness/duplicate violation; handlers map to 409.
var ErrConflict = errors.New("conflict")

// Principal is the authenticated caller's tenancy: the orgs they belong to and
// the subset they administer. Loaded once per request from org_memberships.
type Principal struct {
	UserID      string
	OrgIDs      []string
	AdminOrgIDs []string
}

// LoadPrincipal builds a Principal from org_memberships (ports load_principal).
func LoadPrincipal(ctx context.Context, conn *sql.DB, userID string) (*Principal, error) {
	rows, err := conn.QueryContext(ctx,
		`SELECT org_id, role FROM org_memberships WHERE user_id = ?`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	p := &Principal{UserID: userID}
	for rows.Next() {
		var orgID, role string
		if err := rows.Scan(&orgID, &role); err != nil {
			return nil, err
		}
		p.OrgIDs = append(p.OrgIDs, orgID)
		if role == "owner" || role == "admin" {
			p.AdminOrgIDs = append(p.AdminOrgIDs, orgID)
		}
	}
	return p, rows.Err()
}

func contains(xs []string, v string) bool {
	for _, x := range xs {
		if x == v {
			return true
		}
	}
	return false
}

// InOrg reports membership; IsOrgAdmin reports owner/admin membership.
func (p *Principal) InOrg(orgID string) bool      { return contains(p.OrgIDs, orgID) }
func (p *Principal) IsOrgAdmin(orgID string) bool { return contains(p.AdminOrgIDs, orgID) }

// RequireOrg / RequireOrgAdmin port require_org / require_org_admin.
func (p *Principal) RequireOrg(orgID string) error {
	if !p.InOrg(orgID) {
		return ErrAccessDenied
	}
	return nil
}

func (p *Principal) RequireOrgAdmin(orgID string) error {
	if !p.IsOrgAdmin(orgID) {
		return ErrAccessDenied
	}
	return nil
}

// OrgFilter returns a SQL predicate + args restricting `col` to the principal's
// orgs — the database/sql analogue of org_scoped(). A memberless principal gets
// "1=0" so they see nothing (mirrors org_scoped's false()). Every tenant SELECT
// must AND this in.
func (p *Principal) OrgFilter(col string) (string, []any) {
	if len(p.OrgIDs) == 0 {
		return "1=0", nil
	}
	ph := make([]string, len(p.OrgIDs))
	args := make([]any, len(p.OrgIDs))
	for i, o := range p.OrgIDs {
		ph[i] = "?"
		args[i] = o
	}
	return col + " IN (" + strings.Join(ph, ",") + ")", args
}

// DealOrgID returns the owning org of a non-deleted deal (ports deal_org_id);
// sql.ErrNoRows if the deal does not exist / is soft-deleted.
func DealOrgID(ctx context.Context, conn *sql.DB, dealID string) (string, error) {
	var orgID string
	err := conn.QueryRowContext(ctx,
		`SELECT org_id FROM deals WHERE id = ? AND deleted_at IS NULL`, dealID).Scan(&orgID)
	return orgID, err
}

// MeetingOrgID returns the owning org of a meeting (ports meeting_org_id).
func MeetingOrgID(ctx context.Context, conn *sql.DB, meetingID string) (string, error) {
	var orgID string
	err := conn.QueryRowContext(ctx,
		`SELECT org_id FROM meetings WHERE id = ?`, meetingID).Scan(&orgID)
	return orgID, err
}
