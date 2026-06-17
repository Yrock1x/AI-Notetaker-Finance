package store

import (
	"context"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"errors"
	"strings"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/model"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/util"
)

// HashPartnerKey returns the sha256 hex of a raw partner key (ports _hash_key).
func HashPartnerKey(raw string) string {
	sum := sha256.Sum256([]byte(raw))
	return hex.EncodeToString(sum[:])
}

// PartnerKey is an authenticated partner API key, scoped to one org.
type PartnerKey struct {
	ID     string
	OrgID  string
	Scopes []string
}

func (k *PartnerKey) HasScope(s string) bool {
	for _, x := range k.Scopes {
		if x == s {
			return true
		}
	}
	return false
}

// GetActivePartnerKey looks up an active key by its hash; (nil,nil) if absent.
func GetActivePartnerKey(ctx context.Context, conn *sql.DB, hash string) (*PartnerKey, error) {
	var k PartnerKey
	var scopes []byte
	err := conn.QueryRowContext(ctx,
		"SELECT id, org_id, scopes FROM partner_api_keys WHERE key_hash = ? AND is_active = 1", hash).
		Scan(&k.ID, &k.OrgID, &scopes)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	_ = json.Unmarshal(scopes, &k.Scopes)
	return &k, nil
}

// BumpPartnerKeyUsed records last_used_at (best-effort).
func BumpPartnerKeyUsed(ctx context.Context, conn *sql.DB, id string) {
	_, _ = conn.ExecContext(ctx, "UPDATE partner_api_keys SET last_used_at = ? WHERE id = ?", util.NowISO(), id)
}

// VdrConnection is an active per-deal CogniVault share.
type VdrConnection struct {
	DealID      string
	OrgID       string
	VdrID       string
	VdrName     *string
	Status      string
	ShareScopes []string
}

func (c *VdrConnection) HasShareScope(s string) bool {
	for _, x := range c.ShareScopes {
		if x == s {
			return true
		}
	}
	return false
}

func activeConnection(ctx context.Context, conn *sql.DB, orgID, dealID string) (*VdrConnection, error) {
	var c VdrConnection
	var scopes []byte
	err := conn.QueryRowContext(ctx,
		"SELECT deal_id, org_id, vdr_id, vdr_name, status, share_scopes FROM deal_vdr_connections WHERE deal_id = ? AND org_id = ? AND status = 'active'",
		dealID, orgID).Scan(&c.DealID, &c.OrgID, &c.VdrID, &c.VdrName, &c.Status, &scopes)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	_ = json.Unmarshal(scopes, &c.ShareScopes)
	return &c, nil
}

// PartnerScopedDeal returns a deal the partner may READ: in the key's org, not
// deleted, AND with an active VDR connection — else ErrNotFound (a non-shared /
// foreign / deleted deal is an indistinguishable 404). Ports
// _scoped_shared_deal_or_404.
func PartnerScopedDeal(ctx context.Context, conn *sql.DB, orgID, dealID string) (*model.Deal, *VdrConnection, error) {
	d, err := scanDeal(conn.QueryRowContext(ctx,
		"SELECT "+dealCols+" FROM deals WHERE id = ? AND org_id = ? AND deleted_at IS NULL", dealID, orgID))
	if err != nil && !errors.Is(err, sql.ErrNoRows) {
		return nil, nil, err
	}
	vc, cerr := activeConnection(ctx, conn, orgID, dealID)
	if cerr != nil {
		return nil, nil, cerr
	}
	if errors.Is(err, sql.ErrNoRows) || vc == nil {
		return nil, nil, ErrNotFound
	}
	return d, vc, nil
}

// PartnerScopedMeeting returns the deal_id + active connection for a meeting
// whose deal is shared, else ErrNotFound. Ports _scoped_shared_meeting_or_404.
func PartnerScopedMeeting(ctx context.Context, conn *sql.DB, orgID, meetingID string) (dealID string, vc *VdrConnection, err error) {
	var did sql.NullString
	e := conn.QueryRowContext(ctx,
		"SELECT deal_id FROM meetings WHERE id = ? AND org_id = ?", meetingID, orgID).Scan(&did)
	if errors.Is(e, sql.ErrNoRows) || (e == nil && !did.Valid) {
		return "", nil, ErrNotFound
	}
	if e != nil {
		return "", nil, e
	}
	vc, err = activeConnection(ctx, conn, orgID, did.String)
	if err != nil {
		return "", nil, err
	}
	if vc == nil {
		return "", nil, ErrNotFound
	}
	return did.String, vc, nil
}

// PartnerListConnectedDeals returns the org's deals that have an active
// connection, each with its connection (ports list_deals).
func PartnerListConnectedDeals(ctx context.Context, conn *sql.DB, orgID string) ([]model.Deal, map[string]*VdrConnection, error) {
	rows, err := conn.QueryContext(ctx,
		`SELECT `+prefixCols("d", dealCols)+`, c.vdr_id, c.vdr_name, c.status, c.share_scopes
		 FROM deals d JOIN deal_vdr_connections c ON c.deal_id = d.id
		 WHERE d.org_id = ? AND d.deleted_at IS NULL AND c.status = 'active'
		 ORDER BY d.created_at DESC`, orgID)
	if err != nil {
		return nil, nil, err
	}
	defer rows.Close()
	var deals []model.Deal
	conns := map[string]*VdrConnection{}
	for rows.Next() {
		var d model.Deal
		vc := &VdrConnection{OrgID: orgID}
		var scopes []byte
		if err := rows.Scan(&d.ID, &d.OrgID, &d.Name, &d.Description, &d.TargetCompany,
			&d.DealType, &d.Stage, &d.Status, &d.CreatedBy, &d.DeletedAt, &d.CreatedAt, &d.UpdatedAt,
			&vc.VdrID, &vc.VdrName, &vc.Status, &scopes); err != nil {
			return nil, nil, err
		}
		vc.DealID = d.ID
		_ = json.Unmarshal(scopes, &vc.ShareScopes)
		deals = append(deals, d)
		conns[d.ID] = vc
	}
	return deals, conns, rows.Err()
}

// orgActorID picks a profile to attribute a partner write to (the org owner,
// else any member) — partner keys have no backing profile but documents.
// uploaded_by FKs profiles.id. Ports _org_actor_id. ErrNoRows if the org has
// no members.
func orgActorID(ctx context.Context, conn *sql.DB, orgID string) (string, error) {
	var uid string
	err := conn.QueryRowContext(ctx,
		"SELECT user_id FROM org_memberships WHERE org_id = ? ORDER BY (role = 'owner') DESC, joined_at LIMIT 1",
		orgID).Scan(&uid)
	return uid, err
}

// CreatePartnerDocument inserts a document on behalf of a partner key, attributed
// to the org actor. Returns (id, created_at, uploaded_by).
func CreatePartnerDocument(ctx context.Context, conn *sql.DB, orgID, dealID, title, docType, fileKey string, fileSize int64, extracted *string) (id, createdAt, uploadedBy string, err error) {
	actor, err := orgActorID(ctx, conn, orgID)
	if errors.Is(err, sql.ErrNoRows) {
		return "", "", "", ErrNotFound
	}
	if err != nil {
		return "", "", "", err
	}
	id, createdAt = util.NewUUID(), util.NowISO()
	_, err = conn.ExecContext(ctx,
		`INSERT INTO documents(id, org_id, deal_id, title, document_type, file_key, file_size, extracted_text, uploaded_by, created_at, updated_at)
		 VALUES (?,?,?,?,?,?,?,?,?,?,?)`,
		id, orgID, dealID, title, docType, fileKey, fileSize, extracted, actor, createdAt, createdAt)
	return id, createdAt, actor, err
}

// prefixCols turns "id, org_id, ..." into "x.id, x.org_id, ..." for a JOIN.
func prefixCols(alias, cols string) string {
	parts := strings.Split(cols, ", ")
	for i := range parts {
		parts[i] = alias + "." + strings.TrimSpace(parts[i])
	}
	return strings.Join(parts, ", ")
}
