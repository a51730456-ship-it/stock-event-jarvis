"""자비스4 한국 테마 레이더용 시세·수급·판정 엔진.

기존 자비스1/2/3의 ``price_data.py``·``performance.py``·``jarvis3_data.py``는 사용하거나
수정하지 않는다. 이 모듈의 점수는 확률 예측이 아니라 조건 충족도다.

데이터 경로 (2026-07-22 실조회 검증):
- 테마 목록·구성종목·당일 등락률 : 네이버 금융 테마별 시세(무료, 스크래핑)
- 종목 일봉(추세·신고가·ATR)      : FinanceDataReader
- 종목별 외국인·기관 순매매        : 네이버 종목별 투자자 매매동향
- KOSPI/KOSDAQ 지수               : naver_market_data + FinanceDataReader
- 원/달러                          : FinanceDataReader

pykrx는 쓰지 않는다 — KRX가 로그인(KRX_ID/KRX_PW)을 요구하도록 바뀌어 빈 결과만 온다.
네트워크 실패는 예외 대신 구조화된 오류로 반환하며, 확인되지 않은 값을 0으로 만들지 않는다.
"""

from __future__ import annotations

import logging
import math
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import requests

_log = logging.getLogger(__name__)
_SEOUL = ZoneInfo("Asia/Seoul")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com/",
}

_THEME_LIST_URL = "https://finance.naver.com/sise/theme.naver"
_THEME_DETAIL_URL = "https://finance.naver.com/sise/sise_group_detail.naver?type=theme&no={no}"
_STOCK_FLOW_URL = "https://finance.naver.com/item/frgn.naver?code={code}"

# 화면에 보여줄 테마 수와, 그 후보로 상세 조회할 테마 수.
# 미국테마(자비스3)가 20개를 보여주므로 한국도 20개로 맞춘다(2026-07-25 사용자 지시).
# 화면에서는 1~10위만 펼치고 11위부터는 '더 보기'로 접힌다.
DISPLAY_THEME_COUNT = 20
# 후보 테마 수. 표에는 20개만 보이지만, 눌림목·통과 종목 심사는 이 범위 전체를 훑는다 —
# 30개로 자르면 '은행'(당일 49위) 같은 테마의 좋은 눌림목을 통째로 놓친다(2026-07-22).
CANDIDATE_THEME_COUNT = 40
# 테마당 심사할 구성종목 수 (거래대금 상위부터).
THEME_STOCK_LIMIT = 8
# 이 점수를 넘는 종목은 테마 점수가 낮아도 후보로 인정한다(테마 게이트 면제).
STRONG_STOCK_OVERRIDE = 85.0
THEME_DETAIL_PARSER_VERSION = 2
# 실행 중인 프로세스에 옛 모듈이 남아 있는지 화면이 스스로 알아채기 위한 표식이다.
# 스트림릿은 페이지 파일만 다시 읽고 import된 모듈은 그대로 두는 경우가 있어,
# 화면은 새 코드인데 계산은 옛 코드인 상태가 생긴다(2026-07-24 실제 발생:
# 눌림목 깔때기의 전체·유동성·수급 확인 개수가 전부 0으로 표시됐다).
# 계산 결과나 반환 키를 바꾸면 이 숫자를 올린다.
MODULE_REVISION = 2026072517

_CACHE_LOCK = threading.Lock()
_CACHE: dict = {}
_HTTP_LOCAL = threading.local()


# ---------------------------------------------------------------------------
# 공통 유틸
# ---------------------------------------------------------------------------
def clear_runtime_cache() -> None:
    """사용자가 새로고침을 눌렀을 때 자비스4 메모리 캐시만 비운다.

    직전 테마 순위(previous_theme_names)는 남긴다 — 새로고침은 자료를 다시 받으려는
    것이지 '어제 뭐가 강했는지'를 잊으라는 뜻이 아니다. 이 기억이 사라지면 신규 진입·
    탈락 표시와, 오늘 하루 쉰 강세 테마의 이월 심사가 함께 끊긴다.
    """
    with _CACHE_LOCK:
        keep = _CACHE.get("previous_theme_names")
        _CACHE.clear()
        if keep is not None:
            _CACHE["previous_theme_names"] = keep


def _finite(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _parse_number(text) -> float | None:
    if text is None:
        return None
    cleaned = str(text).replace(",", "").replace("+", "").strip()
    if not cleaned or cleaned in {"-", "--"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _cached(key, ttl_seconds, producer):
    """키별 TTL 캐시. 실패하면 마지막 정상값을 stale로 돌려준다."""
    now = time.time()
    with _CACHE_LOCK:
        entry = _CACHE.get(key)
        if entry and now - entry["at"] < ttl_seconds:
            return entry["value"], False
    try:
        value = producer()
    except Exception as exc:
        _log.warning("jarvis4 fetch failed key=%s: %s", key, exc)
        with _CACHE_LOCK:
            entry = _CACHE.get(key)
        if entry:
            return entry["value"], True
        raise
    with _CACHE_LOCK:
        _CACHE[key] = {"at": now, "value": value}
    return value, False


def _http_session() -> requests.Session:
    """워커별 연결 풀을 재사용해 반복 HTTPS 핸드셰이크를 줄인다."""
    session = getattr(_HTTP_LOCAL, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update(_HEADERS)
        _HTTP_LOCAL.session = session
    return session


def _get_text(url: str, *, timeout: float = 8, retries: int = 2) -> str:
    last_error = None
    for attempt in range(retries + 1):
        try:
            response = _http_session().get(url, timeout=timeout)
            response.raise_for_status()
            response.encoding = "euc-kr"
            return response.text
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.8 * (attempt + 1))
    raise RuntimeError(f"네이버 조회 실패: {last_error}")


def market_phase(now: datetime | None = None) -> dict:
    """한국장 세션 단계."""
    now_seoul = (now or datetime.now(_SEOUL)).astimezone(_SEOUL)
    if now_seoul.weekday() >= 5:
        label = "주말 휴장"
    elif now_seoul.time() < dt_time(8, 30):
        label = "장 시작 전"
    elif now_seoul.time() < dt_time(9, 0):
        label = "장전 동시호가"
    elif now_seoul.time() <= dt_time(15, 20):
        label = "정규장"
    elif now_seoul.time() <= dt_time(15, 30):
        label = "장 마감 동시호가"
    elif now_seoul.time() <= dt_time(18, 0):
        label = "시간외 거래"
    else:
        label = "장 마감"
    return {"label": label, "seoul_time": now_seoul.isoformat(timespec="seconds")}


def is_regular_session(now: datetime | None = None) -> bool:
    now_seoul = (now or datetime.now(_SEOUL)).astimezone(_SEOUL)
    return now_seoul.weekday() < 5 and dt_time(9, 0) <= now_seoul.time() <= dt_time(15, 30)


# ---------------------------------------------------------------------------
# 종목 일봉 (FinanceDataReader)
# ---------------------------------------------------------------------------
def _read_daily(code: str, days: int = 400) -> pd.DataFrame | None:
    import FinanceDataReader as fdr

    end = datetime.now(_SEOUL).date()
    start = end - timedelta(days=days)
    frame = fdr.DataReader(str(code), start.isoformat(), end.isoformat())
    if frame is None or frame.empty or "Close" not in frame.columns:
        return None
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    return frame


def get_daily_frame(code: str, *, ttl_seconds: float = 300) -> pd.DataFrame | None:
    code = str(code).strip()
    try:
        frame, _stale = _cached(("daily", code), ttl_seconds, lambda: _read_daily(code))
    except Exception:
        return None
    return None if frame is None else frame.copy()


def _series_metrics(daily: pd.DataFrame | None, live_price: float | None = None) -> dict:
    """추세·신고가·변동성 지표. 자비스3 _series_metrics의 한국판이다."""
    if daily is None or len(daily) < 25:
        return {"ok": False}
    closes = daily["Close"].dropna().astype(float)
    if len(closes) < 25:
        return {"ok": False}
    live_current = _finite(live_price)
    current = live_current or _finite(closes.iloc[-1])
    if not current:
        return {"ok": False}

    today = datetime.now(_SEOUL).date()
    last_date = pd.Timestamp(closes.index[-1]).date()
    if live_current is not None:
        # 장중 현재가를 따로 넣었으면 일봉의 마지막 값이 오늘 행인지에 따라
        # 전일 종가 위치가 달라진다.
        prev_close = _finite(closes.iloc[-2] if last_date == today and len(closes) >= 2 else closes.iloc[-1])
    else:
        # 종가 일봉 자체를 현재가로 쓸 때는 바로 앞 거래일이 비교 기준이다.
        # 예전 코드는 마지막 종가를 자기 자신과 비교해 등락률이 항상 0%가 됐다.
        prev_close = _finite(closes.iloc[-2]) if len(closes) >= 2 else None

    def ret(days: int):
        index = min(days + 1, len(closes))
        base = _finite(closes.iloc[-index])
        return (current / base - 1) * 100 if base else None

    sma20 = _finite(closes.tail(20).mean())
    sma50 = _finite(closes.tail(50).mean()) if len(closes) >= 50 else None
    sma200 = _finite(closes.tail(200).mean()) if len(closes) >= 200 else None
    # 52주 신고가와 '그 고점을 며칠 전에 찍었나'. 눌림목 판별의 핵심 재료다 —
    # 최근에 신고가를 찍고 지금 눌린 종목이 곧 '올라가던 종목의 조정'이다
    # (2026-07-22 사용자 제안: 복잡한 전체 스캔 대신 이 한 가지만 보면 된다).
    high52 = None
    high52_days_ago = None
    window = daily.tail(248)
    if "High" in daily.columns:
        highs = window["High"].dropna().astype(float)
        if not highs.empty:
            high52 = _finite(highs.max())
            high52_days_ago = int(len(highs) - 1 - highs.values.argmax())
    if high52 is None:
        window_closes = closes.tail(248)
        high52 = _finite(window_closes.max())
        if high52 is not None and not window_closes.empty:
            high52_days_ago = int(len(window_closes) - 1 - window_closes.values.argmax())

    volume_ratio = None
    avg_trading_value = None
    if "Volume" in daily.columns:
        volumes = daily["Volume"].dropna().astype(float)
        if not volumes.empty:
            avg_volume = _finite(volumes.tail(20).mean())
            latest_volume = _finite(volumes.iloc[-1])
            if avg_volume and latest_volume is not None:
                volume_ratio = latest_volume / avg_volume
                avg_trading_value = avg_volume * current  # 원 단위 일평균 거래대금

    atr = atr_pct = None
    if {"High", "Low", "Close"}.issubset(daily.columns) and len(daily) >= 15:
        high = daily["High"].astype(float)
        low = daily["Low"].astype(float)
        prev = daily["Close"].shift(1).astype(float)
        true_range = pd.concat(
            [(high - low), (high - prev).abs(), (low - prev).abs()], axis=1
        ).max(axis=1)
        atr = _finite(true_range.tail(14).mean())
        if atr:
            atr_pct = atr / current * 100

    return {
        "ok": True,
        "current": current,
        "prev_close": prev_close,
        "change_pct": ((current / prev_close - 1) * 100) if prev_close else None,
        "ret5": ret(5),
        "ret20": ret(20),
        "ret60": ret(60) if len(closes) >= 61 else None,
        "sma20": sma20,
        "sma50": sma50,
        "sma200": sma200,
        "high52": high52,
        "high52_days_ago": high52_days_ago,
        "from_high_pct": ((current / high52 - 1) * 100) if high52 else None,
        "volume_ratio": volume_ratio,
        "avg_trading_value": avg_trading_value,
        "atr": atr,
        "atr_pct": atr_pct,
        "last_date": last_date.isoformat(),
        # 당일 시가·고가·저가·종가 (2026-07-24 사용자 요청: 상세에 당일 가격을 함께 본다).
        # 장중에는 일봉 마지막 행이 오늘 행이라 '진행 중인 값'이고, 오늘 행이 아직
        # 없으면 마지막 거래일 값이므로 day_is_today로 구분해 화면에서 알려준다.
        **_day_prices(daily, last_date == today),
    }


def _day_prices(daily: pd.DataFrame, is_today: bool) -> dict:
    """일봉 마지막 행의 시가·고가·저가·종가를 꺼낸다."""
    values = {"day_open": None, "day_high": None, "day_low": None,
              "day_close": None, "day_is_today": bool(is_today)}
    try:
        last = daily.iloc[-1]
    except Exception:
        return values
    for key, column in (("day_open", "Open"), ("day_high", "High"),
                        ("day_low", "Low"), ("day_close", "Close")):
        if column in daily.columns:
            values[key] = _finite(last[column])
    return values


# ---------------------------------------------------------------------------
# 종목별 외국인·기관 수급 (네이버 종목별 투자자 매매동향)
# ---------------------------------------------------------------------------
_FLOW_ROW_PATTERN = re.compile(
    r'<span class="tah p10 gray03">([\d.]+)</span>(.*?)</tr>', re.S
)
_FLOW_NUMBER_PATTERN = re.compile(r'>([+-]?[\d,]+)<')


def _parse_stock_flow(html: str) -> list[dict]:
    """표 열 순서: 날짜 | 종가 | 전일비 | 등락률 | 거래량 | 기관 순매매량 | 외국인 순매매량 | 보유주수 | 보유율."""
    rows = []
    for date_text, body in _FLOW_ROW_PATTERN.findall(html):
        numbers = _FLOW_NUMBER_PATTERN.findall(body)
        if len(numbers) < 4:
            continue
        close = _parse_number(numbers[0])
        volume = _parse_number(numbers[1])
        institution = _parse_number(numbers[2])
        foreign = _parse_number(numbers[3])
        if close is None or institution is None or foreign is None:
            continue
        rows.append({
            "date": date_text.strip(),
            "close": close,
            "volume": volume,
            "institution_net": institution,
            "foreign_net": foreign,
        })
    return rows


# 하루 수급을 네 가지로 나눈다 (2026-07-25 사용자 요청).
#   both_buy  외국인·기관이 둘 다 순매수 = '동반'
#   both_sell 둘 다 순매도
#   one       한쪽만 움직였거나 서로 엇갈림
#   flat      둘 다 거의 0
# 외국인과 기관을 합치지 않는다. 합치면 외국인 +500억 / 기관 −480억인 날이
# '순매수'로 둔갑한다. 한국 증권사 화면(키움 0785·미래에셋 0228 등)도 둘을 합치지
# 않고 따로 보여주며, '동반 순매수'를 별도 개념으로 쓴다. 그 방식을 따른다.
#
# 부호 자체는 주수로 재나 금액으로 재나 같다 — 같은 종목·같은 날이면 종가가 양쪽에
# 똑같이 곱해지기 때문이다. 그래서 여기서 중요한 것은 '얼마나 작으면 무시할까'이고,
# 그 기준을 그날 거래량 대비 비율로 둔다. 큰 종목의 자잘한 매매를 신호로 치지 않는다.
_FLAT_RATIO = 0.0005  # 그날 거래량의 0.05% 미만은 '보합'으로 본다(임의 기준, 화면에 밝힌다)


def _day_flow_mark(row: dict) -> str:
    close = row.get("close") or 0
    volume = row.get("volume") or 0
    flat = abs(volume * close) * _FLAT_RATIO
    foreign = (row.get("foreign_net") or 0) * close
    institution = (row.get("institution_net") or 0) * close
    foreign_buy, foreign_sell = foreign > flat, foreign < -flat
    institution_buy, institution_sell = institution > flat, institution < -flat
    if foreign_buy and institution_buy:
        return "both_buy"
    if foreign_sell and institution_sell:
        return "both_sell"
    # 화면은 동그라미의 왼쪽 반을 외국인, 오른쪽 반을 기관으로 그린다. 그래서 '엇갈렸다'로
    # 뭉치지 않고 누가 사고 누가 팔았는지까지 나눈다(2026-07-25 사용자 선택).
    # 뭉쳐 두면 실제 자료의 절반 이상(8종목 160일 중 101일)이 한 색으로 묻힌다.
    if foreign_buy and institution_sell:
        return "f_buy_i_sell"
    if foreign_sell and institution_buy:
        return "f_sell_i_buy"
    if foreign_buy:
        return "f_buy"
    if foreign_sell:
        return "f_sell"
    if institution_buy:
        return "i_buy"
    if institution_sell:
        return "i_sell"
    return "flat"


def get_stock_flow(code: str, *, ttl_seconds: float = 300) -> dict:
    """종목별 외국인·기관 순매매(주 단위, 최근 20거래일)와 요약 지표."""
    code = str(code).strip()

    def _produce():
        html = _get_text(_STOCK_FLOW_URL.format(code=code))
        rows = _parse_stock_flow(html)
        if not rows:
            raise RuntimeError("수급 표를 찾지 못했습니다")
        return rows

    try:
        rows, stale = _cached(("flow", code), ttl_seconds, _produce)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "rows": []}

    recent5 = rows[:5]
    recent20 = rows[:20]
    combined = [row["foreign_net"] + row["institution_net"] for row in rows]

    def _amount(subset):
        # 순매매 '금액' 근사 = 순매매 주수 × 그날 종가.
        return sum(
            (row["foreign_net"] + row["institution_net"]) * row["close"] for row in subset
        )

    streak = 0
    for value in combined:
        if value > 0:
            streak += 1
        else:
            break

    marks = [_day_flow_mark(row) for row in rows[:20]]   # 최근 날짜가 앞
    return {
        "ok": True,
        "stale": stale,
        "rows": rows,
        # 동반(둘 다 순매수) 일수 — 5일은 세부, 20일은 긴 흐름. 실무에서 5일·20일
        # 두 창을 같이 보라는 권고를 따른다.
        "day_marks": marks,
        "both_buy_days5": sum(1 for mark in marks[:5] if mark == "both_buy"),
        "both_buy_days20": sum(1 for mark in marks if mark == "both_buy"),
        # 20일은 점을 20개 찍을 수 없어 '동반매도 일수'를 숫자로 따로 준다 —
        # 그래야 '꾸준히 매집'과 '사고팔고 반복'이 갈린다(2026-07-25).
        "both_sell_days20": sum(1 for mark in marks if mark == "both_sell"),
        "window5": len(marks[:5]),
        "window20": len(marks),
        "net5_amount": _amount(recent5),
        # 금액만으로는 큰 종목인지 작은 종목인지 감이 안 온다(2026-07-25 사용자 지적).
        # 그날그날 거래대금 합으로 나눠 '거래대금의 몇 %를 사갔나'를 같이 준다.
        # 실무에서도 금액보다 거래대금 대비 비중으로 보라고 권한다.
        "turnover5_amount": sum((row.get("volume") or 0) * (row.get("close") or 0) for row in recent5),
        "net5_ratio_pct": (
            _amount(recent5) / turnover5 * 100
            if (turnover5 := sum((row.get("volume") or 0) * (row.get("close") or 0) for row in recent5))
            else None
        ),
        "net20_amount": _amount(recent20),
        "net5_shares": sum(combined[:5]),
        "buy_streak_days": streak,
        "foreign_net5": sum(row["foreign_net"] for row in recent5),
        "institution_net5": sum(row["institution_net"] for row in recent5),
        "latest_date": rows[0]["date"] if rows else None,
    }


# ---------------------------------------------------------------------------
# 테마 목록·구성종목 (네이버)
# ---------------------------------------------------------------------------
_THEME_ROW_PATTERN = re.compile(
    r'no=(\d+)">([^<]+)</a>.*?col_type2">\s*<span[^>]*>\s*([+-]?[\d.]+)%',
    re.S,
)
_DETAIL_ROW_PATTERN = re.compile(
    r'<td class="name">.*?code=(\d{6})[^>]*>([^<]+)</a>(.*?)</tr>', re.S
)
_DETAIL_PCT_PATTERN = re.compile(r'([+-]?\d+\.\d+)%')


def _parse_theme_detail_numbers(numbers: list[str] | tuple[str, ...]) -> dict:
    """가변 숫자 열을 뒤에서 읽어 현재량·거래대금·전일량을 분리한다.

    전일비가 보합이면 평문 ``0``이 하나 더 잡혀 앞쪽 인덱스가 밀린다.
    마지막 세 열은 현재 거래량, 거래대금(백만원), 전일 거래량 순서다.
    """
    values = list(numbers or [])
    price = _parse_number(values[0]) if values else None
    if len(values) < 4:
        return {
            "price": price,
            "volume": None,
            "trading_value_million": None,
            "trading_value": None,
            "previous_volume": None,
        }

    volume = _parse_number(values[-3])
    trading_value_million = _parse_number(values[-2])
    previous_volume = _parse_number(values[-1])
    if volume is not None and volume < 0:
        volume = None
    if trading_value_million is not None and trading_value_million < 0:
        trading_value_million = None
    if previous_volume is not None and previous_volume < 0:
        previous_volume = None
    return {
        "price": price,
        "volume": volume,
        "trading_value_million": trading_value_million,
        "trading_value": (
            trading_value_million * 1_000_000
            if trading_value_million is not None
            else None
        ),
        "previous_volume": previous_volume,
    }


def _fetch_theme_page(page: int) -> dict:
    url = _THEME_LIST_URL if page == 1 else f"{_THEME_LIST_URL}?page={page}"
    html = _get_text(url)
    found = {}
    for theme_no, name, pct in _THEME_ROW_PATTERN.findall(html):
        found[int(theme_no)] = {
            "no": int(theme_no),
            "name": name.strip(),
            "change_pct": float(pct),
        }
    return found


def get_all_themes(*, ttl_seconds: float = 300) -> dict:
    """네이버 테마별 시세 전체(약 260개)를 당일 평균 등락률과 함께 가져온다."""

    def _produce():
        themes = {}
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(_fetch_theme_page, page): page for page in range(1, 9)}
            for future in as_completed(futures):
                try:
                    themes.update(future.result())
                except Exception:
                    continue
        if not themes:
            raise RuntimeError("테마 목록을 찾지 못했습니다 (페이지 구조 변경 가능성)")
        return themes

    try:
        themes, stale = _cached("theme_list", ttl_seconds, _produce)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "themes": {}}
    return {"ok": True, "stale": stale, "themes": themes}


def _fetch_theme_detail(theme_no: int) -> list[dict]:
    html = _get_text(_THEME_DETAIL_URL.format(no=theme_no))
    stocks = []
    for code, name, body in _DETAIL_ROW_PATTERN.findall(html):
        numbers = _FLOW_NUMBER_PATTERN.findall(body)
        parsed = _parse_theme_detail_numbers(numbers)
        percents = _DETAIL_PCT_PATTERN.findall(body)
        change_pct = float(percents[0]) if percents else None
        if parsed["price"] is None:
            continue
        stocks.append({
            "code": code,
            "name": name.strip(),
            "price": parsed["price"],
            "change_pct": change_pct,
            "volume": parsed["volume"],
            "trading_value_million": parsed["trading_value_million"],
            "trading_value": parsed["trading_value"],
            "previous_volume": parsed["previous_volume"],
            "parser_version": THEME_DETAIL_PARSER_VERSION,
        })
    return stocks


def get_theme_stocks(theme_no: int, *, ttl_seconds: float = 300) -> dict:
    """테마 구성종목 전체(현재가·등락률·거래량)."""

    def _produce():
        stocks = _fetch_theme_detail(int(theme_no))
        if not stocks:
            raise RuntimeError("테마 구성종목을 찾지 못했습니다")
        return stocks

    try:
        stocks, stale = _cached(("theme_detail", int(theme_no)), ttl_seconds, _produce)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "stocks": []}
    return {"ok": True, "stale": stale, "stocks": stocks}


# ---------------------------------------------------------------------------
# 시장 판단 (KOSPI·KOSDAQ·환율·미국 전일·외국인 수급)
# ---------------------------------------------------------------------------
def _index_frame(symbol: str) -> pd.DataFrame | None:
    import FinanceDataReader as fdr

    end = datetime.now(_SEOUL).date()
    start = end - timedelta(days=400)
    frame = fdr.DataReader(symbol, start.isoformat(), end.isoformat())
    if frame is None or frame.empty or "Close" not in frame.columns:
        return None
    return frame.sort_index()



def get_index_sparkline(symbol: str, days: int = 30) -> list:
    """지수의 최근 종가 흐름 — 상단 KOSPI·KOSDAQ 칸에 작은 선을 그린다(2026-07-25).

    이미 받아 둔 일봉(_index_metrics와 같은 캐시)을 그대로 쓴다. 실패하면 빈 목록.
    """
    try:
        frame, _stale = _cached(("index", symbol), 300, lambda: _index_frame(symbol))
    except Exception:
        return []
    if frame is None or frame.empty or "Close" not in frame.columns:
        return []
    return [float(v) for v in frame["Close"].dropna().tail(days).tolist()]


# ---------------------------------------------------------------------------
# 지수 분봉 (2026-07-25) — 왜 두 곳을 이어 붙이는가
#
# 종목에 쓰는 네이버 siseJson은 'KOSPI'·'KPI200'을 받지 않는다(머리줄만 오고 값이
# 없다). 네이버 JSON 차트 api.stock.naver.com은 day·week·month뿐이라 분봉이 없다.
# 둘 다 실제로 불러 확인했다. 그래서 지수 분봉은 두 곳을 이어 붙인다.
#   ① 야후 ^KS11·^KQ11 1분봉 — 09:00~15:00을 한 번에 받는다. 다만 야후가 아는
#      한국장은 15:00에 끝나 마감 30분이 통째로 없고, 장중에는 값이 늦다.
#   ② 네이버 '시간별 시세'(HTML) — 분 단위로 정확하고 15:30까지 있다. 한 쪽에 6줄뿐이라
#      하루를 다 받으려면 66번을 불러야 해서 꼬리(최근 48분)만 받는다.
# 겹치는 구간은 네이버 값을 쓴다. 야후의 지연분과 마감 30분을 이 꼬리가 덮는다.
# ---------------------------------------------------------------------------
_INDEX_YAHOO = {"KOSPI": "^KS11", "KOSDAQ": "^KQ11"}
_INDEX_DAILY = {"KOSPI": "KS11", "KOSDAQ": "KQ11"}
_INDEX_TIME_URL = (
    "https://finance.naver.com/sise/sise_index_time.naver"
    "?code={code}&thistime={stamp}&page={page}"
)
_INDEX_TIME_ROW = re.compile(
    r'class="date">(\d{2}):(\d{2})</td>\s*<td class="number_1">([\d,]+\.\d+)')
# 한 쪽이 6줄이므로 8쪽 = 48분. 야후 지연분과 마감 30분을 함께 덮을 만큼만 받는다.
_INDEX_TAIL_PAGES = 8


def _yahoo_index_minutes(symbol: str) -> list:
    """야후 1분봉에서 마지막으로 열린 장 하루치만 뽑는다. [(시각, 값)]."""
    import warnings

    import yfinance as yf

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        raw = yf.download(
            _INDEX_YAHOO[symbol], period="5d", interval="1m",
            auto_adjust=False, progress=False, threads=False, timeout=15,
        )
    if raw is None or raw.empty or "Close" not in raw:
        raise RuntimeError("야후 지수 분봉이 비어 있습니다")
    closes = raw["Close"]
    if isinstance(closes, pd.DataFrame):
        closes = closes.iloc[:, 0]
    closes = closes.dropna()
    stamps = closes.index
    try:
        stamps = stamps.tz_convert(_SEOUL)
    except (TypeError, AttributeError):
        pass
    if len(closes) < 5:
        raise RuntimeError("야후 지수 분봉이 부족합니다")
    last_day = stamps[-1].date()
    rows = [
        (datetime(stamp.year, stamp.month, stamp.day, stamp.hour, stamp.minute), float(value))
        for stamp, value in zip(stamps, closes.tolist()) if stamp.date() == last_day
    ]
    if len(rows) < 5:
        raise RuntimeError("야후 지수 분봉이 부족합니다")
    return rows


def _index_tail_stamp(day) -> str:
    """네이버 '시간별 시세'의 기준 시각. 지난 장은 15:30, 오늘 장중이면 지금."""
    now = datetime.now(_SEOUL)
    if day < now.date() or now.time() > dt_time(15, 30):
        return f"{day:%Y%m%d}153000"
    return now.strftime("%Y%m%d%H%M00")


def _naver_index_tail(symbol: str, day) -> list:
    """네이버 '시간별 시세'의 마지막 몇 분. [(시각, 값)]."""
    stamp = _index_tail_stamp(day)
    anchor = datetime.strptime(stamp, "%Y%m%d%H%M%S")
    rows = []
    for page in range(1, _INDEX_TAIL_PAGES + 1):
        text = _get_text(_INDEX_TIME_URL.format(code=symbol, stamp=stamp, page=page), timeout=8)
        found = _INDEX_TIME_ROW.findall(text)
        if not found:
            break
        for hour, minute, price in found:
            # 코스피는 천 단위 쉼표가 붙는다("6,690.02") — _parse_number로 벗겨야 한다.
            value = _parse_number(price)
            if value is None:
                continue
            when = datetime.combine(day, dt_time(int(hour), int(minute)))
            # 기준 시각보다 뒤인 줄은 버린다. 장 초반(09:03 같은 때)에 쪽을 넘기면
            # 전날 마감 줄이 딸려 올 수 있는데, 그걸 오늘 것으로 찍으면 하루 그림의
            # 맨 앞에 15:30 값이 박힌다.
            if when <= anchor:
                rows.append((when, value))
    return rows


def _index_prev_close(symbol: str, day) -> float | None:
    """그 세션 '전날' 종가 — 그림의 기준선이다. 같은 날 종가를 쓰면 선이 어긋난다."""
    daily_symbol = _INDEX_DAILY[symbol]
    try:
        frame, _stale = _cached(("index", daily_symbol), 300, lambda: _index_frame(daily_symbol))
    except Exception:
        return None
    if frame is None or frame.empty or "Close" not in frame.columns:
        return None
    closes = frame["Close"].dropna()
    prior = [v for stamp, v in closes.items() if pd.Timestamp(stamp).date() < day]
    return _finite(prior[-1]) if prior else None


def get_index_intraday(symbol: str, *, ttl_seconds: float = 60) -> dict:
    """KOSPI·KOSDAQ 하루치 분봉과 그 전날 종가. 실패하면 빈 dict.

    돌려주는 값은 {"points": 분봉 종가들, "base": 전일 종가, "session": 날짜,
    "last_time": 마지막 시각}이다. 자료가 없으면 그리지 않는다 — 일봉으로 대신
    그렸다가 '기준선 위로 간 적이 없는데 빨간 구간이 있다'는 지적을 받았다(2026-07-25).
    """
    symbol = str(symbol).strip().upper()
    if symbol not in _INDEX_YAHOO:
        return {}

    def _produce():
        body = _yahoo_index_minutes(symbol)
        day = body[-1][0].date()
        merged = dict(body)
        try:
            # 꼬리를 못 받아도 그림은 그린다 — 09:00~15:00만으로도 하루 흐름은 맞다.
            merged.update(_naver_index_tail(symbol, day))
        except Exception as exc:
            _log.warning("jarvis4 지수 꼬리 조회 실패 %s: %s", symbol, exc)
        return [(stamp, merged[stamp]) for stamp in sorted(merged)]

    try:
        rows, _stale = _cached(("index_intraday", symbol), ttl_seconds, _produce)
    except Exception:
        return {}
    if len(rows) < 5:
        return {}
    day = rows[-1][0].date()
    base = _index_prev_close(symbol, day)
    if base is None:
        return {}
    return {
        "points": _thin_points([value for _stamp, value in rows]),
        "base": base,
        "session": day.isoformat(),
        "last_time": rows[-1][0].strftime("%H:%M"),
    }


# 그림은 가로 120px이라 391분을 다 그리면 한 점이 0.3px이다 — 눈에는 똑같은데
# HTML만 지수 한 칸에 45KB가 된다. 폰에서 쓸데없이 무거워지므로 솎아 낸다.
_INDEX_POINT_LIMIT = 180


def _thin_points(points: list) -> list:
    """점이 너무 많으면 일정 간격으로 솎는다. 마지막 값(종가)은 반드시 남긴다."""
    if len(points) <= _INDEX_POINT_LIMIT:
        return points
    step = len(points) // _INDEX_POINT_LIMIT + 1
    thinned = points[::step]
    if (len(points) - 1) % step:
        thinned.append(points[-1])
    return thinned


def _index_metrics(symbol: str, live_price: float | None = None) -> dict:
    try:
        frame, _stale = _cached(("index", symbol), 300, lambda: _index_frame(symbol))
    except Exception:
        return {"ok": False}
    return _series_metrics(frame, live_price)


def _live_index(ticker: str) -> float | None:
    """장중이면 네이버 현재지수, 아니면 None(일봉 종가를 쓴다)."""
    try:
        import naver_market_data

        snapshot = naver_market_data.get_index_snapshot(ticker)
        if snapshot.get("ok"):
            return _finite(snapshot.get("current"))
    except Exception:
        return None
    return None


def get_us_futures_live(*, ttl_seconds: float = 60) -> dict:
    """나스닥100·S&P500 선물 실시간(지연 가능). 한국 장중에 미국 방향을 먼저 보여준다.

    한국장은 미국 선물과 같은 방향으로 움직이는 경우가 많아, 전일 종가만이 아니라
    지금 선물이 어디로 가는지가 장중 판단에 쓸모 있다(2026-07-22 사용자 요청).
    """

    def _produce():
        import warnings

        import yfinance as yf

        # 선물 등락률은 '전일 정산가 대비'다. 24시간 전 값과 비교하면 야간 거래분이
        # 섞여 부호까지 뒤집힌다(2026-07-22 실측: 네이버 -0.41%인데 +0.48%로 나왔다).
        # 그래서 일봉으로 전일 종가(정산가)를 잡고, 오늘 봉의 종가를 현재가로 쓴다.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            raw = yf.download(
                ["NQ=F", "ES=F"], period="5d", interval="1d", group_by="ticker",
                auto_adjust=False, progress=False, threads=True, timeout=12,
            )
        out = {}
        for symbol, label in (("NQ=F", "나스닥100 선물"), ("ES=F", "S&P500 선물")):
            try:
                frame = raw[symbol] if isinstance(raw.columns, pd.MultiIndex) else raw
                closes = frame["Close"].dropna().astype(float)
                if len(closes) < 2:
                    continue
                current = _finite(closes.iloc[-1])
                prev_settle = _finite(closes.iloc[-2])
                if current and prev_settle:
                    out[symbol] = {
                        "label": label,
                        "current": current,
                        "prev_close": prev_settle,
                        "change_pct": (current / prev_settle - 1) * 100,
                    }
            except Exception:
                continue
        if not out:
            raise RuntimeError("미국 선물 시세를 가져오지 못했습니다")
        return out

    try:
        values, stale = _cached("us_futures", ttl_seconds, _produce)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "stale": stale, "values": values}


def _us_previous_session() -> dict:
    """미국 전일 결과 — 한국장은 미국 전일과 갭 상관이 높아 게이트에 넣는다."""
    try:
        import jarvis3_data as j3

        overview = j3.get_market_overview()
        if not overview.get("ok"):
            return {"ok": False}
        rows = overview.get("rows", {})
        # '미국 전일'은 끝난 정규장을 묻는 자리다. change_pct는 지금 값(프리마켓·
        # 시간외 포함) 기준이라 한국 저녁에 보면 전일 -1.2%가 프리마켓 +0.2%로
        # 뒤집혀 보였고, 조건점수 15점까지 잘못 붙었다(2026-07-24 실측 수정).
        #
        # 값은 ETF가 아니라 지수를 쓴다 — 화면에 'S&P500'이라고 적으므로 지수와
        # 같아야 한다(SPY는 -1.23%, 지수는 -1.21%로 조금 어긋난다).
        def _session_change(index_symbol, etf_symbol):
            value = rows.get(index_symbol, {}).get("last_session_change_pct")
            if value is None:
                value = rows.get(etf_symbol, {}).get("last_session_change_pct")
            return value

        spy = _session_change("^GSPC", "SPY")
        qqq = _session_change("^NDX", "QQQ")
        fear_greed = j3.get_fear_greed()
        return {
            "ok": spy is not None and qqq is not None,
            "spy_change": spy,
            "qqq_change": qqq,
            "regime": overview.get("regime"),
            "score": overview.get("score"),
            "fear_greed": fear_greed.get("score") if fear_greed.get("ok") else None,
            "fear_greed_label": fear_greed.get("rating_kr") if fear_greed.get("ok") else None,
            # 게이지 그림에는 지난 값(전일·1주·1개월·1년)까지 필요하다. 자비스4 화면은
            # 규칙상 jarvis3_data를 직접 import하지 않으므로 여기서 통째로 넘긴다.
            "fear_greed_detail": dict(fear_greed) if fear_greed.get("ok") else None,
        }
    except Exception:
        return {"ok": False}


def _market_foreign_flow() -> dict:
    """시장 전체 외국인 수급 — 삼성전자·SK하이닉스 수급을 대표 지표로 쓴다.

    시장 전체 투자자 매매동향은 KIS 키가 있어야 하고 온라인에서만 되므로,
    키 없이도 항상 되는 대표종목 수급을 시장 수급의 근사로 쓴다(대체 신호로 표기).
    """
    total5 = 0.0
    ok_any = False
    details = []
    stocks = []
    for code, label in (("005930", "삼성전자"), ("000660", "SK하이닉스")):
        flow = get_stock_flow(code)
        if flow.get("ok"):
            ok_any = True
            total5 += flow["net5_amount"]
            details.append(f"{label} 5일 {flow['net5_amount'] / 1e8:+,.0f}억")
            # 합계만 주면 화면이 종목별 동반 그림을 못 그린다(2026-07-25 사용자 요청).
            stocks.append({"code": code, "label": label, "flow": flow})
    if not ok_any:
        return {"ok": False}
    return {
        "ok": True, "net5_amount": total5, "detail": " · ".join(details), "stocks": stocks,
    }


def get_market_overview() -> dict:
    """한국 전체시장 판단 — 조건점수 100점."""
    kospi = _index_metrics("KS11", _live_index("^KS11"))
    kosdaq = _index_metrics("KQ11", _live_index("^KQ11"))
    usdkrw = _index_metrics("USD/KRW")
    us_prev = _us_previous_session()
    foreign = _market_foreign_flow()

    if not kospi.get("ok"):
        return {
            "ok": False,
            "error": "KOSPI 지수 자료를 가져오지 못했습니다",
            "phase": market_phase(),
            "rows": {"KOSPI": kospi, "KOSDAQ": kosdaq, "USDKRW": usdkrw},
        }

    score = 0
    reasons = []
    breakdown = []

    def add_check(label: str, passed: bool, points: int, reason: str, *, state=None):
        nonlocal score
        earned = points if passed else 0
        score += earned
        if passed:
            reasons.append(reason)
        breakdown.append({
            "label": label,
            "earned": earned,
            "max": points,
            "state": state or ("충족" if passed else "미충족"),
        })

    add_check(
        "KOSPI 50일선", bool(kospi.get("sma50") and kospi["current"] > kospi["sma50"]),
        20, "KOSPI 50일선 위",
    )
    add_check(
        "KOSPI 20일선", bool(kospi.get("sma20") and kospi["current"] > kospi["sma20"]),
        10, "KOSPI 단기추세 양호",
    )
    add_check(
        "KOSDAQ 50일선", bool(kosdaq.get("ok") and kosdaq.get("sma50") and kosdaq["current"] > kosdaq["sma50"]),
        15, "KOSDAQ 50일선 위",
    )
    add_check(
        "KOSDAQ 20일선", bool(kosdaq.get("ok") and kosdaq.get("sma20") and kosdaq["current"] > kosdaq["sma20"]),
        10, "KOSDAQ 단기추세 양호",
    )

    # 미국 전일 — 한국장 갭 상관이 높아 15점.
    if us_prev.get("ok"):
        us_ok = (us_prev.get("spy_change") or 0) >= 0 and (us_prev.get("qqq_change") or 0) >= 0
        add_check("미국 전일", us_ok, 15, "미국 전일 상승 마감")
    else:
        breakdown.append({"label": "미국 전일", "earned": 0, "max": 15, "state": "자료부족"})

    # 외국인·기관 수급 (대표종목 근사) 15점.
    if foreign.get("ok"):
        add_check("외국인·기관 5일 수급", foreign["net5_amount"] > 0, 15, "대표종목 5일 순매수")
    else:
        breakdown.append({"label": "외국인·기관 5일 수급", "earned": 0, "max": 15, "state": "자료부족"})

    # 원/달러 — 하락(원화 강세)이면 외국인 자금에 우호적.
    if usdkrw.get("ok"):
        stable = bool(usdkrw.get("sma20") and usdkrw["current"] <= usdkrw["sma20"])
        add_check("원/달러 안정", stable, 15, "원/달러 20일선 아래(원화 강세)")
    else:
        breakdown.append({"label": "원/달러 안정", "earned": 0, "max": 15, "state": "자료부족"})

    if score >= 75:
        regime, posture = "상승 우위", "조건 충족 종목만 매수 심사"
    elif score >= 50:
        regime, posture = "중립·선별", "비중 축소·확인 후 진입"
    else:
        regime, posture = "방어 우선", "신규 매수 보류"

    return {
        "ok": True,
        "score": score,
        "regime": regime,
        "posture": posture,
        "reasons": reasons,
        "score_breakdown": breakdown,
        "rows": {"KOSPI": kospi, "KOSDAQ": kosdaq, "USDKRW": usdkrw},
        "us_prev": us_prev,
        "foreign": foreign,
        "phase": market_phase(),
        "checked_at": datetime.now(_SEOUL).isoformat(timespec="seconds"),
    }


# ---------------------------------------------------------------------------
# 테마 순위 — 매일 동적 선정, 약한 테마는 자동 탈락
# ---------------------------------------------------------------------------
def _scale(value: float | None, low: float, high: float, points: float) -> float:
    if value is None or high <= low:
        return 0.0
    return max(0.0, min(points, (value - low) / (high - low) * points))


def _theme_score(detail_stocks: list[dict], theme_change: float, kospi_change: float) -> dict:
    """테마 조건점수 100점.

    당일 등락률만 쓰지 않는다 — 구성종목 확산도와 거래대금 집중도를 함께 본다.
    20일 상대강도는 선택된 테마에서만 계산한다(전체 테마에 다 계산하면 너무 느리다).
    """
    stocks = [s for s in detail_stocks if s.get("change_pct") is not None]
    if not stocks:
        return {"ok": False}

    up_ratio = sum(1 for s in stocks if s["change_pct"] > 0) / len(stocks) * 100
    strong_ratio = sum(1 for s in stocks if s["change_pct"] >= 3.0) / len(stocks) * 100
    relative = theme_change - kospi_change
    values = [s["trading_value"] for s in stocks if s.get("trading_value")]
    total_value = sum(values) if values else None

    # 스케일 상단은 실측(2026-07-22 강세장)에서 만점이 여러 개 나와 변별이 안 되던 것을
    # 보고 넓혔다. 상위권끼리도 순위가 갈리게 한다.
    score = round(
        _scale(relative, -2.0, 9.0, 35)          # KOSPI 대비 당일 상대강도
        + _scale(up_ratio, 30, 98, 25)           # 구성종목 확산
        + _scale(strong_ratio, 0, 65, 20)        # 3%↑ 종목 비중
        + _scale(math.log10(total_value / 1e8) if total_value else None, 1.0, 4.2, 20),
        1,
    )
    status = "주도" if score >= 70 else "관찰" if score >= 50 else "약함"
    return {
        "ok": True,
        "score": score,
        "status": status,
        "up_ratio": up_ratio,
        "strong_ratio": strong_ratio,
        "relative": relative,
        "total_trading_value": total_value,
        "stock_count": len(stocks),
    }


def get_theme_rankings(force_names: tuple[str, ...] | list[str] = ()) -> dict:
    """네이버 전체 테마에서 오늘 강한 테마 20개를 자동 선정한다.

    force_names에 이름을 주면 그 테마는 점수·순위와 무관하게 반드시 심사해서 목록에
    넣는다(사용자가 직접 찾아본 테마용, 2026-07-22 추가).
    """
    listing = get_all_themes()
    if not listing.get("ok"):
        return {"ok": False, "error": listing.get("error"), "rows": []}

    themes = listing["themes"]
    kospi = _index_metrics("KS11", _live_index("^KS11"))
    kospi_change = kospi.get("change_pct") or 0.0

    # 1차: 네이버가 주는 당일 평균 등락률로 후보를 좁힌다(무료·빠름).
    ordered = sorted(themes.values(), key=lambda t: t["change_pct"], reverse=True)
    candidates = ordered[:CANDIDATE_THEME_COUNT]

    # 당일 등락률만으로 자르면 '꾸준히 강했는데 오늘 하루 쉰' 테마가 통째로 사라진다
    # (2026-07-22 사용자 지적: 금융주가 얼마 전까지 좋았는데 목록에서 빠졌다 —
    # 실측 결과 금융 최고 테마가 당일 49위라 후보 30에 못 들었다).
    # 그래서 직전 조회에서 상위권이었던 테마는 오늘 등락률이 낮아도 계속 심사한다.
    # 계속 약하면 점수가 낮아 자연히 20위 밖으로 밀려나므로 '자동 탈락' 원칙은 유지된다.
    previous_entry = _CACHE.get("previous_theme_names")
    previous_names = set(previous_entry["value"]) if previous_entry else set()
    forced = {str(name) for name in (force_names or ())}
    keep_names = previous_names | forced
    if keep_names:
        picked = {theme["name"] for theme in candidates}
        for theme in ordered:
            if theme["name"] in keep_names and theme["name"] not in picked:
                candidates.append(theme)
                picked.add(theme["name"])

    rows = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(get_theme_stocks, theme["no"]): theme for theme in candidates
        }
        for future in as_completed(futures):
            theme = futures[future]
            try:
                detail = future.result()
            except Exception:
                continue
            if not detail.get("ok"):
                continue
            stocks = detail["stocks"]
            scored = _theme_score(stocks, theme["change_pct"], kospi_change)
            if not scored.get("ok"):
                continue
            rows.append({
                "no": theme["no"],
                "name": theme["name"],
                "ok": True,
                "change_pct": theme["change_pct"],
                "stocks": stocks,
                **scored,
                "basis": (
                    f"KOSPI 대비 {scored['relative']:+.2f}%p · 구성종목 상승 {scored['up_ratio']:.0f}% · "
                    f"3%↑ 종목 {scored['strong_ratio']:.0f}%"
                ),
            })

    rows.sort(key=lambda row: row["score"], reverse=True)
    # 표에는 20개만 보이지만, 눌림목·통과 종목 심사가 쓸 수 있도록 전체 심사 결과를 남긴다.
    all_scored = list(rows)
    # 21위 밖으로 밀린 테마도 이름·점수만 남겨 둔다 — "왜 그 테마가 빠졌나"를
    # 화면에서 확인할 수 있어야 한다(2026-07-22 사용자 지적).
    next_rows = [
        {"name": row["name"], "score": row["score"], "change_pct": row["change_pct"],
         "status": row["status"]}
        for row in rows[DISPLAY_THEME_COUNT:DISPLAY_THEME_COUNT + 10]
    ]
    # 사용자가 직접 찾아본 테마는 점수가 낮아도 목록에 남긴다(순위는 실제 점수 순).
    forced_rows = [row for row in rows[DISPLAY_THEME_COUNT:] if row["name"] in forced]
    rows = rows[:DISPLAY_THEME_COUNT] + forced_rows
    rows.sort(key=lambda row: row["score"], reverse=True)
    for index, row in enumerate(rows, 1):
        row["rank"] = index
        row["is_forced"] = row["name"] in forced

    # 어제 대비 신규 진입·탈락 표시 (세션이 아니라 모듈 캐시에 보관).
    previous = _CACHE.get("previous_theme_names", {}).get("value") if _CACHE.get("previous_theme_names") else None
    current_names = [row["name"] for row in rows]
    entered = [name for name in current_names if previous and name not in previous]
    dropped = [name for name in (previous or []) if name not in current_names]
    with _CACHE_LOCK:
        _CACHE["previous_theme_names"] = {"at": time.time(), "value": current_names}
    for row in rows:
        row["is_new"] = row["name"] in entered

    return {
        "ok": bool(rows),
        "rows": rows,
        "all_scored": all_scored,
        "next_rows": next_rows,
        "entered": entered,
        "dropped": dropped,
        "total_scanned": len(themes),
        "kospi_change": kospi_change,
        "checked_at": datetime.now(_SEOUL).isoformat(timespec="seconds"),
        "stale": listing.get("stale", False),
        "error": None if rows else "테마 점수를 계산하지 못했습니다",
    }


# ---------------------------------------------------------------------------
# 종목 심사 — 수급 20점을 포함한 한국형 6개 항목
# ---------------------------------------------------------------------------
# 제외 대상: 관리종목·투자경고 등은 종목명에 표기되거나 우선주·스팩인 경우를 거른다.
_EXCLUDE_PATTERNS = ("스팩", "SPAC", "리츠")


def _is_excluded(name: str, code: str) -> bool:
    if any(token in name for token in _EXCLUDE_PATTERNS):
        return True
    # 우선주는 종목코드가 0/5/7 등으로 끝나는 경우가 많아 이름 기준으로만 거른다.
    return name.endswith("우") or name.endswith("우B") or name.endswith("3우B")


def _stock_score(metrics: dict, flow: dict, theme_ret20: float | None) -> tuple[float, list[float]]:
    """종목 조건점수 100점 = 상대강도20 + 신고가15 + 추세20 + 유동성15 + 변동성10 + 수급20.

    미국판 배점을 그대로 쓰면 안 된다(2026-07-22 실측): 국내 대형주 상당수가 52주 고가
    대비 -30~-45% 구간이라 미국 기준(-25%~0)에서는 전 종목이 0점이 돼 변별력이 없다.
    신고가 항목은 범위를 -45~0으로 넓히고 배점을 15로 줄이는 대신, 국내에서 더 잘 듣는
    추세(이동평균선) 배점을 20으로 올렸다.
    """
    relative = None
    if metrics.get("ret20") is not None and theme_ret20 is not None:
        relative = metrics["ret20"] - theme_ret20
    rs_points = _scale(relative, -8, 8, 20)

    high_points = _scale(metrics.get("from_high_pct"), -45, 0, 15)

    trend_points = 0.0
    for average_key, points in (("sma20", 8), ("sma50", 7), ("sma200", 5)):
        value = metrics.get(average_key)
        if value and metrics.get("current") and metrics["current"] > value:
            trend_points += points

    trading_value = metrics.get("avg_trading_value")
    if trading_value is None:
        liquidity_points = 0.0
    elif trading_value >= 5e10:      # 500억 이상
        liquidity_points = 15.0
    elif trading_value >= 2e10:      # 200억
        liquidity_points = 13.0
    elif trading_value >= 1e10:      # 100억
        liquidity_points = 10.0
    elif trading_value >= 3e9:       # 30억
        liquidity_points = 6.0
    else:
        liquidity_points = 2.0

    atr_pct = metrics.get("atr_pct")
    if atr_pct is None:
        risk_points = 0.0
    elif atr_pct <= 4:
        risk_points = 10.0
    elif atr_pct <= 6:
        risk_points = 8.0
    elif atr_pct <= 9:
        risk_points = 5.0
    elif atr_pct <= 13:
        risk_points = 2.0
    else:
        risk_points = 0.0

    # 수급 20점 — 자비스3에 없던 한국판 핵심 항목.
    # 순매수 '금액'을 그대로 쓰면 대형주가 항상 만점이 된다(삼성전자·하이닉스 실측).
    # 그래서 그 종목의 5일 거래대금 대비 몇 %를 순매수했는지로 정규화한다 —
    # 종목 규모와 무관하게 "얼마나 강하게 담았나"를 본다.
    if not flow.get("ok"):
        flow_points = 0.0
        flow_ratio = None
    else:
        net5 = flow.get("net5_amount") or 0
        base = (trading_value or 0) * 5
        flow_ratio = (net5 / base) if base > 0 else None
        amount_points = _scale(flow_ratio, 0.0, 0.12, 14)  # 5일 거래대금의 12%면 만점
        # 2026-07-25: '연속'(외국인+기관을 합쳐서 센 연속일)에서 '동반'(둘 다 순매수한
        # 날 수)으로 바꿨다. 합산은 외국인 +500억·기관 −480억을 순매수로 둔갑시켜
        # 화면에서 이미 버린 기준이라, 점수도 같은 자를 쓰게 맞췄다(사용자 지시).
        # 5일 중 3일이면 만점 6점. 동반이 더 엄격해 점수는 전보다 낮게 나온다.
        partner_points = min(6.0, (flow.get("both_buy_days5") or 0) * 2.0)
        flow_points = amount_points + partner_points
    flow["net5_ratio"] = flow_ratio if flow.get("ok") else None

    score = rs_points + high_points + trend_points + liquidity_points + risk_points + flow_points
    # 국내형 추격 금지 감점 (상한가 30% 제도 반영).
    if metrics.get("ret5") is not None and metrics["ret5"] >= 25:
        score -= 12
    if metrics.get("change_pct") is not None and metrics["change_pct"] >= 20:
        score -= 12
    return round(max(0.0, min(100.0, score)), 1), [
        round(rs_points, 1), round(high_points, 1), round(trend_points, 1),
        round(liquidity_points, 1), round(risk_points, 1), round(flow_points, 1),
    ]


def tick_size(price: float) -> int:
    """KRX 호가단위(2023년 개편 기준)."""
    if price < 2_000:
        return 1
    if price < 5_000:
        return 5
    if price < 20_000:
        return 10
    if price < 50_000:
        return 50
    if price < 200_000:
        return 100
    if price < 500_000:
        return 500
    return 1_000


def round_to_tick(price: float | None) -> float | None:
    """실제 주문 가능한 가격으로 반올림한다."""
    if not price or price <= 0:
        return None
    unit = tick_size(price)
    return float(round(price / unit) * unit)


def _entry_plan(metrics: dict, score: float, market_score: float, theme_score: float) -> dict:
    """매수 심사 — 돌파 확인 / 눌림목 대기 / 추격 금지. 가격은 호가단위로 반올림한다."""
    current = metrics.get("current")
    if not current:
        return {"state": "자료 부족", "recommendation": "추천 불가"}

    atr = metrics.get("atr")
    sma20 = metrics.get("sma20")
    from_high = metrics.get("from_high_pct")
    ret5 = metrics.get("ret5")
    change_pct = metrics.get("change_pct")
    atr_pct = metrics.get("atr_pct")

    chase_block = (
        (ret5 is not None and ret5 >= 25)
        or (change_pct is not None and change_pct >= 20)
        or (atr_pct is not None and atr_pct >= 15)
    )

    # 눌림목 조건도 국내 현실에 맞춘다(2026-07-22): 미국판의 '50일선 위' 단독 조건은
    # 고점 대비 크게 눌린 국내 종목을 전부 제외시켜 후보가 하나도 남지 않았다.
    # 단기 추세(20일선)가 살아 있으면서 중기 회복 신호(50일선 위 또는 20일 수익률 양수)가
    # 있는 경우까지 눌림목으로 본다.
    sma50 = metrics.get("sma50")
    above_sma20 = bool(sma20 and current >= sma20 * 0.98)
    mid_term_ok = bool((sma50 and current > sma50) or (metrics.get("ret20") or 0) > 0)

    if chase_block:
        state = "추격 금지"
        trigger = zone_high = invalidation = target = None
    elif from_high is not None and from_high >= -3.0 and (metrics.get("volume_ratio") or 0) >= 1.3:
        state = "돌파 확인"
        trigger = current * 1.003
        invalidation = current - max((atr or current * 0.04) * 2, current * 0.04)
        zone_high = trigger * 1.01
        target = trigger + 2 * (trigger - invalidation)
    elif above_sma20 and mid_term_ok and abs(current / sma20 - 1) <= 0.07:
        state = "눌림목 대기"
        trigger = max(current, sma20 * 1.005)
        invalidation = current - max((atr or current * 0.04) * 2, current * 0.04)
        zone_high = trigger * 1.01
        target = trigger + 2 * (trigger - invalidation)
    elif score >= 65:
        state = "관찰"
        trigger = zone_high = invalidation = target = None
    else:
        state = "제외"
        trigger = zone_high = invalidation = target = None

    # 테마 게이트는 종목 점수로 면제될 수 있다(2026-07-22 사용자 지적으로 수정).
    # 미국판은 테마=ETF라 테마가 약하면 구성종목도 대체로 약했지만, 국내 네이버 테마는
    # 성격이 섞여 있어 테마 평균이 종목 품질을 대표하지 못한다 — 실측: '은행' 테마는
    # 22.1점(약함)인데 하나금융지주는 95.0점이었다. 압도적으로 강한 종목을 테마 평균
    # 때문에 버리지 않는다.
    theme_ok = theme_score >= 60 or score >= STRONG_STOCK_OVERRIDE
    gates_ok = market_score >= 50 and theme_ok and score >= 70
    if gates_ok and state in {"돌파 확인", "눌림목 대기"}:
        recommendation = "조건부 후보"
    elif state in {"추격 금지", "제외"}:
        recommendation = "추천 제외"
    else:
        recommendation = "관찰"

    if market_score < 50:
        buy_reason = "시장 국면이 방어 우선이라 신규 매수를 보류합니다."
    elif not theme_ok:
        buy_reason = (
            f"테마 강도가 기준 미달입니다(종목 점수가 {STRONG_STOCK_OVERRIDE:.0f}점을 넘으면 "
            "테마와 무관하게 후보로 봅니다)."
        )
    elif score < 70:
        buy_reason = "종목 조건점수가 기준 미달입니다."
    elif state == "돌파 확인":
        buy_reason = "52주 신고가 부근에서 거래량이 증가해 종가 돌파 확인 후 진입합니다."
    elif state == "눌림목 대기":
        buy_reason = "상승 추세 안의 20일선 눌림으로 기준가 회복 후에만 진입합니다."
    elif state == "추격 금지":
        buy_reason = "단기 급등·상한가 인접 또는 고변동으로 추격 매수를 금지합니다."
    else:
        buy_reason = "가격 셋업이 완성되지 않아 관찰합니다."

    return {
        "state": state,
        "recommendation": recommendation,
        "trigger": round_to_tick(trigger),
        "zone_high": round_to_tick(zone_high),
        "invalidation": round_to_tick(invalidation),
        "target": round_to_tick(target),
        "buy_reason": buy_reason,
    }


def _analyze_stock(stock: dict, theme_ret20: float | None) -> dict | None:
    code, name = stock["code"], stock["name"]
    if _is_excluded(name, code):
        return None
    daily = get_daily_frame(code)
    metrics = _series_metrics(daily, stock.get("price"))
    if not metrics.get("ok"):
        return None
    flow = get_stock_flow(code)
    score, parts = _stock_score(metrics, flow, theme_ret20)
    return {
        "code": code,
        "name": name,
        "metrics": metrics,
        "flow": flow,
        "score": score,
        "score_parts": parts,
        "daily": daily,
    }


def get_theme_leaders(theme_row: dict, market_score: float = 0, theme_score: float = 0) -> dict:
    """선택한 테마의 대장주 순위. 거래대금 상위 종목만 심사한다."""
    stocks = theme_row.get("stocks") or []
    if not stocks:
        detail = get_theme_stocks(theme_row.get("no"))
        if not detail.get("ok"):
            return {"ok": False, "error": detail.get("error"), "rows": []}
        stocks = detail["stocks"]

    ranked_by_value = sorted(
        [s for s in stocks if s.get("trading_value")],
        key=lambda s: s["trading_value"],
        reverse=True,
    )[:THEME_STOCK_LIMIT]
    if not ranked_by_value:
        ranked_by_value = stocks[:THEME_STOCK_LIMIT]

    # 테마 20일 수익률 = 구성종목 20일 수익률의 중앙값(테마 ETF가 없는 국내 사정).
    theme_ret20 = None
    rows = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(_analyze_stock, stock, None) for stock in ranked_by_value]
        for future in as_completed(futures):
            try:
                result = future.result()
            except Exception:
                continue
            if result:
                rows.append(result)

    if not rows:
        return {"ok": False, "error": "구성종목 시세를 가져오지 못했습니다", "rows": []}

    ret20_values = [r["metrics"]["ret20"] for r in rows if r["metrics"].get("ret20") is not None]
    if ret20_values:
        theme_ret20 = float(pd.Series(ret20_values).median())

    # 테마 상대강도가 정해졌으니 점수를 다시 매긴다.
    for row in rows:
        row["score"], row["score_parts"] = _stock_score(row["metrics"], row["flow"], theme_ret20)
        row["plan"] = _entry_plan(row["metrics"], row["score"], market_score, theme_score)

    rows.sort(key=lambda row: row["score"], reverse=True)
    for index, row in enumerate(rows, 1):
        row["rank"] = index
        from_high = row["metrics"].get("from_high_pct")
        flow = row["flow"]
        flow_text = (
            f" · 외국인+기관 5일 {flow['net5_amount'] / 1e8:+,.0f}억"
            if flow.get("ok") else " · 수급 확인 필요"
        )
        row["stock_reason"] = (
            f"테마 내 종합 {index}위 · 52주 고가 대비 {from_high:.1f}%{flow_text}"
            if from_high is not None else f"테마 내 종합 {index}위{flow_text}"
        )

    return {
        "ok": True,
        "rows": rows,
        "theme_ret20": theme_ret20,
        "checked_at": datetime.now(_SEOUL).isoformat(timespec="seconds"),
    }


_MINUTE_URL = (
    "https://api.finance.naver.com/siseJson.naver"
    "?symbol={code}&requestType=1&startTime={day}&endTime={day}&timeframe=minute"
)
_MINUTE_ROW_PATTERN = re.compile(r'\["(\d{12})",[^,]*,[^,]*,[^,]*,\s*([\d.]+)')


def get_last_session_intraday(code: str, back_days: int = 5) -> dict | None:
    """마지막으로 열린 장의 분봉. 주말·휴장이면 하루씩 거슬러 올라가며 찾는다.

    2026-07-25: 주말에 분봉이 없다고 30일 일봉으로 대신 그렸더니 '코스피가 기준가
    위로 간 적이 없는데 빨간 구간이 있다'는 지적을 받았다. 그림은 언제나 '하루치
    분봉 + 그 전날 종가'여야 한다. 자료가 없으면 그리지 않는다(틀린 그림보다 낫다).
    """
    for back in range(back_days + 1):
        day = (datetime.now(_SEOUL) - timedelta(days=back)).strftime("%Y%m%d")
        payload = get_intraday_chart(code, day=day)
        if isinstance(payload, dict) and payload.get("ok"):
            return payload
    return None


def get_intraday_chart(code: str, *, ttl_seconds: float = 60, day: str | None = None) -> dict | None:
    """당일 분봉 흐름(네이버 siseJson). 자비스3의 당일 차트와 같은 역할이다.

    FinanceDataReader는 분봉을 주지 않아서 네이버 차트 API를 쓴다. 응답은 JSON이 아니라
    파이썬 리터럴 형식이고 시가·고가·저가는 null이라 종가만 뽑아 쓴다.
    """
    code = str(code).strip()
    day = day or datetime.now(_SEOUL).strftime("%Y%m%d")

    def _produce():
        text = _get_text(_MINUTE_URL.format(code=code, day=day), timeout=8)
        pairs = _MINUTE_ROW_PATTERN.findall(text)
        if len(pairs) < 5:
            raise RuntimeError("분봉 데이터가 부족합니다")
        rows = []
        for stamp, close in pairs:
            value = _finite(close)
            if value is None:
                continue
            rows.append((datetime.strptime(stamp, "%Y%m%d%H%M"), value))
        if len(rows) < 5:
            raise RuntimeError("분봉 데이터가 부족합니다")
        rows.sort(key=lambda item: item[0])
        return rows

    try:
        rows, _stale = _cached(("minute", code, day), ttl_seconds, _produce)
    except Exception:
        return None

    frame = pd.DataFrame({"Close": [value for _stamp, value in rows]},
                         index=[stamp for stamp, _value in rows])
    daily = get_daily_frame(code)
    prev_close = None
    if daily is not None and len(daily) >= 2:
        last_date = pd.Timestamp(daily.index[-1]).date()
        today = datetime.now(_SEOUL).date()
        prev_close = _finite(daily["Close"].iloc[-2] if last_date == today else daily["Close"].iloc[-1])
    return {
        "ok": True,
        "price": frame,
        "prev_close": prev_close,
        "source_time": rows[-1][0].strftime("%Y-%m-%d %H:%M"),
    }


def _pullback_quality(metrics: dict, flow: dict) -> dict | None:
    """눌림목 품질 100점 — '올라가던 종목이 얼마나 좋은 자리까지 눌렸나'를 잰다.

    매수 심사 통과 여부(게이트)와는 다른 관점이다. 지금 시장이 나빠 못 사더라도,
    시장이 돌아섰을 때 먼저 볼 관찰 목록을 만드는 것이 목적이다(2026-07-22 사용자 제안).

    보는 것 다섯 가지:
    - 신고가 시점 : 52주 신고가를 최근에 찍었을수록 좋다. '올라가던 종목'인지 가리는
                    가장 단순하고 확실한 기준이다(2026-07-22 사용자 제안).
    - 20일선 이격 : 20일선에 붙어 있을수록 좋은 자리(멀면 아직 안 눌렸거나 이미 이탈)
    - 장기 추세   : 200·50일선 위면 상승 추세가 살아 있다는 뜻
    - 눌림 깊이   : 고점 대비 -5~-20%가 건강한 조정. 너무 얕으면 조정 전, 깊으면 추세 훼손
    - 수급        : 눌리는 동안 외국인·기관이 담고 있으면 반등 확률이 높다
    """
    current, sma20 = metrics.get("current"), metrics.get("sma20")
    if not current or not sma20:
        return None

    gap_pct = (current / sma20 - 1) * 100          # 20일선 이격도
    from_high = metrics.get("from_high_pct")

    # 신고가를 며칠 전에 찍었나 — 20거래일(약 한 달) 이내면 만점, 120일 넘으면 0점.
    days_ago = metrics.get("high52_days_ago")
    if days_ago is None:
        recency = 0.0
    elif days_ago <= 20:
        recency = 25.0
    elif days_ago >= 120:
        recency = 0.0
    else:
        recency = 25.0 * (1 - (days_ago - 20) / 100.0)

    # 20일선에 붙을수록 만점(±2% 이내 25점 → ±8% 0점)
    proximity = max(0.0, 25.0 * (1 - max(0.0, abs(gap_pct) - 2.0) / 6.0))

    trend = 0.0
    if metrics.get("sma50") and current > metrics["sma50"]:
        trend += 10.0
    if metrics.get("sma200") and current > metrics["sma200"]:
        trend += 10.0

    # 고점 대비 -5~-20%를 건강한 눌림으로 본다.
    if from_high is None:
        depth = 0.0
    elif -20.0 <= from_high <= -5.0:
        depth = 25.0
    elif -30.0 <= from_high < -20.0 or -5.0 < from_high <= -2.0:
        depth = 15.0
    elif from_high < -30.0:
        depth = 5.0
    else:
        depth = 10.0

    if flow.get("ok"):
        net5 = flow.get("net5_amount") or 0
        # 위 조건점수와 같은 이유로 '연속' 대신 '동반'을 쓴다(2026-07-25).
        partner = flow.get("both_buy_days5") or 0
        supply = min(15.0, (8.0 if net5 > 0 else 0.0) + min(7.0, partner * 2.0))
    else:
        supply = 0.0

    score = round(recency + proximity + trend + depth + supply, 1)
    return {
        "score": score,
        "gap_pct": gap_pct,
        "from_high_pct": from_high,
        "high52_days_ago": days_ago,
        "above_sma200": bool(metrics.get("sma200") and current > metrics["sma200"]),
        "parts": [round(recency, 1), round(proximity, 1), round(trend, 1),
                  round(depth, 1), round(supply, 1)],
    }


def get_theme_universe(*, ttl_seconds: float = 90) -> dict:
    """전체 테마의 구성종목을 한 번 모아 '종목별 소속 테마 목록'을 만든다.

    구성관계는 천천히 변하지만 거래대금은 장중 계속 변한다. 예전 30분 캐시는 장전
    0원 스냅샷을 오전 내내 재사용할 수 있어 90초로 줄인다. 화면은 수동 실행이므로
    사용자가 조회하지 않는 동안에는 네이버 요청이 발생하지 않는다.
    """

    def _produce():
        listing = get_all_themes()
        if not listing.get("ok"):
            raise RuntimeError(listing.get("error") or "테마 목록 조회 실패")
        seen: dict[str, dict] = {}
        themes = list(listing["themes"].values())
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(
                    get_theme_stocks, theme["no"], ttl_seconds=ttl_seconds
                ): theme for theme in themes
            }
            for future in as_completed(futures):
                theme = futures[future]
                try:
                    detail = future.result()
                except Exception:
                    continue
                if not detail.get("ok"):
                    continue
                for stock in detail["stocks"]:
                    if _is_excluded(stock["name"], stock["code"]):
                        continue
                    entry = seen.get(stock["code"])
                    if entry is None:
                        seen[stock["code"]] = {
                            **stock, "themes": [theme["name"]], "theme_name": theme["name"]
                        }
                    elif theme["name"] not in entry["themes"]:
                        entry["themes"].append(theme["name"])
        if not seen:
            raise RuntimeError("구성종목을 모으지 못했습니다")
        return {"stocks": seen, "theme_count": len(themes)}

    try:
        value, stale = _cached("theme_universe", ttl_seconds, _produce)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "stocks": {}}
    return {"ok": True, "stale": stale, **value}


def clear_pullback_cache() -> None:
    """눌림목 재검색 때 결과와 장중 테마 상세를 함께 갱신한다."""
    with _CACHE_LOCK:
        for key in list(_CACHE):
            if key == "theme_universe" or key == "theme_list":
                _CACHE.pop(key, None)
            elif isinstance(key, tuple) and key and key[0] in {"pullback_stocks", "theme_detail"}:
                _CACHE.pop(key, None)


def score_at_past(
    daily: pd.DataFrame | None,
    flow: dict,
    market_ret20,
    days_ago: int,
    *,
    market_daily: pd.DataFrame | None = None,
):
    """며칠 전 시점의 가격·기술 조건점수를 100점으로 환산한다.

    눌림목은 '그때 좋았던 종목이 지금 눌린 것'이다. 지금 점수로 자르면 눌렸다는
    이유로 탈락한다 — 신고가를 찍던 날은 신고가 위치가 만점이었을 테니 그때 점수를
    봐야 한다(2026-07-22 사용자 지적).

    일봉을 그 시점까지 자르고, KOSPI도 같은 날짜까지 잘라 당시 20일 상대강도를
    복원한다. 과거 외국인·기관 수급은 현재 데이터로 복원할 수 없으므로 절대 섞지
    않는다. 종목점수의 가격·기술 80점을 100점으로 환산해 서로 비교한다.

    ``flow`` 인자는 기존 호출 호환을 위해 남기되 과거점수에는 사용하지 않는다.
    ``market_daily``가 없을 때만 전달받은 market_ret20을 대체 기준으로 쓴다.
    """
    # 역산이 실패해도 종목이 통째로 빠지면 안 된다 — None을 돌려주면 호출부가
    # 현재 점수로 대신 판단한다.
    try:
        if daily is None or days_ago is None or days_ago <= 0:
            return None
        if len(daily) <= days_ago + 25:
            return None
        past = daily.iloc[: len(daily) - days_ago]
        metrics = _series_metrics(past)
        if not metrics.get("ok"):
            return None
        past_market_ret20 = market_ret20
        market_basis = "현재 KOSPI 대체"
        if isinstance(market_daily, pd.DataFrame) and not market_daily.empty:
            cutoff = pd.Timestamp(past.index[-1])
            aligned_market = market_daily.loc[:cutoff]
            market_metrics = _series_metrics(aligned_market)
            if market_metrics.get("ok") and market_metrics.get("ret20") is not None:
                past_market_ret20 = market_metrics["ret20"]
                market_basis = "신고가 당시 KOSPI"

        # 과거 수급을 현재 수급으로 위장하지 않는다. 가격·기술 80점만 계산한 뒤
        # 100점으로 환산한다. 추격 감점은 _stock_score 안에서 그대로 반영된다.
        raw_score, parts = _stock_score(metrics, {"ok": False}, past_market_ret20)
        technical_score = round(min(100.0, max(0.0, raw_score / 80.0 * 100.0)), 1)
        return {
            "score": technical_score,
            "raw_score": raw_score,
            "parts": parts[:5],
            "metrics": metrics,
            "as_of": pd.Timestamp(past.index[-1]).date().isoformat(),
            "basis": f"과거 가격·기술(수급 제외) · {market_basis}",
        }
    except Exception:
        return None


def find_pullback_stocks(
    *,
    min_theme_count: int = 2,
    high_days_min: int = 1,
    # 20일이면 삼성전자(신고가 24일 전)처럼 조금 늦게 눌린 대형주가 통째로 빠진다.
    # 2026-07-24 사용자 지시로 30일까지 넓혔다.
    high_days_max: int = 30,
    min_stock_score: float = 75.0,
    min_trading_value: float = 2e10,
    theme_scan_limit: int = 300,
    scan_limit: int = 50,
    result_limit: int = 15,
    ttl_seconds: float = 600,
) -> dict:
    """상승추세 중 조정받은 눌림목 종목을 찾는다 (2026-07-22 사용자 스펙).

    조건 세 가지 — 사용자가 정한 것만 쓴다:
    1. **52주 최고가를 찍고 1~20일 지난 종목** — 방금 고점을 찍고 내려오는 중인 것.
    2. **2개 이상 테마에 속한 종목**
    3. **신고가 시점 종목 조건점수 75점 이상** — 나머지 품질은 이 점수 하나로 거른다.

    하락장 판단은 이 함수가 하지 않는다 — 시장 국면은 상단 '한국 전체시장 판단'에서
    사용자가 보고 정한다.
    """

    def _produce():
        universe = get_theme_universe()
        if not universe.get("ok"):
            raise RuntimeError(universe.get("error") or "테마 구성종목 조회 실패")
        seen = universe["stocks"]

        multi_theme = [
            item for item in seen.values() if len(item["themes"]) >= min_theme_count
        ]
        # 장전·장초반에는 오늘 누적 거래대금이 0에 가깝다. HTML에 이미 있는
        # 전일거래량×현재가를 유동성 대체값으로 함께 쓰되, 오늘 값과 둘 중 큰 값을
        # 선택해 시간대에 따라 후보 수가 수십 배 흔들리는 문제를 줄인다.
        for item in multi_theme:
            current_value = float(item.get("trading_value") or 0)
            previous_proxy = float(item.get("price") or 0) * float(item.get("previous_volume") or 0)
            item["liquidity_value"] = max(current_value, previous_proxy)
        candidates = [
            item for item in multi_theme
            if item["liquidity_value"] >= min_trading_value
        ]
        if not candidates:
            return {
                "rows": [],
                "universe_count": len(seen),
                "multi_theme_count": len(multi_theme),
                "liquid_count": 0,
                "scanned_count": 0,
                "screened_count": 0,
                "flow_checked_count": 0,
                "window": (high_days_min, high_days_max),
                "message": "유동성 기준을 통과한 종목이 없습니다.",
                "checked_at": datetime.now(_SEOUL).isoformat(timespec="seconds"),
            }
        # 조회 시간이 후보 수에 비례하므로 거래대금 상위부터 상한을 둔다 —
        # 눌림목을 노릴 만한 종목은 거래대금이 받쳐주는 쪽이다.
        multi_theme_total = len(multi_theme)
        liquid_total = len(candidates)
        candidates.sort(key=lambda item: item.get("liquidity_value") or 0, reverse=True)
        candidates = candidates[:scan_limit]

        # 2) 일봉으로 '52주 최고가 찍고 1~15일 지난 종목'만 거른다.
        low, high = high_days_min, high_days_max

        def _screen(stock):
            daily = get_daily_frame(stock["code"])
            metrics = _series_metrics(daily, stock.get("price"))
            if not metrics.get("ok"):
                return None
            days_ago = metrics.get("high52_days_ago")
            if days_ago is None or not (low <= days_ago <= high):
                return None
            # 고점을 찍고 '내려가는' 종목이어야 한다(고점 그대로면 눌림이 아니다).
            if (metrics.get("from_high_pct") or 0) >= 0:
                return None
            return {**stock, "metrics": metrics, "daily": daily}

        screened = []
        with ThreadPoolExecutor(max_workers=16) as executor:
            for future in as_completed([executor.submit(_screen, s) for s in candidates]):
                try:
                    item = future.result()
                except Exception:
                    continue
                if item:
                    screened.append(item)

        # 3) 살아남은 종목만 수급을 조회해 최종 점수를 매긴다.
        # 상대강도 기준은 KOSPI 20일 수익률을 쓴다 — 테마를 가로지르는 검색이라
        # 테마 상대강도를 못 쓰는데, None으로 넘기면 20점이 통째로 0점이 돼
        # 하나금융지주가 95점에서 75.5점으로 떨어졌다(2026-07-22 실측 수정).
        kospi = _index_metrics("KS11")
        market_ret20 = kospi.get("ret20") if kospi.get("ok") else None
        try:
            kospi_daily, _kospi_stale = _cached(
                ("index", "KS11"), 300, lambda: _index_frame("KS11")
            )
        except Exception:
            kospi_daily = None

        def _finalize(item):
            flow = get_stock_flow(item["code"])
            quality = _pullback_quality(item["metrics"], flow)
            score, parts = _stock_score(item["metrics"], flow, market_ret20)
            # 신고가를 찍던 시점의 점수를 역산한다 — 눌림목은 '그때 좋았던 종목'이므로
            # 이 점수로 걸러야 한다(지금 점수는 눌린 만큼 낮게 나온다).
            past = score_at_past(
                item.get("daily"), flow, market_ret20,
                item["metrics"].get("high52_days_ago"),
                market_daily=kospi_daily,
            )
            return {**item, "flow": flow, "pullback": quality,
                    "score": score, "score_parts": parts,
                    "peak_score": past["score"] if past else None,
                    "peak_parts": past["parts"] if past else None,
                    "peak_score_date": past["as_of"] if past else None,
                    "peak_score_basis": past["basis"] if past else "현재 종합점수 대체"}

        final = []
        screened.sort(key=lambda item: item.get("liquidity_value") or 0, reverse=True)
        flow_targets = screened[:25]
        with ThreadPoolExecutor(max_workers=10) as executor:
            for future in as_completed([executor.submit(_finalize, s) for s in flow_targets]):
                try:
                    item = future.result()
                except Exception:
                    continue
                # 80점 기준은 '신고가 시점 점수'로 본다 — 지금 점수는 눌린 만큼 낮다.
                # 역산이 안 되는 종목만 현재 점수로 대신 판단한다.
                gate_score = item.get("peak_score")
                if gate_score is None:
                    gate_score = item.get("score")
                if item.get("pullback") and float(gate_score or 0) >= min_stock_score:
                    final.append(item)

        final.sort(
            key=lambda item: float(item.get("peak_score") or item.get("score") or 0),
            reverse=True,
        )
        final = final[:result_limit]
        for index, item in enumerate(final, 1):
            item["pullback_rank"] = index
            item["plan"] = _entry_plan(item["metrics"], item["score"], 100, 100)
            item.pop("daily", None)
        return {
            "rows": final,
            "universe_count": len(seen),
            "multi_theme_count": multi_theme_total,
            "liquid_count": liquid_total,
            "scanned_count": len(candidates),
            "screened_count": len(screened),
            "flow_checked_count": len(flow_targets),
            "window": (low, high),
            "checked_at": datetime.now(_SEOUL).isoformat(timespec="seconds"),
        }

    try:
        cache_key = (
            "pullback_stocks", min_theme_count, high_days_min, high_days_max,
            float(min_stock_score), float(min_trading_value), int(theme_scan_limit),
            int(scan_limit), int(result_limit),
        )
        value, stale = _cached(cache_key, ttl_seconds, _produce)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "rows": []}
    return {"ok": True, "stale": stale, **value}


def get_live_quote(code: str) -> dict:
    """선택 종목 최근가 — 장중이면 네이버 테마 상세의 현재가와 같은 값을 쓴다."""
    daily = get_daily_frame(code, ttl_seconds=60)
    metrics = _series_metrics(daily)
    if not metrics.get("ok"):
        return {"ok": False, "error": "시세 조회 실패"}
    return {"ok": True, **metrics, "code": str(code)}


def _prepare_chart_payload(frame: pd.DataFrame, resample_rule: str | None, limit: int) -> dict:
    chart = frame.copy()
    if resample_rule:
        aggregations = {"Close": "last"}
        for column, how in (("Open", "first"), ("High", "max"), ("Low", "min"), ("Volume", "sum")):
            if column in chart.columns:
                aggregations[column] = how
        chart = chart.resample(resample_rule).agg(aggregations).dropna(subset=["Close"])
    chart["MA20"] = chart["Close"].rolling(20).mean()
    chart["MA50"] = chart["Close"].rolling(50).mean()
    chart = chart.tail(limit)
    return {
        "ok": True,
        "price": chart[["Close", "MA20", "MA50"]].copy(),
        "volume": chart[["Volume"]].copy() if "Volume" in chart.columns else None,
    }


def get_chart_bundle(code: str) -> dict:
    """한 번의 일봉 조회로 일봉·주봉·월봉 차트를 함께 만든다."""
    frame = get_daily_frame(code, ttl_seconds=300)
    if frame is None or frame.empty:
        return {"ok": False, "error": "차트 자료가 없습니다", "charts": {}}
    return {
        "ok": True,
        "charts": {
            "일봉": _prepare_chart_payload(frame, None, 120),
            "주봉": _prepare_chart_payload(frame, "W-FRI", 60),
            "월봉": _prepare_chart_payload(frame, "ME", 36),
        },
    }
