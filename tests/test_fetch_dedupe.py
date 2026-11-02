from types import SimpleNamespace

from app.db.models import ForecastLog
from app.db.mysql import SessionLocal
from app.jobs import run_forecast_job
from app.utils import fetcher


def _row() -> int:
    db = SessionLocal()
    row = ForecastLog(company="INFY", query="q", status="queued", model_used="test:fake", storage_backend="sqlite")
    db.add(row)
    db.commit()
    row_id = row.id
    db.close()
    return row_id


def _fake_agent(monkeypatch):
    run = lambda q, f, t, company_name, symbol, llm_api_key=None: {"company": company_name}  # noqa: E731
    monkeypatch.setattr("app.jobs.get_agent", lambda: SimpleNamespace(run=run))


def test_one_screener_scrape_per_job(monkeypatch, fake_redis):
    calls = []

    def fake_recent(slug, max_quarters=2):
        calls.append(slug)
        return ["q2.pdf", "q1.pdf"], ["t2.pdf"]

    monkeypatch.setattr("app.jobs.fetch_recent_docs", fake_recent)
    _fake_agent(monkeypatch)
    row_id = _row()
    assert run_forecast_job(row_id, "INFY", "INFY", "Infosys", "q", None, None) == "completed"
    assert calls == ["INFY"]
    db = SessionLocal()
    try:
        assert db.get(ForecastLog, row_id).input_meta == {
            "financial_docs": ["q2.pdf", "q1.pdf"],
            "transcripts": ["t2.pdf"],
        }
    finally:
        db.close()


def test_given_urls_skip_the_scrape_entirely(monkeypatch, fake_redis):
    def no_scrape(*a, **k):
        raise AssertionError("scraped screener.in although both URL lists were given")

    monkeypatch.setattr("app.jobs.fetch_recent_docs", no_scrape)
    monkeypatch.setattr("app.jobs.fetch_given_urls", lambda urls: list(urls))
    _fake_agent(monkeypatch)
    assert run_forecast_job(_row(), "INFY", "INFY", "Infosys", "q", ["f.pdf"], ["t.pdf"]) == "completed"


def test_given_financials_only_scrapes_once_for_transcripts(monkeypatch, fake_redis):
    calls = []
    monkeypatch.setattr(
        "app.jobs.fetch_recent_docs",
        lambda slug, max_quarters=2: calls.append(slug) or (["scraped-fin.pdf"], ["t.pdf"]),
    )
    monkeypatch.setattr("app.jobs.fetch_given_urls", lambda urls: list(urls))
    _fake_agent(monkeypatch)
    row_id = _row()
    run_forecast_job(row_id, "INFY", "INFY", "Infosys", "q", ["mine.pdf"], None)
    assert calls == ["INFY"]
    db = SessionLocal()
    try:
        # The caller's financials win; only transcripts come from the scrape.
        assert db.get(ForecastLog, row_id).input_meta == {"financial_docs": ["mine.pdf"], "transcripts": ["t.pdf"]}
    finally:
        db.close()


# --- PDF cache key (F27) ----------------------------------------------------


class _Resp:
    def __init__(self, body: bytes):
        self.body = body
        self.is_redirect = self.is_permanent_redirect = False
        self.headers = {}

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield self.body

    def close(self):
        pass


def _fake_http(monkeypatch):
    fetched = []

    def fake_get(url, **kwargs):
        fetched.append(url)
        return _Resp(f"PDF from {url}".encode())

    monkeypatch.setattr(fetcher, "validate_url", lambda url: url)
    monkeypatch.setattr(fetcher.requests, "get", fake_get)
    return fetched


def test_same_filename_different_urls_never_collide(monkeypatch, tmp_path):
    _fake_http(monkeypatch)
    q1 = fetcher._download("https://www.infosys.com/q1/press-release.pdf", str(tmp_path))
    q2 = fetcher._download("https://www.infosys.com/q2/press-release.pdf", str(tmp_path))
    assert q1 != q2
    assert open(q1, "rb").read() == b"PDF from https://www.infosys.com/q1/press-release.pdf"
    assert open(q2, "rb").read() == b"PDF from https://www.infosys.com/q2/press-release.pdf"
    assert q1.endswith("_press-release.pdf")  # still readable


def test_same_url_is_downloaded_once(monkeypatch, tmp_path):
    fetched = _fake_http(monkeypatch)
    url = "https://www.bseindia.com/xml-data/corpfiling/AttachLive/abc.pdf"
    first = fetcher._download(url, str(tmp_path))
    second = fetcher._download(url, str(tmp_path))
    assert first == second
    assert fetched == [url]


def test_cache_filename_is_bounded_and_safe():
    name = fetcher.cache_filename("https://x.example/AnnPdfOpen.aspx?Pname=" + "a" * 500 + ".pdf")
    assert len(name) <= 16 + 1 + 80
    assert "/" not in name and "?" not in name
