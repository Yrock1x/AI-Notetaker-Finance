// Package calendar fetches upcoming events from a user's connected calendar and
// normalizes them into meeting rows (ports the per-provider clients +
// /internal/calendar/sync mapping in app/api/v1/internal/calendar.py).
package calendar

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"time"
)

// SyncedMeeting is a calendar event normalized to the columns the meetings
// upsert needs. deal_id is always NULL (assigned later on the calendar page).
type SyncedMeeting struct {
	Title           string
	MeetingDate     string // ISO start
	Source          string // zoom | teams | outlook | meet | upload
	SourceURL       *string
	ExternalEventID string
	BotEnabled      bool
}

var zoomURLRe = regexp.MustCompile(`https?://[^\s"'<>]*zoom\.us/[js]/[^\s"'<>]+`)

func extractZoomURL(s string) string {
	return zoomURLRe.FindString(s)
}

func strp(s string) *string {
	if s == "" {
		return nil
	}
	return &s
}

func doGet(ctx context.Context, hc *http.Client, rawURL, accessToken string) ([]byte, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, rawURL, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+accessToken)
	req.Header.Set("Accept", "application/json")
	resp, err := hc.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 8<<20))
	if resp.StatusCode >= 400 {
		return nil, &APIError{Status: resp.StatusCode}
	}
	return body, nil
}

// APIError marks a non-2xx from a calendar provider.
type APIError struct{ Status int }

func (e *APIError) Error() string { return "calendar provider error" }

// ListZoom fetches upcoming Zoom meetings (ports list_upcoming_meetings + the
// zoom mapping). Returns the normalized rows + the raw event count.
func ListZoom(ctx context.Context, hc *http.Client, accessToken string) ([]SyncedMeeting, int, error) {
	body, err := doGet(ctx, hc, "https://api.zoom.us/v2/users/me/meetings?type=upcoming&page_size=50", accessToken)
	if err != nil {
		return nil, 0, err
	}
	var data struct {
		Meetings []struct {
			ID        json.Number `json:"id"`
			Topic     string      `json:"topic"`
			StartTime string      `json:"start_time"`
			JoinURL   string      `json:"join_url"`
		} `json:"meetings"`
	}
	if err := json.Unmarshal(body, &data); err != nil {
		return nil, 0, err
	}
	out := make([]SyncedMeeting, 0, len(data.Meetings))
	for _, m := range data.Meetings {
		if m.StartTime == "" {
			continue
		}
		title := m.Topic
		if title == "" {
			title = "Zoom meeting"
		}
		out = append(out, SyncedMeeting{
			Title: title, MeetingDate: m.StartTime, Source: "zoom",
			SourceURL: strp(m.JoinURL), ExternalEventID: m.ID.String(), BotEnabled: true,
		})
	}
	return out, len(data.Meetings), nil
}

// ListGraph fetches upcoming Microsoft calendar events (ports get_calendar_events
// + the microsoft mapping).
func ListGraph(ctx context.Context, hc *http.Client, accessToken string, timeMin, timeMax time.Time) ([]SyncedMeeting, int, error) {
	q := url.Values{}
	q.Set("startDateTime", timeMin.Format(time.RFC3339))
	q.Set("endDateTime", timeMax.Format(time.RFC3339))
	q.Set("$select", "subject,start,end,bodyPreview,onlineMeeting,webLink")
	q.Set("$orderby", "start/dateTime")
	q.Set("$top", "50")
	body, err := doGet(ctx, hc, "https://graph.microsoft.com/v1.0/users/me/calendarview?"+q.Encode(), accessToken)
	if err != nil {
		return nil, 0, err
	}
	var data struct {
		Value []struct {
			ID      string `json:"id"`
			Subject string `json:"subject"`
			WebLink string `json:"webLink"`
			Start   struct {
				DateTime string `json:"dateTime"`
			} `json:"start"`
			OnlineMeeting *struct {
				JoinURL string `json:"joinUrl"`
			} `json:"onlineMeeting"`
		} `json:"value"`
	}
	if err := json.Unmarshal(body, &data); err != nil {
		return nil, 0, err
	}
	out := make([]SyncedMeeting, 0, len(data.Value))
	for _, ev := range data.Value {
		if ev.Start.DateTime == "" {
			continue
		}
		joinURL := ""
		if ev.OnlineMeeting != nil {
			joinURL = ev.OnlineMeeting.JoinURL
		}
		source := "outlook"
		if joinURL != "" && strings.Contains(joinURL, "teams.microsoft.com") {
			source = "teams"
		}
		srcURL := joinURL
		if srcURL == "" {
			srcURL = ev.WebLink
		}
		title := ev.Subject
		if title == "" {
			title = "Meeting"
		}
		out = append(out, SyncedMeeting{
			Title: title, MeetingDate: ev.Start.DateTime, Source: source,
			SourceURL: strp(srcURL), ExternalEventID: ev.ID, BotEnabled: joinURL != "",
		})
	}
	return out, len(data.Value), nil
}

// ListGoogle fetches upcoming Google Calendar events (ports list_events +
// extract_meet_url + the google mapping incl. the Zoom-via-Google fallback).
func ListGoogle(ctx context.Context, hc *http.Client, accessToken string, timeMin, timeMax time.Time) ([]SyncedMeeting, int, error) {
	q := url.Values{}
	q.Set("timeMin", timeMin.Format(time.RFC3339))
	q.Set("timeMax", timeMax.Format(time.RFC3339))
	q.Set("singleEvents", "true")
	q.Set("orderBy", "startTime")
	q.Set("maxResults", "100")
	q.Set("conferenceDataVersion", "1")
	body, err := doGet(ctx, hc, "https://www.googleapis.com/calendar/v3/calendars/primary/events?"+q.Encode(), accessToken)
	if err != nil {
		return nil, 0, err
	}
	var data struct {
		Items []struct {
			ID          string `json:"id"`
			Summary     string `json:"summary"`
			HTMLLink    string `json:"htmlLink"`
			HangoutLink string `json:"hangoutLink"`
			Description string `json:"description"`
			Location    string `json:"location"`
			Start       struct {
				DateTime string `json:"dateTime"`
			} `json:"start"`
			ConferenceData *struct {
				EntryPoints []struct {
					EntryPointType string `json:"entryPointType"`
					URI            string `json:"uri"`
				} `json:"entryPoints"`
			} `json:"conferenceData"`
		} `json:"items"`
	}
	if err := json.Unmarshal(body, &data); err != nil {
		return nil, 0, err
	}
	out := make([]SyncedMeeting, 0, len(data.Items))
	for _, ev := range data.Items {
		if ev.Start.DateTime == "" {
			continue // all-day events have no dateTime
		}
		meetURL := ""
		if ev.ConferenceData != nil {
			for _, e := range ev.ConferenceData.EntryPoints {
				if e.EntryPointType == "video" && e.URI != "" {
					meetURL = e.URI
					break
				}
			}
		}
		if meetURL == "" {
			meetURL = ev.HangoutLink
		}
		var source string
		var srcURL string
		switch {
		case meetURL != "":
			source, srcURL = "meet", meetURL
		default:
			if z := extractZoomURL(ev.Description + " " + ev.Location); z != "" {
				source, srcURL = "zoom", z
			} else {
				source, srcURL = "upload", ev.HTMLLink
			}
		}
		title := ev.Summary
		if title == "" {
			title = "Meeting"
		}
		out = append(out, SyncedMeeting{
			Title: title, MeetingDate: ev.Start.DateTime, Source: source,
			SourceURL: strp(srcURL), ExternalEventID: ev.ID,
			BotEnabled: source == "meet" || source == "zoom",
		})
	}
	return out, len(data.Items), nil
}
