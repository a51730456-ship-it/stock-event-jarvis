"""테마를 **오르는 쪽으로** 재 본다 (2026-08-07 상하님 지적).

**무엇이 잘못이었나.** 지금까지 '같은 테마 동반'을 *그물에 같이 걸린 개수*로 셌다.
급락일에 그렇게 세면 **같이 떨어진 개수**를 세는 것이다 — 폭락하면 같은 테마가
우르르 떨어지니 당연히 68%가 걸리고, 아무것도 고르지 못한다.

상하님 말씀 — "급락 후 반등이나 상승장에서 테마를 잡아봐라, 또 다르지."
맞다. 테마가 값을 하는 건 **같이 올라올 때**다. 그래서 그날까지의 시세로
'이 테마가 살아나고 있나'를 재서 다시 본다.

**앞을 훔쳐보지 않는다** — 모두 신호일까지의 값이다. 사는 것은 다음 거래일 시가다.

재는 방법 다섯
  ① 테마 최근 3일 평균 수익률   — 막 돌아서고 있나
  ② 테마 최근 5일 평균 수익률   — 반등이 붙었나
  ③ 테마 최근 20일 평균 수익률  — 추세가 살아 있나
  ④ 테마 종목 중 그날 오른 비율 — 오늘 몇 명이나 올랐나
  ⑤ 테마가 시장보다 나은가      — 20일 수익률이 지수보다 위인가
한 종목이 여러 테마에 속하면 **가장 센 테마**의 값을 쓴다.

쓰는 법:  python research/us_theme_strength.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

from us_verify import (MIN_SIDE, MIN_WINDOWS, PASS_MARK, WINDOWS,  # noqa: E402
                       score, show)


def theme_series(close: pd.DataFrame, themes: tuple, days: int) -> pd.DataFrame:
    """테마마다 '구성종목의 최근 N일 수익률 평균'을 만든다."""
    change = close.pct_change(days) * 100.0
    out = {}
    for theme in themes:
        members = [s for s in theme["stocks"] if s in change.columns]
        if members:
            out[theme["name"]] = change[members].mean(axis=1)
    return pd.DataFrame(out)


def spread(per_theme: pd.DataFrame, themes_of: dict[str, set],
           columns) -> pd.DataFrame:
    """테마별 값을 종목별로 편다. 여러 테마면 **가장 센 테마**의 값."""
    out = {}
    for stock in columns:
        names = [n for n in themes_of.get(stock, ()) if n in per_theme.columns]
        out[stock] = per_theme[names].max(axis=1) if names else np.nan
    return pd.DataFrame(out, index=per_theme.index)


def main() -> None:
    import jarvis3_data as j3
    from us_yearly import fetch

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    qqq = wide["close"]["QQQ"]
    close, high = wide["close"][stocks], wide["high"][stocks]
    dates = close.index
    returns = (close.shift(-120) / wide["open"][stocks].shift(-1) - 1.0) * 100.0

    order = pd.DataFrame(np.arange(len(dates))[:, None].repeat(close.shape[1], axis=1),
                         index=dates, columns=close.columns)
    is_new_high = high >= high.rolling(252, min_periods=252).max().shift(1)
    peak = high.where(is_new_high).ffill()
    days_since = order - order.where(is_new_high).ffill()
    from_peak = (close / peak - 1.0) * 100.0
    from_high = (close / high.rolling(252, min_periods=252).max() - 1.0) * 100.0

    qqq_drop = (qqq / qqq.rolling(252, min_periods=252).max() - 1.0) * 100.0
    up_day = (qqq > qqq.rolling(200, min_periods=200).mean()) & (qqq_drop > -10.0)
    up_wide = pd.DataFrame(np.repeat(up_day.to_numpy()[:, None], close.shape[1], axis=1),
                           index=dates, columns=close.columns)
    wait_lo, wait_hi = j3.BREAKOUT_PULLBACK_RULE["wait_days"]
    drop_lo, drop_hi = j3.BREAKOUT_PULLBACK_RULE["drop_band"]
    breakout = (up_wide & (days_since >= wait_lo) & (days_since <= wait_hi)
                & (from_peak <= drop_hi) & (from_peak >= drop_lo))

    band_lo, band_hi = j3.CRASH_MARKET_BAND
    in_band = (qqq_drop <= band_hi) & (qqq_drop >= band_lo)
    episode = (in_band & ~in_band.shift(1, fill_value=False)).cumsum().where(in_band)
    deepest = pd.Series(False, index=dates)
    for _, group in pd.DataFrame({"e": episode, "d": qqq_drop}).dropna().groupby("e"):
        deepest.loc[group["d"].idxmin()] = True
    deep = pd.DataFrame(np.repeat(deepest.to_numpy()[:, None], close.shape[1], axis=1),
                        index=dates, columns=close.columns)
    crash = deep & (from_high <= -20.0) & (from_high >= -50.0)

    themes_of: dict[str, set] = {}
    for theme in j3.US_THEMES:
        for stock in theme["stocks"]:
            themes_of.setdefault(stock, set()).add(theme["name"])

    # ── 테마가 얼마나 살아 있나 (모두 그날까지의 값) ──────────────────────
    ret3 = spread(theme_series(close, j3.US_THEMES, 3), themes_of, close.columns)
    ret5 = spread(theme_series(close, j3.US_THEMES, 5), themes_of, close.columns)
    ret20 = spread(theme_series(close, j3.US_THEMES, 20), themes_of, close.columns)
    daily_up = (close > close.shift(1))
    up_share = {}
    for theme in j3.US_THEMES:
        members = [s for s in theme["stocks"] if s in close.columns]
        if members:
            up_share[theme["name"]] = daily_up[members].mean(axis=1) * 100.0
    share = spread(pd.DataFrame(up_share), themes_of, close.columns)
    market20 = (qqq.pct_change(20) * 100.0)
    beats = ret20.sub(market20, axis=0)

    print(f"창 길이 {WINDOWS[0]}·{WINDOWS[1]}·{WINDOWS[2]}년 · 두 무리 각 {MIN_SIDE}건 이상 · "
          f"창 {MIN_WINDOWS}개 이상 · 합격선 {PASS_MARK:.0f}%")
    print("칸은 '승률로 이긴 창% / 수익률로 이긴 창%(창 개수)'")
    print("테마가 없는 종목(명부 200개 중 63개)은 값이 없어 '아닌 쪽'으로 간다.\n")

    for title, net in (("상승장", breakout), ("급락 후 반등장", crash)):
        in_net = net.to_numpy()
        print(f"\n{'=' * 108}\n### 미국 {title} — 그물에 걸린 자리 {int(in_net.sum()):,}개"
              f"\n{'=' * 108}")
        print(f"  {'후보':<26}{'해당':>5}" + "".join(f"{y:>7}년       " for y in WINDOWS))
        candidates = [
            ("테마 3일 올랐음(>0)", ret3 > 0),
            ("테마 3일 1%↑ 올랐음", ret3 >= 1.0),
            ("테마 5일 올랐음(>0)", ret5 > 0),
            ("테마 5일 2%↑ 올랐음", ret5 >= 2.0),
            ("테마 20일 올랐음(>0)", ret20 > 0),
            ("테마 20일 5%↑ 올랐음", ret20 >= 5.0),
            ("테마 20일 10%↑ 올랐음", ret20 >= 10.0),
            ("테마가 지수보다 나음", beats > 0),
            ("테마가 지수보다 5%p↑", beats >= 5.0),
            ("테마 절반↑이 그날 올랐음", share >= 50.0),
            ("테마 70%↑가 그날 올랐음", share >= 70.0),
            # 견주기 위해 옛 방식도 같이 둔다
            ("[옛] 그물에 같이 걸린 4개↑", None),
        ]
        together = None
        for name, factor in candidates:
            if factor is None:
                columns = list(net.columns)
                array = net.to_numpy()
                counted = np.zeros(array.shape, dtype="int16")
                for row in np.nonzero(array.any(axis=1))[0]:
                    picked = np.nonzero(array[row])[0]
                    codes = [columns[i] for i in picked]
                    tally: dict[str, int] = {}
                    for code in codes:
                        for theme in themes_of.get(code, ()):
                            tally[theme] = tally.get(theme, 0) + 1
                    counted[row, picked] = [
                        max((tally[t] for t in themes_of.get(code, ()) if t in tally),
                            default=1) for code in codes
                    ]
                together = pd.DataFrame(counted, index=dates, columns=net.columns)
                factor = together >= 4
            factor = factor.fillna(False).astype(bool)
            share_pct = float(factor.to_numpy()[in_net].mean() * 100)
            show(name, share_pct, score(returns, net, factor))


if __name__ == "__main__":
    main()
