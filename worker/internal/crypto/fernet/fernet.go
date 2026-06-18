// Package fernet implements the Fernet symmetric-token spec (AES-128-CBC +
// HMAC-SHA256, urlsafe-base64) so the Go worker reads/writes OAuth refresh tokens
// byte-compatibly with the Python worker's cryptography.fernet.Fernet (same
// TOKEN_ENCRYPTION_KEY). Ports the encrypt/decrypt used by
// app/services/oauth_tokens.py.
package fernet

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/base64"
	"encoding/binary"
	"errors"
	"time"
)

const version = 0x80

// ErrInvalidToken is returned when a token fails HMAC verification or is
// malformed (mirrors cryptography's InvalidToken).
var ErrInvalidToken = errors.New("fernet: invalid token")

// Key is a parsed Fernet key: the first 16 bytes sign, the last 16 encrypt.
type Key struct {
	signing    []byte
	encryption []byte
}

// ParseKey decodes a urlsafe-base64 Fernet key (32 raw bytes).
func ParseKey(urlsafeBase64 string) (*Key, error) {
	raw, err := base64.URLEncoding.DecodeString(urlsafeBase64)
	if err != nil || len(raw) != 32 {
		return nil, errors.New("fernet: key must be urlsafe-base64 of 32 bytes")
	}
	return &Key{signing: raw[:16], encryption: raw[16:32]}, nil
}

// Encrypt produces a Fernet token for plaintext. The IV is random and the
// timestamp is the current time, matching Fernet.encrypt.
func (k *Key) Encrypt(plaintext []byte) (string, error) {
	iv := make([]byte, aes.BlockSize)
	if _, err := rand.Read(iv); err != nil {
		return "", err
	}
	return k.encryptWith(plaintext, iv, time.Now().Unix())
}

// encryptWith is the deterministic core (exposed to tests via fixed iv/ts).
func (k *Key) encryptWith(plaintext, iv []byte, ts int64) (string, error) {
	block, err := aes.NewCipher(k.encryption)
	if err != nil {
		return "", err
	}
	ct := make([]byte, len(pkcs7Pad(plaintext, aes.BlockSize)))
	cipher.NewCBCEncrypter(block, iv).CryptBlocks(ct, pkcs7Pad(plaintext, aes.BlockSize))

	body := make([]byte, 0, 1+8+len(iv)+len(ct))
	body = append(body, version)
	var tsb [8]byte
	binary.BigEndian.PutUint64(tsb[:], uint64(ts))
	body = append(body, tsb[:]...)
	body = append(body, iv...)
	body = append(body, ct...)

	mac := hmac.New(sha256.New, k.signing)
	mac.Write(body)
	token := append(body, mac.Sum(nil)...)
	return base64.URLEncoding.EncodeToString(token), nil
}

// Decrypt verifies the HMAC and returns the plaintext. TTL is not enforced
// (matches the Python decrypt(token) call, which passes no ttl).
func (k *Key) Decrypt(token string) ([]byte, error) {
	data, err := base64.URLEncoding.DecodeString(token)
	if err != nil {
		return nil, ErrInvalidToken
	}
	// version(1) + timestamp(8) + iv(16) + >=1 block + hmac(32)
	if len(data) < 1+8+aes.BlockSize+aes.BlockSize+sha256.Size || data[0] != version {
		return nil, ErrInvalidToken
	}
	body := data[:len(data)-sha256.Size]
	sig := data[len(data)-sha256.Size:]

	mac := hmac.New(sha256.New, k.signing)
	mac.Write(body)
	if subtle.ConstantTimeCompare(mac.Sum(nil), sig) != 1 {
		return nil, ErrInvalidToken
	}

	ct := body[1+8+aes.BlockSize:]
	iv := body[1+8 : 1+8+aes.BlockSize]
	if len(ct) == 0 || len(ct)%aes.BlockSize != 0 {
		return nil, ErrInvalidToken
	}
	block, err := aes.NewCipher(k.encryption)
	if err != nil {
		return nil, err
	}
	pt := make([]byte, len(ct))
	cipher.NewCBCDecrypter(block, iv).CryptBlocks(pt, ct)
	return pkcs7Unpad(pt, aes.BlockSize)
}

func pkcs7Pad(b []byte, blockSize int) []byte {
	n := blockSize - len(b)%blockSize
	pad := make([]byte, n)
	for i := range pad {
		pad[i] = byte(n)
	}
	return append(b, pad...)
}

func pkcs7Unpad(b []byte, blockSize int) ([]byte, error) {
	if len(b) == 0 || len(b)%blockSize != 0 {
		return nil, ErrInvalidToken
	}
	n := int(b[len(b)-1])
	if n == 0 || n > blockSize || n > len(b) {
		return nil, ErrInvalidToken
	}
	for _, c := range b[len(b)-n:] {
		if int(c) != n {
			return nil, ErrInvalidToken
		}
	}
	return b[:len(b)-n], nil
}
