"""상승장(신고가 눌림) 배점을 **속도까지 넣어** 다시 잰다 (2026-08-12 저녁).

상하님 지적 — *"속도 안 쟀는데 배점은 왜 수정했지? 이것과 관계없냐?"*

**관계있다.** 오늘 낮에 상승장 배점을 실측 계단으로 갈아끼웠는데
(`research/us_breakout_ladder.py`), 그때 잰 것은 '3개월·6개월·1년 **뒤** 수익률'
뿐이었다. 저녁에 급락 쪽에 속도를 넣었더니 30점짜리 항목이 통째로 뒤집혔다
(`us_rebound_speed.py` — '같이 오르는가'가 바탕보다 느렸다). 상승장 배점에도
같은 '같이 오르는가'가 30점 걸려 있다. **그물이 다르니 답도 다를 수 있어** 잰다.

## 그물 — 화면이 실제로 쓰는 것 그대로

  나스닥이 200일선 위 **그리고** 고점에서 10% 안쪽 (BREAKOUT_MARKET_MAX_DROP)
  신고가 뒤 1~5일 (wait_days) · 신고가 대비 -4~-15% (drop_band)
  어느 테마에도 안 속한 종목은 뺀다

## 재는 것

[빨리] 5·10·20·40일 짧은 보유에서도 합격하나 (창 2·3·4년 · 승률/수익률 65%)
[빨리] +20%에 닿기까지 며칠 · [많이] 1년 안 최고 상승폭 · 1년 뒤 수익

## 후보 — 지금 배점 셋 + 급락에서 이긴 주봉 오름세

  눌린 폭 10~15%        40점 (지금 1등)
  테마가 같이 오르는가    30점 ← 급락에서는 꼴찌였다
  테마가 덜 빠졌나        20점
  테마 주봉이 오름세      아직 안 씀 ← 급락에서 속도 1등
  테마가 20일선 위        아직 안 씀

쓰는 법:  python research/us_breakout_speed.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

from us_rebound_speed import part_fast_marks, part_speed  # noqa: E402
from us_theme_rank import per_theme, top_rank  # noqa: E402


def build() -> dict:
    import jarvis3_data as j3
    from us_yearly import fetch

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    close, high, low = wide["close"][stocks], wide["high"][stocks], wide["low"][stocks]
    opens = wide["open"][stocks]
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

    # ── 화면 그물 그대로 ─────────────────────────────────────────────────
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
    wait_lo, wait_hi = j3.BREAKOUT_PULLBACK_RULE["wait_days"]
    drop_lo, drop_hi = j3.BREAKOUT_PULLBACK_RULE["drop_band"]

    themes_of: dict[str, set] = {}
    for theme in j3.US_THEMES:
        for stock in theme["stocks"]:
            if stock in close.columns:
                themes_of.setdefault(stock, set()).add(theme["name"])
    has_theme = pd.DataFrame(
        np.repeat(np.array([[s in themes_of for s in close.columns]]), len(dates), axis=0),
        index=dates, columns=close.columns)

    net = (up_wide & has_theme & (days_since >= wait_lo) & (days_since <= wait_hi)
           & (from_peak <= drop_hi) & (from_peak >= drop_lo)).fillna(False)

    # ── 후보 ────────────────────────────────────────────────────────────
    band_lo, band_hi = j3.BREAKOUT_DROP_BAND
    theme_values = {
        "테마 같이 오르나(5일)": per_theme(
            (close.pct_change(5) > 0).astype(float) * 100, j3.US_THEMES),
        "테마 덜 빠졌나": per_theme(from_high, j3.US_THEMES),
        "테마 주봉 오름세": per_theme(aligned.astype(float) * 100, j3.US_THEMES),
        "테마 20일선 위": per_theme((close > sma20).astype(float) * 100, j3.US_THEMES),
    }
    factors: dict[str, pd.DataFrame] = {
        f"눌린 폭 {abs(band_hi):.0f}~{abs(band_lo):.0f}%":
            ((from_peak <= band_hi) & (from_peak >= band_lo)).fillna(False),
    }
    tops = {"테마 덜 빠졌나": j3.THEME_LESS_DROP_TOP_N}
    for name, values in theme_values.items():
        top = tops.get(name, j3.THEME_RANK_TOP_N)
        factors[f"{name} 상위{top}"] = top_rank(
            values, themes_of, close.columns, top).reindex(
            index=dates, columns=close.columns).fillna(False)

    return {"dates": dates, "close": close, "opens": opens, "high": high,
            "high52": high52, "net": net, "factors": factors}


def main() -> None:
    env = build()
    print(f"\n{'#' * 118}\n### 미국 **상승장(신고가 눌림)** — 속도까지 넣어 다시 잰다"
          f"\n{'#' * 118}")
    part_fast_marks(env)
    part_speed(env)
    print(f"\n※ 급락 그물에서는 '같이 오르는가'가 +20%까지 46일로 바탕(45일)보다 "
          f"느려서 30점을 뺐다. 여기서도 그런지 보는 것이 이 측정의 목적이다.")


if __name__ == "__main__":
    main()
