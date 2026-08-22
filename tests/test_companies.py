from app.companies import SEED_COMPANIES, resolve_company, seed_companies
from app.db.models import Company
from app.db.mysql import SessionLocal


def test_seed_is_idempotent():
    seed_companies()
    seed_companies()  # second run must not duplicate
    db = SessionLocal()
    try:
        symbols = [c.symbol for c in db.query(Company).all()]
        assert sorted(symbols) == sorted(c["symbol"] for c in SEED_COMPANIES)
    finally:
        db.close()


def test_resolve_by_symbol_case_insensitive():
    db = SessionLocal()
    try:
        c = resolve_company(db, "tcs")
        assert c is not None and c.symbol == "TCS" and c.screener_slug == "TCS"
    finally:
        db.close()


def test_resolve_unknown_returns_none():
    db = SessionLocal()
    try:
        assert resolve_company(db, "NOTACOMPANY") is None
    finally:
        db.close()
