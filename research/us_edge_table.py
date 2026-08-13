"""배점을 정하는 자 — **승률차와 수익률차를 각각 크기까지** 낸다 (2026-08-13).

상하님 지시 — *"결국 승률이 높은 게 배점을 많이 줘야 하고, 이거 논리를 너가 먼저
정리해야 되는 게 중요하고 … 승률 수익률 같이 각각 검토해야지."*

## 그전까지 무엇이 틀렸나

지금까지는 `us_verify.verdict`가 주는 **합격/불합격만 세어** 3/4·2/4로 줄을 세웠다.
그건 문턱을 넘었는지만 보는 것이라 **얼마나 좋은지가 안 들어간다.**
실제로 둘 다 3/4인데 가장 나쁜 창이 -8.0%p와 -13.8%p로 크게 달랐다.
같은 점수를 주면 안 되는 것을 같은 줄에 놓고 있었다.

## 이 파일이 내는 것

후보마다 보유기간 넷(20일·3개월·6개월·1년)에 대해

  · **승률차**   = 해당 자리 승률 − 나머지 자리 승률 (%p)
  · **수익률차** = 해당 자리 수익률 가운데값 − 나머지 가운데값 (%p)

를 창 2·3·4년을 한 달씩 밀며 구하고, 그 창들의 **가운데값**과 **가장 나쁜 창**을
낸다. 걸러내기(승률·수익률 둘 다 65%↑ 창)는 `us_verify`와 **똑같은 규칙**을 쓴다.

**걸러내기와 줄 세우기를 나눈다.**
  1단계 걸러내기 — 지금 기준 그대로. 통과 못 하면 0점.
  2단계 줄 세우기 — 통과한 것만 놓고 **승률차 크기**로 40·30·20·10.
                   단, 가장 나쁜 창이 크게 마이너스인 것은 위로 올리지 않는다.

쓰는 법:  python research/us_edge_table.py
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

HOLDS = ((20, "20일"), (60, "3개월"), (120, "6개월"), (250, "1년"))


def edge(returns: pd.DataFrame, net: pd.DataFrame, factor: pd.DataFrame) -> dict:
    """한 보유기간에서 승률차·수익률차의 가운데값과 가장 나쁜 창.

    창 나누기·최소 표본·합격선은 us_verify와 같다 — 자를 두 개 만들면 안 된다.
    """
    yes = returns.where(net & factor).to_numpy()
    no = returns.where(net & ~factor).to_numpy()
    win_all, ret_all, ok_windows = [], [], []
    for years in WINDOWS:
        length = int(years * 252)
        wins, rets = [], []
        for start in range(0, len(returns) - length + 1, STEP_DAYS):
            stop = start + length
            a = yes[start:stop].ravel()
            a = a[~np.isnan(a)]
            b = no[start:stop].ravel()
            b = b[~np.isnan(b)]
            if a.size < MIN_SIDE or b.size < MIN_SIDE:
                continue
            wins.append((a > 0).mean() * 100 - (b > 0).mean() * 100)
            rets.append(float(np.median(a) - np.median(b)))
        if len(wins) < MIN_WINDOWS:
            ok_windows.append(None)
            continue
        wins, rets = np.array(wins), np.array(rets)
        ok_windows.append(((wins > 0).mean() * 100 >= PASS_MARK
                           and (rets > 0).mean() * 100 >= PASS_MARK))
        win_all.append(wins)
        ret_all.append(rets)
    if not win_all or any(v is None for v in ok_windows):
        return {"ok": False}
    wins = np.concatenate(win_all)
    rets = np.concatenate(ret_all)
    return {
        "ok": True,
        "passed": all(ok_windows),
        "win_mid": float(np.median(wins)),
        "win_worst": float(wins.min()),
        "ret_mid": float(np.median(rets)),
        "ret_worst": float(rets.min()),
    }


def report(title: str, net: pd.DataFrame, factors: dict, close: pd.DataFrame,
           opens: pd.DataFrame, dates) -> list:
    """후보마다 네 보유기간의 승률차·수익률차를 표 두 장으로 낸다."""
    total = int(net.to_numpy().sum())
    rets = {hold: (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
            for hold, _ in HOLDS}
    print(f"\n{'#' * 112}\n### {title} — 그물 {total:,}자리\n{'#' * 112}")

    table = {}
    for name, mask in factors.items():
        factor = mask.reindex(index=dates, columns=close.columns).fillna(False)
        share = (factor.to_numpy() & net.to_numpy()).sum() / max(total, 1) * 100
        table[name] = {"share": share,
                       "holds": {label: edge(rets[hold], net, factor)
                                 for hold, label in HOLDS}}

    for key, unit, caption in (("win", "%p", "승률차 — 이 항목이 붙은 자리가 나머지보다 "
                                            "100번 중 몇 번 더 이겼나"),
                               ("ret", "%p", "수익률차 — 가운데값이 나머지보다 몇 %p 높았나")):
        print(f"\n  ── {caption} ──")
        print(f"     {'후보':<26}{'해당':>5}{'합격':>5}   "
              + "".join(f"{n:>9}" for _h, n in HOLDS) + f"{'가장나쁜창':>11}")
        for name, row in table.items():
            cells, worst, passes = "", [], 0
            for _hold, label in HOLDS:
                item = row["holds"][label]
                if not item.get("ok"):
                    cells += f"{'—':>9}"
                    continue
                cells += f"{item[f'{key}_mid']:>+8.1f}{'*' if item['passed'] else ' '}"
                worst.append(item[f"{key}_worst"])
                passes += bool(item["passed"])
            low = f"{min(worst):>+10.1f}" if worst else f"{'—':>10}"
            print(f"     {name:<26}{row['share']:>4.0f}%{passes:>4}/4   {cells}{low}")
        print(f"     (별표 * = 그 보유기간에서 걸러내기 통과 · 단위 {unit})")

    return [(name, row["share"],
             sum(1 for h in row["holds"].values() if h.get("passed")),
             row) for name, row in table.items()]


def _base_name(name: str) -> str:
    """같은 잣대의 여러 컷을 한 이름으로 묶는다.

    '테마 덜 빠졌나 상위3/5/7'은 **한 항목**이다. 컷만 다른 것을 계단에 나란히
    올리면 40·30·20점이 전부 같은 잣대가 돼 순위를 못 가른다
    (2026-08-13 상하님 지적: "하나 안에 여러 개 있는데 그것도 정리 못 하면서").
    """
    for cut in (" 상위3", " 상위5", " 상위7"):
        if name.endswith(cut):
            return name[: -len(cut)]
    if name.startswith("눌린 폭"):
        return "눌린 폭"
    if name.startswith("60일"):
        return "60일 상승폭"
    if name.startswith("변동성"):
        return "변동성"
    if name.startswith("낙폭"):
        return "낙폭"
    return name


def ladder(rows: list, title: str) -> None:
    """2단계 — 통과한 것만 놓고 **승률차 크기**로 계단을 얹는다.

    **한 잣대는 한 번만 올린다** — 컷이 여럿이면 승률차가 가장 큰 것 하나만 쓴다.
    """
    print(f"\n  ── {title} · 계단 후보 (통과 2개 이상 · 해당 10~85%) ──")
    ranked = []
    for name, share, passes, row in rows:
        if passes < 2 or not (10.0 <= share <= 85.0):
            continue
        mids = [h["win_mid"] for h in row["holds"].values()
                if h.get("ok") and h["passed"]]
        worst = [h["win_worst"] for h in row["holds"].values() if h.get("ok")]
        rmids = [h["ret_mid"] for h in row["holds"].values()
                 if h.get("ok") and h["passed"]]
        ranked.append((float(np.mean(mids)), float(np.mean(rmids)),
                       min(worst), passes, share, name))
    ranked.sort(reverse=True)
    # 같은 잣대는 가장 센 컷 하나만 남긴다.
    seen, unique = set(), []
    for item in ranked:
        base = _base_name(item[-1])
        if base in seen:
            continue
        seen.add(base)
        unique.append(item)
    dropped = [i[-1] for i in ranked if i not in unique]
    ranked = unique
    print(f"     {'':<26}{'해당':>5}{'합격':>5}{'승률차':>9}{'수익률차':>10}{'가장나쁜창':>11}")
    for step, (win, ret, worst, passes, share, name) in zip(
            (40, 30, 20, 10, 0, 0, 0, 0, 0, 0, 0, 0), ranked):
        mark = f"{step}점" if step else "  —"
        print(f"     {mark:>4} {name:<24}{share:>4.0f}%{passes:>4}/4"
              f"{win:>+8.1f}p{ret:>+9.1f}p{worst:>+10.1f}p")
    print("     ※ 승률차 큰 순서로 40·30·20·10. 다섯째부터는 안 준다(기준 3).")
    if dropped:
        print("     ※ 같은 잣대의 다른 컷이라 뺀 것: " + " · ".join(dropped))
