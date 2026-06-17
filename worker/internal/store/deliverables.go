package store

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"
)

// GatherDealContext assembles the LLM context string for a deal's deliverable
// (ports DeliverableService._gather_context). It is org-scoped: it reads only
// meetings/analyses/documents whose org_id is in the principal's orgs, so a
// caller can never pull another tenant's rows into the prompt. The caller must
// have already ScopedDeal'd dealID; the org filter here is defence-in-depth.
//
// Shape matches the Python string exactly:
//
//	Deal ID: <id>
//	Meetings on record: <n>
//	\n--- Analysis (<call_type> v<version>) ---
//	<json.dumps(structured_output, indent=2)[:4000]>
//	\n--- Document: <title> (<document_type>) ---
//	<extracted_text[:4000]>
//
// then the whole thing is truncated to 40000 chars.
func GatherDealContext(ctx context.Context, conn *sql.DB, p *Principal, dealID string) (string, error) {
	pred, oargs := p.OrgFilter("org_id")
	parts := []string{fmt.Sprintf("Deal ID: %s", dealID)}

	// Meetings under the deal (org-scoped).
	meetingRows, err := conn.QueryContext(ctx,
		"SELECT id FROM meetings WHERE deal_id = ? AND "+pred,
		append([]any{dealID}, oargs...)...)
	if err != nil {
		return "", err
	}
	var meetingIDs []string
	for meetingRows.Next() {
		var id string
		if err := meetingRows.Scan(&id); err != nil {
			meetingRows.Close()
			return "", err
		}
		meetingIDs = append(meetingIDs, id)
	}
	meetingRows.Close()
	if err := meetingRows.Err(); err != nil {
		return "", err
	}
	parts = append(parts, fmt.Sprintf("Meetings on record: %d", len(meetingIDs)))

	// Completed analyses for those meetings (org-scoped).
	if len(meetingIDs) > 0 {
		ph := make([]string, len(meetingIDs))
		args := make([]any, 0, len(meetingIDs)+len(oargs))
		for i, id := range meetingIDs {
			ph[i] = "?"
			args = append(args, id)
		}
		args = append(args, oargs...)
		q := "SELECT call_type, version, structured_output FROM analyses WHERE meeting_id IN (" +
			strings.Join(ph, ",") + ") AND status = 'completed' AND " + pred
		aRows, err := conn.QueryContext(ctx, q, args...)
		if err != nil {
			return "", err
		}
		for aRows.Next() {
			var callType string
			var version sql.NullInt64
			var structured []byte
			if err := aRows.Scan(&callType, &version, &structured); err != nil {
				aRows.Close()
				return "", err
			}
			ct := callType
			if ct == "" {
				ct = "?"
			}
			ver := int64(1)
			if version.Valid && version.Int64 != 0 {
				ver = version.Int64
			}
			parts = append(parts, fmt.Sprintf("\n--- Analysis (%s v%d) ---", ct, ver))
			parts = append(parts, truncateRunes(prettyJSON(structured), 4000))
		}
		aRows.Close()
		if err := aRows.Err(); err != nil {
			return "", err
		}
	}

	// Documents under the deal with extracted text (org-scoped).
	dRows, err := conn.QueryContext(ctx,
		"SELECT title, document_type, extracted_text FROM documents WHERE deal_id = ? AND "+pred,
		append([]any{dealID}, oargs...)...)
	if err != nil {
		return "", err
	}
	for dRows.Next() {
		var title, docType string
		var extracted sql.NullString
		if err := dRows.Scan(&title, &docType, &extracted); err != nil {
			dRows.Close()
			return "", err
		}
		text := ""
		if extracted.Valid {
			text = extracted.String
		}
		if text == "" {
			continue
		}
		t := title
		if t == "" {
			t = "?"
		}
		dt := docType
		if dt == "" {
			dt = "?"
		}
		parts = append(parts, fmt.Sprintf("\n--- Document: %s (%s) ---", t, dt))
		parts = append(parts, truncateRunes(text, 4000))
	}
	dRows.Close()
	if err := dRows.Err(); err != nil {
		return "", err
	}

	return truncateRunes(strings.Join(parts, "\n"), 40000), nil
}

// prettyJSON renders structured_output as Python's json.dumps(result, indent=2).
// A null/empty column renders as "{}" (the Python `result = a.structured_output
// or {}` default).
func prettyJSON(raw []byte) string {
	if len(raw) == 0 {
		return "{}"
	}
	var v any
	if err := json.Unmarshal(raw, &v); err != nil {
		return "{}"
	}
	if v == nil {
		return "{}"
	}
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return "{}"
	}
	return string(b)
}

// truncateRunes mirrors Python's str[:n] slice (rune-based, not byte-based) so
// the context length matches the Python service for multibyte text.
func truncateRunes(s string, n int) string {
	r := []rune(s)
	if len(r) <= n {
		return s
	}
	return string(r[:n])
}
