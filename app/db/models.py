from sqlalchemy import JSON, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class ForecastLog(Base):
    __tablename__ = "forecast_logs"
    id = Column(Integer, primary_key=True, index=True)
    query = Column(Text, nullable=False)
    input_meta = Column(JSON, nullable=True)
    output_json = Column(JSON, nullable=False)
    model_used = Column(String(128), nullable=False)
    storage_backend = Column(String(32), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
