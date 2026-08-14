"""20개 테마 실시간 순위 배점을 **그 배점의 목적대로** 잰다 (2026-08-14).

상하님 물음 — "20개 테마 실시간 순위에 배점도 확인해 봤냐?"

아직 안 했다. 급락 자리에서 '예측을 맞히나'만 봤고, **이 순위표 자체의 목적**으로는
한 번도 안 쟀다. 그래서 여기서 잰다.

## 이 순위표는 무엇을 하는 자리인가

날마다 테마 20개를 조건점수로 줄 세워, 상하님이 **오늘 어느 테마를 볼지** 고르시게
한다. 그러니 물음은 하나다.

> **점수가 높은 테마가 정말로 그 뒤에 더 올랐나?**

## 지금 배점 (THEME_SCORE_WEIGHTS)

    20일선 위 비율 40 · 최근 5일 오른 비율 30 · 최근 20일 오른 비율 20 · 덜 빠졌나 10

## 어떻게 재나

날마다 테마 20개를 그 잣대로 줄 세우고, **그 뒤 3개월·6개월·1년 테마별 평균
수익률 순위**와 얼마나 맞는지 본다(순위상관). 날이 2,500일이라 넉넉하다.
오차는 **연도를 통째로 다시 뽑아** 낸다 — 1년 수익률은 날마다 364일씩 겹친다.

**국면을 갈라 본다** — 이것이 핵심이다.
  · 평상시  — 나스닥이 고점 대비 −6% 안
  · 급락 중 — 나스닥이 고점 대비 −6% 아래
같은 배점이 두 국면에서 다르게 나오면, 화면에 그 사실을 적어야 한다.

쓰는 법:  PYTHONIOENCODING=utf-8 python research/us_theme_rank_check.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

# **짧은 앞날부터 본다**(2026-08-14). 이 순위표는 "지금 달아오르는 테마"를 재는
# 자리다. 3개월~1년으로만 채점하면 그 자리가 하는 일과 다른 것을 재게 된다.
HOLDS = ((5, "5일"), (10, "10일"), (20, "20일"),
         (60, "3개월"), (120, "6개월"), (250, "1년"))
MIN_MEMBERS = 3
DRAWS = 2000


def _sc(series, low, high, points):
    """jarvis3_data._scale과 같은 식(값 하나가 아니라 줄 전체에 쓴다)."""
    return np.clip((series - low) / (high - low) * points, 0.0, points)


def band(values: np.ndarray, years: np.ndarray) -> tuple:
    """평균과, **연도를 통째로 다시 뽑아** 낸 오차 범위."""
    if len(values) < 30:
        return None, None, None, len(values)
    point = float(np.mean(values))
    uniq = sorted(set(years))
    by = {y: values[years == y] for y in uniq}
    rng = np.random.default_rng(20260814)
    draws = np.empty(DRAWS)
    for i in range(DRAWS):
        pick = rng.integers(0, len(uniq), len(uniq))
        draws[i] = np.mean(np.concatenate([by[uniq[p]] for p in pick]))
    return point, float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5)), len(values)


def main() -> None:
    import jarvis3_data as j3
    from us_yearly import fetch

    wide = fetch()
    names = [c for c in wide["close"].columns if c != "QQQ"]
    close, high = wide["close"][names], wide["high"][names]
    opens, qqq = wide["open"][names], wide["close"]["QQQ"]
    dates = close.index

    themes = {t["name"]: [s for s in t["stocks"] if s in close.columns]
              for t in j3.US_THEMES}
    themes = {n: m for n, m in themes.items() if len(m) >= MIN_MEMBERS}
    print(f"테마 {len(themes)}개 · 거래일 {len(dates):,}일\n")

    high52 = high.rolling(252, min_periods=252).max()
    from_high = (close / high52 - 1.0) * 100.0
    above20 = (close > close.rolling(20, min_periods=20).mean()).astype(float)
    rose5 = (close > close.shift(5)).astype(float)
    rose20 = (close > close.shift(20)).astype(float)
    # Weinstein 30주선(150일선) — 바닥에서 올라서는 자리를 보는 기준선이다.
    above150 = (close > close.rolling(150, min_periods=150).mean()).astype(float)
    rets = {hold: (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
            for hold, _l in HOLDS}

    # 테마별 값 — 날짜 × 테마
    def by_theme(table: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame({n: table[m].mean(axis=1) for n, m in themes.items()})

    ret5 = (close / close.shift(5) - 1.0) * 100.0
    ret20d = (close / close.shift(20) - 1.0) * 100.0
    ret60d = (close / close.shift(60) - 1.0) * 100.0
    board = {
        "above20": by_theme(above20), "rose5": by_theme(rose5),
        "rose20": by_theme(rose20), "drop": by_theme(from_high),
        "above150": by_theme(above150), "ret5": by_theme(ret5),
        "ret20": by_theme(ret20d), "ret60": by_theme(ret60d),
    }
    ret_board = {hold: by_theme(rets[hold]) for hold, _l in HOLDS}

    score_now = (_sc(board["above20"] * 100, 25, 85, 40.0)
                 + _sc(board["rose5"] * 100, 20, 80, 30.0)
                 + _sc(board["rose20"] * 100, 25, 85, 20.0)
                 + _sc(board["drop"], -30.0, -2.0, 10.0))

    gauges = {
        "지금 순위 점수(그대로)": score_now,
        "  ① 20일선 위 비율 (40점)": board["above20"],
        "  ② 최근 5일 오른 비율 (30점)": board["rose5"],
        "  ③ 최근 20일 오른 비율 (20점)": board["rose20"],
        "  ④ 덜 빠졌나 (10점)": board["drop"],
        "  참고 · 30주선 위 비율": board["above150"],
        "  참고 · 많이 빠졌나(④의 반대)": -board["drop"],
        # 지금 화면이 보여만 주고 점수엔 안 쓰는 값들 — 쓸 만한지 같이 본다.
        "  후보 · 테마 5일 수익률": board["ret5"],
        "  후보 · 테마 20일 수익률": board["ret20"],
        "  후보 · 테마 60일 수익률": board["ret60"],
    }

    drawdown = (qqq / qqq.cummax() - 1.0) * 100.0
    phases = (("평상시 (나스닥 −6% 안)", drawdown >= -6.0),
              ("급락 중 (나스닥 −6% 아래)", drawdown < -6.0))

    for phase_name, mask in phases:
        days = dates[mask.reindex(dates).fillna(False).to_numpy()]
        print(f"\n{'='*84}\n{phase_name} — {len(days):,}일\n{'='*84}")
        head = "잣대".ljust(28) + "  ".join(l.rjust(18) for _h, l in HOLDS)
        print(head); print("─" * len(head))
        for gauge_name, table in gauges.items():
            cells = []
            for hold, _label in HOLDS:
                corrs, years = [], []
                for day in days:
                    if day not in table.index:
                        continue
                    a = table.loc[day]
                    b = ret_board[hold].loc[day]
                    ok = a.notna() & b.notna()
                    if ok.sum() < 8:
                        continue
                    corr = a[ok].rank().corr(b[ok].rank())
                    if pd.isna(corr):
                        continue
                    corrs.append(corr); years.append(day.year)
                point, low, high_, n = band(np.array(corrs), np.array(years))
                if point is None:
                    cells.append("자료부족".rjust(18)); continue
                mark = "▲" if low > 0 else "▼" if high_ < 0 else "·"
                cells.append(f"{point:+.3f}({low:+.2f}~{high_:+.2f}){mark}".rjust(18))
            print(gauge_name.ljust(28) + "  ".join(cells))
        print("\n▲ = 오차가 0을 안 걸치고 **양수**(그 잣대가 높은 테마가 더 올랐다)")
        print("▼ = 오차가 0을 안 걸치고 **음수**(거꾸로다) · · = 못 가름")


if __name__ == "__main__":
    main()
