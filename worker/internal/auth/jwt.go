// Package auth ports the worker's self-issued session JWTs (app/auth/tokens.py)
// and password hashing (app/auth/passwords.py). Same HS256 secret + claim shape
// as the Python worker, so cookies issued by either verify in the other across
// the cutover.
package auth

import (
	"errors"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

const (
	issuer     = "cognisuite-worker"
	DefaultTTL = 7 * 24 * time.Hour
)

// Claims mirrors the Python token: sub (Subject), email, iss, iat, exp.
type Claims struct {
	Email string `json:"email"`
	jwt.RegisteredClaims
}

// IssueSessionToken signs an HS256 session token (ports issue_session_token).
func IssueSessionToken(secret, userID, email string, ttl time.Duration) (string, error) {
	now := time.Now()
	c := Claims{
		Email: email,
		RegisteredClaims: jwt.RegisteredClaims{
			Subject:   userID,
			Issuer:    issuer,
			IssuedAt:  jwt.NewNumericDate(now),
			ExpiresAt: jwt.NewNumericDate(now.Add(ttl)),
		},
	}
	return jwt.NewWithClaims(jwt.SigningMethodHS256, c).SignedString([]byte(secret))
}

// VerifySessionToken validates a self-issued token and returns its claims, or an
// error (ports verify_session_token; signature + issuer + expiry enforced).
func VerifySessionToken(secret, token string) (*Claims, error) {
	c := &Claims{}
	_, err := jwt.ParseWithClaims(token, c, func(t *jwt.Token) (any, error) {
		if _, ok := t.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, errors.New("unexpected signing method")
		}
		return []byte(secret), nil
	}, jwt.WithIssuer(issuer), jwt.WithValidMethods([]string{"HS256"}))
	if err != nil {
		return nil, err
	}
	if c.Subject == "" {
		return nil, errors.New("token missing subject")
	}
	return c, nil
}
