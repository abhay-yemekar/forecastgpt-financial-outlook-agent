import hashlib
import ipaddress
import os
import re
import socket
from datetime import date
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.config import settings

from .logger import get_logger
from .periods import find_periods, latest_ended_quarters

log = get_logger("fetcher")

# --- SSRF guardrails (GAP-02) -------------------------------------------------
# User-supplied document URLs are fetched server-side. The real threat is
# reaching *internal* space (loopback, private ranges, cloud metadata), so the
# hard rules are: http(s) only, every resolved IP must be public, redirects
# re-validated per hop, size-capped. Hosts are unrestricted by default because
# each listed company publishes filings on its OWN domain (wipro.com,
# hdfcbank.com, infosys.com, ...) — a static allowlist can never cover them.
# Set ALLOWED_DOC_HOSTS (comma-separated) to optionally lock to specific hosts.
ALLOWED_DOC_HOSTS = {
    h.strip().lower()
    for h in os.getenv("ALLOWED_DOC_HOSTS", "").split(",")
    if h.strip()
}
MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024  # 25 MB — filings/decks are far smaller
MAX_REDIRECTS = 3


class UnsafeUrlError(ValueError):
    """Raised when a URL fails the SSRF guardrails."""


def validate_url(url: str) -> str:
    """Validate scheme, optional host restriction, and resolved IPs."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeUrlError(f"only http/https URLs are allowed: {url!r}")
    host = (parsed.hostname or "").lower()
    if not host:
        raise UnsafeUrlError(f"URL has no hostname: {url!r}")
    # Optional restriction mode (unset by default — companies host filings
    # on their own domains).
    if ALLOWED_DOC_HOSTS and not any(
        host == h or host.endswith("." + h) for h in ALLOWED_DOC_HOSTS
    ):
        raise UnsafeUrlError(
            f"host {host!r} is not an allowed document source "
            f"(ALLOWED_DOC_HOSTS: {sorted(ALLOWED_DOC_HOSTS)})"
        )
    # Resolve and refuse private/loopback/link-local/reserved addresses
    # (guards literal-IP tricks and DNS rebinding to internal space).
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise UnsafeUrlError(f"could not resolve host {host!r}: {e}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise UnsafeUrlError(f"host {host!r} resolves to a non-public address ({ip})")
    return url


# Link classification for screener.in's #documents section. Text alone is not
# enough anymore: quarterly numbers often sit in investor presentation decks
# labelled just "PPT", while the URL (e.g. infosys.com/...quarterly-results...)
# says what it actually is. Annual reports deliberately do NOT match — wrong
# period and far too large for the prompt.
TRANSCRIPT_TEXT = ["earnings call", "transcript"]
FINANCIAL_TEXT = [
    "financial", "results", "fact sheet", "quarter", "consolidated",
    "presentation", "ppt",
]
FINANCIAL_URL = ["quarterly-results", "quarterly_results", "financial-results", "results.pdf"]

def classify_doc(url: str, text: str) -> str:
    """Return 'transcript', 'financial', or 'other' for a documents link."""
    url_l, text_l = url.lower(), (text or "").lower()
    if any(k in text_l for k in TRANSCRIPT_TEXT):
        return "transcript"
    if any(k in text_l for k in FINANCIAL_TEXT) or any(k in url_l for k in FINANCIAL_URL):
        return "financial"
    return "other"

def screener_docs_url(screener_slug: str) -> str:
    return f"https://www.screener.in/company/{screener_slug}/consolidated/#documents"

def cache_filename(url: str) -> str:
    """Cache file name for `url`: a URL-hash prefix plus a readable basename.
    The basename alone collides, since company sites reuse names like
    press-release.pdf every quarter and would serve last quarter's file."""
    digest = hashlib.sha256(url.encode()).hexdigest()[:16]
    basename = re.sub(r"[^\w\-.]+", "_", url.split("/")[-1])[:80] or "doc.pdf"
    return f"{digest}_{basename}"


def _download(url: str, out_dir: str) -> str:
    url = validate_url(url)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, cache_filename(url))
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    # Manual redirect loop so every hop re-passes validate_url (a redirect
    # from an allowlisted host to an internal address must be refused too).
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        current = validate_url(current)
        resp = requests.get(
            current, headers={"User-Agent": settings.USER_AGENT},
            timeout=60, allow_redirects=False, stream=True,
        )
        if resp.is_redirect or resp.is_permanent_redirect:
            nxt = urljoin(current, resp.headers.get("Location", ""))
            resp.close()
            current = nxt
            continue
        break
    else:
        raise UnsafeUrlError(f"too many redirects fetching {url!r}")
    resp.raise_for_status()

    size = 0
    with open(path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=64 * 1024):
            size += len(chunk)
            if size > MAX_DOWNLOAD_BYTES:
                f.close()
                os.remove(path)
                raise UnsafeUrlError(
                    f"document at {url!r} exceeds the {MAX_DOWNLOAD_BYTES // (1024 * 1024)} MB cap"
                )
            f.write(chunk)
    log.info(f"Downloaded {url} -> {path}")
    return path

# Each quarter's fact sheet or results deck on the company's own IR site, by
# screener slug. screener.in lists these late or not at all: on 2 Nov 2026 it
# had no Q2 FY27 deck for TCS, Infosys or Wipro, and no quarterly deck for
# Infosys since 2025. Fields: {q} 2, {fy2} 27, {fy_span} 2026-27, {fy_span4} 2026-2027.
IR_RESULTS_URLS = {
    "TCS": "https://www.tcs.com/content/dam/tcs/investor-relations/financial-statements/"
    "{fy_span}/q{q}/Presentations/Q{q}%20{fy_span}%20Fact%20Sheet.pdf",
    "INFY": "https://www.infosys.com/investors/reports-filings/quarterly-results/{fy_span4}/q{q}/documents/fact-sheet.pdf",
    "WIPRO": "https://www.wipro.com/content/dam/nexus/en/investor/quarterly-results/"
    "{fy_span4}/q{q}fy{fy2}/wipro-investor-ppt-q{q}fy{fy2}.pdf",
}


def ir_results_urls(company_slug: str, today: date, quarters: int = 3) -> list[str]:
    """IR-site results documents for the last `quarters` ended quarters,
    newest first; those not published yet simply fail to download."""
    template = IR_RESULTS_URLS.get(company_slug.upper())
    if not template:
        return []
    return [
        template.format(q=q, fy2=f"{fy % 100:02d}", fy_span=f"{fy - 1}-{fy % 100:02d}", fy_span4=f"{fy - 1}-{fy}")
        for fy, q in latest_ended_quarters(today, quarters)
    ]


def concall_decks(soup: BeautifulSoup, base_url: str) -> list[str]:
    """Results decks from screener.in's concall list, newest first. Each row
    is one results call; its "PPT" chip is a link when the deck exists and
    plain text when it doesn't."""
    urls = []
    for row in soup.select("#documents .concalls li"):
        for a in row.find_all("a", href=True):
            if a.get_text(strip=True).upper() == "PPT" and ".pdf" in a["href"].lower():
                urls.append(urljoin(base_url, a["href"]))
    return urls


def _unique(urls: list[str]) -> list[str]:
    return list(dict.fromkeys(urls))


def _is_pdf(path: str) -> bool:
    with open(path, "rb") as f:
        return f.read(5) == b"%PDF-"


def _download_results(candidates: list[str], max_quarters: int) -> list[str]:
    """Download candidates in order until `max_quarters` PDFs, skipping a URL
    that names a quarter already fetched, one that fails, or a page that is
    not a PDF (some "PPT" chips link to web pages)."""
    paths: list[str] = []
    quarters: set = set()
    for url in candidates:
        if len(paths) == max_quarters:
            break
        named = find_periods(unquote(url))
        quarter = max(named) if named else None
        if quarter is not None and quarter in quarters:
            continue
        try:
            path = _download(url, settings.DATA_DIR)
        except (requests.RequestException, UnsafeUrlError) as e:
            log.info(f"Skipping results document {url}: {e}")
            continue
        if not _is_pdf(path):
            log.info(f"Skipping results document {url}: not a PDF")
            continue
        if quarter is not None:
            quarters.add(quarter)
        paths.append(path)
    return paths


def fetch_recent_docs(company_slug: str, max_quarters: int = 2, today: date | None = None):
    """Download the latest results documents and earnings-call transcripts.
    Returns (financial_paths, transcript_paths).

    Results documents come from the company's IR site where its URL pattern
    is known, then from the decks in screener.in's concall list. The
    announcements list is a last resort: its "financial" matches are mostly
    press releases ("UNI Financial Cooperation ...").
    """
    base_url = screener_docs_url(company_slug)
    resp = requests.get(base_url, headers={"User-Agent": settings.USER_AGENT}, timeout=60)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    links = []
    for a in soup.select("#documents a[href]"):
        href = a.get("href")
        text = (a.get_text() or "").lower()
        if href and ".pdf" in href.lower():
            links.append((urljoin(base_url, href), text))

    fin_candidates, tr_candidates = [], []
    for url, text in links:
        kind = classify_doc(url, text)
        if kind == "transcript":
            tr_candidates.append(url)
        elif kind == "financial":
            fin_candidates.append(url)

    preferred = _unique(ir_results_urls(company_slug, today or date.today()) + concall_decks(soup, base_url))
    fin_paths = _download_results(preferred, max_quarters) or _download_results(fin_candidates, max_quarters)
    # The same transcript is often listed twice (announcement and concall row).
    tr_paths = [_download(u, settings.DATA_DIR) for u in _unique(tr_candidates)[:3]]
    return fin_paths, tr_paths

def fetch_given_urls(urls):
    return [_download(u, settings.DATA_DIR) for u in urls]
