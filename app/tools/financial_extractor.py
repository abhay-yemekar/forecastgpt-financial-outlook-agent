"""Key quarterly metrics from results PDFs: fact sheets, investor releases, decks.

Per document: rebuild text lines from character positions, find the quarter
the document reports, then read each metric from income-statement rows first
and from highlight sentences second, normalised to ₹ crore and kept only when
inside sanity bounds. A row's columns are matched to the period headers above
it, because companies order them differently (TCS oldest first, Infosys
newest first).
"""

import re
from typing import Any

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from app.utils.logger import get_logger
from app.utils.periods import Period, document_period, find_period_spans, period_label

log = get_logger("FinancialDataExtractorTool")

FLAT_THRESHOLD_PCT = 0.5  # changes smaller than this (in %) count as "flat"

TREND_KEYS = ("total_revenue_inr_cr", "net_profit_inr_cr", "operating_margin_pct", "net_margin_pct")

# Plausible values for one quarter of a listed Indian company, in ₹ crore
# (the largest report about ₹2.5 lakh crore of quarterly revenue) and in %.
# Anything outside is a misread column, a full-year figure or a per-share number.
BOUNDS = {
    "total_revenue_inr_cr": (10, 1_000_000),
    "net_profit_inr_cr": (-100_000, 200_000),
    "operating_profit_inr_cr": (-100_000, 500_000),
    "operating_margin_pct": (-100, 100),
    "net_margin_pct": (-100, 100),
}

# Multipliers to ₹ crore. 1 crore = 10 million = 100 lakh.
_UNIT_TO_CRORE = {"crore": 1.0, "cr": 1.0, "million": 0.1, "mn": 0.1, "billion": 100.0, "bn": 100.0, "lakh": 0.01}
_INR = r"(?:₹|\brs\b\.?|\binr)"
_UNIT = r"(crores?|cr|million|mn|billion|bn|lakhs?)\b"
_NUM = r"\d[\d,]*(?:\.\d+)?"

# Row labels per metric, best first. A label must match a table row's whole label.
_LABELS = {
    "total_revenue_inr_cr": [
        r"revenues?(?: from operations)?",
        r"total revenues?(?: from operations)?",
        r"(?:total )?income from operations",
        r"it services revenue",
    ],
    "net_profit_inr_cr": [
        r"net profit(?: \(after non-controlling interests?\))?",
        r"net income",
        r"profit for the (?:period|quarter)",
        r"profit after tax(?:es)?|pat",
    ],
    "operating_profit_inr_cr": [
        r"ebit",
        r"operating (?:profit|income)",
        r"it services operating income",
    ],
    "operating_margin_pct": [
        r"(?:operating|ebit) margin(?: %)?",
        r"it services operating margin(?: %)?",
    ],
    "net_margin_pct": [r"net (?:profit |income )?margin(?: %)?"],
}
_LABEL_RES = {k: [re.compile(rf"(?:{p})", re.I) for p in pats] for k, pats in _LABELS.items()}

# Highlight sentences: "INR Revenue of ₹ 731,880 Mn", "Net income ... ₹32.0 billion".
# The gap may not cross a currency sign, so "USD Revenue of $ 7,642 Mn" never
# borrows a later rupee figure.
_PROSE = {
    "total_revenue_inr_cr": re.compile(
        rf"\b(?:total )?revenues?(?: from operations)?\b[^₹$\n]{{0,40}}?{_INR}\s*({_NUM})\s*{_UNIT}", re.I
    ),
    "net_profit_inr_cr": re.compile(
        rf"\b(?:net profit|net income|profit after tax(?:es)?|pat|profit for the (?:period|quarter))\b"
        rf"[^₹$\n]{{0,40}}?{_INR}\s*({_NUM})\s*{_UNIT}",
        re.I,
    ),
    "operating_margin_pct": re.compile(r"\b(?:operating|ebit) margin\b[^%\n]{0,40}?(-?\d+(?:\.\d+)?)\s*%", re.I),
    "net_margin_pct": re.compile(r"\bnet (?:profit |income )?margin\b[^%\n]{0,40}?(-?\d+(?:\.\d+)?)\s*%", re.I),
}
# Forward-looking sentences quote targets, not results.
_GUIDANCE = re.compile(r"guidance|expect|outlook|in the range", re.I)

# A unit line above a table: "₹ Crore % of Revenue", "(Amount in ₹ Crores)",
# "In US $ million". Lines naming no money unit ("(in %)", "(Nos.)") end the
# previous unit's reach.
_UNIT_LINE_INR = re.compile(rf"{_INR}\s*(?:in\s+)?{_UNIT}", re.I)
_UNIT_LINE_USD = re.compile(r"(?:us\s*)?\$\s*(?:in\s+)?(?:million|mn|m|billion|bn)\b", re.I)
_UNIT_LINE_OTHER = re.compile(r"^\(?\s*(?:in\s+)?(?:%|nos\.?|numbers?)\s*\)?$", re.I)

_VALUE_TOKEN = re.compile(r"^\(?[-–]?[₹$]?\d[\d,]*(?:\.\d+)?%?\)?\**$|^[-–]$")
_LEADER = re.compile(r"^(?:[a-z0-9]\)|\d+\.|[-•➢*])\s*", re.I)
_YEAR_HEADER = re.compile(r"^\W*(?:particulars\W+)?(?:(?:fy|fiscal)\s?['’]?\d{2,4}\W*){2,}$", re.I)


# --- Text --------------------------------------------------------------------


def _page_lines(page) -> list[str]:
    """Text lines of one page, rebuilt from character positions.

    A PDF's text order is its drawing order, which in many fact sheets is
    every label first and every number after, so plain text extraction
    separates a row's label from its values. Here the characters PDFium
    emits as one run become a word, and words sharing a vertical band
    become a line, read left to right.
    """
    textpage = page.get_textpage()
    try:
        words: list[list[Any]] = []  # [y_centre, height, x_left, x_right, text]
        cur = None
        for i in range(textpage.count_chars()):
            code = pdfium_c.FPDFText_GetUnicode(textpage.raw, i)
            ch = chr(code)
            # Lone UTF-16 surrogates (emoji halves) would break jsonb later.
            if ch.isspace() or code == 0 or 0xD800 <= code <= 0xDFFF:
                cur = None
                continue
            left, bottom, right, top = textpage.get_charbox(i, loose=True)
            height = top - bottom
            if height <= 0:
                cur = None
                continue
            y = (bottom + top) / 2
            if cur is not None and abs(y - cur[0]) < height * 0.4 and -height * 0.2 < left - cur[3] < height * 0.6:
                cur[3] = right
                cur[4] += ch
            else:
                cur = [y, height, left, right, ch]
                words.append(cur)
    finally:
        textpage.close()

    words.sort(key=lambda w: -w[0])
    rows: list[list[list[Any]]] = []
    for w in words:
        if rows and abs(w[0] - rows[-1][0][0]) <= min(w[1], rows[-1][0][1]) * 0.4:
            rows[-1].append(w)
        else:
            rows.append([w])
    return [" ".join(w[4] for w in sorted(row, key=lambda w: w[2])) for row in rows]


def _pdf_pages(path: str) -> list[list[str]]:
    pdf = pdfium.PdfDocument(path)
    try:
        return [_page_lines(page) for page in pdf]
    finally:
        pdf.close()


# --- Parsing -------------------------------------------------------------------


def _number(token: str) -> float | None:
    t = token.rstrip("*").replace("%", "").replace(",", "").replace("₹", "").replace("$", "").replace("–", "-")
    negative = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    if t in ("", "-"):
        return None
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if negative else v


def _split_row(line: str) -> tuple[str, list[float | None], list[float | None]] | None:
    """A table row as (label, amounts, percentages), or None for other lines.

    "Revenues 49,244 44,490 10.7% 48,211 2.1%" gives
    ("Revenues", [49244, 44490, 48211], [10.7, 2.1]).
    """
    tokens = line.split()
    values: list[str] = []
    while tokens and _VALUE_TOKEN.match(tokens[-1]):
        values.insert(0, tokens.pop())
    label = _LEADER.sub("", " ".join(tokens)).strip(" :")
    if not values or not re.search(r"[a-z]", label, re.I):
        return None
    amounts = [_number(v) for v in values if "%" not in v]
    pcts = [_number(v) for v in values if "%" in v]
    return label, amounts, pcts


def _header_periods(line: str) -> list[Period] | None:
    """The periods of a column-header line ("Q2 FY26 Q1 FY27 Q2 FY27",
    "Particulars Sep 30, 2026 Sep 30, 2025 Jun 30, 2026"), else None.
    A header holds nothing but period names and a few words; a sentence
    that mentions quarters ("84 bps in Q2 FY27, 62 bps in Q1 FY27") is not one.
    A full-year header ("FY25 FY26") gives [], so its rows are not read as
    the quarter's."""
    spans = find_period_spans(line)
    if not spans:
        return [] if _YEAR_HEADER.match(line) else None
    rest = line
    for start, end, _ in reversed(spans):
        rest = rest[:start] + " " + rest[end:]
    if re.search(r"\d", rest) or len(re.findall(r"[a-z]{2,}", rest, re.I)) > (3 if len(spans) == 1 else 10):
        return None
    return [p for _, _, p in spans]


def _unit_of(line: str) -> str | None | bool:
    """The unit a line declares for the table below it: a ₹ unit word,
    "usd", None for a non-money unit, or False when it declares none."""
    row = _split_row(line)
    if row is not None and row[1]:
        return False  # a data row, even if its label mentions a unit
    if _UNIT_LINE_USD.search(line):
        return "usd"
    m = _UNIT_LINE_INR.search(line)
    if m:
        return m.group(1).lower().rstrip("s")
    if _UNIT_LINE_OTHER.match(line.strip()):
        return None
    return False


def _label_rank(metric: str, label: str) -> int | None:
    label = " ".join(label.lower().split())
    for rank, rx in enumerate(_LABEL_RES[metric]):
        if rx.fullmatch(label):
            return rank
    return None


def _candidates(pages: list[list[str]], period: Period | None) -> list[tuple[tuple, str, float, str]]:
    """Every reading of every metric as (sort_key, metric, value, source).
    Sort keys order table rows before sentences, then by label preference,
    then by position in the document."""
    out = []
    for page_no, lines in enumerate(pages, start=1):
        unit: str | None = None
        header: list[Period] | None = None
        for line_no, line in enumerate(lines):
            pos = (page_no, line_no)
            # One caption line can carry both ("IFRS Q1’27 ( ₹ million) QoQ Growth").
            u = _unit_of(line)
            if u is not False:
                unit = u
            hp = _header_periods(line)
            if hp is not None:
                header = hp
            if u is not False or hp is not None:
                continue

            row = _split_row(line)
            if row and header:
                label, amounts, pcts = row
                target = period if period in header else (None if period else max(header))
                if target is not None:
                    idx = header.index(target)
                    # "% of revenue" columns mirror the amount columns.
                    mirrored = pcts if len(pcts) == len(amounts) and len(amounts) > 1 else None
                    for metric in _LABELS:
                        rank = _label_rank(metric, label)
                        if rank is None:
                            continue
                        src = f"p.{page_no} table: {label}"
                        if metric.endswith("_pct"):
                            series = mirrored or amounts or pcts
                            if idx < len(series) and series[idx] is not None:
                                out.append(((0, rank, pos), metric, series[idx], src))
                        elif unit in _UNIT_TO_CRORE and idx < len(amounts) and amounts[idx] is not None:
                            out.append(((0, rank, pos), metric, amounts[idx] * _UNIT_TO_CRORE[unit], src))
                            if metric == "operating_profit_inr_cr" and mirrored and mirrored[idx] is not None:
                                out.append(((0, 9, pos), "operating_margin_pct", mirrored[idx], src))

            if _GUIDANCE.search(line):
                continue
            for metric, rx in _PROSE.items():
                m = rx.search(line)
                if not m:
                    continue
                value = _number(m.group(1))
                if value is None:
                    continue
                if m.lastindex and m.lastindex >= 2:
                    value *= _UNIT_TO_CRORE[m.group(2).lower().rstrip("s")]
                out.append(((1, 0, pos), metric, value, f"p.{page_no} text: {line.strip()[:80]}"))
    return out


def _in_bounds(metric: str, value: float) -> bool:
    lo, hi = BOUNDS[metric]
    return lo <= value <= hi


def extract_from_pages(pages: list[list[str]]) -> dict[str, Any]:
    """Period, metrics and where each metric was read, for one document
    given as text lines per page."""
    return _extract(pages)[1]


def _document_period(pages: list[list[str]]) -> Period | None:
    """The quarter a document reports. Column headers list it with earlier
    quarters for comparison but never a later one, so the newest period in
    any multi-column header is it. Without such headers, the most-mentioned
    quarter (footnotes and balance-sheet dates make counting the weaker rule)."""
    header_periods = [
        p for lines in pages for line in lines if len(hp := _header_periods(line) or []) > 1 for p in hp
    ]
    if header_periods:
        return max(header_periods)
    return document_period([line for lines in pages for line in lines])


def _extract(pages: list[list[str]]) -> tuple[Period | None, dict[str, Any]]:
    period = _document_period(pages)
    picked: dict[str, float] = {}
    sources: dict[str, str] = {}
    for _, metric, value, src in sorted(_candidates(pages, period), key=lambda c: c[0]):
        if metric not in picked and _in_bounds(metric, value):
            picked[metric], sources[metric] = value, src

    revenue = picked.get("total_revenue_inr_cr")
    # A profit larger than revenue is a misread (another table, a full year).
    for metric in ("net_profit_inr_cr", "operating_profit_inr_cr"):
        if revenue and metric in picked and abs(picked[metric]) > revenue:
            del picked[metric], sources[metric]
    if revenue:
        for margin, profit in (("operating_margin_pct", "operating_profit_inr_cr"), ("net_margin_pct", "net_profit_inr_cr")):
            if margin not in picked and profit in picked:
                picked[margin] = picked[profit] / revenue * 100
                sources[margin] = f"derived: {profit} / revenue"

    metrics = {
        key: (round(picked[key], 1 if key.endswith("_pct") else 2) if key in picked else None) for key in TREND_KEYS
    }
    return period, {
        "period": period_label(period) if period else None,
        "metrics": metrics,
        "sources": {k: v for k, v in sources.items() if k in TREND_KEYS},
    }


# --- Trend ---------------------------------------------------------------------


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def compute_trend(docs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Compare the two most recent documents that yielded each metric.

    `docs` are newest first, so docs[0] is the latest quarter and docs[1]
    the previous one. Returns, per metric, a direction (up/down/flat) plus
    the percent change of latest vs previous; metrics with fewer than two
    numeric values are reported as "insufficient data". A second document
    for a quarter already counted is skipped.
    """
    trends: dict[str, dict[str, Any]] = {}
    for key in TREND_KEYS:
        values: list[float] = []
        seen: set[Any] = set()
        for d in docs:
            v = _to_float(d["metrics"].get(key))
            p = d.get("period")
            if v is None or (p is not None and p in seen):
                continue
            seen.add(p)
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
    """Extract key metrics from quarterly results PDFs, newest quarter first."""
    dated = []
    for p in pdf_paths:
        try:
            pages = _pdf_pages(p)
        except Exception as e:
            log.error(f"PDF read failed {p}: {e}")
            continue
        period, doc = _extract(pages)
        dated.append((period or (0, 0), {"path": p, **doc}))

    # Newest quarter first; documents with no recognisable quarter go last,
    # in the order given (sort() is stable).
    dated.sort(key=lambda pd: pd[0], reverse=True)
    docs = [doc for _, doc in dated]

    trend: dict[str, Any] = {"docs_analyzed": [d["path"] for d in docs]}
    trend.update(compute_trend(docs))

    return {"documents": docs, "trend_summary": trend}
