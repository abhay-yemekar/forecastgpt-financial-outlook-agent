from datetime import date

import requests
from bs4 import BeautifulSoup

from app.utils import fetcher
from app.utils.periods import latest_ended_quarters

TODAY = date(2026, 11, 2)

# The shape of screener.in's #documents section: announcements first, then
# one concall row per results call. A missing deck is a <div>, not a link.
SCREENER_HTML = """
<div id="documents">
  <div class="documents flex-column"><h3>Announcements</h3><ul class="list-links">
    <li><a href="https://www.bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname=press.pdf">
      Canada'S UNI Financial Cooperation Advances Branch Modernization</a></li>
    <li><a href="https://www.bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname=tr-oct.pdf">
      Announcement under Regulation 30 (LODR)-Earnings Call Transcript</a></li>
  </ul></div>
  <div class="documents concalls flex-column"><ul class="list-links">
    <li><div>Oct 2026</div>
      <a class="button-chip" href="https://www.bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname=tr-oct.pdf">Transcript</a>
      <div class="button-chip">PPT</div></li>
    <li><div>Jul 2026</div>
      <a class="button-chip" href="https://www.bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname=tr-jul.pdf">Transcript</a>
      <a class="button-chip" href="https://nsearchives.nseindia.com/corporate/X_InvestorRelease.pdf">PPT</a></li>
    <li><div>Feb 2026</div>
      <a class="button-chip" href="https://www.bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname=analyst-meet.pdf">PPT</a></li>
  </ul></div>
</div>
"""


class _Page:
    text = SCREENER_HTML

    def raise_for_status(self):
        pass


def _fake_site(monkeypatch, tmp_path, missing=(), not_pdf=()):
    """Serve SCREENER_HTML and record downloads; `missing` URLs 404."""
    downloads = []

    def fake_download(url, out_dir):
        downloads.append(url)
        if any(m in url for m in missing):
            raise requests.HTTPError("404 Not Found")
        path = tmp_path / fetcher.cache_filename(url)
        path.write_bytes(b"<!DOCTYPE html>" if any(m in url for m in not_pdf) else b"%PDF-1.7 " + url.encode())
        return str(path)

    monkeypatch.setattr(fetcher.requests, "get", lambda url, **kw: _Page())
    monkeypatch.setattr(fetcher, "_download", fake_download)
    return downloads


def _sources(paths):
    return [open(p, "rb").read()[9:].decode() for p in paths]


def test_latest_ended_quarters():
    assert latest_ended_quarters(TODAY, 3) == [(2027, 2), (2027, 1), (2026, 4)]
    assert latest_ended_quarters(date(2027, 1, 20), 1) == [(2027, 3)]
    assert latest_ended_quarters(date(2027, 4, 1), 2) == [(2027, 4), (2027, 3)]


def test_ir_urls_match_the_published_q2_fy27_files():
    assert fetcher.ir_results_urls("TCS", TODAY, 1) == [
        "https://www.tcs.com/content/dam/tcs/investor-relations/financial-statements/"
        "2026-27/q2/Presentations/Q2%202026-27%20Fact%20Sheet.pdf"
    ]
    assert fetcher.ir_results_urls("INFY", TODAY, 1) == [
        "https://www.infosys.com/investors/reports-filings/quarterly-results/2026-2027/q2/documents/fact-sheet.pdf"
    ]
    assert fetcher.ir_results_urls("wipro", TODAY, 1) == [
        "https://www.wipro.com/content/dam/nexus/en/investor/quarterly-results/"
        "2026-2027/q2fy27/wipro-investor-ppt-q2fy27.pdf"
    ]
    assert fetcher.ir_results_urls("HCLTECH", TODAY) == []


def test_concall_decks_skip_rows_without_a_deck():
    soup = BeautifulSoup(SCREENER_HTML, "html.parser")
    assert fetcher.concall_decks(soup, "https://www.screener.in/") == [
        "https://nsearchives.nseindia.com/corporate/X_InvestorRelease.pdf",
        "https://www.bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname=analyst-meet.pdf",
    ]


def test_ir_documents_come_first_and_unpublished_quarters_are_skipped(monkeypatch, tmp_path):
    downloads = _fake_site(monkeypatch, tmp_path, missing=["2026-2027/q2/"])
    fin, _ = fetcher.fetch_recent_docs("INFY", today=TODAY)
    assert _sources(fin) == [
        "https://www.infosys.com/investors/reports-filings/quarterly-results/2026-2027/q1/documents/fact-sheet.pdf",
        "https://www.infosys.com/investors/reports-filings/quarterly-results/2025-2026/q4/documents/fact-sheet.pdf",
    ]
    assert not any("press.pdf" in u for u in downloads)


def test_without_an_ir_pattern_the_concall_decks_are_used(monkeypatch, tmp_path):
    _fake_site(monkeypatch, tmp_path)
    fin, _ = fetcher.fetch_recent_docs("HCLTECH", today=TODAY)
    assert _sources(fin) == [
        "https://nsearchives.nseindia.com/corporate/X_InvestorRelease.pdf",
        "https://www.bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname=analyst-meet.pdf",
    ]


def test_a_quarter_already_fetched_is_not_fetched_again(monkeypatch, tmp_path):
    downloads = _fake_site(monkeypatch, tmp_path)
    paths = fetcher._download_results(
        [
            "https://x.example/2026-27/q2/a.pdf",
            "https://y.example/q2fy27-deck.pdf",  # same quarter, other site
            "https://x.example/2026-27/q1/a.pdf",
        ],
        2,
    )
    assert len(paths) == 2
    assert "https://y.example/q2fy27-deck.pdf" not in downloads


def test_web_pages_behind_a_ppt_chip_are_skipped(monkeypatch, tmp_path):
    _fake_site(monkeypatch, tmp_path, not_pdf=["X_InvestorRelease"])
    fin, _ = fetcher.fetch_recent_docs("HCLTECH", max_quarters=1, today=TODAY)
    assert _sources(fin) == ["https://www.bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname=analyst-meet.pdf"]


def test_announcements_are_the_last_resort(monkeypatch, tmp_path):
    _fake_site(monkeypatch, tmp_path, missing=["nseindia", "analyst-meet"])
    fin, _ = fetcher.fetch_recent_docs("HCLTECH", today=TODAY)
    assert _sources(fin) == ["https://www.bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname=press.pdf"]


def test_a_transcript_listed_twice_is_fetched_once(monkeypatch, tmp_path):
    _fake_site(monkeypatch, tmp_path)
    _, tr = fetcher.fetch_recent_docs("HCLTECH", today=TODAY)
    assert _sources(tr) == [
        "https://www.bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname=tr-oct.pdf",
        "https://www.bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname=tr-jul.pdf",
    ]
