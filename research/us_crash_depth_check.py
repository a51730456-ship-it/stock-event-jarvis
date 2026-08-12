"""급락이 **깊어질수록** 테마 항목이 여전히 가르는가 (2026-08-12 상하님 지적).

상하님 물음 — "나스닥이 -12% 가까이 빠지면 대부분 종목이 20일선 밑으로 가는데
배점이 잘못된 것 같은데."

일리 있는 지적이다. 지금 급락 배점 셋 중 하나가 '테마가 20일선 위에 있나'(20점)인데,
깊은 급락에서는 **거의 모든 테마가 0%에 가까워** 등수가 무의미해질 수 있다.
그런데 앞선 측정(us_crash_new_net.py)은 그물 전체를 한 덩어리로 쟀고, 그 그물의
**41%가 얕은 칸(-6~-12%)**이라 평균이 그쪽에 끌려간다.

그래서 여기서는 **나스닥 낙폭 칸별로 갈라** 두 가지를 본다.
  ① 그 칸에서 테마들의 값이 실제로 갈리는가 (몇 %가 0인가 · 1등과 꼴찌 차이)
  ② 그 칸에서 '상위 5등'이 성적을 가르는가

배점 항목 셋을 다 본다 — 덜 빠졌나 · 5일 오른 비율 · 20일선 위 비율.

쓰는 법:  python research/us_crash_depth_check.py
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

TIERS = ((-12.0, -6.0, "6~12%"), (-18.0, -12.0, "12~18%"), (-24.0, -18.0, "18~24%"),
         (-100.0, -24.0, "24% 아래"))
HOLDS = ((60, "3개월"), (120, "6개월"), (250, "1년"))


def main() -> None:
    import jarvis3_data as j3
    from us_yearly import fetch

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    close, high, opens = wide["close"][stocks], wide["high"][stocks], wide["open"][stocks]
    qqq = wide["close"]["QQQ"]
    dates = close.index

    high52 = high.rolling(252, min_periods=252).max()
    from_high = (close / high52 - 1.0) * 100.0
    sma20 = close.rolling(20, min_periods=20).mean()
    qdrop = (qqq / qqq.rolling(252, min_periods=252).max() - 1.0) * 100.0

    themes_of: dict[str, set] = {}
    for theme in j3.US_THEMES:
        for stock in theme["stocks"]:
            if stock in close.columns:
                themes_of.setdefault(stock, set()).add(theme["name"])
    has_theme = pd.DataFrame(
        np.repeat(np.array([[s in themes_of for s in close.columns]]), len(dates), axis=0),
        index=dates, columns=close.columns)

    measures = {
        "테마가 덜 빠졌나": per_theme(from_high, j3.US_THEMES),
        "테마가 같이 오르는가(5일)": per_theme(
            (close.pct_change(5) > 0).astype(float) * 100, j3.US_THEMES),
        "테마가 20일선 위에 있나": per_theme(
            (close > sma20).astype(float) * 100, j3.US_THEMES),
    }

    print(f"\n{'=' * 104}\n### 급락이 깊어질수록 테마 항목이 가르는가"
          f"\n### 명부 {len(stocks)}종목 · 2016-08~2026-08\n{'=' * 104}")

    # ── ① 값 자체가 갈리는가 ────────────────────────────────────────────
    print("\n[1] 그 칸에서 테마들의 값이 갈리나 (그날 20개 테마를 줄 세웠을 때)\n")
    print(f"  {'나스닥 칸':<12}{'날 수':>6}   " +
          "".join(f"{name:<28}" for name in measures))
    print(f"  {'':<12}{'':>6}   " + "".join(f"{'0인 테마%  1등-꼴찌':<28}" for _ in measures))
    for low, high_, name in TIERS:
        inside = ((qdrop <= high_) & (qdrop >= low)).fillna(False)
        days = inside[inside].index
        if len(days) < 10:
            print(f"  {name:<12}{len(days):>6}   (날이 너무 적어 건너뜀)")
            continue
        cells = ""
        for values in measures.values():
            block = values.reindex(days).dropna(how="all")
            if block.empty:
                cells += f"{'—':<28}"
                continue
            zero_share = float((block <= 0.0001).mean(axis=1).mean() * 100)
            spread = float((block.max(axis=1) - block.min(axis=1)).median())
            cells += f"{zero_share:>6.0f}%   {spread:>8.1f}      "
        print(f"  {name:<12}{len(days):>6}   {cells}")

    # ── ② 그 칸에서 성적을 가르는가 ─────────────────────────────────────
    print(f"\n\n[2] 그 칸에서 '상위 5등'이 성적을 가르나 "
          f"(창 2·3·4년 · 승률/수익률 둘 다 65%↑라야 합격)\n")
    crash_lo, crash_hi = -50.0, -20.0     # 종목 낙폭 두 칸 합친 것
    for low, high_, tier_name in TIERS:
        inside = ((qdrop <= high_) & (qdrop >= low)).fillna(False)
        band = pd.DataFrame(np.repeat(inside.to_numpy()[:, None], close.shape[1], axis=1),
                            index=dates, columns=close.columns)
        net = (band & has_theme & (from_high <= crash_hi)
               & (from_high >= crash_lo)).fillna(False)
        total = int(net.to_numpy().sum())
        print(f"\n  ── 나스닥 {tier_name} · 그물 안 {total:,}자리 ──")
        if total < 500:
            print("     자리가 너무 적어 판정하지 않는다")
            continue
        for label, values in measures.items():
            factor = top_rank(values, themes_of, close.columns, 5).reindex(
                index=dates, columns=close.columns).fillna(False)
            share = (factor.to_numpy() & net.to_numpy()).sum() / max(total, 1) * 100
            marks = []
            for hold, hold_name in HOLDS:
                rets = (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
                result = score(rets, net, factor)
                worst = min((result[y]["win_worst"] for y in WINDOWS if result[y]),
                            default=float("nan"))
                marks.append(f"{hold_name} {verdict(result):<9}{worst:>7.1f}p")
            print(f"     {label:<26}해당 {share:>3.0f}%  " + " · ".join(marks))

    print("\n※ '0인 테마%'가 높으면 그 칸에서는 값이 대부분 0이라 등수가 무의미하다."
          "\n※ '1등-꼴찌'가 작으면 테마끼리 차이가 없어 상위 5등을 골라도 뜻이 없다.")


if __name__ == "__main__":
    main()
