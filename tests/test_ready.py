def test_ready_ok(client, fake_redis, monkeypatch):
    monkeypatch.setattr("app.ai.selftest.status", {"chat": "unchecked", "embeddings": "unchecked"})
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json() == {
        "database": "ok",
        "redis": "ok",
        "models": {"chat": "unchecked", "embeddings": "unchecked"},
    }


def test_ready_reports_failed_models_without_failing(client, fake_redis, monkeypatch):
    # Model state is informational: a dead model must not take the service
    # out of rotation, it only shows up here (and loudly in the logs).
    monkeypatch.setattr("app.ai.selftest.status", {"chat": "failed (NotFoundError)", "embeddings": "ok"})
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json()["models"] == {"chat": "failed (NotFoundError)", "embeddings": "ok"}


def test_ready_redis_down_is_503(client, monkeypatch):
    class _BrokenRedis:
        @classmethod
        def from_url(cls, url, **kwargs):
            return cls()

        def ping(self):
            raise ConnectionError("refused")

    monkeypatch.setattr("app.main.Redis", _BrokenRedis)
    resp = client.get("/ready")
    assert resp.status_code == 503
    assert "refused" in resp.json()["redis"]
