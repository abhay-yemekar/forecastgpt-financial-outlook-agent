import os
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from app.config import settings

from .logger import get_logger

log = get_logger("fetcher")

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
    os.makedirs(out_dir, exist_ok=True)
    filename = re.sub(r"[^\w\-.]+", "_", url.split("/")[-1]) or "doc.pdf"
    path = os.path.join(out_dir, filename)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    resp = requests.get(url, headers={"User-Agent": settings.USER_AGENT}, timeout=60)
    resp.raise_for_status()
    with open(path, "wb") as f:
        f.write(resp.content)
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
