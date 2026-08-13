"""상승장(신고가 눌림) — **승률·수익률과 진짜 관계있는 것**을 넓게 훑는다.

상하님 지시 (2026-08-13) — *"실제 승률과 수익률과 관계가 있는 것을 넣어야 되는데
너가 자꾸 기준을 너무 크게 바꿔 버리니 답답하다. **보강**을 해야 되는데 …
일단 승률 수익률과 관계있는 것을 검색해서 답을 낼 수 있겠냐? 이거 제일 핵심이잖아."*

**기준은 안 바꾼다.** 자(`us_verify.score`)도 그물도 그대로 두고, **후보만 넓힌다.**
지금 배점 셋으로는 그물의 절반이 0점이라 순위가 안 생긴다. 0점을 줄이려고 근거
없는 항목을 도로 넣는 대신, **근거 있는 항목을 더 찾는 것**이 이 파일의 목적이다.

## 그물 (지금 앱 그대로)

  나스닥 200일선 위 + 고점 -10% 안 · 신고가 뒤 3~10일 · 눌린 폭 -4~-15%
  어느 테마에도 안 속한 종목은 뺀다

## 합격선 (안 바꾼다)

  창 2·3·4년을 한 달씩 밀고, 그 그물 안에서 견주고,
  승률·수익률 **둘 다** 65% 이상의 창에서 이겨야 합격.
  보유는 20일·3개월·6개월·1년 넷을 다 본다 — 파는 시점을 앱이 안 정하므로
  **여러 기간에서 살아남은 것만** 쓸 수 있다.

## 훑는 것 (마흔 가지 남짓)

  눌린 폭 칸 · 눌림의 모양(며칠에 걸쳐 · 거래량 줄었나 · 갭)
  · 신고가 전에 얼마나 올랐나 · 신고가를 몇 번 찍었나
  · 이동평균 자리(20·50·150·200일선 · 주봉 오름세) · 20일선 이격
  · 변동성 칸 · 거래대금 칸 · 크기 계층
  · 테마 등수 네 가지 × 상위 3·5·7등

쓰는 법:  python research/us_breakout_hunt.py
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
from us_verify import WINDOWS, score, verdict  # noqa: E402

HOLDS = ((20, "20일"), (60, "3개월"), (120, "6개월"), (250, "1년"))


def main() -> None:
    import jarvis3_data as j3
    from us_shares import load as load_shares
    from us_yearly import fetch

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    close, high, low = wide["close"][stocks], wide["high"][stocks], wide["low"][stocks]
    opens, volume = wide["open"][stocks], wide["volume"][stocks]
    qqq = wide["close"]["QQQ"]
    dates = close.index

    sma20 = close.rolling(20, min_periods=20).mean()
    sma50 = close.rolling(50, min_periods=50).mean()
    sma150 = close.rolling(150, min_periods=150).mean()
    sma200 = close.rolling(200, min_periods=200).mean()
    aligned = ((close > sma50) & (sma50 > sma150) & (sma150 > sma200)
               & (sma200 > sma200.shift(20)))

    high52 = high.rolling(252, min_periods=252).max()
    from_high = (close / high52 - 1.0) * 100.0
    order = pd.DataFrame(np.arange(len(dates))[:, None].repeat(close.shape[1], axis=1),
                         index=dates, columns=close.columns)
    is_new_high = high >= high52.shift(1)
    peak = high.where(is_new_high).ffill()
    days_since = order - order.where(is_new_high).ffill()
    from_peak = (close / peak - 1.0) * 100.0

    prev = close.shift(1)
    true_range = pd.concat([(high - low).stack(), (high - prev).abs().stack(),
                            (low - prev).abs().stack()], axis=1).max(axis=1).unstack()
    atr = true_range.rolling(14, min_periods=10).mean() / close * 100.0
    turnover = (close * volume).rolling(20, min_periods=10).mean()
    vol_now = volume.rolling(3, min_periods=2).mean() / volume.rolling(
        20, min_periods=10).mean()
    gap = (opens / prev - 1.0) * 100.0
    down_days = (close < prev).rolling(5, min_periods=3).sum()
    gain60 = (close / close.shift(60) - 1.0) * 100.0
    gain120 = (close / close.shift(120) - 1.0) * 100.0
    new_high_60 = is_new_high.rolling(60, min_periods=30).sum()
    gap20 = (close / sma20 - 1.0) * 100.0
    shares = load_shares().reindex(close.columns)
    cap_rank = close.mul(shares, axis=1).rank(axis=1, ascending=False, method="min")

    themes_of: dict[str, set] = {}
    for theme in j3.US_THEMES:
        for stock in theme["stocks"]:
            if stock in close.columns:
                themes_of.setdefault(stock, set()).add(theme["name"])
    has_theme = pd.DataFrame(
        np.repeat(np.array([[s in themes_of for s in close.columns]]), len(dates), axis=0),
        index=dates, columns=close.columns)

    qdrop = (qqq / qqq.rolling(252, min_periods=252).max() - 1.0) * 100.0
    up_day = (qqq > qqq.rolling(200, min_periods=200).mean()) & (
        qdrop > j3.BREAKOUT_MARKET_MAX_DROP)
    up_wide = pd.DataFrame(np.repeat(up_day.to_numpy()[:, None], close.shape[1], axis=1),
                           index=dates, columns=close.columns)
    wait_lo, wait_hi = j3.BREAKOUT_PULLBACK_RULE["wait_days"]
    drop_lo, drop_hi = j3.BREAKOUT_PULLBACK_RULE["drop_band"]
    net = (up_wide & has_theme & (days_since >= wait_lo) & (days_since <= wait_hi)
           & (from_peak <= drop_hi) & (from_peak >= drop_lo)).fillna(False)
    total = int(net.to_numpy().sum())

    # ── 후보 ────────────────────────────────────────────────────────────
    cands: dict[str, pd.DataFrame] = {}

    def add(name, mask):
        cands[name] = mask

    for lo, hi in ((-6.0, -4.0), (-8.0, -6.0), (-10.0, -8.0),
                   (-12.0, -10.0), (-15.0, -12.0)):
        add(f"눌린 폭 {abs(hi):.0f}~{abs(lo):.0f}%", (from_peak <= hi) & (from_peak > lo))
    add("눌린 폭 10~15%", (from_peak <= -10.0) & (from_peak >= -15.0))
    add("눌린 폭 8~15%", (from_peak <= -8.0) & (from_peak >= -15.0))

    for lo, hi in ((3, 5), (6, 8), (9, 10)):
        add(f"신고가 뒤 {lo}~{hi}일", (days_since >= lo) & (days_since <= hi))

    add("눌리며 거래량 줄었다 (3일/20일 <0.9)", vol_now < 0.9)
    add("눌리며 거래량 늘었다 (>1.2)", vol_now > 1.2)
    add("최근 5일 음봉 3일↑", down_days >= 3)
    add("최근 5일 음봉 2일↓", down_days <= 2)
    add("갭하락 없었다 (오늘 갭 >-1%)", gap > -1.0)

    add("60일 20%↓ 올랐다", gain60 <= 20.0)
    add("60일 20~50% 올랐다", (gain60 > 20.0) & (gain60 <= 50.0))
    add("60일 50%↑ 올랐다", gain60 > 50.0)
    add("120일 30%↑ 올랐다", gain120 > 30.0)
    add("60일 안 신고가 5번↑", new_high_60 >= 5)
    add("60일 안 신고가 10번↑", new_high_60 >= 10)

    add("20일선 위", close > sma20)
    add("20일선 이격 ±3% 안", gap20.abs() <= 3.0)
    add("50일선 위", close > sma50)
    add("200일선 위", close > sma200)
    add("주봉 오름세 (정배열)", aligned)

    add("변동성 3% 이내", atr <= 3.0)
    add("변동성 3~5%", (atr > 3.0) & (atr <= 5.0))
    add("변동성 5%↑", atr > 5.0)
    add("거래대금 3억달러↑", turnover >= 3e8)
    add("거래대금 10억달러↑", turnover >= 1e9)
    add("빅50 안", cap_rank <= 50)
    add("101위 아래", cap_rank > 100)

    theme_values = {
        "테마 같이 오르나(5일)": per_theme((close.pct_change(5) > 0).astype(float) * 100,
                                     j3.US_THEMES),
        "테마 덜 빠졌나": per_theme(from_high, j3.US_THEMES),
        "테마 20일선 위": per_theme((close > sma20).astype(float) * 100, j3.US_THEMES),
        "테마 주봉 오름세": per_theme(aligned.astype(float) * 100, j3.US_THEMES),
        "테마 20일 수익률": per_theme(close.pct_change(20) * 100, j3.US_THEMES),
    }
    for name, values in theme_values.items():
        for top in (3, 5, 7):
            add(f"{name} 상위{top}",
                top_rank(values, themes_of, close.columns, top))

    # ── 잰다 ────────────────────────────────────────────────────────────
    rets = {hold: (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
            for hold, _ in HOLDS}
    print(f"\n{'=' * 108}\n### 미국 상승장 — 승률·수익률과 관계있는 것 찾기"
          f"\n### 그물 {total:,}자리 (신고가 뒤 {wait_lo}~{wait_hi}일 · 눌린 폭 "
          f"{abs(drop_hi):.0f}~{abs(drop_lo):.0f}%)\n{'=' * 108}")
    print(f"  {'후보':<30}{'해당':>5}   " + "".join(f"{n:>12}" for _h, n in HOLDS)
          + "   합격")

    rows = []
    for name, mask in cands.items():
        factor = mask.reindex(index=dates, columns=close.columns).fillna(False)
        share = (factor.to_numpy() & net.to_numpy()).sum() / max(total, 1) * 100
        cells, passes = "", 0
        for hold, _n in HOLDS:
            result = score(rets[hold], net, factor)
            mark = verdict(result).split()[0]
            worst = min((result[y]["win_worst"] for y in WINDOWS if result[y]),
                        default=float("nan"))
            cells += f"{mark:>6}{worst:>6.1f}"
            passes += mark == "○"
        usable = 10.0 <= share <= 85.0
        flag = "" if usable else "  ← 해당 비율이 못 가름"
        print(f"  {name:<30}{share:>4.0f}%   {cells}{passes:>5}/4{flag}")
        rows.append((passes, share, name, usable))

    print(f"\n{'=' * 108}\n### 쓸 수 있는 것 (합격 2개 이상 · 해당 10~85%)\n{'=' * 108}")
    for passes, share, name, usable in sorted(rows, reverse=True):
        if passes >= 2 and usable:
            print(f"  {passes}/4 합격 · 해당 {share:>3.0f}%   {name}")
    print("\n  ○=합격 · △=안 됨 · ✗=거꾸로. 숫자는 그 보유기간에서 가장 나빴던 창의 승률차.")


if __name__ == "__main__":
    main()
