"""Credential/session primitives.

PINs: argon2id (argon2-cffi), per-password random salt.
Session tokens: 32-byte URL-safe random; only the sha256 of the token is stored.
Two token kinds: short-lived access (15 min) and rotating refresh (12 h).
"""

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2 import exceptions as argon2_exceptions

_hasher = PasswordHasher()  # argon2id defaults


def hash_pin(pin: str) -> str:
    return _hasher.hash(pin)


def verify_pin(pin: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        return _hasher.verify(stored, pin)
    except argon2_exceptions.VerificationError:
        return False
    except argon2_exceptions.InvalidHash:
        return False


def needs_rehash(stored: str) -> bool:
    try:
        return _hasher.check_needs_rehash(stored)
    except argon2_exceptions.InvalidHash:
        return True


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
