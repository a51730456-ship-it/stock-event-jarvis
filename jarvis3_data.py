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

# ── 설명서가 말하는 두 갈래를 찾을 종목 범위 (2026-08-01 사용자 지시) ──────────
# '미국장 눌림목 매매 설명서'의 검증은 미국 대형주 200개로 한 것이라, 테마 종목
# 137개만 훑으면 설명서와 범위가 다르다. 그래서 널리 거래되는 대형주를 더해
# 200개 안팎으로 넓힌다. 테마 종목을 **전부 포함하는 묶음**이라 야후를 한 번만
# 부르면 테마 검색도 이 묶음을 잘라 쓴다(_download_cached의 부분집합 재사용).
# 자료를 못 받는 티커는 조용히 빠지고, 화면에 '일봉 확보 n개'로 실제 수를 적는다.
_US_LARGE_CAP_EXTRA = (
    "BRK-B", "JPM", "V", "MA", "UNH", "JNJ", "PG", "HD", "MRK", "PEP",
    "KO", "ABBV", "COST", "WMT", "BAC", "CRM", "MCD", "TMO", "ACN", "ABT",
    "LIN", "DHR", "VZ", "TXN", "NKE", "PM", "WFC", "DIS", "MS", "NEE",
    "UPS", "INTU", "LOW", "GS", "SPGI", "BLK", "AXP", "BKNG", "SYK", "DE",
    "T", "PLD", "GILD", "TJX", "MDT", "ADP", "MDLZ", "CI", "CVS", "C",
    "SO", "SCHW", "BSX", "CB", "ORCL", "ADBE", "SBUX", "UBER", "NOW", "LLY",
    "PFE", "BMY", "ABNB", "ELV", "AON", "ZTS", "DUK", "ITW", "PGR", "EOG",
    "APD",
)
US_LARGE_CAP_UNIVERSE = tuple(dict.fromkeys(
    [ticker for theme in US_THEMES for ticker in theme["stocks"]] + list(_US_LARGE_CAP_EXTRA)
))

# 화면이 찾는 숫자를 여기 한 곳에 둔다. 설명 창의 표 그림(assets/us_method_*.png)과
# 이 값이 어긋나면 화면이 설명과 다른 것을 찾게 되므로 같이 고친다.
# 표 숫자 원본: docs/US_METHOD_TABLES.md · 재는 방법: docs/REMEASURE_20260805.md
#
# 2026-08-06에 10년치 재측정 결과로 바꿨다(사용자 결정).
# 그전 값(3~5일 · 4~6% · 승률 59.7%(119건))은 사용자가 2026-08-01에 준 설명서였는데,
# 표본이 119건이었고 다시 재니 앞 5년 -0.2%p · 뒤 5년 -3.8%p로 **양쪽 다 아무 종목이나
# 산 것보다 못했다.** 10~15%만 앞뒤 양쪽에서 이겼다(+8.0 / +1.4%p).
# 찾는 그물은 **넓게**, 순위는 **별점으로** 매긴다(2026-08-06 사용자 결정).
#
# 왜 이렇게 바꿨나 — 재측정 결과(1~5일 · 10~15%)를 그대로 거르는 조건으로 썼더니
# 화면이 매일 비었다. 신고가 뒤 5일 안에 10% 넘게 빠지는 일은 1년에 30번뿐이라
# (96종목 전체에서) 여드레에 한 번쯤 한 종목 나오는 정도다. 그래서 사용자가
# "넓게 찾고 좋은 자리에 별을 달아라. 고르는 것은 내가 한다"고 정했다.
BREAKOUT_PULLBACK_RULE = {
    "wait_days": (1, 5),         # 52주 신고가 뒤 며칠까지 볼까 (그물)
    "drop_band": (-15.0, -4.0),  # 눌린 폭 (그물 — 옛 기준 4~6%도 품는다)
    "hold_days": 120,            # 6개월
}

# 순위는 **별점이 아니라 100점 배점**으로 매긴다(2026-08-06 사용자 결정).
#
# 별점을 뺀 이유 — 별점은 '눌린 폭'과 '신고가 뒤 며칠'만 보고 달았는데, 10년을
# 앞 5년·뒤 5년으로 갈라 다시 재니 **둘 다 뒤 5년에서 졌다**.
#   눌림 10~15%   앞 +3.9%p / 뒤 -1.2%p
#   신고가 1~3일 전 앞 +3.2%p / 뒤 -0.5%p
# 한쪽 시기에서만 통하는 값을 순위 맨 앞에 두면, 화면이 그 시기에만 맞는 자리를
# 1등으로 올린다. 그래서 **앞뒤 양쪽에서 다 이긴 값**에 점수를 몰아준다.
# 배점 근거는 BREAKOUT_SCORE_WEIGHTS·CRASH_SCORE_WEIGHTS 위 주석에 적었다.
#
# 기준선 — 테마 명부 198종목 10년치, 상승장으로 판정된 1,755일 · 294,686번.
BREAKOUT_BASE_WIN_RATE = 62.2      # 같은 날 아무 종목이나 샀을 때 100번 중
BREAKOUT_BASE_MEDIAN = 6.3

# 표 1(assets/us_method_uptrend.png)의 숫자를 **잰 날의 조건**이다.
# 거르는 조건이 아니다 — 알려만 준다. 자세한 사연은 breakout_market_state() 참고.
BREAKOUT_MARKET_MAX_DROP = -10.0   # 나스닥 고점 대비 이보다 나은 날

# 급락 후 반등장 — 시장 낙폭은 **막지 않고 알려만 준다**(2026-08-06 사용자 결정).
# -6~-12%가 가장 자주 오고(7개월에 한 번) 가장 좋았지만, 그 자리를 지나 시장이
# 올라가도 종목은 여전히 볼 값어치가 있다는 판단이다.
# **2026-08-07 격자로 다시 잡았다.** -6~-12%는 급락이 아니라 흔한 조정이었다
# (10년에 72번). 그 문턱에서는 어떤 조합도 3년 창 검사를 통과하지 못했다.
# **-10~-20%(49번)** 로 깊게 잡으니 통과했다. 측정: research/us_net_grid.py
CRASH_MARKET_BAND = (-20.0, -10.0)
CRASH_MARKET_SYMBOL = "QQQ"
#
# 성적은 **화면이 실제로 뒤지는 명부(테마 198종목)**로 다시 쟀다(2026-08-06).
# 그전 숫자(74.6 / 69.5, 기준선 65.4)는 나스닥100 96종목으로 잰 것이라 화면이
# 찾는 대상과 달랐다. 다시 재 보니 **낙폭 자체는 기준선을 못 넘는다** — 그래서
# 낙폭에는 15점만 준다(CRASH_SCORE_WEIGHTS 주석 참고).
# **2026-08-07 격자로 다시 잡았다.** 얕은 낙폭을 **1년** 들고 있는 것이 답이었다.
# 깊은 갈래(-30~-50%)와 6개월 보유는 3년 창 검사를 통과하지 못했다.
#   나스닥 -10~-20% 가장 깊은 날 · 종목 -20~-30% · 250거래일
#   창 2년 93/74% · 3년 100/86% · 4년 100/100% · 가운데 +3.5%p · 가장 나쁜 창 +0.8%p
CRASH_REBOUND_RULES = (
    {"key": "shallow", "band": (-30.0, -20.0), "hold_days": 250,
     "win_rate": 81.2, "median_return": 31.1, "base_win_rate": 76.1,
     "base_median_return": 24.2, "sample": 1728, "events": 49,
     "years_better": 5, "years_total": 8, "windows_won": "252/252",
     "label": "고점 대비 -20~-30%"},
)

# 실행 중인 프로세스에 옛 모듈이 남아 있는지 화면이 스스로 알아채기 위한 표식이다
# (자비스4와 같은 장치). 계산 결과나 반환 키를 바꾸면 이 숫자를 올린다.
MODULE_REVISION = 2026080800

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
    volume_vs_prev = None
    volume_vs_week = None
    if "Volume" in daily.columns:
        volumes = daily["Volume"].dropna().astype(float)
        if not volumes.empty:
            avg_volume = _finite(volumes.tail(20).mean())
            latest_volume = _finite(volumes.iloc[-1])
            if avg_volume and latest_volume is not None:
                volume_ratio = latest_volume / avg_volume
                avg_dollar_volume = avg_volume * current
            # 금액(억 달러)만 보면 큰 회사가 늘 크다 — 알 수가 없다는 지적을 받았다
            # (2026-08-06). 그래서 **얼마나 늘었나**를 같이 낸다.
            # 미국은 외국인·기관 수급을 종가 뒤에도 공개하지 않으므로, 돈이 몰리는지
            # 볼 수 있는 값은 거래대금 변화뿐이다.
            if len(volumes) >= 2 and latest_volume is not None:
                prev_volume = _finite(volumes.iloc[-2])
                if prev_volume:
                    volume_vs_prev = (latest_volume / prev_volume - 1) * 100
            if len(volumes) >= 6 and latest_volume is not None:
                week_volume = _finite(volumes.iloc[-6:-1].mean())
                if week_volume:
                    volume_vs_week = (latest_volume / week_volume - 1) * 100

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
        "volume_vs_prev": volume_vs_prev,     # 어제 거래량 대비 %
        "volume_vs_week": volume_vs_week,     # 지난 5거래일 평균 대비 %
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

    # 다섯 칸 — regime_gauge_ui.ZONES와 끊는 자리가 같아야 한다(2026-08-05 지시).
    if score >= 80:
        regime, posture = "상승 여건 양호", "조건 충족 종목만 매수 심사"
    elif score >= 65:
        regime, posture = "상승 신호 우세", "확인된 대장주만 분할 진입"
    elif score >= 50:
        regime, posture = "방향 엇갈림", "비중 축소·확인 후 진입"
    elif score >= 30:
        regime, posture = "약세 신호 우세", "신규 매수 보류"
    else:
        regime, posture = "하락 압력 큼", "신규 매수 보류·손절 관리 먼저"
    return {"ok": True, "score": score, "regime": regime, "posture": posture,
            "reasons": reasons, "score_breakdown": score_breakdown}


def _previous_market_regime(daily: dict, now=None) -> dict | None:
    """직전 완료 미국장의 같은 조건점수. 장중에는 오늘 일봉을 제외한다.

    **날짜가 아니라 '그 장이 끝났는가'로 판단한다**(2026-08-06 사용자 지적으로 고침).
    전에는 뉴욕 날짜만 봐서, 뉴욕 자정(한국 오후 1~2시)에 전일이 하루 밀렸다 —
    한국장 한복판에 전일 국면이 바뀌었다. 실측으로 확인했다:
    한국 07:00~11:00은 8/4를 쓰다가 13:00부터 8/5로 바뀌었다.

    아침 쪽이 틀린 값이었다. 한국 07:00이면 미국장은 이미 마감(뉴욕 18:00)했으므로
    그날 일봉이 완성돼 있고, 그것이 '직전 완료 장'이다. 그래서 마감(뉴욕 16시)이
    지났으면 오늘 일봉을 그대로 쓴다. 이렇게 하면 다음 마감까지 값이 고정된다.
    """
    now_ny = (now or datetime.now(_NY)).astimezone(_NY)
    today_ny = now_ny.date()
    # 정규장 마감(16:00) 뒤면 오늘 일봉은 완성된 것으로 본다.
    session_closed = now_ny.time() >= dt_time(16, 0)
    rows = {}
    used_dates = []
    for ticker in ("SPY", "QQQ", "IWM", "^VIX"):
        frame = daily.get(ticker)
        if frame is None or frame.empty:
            return None
        last_date = pd.Timestamp(frame.index[-1])
        last_date = last_date.tz_convert(_NY).date() if last_date.tzinfo else last_date.date()
        done = last_date < today_ny or (last_date == today_ny and session_closed)
        completed = frame if done else frame.iloc[:-1]
        metrics = _series_metrics(completed)
        if not metrics.get("ok"):
            return None
        rows[ticker] = metrics
        if len(completed):
            tail = pd.Timestamp(completed.index[-1])
            used_dates.append(tail.tz_convert(_NY).date() if tail.tzinfo else tail.date())
    result = _market_regime_from_rows(rows)
    result["as_of"] = "직전 완료 미국장"
    # 어느 거래일을 썼는지 밝힌다 — 값이 언제 바뀌는지 화면·시험에서 확인할 수 있어야
    # 한다(2026-08-06). 종목마다 마지막 날이 다를 수 있어 가장 이른 날을 적는다.
    result["trade_date"] = str(min(used_dates)) if used_dates else None
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


def _universe_daily(reuse_only: bool):
    """설명서 두 갈래가 함께 쓰는 대형주 묶음의 1년 일봉과 소속 테마."""
    memberships: dict[str, list[str]] = {}
    for theme in US_THEMES:
        for ticker in theme["stocks"]:
            memberships.setdefault(ticker, []).append(theme["name"])
    loader = _download_cache_only if reuse_only else _download_cached
    daily, meta = loader(
        US_LARGE_CAP_UNIVERSE, period="1y", interval="1d", ttl_seconds=300
    )
    return daily, meta, memberships


# ── 순위를 정하는 값 (2026-08-01, 실제로 재 보고 정했다) ─────────────────────
# 미국 대형주 198종목 10년치(2016-08~2026-07)로 재 본 결과다. 자세한 것은
# docs/US_RANK_BACKTEST.md.
#
#  1순위 · 같은 테마에서 함께 걸린 종목 수 — **검증됨**. 낙폭 구간에서
#          0~1개 +2.16% / 2개 +1.95% / 3개 +4.22% / 4개 이상 +4.28%(가운데 값),
#          승률도 54.9% → 59.8%. 3개부터 뚜렷하게 갈린다.
#  2순위 · 거래대금이 평소(50일 평균) 위에 며칠 연속인가 — **약하게 있음**.
#          0일 +2.54% / 1~3일 +3.03% / 4~10일 +3.26% / 11일 이상 +4.52%.
#          가운데 값은 순서대로 오르지만 승률은 안 오르고 표본도 866개뿐이라,
#          동점을 가르는 데만 쓰고 앞세우지 않는다.
#  버림  · 거래대금 액수 자체 — 큰 회사가 늘 크다. 순위 기준이 못 된다.
#  버림  · '살아 있는 테마 수' — 0개 +2.08% / 1개 +3.53% / 2개 -3.01%로 뒤집힌다.
THEME_TOGETHER_TIERS = ((4, 3, "4개 이상"), (3, 2, "3개"), (2, 1, "2개"))


def theme_together_tier(count: int) -> tuple[int, str]:
    """같은 테마에서 함께 걸린 종목 수 → (순위 점수, 화면에 적을 말)."""
    for least, points, label in THEME_TOGETHER_TIERS:
        if count >= least:
            return points, label
    return 0, f"{max(int(count), 0)}개"


def theme_together_points(count, points: float) -> float:
    """같은 테마 동반 수 → 배점(2026-08-06 새로 만듦).

    **THEME_TOGETHER_TIERS를 그대로 쓰면 안 된다.** 그 등급은 4개 이상이라야 만점이라
    화면 배점표('3개 이상 만점 · 1~2개 절반')와 어긋났다 — 2026-08-06 상하님 캡처에서
    '1개 함께 걸림 → 0.0(40.0)'으로 드러났다.

    재 본 결과가 갈리는 지점은 **3개**다(상승장 3개 이상 67.3% · 기준 62.2%).
    그래서 3개부터 만점, 1~2개 절반, 혼자면 0점이다.

    등급(THEME_TOGETHER_TIERS)은 동점을 가르는 순위에만 계속 쓴다 — 4개와 3개를
    가려 주므로 버리지 않는다.
    """
    number = max(int(count or 0), 0)
    if number >= 3:
        return float(points)
    if number >= 1:
        return float(points) * 0.5
    return 0.0


def volume_streak_days(frame) -> int:
    """거래대금이 50일 평균 위에 며칠 연속인지 센다. 오늘이 평균 아래면 0."""
    try:
        value = frame["Close"].astype(float) * frame["Volume"].astype(float)
        above = value > value.rolling(50).mean()
    except Exception:
        return 0
    days = 0
    for flag in reversed(above.tolist()):
        if flag is not True:
            break
        days += 1
    return days


# ── 급락 후 반등장 전용 배점 (2026-08-01 사용자 지시) ─────────────────────────
# 왜 따로 만드나 — 기존 조건점수는 '52주 신고가에 얼마나 가까운가'와 '이동평균 위에
# 있는가'로 절반을 준다. 고점 대비 -40% 종목은 그 조건을 정의상 하나도 못 맞춘다.
# 실제로 재 보니 낙폭 종목이 전부 14~26점 · '제외'로 나왔다(2026-08-01 실측).
# 찾아 놓고 사지 말라고 하는 화면이 되므로, 이 갈래만 다른 자로 잰다.
#
# 배점은 **10년을 앞 5년·뒤 5년으로 갈라 양쪽에서 다 이겼는가**로 나눴다
# (2026-08-06 재측정 · docs/REMEASURE_20260805.md). 한쪽 시기에서만 통한 값은
# 점수를 안 준다 — 그 시기에만 맞는 자리를 1등으로 올리기 때문이다.
# 기준선은 그날 아무 종목이나 69.5%(앞 75.8 / 뒤 61.6).
#
# ── 2026-08-06 이 배점을 두고 오래 다퉜다. 결론과 근거를 그대로 남긴다. ─────
# 화면이 실제로 쓰는 그물(-20~-50% 합친 것, 16,504건)로 다시 재니 이렇다
# (research/theme_size_bias.py). 그전 숫자(테마 앞 +4.2 / 뒤 +1.8)는 -20~-30%
# **한 칸만** 잰 값이었다.
#     테마 동반 3개↑  10년 70.4%  앞 -2.8 / 뒤 +6.3 → 뒤 5년만 이긴다
#     최근 11일 -5%↓  10년 69.9%  앞 +0.6 / 뒤 +1.8 → 양쪽 다 이긴다(아주 약하다)
#     (기준선 69.5%)
#
# 잣대만 보면 11일을 앞세워야 한다. 실제로 한 번 맞바꿨다가 **되돌렸다.**
# 상하님 판단이다 — "앞으로 5년도 테마가 주도한다. 테마를 무시하면 안 된다."
# 뒷받침하는 자료도 있다(research/theme_cohesion_by_year.py) — 시장 영향을 뺀
# 테마 결속력이 앞 5년 0.186 → 뒤 5년 0.223으로 커졌고 2026년이 0.276으로 10년 중
# 가장 높다. 즉 뒤 5년 성적이 우연이 아니라 **시장이 테마 중심으로 바뀐 것**일 수 있다.
#
# **주의** — 결속력이 커진 것과 그게 돈이 되는 것은 별개다. 2021년 결속력이 이미
# 0.226으로 높았는데 그 시기 테마 점수는 이 갈래에서 손해였다(-2.8). 그래서 이 결정은
# 자료가 아니라 **판단**이다. 1년 뒤 두 스크립트를 다시 돌려 결속력과 성적이 같이
# 올라왔는지 확인한다. 안 올라왔으면 11일 40 / 테마 25로 다시 바꾼다.
# 바꿔 봐야 화면은 거의 안 바뀐다 — 상위권 대부분이 두 항목 다 만점이라 합계가 같다.
#
#   40점 테마 동반   — 상하님 판단으로 1등에 둔다(위 설명).
#   25점 최근 11일에 빠졌나 — 앞뒤 양쪽을 이긴 값이다. 낙폭과 **다른 것**을 잰다.
#          낙폭은 '구덩이가 얼마나 깊나'(위치)이고 이것은 '방금 빠졌나 이미 올라왔나'
#          (방향)다. 낙폭 -35%짜리 안에도 반년 전에 무너진 것과 이번에 빠진 것이 섞여 있다.
#   15점 낙폭 갈래   — 뒤 5년에서 진다(앞 +4.3 / 뒤 -1.6%p). 게다가 이미 **그물로 한 번**
#          썼다(20~50%). 그물을 통과한 것들끼리는 거의 안 갈린다(20~30% 68.9% ·
#          30~50% 68.3% · 기준선 69.5%). 두 번 세는 셈이라 낮게 준다.
#   10점 유동성 — 성적 예측이 아니라 '실제로 사고팔 수 있는가'
#   10점 변동성 — 감당할 크기인가
#
#    0점 거래대금 평소 위 연속 — **뺐다**. 앞뒤 양쪽에서 거꾸로였다(앞 -6.6 / 뒤 -9.3%p).
#    0점 테마 ETF가 오르는 중인가 — **뺐다**. 급락에서는 20일선 위가 오히려 나빴다
#          (위 66.5% · 아래 69.6%). 테마가 살아나는지 미리 아는 방법은 못 찾았다.
# 한국(jarvis4)은 외국인·기관 수급이 있어 배점이 다르다. 같은 자로 재면 안 된다.
# ── 2026-08-07 새 그물 위에서 다시 잼 — 위 배점은 **버린다** ────────────────
# 그물이 바뀌었다(나스닥 -10~-20% 가장 깊은 날 · 종목 -20~-30% · 250거래일).
# 그물이 바뀌면 그 안에 걸리는 종목이 달라지고 어느 항목이 값을 하는지도 달라진다.
# 새 그물 안 1,202자리를 창 2·3·4년으로 다시 쟀다(research/us_score_new.py).
# 칸은 '승률로 이긴 창% / 수익률로 이긴 창%'.
#
#   30점 같은 테마 동반 4개↑ — 80/95 · 93/100 · 100/100 (가운데 +4.7%p · 최악 -1.5%p)
#                            3개↑(55% 해당)는 떨어진다. 문턱은 4개다.
#   20점 많이 흔들리지 않나 · 20점 사고팔기 쉬운가 — 성적 예측이 아니라
#                            '감당할 크기인가 · 실제로 살 수 있는가'.
#    0점 최근 11일에 빠졌나 — **새 그물에서 거꾸로다.** 4/11 · 1/1 · 0/0
#                            (가운데 -7.2%p). 옛 그물(120일 보유)에서는 25점짜리
#                            합격 항목이었는데, **1년을 들 거면 이미 돌아선 종목이
#                            낫다.** 보유기간이 바뀌면 같은 값도 뜻이 뒤집힌다.
#    0점 낙폭 갈래 — 그물(-20~-30%)로 이미 한 번 썼다.
#
# **아직 못 넣은 것** — 테마 등수가 더 셌다. 테마 덜 빠짐 상위 3등이 100/100 세 창
# 전부(가운데 +9.5%p · 최악 +3.2%p), 테마 20일 상위 5등이 90/96·99/94·100/97.
# 화면이 테마별 낙폭·수익률 등수를 아직 계산하지 않아 이번에는 못 넣었다.
# 낙폭 갈래는 0점이다 — 갈래가 하나뿐이라 모두 같은 점수를 받아 순위를 못 가른다.
CRASH_SCORE_WEIGHTS = {
    "together": 40.0, "volatility": 30.0, "liquidity": 30.0,
    "recent_drop": 0.0, "bucket": 0.0,
}
# **문턱은 3개가 아니라 4개다**(2026-08-07 새 그물 실측). 3개↑는 그물의 55%가
# 해당돼 못 가르고(75/46 · 85/64 · 99/88), 4개↑라야 붙는다.
CRASH_TOGETHER_FULL = 4

# 대장주 조건점수(`_leader_score`)의 이동평균 추세 배점. 2026-08-07에 0이 됐다 —
# 20일선 위는 창 96개 중 5개, 50일선 위는 12개에서만 이겼다(거꾸로).
# 되살리려면 이 값을 20.0으로, LEADER_RESCALE을 1.0으로 되돌리면 된다.
LEADER_TREND_POINTS = 0.0
# 뺀 20점을 나머지 네 항목에 비례해 나눈다(80점 → 100점). 새로 검증에 통과한
# 항목이 없어 어디로 몰아 줄 근거가 없으므로, 비례 배분이 가장 덜 손대는 길이다.
LEADER_RESCALE = 100.0 / (100.0 - 20.0 + LEADER_TREND_POINTS)
# 이 점수는 어느 항목도 합격선을 넘지 못했다. 화면이 그 사실을 적을 때 읽는다.
LEADER_SCORE_VERIFIED = False

# 최근 11일에 얼마나 움직였나 → 점수. -5% 넘게 빠졌으면 만점, +5% 넘게 올랐으면 0점.
# 두 갈래가 같은 자를 쓴다 — 상승장에서도 양쪽 다 이겼다(앞 +5.2 / 뒤 +1.3%p).
RECENT_DROP_FULL = -5.0
RECENT_DROP_ZERO = 5.0


def recent_drop_points(gain_pct: float | None, points: float) -> float:
    """최근 11일에 빠졌으면 만점, 이미 올랐으면 0점. 모르면 절반."""
    if gain_pct is None:
        return points * 0.5
    return _scale(-float(gain_pct), -RECENT_DROP_ZERO, -RECENT_DROP_FULL, points)

# 거래대금 연속은 **그냥 주면 안 된다**(2026-08-01 사용자 지적: "이미 오른 상황
# 아닌가? 후행 아닌가?"). 실제로 재 보니 그 지적이 맞았다.
#
# 미국 낙폭 구간 46,653개 — 최근 11일 움직임을 같게 맞춰 놓고 견준 결과
# (왼쪽 연속 0~3일 / 오른쪽 연속 4일 이상, 가운데 값·100번 중 이긴 횟수):
#     이미 -5% 넘게 빠짐   +3.74% 59번  →  +7.70% 67번   ← 가장 좋다
#     -5~0%              +2.05% 55번  →  +3.23% 59번
#     0~+5%              +2.89% 56번  →  +0.52% 51번   ← 뒤집힌다
#     +5~+15%            +2.38% 55번  →  +0.30% 50번
#     +15% 넘게 오름       +4.21% 58번  →  -1.29% 48번   ← 손해다
# 한국 낙폭 구간 111,012개도 같은 모양이었다(-5% 넘게 빠진 쪽 +4.08%·62번,
# +15% 넘게 오른 쪽 -0.77%·48번).
#
# 즉 값을 하는 것은 '거래대금이 많다'가 아니라
# **'값은 아직 안 올랐는데 돈만 계속 붙어 있다'**는 상태다.
# 이미 오른 뒤 거래대금이 많은 것은 후행이고 손해다. 그래서 최근 11일 오름폭으로
# 점수를 깎는다.
VOLUME_STREAK_LOOKBACK = 11
VOLUME_STREAK_GATES = ((0.0, 1.0), (15.0, 0.5))   # (최근 11일 오름폭 상한, 점수 배수)


def volume_streak_weight(recent_gain_pct: float | None) -> float:
    """최근에 이미 오른 만큼 거래대금 연속 점수를 깎는 배수(0~1)."""
    if recent_gain_pct is None:
        return 0.5
    for limit, factor in VOLUME_STREAK_GATES:
        if float(recent_gain_pct) <= limit:
            return factor
    return 0.0                                     # +15% 넘게 올랐으면 아예 안 준다


def recent_gain_pct(frame, days: int = VOLUME_STREAK_LOOKBACK) -> float | None:
    """최근 며칠 동안 이미 얼마나 올랐는지(%). 자료가 짧으면 None."""
    try:
        close = frame["Close"].dropna()
        if len(close) <= days:
            return None
        return (float(close.iloc[-1]) / float(close.iloc[-1 - days]) - 1) * 100
    except Exception:
        return None


def crash_rebound_score(row: dict) -> dict:
    """급락 후 반등장 후보의 점수(100점)와 근거를 낸다."""
    metrics = row.get("metrics") or {}
    weights = CRASH_SCORE_WEIGHTS
    parts = []

    count = int(row.get("together_count") or 0)
    theme = str(row.get("together_theme") or "같은 테마")
    # 급락 후 반등장은 **4개↑라야 만점**이다(2026-08-07 새 그물 실측). 3개↑는
    # 그물의 55%가 해당돼 못 가른다. 상승장은 그대로 3개↑ 만점이다.
    full = float(weights["together"])
    parts.append(("같은 테마 동반",
                  full if count >= CRASH_TOGETHER_FULL
                  else full * 0.5 if count >= 2 else 0.0,
                  full,
                  f"{theme}에서 {count}종목 같이 걸림 "
                  f"({CRASH_TOGETHER_FULL}개↑ 만점 · 2~3개 절반)"))

    # 낙폭과 **다른 것**을 잰다 — 낙폭은 구덩이 깊이, 이것은 방금 빠졌나 여부.
    gain = row.get("recent_gain_pct")
    parts.append(("최근 11일에 빠졌나", recent_drop_points(gain, weights["recent_drop"]),
                  weights["recent_drop"],
                  "모름" if gain is None else f"{float(gain):+.1f}%"))

    # 20~30%가 만점, 30~50%는 절반 — 깊다고 더 좋지는 않았다(68.9% vs 68.3%).
    bucket = weights["bucket"] * (0.5 if row.get("bucket") == "deep" else 1.0)
    parts.append(("낙폭 갈래", bucket, weights["bucket"],
                  str(row.get("bucket_label") or "—")))

    dollar = metrics.get("avg_dollar_volume") or 0
    liquidity = _scale(float(dollar) / 1e9, 0.05, 1.0, weights["liquidity"])
    parts.append(("유동성", liquidity, weights["liquidity"],
                  f"${float(dollar)/1e6:,.0f}M" if dollar else "—"))

    atr = metrics.get("atr_pct")
    # 변동성은 낮을수록 좋다 — 8%가 넘으면 0점, 2% 이하면 만점.
    volatility = weights["volatility"] if atr is None else _scale(-float(atr), -8.0, -2.0,
                                                                 weights["volatility"])
    parts.append(("변동성 안정", volatility, weights["volatility"],
                  f"{float(atr):.1f}%" if atr is not None else "—"))

    score = round(sum(value for _n, value, _m, _t in parts), 1)
    return {"score": score, "parts": parts, "max": 100.0}


# ── 상승장(신고가 눌림매수) 전용 배점 (2026-08-06 재측정) ─────────────────────
# 그물이 다르므로 **낙폭 배점을 그대로 쓰면 안 된다.** 다만 어느 값이 값을 하는지는
# 두 갈래가 같았다 — 테마 동반과 최근 11일, 둘뿐이다.
#
# 테마 명부 198종목 10년치, 상승장 1,755일 · 그물에 걸린 자리 9,875개.
# 기준선은 그날 아무 종목이나 62.2%(앞 65.7 / 뒤 58.8) · 가운데 +6.3%.
#
#   40점 같은 테마 동반 — 3개 이상 67.3%(앞 +8.6 / 뒤 +2.6%p). **양쪽 다 이김.** 가장 세다.
#   25점 최근 11일에 빠졌나 — -5% 넘게 빠짐 65.7%(앞 +5.2 / 뒤 +1.3%p). **양쪽 다 이김.**
#   15점 눌린 폭 — 10~15%가 63.2%인데 앞 +3.9 / 뒤 **-1.2%p**로 뒤 5년에 진다.
#          게다가 그물(4~15%)로 이미 한 번 썼다. 그래서 낮게 준다.
#   10점 유동성 / 10점 변동성 — 성적 예측이 아니라 살 수 있는가·감당할 크기인가.
#
# **0점으로 뺀 것 — 실수하기 쉬우니 반드시 읽을 것**
#   * 최근 60일 상승폭: 예전에 30점을 줬는데(가운데 +14.1%로 커 보인다) 승률로 보면
#     62.9%로 기준선과 같고 **뒤 5년에 진다**(앞 +3.0 / 뒤 -0.5%p). 가운데 값만 보고
#     점수를 준 것이 잘못이었다. 2026-08-06에 뺐다.
#   * 거래대금 평소 위 연속: 상승장에서 60.8%로 **거꾸로**다(앞 -2.2 / 뒤 0.0%p).
#     이미 신고가인데 거래대금까지 오래 실렸으면 늦은 자리다.
#   * 신고가 뒤 며칠: 1~3일 63.5%(앞 +3.2 / 뒤 -0.5%p)로 뒤 5년에 진다. 화면에는
#     날짜를 **보여만 주고** 점수는 안 준다(2026-08-06 사용자 지시).
#   * 50·200일선 위: 신고가 종목은 정의상 100% 위라 가르지 못한다.
BREAKOUT_SCORE_WEIGHTS = {
    "together": 40.0, "recent_drop": 25.0, "drop": 15.0,
    "liquidity": 10.0, "volatility": 10.0,
}


def breakout_score(row: dict) -> dict:
    """상승장(신고가 눌림매수) 후보의 점수(100점)와 근거."""
    metrics = row.get("metrics") or {}
    weights = BREAKOUT_SCORE_WEIGHTS
    parts = []

    # '4개'가 테마 종류 4개로 읽힌다는 지적을 받아 테마 이름을 넣는다(2026-08-06).
    count = int(row.get("together_count") or 0)
    theme = str(row.get("together_theme") or "같은 테마")
    parts.append(("같은 테마 동반", theme_together_points(count, weights["together"]),
                  weights["together"],
                  f"{theme}에서 {count}종목 같이 걸림 (3개↑ 만점 · 1~2개 절반)"))

    gain = row.get("recent_gain_pct")
    parts.append(("최근 11일에 빠졌나", recent_drop_points(gain, weights["recent_drop"]),
                  weights["recent_drop"],
                  "모름" if gain is None else f"{float(gain):+.1f}%"))

    # 눌린 폭은 10~15%가 만점이다(63.2%). 4%에 가까울수록 깎는다 — 그물(4~15%)은
    # 넓게 두고 점수로만 가른다. 15%보다 더 눌린 것은 그물 밖이라 여기 안 온다.
    drop = metrics.get("from_high_pct")
    if drop is None:
        drop_points = weights["drop"] * 0.5
    else:
        drop_points = _scale(-float(drop), 4.0, 10.0, weights["drop"])
    parts.append(("눌린 폭", drop_points, weights["drop"],
                  "—" if drop is None else f"{float(drop):+.1f}%"))

    dollar = metrics.get("avg_dollar_volume") or 0
    parts.append(("유동성", _scale(float(dollar) / 1e9, 0.05, 1.0, weights["liquidity"]),
                  weights["liquidity"], f"${float(dollar)/1e6:,.0f}M" if dollar else "—"))

    atr = metrics.get("atr_pct")
    parts.append(("변동성 안정",
                  weights["volatility"] if atr is None
                  else _scale(-float(atr), -8.0, -2.0, weights["volatility"]),
                  weights["volatility"], f"{float(atr):.1f}%" if atr is not None else "—"))

    return {"score": round(sum(v for _n, v, _m, _t in parts), 1), "parts": parts, "max": 100.0}


def breakout_plan(row: dict) -> dict:
    """상승장(신고가 눌림매수)의 매수 심사 결과.

    낙폭 갈래와 마찬가지로 **넘어야 할 기준가도, 손절가도 없다.** 종가를 확인하고
    다음 거래일 시가에 사서 120거래일 뒤에 판다.
    """
    metrics = row.get("metrics") or {}
    hold = int(row.get("hold_days") or BREAKOUT_PULLBACK_RULE["hold_days"])
    score = float(breakout_score(row)["score"])
    if score >= 70:
        state, recommendation = "규칙에 맞는 자리", "조건부 후보"
    elif score >= 50:
        state, recommendation = "자리는 맞으나 근거가 얇음", "관찰"
    else:
        state, recommendation = "규칙만 맞고 뒷받침이 없음", "관찰"
    return {
        "state": state,
        "recommendation": recommendation,
        "rule_mode": "breakout",
        "entry": "다음 거래일 시가",
        "hold_days": hold,
        "current": metrics.get("current"),
        "invalidation": None,
        "target": None,
        "buy_reason": (
            f"52주 신고가를 찍고 {int(row.get('wait_days') or 0)}거래일이 지나 "
            f"고점 대비 {metrics.get('from_high_pct', 0):.1f}%까지 눌린 자리입니다. "
            f"규칙대로라면 오늘 종가를 확인하고 다음 거래일 시가에 사서 "
            f"{hold}거래일 뒤 종가에 팝니다. 이 규칙에는 손절가가 없습니다."
        ),
    }


def _crash_drop_story(row: dict, metrics: dict) -> str:
    """급락 갈래의 낙폭을 '그날 → 지금 → 그 뒤' 세 숫자로 풀어 쓴다.

    **왜 필요했나(2026-08-07 상하님 지적).** 여기에는 '고점 대비 -12.7%까지 내려온
    낙폭 종목입니다'만 적혀 있었는데, 이 -12.7%는 **오늘** 낙폭이다. 그런데 바로 옆
    점수표는 '낙폭 갈래 -20~-30%'라고 적는다 — 갈래는 **기준일 낙폭**(-21.8%)으로
    가르기 때문이다. 같은 화면이 두 숫자를 말이 없이 섞어 놓아 서로 틀린 것처럼
    보였다.

    그래서 세 숫자를 다 적고 어느 것이 갈래를 정하는지 밝힌다. 표 맨 위 칸에도
    같은 세 숫자가 있고, 그 뜻을 설명한 곳이 화면 어디에도 없었다.

    기준일이 없으면(나스닥이 최근 -6~-12%에 든 날이 없을 때) 오늘 낙폭 하나로만
    가르므로 예전 문장을 그대로 쓴다.
    """
    now_drop = row.get("now_from_high_pct")
    if now_drop is None:
        now_drop = metrics.get("from_high_pct")
    judged = row.get("judged_from_high_pct")
    ref_date = row.get("reference_date")
    since = row.get("since_reference_pct")
    if judged is None or not ref_date or now_drop is None:
        return f"고점 대비 {float(now_drop or 0):.1f}%까지 내려온 낙폭 종목입니다."
    moved = ""
    if since is not None:
        verb = "올라" if float(since) >= 0 else "더 빠져"
        moved = f" 그 뒤 {float(since):+.1f}% {verb}"
    return (
        f"기준일({ref_date})에 고점 대비 {float(judged):.1f}%까지 빠졌던 종목입니다."
        f"{moved} 지금은 고점 대비 {float(now_drop):.1f}%입니다. "
        "갈래와 점수는 오늘이 아니라 그날 낙폭으로 정합니다 — 오늘 값으로 정하면 "
        "이미 반등한 종목이 목록에서 사라져 정작 사야 할 자리를 놓칩니다."
    )


def crash_rebound_plan(row: dict) -> dict:
    """급락 후 반등장의 매수 심사 결과.

    기존 심사는 '기준가를 넘으면 산다'인데, 이 규칙은 **정해진 날 시가에 사서 정해진
    날 판다.** 넘어야 할 가격도, 손절도 규칙에 없다. 그대로 적는다 — 없는 것을
    있는 것처럼 적으면 화면이 거짓말을 한다.
    """
    metrics = row.get("metrics") or {}
    hold = int(row.get("hold_days") or 0)
    score = float(crash_rebound_score(row)["score"])
    if score >= 70:
        state, recommendation = "규칙에 맞는 자리", "조건부 후보"
    elif score >= 50:
        state, recommendation = "자리는 맞으나 근거가 얇음", "관찰"
    else:
        state, recommendation = "규칙만 맞고 뒷받침이 없음", "관찰"
    return {
        "state": state,
        "recommendation": recommendation,
        "rule_mode": "crash",
        "entry": "다음 거래일 시가",
        "hold_days": hold,
        "current": metrics.get("current"),
        "invalidation": None,     # 이 규칙에는 손절이 없다
        "target": None,           # 목표가도 없다 — 정해진 날에 판다
        "buy_reason": (
            _crash_drop_story(row, metrics)
            + f" 규칙대로라면 오늘 종가를 확인하고 다음 거래일 시가에 사서 "
            f"{hold}거래일 뒤 종가에 팝니다. 이 규칙에는 손절가가 없습니다."
        ),
    }


def _attach_theme_together(rows: list, memberships: dict) -> None:
    """같은 테마에서 **함께 기준을 통과한** 종목이 몇 개인지 각 줄에 적는다.

    이 표에 걸린 종목끼리만 센다 — '이 테마가 통째로 그 자리에 와 있나'를 재는 값이다.
    """
    counts: dict[str, int] = {}
    for row in rows:
        for name in row.get("themes") or []:
            counts[name] = counts.get(name, 0) + 1
    for row in rows:
        pairs = [(counts.get(name, 0) - 1, name) for name in (row.get("themes") or [])]
        best = max(pairs) if pairs else (0, "")
        row["together_count"], row["together_theme"] = max(best[0], 0), best[1]
        points, label = theme_together_tier(row["together_count"])
        row["together_tier"], row["together_label"] = points, label


def _rank_key(row: dict):
    """순위 — ① 테마 동반(검증됨) ② 거래대금 연속일(약함) ③ 거래대금(참고)."""
    return (
        -row.get("together_tier", 0),
        -row.get("together_count", 0),
        -min(int(row.get("volume_streak") or 0), VOLUME_STREAK_LOOKBACK)
        * volume_streak_weight(row.get("recent_gain_pct")),
        -(row["metrics"].get("avg_dollar_volume") or 0),
    )


def _breakout_rank_key(row: dict):
    """상승장 순위 — 낙폭과 **다른 차례**다(재 본 결과가 다르다, 2026-08-01).

    ① 같은 테마 동반(3개 이상 100번 중 78번) ② 최근 60일 상승폭(40% 넘으면 70번)
    ③ 거래대금(참고). **거래대금 연속은 안 쓴다** — 상승장에서는 거꾸로였다
    (11일 이상 53번, 기준선 62번). 낙폭 표에서만 쓴다.
    """
    return (
        -row.get("together_tier", 0),
        -row.get("together_count", 0),
        -float((row.get("metrics") or {}).get("ret60") or 0),
        -((row.get("metrics") or {}).get("avg_dollar_volume") or 0),
    )


def _universe_row(ticker: str, metrics: dict, memberships: dict) -> dict:
    themes = memberships.get(ticker) or []
    return {
        "ticker": ticker,
        "name": STOCK_NAMES.get(ticker, ticker),
        "themes": themes,
        "theme_count": len(themes),
        "metrics": metrics,
        # 상세 화면(_render_pullback_detail)이 눌림 점수를 그대로 쓰므로 같이 담는다.
        "pullback": _pullback_quality(metrics, len(themes)) or {},
    }


def find_breakout_pullback_stocks(*, reuse_only: bool = False, result_limit: int = 20) -> dict:
    """설명서 1번 — 정상 상승장의 '신고가 눌림매수' 자리를 찾는다 (2026-08-01).

    설명서 그대로만 거른다. **50일선·200일선은 보지 않는다** — 설명서의 규칙은
    "52주 신고가 돌파 → 3~5거래일 기다림 → 그 고점에서 4~6% 하락한 날 종가 확인"
    뿐이고, 이동평균 조건은 없다. 여기에 없는 조건을 더하면 화면이 설명과 다른
    것을 찾게 된다.

    순서는 평균 거래대금이 큰 순이다 — 규칙이 순위를 정해 주지 않으므로, 사고팔기
    쉬운 종목을 위에 둔다.
    """
    daily, meta, memberships = _universe_daily(reuse_only)
    if not daily:
        return {"ok": False, "error": meta.get("error") or "미국 종목 일봉 조회 실패", "rows": []}

    wait_min, wait_max = BREAKOUT_PULLBACK_RULE["wait_days"]
    drop_low, drop_high = BREAKOUT_PULLBACK_RULE["drop_band"]
    rows, window_count = [], 0
    for ticker in US_LARGE_CAP_UNIVERSE:
        metrics = _series_metrics(daily.get(ticker))
        if not metrics.get("ok"):
            continue
        days_ago = metrics.get("high52_days_ago")
        from_high = metrics.get("from_high_pct")
        if days_ago is None or not (wait_min <= days_ago <= wait_max):
            continue
        window_count += 1
        if from_high is None or not (drop_low <= from_high <= drop_high):
            continue
        row = _universe_row(ticker, metrics, memberships)
        row["wait_days"] = int(days_ago)
        row["hold_days"] = BREAKOUT_PULLBACK_RULE["hold_days"]
        row["volume_streak"] = volume_streak_days(daily.get(ticker))
        row["recent_gain_pct"] = recent_gain_pct(daily.get(ticker))
        rows.append(row)
    # 테마 동반이 배점의 40점이므로 점수를 내기 **전에** 세어 둬야 한다.
    _attach_theme_together(rows, memberships)
    # 점수가 곧 순위다(2026-08-06 사용자 결정 — 별점은 뺐다). 같은 점수 안에서는
    # 예전 순위 기준(테마 동반 → 60일 상승폭 → 거래대금)을 그대로 쓴다.
    for row in rows:
        row["score"] = float(breakout_score(row)["score"])
    rows.sort(key=lambda row: (-row.get("score", 0.0), *_breakout_rank_key(row)))
    rows = rows[: max(1, int(result_limit))]
    for index, row in enumerate(rows, 1):
        row["pullback_rank"] = index
    return {
        "ok": True,
        "mode": "breakout",
        "rows": rows,
        "rule": BREAKOUT_PULLBACK_RULE,
        # 표를 잰 자리인지 알려만 준다 — 막지 않는다(2026-08-06 사용자 결정).
        "market": breakout_market_state(),
        "score_weights": BREAKOUT_SCORE_WEIGHTS,
        "base_win_rate": BREAKOUT_BASE_WIN_RATE,
        "base_median_return": BREAKOUT_BASE_MEDIAN,
        "universe_count": len(US_LARGE_CAP_UNIVERSE),
        "data_count": len(daily),
        "window_count": window_count,
        "result_limit": int(result_limit),
        "checked_at": meta.get("fetched_at"),
        "stale": bool(meta.get("stale")),
        "reused_batch": bool(meta.get("reused_superset")),
    }


def _from_high_on(frame, as_of_date: str):
    """그날까지의 자료만으로 잰 '52주 고점 대비'와 그날 종가.

    오늘 기준으로 다시 재면 이미 오른 종목이 갈래에서 빠져나가므로, 기준일
    시점의 값이 따로 필요하다(2026-08-06). 앞을 훔쳐보지 않는다.
    """
    if frame is None or getattr(frame, "empty", True):
        return None
    try:
        target = pd.Timestamp(as_of_date)
        index = frame.index
        if getattr(index, "tz", None) is not None:
            target = target.tz_localize(index.tz)
        past = frame[index <= target]
        if len(past) < 252:
            return None
        high52 = float(past["High"].tail(252).max())
        close = float(past["Close"].iloc[-1])
        if not (high52 > 0 and close > 0):
            return None
        return (close / high52 - 1.0) * 100, close
    except Exception:
        return None


def crash_reference_day(lookback_days: int = 30) -> dict:
    """급락 후 반등장의 **기준일**을 찾는다 (2026-08-06 사용자 지시).

    오늘 기준으로만 보면 안 된다 — 그 자리에서 걸렸던 종목이 이미 올라 갈래를
    벗어나면 화면에서 사라진다. 실제로 2026-07-29(나스닥 -11.5%)에 걸렸던
    MSFT는 그 뒤 +24.8% 올라 오늘 기준으로는 -11.4%라 목록에서 빠진다.
    가장 많이 오른 종목이 사라지는 셈이라 거꾸로다.

    그래서 최근 한 달 안에 나스닥이 -6~-12%였던 날 중 **가장 깊었던 날**을
    기준일로 잡고, 종목도 그날 기준으로 판단한다.
    """
    low, high = CRASH_MARKET_BAND
    try:
        # 과거 시점의 52주 고점을 계산하려면 2년치가 필요하다(1년치면 창이 안 찬다).
        daily, _meta = _download_cached(
            (CRASH_MARKET_SYMBOL,), period="2y", interval="1d", ttl_seconds=600
        )
        frame = daily.get(CRASH_MARKET_SYMBOL)
        if frame is None or frame.empty:
            return {"ok": False, "reason": "나스닥 일봉을 못 받았습니다"}
        high52 = frame["High"].rolling(252, min_periods=252).max()
        drop = (frame["Close"] / high52 - 1.0) * 100
        recent = drop.dropna().tail(int(lookback_days))
        if recent.empty:
            return {"ok": False, "reason": "나스닥 낙폭을 계산할 자료가 모자랍니다"}
        today_drop = float(recent.iloc[-1])
        inside = recent[(recent >= low) & (recent <= high)]
        if inside.empty:
            return {"ok": True, "armed": False, "today_drop": today_drop,
                    "reference_date": None, "reference_drop": None, "days_in_band": 0,
                    "reason": (f"최근 {lookback_days}거래일에 나스닥이 "
                               f"{abs(high):.0f}~{abs(low):.0f}% 내려온 날이 없었습니다. "
                               f"지금은 {today_drop:.1f}%입니다.")}
        ref = inside.idxmin()          # 가장 깊었던 날
        return {"ok": True, "armed": True, "today_drop": today_drop,
                "reference_date": pd.Timestamp(ref).strftime("%Y-%m-%d"),
                "reference_drop": float(inside.min()),
                "days_in_band": int(len(inside)),
                "last_in_band": pd.Timestamp(inside.index[-1]).strftime("%Y-%m-%d"),
                "reason": ""}
    except Exception as exc:
        return {"ok": False, "reason": f"기준일을 찾지 못했습니다 ({exc})"}


def breakout_market_state() -> dict:
    """상승장 규칙의 표를 **잰 자리**인가 (2026-08-06 사용자 결정).

    거르지 않는다 — 알려만 준다. 급락 갈래와 같은 방식이다.

    왜 거르지 않나 — 이 조건은 설명서에 있던 규칙이 아니다. 2026-08-01에
    '어느 규칙이 어느 장에서 통하나'를 재면서 **날을 둘로 가르려고 내가 정한
    잣대**였고(commit 73e3605·8c3f8e3), 표 1의 숫자는 그 날들에서만 잰 값이라
    표 맨 위 '장세' 칸에 적었다. 상하님이 2026-08-06에 그 표를 화면에 넣으시면서
    '이렇게 쟀다'가 '이렇게 하라'처럼 읽히게 됐다.

    상하님이 주신 원래 설명서(2026-08-01)에는 이동평균도 시장 낙폭도 없다.
    거르는 조건으로 바꾸면 화면이 통째로 비는 날이 생긴다(급락 갈래에서 실제로
    겪었다). 그래서 **표를 잰 자리인지만 알려주고 종목은 그대로 보여준다.**
    """
    try:
        daily, _meta = _download_cached(
            (CRASH_MARKET_SYMBOL,), period="1y", interval="1d", ttl_seconds=300
        )
        metrics = _series_metrics(daily.get(CRASH_MARKET_SYMBOL))
        if not metrics.get("ok"):
            raise RuntimeError("나스닥 일봉 없음")
        drop = _finite(metrics.get("from_high_pct"))
        current = _finite(metrics.get("current"))
        sma200 = _finite(metrics.get("sma200"))
    except Exception:
        drop = current = sma200 = None
    if drop is None or current is None or sma200 is None:
        return {"ok": False, "armed": True, "drop_pct": drop, "above_200": None,
                "reason": "나스닥을 못 읽어 표를 잰 자리인지 확인하지 못했습니다"}
    above = current > sma200
    limit = BREAKOUT_MARKET_MAX_DROP
    armed = bool(above) and drop > limit
    place = "위" if above else "아래"
    if armed:
        reason = (f"나스닥이 200일선 {place}이고 고점 대비 {drop:.1f}%입니다 — "
                  "표를 잰 자리가 맞습니다")
    else:
        reason = (f"나스닥이 200일선 {place}이고 고점 대비 {drop:.1f}%입니다 — "
                  f"**오늘은 표를 잰 자리가 아닙니다.** 위 표의 숫자는 200일선 위이고 "
                  f"고점 대비 {abs(limit):.0f}% 안쪽이던 날에서만 잰 값입니다. "
                  "종목은 그대로 보여드리니 참고만 하십시오.")
    return {"ok": True, "armed": armed, "drop_pct": drop, "above_200": above,
            "max_drop": limit, "reason": reason}


def crash_market_state() -> dict:
    """급락 후 반등장 규칙을 지금 써도 되는 자리인가 (2026-08-06 새로 생김).

    나스닥이 52주 고점에서 **6~12%** 빠졌을 때만 켠다. 10년치로 재 보니 그 자리가
    7개월에 한 번씩 오면서 성적도 가장 좋았고, -12%보다 더 빠진 자리는 아무 종목이나
    산 것보다 못했다(docs/US_METHOD_TABLES.md).

    자료를 못 받으면 막지 않는다 — 조용히 켜 두고 화면은 예전처럼 동작한다.
    자료 문제로 단추가 먹통이 되는 편이 더 나쁘다.
    """
    low, high = CRASH_MARKET_BAND
    try:
        daily, _meta = _download_cached(
            (CRASH_MARKET_SYMBOL,), period="1y", interval="1d", ttl_seconds=300
        )
        metrics = _series_metrics(daily.get(CRASH_MARKET_SYMBOL))
        drop = _finite(metrics.get("from_high_pct")) if metrics.get("ok") else None
    except Exception:
        drop = None
    if drop is None:
        return {"ok": False, "armed": True, "drop_pct": None, "band": CRASH_MARKET_BAND,
                "reason": "나스닥 낙폭을 못 읽어 시장 조건을 확인하지 못했습니다"}
    armed = low <= drop <= high
    if armed:
        reason = f"나스닥이 고점에서 {drop:.1f}% 내려왔습니다 — 이 규칙을 쓰는 자리입니다"
    elif drop > high:
        reason = (f"나스닥이 고점에서 {drop:.1f}%밖에 안 내려왔습니다. "
                  f"이 규칙은 {abs(high):.0f}~{abs(low):.0f}% 내려왔을 때 씁니다 "
                  "(7개월에 한 번쯤 옵니다).")
    else:
        reason = (f"나스닥이 고점에서 {drop:.1f}% 내려왔습니다 — 너무 깊습니다. "
                  f"{abs(low):.0f}%보다 더 빠진 자리는 아무 종목이나 산 것보다 못했습니다.")
    return {"ok": True, "armed": armed, "drop_pct": drop,
            "band": CRASH_MARKET_BAND, "reason": reason}


def find_crash_rebound_stocks(*, reuse_only: bool = False, result_limit: int = 20) -> dict:
    """설명서 2번 — 급락 후 반등장의 '낙폭 종목'을 찾는다 (2026-08-01).

    신고가가 언제 나왔는지는 보지 않고, **고점 대비 얼마나 하락했는지만** 본다.
    50일선 조건도 없다 — 30~50% 빠진 종목이 50일선 위에 있을 리 없고, 설명서에도
    그런 조건이 없다(2026-08-01 사용자 확인: "굳이 50일선 맞출 필요가 있나").

    낙폭이 깊은 갈래를 위에 두고, 같은 갈래 안에서는 평균 거래대금이 큰 순이다.
    """
    daily, meta, memberships = _universe_daily(reuse_only)
    if not daily:
        return {"ok": False, "error": meta.get("error") or "미국 종목 일봉 조회 실패", "rows": []}

    # 시장 낙폭은 막지 않고 알려만 준다(2026-08-06 사용자 결정).
    market = crash_market_state()
    # 기준일 — 최근에 나스닥이 -6~-12%였던 날 중 가장 깊었던 날. 그날 기준으로
    # 종목을 판단해야 이미 오른 종목이 목록에서 사라지지 않는다(2026-08-06 지시).
    reference = crash_reference_day()
    ref_date = reference.get("reference_date") if reference.get("armed") else None
    ref_frames = {}
    if ref_date:
        ref_frames, _ref_meta = _download_cached(
            tuple(US_LARGE_CAP_UNIVERSE), period="2y", interval="1d", ttl_seconds=600
        )

    rows = []
    counts = {rule["key"]: 0 for rule in CRASH_REBOUND_RULES}
    for ticker in US_LARGE_CAP_UNIVERSE:
        metrics = _series_metrics(daily.get(ticker))
        if not metrics.get("ok"):
            continue
        now_from_high = metrics.get("from_high_pct")
        # 갈래를 가르는 값 — 기준일이 있으면 **그날** 낙폭으로, 없으면 오늘 낙폭으로.
        from_high, then_close = now_from_high, None
        if ref_date:
            judged = _from_high_on(ref_frames.get(ticker), ref_date)
            if judged is not None:
                from_high, then_close = judged
        if from_high is None:
            continue
        for order, rule in enumerate(CRASH_REBOUND_RULES):
            low, high = rule["band"]
            if low <= from_high < high:
                counts[rule["key"]] += 1
                row = _universe_row(ticker, metrics, memberships)
                # 그날 낙폭 · 지금 낙폭 · 그 뒤 주가를 같이 보여준다.
                row["judged_from_high_pct"] = from_high
                row["now_from_high_pct"] = now_from_high
                row["reference_date"] = ref_date
                current = metrics.get("current")
                row["since_reference_pct"] = (
                    (float(current) / float(then_close) - 1.0) * 100
                    if then_close and current else None
                )
                row["bucket"] = rule["key"]
                row["bucket_label"] = rule["label"]
                row["hold_days"] = rule["hold_days"]
                row["win_rate"] = rule["win_rate"]
                row["median_return"] = rule["median_return"]
                row["base_win_rate"] = rule["base_win_rate"]
                row["volume_streak"] = volume_streak_days(daily.get(ticker))
                row["recent_gain_pct"] = recent_gain_pct(daily.get(ticker))
                row["_order"] = order
                rows.append(row)
                break
    # 테마 동반이 배점의 40점이므로 점수를 내기 **전에** 세어 둬야 한다.
    _attach_theme_together(rows, memberships)
    # 점수가 곧 순위다(2026-08-06 사용자 결정 — 별점은 뺐다). 같은 점수 안에서는
    # 예전 순위 기준(테마 동반 → 갈래 → 거래대금)을 그대로 쓴다.
    for row in rows:
        row["score"] = float(crash_rebound_score(row)["score"])
    rows.sort(key=lambda row: (-row.get("score", 0.0),
                               _rank_key(row)[0], _rank_key(row)[1],
                               row.get("_order", 9), *_rank_key(row)[2:]))
    rows = rows[: max(1, int(result_limit))]
    for index, row in enumerate(rows, 1):
        row["pullback_rank"] = index
        row.pop("_order", None)
    return {
        "ok": True,
        "mode": "crash",
        "rows": rows,
        "rules": CRASH_REBOUND_RULES,
        "score_weights": CRASH_SCORE_WEIGHTS,
        "bucket_counts": counts,
        "market": market,
        "reference": reference,
        "universe_count": len(US_LARGE_CAP_UNIVERSE),
        "data_count": len(daily),
        "result_limit": int(result_limit),
        "checked_at": meta.get("fetched_at"),
        "stale": bool(meta.get("stale")),
        "reused_batch": bool(meta.get("reused_superset")),
    }


def _leader_score(metrics: dict, theme_ret20: float | None) -> tuple[float, list[float]]:
    """대장주 조건점수 100점. **어느 항목도 검증을 통과하지 못했다**(2026-08-07).

    한국 조건점수를 재 보니 40점이 거꾸로였길래(`research/kr_cond_check.py`) 미국도
    같은 잣대로 쟀다(`research/us_cond_check.py`, 그물 안 375,234자리, 창 2·3·4년).
    결과는 한국보다 더 나빴다 — **합격선(65%)을 넘은 항목이 하나도 없다.**

      · 20일선 위      창  5 /  4 /  0%  ✗ 거꾸로
      · 50일선 위      창 12 / 10 /  4%  ✗ 거꾸로
      · 200일선 위     창 42 / 42 / 33%  △ 미달
      · 신고가 근접    창 47 / 42 / 26%  △ 미달
      · 변동성 낮음    창 55 / 45 / 43%  △ 미달
      · 20일 상대강도  창 32 / 43 / 61%  △ 미달
      · 거래대금 상위  창 70 / 58 / 35%  △ 미달

    미국 대형주는 애초에 고를 게 없다는 뜻이다 — 상승장 그물이 144가지 다 떨어진
    것과 같은 결론이다. 그래서 **배점을 새로 짜지 않았다.** 옮길 데가 없다.
    거꾸로였던 이동평균 추세 20점만 빼고, 그만큼을 나머지에 비례해 나눴다.
    화면에는 이 점수가 검증되지 않았다고 적어 뒀다.
    """
    relative = metrics.get("ret20") - theme_ret20 if theme_ret20 is not None else None
    rs_points = _scale(relative, -8, 8, 25 * LEADER_RESCALE)
    from_high = metrics.get("from_high_pct")
    high_points = _scale(from_high, -20, 0, 25 * LEADER_RESCALE)
    # 20일선·50일선 위는 거꾸로, 200일선 위는 미달이었다 → 항목 전체를 0점으로.
    # 계산은 남겨 둔다(LEADER_TREND_POINTS를 20으로 되돌리면 그대로 살아난다).
    trend_points = 0.0
    for moving_average, share in (("sma20", 0.30), ("sma50", 0.35), ("sma200", 0.35)):
        value = metrics.get(moving_average)
        if value and metrics.get("current") and metrics["current"] > value:
            trend_points += LEADER_TREND_POINTS * share
    dollar_volume = metrics.get("avg_dollar_volume")
    if dollar_volume is None:
        liquidity_points = 0.0
    elif dollar_volume >= 1_000_000_000:
        liquidity_points = 15.0 * LEADER_RESCALE
    elif dollar_volume >= 300_000_000:
        liquidity_points = 13.0 * LEADER_RESCALE
    elif dollar_volume >= 100_000_000:
        liquidity_points = 10.0 * LEADER_RESCALE
    elif dollar_volume >= 50_000_000:
        liquidity_points = 7.0 * LEADER_RESCALE
    elif dollar_volume >= 20_000_000:
        liquidity_points = 4.0 * LEADER_RESCALE
    else:
        liquidity_points = 1.0 * LEADER_RESCALE
    atr_pct = metrics.get("atr_pct")
    if atr_pct is None:
        risk_points = 0.0
    elif atr_pct <= 3:
        risk_points = 15.0 * LEADER_RESCALE
    elif atr_pct <= 5:
        risk_points = 12.0 * LEADER_RESCALE
    elif atr_pct <= 7:
        risk_points = 8.0 * LEADER_RESCALE
    elif atr_pct <= 10:
        risk_points = 4.0 * LEADER_RESCALE
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
        buy_reason = "시장 국면이 약세 구간이라 신규 매수를 보류합니다."
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
    benchmark_ret20: float | None = None,
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
        themes = row.get("themes") or []
        theme_score = max((theme_scores.get(str(t), 0.0) for t in themes), default=0.0)
        merged = dict(row)
        # 갈래 표(상승장·급락)의 'score'는 **그 갈래 전용 배점**이라 대장주의
        # 종목 조건점수와 자가 다르다. 섞어서 줄 세우면 다른 자로 잰 값을 견주는
        # 셈이 되므로 여기서 **같은 자로 다시 잰다**(2026-08-06).
        review = analyze_pullback_stock(
            row,
            benchmark_ret20=benchmark_ret20,
            market_score=market_score,
            theme_score=theme_score,
        )
        merged["score"] = review.get("score")
        merged["plan"] = review.get("plan") or _entry_plan(
            row["metrics"], float(review.get("score") or 0), market_score, theme_score
        )
        # 어느 갈래에서 왔는지 화면에 남긴다.
        origin = ("급락 후 반등장" if row.get("bucket")
                  else "상승장" if row.get("wait_days") is not None
                  else "눌림목")
        _keep_better(picked, merged, source=origin)

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
        # 6개월치를 받는다 — 손을 올렸을 때 보여줄 '일봉 6개월' 그림에 쓴다
        # (2026-08-06). 조회 횟수는 그대로이고 기간만 늘어난다.
        daily, _m2 = _download_cached(
            US_INDEX_SYMBOLS, period="6mo", interval="1d", ttl_seconds=600)
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
            # daily_* 는 손을 올렸을 때 펴 보이는 '일봉 6개월' 그림용이다.
            # 기준선은 6개월 전 첫 종가 — 그 뒤로 올랐는지 내렸는지를 본다.
            daily_points = [float(v) for v in closes["Close"].dropna().tolist()]
            result[symbol] = {
                "points": points, "base": base,
                "daily_points": daily_points if len(daily_points) >= 2 else [],
                "daily_base": daily_points[0] if len(daily_points) >= 2 else None,
            }
    return result


# ── 나스닥 고점 대비 낙폭 (2026-08-01) ────────────────────────────────────────
# 왜 이 값인가 — 55년치(1971~)로 재 봤더니, 나스닥이 **고점 대비 얼마나 빠졌나**
# 하나가 다른 어떤 신호보다 잘 들었다.
#
#   2년 뒤 성적(가운데 값 · 100번 중 이긴 횟수) — 아무 날이나 샀으면 +27.5% · 81번
#     8% 빠졌을 때  +18.7% · 72번   ← 기준선보다 **못하다**. 너무 자주 산다.
#    12% 빠졌을 때  +44.7% · 86번   ← 여기부터 확실히 낫다
#    20% 빠졌을 때  +45.8% · 83번
#
# **몇 %가 최적인지는 못 가린다.** 일봉으로 재느냐 주봉으로 재느냐에 따라 10%와 12%의
# 순서가 뒤집혔다(신호가 55년에 17~32번뿐이라 우연에 묻힌다). 그래서 '12% 넘게'까지만
# 말하고 그 안에서 순위를 매기지 않는다.
#
# 재 보고 **버린 것** — MACD 다이버전스(6개 설정 중 0개에서 기준선에 졌다).
# 자세한 것: docs/US_THREE_RULES_COMPARE.md
NASDAQ_DRAWDOWN_GATES = (
    (-20.0, "아주 깊음", "#ff6b6b"),
    (-12.0, "사는 자리", "#44f0a1"),
    (-8.0, "얕음 — 아직 아니다", "#ffd166"),
)
NASDAQ_DRAWDOWN_ENTRY = -12.0      # 실측이 뒷받침하는 문턱


def nasdaq_drawdown_state(pct: float | None) -> tuple[str, str]:
    """낙폭 → (화면에 적을 말, 색). 문턱을 코드 한 곳에서만 정한다."""
    if pct is None:
        return "자료 없음", "#9aa0aa"
    for limit, label, color in NASDAQ_DRAWDOWN_GATES:
        if float(pct) <= limit:
            return label, color
    return "고점 근처", "#9aa0aa"


def get_nasdaq_drawdown(ttl_seconds: float = 600) -> dict:
    """나스닥이 1년 최고에서 얼마나 내려와 있나, 그리고 문턱까지 얼마 남았나."""
    try:
        daily, meta = _download_cached(
            ("^IXIC",), period="1y", interval="1d", ttl_seconds=ttl_seconds)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    frame = daily.get("^IXIC")
    if frame is None or frame.empty:
        return {"ok": False, "error": meta.get("error") or "나스닥 일봉 조회 실패"}
    try:
        close = frame["Close"].dropna().astype(float)
        high = float(close.max())
        current = float(close.iloc[-1])
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    if not high:
        return {"ok": False, "error": "고점을 구할 수 없습니다"}
    pct = (current / high - 1) * 100
    state, color = nasdaq_drawdown_state(pct)
    gates = []
    for limit, label, _c in sorted(NASDAQ_DRAWDOWN_GATES, key=lambda g: -g[0]):
        level = high * (1 + limit / 100)
        gates.append({
            "pct": limit, "label": label, "level": level,
            "gap_pct": (level / current - 1) * 100,
            "reached": pct <= limit,
        })
    return {
        "ok": True, "current": current, "high": high, "drawdown_pct": pct,
        "state": state, "color": color, "entry_pct": NASDAQ_DRAWDOWN_ENTRY,
        "gates": gates, "stale": bool(meta.get("stale")),
    }


def get_etf_sparklines(
    symbols=("SPY", "QQQ"), *, daily_sessions: int = 126, max_points: int = 120
) -> dict:
    """SPY·QQQ의 '당일 분봉 그림'과 '일봉 여섯 달 그림'.

    2026-08-06에 석 달(60거래일) → 여섯 달(126거래일)로 늘렸다(사용자 지시).
    1년치를 이미 받아 두고 있어 조회는 늘지 않는다.

    야후를 새로 부르지 않는다 — 기간·간격을 시장 요약(get_market_overview)이 쓰는
    것과 똑같이 맞춰 두면 _download_cached가 이미 받아 둔 더 큰 묶음에서 잘라 준다.
    분봉은 하루치 1분봉이 900개가 넘어(프리마켓 포함) 그대로 그리면 카드 하나에
    선이 900개 들어간다. 눈으로는 차이가 없으므로 max_points 개로 솎아 그린다.
    """
    wanted = tuple(str(s).strip().upper() for s in symbols if str(s).strip())
    if not wanted:
        return {}
    try:
        intraday, _m1 = _download_cached(
            wanted, period="1d", interval="1m", ttl_seconds=45, prepost=True)
        daily, _m2 = _download_cached(
            wanted, period="1y", interval="1d", ttl_seconds=300)
    except Exception:
        return {}

    def _thin(values: list) -> list:
        if len(values) <= max_points:
            return values
        step = len(values) / max_points
        picked = [values[int(index * step)] for index in range(max_points)]
        picked[-1] = values[-1]  # 마지막 값(현재가)은 반드시 남긴다
        return picked

    result = {}
    for symbol in wanted:
        frame, closes = intraday.get(symbol), daily.get(symbol)
        if closes is None or closes.empty:
            continue
        pair = {}
        if frame is not None and not frame.empty:
            points = [float(v) for v in frame["Close"].dropna().tolist()]
            base = _prior_session_close(closes, pd.Timestamp(frame.index[-1]).date())
            if len(points) >= 2 and base:
                pair["intraday"] = {"points": _thin(points), "base": base}
        day_points = [float(v) for v in closes["Close"].dropna().tolist()][-daily_sessions:]
        if len(day_points) >= 2:
            # 일봉 그림의 기준선은 '그 구간이 시작한 날의 종가'다. 당일 그림처럼
            # 전일 종가를 쓰면 석 달치가 전부 기준선 한쪽에 붙어 색이 의미를 잃는다.
            pair["daily"] = {"points": day_points, "base": day_points[0]}
        if pair:
            result[symbol] = pair
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
