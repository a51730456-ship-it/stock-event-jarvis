"""네이버 금융의 KOSPI/KOSDAQ 현재지수를 읽기 전용으로 조회한다.

공식 계약형 시세 API가 아닌 네이버 금융 화면의 JSON 응답을 사용하므로 언제든 형식이
바뀔 수 있다. 호출자는 실패를 정상적인 상황으로 취급하고 다른 자료로 대체해야 한다.
자동 반복 조회는 하지 않으며, 사용자가 허용한 기존 한국장 조회 흐름에서 한 번만 호출한다.
"""

import json
import math
from datetime import datetime, time as datetime_time, timedelta
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


_BASE_URL = "https://polling.finance.naver.com/api/realtime/domestic/index"
_INDEX_CODES = {"^KS11": "KOSPI", "^KQ11": "KOSDAQ", "KOSPI": "KOSPI", "KOSDAQ": "KOSDAQ"}
_SEOUL_TZ = ZoneInfo("Asia/Seoul")
_MAX_STALENESS = timedelta(minutes=5)


def _now_seoul():
    return datetime.now(_SEOUL_TZ)


def _is_regular_session(now):
    return now.weekday() < 5 and datetime_time(9, 0) <= now.time() <= datetime_time(15, 30)


def _request_json(url, *, timeout=5):
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "Referer": "https://finance.naver.com/",
            "User-Agent": "Mozilla/5.0",
        },
        method="GET",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _finite_number(value):
    try:
        number = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _parse_traded_at(value):
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_SEOUL_TZ)
    return parsed.astimezone(_SEOUL_TZ)


def get_index_snapshot(ticker, *, now=None, request_json=None):
    """오늘 장중 현재지수를 기존 가격 결과 구조로 반환한다.

    네이버 응답 자체의 ``localTradedAt``을 기준 시각으로 사용한다. 오늘 자료가 아니거나
    5분 넘게 멈춘 값, 장이 열려 있지 않은 응답은 장중가로 인정하지 않는다.
    """
    index_code = _INDEX_CODES.get(str(ticker).upper())
    if not index_code:
        return {"ok": False, "error": "지원하지 않는 국내 지수"}

    now = now or _now_seoul()
    if now.tzinfo is None:
        now = now.replace(tzinfo=_SEOUL_TZ)
    else:
        now = now.astimezone(_SEOUL_TZ)
    if not _is_regular_session(now):
        return {"ok": False, "error": "한국 정규장 시간이 아님"}

    request_json = request_json or _request_json
    try:
        response = request_json(f"{_BASE_URL}/{index_code}", timeout=5)
        rows = response.get("datas") if isinstance(response, dict) else None
        if not isinstance(rows, list):
            return {"ok": False, "error": "네이버 현재지수 데이터 없음"}
        row = next(
            (
                item
                for item in rows
                if isinstance(item, dict) and str(item.get("itemCode") or "").upper() == index_code
            ),
            None,
        )
        if not row:
            return {"ok": False, "error": "네이버 현재지수 항목 없음"}
        if str(row.get("marketStatus") or "").upper() != "OPEN":
            return {"ok": False, "error": "네이버 현재지수가 장중 상태가 아님"}

        current = _finite_number(row.get("closePrice"))
        change_pct = _finite_number(row.get("fluctuationsRatio"))
        traded_at = _parse_traded_at(row.get("localTradedAt"))
        if current is None or current <= 0 or change_pct is None or change_pct <= -100 or traded_at is None:
            return {"ok": False, "error": "네이버 현재지수 유효성 검사 실패"}
        age = now - traded_at
        if traded_at.date() != now.date() or age > _MAX_STALENESS or age < -timedelta(minutes=1):
            return {"ok": False, "error": "네이버 현재지수 기준 시각이 오래됨"}

        previous_close = current / (1 + change_pct / 100)
        if not math.isfinite(previous_close) or previous_close <= 0:
            return {"ok": False, "error": "네이버 전일 종가 계산 실패"}
        as_of_time = traded_at.strftime("%H:%M")
        return {
            "ok": True,
            "current": current,
            "prev_close": previous_close,
            "change_pct": change_pct,
            "asof": as_of_time,
            "as_of_time": as_of_time,
            "as_of_date": traded_at.strftime("%Y-%m-%d"),
            "data_kind": "intraday",
            "source": "네이버 금융 현재지수",
        }
    except Exception:
        return {"ok": False, "error": "네이버 현재지수 조회 실패"}
