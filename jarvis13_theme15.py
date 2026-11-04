"""한국 「상위 테마 5개 · 각 1~3위」 목록 (2026-11-04 상하님 「해라」 · docs/KR_THEME_SPEC.md 3-1-1).

자비스12(jarvis3_data.find_theme_top_picks)와 같은 모양을 한국 셈으로 만든다 — 테마 순위(그물 그대로) 위 5개 테마에서
화면 「테마 종목 1~6위」와 같은 대장주 순위(jarvis4_data.get_theme_leaders · 얼린 파일 · 부르기만)의 1~3위.
줄에는 테마 등수(theme_place)와 테마 안 등수(rank)를 함께 싣는다. **쌓기만** 한다 — 점수·판정·순위 7 에 안 쓴다.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

MODULE_REVISION = 2026110401
TOP_THEMES = 5
PER_THEME = 3
KIND = "theme15"
DATA_DIR = Path(__file__).resolve().parent / "data" / "picklist_theme15"
_SEOUL = ZoneInfo("Asia/Seoul")


def find_theme_top_picks(theme_rows, *, data, market_score: float = 0,
                         top_themes: int = TOP_THEMES, per_theme: int = PER_THEME) -> dict:
    """상위 테마 top_themes 개 × 각 per_theme 종목. data 는 jarvis4_data(시험에서는 가짜)."""
    ordered = [row for row in (theme_rows or []) if row.get("ok", True)]
    ordered = sorted(ordered, key=lambda row: float(row.get("score") or 0), reverse=True)[: max(1, int(top_themes))]
    errors: list[str] = []

    def _one(pair):
        place, theme_row = pair
        name = str(theme_row.get("name") or "")
        try:
            return place, name, theme_row, data.get_theme_leaders(
                theme_row, market_score=market_score, theme_score=float(theme_row.get("score") or 0))
        except Exception as exc:
            return place, name, theme_row, {"ok": False, "error": str(exc), "rows": []}

    picked: list[dict] = []
    if ordered:
        with ThreadPoolExecutor(max_workers=4) as pool:
            done = list(pool.map(_one, enumerate(ordered, 1)))
        for place, name, theme_row, result in sorted(done, key=lambda item: item[0]):
            if not (result or {}).get("ok"):
                errors.append(f"{name}: {(result or {}).get('error') or '조회 실패'}")
                continue
            for row in list(result.get("rows") or [])[: max(1, int(per_theme))]:
                row = dict(row)
                row["sources"] = [name]
                row["themes"] = row.get("themes") or [name]
                row["theme_place"] = place
                row["theme_name"] = name
                row["theme_score"] = float(theme_row.get("score") or 0)
                picked.append(row)
    return {"ok": bool(picked), "rows": picked, "themes": [str(row.get("name") or "") for row in ordered],
            "top_themes": len(ordered), "per_theme": int(per_theme), "errors": errors,
            "checked_at": datetime.now(_SEOUL).isoformat(timespec="seconds")}


def load_all(store, out_dir: Path | str | None = None) -> list[dict]:
    """쌓인 날 전부의 줄(옛것부터). 폴더가 없거나 못 읽으면 빈 목록 — 화면은 그대로 돈다."""
    base = Path(out_dir) if out_dir else DATA_DIR
    rows: list[dict] = []
    try:
        for day in sorted(store.available_dates("KR", out_dir=base)):
            rows.extend(row for row in store.load_rows(day, "KR", out_dir=base) if str(row.get("list_kind")) == KIND)
    except Exception:
        return []
    return rows
