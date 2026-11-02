"""Key quarterly metrics from results PDFs: fact sheets, investor releases, decks.

Per document: rebuild text lines from character positions, find the quarter
the document reports, then read each metric from income-statement rows first
and from highlight sentences second, normalised to ₹ crore and kept only when
inside sanity bounds. A row's values are matched to the column headers above
it, because companies order them differently (TCS oldest first, Infosys
newest first, L&T with the prior quarter left of the label).

Banks report no revenue: their top line is net interest income (NII) and
their margin the net interest margin (NIM), so those are metrics of their
own, and a result whose documents carry NII but no revenue has the "bank"
metric set.
"""

import re
from typing import Any, NamedTuple

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from app.utils.logger import get_logger
from app.utils.periods import Period, document_period, find_period_spans, period_label

log = get_logger("FinancialDataExtractorTool")

FLAT_THRESHOLD_PCT = 0.5  # changes smaller than this (in %) count as "flat"

TREND_KEYS = (
    "total_revenue_inr_cr",
    "net_profit_inr_cr",
    "operating_margin_pct",
    "net_margin_pct",
    "net_interest_income_inr_cr",
    "net_interest_margin_pct",
)

# Plausible values for one quarter of a listed Indian company, in ₹ crore
# (the largest report about ₹2.5 lakh crore of quarterly revenue) and in %.
# Anything outside is a misread column, a full-year figure or a per-share number.
BOUNDS = {
    "total_revenue_inr_cr": (10, 1_000_000),
    "net_profit_inr_cr": (-100_000, 200_000),
    "operating_profit_inr_cr": (-100_000, 500_000),
    "ebitda_inr_cr": (-100_000, 500_000),
    "ebitda_margin_pct": (-100, 100),
    "operating_margin_pct": (-100, 100),
    "net_margin_pct": (-100, 100),
    "net_interest_income_inr_cr": (10, 200_000),
    "net_interest_margin_pct": (0, 10),
}

# Multipliers to ₹ crore. 1 crore = 10 million = 100 lakh.
_UNIT_TO_CRORE = {"crore": 1.0, "cr": 1.0, "million": 0.1, "mn": 0.1, "billion": 100.0, "bn": 100.0, "lakh": 0.01}
_INR = r"(?:₹|\brs\b\.?|\binr)"
_UNIT = r"(crores?|cr|million|mn|billion|bn|lakhs?)\b"
_NUM = r"\d[\d,]*(?:\.\d+)?"

# Row labels per metric, best first. A label must match a table row's whole
# label, after footnote marks ("PAT1", "Net interest margin1,2") and unit
# notes ("PAT (₹ in Crores)") are dropped.
_PCT = r"(?: ?\(?%\)?)?"
_WHOLE_BANK = r"(?: [-–] whole bank| \(whole bank\))?"  # SBI; its "domestic" NIM is not the bank's
_LABELS = {
    "total_revenue_inr_cr": [
        r"revenues?(?: from operations)?",
        r"total revenues?(?: from operations)?",
        r"(?:total )?income from operations",
        r"it services revenue",
        r"gross revenue",  # ITC; its "net revenue" is net of the levies on cigarettes
    ],
    "net_profit_inr_cr": [
        r"net profit(?: \(after non-controlling interests?\))?",
        r"net income",
        r"profit for the (?:period|quarter)",
        r"profit after tax(?:es)?|pat",
        r"(?:reported|overall) pat",  # L&T, beside a "recurring" PAT
    ],
    "operating_profit_inr_cr": [
        r"ebit",
        r"operating (?:profit|income)",
        r"it services operating income",
    ],
    "operating_margin_pct": [
        rf"(?:operating|ebit) margin{_PCT}",
        rf"it services operating margin{_PCT}",
    ],
    # What Reliance, ITC and L&T report instead of EBIT; their operating margin.
    "ebitda_inr_cr": [r"ebitda"],
    "ebitda_margin_pct": [rf"ebitda(?: margin{_PCT}| ?\(?%\)?)"],
    "net_margin_pct": [rf"(?:net (?:profit |income )?|pat )margin{_PCT}"],
    "net_interest_income_inr_cr": [r"net interest income", r"nii"],
    "net_interest_margin_pct": [
        rf"net interest margins?(?: \(nim\))?{_WHOLE_BANK}{_PCT}",
        rf"nim{_WHOLE_BANK}{_PCT}",
    ],
}
_LABEL_RES = {k: [re.compile(rf"(?:{p})", re.I) for p in pats] for k, pats in _LABELS.items()}
_FOOTNOTE = re.compile(r"(?<=[a-z)])(?:\d{1,2}(?:,\d{1,2})*|[*^#†]+)$", re.I)
_UNIT_NOTE = re.compile(r"\s*\((?:in\s+)?(?:₹|rs\.?|inr)[^)]*\)", re.I)

# Highlight sentences: "INR Revenue of ₹ 731,880 Mn", "Net income ... ₹32.0 billion".
# The label must open the sentence or bullet, after at most a few company-level
# words: in "O2C – Revenue ₹ 201,803 crore", "JPL PAT at ₹ 8,387 crore" or
# "Net revenue of ₹ 9.6 bn" it names a segment or subsidiary. The gap may not
# cross a currency sign, so "USD Revenue of $ 7,642 Mn" never borrows a later
# rupee figure.
_QUALIFIERS = r"(?:(?:inr|total|consolidated|record|quarterly|the)\s+){0,3}"
_PROSE = {
    "total_revenue_inr_cr": re.compile(
        rf"{_QUALIFIERS}revenues?(?: from operations)?\b[^₹$\n]{{0,40}}?{_INR}\s*({_NUM})\s*{_UNIT}", re.I
    ),
    "net_profit_inr_cr": re.compile(
        rf"{_QUALIFIERS}(?:net profit|net income|profit after tax(?:es)?|pat|profit for the (?:period|quarter))\b"
        rf"[^₹$\n]{{0,40}}?{_INR}\s*({_NUM})\s*{_UNIT}",
        re.I,
    ),
    "operating_margin_pct": re.compile(
        rf"{_QUALIFIERS}(?:it services )?(?:operating|ebit) margin\b[^%\n]{{0,40}}?(-?\d+(?:\.\d+)?)\s*%", re.I
    ),
    "net_margin_pct": re.compile(
        rf"{_QUALIFIERS}net (?:profit |income )?margin\b[^%\n]{{0,40}}?(-?\d+(?:\.\d+)?)\s*%", re.I
    ),
    "net_interest_income_inr_cr": re.compile(
        rf"{_QUALIFIERS}(?:net interest income|nii)\b[^₹$\n]{{0,40}}?{_INR}\s*({_NUM})\s*{_UNIT}", re.I
    ),
    # "Net interest margin of 3.16%", "Net interest margin ^ (NIM) of 3.26%"
    "net_interest_margin_pct": re.compile(
        rf"{_QUALIFIERS}(?:net interest margins?|nim)\b[^%\n]{{0,40}}?(-?\d+(?:\.\d+)?)\s*%", re.I
    ),
}
_SENTENCE_BREAK = re.compile(r"[.;|]\s+")
# Forward-looking sentences quote targets, not results; the others cover
# more than the quarter ("Annual Net Profit of ₹ 80,032 crores",
# "for FY26, Gross Revenue at Rs. 80867.49 cr.", "H1 revenues grew").
_GUIDANCE = re.compile(r"guidance|expect|outlook|in the range", re.I)
_NOT_THE_QUARTER = re.compile(
    r"\b(?:annual|full[- ]year|for the year|year ended|half[- ]year|six months|nine months|ytd|h[12]|9m)\b"
    r"|\bfy\s?['’]?\d{2,4}\b|\bfiscal (?:year )?20\d{2}\b",
    re.I,
)

# A unit line above a table: "₹ Crore % of Revenue", "(Amount in ₹ Crores)",
# "In US $ million". Lines naming no money unit ("(in %)", "(Nos.)") end the
# previous unit's reach.
_UNIT_LINE_INR = re.compile(rf"{_INR}\s*(?:in\s+)?{_UNIT}", re.I)
_UNIT_LINE_USD = re.compile(r"(?:us\s*)?\$\s*(?:in\s+)?(?:million|mn|m|billion|bn)\b", re.I)
_UNIT_LINE_OTHER = re.compile(r"^\(?\s*(?:in\s+)?(?:%|nos\.?|numbers?)\s*\)?$", re.I)

# A table value: "49,244", "(397)", "10.7%", "(3.6%)", "(42.9)%", "-", or a
# basis-point change ("-3 bps", joined to "-3bps" before splitting).
_VALUE_TOKEN = re.compile(r"^\(?[-–+]?[₹$]?\d[\d,]*(?:\.\d+)?(?:%\)?|\)%|\)|bps?)?\**$|^[-–]$", re.I)
_BPS = re.compile(r"([-–+]?\d+(?:\.\d+)?)\s+(bps?)\b", re.I)
_LEADER = re.compile(r"^(?:[a-z0-9]\)|\d+\.|[-–•➢✓▪■●*])\s*", re.I)

# Column headers. Besides quarters, a header names full-year, half-year and
# nine-month columns ("FY26", "H1-2027", "9M FY27") and change columns
# ("QoQ", "y-o-y", "% Var", "Growth (%)", SBI's "Q1FY27 over Q4FY26").
_OTHER_PERIOD = re.compile(
    r"\b(?:(?:h[12]|9m|ytd)\s?[-_]?\s?(?:fy)?\s?['’]?(?:20)?\d{2}|fy\s?['’]?(?:20)?\d{2}(?:-\d{2})?"
    r"|fiscal\s+(?:year\s+)?20\d{2})\b",
    re.I,
)
_CHANGE_COLUMN = re.compile(
    r"(?:\b(?:[qy]-?o-?[qy]|q[1-4]-o-q[1-4]|growth|change|chg|var(?:iance)?|over|goly)\b|%\s*var\b|\(%\))"
    r"(?:\s*\(%\))?",
    re.I,
)
_OTHER, _CHANGE = "other", "change"  # header columns that are not a quarter
_CUMULATIVE_CAPTION = re.compile(r"\b(?:year|six months|nine months|twelve months|half[- ]year) ended\b", re.I)
_QUARTER_CAPTION = re.compile(r"\bquarter|\bthree months", re.I)


# --- Text --------------------------------------------------------------------

_BULLETS = "➢✓•▪■●►❖"
_STACKED_HEAD = re.compile(r"^(?:q[1-4]|h[12]|9m)[-–]$", re.I)  # "Q2-" over "2026"
_YEAR_WORD = re.compile(r"^(?:20)?\d{2}$")
_FY_WORD = re.compile(r"^fy\s?['’]?(?:20)?\d{2}$", re.I)
# A page about one part of the company: "SBI and its subsidiaries", "Segment
# Revenue", "Infrastructure Projects Segment". Its figures are not the company's.
_PART_TITLE = re.compile(r"\bsubsidiar|\bsegment|\bassociates?\b|\bjoint ventures?\b", re.I)


def _page_lines(page) -> list[str]:
    """Text lines of one page, rebuilt from character positions.

    A PDF's text order is its drawing order, which in many fact sheets is
    every label first and every number after, so plain text extraction
    separates a row's label from its values. Here the characters PDFium
    emits as one run become a word, and words sharing a vertical band
    become a line, read left to right. Text set beside a table on the same
    band becomes lines of its own after the page's other lines, and a page
    titled after a subsidiary or segment gives no lines.
    """
    width, height = page.get_width(), page.get_height()
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
            h = top - bottom
            # Text parked outside the page (Reliance's slide numbers) is not shown.
            if h <= 0 or right <= 0 or left >= width or top <= 0 or bottom >= height:
                cur = None
                continue
            y = (bottom + top) / 2
            if cur is not None and abs(y - cur[0]) < h * 0.4 and -h * 0.2 < left - cur[3] < h * 0.6:
                cur[3] = right
                cur[4] += ch
            else:
                cur = [y, h, left, right, ch]
                words.append(cur)
    finally:
        textpage.close()

    if words and _PART_TITLE.search(_title(words)):
        return []

    words.sort(key=lambda w: -w[0])
    rows: list[list[list[Any]]] = []
    for w in words:
        if rows and abs(w[0] - rows[-1][0][0]) <= min(w[1], rows[-1][0][1]) * 0.4:
            rows[-1].append(w)
        else:
            rows.append([w])
    for row in rows:
        row.sort(key=lambda w: w[2])
    lines, beside = [], []
    for row in _join_stacked_headers(rows):
        main, tails = _split_beside(row)
        lines.append(" ".join(w[4] for w in main))
        beside += [" ".join(w[4] for w in tail) for tail in tails]
    return lines + beside


def _title(words: list[list[Any]]) -> str:
    """The page's words in its largest type, top to bottom."""
    tallest = max(w[1] for w in words)
    return " ".join(w[4] for w in sorted(words, key=lambda w: (-w[0], w[2])) if w[1] >= tallest * 0.95)


def _join_stacked_headers(rows: list[list[list[Any]]]) -> list[list[list[Any]]]:
    """ICICI Bank sets each column header on two lines ("Q2-" over "2026",
    "Q2-o-Q2" over "(%)") with the full-year column ("FY2026") between them;
    rebuild them as one header line."""
    for r, row in enumerate(rows):
        if sum(1 for w in row if _STACKED_HEAD.match(w[4])) < 2:
            continue
        for k in (r + 1, r + 2):
            if k >= len(rows) or row[0][0] - rows[k][0][0] > 2.5 * row[0][1]:
                break
            for v in list(rows[k]):
                above = next((w for w in row if w[2] < v[3] and v[2] < w[3]), None)
                if above is not None and (
                    _YEAR_WORD.match(v[4]) if _STACKED_HEAD.match(above[4]) else v[4] in ("%", "(%)")
                ):
                    above[3], above[4] = max(above[3], v[3]), above[4] + v[4]
                    rows[k].remove(v)
                elif above is None and k == r + 1 and _FY_WORD.match(v[4]):
                    row.append(v)
                    rows[k].remove(v)
        row.sort(key=lambda w: w[2])
    return [row for row in rows if row]


def _is_value(text: str) -> bool:
    return bool(_VALUE_TOKEN.match(text))


def _split_beside(row: list[list[Any]]) -> tuple[list[list[Any]], list[list[list[Any]]]]:
    """Split off text set beside a table on the same band: a bullet after a
    wide gap ("Q2 FY27 ➢ Strong revenue growth..."), or words after a row's
    values that do not end in values themselves ("EBITDA 50,367 62,409 6.5
    23.9% growth in Digital Services"). Values on both sides of a label
    (L&T's "744 828 11% Revenue 2557 2859 12%") stay one row."""
    tails: list[list[list[Any]]] = []
    for i in range(len(row) - 1, 0, -1):
        w, prev = row[i], row[i - 1]
        if w[2] - prev[3] <= 1.5 * w[1]:
            continue
        rest = row[i:]
        beside = w[4][0] in _BULLETS or (
            _is_value(prev[4])
            and not _is_value(w[4])
            and not _is_value(rest[-1][4])
            and not _only_column_names(" ".join(x[4] for x in rest))
        )
        if beside:
            tails.insert(0, rest)
            row = row[:i]
    return row, tails


def _only_column_names(text: str) -> bool:
    """True for "Growth %" or "Jun 30, 2026 Growth %" (the rest of a
    header), false for "growth in Digital Services"."""
    for start, end, _ in find_period_spans(text):
        text = text[:start] + " " * (end - start) + text[end:]
    return not re.search(r"[a-z0-9]", _CHANGE_COLUMN.sub(" ", _OTHER_PERIOD.sub(" ", text)), re.I)


def _pdf_pages(path: str) -> list[list[str]]:
    pdf = pdfium.PdfDocument(path)
    try:
        return [_page_lines(page) for page in pdf]
    finally:
        pdf.close()


# --- Parsing -------------------------------------------------------------------


def _number(token: str) -> float | None:
    t = token.rstrip("*").lower().removesuffix("bps").removesuffix("bp")
    t = t.replace("%", "").replace(",", "").replace("₹", "").replace("$", "").replace("–", "-").replace("+", "")
    negative = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    if t in ("", "-"):
        return None
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if negative else v


class _Row(NamedTuple):
    label: str
    # (kind, number) in column order; kind is "amount", "pct" or "bps".
    values: list[tuple[str, float | None]]

    def of(self, kind: str) -> list[float | None]:
        return [v for k, v in self.values if k == kind]


def _kind(token: str) -> str:
    return "bps" if token.lower().rstrip("*").endswith(("bps", "bp")) else "pct" if "%" in token else "amount"


def _split_row(line: str) -> _Row | None:
    """A table row as its label and values, or None for other lines.

    "Revenues 49,244 44,490 10.7% 48,211 2.1%" gives "Revenues" with amounts
    49244, 44490, 48211 and percentages 10.7, 2.1. L&T puts the prior
    quarter left of the label: "36.2 Reported PAT 41.2 14%".
    """
    tokens = _BPS.sub(r"\1\2", line).split()
    trailing: list[str] = []
    while tokens and _is_value(tokens[-1]):
        trailing.insert(0, tokens.pop())
    leading: list[str] = []
    # A lone dash at the start is a bullet ("- Fee income 257.42 ..."), not a value.
    while trailing and tokens and _is_value(tokens[0]) and tokens[0] not in "-–":
        leading.append(tokens.pop(0))
    label = _LEADER.sub("", " ".join(tokens)).strip(" :")
    if not trailing or not re.search(r"[a-z]", label, re.I):
        return None
    return _Row(label, [(_kind(t), _number(t)) for t in leading + trailing])


def _header_columns(line: str) -> list[Any] | None:
    """The columns of a header line ("Q2 FY26 Q1 FY27 Q2 FY27 QoQ YoY",
    "Particulars Sep 30, 2026 Sep 30, 2025 Jun 30, 2026"), else None: each
    a quarter, _OTHER (a full-year or half-year column) or _CHANGE. A
    header holds nothing but such names and a few words; a sentence that
    mentions quarters ("84 bps in Q2 FY27, 62 bps in Q1 FY27") is not one."""
    spans = [(s, e, p) for s, e, p in find_period_spans(line)]
    masked = line
    for start, end, _ in spans:
        masked = masked[:start] + " " * (end - start) + masked[end:]
    for rx, tag in ((_OTHER_PERIOD, _OTHER), (_CHANGE_COLUMN, _CHANGE)):
        for m in rx.finditer(masked):
            spans.append((m.start(), m.end(), tag))
        for start, end, t in spans:
            if t == tag:
                masked = masked[:start] + " " * (end - start) + masked[end:]
    named = sum(1 for _, _, c in spans if c != _CHANGE)
    if not named or re.search(r"\d", masked):
        return None
    if len(re.findall(r"[a-z]{2,}", masked, re.I)) > (3 if named == 1 else 10):
        return None
    return [c for _, _, c in sorted(spans)]


def _header_periods(line: str) -> list[Period] | None:
    columns = _header_columns(line)
    return None if columns is None else [c for c in columns if isinstance(c, tuple)]


def _unit_of(line: str) -> str | None | bool:
    """The unit a line declares for the table below it: a ₹ unit word,
    "usd", None for a non-money unit, or False when it declares none.
    Reliance's "₹ crore ₹ crore $ Bn %" names a US$ translation column
    beside the ₹ ones, so a ₹ unit wins."""
    row = _split_row(line)
    if row is not None and row.of("amount"):
        return False  # a data row, even if its label mentions a unit
    m = _UNIT_LINE_INR.search(line)
    if m:
        return m.group(1).lower().rstrip("s")
    if _UNIT_LINE_USD.search(line):
        return "usd"
    if _UNIT_LINE_OTHER.match(line.strip()):
        return None
    return False


def _label_rank(metric: str, label: str) -> int | None:
    label = _FOOTNOTE.sub("", _UNIT_NOTE.sub("", " ".join(label.lower().split())))
    for rank, rx in enumerate(_LABEL_RES[metric]):
        if rx.fullmatch(label):
            return rank
    return None


def _column_value(row: _Row, columns: list[Any], target: Period, pct: bool) -> tuple[float | None, int] | None:
    """The row's value in `target`'s column and its index among the row's
    amounts, or None when the values cannot be matched to the columns.

    With one value per column the match is direct. Otherwise the values are
    the quarter and year columns in order, either alone (the change columns
    hold percentages, kept apart) or followed by at most two extra columns
    ("Revenue 283,548 362,268 37.8 27.8%" under "Q2 FY26 Q2 FY27", with a
    US$ translation and a change). More is a segment matrix ("PAT 1078 596
    314 36 2496 (397) 4123" under one quarter)."""
    if len(row.values) == len(columns):
        i = columns.index(target)
        kind, value = row.values[i]
        if kind == "bps" or (kind == "pct" and not pct):
            return None
        return value, sum(1 for k, _ in row.values[:i] if k == "amount")
    named = [c for c in columns if c != _CHANGE]
    amounts, pcts = row.of("amount"), row.of("pct")
    # A margin row may carry its figures as percentages; "% of revenue"
    # columns beside amount columns are a different reading (see _candidates).
    series = pcts if pct and not amounts else amounts
    if len(series) == len(named) or 2 <= len(named) < len(series) <= len(named) + 2:
        i = named.index(target)
        return series[i], i
    return None


def _candidates(pages: list[list[str]], period: Period | None) -> list[tuple[tuple, str, float, str]]:
    """Every reading of every metric as (sort_key, metric, value, source).
    Sort keys order table rows before sentences, then by label preference,
    then by position in the document."""
    out = []
    for page_no, lines in enumerate(pages, start=1):
        unit: str | None = None
        header: list[Any] | None = None
        # Captions and headers can take several lines (SBI: "Q1FY27 / over /
        # Q4FY26" growth columns around the quarter line; ICICI: "(%)" under
        # "(₹ billion)"). Within such a block the widest header and the money
        # unit hold.
        block_header: list[Any] | None = None
        block_unit = False
        # Under "Financials for the Year ended 31-Mar-26" (HCLTech), date
        # headers name years, not quarters.
        cumulative = False
        for line_no, line in enumerate(lines):
            pos = (page_no, line_no)
            if _QUARTER_CAPTION.search(line):
                cumulative = False
            elif _CUMULATIVE_CAPTION.search(line):
                cumulative = True
            # One caption line can carry both ("IFRS Q1’27 ( ₹ million) QoQ Growth").
            u = _unit_of(line)
            hc = _header_columns(line)
            if u is not False or hc is not None:
                if u is not False and not (block_unit and u is None):
                    unit, block_unit = u, u is not None
                if hc is not None and (block_header is None or len(hc) >= len(block_header)):
                    header = block_header = [_OTHER if cumulative and isinstance(c, tuple) else c for c in hc]
                continue
            block_header, block_unit = None, False

            row = _split_row(line)
            if row and header:
                quarters = [c for c in header if isinstance(c, tuple)]
                target = period if period in quarters else (None if period or not quarters else max(quarters))
                if target is not None:
                    _add_row_candidates(out, row, header, target, unit, pos, f"p.{page_no} table: {row.label}")

            out.extend(_sentence_candidates(line, pos, f"p.{page_no} text: {line.strip()[:80]}"))
    return out


def _add_row_candidates(out: list, row: _Row, header: list[Any], target: Period, unit: str | None, pos, src: str):
    amounts, pcts = row.of("amount"), row.of("pct")
    # "% of revenue" columns mirror the amount columns.
    mirrored = pcts if len(pcts) == len(amounts) > 1 else None
    for metric in _LABELS:
        rank = _label_rank(metric, row.label)
        if rank is None:
            continue
        if metric.endswith("_pct"):
            found = _column_value(row, header, target, pct=True)
            if found and found[0] is not None:
                out.append(((0, rank, pos), metric, found[0], src))
            continue
        found = _column_value(row, header, target, pct=False)
        if unit not in _UNIT_TO_CRORE or not found or found[0] is None:
            continue
        value, i = found
        out.append(((0, rank, pos), metric, value * _UNIT_TO_CRORE[unit], src))
        margin = {"operating_profit_inr_cr": "operating_margin_pct", "ebitda_inr_cr": "ebitda_margin_pct"}.get(metric)
        if margin and mirrored and i < len(mirrored) and mirrored[i] is not None:
            out.append(((0, 9, pos), margin, mirrored[i], src))


def _sentence_candidates(line: str, pos: tuple[int, int], src: str) -> list[tuple[tuple, str, float, str]]:
    without_quarters = line
    for start, end, _ in reversed(find_period_spans(line)):
        without_quarters = without_quarters[:start] + " " + without_quarters[end:]
    if _GUIDANCE.search(line) or _NOT_THE_QUARTER.search(without_quarters):
        return []
    out = []
    starts = [0] + [m.end() for m in _SENTENCE_BREAK.finditer(line)]
    for metric, rx in _PROSE.items():
        for start in starts:
            sentence = line[start:]
            m = rx.match(sentence, len(sentence) - len(_LEADER.sub("", sentence)))
            if not m:
                continue
            value = _number(m.group(1))
            if value is None:
                continue
            if m.lastindex and m.lastindex >= 2:
                value *= _UNIT_TO_CRORE[m.group(2).lower().rstrip("s")]
            out.append(((1, 0, pos), metric, value, src))
            break
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


_TOP_LINE = ("total_revenue_inr_cr", "net_interest_income_inr_cr")


def _extract(pages: list[list[str]]) -> tuple[Period | None, dict[str, Any]]:
    period = _document_period(pages)
    candidates = sorted(_candidates(pages, period), key=lambda c: c[0])
    # The main income statement is the page of the first table reading of
    # the top line. A reading there beats any from another page, where a
    # subsidiary's or segment's table may use a preferred label (L&T: a
    # segment's "PAT" against the group's "Reported PAT").
    top_line = (k[2][0] for k, metric, v, _ in candidates if k[0] == 0 and metric in _TOP_LINE and _in_bounds(metric, v))
    anchor = next(top_line, None)
    picked: dict[str, float] = {}
    sources: dict[str, str] = {}
    page_of: dict[str, int] = {}
    for key, metric, value, src in sorted(candidates, key=lambda c: (c[0][0], c[0][2][0] != anchor, *c[0][1:])):
        if metric not in picked and _in_bounds(metric, value):
            picked[metric], sources[metric], page_of[metric] = value, src, key[2][0]

    revenue = picked.get("total_revenue_inr_cr")
    # A profit larger than revenue is a misread (another table, a full year).
    for metric in ("net_profit_inr_cr", "operating_profit_inr_cr", "ebitda_inr_cr"):
        if revenue and metric in picked and abs(picked[metric]) > revenue:
            del picked[metric], sources[metric]
    if revenue:
        for margin, profit in (
            ("operating_margin_pct", "operating_profit_inr_cr"),
            ("ebitda_margin_pct", "ebitda_inr_cr"),
            ("net_margin_pct", "net_profit_inr_cr"),
        ):
            # Only a profit from the main table gives the company's margin
            # (Reliance's other EBIT is Jio's). A margin stated off that table
            # yields to one derived there (Jio's EBITDA margin against the
            # group's EBITDA).
            if profit not in picked or (anchor is not None and page_of[profit] != anchor):
                continue
            if margin not in picked or page_of[margin] != anchor:
                picked[margin] = picked[profit] / revenue * 100
                sources[margin] = f"derived: {profit} / revenue"
    if "operating_margin_pct" not in picked and "ebitda_margin_pct" in picked:
        picked["operating_margin_pct"] = picked["ebitda_margin_pct"]
        sources["operating_margin_pct"] = f"EBITDA margin, {sources['ebitda_margin_pct']}"

    metrics = {key: (round(picked[key], _DECIMALS.get(key, 2)) if key in picked else None) for key in TREND_KEYS}
    return period, {
        "period": period_label(period) if period else None,
        "metrics": metrics,
        "sources": {k: v for k, v in sources.items() if k in TREND_KEYS},
    }


_DECIMALS = {"operating_margin_pct": 1, "net_margin_pct": 1}  # NIM keeps 2 ("3.16%")


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


def results_document(path: str) -> tuple[bool, Period | None]:
    """Whether a PDF reads as a quarter's results (it states a profit),
    and the quarter it reports. Investor-day and debt-investor decks give
    ratios and history but no quarterly profit."""
    try:
        period, doc = _extract(_pdf_pages(path))
    except Exception as e:
        log.error(f"PDF read failed {path}: {e}")
        return False, None
    m = doc["metrics"]
    return m["net_profit_inr_cr"] is not None or m["net_margin_pct"] is not None, period


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

    def found(key: str) -> bool:
        return any(d["metrics"][key] is not None for d in docs)

    bank = found("net_interest_income_inr_cr") and not found("total_revenue_inr_cr")
    return {"metric_set": "bank" if bank else "standard", "documents": docs, "trend_summary": trend}
