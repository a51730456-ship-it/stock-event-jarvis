"""자비스13 「오늘 움직인 까닭」 — 크게 움직인 종목의 **같은 날** 뉴스 제목 (2026-10-31 · 상하님 「다 넣어라」 ③).

화면은 **누를 때만** 받는다 — 자비스12 「종목 뉴스」 규칙(받는 데 종목당 1~3초 · 2026-10-09)과 같다. 이 파일은 받은 뉴스에서
그 종목이 움직인 날(시세의 마지막 거래일)에 나온 제목만 골라 줄이는 셈만 한다. 받는 일은 화면이 news_data 로 한다.

까닭을 지어내지 않는다 — 「같은 날 나온 제목 · 원인 확인 아님」으로만 보인다. 점수·판정에 안 쓴다.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

MODULE_REVISION = 2026103101
MOVE_PCT = 3.0            # 이만큼 넘게 움직인 종목만 받는다 — 받는 수를 줄인다(화면에 그대로 적는다)
TITLES_PER_STOCK = 2
MAX_STOCKS = 8            # 한 번에 받는 종목 수 — 넘으면 크게 움직인 차례로 자른다(화면에 적는다)


def movers(rows, *, threshold: float = MOVE_PCT) -> list[dict]:
    """|등락률| ≥ threshold 인 종목 — 크게 움직인 차례. rows 는 code · name · change_pct · day 를 가진 dict."""
    out = []
    for row in rows or []:
        try:
            change = float(row.get("change_pct"))
        except (TypeError, ValueError):
            continue
        if change != change or abs(change) < threshold or not row.get("code"):
            continue
        out.append({"code": str(row["code"]), "name": str(row.get("name") or row["code"]),
                    "change_pct": change, "day": str(row.get("day") or "")[:10]})
    return sorted(out, key=lambda item: abs(item["change_pct"]), reverse=True)


def same_day(items, day: str) -> list[dict]:
    """그날(YYYY-MM-DD · 서울 시각) 나온 뉴스만. 날을 모르면 빈 목록 — 날짜 없는 제목을 까닭처럼 붙이지 않는다."""
    day = str(day or "")[:10]
    if len(day) != 10:
        return []
    return [item for item in (items or []) if str(item.get("pub_date") or "")[:10] == day]


def pick(items, name: str, code: str, *, classify=None, limit: int = TITLES_PER_STOCK) -> list[dict]:
    """같은 날 제목 가운데 「기업 직접 재료 후보」(news_data 1차 분류)를 먼저, 그다음 나머지 — limit 개."""
    scored = []
    for order, item in enumerate(items or []):
        level = ""
        if classify is not None:
            try:
                level = str((classify(item, name, code) or {}).get("level") or "")
            except Exception:
                level = ""
        scored.append((0 if level == "기업 직접 재료 후보" else 1, order, item, level))
    scored.sort(key=lambda entry: (entry[0], entry[1]))
    return [{"title": str(item.get("title") or "제목 없음"),
             "link": str(item.get("originallink") or item.get("link") or "").strip(),
             "when": str(item.get("pub_date") or "")[:16], "level": level}
            for _rank, _order, item, level in scored[:limit]]


def fetch_all(targets, fetch, *, workers: int = 4) -> dict:
    """{code: 받은 결과} — 종목마다 나눠 받는다. 하나가 실패해도 나머지는 그대로(그 종목만 실패 결과)."""
    targets = list(targets or [])
    if not targets:
        return {}

    def _one(target):
        try:
            return target["code"], fetch(target)
        except Exception as exc:          # 받다 터져도 화면은 살아 있어야 한다
            return target["code"], {"status": "조회 오류", "message": str(exc)[:200], "data": []}

    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(targets)))) as pool:
        return dict(pool.map(_one, targets))
