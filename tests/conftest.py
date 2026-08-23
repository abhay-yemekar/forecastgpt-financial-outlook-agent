"""Shared test setup.

Env vars are redirected BEFORE any app import so the suite never touches
MySQL, the real PDF cache, or the network.
"""

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="forecastgpt_tests_"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["DATA_DIR"] = str(_TMP / "data")

import fakeredis  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import hash_password  # noqa: E402
from app.db.models import ApiKey, User  # noqa: E402
from app.db.mysql import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def test_api_key() -> dict:
    """One user + one valid API key for the whole session; returns the raw key."""
    from app.auth import generate_api_key

    db = SessionLocal()
    try:
        user = User(email="tester@example.com", password_hash=hash_password("correct horse"))
        db.add(user)
        db.commit()
        raw, key_hash, prefix = generate_api_key()
        db.add(ApiKey(user_id=user.id, key_hash=key_hash, prefix=prefix))
        db.commit()
        return {"raw": raw, "prefix": prefix, "email": user.email}
    finally:
        db.close()


@pytest.fixture()
def auth_headers(test_api_key) -> dict:
    return {"X-API-Key": test_api_key["raw"]}


class _FakeRedisClass:
    """Redis stand-in whose from_url() returns one shared in-process fake."""

    fake = None

    @classmethod
    def from_url(cls, url, **kwargs):
        if cls.fake is None:
            cls.fake = fakeredis.FakeRedis(server=fakeredis.FakeServer())
        return cls.fake


@pytest.fixture()
def fake_redis(monkeypatch):
    """Point every Redis.from_url in the app at an in-process fake."""
    _FakeRedisClass.fake = fakeredis.FakeRedis(server=fakeredis.FakeServer())
    monkeypatch.setattr("app.main.Redis", _FakeRedisClass)
    monkeypatch.setattr("app.ratelimit.Redis", _FakeRedisClass)
    monkeypatch.setattr("app.jobs.Redis", _FakeRedisClass)
    return _FakeRedisClass.fake


@pytest.fixture()
def client(monkeypatch):
    # Rate limiting is exercised in dedicated tests; elsewhere it's a no-op
    # so the suite needs no real Redis.
    monkeypatch.setattr("app.main.enforce_rate_limit", lambda api_key_id, bucket="post": None)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def limited_client():
    """Client with rate limiting active (pair with the fake_redis fixture)."""
    with TestClient(app) as c:
        yield c
