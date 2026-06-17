package store

import (
	"context"
	"database/sql"
	"path/filepath"
	"testing"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/db"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/util"
)

func freshDB(t *testing.T) *sql.DB {
	t.Helper()
	conn, err := db.Open(filepath.Join(t.TempDir(), "test.db"))
	if err != nil {
		t.Fatalf("open: %v", err)
	}
	if err := db.Migrate(conn); err != nil {
		t.Fatalf("migrate: %v", err)
	}
	t.Cleanup(func() { conn.Close() })
	return conn
}

func mkOrg(t *testing.T, conn *sql.DB, name string) string {
	t.Helper()
	id, now := util.NewUUID(), util.NowISO()
	_, err := conn.Exec(
		`INSERT INTO organizations(id,name,slug,settings,created_at,updated_at) VALUES (?,?,?,?,?,?)`,
		id, name, name, "{}", now, now)
	if err != nil {
		t.Fatalf("insert org: %v", err)
	}
	return id
}

func mkUser(t *testing.T, conn *sql.DB, email string) string {
	t.Helper()
	id, now := util.NewUUID(), util.NowISO()
	_, err := conn.Exec(
		`INSERT INTO profiles(id,email,full_name,is_active,created_at,updated_at) VALUES (?,?,?,?,?,?)`,
		id, email, email, true, now, now)
	if err != nil {
		t.Fatalf("insert user: %v", err)
	}
	return id
}

func mkMembership(t *testing.T, conn *sql.DB, orgID, userID, role string) {
	t.Helper()
	_, err := conn.Exec(
		`INSERT INTO org_memberships(id,org_id,user_id,role,joined_at) VALUES (?,?,?,?,?)`,
		util.NewUUID(), orgID, userID, role, util.NowISO())
	if err != nil {
		t.Fatalf("insert membership: %v", err)
	}
}

func mkDeal(t *testing.T, conn *sql.DB, orgID, createdBy, name string) string {
	t.Helper()
	id, now := util.NewUUID(), util.NowISO()
	_, err := conn.Exec(
		`INSERT INTO deals(id,org_id,name,deal_type,status,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)`,
		id, orgID, name, "general", "active", createdBy, now, now)
	if err != nil {
		t.Fatalf("insert deal: %v", err)
	}
	return id
}

func TestMigrateCreatesSchema(t *testing.T) {
	conn := freshDB(t)
	if err := db.Ping(conn); err != nil {
		t.Fatalf("ping (sqlite+vec): %v", err)
	}
	for _, table := range []string{
		"profiles", "organizations", "org_memberships", "deals", "meetings",
		"documents", "transcripts", "transcript_segments", "analyses",
		"embeddings", "qa_interactions", "partner_api_keys", "deal_vdr_connections",
		"vec_embeddings",
	} {
		var name string
		err := conn.QueryRow(
			`SELECT name FROM sqlite_master WHERE name = ?`, table).Scan(&name)
		if err != nil {
			t.Errorf("expected table %q to exist after migrate: %v", table, err)
		}
	}
}

func TestPrincipalScopingIsolatesTenants(t *testing.T) {
	conn := freshDB(t)
	ctx := context.Background()

	orgA, orgB := mkOrg(t, conn, "orga"), mkOrg(t, conn, "orgb")
	userA := mkUser(t, conn, "a@x.com")
	mkMembership(t, conn, orgA, userA, "owner")
	dealA := mkDeal(t, conn, orgA, userA, "deal A")
	_ = mkDeal(t, conn, orgB, userA, "deal B") // userA is NOT a member of orgB

	p, err := LoadPrincipal(ctx, conn, userA)
	if err != nil {
		t.Fatalf("LoadPrincipal: %v", err)
	}
	if !p.InOrg(orgA) || p.InOrg(orgB) {
		t.Fatalf("InOrg wrong: orgs=%v (want only %s)", p.OrgIDs, orgA)
	}
	if !p.IsOrgAdmin(orgA) {
		t.Fatalf("owner should be org admin")
	}
	if err := p.RequireOrg(orgB); err != ErrAccessDenied {
		t.Fatalf("RequireOrg(B) = %v, want ErrAccessDenied", err)
	}
	if err := p.RequireOrgAdmin(orgA); err != nil {
		t.Fatalf("RequireOrgAdmin(A) = %v, want nil", err)
	}

	// OrgFilter must restrict a deals query to the principal's orgs → only deal A.
	pred, args := p.OrgFilter("org_id")
	rows, err := conn.QueryContext(ctx,
		"SELECT id FROM deals WHERE "+pred+" AND deleted_at IS NULL", args...)
	if err != nil {
		t.Fatalf("scoped query: %v", err)
	}
	defer rows.Close()
	var got []string
	for rows.Next() {
		var id string
		_ = rows.Scan(&id)
		got = append(got, id)
	}
	if len(got) != 1 || got[0] != dealA {
		t.Fatalf("scoped deals = %v, want [%s] (orgB deal must be invisible)", got, dealA)
	}

	if org, err := DealOrgID(ctx, conn, dealA); err != nil || org != orgA {
		t.Fatalf("DealOrgID(dealA) = %q,%v want %q,nil", org, err, orgA)
	}

	// A memberless principal sees nothing.
	empty := &Principal{UserID: "nobody"}
	pred2, _ := empty.OrgFilter("org_id")
	if pred2 != "1=0" {
		t.Fatalf("memberless OrgFilter = %q, want 1=0", pred2)
	}
}
