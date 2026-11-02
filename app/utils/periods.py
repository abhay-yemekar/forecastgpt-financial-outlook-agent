"""Fiscal quarters as Indian results documents name them.

The fiscal year ends on 31 March: Q1 is Apr-Jun, Q2 Jul-Sep, Q3 Oct-Dec and
Q4 Jan-Mar, so FY27 runs from April 2026 to March 2027. A period is a
(fiscal_year, quarter) tuple such as (2027, 2), which sorts chronologically.
Filings name the same quarter many ways ("Q2 FY27", "Q2'27", "Q2 2026-27",
"quarter ended September 30, 2026", "30-Sep-26", "Second Quarter, Fiscal
2027"), and URLs add "2026-27/q2" and "q2fy27".
"""

import re
from collections import Counter

Period = tuple[int, int]

_MONTHS = {"mar": 3, "jun": 6, "sep": 9, "dec": 12}
_ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4}
_MON = r"(?P<mon>mar|jun|sep|dec)[a-z]*\.?"

# Each pattern's named groups feed _to_period.
_PATTERNS = [
    # Q2 FY27, Q2FY27, q2fy27, Q2 FY 2027, Q2-FY27
    re.compile(r"\bq\s?(?P<q>[1-4])\s*[-_ ]?\s*fy\s?(?P<fy>\d{4}|\d{2})\b", re.I),
    # Q2'27 (Wipro)
    re.compile(r"\bq(?P<q>[1-4])\s?['’]\s?(?P<fy>\d{2})\b", re.I),
    # Q2 2026-27 (TCS), and 2026-27/q2, 2026-2027/q2, 2026-2027/quarter-2 in URLs
    re.compile(r"\bq(?P<q>[1-4])\s+(?P<start>20\d{2})\s*-\s*(?:\d{4}|\d{2})\b", re.I),
    re.compile(r"\b(?P<start>20\d{2})-(?:\d{4}|\d{2})/(?:q|quarter-)(?P<q>[1-4])\b", re.I),
    # Second Quarter, Fiscal 2027
    re.compile(
        r"\b(?P<ord>first|second|third|fourth)\s+quarter,?\s+(?:of\s+)?(?:fiscal(?:\s+year)?|fy)\s*(?P<fy>20\d{2}|\d{2})\b",
        re.I,
    ),
    # September 30, 2026 / Sep 30, 2026 / 30th September 2026 / 30-Sep-26 / Sep'26
    re.compile(rf"\b{_MON}\s+(?P<day>\d{{1,2}}),?\s+(?P<year>20\d{{2}})\b", re.I),
    re.compile(
        rf"\b(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\s*[- ]\s*{_MON}\s*[-, ]\s*(?P<year>20\d{{2}}|\d{{2}})\b",
        re.I,
    ),
    re.compile(rf"\b{_MON}\s?['’](?P<year>\d{{2}})\b", re.I),
    # 30.09.2026 / 30/09/2026 (SEBI results statements)
    re.compile(r"\b(?P<day>\d{2})[./-](?P<mm>03|06|09|12)[./-](?P<year>20\d{2})\b"),
]


def period_label(p: Period) -> str:
    return f"Q{p[1]} FY{p[0] % 100:02d}"


def _year(text: str) -> int:
    y = int(text)
    return y + 2000 if y < 100 else y


def _to_period(m: re.Match) -> Period | None:
    g = m.groupdict()
    if g.get("mon") or g.get("mm"):
        if g.get("day") and int(g["day"]) < 28:  # not a quarter-end date
            return None
        month = int(g["mm"]) if g.get("mm") else _MONTHS[g["mon"][:3].lower()]
        year = _year(g["year"])
        # March closes Q4 of the year it falls in; June/Sep/Dec open the next FY.
        p = (year, 4) if month == 3 else (year + 1, month // 3 - 1)
    elif g.get("ord"):
        p = (_year(g["fy"]), _ORDINALS[g["ord"].lower()])
    elif g.get("start"):
        p = (int(g["start"]) + 1, int(g["q"]))
    else:
        p = (_year(g["fy"]), int(g["q"]))
    return p if 2000 <= p[0] <= 2100 else None


def find_period_spans(text: str) -> list[tuple[int, int, Period]]:
    """(start, end, period) for every quarter mention, in reading order.
    Overlapping matches keep the earliest, longest one."""
    hits = []
    for pat in _PATTERNS:
        for m in pat.finditer(text):
            p = _to_period(m)
            if p:
                hits.append((m.start(), m.end(), p))
    hits.sort(key=lambda h: (h[0], -h[1]))
    out: list[tuple[int, int, Period]] = []
    for h in hits:
        if not out or h[0] >= out[-1][1]:
            out.append(h)
    return out


def find_periods(text: str) -> list[Period]:
    return [p for _, _, p in find_period_spans(text)]


def document_period(lines: list[str]) -> Period | None:
    """The quarter a results document reports: the one it mentions most.

    Tables also carry the prior quarter and the year-ago quarter, but titles,
    headings and footnotes repeat the reported one. Ties go to the newest.
    """
    counts = Counter(p for line in lines for p in find_periods(line))
    if not counts:
        return None
    return max(counts, key=lambda p: (counts[p], p))
