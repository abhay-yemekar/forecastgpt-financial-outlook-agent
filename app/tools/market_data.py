import requests

from app.utils.logger import get_logger

log = get_logger("MarketDataTool")

# The old Yahoo v7 quote endpoint this tool used to call now returns 401
# without a session crumb. The v8 chart endpoint still works anonymously,
# but only when the request carries a browser-like User-Agent.
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

SYMBOL = "TCS.NS"


def fetch_tcs_stock_price():
    """Optional market context. If it fails, returns an empty dict."""
    try:
        resp = requests.get(
            YAHOO_CHART_URL.format(symbol=SYMBOL),
            params={"interval": "1d", "range": "5d"},
            headers={"User-Agent": BROWSER_UA},
            timeout=10,
        )
        resp.raise_for_status()
        price = resp.json()["chart"]["result"][0]["meta"]["regularMarketPrice"]
        if price is None:
            log.warning(f"Yahoo chart response had no regularMarketPrice for {SYMBOL}.")
            return {}
        log.info(f"Fetched {SYMBOL} price {price} via Yahoo chart API.")
        return {"symbol": SYMBOL, "price_inr": price}
    except Exception as e:
        log.warning(f"Market data fetch failed: {e}")
        return {}
