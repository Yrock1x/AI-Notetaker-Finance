package model

// Transcript is one transcripts row (ports app/db/models.py Transcript). One per
// meeting (unique meeting_id). Nullable columns are pointer types.
type Transcript struct {
	ID              string
	OrgID           string
	MeetingID       string
	FullText        string
	Language        string
	WordCount       int
	ConfidenceScore *float64
	CreatedAt       string
	UpdatedAt       string
}

// TranscriptSegment is one transcript_segments row (ports TranscriptSegment).
// No org_id column — tenant isolation is via the parent meeting.
type TranscriptSegment struct {
	ID           string
	TranscriptID *string
	MeetingID    string
	SpeakerLabel string
	SpeakerName  *string
	Text         string
	StartTime    float64
	EndTime      float64
	Confidence   *float64
	SegmentIndex int
	IsPartial    bool
	CreatedAt    string
	UpdatedAt    string
}

// MeetingParticipant is one meeting_participants row (ports MeetingParticipant).
// No org_id column — tenant isolation is via the parent meeting.
type MeetingParticipant struct {
	ID           string
	MeetingID    string
	SpeakerLabel string
	SpeakerName  *string
	UserID       *string
	EmailAddress *string
	JoinedAt     *string
	LeftAt       *string
	CreatedAt    string
	UpdatedAt    string
}

// MeetingChatMessage is one meeting_chat_messages row (ports MeetingChatMessage).
type MeetingChatMessage struct {
	ID          string
	MeetingID   string
	OrgID       string
	SenderName  *string
	SenderEmail *string
	Text        string
	SentAt      string
	CreatedAt   string
}
