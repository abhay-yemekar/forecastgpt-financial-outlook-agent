from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.utils.logger import get_logger

log = get_logger("db")

SQLITE_FALLBACK_URL = "sqlite:///./forecastgpt_fallback.db"

# Backend actually in use ("mysql", "sqlite_fallback", ...). Writers stamp this
# into every forecast_logs row so the fallback is never invisible downstream.
storage_backend = "unknown"


def _mysql_url() -> str:
    return (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DB}"
    )


def _create_engine_with_fallback():
    global storage_backend

    # Explicit override wins: no probing, no fallback logic.
    if settings.DATABASE_URL:
        engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
        storage_backend = engine.dialect.name
        log.info(f"Using explicit DATABASE_URL ({storage_backend}).")
        return engine

    try:
        engine = create_engine(_mysql_url(), pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        storage_backend = "mysql"
        log.info(f"Connected to MySQL at {settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DB}.")
        return engine
    except Exception as e:
        if not settings.ALLOW_SQLITE_FALLBACK:
            raise RuntimeError(
                f"MySQL is not reachable ({e}) and ALLOW_SQLITE_FALLBACK is disabled; refusing to start."
            ) from e
        storage_backend = "sqlite_fallback"
        log.warning(
            f"MySQL not available ({e}). Falling back to SQLite at '{SQLITE_FALLBACK_URL}'. "
            f"Every forecast_logs row is stamped storage_backend='sqlite_fallback'."
        )
        return create_engine(SQLITE_FALLBACK_URL, echo=False, future=True)


engine = _create_engine_with_fallback()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
