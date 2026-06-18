package store

import (
	"context"
	"database/sql"
	"errors"
	"time"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/crypto/fernet"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/util"
	"github.com/golang-jwt/jwt/v5"
)

// oauthtokens.go ports app/services/oauth_tokens.py: the signed OAuth state token
// + Fernet-encrypted credential storage in integration_credentials.

const oauthStateTTL = 10 * time.Minute

// OAuthStateClaims is what the signed state carries across the OAuth redirect so
// the callback can trust org/user/platform without reading the query string.
type OAuthStateClaims struct {
	OrgID    string `json:"org_id"`
	UserID   string `json:"user_id"`
	Platform string `json:"platform"`
	Nonce    string `json:"nonce"`
	jwt.RegisteredClaims
}

// BuildOAuthState signs an HS256 state JWT (ports build_state).
func BuildOAuthState(secret, orgID, userID, platform string) (string, error) {
	now := time.Now()
	c := OAuthStateClaims{
		OrgID: orgID, UserID: userID, Platform: platform, Nonce: util.NewUUID(),
		RegisteredClaims: jwt.RegisteredClaims{
			IssuedAt:  jwt.NewNumericDate(now),
			ExpiresAt: jwt.NewNumericDate(now.Add(oauthStateTTL)),
		},
	}
	return jwt.NewWithClaims(jwt.SigningMethodHS256, c).SignedString([]byte(secret))
}

// VerifyOAuthState validates + parses a state JWT (ports verify_state). exp is
// enforced by the parser.
func VerifyOAuthState(secret, state string) (*OAuthStateClaims, error) {
	c := &OAuthStateClaims{}
	_, err := jwt.ParseWithClaims(state, c, func(t *jwt.Token) (any, error) {
		if _, ok := t.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, errors.New("unexpected signing method")
		}
		return []byte(secret), nil
	}, jwt.WithValidMethods([]string{"HS256"}))
	if err != nil {
		return nil, err
	}
	return c, nil
}

// DefaultOrgForUser returns the user's first org membership, the default scope
// for a credential row (ports _resolve_default_org). ErrNotFound if none.
func DefaultOrgForUser(ctx context.Context, conn *sql.DB, userID string) (string, error) {
	var org string
	err := conn.QueryRowContext(ctx,
		"SELECT org_id FROM org_memberships WHERE user_id = ? LIMIT 1", userID).Scan(&org)
	if errors.Is(err, sql.ErrNoRows) {
		return "", ErrNotFound
	}
	return org, err
}

// CredentialInput is a token set to persist (ports save_credentials args).
type CredentialInput struct {
	OrgID, UserID, Platform string
	AccessToken             string
	RefreshToken            string // "" -> NULL
	ExpiresInSeconds        int    // 0 -> no expiry recorded
	Scopes                  string // "" -> NULL
}

// SaveCredentials upserts an integration_credentials row keyed on
// (org_id, user_id, platform), Fernet-encrypting the tokens (ports
// save_credentials). A missing refresh token is stored as NULL.
func SaveCredentials(ctx context.Context, conn *sql.DB, fkey *fernet.Key, in CredentialInput) error {
	accessEnc, err := fkey.Encrypt([]byte(in.AccessToken))
	if err != nil {
		return err
	}
	var refreshEnc any
	if in.RefreshToken != "" {
		enc, err := fkey.Encrypt([]byte(in.RefreshToken))
		if err != nil {
			return err
		}
		refreshEnc = enc
	}
	var expiresAt any
	if in.ExpiresInSeconds > 0 {
		expiresAt = time.Now().UTC().Add(time.Duration(in.ExpiresInSeconds) * time.Second).Format(time.RFC3339)
	}
	var scopes any
	if in.Scopes != "" {
		scopes = in.Scopes
	}
	now := util.NowISO()

	var id string
	err = conn.QueryRowContext(ctx,
		"SELECT id FROM integration_credentials WHERE org_id=? AND user_id=? AND platform=?",
		in.OrgID, in.UserID, in.Platform).Scan(&id)
	switch {
	case errors.Is(err, sql.ErrNoRows):
		_, err = conn.ExecContext(ctx,
			`INSERT INTO integration_credentials(id, org_id, user_id, platform,
			    access_token_encrypted, refresh_token_encrypted, token_expires_at,
			    scopes, is_active, created_at, updated_at)
			 VALUES (?,?,?,?,?,?,?,?,?,?,?)`,
			util.NewUUID(), in.OrgID, in.UserID, in.Platform, accessEnc, refreshEnc,
			expiresAt, scopes, true, now, now)
		return err
	case err != nil:
		return err
	default:
		_, err = conn.ExecContext(ctx,
			`UPDATE integration_credentials SET access_token_encrypted=?,
			    refresh_token_encrypted=?, token_expires_at=?, scopes=?, is_active=1,
			    updated_at=? WHERE id=?`,
			accessEnc, refreshEnc, expiresAt, scopes, now, id)
		return err
	}
}

// DeactivateCredentials soft-deletes a user's platform credentials (ports
// deactivate_credentials).
func DeactivateCredentials(ctx context.Context, conn *sql.DB, orgID, userID, platform string) error {
	_, err := conn.ExecContext(ctx,
		"UPDATE integration_credentials SET is_active=0, updated_at=? WHERE org_id=? AND user_id=? AND platform=?",
		util.NowISO(), orgID, userID, platform)
	return err
}

// IntegrationRow is the list shape the integrations page reads — it filters on
// is_active (ports list_user_integrations).
type IntegrationRow struct {
	Platform       string  `json:"platform"`
	IsActive       bool    `json:"is_active"`
	Scopes         *string `json:"scopes"`
	ConnectedAt    string  `json:"connected_at"`
	TokenExpiresAt *string `json:"token_expires_at"`
}

// ListUserIntegrations returns the user's active integrations (ports
// list_user_integrations).
func ListUserIntegrations(ctx context.Context, conn *sql.DB, userID string) ([]IntegrationRow, error) {
	rows, err := conn.QueryContext(ctx,
		"SELECT platform, is_active, scopes, created_at, token_expires_at FROM integration_credentials WHERE user_id=? AND is_active=1",
		userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []IntegrationRow{}
	for rows.Next() {
		var r IntegrationRow
		if err := rows.Scan(&r.Platform, &r.IsActive, &r.Scopes, &r.ConnectedAt, &r.TokenExpiresAt); err != nil {
			return nil, err
		}
		out = append(out, r)
	}
	return out, rows.Err()
}
