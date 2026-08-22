"""Async forecast jobs: RQ queue helpers + the worker-side job function.

The API process only creates the log row and enqueues; the worker executes
the pipeline (fetch -> extract -> RAG -> LLM) and writes progress/result
back to the same forecast_logs row.
"""

from redis import Redis
from rq import Queue

from app.agent import ForecastAgent
from app.config import settings
from app.db.models import ForecastLog
from app.db.mysql import SessionLocal
from app.utils.fetcher import fetch_given_urls, fetch_recent_docs
from app.utils.logger import get_logger

log = get_logger("jobs")

# Forecasts regularly take several minutes on CPU-only Ollama; RQ's default
# job timeout (180s) would kill them.
JOB_TIMEOUT_SECONDS = 900

# One agent per worker process, reused across jobs.
agent = ForecastAgent()


def get_queue() -> Queue:
    return Queue("forecasts", connection=Redis.from_url(settings.REDIS_URL))


def enqueue_forecast_job(
    row_id: int,
    company_symbol: str,
    company_slug: str,
    company_name: str,
    query: str,
    financial_doc_urls: list[str] | None,
    transcript_urls: list[str] | None,
) -> None:
    get_queue().enqueue(
        "app.jobs.run_forecast_job",  # string path so the worker imports it itself
        row_id,
        company_symbol,
        company_slug,
        company_name,
        query,
        financial_doc_urls,
        transcript_urls,
        job_id=str(row_id),
        job_timeout=JOB_TIMEOUT_SECONDS,
    )


def run_forecast_job(
    row_id: int,
    company_symbol: str,
    company_slug: str,
    company_name: str,
    query: str,
    financial_doc_urls: list[str] | None,
    transcript_urls: list[str] | None,
) -> str:
    """Worker-side entry: run the full pipeline for one forecast_logs row."""
    db = SessionLocal()
    try:
        row = db.get(ForecastLog, row_id)
        if row is None:
            raise ValueError(f"forecast_logs row {row_id} not found")
        row.status = "running"
        db.commit()

        try:
            if financial_doc_urls:
                fin_paths = fetch_given_urls(financial_doc_urls)
            else:
                fin_paths, _ = fetch_recent_docs(company_slug, max_quarters=2)

            if transcript_urls:
                tr_paths = fetch_given_urls(transcript_urls)
            else:
                _, tr_paths = fetch_recent_docs(company_slug, max_quarters=2)

            out = agent.run(
                query,
                fin_paths,
                tr_paths,
                company_name=company_name,
                symbol=company_symbol,
            )

            row.input_meta = {"financial_docs": fin_paths, "transcripts": tr_paths}
            row.output_json = out
            row.status = "completed"
        except Exception as e:
            log.exception(f"Forecast job {row_id} failed: {e}")
            row.status = "failed"
            row.error = str(e)[:2000]

        db.commit()
        return row.status
    finally:
        db.close()
