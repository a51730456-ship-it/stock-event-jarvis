"""급락 배점 **세 판을 나스닥 저점에서 맞붙인다** (2026-08-15).

상하님 지시 — "지금 배점과 8월 6일 그때 배점, 어느 배점이 실질적으로 나스닥
종목 200이 최저점에서 효과가 있는 배점인지부터 확인해 봐라."

## 맞붙이는 세 판 (git에서 그대로 꺼냈다)

  Ⓐ **8/6 배점 (100점)** — a6de436
       같은 테마 동반 40 · 최근 11일에 빠졌나 25 · 낙폭 갈래 15 ·
       유동성 10 · 변동성 안정 10
       **종목을 본다.** 테마 등수는 '동반 개수'로만 쓴다.
  Ⓑ **8/12 배점 (90점)** — 751c04b
       테마가 덜 빠졌나 상위5 40 · 테마 5일 오른 비율 상위5 30 · 테마 20일선 위 상위5 20
       **전부 테마 등수다.** (2026-08-15에 제가 잰 '주봉 오름세 30'은 이 판이
        아니다 — 그건 8/14에 새로 넣은 값이다. 여기서는 8/12 그대로 5일 오른 비율을 쓴다.)
  Ⓒ **지금 배점 (40점)** — b0b83a7
       테마가 30주선 위 상위3 40

  견줌  ⓪ **아무거나** — 그날 그물에 걸린 후보 전부. 배점이 이것을 못 이기면
       배점이 하는 일이 없다.

## 자리

나스닥 종합(IXIC)이 −12%·−18%·−24%까지 빠졌다가 **바닥을 찍은 다음 날**.
표본이 여섯뿐이라, 같은 것을 **저점 뒤 10거래일 구간**으로도 낸다(자리 60개 남짓).
어느 쪽이든 **같은 자리 안에서만** 견준다 — 좋은 해와 나쁜 해를 섞지 않는다.

성적은 **다음 날 시가에 사서** 3개월·6개월·1년 뒤 종가까지. 승률(오른 비율)과
가운데 수익률을 **둘 다** 본다(CLAUDE.md 0-1 마).

쓰는 법:  PYTHONIOENCODING=utf-8 python research/us_crash_scoreboards.py
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
DEEP_EDGE = -35.0          # 8/6 배점의 '낙폭 갈래' — 이보다 깊으면 절반
HOLDS = ((60, "3개월"), (120, "6개월"), (250, "1년"))
MIN_MEMBERS = 3
PICK_N = 9                 # 화면이 보여 주는 줄 수와 맞춘다
REBOUND_WINDOW = 10        # 저점 뒤 며칠까지를 '반등 초입'으로 볼까


def _scale(value, low, high, points):
    if value is None:
        return 0.0
    return float(np.clip((value - low) / (high - low) * points, 0.0, points))


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
    close, high, low = wide["close"][names], wide["high"][names], wide["low"][names]
    opens, volume = wide["open"][names], wide["volume"][names]
    dates = close.index
    ixic = pd.read_parquet(ROOT / "research" / "_data" / "ixic.parquet")["close"]
    ixic = ixic.reindex(dates).ffill().dropna()

    themes = {t["name"]: [s for s in t["stocks"] if s in close.columns]
              for t in j3.US_THEMES}
    themes = {n: m for n, m in themes.items() if len(m) >= MIN_MEMBERS}
    belongs = {s: [n for n, m in themes.items() if s in m] for s in close.columns}

    high52 = high.rolling(252, min_periods=252).max()
    from_high = (close / high52 - 1.0) * 100.0
    above20 = (close > close.rolling(20, min_periods=20).mean()).astype(float)
    above150 = (close > close.rolling(150, min_periods=150).mean()).astype(float)
    rose5 = (close > close.shift(5)).astype(float)
    gain11 = (close / close.shift(11) - 1.0) * 100.0
    dollar = (close * volume).rolling(20, min_periods=10).mean()
    # ATR 14일 — 하루 오르내림 폭. 8/6 배점의 '변동성 안정'이 쓰던 값이다.
    prev = close.shift(1)
    true_range = pd.concat([(high - low).abs(), (high - prev).abs(),
                            (low - prev).abs()]).groupby(level=0).max()
    atr_pct = (true_range.rolling(14, min_periods=10).mean() / close * 100.0)
    rets = {hold: (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
            for hold, _l in HOLDS}

    def by_theme(table: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame({n: table[m].mean(axis=1) for n, m in themes.items()})

    board = {"above150": by_theme(above150), "drop": by_theme(from_high),
             "rose5": by_theme(rose5), "above20": by_theme(above20)}

    def places_on(day):
        out = {}
        for key, table in board.items():
            series = table.loc[day].dropna()
            out[key] = {name: i for i, name in
                        enumerate(series.sort_values(ascending=False).index, 1)}
        return out

    def best_place(ticker, table):
        return min((table[t] for t in belongs[ticker] if t in table), default=99)

    # ── 세 배점 ──────────────────────────────────────────────────────────────
    def score_0806(day, pool):
        """Ⓐ 8/6 배점 — 동반 40 · 최근 11일 25 · 낙폭 갈래 15 · 유동성 10 · 변동성 10."""
        counts = {}
        for ticker in pool:
            for name in belongs[ticker]:
                counts[name] = counts.get(name, 0) + 1
        out = {}
        for ticker in pool:
            together = max((counts[n] for n in belongs[ticker]), default=0)
            tier = 3 if together >= 4 else 2 if together >= 3 else 1 if together >= 2 else 0
            total = 40.0 * (tier / 3.0)
            gain = gain11.loc[day].get(ticker)
            total += (12.5 if pd.isna(gain)
                      else _scale(-float(gain), -5.0, 5.0, 25.0))
            total += 15.0 * (0.5 if from_high.loc[day][ticker] < DEEP_EDGE else 1.0)
            money = dollar.loc[day].get(ticker)
            total += _scale(float(money) / 1e9 if pd.notna(money) else 0.0, 0.05, 1.0, 10.0)
            atr = atr_pct.loc[day].get(ticker)
            total += (10.0 if pd.isna(atr) else _scale(-float(atr), -8.0, -2.0, 10.0))
            out[ticker] = total
        return out

    def score_0812(day, pool):
        """Ⓑ 8/12 배점 — 덜 빠짐 상위5 40 · 5일 오른 비율 상위5 30 · 20일선 위 상위5 20."""
        place = places_on(day)
        out = {}
        for ticker in pool:
            total = 0.0
            if best_place(ticker, place["drop"]) <= 5:
                total += 40.0
            if best_place(ticker, place["rose5"]) <= 5:
                total += 30.0
            if best_place(ticker, place["above20"]) <= 5:
                total += 20.0
            out[ticker] = total
        return out

    def score_now(day, pool):
        """Ⓒ 지금 배점 — 30주선 위 상위3 40."""
        place = places_on(day)
        return {t: (40.0 if best_place(t, place["above150"]) <= j3.CRASH_ABOVE150_TOP_N
                    else 0.0) for t in pool}

    BOARDS = (("Ⓐ 8/6 배점 (100점)", score_0806),
              ("Ⓑ 8/12 배점 (90점)", score_0812),
              ("Ⓒ 지금 배점 (40점)", score_now))

    def spots_for(window: int) -> list[pd.Timestamp]:
        bottoms = set()
        for step in STEPS:
            bottoms.update(turn_days(ixic, step))
        index = list(dates)
        out = set()
        for day in bottoms:
            if day not in from_high.index:
                continue
            start = index.index(day)
            for offset in range(window):
                if start + offset < len(index):
                    out.add(index[start + offset])
        return sorted(out)

    def run(days: list[pd.Timestamp], title: str) -> None:
        print("\n" + "=" * 104)
        print(f"{title} — 자리 {len(days)}개")
        print("=" * 104)
        head = (f"{'배점':<22}{'보유':<7}{'뽑은 종목':>10}"
                f"{'오른 비율':>11}{'가운데 수익률':>14}"
                f"{'아무거나와 차이':>16}   자리별 이김")
        print(head); print("─" * 100)
        for board_name, scorer in BOARDS:
            for hold, label in HOLDS:
                picked_n, wins, rets_pick, base_win, base_ret = [], [], [], [], []
                better, pairs = 0, 0
                for day in days:
                    drop_today = from_high.loc[day]
                    ret_today = rets[hold].loc[day]
                    pool = [s for s in names
                            if pd.notna(drop_today.get(s))
                            and STOCK_BAND[0] <= drop_today[s] <= STOCK_BAND[1]
                            and belongs.get(s) and pd.notna(ret_today.get(s))]
                    if len(pool) < 12:
                        continue
                    scores = scorer(day, pool)
                    top = sorted(pool, key=lambda t: (-scores[t], t))[:PICK_N]
                    if len(top) < 3:
                        continue
                    picked_n.append(len(top))
                    wins.append(float((ret_today[top] > 0).mean() * 100))
                    rets_pick.append(float(np.median(ret_today[top])))
                    base_win.append(float((ret_today[pool] > 0).mean() * 100))
                    base_ret.append(float(np.median(ret_today[pool])))
                    better += 1 if rets_pick[-1] > base_ret[-1] else 0
                    pairs += 1
                if pairs < 3:
                    print(f"{board_name:<22}{label:<7}{'자리가 모자라 못 잼':>20}")
                    continue
                gap = mid(rets_pick) - mid(base_ret)
                mark = ("▲" if better >= pairs * 0.65 else
                        "▼" if better <= pairs * 0.35 else "·")
                print(f"{board_name:<22}{label:<7}{mid(picked_n):>9.0f}개"
                      f"{mid(wins):>9.0f}번{mid(rets_pick):>+13.1f}%"
                      f"{gap:>+15.1f}%p"
                      f"   {pairs}자리 중 {better}자리 {mark}")
            print()
        # 견줌 줄 — 아무거나 샀을 때
        for hold, label in HOLDS:
            wins, rets_all = [], []
            for day in days:
                drop_today = from_high.loc[day]
                ret_today = rets[hold].loc[day]
                pool = [s for s in names
                        if pd.notna(drop_today.get(s))
                        and STOCK_BAND[0] <= drop_today[s] <= STOCK_BAND[1]
                        and belongs.get(s) and pd.notna(ret_today.get(s))]
                if len(pool) < 12:
                    continue
                wins.append(float((ret_today[pool] > 0).mean() * 100))
                rets_all.append(float(np.median(ret_today[pool])))
            if wins:
                print(f"{'⓪ 아무거나 (견줌)':<22}{label:<7}{'전부':>10}"
                      f"{mid(wins):>9.0f}번{mid(rets_all):>+13.1f}%")
        print("\n   ▲ = 자리 열 중 일곱 이상에서 아무거나보다 나았다 · ▼ = 셋 이하 · · = 못 가름")

    run(spots_for(1), "㉮ 나스닥 저점 **바로 다음 날**")
    run(spots_for(REBOUND_WINDOW),
        f"㉯ 저점 뒤 {REBOUND_WINDOW}거래일 안 (표본을 늘려 다시 본다)")


if __name__ == "__main__":
    main()
