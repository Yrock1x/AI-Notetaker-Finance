package store

import (
	"context"
	"encoding/json"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/util"
)

// Audit is one audit_logs row (ports app/db/audit.record_audit).
type Audit struct {
	OrgID        string
	UserID       *string
	DealID       *string
	Action       string
	ResourceType string
	ResourceID   *string
	Details      any // marshalled to the JSON column; nil -> NULL
}

// RecordAudit appends an audit_logs row. Best-effort callers may ignore the
// error, but writes that are part of a tenant action should propagate it.
func RecordAudit(ctx context.Context, q execer, a Audit) error {
	var details any
	if a.Details != nil {
		b, err := json.Marshal(a.Details)
		if err != nil {
			return err
		}
		details = string(b)
	}
	_, err := q.ExecContext(ctx,
		`INSERT INTO audit_logs(id, org_id, user_id, deal_id, action, resource_type, resource_id, details, created_at)
		 VALUES (?,?,?,?,?,?,?,?,?)`,
		util.NewUUID(), a.OrgID, a.UserID, a.DealID, a.Action, a.ResourceType, a.ResourceID, details, util.NowISO())
	return err
}
