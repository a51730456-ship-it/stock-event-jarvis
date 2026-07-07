"""무료 데이터 소스(yfinance / FinanceDataReader / pykrx) 조회 가능성 테스트.

보조 테스트 파일이다. app.py/database.py의 동작과는 무관하며,
여기서 조회가 실패해도 1단계 MVP 개발을 막지 않는다.

원칙:
- 라이브러리 임포트 자체가 실패해도 다음 라이브러리 테스트로 계속 진행한다.
- 종목/지수 하나의 조회가 실패해도 다음 종목으로 계속 진행한다.
- 증권사 API, 네이버/다음 스크래핑은 사용하지 않는다.

대상: 005930.KS(삼성전자), 000660.KS(SK하이닉스), KOSPI, NVDA, QQQ, SOXX
"""

from datetime import datetime, timedelta

TARGETS = ["005930.KS", "000660.KS", "KOSPI", "NVDA", "QQQ", "SOXX"]

results = []


def record(library, target, ok, detail):
    results.append({"library": library, "target": target, "ok": ok, "detail": detail})
    status = "성공" if ok else "실패"
    print(f"[{library}] {target}: {status} - {detail}")


def test_yfinance():
    library = "yfinance"
    try:
        import yfinance as yf
    except Exception as e:
        for target in TARGETS:
            record(library, target, False, f"라이브러리 임포트 실패: {e}")
        return

    symbol_map = {
        "005930.KS": "005930.KS",
        "000660.KS": "000660.KS",
        "KOSPI": "^KS11",
        "NVDA": "NVDA",
        "QQQ": "QQQ",
        "SOXX": "SOXX",
    }
    for target, symbol in symbol_map.items():
        try:
            hist = yf.Ticker(symbol).history(period="5d")
            if hist is None or hist.empty:
                record(library, target, False, "빈 데이터 반환")
            else:
                last_close = hist["Close"].iloc[-1]
                record(library, target, True, f"{len(hist)}건, 마지막 종가={last_close:.2f}")
        except Exception as e:
            record(library, target, False, f"예외 발생: {e}")


def test_fdr():
    library = "FinanceDataReader"
    try:
        import FinanceDataReader as fdr
    except Exception as e:
        for target in TARGETS:
            record(library, target, False, f"라이브러리 임포트 실패: {e}")
        return

    code_map = {
        "005930.KS": "005930",
        "000660.KS": "000660",
        "KOSPI": "KS11",
        "NVDA": "NVDA",
        "QQQ": "QQQ",
        "SOXX": "SOXX",
    }
    start = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    for target, code in code_map.items():
        try:
            df = fdr.DataReader(code, start)
            if df is None or df.empty:
                record(library, target, False, "빈 데이터 반환")
            else:
                last_close = df["Close"].iloc[-1]
                record(library, target, True, f"{len(df)}건, 마지막 종가={last_close}")
        except Exception as e:
            record(library, target, False, f"예외 발생: {e}")


def test_pykrx():
    library = "pykrx"
    try:
        from pykrx import stock
    except Exception as e:
        for target in TARGETS:
            record(library, target, False, f"라이브러리 임포트 실패: {e}")
        return

    # pykrx는 KR 종목/지수 전용이라 US 티커(NVDA/QQQ/SOXX)는 정상 조회되지 않을 수 있다.
    # 그래도 강제로 호출해보고 결과를 그대로 기록한다(실패도 유의미한 정보).
    code_map = {
        "005930.KS": ("stock", "005930"),
        "000660.KS": ("stock", "000660"),
        "KOSPI": ("index", "1001"),
        "NVDA": ("stock", "NVDA"),
        "QQQ": ("stock", "QQQ"),
        "SOXX": ("stock", "SOXX"),
    }
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")
    for target, (kind, code) in code_map.items():
        try:
            if kind == "index":
                df = stock.get_index_ohlcv_by_date(start, end, code)
            else:
                df = stock.get_market_ohlcv_by_date(start, end, code)
            if df is None or df.empty:
                record(library, target, False, "빈 데이터 반환")
            else:
                last_close = df["종가"].iloc[-1]
                record(library, target, True, f"{len(df)}건, 마지막 종가={last_close}")
        except Exception as e:
            record(library, target, False, f"예외 발생: {e}")


def main():
    print("=== data_test.py: 무료 데이터 소스 조회 가능성 테스트 ===")
    for test_fn in (test_yfinance, test_fdr, test_pykrx):
        try:
            test_fn()
        except Exception as e:
            # 예상 못 한 예외까지 여기서 막아서 다음 라이브러리로 계속 진행한다.
            print(f"[전체 실패] {test_fn.__name__}: {e}")

    print()
    print("=== 요약 ===")
    for r in results:
        status = "성공" if r["ok"] else "실패"
        print(f"{r['library']:20s} {r['target']:10s} {status:4s} {r['detail']}")


if __name__ == "__main__":
    main()
