"""「6개월 34%」·「한 달 9%」를 상승장 그물 안에서 잰다 (2026-09-05 상하님 지시).

상하님이 보내 주신 매매법 메모 —
  · 6개월 동안 34% 넘게 오른 놈
  · 한 달 만에 9% 넘게 치고 올라온 놈

앱의 상승장(신고가 눌림매수)은 지금 **나스닥 대비 등수**로 가른다
(3개월·6개월 각각 상위 20%). 절대 수익률 문턱은 한 개도 없다.
이 파일은 그 문턱을 **넣을 값이 있는지**를 잰다.

**방법은 us_verify.py 를 그대로 쓴다** — 새 자를 만들지 않는다(CLAUDE.md 0-1).
  · 비교 상대는 **같은 그물 안의 나머지**
  · 창 길이 2·3·4년, 한 달에 한 번 밀기
  · 승률과 수익률 **둘 다** 65% 이상이어야 합격
  · 문턱은 눈대중하지 않고 **여러 개를 다 잰다**

**보유기간을 셋으로 잰다** — 상승장은 파는 시점을 앱이 정하지 않는 파트라,
한 기간에서만 통하는 값은 쓰지 않는다(CLAUDE.md 0-1 마).

여기서 재는 것 셋
  ① 문턱마다 그물의 몇 %가 걸리나 (85% 넘거나 10% 미만이면 못 가른다)
  ② 그 문턱이 **그물 안에서** 값이 있나 (합격/안 됨/거꾸로)
  ③ 이미 쓰는 등수 그물(rs120 상위 20%)과 **얼마나 겹치나**
     — 겹치면 같은 것을 두 번 세는 셈이라 배점에서 뺀다

쓰는 법:  python research/us_gain_check.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

from us_verify import MIN_SIDE, MIN_WINDOWS, PASS_MARK, STEP_DAYS, WINDOWS  # noqa: E402

HOLDS = (60, 120, 250)          # 보유기간(거래일) — 3개월·6개월·1년
GAIN120_MARKS = (20.0, 25.0, 30.0, 34.0, 40.0, 50.0)
GAIN21_MARKS = (3.0, 5.0, 7.0, 9.0, 12.0, 15.0)
RS_GATE_PCT = 80.0              # 지금 앱이 쓰는 문턱 (rs120 상위 20%)


def score(returns: pd.DataFrame, net: pd.DataFrame, factor: pd.DataFrame) -> dict:
    """us_verify.score 와 같은 계산. 자를 새로 만들지 않으려고 여기 그대로 둔다."""
    yes = returns.where(net & factor).to_numpy()
    no = returns.where(net & ~factor).to_numpy()
    out: dict[int, dict | None] = {}
    for years in WINDOWS:
        length = int(years * 252)
        wins, medians = [], []
        for start in range(0, len(returns) - length + 1, STEP_DAYS):
            stop = start + length
            a = yes[start:stop].ravel()
            a = a[~np.isnan(a)]
            b = no[start:stop].ravel()
            b = b[~np.isnan(b)]
            if a.size < MIN_SIDE or b.size < MIN_SIDE:
                continue
            wins.append((a > 0).mean() * 100 - (b > 0).mean() * 100)
            medians.append(float(np.median(a) - np.median(b)))
        if len(wins) < MIN_WINDOWS:
            out[years] = None
            continue
        wins, medians = np.array(wins), np.array(medians)
        out[years] = {
            "n": wins.size,
            "win_share": float((wins > 0).mean() * 100),
            "median_share": float((medians > 0).mean() * 100),
            "win_mid": float(np.median(wins)),
        }
    return out


def verdict(result: dict) -> str:
    usable = [item for item in result.values() if item]
    if len(usable) < len(WINDOWS):
        return "판정 못 함"
    if all(item["win_share"] >= PASS_MARK and item["median_share"] >= PASS_MARK
           for item in usable):
        return "○ 합격"
    if all(item["win_share"] <= 100 - PASS_MARK and item["median_share"] <= 100 - PASS_MARK
           for item in usable):
        return "✗ 거꾸로"
    return "△ 안 됨"


def show(name: str, share: float, result: dict) -> None:
    cells = []
    for years in WINDOWS:
        item = result[years]
        cells.append("       —      " if not item else
                     f"{item['win_share']:5.0f}/{item['median_share']:3.0f}%({item['n']:>3})")
    mid = result[WINDOWS[1]]
    tail = "" if not mid else f"  가운데 {mid['win_mid']:+5.1f}p"
    print(f"  {name:<24}{share:>5.0f}%" + "".join(cells) + f"  {verdict(result):<9}{tail}")


def build() -> dict:
    """상승장 그물과 잴 값들을 만든다. 그물은 us_verify 와 **같은 식**이다."""
    import jarvis3_data as j3
    from us_yearly import fetch

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    qqq = wide["close"]["QQQ"]
    close, high = wide["close"][stocks], wide["high"][stocks]
    dates = close.index

    order = pd.DataFrame(np.arange(len(dates))[:, None].repeat(close.shape[1], axis=1),
                         index=dates, columns=close.columns)
    is_new_high = high >= high.rolling(252, min_periods=252).max().shift(1)
    peak = high.where(is_new_high).ffill()
    days_since = order - order.where(is_new_high).ffill()
    from_peak = (close / peak - 1.0) * 100.0

    qqq_drop = (qqq / qqq.rolling(252, min_periods=252).max() - 1.0) * 100.0
    up_day = (qqq > qqq.rolling(200, min_periods=200).mean()) & (qqq_drop > -10.0)
    up_wide = pd.DataFrame(np.repeat(up_day.to_numpy()[:, None], close.shape[1], axis=1),
                           index=dates, columns=close.columns)
    wait_lo, wait_hi = j3.BREAKOUT_PULLBACK_RULE["wait_days"]
    drop_lo, drop_hi = j3.BREAKOUT_PULLBACK_RULE["drop_band"]
    net = (up_wide & (days_since >= wait_lo) & (days_since <= wait_hi)
           & (from_peak <= drop_hi) & (from_peak >= drop_lo))

    gain120 = (close / close.shift(120) - 1.0) * 100.0
    gain21 = (close / close.shift(21) - 1.0) * 100.0
    qqq120 = (qqq / qqq.shift(120) - 1.0) * 100.0
    rs120 = gain120.sub(qqq120, axis=0)
    # 앱은 그날 훑는 종목들 사이의 **등수**로 가른다. 같은 방식으로 줄마다 순위를 낸다.
    rs_pct = rs120.rank(axis=1, pct=True) * 100.0

    returns = {
        hold: (close.shift(-hold) / wide["open"][stocks].shift(-1) - 1.0) * 100.0
        for hold in HOLDS
    }
    return {"net": net, "gain120": gain120, "gain21": gain21,
            "rs_pct": rs_pct, "returns": returns, "stocks": stocks}


def overlap(net: pd.DataFrame, left: pd.DataFrame, right: pd.DataFrame) -> tuple:
    """그물 안에서 두 조건이 얼마나 겹치나. (왼쪽|오른쪽, 오른쪽|왼쪽, 둘 다)"""
    both = int((net & left & right).to_numpy().sum())
    only_left = int((net & left).to_numpy().sum())
    only_right = int((net & right).to_numpy().sum())
    total = int(net.to_numpy().sum())
    return (
        100.0 * both / only_left if only_left else float("nan"),
        100.0 * both / only_right if only_right else float("nan"),
        100.0 * both / total if total else float("nan"),
    )


def main() -> None:
    data = build()
    net, returns = data["net"], data["returns"]
    total = int(net.to_numpy().sum())
    print(f"\n상승장 그물에 걸린 자리 {total:,}개 · 종목 {len(data['stocks'])}개")
    print(f"창 길이 {'·'.join(str(y) for y in WINDOWS)}년 · 한 달에 한 번 밀기 · "
          f"합격선 승률·수익률 둘 다 {PASS_MARK:.0f}%")
    print("칸은 '승률로 이긴 창% / 수익률로 이긴 창%(창 개수)'\n")

    gate = data["rs_pct"] >= RS_GATE_PCT
    gate_share = 100.0 * int((net & gate).to_numpy().sum()) / total
    print(f"※ 지금 앱이 쓰는 문턱(6개월 나스닥 대비 상위 20%)은 그물의 {gate_share:.0f}%를 통과시킨다.\n")

    for hold in HOLDS:
        label = {60: "3개월", 120: "6개월", 250: "1년"}[hold]
        print(f"[{label} 보유]")
        for mark in GAIN120_MARKS:
            factor = data["gain120"] >= mark
            share = 100.0 * int((net & factor).to_numpy().sum()) / total
            show(f"6개월 {mark:.0f}% 넘게", share, score(returns[hold], net, factor))
        for mark in GAIN21_MARKS:
            factor = data["gain21"] >= mark
            share = 100.0 * int((net & factor).to_numpy().sum()) / total
            show(f"한 달 {mark:.0f}% 넘게", share, score(returns[hold], net, factor))
        # 이미 쓰는 등수 그물을 **통과한 것들 안에서만** 다시 잰다.
        # 여기서도 값이 있어야 '더해서 얻는 것'이 있다는 뜻이다.
        print("  ── 등수 그물(상위 20%)을 통과한 것들 안에서만 다시 재면 ──")
        inner = net & gate
        inner_total = int(inner.to_numpy().sum())
        for mark in (30.0, 34.0, 40.0):
            factor = data["gain120"] >= mark
            share = 100.0 * int((inner & factor).to_numpy().sum()) / inner_total
            show(f"6개월 {mark:.0f}% 넘게", share, score(returns[hold], inner, factor))
        for mark in (7.0, 9.0, 12.0):
            factor = data["gain21"] >= mark
            share = 100.0 * int((inner & factor).to_numpy().sum()) / inner_total
            show(f"한 달 {mark:.0f}% 넘게", share, score(returns[hold], inner, factor))
        print()

    print("[겹침 — 이미 쓰는 등수 그물과 얼마나 같은 것을 고르나]")
    for name, factor in (("6개월 34% 넘게", data["gain120"] >= 34.0),
                         ("한 달 9% 넘게", data["gain21"] >= 9.0)):
        a, b, both = overlap(net, factor, gate)
        print(f"  {name:<16} 이 조건을 통과한 것 중 {a:5.1f}%가 등수 그물도 통과 · "
              f"등수 그물 통과한 것 중 {b:5.1f}%가 이 조건도 통과 · 둘 다 {both:4.1f}%")
    print()


if __name__ == "__main__":
    main()
