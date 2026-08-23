from app.db.models import ForecastLog
from app.db.mysql import SessionLocal


def _add_row(company: str, status: str = "completed") -> int:
    db = SessionLocal()
    try:
        row = ForecastLog(
            company=company,
            query="test",
            status=status,
            model_used="test:fake",
            storage_backend="sqlite",
        )
        db.add(row)
        db.commit()
        return row.id
    finally:
        db.close()


def test_list_requires_key(client):
    assert client.get("/forecasts").status_code == 401


def test_list_newest_first_with_filter(client, auth_headers):
    _add_row("TCS")
    _add_row("INFY")
    _add_row("TCS", status="failed")

    resp = client.get("/forecasts", headers=auth_headers)
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) >= 3
    ids = [r["job_id"] for r in rows]
    assert ids == sorted(ids, reverse=True)
    assert {r["company"] for r in rows} >= {"TCS", "INFY"}
    assert all(set(r) == {"job_id", "company", "status", "created_at", "error"} for r in rows)

    filtered = client.get("/forecasts", params={"company": "infy"}, headers=auth_headers).json()
    assert filtered and all(r["company"] == "INFY" for r in filtered)


def test_list_limit_is_clamped(client, auth_headers):
    resp = client.get("/forecasts", params={"limit": 500}, headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) <= 50


def test_stats_open_and_counts(client):
    before = client.get("/stats").json()
    assert set(before) == {"companies", "forecasts_total", "forecasts_completed"}
    assert before["companies"] >= 10

    _add_row("TCS")
    _add_row("INFY", status="failed")

    after = client.get("/stats").json()
    assert after["forecasts_total"] == before["forecasts_total"] + 2
    assert after["forecasts_completed"] == before["forecasts_completed"] + 1
