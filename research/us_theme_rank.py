"""**어느 테마가 살아나는가**를 여러 방법으로 잡아 본다 (2026-08-07).

**왜 이걸 찾나.** 급락 후 반등에서 테마별 평균 성적이 신호일마다 **평균 85.9%p**
벌어졌다(가장 센 테마 +268% vs 가장 약한 테마 -21%인 날도 있었다). 지금까지 잰
어떤 배점 항목보다 크다. 그런데 지금 화면이 쓰는 '같은 테마에서 몇 개 걸렸나'는
급락일에 68%가 해당돼 좋은 테마와 나쁜 테마를 전혀 못 가른다.

**절대 문턱 대신 등수로 잡는다.** '테마 20일 10% 넘게 올랐음'은 합격했지만 그물의
7%뿐이었다 — 시장이 나쁜 해에는 10% 오른 테마가 아예 없기 때문이다. '그날 20개
테마 중 상위 3등 안'은 어느 해에나 같은 양이 걸린다.

모두 신호일까지의 값이다. 사는 것은 다음 거래일 시가다.

쓰는 법:  python research/us_theme_rank.py
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


def per_theme(frame: pd.DataFrame, themes: tuple, how: str = "mean") -> pd.DataFrame:
    """종목별 값을 테마별 값으로 모은다."""
    out = {}
    for theme in themes:
        members = [s for s in theme["stocks"] if s in frame.columns]
        if members:
            block = frame[members]
            out[theme["name"]] = block.mean(axis=1) if how == "mean" else block.sum(axis=1)
    return pd.DataFrame(out)


def top_rank(theme_values: pd.DataFrame, themes_of: dict[str, set],
             columns, top: int, *, bottom: bool = False) -> pd.DataFrame:
    """그날 테마를 줄 세워 상위(또는 하위) top등 안에 드는 테마에 속하면 True.

    bottom=True는 **뒤처진 테마**를 고른다 — 순환매라면 앞선 테마가 아니라
    뒤따라오는 테마가 나을 수도 있어서 같이 잰다(2026-08-07 상하님 지시).
    """
    ranks = theme_values.rank(axis=1, ascending=bool(bottom), method="min")
    winners = ranks <= top
    out = {}
    for stock in columns:
        names = [n for n in themes_of.get(stock, ()) if n in winners.columns]
        out[stock] = winners[names].any(axis=1) if names else False
    return pd.DataFrame(out, index=theme_values.index).fillna(False)


def main() -> None:
    import jarvis3_data as j3
    from us_yearly import fetch

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    qqq = wide["close"]["QQQ"]
    close, high, low = wide["close"][stocks], wide["high"][stocks], wide["low"][stocks]
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

    # ── 테마를 줄 세울 여러 잣대 (모두 그날까지의 값) ────────────────────
    turnover = close * wide["volume"][stocks]
    measures = {
        "5일 수익률": per_theme(close.pct_change(5) * 100, j3.US_THEMES),
        "20일 수익률": per_theme(close.pct_change(20) * 100, j3.US_THEMES),
        "60일 수익률": per_theme(close.pct_change(60) * 100, j3.US_THEMES),
        "덜 빠졌나(고점대비)": per_theme(from_high, j3.US_THEMES),
        "200일선 위 비율": per_theme(
            (close > close.rolling(200, min_periods=100).mean()).astype(float) * 100,
            j3.US_THEMES),
        "5일 오른 종목 비율": per_theme(
            (close.pct_change(5) > 0).astype(float) * 100, j3.US_THEMES),
        "거래대금 늘었나": per_theme(
            turnover.rolling(5, min_periods=3).mean()
            / turnover.rolling(60, min_periods=30).mean() * 100, j3.US_THEMES),
    }

    print(f"창 길이 {WINDOWS[0]}·{WINDOWS[1]}·{WINDOWS[2]}년 · 두 무리 각 {MIN_SIDE}건 이상 · "
          f"합격선 {PASS_MARK:.0f}%")
    print("칸은 '승률로 이긴 창% / 수익률로 이긴 창%(창 개수)'")
    print("테마 20개를 그날 줄 세워 상위 몇 등 안에 드는 테마에 속하면 해당.\n")

    # **테마 없는 종목은 아예 뺀다**(2026-08-07). 명부 200개 중 63개가 어느 테마에도
    # 안 속해, 넣어 두면 '테마 있는 종목 vs 없는 종목'을 재게 된다.
    has_theme = pd.DataFrame(
        np.repeat(np.array([[s in themes_of for s in close.columns]]), len(dates), axis=0),
        index=dates, columns=close.columns)
    print(f"명부 {len(stocks)}종목 중 테마 있는 것 {len(themes_of)}개만 쓴다.\n")

    for title, raw_net in (("상승장", breakout), ("급락 후 반등장", crash)):
        net = raw_net & has_theme
        in_net = net.to_numpy()
        print(f"\n{'=' * 108}\n### 미국 {title} — 테마 있는 종목 {int(in_net.sum()):,}자리"
              f"\n{'=' * 108}")
        print(f"  {'후보':<26}{'해당':>5}" + "".join(f"{y:>7}년       " for y in WINDOWS))
        for name, values in measures.items():
            for top, bottom in ((3, False), (5, False), (7, False),
                                (3, True), (5, True)):
                factor = top_rank(values, themes_of, close.columns, top, bottom=bottom)
                factor = factor.reindex(index=dates, columns=close.columns).fillna(False)
                share = float(factor.to_numpy()[in_net].mean() * 100)
                label = f"{name} {'하위' if bottom else '상위'} {top}등"
                show(label, share, score(returns, net, factor))
            print()


if __name__ == "__main__":
    main()
