"""미국테마 **파트별로, 앱이 실제로 쓰는 그물 그대로** 배점 후보를 잰다 (2026-08-12).

왜 새로 만드나 — 기존 `us_verify.py`는 상승장 그물에 **시장 조건**(나스닥 200일선 위 ·
고점 대비 −10% 안)을 넣어 걸렀는데, 앱(`find_breakout_pullback_stocks`)은 시장을
**안 거른다**(BREAKOUT_MARKET_MAX_DROP은 "알려만 준다"). 그물이 다르면 그 안에 걸리는
종목이 달라지고 어느 항목이 값을 하는지도 달라진다.
`us_cond_check.py`도 그물을 '고점 대비 −45~0%'로 잡았는데, 앱의 눌림목 그물은
50일선 위 · 50>200 · 200일선 위 · 신고가 뒤 1~20일이다. 전혀 다르다.

**앱과 한 줄씩 맞춘 것**(jarvis3_data._series_metrics · find_* 함수)
  high52        = 최근 252일 **High**의 최대값
  high52_days_ago = 그 최대값을 찍고 며칠 지났나
  from_high_pct = (오늘 종가 / high52 − 1) × 100
  sma50·sma200  = 최근 50·200일 **종가** 평균

  상승장   days_ago 1~5 · from_high −15~−4                     (시장 조건 없음)
  눌림목   종가 ≥ sma50×0.97 · sma50 > sma200 · 종가 > sma200
           · days_ago 1~20 · from_high < −0.5
  테마순위 그물 없음 — 명부 전체. 국면(나스닥 200일선 위/아래)으로 갈라 잰다.

잣대는 `us_verify.py`에 못박힌 것 그대로다 — 창 2·3·4년, 그물 안에서 견주기,
승률·수익률 둘 다 65%↑.

쓰는 법:  python research/us_parts.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

from us_verify import MIN_SIDE, PASS_MARK, WINDOWS, score, verdict  # noqa: E402
from us_theme_rank import per_theme, top_rank  # noqa: E402

HOLD = 120          # 앱의 상승장 보유기간. 눌림목·테마순위는 규칙에 보유가 없어 같은 값을 쓴다.
SHARE_HIGH = 85.0   # 해당 비율이 이보다 높으면 못 가른다 (기준 11)
SHARE_LOW = 10.0    # 이보다 낮아도 못 쓴다


def show(name: str, share: float, result: dict) -> tuple:
    cells = ""
    worst = []
    for years in WINDOWS:
        item = result.get(years)
        if not item:
            cells += f"{'—':^15}"
            continue
        cells += f"{item['win_share']:>4.0f}/{item['median_share']:>3.0f}%({item['n']:>3})"
        worst.append(item["win_worst"])
    mark = verdict(result)
    if mark == "○ 합격" and not (SHARE_LOW <= share <= SHARE_HIGH):
        mark = "✎ 못 가름"          # 합격이어도 거의 전부/거의 없음이면 순위를 못 가른다
    worst_text = f"{min(worst):+6.1f}p" if worst else "     —"
    print(f"  {name:<30}{share:>4.0f}%  {cells}  {mark:<10} 최악 {worst_text}")
    return mark, (min(worst) if worst else None)


def main() -> None:
    import jarvis3_data as j3
    from us_yearly import fetch

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    qqq = wide["close"]["QQQ"]
    close = wide["close"][stocks]
    high = wide["high"][stocks]
    low = wide["low"][stocks]
    volume = wide["volume"][stocks]
    dates = close.index

    returns = (close.shift(-HOLD) / wide["open"][stocks].shift(-1) - 1.0) * 100.0

    # ── 앱과 같은 방식으로 지표를 만든다 ────────────────────────────────
    order = pd.DataFrame(np.arange(len(dates))[:, None].repeat(close.shape[1], axis=1),
                         index=dates, columns=close.columns)
    high52 = high.rolling(252, min_periods=252).max()
    at_high = high >= high52                       # 오늘이 52주 신고가 날
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
    gain60 = (close / close.shift(60) - 1.0) * 100.0
    gap20 = (close / sma20 - 1.0).abs() * 100.0

    # ── 앱의 그물 그대로 ───────────────────────────────────────────────
    wait_lo, wait_hi = j3.BREAKOUT_PULLBACK_RULE["wait_days"]
    drop_lo, drop_hi = j3.BREAKOUT_PULLBACK_RULE["drop_band"]
    breakout_net = ((days_ago >= wait_lo) & (days_ago <= wait_hi)
                    & (from_high >= drop_lo) & (from_high <= drop_hi))

    pullback_net = ((close >= sma50 * 0.97) & (sma50 > sma200) & (close > sma200)
                    & (days_ago >= 1) & (days_ago <= 20) & (from_high < -0.5))

    themes_of: dict[str, set] = {}
    for theme in j3.US_THEMES:
        for stock in theme["stocks"]:
            if stock in close.columns:
                themes_of.setdefault(stock, set()).add(theme["name"])
    has_theme = pd.DataFrame(
        np.repeat(np.array([[s in themes_of for s in close.columns]]), len(dates), axis=0),
        index=dates, columns=close.columns)

    # ── 테마를 줄 세울 잣대들 (모두 그날까지의 값) ──────────────────────
    measures = {
        "테마 덜 빠졌나": per_theme(from_high, j3.US_THEMES),
        "테마 오른 종목 비율(5일)": per_theme(
            (close.pct_change(5) > 0).astype(float) * 100, j3.US_THEMES),
        "테마 오른 종목 비율(20일)": per_theme(
            (close.pct_change(20) > 0).astype(float) * 100, j3.US_THEMES),
        "테마 20일선 위 비율": per_theme(
            (close > sma20).astype(float) * 100, j3.US_THEMES),
        "테마 20일 수익률": per_theme(close.pct_change(20) * 100, j3.US_THEMES),
        "테마 60일 수익률": per_theme(close.pct_change(60) * 100, j3.US_THEMES),
        "테마 거래대금 늘었나": per_theme(
            turnover.rolling(5, min_periods=3).mean()
            / turnover.rolling(60, min_periods=30).mean() * 100, j3.US_THEMES),
    }

    def together(net: pd.DataFrame) -> pd.DataFrame:
        """같은 테마에서 함께 걸린 종목 수 (앱의 _attach_theme_together와 같은 뜻)."""
        counts = pd.DataFrame(0, index=dates, columns=close.columns)
        for theme in j3.US_THEMES:
            members = [s for s in theme["stocks"] if s in close.columns]
            if not members:
                continue
            n = net[members].sum(axis=1)
            for stock in members:
                counts[stock] = np.maximum(counts[stock], n)
        return counts

    def run(title: str, net: pd.DataFrame, factors: dict,
            rets: pd.DataFrame | None = None, hold: int = HOLD) -> None:
        rets = returns if rets is None else rets
        net = (net & has_theme).fillna(False)
        total = int(net.to_numpy().sum())
        print(f"\n{'=' * 112}\n### {title} — 그물 안 {total:,}자리 · {hold}거래일 보유\n{'=' * 112}")
        print(f"  {'후보':<28}{'해당':>5}" + "".join(f"{y:>8}년       " for y in WINDOWS))
        passed = []
        for name, factor in factors.items():
            factor = factor.reindex(index=dates, columns=close.columns).fillna(False)
            inside = net.to_numpy()
            share = (factor.to_numpy() & inside).sum() / max(inside.sum(), 1) * 100
            mark, worst = show(name, share, score(rets, net, factor))
            if mark == "○ 합격":
                passed.append((worst, name, share))
        print()
        if passed:
            passed.sort(key=lambda item: -item[0])
            print(f"  ▶ 합격 {len(passed)}개 — 가장 나쁜 창이 좋은 순")
            for rank, (worst, name, share) in enumerate(passed, 1):
                print(f"     {rank}. {name}  (최악 {worst:+.1f}p · 해당 {share:.0f}%)")
        else:
            print("  ▶ 합격 0개")

    def theme_factors(net: pd.DataFrame) -> dict:
        out = {}
        for label, values in measures.items():
            for top in (3, 5):
                out[f"{label} 상위 {top}등"] = top_rank(
                    values, themes_of, close.columns, top)
        return out

    # ── ① 상승장 ────────────────────────────────────────────────────────
    counts = together(breakout_net & has_theme)
    factors = {
        "같은 테마 동반 2개↑": counts >= 2,
        "같은 테마 동반 3개↑": counts >= 3,
        "같은 테마 동반 4개↑": counts >= 4,
        "신고가 뒤 1~3일": days_ago <= 3,
        "눌린 폭 4~6%": (from_high > -6) & (from_high <= -4),
        "눌린 폭 6~10%": (from_high > -10) & (from_high <= -6),
        "눌린 폭 10~15%": from_high <= -10,
        "최근 11일 안 올랐음": recent11 <= 0,
        "최근 11일 -5%↑ 빠짐": recent11 <= -5,
        "60일 40%↑ 오름": gain60 >= 40,
        "변동성 3% 미만": atr_pct < 3,
        "변동성 6%↑": atr_pct >= 6,
        "거래대금 5억달러↑": dollar >= 5e8,
        "거래대금 상위 절반": dollar.rank(axis=1, pct=True, ascending=False) <= 0.5,
    }
    factors.update(theme_factors(breakout_net))
    run("미국 상승장 (앱 그물: 신고가 뒤 1~5일 · −4~−15% · 시장조건 없음)",
        breakout_net, factors)

    # ── ② 눌림목 찾기 ───────────────────────────────────────────────────
    counts_p = together(pullback_net & has_theme)
    factors = {
        "같은 테마 동반 2개↑": counts_p >= 2,
        "같은 테마 동반 3개↑": counts_p >= 3,
        "두 테마 이상 소속": pd.DataFrame(
            np.repeat(np.array([[len(themes_of.get(s, ())) >= 2 for s in close.columns]]),
                      len(dates), axis=0), index=dates, columns=close.columns),
        "신고가 뒤 1~5일": days_ago <= 5,
        "신고가 뒤 1~10일": days_ago <= 10,
        "20일선 이격 2% 이내": gap20 <= 2,
        "20일선 이격 5% 이내": gap20 <= 5,
        "눌린 깊이 2~5%": (from_high > -5) & (from_high <= -2),
        "눌린 깊이 5~10%": (from_high > -10) & (from_high <= -5),
        "눌린 깊이 10~20%": (from_high > -20) & (from_high <= -10),
        "최근 11일 안 올랐음": recent11 <= 0,
        "변동성 3% 미만": atr_pct < 3,
        "변동성 6%↑": atr_pct >= 6,
        "거래대금 5억달러↑": dollar >= 5e8,
        "거래대금 상위 절반": dollar.rank(axis=1, pct=True, ascending=False) <= 0.5,
    }
    factors.update(theme_factors(pullback_net))
    run("미국 눌림목 찾기 (앱 그물: 50일선 위 · 50>200 · 200일선 위 · 신고가 뒤 1~20일)",
        pullback_net, factors)

    # ── ③ 급락 후 반등 — 앱 그물(나스닥 −10~−20% 가장 깊은 날 · 종목 −20~−30%) ──
    # us_score_new.py가 이미 쟀지만 **확산 계열을 안 쟀다.** 다른 네 파트에서 확산이
    # 1등이라 여기만 빠지면 표가 비뚤어진다.
    qqq_drop = (qqq / qqq.rolling(252, min_periods=252).max() - 1.0) * 100.0
    band_lo, band_hi = j3.CRASH_MARKET_BAND
    in_band = (qqq_drop <= band_hi) & (qqq_drop >= band_lo)
    episode = (in_band & ~in_band.shift(1, fill_value=False)).cumsum().where(in_band)
    deepest = pd.Series(False, index=dates)
    for _, group in pd.DataFrame({"e": episode, "d": qqq_drop}).dropna().groupby("e"):
        deepest.loc[group["d"].idxmin()] = True
    deep = pd.DataFrame(np.repeat(deepest.to_numpy()[:, None], close.shape[1], axis=1),
                        index=dates, columns=close.columns)
    crash_lo, crash_hi = j3.CRASH_REBOUND_RULES[0]["band"]
    crash_net = deep & (from_high <= crash_hi) & (from_high >= crash_lo)
    crash_hold = j3.CRASH_REBOUND_RULES[0]["hold_days"]

    crash_returns = (close.shift(-crash_hold) / wide["open"][stocks].shift(-1) - 1.0) * 100.0
    counts_c = together(crash_net & has_theme)
    factors = {"같은 테마 동반 3개↑": counts_c >= 3, "같은 테마 동반 4개↑": counts_c >= 4}
    factors.update(theme_factors(crash_net))
    run("미국 급락 후 반등 (앱 그물: 나스닥 −10~−20% 최저일 · 종목 −20~−30%)",
        crash_net, factors, rets=crash_returns, hold=crash_hold)

    # ── ④ 테마 순위 — 그물 없음. 국면으로 갈라 잰다 ──────────────────────
    # 상하님 지적: "테마 수익률이 하락장에는 의미가 없지." 실제로 갈리는지 본다.
    up = qqq > qqq.rolling(200, min_periods=200).mean()
    up_wide = pd.DataFrame(np.repeat(up.to_numpy()[:, None], close.shape[1], axis=1),
                           index=dates, columns=close.columns)
    enough = close.notna() & sma200.notna()
    for label, phase in (("나스닥 200일선 **위**", up_wide),
                         ("나스닥 200일선 **아래**", ~up_wide)):
        run(f"미국 테마 순위 — 그물 없음 · 국면: {label}",
            enough & phase, theme_factors(enough & phase))


if __name__ == "__main__":
    main()
