from app.utils.fetcher import classify_doc


def test_transcript_by_text():
    assert classify_doc("https://bseindia.com/x.pdf", "Transcript") == "transcript"
    assert classify_doc("https://bseindia.com/x.pdf", "Q2 earnings call transcript") == "transcript"


def test_financial_by_classic_text():
    assert classify_doc("https://x/y.pdf", "Financial results for the quarter") == "financial"
    assert classify_doc("https://x/y.pdf", "Q4 fact sheet") == "financial"


def test_financial_by_presentation_text():
    # screener.in lists investor decks labelled just "PPT" — these carry the
    # quarterly numbers now that labelled results PDFs are rare.
    assert classify_doc("https://bseindia.com/AnnPdfOpen.aspx?Pname=abc.pdf", "PPT") == "financial"


def test_financial_by_url():
    assert (
        classify_doc("https://infosys.com/investors/reports-filings/quarterly-results/q1.pdf", "view")
        == "financial"
    )


def test_annual_report_is_not_a_quarterly_financial():
    assert classify_doc("https://bseindia.com/AnnualReport/500209/x.pdf", "Annual Report 2025 from bse") == "other"


def test_news_and_random_pdfs_are_other():
    assert classify_doc("https://bseindia.com/x.pdf", "Infosys Collaborates With Knorr Bremse") == "other"
    assert classify_doc("https://bseindia.com/x.pdf", "Investor Conference 17 Aug") == "other"
