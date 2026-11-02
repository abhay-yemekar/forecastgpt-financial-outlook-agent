from app.config import settings


def test_config_auth_disabled_without_supabase(client, monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_URL", "")
    monkeypatch.setattr(settings, "SUPABASE_PUBLISHABLE_KEY", "sb_publishable_x")
    resp = client.get("/config")
    assert resp.status_code == 200
    assert resp.json() == {"auth": {"enabled": False, "supabase_url": None, "supabase_key": None}}


def test_config_serves_publishable_key(client, monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://abc.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_PUBLISHABLE_KEY", "sb_publishable_x")
    monkeypatch.setattr(settings, "SUPABASE_ANON_KEY", "legacy-anon")
    auth = client.get("/config").json()["auth"]
    assert auth == {"enabled": True, "supabase_url": "https://abc.supabase.co", "supabase_key": "sb_publishable_x"}


def test_config_falls_back_to_legacy_anon_key(client, monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://abc.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_PUBLISHABLE_KEY", "")
    monkeypatch.setattr(settings, "SUPABASE_ANON_KEY", "legacy-anon")
    assert client.get("/config").json()["auth"]["supabase_key"] == "legacy-anon"


def test_config_never_exposes_server_secrets(client, monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://abc.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_PUBLISHABLE_KEY", "sb_publishable_x")
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "server-only-secret")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "server-only-llm-key")
    body = client.get("/config").text
    assert "server-only-secret" not in body
    assert "server-only-llm-key" not in body
