import pytest

from app.db.models import ForecastLog
from app.db.mysql import SessionLocal
from app.jobs import run_forecast_job

CANNED_OUTPUT = {
    "company": "Infosys",
    "period_analyzed": ["Q2 FY26"],
    "financial_trends": {"revenue": "up", "net_profit": "up", "operating_margin": "flat"},
    "management_themes": [],
    "risks": [],
    "opportunities": [],
    "qualitative_forecast_next_quarter": "Stable growth.",
    "confidence": {"level": "medium", "reasons": ["test"]},
}


def _make_row():
    db = SessionLocal()
    row = ForecastLog(
        company="INFY",
        query="Give me the outlook.",
        status="queued",
        model_used="test:fake",
        storage_backend="sqlite",
    )
    db.add(row)
    db.commit()
    row_id = row.id
    db.close()
    return row_id


def test_job_runs_pipeline_and_completes(monkeypatch):
    monkeypatch.setattr(
        "app.jobs.fetch_recent_docs", lambda slug, max_quarters=2: (["q2.pdf"], ["t2.pdf"])
    )
    monkeypatch.setattr(
        "app.jobs.agent.run",
        lambda q, f, t, company_name, symbol: {**CANNED_OUTPUT, "_symbol": symbol},
    )

    row_id = _make_row()
    final_status = run_forecast_job(row_id, "INFY", "INFY", "Infosys", "Give me the outlook.", None, None)

    assert final_status == "completed"
    db = SessionLocal()
    try:
        row = db.get(ForecastLog, row_id)
        assert row.status == "completed"
        assert row.output_json["company"] == "Infosys"
        assert row.input_meta == {"financial_docs": ["q2.pdf"], "transcripts": ["t2.pdf"]}
        assert row.error is None
    finally:
        db.close()


def test_job_failure_records_error(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("LLM exploded")

    monkeypatch.setattr("app.jobs.fetch_recent_docs", lambda slug, max_quarters=2: (["q2.pdf"], []))
    monkeypatch.setattr("app.jobs.agent.run", boom)

    row_id = _make_row()
    final_status = run_forecast_job(row_id, "INFY", "INFY", "Infosys", "q", None, None)

    assert final_status == "failed"
    db = SessionLocal()
    try:
        row = db.get(ForecastLog, row_id)
        assert row.status == "failed"
        assert "LLM exploded" in row.error
        assert row.output_json is None
    finally:
        db.close()


def test_unknown_row_raises():
    with pytest.raises(ValueError, match="not found"):
        run_forecast_job(999999, "TCS", "TCS", "Tata Consultancy Services", "q", None, None)
