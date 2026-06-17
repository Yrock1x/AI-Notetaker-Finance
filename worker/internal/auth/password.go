package auth

import "github.com/alexedwards/argon2id"

// Bounds match app/auth/passwords.py.
const (
	MinPasswordLength = 8
	MaxPasswordLength = 128
)

// argonParams match argon2-cffi's PasswordHasher() defaults (the Python worker):
// time_cost=3, memory_cost=65536 KiB, parallelism=4, salt=16, hash=32. New hashes
// are therefore consistent with Python's, and because argon2id encodes its params
// in the PHC string, verification works on hashes produced by either worker.
var argonParams = &argon2id.Params{
	Memory:      64 * 1024,
	Iterations:  3,
	Parallelism: 4,
	SaltLength:  16,
	KeyLength:   32,
}

// HashPassword returns an argon2id PHC string (ports hash_password).
func HashPassword(password string) (string, error) {
	return argon2id.CreateHash(password, argonParams)
}

// VerifyPassword checks a password against a stored argon2id hash, including
// hashes written by the Python worker (ports verify_password).
func VerifyPassword(password, hash string) bool {
	ok, err := argon2id.ComparePasswordAndHash(password, hash)
	return err == nil && ok
}
