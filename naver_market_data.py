"""네이버 금융의 KOSPI/KOSDAQ 현재지수를 읽기 전용으로 조회한다.

공식 계약형 시세 API가 아닌 네이버 금융 화면의 JSON 응답을 사용하므로 언제든 형식이
바뀔 수 있다. 호출자는 실패를 정상적인 상황으로 취급하고 다른 자료로 대체해야 한다.
자동 반복 조회는 하지 않으며, 사용자가 허용한 기존 한국장 조회 흐름에서 한 번만 호출한다.
"""

import json
import math
import re
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


def get_index_daily_close(ticker, *, now=None, request_json=None):
    """장이 닫혀 있어도 네이버가 보여주는 가장 최근 종가를 반환한다.

    2026-07-15 추가: 야간에 yfinance가 당일 종가를 아직 안 올려서 KOSPI/KOSDAQ가
    하루 지난 값(-8.95% 같은)으로 표시되던 문제의 대체 조회 경로. get_index_snapshot()과
    같은 폴링 응답을 쓰지만 장중 검증(marketStatus=OPEN, 5분 신선도)을 요구하지 않고,
    응답의 localTradedAt이 최근 7일 안이기만 하면 그 날짜의 종가로 인정한다.
    실시간 스트리밍이 아니라 호출 시점에 한 번 조회하는 스냅샷이다.
    """
    index_code = _INDEX_CODES.get(str(ticker).upper())
    if not index_code:
        return {"ok": False, "error": "지원하지 않는 국내 지수"}

    now = now or _now_seoul()
    if now.tzinfo is None:
        now = now.replace(tzinfo=_SEOUL_TZ)
    else:
        now = now.astimezone(_SEOUL_TZ)

    request_json = request_json or _request_json
    try:
        response = request_json(f"{_BASE_URL}/{index_code}", timeout=5)
        rows = response.get("datas") if isinstance(response, dict) else None
        if not isinstance(rows, list):
            return {"ok": False, "error": "네이버 지수 데이터 없음"}
        row = next(
            (
                item
                for item in rows
                if isinstance(item, dict) and str(item.get("itemCode") or "").upper() == index_code
            ),
            None,
        )
        if not row:
            return {"ok": False, "error": "네이버 지수 항목 없음"}

        current = _finite_number(row.get("closePrice"))
        change_pct = _finite_number(row.get("fluctuationsRatio"))
        traded_at = _parse_traded_at(row.get("localTradedAt"))
        if current is None or current <= 0 or change_pct is None or change_pct <= -100 or traded_at is None:
            return {"ok": False, "error": "네이버 지수 유효성 검사 실패"}
        if not (timedelta(0) - timedelta(minutes=1) <= now - traded_at <= timedelta(days=7)):
            return {"ok": False, "error": "네이버 지수 기준 시각이 범위를 벗어남"}

        previous_close = current / (1 + change_pct / 100)
        if not math.isfinite(previous_close) or previous_close <= 0:
            return {"ok": False, "error": "네이버 전일 종가 계산 실패"}
        return {
            "ok": True,
            "current": current,
            "prev_close": previous_close,
            "change_pct": change_pct,
            "asof": traded_at.strftime("%Y-%m-%d"),
            "as_of_time": None,
            "as_of_date": traded_at.strftime("%Y-%m-%d"),
            "data_kind": "daily_close",
            "source": "네이버 금융 종가",
        }
    except Exception:
        return {"ok": False, "error": "네이버 지수 종가 조회 실패"}


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


# ---------------------------------------------------------------------------
# 외국인 KOSPI200 선물 순매수 (2026-07-22 추가)
#
# KIS 공개 API에는 선물 투자자별 수급 조회처가 확인되지 않아 그동안 HTS 수동
# 입력만 받았다. 네이버 금융의 '파생 투자자별 매매동향' 페이지(sosok=03 = 선물)가
# 당일 누적 순매수 계약수를 지연 공개하는 것을 확인해(실측: 개인+외국인+기관계+
# 기타법인 = 0 정합) 자동 조회를 붙인다. 지연 공개치이므로 실패하면 조용히
# ok=False를 돌려주고, 호출부는 기존 원칙대로 '확인 필요'로 둔다.
# ---------------------------------------------------------------------------

_FUTURES_INVESTOR_URL = (
    "https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate={date}&sosok=03"
)
_FUTURES_ROW_PATTERN = re.compile(
    r'<td class="date2">\s*([\d.]+)\s*</td>(.*?)</tr>', re.S
)
_FUTURES_NUMBER_PATTERN = re.compile(r">([+-]?[\d,]+)<")


def _request_text(url, *, timeout=8):
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://finance.naver.com/",
        },
        method="GET",
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("euc-kr", errors="replace")


def get_foreign_futures_daily_net(*, now=None, request_text=None):
    """네이버 파생 투자자별 매매동향(선물)에서 외국인 당일 순매수 계약수를 읽는다.

    반환 값은 당일 누적 순매수(계약, 지연 공개치)다. 오늘 자 행이 아직 없으면
    (개장 초·휴장일) ok=False를 돌려주고 임의 값을 만들지 않는다.
    표 열 순서는 날짜 | 개인 | 외국인 | 기관계 | ... 이므로 두 번째 숫자가 외국인이다.
    """
    now = now or _now_seoul()
    if now.tzinfo is None:
        now = now.replace(tzinfo=_SEOUL_TZ)
    else:
        now = now.astimezone(_SEOUL_TZ)

    request_text = request_text or _request_text
    try:
        html = request_text(_FUTURES_INVESTOR_URL.format(date=now.strftime("%Y%m%d")))
        if "외국인" not in html:
            return {"ok": False, "error": "네이버 선물 수급 페이지 형식 변경 가능성"}
        rows = _FUTURES_ROW_PATTERN.findall(html)
        if not rows:
            return {"ok": False, "error": "네이버 선물 수급 데이터 없음"}
        first_date, first_body = rows[0]
        if first_date.strip() != now.strftime("%y.%m.%d"):
            return {"ok": False, "error": "오늘 선물 수급 자료가 아직 없음"}
        numbers = _FUTURES_NUMBER_PATTERN.findall(first_body)
        if len(numbers) < 3:
            return {"ok": False, "error": "네이버 선물 수급 열 부족"}
        net_contracts = int(numbers[1].replace(",", ""))
        return {
            "ok": True,
            "net_contracts": net_contracts,
            "trade_date": now.strftime("%Y-%m-%d"),
            "as_of": now,
            "source": "네이버 선물 투자자동향(지연)",
        }
    except Exception:
        return {"ok": False, "error": "네이버 선물 수급 조회 실패"}
