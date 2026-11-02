"""Golden set (#31): recorded lines from the two latest results documents of
TCS, Infosys, HCLTech and Wipro, as the line rebuilder produced them, with
the values checked by hand against the PDFs. The snippets keep only the
lines the extractor reads (unit lines, column headers, metric rows, metric
sentences); on the full documents it gives the same result."""

import json
from pathlib import Path

import pytest

from app.tools.financial_extractor import extract_from_pages

GOLDEN = json.loads((Path(__file__).parent / "fixtures" / "extraction_golden.json").read_text(encoding="utf-8"))


def _pages(doc: dict) -> list[list[str]]:
    last = max(int(p) for p in doc["pages"])
    return [doc["pages"].get(str(n), []) for n in range(1, last + 1)]


@pytest.mark.parametrize("doc", GOLDEN, ids=[d["document"] for d in GOLDEN])
def test_golden_document(doc):
    out = extract_from_pages(_pages(doc))
    assert {"period": out["period"], **out["metrics"]} == doc["expected"]


def test_golden_set_covers_four_companies_two_quarters_each():
    companies = {d["document"].split()[0] for d in GOLDEN}
    assert companies == {"TCS", "Infosys", "HCLTech", "Wipro"}
    for company in companies:
        periods = {d["expected"]["period"] for d in GOLDEN if d["document"].startswith(company)}
        assert periods == {"Q2 FY27", "Q1 FY27"}
    for d in GOLDEN:
        missing = [k for k, v in d["expected"].items() if v is None]
        assert not missing, (d["document"], missing)
