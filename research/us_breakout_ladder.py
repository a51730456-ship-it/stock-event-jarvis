"""미국 상승장 배점 — 보유기간 셋에서 계단 순서가 뒤집히는지 본다 (2026-08-12).

상하님이 정하셨다 — **상승장도 배점으로 간다**(별 아님). 그런데 같은 날
**파는 시점은 앱이 정하지 않는다**고도 정하셨다. 그러면 문제가 하나 생긴다:

  배점 계단(40·30·20·10)의 순서를 **어느 보유기간으로 정할 것인가.**

120일에서 1등인 항목이 250일에서도 1등이라는 보장이 없다. 실제로 급락에서는
보유기간이 바뀌자 '최근 11일'이 합격에서 거꾸로로 뒤집힌 적이 있다.

그래서 **60·120·250일 셋 다 재서, 순서가 뒤집히는지 먼저 확인한다.**
  · 셋 다 순서가 같으면 → 그 순서로 계단을 짠다
  · 뒤집히면 → 세 창에서 **가장 고르게 좋은 것**을 위에 둔다(최악값의 최솟값 기준)

그물은 **앱이 실제로 쓰는 것 그대로**다(2026-08-06 상하님 결정, 안 바꾼다):
  신고가 뒤 1~5거래일 · 눌린 폭 −4~−15% · 시장 조건은 거르지 않음

잣대는 `us_verify.py`에 못박힌 것 그대로 — 창 2·3·4년, 그물 안에서 견주기,
승률·수익률 둘 다 65%↑.

쓰는 법:  python research/us_breakout_ladder.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

from us_verify import PASS_MARK, WINDOWS, score, verdict  # noqa: E402
from us_theme_rank import per_theme, top_rank  # noqa: E402

HOLDS = (60, 120, 250)
NAMES = {60: "3개월", 120: "6개월", 250: "1년"}
SHARE_HIGH, SHARE_LOW = 85.0, 10.0      # 기준 6 — 이 밖이면 못 가른다


def main() -> None:
    import jarvis3_data as j3
    from us_yearly import fetch

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    close, high, low = wide["close"][stocks], wide["high"][stocks], wide["low"][stocks]
    opens, volume = wide["open"][stocks], wide["volume"][stocks]
    dates = close.index

    order = pd.DataFrame(np.arange(len(dates))[:, None].repeat(close.shape[1], axis=1),
                         index=dates, columns=close.columns)
    high52 = high.rolling(252, min_periods=252).max()
    days_ago = order - order.where(high >= high52).ffill()
    from_high = (close / high52 - 1.0) * 100.0
    sma20 = close.rolling(20, min_periods=20).mean()
    prev = close.shift(1)
    true_range = pd.concat([(high - low).stack(), (high - prev).abs().stack(),
                            (low - prev).abs().stack()], axis=1).max(axis=1).unstack()
    atr_pct = true_range.rolling(14, min_periods=14).mean() / close * 100.0
    turnover = close * volume
    dollar = turnover.rolling(50, min_periods=20).mean()
    recent11 = (close / close.shift(11) - 1.0) * 100.0
    gain60 = (close / close.shift(60) - 1.0) * 100.0

    themes_of: dict[str, set] = {}
    for theme in j3.US_THEMES:
        for stock in theme["stocks"]:
            if stock in close.columns:
                themes_of.setdefault(stock, set()).add(theme["name"])
    has_theme = pd.DataFrame(
        np.repeat(np.array([[s in themes_of for s in close.columns]]), len(dates), axis=0),
        index=dates, columns=close.columns)

    lo, hi = j3.BREAKOUT_PULLBACK_RULE["drop_band"]
    wait_lo, wait_hi = j3.BREAKOUT_PULLBACK_RULE["wait_days"]
    net = ((days_ago >= wait_lo) & (days_ago <= wait_hi)
           & (from_high >= lo) & (from_high <= hi) & has_theme).fillna(False)

    counts = pd.DataFrame(0, index=dates, columns=close.columns)
    for theme in j3.US_THEMES:
        members = [s for s in theme["stocks"] if s in close.columns]
        if not members:
            continue
        n = net[members].sum(axis=1)
        for stock in members:
            counts[stock] = np.maximum(counts[stock], n)

    def flag(values, top):
        return top_rank(values, themes_of, close.columns, top).reindex(
            index=dates, columns=close.columns).fillna(False)

    factors = {
        "눌린 폭 10~15%": (from_high <= -10) & (from_high >= -15),
        "눌린 폭 6~10%": (from_high < -6) & (from_high > -10),
        "같은 테마 동반 3개↑": counts >= 3,
        "같은 테마 동반 4개↑": counts >= 4,
        "신고가 뒤 1~3일": days_ago <= 3,
        "최근 11일 안 올랐음": recent11 <= 0,
        "최근 11일 −5%↑ 빠짐": recent11 <= -5,
        "60일 40%↑ 오름": gain60 >= 40,
        "변동성 3% 미만": atr_pct < 3,
        "변동성 6%↑": atr_pct >= 6,
        "거래대금 5억달러↑": dollar >= 5e8,
        "테마 20일선 위 비율 상위 3등": flag(
            per_theme((close > sma20).astype(float) * 100, j3.US_THEMES), 3),
        "테마 20일선 위 비율 상위 5등": flag(
            per_theme((close > sma20).astype(float) * 100, j3.US_THEMES), 5),
        "테마 오른 종목 비율(5일) 상위 5등": flag(
            per_theme((close.pct_change(5) > 0).astype(float) * 100, j3.US_THEMES), 5),
        "테마 오른 종목 비율(20일) 상위 5등": flag(
            per_theme((close.pct_change(20) > 0).astype(float) * 100, j3.US_THEMES), 5),
        "테마 덜 빠졌나 상위 3등": flag(per_theme(from_high, j3.US_THEMES), 3),
        "테마 60일 수익률 상위 5등": flag(
            per_theme(close.pct_change(60) * 100, j3.US_THEMES), 5),
    }

    inside = net.to_numpy()
    print(f"\n{'=' * 104}\n### 미국 상승장 — 앱 그물(신고가 뒤 1~5일 · −4~−15%) "
          f"· 그물 안 {int(inside.sum()):,}자리\n{'=' * 104}")
    print(f"  {'후보':<30}{'해당':>5}" + "".join(f"{NAMES[h]:>18}" for h in HOLDS))

    table: dict[str, dict] = {}
    for name, factor in factors.items():
        factor = factor.reindex(index=dates, columns=close.columns).fillna(False)
        share = (factor.to_numpy() & inside).sum() / max(inside.sum(), 1) * 100
        cells, marks = "", {}
        for hold in HOLDS:
            rets = (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
            result = score(rets, net, factor)
            mark = verdict(result)
            if mark == "○ 합격" and not (SHARE_LOW <= share <= SHARE_HIGH):
                mark = "✎ 못 가름"
            worst = min((result[y]["win_worst"] for y in WINDOWS if result[y]),
                        default=float("nan"))
            marks[hold] = (mark, worst)
            cells += f"  {mark:<8}{worst:>7.1f}p"
        table[name] = {"share": share, "marks": marks}
        print(f"  {name:<30}{share:>4.0f}%{cells}")

    print(f"\n{'=' * 104}\n### 보유기간별 합격 목록 — 가장 나쁜 창이 좋은 순\n{'=' * 104}")
    ladders = {}
    for hold in HOLDS:
        passed = [(item["marks"][hold][1], name, item["share"])
                  for name, item in table.items() if item["marks"][hold][0] == "○ 합격"]
        passed.sort(key=lambda row: -row[0])
        ladders[hold] = [name for _w, name, _s in passed]
        print(f"\n  ── {NAMES[hold]} 보유 — 합격 {len(passed)}개 ──")
        for rank, (worst, name, share) in enumerate(passed, 1):
            points = (40, 30, 20, 10)[rank - 1] if rank <= 4 else 0
            print(f"     {rank}. {name}  (최악 {worst:+.1f}p · 해당 {share:.0f}%)"
                  f"  → {points}점" if points else
                  f"     {rank}. {name}  (최악 {worst:+.1f}p · 해당 {share:.0f}%)  → 계단 밖")

    print(f"\n{'=' * 104}\n### 세 보유기간에서 순서가 뒤집히나\n{'=' * 104}")
    everywhere = set(ladders[HOLDS[0]])
    for hold in HOLDS[1:]:
        everywhere &= set(ladders[hold])
    print(f"  세 기간 **모두** 합격한 항목: {len(everywhere)}개")
    for name in sorted(everywhere,
                       key=lambda n: -min(table[n]["marks"][h][1] for h in HOLDS)):
        spots = " / ".join(f"{NAMES[h]} {ladders[h].index(name) + 1}등" for h in HOLDS)
        worst = min(table[name]["marks"][h][1] for h in HOLDS)
        print(f"     · {name:<32} {spots}   (세 기간 통틀어 최악 {worst:+.1f}p)")

    only_one = [n for n in table
                if sum(table[n]["marks"][h][0] == "○ 합격" for h in HOLDS) == 1]
    if only_one:
        print(f"\n  **한 기간에서만 합격한 항목 (쓰면 안 된다)**")
        for name in only_one:
            where = [NAMES[h] for h in HOLDS if table[name]["marks"][h][0] == "○ 합격"]
            print(f"     · {name} — {where[0]}에서만")

    print("\n※ 계단은 40·30·20·10 네 칸뿐이다(기준 3). 다섯 번째부터는 0점."
          "\n※ 해당 비율 85%↑ 또는 10%↓면 합격이어도 못 가른다(기준 6).")


if __name__ == "__main__":
    main()
