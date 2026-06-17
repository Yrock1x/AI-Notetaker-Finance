package model

// Deliverable is the JSON returned by POST /deals/{dealID}/deliverables/generate
// (matches the dict in DeliverableService.generate). Deliverables are not
// persisted in the current schema — this is built fresh per request.
type Deliverable struct {
	ID              string `json:"id"`
	DealID          string `json:"deal_id"`
	Title           string `json:"title"`
	DeliverableType string `json:"deliverable_type"`
	FileFormat      string `json:"file_format"`
	FileKey         string `json:"file_key"`
	Status          string `json:"status"`
	DownloadURL     string `json:"download_url"`
	CreatedAt       string `json:"created_at"`
}

// DeliverableChatMessage is the JSON returned by POST
// /deals/{dealID}/deliverables/chat (matches the dict in deliverable_chat).
type DeliverableChatMessage struct {
	ID        string `json:"id"`
	DealID    string `json:"deal_id"`
	Role      string `json:"role"`
	Content   string `json:"content"`
	CreatedAt string `json:"created_at"`
}
