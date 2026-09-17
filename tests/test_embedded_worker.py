"""Embedded-worker mode (EMBED_WORKER=1) integration tests."""

import threading
import time

from app.config import settings


def test_embedded_worker_off_by_default(client):
    # The client fixture never enables EMBED_WORKER; the startup hook must
    # be a no-op (no rq-embedded-worker thread).
    names = [t.name for t in threading.enumerate()]
    assert "rq-embedded-worker" not in names


def test_embedded_worker_processes_a_real_job(client, fake_redis, monkeypatch, auth_headers):
    monkeypatch.setattr(settings, "EMBED_WORKER", True)
    monkeypatch.setattr("app.jobs.fetch_recent_docs", lambda slug, max_quarters=2: (["q.pdf"], ["t.pdf"]))
    monkeypatch.setattr(
        "app.jobs.agent.run",
        lambda q, f, t, company_name, symbol, llm_api_key=None: {
            "company": company_name,
            "confidence": {"level": "high", "reasons": ["embedded test"]},
        },
    )

    # TestClient startup fires the hook; the worker thread shares the fake
    # Redis with the queue (fake_redis patches app.jobs.Redis).
    with client:
        resp = client.post("/forecasts", json={"query": "q", "company": "TCS"}, headers=auth_headers)
        assert resp.status_code == 202
        job_id = resp.json()["job_id"]

        deadline = time.time() + 20
        body = {}
        while time.time() < deadline:
            body = client.get(f"/forecasts/{job_id}", headers=auth_headers).json()
            if body["status"] in ("completed", "failed"):
                break
            time.sleep(0.2)

        assert body["status"] == "completed", f"embedded worker did not process job: {body}"
        assert body["result"]["company"] == "Tata Consultancy Services"


def test_create_worker_platform_choice(fake_redis):
    """create_worker() respects the platform: SimpleWorker on win32."""
    import sys

    from app.worker import create_worker

    worker = create_worker()
    if sys.platform == "win32":
        from rq import SimpleWorker

        assert isinstance(worker, SimpleWorker)
