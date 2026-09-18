# -*- coding: utf-8 -*-
"""상승장 미리 만들기를 앞줄로 옮긴 것이 무엇을 밀어내나 (2026-09-18).

CLAUDE.md 0-0 — 새로 넣는 것이 무엇을 밀어내는지 **먼저 잰다.**

화면이 부르는 차례 그대로 두 가지를 견준다.
  전(뒤 일꾼)  테마 순위 → warm_breakout_scan()  → 곧바로 단추
  후(앞줄)     테마 순위 → prepare_breakout_scan() → 곧바로 단추

"곧바로 단추"는 상하님이 **단추가 보이자마자 누르시는** 그 순간이다.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import jarvis3_data as j3  # noqa: E402


def timed(label, fn):
    w0, c0 = time.perf_counter(), time.process_time()
    out = fn()
    w, c = time.perf_counter() - w0, time.process_time() - c0
    print(f"    {label:<34} 벽시계 {w:6.2f}s  CPU {c:6.2f}s")
    return out, w


def reset():
    j3.clear_runtime_cache()
    j3._BREAKOUT_WARM["at"] = 0.0
    j3._BREAKOUT_WARM["on"] = False


def run(label, warmer):
    print(label)
    reset()
    _r, t_rank = timed("① 테마 순위 (화면 그리는 길)", j3.get_theme_rankings)
    _w, t_warm = timed("② 미리 만들기", warmer)
    _s, t_btn = timed("③ 단추를 바로 누른다", lambda: j3.breakout_scan(persist=False))
    print(f"    ── 화면 뜰 때까지 {t_rank + t_warm:5.2f}s · 누르고 나올 때까지 {t_btn:5.2f}s")
    print()
    return t_rank + t_warm, t_btn


def main():
    # 한 번 데워서 인터넷 내려받기를 공책에 넣어 둔다 — 두 방식을 같은 자리에서 견준다.
    j3.get_theme_rankings()
    j3.find_breakout_pullback_stocks()
    print()

    before = run("== 전 — 뒤 일꾼에게 시킨다(warm_breakout_scan) ==",
                 j3.warm_breakout_scan)
    after = run("== 후 — 그 자리에서 만든다(prepare_breakout_scan) ==",
                j3.prepare_breakout_scan)

    print("== 견줌 ==")
    print(f"  화면 뜰 때까지   {before[0]:5.2f}s → {after[0]:5.2f}s "
          f"({after[0] - before[0]:+.2f}s)")
    print(f"  단추 누르고      {before[1]:5.2f}s → {after[1]:5.2f}s "
          f"({after[1] - before[1]:+.2f}s)")


if __name__ == "__main__":
    main()
