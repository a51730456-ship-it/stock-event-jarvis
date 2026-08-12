"""급락 후 반등 — **빨리 오르나 · 많이 오르나**로 다시 잰다 (2026-08-12 상하님 지시).

상하님 말씀 — *"반등은 어떤 종목들이 반등을 빨리하느냐, 어느 만큼 많이 오르냐가
기준이 되겠지. 다시 검토해라."*

**맞는 지적이고, 속도는 여태 한 번도 안 쟀다.** 지금까지 쓴 자(`us_verify.score`)는
"3개월·6개월·1년 **뒤** 수익률"만 봤다. 6개월 뒤 같은 자리에 있어도, 한 달 만에
올라 다섯 달을 기다린 것과 다섯 달을 기다렸다 마지막에 오른 것은 전혀 다르다.
급락 후 반등에서는 그 차이가 곧 돈이다(묶인 돈 · 견디는 시간).

## 두 가지를 따로 본다

**[빨리]**
  · 5 · 10 · 20 · 40거래일 뒤 수익률 — 못박은 자(창 2·3·4년 · 승률/수익률 65%)로 합격 판정
  · **+20%에 닿기까지 걸린 날 수** — 1년 안에 닿은 비율과, 닿은 것들의 가운데 날 수
  · **급락 전 고점 회복까지 걸린 날 수** — 신호일의 52주 최고가로 되돌아오기까지

**[많이]**
  · 1년 뒤 수익률 가운데값
  · 1년 안 **최고 상승폭** 가운데값 — 들고 있는 동안 얼마나 크게 벌 자리를 줬나

## 후보

테마 잣대 넷(덜 빠졌나 · 같이 오르는가 · 20일선 위 · 주봉 정배열)에
**크기 계층**과 **낙폭 깊이 · 변동성**을 더한다. 상하님이 물으신 빅10 이야기가
'많이 오르냐'에서 갈릴 수 있어서다.

사는 것은 늘 **다음 거래일 시가**다.

쓰는 법:  python research/us_rebound_speed.py
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

FAST_HOLDS = ((5, "5일"), (10, "10일"), (20, "20일"), (40, "40일"))
BIG_HOLDS = ((120, "6개월"), (250, "1년"))
HORIZON = 250          # 속도를 볼 때 앞으로 보는 최대 거래일
TARGET_GAIN = 20.0     # '빨리 올랐다'의 기준 — 다음날 시가 대비 +20%


def build() -> dict:
    import jarvis3_data as j3
    from us_shares import load as load_shares
    from us_yearly import fetch

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    close, high, low = wide["close"][stocks], wide["high"][stocks], wide["low"][stocks]
    opens, volume = wide["open"][stocks], wide["volume"][stocks]
    qqq = wide["close"]["QQQ"]
    dates = close.index

    high52 = high.rolling(252, min_periods=252).max()
    from_high = (close / high52 - 1.0) * 100.0
    qdrop = (qqq / qqq.rolling(252, min_periods=252).max() - 1.0) * 100.0

    sma20 = close.rolling(20, min_periods=20).mean()
    sma50 = close.rolling(50, min_periods=50).mean()
    sma150 = close.rolling(150, min_periods=150).mean()
    sma200 = close.rolling(200, min_periods=200).mean()
    aligned = ((close > sma50) & (sma50 > sma150) & (sma150 > sma200)
               & (sma200 > sma200.shift(20)))

    prev = close.shift(1)
    true_range = pd.concat([(high - low).stack(), (high - prev).abs().stack(),
                            (low - prev).abs().stack()], axis=1).max(axis=1).unstack()
    atr = true_range.rolling(14, min_periods=10).mean() / close * 100.0
    turnover = (close * volume).rolling(20, min_periods=10).mean()

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

    crash_lo = min(rule["band"][0] for rule in j3.CRASH_REBOUND_RULES)
    crash_hi = max(rule["band"][1] for rule in j3.CRASH_REBOUND_RULES)
    market_lo, market_hi = j3.CRASH_MARKET_BAND
    market = ((qdrop <= market_hi) & (qdrop >= market_lo)).fillna(False)
    market_wide = pd.DataFrame(
        np.repeat(market.to_numpy()[:, None], close.shape[1], axis=1),
        index=dates, columns=close.columns)
    net = (market_wide & has_theme & (from_high <= crash_hi)
           & (from_high >= crash_lo)).fillna(False)

    # ── 후보 잣대 ────────────────────────────────────────────────────────
    theme_values = {
        "테마 덜 빠졌나": per_theme(from_high, j3.US_THEMES),
        "테마 같이 오르나(5일)": per_theme(
            (close.pct_change(5) > 0).astype(float) * 100, j3.US_THEMES),
        "테마 20일선 위": per_theme((close > sma20).astype(float) * 100, j3.US_THEMES),
        "테마 주봉 정배열": per_theme(aligned.astype(float) * 100, j3.US_THEMES),
    }
    factors: dict[str, pd.DataFrame] = {
        f"{name} 상위5": top_rank(values, themes_of, close.columns, 5).reindex(
            index=dates, columns=close.columns).fillna(False)
        for name, values in theme_values.items()
    }
    factors.update({
        "종목 주봉 정배열": aligned.fillna(False),
        "종목 20일선 위": (close > sma20).fillna(False),
        "빅10": (cap_rank <= 10).fillna(False),
        "빅50 안": (cap_rank <= 50).fillna(False),
        "101위 아래": (cap_rank > 100).fillna(False),
        "낙폭 -30% 아래(깊게 빠짐)": (from_high <= -30.0).fillna(False),
        "변동성 큼(ATR 4%↑)": (atr >= 4.0).fillna(False),
        "변동성 작음(ATR 2.5%↓)": (atr <= 2.5).fillna(False),
        "거래대금 상위 50": turnover.rank(axis=1, ascending=False,
                                     method="min").le(50).fillna(False),
    })

    return {"dates": dates, "close": close, "opens": opens, "high": high,
            "high52": high52, "net": net, "factors": factors}


def part_fast_marks(env: dict) -> None:
    """[빨리 ①] 짧은 보유에서 합격하나 — 못박은 자 그대로."""
    close, opens, net = env["close"], env["opens"], env["net"]
    print(f"\n{'=' * 118}\n### [빨리 ①] **짧게 들고 있어도** 이기나"
          f"  (창 2·3·4년 · 승률/수익률 둘 다 65%↑라야 합격)\n{'=' * 118}")
    rets = {hold: (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
            for hold, _ in FAST_HOLDS + BIG_HOLDS}
    total = int(net.to_numpy().sum())
    print(f"  급락 그물 {total:,}자리\n")
    header = "".join(f"{label:>9}" for _, label in FAST_HOLDS + BIG_HOLDS)
    print(f"  {'후보':<26}{'해당':>5}{header}")
    for name, factor in env["factors"].items():
        share = (factor.to_numpy() & net.to_numpy()).sum() / max(total, 1) * 100
        cells = ""
        for hold, _ in FAST_HOLDS + BIG_HOLDS:
            mark = verdict(score(rets[hold], net, factor))
            cells += f"{mark.split()[0]:>9}"
        print(f"  {name:<26}{share:>4.0f}%{cells}")
    print("\n  ○=합격 · △=안 됨 · ✗=거꾸로 · 판정=자리가 모자라 판정 못 함")


def part_speed(env: dict) -> None:
    """[빨리 ②·③] 며칠 만에 +20%인가 · 며칠 만에 전 고점 회복인가."""
    close, opens, high = env["close"], env["opens"], env["high"]
    high52, net = env["high52"], env["net"]

    close_a = close.to_numpy(dtype="float64")
    high_a = high.to_numpy(dtype="float64")
    buy_a = opens.shift(-1).to_numpy(dtype="float64")
    peak_a = high52.to_numpy(dtype="float64")
    net_a = net.to_numpy()
    rows, cols = np.nonzero(net_a)
    keep = rows + 1 < len(close_a) - 5
    rows, cols = rows[keep], cols[keep]

    n = rows.size
    days_gain = np.full(n, np.nan)
    days_back = np.full(n, np.nan)
    best = np.full(n, np.nan)
    for i in range(n):
        row, col = rows[i], cols[i]
        buy = buy_a[row, col]
        if not np.isfinite(buy) or buy <= 0:
            continue
        stop = min(row + 1 + HORIZON, len(close_a))
        window_high = high_a[row + 1:stop, col]
        window_close = close_a[row + 1:stop, col]
        if window_high.size == 0:
            continue
        best[i] = np.nanmax(window_high) / buy * 100.0 - 100.0
        hit = np.nonzero(window_high >= buy * (1 + TARGET_GAIN / 100.0))[0]
        if hit.size:
            days_gain[i] = hit[0] + 1
        target = peak_a[row, col]
        if np.isfinite(target):
            back = np.nonzero(window_close >= target)[0]
            if back.size:
                days_back[i] = back[0] + 1

    print(f"\n\n{'=' * 118}\n### [빨리 ②·③ / 많이] 그룹별 실제 모습"
          f"  (1년 안 · 다음날 시가에 사서)\n{'=' * 118}")
    print(f"  {'후보':<26}{'해당':>5}"
          f"{'+20% 닿음':>10}{'닿기까지':>9}{'고점회복':>9}{'회복까지':>9}"
          f"{'최고상승폭':>11}{'1년 수익':>9}")
    ret250 = ((close.shift(-250) / opens.shift(-1) - 1.0) * 100.0).to_numpy()[rows, cols]

    def line(name: str, pick: np.ndarray) -> None:
        if pick.sum() < 200:
            print(f"  {name:<26}{pick.mean() * 100:>4.0f}%   (자리가 적어 건너뜀)")
            return
        hit_share = np.isfinite(days_gain[pick]).mean() * 100
        hit_days = np.nanmedian(days_gain[pick])
        back_share = np.isfinite(days_back[pick]).mean() * 100
        back_days = np.nanmedian(days_back[pick])
        print(f"  {name:<26}{pick.mean() * 100:>4.0f}%"
              f"{hit_share:>9.0f}%{hit_days:>8.0f}일{back_share:>8.0f}%{back_days:>8.0f}일"
              f"{np.nanmedian(best[pick]):>10.1f}%{np.nanmedian(ret250[pick]):>8.1f}%")

    line("── 그물 전체(견줄 바탕) ──", np.ones(n, dtype=bool))
    print()
    for name, factor in env["factors"].items():
        pick = factor.to_numpy()[rows, cols]
        line(name, pick)
        rest = ~pick
        if rest.sum() >= 200:
            hit_days = np.nanmedian(days_gain[pick]) - np.nanmedian(days_gain[rest])
            back_days = np.nanmedian(days_back[pick]) - np.nanmedian(days_back[rest])
            gap_best = np.nanmedian(best[pick]) - np.nanmedian(best[rest])
            print(f"  {'  └ 나머지와 차이':<26}     "
                  f"{'':>9}{hit_days:>+8.0f}일{'':>9}{back_days:>+8.0f}일"
                  f"{gap_best:>+10.1f}%"
                  f"{np.nanmedian(ret250[pick]) - np.nanmedian(ret250[rest]):>+8.1f}%")

    print("\n  · '+20% 닿음' = 1년 안에 다음날 시가보다 20% 위를 한 번이라도 찍은 비율")
    print("  · '고점회복' = 급락 전 52주 최고가를 되찾은 비율 / 걸린 날 수")
    print("  · '차이'의 날 수는 **작을수록(마이너스일수록) 빠르다**")


def main() -> None:
    env = build()
    part_fast_marks(env)
    part_speed(env)


if __name__ == "__main__":
    main()
