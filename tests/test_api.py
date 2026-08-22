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


def test_unknown_company_rejected_before_any_work(client, monkeypatch):
    def should_not_fetch(*args, **kwargs):
        raise AssertionError("fetched documents for an unknown company")

    monkeypatch.setattr("app.main.fetch_recent_docs", should_not_fetch)
    resp = client.post("/forecast", json={"query": "outlook", "company": "NOTACOMPANY"})
    assert resp.status_code == 404
    assert "Unknown company" in resp.json()["detail"]


def test_forecast_runs_and_logs_row(client, monkeypatch):
    canned_output = {
        "company": "Infosys",
        "period_analyzed": ["Q2 FY26"],
        "financial_trends": {"revenue": "up", "net_profit": "up", "operating_margin": "flat"},
        "management_themes": ["GenAI deals"],
        "risks": ["macro"],
        "opportunities": ["cost takeout"],
        "qualitative_forecast_next_quarter": "Stable growth expected.",
        "confidence": {"level": "medium", "reasons": ["two quarters of data"]},
    }

    seen = {}

    def fake_fetch(slug, max_quarters=2):
        seen["slug"] = slug
        return [f"{slug}_results.pdf"], [f"{slug}_transcript.pdf"]

    def fake_run(query, fin, tr, company_name, symbol):
        return {**canned_output, "_symbol": symbol}

    monkeypatch.setattr("app.main.fetch_recent_docs", fake_fetch)
    monkeypatch.setattr("app.main.agent.run", fake_run)

    resp = client.post("/forecast", json={"query": "Give me the outlook.", "company": "infy"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["company"] == "Infosys"
    assert body["_symbol"] == "INFY"
    assert seen["slug"] == "INFY"  # case-insensitive resolution, correct slug passed to the fetcher

    db = SessionLocal()
    try:
        row = db.query(ForecastLog).order_by(ForecastLog.id.desc()).first()
        assert row is not None
        assert row.company == "INFY"
        assert row.output_json == body
        assert row.storage_backend == storage_backend
        assert storage_backend == "sqlite"  # tests run on the overridden SQLite URL
    finally:
        db.close()
