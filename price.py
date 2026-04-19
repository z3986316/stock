import sys
import math
from datetime import date, timedelta
import pandas as pd
from pykrx import stock

from news import get_news
from realtime import get_realtime


KNOWN_NAMES = {
    "360750": "TIGER 미국S&P500",
    "133690": "TIGER 미국나스닥100",
}


def get_name(ticker: str) -> str:
    if ticker in KNOWN_NAMES:
        return KNOWN_NAMES[ticker]
    try:
        name = stock.get_market_ticker_name(ticker)
        if isinstance(name, str) and name:
            return name
    except Exception:
        pass
    return ticker


def fetch_history(ticker: str, days: int = 450) -> pd.DataFrame:
    today = date.today()
    start = (today - timedelta(days=days)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")
    return stock.get_market_ohlcv(start, end, ticker)


def price_on_or_before(df: pd.DataFrame, target: date):
    mask = df.index.date <= target
    if not mask.any():
        return None
    sub = df.loc[mask]
    return sub.index[-1].date(), int(sub.iloc[-1]["종가"])


def pct(old: float, new: float) -> str:
    if old == 0:
        return "N/A"
    return f"{(new - old) / old * 100:+.2f}%"


def fmt(n: float) -> str:
    return f"{int(round(n)):,}원"


WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]


def fmt_date_short(d: date) -> str:
    return f"{d.month}/{d.day} {WEEKDAY_KO[d.weekday()]}"


def next_business_days(start: date, n: int) -> list:
    out = []
    d = start
    while len(out) < n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            out.append(d)
    return out


def nearest_bday(d: date) -> date:
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def trading_days_between(start: date, end: date) -> int:
    count = 0
    d = start
    while d < end:
        d += timedelta(days=1)
        if d.weekday() < 5:
            count += 1
    return count


def trend_label(price: float, ma5: float, ma20: float, ma60: float) -> str:
    if price > ma5 > ma20 > ma60:
        return "강한 상승 추세 (정배열)"
    if price < ma5 < ma20 < ma60:
        return "강한 하락 추세 (역배열)"
    above = sum([price > ma5, price > ma20, price > ma60])
    if above == 3:
        return "상승 우위"
    if above == 0:
        return "하락 우위"
    return "혼조"


def forecast(
    df: pd.DataFrame,
    horizons=(("익일", 1), ("차주 (+5거래일)", 5)),
    window: int = 120,
):
    closes = df["종가"].astype(float)
    recent = closes.iloc[-min(window, len(closes)):]
    log_ret = (recent / recent.shift(1)).apply(
        lambda x: math.log(x) if x and x > 0 else float("nan")
    ).dropna()
    mu = float(log_ret.mean())
    sigma = float(log_ret.std())
    current = float(closes.iloc[-1])
    rows = []
    for label, h in horizons:
        drift = mu * h
        vol = sigma * math.sqrt(h)
        center = current * math.exp(drift)
        low = current * math.exp(drift - 1.96 * vol)
        high = current * math.exp(drift + 1.96 * vol)
        rows.append((label, h, center, low, high))
    return mu, sigma, rows


def build_past_rows(df: pd.DataFrame, latest_date: date, latest_price: int):
    rows = []
    for label, cal_days in [("1년전", 365), ("6개월전", 182), ("1달전", 30)]:
        r = price_on_or_before(df, latest_date - timedelta(days=cal_days))
        if r is None:
            rows.append((label, None, None, None))
        else:
            d, p = r
            rows.append((label, d, p, None))

    for n in range(7, 0, -1):
        if n + 1 > len(df):
            rows.append((f"{n}일전", None, None, None))
            continue
        d = df.index[-(n + 1)].date()
        p = int(df.iloc[-(n + 1)]["종가"])
        rows.append((f"{n}일전", d, p, None))

    rows.append(("오늘", latest_date, latest_price, None))

    for i in range(max(0, len(rows) - 3), len(rows)):
        if i == 0:
            continue
        prev_p = rows[i - 1][2]
        if prev_p is not None and rows[i][2] is not None:
            rows[i] = (rows[i][0], rows[i][1], rows[i][2], prev_p)
    return rows


def build_future_points(latest_date: date):
    specs = [
        ("1일후",   "bday", 1),
        ("2일후",   "bday", 2),
        ("3일후",   "bday", 3),
        ("7일후",   "bday", 7),
        ("1달후",   "cal",  30),
        ("6개월후", "cal",  182),
        ("1년후",   "cal",  365),
    ]
    out = []
    for label, mode, n in specs:
        if mode == "bday":
            d = next_business_days(latest_date, n)[-1]
            h = n
        else:
            d = nearest_bday(latest_date + timedelta(days=n))
            h = trading_days_between(latest_date, d)
        out.append((label, d, h))
    return out


def generate_observations(df: pd.DataFrame, latest_price: int, mu: float, sigma: float):
    out = []
    closes = df["종가"].astype(float)

    # 연속 상승/하락 스트릭
    tail = closes.iloc[-11:].tolist()
    streak = 0
    direction = None
    for i in range(len(tail) - 1, 0, -1):
        diff = tail[i] - tail[i - 1]
        d = "up" if diff > 0 else ("down" if diff < 0 else None)
        if direction is None:
            direction = d
            if d is not None:
                streak = 1
        elif d == direction:
            streak += 1
        else:
            break
    if streak >= 2 and direction:
        start = tail[-streak - 1]
        cum = (latest_price - start) / start * 100
        word = "상승" if direction == "up" else "하락"
        out.append(f"{streak}거래일 연속 {word}, 누적 {cum:+.2f}%")

    # MA 정렬
    ma5 = closes.rolling(5).mean().iloc[-1]
    ma20 = closes.rolling(20).mean().iloc[-1]
    ma60 = closes.rolling(60).mean().iloc[-1]
    if not any(pd.isna(x) for x in [ma5, ma20, ma60]):
        trend = trend_label(latest_price, ma5, ma20, ma60)
        out.append(
            f"추세: {trend} (MA5 {fmt(ma5)} / MA20 {fmt(ma20)} / MA60 {fmt(ma60)})"
        )

    # 52주 고/저
    window_252 = closes.tail(252)
    hi = window_252.max()
    lo = window_252.min()
    hi_pct = (latest_price - hi) / hi * 100
    lo_pct = (latest_price - lo) / lo * 100
    out.append(
        f"52주 최고 {fmt(hi)} 대비 {hi_pct:+.2f}%, 최저 {fmt(lo)} 대비 {lo_pct:+.2f}%"
    )

    # 변동성
    ann_vol = sigma * math.sqrt(252) * 100
    level = "낮음" if ann_vol < 15 else ("중간" if ann_vol < 25 else "높음")
    out.append(
        f"연율 변동성 {ann_vol:.1f}% ({level}) - 장기 예상(1달 이상) 범위는 폭이 매우 넓어 참고용"
    )

    # 연율 drift
    ann_drift = mu * 252 * 100
    out.append(
        f"최근 120일 평균 추세 연율 {ann_drift:+.1f}% - 미래 중심값은 이 추세 연장 가정"
    )

    return out


def analyze(ticker: str) -> None:
    name = get_name(ticker)
    df = fetch_history(ticker)
    if df.empty:
        print(f"\n[{ticker}] {name} - 데이터 없음")
        return

    latest_date = df.index[-1].date()
    latest_price = int(df.iloc[-1]["종가"])

    header = f"{ticker} {name}" if name != ticker else ticker
    print(f"\n{header} 최근 흐름")

    # 과거 출력
    past_rows = build_past_rows(df, latest_date, latest_price)
    for label, d, p, prev_p in past_rows:
        if p is None:
            print(f"  - {label}: 데이터 없음")
            continue
        date_str = fmt_date_short(d)
        if prev_p is not None:
            chg = (p - prev_p) / prev_p * 100 if prev_p else 0
            print(f"  - {label} ({date_str}): {prev_p:,} → {p:,}원 ({chg:+.2f}%)")
        else:
            print(f"  - {label} ({date_str}): {p:,}원")

    # 실시간 (장중이거나 종가 미반영일 때만)
    rt = get_realtime(ticker)
    if rt and rt["price"] != latest_price:
        status = "장중" if rt["market_open"] else "장마감"
        pct_rt = (rt["price"] - latest_price) / latest_price * 100 if latest_price else 0
        print(
            f"  - 실시간 ({status}): {latest_price:,} → {rt['price']:,}원 "
            f"({pct_rt:+.2f}%)  [{rt['traded_at']}]"
        )

    # 미래 예상
    future_points = build_future_points(latest_date)
    horizons = [(lab, h) for lab, _, h in future_points]
    mu, sigma, fut_rows = forecast(df, horizons=horizons)
    for (label, h, center, low, high), (_, fd, _) in zip(fut_rows, future_points):
        low_pct = (low - latest_price) / latest_price * 100
        high_pct = (high - latest_price) / latest_price * 100
        date_str = fmt_date_short(fd)
        print(
            f"  - {label} ({date_str}): "
            f"{fmt(low)} ~ {fmt(high)} "
            f"(현재가 대비 {low_pct:+.2f}% ~ {high_pct:+.2f}%), "
            f"중심 {fmt(center)}"
        )

    # 특이사항
    print(f"\n  (특이사항)")
    for o in generate_observations(df, latest_price, mu, sigma):
        print(f"  - {o}")

    # 관련 뉴스 (참고용)
    print(f"\n  [관련 뉴스 (최근 48시간, 참고용)]")
    try:
        news_items = get_news(ticker, limit=8)
    except Exception as e:
        print(f"  뉴스 로드 실패: {e}")
        news_items = []
    if not news_items:
        print("  관련 뉴스 없음")
    else:
        for item in news_items:
            pub = item["pub"]
            when = pub.astimezone().strftime("%m-%d %H:%M") if pub else "  ?  "
            print(f"  {when}  [{item['kw']}]  {item['title']}")


if __name__ == "__main__":
    tickers = sys.argv[1:] or ["360750", "133690"]
    for t in tickers:
        analyze(t)
