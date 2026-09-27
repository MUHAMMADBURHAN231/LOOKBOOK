"""Password hashing and opaque token helpers."""

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# OWASP-recommended Argon2id parameters (m=19 MiB, t=2, p=1).
_hasher = PasswordHasher(time_cost=2, memory_cost=19 * 1024, parallelism=1)
# Verified against when the email is unknown, so response time doesn't reveal which emails exist.
_DUMMY_HASH = _hasher.hash("lookbook-timing-equalizer")

MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128
_COMMON = {
    "password", "password1", "password123", "1234567890", "qwertyuiop", "iloveyou12",
    "letmein123", "welcome123", "admin12345", "passw0rd12", "football12", "lookbook123",
}


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    try:
        return _hasher.verify(hashed or _DUMMY_HASH, password) and hashed is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed: str) -> bool:
    return _hasher.check_needs_rehash(hashed)


def password_problem(password: str, email: str = "") -> str | None:
    """Return a user-facing reason the password is too weak, or None."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Use at least {MIN_PASSWORD_LENGTH} characters."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"Use at most {MAX_PASSWORD_LENGTH} characters."
    lowered = password.lower()
    if lowered in _COMMON or len(set(lowered)) < 4:
        return "That password is too easy to guess."
    local = email.split("@")[0].lower()
    if len(local) >= 4 and local in lowered:
        return "Don't include your email address in your password."
    return None


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def token_hash(token: str) -> str:
    """Only hashes of session and reset tokens are stored, so a database leak can't be replayed."""
    return hashlib.sha256(token.encode()).hexdigest()


def constant_time_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def sign(value: str, secret: str) -> str:
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()
