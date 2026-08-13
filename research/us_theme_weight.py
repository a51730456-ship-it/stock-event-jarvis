"""고친 자로 **테마 배점을 얼마까지 올릴 수 있나** 잰다 (2026-08-13).

## 앞의 두 스크립트에서 찾은 것

`us_theme_measures.py` — 자를 아홉 개 만들어 견줬다. 결함 셋을 확인했다.
  ① 절대 수준을 재서 사건의 73%가 한 칸에 몰려 있었다 → 등수로 바꾼다
  ② 시총 가중이라 대장주 하나가 테마를 대신했다 → 머릿수로 센다
  ③ 후보 자신이 테마 합계에 들어갔다 → 뺀다

`us_theme_horizon.py` — 1년 보유 하나로만 쟀던 것을 넷으로 갈랐다.
  ④ 산업 모멘텀은 1~6개월이 가장 센데(Moskowitz & Grinblatt 1999)
     나는 힘이 빠지는 1년 자리에서만 봤다

고친 자로 다시 보니 **테마 등수**가 네 보유기간 **모두에서** 갈렸다.

    하위 25%   1개월 45번 · 3개월 43번 · 6개월 55번 · 1년 53번   ← 모두 나쁨
    50~75%     1개월 61번 · 3개월 60번 · 6개월 66번 · 1년 67번   ← 모두 좋음

같은 날 견주기도 하위 25%가 41%/41%/39%/38%로 **네 번 다 진다.**
지금까지 테마 항목 중 이만큼 한결같은 것은 없었다.

## 이 스크립트가 하는 일

테마 점수를 셋으로 짜고, 총점에서 테마가 차지하는 몫을 10점부터 50점까지
올려 가며 **네 보유기간 전부에서** 같은 날 견주기를 다시 잰다.
CLAUDE.md 0-1 마 — 파는 시점을 안 정하는 파트는 **여러 보유기간에서 모두
합격한 것**만 쓴다. 한 기간에서만 좋은 값은 보유가 바뀌면 뒤집힌다.

쓰는 법:  python research/us_theme_weight.py
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


def steps(values: np.ndarray, spec) -> np.ndarray:
    out = np.zeros(len(values))
    for low, high, share in spec:
        out = np.where((values >= low) & (values < high), share, out)
    return out


GAIN = ((-999, 20, 0.13), (20, 35, 0.37), (35, 50, 0.50), (50, 75, 0.63), (75, 9999, 1.0))
PULL = ((4, 6, 0.50), (6, 8, 0.50), (8, 10, 1.0), (10, 12, 0.70), (12, 16, 0.60))
# 테마 등수 — 실측 계단. 하위 25%는 네 기간 모두 나빠 0점, 중상위가 가장 좋다.
RANK = ((0, 25, 0.0), (25, 50, 0.40), (50, 75, 1.0), (75, 101, 0.60))
# 테마가 지금 좀 쉬었나 — 6개월 보유에서 같은 날 58%(+4.9%p)로 갈렸다.
REST = ((0, 85, 0.7), (85, 95, 1.0), (95, 99, 0.2), (99, 999, 0.6))


def theme_score(frame: pd.DataFrame, kind: str) -> np.ndarray:
    rank = steps(frame.rank120.values, RANK)
    if kind == "등수만":
        return rank
    rest = steps(frame.prox.values, REST)
    if kind == "등수+쉼":
        return 0.7 * rank + 0.3 * rest
    both = 0.6 * rank + 0.25 * rest
    return both + 0.15 * np.clip(frame.n_theme.values - 1, 0, 2) / 2.0


def contest(frame: pd.DataFrame, score: np.ndarray, hold: int) -> tuple:
    """그날 후보 중 총점 1등이 나머지 평균을 이겼나."""
    column = f"r{hold}"
    data = frame.assign(s=score).dropna(subset=[column])
    gaps = []
    for _day, group in data.groupby("date"):
        if len(group) < 2:
            continue
        top = group.sort_values(["s", "gain60", "pullback", "ticker"],
                                ascending=[False, False, False, True]).iloc[0]
        gaps.append(top[column] - group.drop(top.name)[column].mean())
    if len(gaps) < 30:
        return len(gaps), None, None
    array = np.array(gaps)
    return len(array), 100 * (array > 0).mean(), float(np.median(array))


def main() -> None:
    from us_theme_horizon import load_events

    events = load_events()
    gain = steps(events.gain60.values, GAIN)
    pull = steps(events.pullback.values, PULL)
    old = steps(events.prox.values, ((0, 85, 0.0), (85, 95, 1.0), (95, 999, 0.3)))

    print(f"\n{'=' * 112}\n### 고친 자로 테마 배점을 올려 본다 — 사건 {len(events):,}건"
          f"\n{'=' * 112}")
    print("  숫자는 **같은 날 견주기** — 그날 총점 1등이 나머지를 이긴 날의 비율.")
    print("  네 기간 모두 50%를 넘어야 쓴다(CLAUDE.md 0-1 마).\n")
    header = "".join(f"{name:>19}" for _h, name in HOLDS)
    print(f"  {'종목상승/눌림/테마 · 테마 재는 법':<40}{header}")

    plans = [
        ("70 / 20 / 10 · 근접도 세 칸 (지금)", 70, 20, 10, "옛자"),
        ("70 / 20 / 10 · 등수", 70, 20, 10, "등수만"),
        ("60 / 20 / 20 · 등수", 60, 20, 20, "등수만"),
        ("50 / 20 / 30 · 등수", 50, 20, 30, "등수만"),
        ("40 / 20 / 40 · 등수", 40, 20, 40, "등수만"),
        ("30 / 20 / 50 · 등수", 30, 20, 50, "등수만"),
        ("60 / 20 / 20 · 등수+쉼", 60, 20, 20, "등수+쉼"),
        ("50 / 20 / 30 · 등수+쉼", 50, 20, 30, "등수+쉼"),
        ("40 / 20 / 40 · 등수+쉼", 40, 20, 40, "등수+쉼"),
        ("30 / 20 / 50 · 등수+쉼", 30, 20, 50, "등수+쉼"),
        ("50 / 20 / 30 · 등수+쉼+겹침", 50, 20, 30, "셋 다"),
        ("40 / 20 / 40 · 등수+쉼+겹침", 40, 20, 40, "셋 다"),
        ("30 / 20 / 50 · 등수+쉼+겹침", 30, 20, 50, "셋 다"),
        ("0 / 0 / 100 · 등수+쉼 (테마만)", 0, 0, 100, "등수+쉼"),
        ("70 / 30 / 0 · 테마 안 씀", 70, 30, 0, "옛자"),
    ]
    best = {}
    for label, g_max, p_max, t_max, kind in plans:
        theme = old if kind == "옛자" else theme_score(events, kind)
        total = g_max * gain + p_max * pull + t_max * theme
        line = ""
        for hold, _name in HOLDS:
            days, win, gap = contest(events, total, hold)
            if win is None:
                line += f"{'못 잼':>19}"
                continue
            line += f"{days:>5}일{win:>6.1f}%{gap:>+7.1f}%p"
            best.setdefault(label, []).append(win)
        print(f"  {label:<40}{line}")

    print(f"\n{'=' * 112}\n### 네 기간 **모두** 50%를 넘긴 것만\n{'=' * 112}")
    passed = [(label, wins) for label, wins in best.items() if min(wins) >= 50.0]
    if not passed:
        print("  없다.")
    for label, wins in sorted(passed, key=lambda x: -min(x[1])):
        print(f"  {label:<40}가장 낮은 기간 {min(wins):.1f}% · "
              f"평균 {np.mean(wins):.1f}%")


if __name__ == "__main__":
    main()
