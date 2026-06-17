// Package config loads runtime configuration from the environment, mirroring the
// Python worker's app/core/config.py (same env var names + defaults) so the Go
// worker is a drop-in on the same Railway service + env.
package config

import (
	"encoding/base64"
	"fmt"
	"os"
	"strings"
)

type Config struct {
	AppEnv string // development | staging | production
	Port   string

	// SQLite data layer
	SQLiteDBPath string
	StorageRoot  string

	// Signing / auth secrets
	SessionJWTSecret    string
	StorageSigningKey   string
	WorkerInternalToken string
	SessionCookieName   string

	// LLM
	FireworksAPIKey   string
	PremiumLLMEnabled bool
	AnthropicAPIKey   string

	// Transcription / bots
	RecallAPIKey        string
	RecallWebhookSecret string

	// Encryption (Fernet) for stored OAuth refresh tokens
	TokenEncryptionKey string

	// CogniVault OAuth (this worker is the client). Empty client id => the
	// connect flow reports "not configured" (same as the Python worker).
	CognivaultClientID string

	// Web / CORS
	CORSOrigins     string // comma-separated
	CORSOriginRegex string
	FrontendURL     string
	PublicAPIURL    string
}

func env(key, def string) string {
	if v, ok := os.LookupEnv(key); ok {
		return v
	}
	return def
}

func envBool(key string, def bool) bool {
	v, ok := os.LookupEnv(key)
	if !ok {
		return def
	}
	switch strings.ToLower(strings.TrimSpace(v)) {
	case "1", "true", "yes", "on":
		return true
	default:
		return false
	}
}

// Load reads the environment. Defaults match app/core/config.py.
func Load() *Config {
	return &Config{
		AppEnv:              env("APP_ENV", "development"),
		Port:                env("PORT", "8000"),
		SQLiteDBPath:        env("SQLITE_DB_PATH", "/data/app.db"),
		StorageRoot:         env("STORAGE_ROOT", "/data/storage"),
		SessionJWTSecret:    env("SESSION_JWT_SECRET", ""),
		StorageSigningKey:   env("STORAGE_SIGNING_KEY", ""),
		WorkerInternalToken: env("WORKER_INTERNAL_TOKEN", ""),
		SessionCookieName:   env("SESSION_COOKIE_NAME", "cogni_session"),
		FireworksAPIKey:     env("FIREWORKS_API_KEY", ""),
		PremiumLLMEnabled:   envBool("PREMIUM_LLM_ENABLED", false),
		AnthropicAPIKey:     env("ANTHROPIC_API_KEY", ""),
		RecallAPIKey:        env("RECALL_API_KEY", ""),
		RecallWebhookSecret: env("RECALL_WEBHOOK_SECRET", ""),
		TokenEncryptionKey:  env("TOKEN_ENCRYPTION_KEY", ""),
		CognivaultClientID:  env("COGNIVAULT_CLIENT_ID", ""),
		CORSOrigins:         env("CORS_ORIGINS", "http://localhost:3000"),
		CORSOriginRegex:     env("CORS_ORIGIN_REGEX", ""),
		FrontendURL:         env("FRONTEND_URL", "http://localhost:3000"),
		PublicAPIURL:        env("PUBLIC_API_URL", "http://localhost:8000"),
	}
}

func (c *Config) IsProduction() bool { return c.AppEnv == "production" }

// SessionSigningSecret returns the HS256 secret for session JWTs, mirroring
// app/auth/tokens.py: SESSION_JWT_SECRET, falling back to WORKER_INTERNAL_TOKEN
// only outside production (prod boot requires SESSION_JWT_SECRET via Validate).
func (c *Config) SessionSigningSecret() (string, error) {
	if c.SessionJWTSecret != "" {
		return c.SessionJWTSecret, nil
	}
	if !c.IsProduction() && c.WorkerInternalToken != "" {
		return c.WorkerInternalToken, nil
	}
	return "", fmt.Errorf("no session signing secret configured (set SESSION_JWT_SECRET)")
}

// StorageSigningKeyOrFallback mirrors the Python fallback to worker_internal_token
// in non-prod. In production the validator requires it set explicitly + distinct.
func (c *Config) StorageSigningKeyOrFallback() string {
	if c.StorageSigningKey != "" {
		return c.StorageSigningKey
	}
	return c.WorkerInternalToken
}

func (c *Config) CORSOriginList() []string {
	var out []string
	for _, o := range strings.Split(c.CORSOrigins, ",") {
		if s := strings.TrimSpace(o); s != "" {
			out = append(out, s)
		}
	}
	return out
}

// Validate fails fast in production on missing/weak secrets — a 1:1 port of
// app/core/config.py _require_prod_secrets (the "H1" hardening). In dev it's a
// no-op (the worker runs without provider keys and errors clearly on first use).
func (c *Config) Validate() error {
	if !c.IsProduction() {
		return nil
	}
	var missing []string
	if c.TokenEncryptionKey == "" {
		missing = append(missing, "TOKEN_ENCRYPTION_KEY")
	}
	if c.FireworksAPIKey == "" {
		missing = append(missing, "FIREWORKS_API_KEY")
	}
	if c.SessionJWTSecret == "" {
		missing = append(missing, "SESSION_JWT_SECRET")
	}
	if c.StorageSigningKey == "" {
		missing = append(missing, "STORAGE_SIGNING_KEY")
	}
	if c.WorkerInternalToken == "" {
		missing = append(missing, "WORKER_INTERNAL_TOKEN")
	}
	if c.RecallAPIKey != "" && c.RecallWebhookSecret == "" {
		missing = append(missing, "RECALL_WEBHOOK_SECRET")
	}
	if len(missing) > 0 {
		return fmt.Errorf("missing required production env vars: %s", strings.Join(missing, ", "))
	}

	signing := map[string]string{
		"SESSION_JWT_SECRET":    c.SessionJWTSecret,
		"STORAGE_SIGNING_KEY":   c.StorageSigningKey,
		"WORKER_INTERNAL_TOKEN": c.WorkerInternalToken,
	}
	seen := map[string]bool{}
	for name, val := range signing {
		if len(val) < 32 {
			return fmt.Errorf("%s must be at least 32 characters in production", name)
		}
		if seen[val] {
			return fmt.Errorf("SESSION_JWT_SECRET, STORAGE_SIGNING_KEY, and WORKER_INTERNAL_TOKEN must all be distinct in production")
		}
		seen[val] = true
	}

	// TOKEN_ENCRYPTION_KEY must be a valid Fernet key: urlsafe-base64 of 32 bytes.
	if raw, err := base64.URLEncoding.DecodeString(c.TokenEncryptionKey); err != nil || len(raw) != 32 {
		return fmt.Errorf("TOKEN_ENCRYPTION_KEY is not a valid Fernet key (want urlsafe-base64 of 32 bytes)")
	}

	if c.PremiumLLMEnabled && c.AnthropicAPIKey == "" {
		return fmt.Errorf("PREMIUM_LLM_ENABLED=true but ANTHROPIC_API_KEY is empty")
	}
	return nil
}
