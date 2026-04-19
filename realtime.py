import json
import urllib.request


def get_realtime(ticker: str, timeout: int = 5):
    url = f"https://m.stock.naver.com/api/stock/{ticker}/basic"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read())
    except Exception:
        return None
    close_str = (d.get("closePrice") or "").replace(",", "")
    if not close_str.isdigit():
        return None
    return {
        "price": int(close_str),
        "market_open": d.get("marketStatus") == "OPEN",
        "traded_at": d.get("localTradedAt"),
        "status_raw": d.get("marketStatus"),
    }
