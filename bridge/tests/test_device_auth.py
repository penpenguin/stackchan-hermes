from __future__ import annotations

from stackchan_bridge.security.tokens import hash_device_token, verify_device_token


def test_device_token_is_stored_as_a_salted_derived_value() -> None:
    token = "simulator-device-token"  # pragma: allowlist secret

    encoded = hash_device_token(token, salt=b"0123456789abcdef")

    assert encoded.startswith("scrypt$")
    assert token not in encoded
    assert verify_device_token(token, encoded) is True
    assert verify_device_token("different-device-token", encoded) is False


def test_malformed_device_token_hash_is_rejected_without_crashing() -> None:
    assert verify_device_token("candidate-token", "not-a-supported-hash") is False
