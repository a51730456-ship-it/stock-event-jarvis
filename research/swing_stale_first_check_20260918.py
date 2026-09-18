# -*- coding: utf-8 -*-
"""화면을 켜 둔 채 30분이 지난 뒤 상승장을 누르면 얼마나 걸리나 (2026-09-18).

상하님 — *"30분 지난 뒤 느린 것도 고쳐라."*

**30분을 실제로 기다리지 않는다.** 앱이 받아 둔 주가에 적힌 '받은 시각'을 40분
뒤로 밀고, 파일로 남긴 공책도 안 쓰게 한다 — 앱이 보기에는 미국장이 도는 밤에
40분이 지난 것과 똑같다(장중에는 파일 공책 수명이 3분이라 그것도 식는다).

    $ python research/swing_stale_first_check_20260918.py

노트북 실측 (2026-09-18)
    고치기 전   7.84초 (CPU 9.28초) · 40분 전과 목록이 **똑같다**
    고친 뒤     0.00초              · 같은 목록, 새로 받는 일은 뒤 일꾼이 한다
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import jarvis3_data as j3  # noqa: E402


def age_the_notebook(seconds: float) -> None:
    """공책에 적힌 '받은 시각'을 그만큼 뒤로 민다."""
    with j3._CACHE_LOCK:
        for entry in j3._CACHE.values():
            if isinstance(entry, dict) and "at" in entry:
                entry["at"] = float(entry["at"]) - seconds


def timed(label, fn):
    wall0, cpu0 = time.perf_counter(), time.process_time()
    out = fn()
    print(f"  {label:<40} 벽시계 {time.perf_counter() - wall0:6.2f}s"
          f"  CPU {time.process_time() - cpu0:6.2f}s")
    return out


def tickers(scan, key):
    return [row.get("ticker") for row in (scan.get(key) or [])]


def main():
    print("== 준비 — 화면을 켠 것처럼 한 번 다 받아 둔다 ==")
    timed("테마 순위(화면 그릴 때)", j3.get_theme_rankings)
    before = timed("상승장 한 벌", lambda: j3.breakout_scan(persist=False))
    print(f"     정식 {len(before.get('primary_rows') or [])}"
          f" · 관찰 {len(before.get('watch_rows') or [])}"
          f" · 잰 날 {before.get('date')}")
    print()

    print("== 미국장이 도는 밤에 화면을 켜 둔 채 40분이 지났다 ==")
    j3._disk_fresh_seconds = lambda interval="": 0.0     # 파일 공책도 식은 상태
    age_the_notebook(2400)
    after = timed("상승장 단추를 누른다", lambda: j3.breakout_scan(persist=False))
    print(f"     정식 {len(after.get('primary_rows') or [])}"
          f" · 관찰 {len(after.get('watch_rows') or [])}"
          f" · 잰 날 {after.get('date')}")
    print("     40분 전과 목록이 같은가: "
          f"정식 {'예' if tickers(before, 'primary_rows') == tickers(after, 'primary_rows') else '아니오'}"
          f" · 관찰 {'예' if tickers(before, 'watch_rows') == tickers(after, 'watch_rows') else '아니오'}")
    print()

    print("== 새로 받는 일은 뒤 일꾼이 하는가 ==")
    running = [t.name for t in threading.enumerate() if "breakout" in t.name]
    print("     지금 도는 일꾼:", running or "없음")
    for thread in threading.enumerate():
        if thread.name == "breakout-refresh":
            thread.join(timeout=180)
    print("     다 돈 뒤:",
          [t.name for t in threading.enumerate() if "breakout" in t.name] or "없음")
    print()

    print("== 맨 위 ↻ 를 누르면 담아 둔 것도 버리는가 ==")
    j3.clear_runtime_cache()
    print("     담아 둔 것:",
          "비었다" if j3._breakout_kept_for_this_session() is None else "**남아 있다**")


if __name__ == "__main__":
    main()
