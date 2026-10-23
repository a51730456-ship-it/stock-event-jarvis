"""자비스3 급락 후 반등장 목록을 오늘 자료로 그대로 돌려 본다 (2026-10-23 상하님 「자비스3 도 과거 기준이 아니다」).

자비스3 화면이 부르는 jarvis3_data.find_crash_rebound_stocks() 를 그대로 부르고 결과를 적는다 — 얼린 계산(옛 기준·배점) 그대로인지 본다.
"""
from __future__ import annotations

import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import jarvis3_data as j3  # noqa: E402

result = j3.find_crash_rebound_stocks()
print("ok", result.get("ok"), "· 까닭", result.get("reason") or result.get("error"), "· j12 표시", result.get("j12_fixed"))
print("칸(규칙):", [(r.get("key"), r.get("label"), r.get("band")) for r in result.get("rules") or []])
ref = result.get("reference") or {}
print("기준:", {k: ref.get(k) for k in ("reference_date", "days_in_band", "last_in_band")} if isinstance(ref, dict) else ref)
print("시장:", {k: (result.get("market") or {}).get(k) for k in ("drop_pct", "state")})
rows = list(result.get("rows") or [])
print("보이는 줄", len(rows), "· 칸별", dict(Counter(row.get("bucket") for row in rows)), "· 최대", result.get("result_limit"))
for row in rows:
    print(f"  {row.get('pullback_rank'):>2} {row.get('ticker'):<6} {row.get('bucket')} {row.get('bucket_label')} "
          f"고점 대비 {row.get('judged_from_high_pct')} 점수 {row.get('score')}")
