from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)  # Argon2id
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    key_hash = Column(String(64), unique=True, nullable=False, index=True)  # sha256 hex
    prefix = Column(String(16), nullable=False)  # first chars of the raw key, for identification
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(16), unique=True, nullable=False, index=True)  # NSE symbol, e.g. "TCS"
    screener_slug = Column(String(32), unique=True, nullable=False)  # screener.in URL slug
    display_name = Column(String(128), nullable=False)
    exchange = Column(String(16), nullable=False, default="NSE")


class ForecastLog(Base):
    __tablename__ = "forecast_logs"
    id = Column(Integer, primary_key=True, index=True)
    company = Column(String(16), nullable=True, index=True)  # NSE symbol of the subject company
    query = Column(Text, nullable=False)
    status = Column(String(16), nullable=False, default="queued", index=True)  # queued|running|completed|failed
    error = Column(Text, nullable=True)
    input_meta = Column(JSON, nullable=True)
    output_json = Column(JSON, nullable=True)  # filled once status == completed
    model_used = Column(String(128), nullable=False)
    storage_backend = Column(String(32), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
