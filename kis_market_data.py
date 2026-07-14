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
