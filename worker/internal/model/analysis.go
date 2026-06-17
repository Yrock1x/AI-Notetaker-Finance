package model

// Analysis is one analyses row. Mirrors app/db/models.py Analysis. Columns:
// id, org_id, meeting_id, call_type, structured_output (JSON), model_used,
// prompt_version, grounding_score, status, error_message, requested_by, version,
// created_at, updated_at.
//
// StructuredOutput is the raw JSON blob as stored; the handler unmarshals it into
// an `any` for the wire response (matching the Python dict[str, Any] | None).
// created_at / updated_at are ISO-8601 strings round-tripped verbatim.
type Analysis struct {
	ID               string
	OrgID            string
	MeetingID        string
	CallType         string
	StructuredOutput []byte // JSON, may be NULL
	ModelUsed        string
	PromptVersion    string
	GroundingScore   *float64
	Status           string
	ErrorMessage     *string
	RequestedBy      *string
	Version          int
	CreatedAt        string
	UpdatedAt        string
}
