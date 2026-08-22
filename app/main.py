from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agent import ForecastAgent
from app.companies import resolve_company, seed_companies
from app.config import settings
from app.db.models import Base, Company, ForecastLog
from app.db.mysql import engine, get_db, storage_backend
from app.utils.fetcher import fetch_given_urls, fetch_recent_docs

Base.metadata.create_all(bind=engine)
seed_companies()

app = FastAPI(title="ForecastGPT - Financial Outlook Agent")
agent = ForecastAgent()


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


@app.post("/forecast")
def forecast(req: ForecastRequest, db: Session = Depends(get_db)):
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

    # Auto-fetch from Screener unless URLs provided
    if req.financial_doc_urls:
        fin_paths = fetch_given_urls(req.financial_doc_urls)
    else:
        fin_paths, _ = fetch_recent_docs(company.screener_slug, max_quarters=2)

    if req.transcript_urls:
        tr_paths = fetch_given_urls(req.transcript_urls)
    else:
        _, tr_paths = fetch_recent_docs(company.screener_slug, max_quarters=2)

    out = agent.run(
        req.query,
        fin_paths,
        tr_paths,
        company_name=company.display_name,
        symbol=company.symbol,
    )

    row = ForecastLog(
        company=company.symbol,
        query=req.query,
        input_meta={"financial_docs": fin_paths, "transcripts": tr_paths},
        output_json=out,
        model_used=f"{settings.LLM_PROVIDER}:{settings.LLM_MODEL}",
        storage_backend=storage_backend,
    )
    db.add(row)
    db.commit()

    return out


@app.get("/health")
def health():
    return {"status": "ok"}
