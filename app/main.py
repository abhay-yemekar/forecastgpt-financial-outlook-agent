from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from redis import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.companies import resolve_company, seed_companies
from app.config import settings
from app.db.models import Base, Company, ForecastLog
from app.db.mysql import engine, get_db, storage_backend
from app.jobs import enqueue_forecast_job
from app.utils.logger import get_logger

log = get_logger("api")

Base.metadata.create_all(bind=engine)
seed_companies()

app = FastAPI(title="ForecastGPT - Financial Outlook Agent")


class ForecastRequest(BaseModel):
    query: str
    company: str  # NSE symbol or screener slug, e.g. "TCS" or "INFY"
    financial_doc_urls: list[str] | None = None
    transcript_urls: list[str] | None = None


@app.get("/companies")
def list_companies(db: Session = Depends(get_db)):
    rows = db.query(Company).order_by(Company.symbol).all()
    return [
        {"symbol": c.symbol, "display_name": c.display_name, "exchange": c.exchange}
        for c in rows
    ]


@app.post("/forecasts", status_code=202)
def create_forecast(req: ForecastRequest, db: Session = Depends(get_db)):
    # Validate the company before doing any work, so an unrecognized ticker
    # never silently produces an empty forecast.
    company = resolve_company(db, req.company)
    if company is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Unknown company '{req.company}'. "
                "Call GET /companies for the list of supported companies."
            ),
        )

    row = ForecastLog(
        company=company.symbol,
        query=req.query,
        status="queued",
        model_used=f"{settings.LLM_PROVIDER}:{settings.LLM_MODEL}",
        storage_backend=storage_backend,
    )
    db.add(row)
    db.commit()

    try:
        enqueue_forecast_job(
            row.id,
            company.symbol,
            company.screener_slug,
            company.display_name,
            req.query,
            req.financial_doc_urls,
            req.transcript_urls,
        )
    except Exception as e:
        row.status = "failed"
        row.error = f"enqueue failed: {e}"[:2000]
        db.commit()
        raise HTTPException(status_code=503, detail="Job queue unavailable; is Redis running?") from e

    return {"job_id": row.id, "status": "queued", "poll": f"/forecasts/{row.id}"}


@app.get("/forecasts/{job_id}")
def get_forecast(job_id: int, db: Session = Depends(get_db)):
    row = db.get(ForecastLog, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No forecast job with id {job_id}.")

    out = {
        "job_id": row.id,
        "company": row.company,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
    if row.status == "completed":
        out["result"] = row.output_json
    if row.status == "failed":
        out["error"] = row.error
    return out


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """Connectivity check for the app's two dependencies: DB and Redis."""
    checks = {}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"unavailable: {e}"
    try:
        Redis.from_url(settings.REDIS_URL).ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"unavailable: {e}"
    ok = all(v == "ok" for v in checks.values())
    return JSONResponse(checks, status_code=200 if ok else 503)
