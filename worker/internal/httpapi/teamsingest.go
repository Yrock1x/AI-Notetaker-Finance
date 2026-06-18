package httpapi

import (
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"strings"
	"time"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/crypto/fernet"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/integrations/graph"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/integrations/oauth"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/store"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/util"
)

// teamsingest.go ports teams_ingest_call_record + ensure_microsoft_subscription
// (app/api/v1/internal/{ingest,calendar}.py): the MS Graph call-record ingest +
// change-notification subscription machinery. The most inert surface — it only
// runs once a Graph subscription is live and Teams call records arrive.

// graphHTTPClient is the HTTP client Graph calls use; a package var so tests can
// intercept the Graph API.
var graphHTTPClient = &http.Client{Timeout: 30 * time.Second}

func (s *Server) graphClient() *graph.Client {
	c := graph.New()
	c.HTTPClient = graphHTTPClient
	return c
}

// microsoftAccessToken resolves a valid Graph access token for (org,user).
func (s *Server) microsoftAccessToken(ctx context.Context, orgID, userID string) (string, error) {
	fkey, err := fernet.ParseKey(s.Cfg.TokenEncryptionKey)
	if err != nil {
		return "", err
	}
	return store.GetValidAccessToken(ctx, s.DB, fkey, oauth.Microsoft,
		s.Cfg.MicrosoftClientID, s.Cfg.MicrosoftClientSecret, oauthHTTPClient, orgID, userID, "microsoft")
}

// nested-map helpers for the dynamic Graph call-record JSON.
func mObj(m map[string]any, key string) map[string]any {
	v, _ := m[key].(map[string]any)
	return v
}
func mStr(m map[string]any, key string) string {
	v, _ := m[key].(string)
	return v
}

// POST /internal/teams/ingest-call-record  {call_record_id, tenant_id?}
func (s *Server) internalTeamsIngest(w http.ResponseWriter, r *http.Request) {
	var body struct {
		CallRecordID string `json:"call_record_id"`
		TenantID     string `json:"tenant_id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil || body.CallRecordID == "" {
		writeError(w, http.StatusUnprocessableEntity, "call_record_id is required")
		return
	}
	notHandled := func() {
		writeJSON(w, http.StatusOK, map[string]any{
			"call_record_id": body.CallRecordID, "organizer": nil, "participant_count": 0, "handled": false,
		})
	}

	orgID, userID, _, ok, err := store.FirstActiveMicrosoftCredential(r.Context(), s.DB)
	if storeError(w, err) {
		return
	}
	if !ok {
		notHandled()
		return
	}
	access, err := s.microsoftAccessToken(r.Context(), orgID, userID)
	if err != nil {
		slog.Error("teams ingest token resolve failed", "err", err)
		notHandled()
		return
	}
	record, err := s.graphClient().GetCallRecord(r.Context(), access, body.CallRecordID)
	if err != nil {
		slog.Error("teams ingest call-record fetch failed", "call_record_id", body.CallRecordID, "err", err)
		notHandled()
		return
	}

	organizer := mStr(mObj(mObj(record, "organizer"), "user"), "displayName")
	participants, _ := record["participants"].([]any)

	// Match an existing microsoft meeting in a ±30min window of the first session.
	meetingID := ""
	if sessions, _ := record["sessions"].([]any); len(sessions) > 0 {
		if first, ok := sessions[0].(map[string]any); ok {
			if start := mStr(first, "startDateTime"); start != "" {
				ws, we := start, start
				if t, perr := time.Parse(time.RFC3339, start); perr == nil {
					ws = t.Add(-30 * time.Minute).Format(time.RFC3339)
					we = t.Add(30 * time.Minute).Format(time.RFC3339)
				}
				if id, found, merr := store.MatchMicrosoftMeeting(r.Context(), s.DB, orgID, ws, we); merr == nil && found {
					meetingID = id
				}
			}
		}
	}
	if meetingID != "" {
		_ = store.SetMeetingStatus(r.Context(), s.DB, meetingID, "uploaded", nil)
	} else {
		title := "Teams call"
		if organizer != "" {
			title = "Teams call w/ " + organizer
		}
		meetingID, err = store.CreateTeamsMeeting(r.Context(), s.DB, orgID, title, userID, body.CallRecordID)
		if storeError(w, err) {
			return
		}
	}

	for _, pv := range participants {
		p, _ := pv.(map[string]any)
		if p == nil {
			continue
		}
		identity := mObj(p, "user")
		displayName := mStr(identity, "displayName")
		if displayName == "" {
			displayName = mStr(p, "displayName")
		}
		upn := mStr(identity, "userPrincipalName")
		if upn == "" {
			upn = mStr(p, "userPrincipalName")
		}
		externalID := mStr(p, "id")
		if externalID == "" {
			externalID = mStr(identity, "id")
		}
		if externalID == "" && displayName == "" {
			continue
		}
		label := displayName
		if label == "" {
			if upn != "" {
				label = upn
			} else if externalID != "" {
				label = externalID
			} else {
				label = "Unknown"
			}
		}
		_ = store.UpsertTeamsParticipant(r.Context(), s.DB, meetingID, label,
			strPtrOrNil(displayName), strPtrOrNil(upn), strPtrOrNil(externalID))
	}

	var org any
	if organizer != "" {
		org = organizer
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"call_record_id": body.CallRecordID, "organizer": org,
		"participant_count": len(participants), "handled": true,
	})
}

func strPtrOrNil(s string) *string {
	if s == "" {
		return nil
	}
	return &s
}

// POST /internal/microsoft/ensure-subscription  {user_id, org_id, resource?}
func (s *Server) internalEnsureSubscription(w http.ResponseWriter, r *http.Request) {
	var body struct {
		UserID   string `json:"user_id"`
		OrgID    string `json:"org_id"`
		Resource string `json:"resource"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil || body.UserID == "" || body.OrgID == "" {
		writeError(w, http.StatusUnprocessableEntity, "user_id and org_id are required")
		return
	}
	resource := body.Resource
	if resource == "" {
		resource = "communications/callRecords"
	}
	access, err := s.microsoftAccessToken(r.Context(), body.OrgID, body.UserID)
	if err == store.ErrNotFound {
		writeError(w, http.StatusNotFound, "No active microsoft credentials for user")
		return
	}
	if err != nil {
		writeError(w, http.StatusBadGateway, "Microsoft Graph unavailable")
		return
	}

	notificationURL := strings.TrimRight(s.Cfg.PublicAPIURL, "/") + "/api/v1/webhooks/teams"
	clientState := s.Cfg.MicrosoftWebhookSecret
	if clientState == "" {
		clientState = util.NewUUID()
	}
	renewalThreshold := time.Now().Add(24 * time.Hour)

	existing, err := store.ActiveGraphSubscription(r.Context(), s.DB, body.UserID, resource)
	if storeError(w, err) {
		return
	}
	if existing != nil {
		if exp, perr := time.Parse(time.RFC3339, existing.Expiration); perr == nil && exp.After(renewalThreshold) {
			writeJSON(w, http.StatusOK, map[string]any{"subscription_id": existing.ID, "expiration": existing.Expiration, "action": "noop"})
			return
		}
		if renewed, rerr := s.graphClient().RenewSubscription(r.Context(), access, existing.ID, 4230); rerr == nil {
			_ = store.UpdateGraphSubscriptionExpiration(r.Context(), s.DB, existing.ID, renewed.ExpirationDateTime)
			writeJSON(w, http.StatusOK, map[string]any{"subscription_id": existing.ID, "expiration": renewed.ExpirationDateTime, "action": "renewed"})
			return
		}
		// Renew failed — deactivate so we re-create below.
		_ = store.DeactivateGraphSubscription(r.Context(), s.DB, existing.ID)
	}

	created, err := s.graphClient().SubscribeCallRecords(r.Context(), access, notificationURL, clientState, 4230)
	if err != nil {
		writeError(w, http.StatusBadGateway, "Graph subscription create failed")
		return
	}
	if storeError(w, store.UpsertGraphSubscription(r.Context(), s.DB, store.GraphSub{
		ID: created.ID, OrgID: body.OrgID, UserID: body.UserID, Resource: resource,
		ClientState: clientState, NotificationURL: notificationURL, Expiration: created.ExpirationDateTime,
	})) {
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"subscription_id": created.ID, "expiration": created.ExpirationDateTime, "action": "created"})
}
