import re
from typing import Any

import pdfplumber

from app.utils.logger import get_logger
from app.utils.text import clean_text

log = get_logger("FinancialDataExtractorTool")

def _extract_text_from_pdf(path: str) -> str:
    texts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            texts.append(page.extract_text() or "")
    return clean_text("\n".join(texts))

def _find(patterns: list[str], text: str) -> str | None:
    for pat in patterns:
        m = re.search(pat, text, flags=re.I)
        if m:
            return m.group(1)
    return None

FLAT_THRESHOLD_PCT = 0.5  # changes smaller than this (in %) count as "flat"

TREND_KEYS = ("total_revenue_inr_cr", "net_profit_inr_cr", "operating_margin_pct")


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def compute_trend(docs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Compare the two most recent documents that yielded each metric.

    Screener.in lists documents newest-first, so docs[0] is the latest quarter
    and docs[1] the previous one. Returns, per metric, a direction
    (up/down/flat) plus the percent change of latest vs previous; metrics with
    fewer than two numeric values are reported as "insufficient data".
    """
    trends: dict[str, dict[str, Any]] = {}
    for key in TREND_KEYS:
        values: list[float] = []
        for d in docs:
            v = _to_float(d["metrics"].get(key))
            if v is not None:
                values.append(v)
                if len(values) == 2:
                    break
        if len(values) < 2 or values[1] == 0:
            trends[key] = {"direction": "insufficient data"}
            continue
        pct_change = (values[0] - values[1]) / abs(values[1]) * 100
        if abs(pct_change) < FLAT_THRESHOLD_PCT:
            direction = "flat"
        elif pct_change > 0:
            direction = "up"
        else:
            direction = "down"
        trends[key] = {"direction": direction, "pct_change": round(pct_change, 1)}
    return trends


def extract_financial_metrics(pdf_paths: list[str]) -> dict[str, Any]:
    """Extract key metrics from quarterly financial PDFs."""
    docs = []
    for p in pdf_paths:
        try:
            text = _extract_text_from_pdf(p)
        except Exception as e:
            log.error(f"PDF read failed {p}: {e}")
            continue

        metrics = {}
        # Precise forms first (label + ₹/Rs/INR + crore); the fallback accepts
        # a bare crore-scale number shortly after the label, because investor
        # decks flatten tables into "Total Revenue Operating Profit ... 162,990".
        metrics["total_revenue_inr_cr"] = _find([
            r"total\s+revenue[^₹0-9]{0,30}(?:₹|rs\.?|inr)\s*([\d,]+\.?\d*)\s*crore",
            r"revenue[^₹0-9]{0,30}(?:₹|rs\.?|inr)\s*([\d,]+\.?\d*)\s*crore",
            r"total\s+revenue[^0-9]{0,60}([\d,]{4,})\.?\d*\b",
        ], text)

        metrics["net_profit_inr_cr"] = _find([
            r"net\s+profit[^₹0-9]{0,30}(?:₹|rs\.?|inr)\s*([\d,]+\.?\d*)\s*crore",
            r"profit\s+after\s+tax[^₹0-9]{0,30}(?:₹|rs\.?|inr)\s*([\d,]+\.?\d*)\s*crore",
            r"net\s+profit[^0-9]{0,60}([\d,]{4,})\.?\d*\b",
        ], text)

        metrics["operating_margin_pct"] = _find([
            r"operating\s+margin[^\d]{0,10}([\d.]+)\s*%",
            r"ebit\s+margin[^\d]{0,10}([\d.]+)\s*%",
        ], text)

        docs.append({"path": p, "metrics": metrics})

    trend: dict[str, Any] = {"docs_analyzed": [d["path"] for d in docs]}
    trend.update(compute_trend(docs))

    return {"documents": docs, "trend_summary": trend}
