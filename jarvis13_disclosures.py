"""자비스13 「📢 최근 공시」 — OpenDART(금융감독원 전자공시) 30일 공시 목록과 「⚠ 살펴볼 공시」 딱지 (2026-11-04 상하님 「DART 하자」).

받는 일은 앱에 이미 있는 `disclosure_data`(OpenDART 짧은 받기 · 열쇠를 오류 글에 안 남김)를 **부르기만** 한다.
화면은 **누를 때만** 받는다 — 종목을 누를 때마다 받으면 그만큼 늦어진다(자비스12 「종목 뉴스」와 같은 규칙).
종목코드 → 공시 회사번호(corp_code) 표는 처음 한 번 받아 서버에 하루 담아 둔다(파일 하나 · 몇 초).

딱지는 **낱말로 고른 1차 참고**다 — 공시 제목에 아래 낱말이 있으면 「⚠ 살펴볼 공시」. 좋고 나쁨을 판정하지 않는다.
점수·판정·목록에 안 쓴다. 열쇠(DART_API_KEY)는 스트림릿 비밀 칸에서만 읽는다 — 코드·기록에 적지 않는다.
"""

from __future__ import annotations

import threading
import time
from datetime import date, timedelta

MODULE_REVISION = 2026110401
DAYS = 30
MAP_SECONDS = 24 * 3600
CAUTION_WORDS = ("유상증자", "감자", "전환사채", "신주인수권부사채", "교환사채", "최대주주변경", "최대주주 변경", "소송",
                 "횡령", "배임", "거래정지", "매매거래정지", "상장폐지", "관리종목", "불성실공시", "회생", "감사의견",
                 "부도", "영업정지", "투자주의", "투자경고", "투자위험")
_MAP: dict = {"at": 0.0, "value": None, "status": None}
_LOCK = threading.Lock()


def corp_map(api_key: str, fetch) -> tuple[dict, str]:
    """(종목코드 → {corp_code, corp_name}, 상태). 성공하면 하루 담아 둔다 · 실패는 담지 않는다(다음 누름에 다시)."""
    now = time.time()
    with _LOCK:
        if _MAP["value"] and now - _MAP["at"] < MAP_SECONDS:
            return _MAP["value"], "정상"
    result = fetch(api_key) or {}
    status = str(result.get("status") or "조회 오류")
    data = result.get("data") if status == "정상" else None
    if isinstance(data, dict) and data:
        with _LOCK:
            _MAP.update({"at": now, "value": data, "status": status})
        return data, status
    return {}, status


def caution(title: str) -> bool:
    text = str(title or "").replace(" ", "")
    return any(word.replace(" ", "") in text for word in CAUTION_WORDS)


def recent(api_key: str, code: str, *, fetch_map, fetch_list, today: date | None = None, days: int = DAYS) -> dict:
    """{"status", "rows": [{"day","title","link","caution","filer"}], "start", "end"} — 새것부터."""
    if not api_key:
        return {"status": "열쇠 없음", "rows": []}
    mapping, status = corp_map(api_key, fetch_map)
    if not mapping:
        return {"status": status, "rows": []}
    corp = mapping.get(str(code).strip())
    if not corp:
        return {"status": "공시 회사번호 없음", "rows": []}
    today = today or date.today()
    start, end = (today - timedelta(days=days)).strftime("%Y%m%d"), today.strftime("%Y%m%d")
    result = fetch_list(api_key, corp["corp_code"], start, end) or {}
    status = str(result.get("status") or "조회 오류")
    rows = []
    for item in result.get("data") or []:
        number = str(item.get("rcept_no") or "")
        day = str(item.get("rcept_dt") or "")
        title = str(item.get("report_nm") or "").strip()
        if not number or not title:
            continue
        rows.append({"day": f"{day[:4]}-{day[4:6]}-{day[6:8]}" if len(day) == 8 else day, "title": title,
                     "link": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={number}" if number.isdigit() else "",
                     "caution": caution(title), "filer": str(item.get("flr_nm") or "").strip()})
    return {"status": status, "rows": rows, "start": start, "end": end}
