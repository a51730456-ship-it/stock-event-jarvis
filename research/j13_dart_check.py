"""자비스13 「📢 최근 공시」를 실제 OpenDART 로 한 번 받아 본다 (2026-11-04 상하님 「DART 하자」).

깃허브 비밀 칸의 DART_API_KEY 를 쓴다(값은 찍지 않는다). 화면과 같은 함수(jarvis13_disclosures.recent)를 부른다.
열쇠가 없으면 「열쇠 없음」만 찍고 끝낸다(실패로 만들지 않는다 — 열쇠를 넣으시면 다시 돌린다).
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import disclosure_data  # noqa: E402
import jarvis13_disclosures as dart  # noqa: E402

SAMPLES = (("005930", "삼성전자"), ("000660", "SK하이닉스"), ("035420", "NAVER"), ("247540", "에코프로비엠"))


def main() -> int:
    key = (os.environ.get("DART_API_KEY") or "").strip()
    if not key:
        print("열쇠 없음 — 깃허브 비밀 칸에 DART_API_KEY 가 없습니다. 시험을 건너뜁니다.", flush=True)
        return 0
    started = time.time()
    ok = 0
    for code, name in SAMPLES:
        out = dart.recent(key, code, fetch_map=disclosure_data.fetch_dart_corp_code_map,
                          fetch_list=disclosure_data.fetch_recent_dart_disclosures)
        rows = out.get("rows") or []
        if out.get("status") in ("정상", "데이터 없음"):
            ok += 1
        print(f"{name}({code}) · {out.get('status')} · {len(rows)}건 · ⚠ {sum(1 for r in rows if r['caution'])}건", flush=True)
        for row in rows[:3]:
            print(f"   {row['day']} {'[⚠] ' if row['caution'] else ''}{row['title']}", flush=True)
    print(f"\n끝 · {ok}/{len(SAMPLES)} 됨 · {time.time() - started:.0f}초", flush=True)
    return 0 if ok == len(SAMPLES) else 1


if __name__ == "__main__":
    sys.exit(main())
