package fernet

import (
	"bytes"
	"testing"
)

// The official Fernet spec test vector (generate.json / verify.json). Decrypting
// the token with the key must yield "hello", and encrypting "hello" with the same
// fixed iv + timestamp must reproduce the token byte-for-byte — that proves this
// implementation interops with Python's cryptography.fernet.Fernet.
const (
	specKey   = "cw_0x689RpI-jtRR7oE8h_eQsKImvJapLeSbXpwF4e4="
	specToken = "gAAAAAAdwJ6wAAECAwQFBgcICQoLDA0ODy021cpGVWKZ_eEwCGM4BLLF_5CV9dOPmrhuVUPgJobwOz7JcbmrR64jVmpU4IwqDA=="
	specTS    = int64(499162800) // 1985-10-26T01:20:00-07:00
	specSrc   = "hello"
)

func specIV() []byte {
	iv := make([]byte, 16)
	for i := range iv {
		iv[i] = byte(i)
	}
	return iv
}

func TestDecryptSpecVector(t *testing.T) {
	k, err := ParseKey(specKey)
	if err != nil {
		t.Fatalf("ParseKey: %v", err)
	}
	pt, err := k.Decrypt(specToken)
	if err != nil {
		t.Fatalf("Decrypt: %v", err)
	}
	if string(pt) != specSrc {
		t.Fatalf("decrypted %q, want %q", pt, specSrc)
	}
}

func TestEncryptSpecVector(t *testing.T) {
	k, _ := ParseKey(specKey)
	got, err := k.encryptWith([]byte(specSrc), specIV(), specTS)
	if err != nil {
		t.Fatalf("encryptWith: %v", err)
	}
	if got != specToken {
		t.Fatalf("encrypt produced\n  %s\nwant\n  %s", got, specToken)
	}
}

func TestRoundTrip(t *testing.T) {
	k, _ := ParseKey(specKey)
	for _, msg := range []string{"", "x", "a refresh token value 1234567890", "exactly-16-bytes"} {
		tok, err := k.Encrypt([]byte(msg))
		if err != nil {
			t.Fatalf("Encrypt(%q): %v", msg, err)
		}
		got, err := k.Decrypt(tok)
		if err != nil {
			t.Fatalf("Decrypt(%q): %v", msg, err)
		}
		if !bytes.Equal(got, []byte(msg)) {
			t.Fatalf("roundtrip %q -> %q", msg, got)
		}
	}
}

func TestTamperRejected(t *testing.T) {
	k, _ := ParseKey(specKey)
	tok, _ := k.Encrypt([]byte("secret"))
	// Flip a byte in the base64 body.
	b := []byte(tok)
	b[10] ^= 0x01
	if _, err := k.Decrypt(string(b)); err == nil {
		t.Fatalf("tampered token accepted")
	}
	// A token from a different key must not verify (32 zero bytes, valid length).
	other, err := ParseKey("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
	if err != nil {
		t.Fatalf("ParseKey(other): %v", err)
	}
	if _, err := other.Decrypt(tok); err == nil {
		t.Fatalf("token verified under wrong key")
	}
}

func TestParseKeyInvalid(t *testing.T) {
	if _, err := ParseKey("not-base64!!!"); err == nil {
		t.Fatalf("accepted non-base64 key")
	}
	if _, err := ParseKey("c2hvcnQ="); err == nil { // "short" -> 5 bytes
		t.Fatalf("accepted wrong-length key")
	}
}
