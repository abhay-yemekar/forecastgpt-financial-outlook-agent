"""Golden set: recorded lines from the two latest results documents of each
seeded company, as the line rebuilder produced them, with the values
checked by hand against the PDFs. The snippets keep only the lines the
extractor reads (unit lines, captions, column headers, metric rows, metric
sentences); on the full documents it gives the same result.

On 2 Nov 2026 SBI, ITC and L&T had not yet published Q2 FY27, so theirs
are Q1 FY27 and Q4 FY26.
"""

import json
from pathlib import Path

import pytest

from app.tools.financial_extractor import extract_from_pages

GOLDEN = json.loads((Path(__file__).parent / "fixtures" / "extraction_golden.json").read_text(encoding="utf-8"))

BANKS = {"HDFC Bank", "ICICI Bank", "SBI"}
# What each kind of company must yield: banks report net interest income
# and margin instead of revenue and operating margin.
REQUIRED = {
    "bank": ("net_interest_income_inr_cr", "net_profit_inr_cr", "net_interest_margin_pct"),
    "standard": ("total_revenue_inr_cr", "net_profit_inr_cr", "operating_margin_pct", "net_margin_pct"),
}


def _pages(doc: dict) -> list[list[str]]:
    last = max(int(p) for p in doc["pages"])
    return [doc["pages"].get(str(n), []) for n in range(1, last + 1)]


@pytest.mark.parametrize("doc", GOLDEN, ids=[d["document"] for d in GOLDEN])
def test_golden_document(doc):
    out = extract_from_pages(_pages(doc))
    assert {"period": out["period"], **out["metrics"]} == doc["expected"]


def test_golden_set_covers_ten_companies_two_quarters_each():
    companies = {d["company"] for d in GOLDEN}
    assert companies == {"TCS", "Infosys", "HCLTech", "Wipro", "Reliance", "ITC", "L&T"} | BANKS
    for company in companies:
        periods = {d["expected"]["period"] for d in GOLDEN if d["company"] == company}
        assert len(periods) == 2, (company, periods)
    for d in GOLDEN:
        required = REQUIRED["bank" if d["company"] in BANKS else "standard"]
        missing = [k for k in required if d["expected"][k] is None]
        assert not missing, (d["document"], missing)
        if d["company"] in BANKS:
            assert d["expected"]["total_revenue_inr_cr"] is None, d["document"]
