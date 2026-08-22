from unittest.mock import patch

from app.tools import market_data as md


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _chart_payload(price):
    return {"chart": {"result": [{"meta": {"regularMarketPrice": price}}]}}


def test_returns_price_from_chart_meta():
    with patch.object(md.requests, "get", return_value=_FakeResp(_chart_payload(2302.0))) as mock_get:
        out = md.fetch_tcs_stock_price()
    assert out == {"symbol": "TCS.NS", "price_inr": 2302.0}
    assert "TCS.NS" in mock_get.call_args.args[0]
    # The v8 endpoint only answers browser-like User-Agents.
    assert "Mozilla" in mock_get.call_args.kwargs["headers"]["User-Agent"]


def test_missing_price_returns_empty():
    with patch.object(md.requests, "get", return_value=_FakeResp(_chart_payload(None))):
        assert md.fetch_tcs_stock_price() == {}


def test_http_error_returns_empty():
    class _Boom:
        def raise_for_status(self):
            raise md.requests.HTTPError("401")

        def json(self):
            return {}

    with patch.object(md.requests, "get", return_value=_Boom()):
        assert md.fetch_tcs_stock_price() == {}
