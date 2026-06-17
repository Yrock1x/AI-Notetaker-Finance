package auth

import (
	"os"
	"testing"
	"time"
)

func TestIssueVerifyRoundTrip(t *testing.T) {
	secret := "round-trip-secret-0123456789abcdef"
	tok, err := IssueSessionToken(secret, "user-123", "a@b.com", DefaultTTL)
	if err != nil {
		t.Fatalf("issue: %v", err)
	}
	c, err := VerifySessionToken(secret, tok)
	if err != nil {
		t.Fatalf("verify: %v", err)
	}
	if c.Subject != "user-123" || c.Email != "a@b.com" {
		t.Fatalf("claims=%+v", c)
	}
	if c.ExpiresAt == nil || c.ExpiresAt.Before(time.Now()) {
		t.Fatalf("missing/expired exp")
	}
	// wrong secret must fail
	if _, err := VerifySessionToken("other-secret-0123456789abcdef00", tok); err == nil {
		t.Fatalf("verify with wrong secret should fail")
	}
}

// TestVerifyPythonToken proves cross-compat: a token the PYTHON worker issued
// (same SESSION_JWT_SECRET) verifies in Go — required so existing users' cookies
// survive the cutover. Driven by env (set by the harness); skipped otherwise.
func TestVerifyPythonToken(t *testing.T) {
	secret, tok := os.Getenv("PY_SECRET"), os.Getenv("PY_TOKEN")
	if secret == "" || tok == "" {
		t.Skip("set PY_SECRET + PY_TOKEN (a Python-issued token) to run cross-compat")
	}
	c, err := VerifySessionToken(secret, tok)
	if err != nil {
		t.Fatalf("python token failed to verify in Go: %v", err)
	}
	if c.Subject == "" {
		t.Fatalf("python token verified but has no subject: %+v", c)
	}
	t.Logf("cross-compat OK: sub=%s email=%s iss=%s", c.Subject, c.Email, c.Issuer)
}
