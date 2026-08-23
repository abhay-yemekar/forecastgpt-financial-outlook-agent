import json

from app.agent import ForecastAgent


def test_run_includes_financial_metrics_and_sources(monkeypatch):
    agent = ForecastAgent()
    canned = json.dumps({"company": "TCS", "confidence": {"level": "high", "reasons": ["ok"]}})

    class _FakeLLM:
        def invoke(self, messages):
            class _Resp:
                content = canned

            return _Resp()

    agent.llm = _FakeLLM()
    monkeypatch.setattr("app.agent.fetch_stock_price", lambda symbol: {"symbol": "TCS.NS", "price_inr": 1.0})

    out = agent.run(
        "query",
        financial_pdfs=[],
        transcripts=[],
        company_name="Tata Consultancy Services",
        symbol="TCS",
    )

    # Raw extractor output is exposed for charting, alongside the LLM view.
    fm = out["financial_metrics"]
    assert fm["documents"] == []
    assert fm["trend_summary"]["docs_analyzed"] == []
    assert fm["trend_summary"]["total_revenue_inr_cr"] == {"direction": "insufficient data"}
    assert out["sources"] == {"financial_docs": [], "transcripts": []}
    assert out["market_context"] == {"symbol": "TCS.NS", "price_inr": 1.0}
    assert out["confidence"]["level"] == "high"
