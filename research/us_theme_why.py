"""테마가 살아난 것이 **자 때문인가, 기간 때문인가** 갈라 본다 (2026-08-13).

## 왜 이걸 만드나 — 내가 검증 없이 말한 것을 검증한다

2026-08-13에 내가 상하님께 이렇게 보고했다.

  "산업 모멘텀은 1~6개월이 가장 세고 1년까지 가면 약해진다.
   나는 1년 보유 하나로만 쟀다. 그래서 테마가 약해 보였다."

앞 문장은 **논문 원문이 아니라 검색 요약문에서 옮긴 것**이고, 뒷 문장은
**내 자료로 확인하지 않은 추측**이었다. 상하님이 "이거 확인해봤냐"고 물으셨다.
확인 안 했다. 여기서 확인한다.

## 가르는 방법

테마가 순서를 얼마나 잘 가르는지를 **테마를 아예 안 쓴 배점과의 차이**로 잰다.

    보탬 = (테마 넣은 배점의 같은 날 승률) − (테마 뺀 배점의 같은 날 승률)

이 보탬을 **자 두 개 × 보유기간 네 개**로 늘어놓으면 원인이 갈린다.

  · 기간을 옮겨서 살아난 것이면 → 옛 자도 3~6개월에서 보탬이 커야 한다
  · 자를 고쳐서 살아난 것이면 → 같은 기간에서 새 자가 옛 자보다 커야 한다
  · 둘 다면 → 둘 다 나타난다

**테마 하나만으로 순서를 매겼을 때**도 같이 본다. 다른 항목에 묻히지 않은
테마 자신의 힘이다.

표본이 330일뿐이라 오차가 ±2.7%p쯤 된다. **오차를 같이 적는다.**

쓰는 법:  python research/us_theme_why.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

HOLDS = ((20, "1개월"), (60, "3개월"), (120, "6개월"), (250, "1년"))


def main() -> None:
    from us_theme_horizon import load_events
    from us_theme_weight import GAIN, PULL, RANK, REST, steps

    events = load_events()
    gain = steps(events.gain60.values, GAIN)
    pull = steps(events.pullback.values, PULL)
    old = steps(events.prox.values, ((0, 85, 0.0), (85, 95, 1.0), (95, 999, 0.3)))
    new = 0.7 * steps(events.rank120.values, RANK) + 0.3 * steps(events.prox.values, REST)

    def contest(score, hold, tie=True):
        column = f"r{hold}"
        data = events.assign(s=score).dropna(subset=[column])
        keys = ["s", "gain60", "pullback", "ticker"] if tie else ["s", "ticker"]
        way = [False, False, False, True] if tie else [False, True]
        gaps = []
        for _day, group in data.groupby("date"):
            if len(group) < 2:
                continue
            top = group.sort_values(keys, ascending=way).iloc[0]
            gaps.append(top[column] - group.drop(top.name)[column].mean())
        array = np.array(gaps)
        win = 100 * (array > 0).mean()
        se = 100 * np.sqrt(win / 100 * (1 - win / 100) / len(array))
        return win, se, len(array)

    print(f"\n{'=' * 104}\n### 테마가 살아난 이유 — 자 때문인가 기간 때문인가"
          f"\n{'=' * 104}")
    print("  숫자 = 같은 날 견주기 승률. 괄호는 오차(±1.96 표준오차).\n")

    base = {}
    print(f"  {'배점':<30}" + "".join(f"{n:>19}" for _h, n in HOLDS))
    for label, score in (("테마 뺌  70 / 30 / 0", 70 * gain + 30 * pull),
                         ("옛 자    70 / 20 / 10", 70 * gain + 20 * pull + 10 * old),
                         ("새 자    70 / 20 / 10", 70 * gain + 20 * pull + 10 * new),
                         ("새 자    40 / 20 / 40", 40 * gain + 20 * pull + 40 * new)):
        line = ""
        base[label] = []
        for hold, _name in HOLDS:
            win, se, days = contest(score, hold)
            base[label].append(win)
            line += f"{win:>10.1f}%±{1.96 * se:>4.1f}"
        print(f"  {label:<30}{line}")

    print(f"\n  ── 테마의 보탬 (테마 뺀 것과의 차이) ──")
    zero = base["테마 뺌  70 / 30 / 0"]
    for label in ("옛 자    70 / 20 / 10", "새 자    70 / 20 / 10", "새 자    40 / 20 / 40"):
        line = "".join(f"{base[label][i] - zero[i]:>+18.1f}%p" for i in range(len(HOLDS)))
        print(f"  {label:<30}{line}")

    print(f"\n  ── 테마 **하나만으로** 순서를 매기면 (다른 항목 없이) ──")
    for label, score in (("옛 자 (근접도)", old), ("새 자 (등수+쉼)", new),
                         ("등수만", steps(events.rank120.values, RANK)),
                         ("근접도 쉼만", steps(events.prox.values, REST))):
        line = ""
        for hold, _name in HOLDS:
            win, se, _days = contest(score, hold, tie=False)
            line += f"{win:>10.1f}%±{1.96 * se:>4.1f}"
        print(f"  {label:<30}{line}")

    print(f"\n  ── 테마 등수 하위 25%를 **빼기만** 하면 (배점 말고 그물로) ──")
    keep = events[events.rank120 >= 25]
    print(f"     남는 사건 {len(keep):,}건 / {len(events):,}건 "
          f"({len(keep) / len(events) * 100:.0f}%)")
    print(f"     {'':<12}" + "".join(f"{n:>17}" for _h, n in HOLDS))
    for label, sel in (("전체", events), ("하위 25% 뺀 뒤", keep)):
        line = ""
        for hold, _name in HOLDS:
            values = sel[f"r{hold}"].dropna()
            line += f"{(values > 0).mean() * 100:>8.0f}번{np.median(values):>+8.1f}%"
        print(f"     {label:<12}{line}")

    print("\n  ※ 오차가 겹치면 '더 낫다'고 말할 수 없다.")


if __name__ == "__main__":
    main()
