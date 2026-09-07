"""Tests for password hashing, JWT issuance, and TOTP."""

import time

import pyotp
import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    new_totp_secret,
    totp_provisioning_uri,
    verify_password,
    verify_totp,
)


class TestPasswords:
    def test_roundtrip(self):
        hashed = hash_password("Sankhya@2026")
        assert verify_password("Sankhya@2026", hashed)

    def test_wrong_password_rejected(self):
        assert not verify_password("wrong", hash_password("Sankhya@2026"))

    def test_missing_hash_is_rejected_not_crashed(self):
        """Officers who only use OTP or TOTP have no password hash."""
        assert not verify_password("anything", None)

    def test_hash_is_salted(self):
        assert hash_password("same") != hash_password("same")

    def test_plaintext_never_appears_in_the_hash(self):
        assert "Sankhya@2026" not in hash_password("Sankhya@2026")


class TestAccessTokens:
    def test_roundtrip_carries_identity_role_and_method(self):
        token = create_access_token(42, "supervisor", "totp")
        payload = decode_access_token(token)
        assert payload["sub"] == "42"
        assert payload["role"] == "supervisor"
        assert payload["amr"] == "totp"

    def test_tampered_token_is_rejected(self):
        token = create_access_token(1, "learner", "password")
        assert decode_access_token(token[:-2] + "xy") is None

    def test_garbage_is_rejected_without_raising(self):
        assert decode_access_token("not-a-token") is None

    def test_all_four_methods_produce_equivalent_tokens(self):
        """Authorisation must not care how someone signed in."""
        roles = {
            decode_access_token(create_access_token(7, "learner", m))["role"]
            for m in ("password", "email_otp", "totp", "parichay")
        }
        assert roles == {"learner"}


class TestTotp:
    def test_valid_code_accepted(self):
        secret = new_totp_secret()
        assert verify_totp(secret, pyotp.TOTP(secret).now())

    def test_wrong_code_rejected(self):
        secret = new_totp_secret()
        assert not verify_totp(secret, "000000")

    def test_code_from_another_secret_rejected(self):
        assert not verify_totp(new_totp_secret(), pyotp.TOTP(new_totp_secret()).now())

    def test_no_secret_is_rejected_not_crashed(self):
        assert not verify_totp(None, "123456")

    def test_provisioning_uri_is_scannable(self):
        secret = new_totp_secret()
        uri = totp_provisioning_uri(secret, "venkatesan@sankhya.gov.in")
        assert uri.startswith("otpauth://totp/")
        assert "SANKHYA" in uri
        assert secret in uri

    def test_works_with_no_network(self):
        """The reason TOTP is the method to demo on stage: it is pure computation."""
        secret = new_totp_secret()
        assert verify_totp(secret, pyotp.TOTP(secret).now())
