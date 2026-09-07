"""Salted device-token derivation and constant-time verification."""

from __future__ import annotations

from hashlib import scrypt
from hmac import compare_digest
from secrets import token_bytes

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SALT_BYTES = 16
_DERIVED_BYTES = 32
_MAX_TOKEN_BYTES = 512


def hash_device_token(token: str, *, salt: bytes | None = None) -> str:
    """Return a portable salted scrypt representation, never the plaintext token."""

    token_data = _token_bytes(token)
    selected_salt = token_bytes(_SALT_BYTES) if salt is None else salt
    if len(selected_salt) < _SALT_BYTES:
        raise ValueError(f"device token salt must be at least {_SALT_BYTES} bytes")
    derived = scrypt(
        token_data,
        salt=selected_salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_DERIVED_BYTES,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${selected_salt.hex()}${derived.hex()}"


def verify_device_token(candidate: str, encoded: str) -> bool:
    """Verify a candidate against a trusted local hash without raising on malformed data."""

    try:
        algorithm, n_text, r_text, p_text, salt_hex, expected_hex = encoded.split("$")
        if algorithm != "scrypt":
            return False
        parameters = (int(n_text), int(r_text), int(p_text))
        if parameters != (_SCRYPT_N, _SCRYPT_R, _SCRYPT_P):
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(expected_hex)
        if len(salt) < _SALT_BYTES or len(expected) != _DERIVED_BYTES:
            return False
        actual = scrypt(
            _token_bytes(candidate),
            salt=salt,
            n=_SCRYPT_N,
            r=_SCRYPT_R,
            p=_SCRYPT_P,
            dklen=_DERIVED_BYTES,
        )
    except (TypeError, ValueError):
        return False
    return compare_digest(actual, expected)


def _token_bytes(token: str) -> bytes:
    value = token.encode("utf-8")
    if not value or len(value) > _MAX_TOKEN_BYTES:
        raise ValueError("device token must contain 1 to 512 UTF-8 bytes")
    return value
