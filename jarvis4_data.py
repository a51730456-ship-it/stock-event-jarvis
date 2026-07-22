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
DISPLAY_THEME_COUNT = 20
CANDIDATE_THEME_COUNT = 30
# 테마당 심사할 구성종목 수 (거래대금 상위부터).
THEME_STOCK_LIMIT = 8

_CACHE_LOCK = threading.Lock()
_CACHE: dict = {}


# ---------------------------------------------------------------------------
# 공통 유틸
# ---------------------------------------------------------------------------
def clear_runtime_cache() -> None:
    """사용자가 새로고침을 눌렀을 때 자비스4 메모리 캐시만 비운다."""
    with _CACHE_LOCK:
        _CACHE.clear()


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


def _get_text(url: str, *, timeout: float = 8, retries: int = 2) -> str:
    last_error = None
    for attempt in range(retries + 1):
        try:
            response = requests.get(url, timeout=timeout, headers=_HEADERS)
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
    current = _finite(live_price) or _finite(closes.iloc[-1])
    if not current:
        return {"ok": False}

    today = datetime.now(_SEOUL).date()
    last_date = pd.Timestamp(closes.index[-1]).date()
    if last_date == today and len(closes) >= 2:
        prev_close = _finite(closes.iloc[-2])
    else:
        prev_close = _finite(closes.iloc[-1])

    def ret(days: int):
        index = min(days + 1, len(closes))
        base = _finite(closes.iloc[-index])
        return (current / base - 1) * 100 if base else None

    sma20 = _finite(closes.tail(20).mean())
    sma50 = _finite(closes.tail(50).mean()) if len(closes) >= 50 else None
    sma200 = _finite(closes.tail(200).mean()) if len(closes) >= 200 else None
    high52 = None
    if "High" in daily.columns:
        high52 = _finite(daily["High"].tail(248).max())
    if high52 is None:
        high52 = _finite(closes.tail(248).max())

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
        "from_high_pct": ((current / high52 - 1) * 100) if high52 else None,
        "volume_ratio": volume_ratio,
        "avg_trading_value": avg_trading_value,
        "atr": atr,
        "atr_pct": atr_pct,
        "last_date": last_date.isoformat(),
    }


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

    return {
        "ok": True,
        "stale": stale,
        "rows": rows,
        "net5_amount": _amount(recent5),
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
        percents = _DETAIL_PCT_PATTERN.findall(body)
        price = _parse_number(numbers[0]) if numbers else None
        volume = _parse_number(numbers[3]) if len(numbers) > 3 else None
        change_pct = float(percents[0]) if percents else None
        if price is None:
            continue
        stocks.append({
            "code": code,
            "name": name.strip(),
            "price": price,
            "change_pct": change_pct,
            "volume": volume,
            "trading_value": (price * volume) if (price and volume) else None,
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


def _us_previous_session() -> dict:
    """미국 전일 결과 — 한국장은 미국 전일과 갭 상관이 높아 게이트에 넣는다."""
    try:
        import jarvis3_data as j3

        overview = j3.get_market_overview()
        if not overview.get("ok"):
            return {"ok": False}
        rows = overview.get("rows", {})
        spy = rows.get("SPY", {}).get("change_pct")
        qqq = rows.get("QQQ", {}).get("change_pct")
        fear_greed = j3.get_fear_greed()
        return {
            "ok": spy is not None and qqq is not None,
            "spy_change": spy,
            "qqq_change": qqq,
            "regime": overview.get("regime"),
            "score": overview.get("score"),
            "fear_greed": fear_greed.get("score") if fear_greed.get("ok") else None,
            "fear_greed_label": fear_greed.get("rating_kr") if fear_greed.get("ok") else None,
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
    for code, label in (("005930", "삼성전자"), ("000660", "SK하이닉스")):
        flow = get_stock_flow(code)
        if flow.get("ok"):
            ok_any = True
            total5 += flow["net5_amount"]
            details.append(f"{label} 5일 {flow['net5_amount'] / 1e8:+,.0f}억")
    if not ok_any:
        return {"ok": False}
    return {"ok": True, "net5_amount": total5, "detail": " · ".join(details)}


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


def get_theme_rankings() -> dict:
    """네이버 전체 테마에서 오늘 강한 테마 20개를 자동 선정한다."""
    listing = get_all_themes()
    if not listing.get("ok"):
        return {"ok": False, "error": listing.get("error"), "rows": []}

    themes = listing["themes"]
    kospi = _index_metrics("KS11", _live_index("^KS11"))
    kospi_change = kospi.get("change_pct") or 0.0

    # 1차: 네이버가 주는 당일 평균 등락률로 후보를 좁힌다(무료·빠름).
    candidates = sorted(themes.values(), key=lambda t: t["change_pct"], reverse=True)
    candidates = candidates[:CANDIDATE_THEME_COUNT]

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
    rows = rows[:DISPLAY_THEME_COUNT]
    for index, row in enumerate(rows, 1):
        row["rank"] = index

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
        streak_points = min(6.0, (flow.get("buy_streak_days") or 0) * 2.0)
        flow_points = amount_points + streak_points
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

    gates_ok = market_score >= 50 and theme_score >= 60 and score >= 70
    if gates_ok and state in {"돌파 확인", "눌림목 대기"}:
        recommendation = "조건부 후보"
    elif state in {"추격 금지", "제외"}:
        recommendation = "추천 제외"
    else:
        recommendation = "관찰"

    if market_score < 50:
        buy_reason = "시장 국면이 방어 우선이라 신규 매수를 보류합니다."
    elif theme_score < 60:
        buy_reason = "테마 강도가 기준 미달이라 종목 점수가 높아도 매수하지 않습니다."
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


def get_intraday_chart(code: str, *, ttl_seconds: float = 60) -> dict | None:
    """당일 분봉 흐름(네이버 siseJson). 자비스3의 당일 차트와 같은 역할이다.

    FinanceDataReader는 분봉을 주지 않아서 네이버 차트 API를 쓴다. 응답은 JSON이 아니라
    파이썬 리터럴 형식이고 시가·고가·저가는 null이라 종가만 뽑아 쓴다.
    """
    code = str(code).strip()
    day = datetime.now(_SEOUL).strftime("%Y%m%d")

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
