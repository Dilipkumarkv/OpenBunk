"""Credential/session primitives. Demo-grade for Phase 04; hardened in Phase 05.

PINs: pbkdf2_hmac(sha256) with per-employee random salt, stored as "salt$hash" hex.
Session tokens: 32-byte URL-safe random; only the sha256 of the token is stored.
"""

import hashlib
import hmac
import secrets


def hash_pin(pin: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 120_000)
    return f"{salt.hex()}${digest.hex()}"


def verify_pin(pin: str, stored: str) -> bool:
    try:
        salt_hex, hash_hex = stored.split("$", 1)
        expected = hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt_hex), 120_000)
        return hmac.compare_digest(expected, bytes.fromhex(hash_hex))
    except (ValueError, TypeError):
        return False


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
