from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from redis import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.companies import resolve_company, seed_companies
from app.config import settings
from app.db.models import ApiKey, Base, Company, ForecastLog
from app.db.mysql import engine, get_db, storage_backend
from app.jobs import enqueue_forecast_job
from app.ratelimit import enforce_rate_limit
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


@app.get("/stats")
def stats(db: Session = Depends(get_db)):
    """Public, non-sensitive counts for the web app's landing hero."""
    return {
        "companies": db.query(Company).count(),
        "forecasts_total": db.query(ForecastLog).count(),
        "forecasts_completed": db.query(ForecastLog).filter(ForecastLog.status == "completed").count(),
    }


@app.post("/forecasts", status_code=202)
def create_forecast(
    req: ForecastRequest,
    api_key: ApiKey = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    enforce_rate_limit(api_key.id)

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


@app.get("/forecasts")
def list_forecasts(
    company: str | None = None,
    limit: int = 20,
    api_key: ApiKey = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    """Recent forecast jobs, newest first — powers the web app's history panel."""
    enforce_rate_limit(api_key.id, bucket="get")

    query = db.query(ForecastLog).order_by(ForecastLog.id.desc())
    if company:
        query = query.filter(ForecastLog.company == company.strip().upper())
    rows = query.limit(max(1, min(limit, 50))).all()
    return [
        {
            "job_id": r.id,
            "company": r.company,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "error": r.error,
        }
        for r in rows
    ]


@app.get("/forecasts/{job_id}")
def get_forecast(
    job_id: int,
    api_key: ApiKey = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    enforce_rate_limit(api_key.id, bucket="get")

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


# Serve the built web frontend (web/dist) if present — one deployable unit.
# API routes are registered above, so they take precedence over the mount.
_web_dist = Path(__file__).resolve().parent.parent / "web" / "dist"
if _web_dist.is_dir():
    app.mount("/", StaticFiles(directory=_web_dist, html=True), name="web")
    log.info(f"Serving web frontend from {_web_dist}")
