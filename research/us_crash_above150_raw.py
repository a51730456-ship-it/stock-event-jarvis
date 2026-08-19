"""「테마가 30주선 위에 있나」 하나만 — **자리 하나하나를 다 까서** 보인다 (2026-08-15).

상하님 — "테마가 30주선 위에 있나, 이것도 못 믿겠다. 도대체 돌릴 때마다 달라지냐."

## 왜 돌릴 때마다 숫자가 달랐나

**같은 잣대를 서로 다른 방식으로 잘랐기 때문이다.** 오늘 하루에 저는 이렇게 넷을 냈다.

    us_crash_appstyle    (8/14) 테마끼리 견줌 · 적중률          → 반등 87.7%
    us_crash_rebound_effect     상위 3등 안 종목 vs 밖 종목      → 6개월 +13.4%p
    us_crash_scoreboards        상위 9종목 vs 후보 전체 평균     → 6개월  +3.6%p
    us_crash_wide_sweep         값의 위 절반 vs 아래 절반        → 6개월  +7.3%p

넷 다 다른 것을 쟀으니 숫자가 다른 것은 당연하다. **그런데 그것은 변명이 안 된다** —
상하님께는 그때그때 한 숫자만 들이밀었으니 흔들리는 것으로 보일 수밖에 없다.

## 그래서 여기서는 평균을 내지 않는다

자리 여섯 개를 **하나씩 그대로** 적는다. 평균에 가려진 것이 없는지 상하님이 직접
보시라는 것이다. 한 자리가 전체를 끌고 갔는지, 고르게 이겼는지가 그대로 드러난다.

가름   그날 후보(1년 고점 대비 −20~−50%) 중
       · 「30주선 위 상위 3등 테마」에 든 종목  ← 40점 받는 쪽
       · 나머지                                ← 0점
성적   다음 날 시가에 사서 3개월·6개월·1년 뒤 종가. 가운데 수익률과 오른 비율.

쓰는 법:  PYTHONIOENCODING=utf-8 python research/us_crash_above150_raw.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

from us_crash_appstyle import turn_days  # noqa: E402

STEPS = (-12.0, -18.0, -24.0)
STOCK_BAND = (-50.0, -20.0)
HOLDS = ((60, "3개월"), (120, "6개월"), (250, "1년"))
MIN_MEMBERS = 3
TOP_N = 3


# **합칠 때도 중간값이다** (2026-08-15 상하님 지적 — "왜 또 평균을 내냐, 중간값으로
# 하기로 예전부터 이야기했잖아"). 종목 수익률은 중간값을 냈으면서 자리끼리 합칠 때
# 평균을 내면, 2020년 3월처럼 한 번 크게 터진 자리가 전체를 끌고 간다.
# 자리가 여섯 개뿐이라 그 영향이 특히 크다. mid()로 통일한다.
def mid(values):
    """가운데 값. 빈 목록이면 0."""
    return float(np.median(values)) if len(values) else 0.0


def main() -> None:
    import jarvis3_data as j3
    from us_yearly import fetch

    wide = fetch()
    names = [c for c in wide["close"].columns if c != "QQQ"]
    close, high, opens = wide["close"][names], wide["high"][names], wide["open"][names]
    dates = close.index
    ixic = pd.read_parquet(ROOT / "research" / "_data" / "ixic.parquet")["close"]
    ixic = ixic.reindex(dates).ffill().dropna()

    themes = {t["name"]: [s for s in t["stocks"] if s in close.columns]
              for t in j3.US_THEMES}
    themes = {n: m for n, m in themes.items() if len(m) >= MIN_MEMBERS}
    belongs = {s: [n for n, m in themes.items() if s in m] for s in close.columns}

    from_high = (close / high.rolling(252, min_periods=252).max() - 1.0) * 100.0
    above150 = (close > close.rolling(150, min_periods=150).mean()).astype(float)
    board = pd.DataFrame({n: above150[m].mean(axis=1) for n, m in themes.items()})
    rets = {hold: (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
            for hold, _l in HOLDS}

    bottoms = sorted({d for step in STEPS for d in turn_days(ixic, step)
                      if d in from_high.index})

    print(f"나스닥이 −12·−18·−24%까지 빠졌다 바닥 찍은 다음 날 — 모두 {len(bottoms)}자리")
    print("(같은 날이 여러 문턱에 겹치면 한 번만 셌다)\n")

    tally = {label: [0, 0] for _h, label in HOLDS}    # [이긴 자리, 잰 자리]
    for day in bottoms:
        drop_today = from_high.loc[day]
        pool = [s for s in names
                if pd.notna(drop_today.get(s))
                and STOCK_BAND[0] <= drop_today[s] <= STOCK_BAND[1]
                and belongs.get(s)]
        series = board.loc[day].dropna()
        place = {n: i for i, n in enumerate(series.sort_values(ascending=False).index, 1)}
        top_themes = [n for n, i in place.items() if i <= TOP_N]
        got = [s for s in pool
               if min((place[t] for t in belongs[s] if t in place), default=99) <= TOP_N]
        miss = [s for s in pool if s not in got]

        print("─" * 94)
        print(f"{day.date()} · 후보 {len(pool)}종목 → 40점 {len(got)}종목 / 0점 {len(miss)}종목")
        print(f"   상위 {TOP_N}등 테마: " + " · ".join(
            f"{i}등 {n}({series[n]*100:.0f}%)" for n, i in
            sorted(((n, place[n]) for n in top_themes), key=lambda x: x[1])))
        if got:
            print(f"   40점 종목: {', '.join(sorted(got)[:14])}"
                  + (" …" if len(got) > 14 else ""))
        for hold, label in HOLDS:
            row = rets[hold].loc[day]
            g = [s for s in got if pd.notna(row.get(s))]
            m = [s for s in miss if pd.notna(row.get(s))]
            if len(g) < 3 or len(m) < 3:
                print(f"   {label:<5} 아직 그만큼 시간이 안 지났습니다")
                continue
            gw, mw = (row[g] > 0).mean() * 100, (row[m] > 0).mean() * 100
            gr, mr = np.median(row[g]), np.median(row[m])
            win = gr > mr
            tally[label][0] += 1 if win else 0
            tally[label][1] += 1
            print(f"   {label:<5} 40점 {gw:>3.0f}번 {gr:+7.1f}%   |   "
                  f"0점 {mw:>3.0f}번 {mr:+7.1f}%   |   "
                  f"차이 {gr - mr:+7.1f}%p  {'이김' if win else '짐'}")

    print("─" * 94)
    print("\n합계 — 몇 자리에서 이겼나")
    for _hold, label in HOLDS:
        won, total = tally[label]
        print(f"   {label:<5} {won} / {total}자리")

    # 자리 하나를 빼면 답이 바뀌나 — 한 자리가 끌고 가는지 본다
    print("\n한 자리를 빼도 그대로인가 (6개월 기준)")
    hold = 120
    diffs = []
    for day in bottoms:
        drop_today = from_high.loc[day]
        row = rets[hold].loc[day]
        pool = [s for s in names
                if pd.notna(drop_today.get(s))
                and STOCK_BAND[0] <= drop_today[s] <= STOCK_BAND[1]
                and belongs.get(s) and pd.notna(row.get(s))]
        series = board.loc[day].dropna()
        place = {n: i for i, n in enumerate(series.sort_values(ascending=False).index, 1)}
        got = [s for s in pool
               if min((place[t] for t in belongs[s] if t in place), default=99) <= TOP_N]
        miss = [s for s in pool if s not in got]
        if len(got) < 3 or len(miss) < 3:
            continue
        diffs.append((day.date(), float(np.median(row[got]) - np.median(row[miss]))))
    if diffs:
        values = [v for _d, v in diffs]
        print(f"   전부 넣으면 평균 {mid(values):+.1f}%p")
        for day, value in diffs:
            rest = [v for d, v in diffs if d != day]
            print(f"   {day} 자리를 빼면 {mid(rest):+.1f}%p"
                  f"   (그 자리 혼자서는 {value:+.1f}%p)")


if __name__ == "__main__":
    main()
