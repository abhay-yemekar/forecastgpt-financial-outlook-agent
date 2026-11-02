import pytest

from app.utils.periods import document_period, find_periods, period_label


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Q2 FY27 Performance Highlights", ["Q2 FY27"]),
        ("q2fy27 and Q2-FY27 and Q2 FY 2027", ["Q2 FY27", "Q2 FY27", "Q2 FY27"]),
        ("Q2’27 Revenue Distribution", ["Q2 FY27"]),
        ("Q1 2026-27 Fact Sheet", ["Q1 FY27"]),
        ("financial-statements/2025-26/q4/Presentations", ["Q4 FY26"]),
        ("quarterly-results/2026-2027/q2/documents/fact-sheet.pdf", ["Q2 FY27"]),
        ("financial-results/2026-2027/quarter-2/", ["Q2 FY27"]),
        ("Consolidated Financial Data - Second Quarter, Fiscal 2027", ["Q2 FY27"]),
        ("Particulars Sep 30, 2026 Sep 30, 2025 Jun 30, 2026", ["Q2 FY27", "Q2 FY26", "Q1 FY27"]),
        ("for the quarter ended September 30, 2026", ["Q2 FY27"]),
        ("30-Sep-25 30-Jun-26 30 - Sep - 26", ["Q2 FY26", "Q1 FY27", "Q2 FY27"]),
        ("Quarter ended 31.12.2025 and 31/03/2026", ["Q3 FY26", "Q4 FY26"]),
        ("Sep’26 & June’26 Diluted EPS", ["Q2 FY27", "Q1 FY27"]),
        ("30th June 2026", ["Q1 FY27"]),
    ],
)
def test_quarter_phrasings(text, expected):
    assert [period_label(p) for p in find_periods(text)] == expected


@pytest.mark.parametrize(
    "text",
    [
        "Investor Release dated October 12, 2026",  # not a quarter-end month
        "June 15, 2026",  # not a quarter-end day
        "FY27 Guidance",
        "Sub.: Investor Release Q 2 FY 202 7",  # broken glyph spacing must not read as FY20
    ],
)
def test_non_quarters(text):
    assert find_periods(text) == []


def test_document_period_is_the_most_mentioned_quarter():
    lines = ["Q2 FY27 Performance", "Q2 FY26 Q1 FY27 Q2 FY27", "Revenue up in Q2 FY27"]
    assert document_period(lines) == (2027, 2)


def test_document_period_ties_go_to_the_newest():
    assert document_period(["Q1 FY27 Q2 FY27"]) == (2027, 2)


def test_document_period_none_without_quarters():
    assert document_period(["Annual Report 2026"]) is None
