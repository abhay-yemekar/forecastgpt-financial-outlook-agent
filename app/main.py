from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from redis import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import Principal, get_current_principal
from app.companies import resolve_company, seed_companies
from app.config import settings
from app.db.models import Base, Company, ForecastLog
from app.db.mysql import engine, get_db, storage_backend
from app.jobs import enqueue_forecast_job
from app.quota import enforce_user_quota, quota_usage
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
    principal: Principal = Depends(get_current_principal),
    x_provider_key: str | None = Header(default=None, alias="X-Provider-Key"),
    db: Session = Depends(get_db),
):
    enforce_rate_limit(principal.rate_limit_key)

    # D-2 hybrid: console users on the operator's managed LLM key are
    # quota'd; BYOK (X-Provider-Key) bypasses the quota.
    byok = bool(x_provider_key)
    if principal.is_user and not byok:
        enforce_user_quota(principal.id)

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
        owner_id=principal.id if principal.is_user else None,
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
            provider_key=x_provider_key,
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
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    """Recent forecast jobs, newest first — powers the web app's history
    panel. Console users see only their own jobs; API-key principals see all."""
    enforce_rate_limit(principal.rate_limit_key, bucket="get")

    query = db.query(ForecastLog).order_by(ForecastLog.id.desc())
    if principal.is_user:
        query = query.filter(ForecastLog.owner_id == principal.id)
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
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    enforce_rate_limit(principal.rate_limit_key, bucket="get")

    row = db.get(ForecastLog, job_id)
    # Console users may only read their own jobs; API keys (operator-level)
    # see everything. A 404 — not 403 — avoids leaking job ids.
    if row is None or (principal.is_user and row.owner_id != principal.id):
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


@app.get("/quota/me")
def my_quota(
    principal: Principal = Depends(get_current_principal),
):
    """Quota snapshot for the current console user (API-key principals are
    operator-level and not quota'd)."""
    if not principal.is_user:
        return {"quota": "unlimited", "kind": "api_key"}
    usage = quota_usage(principal.id)
    return {"quota": "free_tier", "kind": "user", "email": principal.label, **usage}


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
