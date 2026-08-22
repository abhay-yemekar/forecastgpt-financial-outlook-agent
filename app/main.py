from fastapi import Depends, FastAPI
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agent import ForecastAgent
from app.db.models import Base, ForecastLog
from app.db.mysql import engine, get_db, storage_backend
from app.utils.config import settings
from app.utils.fetcher import fetch_given_urls, fetch_recent_docs

Base.metadata.create_all(bind=engine)

app = FastAPI(title="ForecastGPT - Financial Forecasting Agent for TCS (Ollama)")
agent = ForecastAgent()

class ForecastRequest(BaseModel):
    query: str
    financial_doc_urls: list[str] | None = None
    transcript_urls: list[str] | None = None

@app.post("/forecast")
def forecast(req: ForecastRequest, db: Session = Depends(get_db)):
    # Auto-fetch from Screener unless URLs provided
    if req.financial_doc_urls:
        fin_paths = fetch_given_urls(req.financial_doc_urls)
    else:
        fin_paths, _ = fetch_recent_docs(max_quarters=2)

    if req.transcript_urls:
        tr_paths = fetch_given_urls(req.transcript_urls)
    else:
        _, tr_paths = fetch_recent_docs(max_quarters=2)

    out = agent.run(req.query, fin_paths, tr_paths)

    row = ForecastLog(
        query=req.query,
        input_meta={"financial_docs": fin_paths, "transcripts": tr_paths},
        output_json=out,
        model_used=settings.OPENAI_MODEL,
        storage_backend=storage_backend,
    )
    db.add(row)
    db.commit()

    return out

@app.get("/health")
def health():
    return {"status": "ok"}
