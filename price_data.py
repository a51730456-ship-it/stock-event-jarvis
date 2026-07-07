"""무료 데이터 소스(yfinance 우선, FinanceDataReader 보조)로 과거 시세를 조회한다.

읽기 전용 사후 조회만 수행한다. 실시간 시세 연결, 증권사 API, 자동매매와는 무관하다.
pykrx는 이번 1차 성과검증에서는 사용하지 않는다.
조회 실패 시 예외를 던지지 않고 None을 반환한다 — 호출부(performance.py)에서
"데이터 부족"으로 처리한다.
"""

import pandas as pd

BENCHMARK_YF_SYMBOL = {"KOSPI": "^KS11", "SPY": "SPY", "SOXX": "SOXX"}
BENCHMARK_FDR_SYMBOL = {"KOSPI": "KS11", "SPY": "SPY", "SOXX": "SOXX"}


def _clean_index(df):
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df.index = df.index.normalize()
    return df


def _try_yfinance(symbol, start, end):
    import yfinance as yf

    df = yf.Ticker(symbol).history(start=start, end=end)
    if df is None or df.empty or "Open" not in df.columns or "Close" not in df.columns:
        return None
    df = _clean_index(df[["Open", "Close"]].copy())
    return df


def _try_fdr(symbol, start, end):
    import FinanceDataReader as fdr

    df = fdr.DataReader(symbol, start, end)
    if df is None or df.empty or "Open" not in df.columns or "Close" not in df.columns:
        return None
    df = _clean_index(df[["Open", "Close"]].copy())
    return df


def _fdr_code(ticker):
    """KR 티커의 거래소 접미사(.KS/.KQ)를 제거한다. FinanceDataReader는 접미사 없는 코드를 쓴다."""
    upper = ticker.upper()
    for suffix in (".KS", ".KQ"):
        if upper.endswith(suffix):
            return ticker[: -len(suffix)]
    return ticker


def get_price_history(ticker, start, end):
    """종목 ticker의 Open/Close 시세를 [start, end] 기간에 대해 조회.

    yfinance로 먼저 시도하고, 실패하면 FinanceDataReader로 보조 조회한다.
    둘 다 실패하면 None을 반환한다(예외를 전파하지 않음).
    """
    try:
        df = _try_yfinance(ticker, start, end)
        if df is not None:
            return df
    except Exception:
        pass
    try:
        df = _try_fdr(_fdr_code(ticker), start, end)
        if df is not None:
            return df
    except Exception:
        pass
    return None


def get_benchmark_history(benchmark_name, start, end):
    """benchmark_name("KOSPI"/"SPY"/"SOXX")의 Open/Close 시세를 조회. 실패 시 None."""
    yf_symbol = BENCHMARK_YF_SYMBOL.get(benchmark_name)
    fdr_symbol = BENCHMARK_FDR_SYMBOL.get(benchmark_name)
    if yf_symbol:
        try:
            df = _try_yfinance(yf_symbol, start, end)
            if df is not None:
                return df
        except Exception:
            pass
    if fdr_symbol:
        try:
            df = _try_fdr(fdr_symbol, start, end)
            if df is not None:
                return df
        except Exception:
            pass
    return None


# ── 장중 스냅샷 "기본값 자동 채우기" 전용 (읽기 전용, 저장 없음) ──────────────────
# 아래 함수들은 기존 get_price_history/get_benchmark_history(성과검증에서 사용 중)와
# 완전히 분리된 새 함수다. 기존 함수/성과검증 로직은 전혀 건드리지 않는다.

_SNAPSHOT_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


def _try_yfinance_ohlcv(symbol, start, end):
    import yfinance as yf

    df = yf.Ticker(symbol).history(start=start, end=end)
    if df is None or df.empty or not all(c in df.columns for c in _SNAPSHOT_COLUMNS):
        return None
    return _clean_index(df[_SNAPSHOT_COLUMNS].copy())


def _try_fdr_ohlcv(symbol, start, end):
    import FinanceDataReader as fdr

    df = fdr.DataReader(symbol, start, end)
    if df is None or df.empty or not all(c in df.columns for c in _SNAPSHOT_COLUMNS):
        return None
    return _clean_index(df[_SNAPSHOT_COLUMNS].copy())


def get_snapshot_defaults(ticker):
    """장중 스냅샷 "기본값 자동 채우기" 전용 조회. DB에 저장하지 않는 읽기 전용 헬퍼다.

    yfinance 우선, 실패 시 FinanceDataReader 보조로 최근 일봉(시가/고가/저가/종가/거래량)을
    가져온다. 실시간 시세가 아니라 가장 최근 완료된 거래일 기준이며, "현재가"는 최근
    종가로 대체한다(이 프로젝트는 실시간 자동조회를 금지한다).

    거래대금/시가총액은 일별 정확한 값을 무료 소스에서 안정적으로 얻기 어려워
    근사치(거래량×종가, 상장주식수×종가)로 계산하고 *_approx=True로 표시한다.
    조회 실패 시 예외를 던지지 않고 {"ok": False, "error": "..."}를 반환한다.
    """
    from datetime import datetime, timedelta

    now = datetime.now()
    start_str = (now - timedelta(days=15)).strftime("%Y-%m-%d")
    end_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    df = None
    try:
        df = _try_yfinance_ohlcv(ticker, start_str, end_str)
    except Exception:
        df = None
    if df is None:
        try:
            df = _try_fdr_ohlcv(_fdr_code(ticker), start_str, end_str)
        except Exception:
            df = None

    if df is None or len(df) < 2:
        return {"ok": False, "error": "시세 조회 실패(데이터 없음)"}

    try:
        last = df.iloc[-1]
        prev = df.iloc[-2]
        current = float(last["Close"])
        prev_close = float(prev["Close"])
        open_price = float(last["Open"])
        high = float(last["High"])
        low = float(last["Low"])
        volume = float(last["Volume"])
    except Exception as e:
        return {"ok": False, "error": f"시세 데이터 해석 실패: {e}"}

    turnover_approx_value = volume * current  # 근사치(실제 체결대금과 다를 수 있음)

    market_cap = None
    try:
        import yfinance as yf

        shares = getattr(yf.Ticker(ticker).fast_info, "shares", None)
        if shares:
            market_cap = float(shares) * current
    except Exception:
        market_cap = None

    return {
        "ok": True,
        "current": current,
        "prev_close": prev_close,
        "open": open_price,
        "high": high,
        "low": low,
        "turnover": turnover_approx_value,
        "turnover_approx": True,
        "market_cap": market_cap,
        "market_cap_approx": True,
    }
