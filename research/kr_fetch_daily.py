"""자비스4 명부 2,272종목의 일봉을 받아 둔다 (2026-08-07).

한국 배점을 미국과 같은 잣대(기간을 반으로 갈라 양쪽 다 이겼나)로 다시 재기 위한
바탕 자료다. 받아 둔 시세는 `research/_data/`에 두고 저장소에는 올리지 않는다
(.gitignore에 이미 있다) — 다시 받으면 되고 용량이 크다.

**중간에 끊겨도 다시 돌리면 이어서 받는다.** 이미 받은 종목 파일은 건너뛴다.

쓰는 법:  python research/kr_fetch_daily.py
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "research" / "_data" / "kr_daily"
ROSTER = ROOT / "data" / "kr_roster.json"

# 네이버 일봉. count는 한 번에 받을 수 있는 최대치가 3,000줄이다(약 12년).
URL = ("https://fchart.stock.naver.com/sise.nhn"
       "?timeframe=day&count=3000&requestType=0&symbol={code}")
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Referer": "https://finance.naver.com/",
}
ITEM = re.compile(r'data="([^"]+)"')


def fetch(code: str) -> int:
    """한 종목의 일봉을 받아 CSV로 남긴다. 줄 수를 돌려준다."""
    target = OUT / f"{code}.csv"
    if target.exists():
        return -1  # 이미 받아 둠
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(URL.format(code=code), headers=HEADERS)
            with urllib.request.urlopen(request, timeout=20) as response:
                text = response.read().decode("euc-kr", errors="replace")
            break
        except Exception as exc:  # 네트워크는 가끔 튕긴다 — 세 번까지 다시 시도
            last_error = exc
            time.sleep(0.6 * (attempt + 1))
    else:
        raise RuntimeError(f"{code}: {last_error}")
    rows = []
    for raw in ITEM.findall(text):
        parts = raw.split("|")
        if len(parts) < 6 or not parts[0].isdigit():
            continue
        rows.append(",".join(parts[:6]))
    if not rows:
        return 0
    target.write_text("date,open,high,low,close,volume\n" + "\n".join(rows) + "\n",
                      encoding="utf-8")
    return len(rows)


def main() -> None:
    codes = sorted(json.loads(ROSTER.read_text(encoding="utf-8"))["stocks"])
    OUT.mkdir(parents=True, exist_ok=True)
    done = skipped = empty = failed = 0
    started = time.time()
    # 일꾼 8개 — 네이버에 예의를 지키는 선이다. 앱이 평소 쓰는 수(12)보다 적게 둔다.
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(fetch, code): code for code in codes}
        for index, future in enumerate(as_completed(futures), 1):
            code = futures[future]
            try:
                count = future.result()
            except Exception as exc:
                failed += 1
                print(f"  실패 {code}: {exc}", file=sys.stderr)
                continue
            if count < 0:
                skipped += 1
            elif count == 0:
                empty += 1
            else:
                done += 1
            if index % 200 == 0:
                print(f"{index}/{len(codes)}  받음 {done} · 건너뜀 {skipped} · "
                      f"빈것 {empty} · 실패 {failed}  ({time.time() - started:.0f}초)",
                      flush=True)
    print(f"끝. 받음 {done} · 건너뜀 {skipped} · 빈것 {empty} · 실패 {failed} "
          f"({time.time() - started:.0f}초)")


if __name__ == "__main__":
    main()
