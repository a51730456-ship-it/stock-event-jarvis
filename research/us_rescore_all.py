"""**네 파트를 각각** 10년치로 다시 재고 배점을 새로 매긴다 (2026-08-13 상하님 지시).

*"처음부터 각 점수 파트별로 10년치 검색하고 난 뒤 배점을 정하는 게 맞는지를
생각하고 진행해야 되."* — 맞다. 그물이 파트마다 다르니 파트마다 따로 잰다.

## 논리 (상하님과 정한 것)

  1단계 걸러내기 — 창 2·3·4년을 한 달씩 밀고, 승률·수익률 **둘 다** 65% 이상
                 창에서 이겨야 통과. 못 넘으면 0점. (`us_verify`와 같은 규칙)
  2단계 줄 세우기 — 통과한 것만 놓고 **승률차 크기**로 40·30·20·10.
                 승률차와 수익률차를 **각각** 표로 남긴다.
  단서 — 해당 비율 85%↑·10%↓는 못 가르므로 뺀다(기준 6).
        여러 보유기간에서 살아남은 것만 쓴다 — 파는 시점을 앱이 안 정한다(기준 마).

쓰는 법:  python research/us_rescore_all.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

from us_edge_table import ladder, report  # noqa: E402
from us_theme_rank import per_theme, top_rank  # noqa: E402


def main() -> None:
    import jarvis3_data as j3
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
    gain60 = (close / close.shift(60) - 1.0) * 100.0
    down_days = (close < prev).rolling(5, min_periods=3).sum()
    recent11 = (close / close.shift(11) - 1.0) * 100.0

    themes_of: dict[str, set] = {}
    for theme in j3.US_THEMES:
        for stock in theme["stocks"]:
            if stock in close.columns:
                themes_of.setdefault(stock, set()).add(theme["name"])
    has_theme = pd.DataFrame(
        np.repeat(np.array([[s in themes_of for s in close.columns]]), len(dates), axis=0),
        index=dates, columns=close.columns)

    theme_values = {
        "테마 같이 오르나": per_theme((close.pct_change(5) > 0).astype(float) * 100,
                                j3.US_THEMES),
        "테마 덜 빠졌나": per_theme(from_high, j3.US_THEMES),
        "테마 20일선 위": per_theme((close > sma20).astype(float) * 100, j3.US_THEMES),
        "테마 주봉 오름세": per_theme(aligned.astype(float) * 100, j3.US_THEMES),
    }

    def theme_factors(tops=(3, 5, 7)) -> dict:
        out = {}
        for name, values in theme_values.items():
            for top in tops:
                out[f"{name} 상위{top}"] = top_rank(values, themes_of, close.columns, top)
        return out

    qdrop = (qqq / qqq.rolling(252, min_periods=252).max() - 1.0) * 100.0

    # ── 파트 2 · 상승장 ─────────────────────────────────────────────────
    up_day = (qqq > qqq.rolling(200, min_periods=200).mean()) & (
        qdrop > j3.BREAKOUT_MARKET_MAX_DROP)
    up_wide = pd.DataFrame(np.repeat(up_day.to_numpy()[:, None], close.shape[1], axis=1),
                           index=dates, columns=close.columns)
    wait_lo, wait_hi = j3.BREAKOUT_PULLBACK_RULE["wait_days"]
    drop_lo, drop_hi = j3.BREAKOUT_PULLBACK_RULE["drop_band"]
    breakout_net = (up_wide & has_theme
                    & (days_since >= wait_lo) & (days_since <= wait_hi)
                    & (from_peak <= drop_hi) & (from_peak >= drop_lo)).fillna(False)
    breakout_factors = {
        "눌린 폭 10~15%": (from_peak <= -10.0) & (from_peak >= -15.0),
        "눌린 폭 8~15%": (from_peak <= -8.0) & (from_peak >= -15.0),
        "60일 50%↑ 올랐다": gain60 > 50.0,
        "60일 20~50% 올랐다": (gain60 > 20.0) & (gain60 <= 50.0),
        "변동성 3~5%": (atr > 3.0) & (atr <= 5.0),
        "최근 5일 음봉 2일↓": down_days <= 2,
        **theme_factors(),
    }
    rows = report("파트 2 · 상승장 (신고가 눌림매수)", breakout_net, breakout_factors,
                  close, opens, dates)
    ladder(rows, "상승장")

    # 파트 3(급락)은 여기서 안 잰다 — 상하님 지시 "상승장만 하라고"(2026-08-13).
    # 한 파트를 고치면서 다른 파트를 같이 건드리지 않는다(CLAUDE.md 0-1 다).


if __name__ == "__main__":
    main()
