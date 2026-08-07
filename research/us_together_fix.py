"""'같은 테마 동반'을 제대로 재 본다 (2026-08-07 상하님 재지적).

**앞서 잰 것에 구멍이 둘 있다.**

  ① **테마 없는 종목이 비교군에 섞였다.** 명부 200종목 중 63개는 어느 테마에도
     안 속해 동반이 늘 1개로 잡힌다. 그러면 '3개 이상 vs 나머지'가 실은
     '테마 있는 종목 vs 테마 없는 종목'을 재는 것이 된다. **테마 있는 종목끼리만**
     견줘야 한다.

  ② **개수는 테마 크기에 휘둘린다.** 빅테크10은 10종목, 사이버보안은 7종목이다.
     같은 3개라도 뜻이 다르다 — 큰 테마는 그냥 확률적으로 3개를 채운다.
     **비율**(걸린 수 ÷ 테마 구성종목 수)로 재야 크기가 상쇄된다.
     (상하님이 2026-08-06에 이미 짚으신 문제다.)

여기서는 그 둘을 고쳐 다시 잰다. 그래도 값이 없으면 그때 0점을 말할 수 있다.

쓰는 법:  python research/us_together_fix.py
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
            if stock in close.columns:
                themes_of.setdefault(stock, set()).add(theme["name"])
    size_of = {theme["name"]: len([s for s in theme["stocks"] if s in close.columns])
               for theme in j3.US_THEMES}
    has_theme = pd.DataFrame(
        np.repeat(np.array([[s in themes_of for s in close.columns]]), len(dates), axis=0),
        index=dates, columns=close.columns)
    print(f"명부 {len(stocks)}종목 중 테마 있는 것 {len(themes_of)}개 · "
          f"없는 것 {len(stocks) - len(themes_of)}개")
    print("→ **테마 있는 종목끼리만** 견준다. 없는 종목은 아예 빼고 잰다.\n")

    def counts_and_share(mask: pd.DataFrame):
        """걸린 개수와, 테마 구성종목 대비 걸린 비율."""
        columns = list(mask.columns)
        array = mask.to_numpy()
        count_out = np.zeros(array.shape, dtype="float32")
        share_out = np.zeros(array.shape, dtype="float32")
        for row in np.nonzero(array.any(axis=1))[0]:
            picked = np.nonzero(array[row])[0]
            codes = [columns[i] for i in picked]
            tally: dict[str, int] = {}
            for code in codes:
                for theme in themes_of.get(code, ()):
                    tally[theme] = tally.get(theme, 0) + 1
            best_count, best_share = [], []
            for code in codes:
                names = [t for t in themes_of.get(code, ()) if t in tally]
                best_count.append(max((tally[t] for t in names), default=0))
                best_share.append(max((tally[t] / size_of[t] * 100 for t in names),
                                      default=0.0))
            count_out[row, picked] = best_count
            share_out[row, picked] = best_share
        return (pd.DataFrame(count_out, index=dates, columns=mask.columns),
                pd.DataFrame(share_out, index=dates, columns=mask.columns))

    print(f"창 길이 {WINDOWS[0]}·{WINDOWS[1]}·{WINDOWS[2]}년 · 두 무리 각 {MIN_SIDE}건 이상 · "
          f"합격선 {PASS_MARK:.0f}%")
    print("칸은 '승률로 이긴 창% / 수익률로 이긴 창%(창 개수)'\n")

    for title, raw_net in (("급락 후 반등장", crash), ("상승장", breakout)):
        net = raw_net & has_theme          # ← 테마 있는 종목만
        count, share = counts_and_share(net)
        in_net = net.to_numpy()
        total = int(in_net.sum())
        share_values = share.to_numpy()[in_net]
        print(f"\n{'=' * 108}\n### 미국 {title} — 테마 있는 종목만 {total:,}자리"
              f"  (테마 구성종목 대비 걸린 비율 가운데값 {np.median(share_values):.0f}%)"
              f"\n{'=' * 108}")
        print(f"  {'후보':<26}{'해당':>5}" + "".join(f"{y:>7}년       " for y in WINDOWS))
        candidates = [(f"개수 {n}개↑", count >= n) for n in (2, 3, 4, 5, 6)]
        candidates += [(f"비율 {p}%↑ 걸림", share >= p) for p in (30, 40, 50, 60, 70)]
        for name, factor in candidates:
            factor = factor.fillna(False).astype(bool)
            got = float(factor.to_numpy()[in_net].mean() * 100)
            show(name, got, score(returns, net, factor))
            if name == "개수 6개↑":
                print()


if __name__ == "__main__":
    main()
