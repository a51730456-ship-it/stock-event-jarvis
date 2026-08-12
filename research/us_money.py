"""점수를 높게 준 종목이 **실제로 벌었나** (2026-08-12 상하님 질문).

지금까지 잰 것은 전부 '그물 안 나머지보다 나은가'(상대)였다. 상하님이 물으신 것은
**'그래서 돈을 벌었나'**(절대)다. 다른 질문이다 — 상대로 이겨도 둘 다 잃으면 소용없다.

무엇을 견주나 (파트마다 셋)
  ① 그물 전체        — 그날 그물에 걸린 것을 다 샀을 때
  ② 지금 배점 상위 3 — 앱이 오늘 화면에 올리는 방식 그대로
  ③ 새 배점 상위 3   — 2026-08-12 실측으로 합격한 항목만 계단(40·30·20·10)에 얹은 것
  ④ QQQ             — 같은 날 사서 같은 기간 들었을 때 (아무것도 안 고른 경우)

사는 것은 **신호 다음 거래일 시가**, 파는 것은 **정해진 거래일 뒤 종가**다
(설명서 규칙 그대로). 배당은 auto_adjust로 이미 들어 있다.

쓰는 법:  python research/us_money.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

from us_theme_rank import per_theme, top_rank  # noqa: E402

TOP_K = 3       # 그날 점수 상위 몇 개를 살 것인가


def clamp(frame, points):
    return frame.clip(lower=0.0, upper=points)


def scale(value, low, high, points):
    return clamp((value - low) / (high - low) * points, points)


def report(title: str, rows: list) -> None:
    print(f"\n{'=' * 96}\n### {title}\n{'=' * 96}")
    print(f"  {'무엇을 샀나':<22}{'건수':>7}{'번 중 이김':>12}{'가운데 수익':>13}"
          f"{'평균 수익':>12}{'가장 나쁜 해':>13}")
    for name, series, yearly in rows:
        series = series.dropna()
        if series.empty:
            print(f"  {name:<22}{'—':>7}")
            continue
        worst = f"{min(yearly.values()):+.1f}%" if yearly else "—"
        print(f"  {name:<22}{len(series):>7,}{(series > 0).mean() * 100:>11.1f}번"
              f"{series.median():>12.1f}%{series.mean():>11.1f}%{worst:>13}")


def by_year(picks: pd.Series) -> dict:
    """해마다 가운데 수익률. '어느 해에 무너졌나'를 보려는 것이다."""
    if picks.empty:
        return {}
    frame = picks.reset_index()
    frame.columns = ["date", "value"]
    return {int(y): float(g["value"].median())
            for y, g in frame.groupby(frame["date"].dt.year) if len(g) >= 5}


def picked_returns(score: pd.DataFrame, net: pd.DataFrame,
                   returns: pd.DataFrame, top: int) -> pd.Series:
    """그날 점수 상위 `top`개를 샀을 때의 실현 수익률들."""
    masked = score.where(net)
    rank = masked.rank(axis=1, ascending=False, method="first")
    chosen = (rank <= top) & net
    values = returns.where(chosen).stack()
    values.index = values.index.droplevel(1)
    return values.sort_index()


def all_returns(net: pd.DataFrame, returns: pd.DataFrame) -> pd.Series:
    values = returns.where(net).stack()
    values.index = values.index.droplevel(1)
    return values.sort_index()


def main() -> None:
    import jarvis3_data as j3
    from us_yearly import fetch

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    qqq = wide["close"]["QQQ"]
    qqq_open = wide["open"]["QQQ"]
    close, high, low = wide["close"][stocks], wide["high"][stocks], wide["low"][stocks]
    volume = wide["volume"][stocks]
    opens = wide["open"][stocks]
    dates = close.index

    order = pd.DataFrame(np.arange(len(dates))[:, None].repeat(close.shape[1], axis=1),
                         index=dates, columns=close.columns)
    high52 = high.rolling(252, min_periods=252).max()
    at_high = high >= high52
    days_ago = order - order.where(at_high).ffill()
    from_high = (close / high52 - 1.0) * 100.0
    sma20 = close.rolling(20, min_periods=20).mean()
    sma50 = close.rolling(50, min_periods=50).mean()
    sma200 = close.rolling(200, min_periods=200).mean()
    prev = close.shift(1)
    true_range = pd.concat([(high - low).stack(), (high - prev).abs().stack(),
                            (low - prev).abs().stack()], axis=1).max(axis=1).unstack()
    atr_pct = true_range.rolling(14, min_periods=14).mean() / close * 100.0
    turnover = close * volume
    dollar = turnover.rolling(50, min_periods=20).mean()
    recent11 = (close / close.shift(11) - 1.0) * 100.0
    gap20 = (close / sma20 - 1.0).abs() * 100.0

    themes_of: dict[str, set] = {}
    for theme in j3.US_THEMES:
        for stock in theme["stocks"]:
            if stock in close.columns:
                themes_of.setdefault(stock, set()).add(theme["name"])
    has_theme = pd.DataFrame(
        np.repeat(np.array([[s in themes_of for s in close.columns]]), len(dates), axis=0),
        index=dates, columns=close.columns)
    theme_count = pd.DataFrame(
        np.repeat(np.array([[len(themes_of.get(s, ())) for s in close.columns]]),
                  len(dates), axis=0), index=dates, columns=close.columns)

    spread5 = per_theme((close.pct_change(5) > 0).astype(float) * 100, j3.US_THEMES)
    less_drop = per_theme(from_high, j3.US_THEMES)
    ret60_theme = per_theme(close.pct_change(60) * 100, j3.US_THEMES)
    above20 = per_theme((close > sma20).astype(float) * 100, j3.US_THEMES)

    def rank_flag(values, top):
        return top_rank(values, themes_of, close.columns, top).reindex(
            index=dates, columns=close.columns).fillna(False)

    def together(net):
        counts = pd.DataFrame(0, index=dates, columns=close.columns)
        for theme in j3.US_THEMES:
            members = [s for s in theme["stocks"] if s in close.columns]
            if not members:
                continue
            n = net[members].sum(axis=1)
            for stock in members:
                counts[stock] = np.maximum(counts[stock], n)
        return counts

    def qqq_returns(net, hold):
        """그물에 신호가 난 날짜마다 QQQ를 샀을 때."""
        base = (qqq.shift(-hold) / qqq_open.shift(1).shift(-1) - 1.0) * 100.0
        signal_days = net.any(axis=1)
        return base.where(signal_days).dropna()

    def run(title, net, hold, score_now, score_new):
        net = (net & has_theme).fillna(False)
        rets = (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
        every = all_returns(net, rets)
        now = picked_returns(score_now, net, rets, TOP_K)
        new = picked_returns(score_new, net, rets, TOP_K)
        bench = qqq_returns(net, hold)
        report(f"{title} · {hold}거래일 보유", [
            ("① 그물 전체", every, by_year(every)),
            (f"② 지금 배점 상위{TOP_K}", now, by_year(now)),
            (f"③ 새 배점 상위{TOP_K}", new, by_year(new)),
            ("④ QQQ (안 고름)", bench, by_year(bench)),
        ])

    # ── 상승장 ──────────────────────────────────────────────────────────
    wait_lo, wait_hi = j3.BREAKOUT_PULLBACK_RULE["wait_days"]
    drop_lo, drop_hi = j3.BREAKOUT_PULLBACK_RULE["drop_band"]
    b_net = ((days_ago >= wait_lo) & (days_ago <= wait_hi)
             & (from_high >= drop_lo) & (from_high <= drop_hi))
    b_count = together(b_net & has_theme)
    w = j3.BREAKOUT_SCORE_WEIGHTS
    b_now = (np.where(b_count >= 3, w["together"], np.where(b_count >= 1, w["together"] * .5, 0.0))
             + scale(-recent11, -5.0, 5.0, w["recent_drop"])
             + scale(dollar / 1e9, 0.05, 1.0, w["liquidity"])
             + scale(-atr_pct, -8.0, -2.0, w["volatility"]))
    b_new = (rank_flag(spread5, 5) * 40.0
             + rank_flag(less_drop, 3) * 30.0
             + ((from_high <= -10) & (from_high >= -15)) * 20.0
             + (b_count >= 4) * 10.0)
    run("미국 상승장 (신고가 뒤 1~5일 · −4~−15%)", b_net, 120, b_now, b_new)

    # ── 눌림목 찾기 ─────────────────────────────────────────────────────
    p_net = ((close >= sma50 * 0.97) & (sma50 > sma200) & (close > sma200)
             & (days_ago >= 1) & (days_ago <= 20) & (from_high < -0.5))
    recency = np.where(days_ago <= 10, 25.0,
                       np.where(days_ago >= 60, 0.0, 25.0 * (1 - (days_ago - 10) / 50)))
    proximity = (20.0 * (1 - (gap20 - 1.5).clip(lower=0) / 7.5)).clip(lower=0)
    trend = (close > sma50) * 10.0 + (close > sma200) * 10.0
    depth = np.where((from_high >= -20) & (from_high <= -4), 20.0,
                     np.where(((from_high >= -28) & (from_high < -20))
                              | ((from_high > -4) & (from_high <= -2)), 12.0, 3.0))
    p_now = (pd.DataFrame(recency, index=dates, columns=close.columns) + proximity + trend
             + pd.DataFrame(depth, index=dates, columns=close.columns)
             + scale(dollar, 2e7, 5e8, 10.0)
             + (theme_count - 1).clip(lower=0).mul(2.5).clip(upper=5.0))
    p_new = (rank_flag(spread5, 5) * 40.0
             + rank_flag(less_drop, 5) * 30.0
             + ((from_high <= -5) & (from_high >= -10)) * 20.0
             + (theme_count >= 2) * 10.0)
    run("미국 눌림목 찾기 (50일선 위 · 신고가 뒤 1~20일)", p_net, 120, p_now, p_new)

    # ── 급락 후 반등 ────────────────────────────────────────────────────
    qqq_drop = (qqq / qqq.rolling(252, min_periods=252).max() - 1.0) * 100.0
    band_lo, band_hi = j3.CRASH_MARKET_BAND
    in_band = (qqq_drop <= band_hi) & (qqq_drop >= band_lo)
    episode = (in_band & ~in_band.shift(1, fill_value=False)).cumsum().where(in_band)
    deepest = pd.Series(False, index=dates)
    for _, group in pd.DataFrame({"e": episode, "d": qqq_drop}).dropna().groupby("e"):
        deepest.loc[group["d"].idxmin()] = True
    deep = pd.DataFrame(np.repeat(deepest.to_numpy()[:, None], close.shape[1], axis=1),
                        index=dates, columns=close.columns)
    c_lo, c_hi = j3.CRASH_REBOUND_RULES[0]["band"]
    c_net = deep & (from_high <= c_hi) & (from_high >= c_lo)
    c_hold = j3.CRASH_REBOUND_RULES[0]["hold_days"]
    c_count = together(c_net & has_theme)
    cw = j3.CRASH_SCORE_WEIGHTS
    c_now = (np.where(c_count >= 4, cw["together"],
                      np.where(c_count >= 2, cw["together"] * .5, 0.0))
             + rank_flag(ret60_theme, 5) * cw["theme_rank"]
             + scale(dollar / 1e9, 0.05, 1.0, cw["liquidity"])
             + scale(-atr_pct, -8.0, -2.0, cw["volatility"]))
    c_new = (rank_flag(less_drop, 3) * 40.0
             + rank_flag(spread5, 5) * 30.0
             + rank_flag(ret60_theme, 5) * 20.0
             + rank_flag(above20, 3) * 10.0)
    run("미국 급락 후 반등 (나스닥 −10~−20% 최저일 · 종목 −20~−30%)",
        c_net, c_hold, c_now, c_new)

    print("\n※ 사는 것은 신호 다음 거래일 시가, 파는 것은 정해진 거래일 뒤 종가."
          "\n※ 명부 198종목 · 2016-08~2026-08 10년 · 살아남은 대형주만(망한 종목 없음).")


if __name__ == "__main__":
    main()
