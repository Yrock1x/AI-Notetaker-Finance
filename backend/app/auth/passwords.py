"""Local password hashing for email/password accounts (Argon2id).

OAuth-only users have ``Profile.password_hash = NULL`` and never touch this
module. Argon2id is used (not bcrypt) to avoid bcrypt's silent 72-byte
truncation; the hasher's defaults are sensible for an interactive login.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

# Reasonable bounds: enough entropy to matter, capped so a multi-megabyte
# "password" can't be used to burn CPU in the hasher (a cheap DoS).
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Return an Argon2id hash (includes the salt + parameters) for ``password``."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """True iff ``password`` matches ``password_hash``. Never raises."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        # Wrong password (VerificationError) or a malformed/legacy hash
        # (InvalidHashError) — both are simply "no match".
        return False
