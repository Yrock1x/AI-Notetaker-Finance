package store

import (
	"context"
	"database/sql"
	"testing"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/db"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/util"
)

func oneHot(i int) []float32 {
	v := make([]float32, db.EmbeddingDim)
	v[i] = 1
	return v
}

func mkEmbedding(t *testing.T, conn *sql.DB, orgID, dealID, sourceID, text string, vec []float32) string {
	t.Helper()
	id := util.NewUUID()
	_, err := conn.Exec(
		`INSERT INTO embeddings(id, org_id, deal_id, source_type, source_id, chunk_text, chunk_index, metadata, created_at)
		 VALUES (?,?,?,?,?,?,?,?,?)`,
		id, orgID, dealID, "transcript_segment", sourceID, text, 0, `{"k":"v"}`, util.NowISO())
	if err != nil {
		t.Fatalf("insert embedding: %v", err)
	}
	if err := UpsertVector(context.Background(), conn, id, dealID, vec); err != nil {
		t.Fatalf("upsert vector: %v", err)
	}
	return id
}

func TestMatchEmbeddingsForDeal(t *testing.T) {
	conn := freshDB(t)
	ctx := context.Background()

	user := mkUser(t, conn, "v@x.com")
	orgA := mkOrg(t, conn, "vorga")
	orgB := mkOrg(t, conn, "vorgb")
	dealA := mkDeal(t, conn, orgA, user, "A")
	dealB := mkDeal(t, conn, orgB, user, "B")

	a1 := mkEmbedding(t, conn, orgA, dealA, "seg-A1", "alpha", oneHot(1))
	mkEmbedding(t, conn, orgA, dealA, "seg-A2", "beta", oneHot(2))
	mkEmbedding(t, conn, orgA, dealA, "seg-A3", "gamma", oneHot(3))
	mkEmbedding(t, conn, orgB, dealB, "seg-B1", "delta", oneHot(1)) // same vector, other deal

	// KNN in deal-A for a query == A1's vector
	hits, err := MatchEmbeddingsForDeal(ctx, conn, dealA, oneHot(1), 5, 0.0, nil)
	if err != nil {
		t.Fatalf("match: %v", err)
	}
	if len(hits) != 3 {
		t.Fatalf("got %d hits, want 3 (deal-B excluded by partition)", len(hits))
	}
	if hits[0].ID != a1 || hits[0].Similarity < 0.99 {
		t.Fatalf("closest=%+v, want A1 with sim~1", hits[0])
	}
	if hits[0].ChunkText != "alpha" || hits[0].SourceID != "seg-A1" || hits[0].Metadata["k"] != "v" {
		t.Fatalf("hydration wrong: %+v", hits[0])
	}

	// min_similarity drops the orthogonal hits (sim 0)
	hi2, _ := MatchEmbeddingsForDeal(ctx, conn, dealA, oneHot(1), 5, 0.99, nil)
	if len(hi2) != 1 || hi2[0].ID != a1 {
		t.Fatalf("min_similarity filter: got %d, want only A1", len(hi2))
	}

	// source_ids allowlist restricts to a subset
	hi3, _ := MatchEmbeddingsForDeal(ctx, conn, dealA, oneHot(1), 5, 0.0, []string{"seg-A1"})
	if len(hi3) != 1 || hi3[0].SourceID != "seg-A1" {
		t.Fatalf("source_ids filter: got %+v, want only seg-A1", hi3)
	}
}
