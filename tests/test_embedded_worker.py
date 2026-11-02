"""Embedded-worker mode (EMBED_WORKER=1) integration tests."""

import threading
import time
from types import SimpleNamespace

from app.config import settings


def test_embedded_worker_off_by_default(client):
    # The client fixture never enables EMBED_WORKER; the startup hook must
    # be a no-op (no rq-embedded-worker thread).
    names = [t.name for t in threading.enumerate()]
    assert "rq-embedded-worker" not in names


def test_embedded_worker_processes_a_real_job(client, fake_redis, monkeypatch, auth_headers):
    monkeypatch.setattr(settings, "EMBED_WORKER", True)
    monkeypatch.setattr("app.jobs.fetch_recent_docs", lambda slug, max_quarters=2: (["q.pdf"], ["t.pdf"]))
    fake_run = lambda q, f, t, company_name, symbol, llm_api_key=None: {  # noqa: E731
        "company": company_name,
        "confidence": {"level": "high", "reasons": ["embedded test"]},
    }
    monkeypatch.setattr("app.jobs.get_agent", lambda: SimpleNamespace(run=fake_run))

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
    """Standalone create_worker() forks per job except on Windows."""
    import sys

    from rq import SimpleWorker

    from app.worker import create_worker

    worker = create_worker()
    assert isinstance(worker, SimpleWorker) == (sys.platform == "win32")


def test_embedded_worker_runs_in_process_with_timer_timeouts(fake_redis):
    """Embedded mode never forks from the API's threads, and its job timeout
    can't rely on SIGALRM (main thread only)."""
    from rq import SimpleWorker
    from rq.timeouts import TimerDeathPenalty

    from app.worker import create_worker

    worker = create_worker(embedded=True)
    assert isinstance(worker, SimpleWorker)
    assert worker.death_penalty_class is TimerDeathPenalty


def _slow_job():
    # Python-level loop so the timer's async exception is delivered promptly.
    for _ in range(100):
        time.sleep(0.05)
    return "finished"


def test_embedded_job_timeout_fires_inside_a_thread(fake_redis):
    from rq import Queue

    from app.worker import create_worker

    worker = create_worker(embedded=True)
    worker._install_signal_handlers = lambda: None
    job = Queue("forecasts", connection=fake_redis).enqueue(_slow_job, job_timeout=1)

    started = time.time()
    thread = threading.Thread(target=lambda: worker.work(burst=True), daemon=True)
    thread.start()
    thread.join(timeout=15)

    assert not thread.is_alive()
    assert time.time() - started < 4  # killed at ~1 s, not after the full 5 s
    job.refresh()
    assert job.is_failed
    assert "JobTimeoutException" in (job.latest_result().exc_string or "")
