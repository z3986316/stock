import json
import math
import os
import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd

from news import get_news
from price import (
    build_future_points,
    build_past_rows,
    fetch_history,
    fmt_date_short,
    forecast,
    generate_observations,
    get_name,
    trend_label,
)
from realtime import get_realtime


HISTORY_DAYS_FOR_CHART = 180


def iso(d) -> str:
    if isinstance(d, datetime):
        return d.date().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    return str(d)


def build_history(df: pd.DataFrame, days: int) -> list:
    tail = df.tail(days)
    out = []
    for ts, row in tail.iterrows():
        out.append({"date": ts.date().isoformat(), "close": int(row["종가"])})
    return out


def build_past_section(past_rows: list) -> list:
    out = []
    for label, d, p, prev_p in past_rows:
        entry = {"label": label, "date": None, "date_short": None, "close": p, "prev": prev_p}
        if d is not None:
            entry["date"] = d.isoformat()
            entry["date_short"] = fmt_date_short(d)
        if p is not None and prev_p:
            entry["change_pct"] = (p - prev_p) / prev_p * 100
        out.append(entry)
    return out


def build_forecast_section(fut_rows, future_points, latest_price) -> list:
    out = []
    for (label, h, center, low, high), (_, fd, _) in zip(fut_rows, future_points):
        low_pct = (low - latest_price) / latest_price * 100
        high_pct = (high - latest_price) / latest_price * 100
        center_pct = (center - latest_price) / latest_price * 100
        out.append({
            "label": label,
            "date": fd.isoformat(),
            "date_short": fmt_date_short(fd),
            "horizon_days": h,
            "low": int(round(low)),
            "high": int(round(high)),
            "center": int(round(center)),
            "low_pct": low_pct,
            "high_pct": high_pct,
            "center_pct": center_pct,
        })
    return out


def build_ticker(ticker: str) -> dict:
    name = get_name(ticker)
    df = fetch_history(ticker)
    if df.empty:
        return {"ticker": ticker, "name": name, "error": "데이터 없음"}

    latest_date = df.index[-1].date()
    latest_price = int(df.iloc[-1]["종가"])

    past_rows = build_past_rows(df, latest_date, latest_price)
    future_points = build_future_points(latest_date)
    horizons = [(lab, h) for lab, _, h in future_points]
    mu, sigma, fut_rows = forecast(df, horizons=horizons)

    rt = get_realtime(ticker)
    realtime = None
    if rt and rt["price"] != latest_price and latest_price:
        pct_rt = (rt["price"] - latest_price) / latest_price * 100
        realtime = {
            "price": rt["price"],
            "pct": pct_rt,
            "market_open": rt["market_open"],
            "traded_at": rt["traded_at"],
        }

    news = []
    try:
        for item in get_news(ticker, limit=8):
            pub = item["pub"]
            news.append({
                "at": pub.astimezone().strftime("%m-%d %H:%M") if pub else "",
                "kw": item["kw"],
                "title": item["title"],
                "link": item.get("link", ""),
            })
    except Exception as e:
        news = [{"at": "", "kw": "error", "title": f"뉴스 로드 실패: {e}", "link": ""}]

    return {
        "ticker": ticker,
        "name": name,
        "latest_date": latest_date.isoformat(),
        "latest_price": latest_price,
        "history": build_history(df, HISTORY_DAYS_FOR_CHART),
        "past": build_past_section(past_rows),
        "forecast": build_forecast_section(fut_rows, future_points, latest_price),
        "observations": generate_observations(df, latest_price, mu, sigma),
        "realtime": realtime,
        "news": news,
    }


def main() -> None:
    tickers = sys.argv[1:] or ["360750", "133690"]
    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    payload = {
        "generated_at": now_kst.strftime("%Y-%m-%d %H:%M KST"),
        "tickers": [build_ticker(t) for t in tickers],
    }
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "data.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"wrote {os.path.join(out_dir, 'data.json')}")


if __name__ == "__main__":
    main()
