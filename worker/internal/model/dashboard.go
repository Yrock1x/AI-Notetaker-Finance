package model

// Dashboard read-model row structs. These mirror the projected columns selected
// by the dashboard endpoints (app/api/v1/store/dashboard.py), not whole tables:
// the activity feed and extractions are joins/projections, while ActionItem is
// the action_item_completions table (see app/db/models.py ActionItemCompletion).

// ActivityRow is one audit_logs row projected with the actor's profile name and
// the deal's name (the shape behind ActivityResponse). DealID/DealName/ActorName
// are nullable on the wire — audit rows may have no deal (deal_id NULL) and the
// outer joins to profiles/deals may miss. Details holds the raw JSON of the
// audit_logs.details column (NULL -> JSON null).
type ActivityRow struct {
	ID           string
	Action       string
	ResourceType string
	ResourceID   *string
	DealID       *string
	DealName     *string
	ActorName    *string
	CreatedAt    string
	Details      *string // raw JSON text from the details column; nil = NULL
}

// ExtractionRow is a completed analyses row projected to the columns the
// extractions feed exposes (behind ExtractionResponse). StructuredOutput holds
// the raw JSON text of analyses.structured_output (NULL -> JSON null).
type ExtractionRow struct {
	ID               string
	MeetingID        string
	CallType         string
	StructuredOutput *string // raw JSON text from structured_output; nil = NULL
	CreatedAt        string
}

// ActionItem is an action_item_completions row, restricted to the columns the
// action-items endpoints return (behind ActionItemResponse). ActionText is
// nullable in the schema (action_text TEXT).
type ActionItem struct {
	ActionKey   string
	ActionText  *string
	AnalysisID  string
	CompletedBy string
	CompletedAt string
}
