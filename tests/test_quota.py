import pytest

from app.config import settings
from app.db.models import ForecastLog
from app.db.mysql import SessionLocal
from app.quota import enforce_user_quota, refund_user_quota


def _auth(sub: str) -> dict:
    import time

    import jwt

    token = jwt.encode(
        {"sub": sub, "email": f"{sub}@example.com", "exp": int(time.time()) + 600},
        "test-jwt-secret-for-principal-auth",
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def supabase_on(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "test-jwt-secret-for-principal-auth")


@pytest.fixture()
def tiny_quota(monkeypatch):
    monkeypatch.setattr(settings, "QUOTA_FREE_PER_DAY", 2)
    monkeypatch.setattr(settings, "QUOTA_GLOBAL_PER_DAY", 400)


def test_quota_enforced_for_users(quota_client, supabase_on, tiny_quota, monkeypatch, fake_redis):
    monkeypatch.setattr("app.main.enqueue_forecast_job", lambda *a, **k: None)
    headers = _auth("quota-user")

    assert quota_client.post("/forecasts", json={"query": "q", "company": "TCS"}, headers=headers).status_code == 202
    assert quota_client.post("/forecasts", json={"query": "q", "company": "TCS"}, headers=headers).status_code == 202

    third = quota_client.post("/forecasts", json={"query": "q", "company": "TCS"}, headers=headers)
    assert third.status_code == 429
    assert "BYOK" in third.json()["detail"] or "X-Provider-Key" in third.json()["detail"]
    assert "Retry-After" in third.headers


def test_byok_bypasses_user_quota(quota_client, supabase_on, tiny_quota, monkeypatch, fake_redis):
    monkeypatch.setattr("app.main.enqueue_forecast_job", lambda *a, **k: None)
    headers = _auth("byok-user")
    byok = {**headers, "X-Provider-Key": "sk-user-own-key"}

    for _ in range(4):  # beyond the free quota of 2
        resp = quota_client.post("/forecasts", json={"query": "q", "company": "TCS"}, headers=byok)
        assert resp.status_code == 202


def test_api_keys_are_never_quota_d(client, tiny_quota, monkeypatch, auth_headers):
    monkeypatch.setattr("app.main.enqueue_forecast_job", lambda *a, **k: None)
    for _ in range(5):  # beyond 2 — api-key principals are operator-level
        resp = client.post("/forecasts", json={"query": "q", "company": "TCS"}, headers=auth_headers)
        assert resp.status_code == 202


def test_global_cap_applies_across_users(quota_client, supabase_on, monkeypatch, fake_redis):
    monkeypatch.setattr(settings, "QUOTA_FREE_PER_DAY", 10)
    monkeypatch.setattr(settings, "QUOTA_GLOBAL_PER_DAY", 1)
    monkeypatch.setattr("app.main.enqueue_forecast_job", lambda *a, **k: None)

    first = quota_client.post("/forecasts", json={"query": "q", "company": "TCS"}, headers=_auth("g-user-1"))
    assert first.status_code == 202

    second = quota_client.post("/forecasts", json={"query": "q", "company": "TCS"}, headers=_auth("g-user-2"))
    assert second.status_code == 429
    assert "service-wide" in second.json()["detail"]


def test_quota_me_reflects_usage(quota_client, supabase_on, tiny_quota, monkeypatch, fake_redis):
    monkeypatch.setattr("app.main.enqueue_forecast_job", lambda *a, **k: None)
    headers = _auth("me-user")
    quota_client.post("/forecasts", json={"query": "q", "company": "TCS"}, headers=headers)

    body = quota_client.get("/quota/me", headers=headers).json()
    assert body["quota"] == "free_tier"
    assert body["used"] == 1
    assert body["limit"] == 2
    assert body["resets_at"].endswith("T00:00:00Z")


def test_quota_me_for_api_key_is_unlimited(client, auth_headers):
    body = client.get("/quota/me", headers=auth_headers).json()
    assert body == {"quota": "unlimited", "kind": "api_key"}


def test_failed_rejections_do_not_consume_quota(quota_client, supabase_on, tiny_quota, monkeypatch, fake_redis):
    monkeypatch.setattr("app.main.enqueue_forecast_job", lambda *a, **k: None)
    headers = _auth("rollback-user")
    # Exhaust, get rejected once, then check the counter wasn't inflated.
    for _ in range(2):
        quota_client.post("/forecasts", json={"query": "q", "company": "TCS"}, headers=headers)
    quota_client.post("/forecasts", json={"query": "q", "company": "TCS"}, headers=headers)  # 429
    body = quota_client.get("/quota/me", headers=headers).json()
    assert body["used"] == 2  # exactly the two accepted calls


def test_failed_job_refunds_quota(fake_redis, monkeypatch):
    """The exact bug Abhay hit: a failed forecast consumed a daily slot."""
    from app.db.models import ForecastLog
    from app.db.mysql import SessionLocal
    from app.jobs import run_forecast_job

    # Seed a row owned by a console user (no BYOK staged).
    db = SessionLocal()
    row = ForecastLog(
        company="WIPRO", owner_id="refund-user", query="q",
        status="queued", model_used="test:fake", storage_backend="sqlite",
    )
    db.add(row)
    db.commit()
    row_id = row.id
    db.close()

    def boom(*args, **kwargs):
        raise RuntimeError("host blocked")

    monkeypatch.setattr("app.jobs.fetch_given_urls", boom)
    status = run_forecast_job(row_id, "WIPRO", "WIPRO", "Wipro", "q", ["x.pdf"], None)
    assert status == "failed"

    # Refund already ran inside the failed job; one more slot must still be
    # available under limit 2 (i.e. the failure did not stack usage).
    enforce_user_quota("refund-user")  # no exception → slot was refunded
    usage_keys = [k for k in fake_redis.keys("quota:user:refund-user:*")]
    assert all(int(fake_redis.get(k) or 0) <= 2 for k in usage_keys)
    refund_user_quota("refund-user")  # tidy up for other assertions


def test_failed_byok_job_does_not_refund_managed_quota(fake_redis, monkeypatch):
    from app.jobs import _pop_provider_key, run_forecast_job

    db = SessionLocal()
    row = ForecastLog(
        company="WIPRO", owner_id="byok-refund-user", query="q",
        status="queued", model_used="test:fake", storage_backend="sqlite",
    )
    db.add(row)
    db.commit()
    row_id = row.id
    db.close()

    fake_redis.setex(f"byok:{row_id}", 3600, "sk-user-key")

    def boom(*args, **kwargs):
        raise RuntimeError("LLM down")

    monkeypatch.setattr("app.jobs.fetch_given_urls", boom)
    status = run_forecast_job(row_id, "WIPRO", "WIPRO", "Wipro", "q", ["x.pdf"], None)
    assert status == "failed"
    assert _pop_provider_key(row_id) is None  # consumed earlier by the job
