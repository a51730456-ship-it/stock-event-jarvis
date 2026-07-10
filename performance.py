"""읽기 기반 성과검증(1차). 저장된 report_items 중 ticker가 있는 종목만 대상으로 한다.

docs/STAGE2_PERFORMANCE_SPEC.md의 진입가 규칙/검증 기간/기준지수 결정을 따른다.
자동매매, 매수/매도 신호, 증권사 API, 실시간 시세 연결과는 무관한 사후 배치 조회다.
report_items가 0개인 "오늘 추천 없음" report의 기회비용/위험회피 평가도 포함한다
(market_scope별 기준지수: KR->KOSPI, US->SPY, MIXED->KOSPI/SPY 분리 표시).
"""

from datetime import datetime, timedelta

import pandas as pd

import database as db
import price_data

HORIZONS = [1, 3, 5, 10, 20]
REPRESENTATIVE_HORIZON = 5  # 요약 초과수익률 대표 기간 (STAGE2_PERFORMANCE_SPEC.md 3번)

# 1차 구현용 반도체 티커 화이트리스트 (STAGE2_PERFORMANCE_SPEC.md 4번 예시 종목 기준)
SEMICONDUCTOR_TICKERS = {
    "NVDA", "MU", "TSM", "AMD", "INTC", "AVGO", "QCOM",
    "ASML", "AMAT", "LRCX", "KLAC", "ON", "SOXX", "SMH",
}


def _strip_kr_suffix(ticker):
    upper = ticker.upper()
    for suffix in (".KS", ".KQ"):
        if upper.endswith(suffix):
            return ticker[: -len(suffix)]
    return ticker


def determine_benchmark(market, ticker):
    """market/ticker로 비교 기준지수를 결정한다 (KOSPI/SPY/SOXX). 지원 불가하면 None(OTHER 등)."""
    if market == "KR":
        return "KOSPI"
    if market == "US":
        base = _strip_kr_suffix(ticker or "").upper()
        if base in SEMICONDUCTOR_TICKERS:
            return "SOXX"
        return "SPY"
    return None


def determine_entry_rule(timing_class):
    """timing_class로 진입 기준을 결정한다. 장전->당일 시가, 장중->당일 종가,
    장후/혼합/기타/미지정 -> 다음 거래일 시가(보수적)."""
    if timing_class == "장전":
        return "당일 시가"
    if timing_class == "장중":
        return "당일 종가"
    if timing_class == "장후":
        return "다음 거래일 시가"
    return "다음 거래일 시가(보수적)"


def _entry_point(price_df, ref_date, rule):
    """price_df에서 rule에 따른 기준일/기준가/기준일의 위치(인덱스)를 찾는다.

    ref_date **이전** 데이터는 절대 사용하지 않는다.
    데이터가 아직 없으면 (None, None, None) 반환 -> 호출부에서 "대기"로 처리.
    """
    if price_df is None or price_df.empty:
        return None, None, None

    idx = price_df.index

    if rule == "당일 종가":
        candidates = idx[idx >= ref_date]
        if len(candidates) == 0:
            return None, None, None
        entry_date = candidates[0]
        return entry_date, float(price_df.loc[entry_date, "Close"]), idx.get_loc(entry_date)

    if rule == "당일 시가":
        candidates = idx[idx >= ref_date]
        if len(candidates) == 0:
            return None, None, None
        entry_date = candidates[0]
        return entry_date, float(price_df.loc[entry_date, "Open"]), idx.get_loc(entry_date)

    # "다음 거래일 시가" / "다음 거래일 시가(보수적)"
    candidates = idx[idx > ref_date]
    if len(candidates) == 0:
        return None, None, None
    entry_date = candidates[0]
    return entry_date, float(price_df.loc[entry_date, "Open"]), idx.get_loc(entry_date)


def _future_close(price_df, entry_idx, n_trading_days):
    """entry_idx로부터 n 거래일 뒤 종가. 아직 그만큼 시간이 지나지 않았으면 None."""
    target = entry_idx + n_trading_days
    if target >= len(price_df.index):
        return None
    return float(price_df["Close"].iloc[target])


def _future_point(price_df, entry_idx, n_trading_days):
    """entry_idx로부터 n 거래일 뒤 (날짜, 종가). 아직 그만큼 지나지 않았으면 (None, None).

    _future_close()와 동일한 위치 선택 로직이며, 성과 저장용 상세 정보(target_date)를
    추가로 노출하기 위한 보조 함수다. 기존 returns 계산(_future_close 자체와 그 호출부)은
    건드리지 않고, 이 함수는 evaluate_item()의 outcome_details 구성에서만 별도로 쓴다.
    """
    target = entry_idx + n_trading_days
    if target >= len(price_df.index):
        return None, None
    target_date = price_df.index[target]
    close_price = float(price_df["Close"].iloc[target])
    return target_date, close_price


def _empty_outcome_detail():
    return {
        "target_date": None,
        "close_price": None,
        "return_pct": None,
        "benchmark_return_pct": None,
        "excess_return_pct": None,
    }


def _empty_outcome_details():
    return {h: _empty_outcome_detail() for h in HORIZONS}


def evaluate_item(report, item):
    """report_items 한 행에 대한 성과검증 결과 dict."""
    ticker = (item.get("ticker") or "").strip()
    result = {
        "report_id": report["id"],
        "saved_at": report["saved_at"],
        "briefing_stage": report.get("briefing_stage") or "-",
        "signal_type": item.get("signal_type") or "-",
        "trade_mode": item.get("trade_mode") or "공통",
        "stock_name": item.get("stock_name") or "-",
        "ticker": ticker,
        "market": item.get("market") or "-",
        "verdict": item.get("verdict") or "-",
        "benchmark": "-",
        "entry_rule": "-",
        "returns": {h: None for h in HORIZONS},
        "excess_return": None,
        "status": "대기",
    }

    if not ticker:
        result["status"] = "데이터 부족"
        result["entry_price_used"] = None
        result["benchmark_symbol"] = None
        result["outcome_details"] = _empty_outcome_details()
        return result

    timing_class = item.get("item_timing_class") or report.get("timing_class")
    result["entry_rule"] = determine_entry_rule(timing_class)

    benchmark = determine_benchmark(item.get("market"), ticker)
    if benchmark is None:
        result["benchmark"] = "미지원(OTHER)"
        result["status"] = "데이터 부족"
        result["entry_price_used"] = None
        result["benchmark_symbol"] = None
        result["outcome_details"] = _empty_outcome_details()
        return result
    result["benchmark"] = benchmark

    try:
        saved_at_dt = datetime.fromisoformat(report["saved_at"])
    except ValueError:
        result["status"] = "데이터 부족"
        result["entry_price_used"] = None
        result["benchmark_symbol"] = benchmark
        result["outcome_details"] = _empty_outcome_details()
        return result
    ref_date = pd.Timestamp(saved_at_dt.date())

    start = (saved_at_dt - timedelta(days=10)).strftime("%Y-%m-%d")
    end = (saved_at_dt + timedelta(days=45)).strftime("%Y-%m-%d")

    price_df = price_data.get_price_history(ticker, start, end)
    bench_df = price_data.get_benchmark_history(benchmark, start, end)

    if price_df is None or bench_df is None:
        result["status"] = "데이터 부족"
        result["entry_price_used"] = None
        result["benchmark_symbol"] = benchmark
        result["outcome_details"] = _empty_outcome_details()
        return result

    entry_date, entry_price, entry_idx = _entry_point(price_df, ref_date, result["entry_rule"])
    b_entry_date, b_entry_price, b_entry_idx = _entry_point(bench_df, ref_date, result["entry_rule"])

    if entry_date is None or b_entry_date is None:
        result["status"] = "대기"
        result["entry_price_used"] = entry_price
        result["benchmark_symbol"] = benchmark
        result["outcome_details"] = _empty_outcome_details()
        return result

    any_computed = False
    stock_rep_return = None
    bench_rep_return = None
    for h in HORIZONS:
        fp = _future_close(price_df, entry_idx, h)
        if fp is not None and entry_price:
            stock_ret = (fp - entry_price) / entry_price * 100
            result["returns"][h] = stock_ret
            any_computed = True
            if h == REPRESENTATIVE_HORIZON:
                stock_rep_return = stock_ret

        bp = _future_close(bench_df, b_entry_idx, h)
        if bp is not None and b_entry_price and h == REPRESENTATIVE_HORIZON:
            bench_rep_return = (bp - b_entry_price) / b_entry_price * 100

    if stock_rep_return is not None and bench_rep_return is not None:
        result["excess_return"] = stock_rep_return - bench_rep_return

    # 성과 저장용 상세 정보(entry_price_used/benchmark_symbol/outcome_details) 노출.
    # 기존 returns/excess_return 계산(위 for문)은 전혀 건드리지 않고, 이미 계산된
    # price_df/bench_df/entry_idx/b_entry_idx/entry_price/b_entry_price를 그대로
    # 재사용해서 기간별 날짜/종가/벤치마크 수익률만 추가로 뽑아낸다(신규 가격 조회 없음).
    outcome_details = {}
    for h in HORIZONS:
        target_date, close_price = _future_point(price_df, entry_idx, h)
        _, b_close_price = _future_point(bench_df, b_entry_idx, h)

        horizon_return_pct = result["returns"][h]

        horizon_benchmark_return_pct = None
        if b_close_price is not None and b_entry_price:
            horizon_benchmark_return_pct = (b_close_price - b_entry_price) / b_entry_price * 100

        horizon_excess_return_pct = None
        if horizon_return_pct is not None and horizon_benchmark_return_pct is not None:
            horizon_excess_return_pct = horizon_return_pct - horizon_benchmark_return_pct

        outcome_details[h] = {
            "target_date": target_date.strftime("%Y-%m-%d") if target_date is not None else None,
            "close_price": close_price,
            "return_pct": horizon_return_pct,
            "benchmark_return_pct": horizon_benchmark_return_pct,
            "excess_return_pct": horizon_excess_return_pct,
        }

    result["entry_price_used"] = entry_price
    result["benchmark_symbol"] = benchmark
    result["outcome_details"] = outcome_details

    result["status"] = "계산 완료" if any_computed else "대기"
    return result


def build_verification_rows():
    """모든 report의 report_items 중 ticker가 있는 항목만 대상으로 성과검증 결과 리스트를 만든다."""
    rows = []
    for report in db.list_reports():
        for item in db.get_report_items(report["id"]):
            if not (item.get("ticker") or "").strip():
                continue
            rows.append(evaluate_item(report, item))
    return rows


def _judge_return(value):
    """기준지수 수익률 부호로 기회비용/위험회피/보합을 판정한다.
    지수 상승만으로 실패 처리하지 않는다 — '기회비용'은 실패가 아니라 별도 축이다."""
    if value is None:
        return "-"
    if value > 0:
        return "기회비용"
    if value < 0:
        return "위험회피 성공"
    return "보합"


def _evaluate_benchmark_for_no_rec(report, benchmark_name, market_label):
    """report_items가 0개인 report 1건에 대해, 지정된 기준지수 하나로 기회비용/위험회피를 평가."""
    result = {
        "report_id": report["id"],
        "saved_at": report["saved_at"],
        "day_conclusion": report.get("day_conclusion") or "-",
        "market_label": market_label,
        "benchmark": benchmark_name,
        "entry_rule": determine_entry_rule(report.get("timing_class")),
        "returns": {h: None for h in HORIZONS},
        "judgment_5d": "-",
        "status": "대기",
    }

    try:
        saved_at_dt = datetime.fromisoformat(report["saved_at"])
    except ValueError:
        result["status"] = "데이터 부족"
        return result
    ref_date = pd.Timestamp(saved_at_dt.date())

    start = (saved_at_dt - timedelta(days=10)).strftime("%Y-%m-%d")
    end = (saved_at_dt + timedelta(days=45)).strftime("%Y-%m-%d")

    bench_df = price_data.get_benchmark_history(benchmark_name, start, end)
    if bench_df is None:
        result["status"] = "데이터 부족"
        return result

    entry_date, entry_price, entry_idx = _entry_point(bench_df, ref_date, result["entry_rule"])
    if entry_date is None:
        result["status"] = "대기"
        return result

    any_computed = False
    for h in HORIZONS:
        fp = _future_close(bench_df, entry_idx, h)
        if fp is not None and entry_price:
            ret = (fp - entry_price) / entry_price * 100
            result["returns"][h] = ret
            any_computed = True
            if h == REPRESENTATIVE_HORIZON:
                result["judgment_5d"] = _judge_return(ret)

    result["status"] = "계산 완료" if any_computed else "대기"
    return result


def build_no_recommendation_rows():
    """report_items가 0개인 "오늘 추천 없음" report에 대해 기회비용/위험회피를 평가한다.

    market_scope=KR -> KOSPI 1건, US -> SPY 1건, MIXED -> KOSPI/SPY 각각 1건(합쳐서 2건).
    """
    rows = []
    for report in db.list_reports():
        if db.get_report_items(report["id"]):
            continue  # 종목 항목이 있는 report는 대상 아님

        market_scope = report.get("market_scope")
        if market_scope == "KR":
            rows.append(_evaluate_benchmark_for_no_rec(report, "KOSPI", "KR"))
        elif market_scope == "US":
            rows.append(_evaluate_benchmark_for_no_rec(report, "SPY", "US"))
        elif market_scope == "MIXED":
            rows.append(_evaluate_benchmark_for_no_rec(report, "KOSPI", "KR"))
            rows.append(_evaluate_benchmark_for_no_rec(report, "SPY", "US"))
    return rows
