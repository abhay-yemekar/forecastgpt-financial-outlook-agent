from app.tools import financial_extractor as fe

SAMPLE_TEXT = (
    "Tata Consultancy Services Limited reported results for the quarter. "
    "Total revenue ₹ 64,479 crore, up from ₹ 62,963 crore year-on-year. "
    "Net profit ₹ 12,650 crore against ₹ 11,909 crore in the prior period. "
    "Operating margin 24.5 % while EBIT margin was mentioned separately."
)


def metrics(*lines: str, pages: list[list[str]] | None = None) -> dict:
    return fe.extract_from_pages(pages if pages is not None else [list(lines)])["metrics"]


# --- Highlight sentences -------------------------------------------------------


def test_sentence_extraction():
    m = metrics(SAMPLE_TEXT)
    assert m["total_revenue_inr_cr"] == 64479
    assert m["net_profit_inr_cr"] == 12650
    assert m["operating_margin_pct"] == 24.5


def test_rs_and_inr_currency_variants():
    m = metrics("Total revenue Rs. 62,963 crore; net profit INR 11,909 crore for the quarter.")
    assert m["total_revenue_inr_cr"] == 62963
    assert m["net_profit_inr_cr"] == 11909


def test_units_are_normalised_to_crore():
    assert metrics("- INR Revenue of ₹ 731,880 Mn, up 1.3% QoQ")["total_revenue_inr_cr"] == 73188  # TCS
    assert metrics("Revenue of ₹35,620 Crores, up 3.0% QoQ")["total_revenue_inr_cr"] == 35620  # HCLTech
    assert metrics("• Profit after tax grew by 20.1% y-o-y to ₹ 148.43 bn")["net_profit_inr_cr"] == 14843  # ICICI
    assert metrics("Net income for the quarter was at ₹32.0 billion ($333.9 million)")["net_profit_inr_cr"] == 3200
    assert metrics("Net profit ₹ 5,00,000 lakh")["net_profit_inr_cr"] == 5000


def test_label_synonyms():
    assert metrics("Net Income of INR 5,132 Crores, up 11.0% QoQ")["net_profit_inr_cr"] == 5132  # HCLTech
    assert metrics("Profit for the period ₹ 2,412 crore")["net_profit_inr_cr"] == 2412
    assert metrics("EBIT Margin at 18.2%")["operating_margin_pct"] == 18.2
    m = metrics("- Net Margin at 19.0%")  # TCS reports a margin, not an absolute profit
    assert m["net_margin_pct"] == 19.0
    assert m["net_profit_inr_cr"] is None


def test_usd_and_unitless_figures_are_ignored():
    m = metrics(
        "- USD Revenue of $ 7,642 Mn, up 0.2% QoQ",
        # The v1 fallback read the first bare number after a label as ₹ crore;
        # on TCS's Q4 sheet that was the full-year revenue.
        "Overview Total Revenue Operating Profit Operating Cash Flow 162,990 34,424 31,747",
        "Revenue growth: 4.2% YoY Large deals: 11.6 billion",
    )
    assert m["total_revenue_inr_cr"] is None


def test_guidance_is_not_a_result():
    assert metrics("FY27 guidance: EBIT margin expected in the range of 17.5% - 18.5%")["operating_margin_pct"] is None


def test_full_year_and_half_year_sentences_are_not_the_quarter():
    m = metrics(
        "Highest ever Annual Net Profit of ₹ 80,032 crores with a YoY growth of 12.88%",  # SBI
        "environment. Overall, for FY26, Gross Revenue at Rs. 80867.49 cr. increased by 1",  # ITC
        "H1 revenues grew to ₹ 97,454 crore",
    )
    assert m["net_profit_inr_cr"] is None
    assert m["total_revenue_inr_cr"] is None
    # A quarter named with its fiscal year is still the quarter.
    assert metrics("HCLTech delivered Q2 FY27 revenue of ₹35,620 Crores. Net income of ₹5,132 Crores")[
        "net_profit_inr_cr"
    ] == 5132


def test_segment_and_subsidiary_sentences_are_skipped():
    m = metrics(
        "➢ O2C – Revenue ₹ 201,803 crore, up 30.4% YoY",  # Reliance segment
        "✓ JPL PAT at ₹ 8,387 crore, up 13.7%",  # Reliance subsidiary
        "– Net revenue of ₹ 9.6 bn; grew 37.3% YoY",  # HDFC Bank subsidiary
    )
    assert m["total_revenue_inr_cr"] is None
    assert m["net_profit_inr_cr"] is None
    assert metrics("➢ Record quarterly PAT: ₹29,550 crore (+33.8% YoY)")["net_profit_inr_cr"] == 29550


# --- Table rows ------------------------------------------------------------------


def test_row_columns_follow_the_period_header():
    newest_first = metrics(  # Infosys
        "In ₹ crore, except per equity share data",
        "Particulars Sep 30, 2026 Sep 30, 2025 Jun 30, 2026",
        "Revenues 49,244 44,490 10.7% 48,211 2.1%",
        "Operating margin % 21.0 21.0 0.0% 21.1 -0.1%",
    )
    assert newest_first["total_revenue_inr_cr"] == 49244
    assert newest_first["operating_margin_pct"] == 21.0

    oldest_first = metrics(  # HCLTech
        "Consolidated Income Statement (Amount in ₹ Crores)",
        "30-Sep-25 30-Jun-26 30-Sep-26 30-Sep-25 30-Jun-26 30-Sep-26",
        "Revenues 31,942 34,579 35,620 100.0% 100.0% 100.0%",
        "EBIT 5,550 5,831 6,465 17.4%* 16.9%* 18.2%*",
        "Net Income 4,235 4,624 5,132 13.3%* 13.4%* 14.4%*",
    )
    assert oldest_first["total_revenue_inr_cr"] == 35620
    assert oldest_first["net_profit_inr_cr"] == 5132
    assert oldest_first["operating_margin_pct"] == 18.2  # from the "% of revenue" columns


def test_row_unit_comes_from_the_unit_line_above():
    m = metrics(
        "( ₹ million)",
        "Q2’27",
        "IT Services Revenue 246,670 0.9% 9.0%",
        "IT Services Operating Income 40,726 3.9% 6.8%",
    )
    assert m["total_revenue_inr_cr"] == 24667
    assert m["operating_margin_pct"] == 16.5  # derived: operating income / revenue


def test_usd_tables_are_skipped():
    m = metrics(
        "In US $ million, except per equity share data",
        "Particulars Sep 30, 2026 Jun 30, 2026",
        "Revenues 5,530 5,447",
    )
    assert m["total_revenue_inr_cr"] is None


def test_segment_matrix_rows_are_skipped():
    # L&T: one quarter heading over a row of per-segment values.
    m = metrics("Segment Details – Q1 FY27", "₹ Crore", "Q1 FY27", "PAT 1078 596 314 36 2496 (397) 4123")
    assert m["net_profit_inr_cr"] is None


def test_full_year_columns_are_not_read_as_the_quarter():
    m = metrics(
        "Q4 FY26 Performance Highlights",
        "₹ Crore",
        "FY25 FY26",
        "Revenue 2,55,324 2,67,021",
    )
    assert m["total_revenue_inr_cr"] is None


def test_table_beats_sentence_and_net_margin_is_derived():
    m = metrics(
        "Q2 FY27 Performance Highlights",
        "Revenue of ₹ 70,000 crore",
        "₹ Crore % of Revenue",
        "Q2 FY26 Q1 FY27 Q2 FY27 Q2 FY26 Q1 FY27 Q2 FY27",
        "Revenue 65,799 72,275 73,188 100.0 100.0 100.0",
        "Net Profit 12,904 13,849 13,884 19.6 19.2 19.0",
    )
    assert m["total_revenue_inr_cr"] == 73188
    assert m["net_margin_pct"] == 19.0  # 13,884 / 73,188


def test_full_year_tables_dated_like_quarters_are_not_the_quarter():
    # HCLTech dates its full-year columns with the year-end, which is also Q4's end.
    m = metrics(
        pages=[
            [
                "Financials for the Year ended 31-Mar-26",
                "In ₹ Crores In $M % of Revenue (Ind AS)",
                "31-Mar-25 31-Mar-26 31-Mar-25 31-Mar-26 31-Mar-25 31-Mar-26",
                "Revenues 117,055 130,144 13,840 14,664 100.0% 100.0%",
            ],
            [
                "Financials in ₹ for the Quarter ended 31-Mar-26 (Ind AS)",
                "(Amount in ₹ Crores)",
                "31-Mar-25 31-Dec-25 31-Mar-26 31-Mar-25 31-Dec-25 31-Mar-26",
                "Revenues 30,246 33,872 33,981 100.0% 100.0% 100.0%",
            ],
        ]
    )
    assert m["total_revenue_inr_cr"] == 33981


# --- Banks and conglomerates ------------------------------------------------------


def test_bank_income_statement():  # HDFC Bank
    m = metrics(
        "Income statement",
        "P&L (₹ bn) Q2 FY26 Q1 FY27 Q2 FY27 QoQ YoY",
        "Net interest income 315.5 335.3 346.2 3.2% 9.7%",
        "Net revenue 459.0 463.6 484.5 4.5% 5.6%",
        "Profit after tax 186.4 190.6 195.1 2.4% 4.7%",
        "Net interest margin of 3.16% ^",
    )
    assert m["net_interest_income_inr_cr"] == 34620
    assert m["net_profit_inr_cr"] == 19510
    assert m["net_interest_margin_pct"] == 3.16
    # A bank's "net revenue" (NII plus fees) is not revenue, so no margins are derived.
    assert m["total_revenue_inr_cr"] is None
    assert m["net_margin_pct"] is None


def test_stacked_growth_headers_and_basis_point_changes():  # SBI
    m = metrics(
        "Particulars (₹ in Crores) Quarter Ended Year Ended Growth (%)",
        "Q4FY26 Q4FY26 FY26",
        "Q4FY25 Q3FY26 Q4FY26 FY25 FY26 over over over",
        "Q3FY26 Q4FY25 FY25",
        "Net Interest Income 42,618 44,987 44,380 1,66,340 1,73,120 -1.35 4.13 4.08",
        "Net Profit 18,643 21,028 19,684 70,901 80,032 -6.39 5.58 12.88",
        "NIM (Whole Bank) (%) 2.99 2.98 2.81 3.08 2.91 -17 bps -18 bps -17 bps",
        "NIM (Domestic) (%) 3.14 3.11 2.93 3.21 3.03 -18 bps -21 bps -18 bps",
    )
    assert m["net_interest_income_inr_cr"] == 44380
    assert m["net_profit_inr_cr"] == 19684
    assert m["net_interest_margin_pct"] == 2.81


def test_footnote_marks_and_full_year_columns():  # ICICI Bank
    m = metrics(
        "Q1-o-Q1",
        "(₹ billion) FY2026 Q1-2026 Q4-2026 Q1-2027",
        "(%)",
        "Net interest income1 880.75 216.35 229.79 243.84 12.7%",
        "Profit after tax 501.47 127.68 137.02 148.05 15.9%",
        "Percent FY2026 Q1-2026 Q4-2026 Q1-2027",
        "Net interest margin1,2 4.32 4.34 4.32 4.36",
    )
    assert m["net_interest_income_inr_cr"] == 24384
    assert m["net_profit_inr_cr"] == 14805
    assert m["net_interest_margin_pct"] == 4.36


def test_translation_and_change_columns_after_the_quarters():  # Reliance
    m = metrics(
        "Consolidated Financial Results: Q2 FY27",
        "Q2 FY26 Q2 FY27",
        "₹ crore ₹ crore $ Bn %",
        "Revenue 283,548 362,268 37.8 27.8%",
        "EBITDA 50,367 62,409 6.5 23.9%",
        "PAT1 22,092 29,550 3.1 33.8%",
    )
    assert m["total_revenue_inr_cr"] == 362268
    assert m["net_profit_inr_cr"] == 29550
    assert m["operating_margin_pct"] == 17.2  # EBITDA / revenue: no EBIT reported


def test_a_subsidiarys_figures_on_a_later_page_do_not_count():  # Reliance and Jio
    group = ["Q2 FY26 Q2 FY27", "₹ crore ₹ crore $ Bn %", "Revenue 283,548 362,268 37.8 27.8%", "EBITDA 50,367 62,409 6.5 23.9%"]
    jio = ["₹ crore Q2 FY26 Q2 FY27", "EBITDA Margin (%) 51.6% 54.1%", "EBIT 12,082 14,268"]
    m = metrics(pages=[group, jio])
    assert m["operating_margin_pct"] == 17.2


def test_values_on_both_sides_of_the_label():  # L&T
    m = metrics(
        "(Amount in ₹ bn)",
        "Q4 FY25 Q4 FY26 (y-o-y) Particulars FY25 FY26 (y-o-y)",
        "744 828 11% Revenue 2557 2859 12%",
        "11.0% 10.4% EBITDA (%) 10.3% 10.2%",
        "50 53 5% Recurring PAT 146 172 18%",
        "55 53 -3% Reported PAT 150 161 7%",
    )
    assert m["total_revenue_inr_cr"] == 82800
    assert m["net_profit_inr_cr"] == 5300
    assert m["operating_margin_pct"] == 10.4


def test_the_main_table_beats_a_segment_table_with_a_preferred_label():  # L&T
    group = ["In ₹ bn", "Particulars Q1 FY26 Q1 FY27 % Var", "Revenue 637 679 7%", "Reported PAT 36 41 14%"]
    business = ["₹ Crore", "Q1 FY26 Q1 FY27", "PAT 812 900"]
    assert metrics(pages=[group, business])["net_profit_inr_cr"] == 4100


def test_gross_revenue_and_ebitda_margin():  # ITC
    m = metrics(
        "Key Financials – Standalone – Q1 FY27",
        "Rs. Cr. Q1 FY27 Q1 FY26 Goly(%) GOLY",
        "Gross Revenue 26794 20922 28.1%",
        "Net revenue 16812 19635 -14.4%",
        "EBITDA 4514 6261 -27.9%",
        "PAT 3579 4911 -27.1%",
    )
    assert m["total_revenue_inr_cr"] == 26794
    assert m["net_profit_inr_cr"] == 3579
    assert m["operating_margin_pct"] == 16.8


# --- Sanity bounds ----------------------------------------------------------------


def test_out_of_bounds_values_fall_through_to_the_next_reading():
    m = metrics(
        "₹ Crore",
        "Q1 FY27 Q2 FY27",
        "Revenue 6,57,99,000 7,31,88,000",  # a ₹ lakh table mislabelled as crore
        "Revenue of ₹ 73,188 crore",
    )
    assert m["total_revenue_inr_cr"] == 73188


def test_profit_above_revenue_is_dropped():
    m = metrics("Total revenue ₹ 5,000 crore", "Net profit ₹ 12,000 crore")
    assert m["total_revenue_inr_cr"] == 5000
    assert m["net_profit_inr_cr"] is None


def test_margin_outside_bounds_is_dropped():
    assert metrics("Operating margin 124.0%")["operating_margin_pct"] is None


# --- Documents, periods, trend ------------------------------------------------


def _fake_pdfs(monkeypatch, docs: dict[str, list[str]]):
    monkeypatch.setattr(fe, "_pdf_pages", lambda path: [docs[path]])


def test_documents_are_ordered_newest_quarter_first(monkeypatch):
    _fake_pdfs(
        monkeypatch,
        {
            "q1.pdf": ["Q1 FY27 Performance", "Total revenue ₹ 100 crore"],
            "q2.pdf": ["Q2 FY27 Performance", "Total revenue ₹ 110 crore"],
        },
    )
    out = fe.extract_financial_metrics(["q1.pdf", "q2.pdf"])
    assert [d["period"] for d in out["documents"]] == ["Q2 FY27", "Q1 FY27"]
    assert out["trend_summary"]["docs_analyzed"] == ["q2.pdf", "q1.pdf"]
    assert out["trend_summary"]["total_revenue_inr_cr"] == {"direction": "up", "pct_change": 10.0}


def test_document_without_a_quarter_goes_last(monkeypatch):
    _fake_pdfs(monkeypatch, {"x.pdf": ["Total revenue ₹ 90 crore"], "q2.pdf": ["Q2 FY27", "Total revenue ₹ 110 crore"]})
    out = fe.extract_financial_metrics(["x.pdf", "q2.pdf"])
    assert [d["period"] for d in out["documents"]] == ["Q2 FY27", None]


def test_same_quarter_twice_is_not_a_trend(monkeypatch):
    _fake_pdfs(
        monkeypatch,
        {
            "sheet.pdf": ["Q2 FY27 fact sheet", "Total revenue ₹ 110 crore"],
            "release.pdf": ["Q2 FY27 press release", "Total revenue ₹ 110 crore"],
        },
    )
    out = fe.extract_financial_metrics(["sheet.pdf", "release.pdf"])
    assert out["trend_summary"]["total_revenue_inr_cr"] == {"direction": "insufficient data"}


def test_banks_get_the_bank_metric_set(monkeypatch):
    _fake_pdfs(
        monkeypatch,
        {
            "bank.pdf": ["P&L (₹ bn) Q1 FY27 Q2 FY27", "Net interest income 335.3 346.2", "Profit after tax 190.6 195.1"],
            "q1.pdf": ["Q1 FY27 Performance", "P&L (₹ bn) Q4 FY26 Q1 FY27", "Net interest income 330.8 335.3"],
            "it.pdf": ["Q2 FY27 Performance", "Total revenue ₹ 110 crore"],
        },
    )
    out = fe.extract_financial_metrics(["bank.pdf", "q1.pdf"])
    assert out["metric_set"] == "bank"
    assert out["trend_summary"]["net_interest_income_inr_cr"] == {"direction": "up", "pct_change": 3.3}
    assert fe.extract_financial_metrics(["it.pdf"])["metric_set"] == "standard"


def test_sources_say_where_each_metric_came_from():
    out = fe.extract_from_pages([["Q2 FY27"], ["Total revenue ₹ 110 crore"]])
    assert out["sources"]["total_revenue_inr_cr"].startswith("p.2 text:")


def test_failed_pdf_is_skipped(monkeypatch):
    def boom(path):
        raise OSError("corrupt pdf")

    monkeypatch.setattr(fe, "_pdf_pages", boom)
    out = fe.extract_financial_metrics(["bad.pdf"])
    assert out["documents"] == []
    assert out["trend_summary"]["total_revenue_inr_cr"] == {"direction": "insufficient data"}


# --- Line rebuilding from a real PDF ----------------------------------------------


def _pdf(path, runs: list[tuple]) -> str:
    """A one-page PDF drawing each (x, y, text) or (x, y, text, size) run
    in the given order."""
    ops = [f"/F1 {run[3] if len(run) > 3 else 10} Tf 1 0 0 1 {run[0]} {run[1]} Tm ({run[2]}) Tj" for run in runs]
    stream = "BT " + " ".join(ops) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 400] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{obj}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    with open(path, "wb") as f:
        f.write(out)
    return str(path)


def test_labels_drawn_before_values_are_rejoined_into_rows(tmp_path):
    # Infosys's fact sheet draws every label first and every number after,
    # so plain text extraction lists them in two separate blocks.
    path = _pdf(
        tmp_path / "sheet.pdf",
        [
            (50, 350, "Rs crore"),
            (50, 330, "Particulars"),
            (50, 310, "Revenues"),
            (50, 290, "Net profit"),
            (300, 330, "Sep 30, 2026"),
            (400, 330, "Jun 30, 2026"),
            (300, 310, "49,244"),
            (400, 310, "48,211"),
            (300, 290, "7,823"),
            (400, 290, "7,769"),
        ],
    )
    assert fe._pdf_pages(path)[0] == [
        "Rs crore",
        "Particulars Sep 30, 2026 Jun 30, 2026",
        "Revenues 49,244 48,211",
        "Net profit 7,823 7,769",
    ]
    doc = fe.extract_financial_metrics([path])["documents"][0]
    assert doc["period"] == "Q2 FY27"
    assert doc["metrics"]["total_revenue_inr_cr"] == 49244
    assert doc["metrics"]["net_profit_inr_cr"] == 7823


def test_text_beside_a_table_becomes_its_own_line(tmp_path):
    # Reliance sets bullets on the table's lines; its slide numbers sit off the page.
    path = _pdf(
        tmp_path / "deck.pdf",
        [
            (50, 350, "Q2 FY26"),
            (150, 350, "Q2 FY27"),
            (50, 330, "EBITDA"),
            (150, 330, "50,367"),
            (250, 330, "62,409"),
            (400, 330, "growth in Digital Services"),
            (-40, 330, "158"),
            # L&T: values on both sides of the label stay one row.
            (50, 310, "744"),
            (100, 310, "828"),
            (200, 310, "Revenue"),
            (350, 310, "2557"),
        ],
    )
    assert fe._pdf_pages(path)[0] == [
        "Q2 FY26 Q2 FY27",
        "EBITDA 50,367 62,409",
        "744 828 Revenue 2557",
        "growth in Digital Services",
    ]


def test_column_headers_set_on_two_lines_are_joined(tmp_path):
    # ICICI Bank: "Q2-" over "2026", with the full-year column between the two lines.
    path = _pdf(
        tmp_path / "deck.pdf",
        [
            (200, 350, "Q2-"),
            (300, 350, "Q1-"),
            (400, 350, "Q2-"),
            (50, 342, "(Rs billion)"),
            (120, 342, "FY2026"),
            (200, 334, "2026"),
            (300, 334, "2027"),
            (400, 334, "2027"),
            (50, 310, "NII"),
            (120, 310, "880.75"),
            (200, 310, "215.29"),
            (300, 310, "243.84"),
            (400, 310, "253.39"),
        ],
    )
    assert fe._pdf_pages(path)[0] == [
        "FY2026 Q2-2026 Q1-2027 Q2-2027",
        "(Rs billion)",
        "NII 880.75 215.29 243.84 253.39",
    ]
    assert fe.extract_financial_metrics([path])["documents"][0]["metrics"]["net_interest_income_inr_cr"] == 25339


def test_a_page_titled_after_a_subsidiary_gives_no_lines(tmp_path):
    def page(title):
        # SBI's navigation bar names "Subsidiaries" in small type on every page.
        runs = [(50, 370, title, 20), (400, 390, "Subsidiaries,", 8), (50, 330, "Q4 FY25 Q4 FY26"), (50, 310, "PAT 1,916 2,167")]
        return _pdf(tmp_path / f"{len(title)}.pdf", runs)

    assert fe._pdf_pages(page("SBI and its subsidiaries"))[0] == []
    assert "PAT 1,916 2,167" in fe._pdf_pages(page("Financials at a glance"))[0]
