package model

// MeetingBotSession is one meeting_bot_sessions row (mirrors
// app/db/models.py:MeetingBotSession). Nullable columns are pointer types.
type MeetingBotSession struct {
	ID                    string
	OrgID                 string
	DealID                string
	MeetingID             *string
	Platform              string
	MeetingURL            string
	Status                string
	ScheduledStart        *string
	ActualStart           *string
	ActualEnd             *string
	RecordingFileKey      *string
	RecallBotID           *string
	LiveTranscriptChannel *string
	ConsentObtained       bool
	CreatedBy             string
	CreatedAt             string
	UpdatedAt             string
}
