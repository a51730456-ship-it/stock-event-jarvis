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

MARKET_SYMBOLS = ("SPY", "QQQ", "IWM", "DIA", "^VIX")

# 실행 중인 프로세스에 옛 모듈이 남아 있는지 화면이 스스로 알아채기 위한 표식이다
# (자비스4와 같은 장치). 계산 결과나 반환 키를 바꾸면 이 숫자를 올린다.
MODULE_REVISION = 20260724

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
    }


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


def get_market_overview() -> dict:
    daily, daily_meta = _download_cached(
        MARKET_SYMBOLS, period="1y", interval="1d", ttl_seconds=300
    )
    intraday, live_meta = _download_cached(
        MARKET_SYMBOLS, period="1d", interval="1m", ttl_seconds=45, prepost=True
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
        score_breakdown.append({
            "label": label,
            "earned": earned,
            "max": points,
            "state": "충족" if passed else "미충족",
        })

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
    score_breakdown.append({
        "label": "VIX 위험수준",
        "earned": vix_earned,
        "max": 15,
        "state": vix_state,
    })

    if score >= 75:
        regime, posture = "상승 우위", "조건 충족 종목만 매수 심사"
    elif score >= 50:
        regime, posture = "중립·선별", "비중 축소·확인 후 진입"
    else:
        regime, posture = "방어 우선", "신규 매수 보류"

    source_times = [row.get("source_time") for row in rows.values() if row.get("source_time")]
    return {
        "ok": True,
        "score": score,
        "regime": regime,
        "posture": posture,
        "reasons": reasons,
        "score_breakdown": score_breakdown,
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
    min_score: float = 60.0,
    result_limit: int = 20,
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


def get_theme_leaders(theme_name: str, market_score: float = 0, theme_score: float = 0) -> dict:
    theme = THEME_BY_NAME.get(theme_name)
    if theme is None:
        return {"ok": False, "error": "등록되지 않은 테마입니다", "rows": []}
    tickers = (theme["etf"], theme["alt_etf"], *theme["stocks"])
    daily, daily_meta = _download_cached(tickers, period="1y", interval="1d", ttl_seconds=300)
    live, live_meta = _download_cached(tickers, period="1d", interval="1m", ttl_seconds=45, prepost=True)
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
        if daily_frame is not None and not daily_frame.empty:
            # 대장주 비교 차트도 종목 상세와 같은 형식(주가·20일선·50일선)으로 만든다.
            daily_chart = _prepare_chart_payload(daily_frame, None, 60, daily_meta)
            weekly_chart = _prepare_chart_payload(daily_frame, "W-FRI", 52, daily_meta)
        rows.append({
            "ticker": ticker,
            "name": STOCK_NAMES.get(ticker, ticker),
            "score": score,
            "score_parts": parts,
            "metrics": metrics,
            "plan": plan,
            "intraday_chart": _intraday_chart_payload(live.get(ticker), metrics.get("prev_close")),
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
    """한 번의 10년 일봉 조회로 일봉·주봉·월봉 차트를 함께 만든다."""
    ticker = str(ticker).strip().upper()
    frames, meta = _download_cached((ticker,), period="10y", interval="1d", ttl_seconds=300)
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
