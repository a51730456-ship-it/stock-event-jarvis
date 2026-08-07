"""코스피 일봉을 받아 둔다. 급락 그물의 '시장이 얼마나 빠졌나'를 재는 데 쓴다."""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from kr_fetch_daily import OUT, fetch  # noqa: E402

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for symbol in ("KOSPI", "KOSDAQ"):
        count = fetch(symbol)
        print(f"{symbol}: {count}줄")
