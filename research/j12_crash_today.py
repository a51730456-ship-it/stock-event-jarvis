"""자비스12 급락 후 반등장 목록을 오늘 자료로 그대로 돌려 본다 (2026-10-23 상하님 「-10~-20% 안 나온다 · 돌려보고 확인해라」).

화면이 부르는 jarvis12_crash.crash_list() 를 같은 인자로 부르고 결과를 그대로 적는다(값을 다시 계산하지 않는다).
야후가 막힌 클라우드 작업 칸에서는 못 돈다 — 깃허브(.github/workflows/j12_band_remeasure.yml)에서 돈다.
"""
from __future__ import annotations

import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import jarvis12_crash as c12  # noqa: E402

ref = c12.reference()
print("기준:", {k: ref.get(k) for k in ("ok", "armed", "reference_date", "reference_drop", "peak_date", "nasdaq_drop",
                                       "today_drop", "as_of", "recovered_on", "reason")})
result = c12.crash_list()
print("ok", result.get("ok"), "· 까닭", result.get("reason") or result.get("error"))
print("칸마다 걸린 종목 수(20개로 자르기 전):", result.get("counts") or result.get("bucket_counts"))
rows = list(result.get("rows") or [])
print("보이는 줄", len(rows), "· 칸별", dict(Counter(row.get("bucket") for row in rows)))
for row in rows:
    print(f"  {row.get('pullback_rank'):>2} {row.get('ticker'):<6} {row.get('bucket')} {row.get('bucket_label')} "
          f"낙폭 {row.get('judged_from_high_pct'):.1f}% 점수 {row.get('score'):.1f} 경고 {row.get('suspicious')}")
print("결과 열쇠:", sorted(result.keys()))
