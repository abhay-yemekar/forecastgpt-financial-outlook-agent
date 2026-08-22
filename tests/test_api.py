from app.db.models import ForecastLog
from app.db.mysql import SessionLocal, storage_backend


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_forecast_logs_row_with_storage_backend(client, monkeypatch):
    canned_output = {
        "company": "TCS",
        "period_analyzed": ["Q2 FY25"],
        "financial_trends": {"revenue": "up", "net_profit": "up", "operating_margin": "flat"},
        "management_themes": ["GenAI deals"],
        "risks": ["macro"],
        "opportunities": ["cost takeout"],
        "qualitative_forecast_next_quarter": "Stable growth expected.",
        "confidence": {"level": "medium", "reasons": ["two quarters of data"]},
    }

    monkeypatch.setattr("app.main.fetch_recent_docs", lambda max_quarters=2: (["q2.pdf"], ["t2.pdf"]))
    monkeypatch.setattr("app.main.agent.run", lambda *a, **k: canned_output)

    resp = client.post("/forecast", json={"query": "Give me the outlook."})
    assert resp.status_code == 200
    assert resp.json() == canned_output

    db = SessionLocal()
    try:
        row = db.query(ForecastLog).order_by(ForecastLog.id.desc()).first()
        assert row is not None
        assert row.output_json == canned_output
        assert row.storage_backend == storage_backend
        assert storage_backend == "sqlite"  # tests run on the overridden SQLite URL
    finally:
        db.close()
