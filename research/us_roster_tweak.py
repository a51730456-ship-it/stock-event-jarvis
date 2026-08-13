"""지금 명부를 **조금만** 손대 보고 고른다 (2026-08-13).

## 앞에서 나온 것

`us_roster_compare.py` — StockTitan 명부(19개·115종목)로 통째로 갈아엎었더니
**가짜 테마 시험에서 완전히 떨어졌다.** 제비뽑기로 아무렇게나 묶은 것과
성적이 같았다(가짜가 100번 중 26·49·47·51번 이김).

원인으로 보이는 것 — StockTitan의 「순수 테마주(5점)」만 남기니 테마가
3~4종목으로 작아졌다. 그러면 **테마 합산 시총이 사실상 그 종목 하나**가 되어
「테마가 어떤가」가 아니라 「그 종목이 어떤가」를 다시 재게 된다.

**테마는 어느 정도 커야 테마 노릇을 한다.**

## 그래서 통째 교체 대신 조금만 손댄다

  ㉮ 지금 그대로                    (견줄 기준)
  ㉯ 빅테크10 삭제                  테마가 아니라 큰 회사 열 개 모음이다.
                                  열 개가 이미 딴 테마에 다 들어 있어 두 번 센다.
  ㉰ ㉯ + 양자컴퓨팅에서 대기업 넷 삭제  IBM·GOOGL·HON·MSFT는 양자를 연구할 뿐
                                  주가가 양자로 움직이지 않는다(StockTitan 4점).
                                  순수 양자주 IONQ·QBTS·RGTI·QUBT만 남긴다.
  ㉱ ㉰ + 우주·위성에 SATS·PL·RDW 유지, 로봇에서 ABBNY(미국 상장 아님) 삭제

각각 **짝 견주기 + 연 단위 오차 + 가짜 테마 시험**을 다 돌린다.
가짜 시험을 통과하고 합격 칸이 가장 많은 것을 고른다.

쓰는 법:  python research/us_roster_tweak.py [가짜뽑기횟수]
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

SHUFFLES = int(sys.argv[1]) if len(sys.argv) > 1 else 100


def main() -> None:
    import jarvis3_data as j3
    from us_roster_compare import (GAIN, HOLDS, OLD_THEME, PULL, Board,
                                   line, pairs_by_year, placebo, steps)

    ours = {t["name"]: list(t["stocks"]) for t in j3.US_THEMES}

    def without(drop_themes=(), drop_stocks=None):
        drop_stocks = drop_stocks or {}
        out = []
        for name, members in ours.items():
            if name in drop_themes:
                continue
            kept = [s for s in members if s not in drop_stocks.get(name, ())]
            if len(kept) >= 3:
                out.append(kept)
        return out

    plans = {
        "㉮ 지금 그대로": without(),
        "㉯ 빅테크10 삭제": without(("빅테크10",)),
        "㉰ ㉯ + 양자 대기업 넷 삭제": without(
            ("빅테크10",), {"양자컴퓨팅": {"IBM", "GOOGL", "HON", "MSFT"}}),
        "㉱ ㉰ + 로봇 ABBNY 삭제": without(
            ("빅테크10",), {"양자컴퓨팅": {"IBM", "GOOGL", "HON", "MSFT"},
                          "로봇·자동화": {"ABBNY"}}),
    }

    board = Board()
    head = "".join(f"{n:>19}" for _h, n in HOLDS)
    made = {}
    print(f"\n{'=' * 110}\n### ① 테마 근접도 (계단 없이) — 짝 견주기 · 연 단위 오차"
          f"\n{'=' * 110}")
    print(f"  {'명부':<26}{'테마':>5}{'종목':>5}{'사건':>7}{head}  합격")
    for name, groups in plans.items():
        events = board.events(groups)
        made[name] = (events, groups)
        text, passed = line(events, events.prox.values)
        stocks = len({s for m in groups for s in m})
        print(f"  {name:<26}{len(groups):>5}{stocks:>5}{len(events):>7,}{text}  {passed}/4")

    print(f"\n{'=' * 110}\n### ② 비중\n{'=' * 110}")
    print(f"  {'명부 · 종목상승/눌림/테마':<38}{head}  합격")
    for name, (events, _g) in made.items():
        gain = steps(events.gain60.values, GAIN)
        pull = steps(events.pullback.values, PULL)
        theme = np.clip((events.prox.values - 80.0) / 20.0, 0, 1)
        old = steps(events.prox.values, OLD_THEME)
        print()
        for label, score in (
                ("70/20/10 지금 배점", 70 * gain + 20 * pull + 10 * old),
                ("50/10/40 근접도 그대로", 50 * gain + 10 * pull + 40 * theme),
                ("30/ 0/70 눌림 뺌", 30 * gain + 70 * theme),
                ("0/ 0/100 테마만", theme)):
            text, passed = line(events, score)
            print(f"  {name[:2] + ' ' + label:<38}{text}  {passed}/4")

    print(f"\n{'=' * 110}\n### ③ 가짜 테마 시험 — 제비뽑기 {SHUFFLES}번\n{'=' * 110}")
    for name, (events, groups) in made.items():
        print(f"\n  ── {name} ──", flush=True)
        truth = {}
        for hold, _n in HOLDS:
            rows = pairs_by_year(events, events.prox.values, hold)
            truth[hold] = (sum(v[0] for v in rows.values())
                           / sum(v[1] for v in rows.values()) * 100.0)
        fake = placebo(board, groups, board.events)
        cells = ""
        for hold, label in HOLDS:
            arr = np.array(fake[hold])
            beat = int((arr >= truth[hold]).sum())
            cells += (f"     {label} 진짜 {truth[hold]:.1f} · 가짜 "
                      f"{np.median(arr):.1f} · 가짜가 이김 {beat}번\n")
        print(cells, end="")

    print("\n  ※ 가짜가 5번 이하면 그 명부의 테마 효과는 진짜다. 20번을 넘으면 명부 탓이다.")


if __name__ == "__main__":
    main()
