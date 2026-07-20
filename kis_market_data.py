"""한국투자증권 Open API의 국내 업종 현재지수를 읽기 전용으로 조회한다.

주문·잔고·자동매매 API는 포함하지 않는다. 호출자가 명시적으로 조회할 때만 REST
요청을 한 번 수행하며, 키가 없거나 호출에 실패하면 예외 대신 ``ok=False``를 반환한다.
"""

import json
import math
import threading
import time
from datetime import datetime, time as datetime_time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


_BASE_URL = "https://openapi.koreainvestment.com:9443"
_TOKEN_PATH = "/oauth2/tokenP"
_INDEX_PATH = "/uapi/domestic-stock/v1/quotations/inquire-index-price"
_INDEX_TR_ID = "FHPUP02100000"
_INDEX_CODES = {"^KS11": "0001", "^KQ11": "1001", "KOSPI": "0001", "KOSDAQ": "1001"}
_SEOUL_TZ = ZoneInfo("Asia/Seoul")

_TOKEN_CACHE = {"app_key": None, "token": None, "expires_at": 0.0}
_TOKEN_LOCK = threading.Lock()


def _now_seoul():
    return datetime.now(_SEOUL_TZ)


def _is_regular_session(now):
    return now.weekday() < 5 and datetime_time(9, 0) <= now.time() <= datetime_time(15, 30)


def _request_json(method, url, *, headers=None, payload=None, timeout=5):
    body = None
    final_headers = dict(headers or {})
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        final_headers.setdefault("Content-Type", "application/json")
    request = Request(url, data=body, headers=final_headers, method=method)
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _positive_finite(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _finite(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _get_access_token(app_key, app_secret, request_json):
    now_monotonic = time.monotonic()
    with _TOKEN_LOCK:
        if (
            _TOKEN_CACHE["app_key"] == app_key
            and _TOKEN_CACHE["token"]
            and _TOKEN_CACHE["expires_at"] > now_monotonic + 60
        ):
            return _TOKEN_CACHE["token"]

        response = request_json(
            "POST",
            f"{_BASE_URL}{_TOKEN_PATH}",
            headers={"Accept": "text/plain", "charset": "UTF-8"},
            payload={
                "grant_type": "client_credentials",
                "appkey": app_key,
                "appsecret": app_secret,
            },
            timeout=5,
        )
        token = str(response.get("access_token") or "").strip()
        if not token:
            return None
        try:
            expires_in = max(300, int(response.get("expires_in") or 3600))
        except (TypeError, ValueError):
            expires_in = 3600
        _TOKEN_CACHE.update(
            {"app_key": app_key, "token": token, "expires_at": now_monotonic + expires_in - 30}
        )
        return token


def get_index_snapshot(ticker, app_key, app_secret, *, now=None, request_json=None):
    """KOSPI/KOSDAQ 현재지수를 조회해 기존 장중 스냅샷 형태로 반환한다.

    한국 정규장 시간에만 시도한다. 서버 응답에 기준시각 필드가 없으므로 ``as_of_time``은
    요청이 성공한 한국 시각이며, 정규장 밖에서는 종가를 장중가로 오인하지 않도록 조회하지
    않는다. 테스트에서는 ``request_json``을 주입해 외부 연결 없이 검증할 수 있다.
    """
    index_code = _INDEX_CODES.get(str(ticker).upper())
    if not index_code:
        return {"ok": False, "error": "지원하지 않는 국내 지수"}
    app_key = str(app_key or "").strip()
    app_secret = str(app_secret or "").strip()
    if not app_key or not app_secret:
        return {"ok": False, "error": "KIS API 키 없음"}

    now = now or _now_seoul()
    if now.tzinfo is None:
        now = now.replace(tzinfo=_SEOUL_TZ)
    else:
        now = now.astimezone(_SEOUL_TZ)
    if not _is_regular_session(now):
        return {"ok": False, "error": "한국 정규장 시간이 아님"}

    request_json = request_json or _request_json
    try:
        token = _get_access_token(app_key, app_secret, request_json)
        if not token:
            return {"ok": False, "error": "KIS 접근토큰 발급 실패"}
        query = urlencode({"FID_COND_MRKT_DIV_CODE": "U", "FID_INPUT_ISCD": index_code})
        response = request_json(
            "GET",
            f"{_BASE_URL}{_INDEX_PATH}?{query}",
            headers={
                "Content-Type": "application/json",
                "authorization": f"Bearer {token}",
                "appkey": app_key,
                "appsecret": app_secret,
                "tr_id": _INDEX_TR_ID,
                "custtype": "P",
            },
            timeout=5,
        )
        if str(response.get("rt_cd")) != "0":
            return {"ok": False, "error": "KIS 현재지수 조회 실패"}
        output = response.get("output")
        if isinstance(output, list):
            output = output[0] if output else None
        if not isinstance(output, dict):
            return {"ok": False, "error": "KIS 현재지수 데이터 없음"}

        current = _positive_finite(output.get("bstp_nmix_prpr"))
        change_pct = _finite(output.get("bstp_nmix_prdy_ctrt"))
        if current is None or change_pct is None or change_pct <= -100:
            return {"ok": False, "error": "KIS 현재지수 유효성 실패"}
        previous_close = current / (1 + change_pct / 100)
        if not math.isfinite(previous_close) or previous_close <= 0:
            return {"ok": False, "error": "KIS 전일 종가 계산 실패"}

        return {
            "ok": True,
            "current": current,
            "prev_close": previous_close,
            "change_pct": change_pct,
            "asof": now.strftime("%H:%M"),
            "as_of_time": now.strftime("%H:%M"),
            "as_of_date": now.strftime("%Y-%m-%d"),
            "data_kind": "intraday",
            "source": "한국투자증권",
        }
    except Exception:
        return {"ok": False, "error": "KIS 현재지수 조회 실패"}


def _clear_token_cache_for_tests():
    with _TOKEN_LOCK:
        _TOKEN_CACHE.update({"app_key": None, "token": None, "expires_at": 0.0})


# ===========================================================================
# 장중 수급 조회 (2026-07-20 추가) — 전부 읽기 전용 시세/수급 API다.
# 주문·잔고 API는 여기에도 넣지 않는다.
#
# 아래 경로와 TR ID는 사용자가 확인한 KIS 공식 문서 기준이다. 키가 없거나 응답이
# 예상과 다르면 예외 대신 ok=False를 돌려주고, 호출부는 그 항목만 UNKNOWN으로
# 처리한다. 절대 0으로 대체하지 않는다.
# ===========================================================================

_PROGRAM_TODAY_PATH = "/uapi/domestic-stock/v1/quotations/comp-program-trade-today"
_PROGRAM_TODAY_TR_ID = "FHPPG04600101"

_PROGRAM_INVESTOR_PATH = "/uapi/domestic-stock/v1/quotations/investor-program-trade-today"
_PROGRAM_INVESTOR_TR_ID = "HHPPG046600C1"

_INVESTOR_TIME_PATH = "/uapi/domestic-stock/v1/quotations/inquire-investor-time-by-market"
_INVESTOR_TIME_TR_ID = "FHPTJ04030000"

_SECTOR_CATEGORY_PATH = "/uapi/domestic-stock/v1/quotations/inquire-index-category-price"
_SECTOR_CATEGORY_TR_ID = "FHPUP02140000"

_FUTURES_PRICE_PATH = "/uapi/domestic-futureoption/v1/quotations/inquire-price"
_FUTURES_PRICE_TR_ID = "FHMIF10000000"


def _kis_get(path, tr_id, params, app_key, app_secret, request_json, *, timeout=6):
    """공통 GET 호출. 성공하면 (True, output), 실패하면 (False, 사유)."""
    app_key = str(app_key or "").strip()
    app_secret = str(app_secret or "").strip()
    if not app_key or not app_secret:
        return False, "KIS API 키 없음"

    request_json = request_json or _request_json
    try:
        token = _get_access_token(app_key, app_secret, request_json)
        if not token:
            return False, "KIS 접근토큰 발급 실패"
        response = request_json(
            "GET",
            f"{_BASE_URL}{path}?{urlencode(params)}",
            headers={
                "Content-Type": "application/json",
                "authorization": f"Bearer {token}",
                "appkey": app_key,
                "appsecret": app_secret,
                "tr_id": tr_id,
                "custtype": "P",
            },
            timeout=timeout,
        )
    except Exception:
        return False, "KIS 조회 실패"

    if str(response.get("rt_cd")) != "0":
        return False, "KIS 응답 오류"

    # KIS는 API에 따라 output / output1 / output2를 쓴다. 있는 것을 순서대로 쓴다.
    for field in ("output", "output1", "output2"):
        value = response.get(field)
        if value:
            return True, value
    return False, "KIS 응답에 데이터 없음"


def get_program_trade_intraday(app_key, app_secret, *, market="K", request_json=None):
    """프로그램매매 종합현황(시간) — 최근 약 30분 구간 데이터를 리스트로 돌려준다."""
    ok, payload = _kis_get(
        _PROGRAM_TODAY_PATH,
        _PROGRAM_TODAY_TR_ID,
        {"FID_COND_MRKT_DIV_CODE": "J", "FID_MRKT_CLS_CODE": market},
        app_key,
        app_secret,
        request_json,
    )
    if not ok:
        return {"ok": False, "error": payload, "rows": []}
    rows = payload if isinstance(payload, list) else [payload]
    return {
        "ok": True,
        "rows": [r for r in rows if isinstance(r, dict)],
        "source": "KIS 프로그램매매 종합현황",
    }


def get_program_trade_by_investor(app_key, app_secret, *, market_code="1", request_json=None):
    """투자자별 차익·비차익 프로그램 당일 수급."""
    ok, payload = _kis_get(
        _PROGRAM_INVESTOR_PATH,
        _PROGRAM_INVESTOR_TR_ID,
        {"MRKT_DIV_CLS_CODE": market_code},
        app_key,
        app_secret,
        request_json,
    )
    if not ok:
        return {"ok": False, "error": payload, "rows": []}
    rows = payload if isinstance(payload, list) else [payload]
    return {
        "ok": True,
        "rows": [r for r in rows if isinstance(r, dict)],
        "source": "KIS 투자자별 프로그램매매",
    }


def get_market_investor_intraday(
    app_key, app_secret, *, market_code="999", sector_code="S001", request_json=None
):
    """시장별 투자자매매동향(시간) — 외국인/개인/기관 및 기관 세부 주체."""
    ok, payload = _kis_get(
        _INVESTOR_TIME_PATH,
        _INVESTOR_TIME_TR_ID,
        {"FID_INPUT_ISCD": market_code, "FID_INPUT_ISCD_2": sector_code},
        app_key,
        app_secret,
        request_json,
    )
    if not ok:
        return {"ok": False, "error": payload, "row": None}
    row = payload[0] if isinstance(payload, list) and payload else payload
    if not isinstance(row, dict):
        return {"ok": False, "error": "KIS 투자자 수급 형식 오류", "row": None}
    return {"ok": True, "row": row, "source": "KIS 시장별 투자자매매동향"}


def get_sector_category_prices(app_key, app_secret, *, market="K", request_json=None):
    """업종별 지수·거래대금 목록. 전기전자 업종코드를 이름으로 찾을 때 쓴다."""
    ok, payload = _kis_get(
        _SECTOR_CATEGORY_PATH,
        _SECTOR_CATEGORY_TR_ID,
        {
            "FID_COND_MRKT_DIV_CODE": "U",
            "FID_INPUT_ISCD": "0001",
            "FID_COND_SCR_DIV_CODE": "20214",
            "FID_MRKT_CLS_CODE": market,
            "FID_BLNG_CLS_CODE": "0",
        },
        app_key,
        app_secret,
        request_json,
    )
    if not ok:
        return {"ok": False, "error": payload, "rows": []}
    rows = payload if isinstance(payload, list) else [payload]
    return {"ok": True, "rows": [r for r in rows if isinstance(r, dict)], "source": "KIS 업종별 시세"}


def get_kospi200_futures_snapshot(app_key, app_secret, *, futures_code=None, request_json=None):
    """KOSPI200 선물 현재가와 베이시스.

    최근월물 코드는 하드코딩하지 않는다. 호출부가 설정값으로 넘기지 않으면
    조회하지 않고 미확인으로 돌려준다 — 임의 종목코드로 엉뚱한 값을 만들지 않기 위함이다.
    """
    code = str(futures_code or "").strip()
    if not code:
        return {
            "ok": False,
            "error": "KOSPI200 최근월물 코드 미설정",
            "futures_code": None,
        }

    ok, payload = _kis_get(
        _FUTURES_PRICE_PATH,
        _FUTURES_PRICE_TR_ID,
        {"FID_COND_MRKT_DIV_CODE": "F", "FID_INPUT_ISCD": code},
        app_key,
        app_secret,
        request_json,
    )
    if not ok:
        return {"ok": False, "error": payload, "futures_code": code}

    row = payload[0] if isinstance(payload, list) and payload else payload
    if not isinstance(row, dict):
        return {"ok": False, "error": "KIS 선물 시세 형식 오류", "futures_code": code}

    from kr_intraday_flow import parse_kis_number

    return {
        "ok": True,
        "futures_code": code,
        "price": parse_kis_number(row.get("futs_prpr")),
        "change_pct": parse_kis_number(row.get("futs_prdy_ctrt")),
        "basis": parse_kis_number(row.get("basis")),
        "market_basis": parse_kis_number(row.get("mrkt_basis")),
        "open_interest": parse_kis_number(row.get("hts_otst_stpl_qty")),
        "open_interest_change": parse_kis_number(row.get("otst_stpl_qty_icdc")),
        "as_of": _now_seoul(),
        "source": "KIS",
    }
