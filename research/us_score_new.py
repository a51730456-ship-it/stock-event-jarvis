"""**새 그물** 위에서 미국 배점을 다시 잰다 (2026-08-07).

2026-08-07에 미국 급락 후 반등 그물을 격자로 다시 잡았다 —
나스닥 -10~-20% 국면의 가장 깊은 날 · 종목 -20~-30% · 250거래일.
그런데 배점은 옛 그물(-6~-12% · -20~-50% · 120일)에서 잰 값 그대로였다.
그물이 바뀌면 그 안에 걸리는 종목이 달라지고 어느 항목이 값을 하는지도 달라진다.

방법은 못박아 둔 그대로다 — 창 2·3·4년, **그물 안에서** 비교, 합격선 65%.

쓰는 법:  python research/us_score_new.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

from us_verify import MIN_SIDE, PASS_MARK, WINDOWS, score, show  # noqa: E402


def main() -> None:
    import jarvis3_data as j3
    from us_theme_rank import per_theme, top_rank
    from us_yearly import fetch

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    qqq = wide["close"]["QQQ"]
    close, high = wide["close"][stocks], wide["high"][stocks]
    dates = close.index
    hold = j3.CRASH_REBOUND_RULES[0]["hold_days"]
    returns = (close.shift(-hold) / wide["open"][stocks].shift(-1) - 1.0) * 100.0

    from_high = (close / high.rolling(252, min_periods=252).max() - 1.0) * 100.0
    qqq_drop = (qqq / qqq.rolling(252, min_periods=252).max() - 1.0) * 100.0
    band_lo, band_hi = j3.CRASH_MARKET_BAND
    in_band = (qqq_drop <= band_hi) & (qqq_drop >= band_lo)
    episode = (in_band & ~in_band.shift(1, fill_value=False)).cumsum().where(in_band)
    deepest = pd.Series(False, index=dates)
    for _, group in pd.DataFrame({"e": episode, "d": qqq_drop}).dropna().groupby("e"):
        deepest.loc[group["d"].idxmin()] = True
    deep = pd.DataFrame(np.repeat(deepest.to_numpy()[:, None], close.shape[1], axis=1),
                        index=dates, columns=close.columns)
    low, high_band = j3.CRASH_REBOUND_RULES[0]["band"]
    net = deep & (from_high <= high_band) & (from_high >= low)

    themes_of: dict[str, set] = {}
    for theme in j3.US_THEMES:
        for stock in theme["stocks"]:
            if stock in close.columns:
                themes_of.setdefault(stock, set()).add(theme["name"])
    has_theme = pd.DataFrame(
        np.repeat(np.array([[s in themes_of for s in close.columns]]), len(dates), axis=0),
        index=dates, columns=close.columns)
    net = (net & has_theme).fillna(False)

    recent11 = (close / close.shift(11) - 1.0) * 100.0
    gain60 = (close / close.shift(60) - 1.0) * 100.0
    turnover = close * wide["volume"][stocks]
    flow = (turnover.rolling(5, min_periods=3).mean()
            / turnover.rolling(60, min_periods=30).mean() * 100)
    prev = close.shift(1)
    true_range = pd.concat([(high - wide["low"][stocks]).stack(),
                            (high - prev).abs().stack(),
                            (wide["low"][stocks] - prev).abs().stack()],
                           axis=1).max(axis=1).unstack()
    atr = true_range.rolling(14, min_periods=10).mean() / close * 100.0

    ret20 = per_theme(close.pct_change(20) * 100, j3.US_THEMES)
    ret60 = per_theme(close.pct_change(60) * 100, j3.US_THEMES)
    theme_flow = per_theme(flow, j3.US_THEMES)
    theme_drop = per_theme(from_high, j3.US_THEMES)

    def rank(values, top):
        frame = top_rank(values, themes_of, close.columns, top)
        return frame.reindex(index=dates, columns=close.columns).fillna(False).astype(bool)

    def together(mask):
        columns = list(mask.columns)
        array = mask.to_numpy()
        out = np.zeros(array.shape, dtype="int16")
        for row in np.nonzero(array.any(axis=1))[0]:
            picked = np.nonzero(array[row])[0]
            codes = [columns[i] for i in picked]
            tally: dict[str, int] = {}
            for code in codes:
                for name in themes_of.get(code, ()):
                    tally[name] = tally.get(name, 0) + 1
            out[row, picked] = [
                max((tally[n] for n in themes_of.get(code, ()) if n in tally), default=0)
                for code in codes
            ]
        return pd.DataFrame(out, index=dates, columns=mask.columns)

    pair = together(net)
    print(f"### 미국 급락 후 반등장 (새 그물) — 테마 있는 종목 "
          f"{int(net.to_numpy().sum()):,}자리 · {hold}거래일 보유")
    print(f"나스닥 {band_hi:.0f}~{band_lo:.0f}% 가장 깊은 날 · 종목 "
          f"{high_band:.0f}~{low:.0f}%\n")
    print(f"  {'후보':<26}{'해당':>5}" + "".join(f"{y:>7}년       " for y in WINDOWS))
    for name, factor in (
        ("테마 동반 3개↑", pair >= 3),
        ("테마 동반 4개↑", pair >= 4),
        ("최근 11일 -5%↑ 빠짐", recent11 <= -5.0),
        ("최근 11일 안 올랐음", recent11 <= 0.0),
        ("60일 안 올랐음", gain60 <= 0.0),
        ("변동성 4% 미만", atr <= 4.0),
        ("변동성 6%↑", atr >= 6.0),
        ("테마 20일 상위 3등", rank(ret20, 3)),
        ("테마 20일 상위 5등", rank(ret20, 5)),
        ("테마 60일 상위 5등", rank(ret60, 5)),
        ("테마 거래대금 상위 3등", rank(theme_flow, 3)),
        ("테마 덜 빠짐 상위 3등", rank(theme_drop, 3)),
    ):
        factor = factor.reindex(index=dates, columns=close.columns).fillna(False).astype(bool)
        got = float(factor.to_numpy()[net.to_numpy()].mean() * 100)
        show(name, got, score(returns, net, factor))


if __name__ == "__main__":
    main()
