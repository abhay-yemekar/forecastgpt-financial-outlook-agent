import fakeredis
import pytest


@pytest.fixture()
def fake_redis(monkeypatch):
    # FakeServer keeps the fake entirely in-process (no TCP attempted).
    fake = fakeredis.FakeRedis(server=fakeredis.FakeServer())

    class _FakeRedisClass:
        @classmethod
        def from_url(cls, url, **kwargs):
            return fake

    monkeypatch.setattr("app.main.Redis", _FakeRedisClass)
    return fake


def test_ready_ok(client, fake_redis):
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json() == {"database": "ok", "redis": "ok"}


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
