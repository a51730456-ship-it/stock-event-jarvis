"""급락 반등 자리마다 **앱이 뽑았을 종목을 하나씩** 적는다 (2026-08-15).

상하님 지시 — "또 종목 선정하면 중간값 평균값이 뭐가 필요하냐. 테마 종목들 상위
5개 종목 하나하나 보면 되지."

**맞습니다.** 급락 자리는 10년에 여섯 번뿐입니다. 여섯 번을 중간값 하나로 뭉개면
무엇이 되고 무엇이 안 됐는지가 사라집니다. 여기서는 **종목 이름과 그 종목이
실제로 몇 % 갔는지**를 그대로 적습니다.

## 앱이 뽑는 차례를 그대로 따른다

  ① 그날 후보 — 1년 고점 대비 −20~−50% 빠진 종목
  ② 점수 — 그 종목의 테마가 30주선 위 **상위 3등**이면 40점, 아니면 0점
  ③ 같은 점수 안에서는 **테마를 번갈아** 놓는다(_spread_by_theme와 같은 방식)
  ④ 위에서 다섯 종목

성적은 **다음 날 시가에 사서** 3개월·6개월·1년 뒤 종가까지. 각 종목의 실제 값이다.

쓰는 법:  PYTHONIOENCODING=utf-8 python research/us_crash_picks_one_by_one.py
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
PICK = 5


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

    def spread_by_theme(rows: list[tuple[str, str]]) -> list[tuple[str, str]]:
        """같은 점수 안에서 테마를 번갈아 — 앱의 _spread_by_theme와 같은 생각."""
        buckets: dict[str, list[tuple[str, str]]] = {}
        for ticker, theme in rows:
            buckets.setdefault(theme, []).append((ticker, theme))
        out, order = [], list(buckets)
        while any(buckets[name] for name in order):
            for name in order:
                if buckets[name]:
                    out.append(buckets[name].pop(0))
        return out

    wins = {label: [0, 0] for _h, label in HOLDS}
    print("앱이 급락 자리마다 뽑았을 위 5종목 — 하나씩\n")

    for day in bottoms:
        drop_today = from_high.loc[day]
        pool = [s for s in names
                if pd.notna(drop_today.get(s))
                and STOCK_BAND[0] <= drop_today[s] <= STOCK_BAND[1] and belongs.get(s)]
        series = board.loc[day].dropna()
        place = {n: i for i, n in enumerate(series.sort_values(ascending=False).index, 1)}
        scored = []
        for ticker in pool:
            mine = [(place[t], t) for t in belongs[ticker] if t in place]
            if not mine:
                continue
            best, theme = min(mine)
            if best <= TOP_N:
                scored.append((ticker, theme))
        picks = spread_by_theme(scored)[:PICK]

        print("═" * 88)
        top_names = " · ".join(f"{i}등 {n}({series[n]*100:.0f}%)" for n, i in
                               sorted(((n, place[n]) for n in place if place[n] <= TOP_N),
                                      key=lambda x: x[1]))
        print(f"{day.date()} · 나스닥 바닥 다음 날 · 후보 {len(pool)}종목 중 40점 {len(scored)}종목")
        print(f"  30주선 위 상위 3등 테마 — {top_names}")
        if not picks:
            print("  뽑힌 종목이 없습니다"); continue
        head = f"  {'':<4}{'종목':<8}{'테마':<18}{'낙폭':>8}" + "".join(
            f"{label:>10}" for _h, label in HOLDS)
        print(head)
        for rank, (ticker, theme) in enumerate(picks, 1):
            cells = []
            for hold, label in HOLDS:
                value = rets[hold].loc[day].get(ticker)
                cells.append("  아직" if pd.isna(value) else f"{value:>+9.1f}%")
            print(f"  {rank}위  {ticker:<8}{theme:<18}{drop_today[ticker]:>7.0f}%"
                  + "".join(f"{c:>10}" for c in cells))
        # 뽑힌 다섯과 **그날 아무거나**를 견준다 — 다섯 종목 그대로
        for hold, label in HOLDS:
            row = rets[hold].loc[day]
            got = [row[t] for t, _th in picks if pd.notna(row.get(t))]
            rest = [row[s] for s in pool if s not in [t for t, _ in picks]
                    and pd.notna(row.get(s))]
            if len(got) < 3 or len(rest) < 3:
                continue
            up = sum(1 for v in got if v > 0)
            win = float(np.median(got)) > float(np.median(rest))
            wins[label][0] += 1 if win else 0
            wins[label][1] += 1
            print(f"    {label} — 다섯 중 {up}개 올랐다 · 가운데 {np.median(got):+.1f}%"
                  f"  |  그날 나머지 {len(rest)}종목 가운데 {np.median(rest):+.1f}%"
                  f"  → {'이김' if win else '짐'}")
        print()

    print("═" * 88)
    print("몇 자리에서 이겼나 (뽑은 다섯 vs 그날 나머지)")
    for _hold, label in HOLDS:
        won, total = wins[label]
        print(f"   {label:<5} {won} / {total}자리")


if __name__ == "__main__":
    main()
