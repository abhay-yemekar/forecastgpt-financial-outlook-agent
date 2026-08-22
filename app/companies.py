"""Company registry: which listed companies ForecastGPT can forecast.

The set of supported companies is a seeded `companies` table. Adding a new
company is a one-line change to SEED_COMPANIES (symbol + screener.in slug).
"""


from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import Company
from app.db.mysql import SessionLocal
from app.utils.logger import get_logger

log = get_logger("companies")

# screener.in organises company pages under the NSE symbol for these names,
# so symbol == screener_slug for the whole seed list today; the separate slug
# column exists for companies where the two differ.
SEED_COMPANIES = [
    {"symbol": "TCS", "screener_slug": "TCS", "display_name": "Tata Consultancy Services"},
    {"symbol": "INFY", "screener_slug": "INFY", "display_name": "Infosys"},
    {"symbol": "HCLTECH", "screener_slug": "HCLTECH", "display_name": "HCL Technologies"},
    {"symbol": "WIPRO", "screener_slug": "WIPRO", "display_name": "Wipro"},
    {"symbol": "HDFCBANK", "screener_slug": "HDFCBANK", "display_name": "HDFC Bank"},
    {"symbol": "ICICIBANK", "screener_slug": "ICICIBANK", "display_name": "ICICI Bank"},
    {"symbol": "SBIN", "screener_slug": "SBIN", "display_name": "State Bank of India"},
    {"symbol": "RELIANCE", "screener_slug": "RELIANCE", "display_name": "Reliance Industries"},
    {"symbol": "ITC", "screener_slug": "ITC", "display_name": "ITC Limited"},
    {"symbol": "LT", "screener_slug": "LT", "display_name": "Larsen & Toubro"},
]


def seed_companies() -> None:
    """Insert seed companies that are not in the table yet (idempotent)."""
    db = SessionLocal()
    try:
        existing = {c.symbol for c in db.query(Company).all()}
        added = 0
        for c in SEED_COMPANIES:
            if c["symbol"] not in existing:
                db.add(Company(**c, exchange="NSE"))
                added += 1
        db.commit()
        if added:
            log.info(f"Seeded {added} new companies into the registry.")
    finally:
        db.close()


def resolve_company(db: Session, ident: str) -> Company | None:
    """Resolve a user-supplied identifier (NSE symbol or screener slug, case-insensitive)."""
    norm = ident.strip().upper()
    return (
        db.query(Company)
        .filter((func.upper(Company.symbol) == norm) | (func.upper(Company.screener_slug) == norm))
        .first()
    )
