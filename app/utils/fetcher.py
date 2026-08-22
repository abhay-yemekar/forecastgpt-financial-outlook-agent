import os
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .config import settings
from .logger import get_logger

log = get_logger("fetcher")

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
        if any(k in text for k in ["earnings call", "transcript"]):
            tr_candidates.append(url)
        elif any(k in text for k in ["financial", "results", "fact sheet", "quarter", "consolidated"]):
            fin_candidates.append(url)

    fin_urls = fin_candidates[:max_quarters]
    tr_urls = tr_candidates[:3]

    fin_paths = [_download(u, settings.DATA_DIR) for u in fin_urls]
    tr_paths = [_download(u, settings.DATA_DIR) for u in tr_urls]
    return fin_paths, tr_paths

def fetch_given_urls(urls):
    return [_download(u, settings.DATA_DIR) for u in urls]
