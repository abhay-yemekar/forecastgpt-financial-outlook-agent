import pytest

from app.config import settings


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
