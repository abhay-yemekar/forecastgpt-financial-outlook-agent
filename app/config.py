import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration, read from the environment (or a local .env file).

    Field names double as environment variable names, e.g. LLM_PROVIDER.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM / embeddings — see app/ai for the provider implementations.
    LLM_PROVIDER: str = "ollama"  # ollama | openai | anthropic
    EMBEDDING_PROVIDER: str = "ollama"  # ollama | openai
    LLM_MODEL: str = "llama3.2"
    EMBEDDING_MODEL: str = "nomic-embed-text"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # Database configuration (used for logging only)
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DB: str = "forecastgpt"

    # Leave DATABASE_URL empty to use the MySQL settings above (with SQLite
    # fallback per ALLOW_SQLITE_FALLBACK). Set it to force a specific engine,
    # e.g. sqlite:///./dev.db or mysql+pymysql://user:pass@host:3306/forecastgpt.
    DATABASE_URL: str = ""
    ALLOW_SQLITE_FALLBACK: bool = True

    # Data / scraping
    DATA_DIR: str = "data/cache"
    USER_AGENT: str = "ForecastGPT/1.0"


settings = Settings()

# Ensure data directory always exists so PDF downloads never fail on missing folder
os.makedirs(settings.DATA_DIR, exist_ok=True)
