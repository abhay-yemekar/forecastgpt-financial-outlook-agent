"""JWKS-mode (asymmetric) verification tests for decode_supabase_jwt.

Legacy HS256-mode tests live in test_principal_auth.py / test_auth.py.
"""

import base64
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import settings

SECRET = "test-jwt-secret-for-principal-auth"
SUPABASE_URL = "https://testproject.supabase.co"
ISSUER = f"{SUPABASE_URL}/auth/v1"

# One RSA keypair for the whole module (keygen is slow).
_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_KID = "test-key-1"


def _b64url_int(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _sign(payload: dict) -> str:
    return jwt.encode(payload, _PRIVATE_KEY, algorithm="RS256", headers={"kid": _KID})


def make_token(
    sub: str = "user-abc",
    email: str = "u@example.com",
    exp_offset: int = 600,
    iss: str = ISSUER,
    aud: str = "authenticated",
) -> str:
    return _sign(
        {
            "sub": sub,
            "email": email,
            "aud": aud,
            "iss": iss,
            "exp": int(time.time()) + exp_offset,
        }
    )


@pytest.fixture()
def jwks_mode(monkeypatch):
    """SUPABASE_URL set; the JWKS client is replaced with one backed by our
    test keypair — no network."""
    monkeypatch.setattr(settings, "SUPABASE_URL", SUPABASE_URL)
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "")

    class _FakeSigningKey:
        key = _PRIVATE_KEY.public_key()

    class _FakeClient:
        def get_signing_key_from_jwt(self, token):
            header = jwt.get_unverified_header(token)
            if header.get("kid") != _KID:
                raise jwt.PyJWKClientError("no matching key")
            return _FakeSigningKey()

    monkeypatch.setattr("app.auth._jwk_client_instance", _FakeClient())
    return _FakeClient()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_valid_rs256_token_accepted(client, jwks_mode, fake_redis):
    resp = client.get("/quota/me", headers=_auth(make_token()))
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "user" and body["email"] == "u@example.com"


def test_issuer_without_trailing_slash_also_accepted(client, jwks_mode, fake_redis):
    token = make_token(iss=ISSUER + "/")
    assert client.get("/quota/me", headers=_auth(token)).status_code == 200


def test_expired_token_rejected(client, jwks_mode):
    resp = client.get("/quota/me", headers=_auth(make_token(exp_offset=-10)))
    assert resp.status_code == 401
    assert "expired" in resp.json()["detail"].lower()


def test_wrong_issuer_rejected(client, jwks_mode):
    resp = client.get("/quota/me", headers=_auth(make_token(iss="https://evil.example.com/auth/v1")))
    assert resp.status_code == 401


def test_wrong_audience_rejected(client, jwks_mode):
    resp = client.get("/quota/me", headers=_auth(make_token(aud="someone-else")))
    assert resp.status_code == 401


def test_unknown_kid_rejected(client, jwks_mode):
    token = jwt.encode(
        {"sub": "u", "aud": "authenticated", "iss": ISSUER, "exp": int(time.time()) + 600},
        _PRIVATE_KEY,
        algorithm="RS256",
        headers={"kid": "rotated-away-key"},
    )
    resp = client.get("/quota/me", headers=_auth(token))
    assert resp.status_code == 401
    assert "Invalid session token" in resp.json()["detail"]


def test_hs256_token_rejected_in_jwks_mode(client, jwks_mode):
    # A legacy-style HMAC token must not pass under asymmetric verification.
    token = jwt.encode(
        {"sub": "u", "aud": "authenticated", "iss": ISSUER, "exp": int(time.time()) + 600},
        "some-symmetric-secret",
        algorithm="HS256",
    )
    resp = client.get("/quota/me", headers=_auth(token))
    assert resp.status_code == 401


def test_tampered_token_rejected(client, jwks_mode):
    token = make_token()[:-4] + "cafe"
    resp = client.get("/quota/me", headers=_auth(token))
    assert resp.status_code == 401


def test_jwks_mode_takes_precedence_over_legacy_secret(client, jwks_mode):
    # Both configured: URL (JWKS) must win. An HS256 token that WOULD pass
    # legacy verification is correctly refused in JWKS mode.
    monkeypatch_token = jwt.encode(
        {"sub": "legacy-user", "exp": int(time.time()) + 600},
        "legacy-secret-should-not-be-used",
        algorithm="HS256",
    )
    old = settings.SUPABASE_JWT_SECRET
    settings.SUPABASE_JWT_SECRET = "legacy-secret-should-not-be-used"
    try:
        resp = client.get("/quota/me", headers=_auth(monkeypatch_token))
        assert resp.status_code == 401
    finally:
        settings.SUPABASE_JWT_SECRET = old


def test_legacy_hs256_still_works_without_url(client, monkeypatch, fake_redis):
    monkeypatch.setattr(settings, "SUPABASE_URL", "")
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", SECRET)
    token = jwt.encode(
        {"sub": "legacy-user", "exp": int(time.time()) + 600},
        SECRET,
        algorithm="HS256",
    )
    resp = client.get("/quota/me", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["kind"] == "user"


def test_unconfigured_returns_503(client, monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_URL", "")
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "")
    resp = client.get("/quota/me", headers=_auth(make_token()))
    assert resp.status_code == 503
