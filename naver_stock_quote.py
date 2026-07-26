"""네이버 실시간 시세 묶음 조회 — 당일 시가·고가·저가를 얻기 위한 것.

왜 필요한가 (2026-07-26)
------------------------
자비스5 수집기가 긁는 네이버 **테마 상세** 페이지에는 현재가·등락률·거래량·
거래대금·전일거래량만 있고 **당일 고가·저가가 없다.** 그런데 종가매매 조건
두 가지가 그 값을 쓴다.

    종가 위치  = (현재가 − 당일저가) ÷ (당일고가 − 당일저가)
    윗꼬리 비율 = (당일고가 − 현재가) ÷ (당일고가 − 당일저가)

이 값은 **지나가면 소급할 수 없다.** 15:18에 안 찍어 두면 그날 윗꼬리가
얼마였는지 영원히 알 수 없다. 그래서 수집기에 붙인다.

실측 (2026-07-26)
-----------------
- 한 번에 **1,000종목까지** 된다. 1,200부터 응답이 깨진다(URL 길이 한계).
  그래서 800씩 끊는다.
- 2,342종목을 800씩 3번 = 약 0.4초. 3분마다 도는 수집기에 사실상 공짜다.
- 시간외(`overMarketPriceInfo`)와 KRX+NXT 통합(`integratedPriceInfo`)도 같이
  준다. 지금은 저장만 하고 쓰지 않는다 — 시간외 이탈 감시에 나중에 쓴다.

이 파일은 조회만 한다. 점수도 판정도 만들지 않는다.
"""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

MODULE_REVISION = 2026072601

_URL = "https://polling.finance.naver.com/api/realtime/domestic/stock/{codes}"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com/",
}

# 1,000까지 되지만 여유를 둔다. 종목코드가 6자리라 800이면 URL이 5,700자쯤이다.
BATCH_SIZE = 800

_HTTP_LOCAL = threading.local()


def _session() -> requests.Session:
    session = getattr(_HTTP_LOCAL, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update(_HEADERS)
        _HTTP_LOCAL.session = session
    return session


def _number(value) -> float | None:
    """'266,000' 같은 문자열도, 숫자도 받는다. 못 읽으면 None."""
    if value is None:
        return None
    try:
        result = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return result if result == result and result not in (float("inf"), float("-inf")) else None


def _pick(payload: dict) -> dict:
    """응답 한 종목분에서 우리가 쓸 값만 꺼낸다."""
    over = payload.get("overMarketPriceInfo") or {}
    integrated = payload.get("integratedPriceInfo") or {}
    trade_stop = (payload.get("tradeStopType") or {}).get("name")
    return {
        "code": str(payload.get("itemCode") or "").strip(),
        "price": _number(payload.get("closePriceRaw") or payload.get("closePrice")),
        "day_open": _number(payload.get("openPriceRaw") or payload.get("openPrice")),
        "day_high": _number(payload.get("highPriceRaw") or payload.get("highPrice")),
        "day_low": _number(payload.get("lowPriceRaw") or payload.get("lowPrice")),
        "volume": _number(payload.get("accumulatedTradingVolumeRaw")),
        "trading_value": _number(payload.get("accumulatedTradingValueRaw")),
        "market_cap": _number(payload.get("marketValueFullRaw")),
        "market_status": payload.get("marketStatus"),
        "traded_at": payload.get("localTradedAt"),
        # 거래정지 종목은 고가·저가가 0으로 오거나 값이 안 변한다. 뒤에서
        # 걸러낼 수 있도록 상태를 그대로 남긴다.
        "tradable": payload.get("tradableStatusCode") == "ok" and trade_stop == "TRADING",
        # 시간외·통합(KRX+NXT). 지금은 보관만 한다.
        "after_price": _number(over.get("overPrice")),
        "after_volume": _number(over.get("accumulatedTradingVolumeRaw")),
        "after_session": over.get("tradingSessionType"),
        "integrated_volume": _number(integrated.get("accumulatedTradingVolumeRaw")),
    }


def _fetch_batch(codes: tuple[str, ...], *, timeout: float = 10) -> dict[str, dict]:
    if not codes:
        return {}
    response = _session().get(_URL.format(codes=",".join(codes)), timeout=timeout)
    payload = json.loads(response.content.decode("utf-8"))
    result = {}
    for row in payload.get("datas") or []:
        picked = _pick(row)
        if picked["code"]:
            result[picked["code"]] = picked
    return result


def get_quotes(codes, *, batch_size: int = BATCH_SIZE, max_workers: int = 3,
               timeout: float = 10) -> dict[str, dict]:
    """종목코드 목록을 받아 ``{코드: 시세}``를 돌려준다.

    일부 묶음이 실패해도 나머지는 살린다. 수집기는 이 값이 없어도 예전처럼
    돌아야 하므로 여기서 예외를 밖으로 던지지 않는다.
    """
    unique = []
    seen = set()
    for code in codes or []:
        text = str(code).strip()
        if text and text not in seen:
            seen.add(text)
            unique.append(text)
    if not unique:
        return {}

    batches = [
        tuple(unique[index:index + max(1, int(batch_size))])
        for index in range(0, len(unique), max(1, int(batch_size)))
    ]

    quotes: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as executor:
        futures = [executor.submit(_fetch_batch, batch, timeout=timeout) for batch in batches]
        for future in as_completed(futures):
            try:
                quotes.update(future.result())
            except Exception:
                continue  # 한 묶음이 실패해도 수집 자체는 계속된다
    return quotes


def intraday_location(quote: dict) -> float | None:
    """당일 가격범위에서 현재가가 어디쯤인지 (0=저가, 1=고가).

    고가와 저가가 같으면(상한가 직행·거래정지) 나눌 수 없으므로 None이다.
    0으로 나누기를 막는 것이 이 함수의 존재 이유다.
    """
    high, low, price = quote.get("day_high"), quote.get("day_low"), quote.get("price")
    if high is None or low is None or price is None or high <= low:
        return None
    return max(0.0, min(1.0, (price - low) / (high - low)))


def upper_wick_ratio(quote: dict) -> float | None:
    """당일 변동폭 대비 윗꼬리 비율 (0=고가 마감, 1=고가에서 저가까지 밀림)."""
    location = intraday_location(quote)
    return None if location is None else 1.0 - location
