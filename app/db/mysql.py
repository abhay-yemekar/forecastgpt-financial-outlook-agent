from sqlalchemy import create_engine, make_url, text
from sqlalchemy.exc import ArgumentError
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


def check_database_url(raw: str) -> None:
    """Reject a DATABASE_URL that would put part of the password in the host.

    The URL parser ends the password at its first '@', so a raw '@' inside
    the password moves the rest of it into the host name, and the driver's
    DNS error then prints it to the logs. Errors here never echo the URL.
    """
    try:
        host = make_url(raw).host or ""
    except ArgumentError:
        raise RuntimeError("DATABASE_URL could not be parsed; see docs/DEPLOY.md, D-03.") from None
    if "@" in host:
        raise RuntimeError(
            "DATABASE_URL: the password contains a raw '@'. Percent-encode it as %40 "
            "(see docs/DEPLOY.md, D-03)."
        )


def _create_engine_with_fallback():
    global storage_backend

    # Explicit override wins: no probing, no fallback logic.
    if settings.DATABASE_URL:
        check_database_url(settings.DATABASE_URL)
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


def enable_row_level_security(engine, metadata) -> None:
    """Turn on row-level security for every app table (PostgreSQL only).

    On Supabase the public schema is also served by its REST Data API to
    anyone holding the publishable key, which the web app serves publicly.
    RLS with no policies gives those API roles no rows at all, while this
    app keeps full access because it connects as the tables' owner, which
    RLS does not restrict. Idempotent; a no-op on SQLite and MySQL.
    """
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        for table in metadata.sorted_tables:
            conn.execute(text(f'ALTER TABLE "{table.name}" ENABLE ROW LEVEL SECURITY'))
    log.info(f"Row-level security enabled on {len(metadata.sorted_tables)} app tables.")


engine = _create_engine_with_fallback()
# expire_on_commit=False keeps ORM attributes readable after commit/close
# (the CLI prints row fields after committing).
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
