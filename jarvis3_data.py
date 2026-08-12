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
    # 자비스 빅테크10: 매그니피센트7 + Broadcom·Netflix·Oracle.
    # CrowdStrike는 빅테크가 아니라 아래 사이버보안 테마에서만 다룬다.
    {"name": "빅테크10", "etf": "FNGS", "alt_etf": "MAGS", "stocks": ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "NFLX", "ORCL")},
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

# ── 급락 후 반등장 — 상하님 표 2 그대로 (2026-08-12 확정) ────────────────────
# 원본: assets/us_method_drawdown.png · 숫자: docs/US_METHOD_TABLES.md 표 2
#
# **2026-08-07에 내가 -10~-20%로 좁혀 놓았던 것을 되돌린다.** 그때 나스닥 구간·
# 종목 낙폭·보유기간 **세 가지를 한꺼번에 바꿔 놓고** "-6%는 급락이 아니라 흔한
# 조정"이라고 적었다. 2026-08-12에 갈라서 다시 재 보니 진짜 원인은 **보유기간**
# 이었다 — -6%도 1년 들면 가운데 +33.1%다(research/us_crash_timing.py).
# 상하님 표가 맞았고 내가 엉뚱한 것을 범인으로 지목했다.
#
# 이제 **고점 대비 -6% 아래면 전부 본다.** 상하님 표처럼 다섯 칸으로 나눠 보여주되
# 거르지는 않는다. 10년에 그런 날이 710일(전체의 28%)이다.
CRASH_MARKET_BAND = (-100.0, -6.0)
CRASH_MARKET_SYMBOL = "QQQ"

# 상하님 표 2의 다섯 칸. **거르는 조건이 아니라 지금이 어느 칸인지 알려 주는 표**다.
# median/win은 앱 명부 198종목·10년으로 다시 잰 값(1년 보유 · 종목 -30~-50% 기준).
CRASH_MARKET_TIERS = (
    {"band": (-12.0, -6.0), "label": "6~12%", "events": 72, "median_return": 33.1},
    {"band": (-18.0, -12.0), "label": "12~18%", "events": 35, "median_return": 30.7},
    {"band": (-24.0, -18.0), "label": "18~24%", "events": 22, "median_return": 24.6},
    {"band": (-30.0, -24.0), "label": "24~30%", "events": 20, "median_return": 26.6},
    {"band": (-100.0, -30.0), "label": "30% 아래", "events": 10, "median_return": 26.9},
)

# 종목 낙폭 두 칸 — **상하님 표 2에 있던 30~50%를 되살린다.** 2026-08-07에 내가
# 통째로 지웠는데, 1년 보유에서 20~30%보다 5.6%p 더 벌던 자리다.
#
# **파는 날은 규칙에 없다**(2026-08-12 상하님 확정: "파는 시점은 내가 정한다").
# 3개월·6개월·1년 성적을 나란히 적고 고르는 것은 상하님이 하신다.
# 아래 숫자는 새 그물(나스닥 -6% 아래 전부 · 구간에 있는 동안 매일)에서 잰 값이다.
CRASH_HOLD_SPANS = ((60, "3개월"), (120, "6개월"), (250, "1년"))
CRASH_REBOUND_RULES = (
    {"key": "shallow", "band": (-30.0, -20.0), "label": "고점 대비 -20~-30%",
     "results": ({"days": 60, "label": "3개월", "median_return": 7.4, "win_rate": 65.8},
                 {"days": 120, "label": "6개월", "median_return": 13.7, "win_rate": 69.6},
                 {"days": 250, "label": "1년", "median_return": 26.6, "win_rate": 76.7}),
     "sample": 15016},
    {"key": "deep", "band": (-50.0, -30.0), "label": "고점 대비 -30~-50%",
     "results": ({"days": 60, "label": "3개월", "median_return": 8.6, "win_rate": 65.1},
                 {"days": 120, "label": "6개월", "median_return": 14.9, "win_rate": 66.5},
                 {"days": 250, "label": "1년", "median_return": 32.2, "win_rate": 73.1}),
     "sample": 18205},
)

# 실행 중인 프로세스에 옛 모듈이 남아 있는지 화면이 스스로 알아채기 위한 표식이다
# (자비스4와 같은 장치). 계산 결과나 반환 키를 바꾸면 이 숫자를 올린다.
MODULE_REVISION = 2026081260

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


def _freeze_fear_greed(value: dict, now=None) -> dict:
    """장중에는 **전일 마감값**을 보여준다 (2026-08-12 상하님 지시).

    상하님 지적 — "공포탐욕지수도 전날 종가에 마감되고 변동이 없어야 되는데
    조금씩 변동이 생긴다." 맞다. **CNN은 이 지수를 장중 내내 계속 고친다.**
    그 값을 그대로 쓰고 있었으니 화면 숫자가 하루 종일 움직였다.

    CNN 응답에 **previous_close(전일 마감값)가 이미 같이 온다.** 미국장이 끝나기
    전에는 그것을 쓰고, 뉴욕 16:00을 지나면 그날 값이 곧 종가이므로 그대로 쓴다.
    그러면 값이 **하루에 한 번, 마감 때만** 바뀐다.

    실시간 값은 지우지 않고 ``live_score``로 남긴다 — 화면이 참고로 보여줄 수 있고,
    되돌리려면 이 함수만 빼면 된다.
    """
    if not value.get("ok"):
        return value
    live = _finite(value.get("score"))
    frozen = live if us_session_closed(now) else _finite(value.get("previous_close"))
    if frozen is None:                      # 전일값을 못 받았으면 있는 값을 그대로 쓴다
        frozen = live
    out = dict(value)
    out["live_score"] = live
    out["score"] = round(float(frozen), 1)
    out["rating_kr"] = fear_greed_label(float(frozen))
    out["frozen"] = frozen != live
    out["as_of_label"] = "직전 완료 미국장 종가"
    return out


def get_fear_greed(request_json=None) -> dict:
    """CNN 공포·탐욕 지수(0~100)를 조회한다. 실패하면 ok=False 또는 마지막 정상값.

    **돌려주는 score는 직전 완료 미국장의 종가값이다**(`_freeze_fear_greed` 참고).
    얼리는 계산은 캐시 **밖**에서 한다 — 캐시에 넣어 두면 뉴욕 16:00을 지나도
    캐시가 살아 있는 동안 옛 값이 남는다.
    """
    now = time.time()
    with _FEAR_GREED_LOCK:
        cached = _FEAR_GREED_CACHE["value"]
        if cached and now - _FEAR_GREED_CACHE["at"] < _FEAR_GREED_TTL_SECONDS:
            return _freeze_fear_greed(dict(cached))
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
        return _freeze_fear_greed(value)
    except Exception as exc:
        _log.warning("jarvis3 fear&greed fetch failed: %s", exc)
        with _FEAR_GREED_LOCK:
            stale_value = _FEAR_GREED_CACHE["value"]
        if stale_value:
            return _freeze_fear_greed({**stale_value, "stale": True, "error": str(exc)})
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


def us_session_closed(now=None) -> bool:
    """지금 보는 미국장이 **끝난 장**인가 (2026-08-12 상하님 지시).

    상하님 요구 — "시장국면·공포탐욕지수·미국장 시장상태는 전날 종가에 마감되고
    변동이 없어야 한다." 세 곳이 **같은 잣대**로 얼어야 화면이 서로 다른 말을 하지
    않으므로, 판단을 여기 한 곳에 둔다.

    **날짜가 아니라 '그 장이 끝났는가'로 본다.** 뉴욕 16:00을 지났으면 오늘 장은
    끝난 것이고 그 종가가 '직전 완료 장'이다. 그 전이면 어제 종가가 직전이다.
    이렇게 하면 값이 **하루에 한 번, 뉴욕 마감 때만** 바뀐다
    (`_previous_market_regime`이 쓰던 규칙과 같다 — 날짜로 판단하면 뉴욕 자정,
    즉 한국 오후 1~2시에 값이 바뀌어 한국장 한복판에서 흔들린다).
    """
    now_ny = (now or datetime.now(_NY)).astimezone(_NY)
    return now_ny.time() >= dt_time(16, 0)


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


# ── 테마 20개 순위 배점 (2026-08-12 처음 쟀다) ───────────────────────────────
# 그동안 이 배점은 **한 번도 재지 않은 채** 상대강도 55점(20일 30 + 60일 25) ·
# 이동평균 20점 · 확산 15점 · 오른 날 비율 10점으로 돌고 있었다.
#
# 상하님 지적 — "테마가 같이 상승하는 기준이 먼저이고 구성종목 확산이 먼저
# 기준이 되어야지. 테마 수익률이 하락장에는 의미가 없지."
#
# 국면을 갈라 처음 쟀더니(research/us_parts.py) **그 말이 그대로 맞았다.**
#
#   나스닥 200일선 **위** (226,105자리)      나스닥 200일선 **아래** (49,830자리)
#   1. 20일선 위 비율 상위3   최악 -0.5p    1. 5일 오른 비율 상위3   최악  -7.0p
#   2. 20일선 위 비율 상위5        -0.6p    2. 5일 오른 비율 상위5        -8.7p
#   3. 5일 오른 비율 상위5         -1.4p    3. 20일선 위 비율 상위5      -11.2p
#   4. 20일 오른 비율 상위5        -1.6p    4. 20일선 위 비율 상위3      -12.7p
#   …                                       …
#   7. 60일 수익률 상위5  꼴찌    -9.5p    6. 20일 수익률 상위3        -19.9p
#      20일 수익률        탈락                 60일 수익률              탈락
#
# **두 국면 모두 확산 계열이 1~4등을 독차지했고 수익률 계열은 꼴찌거나 탈락이었다.**
# 그래서 상대강도 55점과 이동평균 20점을 0으로 빼고 확산으로 옮긴다.
#
# 여기서는 **등수 대신 그 등수를 만드는 값**에 점수를 준다. '상위 3등 안인가'로
# 점수를 주면 순위를 매기려고 순위가 필요해진다(순환). 값이 높을수록 등수가
# 높으므로 결과는 같다.
THEME_SCORE_WEIGHTS = {
    "above20": 40.0,     # 구성종목 중 20일선 위 비율
    "rose5": 30.0,       # 구성종목 중 최근 5일에 오른 비율
    "rose20": 20.0,      # 구성종목 중 최근 20일에 오른 비율
    "less_drop": 10.0,   # 구성종목 평균 고점 대비 (덜 빠졌을수록 높다)
    "relative": 0.0,     # 20·60일 상대강도 — 두 국면 다 꼴찌거나 탈락
    "trend": 0.0,        # ETF 20·50일선 위 — 다른 파트에서 거꾸로
}
THEME_SCORE_MAX = round(sum(THEME_SCORE_WEIGHTS.values()), 1)
THEME_STATUS_LEAD = round(THEME_SCORE_MAX * 0.75, 1)
THEME_STATUS_WATCH = round(THEME_SCORE_MAX * 0.60, 1)


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
        # 구성종목을 하나씩 보고 **몇 %가 그런가**를 센다. 테마 점수의 90점이
        # 여기서 나온다 — 실측에서 확산 계열이 두 국면 모두 1~4등이었다.
        above20, rose5, rose20, from_highs = [], [], [], []
        for ticker in theme["stocks"]:
            stock = _series_metrics(daily.get(ticker))
            if not stock.get("ok"):
                continue
            if stock.get("sma20"):
                above20.append(stock["current"] > stock["sma20"])
            if stock.get("ret5") is not None:
                rose5.append(stock["ret5"] > 0)
            if stock.get("ret20") is not None:
                rose20.append(stock["ret20"] > 0)
            if stock.get("from_high_pct") is not None:
                from_highs.append(float(stock["from_high_pct"]))

        def _share(flags):
            return (sum(flags) / len(flags) * 100) if flags else None

        breadth = _share(above20)
        rose5_share = _share(rose5)
        rose20_share = _share(rose20)
        less_drop = (sum(from_highs) / len(from_highs)) if from_highs else None
        rs20 = metrics["ret20"] - spy["ret20"]
        rs60 = metrics["ret60"] - spy["ret60"] if spy.get("ret60") is not None else None
        score = round(
            _scale(breadth, 25, 85, THEME_SCORE_WEIGHTS["above20"])
            + _scale(rose5_share, 20, 80, THEME_SCORE_WEIGHTS["rose5"])
            + _scale(rose20_share, 25, 85, THEME_SCORE_WEIGHTS["rose20"])
            + _scale(less_drop, -30.0, -2.0, THEME_SCORE_WEIGHTS["less_drop"]),
            1,
        )
        status = ("주도" if score >= THEME_STATUS_LEAD
                  else "관찰" if score >= THEME_STATUS_WATCH else "약함")
        rows.append({
            "name": theme["name"],
            "etf": etf_used,
            "alt_etf": theme["alt_etf"],
            "ok": True,
            "score": score,
            "status": status,
            "change_pct": metrics.get("change_pct"),
            # 상대강도는 **점수에 안 쓴다**(위 THEME_SCORE_WEIGHTS 참고). 다만
            # 화면이 참고로 보여주고 있어 값 자체는 그대로 실어 보낸다.
            "rs20": rs20,
            "rs60": rs60,
            "breadth": breadth,
            "rose5_share": rose5_share,
            "rose20_share": rose20_share,
            "theme_from_high": less_drop,
            "source_time": metrics.get("source_time"),
            # 점수의 근거를 그대로 적는다 — 화면 숫자와 배점이 어긋나면 안 된다.
            "basis": (
                f"20일선 위 {breadth:.0f}% · 5일 오른 종목 {rose5_share:.0f}% · "
                f"20일 오른 종목 {rose20_share:.0f}% · 고점 대비 {less_drop:+.1f}%"
                if None not in (breadth, rose5_share, rose20_share, less_drop)
                else "자료 일부 부족"),
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
# ── 여기서부터는 **옛 기록**이다(2026-08-05 기준). 지금 배점이 아니다. ──────
# 2026-08-07에 그물을 격자로 다시 잡고 배점도 두 번 다시 쟀다. 지금 값은 아래
# CRASH_SCORE_WEIGHTS를 보라 — 테마 동반 30 / 테마 등수 25 / 변동성 22.5 /
# 유동성 22.5이고, 최근 11일과 낙폭 갈래는 0점이 됐다.
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
# 2026-08-07: '테마 등수' 25점을 새로 넣고 나머지를 비례해 줄였다(40/30/30 → 30/22.5/22.5).
# 테마 60일 수익률 상위 5등은 창 80 / 95 / 100%로 통과했고 최악의 창에서도 -0.0p였다
# — 통과한 후보 중 최악값이 가장 좋았다(`research/us_theme_rank.py`).
# ── 2026-08-12 새 그물에서 다시 쟀다 — 위 기록은 전부 **옛것**이다 ────────────
# 그물을 상하님 표 2로 되돌렸으므로(나스닥 -6% 아래 전부 · 구간에 있는 동안 매일 ·
# 종목 -20~-30%와 -30~-50% 둘 다) 배점도 그 위에서 다시 잰다(기준 7).
# 그물이 29배로 커졌다 — 옛 그물 1,202자리 → 새 그물 34,710자리.
# 측정: research/us_crash_new_net.py
#
# **파는 시점을 앱이 정하지 않으므로** 보유 60·120·250일 셋 다 재고, **여러 기간에서
# 살아남은 항목만** 쓴다. 보유가 바뀌면 뒤집히는 항목이 14개나 나왔다 —
# '최근 11일 -10%↑ 빠짐'은 3개월 1등(-5.8p)인데 1년에서는 거의 거꾸로(-19.7p)다.
#
#   테마 덜 빠졌나 상위 5등     3개월 3등 · 6개월 3등 · 1년 1등  ← 셋 다. 유일하다
#   테마 5일 오른 비율 상위 5등   6개월 1등 · 1년 6등             ← 둘
#   테마 20일선 위 비율 상위 5등  6개월 2등 · 1년 8등             ← 둘
#   최근 11일 -10%↑ 빠짐       3개월 1등 · 1년 △(거의 거꾸로)   ← 안 쓴다
#   같은 테마 동반 4개↑ · 5개↑   1년만 · 해당 67%·47%           ← 안 쓴다
#
# **종목 항목은 전멸이다.** 변동성 3·4·6%, 거래대금 5억달러↑·상위 절반, 60일 등락,
# 종목 낙폭 두 칸 — 아홉 개가 세 보유 다 미달이다. **미국은 테마로만 고를 수 있다.**
#
# 같은 테마 동반 30점은 뺀다 — 2026-08-09에 명부에서 종목 하나(CRWD→ORCL)를 바꾼
# 뒤로 옛 그물에서도 이미 불합격이었고(80/95 → 64/93), 새 그물에서는 1년 보유에만
# 걸리는 데다 해당이 67%라 못 가른다(기준 6).
CRASH_SCORE_WEIGHTS = {
    "less_drop": 40.0,     # 테마 덜 빠졌나 상위 5등 — 세 보유기간 모두 합격
    "spread5": 30.0,       # 테마 5일 오른 종목 비율 상위 5등 (확산)
    "above20": 20.0,       # 테마 20일선 위 종목 비율 상위 5등 (확산)
    "together": 0.0,       # 명부 교체 뒤 불합격 · 새 그물에서 해당 67%라 못 가름
    "theme_rank": 0.0,     # 테마 60일 수익률 — 6개월에서만 합격
    "recent_drop": 0.0,    # 보유기간마다 뒤집힌다
    "volatility": 0.0,     # 세 보유 다 미달
    "liquidity": 0.0,      # 세 보유 다 미달
    "bucket": 0.0,         # 그물이 이미 쓴 값 · 두 칸 다 미달
}
CRASH_SCORE_MAX = round(sum(CRASH_SCORE_WEIGHTS.values()), 1)
# '덜 빠졌나'는 급락에서 상위 5등이라야 붙는다(상위 3등은 해당 7%로 못 가름).
CRASH_LESS_DROP_TOP_N = 5
CRASH_SPREAD_TOP_N = 5
CRASH_STATE_GOOD = round(CRASH_SCORE_MAX * 0.70, 1)
CRASH_STATE_FAIR = round(CRASH_SCORE_MAX * 0.50, 1)
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


def _theme_rank_part(row: dict, label: str, prefix: str, points: float) -> tuple:
    """테마 등수 한 줄 — '어느 테마가 몇 등인가'를 사람 말로 적는다."""
    rank = row.get(prefix)
    total = int(row.get(f"{prefix}_total") or 0)
    return (label,
            points if row.get(f"{prefix}_top") else 0.0,
            points,
            "모름" if not rank else
            f"{row.get(f'{prefix}_name') or '테마'} {int(rank)}등"
            + (f" / {total}개" if total else ""))


def crash_rebound_score(row: dict) -> dict:
    """급락 후 반등장 후보의 점수(90점 만점)와 근거를 낸다.

    **0점 항목은 parts에 넣지 않는다**(CLAUDE.md 0-1 마). 계산은 위
    CRASH_SCORE_WEIGHTS에 0으로 남아 있어 다시 재서 되살릴 수 있다.
    """
    weights = CRASH_SCORE_WEIGHTS
    parts = [
        _theme_rank_part(row, f"테마가 덜 빠졌나 (상위 {CRASH_LESS_DROP_TOP_N}등)",
                         "theme_less_drop", weights["less_drop"]),
        _theme_rank_part(row, f"테마가 같이 오르는가 (상위 {CRASH_SPREAD_TOP_N}등)",
                         "theme_spread5", weights["spread5"]),
        _theme_rank_part(row, f"테마가 20일선 위에 있나 (상위 {CRASH_SPREAD_TOP_N}등)",
                         "theme_above20", weights["above20"]),
    ]
    return {"score": round(sum(v for _n, v, _m, _t in parts), 1),
            "parts": parts, "max": CRASH_SCORE_MAX}


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
# **눌린 폭 15점을 0점으로 뺐다 (2026-08-09 상하님 지적).**
# 상하님 말씀 — "고점 돌파 후 며칠 눌리고 몇 % 눌린 뒤 사는 게 기준인데, 그 눌린
# 폭이 점수에 또 들어가는 게 맞나?" 맞지 않는다. 이유가 둘이다.
#   ① **그물이 이미 쓴 값이다.** 4~15%로 걸러 놓고 그 안에서 다시 '더 눌린 쪽'에
#      만점을 준다. 설명서 어디에도 "더 눌릴수록 좋다"는 말이 없다.
#   ② **앞뒤 5년으로 갈라 재니 뒤 절반에서 거꾸로였다**(앞 +3.9 / 뒤 -1.2%p).
#      같은 이유로 이미 0점 처리한 항목이 둘 있다(최근 60일 상승폭 +3.0/-0.5,
#      거래대금 연속 -2.2/0.0). 눌린 폭이 그 둘보다 나쁜데 혼자 살아남아 있었다.
# **미국 급락 배점에서는 같은 이유로 이미 뺐다**(CRASH_SCORE_WEIGHTS의 bucket 0.0).
# 상승장만 2026-08-06판 그대로 남아 있었다.
#
# 뺀 15점은 **새 항목을 만들지 않고 남은 넷에 비례해 나눈다** — 2026-08-07에 미국
# 조건점수에서 추세 20점을 뺄 때 쓴 방식 그대로다(LEADER_RESCALE). 옮길 데를
# 지어내지 않기 위해서다. 테마 등수를 넣자는 생각이 먼저 들지만, 그건 미국 급락·
# 한국 두 갈래에서만 쟀고 **미국 상승장에서는 아직 안 쟀다.**
# ── 2026-08-12 전면 재측정 — 위 기록은 전부 **옛것**이다 ─────────────────────
# 상하님 지시로 `research/us_breakout_ladder.py`를 새로 짜서 **앱 그물 그대로**
# (신고가 뒤 1~5일 · −4~−15% · 시장 조건 안 봄) 다시 쟀다. 그전 측정은 그물에
# 시장 조건까지 넣고 걸러서 앱과 다른 모집단을 잰 것이었다.
#
# **파는 시점을 앱이 정하지 않기로 했으므로**(상하님 확정) 보유 60·120·250일 셋 다
# 재고, **세 기간 모두 합격한 항목만** 쓴다. 한 기간에서만 통하는 값은 보유가
# 바뀌면 뒤집힌다 — 실제로 '같은 테마 동반 4개↑'는 6개월에서만, '테마 60일
# 수익률'은 3개월에서만 합격했다. 그런 것은 안 쓴다.
#
#   후보                       3개월      6개월      1년      판정
#   눌린 폭 10~15%              ○ −7.0    ○ −8.9    ○ −6.1   ← 셋 다 합격. 유일하다
#   테마 5일 오른 비율 상위5등     △        ○ −0.4    ○ −4.7   ← 둘
#   테마 덜 빠졌나 상위3등        ○ −7.5    ○ −6.7    △        ← 둘
#   같은 테마 동반 4개↑          △        ○ −9.5    △        ← 하나. 안 쓴다
#   테마 60일 수익률 상위5등      ○ −6.4    △        △        ← 하나. 안 쓴다
#   눌린 폭 6~10%              ✗ 거꾸로   ✗ 거꾸로   △        ← 0점
#   거래대금 5억달러↑            ✗ 거꾸로   △        △        ← 0점
#   최근 11일·변동성·신고가 뒤 며칠   전부 △              ← 0점
#
# **최근 11일 29.4점과 테마 동반 47.0점은 뺀다.** 둘 다 이 그물에서 합격이 아니다.
# 47.0은 2026-08-09에 눌린 폭 15점을 빼고 남은 넷에 비례로 나눈 뒤 반올림 잔돈까지
# 얹은 값이었다 — 잰 값이 아니다(CLAUDE.md 0-1 마: 비례 배분 금지).
#
# **눌린 폭이 1등으로 돌아왔다.** 상하님이 2026-08-09에 "그물이 이미 쓴 값"이라고
# 지적하셔서 0점으로 뺐던 항목인데, 앱 그물 안에서 다시 재니 확실히 갈렸다
# (1년 기준 10~15% 칸 27.8% · 4~6% 칸 14.7% · 아무 종목이나 14.1%).
# 그물이 쓴 값이라도 **그 안에서 다시 재서 갈리면 점수를 준다**(KR_THEME_SPEC 1부 부칙).
#
# 합이 100이 안 되므로 **90점 만점**이라고 화면에 적는다(CLAUDE.md 0-1 마).
BREAKOUT_SCORE_WEIGHTS = {
    "drop": 40.0,          # 눌린 폭 10~15% — 세 보유기간 모두 합격한 유일한 항목
    "spread5": 30.0,       # 테마 5일 오른 종목 비율 상위 5등 (확산)
    "less_drop": 20.0,     # 테마 덜 빠졌나 상위 3등
    "together": 0.0,       # 이 그물에서 불합격 (4개↑는 6개월에서만)
    "recent_drop": 0.0,    # 이 그물에서 불합격
    "liquidity": 0.0,      # 3개월에서 거꾸로
    "volatility": 0.0,     # 전부 미달
}
BREAKOUT_SCORE_MAX = round(sum(BREAKOUT_SCORE_WEIGHTS.values()), 1)
# 눌린 폭은 **칸으로 가른다** — 실측이 10~15%만 합격이고 6~10%는 거꾸로였다.
# 비례로 깎으면 거꾸로인 구간에도 점수가 붙는다.
BREAKOUT_DROP_BAND = (-15.0, -10.0)
# 이름표 문턱도 만점이 100 → 90으로 바뀐 만큼 같이 내린다(뜻은 그대로).
BREAKOUT_STATE_GOOD = round(BREAKOUT_SCORE_MAX * 0.70, 1)
BREAKOUT_STATE_FAIR = round(BREAKOUT_SCORE_MAX * 0.50, 1)


def breakout_score(row: dict) -> dict:
    """상승장(신고가 눌림매수) 후보의 점수(90점 만점)와 근거.

    **0점 항목은 parts에 넣지 않는다**(CLAUDE.md 0-1 마). 0점은 기준이 아니라서
    화면 배점표에 "0.0 (0.0)" 줄로 뜨면 상하님이 읽을 것이 없다. 계산은 위
    BREAKOUT_SCORE_WEIGHTS에 0으로 남아 있어 다시 재서 되살릴 수 있다.
    """
    metrics = row.get("metrics") or {}
    weights = BREAKOUT_SCORE_WEIGHTS
    parts = []

    # ① 눌린 폭 — 세 보유기간 모두 합격한 유일한 항목. 칸으로 가른다.
    low, high = BREAKOUT_DROP_BAND
    drop = metrics.get("from_high_pct")
    inside = drop is not None and low <= float(drop) <= high
    parts.append((
        "눌린 폭 10~15%",
        weights["drop"] if inside else 0.0,
        weights["drop"],
        "—" if drop is None else f"{float(drop):+.1f}%"
        + ("" if inside else " (10~15%가 아님)")))

    # ② 테마 확산 — 그 테마 종목 중 몇 %가 최근 5일에 올랐나, 그 등수.
    spread_rank = row.get("theme_spread5")
    parts.append((
        f"테마가 같이 오르는가 (상위 {THEME_RANK_TOP_N}등)",
        weights["spread5"] if row.get("theme_spread5_top") else 0.0,
        weights["spread5"],
        "모름" if not spread_rank else
        f"{row.get('theme_spread5_name') or '테마'} {int(spread_rank)}등"
        + (f" / {int(row['theme_spread5_total'])}개" if row.get("theme_spread5_total") else "")))

    # ③ 테마가 덜 빠졌나 — 상위 3등. 급락 갈래에서도 가장 센 항목이다.
    less_rank = row.get("theme_less_drop")
    parts.append((
        f"테마가 덜 빠졌나 (상위 {THEME_LESS_DROP_TOP_N}등)",
        weights["less_drop"] if row.get("theme_less_drop_top") else 0.0,
        weights["less_drop"],
        "모름" if not less_rank else
        f"{row.get('theme_less_drop_name') or '테마'} {int(less_rank)}등"
        + (f" / {int(row['theme_less_drop_total'])}개" if row.get("theme_less_drop_total") else "")))

    return {"score": round(sum(v for _n, v, _m, _t in parts), 1),
            "parts": parts, "max": BREAKOUT_SCORE_MAX}


# 상하님 표 1의 성적 — 신고가 뒤 1~5일 · 10~15% 눌림 자리를 보유기간별로 잰 값
# (2026-08-12 `research/us_grid.py`, 앱 명부 198종목 10년). **앱은 파는 시점을
# 정하지 않는다**(상하님 확정). 셋을 나란히 보여주고 고르는 것은 상하님이 하신다.
BREAKOUT_HOLD_RESULTS = (
    {"days": 60, "label": "3개월", "median_return": 3.0, "win_rate": 54.8},
    {"days": 120, "label": "6개월", "median_return": 9.7, "win_rate": 62.8},
    {"days": 250, "label": "1년", "median_return": 27.6, "win_rate": 68.3},
)


def breakout_plan(row: dict) -> dict:
    """상승장(신고가 눌림매수)의 매수 심사 결과.

    **넘어야 할 기준가도, 손절가도, 파는 날도 규칙에 없다.** 종가를 확인하고 다음
    거래일 시가에 산다. **파는 시점은 앱이 정하지 않는다**(2026-08-12 상하님 확정:
    "파는 시점은 내가 정한다"). 대신 그 자리의 3개월·6개월·1년 과거 성적을 나란히
    보여준다 — 상하님 표 1이 원래 그 모양이다.
    """
    metrics = row.get("metrics") or {}
    score = float(breakout_score(row)["score"])
    if score >= BREAKOUT_STATE_GOOD:
        state, recommendation = "규칙에 맞는 자리", "조건부 후보"
    elif score >= BREAKOUT_STATE_FAIR:
        state, recommendation = "자리는 맞으나 근거가 얇음", "관찰"
    else:
        state, recommendation = "규칙만 맞고 뒷받침이 없음", "관찰"
    spans = " · ".join(
        f"{item['label']} {item['median_return']:+.1f}%(100번 중 {item['win_rate']:.0f}번)"
        for item in BREAKOUT_HOLD_RESULTS
    )
    return {
        "state": state,
        "recommendation": recommendation,
        "rule_mode": "breakout",
        "entry": "다음 거래일 시가",
        # 파는 날을 규칙으로 못박지 않는다. 화면이 '며칠 뒤에 판다'고 적으면
        # 앱이 매매를 지시하는 것이 된다(CLAUDE.md 0-1 바).
        "hold_days": None,
        "hold_results": BREAKOUT_HOLD_RESULTS,
        "current": metrics.get("current"),
        "invalidation": None,
        "target": None,
        "buy_reason": (
            f"52주 신고가를 찍고 {int(row.get('wait_days') or 0)}거래일이 지나 "
            f"고점 대비 {metrics.get('from_high_pct', 0):.1f}%까지 눌린 자리입니다. "
            f"규칙대로라면 오늘 종가를 확인하고 다음 거래일 시가에 삽니다. "
            f"**파는 시점은 규칙에 없습니다** — 이 자리의 과거 성적은 {spans}였습니다. "
            f"이 규칙에는 손절가가 없습니다."
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
    score = float(crash_rebound_score(row)["score"])
    if score >= CRASH_STATE_GOOD:
        state, recommendation = "규칙에 맞는 자리", "조건부 후보"
    elif score >= CRASH_STATE_FAIR:
        state, recommendation = "자리는 맞으나 근거가 얇음", "관찰"
    else:
        state, recommendation = "규칙만 맞고 뒷받침이 없음", "관찰"
    results = row.get("hold_results") or ()
    spans = " · ".join(
        f"{item['label']} {item['median_return']:+.1f}%(100번 중 {item['win_rate']:.0f}번)"
        for item in results
    )
    return {
        "state": state,
        "recommendation": recommendation,
        "rule_mode": "crash",
        "entry": "다음 거래일 시가",
        # 파는 날을 규칙으로 못박지 않는다(2026-08-12 상하님 확정).
        "hold_days": None,
        "hold_results": results,
        "current": metrics.get("current"),
        "invalidation": None,     # 이 규칙에는 손절이 없다
        "target": None,           # 목표가도 없다
        "buy_reason": (
            _crash_drop_story(row, metrics)
            + " 규칙대로라면 오늘 종가를 확인하고 다음 거래일 시가에 삽니다."
            + (f" **파는 시점은 규칙에 없습니다** — 이 자리의 과거 성적은 {spans}였습니다."
               if spans else "")
            + " 이 규칙에는 손절가가 없습니다."
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


THEME_RANK_MIN_MEMBERS = 3
THEME_RANK_TOP_N = 5
# '테마가 덜 빠졌나'는 상위 3등이라야 붙는다(2026-08-12 실측 — 상위 5등은 미달).
THEME_LESS_DROP_TOP_N = 3


def _rose_5d(metrics: dict) -> float | None:
    """이 종목이 최근 5일에 올랐나 — 오르면 100, 아니면 0.

    테마별로 평균 내면 곧 **'그 테마 구성종목 중 몇 %가 5일간 올랐나'**(확산)가 된다.
    2026-08-12 실측에서 미국 두 갈래·테마 순위 모두 이 확산이 가장 잘 갈랐다
    (상승장 그물에서 최악 −0.4p로 전 항목 중 1등, `research/us_parts.py`).
    """
    value = (metrics or {}).get("ret5")
    return None if value is None else (100.0 if float(value) > 0 else 0.0)


def _above_sma20(metrics: dict) -> float | None:
    """이 종목이 20일선 위인가 — 위면 100, 아니면 0. 테마별 평균이 곧 확산이다."""
    current, sma20 = (metrics or {}).get("current"), (metrics or {}).get("sma20")
    if not current or not sma20:
        return None
    return 100.0 if float(current) > float(sma20) else 0.0


def _attach_theme_rank(rows: list, memberships: dict, all_metrics: dict,
                       metric_key: str = "ret60", top_n: int = THEME_RANK_TOP_N,
                       *, prefix: str = "theme_rank", derive=None) -> None:
    """이 종목이 속한 테마가 **오늘 몇 등인지** 각 줄에 적는다 (2026-08-07 도입).

    왜 넣나 — 지금까지 배점은 종목 하나만 봤다. 그런데 실측에서 **테마 자체의
    등수**가 종목 항목 대부분보다 잘 들었다. 미국 급락 그물에서 '테마 60일 수익률
    상위 5등'은 창 80 / 95 / 100%로 통과했고 최악의 창에서도 손해가 0.0p였다
    (`research/us_theme_rank.py`). 종목의 이동평균·상대강도가 전부 거꾸로로 나온
    것과 대비된다 — **고를 게 있다면 종목이 아니라 테마 쪽**이라는 뜻이다.

    등수는 **명부 전체**로 매긴다. 표에 걸린 종목만으로 매기면 그날 몇 종목이
    걸렸느냐에 따라 등수가 출렁인다. 구성종목이 3개 미만인 테마는 평균이 한두
    종목에 휘둘리므로 등수에서 뺀다.

    `metric_key`는 무엇으로 줄 세울지다 — 미국 급락은 `ret60`(60일 수익률),
    한국 급락은 `from_high_pct`('덜 빠졌나')를 쓴다. 시장마다 실측 결과가 갈렸다.

    한 줄에 **등수를 여럿** 달 수 있다 — `prefix`를 바꿔 부르면 된다. 미국 상승장은
    '5일간 오른 종목 비율'과 '덜 빠졌나' 두 등수를 같이 쓴다(2026-08-12 실측).
    `derive`를 주면 metrics에서 그 함수로 값을 뽑는다(`_rose_5d`처럼 계산이 필요한 값).
    """
    totals: dict[str, list] = {}
    for ticker, metrics in (all_metrics or {}).items():
        value = derive(metrics) if derive else (metrics or {}).get(metric_key)
        if value is None:
            continue
        for name in memberships.get(ticker) or []:
            totals.setdefault(name, []).append(float(value))

    averages = {name: sum(values) / len(values)
                for name, values in totals.items()
                if len(values) >= THEME_RANK_MIN_MEMBERS}
    order = sorted(averages, key=lambda name: -averages[name])
    place = {name: index + 1 for index, name in enumerate(order)}

    for row in rows:
        places = [place[name] for name in (row.get("themes") or []) if name in place]
        best = min(places) if places else None
        row[prefix] = best
        row[f"{prefix}_total"] = len(order)
        row[f"{prefix}_top"] = bool(best is not None and best <= top_n)
        row[f"{prefix}_name"] = (
            next((name for name in (row.get("themes") or []) if place.get(name) == best), "")
            if best else "")


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
    """설명서 1번 — 정상 상승장의 '신고가 눌림매수' 자리를 찾는다.

    **50일선·200일선은 보지 않는다** — 상하님 표 1의 규칙은 '52주 신고가 돌파 →
    며칠 기다림 → 그 고점에서 얼마나 눌린 날 종가 확인'뿐이고 이동평균 조건은
    없다. 여기에 없는 조건을 더하면 화면이 설명과 다른 것을 찾게 된다.

    **그물은 넓게 둔다**(2026-08-06 상하님 결정) — 표 1의 매수 자리(10~15%)만
    거르게 했더니 화면이 매일 비었다(1년에 30번). "넓게 찾고 좋은 자리에 별을
    달아라. 고르는 것은 내가 한다." 지금은 별 대신 배점이 그 일을 한다 —
    눌린 폭 10~15%가 40점으로 1등이라 그 자리가 맨 위로 온다.

    차례는 **점수 순**이다(BREAKOUT_SCORE_WEIGHTS). 같은 점수 안에서만
    _breakout_rank_key(테마 동반 → 60일 → 거래대금)로 가른다.
    """
    daily, meta, memberships = _universe_daily(reuse_only)
    if not daily:
        return {"ok": False, "error": meta.get("error") or "미국 종목 일봉 조회 실패", "rows": []}

    wait_min, wait_max = BREAKOUT_PULLBACK_RULE["wait_days"]
    drop_low, drop_high = BREAKOUT_PULLBACK_RULE["drop_band"]
    rows, window_count = [], 0
    # 테마 등수는 **명부 전체**로 매긴다(걸린 종목만 쓰면 그날 몇 개 걸렸느냐로
    # 출렁인다). 새 자료를 받지 않는다 — 어차피 전 종목을 훑고 있으니 모아만 둔다.
    all_metrics: dict[str, dict] = {}
    for ticker in US_LARGE_CAP_UNIVERSE:
        metrics = _series_metrics(daily.get(ticker))
        if not metrics.get("ok"):
            continue
        all_metrics[ticker] = metrics
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
    # 테마 동반은 배점에서 빠졌지만 **같은 점수 안의 차례**를 가르는 데 계속 쓴다
    # (_breakout_rank_key). 그래서 여기서 세어 둔다.
    _attach_theme_together(rows, memberships)
    # 배점의 30점·20점이 테마 등수다. 점수를 내기 **전에** 달아 둬야 한다.
    _attach_theme_rank(rows, memberships, all_metrics, prefix="theme_spread5",
                       top_n=THEME_RANK_TOP_N, derive=_rose_5d)
    _attach_theme_rank(rows, memberships, all_metrics, prefix="theme_less_drop",
                       metric_key="from_high_pct", top_n=THEME_LESS_DROP_TOP_N)
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
    # 테마 등수는 **명부 전체**로 매긴다 — 표에 걸린 종목만 쓰면 그날 몇 개가
    # 걸렸느냐에 따라 등수가 출렁인다. 어차피 아래 반복문이 전 종목 지표를 낸다.
    all_metrics: dict[str, dict] = {}
    counts = {rule["key"]: 0 for rule in CRASH_REBOUND_RULES}
    for ticker in US_LARGE_CAP_UNIVERSE:
        metrics = _series_metrics(daily.get(ticker))
        if not metrics.get("ok"):
            continue
        all_metrics[ticker] = metrics
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
                # 파는 날은 규칙에 없다(2026-08-12 상하님 확정). 대신 3개월·6개월·
                # 1년 성적을 그대로 실어 화면이 셋을 나란히 보여준다.
                row["hold_days"] = None
                row["hold_results"] = rule["results"]
                row["sample"] = rule["sample"]
                row["volume_streak"] = volume_streak_days(daily.get(ticker))
                row["recent_gain_pct"] = recent_gain_pct(daily.get(ticker))
                row["_order"] = order
                rows.append(row)
                break
    # 테마 동반·테마 등수가 배점의 55점이므로 점수를 내기 **전에** 붙여 둬야 한다.
    _attach_theme_together(rows, memberships)
    # 배점 셋이 전부 테마 등수다(2026-08-12 새 그물 실측 — 종목 항목은 전멸).
    _attach_theme_rank(rows, memberships, all_metrics, prefix="theme_less_drop",
                       metric_key="from_high_pct", top_n=CRASH_LESS_DROP_TOP_N)
    _attach_theme_rank(rows, memberships, all_metrics, prefix="theme_spread5",
                       top_n=CRASH_SPREAD_TOP_N, derive=_rose_5d)
    _attach_theme_rank(rows, memberships, all_metrics, prefix="theme_above20",
                       top_n=CRASH_SPREAD_TOP_N, derive=_above_sma20)
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


# '매수심사결과 높은 순위 9' — **자리 배분**으로 뽑는다 (2026-08-12 상하님 지시).
# "대장주 3개 상승장 3개 급락 3개씩 해라. 급락하는 시장에서는 상승장이 없잖아.
#  없으면 없는 대로 하면 돼. 그 대신 설명을 해야겠지."
#
# 그전에는 셋을 섞어 조건점수 하나로 다시 재서 7개를 뽑았는데, 그 조건점수는
# 일곱 항목이 전부 검증 실패였다(2026-08-07 · 375,234자리). 각 갈래가 제 자로
# 잰 점수를 버리고 근거 없는 자로 다시 재는 구조였다.
TOP_REVIEW_SLOTS = {"leader": 3, "breakout": 3, "crash": 3}
TOP_REVIEW_LIMIT = sum(TOP_REVIEW_SLOTS.values())

# 지금 시세로 다시 재 볼 후보 수. 종가 순위 30위 밖에서 최종 순위 안으로 들어오려면
# 하루 만에 스물몇 계단을 올라와야 한다(2026-07-31 실측). 157종목 전부 분봉을
# 받으면 3.7초, 종가만이면 0.3초였다.
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
        # 갈래(상승장·급락)에서 온 줄은 **그 갈래 점수를 그대로 둔다**(2026-08-12).
        # 예전에는 여기서 조건점수로 다시 쟀는데, 그 조건점수는 375,234자리로 재 보니
        # 일곱 항목이 전부 검증 실패였다(20·50일선 위는 거꾸로). 각 갈래가 제 자로
        # 잰 점수를 버리고 근거 없는 자로 다시 재는 구조였다.
        merged = dict(row)
        origin = ("급락 후 반등장" if row.get("bucket")
                  else "상승장" if row.get("wait_days") is not None
                  else "눌림목")
        _keep_better(picked, merged, source=origin)

    # **대장주는 종목 조건점수가 아니라 테마 순위로 줄 세운다**(2026-08-12).
    # 조건점수는 합격 항목이 하나도 없고, 테마 등수는 세 그물에서 다 통과한
    # 유일한 항목이다. 테마 1위의 대장주가 맨 위로 온다.
    theme_place = {name: index for index, name in enumerate(
        [str(r.get("name") or "") for r in sorted(
            theme_rows or [], key=lambda r: float(r.get("score") or 0), reverse=True)])}

    def _order(item):
        places = [theme_place[name] for name in (item.get("sources") or [])
                  if name in theme_place]
        return (min(places) if places else len(theme_place),
                -float(item.get("score") or 0))

    ranked = sorted(picked.values(), key=_order)
    # 상위 후보 몇 개만 지금 시세로 다시 재고 그 안에서 최종 차례를 낸다 —
    # 157종목 전부 분봉을 받던 것을 없앤다.
    _refine_top_with_live(ranked[:TOP_REVIEW_REFINE], market_score=market_score)
    rows = sorted(ranked[:TOP_REVIEW_REFINE], key=_order)[: max(1, int(limit))]
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
