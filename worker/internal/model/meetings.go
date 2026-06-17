package model

// Meeting is one meetings row. Mirrors app/db/models.py Meeting (+ the
// UUIDPrimaryKey/Timestamps mixins). Nullable columns are pointer types so the
// JSON wire shape can distinguish null from empty, matching the Python
// MeetingResponse (id, org_id, deal_id, title, meeting_date, duration_seconds,
// source, source_url, file_key, status, error_message, bot_enabled,
// external_event_id, external_provider, created_by, created_at, updated_at).
//
// meeting_date / created_at / updated_at are stored as ISO-8601 strings (the
// Python worker stores them via utcnow_iso / .isoformat()); we round-trip the
// raw string so the wire format stays byte-identical.
type Meeting struct {
	ID               string
	OrgID            string
	DealID           *string
	Title            string
	MeetingDate      *string
	DurationSeconds  *int64
	Source           string
	SourceURL        *string
	FileKey          *string
	Status           string
	ErrorMessage     *string
	BotEnabled       bool
	ExternalEventID  *string
	ExternalProvider *string
	CreatedBy        string
	CreatedAt        string
	UpdatedAt        string
}
