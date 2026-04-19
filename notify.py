import os
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
        json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
        timeout=30,
    )
    resp.raise_for_status()


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


def strip_news_sections(text: str) -> str:
    out: list[str] = []
    skipping = False
    for line in text.splitlines(keepends=True):
        if "[관련 뉴스" in line:
            skipping = True
            continue
        if skipping:
            # 다음 종목 헤더 (공백 없이 시작하는 줄) 만나면 뉴스 블록 끝
            if line.strip() and not line.startswith(" "):
                skipping = False
                out.append(line)
            continue
        out.append(line)
    return "".join(out).rstrip() + "\n"


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
    return strip_news_sections(result.stdout)


def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    tickers = sys.argv[1:] or ["360750", "133690"]

    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    header = f"[주식 리포트] {now_kst.strftime('%Y-%m-%d %H:%M KST')}\n대상: {', '.join(tickers)}\n"

    body = run_analysis(tickers)
    full = header + "\n" + body

    for chunk in split_by_section(full):
        send_chunk(token, chat_id, chunk)
        time.sleep(0.5)  # avoid Telegram rate limit


if __name__ == "__main__":
    main()
