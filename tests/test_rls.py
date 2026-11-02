from contextlib import contextmanager
from types import SimpleNamespace

from app.db.models import Base
from app.db.mysql import enable_row_level_security


class _RecordingEngine:
    def __init__(self, dialect: str):
        self.dialect = SimpleNamespace(name=dialect)
        self.statements: list[str] = []

    @contextmanager
    def begin(self):
        yield SimpleNamespace(execute=lambda stmt: self.statements.append(str(stmt)))


def test_postgres_enables_rls_on_every_app_table():
    engine = _RecordingEngine("postgresql")
    enable_row_level_security(engine, Base.metadata)
    tables = {"users", "api_keys", "companies", "forecast_logs"}
    assert {t.name for t in Base.metadata.sorted_tables} == tables
    assert sorted(engine.statements) == sorted(f'ALTER TABLE "{t}" ENABLE ROW LEVEL SECURITY' for t in tables)


def test_other_databases_are_untouched():
    for dialect in ("sqlite", "mysql"):
        engine = _RecordingEngine(dialect)
        enable_row_level_security(engine, Base.metadata)
        assert engine.statements == []
