import os

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

class Settings(BaseModel):
    # Model names – keep key names so you don't have to touch other files
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "llama3.2")
    EMBED_MODEL: str = os.getenv("EMBED_MODEL", "nomic-embed-text")

    # Database configuration (used for logging only)
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DB: str = os.getenv("MYSQL_DB", "forecastgpt")

    # Set DATABASE_URL to use a specific engine verbatim (skips MySQL probing).
    # Otherwise: try MySQL first; if unreachable, fall back to SQLite only when
    # ALLOW_SQLITE_FALLBACK is enabled (rows are stamped storage_backend).
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    ALLOW_SQLITE_FALLBACK: bool = os.getenv("ALLOW_SQLITE_FALLBACK", "true").lower() in ("1", "true", "yes")

    # Data / scraping
    DATA_DIR: str = os.getenv("DATA_DIR", "data/cache")
    USER_AGENT: str = os.getenv("USER_AGENT", "ForecastGPT/1.0")

settings = Settings()

# Ensure data directory always exists so PDF downloads never fail on missing folder
os.makedirs(settings.DATA_DIR, exist_ok=True)
