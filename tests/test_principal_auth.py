import time

import jwt
import pytest

from app.config import settings

SECRET = "test-jwt-secret-for-principal-auth"


def make_token(sub: str = "user-abc", email: str = "u@example.com", exp_offset: int = 600) -> str:
    return jwt.encode(
        {"sub": sub, "email": email, "exp": int(time.time()) + exp_offset},
        SECRET,
        algorithm="HS256",
    )


@pytest.fixture()
def supabase_on(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", SECRET)


def auth(sub: str = "user-abc") -> dict:
    return {"Authorization": f"Bearer {make_token(sub=sub)}"}


def test_api_key_still_works(client, monkeypatch, auth_headers):
    monkeypatch.setattr("app.main.enqueue_forecast_job", lambda *a, **k: None)
    resp = client.post("/forecasts", json={"query": "q", "company": "TCS"}, headers=auth_headers)
    assert resp.status_code == 202


def test_no_credentials_rejected(client):
    resp = client.post("/forecasts", json={"query": "q", "company": "TCS"})
    assert resp.status_code == 401
    assert "Sign in" in resp.json()["detail"] or "X-API-Key" in resp.json()["detail"]


def test_bearer_jwt_accepted(client, supabase_on, monkeypatch, fake_redis):
    monkeypatch.setattr("app.main.enqueue_forecast_job", lambda *a, **k: None)
    resp = client.post("/forecasts", json={"query": "q", "company": "TCS"}, headers=auth())
    assert resp.status_code == 202
    quota = client.get("/quota/me", headers=auth())
    assert quota.status_code == 200
    body = quota.json()
    assert body["kind"] == "user" and body["email"] == "u@example.com"
    # Quota counting itself is covered in test_quota.py; here the client
    # fixture stubs it, so usage stays 0.
    assert body["used"] == 0


def test_jwt_without_config_returns_503(client, monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "")
    resp = client.get("/quota/me", headers=auth())
    assert resp.status_code == 503
    assert "SUPABASE_JWT_SECRET" in resp.json()["detail"]


def test_expired_jwt_rejected(client, supabase_on):
    stale = {"Authorization": f"Bearer {make_token(exp_offset=-10)}"}
    resp = client.get("/quota/me", headers=stale)
    assert resp.status_code == 401
    assert "expired" in resp.json()["detail"].lower()


def test_tampered_jwt_rejected(client, supabase_on):
    token = make_token()[:-3] + "xyz"
    resp = client.get("/quota/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_users_see_only_their_jobs(client, supabase_on, monkeypatch, auth_headers):
    monkeypatch.setattr("app.main.enqueue_forecast_job", lambda *a, **k: None)

    mine = client.post("/forecasts", json={"query": "q", "company": "TCS"}, headers=auth(sub="user-A")).json()
    theirs = client.post("/forecasts", json={"query": "q", "company": "TCS"}, headers=auth(sub="user-B")).json()

    # A can read their own job but not B's (404, not 403 — no id leaking).
    assert client.get(f"/forecasts/{mine['job_id']}", headers=auth(sub="user-A")).status_code == 200
    assert client.get(f"/forecasts/{theirs['job_id']}", headers=auth(sub="user-A")).status_code == 404

    # History is scoped per user.
    ids_a = [r["job_id"] for r in client.get("/forecasts", headers=auth(sub="user-A")).json()]
    assert mine["job_id"] in ids_a and theirs["job_id"] not in ids_a

    # Operator-level API keys still see everything.
    all_ids = [r["job_id"] for r in client.get("/forecasts", headers=auth_headers).json()]
    assert mine["job_id"] in all_ids and theirs["job_id"] in all_ids
