"""자비스3 미국 테마 레이더용 시세·판정 엔진.

기존 자비스1/2의 ``price_data.py``·``performance.py``는 사용하거나 수정하지 않는다.
Yahoo Finance의 최근 가용 시세를 읽기 전용으로 조회하며, 네트워크 실패는 예외 대신
구조화된 오류로 반환한다. 이 모듈의 점수는 확률 예측이 아니라 조건 충족도다.
"""

from __future__ import annotations

import logging
import math
import threading
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time as dt_time
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

_log = logging.getLogger(__name__)
_NY = ZoneInfo("America/New_York")
_SEOUL = ZoneInfo("Asia/Seoul")


US_THEMES = (
    {"name": "반도체", "etf": "SMH", "alt_etf": "SOXX", "stocks": ("NVDA", "AVGO", "AMD", "TSM", "QCOM", "MU", "AMAT", "LRCX", "ASML", "KLAC")},
    {"name": "AI·데이터센터", "etf": "AIQ", "alt_etf": "DTCR", "stocks": ("NVDA", "MSFT", "AVGO", "ANET", "VRT", "ORCL", "PLTR", "DELL", "HPE")},
    {"name": "전력망·전력설비", "etf": "GRID", "alt_etf": "PAVE", "stocks": ("GEV", "ETN", "PWR", "HUBB", "VRT", "NEE", "CEG", "EMR")},
    {"name": "방산·드론", "etf": "ITA", "alt_etf": "XAR", "stocks": ("RTX", "LMT", "NOC", "GD", "LHX", "AVAV", "KTOS", "HII")},
    {"name": "빅테크10", "etf": "FNGS", "alt_etf": "MAGS", "stocks": ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "NFLX", "CRWD")},
    {"name": "원전·우라늄", "etf": "URA", "alt_etf": "NLR", "stocks": ("CCJ", "CEG", "VST", "LEU", "SMR", "OKLO", "NXE", "UEC")},
    {"name": "사이버보안", "etf": "CIBR", "alt_etf": "HACK", "stocks": ("CRWD", "PANW", "FTNT", "ZS", "OKTA", "CHKP", "GEN")},
    {"name": "희토류·핵심광물", "etf": "REMX", "alt_etf": "PICK", "stocks": ("MP", "ALB", "SQM", "ELVR", "UUUU", "FCX", "RIO")},
    {"name": "양자컴퓨팅", "etf": "QTUM", "alt_etf": "WQTM", "stocks": ("IONQ", "QBTS", "RGTI", "QUBT", "IBM", "GOOGL", "HON", "MSFT")},
    {"name": "인프라·리쇼어링", "etf": "PAVE", "alt_etf": "IFRA", "stocks": ("CAT", "URI", "MLM", "VMC", "PWR", "GEV", "ETN", "NUE")},
    {"name": "핀테크·블록체인", "etf": "BLOK", "alt_etf": "FINX", "stocks": ("COIN", "HOOD", "PYPL", "XYZ", "MSTR", "SOFI", "NU")},
    {"name": "클라우드·SaaS", "etf": "SKYY", "alt_etf": "CLOU", "stocks": ("MSFT", "ORCL", "CRM", "NOW", "SNOW", "DDOG", "NET", "MDB")},
    {"name": "석유·가스", "etf": "XLE", "alt_etf": "XOP", "stocks": ("XOM", "CVX", "COP", "SLB", "EOG", "OXY", "MPC", "VLO")},
    {"name": "로봇·자동화", "etf": "BOTZ", "alt_etf": "ROBO", "stocks": ("ISRG", "NVDA", "ABBNY", "TER", "SYM", "ROK", "CGNX")},
    {"name": "바이오", "etf": "XBI", "alt_etf": "IBB", "stocks": ("REGN", "VRTX", "AMGN", "GILD", "BIIB", "MRNA", "CRSP", "ILMN")},
    {"name": "우주·위성", "etf": "UFO", "alt_etf": "ARKX", "stocks": ("RKLB", "ASTS", "LUNR", "RDW", "PL", "SATS", "IRDM")},
    {"name": "주택·홈빌더", "etf": "XHB", "alt_etf": "ITB", "stocks": ("DHI", "LEN", "PHM", "TOL", "NVR", "HD", "LOW")},
    {"name": "유전체·정밀의료", "etf": "ARKG", "alt_etf": "GNOM", "stocks": ("CRSP", "NTLA", "BEAM", "TWST", "PACB", "ILMN", "TEM")},
    {"name": "배터리·전기차", "etf": "LIT", "alt_etf": "DRIV", "stocks": ("TSLA", "ALB", "RIVN", "GM", "F", "STLA", "QS", "CHPT")},
    {"name": "태양광·청정에너지", "etf": "TAN", "alt_etf": "ICLN", "stocks": ("FSLR", "ENPH", "NXT", "SEDG", "RUN", "BEP", "CWEN")},
)

THEME_BY_NAME = {item["name"]: item for item in US_THEMES}

STOCK_NAMES = {
    "NVDA": "NVIDIA", "AVGO": "Broadcom", "AMD": "AMD", "TSM": "TSMC",
    "QCOM": "Qualcomm", "MU": "Micron", "AMAT": "Applied Materials",
    "LRCX": "Lam Research", "ASML": "ASML", "KLAC": "KLA",
    "MSFT": "Microsoft", "ANET": "Arista Networks", "VRT": "Vertiv",
    "ORCL": "Oracle", "PLTR": "Palantir", "DELL": "Dell", "HPE": "HPE",
    "GEV": "GE Vernova", "ETN": "Eaton", "PWR": "Quanta Services",
    "HUBB": "Hubbell", "NEE": "NextEra Energy", "CEG": "Constellation Energy",
    "RTX": "RTX", "LMT": "Lockheed Martin", "NOC": "Northrop Grumman",
    "GD": "General Dynamics", "LHX": "L3Harris", "AVAV": "AeroVironment",
    "KTOS": "Kratos", "AAPL": "Apple", "AMZN": "Amazon", "GOOGL": "Alphabet",
    "META": "Meta", "TSLA": "Tesla", "NFLX": "Netflix", "CRWD": "CrowdStrike",
    "IONQ": "IonQ", "QBTS": "D-Wave Quantum", "RGTI": "Rigetti Computing",
    "QUBT": "Quantum Computing", "IBM": "IBM", "HON": "Honeywell",
    "CCJ": "Cameco", "VST": "Vistra", "LEU": "Centrus Energy", "SMR": "NuScale Power",
    "OKLO": "Oklo", "XOM": "Exxon Mobil", "CVX": "Chevron", "COIN": "Coinbase",
    "ELVR": "Elevra Lithium", "ABBNY": "ABB ADR",
    "HOOD": "Robinhood", "PANW": "Palo Alto Networks", "FTNT": "Fortinet",
    "RKLB": "Rocket Lab", "ASTS": "AST SpaceMobile", "LUNR": "Intuitive Machines",
    "FSLR": "First Solar", "ENPH": "Enphase Energy", "ISRG": "Intuitive Surgical",
}

# 지수 자체. ETF(SPY·QQQ)는 지수를 따라갈 뿐이라 등락률이 조금씩 어긋난다
# (2026-07-24 실측: 전일 S&P500 지수 -1.21%인데 SPY는 -1.23%, 나스닥100 -1.87% vs
# QQQ -1.90%). 화면에 '지수'라고 적는 자리에는 지수를 그대로 쓴다.
US_INDEX_DISPLAY = (
    ("^GSPC", "S&P 500"),
    ("^IXIC", "나스닥 종합"),
    ("^DJI", "다우존스"),
    ("^NDX", "나스닥 100"),
)
US_INDEX_SYMBOLS = tuple(symbol for symbol, _name in US_INDEX_DISPLAY)

MARKET_SYMBOLS = ("SPY", "QQQ", "IWM", "DIA", "^VIX") + US_INDEX_SYMBOLS

# 실행 중인 프로세스에 옛 모듈이 남아 있는지 화면이 스스로 알아채기 위한 표식이다
# (자비스4와 같은 장치). 계산 결과나 반환 키를 바꾸면 이 숫자를 올린다.
MODULE_REVISION = 2026073110

_DOWNLOAD_LOCK = threading.Lock()
_CACHE_LOCK = threading.Lock()
_CACHE: dict[tuple, dict] = {}
_YF_CACHE_READY = False


def _configure_yfinance_cache(yf) -> None:
    """권한이 제한된 실행환경에서도 yfinance SQLite 캐시가 열리게 한다."""
    global _YF_CACHE_READY
    if _YF_CACHE_READY:
        return
    cache_dir = Path(__file__).parent / "cache" / "jarvis3_yfinance"
    cache_dir.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(cache_dir))
    _YF_CACHE_READY = True


def clear_runtime_cache() -> None:
    """사용자가 새로고침을 눌렀을 때 자비스3 메모리 캐시만 비운다."""
    with _CACHE_LOCK:
        _CACHE.clear()
    with _FEAR_GREED_LOCK:
        _FEAR_GREED_CACHE.update({"at": 0.0, "value": None})


def _finite(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _normalize_frame(frame) -> pd.DataFrame | None:
    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
        return None
    out = frame.copy()
    if isinstance(out.columns, pd.MultiIndex):
        if len(set(out.columns.get_level_values(0))) == 1:
            out.columns = out.columns.get_level_values(-1)
        elif len(set(out.columns.get_level_values(-1))) == 1:
            out.columns = out.columns.get_level_values(0)
    out.columns = [str(col).title() for col in out.columns]
    required = [col for col in ("Open", "High", "Low", "Close", "Volume") if col in out.columns]
    if "Close" not in required:
        return None
    out = out[required]
    for column in required:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    out = out.dropna(subset=["Close"])
    if out.empty:
        return None
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out


def _split_download(raw, tickers: tuple[str, ...]) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    if raw is None or not isinstance(raw, pd.DataFrame) or raw.empty:
        return frames
    if isinstance(raw.columns, pd.MultiIndex):
        level0 = set(map(str, raw.columns.get_level_values(0)))
        level1 = set(map(str, raw.columns.get_level_values(1)))
        for ticker in tickers:
            try:
                if ticker in level0:
                    candidate = raw[ticker]
                elif ticker in level1:
                    candidate = raw.xs(ticker, axis=1, level=1)
                else:
                    continue
                normalized = _normalize_frame(candidate)
                if normalized is not None:
                    frames[ticker] = normalized
            except Exception:
                continue
    elif len(tickers) == 1:
        normalized = _normalize_frame(raw)
        if normalized is not None:
            frames[tickers[0]] = normalized
    return frames


def _copy_frames(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    return {ticker: frame.copy() for ticker, frame in frames.items()}


def _download_cache_only(
    tickers, *, period: str, interval: str, ttl_seconds: float, prepost: bool = False
) -> tuple[dict[str, pd.DataFrame], dict]:
    """정확 키 또는 더 큰 배치의 메모리 캐시만 읽고 네트워크는 호출하지 않는다."""
    unique = tuple(dict.fromkeys(str(t).strip().upper() for t in tickers if str(t).strip()))
    requested = set(unique)
    now = time.time()
    with _CACHE_LOCK:
        for cached_key, candidate in _CACHE.items():
            if not isinstance(cached_key, tuple) or len(cached_key) != 4:
                continue
            cached_tickers, cached_period, cached_interval, cached_prepost = cached_key
            if (
                cached_period == period
                and cached_interval == interval
                and bool(cached_prepost) == bool(prepost)
                and requested.issubset(set(cached_tickers))
                and now - candidate["at"] < ttl_seconds
            ):
                frames = {
                    ticker: candidate["frames"][ticker].copy()
                    for ticker in unique if ticker in candidate["frames"]
                }
                if frames:
                    return frames, {
                        "ok": True, "error": None, "stale": False,
                        "fetched_at": candidate["fetched_at"], "reused_superset": True,
                    }
    return {}, {"ok": False, "error": "재사용할 일봉 배치가 없습니다", "stale": False}


def _cached_value(key, ttl_seconds: float, produce):
    """시세가 아닌 일반 값(예: 상장 종목 목록)을 같은 캐시에 담는다.

    _download_cached는 (티커, 기간, 간격, 프리포스트) 4칸 키만 다루므로 그쪽에
    끼워 넣을 수 없다. 키를 문자열로 두어 그 순회 로직과 섞이지 않게 한다.
    """
    now = time.time()
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and now - cached["at"] < ttl_seconds:
            return cached["value"], False
    value = produce()
    with _CACHE_LOCK:
        _CACHE[key] = {"at": now, "value": value}
    return value, False


def _download_cached(
    tickers,
    *,
    period: str,
    interval: str,
    ttl_seconds: float,
    prepost: bool = False,
) -> tuple[dict[str, pd.DataFrame], dict]:
    unique = tuple(dict.fromkeys(str(t).strip().upper() for t in tickers if str(t).strip()))
    if not unique:
        return {}, {"ok": False, "error": "조회 티커가 없습니다", "stale": False}
    key = (unique, period, interval, bool(prepost))
    now = time.time()
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and now - cached["at"] < ttl_seconds:
            return _copy_frames(cached["frames"]), {
                "ok": True, "error": None, "stale": False, "fetched_at": cached["fetched_at"]
            }
        # 테마 순위가 이미 더 큰 티커 묶음을 한 번에 내려받았다면 그 프레임을 재사용한다.
        # 눌림목 찾기가 130여 종목을 다시 다운로드하지 않게 하는 핵심 경로다.
        requested = set(unique)
        for cached_key, candidate in _CACHE.items():
            if not isinstance(cached_key, tuple) or len(cached_key) != 4:
                continue
            cached_tickers, cached_period, cached_interval, cached_prepost = cached_key
            if (
                cached_period == period
                and cached_interval == interval
                and bool(cached_prepost) == bool(prepost)
                and requested.issubset(set(cached_tickers))
                and now - candidate["at"] < ttl_seconds
            ):
                frames = {
                    ticker: candidate["frames"][ticker].copy()
                    for ticker in unique if ticker in candidate["frames"]
                }
                if frames:
                    return frames, {
                        "ok": True, "error": None, "stale": False,
                        "fetched_at": candidate["fetched_at"], "reused_superset": True,
                    }

    try:
        import yfinance as yf

        with _DOWNLOAD_LOCK:
            _configure_yfinance_cache(yf)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                raw = yf.download(
                    list(unique),
                    period=period,
                    interval=interval,
                    group_by="ticker",
                    auto_adjust=True,
                    prepost=prepost,
                    threads=True,
                    progress=False,
                    timeout=15,
                    multi_level_index=True,
                )
        frames = _split_download(raw, unique)
        if not frames:
            raise RuntimeError("시세 응답이 비어 있습니다")
        fetched_at = datetime.now(_SEOUL).isoformat(timespec="seconds")
        with _CACHE_LOCK:
            _CACHE[key] = {"at": now, "fetched_at": fetched_at, "frames": _copy_frames(frames)}
        return frames, {"ok": True, "error": None, "stale": False, "fetched_at": fetched_at}
    except Exception as exc:
        _log.warning("jarvis3 yfinance download failed interval=%s tickers=%s: %s", interval, len(unique), exc)
        with _CACHE_LOCK:
            stale = _CACHE.get(key)
        if stale:
            return _copy_frames(stale["frames"]), {
                "ok": True,
                "error": str(exc),
                "stale": True,
                "fetched_at": stale["fetched_at"],
            }
        return {}, {"ok": False, "error": str(exc), "stale": False, "fetched_at": None}


def _last_close(frame: pd.DataFrame | None) -> float | None:
    if frame is None or frame.empty:
        return None
    return _finite(frame["Close"].dropna().iloc[-1])


def _source_time(frame: pd.DataFrame | None) -> str | None:
    if frame is None or frame.empty:
        return None
    try:
        stamp = pd.Timestamp(frame.index[-1])
        if stamp.tzinfo is None:
            stamp = stamp.tz_localize(_NY)
        else:
            stamp = stamp.tz_convert(_NY)
        return stamp.astimezone(_SEOUL).isoformat(timespec="seconds")
    except Exception:
        return None


def _last_session_change(closes, last_date, today_ny, now_ny=None) -> float | None:
    """마지막으로 '끝난' 정규장의 등락률.

    일봉 마지막 줄이 오늘 날짜여도 장이 아직 안 끝났으면(뉴욕 16시 전) 그 줄은
    진행 중이라 쓰면 안 된다. 그 경우 한 칸 앞 세션을 쓴다.
    """
    if len(closes) < 2:
        return None
    now_ny = now_ny or datetime.now(_NY)
    finished = last_date < today_ny or now_ny.time() >= dt_time(16, 0)
    end = -1 if finished else -2
    if len(closes) < abs(end) + 1:
        return None
    base = _finite(closes.iloc[end - 1])
    close = _finite(closes.iloc[end])
    if not base or close is None:
        return None
    return (close / base - 1) * 100


def _series_metrics(daily: pd.DataFrame | None, intraday: pd.DataFrame | None = None) -> dict:
    if daily is None or len(daily) < 25:
        return {"ok": False}
    closes = daily["Close"].dropna().astype(float)
    if len(closes) < 25:
        return {"ok": False}
    current = _last_close(intraday) or _last_close(daily)
    if current is None:
        return {"ok": False}

    today_ny = datetime.now(_NY).date()
    last_index = pd.Timestamp(closes.index[-1])
    if last_index.tzinfo is not None:
        last_date = last_index.tz_convert(_NY).date()
    else:
        last_date = last_index.date()
    if last_date == today_ny and len(closes) >= 2:
        prev_close = _finite(closes.iloc[-2])
    else:
        prev_close = _finite(closes.iloc[-1])

    # '마지막으로 끝난 정규장'의 등락률. change_pct는 지금 값(프리마켓·시간외 포함)
    # 기준이라 '미국 전일'처럼 끝난 장을 물어보는 자리에는 쓸 수 없다
    # (2026-07-24 실측: 전일 -1.23%인데 화면에 프리마켓 +0.22%가 나왔다).
    last_session_change_pct = _last_session_change(closes, last_date, today_ny)

    ret = lambda days: (current / float(closes.iloc[-min(days + 1, len(closes))]) - 1) * 100
    sma20 = _finite(closes.tail(20).mean())
    sma50 = _finite(closes.tail(50).mean()) if len(closes) >= 50 else None
    sma200 = _finite(closes.tail(200).mean()) if len(closes) >= 200 else None
    high52 = None
    high52_days_ago = None
    if "High" in daily.columns:
        highs = daily["High"].dropna().astype(float).tail(252)
        if not highs.empty:
            high52 = _finite(highs.max())
            high52_days_ago = int(len(highs) - 1 - highs.values.argmax())
    if high52 is None:
        high_closes = closes.tail(252)
        high52 = _finite(high_closes.max())
        if high52 is not None and not high_closes.empty:
            high52_days_ago = int(len(high_closes) - 1 - high_closes.values.argmax())

    volume_ratio = None
    avg_dollar_volume = None
    if "Volume" in daily.columns:
        volumes = daily["Volume"].dropna().astype(float)
        if not volumes.empty:
            avg_volume = _finite(volumes.tail(20).mean())
            latest_volume = _finite(volumes.iloc[-1])
            if avg_volume and latest_volume is not None:
                volume_ratio = latest_volume / avg_volume
                avg_dollar_volume = avg_volume * current

    atr_pct = None
    atr = None
    if {"High", "Low", "Close"}.issubset(daily.columns) and len(daily) >= 15:
        high = daily["High"].astype(float)
        low = daily["Low"].astype(float)
        prev = daily["Close"].shift(1).astype(float)
        tr = pd.concat([(high - low), (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
        atr = _finite(tr.tail(14).mean())
        if atr is not None and current:
            atr_pct = atr / current * 100

    return {
        "ok": True,
        "current": current,
        "prev_close": prev_close,
        "change_pct": ((current / prev_close - 1) * 100) if prev_close else None,
        "last_session_change_pct": last_session_change_pct,
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
        "avg_dollar_volume": avg_dollar_volume,
        "atr": atr,
        "atr_pct": atr_pct,
        "source_time": _source_time(intraday) or _source_time(daily),
        # 당일 시가·고가·저가·종가 (2026-07-24 사용자 요청, 자비스4와 같은 칸).
        # 장중에는 일봉 마지막 행이 진행 중인 값이고, 오늘 행이 아직 없으면
        # 마지막 거래일 값이므로 day_is_today로 구분해 화면에서 알려준다.
        **_day_prices(daily, last_date == today_ny),
    }


def _day_prices(daily: pd.DataFrame, is_today: bool) -> dict:
    """일봉 마지막 행의 시가·고가·저가·종가를 꺼낸다(자비스4와 같은 형식)."""
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
# CNN 공포·탐욕 지수 (2026-07-22 추가) — 읽기 전용 참고 지표.
# 점수·판정에는 반영하지 않고 시장판단 상단에 표시만 한다.
# ---------------------------------------------------------------------------
_FEAR_GREED_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
_FEAR_GREED_TTL_SECONDS = 300.0
_FEAR_GREED_LOCK = threading.Lock()
_FEAR_GREED_CACHE: dict = {"at": 0.0, "value": None}

_FEAR_GREED_RATING_KR = {
    "extreme fear": "극단적 공포",
    "fear": "공포",
    "neutral": "중립",
    "greed": "탐욕",
    "extreme greed": "극단적 탐욕",
}


def fear_greed_label(score: float) -> str:
    """CNN 게이지와 같은 구간 이름. rating 문자열이 없을 때의 대체 라벨."""
    if score <= 25:
        return "극단적 공포"
    if score < 45:
        return "공포"
    if score <= 55:
        return "중립"
    if score < 75:
        return "탐욕"
    return "극단적 탐욕"


def _fear_greed_request(url: str, *, timeout: float = 8):
    import json
    from urllib.request import Request, urlopen

    # CNN이 브라우저가 아닌 요청을 418로 차단한다 — Referer·언어 헤더까지 있어야
    # 통과한다(2026-07-22 실측: UA만으로는 418, 아래 조합으로 200 확인).
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://edition.cnn.com/markets/fear-and-greed",
        },
        method="GET",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def get_fear_greed(request_json=None) -> dict:
    """CNN 공포·탐욕 지수(0~100)를 조회한다. 실패하면 ok=False 또는 마지막 정상값."""
    now = time.time()
    with _FEAR_GREED_LOCK:
        cached = _FEAR_GREED_CACHE["value"]
        if cached and now - _FEAR_GREED_CACHE["at"] < _FEAR_GREED_TTL_SECONDS:
            return dict(cached)
    try:
        payload = (request_json or _fear_greed_request)(_FEAR_GREED_URL)
        block = payload.get("fear_and_greed") if isinstance(payload, dict) else None
        if not isinstance(block, dict):
            raise RuntimeError("응답에 fear_and_greed 데이터가 없습니다")
        score = _finite(block.get("score"))
        if score is None or not 0 <= score <= 100:
            raise RuntimeError("지수 값이 0~100 범위가 아닙니다")
        rating = str(block.get("rating") or "").strip().lower()
        value = {
            "ok": True,
            "score": round(score, 1),
            "rating": rating,
            "rating_kr": _FEAR_GREED_RATING_KR.get(rating) or fear_greed_label(score),
            "previous_close": _finite(block.get("previous_close")),
            "previous_1_week": _finite(block.get("previous_1_week")),
            "previous_1_month": _finite(block.get("previous_1_month")),
            "previous_1_year": _finite(block.get("previous_1_year")),
            "as_of": str(block.get("timestamp") or ""),
            "stale": False,
            "source": "CNN Fear & Greed",
        }
        with _FEAR_GREED_LOCK:
            _FEAR_GREED_CACHE.update({"at": now, "value": dict(value)})
        return value
    except Exception as exc:
        _log.warning("jarvis3 fear&greed fetch failed: %s", exc)
        with _FEAR_GREED_LOCK:
            stale_value = _FEAR_GREED_CACHE["value"]
        if stale_value:
            return {**stale_value, "stale": True, "error": str(exc)}
        return {"ok": False, "error": str(exc)}


def market_phase(now: datetime | None = None) -> dict:
    now_ny = (now or datetime.now(_NY)).astimezone(_NY)
    if now_ny.weekday() >= 5:
        label = "주말 휴장"
    elif now_ny.time() < dt_time(4, 0):
        label = "정규장 전"
    elif now_ny.time() < dt_time(9, 30):
        label = "프리마켓"
    elif now_ny.time() < dt_time(16, 0):
        label = "정규장 시간"
    elif now_ny.time() < dt_time(20, 0):
        label = "애프터마켓"
    else:
        label = "장 마감"
    return {"label": label, "new_york_time": now_ny.isoformat(timespec="seconds")}


def _market_regime_from_rows(rows: dict) -> dict:
    """SPY·QQQ·IWM·VIX 행으로 시장 조건점수와 국면을 만든다.

    현재 장중값과 전일 마감값에 같은 배점을 적용하기 위해 계산을 한 곳에 둔다.
    """
    spy, qqq = rows.get("SPY", {}), rows.get("QQQ", {})
    iwm, vix = rows.get("IWM", {}), rows.get("^VIX", {})
    score = 0
    reasons = []
    score_breakdown = []

    def add_trend_check(label: str, row: dict, average_key: str, points: int, reason: str) -> None:
        nonlocal score
        current = row.get("current")
        average = row.get(average_key)
        passed = current is not None and average is not None and current > average
        earned = points if passed else 0
        score += earned
        if passed:
            reasons.append(reason)
        score_breakdown.append({"label": label, "earned": earned, "max": points,
                                "state": "충족" if passed else "미충족"})

    add_trend_check("SPY 50일선", spy, "sma50", 25, "SPY 50일선 위")
    add_trend_check("QQQ 50일선", qqq, "sma50", 20, "QQQ 50일선 위")
    add_trend_check("SPY 20일선", spy, "sma20", 15, "SPY 단기추세 양호")
    add_trend_check("QQQ 20일선", qqq, "sma20", 15, "QQQ 단기추세 양호")
    add_trend_check("IWM 50일선", iwm, "sma50", 10, "중소형주 동행")
    vix_value = vix.get("current") if vix.get("ok") else None
    if vix_value is not None and vix_value < 25:
        score += 15
        reasons.append("VIX 25 미만")
        vix_earned, vix_state = 15, "충족"
    elif vix_value is not None and vix_value < 35:
        score += 5
        reasons.append("VIX 경계 구간")
        vix_earned, vix_state = 5, "부분 충족"
    else:
        vix_earned = 0
        vix_state = "자료부족" if vix_value is None else "미충족"
    score_breakdown.append({"label": "VIX 위험수준", "earned": vix_earned, "max": 15,
                            "state": vix_state})

    if score >= 75:
        regime, posture = "상승 우위", "조건 충족 종목만 매수 심사"
    elif score >= 50:
        regime, posture = "중립·선별", "비중 축소·확인 후 진입"
    else:
        regime, posture = "방어 우선", "신규 매수 보류"
    return {"ok": True, "score": score, "regime": regime, "posture": posture,
            "reasons": reasons, "score_breakdown": score_breakdown}


def _previous_market_regime(daily: dict) -> dict | None:
    """직전 완료 미국장의 같은 조건점수. 장중에는 오늘 일봉을 제외한다."""
    rows = {}
    today_ny = datetime.now(_NY).date()
    for ticker in ("SPY", "QQQ", "IWM", "^VIX"):
        frame = daily.get(ticker)
        if frame is None or frame.empty:
            return None
        last_date = pd.Timestamp(frame.index[-1])
        last_date = last_date.tz_convert(_NY).date() if last_date.tzinfo else last_date.date()
        completed = frame if last_date < today_ny else frame.iloc[:-1]
        metrics = _series_metrics(completed)
        if not metrics.get("ok"):
            return None
        rows[ticker] = metrics
    result = _market_regime_from_rows(rows)
    result["as_of"] = "직전 완료 미국장"
    return result


def get_market_overview() -> dict:
    daily, daily_meta = _download_cached(
        MARKET_SYMBOLS, period="1y", interval="1d", ttl_seconds=300
    )
    # 지수는 시간외·프리마켓 거래가 없어 1분봉을 달라고 하면 빈 응답과 경고만
    # 돌아온다. 지수는 일봉만 쓰고, 실시간이 있는 것만 1분봉을 받는다(2026-07-24).
    _INTRADAY_SYMBOLS = tuple(s for s in MARKET_SYMBOLS if s not in US_INDEX_SYMBOLS)
    intraday, live_meta = _download_cached(
        _INTRADAY_SYMBOLS, period="1d", interval="1m", ttl_seconds=45, prepost=True
    )
    rows = {}
    for ticker in MARKET_SYMBOLS:
        rows[ticker] = _series_metrics(daily.get(ticker), intraday.get(ticker))

    spy, qqq, iwm, vix = rows.get("SPY", {}), rows.get("QQQ", {}), rows.get("IWM", {}), rows.get("^VIX", {})
    if not spy.get("ok") or not qqq.get("ok"):
        return {
            "ok": False,
            "error": live_meta.get("error") or daily_meta.get("error") or "SPY·QQQ 시세 조회 실패",
            "phase": market_phase(),
            "rows": rows,
        }

    assessment = _market_regime_from_rows(rows)
    previous_market = _previous_market_regime(daily)

    source_times = [row.get("source_time") for row in rows.values() if row.get("source_time")]
    return {
        "ok": True,
        **assessment,
        "previous_market": previous_market,
        "rows": rows,
        "phase": market_phase(),
        "checked_at": max(source_times) if source_times else live_meta.get("fetched_at"),
        "stale": bool(daily_meta.get("stale") or live_meta.get("stale")),
        "error": live_meta.get("error") if live_meta.get("stale") else None,
    }


def _scale(value: float | None, low: float, high: float, points: float) -> float:
    if value is None:
        return 0.0
    if high <= low:
        return 0.0
    return max(0.0, min(points, (value - low) / (high - low) * points))


def get_theme_rankings() -> dict:
    all_tickers = ["SPY"]
    live_tickers = ["SPY"]
    for theme in US_THEMES:
        all_tickers.extend((theme["etf"], theme["alt_etf"], *theme["stocks"]))
        live_tickers.extend((theme["etf"], theme["alt_etf"]))
    all_tickers = list(dict.fromkeys(all_tickers))
    live_tickers = list(dict.fromkeys(live_tickers))

    daily, daily_meta = _download_cached(
        all_tickers, period="1y", interval="1d", ttl_seconds=300
    )
    intraday, live_meta = _download_cached(
        live_tickers, period="1d", interval="1m", ttl_seconds=45, prepost=True
    )
    spy = _series_metrics(daily.get("SPY"), intraday.get("SPY"))
    if not spy.get("ok"):
        return {"ok": False, "error": daily_meta.get("error") or "SPY 기준 자료가 없습니다", "rows": []}

    rows = []
    for theme in US_THEMES:
        etf_used = theme["etf"] if theme["etf"] in daily else theme["alt_etf"]
        metrics = _series_metrics(daily.get(etf_used), intraday.get(etf_used))
        if not metrics.get("ok") or metrics.get("ret60") is None:
            rows.append({"name": theme["name"], "etf": etf_used, "ok": False, "error": "ETF 이력 부족"})
            continue
        valid_breadth = []
        for ticker in theme["stocks"]:
            stock_metrics = _series_metrics(daily.get(ticker))
            if stock_metrics.get("ok") and stock_metrics.get("sma20"):
                valid_breadth.append(stock_metrics["current"] > stock_metrics["sma20"])
        breadth = (sum(valid_breadth) / len(valid_breadth) * 100) if valid_breadth else None
        rs20 = metrics["ret20"] - spy["ret20"]
        rs60 = metrics["ret60"] - spy["ret60"] if spy.get("ret60") is not None else None
        trend_points = 0
        if metrics.get("sma20") and metrics["current"] > metrics["sma20"]:
            trend_points += 10
        if metrics.get("sma50") and metrics["current"] > metrics["sma50"]:
            trend_points += 10
        daily_frame = daily.get(etf_used)
        up_ratio = None
        if daily_frame is not None and len(daily_frame) >= 21:
            changes = daily_frame["Close"].pct_change().dropna().tail(20)
            up_ratio = float((changes > 0).mean() * 100) if not changes.empty else None
        score = round(
            _scale(rs20, -10, 10, 30)
            + _scale(rs60, -15, 15, 25)
            + trend_points
            + _scale(breadth, 25, 85, 15)
            + _scale(up_ratio, 30, 70, 10),
            1,
        )
        status = "주도" if score >= 75 else "관찰" if score >= 60 else "약함"
        rows.append({
            "name": theme["name"],
            "etf": etf_used,
            "alt_etf": theme["alt_etf"],
            "ok": True,
            "score": score,
            "status": status,
            "change_pct": metrics.get("change_pct"),
            "rs20": rs20,
            "rs60": rs60,
            "breadth": breadth,
            "source_time": metrics.get("source_time"),
            "basis": f"20일 상대강도 {rs20:+.1f}%p · 60일 {rs60:+.1f}%p · 20일선 위 {breadth:.0f}%" if breadth is not None and rs60 is not None else "자료 일부 부족",
        })

    rows.sort(key=lambda row: (bool(row.get("ok")), row.get("score", -1)), reverse=True)
    for index, row in enumerate(rows, 1):
        row["rank"] = index
    return {
        "ok": any(row.get("ok") for row in rows),
        "rows": rows,
        "checked_at": live_meta.get("fetched_at") or daily_meta.get("fetched_at"),
        "stale": bool(daily_meta.get("stale") or live_meta.get("stale")),
        "error": live_meta.get("error") if live_meta.get("stale") else None,
    }


def _pullback_quality(metrics: dict, theme_count: int) -> dict | None:
    """미국 종목 눌림목 품질. 다중 테마는 필수가 아니라 최대 5점 가산이다."""
    current = _finite(metrics.get("current"))
    sma20 = _finite(metrics.get("sma20"))
    if current is None or sma20 is None or current <= 0:
        return None
    days_ago = metrics.get("high52_days_ago")
    from_high = _finite(metrics.get("from_high_pct"))
    gap = (current / sma20 - 1) * 100

    if days_ago is None:
        recency = 0.0
    elif days_ago <= 10:
        recency = 25.0
    elif days_ago >= 60:
        recency = 0.0
    else:
        recency = 25.0 * (1 - (days_ago - 10) / 50)
    proximity = max(0.0, 20.0 * (1 - max(0.0, abs(gap) - 1.5) / 7.5))
    trend = 0.0
    if metrics.get("sma50") and current > metrics["sma50"]:
        trend += 10.0
    if metrics.get("sma200") and current > metrics["sma200"]:
        trend += 10.0
    if from_high is None:
        depth = 0.0
    elif -20 <= from_high <= -4:
        depth = 20.0
    elif -28 <= from_high < -20 or -4 < from_high <= -2:
        depth = 12.0
    else:
        depth = 3.0
    liquidity = _scale(metrics.get("avg_dollar_volume"), 20_000_000, 500_000_000, 10)
    theme_bonus = min(5.0, max(0, int(theme_count) - 1) * 2.5)
    return {
        "score": round(min(100.0, recency + proximity + trend + depth + liquidity + theme_bonus), 1),
        "parts": [round(recency, 1), round(proximity, 1), round(trend, 1),
                  round(depth, 1), round(liquidity, 1), round(theme_bonus, 1)],
        "gap_pct": gap,
        "from_high_pct": from_high,
        "high52_days_ago": days_ago,
    }


def find_pullback_stocks(
    *,
    high_days_min: int = 1,
    high_days_max: int = 20,
    # 2026-07-24 사용자 지시로 합격선을 60 → 75점으로 올리고 목록을 8개로 줄였다 —
    # 한국(신고가 시점 75점)과 같은 성격의 짧은 목록으로 맞추기 위해서다.
    min_score: float = 75.0,
    result_limit: int = 8,
    reuse_only: bool = False,
) -> dict:
    """미국 테마 전체 종목에서 상승추세 중 조정 후보를 한 번에 찾는다.

    테마 순위가 받은 1년 일봉 묶음을 그대로 재사용한다. 이 함수를 먼저 실행한
    경우에도 모든 종목을 yfinance 한 번의 배치 요청으로 받는다.
    """
    memberships: dict[str, list[str]] = {}
    for theme in US_THEMES:
        for ticker in theme["stocks"]:
            memberships.setdefault(ticker, []).append(theme["name"])
    tickers = tuple(memberships)
    loader = _download_cache_only if reuse_only else _download_cached
    daily, meta = loader(tickers, period="1y", interval="1d", ttl_seconds=300)
    if not daily:
        return {"ok": False, "error": meta.get("error") or "미국 종목 일봉 조회 실패", "rows": []}

    rows = []
    trend_count = 0
    window_count = 0
    for ticker, themes in memberships.items():
        metrics = _series_metrics(daily.get(ticker))
        if not metrics.get("ok"):
            continue
        current = metrics.get("current")
        sma50 = metrics.get("sma50")
        sma200 = metrics.get("sma200")
        if not current or not sma50:
            continue
        # 상승 배열(sma50>sma200)은 유지하되 조정 중 50일선을 3% 이내로 잠깐
        # 밑도는 종목은 눌림 후보에서 바로 버리지 않는다.
        if current < sma50 * 0.97:
            continue
        if sma200 and (sma50 <= sma200 or current <= sma200):
            continue
        trend_count += 1
        days_ago = metrics.get("high52_days_ago")
        from_high = metrics.get("from_high_pct")
        if days_ago is None or not (high_days_min <= days_ago <= high_days_max):
            continue
        if from_high is None or from_high >= -0.5:
            continue
        window_count += 1
        quality = _pullback_quality(metrics, len(themes))
        if quality and quality["score"] >= min_score:
            rows.append({
                "ticker": ticker,
                "name": STOCK_NAMES.get(ticker, ticker),
                "themes": themes,
                "theme_count": len(themes),
                "metrics": metrics,
                "pullback": quality,
            })
    rows.sort(
        key=lambda row: (row["pullback"]["score"], row["metrics"].get("avg_dollar_volume") or 0),
        reverse=True,
    )
    rows = rows[: max(1, int(result_limit))]
    for index, row in enumerate(rows, 1):
        row["pullback_rank"] = index
    return {
        "ok": True,
        "rows": rows,
        "universe_count": len(tickers),
        "data_count": len(daily),
        "trend_count": trend_count,
        "window_count": window_count,
        "window": (high_days_min, high_days_max),
        # 화면 안내 문구가 합격선을 직접 적지 않고 이 값을 쓰게 한다 —
        # 기준을 바꿔도 문구가 따라 바뀌도록.
        "min_score": float(min_score),
        "result_limit": int(result_limit),
        "checked_at": meta.get("fetched_at"),
        "stale": bool(meta.get("stale")),
        "reused_batch": bool(meta.get("reused_superset")),
    }


def _leader_score(metrics: dict, theme_ret20: float | None) -> tuple[float, list[float]]:
    relative = metrics.get("ret20") - theme_ret20 if theme_ret20 is not None else None
    rs_points = _scale(relative, -8, 8, 25)
    from_high = metrics.get("from_high_pct")
    high_points = _scale(from_high, -20, 0, 25)
    trend_points = 0.0
    for moving_average, points in (("sma20", 6), ("sma50", 7), ("sma200", 7)):
        value = metrics.get(moving_average)
        if value and metrics.get("current") and metrics["current"] > value:
            trend_points += points
    dollar_volume = metrics.get("avg_dollar_volume")
    if dollar_volume is None:
        liquidity_points = 0.0
    elif dollar_volume >= 1_000_000_000:
        liquidity_points = 15.0
    elif dollar_volume >= 300_000_000:
        liquidity_points = 13.0
    elif dollar_volume >= 100_000_000:
        liquidity_points = 10.0
    elif dollar_volume >= 50_000_000:
        liquidity_points = 7.0
    elif dollar_volume >= 20_000_000:
        liquidity_points = 4.0
    else:
        liquidity_points = 1.0
    atr_pct = metrics.get("atr_pct")
    if atr_pct is None:
        risk_points = 0.0
    elif atr_pct <= 3:
        risk_points = 15.0
    elif atr_pct <= 5:
        risk_points = 12.0
    elif atr_pct <= 7:
        risk_points = 8.0
    elif atr_pct <= 10:
        risk_points = 4.0
    else:
        risk_points = 0.0
    score = rs_points + high_points + trend_points + liquidity_points + risk_points
    if metrics.get("ret5") is not None and metrics["ret5"] >= 15:
        score -= 10
    return round(max(0.0, min(100.0, score)), 1), [
        round(rs_points, 1), round(high_points, 1), round(trend_points, 1),
        round(liquidity_points, 1), round(risk_points, 1),
    ]


def _entry_plan(metrics: dict, score: float, market_score: float, theme_score: float) -> dict:
    current = metrics.get("current")
    atr = metrics.get("atr")
    sma20 = metrics.get("sma20")
    from_high = metrics.get("from_high_pct")
    ret5 = metrics.get("ret5")
    atr_pct = metrics.get("atr_pct")
    if not current:
        return {"state": "자료 부족", "recommendation": "추천 불가"}

    if (ret5 is not None and ret5 >= 15) or (atr_pct is not None and atr_pct >= 10):
        state = "추격 금지"
        trigger = zone_low = zone_high = invalidation = target = None
    elif from_high is not None and from_high >= -2.0 and (metrics.get("volume_ratio") or 0) >= 1.3:
        state = "돌파 확인"
        trigger = current * 1.002
        invalidation = current - max((atr or current * .03) * 2, current * .03)
        zone_low, zone_high = trigger, trigger * 1.007
        target = trigger + 2 * (trigger - invalidation)
    elif sma20 and metrics.get("sma50") and current > metrics["sma50"] and abs(current / sma20 - 1) <= .035:
        state = "눌림목 대기"
        trigger = max(current, sma20 * 1.005)
        invalidation = current - max((atr or current * .03) * 2, current * .03)
        zone_low, zone_high = trigger, trigger * 1.007
        target = trigger + 2 * (trigger - invalidation)
    elif score >= 75:
        state = "관찰"
        trigger = zone_low = zone_high = invalidation = target = None
    else:
        state = "제외"
        trigger = zone_low = zone_high = invalidation = target = None

    gates_ok = market_score >= 50 and theme_score >= 70 and score >= 75
    recommendation = "조건부 후보" if gates_ok and state in {"돌파 확인", "눌림목 대기"} else "관찰" if state not in {"추격 금지", "제외"} else "추천 제외"
    if market_score < 50:
        buy_reason = "시장 국면이 방어 우선이라 신규 매수를 보류합니다."
    elif theme_score < 70:
        buy_reason = "테마 강도가 기준 미달이라 종목 점수가 높아도 매수하지 않습니다."
    elif score < 75:
        buy_reason = "대장주 품질 점수가 기준 미달입니다."
    elif state == "돌파 확인":
        buy_reason = "52주 신고가 부근에서 거래량이 증가해 종가 돌파 확인 후 진입합니다."
    elif state == "눌림목 대기":
        buy_reason = "상승 추세 안의 20일선 눌림으로 기준가 회복 후에만 진입합니다."
    elif state == "추격 금지":
        buy_reason = "단기 급등 또는 변동성 과열로 추격 매수를 금지합니다."
    else:
        buy_reason = "가격 셋업이 완성되지 않아 관찰합니다."
    return {
        "state": state,
        "recommendation": recommendation,
        "trigger": trigger,
        "zone_low": zone_low,
        "zone_high": zone_high,
        "invalidation": invalidation,
        "target": target,
        "buy_reason": buy_reason,
    }


def _intraday_chart_payload(frame: pd.DataFrame | None, prev_close: float | None) -> dict | None:
    """당일 1분봉 흐름 차트 자료. 자비스1 코스피/코스닥 당일 차트와 같은 성격이다.

    이미 받아 둔 1일 1분봉(live) 프레임을 재사용하므로 추가 네트워크 호출이 없다.
    차트 x축이 뉴욕 거래시간으로 보이도록 시각을 뉴욕 기준 naive로 바꾼다.
    """
    if frame is None or frame.empty or "Close" not in frame.columns:
        return None
    closes = frame["Close"].dropna().astype(float)
    if len(closes) < 5:
        return None
    price = closes.to_frame(name="Close")
    try:
        index = pd.DatetimeIndex(price.index)
        if index.tz is not None:
            price.index = index.tz_convert(_NY).tz_localize(None)
    except Exception:
        pass
    return {
        "ok": True,
        "price": price,
        "prev_close": _finite(prev_close),
        "source_time": _source_time(frame),
    }


TOP_REVIEW_LIMIT = 7

# 지금 시세로 다시 재 볼 후보 수. 종가 순위 30위 밖에서 최종 7위 안으로 들어오려면
# 하루 만에 스물몇 계단을 올라와야 한다(2026-07-31 실측: 그날 진짜 상위 7은 종가
# 순위에서도 1~7위였다). 157종목 전부 분봉을 받으면 3.7초, 종가만이면 0.3초였다.
TOP_REVIEW_REFINE = 30


def _refine_top_with_live(rows, *, market_score: float) -> None:
    """상위 후보만 지금 시세(분봉)로 다시 점수를 낸다. 실패하면 종가 점수 그대로 둔다."""
    tickers = [str(r.get("ticker") or "").upper() for r in rows if r.get("ticker")]
    if not tickers:
        return
    try:
        live, meta = _download_cached(
            tickers, period="1d", interval="1m", ttl_seconds=45, prepost=True
        )
        daily, _ = _download_cached(tickers, period="1y", interval="1d", ttl_seconds=300)
    except Exception as exc:
        _log.warning("jarvis3 top7 refine failed: %s", exc)
        return
    if not live:
        return
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        frame = live.get(ticker)
        if frame is None or frame.empty:
            continue
        metrics = _series_metrics(daily.get(ticker), frame)
        if not metrics.get("ok"):
            continue
        row["metrics"] = metrics
        # 눌림목에서 온 줄은 점수 계산식이 다르다(눌림 점수). 그건 건드리지 않는다.
        if "pullback" in row:
            continue
        row["score"], row["score_parts"] = _leader_score(metrics, row.get("theme_ret20"))
        row["plan"] = _entry_plan(
            metrics, row["score"], market_score, float(row.get("theme_score") or 0)
        )


def _cache_is_warm(tickers, *, period: str, interval: str, ttl_seconds: float,
                   prepost: bool = False) -> bool:
    """이 티커 묶음을 덮는 캐시가 이미 있는지. 있으면 프레임을 복사하지 않는다."""
    requested = {str(t).strip().upper() for t in tickers if str(t).strip()}
    if not requested:
        return True
    now = time.time()
    with _CACHE_LOCK:
        for cached_key, candidate in _CACHE.items():
            if not isinstance(cached_key, tuple) or len(cached_key) != 4:
                continue
            cached_tickers, cached_period, cached_interval, cached_prepost = cached_key
            if (
                cached_period == period
                and cached_interval == interval
                and bool(cached_prepost) == bool(prepost)
                and requested.issubset(set(cached_tickers))
                and now - candidate["at"] < ttl_seconds
            ):
                return True
    return False


def _prefetch_leader_quotes(theme_rows) -> None:
    """순위 7이 볼 테마 전체의 시세를 **한 번에** 받아 둔다 (2026-07-30).

    이걸 안 하면 테마마다 자기 1분봉을 따로 받는다. 테마 순위는 1분봉을 ETF만
    받아 두기 때문에 종목 1분봉은 캐시에 없고, 20개 테마가 각자 내려받는다.
    게다가 다운로드는 _DOWNLOAD_LOCK 하나로 묶여 있어 스레드를 4개 띄워도 동시에
    받지 못하고 20번을 줄줄이 기다린다 — 이것이 '클릭하면 느리다'의 몸통이다.
    여기서 한 묶음으로 받아 두면 각 테마는 _download_cached의 묶음 재사용 경로를 탄다.
    """
    tickers: list[str] = []
    for row in theme_rows or []:
        theme = THEME_BY_NAME.get(str(row.get("name") or ""))
        if theme is None:
            continue
        tickers.extend((theme["etf"], theme["alt_etf"], *theme["stocks"]))
    unique = list(dict.fromkeys(tickers))
    if not unique:
        return
    # 실패해도 그냥 넘어간다 — 각 테마가 예전처럼 자기 몫을 받으면 되므로
    # 여기서 막히면 느려지기만 하고 결과는 같다.
    try:
        if not _cache_is_warm(unique, period="1y", interval="1d", ttl_seconds=300):
            _download_cached(unique, period="1y", interval="1d", ttl_seconds=300)
    except Exception as exc:
        _log.warning("jarvis3 top7 prefetch failed: %s", exc)


def _keep_better(picked: dict, row: dict, *, source: str) -> None:
    """같은 종목이 여러 테마에 겹치면 점수가 높은 쪽만 남긴다."""
    ticker = str(row.get("ticker") or "").strip().upper()
    if not ticker:
        return
    kept = picked.get(ticker)
    if kept is not None:
        kept.setdefault("sources", [])
        if source and source not in kept["sources"]:
            kept["sources"].append(source)
        if float(row.get("score") or 0) <= float(kept.get("score") or 0):
            return
        row = dict(row)
        row["sources"] = kept["sources"]
    else:
        row = dict(row)
        row["sources"] = [source] if source else []
    picked[ticker] = row


def find_top_reviewed_stocks(
    theme_rows,
    *,
    market_score: float = 0,
    extra_rows=None,
    limit: int = TOP_REVIEW_LIMIT,
) -> dict:
    """'매수 심사 결과' 종목 조건점수 상위 N개 (2026-07-30 사용자 지시).

    자비스4(한국)의 같은 이름 함수와 짝이다. 전수 검색을 새로 돌리지 않고,
    **이미 화면에 떠 있는 테마의 대장주**와 **이미 돌려 둔 눌림목 결과**만 모아
    종목 조건점수 하나로 줄 세운다.
    """
    picked: dict[str, dict] = {}
    errors: list[str] = []
    scanned_themes = 0
    theme_scores = {
        str(row.get("name") or ""): float(row.get("score") or 0)
        for row in (theme_rows or [])
    }

    # 테마를 하나씩 돌면 20개에 한참 걸린다(2026-07-30 사용자 지적: 로딩이 너무 길다).
    # 테마끼리는 서로를 안 기다리므로 한꺼번에 돌린다.
    def _one(theme_row):
        # 예외는 여기서 잡아 테마 이름과 함께 돌려준다 — 밖에서 잡으면 어느 테마가
        # 실패했는지 알 수 없다.
        name = str(theme_row.get("name") or "")
        try:
            return name, get_theme_leaders(
                name,
                market_score=market_score,
                theme_score=float(theme_row.get("score") or 0),
                # 표만 그리므로 차트 자료는 만들지 않는다 — 만들면 157종목치가 다 버려진다.
                with_charts=False,
                # 1차는 종가로만 줄 세운다. 157종목 분봉을 받는 데 시간 대부분이 갔다.
                with_live=False,
            )
        except Exception as exc:
            return name, {"ok": False, "error": str(exc), "rows": []}

    themes = list(theme_rows or [])
    if themes:
        _prefetch_leader_quotes(themes)
        with ThreadPoolExecutor(max_workers=4) as executor:
            for future in [executor.submit(_one, row) for row in themes]:
                name, result = future.result()
                if not result.get("ok"):
                    errors.append(f"{name}: {result.get('error') or '조회 실패'}")
                    continue
                scanned_themes += 1
                for row in result["rows"]:
                    _keep_better(picked, row, source=name)

    for row in extra_rows or []:
        if not row.get("metrics"):
            continue
        # 눌림목 결과는 게이트를 열어 둔 채 계산돼 있다 — 오늘 시장 점수로 다시 판정한다.
        themes = row.get("themes") or []
        theme_score = max((theme_scores.get(str(t), 0.0) for t in themes), default=0.0)
        merged = dict(row)
        merged["plan"] = _entry_plan(
            row["metrics"], float(row.get("score") or 0), market_score, theme_score
        )
        _keep_better(picked, merged, source=(str(themes[0]) if themes else "눌림목"))

    ranked = sorted(
        picked.values(), key=lambda item: float(item.get("score") or 0), reverse=True
    )
    # 여기까지는 종가로만 줄 세운 것이다. 상위 후보 몇 개만 지금 시세로 다시 재고
    # 그 안에서 최종 순위를 낸다 — 157종목 전부 분봉을 받던 것을 없앤다.
    _refine_top_with_live(ranked[:TOP_REVIEW_REFINE], market_score=market_score)
    rows = sorted(
        ranked[:TOP_REVIEW_REFINE], key=lambda item: float(item.get("score") or 0), reverse=True
    )[: max(1, int(limit))]
    for index, row in enumerate(rows, 1):
        row["pick_rank"] = index

    return {
        "ok": bool(rows),
        "rows": rows,
        "scanned_themes": scanned_themes,
        "candidate_count": len(picked),
        "errors": errors,
        "checked_at": datetime.now(_NY).isoformat(timespec="seconds"),
    }


def get_theme_leaders(theme_name: str, market_score: float = 0, theme_score: float = 0,
                      with_charts: bool = True, with_live: bool = True) -> dict:
    """선택한 테마의 대장주 순위.

    with_charts — 분봉·일봉·주봉 차트 자료를 함께 담을지. 테마 하나를 열어 볼 때는
    옆에 차트를 그리니 담아야 하지만, '매수심사결과 높은 순위 7'은 테마 20개를
    한꺼번에 돌면서 표만 그린다. 그때 157종목 차트를 만들면 전부 버려진다
    (2026-07-30 실측: 차트 만들기만 노트북 CPU 0.7초, 온라인은 코어가 적어 더 걸린다).
    """
    theme = THEME_BY_NAME.get(theme_name)
    if theme is None:
        return {"ok": False, "error": "등록되지 않은 테마입니다", "rows": []}
    tickers = (theme["etf"], theme["alt_etf"], *theme["stocks"])
    daily, daily_meta = _download_cached(tickers, period="1y", interval="1d", ttl_seconds=300)
    # with_live=False면 분봉을 아예 안 받는다. 순위 7이 1차로 줄만 세울 때 쓴다 —
    # 157종목 분봉을 받는 데 시간 대부분이 갔다(2026-07-31 실측 3.7초 → 0.3초).
    if with_live:
        live, live_meta = _download_cached(
            tickers, period="1d", interval="1m", ttl_seconds=45, prepost=True)
    else:
        live, live_meta = {}, {}
    etf_used = theme["etf"] if theme["etf"] in daily else theme["alt_etf"]
    theme_metrics = _series_metrics(daily.get(etf_used), live.get(etf_used))
    theme_ret20 = theme_metrics.get("ret20") if theme_metrics.get("ok") else None
    rows = []
    for ticker in theme["stocks"]:
        metrics = _series_metrics(daily.get(ticker), live.get(ticker))
        if not metrics.get("ok"):
            continue
        score, parts = _leader_score(metrics, theme_ret20)
        plan = _entry_plan(metrics, score, market_score, theme_score)
        daily_frame = daily.get(ticker)
        daily_chart = None
        weekly_chart = None
        if with_charts and daily_frame is not None and not daily_frame.empty:
            # 대장주 비교 차트도 종목 상세와 같은 형식(주가·20일선·50일선)으로 만든다.
            daily_chart = _prepare_chart_payload(daily_frame, None, 60, daily_meta)
            weekly_chart = _prepare_chart_payload(daily_frame, "W-FRI", 52, daily_meta)
        rows.append({
            "ticker": ticker,
            "name": STOCK_NAMES.get(ticker, ticker),
            "score": score,
            "score_parts": parts,
            # 이 두 값이 있어야 나중에 이 종목만 따로 다시 점수를 낼 수 있다
            # (순위 7이 상위 후보만 분봉을 받아 다시 재는 데 쓴다).
            "theme_ret20": theme_ret20,
            "theme_score": theme_score,
            "metrics": metrics,
            "plan": plan,
            "intraday_chart": (
                _intraday_chart_payload(live.get(ticker), metrics.get("prev_close"))
                if with_charts else None
            ),
            "daily_chart": daily_chart,
            "weekly_chart": weekly_chart,
        })
    rows.sort(key=lambda row: row["score"], reverse=True)
    for index, row in enumerate(rows, 1):
        row["rank"] = index
        from_high = row["metrics"].get("from_high_pct")
        row["stock_reason"] = (
            f"테마 내 종합 {index}위 · 52주 고가 대비 {from_high:.1f}% · "
            f"20일 수익률 {row['metrics']['ret20']:+.1f}%"
            if from_high is not None else f"테마 내 종합 {index}위"
        )
    return {
        "ok": bool(rows),
        "rows": rows,
        "etf": etf_used,
        "checked_at": live_meta.get("fetched_at") or daily_meta.get("fetched_at"),
        "stale": bool(daily_meta.get("stale") or live_meta.get("stale")),
        "error": None if rows else (live_meta.get("error") or daily_meta.get("error") or "종목 시세 조회 실패"),
    }


# 미국 종목은 티커·회사명이 영어다. 그래도 한글로 칠 수 있어야 한다
# (2026-07-29 사용자 질문 "이거 영어로만 쳐야겠지?"). 널리 쓰는 한글 이름을
# 티커로 이어 준다. 여기 없는 종목은 영어로 치면 된다.
KOREAN_TICKER_ALIASES = {
    "엔비디아": "NVDA", "애플": "AAPL", "테슬라": "TSLA", "구글": "GOOGL",
    "알파벳": "GOOGL", "아마존": "AMZN", "마이크로소프트": "MSFT", "마소": "MSFT",
    "메타": "META", "페이스북": "META", "넷플릭스": "NFLX", "브로드컴": "AVGO",
    "인텔": "INTC", "마이크론": "MU", "퀄컴": "QCOM", "티에스엠씨": "TSM",
    "티에스엠시": "TSM", "타이완반도체": "TSM", "팔란티어": "PLTR",
    "오라클": "ORCL", "델": "DELL", "아리스타": "ANET", "버티브": "VRT",
    "코인베이스": "COIN", "로빈후드": "HOOD", "페이팔": "PYPL",
    "마이크로스트래티지": "MSTR", "스트래티지": "MSTR",
    "일라이릴리": "LLY", "릴리": "LLY", "존슨앤존슨": "JNJ", "화이자": "PFE",
    "머크": "MRK", "모더나": "MRNA", "버크셔": "BRK-B", "코스트코": "COST",
    "월마트": "WMT", "스타벅스": "SBUX", "맥도날드": "MCD", "나이키": "NKE",
    "보잉": "BA", "록히드마틴": "LMT", "레이시온": "RTX", "캐터필러": "CAT",
    "엑슨": "XOM", "엑슨모빌": "XOM", "셰브론": "CVX", "쉐브론": "CVX",
    "비자": "V", "마스터카드": "MA", "제이피모건": "JPM", "골드만삭스": "GS",
    "디즈니": "DIS", "우버": "UBER", "에어비앤비": "ABNB", "슈퍼마이크로": "SMCI",
    "암": "ARM", "에이엠디": "AMD", "이비아이디": "EBAY",
}


def _us_listing() -> list[tuple[str, str, str]]:
    """미국 상장 종목 (티커, 이름, 시장) 전체. 하루 한 번만 받아 캐시에 둔다."""
    def _produce():
        import FinanceDataReader as fdr

        out, seen = [], set()
        for market in ("NASDAQ", "NYSE", "AMEX"):
            try:
                frame = fdr.StockListing(market)
            except Exception:
                continue
            for _, row in frame.iterrows():
                symbol = str(row.get("Symbol") or "").strip().upper()
                name = str(row.get("Name") or "").strip()
                if not symbol or symbol in seen:
                    continue
                seen.add(symbol)
                out.append((symbol, name or symbol, market))
        if not out:
            raise RuntimeError("미국 상장 종목 목록이 비었습니다")
        return out

    listing, _stale = _cached_value("us_listing", 6 * 3600, _produce)
    return listing


def search_stocks(query: str, *, limit: int = 12) -> dict:
    """티커나 회사 이름으로 미국 종목을 찾는다. 한글 이름과 오타도 받아 준다."""
    text = str(query or "").strip()
    if not text:
        return {"ok": True, "rows": []}
    try:
        listing = _us_listing()
    except Exception as exc:
        return {"ok": False, "error": str(exc), "rows": []}

    by_symbol = {item[0]: item for item in listing}
    picked, seen = [], set()

    def _add(item):
        if item and item[0] not in seen:
            seen.add(item[0])
            picked.append(item)

    # 1) 한글 이름으로 바로 찾기
    korean = KOREAN_TICKER_ALIASES.get(text.replace(" ", ""))
    if korean:
        _add(by_symbol.get(korean) or (korean, STOCK_NAMES.get(korean, korean), "US"))

    upper = text.upper().replace(" ", "")
    lowered = text.lower().replace(" ", "")

    def _key(name):
        return str(name).lower().replace(" ", "")

    # 2) 티커 일치 → 티커 시작 → 이름 시작 → 이름 포함
    _add(by_symbol.get(upper))
    for item in listing:
        if item[0].startswith(upper):
            _add(item)
    for item in listing:
        if _key(item[1]).startswith(lowered):
            _add(item)
    for item in listing:
        if lowered in _key(item[1]):
            _add(item)

    # 3) 그래도 모자라면 오타까지 받아 준다
    if len(picked) < limit:
        import difflib

        names = [_key(item[1]) for item in listing]
        for target in difflib.get_close_matches(lowered, names, n=limit, cutoff=0.7):
            for item in listing:
                if _key(item[1]) == target:
                    _add(item)

    return {"ok": True, "rows": [
        {"ticker": t, "name": n, "market": m} for t, n, m in picked[:limit]
    ]}


def analyze_one_stock(ticker: str, *, market_score: float = 0,
                      theme_score: float = 0) -> dict:
    """종목 하나만 대장주와 똑같은 방식으로 심사한다.

    테마 안에서 재는 상대강도(theme_ret20)는 비교할 테마가 없으므로 뺀다 —
    그 항목은 0점이 되고, 그래서 점수를 테마 대장주 점수와 나란히 견주면 안 된다.
    """
    ticker = str(ticker or "").strip().upper()
    if not ticker:
        return {"ok": False, "error": "티커가 비었습니다"}
    daily, daily_meta = _download_cached((ticker,), period="1y", interval="1d", ttl_seconds=300)
    live, _live_meta = _download_cached(
        (ticker,), period="1d", interval="1m", ttl_seconds=45, prepost=True)
    metrics = _series_metrics(daily.get(ticker), live.get(ticker))
    if not metrics.get("ok"):
        return {"ok": False,
                "error": daily_meta.get("error") or f"{ticker} 시세를 가져오지 못했습니다"}
    score, parts = _leader_score(metrics, None)
    frame = daily.get(ticker)
    row = {
        "ticker": ticker,
        "name": STOCK_NAMES.get(ticker, ticker),
        "score": score,
        "score_parts": parts,
        "metrics": metrics,
        "plan": _entry_plan(metrics, score, market_score, theme_score),
        "intraday_chart": _intraday_chart_payload(live.get(ticker), metrics.get("prev_close")),
        "daily_chart": (_prepare_chart_payload(frame, None, 60, daily_meta)
                        if frame is not None and not frame.empty else None),
        "weekly_chart": (_prepare_chart_payload(frame, "W-FRI", 52, daily_meta)
                         if frame is not None and not frame.empty else None),
        "rank": 0,
        "from_search": True,
    }
    from_high = metrics.get("from_high_pct")
    row["stock_reason"] = (
        f"직접 찾은 종목 · 52주 고가 대비 {from_high:.1f}%"
        if from_high is not None else "직접 찾은 종목"
    )
    return {"ok": True, "row": row}


def get_live_quote(ticker: str) -> dict:
    ticker = str(ticker).strip().upper()
    daily, daily_meta = _download_cached((ticker,), period="1y", interval="1d", ttl_seconds=300)
    live, live_meta = _download_cached((ticker,), period="1d", interval="1m", ttl_seconds=45, prepost=True)
    metrics = _series_metrics(daily.get(ticker), live.get(ticker))
    if not metrics.get("ok"):
        return {"ok": False, "error": live_meta.get("error") or daily_meta.get("error") or "시세 조회 실패"}
    return {
        "ok": True,
        **metrics,
        "ticker": ticker,
        "stale": bool(daily_meta.get("stale") or live_meta.get("stale")),
    }


def get_intraday_chart(ticker: str) -> dict | None:
    """아무 종목의 당일 1분봉 차트 자료. 눌림목 상세에서 쓴다(2026-07-25 추가).

    테마 대장주는 목록을 만들 때 intraday_chart를 함께 담지만, 눌림목 종목은
    고른 뒤에야 알 수 있어 그때 한 종목만 따로 불러온다.
    """
    ticker = str(ticker).strip().upper()
    daily, _ = _download_cached((ticker,), period="1y", interval="1d", ttl_seconds=300)
    live, _ = _download_cached((ticker,), period="1d", interval="1m", ttl_seconds=45, prepost=True)
    metrics = _series_metrics(daily.get(ticker), live.get(ticker))
    return _intraday_chart_payload(live.get(ticker), metrics.get("prev_close"))



def get_index_sparklines(days: int = 30) -> dict:
    """4대 지수의 '당일 분봉 흐름'과 '전일 종가'.

    네이버 금융처럼 그리려면 30일 일봉이 아니라 마지막 장의 분봉이어야 하고,
    기준선은 전일 종가여야 한다(2026-07-25 사용자 지적 — 이전 구현이 틀렸다).
    분봉을 못 받으면 그 지수는 빼고 숫자만 보여준다.
    """
    try:
        intraday, _m1 = _download_cached(
            US_INDEX_SYMBOLS, period="1d", interval="5m", ttl_seconds=300)
        daily, _m2 = _download_cached(
            US_INDEX_SYMBOLS, period="1mo", interval="1d", ttl_seconds=600)
    except Exception:
        return {}
    result = {}
    for symbol in US_INDEX_SYMBOLS:
        frame = intraday.get(symbol)
        closes = daily.get(symbol)
        if frame is None or frame.empty or closes is None or len(closes) < 2:
            continue
        points = [float(v) for v in frame["Close"].dropna().tolist()]
        base = _prior_session_close(closes, pd.Timestamp(frame.index[-1]).date())
        if len(points) >= 2 and base:
            result[symbol] = {"points": points, "base": base}
    return result


def _prior_session_close(daily: pd.DataFrame, session_day) -> float | None:
    """분봉이 그리는 그 날 '앞' 세션의 종가 — 그림의 기준선이자 등락률의 분모다.

    2026-07-25 실측 사고: iloc[-2]로 잡았더니 야후 일봉에 금요일 줄이 아직 안 올라온
    사이에 기준선이 하루 더 옛날(수요일) 종가가 됐다. 그래서 S&P가 실제로는 +0.06%인데
    화면에 -1.15%로 뜨고, 그림은 선 전체가 기준선 아래로 내려가 통째로 빨갛게 나왔다.
    일봉의 몇 번째 줄인지가 아니라 '분봉 날짜보다 앞선 마지막 종가'로 잡아야 한다.
    """
    try:
        closes = daily["Close"].dropna()
    except Exception:
        return None
    prior = [v for stamp, v in closes.items() if pd.Timestamp(stamp).date() < session_day]
    return _finite(prior[-1]) if prior else None


def _prepare_chart_payload(frame: pd.DataFrame, resample_rule: str | None, limit: int, meta: dict) -> dict:
    chart = frame.copy()
    if resample_rule:
        aggregations = {"Close": "last"}
        if "Open" in chart.columns:
            aggregations["Open"] = "first"
        if "High" in chart.columns:
            aggregations["High"] = "max"
        if "Low" in chart.columns:
            aggregations["Low"] = "min"
        if "Volume" in chart.columns:
            aggregations["Volume"] = "sum"
        chart = chart.resample(resample_rule).agg(aggregations).dropna(subset=["Close"])
    chart["MA20"] = chart["Close"].rolling(20).mean()
    chart["MA50"] = chart["Close"].rolling(50).mean()
    chart = chart.tail(limit)
    return {
        "ok": True,
        "price": chart[["Close", "MA20", "MA50"]].copy(),
        "volume": chart[["Volume"]].copy() if "Volume" in chart.columns else None,
        "ohlcv": chart.copy(),
        "stale": bool(meta.get("stale")),
        "error": meta.get("error") if meta.get("stale") else None,
    }


def get_chart_data(ticker: str, timeframe: str) -> dict:
    ticker = str(ticker).strip().upper()
    configs = {
        "일봉": ("1y", "1d", None, 180),
        "주봉": ("5y", "1d", "W-FRI", 156),
        "월봉": ("10y", "1d", "ME", 120),
    }
    if timeframe not in configs:
        return {"ok": False, "error": "지원하지 않는 차트 주기입니다"}
    period, interval, resample_rule, limit = configs[timeframe]
    frames, meta = _download_cached((ticker,), period=period, interval=interval, ttl_seconds=300)
    frame = frames.get(ticker)
    if frame is None or frame.empty:
        return {"ok": False, "error": meta.get("error") or "차트 자료가 없습니다"}
    return _prepare_chart_payload(frame, resample_rule, limit, meta)


def analyze_pullback_stock(
    row: dict,
    *,
    benchmark_ret20: float | None = None,
    market_score: float = 0.0,
    theme_score: float = 0.0,
) -> dict:
    """눌림목 표에서 고른 종목을 대장주와 같은 기준으로 다시 심사한다.

    눌림목 검색은 테마를 가로질러 돌기 때문에 테마 ETF 상대강도를 쓸 수 없다.
    한국 자비스4가 KOSPI 20일 수익률을 기준으로 쓰듯, 여기서는 SPY 20일 수익률을
    상대강도 기준으로 넘겨 받는다(넘기지 않으면 상대강도 25점이 통째로 0이 된다).
    """
    metrics = row.get("metrics") or {}
    # 종목 20일 수익률이 없으면 상대강도를 계산할 수 없다 — 기준값을 그대로 넘기면
    # None 뺄셈으로 죽으므로 이때는 기준 없음(상대강도 0점)으로 내린다.
    if metrics.get("ret20") is None:
        benchmark_ret20 = None
    score, parts = _leader_score(metrics, benchmark_ret20)
    plan = _entry_plan(metrics, score, float(market_score or 0), float(theme_score or 0))
    from_high = metrics.get("from_high_pct")
    ret20 = metrics.get("ret20")
    reason = f"눌림목 순위 {row.get('pullback_rank', '—')}위"
    if from_high is not None:
        reason += f" · 52주 고가 대비 {from_high:.1f}%"
    if ret20 is not None:
        reason += f" · 20일 수익률 {ret20:+.1f}%"
    return {
        "ok": bool(metrics.get("ok")),
        "score": score,
        "score_parts": parts,
        "plan": plan,
        "stock_reason": reason,
        "benchmark_ret20": benchmark_ret20,
    }


def get_chart_bundle(ticker: str) -> dict:
    """일봉·주봉·월봉 차트를 한 번의 조회로 함께 만든다.

    10년치로는 월봉 120개를 그릴 때 50개월선의 앞 49개월이 비어 선이 토막났다
    (2026-07-29 실측: NVDA 월봉 120개 중 50선 72개). 상장 이후 전체를 받아
    이평선을 채운다. 상장한 지 얼마 안 된 종목은 자료 자체가 없어 여전히 짧다 —
    그건 지어낼 수 없다.
    """
    ticker = str(ticker).strip().upper()
    frames, meta = _download_cached((ticker,), period="max", interval="1d", ttl_seconds=300)
    frame = frames.get(ticker)
    if frame is None or frame.empty:
        return {"ok": False, "error": meta.get("error") or "차트 자료가 없습니다", "charts": {}}
    charts = {
        "일봉": _prepare_chart_payload(frame, None, 180, meta),
        "주봉": _prepare_chart_payload(frame, "W-FRI", 156, meta),
        "월봉": _prepare_chart_payload(frame, "ME", 120, meta),
    }
    return {
        "ok": True,
        "charts": charts,
        "stale": bool(meta.get("stale")),
        "error": meta.get("error") if meta.get("stale") else None,
    }
