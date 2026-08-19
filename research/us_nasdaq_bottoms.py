"""나스닥 10년 — **하락 국면과 최저점을 하나도 빼지 않고** 적는다 (2026-08-15).

상하님 지시 — "나스닥 10년간 최저점이 몇 번 나왔고 날짜는? 또 그때 최저점이 고점
대비 몇 프로 −였나? 그리고 각 최저점을 리스트 만들어 봐라. 믿지를 못하겠다."

## 어떻게 셌나 — 숨기는 것 없이

  ① 나스닥 **종합지수(IXIC) 종가**로 그날까지의 **사상 최고가 대비 낙폭**을 낸다.
  ② 낙폭이 **−5% 아래로 내려간 순간부터** 한 국면이 시작되고, 다시 **−1% 위로
     올라오면** 그 국면이 끝난다.
  ③ 국면 안에서 낙폭이 가장 깊었던 날이 그 국면의 **최저점**이다.
  ④ 앱이 사는 자리는 그 **최저점 다음 거래일**이다(종가 확인 후 다음 날 시가 매수).

**−5%부터 전부 적는다.** 앱이 쓰는 −12·−18·−24%보다 얕은 것까지 다 적어야
"몇 개를 골라 썼는지"가 드러난다. 어느 것을 썼는지는 맨 오른쪽 칸에 표시한다.

쓰는 법:  PYTHONIOENCODING=utf-8 python research/us_nasdaq_bottoms.py
"""

from __future__ import annotations

import pathlib
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

STEPS = (-12.0, -18.0, -24.0)
START_EDGE = -5.0      # 이보다 깊어지면 국면 시작
END_EDGE = -1.0        # 이보다 얕아지면 국면 끝


def main() -> None:
    from us_yearly import fetch

    wide = fetch()
    stock_dates = wide["close"].index          # 명부 종목 자료가 있는 날
    ixic = pd.read_parquet(ROOT / "research" / "_data" / "ixic.parquet")["close"].dropna()

    print("나스닥 종합지수(IXIC) 종가")
    print(f"   자료 {len(ixic):,}일 · {ixic.index[0].date()} ~ {ixic.index[-1].date()}")
    print(f"   명부 종목 자료 {len(stock_dates):,}일 · "
          f"{stock_dates[0].date()} ~ {stock_dates[-1].date()}")
    print("   → 성적을 잴 수 있는 것은 **두 자료가 겹치는 기간**뿐입니다.\n")

    drop = (ixic / ixic.cummax() - 1.0) * 100.0
    index = list(drop.index)

    # 국면 나누기
    episodes, start = [], None
    for i, value in enumerate(drop.to_numpy()):
        if value <= START_EDGE and start is None:
            start = i
        elif start is not None and value > END_EDGE:
            episodes.append((start, i - 1)); start = None
    if start is not None:
        episodes.append((start, len(index) - 1))

    print("=" * 108)
    print("나스닥 하락 국면 전부 (고점 대비 −5% 아래로 내려간 것)")
    print("=" * 108)
    head = (f"{'번호':<5}{'시작':<12}{'최저점 날짜':<14}{'최저 낙폭':>10}"
            f"{'끝난 날':<14}{'며칠':>6}   {'닿은 문턱':<14}{'앱이 썼나'}")
    print(head); print("─" * 106)

    used, skipped = [], []
    for number, (a, b) in enumerate(episodes, 1):
        segment = drop.iloc[a:b + 1]
        worst_day = segment.idxmin()
        worst = float(segment.min())
        worst_pos = index.index(worst_day)
        next_day = index[worst_pos + 1] if worst_pos + 1 < len(index) else None
        touched = [s for s in STEPS if worst <= s]
        touch_text = " ".join(f"{int(s)}%" for s in touched) or "—"
        if not touched:
            mark = "안 씀 (−12% 못 닿음)"
        elif next_day is None:
            mark = "안 씀 (다음 날 없음)"
        elif next_day not in stock_dates:
            mark = "안 씀 (종목 자료 밖)"
        else:
            mark = f"**썼다** → {next_day.date()}"
            used.append((worst_day, worst, next_day, touch_text))
        if not touched or next_day is None or next_day not in stock_dates:
            skipped.append((worst_day, worst, touch_text, mark))
        print(f"{number:<5}{str(index[a].date()):<12}{str(worst_day.date()):<14}"
              f"{worst:>9.1f}%{str(index[b].date()):<14}{b - a + 1:>6}   "
              f"{touch_text:<14}{mark}")

    print("\n" + "=" * 108)
    print(f"앱이 실제로 쓴 자리 — {len(used)}개")
    print("=" * 108)
    print(f"{'':<4}{'최저점 날짜':<14}{'그날 낙폭':>10}   {'사는 날(다음 거래일)':<22}{'닿은 문턱'}")
    print("─" * 80)
    for i, (worst_day, worst, next_day, touch_text) in enumerate(used, 1):
        print(f"{i:<4}{str(worst_day.date()):<14}{worst:>9.1f}%   "
              f"{str(next_day.date()):<22}{touch_text}")

    if skipped:
        print(f"\n쓰지 않은 국면 — {len(skipped)}개")
        for worst_day, worst, touch_text, why in skipped:
            print(f"   {worst_day.date()}  {worst:>6.1f}%  {why}")

    print("\n" + "=" * 108)
    print("가장 깊었던 국면 다섯 — 낙폭 순")
    print("=" * 108)
    ranked = sorted(((drop.iloc[a:b + 1].min(), drop.iloc[a:b + 1].idxmin())
                     for a, b in episodes), key=lambda x: x[0])[:5]
    for rank, (worst, worst_day) in enumerate(ranked, 1):
        print(f"   {rank}등  {worst_day.date()}  {worst:>6.1f}%")


if __name__ == "__main__":
    main()
