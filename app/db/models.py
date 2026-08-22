from sqlalchemy import JSON, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


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
    input_meta = Column(JSON, nullable=True)
    output_json = Column(JSON, nullable=False)
    model_used = Column(String(128), nullable=False)
    storage_backend = Column(String(32), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
