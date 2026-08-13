"""상승장 눌림매수 — **시장 조건 셋에서 다 살아남는 것만** 고른다 (2026-08-13).

상하님 지시 — *"다시 나스닥 10년치 검토 다시 해보고 정리해서 브리핑해봐."*

## 왜 다시 재나

한 가지 시장 조건(나스닥 고점 −3% 안)에서만 재면 **그 조건에서만 통한 값**을
1등으로 올리게 된다. 창을 2·3·4년으로 미는 것과 같은 이유로, **시장 조건도
갈라서** 세 번 재고 **셋 다에서 같은 방향이 나오는 것만** 쓴다.

  느슨 — 나스닥 200일선 위 + 고점 −10% 안 (지금 앱 그물)
  중간 — 나스닥 200일선 위 + 고점 −6% 안
  빡빡 — 나스닥 200일선 위 + 고점 −3% 안 (거의 신고가)

**하락장(200일선 아래)은 셋 다에서 빠진다.** 상하님 지시 — "하락장일 때 종목
검색하지 말고."

## 무엇을 내나

후보마다 세 조건의 **승률차 평균**과 **통과 개수**를 나란히 놓고,

  ○ 굳음  — 세 조건 다 +이고, 두 조건 이상에서 통과 2개↑
  △ 흔들림 — 조건에 따라 방향이 바뀜
  ✗ 거꾸로 — 세 조건 다 −

로 가른다. **굳음만 배점 후보다.**

쓰는 법:  python research/us_pullback_final.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

from us_edge_table import HOLDS, edge  # noqa: E402
from us_pullback_logic import build  # noqa: E402

GATES = ((-3.0, "고점 -3% 안"), (-6.0, "고점 -6% 안"), (-10.0, "고점 -10% 안"))


def main() -> None:
    results: dict[str, dict] = {}
    meta = []
    for gate, label in GATES:
        env = build(gate)
        net, close, opens, dates = (env["net"], env["close"], env["opens"],
                                    env["dates"])
        total = env["total"]
        meta.append((label, env["market_days"], total))
        rets = {hold: (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
                for hold, _ in HOLDS}
        for axis, factors in env["axes"].items():
            for name, mask in factors.items():
                factor = mask.reindex(index=dates, columns=close.columns).fillna(False)
                share = (factor.to_numpy() & net.to_numpy()).sum() / max(total, 1) * 100
                wins, rets_mid, passes = [], [], 0
                for hold, _label in HOLDS:
                    item = edge(rets[hold], net, factor)
                    if not item.get("ok"):
                        continue
                    wins.append(item["win_mid"])
                    rets_mid.append(item["ret_mid"])
                    passes += bool(item["passed"])
                key = f"{axis[0]} {name}"
                results.setdefault(key, {})[label] = {
                    "win": float(np.mean(wins)) if wins else float("nan"),
                    "ret": float(np.mean(rets_mid)) if rets_mid else float("nan"),
                    "passes": passes, "share": share,
                }

    print(f"\n{'=' * 118}\n### 상승장 눌림매수 — 시장 조건 셋에서 다시 잰 것"
          f"\n{'=' * 118}")
    for label, days, total in meta:
        print(f"  {label:<14}나스닥이 그런 날 {days:>5,}일 · 그물 {total:>6,}자리")

    rows = []
    for name, per_gate in results.items():
        wins = [per_gate[label]["win"] for _g, label in GATES if label in per_gate]
        passes = [per_gate[label]["passes"] for _g, label in GATES if label in per_gate]
        shares = [per_gate[label]["share"] for _g, label in GATES if label in per_gate]
        rets_ = [per_gate[label]["ret"] for _g, label in GATES if label in per_gate]
        if len(wins) < 3 or any(np.isnan(w) for w in wins):
            continue
        usable = all(10.0 <= s <= 85.0 for s in shares)
        if all(w > 0 for w in wins) and sum(p >= 2 for p in passes) >= 2 and usable:
            grade = "○ 굳음"
        elif all(w < 0 for w in wins):
            grade = "✗ 거꾸로"
        else:
            grade = "△ 흔들림"
        rows.append((grade, float(np.mean(wins)), wins, rets_, passes, shares, name))

    order = {"○ 굳음": 0, "△ 흔들림": 1, "✗ 거꾸로": 2}
    rows.sort(key=lambda r: (order[r[0]], -r[1]))

    print(f"\n  {'후보':<30}{'판정':<8}{'해당':>5}   "
          + "".join(f"{label:>14}" for _g, label in GATES) + f"{'평균':>8}")
    print(f"  {'':<30}{'':<8}{'':>5}   "
          + "".join(f"{'승률/통과':>14}" for _g in GATES))
    last = None
    for grade, mean_win, wins, rets_, passes, shares, name in rows:
        if grade != last:
            print()
            last = grade
        cells = "".join(f"{w:>+9.1f}/{p}/4" for w, p in zip(wins, passes))
        print(f"  {name:<30}{grade:<8}{np.mean(shares):>4.0f}%   {cells}{mean_win:>+7.1f}p")

    print(f"\n{'=' * 118}\n### 배점 후보 — **굳음**만 (승률차 순)\n{'=' * 118}")
    print(f"  {'':<32}{'해당':>5}{'승률차':>9}{'수익률차':>10}   시장 조건별 승률차")
    for grade, mean_win, wins, rets_, passes, shares, name in rows:
        if grade != "○ 굳음":
            continue
        detail = " · ".join(f"{w:+.1f}" for w in wins)
        print(f"  {name:<32}{np.mean(shares):>4.0f}%{mean_win:>+8.1f}p"
              f"{np.mean(rets_):>+9.1f}p   {detail}")
    print("\n  ※ 굳음 = 세 시장 조건 다 +이고, 둘 이상에서 걸러내기 2개↑ 통과, 해당 10~85%.")


if __name__ == "__main__":
    main()
