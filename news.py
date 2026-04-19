from datetime import datetime, timezone, timedelta
from urllib.parse import quote
import feedparser


SHARED_KEYWORDS = [
    "FOMC", "연준", "미국 금리", "미국 CPI", "미국 고용",
    "환율", "원달러 환율", "국채가",
    "유가", "반도체",
    "트럼프",
    "전쟁", "종전", "해협",
]

# S&P500 / 나스닥100 시가총액 상위 기업 (둘 다 포함된 이름은 한 번만)
COMPANY_KEYWORDS = [
    "애플", "마이크로소프트", "엔비디아", "구글", "아마존", "메타", "테슬라", "브로드컴",
    "코스트코", "넷플릭스", "AMD", "어도비", "펩시코", "퀄컴",
    "버크셔해서웨이", "JP모건", "엑슨모빌", "일라이릴리", "비자", "월마트", "유나이티드헬스",
]

TICKER_KEYWORDS = {
    "360750": ["S&P 500", "미국 증시"] + SHARED_KEYWORDS + COMPANY_KEYWORDS,
    "133690": ["나스닥", "빅테크"] + SHARED_KEYWORDS + COMPANY_KEYWORDS,
}


_RSS_CACHE: dict = {}


def _rss_url(query: str) -> str:
    return f"https://news.google.com/rss/search?q={quote(query)}&hl=ko&gl=KR&ceid=KR:ko"


def _fetch_entries(kw: str, per_query: int):
    if kw in _RSS_CACHE:
        return _RSS_CACHE[kw]
    try:
        d = feedparser.parse(_rss_url(kw))
        entries = list(d.entries[:per_query])
    except Exception:
        entries = []
    _RSS_CACHE[kw] = entries
    return entries


def fetch_headlines(keywords, max_age_hours: int = 48, per_query: int = 3):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    items = []
    seen = set()
    for kw in keywords:
        for e in _fetch_entries(kw, per_query):
            title = (e.get("title") or "").strip()
            if not title or title in seen:
                continue
            ts = e.get("published_parsed")
            pub = datetime(*ts[:6], tzinfo=timezone.utc) if ts else None
            if pub and pub < cutoff:
                continue
            seen.add(title)
            items.append({"title": title, "pub": pub, "kw": kw})
    items.sort(
        key=lambda x: x["pub"] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return items


def get_news(ticker: str, limit: int = 10, max_age_hours: int = 48):
    kws = TICKER_KEYWORDS.get(ticker, SHARED_KEYWORDS)
    return fetch_headlines(kws, max_age_hours=max_age_hours)[:limit]
