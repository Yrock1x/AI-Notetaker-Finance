package store

import (
	"context"
	"database/sql"
	"encoding/json"
	"strings"

	sqlite_vec "github.com/asg017/sqlite-vec-go-bindings/cgo"
)

const vecTable = "vec_embeddings"

// SerializeFloat32 packs a vector into sqlite-vec's little-endian float32 blob —
// byte-identical to Python's sqlite_vec.serialize_float32, so Go-written vectors
// match Python-written ones.
func SerializeFloat32(v []float32) ([]byte, error) { return sqlite_vec.SerializeFloat32(v) }

// UpsertVector inserts/replaces the vector for an embeddings row (ports upsert_vector).
func UpsertVector(ctx context.Context, q execer, embeddingID, dealID string, vec []float32) error {
	blob, err := SerializeFloat32(vec)
	if err != nil {
		return err
	}
	if _, err := q.ExecContext(ctx, "DELETE FROM "+vecTable+" WHERE embedding_id = ?", embeddingID); err != nil {
		return err
	}
	_, err = q.ExecContext(ctx,
		"INSERT INTO "+vecTable+"(embedding_id, deal_id, embedding) VALUES (?, ?, ?)",
		embeddingID, dealID, blob)
	return err
}

// VecHit is a KNN result (matches the partner SearchHit shape).
type VecHit struct {
	ID         string
	SourceType string
	SourceID   string
	ChunkText  string
	Similarity float64
	Metadata   map[string]any
}

// MatchEmbeddingsForDeal runs cosine KNN over a deal's embeddings and hydrates
// the rows (ports match_embeddings_for_deal). sourceIDs (when non-nil)
// restricts results to that allowlist; vec0 can't join an IN-list so we
// over-fetch ×4 and filter the hydrated rows, preserving KNN order.
func MatchEmbeddingsForDeal(ctx context.Context, conn *sql.DB, dealID string, queryVec []float32, topK int, minSim float64, sourceIDs []string) ([]VecHit, error) {
	if topK <= 0 {
		topK = 15
	}
	blob, err := SerializeFloat32(queryVec)
	if err != nil {
		return nil, err
	}
	knnK := topK
	var allow map[string]bool
	if sourceIDs != nil {
		knnK = topK * 4
		allow = make(map[string]bool, len(sourceIDs))
		for _, s := range sourceIDs {
			allow[s] = true
		}
	}

	rows, err := conn.QueryContext(ctx,
		"SELECT embedding_id, distance FROM "+vecTable+
			" WHERE deal_id = ? AND embedding MATCH ? AND k = ? ORDER BY distance",
		dealID, blob, knnK)
	if err != nil {
		return nil, err
	}
	var order []string
	sim := map[string]float64{}
	for rows.Next() {
		var id string
		var dist float64
		if err := rows.Scan(&id, &dist); err != nil {
			rows.Close()
			return nil, err
		}
		order = append(order, id)
		sim[id] = 1.0 - dist
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}
	if len(order) == 0 {
		return nil, nil
	}

	// Hydrate the embeddings rows.
	ph := make([]string, len(order))
	args := make([]any, len(order))
	for i, id := range order {
		ph[i] = "?"
		args[i] = id
	}
	hrows, err := conn.QueryContext(ctx,
		"SELECT id, source_type, source_id, chunk_text, metadata FROM embeddings WHERE id IN ("+strings.Join(ph, ",")+")", args...)
	if err != nil {
		return nil, err
	}
	type emb struct {
		sourceType, sourceID, chunkText string
		metadata                        map[string]any
	}
	byID := map[string]emb{}
	for hrows.Next() {
		var id, st, sid, ct string
		var meta []byte
		if err := hrows.Scan(&id, &st, &sid, &ct, &meta); err != nil {
			hrows.Close()
			return nil, err
		}
		m := map[string]any{}
		if len(meta) > 0 {
			_ = json.Unmarshal(meta, &m)
		}
		byID[id] = emb{st, sid, ct, m}
	}
	hrows.Close()
	if err := hrows.Err(); err != nil {
		return nil, err
	}

	out := make([]VecHit, 0, topK)
	for _, id := range order { // KNN order, closest first
		s := sim[id]
		if s < minSim {
			continue
		}
		e, ok := byID[id]
		if !ok {
			continue
		}
		if allow != nil && !allow[e.sourceID] {
			continue
		}
		out = append(out, VecHit{ID: id, SourceType: e.sourceType, SourceID: e.sourceID,
			ChunkText: e.chunkText, Similarity: s, Metadata: e.metadata})
		if len(out) >= topK {
			break
		}
	}
	return out, nil
}
