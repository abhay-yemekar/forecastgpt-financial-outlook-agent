import requests

from app.utils.logger import get_logger

log = get_logger("MarketDataTool")

# The old Yahoo v7 quote endpoint this tool used to call now returns 401
# without a session crumb. The v8 chart endpoint still works anonymously,
# but only when the request carries a browser-like User-Agent.
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def fetch_stock_price(symbol: str) -> dict:
    """Latest NSE quote for `symbol` (e.g. "TCS" -> "TCS.NS"). Best-effort:
    on any failure returns an empty dict."""
    yahoo_symbol = symbol if "." in symbol else f"{symbol}.NS"
    try:
        resp = requests.get(
            YAHOO_CHART_URL.format(symbol=yahoo_symbol),
            params={"interval": "1d", "range": "5d"},
            headers={"User-Agent": BROWSER_UA},
            timeout=10,
        )
        resp.raise_for_status()
        price = resp.json()["chart"]["result"][0]["meta"]["regularMarketPrice"]
        if price is None:
            log.warning(f"Yahoo chart response had no regularMarketPrice for {yahoo_symbol}.")
            return {}
        log.info(f"Fetched {yahoo_symbol} price {price} via Yahoo chart API.")
        return {"symbol": yahoo_symbol, "price_inr": price}
    except Exception as e:
        log.warning(f"Market data fetch failed for {yahoo_symbol}: {e}")
        return {}
