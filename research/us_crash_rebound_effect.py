"""나스닥이 **바닥 찍고 반등할 때** 급락 배점 항목이 실제로 값을 했나 (2026-08-15).

상하님 물음 — "나스닥이 최저점 찍고 반등할 때 심사항목들이 실제 효과를 나타내었느냐를
질문하는 것이야. 저 배점들이 실질적으로 점수가 나오는지, 그리고 점수 나온 종목들이
상승율과 수익율에 영향을 미친 것인지를 확인하는 것이야."

## 앞서 잰 것과 무엇이 다른가

  · 2026-08-14 `us_crash_appstyle.py` — **테마**를 줄 세워 "그 잣대 위쪽 테마가
    아래쪽 테마보다 더 벌었나"를 봤다. 재는 대상이 테마였다.
  · 2026-08-15 `us_crash_zero_items.py` — 문턱을 **통과한 종목이 있기는 했나**만 셌다.
  · **여기(이 파일)** — 통과한 **종목**과 통과 못 한 **종목**을 갈라, 그 뒤 성적을
    직접 견준다. 상하님이 물으신 것이 이것이다.

## 어떻게 재나

자리   나스닥 종합(IXIC)이 −12%·−18%·−24%까지 빠졌다가 **바닥을 찍은 다음 날**.
       같은 날이 여러 문턱에 겹치면 한 번만 센다.
       견주기 위해 **문턱에 처음 닿은 날**(아직 내려가는 길목)도 따로 낸다.
후보   그 자리에서 1년 고점 대비 −20~−50% 빠진 종목 (앱의 급락 그물)
가름   항목마다 '점수를 받은 종목'과 '못 받은 종목'으로 가른다
성적   **다음 날 시가에 사서** 3개월·6개월·1년 뒤 종가까지
       · 오른 비율(100번 중 몇 번) · 가운데 수익률
견주기 **같은 자리 안에서만** 견준다(CLAUDE.md 0-1 마). 자리마다 시장 상황이
       달라서, 좋은 해의 통과 종목과 나쁜 해의 미달 종목을 섞으면 안 된다.

쓰는 법:  PYTHONIOENCODING=utf-8 python research/us_crash_rebound_effect.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

from us_crash_appstyle import touch_days, turn_days  # noqa: E402

STEPS = (-12.0, -18.0, -24.0)
STOCK_BAND = (-50.0, -20.0)
HOLDS = ((60, "3개월"), (120, "6개월"), (250, "1년"))
MIN_MEMBERS = 3


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

    high52 = high.rolling(252, min_periods=252).max()
    from_high = (close / high52 - 1.0) * 100.0
    sma50 = close.rolling(50, min_periods=50).mean()
    sma150 = close.rolling(150, min_periods=150).mean()
    sma200 = close.rolling(200, min_periods=200).mean()
    above20 = (close > close.rolling(20, min_periods=20).mean()).astype(float)
    above150 = (close > sma150).astype(float)
    aligned = ((close > sma50) & (sma50 > sma150) & (sma150 > sma200)
               & (sma200 > sma200.shift(20))).astype(float)
    # **다음 날 시가에 산다** — 신호가 난 날 종가로는 못 산다(설명서 규칙).
    rets = {hold: (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
            for hold, _l in HOLDS}

    def by_theme(table: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame({n: table[m].mean(axis=1) for n, m in themes.items()})

    board = {"above150": by_theme(above150), "drop": by_theme(from_high),
             "aligned": by_theme(aligned), "above20": by_theme(above20)}

    ITEMS = (
        ("① 테마 30주선 위",   "above150", j3.CRASH_ABOVE150_TOP_N, "지금 40점"),
        ("② 테마가 덜 빠졌나", "drop",     j3.CRASH_LESS_DROP_TOP_N, "지금 0점 (옛 40점)"),
        ("③ 테마 주봉 오름세", "aligned",  j3.CRASH_SPREAD_TOP_N,    "지금 0점 (옛 30점)"),
        ("④ 테마 20일선 위",   "above20",  j3.CRASH_SPREAD_TOP_N,    "지금 0점 (옛 20점)"),
    )
    OLD_POINTS = {"drop": 40.0, "aligned": 30.0, "above20": 20.0}

    def spot_days(kind: str) -> list[pd.Timestamp]:
        picker = turn_days if kind == "반등" else touch_days
        found = set()
        for step in STEPS:
            found.update(picker(ixic, step))
        return sorted(day for day in found if day in from_high.index)

    def measure(days: list[pd.Timestamp], title: str) -> None:
        print("\n" + "=" * 100)
        print(f"{title} — 자리 {len(days)}개")
        print("=" * 100)
        for day in days:
            print(f"   {day.date()}", end="")
        print("\n")

        head = (f"{'항목':<20}{'보유':<7}{'점수 받음':>22}{'못 받음':>22}   차이")
        print(head); print("─" * 96)
        for item_name, key, top_n, note in ITEMS:
            for hold, label in HOLDS:
                got_win, got_ret, miss_win, miss_ret, pairs, n_got = [], [], [], [], 0, 0
                for day in days:
                    drop_today = from_high.loc[day]
                    pool = [s for s in names
                            if pd.notna(drop_today.get(s))
                            and STOCK_BAND[0] <= drop_today[s] <= STOCK_BAND[1]
                            and belongs.get(s)
                            and pd.notna(rets[hold].loc[day].get(s))]
                    if len(pool) < 8:
                        continue
                    series = board[key].loc[day].dropna()
                    if series.empty:
                        continue
                    place = {name: i for i, name in
                             enumerate(series.sort_values(ascending=False).index, 1)}
                    got = [s for s in pool
                           if min((place[t] for t in belongs[s] if t in place),
                                  default=99) <= top_n]
                    miss = [s for s in pool if s not in got]
                    if not got or not miss:
                        continue
                    row = rets[hold].loc[day]
                    got_win.append(float((row[got] > 0).mean() * 100))
                    miss_win.append(float((row[miss] > 0).mean() * 100))
                    got_ret.append(float(np.median(row[got])))
                    miss_ret.append(float(np.median(row[miss])))
                    pairs += 1
                    n_got += len(got)
                if pairs < 3:
                    print(f"{item_name:<20}{label:<7}{'자리가 모자라 못 잼':>22}")
                    continue
                gw, mw = mid(got_win), mid(miss_win)
                gr, mr = mid(got_ret), mid(miss_ret)
                better = sum(1 for a, b in zip(got_ret, miss_ret) if a > b)
                mark = "▲" if better >= pairs * 0.65 else "▼" if better <= pairs * 0.35 else "·"
                print(f"{item_name:<20}{label:<7}"
                      f"{gw:>7.0f}번{gr:>+9.1f}%{'':>5}"
                      f"{mw:>7.0f}번{mr:>+9.1f}%{'':>5}"
                      f"  {gr - mr:+6.1f}%p · {pairs}자리 중 {better}자리 이김 {mark}")
            print()
        print("   ▲ = 자리 열 중 일곱 이상에서 이겼다 · ▼ = 셋 이하 · · = 못 가름")
        print("   '점수 받음'의 두 숫자 = 100번 중 오른 횟수 · 가운데 수익률")

    rebound = spot_days("반등")
    threshold = spot_days("문턱")
    measure(rebound, "㉮ 나스닥이 바닥 찍고 **반등한 다음 날** — 상하님이 물으신 자리")
    measure(threshold, "㉯ 견주기 · 문턱에 처음 닿은 날 (아직 내려가는 길목)")

    # ── 옛 배점 90점을 통째로 견준다 ──────────────────────────────────────────
    print("\n" + "=" * 100)
    print("㉰ 옛 배점(덜 빠짐 40 + 주봉 30 + 20일선 20 = 90점)을 통째로 — 반등 자리")
    print("=" * 100)
    head = f"{'보유':<8}{'높은 점수 절반':>24}{'낮은 절반':>22}   차이"
    print(head); print("─" * 80)
    for hold, label in HOLDS:
        hi_win, hi_ret, lo_win, lo_ret, pairs, better = [], [], [], [], 0, 0
        for day in rebound:
            drop_today = from_high.loc[day]
            pool = [s for s in names
                    if pd.notna(drop_today.get(s))
                    and STOCK_BAND[0] <= drop_today[s] <= STOCK_BAND[1]
                    and belongs.get(s)
                    and pd.notna(rets[hold].loc[day].get(s))]
            if len(pool) < 12:
                continue
            places = {}
            for key in OLD_POINTS:
                series = board[key].loc[day].dropna()
                places[key] = {name: i for i, name in
                               enumerate(series.sort_values(ascending=False).index, 1)}
            scores = {}
            for ticker in pool:
                total = 0.0
                for key, points in OLD_POINTS.items():
                    top_n = (j3.CRASH_LESS_DROP_TOP_N if key == "drop"
                             else j3.CRASH_SPREAD_TOP_N)
                    best = min((places[key][t] for t in belongs[ticker]
                                if t in places[key]), default=99)
                    if best <= top_n:
                        total += points
                scores[ticker] = total
            cut = np.median(list(scores.values()))
            hi = [s for s in pool if scores[s] > cut]
            lo = [s for s in pool if scores[s] <= cut]
            if len(hi) < 3 or len(lo) < 3:
                continue
            row = rets[hold].loc[day]
            hi_win.append(float((row[hi] > 0).mean() * 100))
            lo_win.append(float((row[lo] > 0).mean() * 100))
            hi_ret.append(float(np.median(row[hi])))
            lo_ret.append(float(np.median(row[lo])))
            better += 1 if hi_ret[-1] > lo_ret[-1] else 0
            pairs += 1
        if pairs < 3:
            print(f"{label:<8}자리가 모자라 못 잼")
            continue
        print(f"{label:<8}{mid(hi_win):>9.0f}번{mid(hi_ret):>+11.1f}%{'':>4}"
              f"{mid(lo_win):>9.0f}번{mid(lo_ret):>+9.1f}%"
              f"   {mid(hi_ret) - mid(lo_ret):+6.1f}%p · "
              f"{pairs}자리 중 {better}자리 이김")

    # ── 오늘은 어디쯤인가 ────────────────────────────────────────────────────
    print("\n" + "=" * 100)
    print("㉱ 오늘 나스닥은 어디쯤인가 — 지금 0점이 많은 까닭을 보는 자리")
    print("=" * 100)
    drop_now = (ixic / ixic.cummax() - 1.0) * 100.0
    print(f"나스닥 종합 마지막 자료 {ixic.index[-1].date()} · "
          f"1년 고점 대비 {drop_now.iloc[-1]:+.1f}%")
    last = board["above150"].iloc[-1].dropna().sort_values(ascending=False)
    print(f"\n테마 30주선 위 비율 — 위 6개 (상위 {j3.CRASH_ABOVE150_TOP_N}등까지 40점)")
    for i, (name, value) in enumerate(last.head(6).items(), 1):
        mark = " ← 40점" if i <= j3.CRASH_ABOVE150_TOP_N else ""
        print(f"   {i}등 {name:<18}{value * 100:>6.1f}%{mark}")
    for key, title, top_n in (("drop", "테마가 덜 빠졌나", j3.CRASH_LESS_DROP_TOP_N),
                              ("aligned", "테마 주봉 오름세", j3.CRASH_SPREAD_TOP_N),
                              ("above20", "테마 20일선 위", j3.CRASH_SPREAD_TOP_N)):
        row = board[key].iloc[-1].dropna().sort_values(ascending=False)
        top = " · ".join(f"{i}등 {n}" for i, (n, _v) in enumerate(row.head(3).items(), 1))
        print(f"\n{title} — 위 3개: {top}")


if __name__ == "__main__":
    main()
