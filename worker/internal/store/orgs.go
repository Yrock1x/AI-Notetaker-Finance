package store

import (
	"context"
	"database/sql"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/model"
)

// ListOrgs returns the organizations the principal belongs to, each annotated
// with the caller's membership role (ports list_orgs). Implicitly org-scoped:
// the join on org_memberships.user_id = p.UserID restricts the result to the
// caller's own memberships, so no foreign org can appear.
func ListOrgs(ctx context.Context, conn *sql.DB, p *Principal) ([]model.OrgWithRole, error) {
	rows, err := conn.QueryContext(ctx,
		`SELECT o.id, o.name, o.slug, m.role
		   FROM organizations o
		   JOIN org_memberships m ON m.org_id = o.id
		  WHERE m.user_id = ?`, p.UserID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]model.OrgWithRole, 0)
	for rows.Next() {
		var o model.OrgWithRole
		if err := rows.Scan(&o.ID, &o.Name, &o.Slug, &o.Role); err != nil {
			return nil, err
		}
		out = append(out, o)
	}
	return out, rows.Err()
}

// ListOrgMembers returns every member of orgID joined with their profile (ports
// list_org_members). The caller MUST already be a member of orgID — enforced by
// the handler via p.RequireOrg (which maps to 403) before this is called, so a
// non-member never reaches this query and can't enumerate a foreign org's roster.
func ListOrgMembers(ctx context.Context, conn *sql.DB, orgID string) ([]model.OrgMember, error) {
	rows, err := conn.QueryContext(ctx,
		`SELECT m.user_id, m.role, p.email, p.full_name, p.avatar_url
		   FROM org_memberships m
		   JOIN profiles p ON p.id = m.user_id
		  WHERE m.org_id = ?`, orgID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]model.OrgMember, 0)
	for rows.Next() {
		var m model.OrgMember
		if err := rows.Scan(&m.UserID, &m.Role, &m.Email, &m.FullName, &m.AvatarURL); err != nil {
			return nil, err
		}
		out = append(out, m)
	}
	return out, rows.Err()
}
