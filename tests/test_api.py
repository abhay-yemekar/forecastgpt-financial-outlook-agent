from app.db.models import ForecastLog
from app.db.mysql import SessionLocal, storage_backend


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_list_companies(client):
    resp = client.get("/companies")
    assert resp.status_code == 200
    symbols = {c["symbol"] for c in resp.json()}
    assert {"TCS", "INFY", "HDFCBANK"}.issubset(symbols)


def test_unknown_company_rejected_before_enqueue(client, monkeypatch, auth_headers):
    def should_not_enqueue(*args, **kwargs):
        raise AssertionError("enqueued a job for an unknown company")

    monkeypatch.setattr("app.main.enqueue_forecast_job", should_not_enqueue)
    resp = client.post("/forecasts", json={"query": "outlook", "company": "NOTACOMPANY"}, headers=auth_headers)
    assert resp.status_code == 404
    assert "Unknown company" in resp.json()["detail"]


def test_create_forecast_returns_202_and_creates_queued_row(client, monkeypatch, auth_headers):
    captured = {}

    def fake_enqueue(row_id, symbol, slug, name, query, fin_urls, tr_urls, provider_key=None):
        captured.update(
            row_id=row_id, symbol=symbol, slug=slug, name=name, query=query,
            fin_urls=fin_urls, tr_urls=tr_urls, provider_key=provider_key,
        )

    monkeypatch.setattr("app.main.enqueue_forecast_job", fake_enqueue)

    resp = client.post(
        "/forecasts",
        json={"query": "Give me the outlook.", "company": "infy"},
        headers=auth_headers,
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued"
    assert body["poll"] == f"/forecasts/{body['job_id']}"

    # The enqueue got the resolved company, not the raw user input.
    assert captured["symbol"] == "INFY" and captured["slug"] == "INFY"
    assert captured["name"] == "Infosys"

    db = SessionLocal()
    try:
        row = db.get(ForecastLog, body["job_id"])
        assert row.status == "queued"
        assert row.company == "INFY"
        assert row.model_used == "ollama:llama3.2"
        assert row.storage_backend == storage_backend
    finally:
        db.close()

    # Immediately pollable: status only, no result yet.
    poll = client.get(f"/forecasts/{body['job_id']}", headers=auth_headers)
    assert poll.status_code == 200
    assert poll.json()["status"] == "queued"
    assert "result" not in poll.json()


def test_enqueue_failure_returns_503_and_marks_row(client, monkeypatch, auth_headers):
    def broken_enqueue(*args, **kwargs):
        raise ConnectionError("redis down")

    monkeypatch.setattr("app.main.enqueue_forecast_job", broken_enqueue)
    resp = client.post("/forecasts", json={"query": "q", "company": "TCS"}, headers=auth_headers)
    assert resp.status_code == 503

    db = SessionLocal()
    try:
        row = db.query(ForecastLog).order_by(ForecastLog.id.desc()).first()
        assert row.status == "failed"
        assert "enqueue failed" in row.error
    finally:
        db.close()


def test_get_unknown_job_404(client, auth_headers):
    resp = client.get("/forecasts/999999", headers=auth_headers)
    assert resp.status_code == 404
