"""market_data.py — 자비스2 신규 페이지 전용 일봉 조회 및 기술 지표 계산 모듈.

기존 price_data.py(성과검증·스냅샷 전용)는 일체 수정하지 않는다.
이 모듈은 P1 엔진 전용이며 앱의 저장/판정/DB 로직에는 연결하지 않는다.
모든 함수는 네트워크·파싱 실패 시 예외 대신 None을 반환한다.
"""

import json
import logging
import time
import warnings
from datetime import datetime
from pathlib import Path

import pandas as pd

_log = logging.getLogger(__name__)

_CACHE_DIR = Path(__file__).parent / "cache" / "market_data"
_KOSPI_INDEX = "^KS11"

# 프로세스 메모리 캐시 — 파일 캐시가 있어도 rerun마다 JSON 300행을 재파싱하면
# 화면당 수십 ms씩 누적된다. {key: (yyyy-mm-dd, df)}
_MEM_CACHE: dict = {}


# ── 내부 헬퍼 ──────────────────────────────────────────────────────────────────


def _cache_path(code6: str) -> Path:
    return _CACHE_DIR / f"daily_{code6}.json"


def _load_cache(code6: str):
    p = _cache_path(code6)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("date") != datetime.now().strftime("%Y-%m-%d"):
            return None
        records = data.get("records")
        if not records:
            return None
        df = pd.DataFrame(records)
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")
        return df
    except Exception as e:
        _log.debug("cache load failed %s: %s", code6, e)
        return None


def _save_cache(code6: str, df: pd.DataFrame) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p = _cache_path(code6)
    try:
        records = df.copy().reset_index()
        records.columns = [str(c) for c in records.columns]
        # DatetimeIndex → 문자열
        for col in records.columns:
            if pd.api.types.is_datetime64_any_dtype(records[col]):
                records[col] = records[col].dt.strftime("%Y-%m-%d")
        data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "records": records.to_dict(orient="records"),
        }
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        _log.debug("cache save failed %s: %s", code6, e)


def _download_yf(ticker: str, period: str = "300d"):
    """yfinance로 일봉 다운로드. 실패 시 None."""
    try:
        import yfinance as yf

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        required = {"Open", "High", "Low", "Close", "Volume"}
        if not required.issubset(df.columns):
            return None
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        df.index = df.index.normalize()
        return df[list(required)]
    except Exception as e:
        _log.debug("yf download failed %s: %s", ticker, e)
        return None


def _clean_ohlcv(df):
    """Close/High가 NaN인 행(장중 미확정 행 등) 제거.

    yfinance가 당일 장중 행을 High/Close=NaN, Volume만 채워 내려주는 경우가
    확인됨 — NaN 한 행이 52주고가·거래대금배수 등 모든 지표를 NaN으로
    오염시키므로 소스에서 제거한다.
    """
    try:
        cleaned = df.dropna(subset=["Close", "High"])
        return cleaned if len(cleaned) > 1 else df
    except Exception:
        return df


# ── 공개 API ──────────────────────────────────────────────────────────────────


def get_daily(code6: str):
    """6자리 종목코드 → 최근 300거래일 일봉 DataFrame (OHLCV).

    .KS 먼저 시도하고 0~1행이면 .KQ로 재시도한다. 당일 1회 파일 캐시로
    반복 호출 시 네트워크 요청을 건너뛴다. 실패 시 None.
    """
    code6 = str(code6).strip().zfill(6)

    today = datetime.now().strftime("%Y-%m-%d")
    hit = _MEM_CACHE.get(code6)
    if hit and hit[0] == today:
        return hit[1]

    cached = _load_cache(code6)
    if cached is not None and len(cached) > 1:
        out = _clean_ohlcv(cached)
        _MEM_CACHE[code6] = (today, out)
        return out

    df = _download_yf(f"{code6}.KS")
    if df is None or len(df) <= 1:
        df = _download_yf(f"{code6}.KQ")

    if df is None or len(df) <= 1:
        _log.warning("get_daily: no data for %s", code6)
        return None

    _save_cache(code6, df)
    out = _clean_ohlcv(df)
    _MEM_CACHE[code6] = (today, out)
    return out


def get_index_daily(ticker: str = _KOSPI_INDEX):
    """지수(기본: ^KS11) 일봉 DataFrame. 당일 캐시 적용. 실패 시 None."""
    safe_key = ticker.replace("^", "IDX_")
    today = datetime.now().strftime("%Y-%m-%d")
    hit = _MEM_CACHE.get(safe_key)
    if hit and hit[0] == today:
        return hit[1]

    cached = _load_cache(safe_key)
    if cached is not None and len(cached) > 1:
        out = _clean_ohlcv(cached)
        _MEM_CACHE[safe_key] = (today, out)
        return out

    df = _download_yf(ticker)
    if df is None or len(df) <= 1:
        return None

    _save_cache(safe_key, df)
    out = _clean_ohlcv(df)
    _MEM_CACHE[safe_key] = (today, out)
    return out


_INTRADAY_CACHE: dict = {}
_INTRADAY_TTL_SEC = 120.0


def get_intraday_summary(code6: str):
    """당일 1분봉 기반 시가/고가/현재가. {"open","high","last"} 또는 None.
    120초 메모리 캐시 (실시간 자동조회 허용 — 2026-07-17 사용자 지시)."""
    code6 = str(code6).strip().zfill(6)
    now = time.time()
    hit = _INTRADAY_CACHE.get(code6)
    if hit and now - hit[0] < _INTRADAY_TTL_SEC:
        return hit[1]

    out = None
    for suffix in (".KS", ".KQ"):
        try:
            import yfinance as yf

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df = yf.download(
                    f"{code6}{suffix}", period="1d", interval="1m",
                    auto_adjust=True, progress=False,
                )
            if df is None or df.empty:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            closes = df["Close"].dropna()
            opens = df["Open"].dropna()
            highs = df["High"].dropna()
            if closes.empty or opens.empty or highs.empty:
                continue
            out = {
                "open": float(opens.iloc[0]),
                "high": float(highs.max()),
                "last": float(closes.iloc[-1]),
            }
            break
        except Exception as e:
            _log.debug("intraday fetch failed %s%s: %s", code6, suffix, e)
            continue

    _INTRADAY_CACHE[code6] = (now, out)
    return out


# ── 지표 함수 ─────────────────────────────────────────────────────────────────


def high_52w(df) -> float | None:
    """52주(최근 252거래일) 최고가."""
    try:
        return float(df["High"].tail(252).max())
    except Exception:
        return None


def pct_from_52w_high(df) -> float | None:
    """현재 종가가 52주 최고가 대비 % (하락 시 음수)."""
    h = high_52w(df)
    if h is None or h <= 0:
        return None
    try:
        current = float(df["Close"].iloc[-1])
        return round((current - h) / h * 100, 2)
    except Exception:
        return None


def avg_turnover_20d(df) -> float | None:
    """최근 20거래일 평균 거래대금 (종가×거래량 근사, 단위: 원)."""
    try:
        t = (df["Close"] * df["Volume"]).tail(20)
        return float(t.mean()) if len(t) > 0 else None
    except Exception:
        return None


def today_turnover_multiple(df) -> float | None:
    """당일 거래대금이 20일 평균 대비 몇 배인지."""
    avg = avg_turnover_20d(df)
    if avg is None or avg <= 0:
        return None
    try:
        today = float(df["Close"].iloc[-1]) * float(df["Volume"].iloc[-1])
        return round(today / avg, 2)
    except Exception:
        return None


def max_gain_20d(df) -> float | None:
    """최근 20거래일 내 최대 일간 상승률 (%)."""
    try:
        closes = df["Close"].tail(21)
        if len(closes) < 2:
            return None
        rets = closes.pct_change().dropna() * 100
        return round(float(rets.max()), 2)
    except Exception:
        return None


def volatile_days_60d(index_df) -> int | None:
    """지수 일봉의 최근 60거래일 중 종가 등락 ±3% 이상인 날 수."""
    try:
        closes = index_df["Close"].tail(61)
        if len(closes) < 2:
            return None
        rets = closes.pct_change().dropna() * 100
        rets = rets.tail(60)
        return int((rets.abs() >= 3.0).sum())
    except Exception:
        return None
