package store

import (
	"context"
	"database/sql"
	"errors"
	"strings"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/model"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/util"
)

const analysisCols = "id, org_id, meeting_id, call_type, structured_output, model_used, prompt_version, grounding_score, status, error_message, requested_by, version, created_at, updated_at"

func scanAnalysis(row interface{ Scan(...any) error }) (*model.Analysis, error) {
	var a model.Analysis
	err := row.Scan(&a.ID, &a.OrgID, &a.MeetingID, &a.CallType, &a.StructuredOutput,
		&a.ModelUsed, &a.PromptVersion, &a.GroundingScore, &a.Status, &a.ErrorMessage,
		&a.RequestedBy, &a.Version, &a.CreatedAt, &a.UpdatedAt)
	return &a, err
}

// RequireMeetingOrg resolves the meeting's owning org and 404s (ErrNotFound)
// unless the principal is a member of it (ports analysis.py _require_meeting_org).
// A missing meeting and a foreign-org meeting are indistinguishable — both 404.
func RequireMeetingOrg(ctx context.Context, conn *sql.DB, p *Principal, meetingID string) (string, error) {
	orgID, err := MeetingOrgID(ctx, conn, meetingID)
	if errors.Is(err, sql.ErrNoRows) {
		return "", ErrNotFound
	}
	if err != nil {
		return "", err
	}
	if !p.InOrg(orgID) {
		return "", ErrNotFound
	}
	return orgID, nil
}

// ListAnalyses returns every analysis for a meeting, newest-first (ports
// AnalysisService.list_analyses). Org-scoped: rows are restricted to the
// principal's orgs so a meeting_id can never surface another tenant's analyses.
func ListAnalyses(ctx context.Context, conn *sql.DB, p *Principal, meetingID string) ([]model.Analysis, error) {
	pred, args := p.OrgFilter("org_id")
	q := "SELECT " + analysisCols + " FROM analyses WHERE meeting_id = ? AND " + pred +
		" ORDER BY created_at DESC"
	rows, err := conn.QueryContext(ctx, q, append([]any{meetingID}, args...)...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]model.Analysis, 0)
	for rows.Next() {
		a, err := scanAnalysis(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, *a)
	}
	return out, rows.Err()
}

// GetAnalysis returns a single analysis by id, org-scoped to the principal (ports
// AnalysisService.get_analysis + the analysis.py meeting-ownership check). It is
// org-scoped (not just meeting-scoped) so the lookup never reads a foreign
// tenant's row; the handler additionally asserts meeting_id == the path meeting.
func GetAnalysis(ctx context.Context, conn *sql.DB, p *Principal, analysisID string) (*model.Analysis, error) {
	pred, args := p.OrgFilter("org_id")
	q := "SELECT " + analysisCols + " FROM analyses WHERE id = ? AND " + pred
	a, err := scanAnalysis(conn.QueryRowContext(ctx, q, append([]any{analysisID}, args...)...))
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	return a, err
}

// NextAnalysisVersion returns the next version for a (meeting, call_type) tuple
// (ports AnalysisService._next_version) — 1 if none exist yet.
func NextAnalysisVersion(ctx context.Context, conn *sql.DB, meetingID, callType string) (int, error) {
	var latest sql.NullInt64
	err := conn.QueryRowContext(ctx,
		"SELECT MAX(version) FROM analyses WHERE meeting_id = ? AND call_type = ?",
		meetingID, callType).Scan(&latest)
	if err != nil {
		return 0, err
	}
	if latest.Valid {
		return int(latest.Int64) + 1, nil
	}
	return 1, nil
}

// FetchTranscriptText renders the meeting's finalized transcript segments,
// ordered by start_time, as speaker-attributed lines (ports
// AnalysisService._fetch_transcript_text). The label is speaker_name, else
// speaker_label, else "Speaker".
func FetchTranscriptText(ctx context.Context, conn *sql.DB, meetingID string) (string, error) {
	rows, err := conn.QueryContext(ctx,
		"SELECT speaker_label, speaker_name, text FROM transcript_segments "+
			"WHERE meeting_id = ? AND is_partial = 0 ORDER BY start_time",
		meetingID)
	if err != nil {
		return "", err
	}
	defer rows.Close()
	var lines []string
	for rows.Next() {
		var speakerLabel sql.NullString
		var speakerName sql.NullString
		var text sql.NullString
		if err := rows.Scan(&speakerLabel, &speakerName, &text); err != nil {
			return "", err
		}
		label := "Speaker"
		if speakerName.Valid && speakerName.String != "" {
			label = speakerName.String
		} else if speakerLabel.Valid && speakerLabel.String != "" {
			label = speakerLabel.String
		}
		lines = append(lines, label+": "+strings.TrimSpace(text.String))
	}
	if err := rows.Err(); err != nil {
		return "", err
	}
	return strings.Join(lines, "\n"), nil
}

// MeetingDealName returns the meeting's deal name (or "Unknown") for the
// summarization prompt (ports AnalysisService._fetch_meeting_with_deal). The
// meeting must already be org-scoped by the caller (RequireMeetingOrg).
func MeetingDealName(ctx context.Context, conn *sql.DB, meetingID string) (string, error) {
	var dealID sql.NullString
	err := conn.QueryRowContext(ctx,
		"SELECT deal_id FROM meetings WHERE id = ?", meetingID).Scan(&dealID)
	if errors.Is(err, sql.ErrNoRows) {
		return "Unknown", nil
	}
	if err != nil {
		return "", err
	}
	if !dealID.Valid || dealID.String == "" {
		return "Unknown", nil
	}
	var name sql.NullString
	err = conn.QueryRowContext(ctx,
		"SELECT name FROM deals WHERE id = ?", dealID.String).Scan(&name)
	if errors.Is(err, sql.ErrNoRows) {
		return "Unknown", nil
	}
	if err != nil {
		return "", err
	}
	if !name.Valid || name.String == "" {
		return "Unknown", nil
	}
	return name.String, nil
}

// AnalysisInsert is the initial "running" row written before the LLM call
// (ports the Analysis(...) constructor in run_analysis).
type AnalysisInsert struct {
	OrgID         string
	MeetingID     string
	CallType      string
	PromptVersion string
	Version       int
	RequestedBy   *string
}

// InsertRunningAnalysis writes the initial analyses row (status="running",
// model_used="") and returns the populated id/created_at/updated_at, so the
// handler can stamp the result onto it. Ports the session.add + flush.
func InsertRunningAnalysis(ctx context.Context, conn *sql.DB, in AnalysisInsert) (*model.Analysis, error) {
	now, id := util.NowISO(), util.NewUUID()
	promptVer := in.PromptVersion
	if promptVer == "" {
		promptVer = "v1"
	}
	_, err := conn.ExecContext(ctx,
		"INSERT INTO analyses("+analysisCols+") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
		id, in.OrgID, in.MeetingID, in.CallType, nil, "", promptVer, nil,
		"running", nil, in.RequestedBy, in.Version, now, now)
	if err != nil {
		return nil, err
	}
	return GetAnalysisByID(ctx, conn, id)
}

// GetAnalysisByID reads an analysis by id without org-scoping. Used internally to
// re-read a row the caller just inserted (its org is already known/derived).
func GetAnalysisByID(ctx context.Context, conn *sql.DB, id string) (*model.Analysis, error) {
	a, err := scanAnalysis(conn.QueryRowContext(ctx,
		"SELECT "+analysisCols+" FROM analyses WHERE id = ?", id))
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	return a, err
}

// CompleteAnalysis stamps the LLM result onto a running row (ports the success
// branch: structured_output, model_used, prompt_version, status).
func CompleteAnalysis(ctx context.Context, conn *sql.DB, id string, structuredOutput []byte, modelUsed, promptVersion, status string) (*model.Analysis, error) {
	now := util.NowISO()
	_, err := conn.ExecContext(ctx,
		"UPDATE analyses SET structured_output = ?, model_used = ?, prompt_version = ?, status = ?, updated_at = ? WHERE id = ?",
		structuredOutput, modelUsed, promptVersion, status, now, id)
	if err != nil {
		return nil, err
	}
	return GetAnalysisByID(ctx, conn, id)
}

// FailAnalysis marks a running row failed with the error message (ports the
// except branch which commits status="failed" so it survives the rollback).
func FailAnalysis(ctx context.Context, conn *sql.DB, id, errMsg string) error {
	_, err := conn.ExecContext(ctx,
		"UPDATE analyses SET status = 'failed', error_message = ?, updated_at = ? WHERE id = ?",
		errMsg, util.NowISO(), id)
	return err
}
