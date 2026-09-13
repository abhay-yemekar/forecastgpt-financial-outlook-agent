import ipaddress
import os
import re
import socket
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.config import settings

from .logger import get_logger

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

def _download(url: str, out_dir: str) -> str:
    url = validate_url(url)
    os.makedirs(out_dir, exist_ok=True)
    filename = re.sub(r"[^\w\-.]+", "_", url.split("/")[-1]) or "doc.pdf"
    path = os.path.join(out_dir, filename)
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

def fetch_recent_docs(company_slug: str, max_quarters: int = 2):
    """Scrape Screener docs for `company_slug` and download latest PDFs.
    Returns (financial_paths, transcript_paths)
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

    fin_urls = fin_candidates[:max_quarters]
    tr_urls = tr_candidates[:3]

    fin_paths = [_download(u, settings.DATA_DIR) for u in fin_urls]
    tr_paths = [_download(u, settings.DATA_DIR) for u in tr_urls]
    return fin_paths, tr_paths

def fetch_given_urls(urls):
    return [_download(u, settings.DATA_DIR) for u in urls]
