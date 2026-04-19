import html
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests


TELEGRAM_MAX = 4000  # safety margin below 4096


def send_chunk(token: str, chat_id: str, text: str) -> None:
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
            "parse_mode": "HTML",
        },
        timeout=30,
    )
    resp.raise_for_status()


def format_for_telegram(text: str) -> str:
    # HTML-escape first so user content cannot inject tags; then wrap key lines in <b>.
    escaped = html.escape(text)
    patterns = [
        r"^([^\s].+ 최근 흐름)$",            # ticker header
        r"^([ \t]*-[ \t]*오늘[ \t].*)$",     # today row
        r"^([ \t]*-[ \t]*실시간[ \t].*)$",   # realtime row
        r"^([ \t]*\(특이사항\))$",           # observations header
        r"^([ \t]*\[관련 뉴스[^\]]*\])$",    # news header
    ]
    for pat in patterns:
        escaped = re.sub(pat, r"<b>\1</b>", escaped, flags=re.MULTILINE)
    return escaped


def split_by_section(text: str) -> list[str]:
    chunks: list[str] = []
    buf: list[str] = []
    size = 0
    for line in text.splitlines(keepends=True):
        if size + len(line) > TELEGRAM_MAX and buf:
            chunks.append("".join(buf))
            buf, size = [], 0
        buf.append(line)
        size += len(line)
    if buf:
        chunks.append("".join(buf))
    return chunks


def run_analysis(tickers: list[str]) -> str:
    cmd = [sys.executable, "price.py", *tickers]
    result = subprocess.run(
        cmd,
        cwd=os.path.dirname(os.path.abspath(__file__)),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return f"[분석 실패] exit={result.returncode}\n\nstderr:\n{result.stderr}"
    return result.stdout


def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    tickers = sys.argv[1:] or ["360750", "133690"]

    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    header = f"[주식 리포트] {now_kst.strftime('%Y-%m-%d %H:%M KST')}\n대상: {', '.join(tickers)}\n"

    body = run_analysis(tickers)
    full = format_for_telegram(header + "\n" + body)

    for chunk in split_by_section(full):
        send_chunk(token, chat_id, chunk)
        time.sleep(0.5)  # avoid Telegram rate limit


if __name__ == "__main__":
    main()
