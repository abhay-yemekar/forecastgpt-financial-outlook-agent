from app.tools.financial_extractor import _to_float, compute_trend

_seq = iter(range(1000))


def doc(**metrics):
    return {"path": f"doc_{next(_seq)}.pdf", "metrics": metrics}


def test_up_direction():
    docs = [doc(total_revenue_inr_cr="110"), doc(total_revenue_inr_cr="100")]
    trend = compute_trend(docs)
    assert trend["total_revenue_inr_cr"] == {"direction": "up", "pct_change": 10.0}


def test_down_direction():
    docs = [doc(net_profit_inr_cr="100"), doc(net_profit_inr_cr="150")]
    trend = compute_trend(docs)
    assert trend["net_profit_inr_cr"]["direction"] == "down"
    assert trend["net_profit_inr_cr"]["pct_change"] == -33.3


def test_flat_within_threshold():
    docs = [doc(operating_margin_pct="24.6"), doc(operating_margin_pct="24.5")]
    trend = compute_trend(docs)
    assert trend["operating_margin_pct"]["direction"] == "flat"


def test_small_change_is_flat():
    # ~0.4% is below the 0.5% flat threshold.
    docs = [doc(operating_margin_pct="100.4"), doc(operating_margin_pct="100")]
    trend = compute_trend(docs)
    assert trend["operating_margin_pct"]["direction"] == "flat"


def test_insufficient_data_single_value():
    docs = [doc(total_revenue_inr_cr="100"), doc(total_revenue_inr_cr=None)]
    trend = compute_trend(docs)
    assert trend["total_revenue_inr_cr"] == {"direction": "insufficient data"}


def test_insufficient_data_zero_previous():
    docs = [doc(total_revenue_inr_cr="100"), doc(total_revenue_inr_cr="0")]
    trend = compute_trend(docs)
    assert trend["total_revenue_inr_cr"] == {"direction": "insufficient data"}


def test_skips_docs_missing_metric():
    # Newest doc lacks revenue; comparison falls back to the next two that have it.
    docs = [
        doc(operating_margin_pct="25"),
        doc(total_revenue_inr_cr="120"),
        doc(total_revenue_inr_cr="100"),
    ]
    trend = compute_trend(docs)
    assert trend["total_revenue_inr_cr"] == {"direction": "up", "pct_change": 20.0}


def test_comma_thousands_parsed():
    docs = [doc(total_revenue_inr_cr="64,479"), doc(total_revenue_inr_cr="62,000")]
    trend = compute_trend(docs)
    assert trend["total_revenue_inr_cr"]["direction"] == "up"
    assert trend["total_revenue_inr_cr"]["pct_change"] == 4.0


def test_negative_profit_change():
    # Profit swinging deeper into loss is "down".
    docs = [doc(net_profit_inr_cr="-100"), doc(net_profit_inr_cr="-50")]
    trend = compute_trend(docs)
    assert trend["net_profit_inr_cr"]["direction"] == "down"
    assert trend["net_profit_inr_cr"]["pct_change"] == -100.0


def test_to_float_variants():
    assert _to_float("1,234.5") == 1234.5
    assert _to_float("42") == 42.0
    assert _to_float(None) is None
    assert _to_float("abc") is None
