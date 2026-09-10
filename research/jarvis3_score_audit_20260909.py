# -*- coding: utf-8 -*-
"""자비스3 배점 구조 점검 — 2026-09-09

**무엇을 재나** — 앞날 수익률이 아니라 **배점 자체의 성질**을 잰다.
과거 수익률 검증은 시세 자료가 있어야 하지만, 아래 일곱 가지는 시세 없이
배점 함수만으로 답이 나온다. 그래서 노트북·온라인 어디서든 돌아간다.

**돌리는 법** — python research/jarvis3_score_audit_20260909.py

**고치지 않는다.** 이 파일은 재기만 한다. 배점을 바꾸는 것은 CLAUDE.md 0-1에
따라 상하님께 먼저 여쭙는다.
"""
from __future__ import annotations

import ast
import math
import random
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
J3 = ROOT / "jarvis3_data.py"
SWING = ROOT / "us_swing_selector.py"


def _load_j3_scoring():
    """운영 코드의 배점 함수를 **그대로** 떼어 온다.

    pandas가 있으면 jarvis3_data를 직접 불러 쓰고, 없으면 원문에서 함수만
    떼어 낸다. 어느 쪽이든 **여기서 배점 식을 새로 쓰지 않는다** — 새로 쓰면
    운영과 조용히 갈라진다.
    """
    try:
        import jarvis3_data as j3  # noqa: F401
        return (j3._general_rank_points, j3._apply_general_theme_scores,
                j3._general_stock_score, dict(j3.GENERAL_THEME_SCORE_WEIGHTS),
                "jarvis3_data 직접 불러옴")
    except Exception:
        pass

    src = J3.read_text(encoding="utf-8")
    ns: dict = {}
    exec(
        "def _finite(v):\n"
        "    try:\n"
        "        f = float(v)\n"
        "    except (TypeError, ValueError):\n"
        "        return None\n"
        "    return f if f == f and abs(f) != float('inf') else None\n",
        ns,
    )

    def grab(name: str) -> str:
        return re.search(rf"^def {name}\(.*?(?=^def |\Z)", src, re.S | re.M).group(0)

    tree = ast.parse(src)
    weights = next(
        ast.literal_eval(n.value)
        for n in ast.walk(tree)
        if isinstance(n, ast.Assign)
        and any(getattr(t, "id", "") == "GENERAL_THEME_SCORE_WEIGHTS" for t in n.targets)
    )
    ns["GENERAL_THEME_SCORE_WEIGHTS"] = weights
    ns["GENERAL_THEME_SCORE_MAX"] = round(sum(weights.values()), 1)
    ns["GENERAL_THEME_STATUS_LEAD"] = round(ns["GENERAL_THEME_SCORE_MAX"] * 0.75, 1)
    ns["GENERAL_THEME_STATUS_WATCH"] = round(ns["GENERAL_THEME_SCORE_MAX"] * 0.60, 1)
    ns["GENERAL_STOCK_SCORE_MAX"] = 100.0
    for fn in ("_scale", "_general_rank_points", "_apply_general_theme_scores",
               "_general_stock_score"):
        exec(grab(fn), ns)
    return (ns["_general_rank_points"], ns["_apply_general_theme_scores"],
            ns["_general_stock_score"], weights, "원문에서 함수만 떼어 냄(pandas 없음)")


def _theme_sizes() -> list[int]:
    tree = ast.parse(J3.read_text(encoding="utf-8"))
    themes = next(
        ast.literal_eval(n.value)
        for n in ast.walk(tree)
        if isinstance(n, ast.Assign)
        and any(getattr(t, "id", "") == "US_THEMES" for t in n.targets)
    )
    return [len(t["stocks"]) for t in themes], themes


def _rows(level: float, seed: int, n: int, spread: float = 8.0, clip: bool = False):
    """테마 n개를 만든다. level 은 시장 전체 수준."""
    rnd = random.Random(seed)
    out = []
    for _ in range(n):
        s120 = level + rnd.gauss(0, spread)
        s60 = level / 2 + rnd.gauss(0, spread)
        share = 50 + rnd.gauss(0, 15)
        if clip:
            share = max(0.0, min(100.0, share))
        out.append({
            "strength_120": s120,
            "strength_60": s60,
            "strong_members": share,
            # 운영 코드 _compute_theme_rankings 와 **같은 식**
            "strength_change": s60 - s120 / 2,
        })
    return out


def check1_translation(apply, n):
    print("\n[검사1] 시장 전체가 통째로 오르내려도 테마 점수가 달라지나")
    base = _rows(0.0, 11, n)
    apply(base)
    b = [r["score"] for r in base]
    for lv in (-60, -30, 30, 60):
        o = _rows(float(lv), 11, n)
        apply(o)
        diff = max(abs(x - y) for x, y in zip(b, [r["score"] for r in o]))
        print(f"   전체 {lv:+4d}%p 이동 → 점수 최대 차이 {diff:.4f}")
    print("   → 0.0000 이면 배점이 시장 수준을 전혀 보지 않는다는 뜻이다.")


def check2_mean_fixed(apply, n, runs=30):
    print("\n[검사2] 어떤 시장이든 전체 테마 평균점수가 고정되나")
    means, leads = [], []
    for seed in range(runs):
        rows = _rows(random.Random(seed).uniform(-40, 40), seed, n)
        apply(rows)
        means.append(statistics.mean(r["score"] for r in rows))
        leads.append(sum(1 for r in rows if r["status"] == "강함"))
    print(f"   서로 다른 {runs}개 시장에서 평균점수 최소 {min(means):.2f} · 최대 {max(means):.2f}")
    print(f"   '강함' 개수 최소 {min(leads)} · 최대 {max(leads)} · 평균 {statistics.mean(leads):.1f}")


def check3_stock_in_crash(gs):
    print("\n[검사3] 시장과 '똑같이' 움직인 종목이 상대강도 80점 중 몇 점을 받나")
    print(f"   {'상황':32}{'종목':>7}{'시장':>7}{'총점':>7}   항목")
    for label, s, m, fh in [
        ("대폭락, 시장과 똑같이 빠짐", -45.0, -45.0, -45.0),
        ("보합, 시장과 똑같음", 0.0, 0.0, -10.0),
        ("강세, 시장과 똑같이 오름", 35.0, 35.0, -2.0),
    ]:
        sc, parts = gs({"ret60": s, "ret120": s, "from_high_pct": fh},
                       {"ret60": m, "ret120": m})
        print(f"   {label:32}{s:>6.0f}%{m:>6.0f}%{sc:>7.1f}   {parts}")
    print("   → 시장과 같이 움직이면 상대강도 두 항목이 각각 절반씩 붙는다.")


def check4_redundant():
    print("\n[검사4] '최근 힘 증가' 10점이 새 정보를 담고 있나")
    src = J3.read_text(encoding="utf-8")
    line = re.search(r"strength_change = \(?(.+?)\n", src).group(1).strip()
    print(f"   운영 코드 식: strength_change = {line}")
    rnd = random.Random(3)
    ok = sum(1 for _ in range(2000)
             if (lambda a, b: abs((a - b / 2) - (a - b / 2)) < 1e-12)(
                 rnd.gauss(0, 10), rnd.gauss(0, 10)))
    print(f"   3개월·6개월 강도만 알면 이 값이 정해지는가: {ok}/2000")
    print("   → 세 항목(6개월 35 + 3개월 30 + 힘 증가 10 = 75점)이 숫자 두 개에서 나온다.")


def check5_swing_zero():
    print("\n[검사5] 스윙 배점에서 미달 항목을 0점으로 둘 수 있나")
    src = SWING.read_text(encoding="utf-8")
    lines = src.splitlines()
    fn = next(n for n in ast.parse(src).body
              if isinstance(n, ast.FunctionDef) and n.name == "validate_config")
    ns = {"math": math, "Mapping": dict}
    exec("\n".join(lines[fn.lineno - 1:fn.end_lineno]), ns)
    validate = ns["validate_config"]
    base = {"rs60": 25.0, "rs120": 25.0, "pullback": 20.0, "theme": 10.0,
            "volume": 8.0, "breadth": 5.0, "rebound": 7.0}
    entry = {"watch_start_day": 1, "watch_end_day": 3, "pullback_watch_near": 0.015,
             "pullback_min": 0.03, "pullback_priority_start": 0.06, "pullback_max": 0.10}

    def run(w, label):
        try:
            validate({"weights": w, "entry": entry})
            print(f"   {label:44} 통과")
        except ValueError as exc:
            print(f"   {label:44} 거부 → {exc}")

    run(dict(base), "지금 그대로 (합 100)")
    for key, pts in (("breadth", 5), ("volume", 8), ("rebound", 7)):
        w = dict(base)
        w[key] = 0.0
        run(w, f"'{key} {pts}점'이 미달이라 0점 (합 {100 - pts})")
    w = dict(base)
    w["breadth"] = 0.0
    w["rs60"] = 30.0
    run(w, "0으로 두고 뺀 5점을 rs60에 얹기 (합 100)")
    print("   → 0점으로 두려면 반드시 다른 항목에 나눠 얹어야 한다.")
    print("     CLAUDE.md 0-1 마는 그 비례 배분을 금지한다.")


def check6_size_bias(apply, sizes, runs=3000):
    print(f"\n[검사6] 테마 효과가 전혀 없을 때 크기만으로 순위가 갈리나 ({runs:,}회)")
    rnd = random.Random(0)
    top3 = {i: 0 for i in range(len(sizes))}
    for _ in range(runs):
        rows = []
        for k in sizes:
            rs60 = [rnd.gauss(0, 25) for _ in range(k)]
            rs120 = [rnd.gauss(0, 25) for _ in range(k)]
            m60, m120 = statistics.mean(rs60), statistics.mean(rs120)
            share = sum(1 for a, b in zip(rs60, rs120) if a > 0 and b > 0) / k * 100
            rows.append({"strength_120": m120, "strength_60": m60,
                         "strong_members": share, "strength_change": m60 - m120 / 2})
        apply(rows)
        for i in sorted(range(len(rows)), key=lambda j: -rows[j]["score"])[:3]:
            top3[i] += 1
    by_size: dict[int, list[float]] = {}
    for i, k in enumerate(sizes):
        by_size.setdefault(k, []).append(top3[i] / runs * 100)
    fair = 3 / len(sizes) * 100
    print(f"   {'구성종목수':>9}{'테마수':>6}{'상위3 진입률':>13}")
    for k in sorted(by_size):
        print(f"   {k:>9}{len(by_size[k]):>6}{statistics.mean(by_size[k]):>12.1f}%")
    small = [v for k, vs in by_size.items() if k <= 8 for v in vs]
    large = [v for k, vs in by_size.items() if k >= 12 for v in vs]
    print(f"   작은 테마(6~8종목) {statistics.mean(small):.1f}% · "
          f"큰 테마(12종목↑) {statistics.mean(large):.1f}% · 공평하면 {fair:.1f}%")


def check7_paper_trail(weights, themes):
    print("\n[검사7] 이 배점의 근거가 코드·문서에 남아 있나")
    src = J3.read_text(encoding="utf-8")
    block = src[src.index("GENERAL_THEME_SCORE_WEIGHTS"):]
    block = src[max(0, src.index("GENERAL_THEME_SCORE_WEIGHTS") - 400):
                src.index("GENERAL_THEME_SCORE_MAX")]
    hits = len(re.findall(r"실측|research/", block))
    print(f"   GENERAL 배점 둘레 주석의 '실측·research/' 언급 횟수: {hits}")
    for name in ("CRASH_SCORE_WEIGHTS", "THEME_SCORE_WEIGHTS"):
        b = src[max(0, src.index(name) - 2500):src.index(name)]
        print(f"   (견줌) {name:22} 둘레 주석 언급 횟수: "
              f"{len(re.findall(r'실측|research/', b))}")
    docs = ROOT / "docs"
    found = [p.name for p in docs.glob("*.md")
             if re.search(r"강한 종목 수|최근 힘 증가|GENERAL_THEME_SCORE",
                          p.read_text(encoding="utf-8", errors="ignore"))]
    print(f"   docs/ 에서 이 배점을 설명한 문서: {found or '없음'}")
    counts: dict[str, int] = {}
    for t in themes:
        for s in t["stocks"]:
            counts[s] = counts.get(s, 0) + 1
    dup = sorted(((v, k) for k, v in counts.items() if v >= 3), reverse=True)
    print(f"   3개 이상 테마에 겹치는 종목: "
          f"{', '.join(f'{k}({v})' for v, k in dup) or '없음'}")


def main() -> None:
    rank_points, apply, gs, weights, how = _load_j3_scoring()
    sizes, themes = _theme_sizes()
    print("=" * 68)
    print("자비스3 배점 구조 점검 — 2026-09-09")
    print(f"배점 함수: {how}")
    print(f"테마 배점: {weights} (합 {sum(weights.values()):.0f})")
    print(f"테마 {len(sizes)}개 · 구성종목 {min(sizes)}~{max(sizes)}개")
    print("=" * 68)
    check1_translation(apply, len(sizes))
    check2_mean_fixed(apply, len(sizes))
    check3_stock_in_crash(gs)
    check4_redundant()
    check5_swing_zero()
    check6_size_bias(apply, sizes)
    check7_paper_trail(weights, themes)
    print("\n" + "=" * 68)
    print("이 파일은 재기만 한다. 배점 변경은 CLAUDE.md 0-1에 따라 먼저 여쭙는다.")
    print("=" * 68)


if __name__ == "__main__":
    main()
