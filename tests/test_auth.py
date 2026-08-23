from app.auth import generate_api_key, hash_key, hash_password, verify_password


def test_password_hash_roundtrip():
    h = hash_password("correct horse")
    assert h != "correct horse"
    assert verify_password(h, "correct horse")
    assert not verify_password(h, "wrong")


def test_api_key_shape_and_hashing():
    raw, key_hash, prefix = generate_api_key()
    assert raw.startswith("fgpt_")
    assert len(raw) > 30
    assert prefix == raw[:12]
    # Only the sha256 hex digest is stored.
    assert key_hash == hash_key(raw) and len(key_hash) == 64


def test_forecast_requires_api_key(client, monkeypatch):
    monkeypatch.setattr("app.main.enqueue_forecast_job", lambda *a, **k: None)
    resp = client.post("/forecasts", json={"query": "q", "company": "TCS"})
    assert resp.status_code == 401
    assert "X-API-Key" in resp.json()["detail"]


def test_invalid_key_rejected(client, auth_headers):
    resp = client.post(
        "/forecasts",
        json={"query": "q", "company": "TCS"},
        headers={"X-API-Key": "fgpt_notarealkey"},
    )
    assert resp.status_code == 401


def test_get_forecast_requires_key(client, auth_headers):
    no_key = client.get("/forecasts/1")
    assert no_key.status_code == 401
    with_key = client.get("/forecasts/1", headers=auth_headers)
    assert with_key.status_code in (200, 404)  # auth passed; 1 may or may not exist


def test_open_endpoints_stay_open(client):
    assert client.get("/health").status_code == 200
    assert client.get("/companies").status_code == 200


def test_revoked_key_rejected(client, monkeypatch):
    from app import cli
    from app.auth import generate_api_key, hash_password
    from app.db.models import ApiKey, User
    from app.db.mysql import SessionLocal

    # Dedicated user+key so the shared session key stays valid.
    db = SessionLocal()
    try:
        user = User(email="revoke-me@example.com", password_hash=hash_password("pw123456"))
        db.add(user)
        db.commit()
        raw, key_hash, prefix = generate_api_key()
        db.add(ApiKey(user_id=user.id, key_hash=key_hash, prefix=prefix))
        db.commit()
    finally:
        db.close()

    cli.revoke_key(prefix)
    monkeypatch.setattr("app.main.enqueue_forecast_job", lambda *a, **k: None)
    resp = client.post(
        "/forecasts",
        json={"query": "q", "company": "TCS"},
        headers={"X-API-Key": raw},
    )
    assert resp.status_code == 401
