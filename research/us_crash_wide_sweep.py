"""나스닥 저점 반등 자리에서 **잣대를 넓게 훑는다** (2026-08-15).

상하님 물음 — "나스닥이 최저점 찍고 반등할 때 급락 후 반등장의 낙폭 종목들이
승률과 수익률을 높게 주는 게, 테마가 30주선 위에 있나 이거 말고는 하나도 없었다는 게
말이 되냐?"

**말이 안 됩니다.** 제가 그동안 잰 것은 테마 잣대 **넷**뿐이었습니다(30주선·덜빠짐·
주봉 오름세·20일선). 종목 자체를 보는 잣대는 2026-08-12에 한 번 재고 "전멸"이라
적어 둔 뒤로 다시 안 봤고, 그때 잰 자리는 지금과 **다른 자리**(−6% 아래인 날 전부)
였습니다. 그러니 지금 자리에서는 아직 아무도 안 재 본 것이나 같습니다.

여기서는 **스물두 가지**를 같은 자리에서 한꺼번에 훑는다.

  종목 값 — 낙폭 깊이 · 최근 5·11·20·60일 등락 · 바닥 대비 반등폭 ·
            거래대금 · 거래대금 급증 · 하루 오르내림 폭 · 60일 흔들림 ·
            20·50·150·200일선 위인가 · 52주 저점 대비 위치
  테마 값 — 30주선 위 · 덜 빠졌나 · 주봉 오름세 · 20일선 위 · 5일 오른 비율 ·
            테마 60일 수익률 · 같은 테마 동반 개수

## 어떻게 재나

자리   나스닥 종합이 −12·−18·−24%까지 빠졌다 **바닥 찍은 다음 날**(6자리),
       그리고 표본을 늘려 **저점 뒤 10거래일**(60자리).
후보   그 자리에서 1년 고점 대비 −20~−50% 빠진 종목.
가름   **같은 자리 안에서** 그 잣대 위 절반과 아래 절반으로 가른다. 자리를 섞지 않는다.
성적   다음 날 시가에 사서 3개월·6개월·1년. **승률과 수익률 둘 다** 본다.

쓰는 법:  PYTHONIOENCODING=utf-8 python research/us_crash_wide_sweep.py
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
WINDOW = 10


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
    low52 = low.rolling(252, min_periods=252).min()
    from_high = (close / high52 - 1.0) * 100.0
    from_low = (close / low52 - 1.0) * 100.0
    sma20 = close.rolling(20, min_periods=20).mean()
    sma50 = close.rolling(50, min_periods=50).mean()
    sma150 = close.rolling(150, min_periods=150).mean()
    sma200 = close.rolling(200, min_periods=200).mean()
    above20 = (close > sma20).astype(float)
    above50 = (close > sma50).astype(float)
    above150 = (close > sma150).astype(float)
    above200 = (close > sma200).astype(float)
    aligned = ((close > sma50) & (sma50 > sma150) & (sma150 > sma200)
               & (sma200 > sma200.shift(20))).astype(float)
    rose5 = (close > close.shift(5)).astype(float)
    ret5 = (close / close.shift(5) - 1.0) * 100.0
    ret11 = (close / close.shift(11) - 1.0) * 100.0
    ret20 = (close / close.shift(20) - 1.0) * 100.0
    ret60 = (close / close.shift(60) - 1.0) * 100.0
    bounce = (close / low.rolling(20, min_periods=10).min() - 1.0) * 100.0
    money = (close * volume).rolling(20, min_periods=10).mean()
    money_surge = ((close * volume).rolling(5, min_periods=3).mean() / money)
    daily = close.pct_change()
    swing60 = daily.rolling(60, min_periods=30).std() * 100.0
    prev = close.shift(1)
    true_range = pd.concat([(high - low).abs(), (high - prev).abs(),
                            (low - prev).abs()]).groupby(level=0).max()
    atr_pct = true_range.rolling(14, min_periods=10).mean() / close * 100.0
    rets = {hold: (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
            for hold, _l in HOLDS}

    def by_theme(table: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame({n: table[m].mean(axis=1) for n, m in themes.items()})

    theme_tables = {
        "30주선 위": by_theme(above150), "덜 빠졌나": by_theme(from_high),
        "주봉 오름세": by_theme(aligned), "20일선 위": by_theme(above20),
        "5일 오른 비율": by_theme(rose5), "60일 수익률": by_theme(ret60),
    }
    # 종목마다 '자기 테마 중 가장 좋은 값' — 앱이 등수를 그렇게 쓴다.
    theme_best = {}
    for label, table in theme_tables.items():
        frame = pd.DataFrame(index=dates, columns=names, dtype=float)
        for ticker in names:
            mine = [n for n in belongs.get(ticker, []) if n in table.columns]
            if mine:
                frame[ticker] = table[mine].max(axis=1)
        theme_best[label] = frame

    FACTORS = (
        ("종목 · 덜 빠졌나(낙폭 얕음)",   lambda d, p: from_high.loc[d][p]),
        ("종목 · 최근 5일 오름",          lambda d, p: ret5.loc[d][p]),
        ("종목 · 최근 11일 오름",         lambda d, p: ret11.loc[d][p]),
        ("종목 · 최근 20일 오름",         lambda d, p: ret20.loc[d][p]),
        ("종목 · 최근 60일 오름",         lambda d, p: ret60.loc[d][p]),
        ("종목 · 바닥 대비 반등폭",       lambda d, p: bounce.loc[d][p]),
        ("종목 · 52주 저점 대비 위치",    lambda d, p: from_low.loc[d][p]),
        ("종목 · 거래대금(20일)",         lambda d, p: money.loc[d][p]),
        ("종목 · 거래대금 급증(5/20)",    lambda d, p: money_surge.loc[d][p]),
        ("종목 · 하루 오르내림 작음",     lambda d, p: -atr_pct.loc[d][p]),
        ("종목 · 60일 흔들림 작음",       lambda d, p: -swing60.loc[d][p]),
        ("종목 · 20일선 위",              lambda d, p: above20.loc[d][p]),
        ("종목 · 50일선 위",              lambda d, p: above50.loc[d][p]),
        ("종목 · 150일선 위",             lambda d, p: above150.loc[d][p]),
        ("종목 · 200일선 위",             lambda d, p: above200.loc[d][p]),
        ("종목 · 주봉 오름세",            lambda d, p: aligned.loc[d][p]),
        ("테마 · 30주선 위 ★지금 40점",   lambda d, p: theme_best["30주선 위"].loc[d][p]),
        ("테마 · 덜 빠졌나",              lambda d, p: theme_best["덜 빠졌나"].loc[d][p]),
        ("테마 · 주봉 오름세",            lambda d, p: theme_best["주봉 오름세"].loc[d][p]),
        ("테마 · 20일선 위",              lambda d, p: theme_best["20일선 위"].loc[d][p]),
        ("테마 · 5일 오른 비율",          lambda d, p: theme_best["5일 오른 비율"].loc[d][p]),
        ("테마 · 60일 수익률",            lambda d, p: theme_best["60일 수익률"].loc[d][p]),
    )

    def spots(window: int) -> list[pd.Timestamp]:
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

    def run(days, title):
        print("\n" + "=" * 108)
        print(f"{title} — 자리 {len(days)}개")
        print("=" * 108)
        head = f"{'잣대':<28}" + "".join(f"{label:>26}" for _h, label in HOLDS)
        print(head); print("─" * 106)
        for factor_name, getter in FACTORS:
            cells = []
            for hold, _label in HOLDS:
                hi_win, hi_ret, lo_win, lo_ret, better, pairs = [], [], [], [], 0, 0
                for day in days:
                    drop_today = from_high.loc[day]
                    ret_today = rets[hold].loc[day]
                    pool = [s for s in names
                            if pd.notna(drop_today.get(s))
                            and STOCK_BAND[0] <= drop_today[s] <= STOCK_BAND[1]
                            and belongs.get(s) and pd.notna(ret_today.get(s))]
                    if len(pool) < 12:
                        continue
                    values = getter(day, pool).astype(float)
                    values = values.dropna()
                    if len(values) < 12 or values.nunique() < 2:
                        continue
                    cut = values.median()
                    hi = list(values[values > cut].index)
                    lo = list(values[values <= cut].index)
                    if len(hi) < 3 or len(lo) < 3:
                        continue
                    hi_win.append(float((ret_today[hi] > 0).mean() * 100))
                    lo_win.append(float((ret_today[lo] > 0).mean() * 100))
                    hi_ret.append(float(np.median(ret_today[hi])))
                    lo_ret.append(float(np.median(ret_today[lo])))
                    better += 1 if hi_ret[-1] > lo_ret[-1] else 0
                    pairs += 1
                if pairs < 3:
                    cells.append("못 잼".rjust(26)); continue
                gap = mid(hi_ret) - mid(lo_ret)
                win_gap = mid(hi_win) - mid(lo_win)
                mark = ("▲" if better >= pairs * 0.7 and gap > 0 and win_gap > 0 else
                        "▼" if better <= pairs * 0.3 else "·")
                cells.append(f"{win_gap:+5.0f}번 {gap:+6.1f}%p {better}/{pairs}{mark}".rjust(26))
            print(f"{factor_name:<28}" + "".join(cells))
        print("\n   숫자 = (위 절반 − 아래 절반) 오른 횟수 차이 · 수익률 차이 · 이긴 자리/전체")
        print("   ▲ = 자리 열 중 일곱 이상에서 이겼고 승률·수익률 둘 다 앞선 것")

    run(spots(1), "㉮ 나스닥 저점 **바로 다음 날**")
    run(spots(WINDOW), f"㉯ 저점 뒤 {WINDOW}거래일 안 — 표본을 늘려 다시")


if __name__ == "__main__":
    main()
