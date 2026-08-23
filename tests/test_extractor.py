from app.tools import financial_extractor as fe

SAMPLE_TEXT = (
    "Tata Consultancy Services Limited reported results for the quarter. "
    "Total revenue ₹ 64,479 crore, up from ₹ 62,963 crore year-on-year. "
    "Net profit ₹ 12,650 crore against ₹ 11,909 crore in the prior period. "
    "Operating margin 24.5 % while EBIT margin was mentioned separately."
)


def test_regex_extraction(monkeypatch):
    monkeypatch.setattr(fe, "_extract_text_from_pdf", lambda path: SAMPLE_TEXT)
    out = fe.extract_financial_metrics(["q2.pdf"])

    metrics = out["documents"][0]["metrics"]
    assert metrics["total_revenue_inr_cr"] == "64,479"
    assert metrics["net_profit_inr_cr"] == "12,650"
    assert metrics["operating_margin_pct"] == "24.5"


def test_rs_and_inr_currency_variants(monkeypatch):
    text = "Total revenue Rs. 62,963 crore and net profit INR 11,909 crore for the quarter."
    monkeypatch.setattr(fe, "_extract_text_from_pdf", lambda path: text)
    metrics = fe.extract_financial_metrics(["q.pdf"])["documents"][0]["metrics"]
    assert metrics["total_revenue_inr_cr"] == "62,963"
    assert metrics["net_profit_inr_cr"] == "11,909"


def test_bare_number_fallback_for_flattened_deck_tables(monkeypatch):
    # Investor decks extract as "label label label 162,990 34,424 ..." with no
    # currency next to the number.
    text = "Overview Total Revenue Operating Profit Operating Cash Flow 162,990 34,424 31,747"
    monkeypatch.setattr(fe, "_extract_text_from_pdf", lambda path: text)
    metrics = fe.extract_financial_metrics(["deck.pdf"])["documents"][0]["metrics"]
    assert metrics["total_revenue_inr_cr"] == "162,990"


def test_bare_number_fallback_ignores_small_numbers(monkeypatch):
    # "Revenue growth: 4.2%" must not be read as revenue in crore.
    text = "Revenue growth: 4.2% YoY Large deals: 11.6 billion"
    monkeypatch.setattr(fe, "_extract_text_from_pdf", lambda path: text)
    metrics = fe.extract_financial_metrics(["deck.pdf"])["documents"][0]["metrics"]
    assert metrics["total_revenue_inr_cr"] is None


def test_trend_summary_computed_across_two_quarters(monkeypatch):
    monkeypatch.setattr(fe, "_extract_text_from_pdf", lambda path: SAMPLE_TEXT)
    out = fe.extract_financial_metrics(["q2.pdf", "q1.pdf"])

    assert out["trend_summary"]["docs_analyzed"] == ["q2.pdf", "q1.pdf"]
    assert out["trend_summary"]["total_revenue_inr_cr"]["direction"] == "flat"  # same text both quarters


def test_failed_pdf_is_skipped(monkeypatch):
    def boom(path):
        raise OSError("corrupt pdf")

    monkeypatch.setattr(fe, "_extract_text_from_pdf", boom)
    out = fe.extract_financial_metrics(["bad.pdf"])
    assert out["documents"] == []
    assert out["trend_summary"]["total_revenue_inr_cr"] == {"direction": "insufficient data"}
