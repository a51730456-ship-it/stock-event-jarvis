"""한국 「상위 테마 5개 · 각 1~3위」 날마다 쌓기 (2026-11-04 상하님 「해라」 · docs/KR_THEME_SPEC.md 3-1-1).

마감 뒤 테마 순위(그물 그대로)를 받아 jarvis13_theme15.find_theme_top_picks 로 15종목을 고르고,
data/picklist_theme15/{날짜}.KR.csv 에 날짜별 목록과 **같은 칸**으로 쓴다(얼린 picklist_store 의 rows_from_result ·
save_rows 를 부르기만 한다 — 한국 theme15 를 감추는 규칙은 그대로). 지난 며칠치의 빈 매수금액(다음 거래일 시가)도
같은 창고 함수로 채운다(날짜별 목록과 같은 방식). **지우지 않는다**(CLAUDE.md 10-1). 휴장일은 찍지 않는다.
깃허브 「자비스13 상위 테마 5개 저장」(.github/workflows/j13_theme15_collect.yml)이 평일 16:20 KST 에 돌린다.
"""
from __future__ import annotations

import os
import pathlib
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import jarvis4_data as data  # noqa: E402  — 얼린 파일 · 부르기만
import jarvis13_theme15 as theme15  # noqa: E402
import picklist_collector as collector  # noqa: E402  — 마지막으로 끝난 장 날짜 셈을 그대로 쓴다
import picklist_store as store  # noqa: E402  — 얼린 파일 · 부르기만

OUT = pathlib.Path(os.environ.get("J13_THEME15_OUT") or theme15.DATA_DIR)
SEOUL = ZoneInfo("Asia/Seoul")


def main() -> int:
    trade_date = collector._last_closed_session("KR")
    traded = getattr(data, "kr_market_traded_today", lambda: None)()
    if traded is False:
        print(f"KR {trade_date} — 한국 증시가 쉬는 날이라 찍지 않습니다", flush=True)
        return 0
    overview = data.get_market_overview() or {}
    ranking = data.get_theme_rankings() or {}
    rows = list(ranking.get("rows") or [])
    if not rows:
        print(f"테마 순위를 못 받았습니다: {ranking.get('error')}", flush=True)
        return 1
    result = theme15.find_theme_top_picks(rows, data=data, market_score=float(overview.get("score") or 0))
    saved_at = datetime.now(SEOUL).isoformat(timespec="seconds")
    lines = store.rows_from_result(result, market="KR", list_kind=theme15.KIND, trade_date=trade_date,
                                   saved_at=saved_at, limit=theme15.TOP_THEMES * theme15.PER_THEME)
    path = store.save_rows(lines, trade_date=trade_date, market="KR", out_dir=OUT)
    print(f"KR {trade_date} · 테마 {result.get('themes')} · {len(lines)}줄 · {path or '안 씀(빈 결과)'}", flush=True)
    for error in result.get("errors") or []:
        print(f"  못 받음 — {error}", flush=True)
    try:
        filled = store.backfill_buy_opens("KR", out_dir=OUT)
    except Exception as exc:
        filled = {}
        print(f"  매수금액 채우기 실패 — {exc}", flush=True)
    for day, count in sorted((filled or {}).items()):
        print(f"  {day} 매수금액 {count}줄 채움", flush=True)
    return 0 if lines else 1


if __name__ == "__main__":
    sys.exit(main())
