"""상승장 그물의 **'신고가 뒤 며칠'**을 넓혀도 되는지 잰다 (2026-08-12 저녁).

상하님 지적 — *"S&P나 나스닥은 전고점을 뚫었는데 신고가 뚫었다가 며칠 몇 % 눌린
종목이 저렇게 없다는 게 이상하고 배점도 이상하다."*

**세어 보니 화면 숫자는 맞았다.** 명부 198종목 중 52주 신고가를 1~5일 전에 찍은
것이 16개다(오늘 찍은 것 6 · 6~20일 전 25 · 21~60일 전 50 · **61일 넘음 101**).
지수는 전고점인데 개별 대형주 절반은 두 달 넘게 신고가를 못 찍었다.

**그런데 그물이 좁은 것은 사실이다.** '1~5일'을 '1~20일'로 넓히면 후보가 두 배가
넘는다. 그리고 40점짜리 '눌린 폭 10~15%'는 16개 중 1개뿐이라 화면이 0점 천지다.

여기서 두 가지를 잰다. **둘 다 그물·배점을 바꾸는 일이라 재고 나서 여쭙는다.**

  [가] 신고가 뒤 며칠까지 봐도 되나 — 1~5일이 6~10일·11~20일보다 정말 나은가
  [나] 눌린 폭 칸을 하나 더 줄 수 있나 — 4~10% 칸이 값을 하는가

넓힌 그물(신고가 뒤 1~20일 · 눌린 폭 -4~-15% · 나스닥 200일선 위 + 고점 -10% 안)
**안에서** 견준다. 그래야 '넓혀도 되나'를 그 그물의 자로 재는 것이 된다.

쓰는 법:  python research/us_breakout_window.py
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
WIDE_WAIT = (3, 10)          # 상하님이 정하신 새 그물 (2026-08-12)
DROP_BAND = (-15.0, -4.0)    # 눌린 폭은 지금 그물 그대로


def main() -> None:
    import jarvis3_data as j3
    from us_yearly import fetch

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    close, high = wide["close"][stocks], wide["high"][stocks]
    opens, qqq = wide["open"][stocks], wide["close"]["QQQ"]
    dates = close.index

    sma20 = close.rolling(20, min_periods=20).mean()
    high52 = high.rolling(252, min_periods=252).max()
    from_high = (close / high52 - 1.0) * 100.0

    order = pd.DataFrame(np.arange(len(dates))[:, None].repeat(close.shape[1], axis=1),
                         index=dates, columns=close.columns)
    is_new_high = high >= high52.shift(1)
    peak = high.where(is_new_high).ffill()
    days_since = order - order.where(is_new_high).ffill()
    from_peak = (close / peak - 1.0) * 100.0

    qdrop = (qqq / qqq.rolling(252, min_periods=252).max() - 1.0) * 100.0
    up_day = (qqq > qqq.rolling(200, min_periods=200).mean()) & (
        qdrop > j3.BREAKOUT_MARKET_MAX_DROP)
    up_wide = pd.DataFrame(np.repeat(up_day.to_numpy()[:, None], close.shape[1], axis=1),
                           index=dates, columns=close.columns)

    themes_of: dict[str, set] = {}
    for theme in j3.US_THEMES:
        for stock in theme["stocks"]:
            if stock in close.columns:
                themes_of.setdefault(stock, set()).add(theme["name"])
    has_theme = pd.DataFrame(
        np.repeat(np.array([[s in themes_of for s in close.columns]]), len(dates), axis=0),
        index=dates, columns=close.columns)

    drop_lo, drop_hi = DROP_BAND
    wait_lo, wait_hi = WIDE_WAIT
    net = (up_wide & has_theme & (days_since >= wait_lo) & (days_since <= wait_hi)
           & (from_peak <= drop_hi) & (from_peak >= drop_lo)).fillna(False)
    total = int(net.to_numpy().sum())
    now_net = (up_wide & has_theme & (days_since >= 1) & (days_since <= 5)
               & (from_peak <= drop_hi) & (from_peak >= drop_lo)).fillna(False)

    rets = {hold: (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
            for hold, _ in HOLDS}

    print(f"\n{'=' * 112}\n### 상승장 그물을 '신고가 뒤 1~20일'로 넓혀서 잰다"
          f"\n### 넓힌 그물 {total:,}자리 (지금 1~5일 그물은 "
          f"{int(now_net.to_numpy().sum()):,}자리 — {total / max(int(now_net.to_numpy().sum()),1):.1f}배)"
          f"\n{'=' * 112}")

    def run(title: str, factors: dict) -> None:
        print(f"\n  ── {title} ──")
        print(f"     {'후보':<24}{'해당':>5}   " + "".join(f"{n:>10}" for _h, n in HOLDS))
        for name, factor in factors.items():
            factor = factor.reindex(index=dates, columns=close.columns).fillna(False)
            share = (factor.to_numpy() & net.to_numpy()).sum() / max(total, 1) * 100
            cells = ""
            for hold, _n in HOLDS:
                result = score(rets[hold], net, factor)
                worst = min((result[y]["win_worst"] for y in WINDOWS if result[y]),
                            default=float("nan"))
                mark = verdict(result).split()[0]
                cells += f"{mark:>6}{worst:>6.1f}"
            print(f"     {name:<24}{share:>4.0f}%   {cells}")

    # ── [가] 신고가 뒤 며칠 ─────────────────────────────────────────────
    run("[가] 신고가 뒤 며칠이 나은가 (넓힌 그물 안에서 견줌)", {
        "3~5일 전": (days_since >= 3) & (days_since <= 5),
        "6~10일 전": (days_since >= 6) & (days_since <= 10),
    })

    # ── [나] 눌린 폭 칸 ────────────────────────────────────────────────
    run("[나] 눌린 폭 칸마다 값을 하나", {
        "4~7% 눌림": (from_peak <= -4.0) & (from_peak > -7.0),
        "7~10% 눌림": (from_peak <= -7.0) & (from_peak > -10.0),
        "4~10% 눌림": (from_peak <= -4.0) & (from_peak > -10.0),
        "10~15% 눌림": (from_peak <= -10.0) & (from_peak >= -15.0),
    })

    # ── [다] 지금 배점 셋이 넓힌 그물에서도 통하나 ────────────────────────
    theme_values = {
        "같이 오르나(5일)": per_theme((close.pct_change(5) > 0).astype(float) * 100,
                                 j3.US_THEMES),
        "덜 빠졌나": per_theme(from_high, j3.US_THEMES),
        "20일선 위": per_theme((close > sma20).astype(float) * 100, j3.US_THEMES),
    }
    tops = {"덜 빠졌나": j3.THEME_LESS_DROP_TOP_N}
    run("[다] 지금 배점 셋이 넓힌 그물에서도 통하나", {
        f"테마 {name} 상위{tops.get(name, j3.THEME_RANK_TOP_N)}":
            top_rank(values, themes_of, close.columns, tops.get(name, j3.THEME_RANK_TOP_N))
        for name, values in theme_values.items()
    })

    print("\n  칸은 '판정  가장 나쁜 창의 승률차'. ○=합격 · △=안 됨 · ✗=거꾸로")
    print("  넓혀도 되려면 — '6~20일 전'이 거꾸로가 아니어야 한다"
          "(거꾸로면 넓히는 순간 나쁜 자리를 목록에 넣는 것이다).")


if __name__ == "__main__":
    main()
