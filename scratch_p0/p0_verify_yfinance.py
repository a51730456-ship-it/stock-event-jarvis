"""
P0 검증 1 — yfinance 한국 종목 일봉 + 지수 이벤트 카운트
기존 코드 수정 없음. 결과만 출력.
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import warnings
warnings.filterwarnings("ignore")

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

PERIOD = "300d"  # 최근 300 거래일 커버용

TICKERS = {
    "005930.KS": "삼성전자(KOSPI)",
    "000660.KS": "SK하이닉스(KOSPI)",
    "035720.KQ": "카카오(KOSDAQ)",
}
INDEX_TICKER = "^KS11"


def test_kr_stocks():
    print("=" * 60)
    print("[검증 1-A] 한국 종목 일봉 (OHLCV) 및 파생 지표")
    print("=" * 60)

    for ticker, label in TICKERS.items():
        print(f"\n▶ {label} ({ticker})")
        try:
            df = yf.download(ticker, period=PERIOD, auto_adjust=True, progress=False)
            if df is None or df.empty:
                print(f"  FAIL 실패: 데이터 없음")
                continue

            # 컬럼이 MultiIndex이면 단순화
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            print(f"  OK 수신 행수: {len(df)}")
            print(f"  기간: {df.index[0].date()} ~ {df.index[-1].date()}")
            print(f"  컬럼: {list(df.columns)}")

            # --- 52주 최고가 대비 현재가 % ---
            recent_252 = df.tail(252)
            high_52w = recent_252["High"].max()
            current = float(df["Close"].iloc[-1])
            pct_from_high = (current - high_52w) / high_52w * 100
            print(f"  52주 최고가: {high_52w:,.0f}  현재가: {current:,.0f}  대비: {pct_from_high:+.1f}%")

            # --- 20일 평균 거래대금 vs 당일 거래대금 ---
            df["turnover"] = df["Close"] * df["Volume"]
            avg_20d = df["turnover"].tail(20).mean()
            today_turnover = float(df["turnover"].iloc[-1])
            multiple = today_turnover / avg_20d if avg_20d else float("nan")
            print(f"  20일 평균 거래대금: {avg_20d/1e8:.1f}억  당일: {today_turnover/1e8:.1f}억  배수: {multiple:.2f}x")

            # --- 최근 20거래일 내 최대 일간 상승률 ---
            last_20 = df["Close"].tail(21)
            daily_ret = last_20.pct_change().dropna() * 100
            max_gain = daily_ret.max()
            max_date = daily_ret.idxmax()
            print(f"  최근20일 최대 일간 상승률: {max_gain:.2f}% ({max_date.date()})")

        except Exception as e:
            print(f"  FAIL 예외: {e}")


def test_kospi_index_events():
    print("\n" + "=" * 60)
    print("[검증 1-B] ^KS11 코스피 지수 일봉 — 최근 60일 ±3% 이상 일수")
    print("=" * 60)
    try:
        df = yf.download(INDEX_TICKER, period="90d", auto_adjust=True, progress=False)
        if df is None or df.empty:
            print("  FAIL 실패: 데이터 없음")
            return

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.tail(60)
        daily_chg = df["Close"].pct_change().dropna() * 100
        events = (daily_chg.abs() >= 3.0)
        print(f"  OK 수신 행수(최근60일): {len(df)}")
        print(f"  ±3% 이상 날 수: {events.sum()}일")
        if events.sum() > 0:
            for dt, chg in daily_chg[events].items():
                print(f"    {dt.date()} → {chg:+.2f}%")

    except Exception as e:
        print(f"  FAIL 예외: {e}")


if __name__ == "__main__":
    test_kr_stocks()
    test_kospi_index_events()
    print("\n완료:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
