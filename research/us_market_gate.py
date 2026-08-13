"""**나스닥 관문**을 다시 정한다 — 200일선 위는 너무 헐렁하지 않나 (2026-08-13).

상하님 지적 — *"나스닥이 200일선 위가 아니지. 정배열이고 신고가를 향하는 기준이지.
웬만하면 200일선 위가 되지 않나? 대부분 120일선 아님 다른 선을 잡아야 되지 않나?"*

**맞는 지적이다.** 200일선 위는 10년의 대부분이라 거의 아무것도 안 거른다.
관문이 거르는 게 없으면 "상승장일 때만 본다"는 말이 빈말이 된다.

## 어떻게 재나

그물에서 **시장 조건을 빼고**(신고가 뒤 3~10일 · 눌린 폭 4~15% · 테마 있는 종목)
그 안에서 **"그 시장 조건인 날에 산 것"이 "아닌 날에 산 것"보다 나은가**를 잰다.
자는 그대로 — 창 2·3·4년, 승률·수익률 둘 다 65%↑.

관문은 **해당 비율이 낮을수록 좋다** — 많이 걸러야 관문이다. 다만 너무 낮으면
목록이 거의 안 뜬다. 그래서 '며칠에 한 번 뜨는가'도 같이 낸다.

쓰는 법:  python research/us_market_gate.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

from us_edge_table import HOLDS, edge  # noqa: E402


def main() -> None:
    import jarvis3_data as j3
    from us_yearly import fetch

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    close, high = wide["close"][stocks], wide["high"][stocks]
    opens, qqq = wide["open"][stocks], wide["close"]["QQQ"]
    dates = close.index

    high52 = high.rolling(252, min_periods=252).max()
    order = pd.DataFrame(np.arange(len(dates))[:, None].repeat(close.shape[1], axis=1),
                         index=dates, columns=close.columns)
    is_new_high = high >= high52.shift(1)
    peak = high.where(is_new_high).ffill()
    days_since = order - order.where(is_new_high).ffill()
    from_peak = (close / peak - 1.0) * 100.0

    themes_of: dict[str, set] = {}
    for theme in j3.US_THEMES:
        for stock in theme["stocks"]:
            if stock in close.columns:
                themes_of.setdefault(stock, set()).add(theme["name"])
    has_theme = pd.DataFrame(
        np.repeat(np.array([[s in themes_of for s in close.columns]]), len(dates), axis=0),
        index=dates, columns=close.columns)

    wait_lo, wait_hi = j3.BREAKOUT_PULLBACK_RULE["wait_days"]
    drop_lo, drop_hi = j3.BREAKOUT_PULLBACK_RULE["drop_band"]
    # **시장 조건을 뺀 그물** — 관문 자체를 재려면 관문이 그물에 들어 있으면 안 된다.
    net = (has_theme & (days_since >= wait_lo) & (days_since <= wait_hi)
           & (from_peak <= drop_hi) & (from_peak >= drop_lo)).fillna(False)
    total = int(net.to_numpy().sum())

    q20 = qqq.rolling(20, min_periods=20).mean()
    q60 = qqq.rolling(60, min_periods=60).mean()
    q120 = qqq.rolling(120, min_periods=120).mean()
    q200 = qqq.rolling(200, min_periods=200).mean()
    qhigh = qqq.rolling(252, min_periods=252).max()
    qdrop = (qqq / qhigh - 1.0) * 100.0
    q_new_high = (qqq >= qhigh.shift(1))
    days_since_qhigh = (pd.Series(np.arange(len(dates)), index=dates)
                        - pd.Series(np.arange(len(dates)), index=dates)
                        .where(q_new_high).ffill())

    gates = {
        "200일선 위 (지금 앱)": qqq > q200,
        "120일선 위": qqq > q120,
        "60일선 위": qqq > q60,
        "20일선 위": qqq > q20,
        "정배열 20>60>120>200": (qqq > q20) & (q20 > q60) & (q60 > q120) & (q120 > q200),
        "정배열 60>120>200": (q60 > q120) & (q120 > q200) & (qqq > q60),
        "고점 -3% 안": qdrop > -3.0,
        "고점 -5% 안": qdrop > -5.0,
        "고점 -10% 안": qdrop > -10.0,
        "최근 20일 안에 신고가": days_since_qhigh <= 20,
        "최근 60일 안에 신고가": days_since_qhigh <= 60,
        "200일선 위 + 고점 -10% 안 (지금 앱)": (qqq > q200) & (qdrop > -10.0),
        "정배열 + 고점 -5% 안": ((qqq > q20) & (q20 > q60) & (q60 > q120)
                            & (q120 > q200) & (qdrop > -5.0)),
        "120일선 위 + 최근 20일 안에 신고가": (qqq > q120) & (days_since_qhigh <= 20),
        "정배열 + 최근 20일 안에 신고가": ((qqq > q20) & (q20 > q60) & (q60 > q120)
                               & (q120 > q200) & (days_since_qhigh <= 20)),
    }

    rets = {hold: (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
            for hold, _ in HOLDS}
    usable = int(qqq.notna().sum())
    print(f"\n{'=' * 112}\n### 나스닥 관문 — 어느 조건이 실제로 거르나"
          f"\n### 시장 조건 뺀 그물 {total:,}자리 · 10년 {usable:,}거래일"
          f"\n{'=' * 112}")
    print(f"  {'관문':<32}{'그런 날':>7}{'그물 중':>7}   "
          + "".join(f"{n:>14}" for _h, n in HOLDS) + f"{'평균':>8}")
    print(f"  {'':<32}{'비율':>7}{'해당':>7}   " + "".join(f"{'승률/수익':>14}" for _h in HOLDS))

    rows = []
    for name, mask in gates.items():
        day_share = float(mask.fillna(False).mean() * 100)
        wide_mask = pd.DataFrame(
            np.repeat(mask.fillna(False).to_numpy()[:, None], close.shape[1], axis=1),
            index=dates, columns=close.columns)
        share = (wide_mask.to_numpy() & net.to_numpy()).sum() / max(total, 1) * 100
        cells, wins, passes = "", [], 0
        for hold, _label in HOLDS:
            item = edge(rets[hold], net, wide_mask)
            if not item.get("ok"):
                cells += f"{'—':>14}"
                continue
            star = "*" if item["passed"] else " "
            cells += f"{item['win_mid']:>+6.1f}/{item['ret_mid']:>+6.1f}{star}"
            wins.append(item["win_mid"])
            passes += bool(item["passed"])
        mean = float(np.mean(wins)) if wins else float("nan")
        print(f"  {name:<32}{day_share:>6.0f}%{share:>6.0f}%   {cells}{mean:>+7.1f}p")
        rows.append((mean, passes, day_share, share, name))

    print("\n  칸은 '승률차 / 수익률차' (%p). 별표 * = 그 보유기간에서 걸러내기 통과.")
    print("  ※ 관문은 **많이 거를수록** 관문답다 — '그런 날 비율'이 낮은데 승률차가 크면 좋다.")
    print(f"\n{'=' * 112}\n### 관문 순위 (승률차)\n{'=' * 112}")
    for mean, passes, day_share, share, name in sorted(rows, reverse=True):
        print(f"  {mean:>+6.1f}p  통과 {passes}/4  그런 날 {day_share:>3.0f}%  {name}")


if __name__ == "__main__":
    main()
