"""무료 데이터 소스(yfinance 우선, FinanceDataReader 보조)로 과거 시세를 조회한다.

읽기 전용 사후 조회만 수행한다. 실시간 시세 연결, 증권사 API, 자동매매와는 무관하다.
pykrx는 이번 1차 성과검증에서는 사용하지 않는다.
조회 실패 시 예외를 던지지 않고 None을 반환한다 — 호출부(performance.py)에서
"데이터 부족"으로 처리한다.
"""

import math
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

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
_SEOUL_TZ = ZoneInfo("Asia/Seoul")


def _now_seoul():
    """테스트에서 고정할 수 있는 한국 현재 시각."""
    return datetime.now(_SEOUL_TZ)


def _latest_ohlc_row_is_valid(df):
    """df.iloc[-1](가장 최근 행)의 Open/High/Low/Close가 전부 유한한 숫자인지 확인한다.

    NaN/Infinity/숫자로 변환 불가한 값이 하나라도 있으면 False를 반환한다 — 데이터
    제공처가 아직 확정되지 않은 당일 행(거래량만 채워지고 가격은 비어 있는 경우 등)을
    돌려주는 상황을 걸러내기 위함이다. yfinance/FinanceDataReader 조회 함수가 이
    검사를 공유해서 "최신 행이 유효하다"는 기준이 서로 갈라지지 않게 한다.
    """
    last = df.iloc[-1]
    for col in ("Open", "High", "Low", "Close"):
        try:
            if not math.isfinite(float(last[col])):
                return False
        except (TypeError, ValueError):
            return False
    return True


def _try_yfinance_ohlcv(symbol, start, end):
    import yfinance as yf

    df = yf.Ticker(symbol).history(start=start, end=end)
    if df is None or df.empty or not all(c in df.columns for c in _SNAPSHOT_COLUMNS):
        return None
    df = _clean_index(df[_SNAPSHOT_COLUMNS].copy())
    if not _latest_ohlc_row_is_valid(df):
        return None
    return df


def _try_fdr_ohlcv(symbol, start, end):
    import FinanceDataReader as fdr

    df = fdr.DataReader(symbol, start, end)
    if df is None or df.empty or not all(c in df.columns for c in _SNAPSHOT_COLUMNS):
        return None
    df = _clean_index(df[_SNAPSHOT_COLUMNS].copy())
    if not _latest_ohlc_row_is_valid(df):
        return None
    return df


def get_intraday_last(ticker):
    """오늘 1분봉 중 가장 최근 값을 조회한다(장중 현재가에 가장 가까운 값).

    실시간 스트리밍이 아니다 — 호출된 그 순간에 한 번만 조회하는 스냅샷이며,
    자동으로 반복 호출되지 않는다(화면에 뜨는 숫자가 항상 전날 종가라서 시간차가
    크다는 지적을 반영해 2026-07-13 사용자 명시 요청으로 추가). 기존
    get_snapshot_defaults()는 그대로 두고 완전히 새 함수로 분리했다. 장이 닫혀
    있거나(주말·공휴일·장 시작 전) 1분봉이 없으면 ok=False를 반환하며, 호출부는
    그러면 기존처럼 최근 완료된 거래일 종가로 대체 표시해야 한다.
    """
    try:
        import yfinance as yf

        # 오늘 현재가뿐 아니라 직전 거래일의 마지막 1분봉도 함께 받아 전일 종가
        # 기준을 잡는다. yfinance 일봉은 간혹 직전 거래일 행이 누락되어 며칠 전
        # 종가와 비교되는 경우가 있으므로(2026-07-14 KOSPI/KOSDAQ에서 확인),
        # 장중 등락률의 기준값은 직전 거래일 1분봉 종가를 우선 사용한다.
        df = yf.Ticker(ticker).history(period="5d", interval="1m")
        if df is None or df.empty or "Close" not in df.columns:
            return {"ok": False, "error": "장중 1분봉 데이터 없음"}

        # 아직 값이 확정되지 않은 마지막 행(NaN/Infinity/0 이하)은 사용하지 않고,
        # 같은 응답 안에서 가장 최근의 유효한 1분봉을 고른다.
        valid_rows = []
        for position, value in enumerate(df["Close"].tolist()):
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(numeric) or numeric <= 0:
                continue
            try:
                asof = pd.Timestamp(df.index[position])
                # 시간대가 있는 값은 반드시 Asia/Seoul로 변환한다. 시간대가 없는 값은
                # yfinance의 한국 거래소 현지 시각으로 간주해 Asia/Seoul을 명시한다.
                asof_seoul = (
                    asof.tz_localize(_SEOUL_TZ)
                    if asof.tzinfo is None
                    else asof.tz_convert(_SEOUL_TZ)
                )
            except Exception:
                continue
            valid_rows.append((asof_seoul, numeric))
        if not valid_rows:
            return {"ok": False, "error": "장중 데이터 유효성 실패"}

        today = _now_seoul().date()
        today_rows = [row for row in valid_rows if row[0].date() == today]
        if not today_rows:
            return {"ok": False, "error": "오늘 장중 1분봉 데이터 없음"}

        asof_seoul, close = today_rows[-1]
        previous_rows = [row for row in valid_rows if row[0].date() < today]
        prev_close = None
        prev_close_as_of_date = None
        if previous_rows:
            previous_date = max(row[0].date() for row in previous_rows)
            previous_session_rows = [row for row in previous_rows if row[0].date() == previous_date]
            prev_close = previous_session_rows[-1][1]
            prev_close_as_of_date = previous_date.strftime("%Y-%m-%d")

        as_of_date = asof_seoul.strftime("%Y-%m-%d")
        as_of_time = asof_seoul.strftime("%H:%M")
        return {
            "ok": True,
            "current": close,
            "prev_close": prev_close,
            "prev_close_as_of_date": prev_close_as_of_date,
            "asof": as_of_time,  # 기존 호출자 호환
            "as_of_time": as_of_time,
            "as_of_date": as_of_date,
            "data_kind": "intraday",
        }
    except Exception:
        return {"ok": False, "error": "장중 시세 조회 실패"}


def get_snapshot_defaults(ticker, completed_only=False):
    """장중 스냅샷 "기본값 자동 채우기" 전용 조회. DB에 저장하지 않는 읽기 전용 헬퍼다.

    yfinance 우선, 실패 시 FinanceDataReader 보조로 최근 일봉(시가/고가/저가/종가/거래량)을
    가져온다. 실시간 시세가 아니라 가장 최근 완료된 거래일 기준이며, "현재가"는 최근
    종가로 대체한다(이 프로젝트는 실시간 자동조회를 금지한다).

    거래대금/시가총액은 일별 정확한 값을 무료 소스에서 안정적으로 얻기 어려워
    근사치(거래량×종가, 상장주식수×종가)로 계산하고 *_approx=True로 표시한다.
    조회 실패 시 예외를 던지지 않고 {"ok": False, "error": "..."}를 반환한다.

    completed_only=True이면 한국 장중(15:40 이전)에 생성된 오늘 일봉을 제외한다.
    기본값은 False이므로 기존 호출자의 장중 스냅샷 동작은 그대로 유지된다.
    """
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

    if df is not None and completed_only and not df.empty:
        try:
            now_seoul = _now_seoul()
            last_date = pd.Timestamp(df.index[-1]).date()
            if last_date == now_seoul.date() and now_seoul.time() < time(15, 40):
                df = df.iloc[:-1]
        except Exception:
            return {"ok": False, "error": "완료 거래일 확인 실패"}

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

    # 이 종가가 실제로 "며칠 몇 일자" 데이터인지 호출부가 표시할 수 있도록 날짜를
    # 같이 반환한다(추가 필드라 기존 호출부는 영향 없음, 2026-07-13 추가 — 화면에
    # "최근 종가로 대체"라고만 쓰면 정확히 언제 종가인지 알 수 없다는 지적 반영).
    try:
        as_of_date = df.index[-1].strftime("%Y-%m-%d")
    except Exception:
        as_of_date = None

    # 최종 반환 직전 재검증. _try_yfinance_ohlcv()/_try_fdr_ohlcv()가 이미 최신 행의
    # OHLC 유효성을 확인하지만, 여기서도 실제로 반환할 값 자체를 다시 확인해 NaN/
    # Infinity/0 이하 가격이 ok=True로 새어나가지 않게 한다(이중 방어).
    required_prices = {
        "current": current,
        "prev_close": prev_close,
        "open": open_price,
        "high": high,
        "low": low,
    }
    invalid_price_fields = [
        name
        for name, value in required_prices.items()
        if not math.isfinite(value) or value <= 0
    ]
    if invalid_price_fields:
        return {
            "ok": False,
            "error": f"시세 데이터 비정상(유한한 양수 아님): {', '.join(invalid_price_fields)}",
        }
    if not math.isfinite(volume) or volume < 0:
        return {"ok": False, "error": "거래량 데이터가 유효하지 않습니다"}

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
        "as_of_date": as_of_date,
        "as_of_time": None,
        "data_kind": "daily_close",
    }


def _try_yfinance_ohlc_chart(symbol, start, end):
    """차트 전용 조회. _try_yfinance_ohlcv와 달리 최신 행이 아직 확정 안 됐어도
    (NaN 등, 장중 스냅샷 기준으로는 무효) 그 행만 제외하고 나머지 과거 데이터는
    살린다 — 스냅샷 "현재가" 채우기와 달리 차트는 지난 몇 달치 흐름을 보여주는
    용도라 최신 하루가 아직 안 채워졌다고 전체를 버릴 이유가 없다."""
    import yfinance as yf

    df = yf.Ticker(symbol).history(start=start, end=end)
    if df is None or df.empty or not all(c in df.columns for c in _SNAPSHOT_COLUMNS):
        return None
    df = _clean_index(df[_SNAPSHOT_COLUMNS].copy())
    if not _latest_ohlc_row_is_valid(df):
        df = df.iloc[:-1]
    return df if not df.empty else None


def _try_fdr_ohlc_chart(symbol, start, end):
    """차트 전용 조회. _try_fdr_ohlcv와 달리 최신 행만 무효해도 나머지는 살린다."""
    import FinanceDataReader as fdr

    df = fdr.DataReader(symbol, start, end)
    if df is None or df.empty or not all(c in df.columns for c in _SNAPSHOT_COLUMNS):
        return None
    df = _clean_index(df[_SNAPSHOT_COLUMNS].copy())
    if not _latest_ohlc_row_is_valid(df):
        df = df.iloc[:-1]
    return df if not df.empty else None


def get_ohlc_history_for_chart(ticker, start, end):
    """차트 표시 전용 일봉 OHLC 조회 (읽기 전용, 점수 계산과 무관).

    yfinance 우선, 실패 시 FinanceDataReader 보조. 기존 계산 로직
    (get_snapshot_defaults 등)은 건드리지 않는다 — 전용 헬퍼(_try_yfinance_ohlc_chart/
    _try_fdr_ohlc_chart)를 따로 써서, 스냅샷용 헬퍼(_try_yfinance_ohlcv/_try_fdr_ohlcv)의
    "최신 행 하나라도 무효면 전체 거부" 기준이 차트에는 그대로 적용되지 않게 했다
    (2026-07-13 전체 코드검사에서 발견: 최신 하루치만 깨져도 몇 달치 차트가 통째로
    "데이터 없음"으로 나오던 문제, 상하님 승인 후 수정). 조회 실패 시 예외 대신
    None을 반환한다.
    """
    try:
        df = _try_yfinance_ohlc_chart(ticker, start, end)
        if df is not None and len(df) > 0:
            return df
    except Exception:
        pass
    try:
        df = _try_fdr_ohlc_chart(_fdr_code(ticker), start, end)
        if df is not None and len(df) > 0:
            return df
    except Exception:
        pass
    return None


# ── 오늘 거래대금 상위 종목 자동 선정 (읽기 전용, 저장 없음, 사용자 명시 요청으로 추가) ──
# 2026-07-13: 하드코딩된 7종목 고정 목록 대신, 매일 거래대금 상위 종목을 자동으로 뽑아
# app.py의 SNAPSHOT_STOCKS를 동적으로 채우기 위한 함수. 기존 get_price_history/
# get_snapshot_defaults/get_ohlc_history_for_chart와는 완전히 분리된 새 함수라 기존
# 동작에는 영향이 없다.

_PREFERRED_STOCK_SUFFIX_PATTERN = r"\d*우[A-Z]?$"


def get_top_kr_stocks_by_amount(n=20, exclude_dept=("SPAC(소속부없음)", "관리종목(소속부없음)", "투자주의환기종목(소속부없음)")):
    """오늘(가장 최근 완료된 거래일) 코스피/코스닥 거래대금 상위 n종목을 뽑는다.

    FinanceDataReader의 KRX 전체 종목 스냅샷(fdr.StockListing('KRX'))을 한 번 조회해
    Amount(거래대금) 기준 내림차순 정렬한다. 우선주(이름이 "우"/"우B" 등으로 끝나는
    종목)와 스팩·관리종목·투자주의환기종목은 제외한다(정상적인 매매 후보로 보기
    어려움). 'KOSDAQ GLOBAL'은 'KOSDAQ'과 중복 상장 표기라 KOSPI/KOSDAQ만 남긴다.
    조회 실패 시 예외를 던지지 않고 빈 리스트를 반환한다.

    반환: [{"name": str, "ticker": str(".KS"/".KQ" 접미사 포함), "sector": "-"}] (최대 n개)
    """
    try:
        import FinanceDataReader as fdr

        df = fdr.StockListing("KRX")
    except Exception:
        return []
    if df is None or df.empty or "Amount" not in df.columns:
        return []

    df = df[df["Market"].isin(["KOSPI", "KOSDAQ"])]
    if exclude_dept:
        df = df[~df["Dept"].isin(exclude_dept)]
    df = df[~df["Name"].astype(str).str.contains(_PREFERRED_STOCK_SUFFIX_PATTERN, regex=True)]
    df = df.sort_values("Amount", ascending=False).head(n)

    results = []
    for _, row in df.iterrows():
        code = str(row["Code"]).strip()
        market = row["Market"]
        suffix = ".KS" if market == "KOSPI" else ".KQ"
        results.append({"name": str(row["Name"]).strip(), "ticker": f"{code}{suffix}", "sector": "-"})
    return results
