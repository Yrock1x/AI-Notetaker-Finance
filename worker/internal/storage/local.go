// Package storage is the local-filesystem object store + HMAC-signed URL helpers
// (ports app/storage/local.py). Files live under {root}/{bucket}/{key}; a
// short-lived HMAC-SHA256 signature over "METHOD:bucket:key:expires" IS the
// capability to read/write that object.
package storage

import (
	"crypto/hmac"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// Buckets that exist (deliverables are produced server-side).
var Buckets = map[string]bool{
	"meeting-recordings": true,
	"deal-documents":     true,
	"deliverables":       true,
}

var (
	ErrUnknownBucket = errors.New("unknown bucket")
	ErrUnsafeKey     = errors.New("unsafe key")
)

// safePath resolves {root}/{bucket}/{key}, guaranteeing the result stays inside
// the bucket dir (defends against path traversal via the key).
func safePath(root, bucket, key string) (string, error) {
	if !Buckets[bucket] {
		return "", ErrUnknownBucket
	}
	if strings.HasPrefix(key, "/") {
		return "", ErrUnsafeKey
	}
	bucketRoot, err := filepath.Abs(filepath.Join(root, bucket))
	if err != nil {
		return "", err
	}
	candidate, err := filepath.Abs(filepath.Join(bucketRoot, filepath.FromSlash(key)))
	if err != nil {
		return "", err
	}
	if candidate != bucketRoot && !strings.HasPrefix(candidate, bucketRoot+string(os.PathSeparator)) {
		return "", ErrUnsafeKey
	}
	return candidate, nil
}

// SaveBytes writes data to {root}/{bucket}/{key}, creating parent dirs.
func SaveBytes(root, bucket, key string, data []byte) error {
	p, err := safePath(root, bucket, key)
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
		return err
	}
	return os.WriteFile(p, data, 0o644)
}

// ObjectPath returns the traversal-safe on-disk path (for streaming downloads).
func ObjectPath(root, bucket, key string) (string, error) {
	return safePath(root, bucket, key)
}

// Exists reports whether the object is a regular file.
func Exists(root, bucket, key string) bool {
	p, err := safePath(root, bucket, key)
	if err != nil {
		return false
	}
	fi, err := os.Stat(p)
	return err == nil && fi.Mode().IsRegular()
}

// sign computes the method-bound HMAC-SHA256 hex signature.
func sign(signingKey, method, bucket, key string, expiresAt int64) string {
	msg := fmt.Sprintf("%s:%s:%s:%d", strings.ToUpper(method), bucket, key, expiresAt)
	mac := hmac.New(sha256.New, []byte(signingKey))
	mac.Write([]byte(msg))
	return hex.EncodeToString(mac.Sum(nil))
}

// MakeSignedURL returns a relative capability URL valid for ttl seconds.
func MakeSignedURL(signingKey, bucket, key, method string, ttl time.Duration) string {
	exp := time.Now().Unix() + int64(ttl.Seconds())
	sig := sign(signingKey, method, bucket, key, exp)
	return fmt.Sprintf("/api/v1/storage/%s/%s?expires=%d&sig=%s", bucket, key, exp, sig)
}

// Verify checks expiry + the method-bound signature (constant-time).
func Verify(signingKey, method, bucket, key string, expiresAt int64, sig string) bool {
	if time.Now().Unix() > expiresAt {
		return false
	}
	expected := sign(signingKey, method, bucket, key, expiresAt)
	return subtle.ConstantTimeCompare([]byte(expected), []byte(sig)) == 1
}
