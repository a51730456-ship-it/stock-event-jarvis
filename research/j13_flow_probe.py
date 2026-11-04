"""자비스13 종목 수급 — 실제 네이버 자료로 확인 (2026-11-04 상하님 「고쳐라」 → 「1 · 값만 보이게」).

깃허브 컴퓨터에서 ① 바꾸기 전(얼린 그대로 · 수급 못 받음)과 ② jarvis13_flow 를 끼운 뒤를 같은 테마로 견준다.
  · 점수 · 순위가 **한 글자도 안 바뀌었나**(수급은 점수에 안 씀)
  · 수급 값이 실제로 들어오나(ok · 5일 순매수 · 동반 일수)
  · 시장 점수가 같은가 · 시장 카드용 대표종목 수급이 들어오나
저장소에는 아무것도 안 쓴다(재기만).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jarvis4_data as j4  # noqa: E402  — 얼린 파일 · 부르기만
import jarvis13_flow  # noqa: E402


def _snapshot(label: str):
    # 수급 칸만 비운다 — 시세·테마 자료는 앞 판 것을 그대로 써서, 사이에 주가가 움직여 점수가 바뀌는 일이 없게(견줌이 공정하게).
    with j4._CACHE_LOCK:
        for key in [key for key in j4._CACHE if isinstance(key, tuple) and key and key[0] == "flow"]:
            j4._CACHE.pop(key, None)
    overview = j4.get_market_overview()
    ranking = j4.get_theme_rankings()
    rows = [row for row in (ranking.get("rows") or []) if row.get("ok", True)][:3]
    leaders = {}
    for theme in rows:
        result = j4.get_theme_leaders(theme, market_score=overview.get("score") or 0, theme_score=theme.get("score") or 0)
        leaders[theme["name"]] = [(r["code"], r.get("rank"), r.get("score"), (r.get("flow") or {}).get("ok"),
                                   (r.get("flow") or {}).get("both_buy_days5")) for r in (result.get("rows") or [])]
    foreign = jarvis13_flow.for_display(overview.get("foreign"))
    print(f"\n== {label} · 시장 점수 {overview.get('score')} · 국면 {overview.get('regime')} · "
          f"대표종목 수급 ok={foreign.get('ok')} 5일={foreign.get('net5_amount')}", flush=True)
    for name, items in leaders.items():
        print(f"   {name}: " + " | ".join(f"{c} {k}위 {s} 수급{'○' if ok else '×'} 동반{d}" for c, k, s, ok, d in items), flush=True)
    return overview.get("score"), {name: [(c, k, s) for c, k, s, _o, _d in items] for name, items in leaders.items()}, leaders


def main() -> int:
    for code in ("005930", "000660"):
        before = j4.get_stock_flow(code)
        print(f"바꾸기 전 {code}: ok={before.get('ok')} {before.get('error', '')}", flush=True)
    score_a, rank_a, _ = _snapshot("① 바꾸기 전(얼린 그대로)")
    jarvis13_flow.install(j4)
    for code in ("005930", "000660"):
        after = j4.get_stock_flow(code)
        print(f"바꾼 뒤 {code}: ok={after.get('ok')} 기준일 {after.get('latest_date')} 5일 {after.get('net5_amount')} "
              f"동반5 {after.get('both_buy_days5')} 줄 {len(after.get('rows') or [])}", flush=True)
    score_b, rank_b, leaders_b = _snapshot("② jarvis13_flow 끼운 뒤")
    same_rank = rank_a == rank_b
    flow_ok = sum(1 for items in leaders_b.values() for item in items if item[3])
    total = sum(len(items) for items in leaders_b.values())
    print(f"\n결과 — 시장 점수 같음 {score_a == score_b} ({score_a} → {score_b}) · 테마 종목 순위·점수 같음 {same_rank} · "
          f"수급 받은 종목 {flow_ok}/{total}", flush=True)
    if not same_rank:
        for name in rank_a:
            if rank_a.get(name) != rank_b.get(name):
                print(f"   다름 {name}: {rank_a.get(name)} → {rank_b.get(name)}", flush=True)
    return 0 if (score_a == score_b and same_rank and flow_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
