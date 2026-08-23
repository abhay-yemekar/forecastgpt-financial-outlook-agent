import pytest

from app.config import settings
from app.ratelimit import WINDOW_SECONDS, enforce_rate_limit


@pytest.fixture()
def low_limit(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 2)


def test_under_limit_passes(fake_redis, low_limit):
    enforce_rate_limit(1)
    enforce_rate_limit(1)  # no exception == allowed


def test_over_limit_raises_429_with_retry_after(fake_redis, low_limit):
    enforce_rate_limit(1)
    enforce_rate_limit(1)
    with pytest.raises(Exception) as exc_info:
        enforce_rate_limit(1)
    assert exc_info.value.status_code == 429
    retry_after = int(exc_info.value.headers["Retry-After"])
    assert 0 < retry_after <= WINDOW_SECONDS


def test_zero_disables_limiting(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 0)
    enforce_rate_limit(1)  # no Redis contact at all


def test_endpoint_returns_429(limited_client, monkeypatch, fake_redis, low_limit):
    from app.auth import generate_api_key
    from app.db.models import ApiKey, User
    from app.db.mysql import SessionLocal

    # Dedicated key so this test's counting doesn't interact with others.
    db = SessionLocal()
    try:
        user = User(email="ratelimit@example.com", password_hash="x")
        db.add(user)
        db.commit()
        raw, key_hash, prefix = generate_api_key()
        db.add(ApiKey(user_id=user.id, key_hash=key_hash, prefix=prefix))
        db.commit()
    finally:
        db.close()
    headers = {"X-API-Key": raw}

    # Two allowed calls, third is rejected by the endpoint itself.
    monkeypatch.setattr("app.main.enqueue_forecast_job", lambda *a, **k: None)
    for _ in range(2):
        r = limited_client.post("/forecasts", json={"query": "q", "company": "TCS"}, headers=headers)
        assert r.status_code in (202, 404)  # allowed through auth+ratelimit
    r = limited_client.post("/forecasts", json={"query": "q", "company": "TCS"}, headers=headers)
    assert r.status_code == 429
    assert "Retry-After" in r.headers
