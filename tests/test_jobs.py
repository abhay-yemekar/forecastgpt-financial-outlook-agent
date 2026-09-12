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


def test_job_runs_pipeline_and_completes(monkeypatch, fake_redis):
    monkeypatch.setattr(
        "app.jobs.fetch_recent_docs", lambda slug, max_quarters=2: (["q2.pdf"], ["t2.pdf"])
    )
    seen = {}

    def fake_run(q, f, t, company_name, symbol, llm_api_key=None):
        seen["llm_api_key"] = llm_api_key
        return {**CANNED_OUTPUT, "_symbol": symbol}

    monkeypatch.setattr("app.jobs.agent.run", fake_run)

    row_id = _make_row()
    final_status = run_forecast_job(row_id, "INFY", "INFY", "Infosys", "Give me the outlook.", None, None)

    assert final_status == "completed"
    assert seen["llm_api_key"] is None  # no BYOK key staged for this job
    db = SessionLocal()
    try:
        row = db.get(ForecastLog, row_id)
        assert row.status == "completed"
        assert row.output_json["company"] == "Infosys"
        assert row.input_meta == {"financial_docs": ["q2.pdf"], "transcripts": ["t2.pdf"]}
        assert row.error is None
    finally:
        db.close()


def test_byok_key_staged_in_redis_is_used_once_and_deleted(fake_redis, monkeypatch):
    from app.jobs import enqueue_forecast_job, run_forecast_job

    monkeypatch.setattr("app.jobs.fetch_given_urls", lambda urls: list(urls))

    row_id = _make_row()
    enqueue_forecast_job(
        row_id, "INFY", "INFY", "Infosys", "q", ["q.pdf"], None,
        provider_key="sk-byok-secret-123",
    )
    # Staged under a short-lived side-channel key...
    assert fake_redis.get(f"byok:{row_id}") == b"sk-byok-secret-123"
    # ...and NOT part of the queue payload (RQ logs job arguments).
    queued = fake_redis.lrange("rq:queue:forecasts", 0, -1)
    assert all(b"sk-byok-secret-123" not in item for item in queued)

    seen = {}

    def fake_run(q, f, t, company_name, symbol, llm_api_key=None):
        seen["llm_api_key"] = llm_api_key
        return CANNED_OUTPUT

    monkeypatch.setattr("app.jobs.agent.run", fake_run)
    status = run_forecast_job(row_id, "INFY", "INFY", "Infosys", "q", ["q.pdf"], None)

    assert status == "completed"
    assert seen["llm_api_key"] == "sk-byok-secret-123"
    # One-time read: gone after the job.
    assert fake_redis.get(f"byok:{row_id}") is None


def test_job_failure_records_error(monkeypatch, fake_redis):
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


def test_unknown_row_raises(fake_redis):
    with pytest.raises(ValueError, match="not found"):
        run_forecast_job(999999, "TCS", "TCS", "Tata Consultancy Services", "q", None, None)
