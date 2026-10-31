"""자비스12 「오늘 움직인 까닭」 — 크게 움직인 종목의 **그 장 시간대** 뉴스 제목 (2026-10-31 상하님 「자비스12에도 넣어라」).

자비스13 것(jarvis13_movers)을 미국 쪽으로 옮겼다. 받는 일은 화면이 관심종목 카드·「종목 뉴스」와 **같은 공책**
(jarvis3_briefing_news · 얼린 파일 — 부르기만 한다)으로 한다. 이 파일은 받은 뉴스에서 그 장 시간대에 나온 제목만
골라 줄이는 셈만 한다.

그 장 시간대 — 미국 동부 시각으로 **앞 장 마감(16:00) 뒤부터 그 장 날 20:00까지**. 장 전·장중 뉴스가 그날 움직임에
걸리게 한다. 그 장 = 평일 9:30 뒤면 그날, 아니면 앞 평일. 휴장일(공휴일)은 셈에 없다 — 휴장 다음 날은 시간대가 하루
짧다(화면에 적지 않는 작은 틈 · 문서에 적음).
까닭을 지어내지 않는다 — 「그 장 시간대 나온 제목 · 원인 확인 아님」으로만 보인다. 점수·판정에 안 쓴다.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

MODULE_REVISION = 2026103101
MOVE_PCT = 3.0            # 이만큼 넘게 움직인 종목만 받는다(화면에 그대로 적는다)
TITLES_PER_STOCK = 2
MAX_STOCKS = 8            # 넘으면 크게 움직인 차례로 자른다(화면에 적는다)
NY = ZoneInfo("America/New_York")


def movers(rows, *, threshold: float = MOVE_PCT) -> list[dict]:
    """|등락률| ≥ threshold 인 종목 — 크게 움직인 차례. rows 는 ticker · name · change_pct 를 가진 dict."""
    out, seen = [], set()
    for row in rows or []:
        ticker = str(row.get("ticker") or "").strip().upper()
        try:
            change = float(row.get("change_pct"))
        except (TypeError, ValueError):
            continue
        if not ticker or ticker in seen or change != change or abs(change) < threshold:
            continue
        seen.add(ticker)
        out.append({"ticker": ticker, "name": str(row.get("name") or ticker), "change_pct": change})
    return sorted(out, key=lambda item: abs(item["change_pct"]), reverse=True)


def _prev_weekday(day: date) -> date:
    day -= timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def session_window(now: datetime | None = None) -> tuple[date, datetime, datetime]:
    """(그 장 날, 시작, 끝) — 시작·끝은 UTC. 앞 장 16:00 ET 뒤 ~ 그 장 날 20:00 ET."""
    now = (now or datetime.now(timezone.utc)).astimezone(NY)
    day = now.date()
    if day.weekday() >= 5 or now.time() < time(9, 30):
        day = _prev_weekday(day)
    start = datetime.combine(_prev_weekday(day), time(16, 0), NY)
    end = datetime.combine(day, time(20, 0), NY)
    return day, start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def _when(item) -> datetime | None:
    try:
        stamp = datetime.fromisoformat(str(item.get("published_at") or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def in_window(items, start: datetime, end: datetime, *, limit: int = TITLES_PER_STOCK) -> list[dict]:
    """시간대 안 제목만, 새것부터 limit 개. 날짜 없는 제목은 까닭처럼 붙이지 않는다."""
    picked = []
    for item in items or []:
        when = _when(item)
        text = str(item.get("brief") or item.get("headline") or "").strip()
        if when is None or not text or not (start < when <= end):
            continue
        picked.append({"title": text, "link": str(item.get("url") or "").strip(),
                       "when": when.astimezone(NY), "source": str(item.get("source") or "")})
    picked.sort(key=lambda entry: entry["when"], reverse=True)
    return picked[:limit]
