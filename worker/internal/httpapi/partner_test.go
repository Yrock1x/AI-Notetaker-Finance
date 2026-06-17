package httpapi

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/config"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/db"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/llm"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/store"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/util"
)

func partnerPost(t *testing.T, url, key, body string) *http.Response {
	t.Helper()
	req, _ := http.NewRequest("POST", url, strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	if key != "" {
		req.Header.Set("Authorization", "Bearer "+key)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("POST %s: %v", url, err)
	}
	return resp
}

func TestPartnerAPIAndTextSearch(t *testing.T) {
	conn, err := db.Open(filepath.Join(t.TempDir(), "p.db"))
	if err != nil {
		t.Fatal(err)
	}
	defer conn.Close()
	if err := db.Migrate(conn); err != nil {
		t.Fatal(err)
	}
	ctx := context.Background()
	now := util.NowISO()
	orgID, userID, dealID, embID := util.NewUUID(), util.NewUUID(), util.NewUUID(), util.NewUUID()
	exec := func(q string, a ...any) {
		if _, err := conn.Exec(q, a...); err != nil {
			t.Fatalf("seed: %v", err)
		}
	}
	exec(`INSERT INTO organizations(id,name,slug,settings,created_at,updated_at) VALUES(?,?,?,?,?,?)`, orgID, "o", "o", "{}", now, now)
	exec(`INSERT INTO profiles(id,email,full_name,is_active,created_at,updated_at) VALUES(?,?,?,?,?,?)`, userID, "u@x.com", "u", true, now, now)
	exec(`INSERT INTO org_memberships(id,org_id,user_id,role,joined_at) VALUES(?,?,?,?,?)`, util.NewUUID(), orgID, userID, "owner", now)
	exec(`INSERT INTO deals(id,org_id,name,deal_type,status,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)`, dealID, orgID, "D", "general", "active", userID, now, now)
	exec(`INSERT INTO deal_vdr_connections(id,deal_id,org_id,provider,vdr_id,status,share_scopes,connected_by,connected_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)`,
		util.NewUUID(), dealID, orgID, "cognivault", "vdr-1", "active", `["search"]`, userID, now, now, now)
	exec(`INSERT INTO embeddings(id,org_id,deal_id,source_type,source_id,chunk_text,chunk_index,metadata,created_at) VALUES(?,?,?,?,?,?,?,?,?)`,
		embID, orgID, dealID, "transcript_segment", "seg-1", "customer concentration risk", 0, "{}", now)
	vec := make([]float32, db.EmbeddingDim)
	vec[5] = 1
	if err := store.UpsertVector(ctx, conn, embID, dealID, vec); err != nil {
		t.Fatal(err)
	}
	searchKey := "raw-search-key"
	exec(`INSERT INTO partner_api_keys(id,org_id,name,key_hash,scopes,is_active,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)`,
		util.NewUUID(), orgID, "k", store.HashPartnerKey(searchKey), `["search","deals:read"]`, true, now, now)
	noScopeKey := "raw-noscope-key"
	exec(`INSERT INTO partner_api_keys(id,org_id,name,key_hash,scopes,is_active,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)`,
		util.NewUUID(), orgID, "k2", store.HashPartnerKey(noScopeKey), `["deals:read"]`, true, now, now)

	// mock Fireworks embeddings -> returns the stored vector so KNN finds seg-1
	mock := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{"data": []map[string]any{{"embedding": vec}}})
	}))
	defer mock.Close()

	srv := &Server{
		Cfg: &config.Config{AppEnv: "development", SessionJWTSecret: "x0123456789abcdef", SessionCookieName: "cogni_session", CORSOrigins: "http://localhost:3000"},
		DB:  conn,
		LLM: llm.New("k", 5).WithBaseURL(mock.URL),
	}
	ts := httptest.NewServer(srv.Router())
	defer ts.Close()
	searchURL := ts.URL + "/partner/v1/deals/" + dealID + "/search"

	// no auth -> 401
	if r := partnerPost(t, searchURL, "", `{"query":"x"}`); r.StatusCode != 401 {
		t.Fatalf("no-auth search: %d, want 401", r.StatusCode)
	}
	// wrong key -> 401
	if r := partnerPost(t, searchURL, "bogus", `{"query":"x"}`); r.StatusCode != 401 {
		t.Fatalf("bad-key search: %d, want 401", r.StatusCode)
	}
	// key without 'search' scope -> 403
	if r := partnerPost(t, searchURL, noScopeKey, `{"query":"x"}`); r.StatusCode != 403 {
		t.Fatalf("no-scope search: %d, want 403", r.StatusCode)
	}
	// both query and query_vector -> 422
	if r := partnerPost(t, searchURL, searchKey, `{"query":"x","query_vector":[1,2]}`); r.StatusCode != 422 {
		t.Fatalf("both inputs: %d, want 422", r.StatusCode)
	}
	// TEXT search -> 200 + the seeded hit (server embedded the text)
	r := partnerPost(t, searchURL, searchKey, `{"query":"customer concentration"}`)
	if r.StatusCode != 200 {
		t.Fatalf("text search: %d, want 200", r.StatusCode)
	}
	var hits []searchHitJSON
	_ = json.NewDecoder(r.Body).Decode(&hits)
	if len(hits) != 1 || hits[0].SourceID != "seg-1" || hits[0].Similarity < 0.99 {
		t.Fatalf("text search hits=%+v, want 1 hit seg-1", hits)
	}

	// deals:read list -> 200 with vdr_id + shared_scopes
	dl, _ := http.NewRequest("GET", ts.URL+"/partner/v1/deals", nil)
	dl.Header.Set("Authorization", "Bearer "+searchKey)
	dr, _ := http.DefaultClient.Do(dl)
	if dr.StatusCode != 200 {
		t.Fatalf("partner list deals: %d", dr.StatusCode)
	}
	var deals []partnerDealJSON
	_ = json.NewDecoder(dr.Body).Decode(&deals)
	if len(deals) != 1 || deals[0].VdrID != "vdr-1" {
		t.Fatalf("partner deals=%+v", deals)
	}
}
