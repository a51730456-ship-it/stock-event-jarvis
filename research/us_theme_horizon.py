"""테마를 **보유 기간별로** 다시 잰다 (2026-08-13).

## 왜 — 측정법의 두 번째 결함

`us_theme_measures.py`까지는 **1년 보유(250거래일) 하나로만** 쟀다.
그런데 산업(테마) 모멘텀 논문은 이렇게 말한다.

  Moskowitz & Grinblatt(1999) — 산업 모멘텀은 **1~6개월에 가장 세고**
  1년까지 가면 힘이 빠진다. 12개월을 넘기면 되레 뒤집힌다.

즉 **테마 신호가 가장 잘 보이는 자리는 1~6개월인데, 나는 1년에서만 봤다.**
테마가 힘을 못 쓴다고 나온 것이 테마 탓이 아니라 **잰 자리 탓**일 수 있다.

CLAUDE.md 0-1 마도 같은 말을 한다 — "파는 시점을 정하지 않는 파트는
**여러 보유기간에서 모두 합격한 항목**만 쓴다."

## 그래서

  보유 1개월(20일) · 3개월(60일) · 6개월(120일) · 1년(250일) 넷을 나란히 본다.
  자는 `us_theme_measures.py`가 만들어 둔 사건표를 그대로 쓴다(다시 안 잰다).

## 세 번째로 확인하는 것 — 테마도 눌림목인가

테마 자 둘이 서로 반대를 가리켰다.
  · 동료 120일 상승 **등수**가 바닥이면 나쁘다 (모멘텀)
  · 근접도가 85~95%로 **좀 쉰** 테마가 좋다 (눌림)
둘은 안 싸운다. **6개월간 많이 오른 테마가 지금 잠깐 쉬는 중**이 가장 좋다는
뜻일 수 있다. 종목에 쓰는 눌림목 논리를 테마에 그대로 적용한 것이다. 이것도 잰다.

쓰는 법:  python research/us_theme_horizon.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

SRC = ROOT / "research" / "_data" / "theme_measures_events.csv"
HOLDS = ((20, "1개월"), (60, "3개월"), (120, "6개월"), (250, "1년"))
SPLIT = pd.Timestamp("2021-08-04")


def load_events() -> pd.DataFrame:
    from us_yearly import fetch

    events = pd.read_csv(SRC, parse_dates=["date"])
    wide = fetch()
    close, opens = wide["close"], wide["open"]
    dates = close.index
    row = pd.Series(np.arange(len(dates)), index=dates)

    for hold, _name in HOLDS:
        got = np.full(len(events), np.nan)
        buy = (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
        for i, (day, ticker) in enumerate(zip(events.date, events.ticker)):
            if ticker not in buy.columns or day not in row.index:
                continue
            got[i] = buy[ticker].iloc[row[day]]
        events[f"r{hold}"] = got
    events["half"] = np.where(events["date"] < SPLIT, "앞", "뒤")
    return events


def cells(sel: pd.DataFrame, whole: pd.DataFrame) -> str:
    out = ""
    for hold, _name in HOLDS:
        values = sel[f"r{hold}"].dropna()
        if len(values) < 30:
            out += f"{'못 잼':>18}"
            continue
        base = whole[f"r{hold}"].dropna()
        out += (f"{(values > 0).mean() * 100:>7.0f}번"
                f"{np.median(values) - np.median(base):>+9.1f}%p")
    return out


def same_day(events: pd.DataFrame, mask, hold: int) -> tuple:
    column = f"r{hold}"
    table = (events.assign(g=mask).dropna(subset=[column])
             .groupby(["date", "g"])[column].mean().unstack().dropna())
    if len(table) < 30:
        return len(table), None, None
    gap = table[True] - table[False]
    return len(gap), 100 * (gap > 0).mean(), gap.median()


BANDS = (
    ("A 동료 20일 오름 비율", "breadth20",
     ((0, 40, "40% 미만"), (40, 60, "40~60%"), (60, 80, "60~80%"), (80, 101, "80%↑"))),
    ("C 동료 20일 평균 상승", "strength20",
     ((-999, 0, "내렸다"), (0, 3, "0~3%"), (3, 7, "3~7%"), (7, 9999, "7%↑"))),
    ("D 동료 신고가 비율", "nearhigh",
     ((0, 50, "50% 미만"), (50, 70, "50~70%"), (70, 90, "70~90%"), (90, 101, "90%↑"))),
    ("F 동료 120일 상승 등수", "rank120",
     ((0, 25, "하위 25%"), (25, 50, "25~50%"), (50, 75, "50~75%"), (75, 101, "상위 25%"))),
    ("H 근접도 (지금 쓰는 자)", "prox",
     ((0, 85, "85% 미만"), (85, 95, "85~95%"), (95, 99, "95~99%"), (99, 999, "99%↑"))),
)


def main() -> None:
    events = load_events()
    head = "".join(f"{name:>18}" for _h, name in HOLDS)
    print(f"\n{'=' * 108}\n### 보유 기간을 갈라서 — 사건 {len(events):,}건"
          f"\n{'=' * 108}")
    print(f"  {'':<14}{'N':>6}{head}")
    print(f"  {'':<14}{'':>6}" + "".join(f"{'승률   목록대비':>18}" for _h in HOLDS))
    print(f"  {'── 목록 전체 ──':<14}{len(events):>6,}"
          + "".join(f"{(events[f'r{h}'] > 0).mean() * 100:>7.0f}번"
                   f"{np.median(events[f'r{h}'].dropna()):>+9.1f}%" for h, _n in HOLDS))

    for title, column, bands in BANDS:
        print(f"\n  ── {title} ──")
        for low, high_, label in bands:
            sel = events[(events[column] >= low) & (events[column] < high_)]
            print(f"  {label:<14}{len(sel):>6,}{cells(sel, events)}")

    print(f"\n{'=' * 108}\n### 같은 날 견주기 — 보유 기간별 (한 날에 여럿 뜰 때 순서를 가르나)"
          f"\n{'=' * 108}")
    tests = (
        ("동료 신고가 70~90%", (events.nearhigh >= 70) & (events.nearhigh < 90)),
        ("동료 20일 평균 7%↑", events.strength20 >= 7),
        ("테마 등수 하위 25%", events.rank120 < 25),
        ("테마 등수 상위 25%", events.rank120 >= 75),
        ("근접도 85~95% 쉼", (events.prox >= 85) & (events.prox < 95)),
        ("**6개월 상위 + 지금 쉼**",
         (events.rank120 >= 50) & (events.prox >= 85) & (events.prox < 97)),
        ("**6개월 상위 + 동료 신고가 70%↑**",
         (events.rank120 >= 50) & (events.nearhigh >= 70)),
        ("테마 2개 이상", events.n_theme >= 2),
    )
    print(f"  {'항목':<26}{'붙은 수':>8}" + "".join(f"{n:>20}" for _h, n in HOLDS))
    for label, mask in tests:
        line = ""
        for hold, _name in HOLDS:
            days, win, gap = same_day(events, mask, hold)
            line += f"{'못 잼':>20}" if win is None else f"{days:>6}일{win:>5.0f}%{gap:>+8.1f}%p"
        print(f"  {label:<26}{int(mask.sum()):>8,}{line}")

    print("\n  ※ 승률 옆 숫자는 목록 전체 중앙값과의 차이다(그 칸이 얼마나 나은가).")
    print("  ※ 같은 날 견주기 50% 미만 = 그 항목이 붙은 종목이 같은 날 나머지에게 진다.")


if __name__ == "__main__":
    main()
