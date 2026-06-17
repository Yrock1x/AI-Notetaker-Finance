package store

import (
	"context"
	"database/sql"
	"errors"
	"strings"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/model"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/util"
)

const dealCols = "id, org_id, name, description, target_company, deal_type, stage, status, created_by, deleted_at, created_at, updated_at"

func scanDeal(row interface{ Scan(...any) error }) (*model.Deal, error) {
	var d model.Deal
	err := row.Scan(&d.ID, &d.OrgID, &d.Name, &d.Description, &d.TargetCompany,
		&d.DealType, &d.Stage, &d.Status, &d.CreatedBy, &d.DeletedAt, &d.CreatedAt, &d.UpdatedAt)
	return &d, err
}

// ScopedDeal returns a non-deleted deal in one of the principal's orgs, else
// ErrNotFound (ports scoped_deal_or_404).
func ScopedDeal(ctx context.Context, conn *sql.DB, p *Principal, dealID string) (*model.Deal, error) {
	pred, args := p.OrgFilter("org_id")
	q := "SELECT " + dealCols + " FROM deals WHERE id = ? AND " + pred + " AND deleted_at IS NULL"
	d, err := scanDeal(conn.QueryRowContext(ctx, q, append([]any{dealID}, args...)...))
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	return d, err
}

// DealFilters are the list query params.
type DealFilters struct {
	Status   string
	DealType string
	Q        string
	Cursor   string
	Limit    int
}

// ListDeals returns an org-scoped page newest-first with a composite
// (created_at|id) cursor (ports list_deals).
func ListDeals(ctx context.Context, conn *sql.DB, p *Principal, f DealFilters) (items []model.Deal, nextCursor *string, hasMore bool, err error) {
	pred, args := p.OrgFilter("org_id")
	where := []string{pred, "deleted_at IS NULL"}
	if f.Status != "" {
		where = append(where, "status = ?")
		args = append(args, f.Status)
	}
	if f.DealType != "" {
		where = append(where, "deal_type = ?")
		args = append(args, f.DealType)
	}
	if f.Q != "" {
		where = append(where, "(name LIKE ? OR target_company LIKE ?)")
		like := "%" + f.Q + "%"
		args = append(args, like, like)
	}
	if f.Cursor != "" {
		if cCreated, cID, ok := strings.Cut(f.Cursor, "|"); ok {
			where = append(where, "(created_at, id) < (?, ?)")
			args = append(args, cCreated, cID)
		} else {
			where = append(where, "created_at < ?")
			args = append(args, f.Cursor)
		}
	}
	limit := f.Limit
	if limit <= 0 || limit > 100 {
		limit = 25
	}
	q := "SELECT " + dealCols + " FROM deals WHERE " + strings.Join(where, " AND ") +
		" ORDER BY created_at DESC, id DESC LIMIT ?"
	args = append(args, limit+1)

	rows, err := conn.QueryContext(ctx, q, args...)
	if err != nil {
		return nil, nil, false, err
	}
	defer rows.Close()
	for rows.Next() {
		d, err := scanDeal(rows)
		if err != nil {
			return nil, nil, false, err
		}
		items = append(items, *d)
	}
	if err := rows.Err(); err != nil {
		return nil, nil, false, err
	}
	hasMore = len(items) > limit
	if hasMore {
		items = items[:limit]
		last := items[len(items)-1]
		c := last.CreatedAt + "|" + last.ID
		nextCursor = &c
	}
	return items, nextCursor, hasMore, nil
}

// DealCreate is the create payload.
type DealCreate struct {
	OrgID         string
	Name          string
	Description   *string
	TargetCompany *string
	DealType      string
	Stage         *string
	Status        string
}

// CreateDeal inserts a deal + the creator's lead membership + an audit row. The
// caller must already have RequireOrg'd payload.OrgID.
func CreateDeal(ctx context.Context, conn *sql.DB, p *Principal, in DealCreate) (*model.Deal, error) {
	tx, err := conn.BeginTx(ctx, nil)
	if err != nil {
		return nil, err
	}
	defer tx.Rollback()

	now, id := util.NowISO(), util.NewUUID()
	dealType := in.DealType
	if dealType == "" {
		dealType = "general"
	}
	st := in.Status
	if st == "" {
		st = "active"
	}
	if _, err := tx.ExecContext(ctx,
		"INSERT INTO deals("+dealCols+") VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
		id, in.OrgID, in.Name, in.Description, in.TargetCompany, dealType, in.Stage, st, p.UserID, nil, now, now); err != nil {
		return nil, err
	}
	if _, err := tx.ExecContext(ctx,
		"INSERT INTO deal_memberships(id, deal_id, user_id, org_id, role, added_by, added_at) VALUES (?,?,?,?,?,?,?)",
		util.NewUUID(), id, p.UserID, in.OrgID, "lead", p.UserID, now); err != nil {
		return nil, err
	}
	uid, did := p.UserID, id
	if err := RecordAudit(ctx, tx, Audit{OrgID: in.OrgID, UserID: &uid, DealID: &did, Action: "create", ResourceType: "deal", ResourceID: &did, Details: map[string]any{"name": in.Name}}); err != nil {
		return nil, err
	}
	if err := tx.Commit(); err != nil {
		return nil, err
	}
	return ScopedDeal(ctx, conn, p, id)
}

// DealUpdate carries only the fields supplied by the caller (nil = unchanged).
type DealUpdate struct {
	Name          *string
	Description   *string
	TargetCompany *string
	DealType      *string
	Stage         *string
	Status        *string
}

// UpdateDeal patches supplied fields on a scoped deal (ports update_deal).
func UpdateDeal(ctx context.Context, conn *sql.DB, p *Principal, dealID string, u DealUpdate) (*model.Deal, error) {
	deal, err := ScopedDeal(ctx, conn, p, dealID)
	if err != nil {
		return nil, err
	}
	var sets []string
	var args []any
	add := func(col string, v any) { sets = append(sets, col+" = ?"); args = append(args, v) }
	if u.Name != nil {
		add("name", *u.Name)
	}
	if u.Description != nil {
		add("description", *u.Description)
	}
	if u.TargetCompany != nil {
		add("target_company", *u.TargetCompany)
	}
	if u.DealType != nil {
		add("deal_type", *u.DealType)
	}
	if u.Stage != nil {
		add("stage", *u.Stage)
	}
	if u.Status != nil {
		add("status", *u.Status)
	}
	if len(sets) > 0 {
		add("updated_at", util.NowISO())
		args = append(args, dealID)
		if _, err := conn.ExecContext(ctx, "UPDATE deals SET "+strings.Join(sets, ", ")+" WHERE id = ?", args...); err != nil {
			return nil, err
		}
	}
	uid := p.UserID
	_ = RecordAudit(ctx, conn, Audit{OrgID: deal.OrgID, UserID: &uid, DealID: &dealID, Action: "update", ResourceType: "deal", ResourceID: &dealID})
	return ScopedDeal(ctx, conn, p, dealID)
}

// SoftDeleteDeal sets deleted_at + audits (ports delete_deal).
func SoftDeleteDeal(ctx context.Context, conn *sql.DB, p *Principal, dealID string) error {
	deal, err := ScopedDeal(ctx, conn, p, dealID)
	if err != nil {
		return err
	}
	if _, err := conn.ExecContext(ctx, "UPDATE deals SET deleted_at = ? WHERE id = ?", util.NowISO(), dealID); err != nil {
		return err
	}
	uid := p.UserID
	_ = RecordAudit(ctx, conn, Audit{OrgID: deal.OrgID, UserID: &uid, DealID: &dealID, Action: "delete", ResourceType: "deal", ResourceID: &dealID})
	return nil
}

// DealMember is a member row joined with its profile.
type DealMember struct {
	UserID    string
	Role      string
	Email     *string
	FullName  *string
	AvatarURL *string
}

func ListDealMembers(ctx context.Context, conn *sql.DB, dealID string) ([]DealMember, error) {
	rows, err := conn.QueryContext(ctx,
		`SELECT m.user_id, m.role, p.email, p.full_name, p.avatar_url
		 FROM deal_memberships m JOIN profiles p ON p.id = m.user_id WHERE m.deal_id = ?`, dealID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []DealMember
	for rows.Next() {
		var m DealMember
		if err := rows.Scan(&m.UserID, &m.Role, &m.Email, &m.FullName, &m.AvatarURL); err != nil {
			return nil, err
		}
		out = append(out, m)
	}
	return out, rows.Err()
}

// AddDealMember adds an org member to a deal (ports add_member): the target must
// belong to the deal's org (else ErrNotFound), and must not already be a member
// (else ErrConflict).
func AddDealMember(ctx context.Context, conn *sql.DB, deal *model.Deal, userID, role string, addedBy string) (*DealMember, error) {
	var x string
	err := conn.QueryRowContext(ctx,
		"SELECT id FROM org_memberships WHERE org_id = ? AND user_id = ?", deal.OrgID, userID).Scan(&x)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	} else if err != nil {
		return nil, err
	}
	err = conn.QueryRowContext(ctx,
		"SELECT id FROM deal_memberships WHERE deal_id = ? AND user_id = ?", deal.ID, userID).Scan(&x)
	if err == nil {
		return nil, ErrConflict
	} else if !errors.Is(err, sql.ErrNoRows) {
		return nil, err
	}
	if role == "" {
		role = "analyst"
	}
	if _, err := conn.ExecContext(ctx,
		"INSERT INTO deal_memberships(id, deal_id, user_id, org_id, role, added_by, added_at) VALUES (?,?,?,?,?,?,?)",
		util.NewUUID(), deal.ID, userID, deal.OrgID, role, addedBy, util.NowISO()); err != nil {
		return nil, err
	}
	var m DealMember
	m.UserID, m.Role = userID, role
	_ = conn.QueryRowContext(ctx, "SELECT email, full_name, avatar_url FROM profiles WHERE id = ?", userID).
		Scan(&m.Email, &m.FullName, &m.AvatarURL)
	return &m, nil
}

func RemoveDealMember(ctx context.Context, conn *sql.DB, dealID, userID string) error {
	res, err := conn.ExecContext(ctx,
		"DELETE FROM deal_memberships WHERE deal_id = ? AND user_id = ?", dealID, userID)
	if err != nil {
		return err
	}
	if n, _ := res.RowsAffected(); n == 0 {
		return ErrNotFound
	}
	return nil
}
