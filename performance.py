"""읽기 기반 성과검증(1차). 저장된 report_items 중 ticker가 있는 종목만 대상으로 한다.

docs/STAGE2_PERFORMANCE_SPEC.md의 진입가 규칙/검증 기간/기준지수 결정을 따른다.
자동매매, 매수/매도 신호, 증권사 API, 실시간 시세 연결과는 무관한 사후 배치 조회다.
report_items가 0개인 "오늘 추천 없음" report의 기회비용/위험회피 평가도 포함한다
(market_scope별 기준지수: KR->KOSPI, US->SPY, MIXED->KOSPI/SPY 분리 표시).
"""

import json
import math
import statistics
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


# ---- report_item_outcomes 저장용 순수 매핑 (DB 접근 없음, 3단계: 이후 별도 저장 단계에서
# database.py의 upsert_report_item_outcome()을 호출할 때 이 함수의 결과를 그대로 넘긴다) ----

def _is_valid_finite_number(value, require_positive):
    """bool/None/비유한(NaN, Infinity)/비숫자를 전부 걸러내는 순수 검증 헬퍼.

    성과 저장 후보 판정에만 쓰며, DB에는 접근하지 않는다.
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    if not math.isfinite(value):
        return False
    if require_positive and value <= 0:
        return False
    return True


def build_judgment_outcome_rows(report_item_id, evaluation_result):
    """evaluate_item()의 반환값(evaluation_result)을 report_item_outcomes 저장 형식의
    list[dict]로 변환하는 순수 매핑 함수다. DB 연결/INSERT/UPDATE를 전혀 하지 않으며,
    upsert_report_item_outcome()도 호출하지 않는다 — 이후 별도 저장 단계에서 이 함수의
    반환값을 그대로 그 함수에 넘기는 용도다.

    entry_basis='judgment', status='evaluated' 후보만 만든다. 정상 계산이 완료된 horizon
    (1/3/5/10/20)만 포함하고, entry_price_used/target_date/close_price/return_pct 중
    하나라도 비어 있거나 비정상이면 그 horizon만 조용히 제외한다(pending/unavailable/
    error로 추정해서 채우지 않는다 — 그 상태들은 이 함수의 책임이 아니다). evaluation_result
    딕셔너리 자체는 수정하지 않는다(읽기만 함).

    반환 행 하나가 만들어지려면 다음이 전부 충족되어야 한다:
    - report_item_id가 bool이 아닌 양의 정수
    - entry_price_used가 0보다 큰 유한 숫자
    - target_date가 비어 있지 않음
    - close_price가 0보다 큰 유한 숫자
    - return_pct가 유한 숫자(부호 무관)
    benchmark_return_pct/excess_return_pct는 유한 숫자면 싣고, 없거나 비정상이면 None으로만
    채우고 그 이유로 행 자체를 제외하지 않는다. 새로 벤치마크를 계산하거나 추정하지 않고
    evaluation_result에 이미 있는 값만 그대로 옮긴다. high_price/low_price는 현재
    evaluate_item()에 데이터가 없으므로 항상 None이다(임의 계산 금지).
    """
    if not isinstance(evaluation_result, dict):
        raise ValueError(f"evaluation_result must be a dict, got {type(evaluation_result)!r}")
    if (
        isinstance(report_item_id, bool)
        or not isinstance(report_item_id, int)
        or report_item_id <= 0
    ):
        raise ValueError(
            f"report_item_id must be a positive int (not bool), got {report_item_id!r}"
        )

    outcome_details = evaluation_result.get("outcome_details")
    if not isinstance(outcome_details, dict):
        return []

    entry_price_used = evaluation_result.get("entry_price_used")
    if not _is_valid_finite_number(entry_price_used, require_positive=True):
        return []

    benchmark_symbol = evaluation_result.get("benchmark_symbol")

    rows = []
    for horizon in HORIZONS:
        detail = outcome_details.get(horizon)
        if not isinstance(detail, dict):
            continue

        target_date = detail.get("target_date")
        if not target_date:
            continue

        close_price = detail.get("close_price")
        if not _is_valid_finite_number(close_price, require_positive=True):
            continue

        return_pct = detail.get("return_pct")
        if not _is_valid_finite_number(return_pct, require_positive=False):
            continue

        benchmark_return_pct = detail.get("benchmark_return_pct")
        if not _is_valid_finite_number(benchmark_return_pct, require_positive=False):
            benchmark_return_pct = None

        excess_return_pct = detail.get("excess_return_pct")
        if not _is_valid_finite_number(excess_return_pct, require_positive=False):
            excess_return_pct = None

        rows.append(
            {
                "report_item_id": report_item_id,
                "horizon_sessions": horizon,
                "entry_basis": "judgment",
                "entry_price_used": float(entry_price_used),
                "target_date": target_date,
                "close_price": float(close_price),
                "high_price": None,
                "low_price": None,
                "return_pct": float(return_pct),
                "benchmark_symbol": benchmark_symbol,
                "benchmark_return_pct": (
                    float(benchmark_return_pct) if benchmark_return_pct is not None else None
                ),
                "excess_return_pct": (
                    float(excess_return_pct) if excess_return_pct is not None else None
                ),
                "status": "evaluated",
                "evaluated_at": None,
            }
        )

    return rows


# ---- 실제 매매(actual) 성과 계산 (DB 접근/네트워크 조회 없음, evaluate_item()과 완전히
# 분리된 독립 경로) — 이후 별도 저장 단계에서 database.py의 upsert_report_item_outcome(s)를
# 호출할 때 build_actual_outcome_rows()의 결과를 그대로 넘긴다. 이번 단계에서는 계산·매핑
# 함수만 추가하며 DB 저장/버튼/UI는 만들지 않는다. ----

def _dedup_sorted_price_df(df):
    """가격 df를 날짜 오름차순으로 정렬하고, 같은 날짜가 중복되면 첫 번째 행만 남긴 새
    DataFrame을 반환한다(입력 df는 수정하지 않는다). evaluate_actual_item() 전용 안전장치이며,
    기존 judgment 계산 경로(_entry_point/_future_close/_future_point)는 건드리지 않는다.
    """
    sorted_df = df.sort_index()
    return sorted_df[~sorted_df.index.duplicated(keep="first")]


def evaluate_actual_item(item, price_df, benchmark_df=None):
    """report_items 한 행(item)의 실제 매매(actual) 성과를 계산한다.

    기준가격은 item["actual_entry_price"], 기준일은 item["actual_entry_date"]다(사후에
    사용자가 입력한 실제 체결 정보 — 저장 당시 판단용 entry_price/evaluate_item()의
    판단 기준가와는 다른 별개 값이며 서로 섞지 않는다). price_df/benchmark_df는 호출자가
    이미 조회해 전달한 DataFrame만 쓰고, 이 함수 자체는 네트워크 조회를 하지 않으며
    evaluate_item()도 호출하지 않는다(완전히 독립된 계산 경로). 입력 item/price_df/
    benchmark_df는 전혀 수정하지 않는다.

    actual_action이 '매수'가 아니거나 actual_entry_price/actual_entry_date 중 하나라도
    없으면 outcome_details가 전부 None인 빈 결과를 반환한다(조용히, 예외 없음). 값이
    존재하는데 형식이 잘못되면(가격이 bool/0 이하/비유한, 날짜가 실제 YYYY-MM-DD가
    아님) ValueError를 던진다 — database.py의 normalize_actual_entry_date()를 그대로
    재사용해 UPDATE 경로와 검증 규칙이 갈라지지 않게 한다.

    horizon 1은 actual_entry_date "다음" 첫 거래일이다(매수 당일 종가는 horizon에서
    제외). price_df/benchmark_df는 날짜 오름차순 정렬 + 중복 날짜 제거 후 사용하며,
    entry_date보다 엄격히 뒤인 거래일만 대상으로 순서대로 horizon 1/3/5/10/20에 배정한다.
    아직 그만큼 거래일이 지나지 않은 horizon은 해당 세부값이 전부 None이다.
    """
    ticker = (item.get("ticker") or "").strip()
    market = item.get("market")
    benchmark_symbol = determine_benchmark(market, ticker)

    empty_result = {
        "entry_price_used": None,
        "entry_date_used": None,
        "benchmark_symbol": benchmark_symbol,
        "outcome_details": _empty_outcome_details(),
    }

    if item.get("actual_action") != "매수":
        return empty_result

    actual_entry_price = item.get("actual_entry_price")
    actual_entry_date = item.get("actual_entry_date")
    if actual_entry_price is None or actual_entry_date is None:
        return empty_result

    if not _is_valid_finite_number(actual_entry_price, require_positive=True):
        raise ValueError(
            f"actual_entry_price must be a positive finite number, got {actual_entry_price!r}"
        )
    normalized_entry_date = db.normalize_actual_entry_date(actual_entry_date)
    if normalized_entry_date is None:
        return empty_result

    entry_price_float = float(actual_entry_price)

    result = {
        "entry_price_used": entry_price_float,
        "entry_date_used": normalized_entry_date,
        "benchmark_symbol": benchmark_symbol,
        "outcome_details": _empty_outcome_details(),
    }

    if price_df is None or price_df.empty:
        return result

    entry_date_ts = pd.Timestamp(normalized_entry_date)
    price_df_clean = _dedup_sorted_price_df(price_df)
    future_dates = price_df_clean.index[price_df_clean.index > entry_date_ts]

    bench_df_clean = None
    # benchmark_symbol이 None(OTHER 시장 등 결정 불가)이면 benchmark_df가 전달됐더라도
    # 쓰지 않는다 — OTHER 시장은 벤치마크 값이 전부 None이어야 한다.
    if benchmark_symbol is not None and benchmark_df is not None and not benchmark_df.empty:
        bench_df_clean = _dedup_sorted_price_df(benchmark_df)

    # 벤치마크 기준가는 실제 체결 시각의 지수값이 아니라 매수 거래일 종가를 쓰는
    # 근사치다(정확히 같은 날짜의 벤치마크 종가가 없으면 이전/다음 날짜로 대체하지 않음).
    bench_entry_price = None
    if bench_df_clean is not None and entry_date_ts in bench_df_clean.index:
        bench_entry_price = float(bench_df_clean.loc[entry_date_ts, "Close"])

    outcome_details = {}
    for h in HORIZONS:
        if len(future_dates) < h:
            outcome_details[h] = _empty_outcome_detail()
            continue

        target_date = future_dates[h - 1]
        close_price = float(price_df_clean.loc[target_date, "Close"])
        return_pct = (close_price / entry_price_float - 1) * 100

        benchmark_return_pct = None
        if (
            bench_entry_price is not None
            and bench_df_clean is not None
            and target_date in bench_df_clean.index
        ):
            bench_close_price = float(bench_df_clean.loc[target_date, "Close"])
            benchmark_return_pct = (bench_close_price / bench_entry_price - 1) * 100

        excess_return_pct = None
        if benchmark_return_pct is not None:
            excess_return_pct = return_pct - benchmark_return_pct

        outcome_details[h] = {
            "target_date": target_date.strftime("%Y-%m-%d"),
            "close_price": close_price,
            "return_pct": return_pct,
            "benchmark_return_pct": benchmark_return_pct,
            "excess_return_pct": excess_return_pct,
        }

    result["outcome_details"] = outcome_details
    return result


def build_actual_outcome_rows(report_item_id, evaluation_result):
    """evaluate_actual_item()의 반환값(evaluation_result)을 report_item_outcomes 저장
    형식의 list[dict]로 변환하는 순수 매핑 함수다. DB 연결/INSERT/UPDATE를 전혀 하지
    않으며, upsert_report_item_outcome(s)도 호출하지 않는다 —
    build_judgment_outcome_rows()와 검증 규칙은 동일하되 entry_basis만 'actual'이다.

    entry_basis='actual', status='evaluated' 후보만 만든다. 정상 계산이 완료된 horizon
    (1/3/5/10/20)만 포함하고, entry_price_used/target_date/close_price/return_pct 중
    하나라도 비어 있거나 비정상이면 그 horizon만 조용히 제외한다(나머지 정상 horizon은
    유지). evaluation_result 딕셔너리 자체는 수정하지 않는다(읽기만 함). high_price/
    low_price는 현재 evaluate_actual_item()에 데이터가 없으므로 항상 None이다.
    """
    if not isinstance(evaluation_result, dict):
        raise ValueError(f"evaluation_result must be a dict, got {type(evaluation_result)!r}")
    if (
        isinstance(report_item_id, bool)
        or not isinstance(report_item_id, int)
        or report_item_id <= 0
    ):
        raise ValueError(
            f"report_item_id must be a positive int (not bool), got {report_item_id!r}"
        )

    outcome_details = evaluation_result.get("outcome_details")
    if not isinstance(outcome_details, dict):
        return []

    entry_price_used = evaluation_result.get("entry_price_used")
    if not _is_valid_finite_number(entry_price_used, require_positive=True):
        return []

    benchmark_symbol = evaluation_result.get("benchmark_symbol")

    rows = []
    for horizon in HORIZONS:
        detail = outcome_details.get(horizon)
        if not isinstance(detail, dict):
            continue

        target_date = detail.get("target_date")
        if not target_date:
            continue

        close_price = detail.get("close_price")
        if not _is_valid_finite_number(close_price, require_positive=True):
            continue

        return_pct = detail.get("return_pct")
        if not _is_valid_finite_number(return_pct, require_positive=False):
            continue

        benchmark_return_pct = detail.get("benchmark_return_pct")
        if not _is_valid_finite_number(benchmark_return_pct, require_positive=False):
            benchmark_return_pct = None

        excess_return_pct = detail.get("excess_return_pct")
        if not _is_valid_finite_number(excess_return_pct, require_positive=False):
            excess_return_pct = None

        rows.append(
            {
                "report_item_id": report_item_id,
                "horizon_sessions": horizon,
                "entry_basis": "actual",
                "entry_price_used": float(entry_price_used),
                "target_date": target_date,
                "close_price": float(close_price),
                "high_price": None,
                "low_price": None,
                "return_pct": float(return_pct),
                "benchmark_symbol": benchmark_symbol,
                "benchmark_return_pct": (
                    float(benchmark_return_pct) if benchmark_return_pct is not None else None
                ),
                "excess_return_pct": (
                    float(excess_return_pct) if excess_return_pct is not None else None
                ),
                "status": "evaluated",
                "evaluated_at": None,
            }
        )

    return rows


# ---- 판단(judgment) 대 실매매(actual) 순수 비교 (DB 접근/네트워크 조회/UI 출력 없음) ----
# report_item_outcomes를 수정하지 않으며, 좋음/나쁨 판정이나 점수는 만들지 않는다 —
# 원시 수치 차이(gap)만 계산한다.

def _sanitize_comparison_number(value):
    """유한 숫자(bool 제외)만 그대로 반환하고, 그 외(None/NaN/Infinity/bool/비숫자)는
    None으로 정규화한다. build_judgment_actual_comparison_rows() 전용 안전장치다.
    """
    if _is_valid_finite_number(value, require_positive=False):
        return value
    return None


def build_judgment_actual_comparison_rows(outcome_rows):
    """db.get_report_outcomes(report_id) 형식의 행 목록에서 같은 (report_item_id,
    horizon_sessions)에 대해 entry_basis='judgment'와 entry_basis='actual'이 모두
    존재하고 둘 다 status='evaluated'인 경우만 판단 대 실매매 수익률 차이를 비교하는
    list[dict]를 만드는 순수 함수다. DB 연결/INSERT/UPDATE, 가격·벤치마크 네트워크
    조회, UI 출력을 전혀 하지 않는다. 입력 outcome_rows와 그 안의 각 행 dict는
    수정하지 않는다(읽기만 함).

    같은 (report_item_id, horizon_sessions, entry_basis) 키가 입력에 두 번 이상
    나오면 어느 쪽을 쓸지 조용히 임의로 고르지 않고 ValueError를 던진다.
    judgment/actual 중 한쪽만 있거나 둘 중 하나라도 status가 'evaluated'가 아니면
    그 (report_item_id, horizon_sessions)는 비교 행을 만들지 않고 조용히 제외한다
    (실제 행동이 '매수'가 아닌 종목은 actual 행 자체가 없으므로 자연스럽게 제외됨).
    return_gap_pct/excess_return_gap_pct는 두 값이 전부 유효한 유한 숫자일 때만
    계산하고, 하나라도 없거나 NaN/Infinity/bool이면 None이다. 좋음/나쁨 판정이나
    점수는 만들지 않는다.
    """
    rows_by_key = {}
    for row in outcome_rows:
        entry_basis = row.get("entry_basis")
        if entry_basis not in ("judgment", "actual"):
            continue
        key = (row.get("report_item_id"), row.get("horizon_sessions"), entry_basis)
        if key in rows_by_key:
            raise ValueError(
                "duplicate (report_item_id, horizon_sessions, entry_basis) in "
                f"outcome_rows: {key!r}"
            )
        rows_by_key[key] = row

    seen_pairs = {
        (report_item_id, horizon_sessions)
        for (report_item_id, horizon_sessions, _entry_basis) in rows_by_key
    }

    comparison_rows = []
    for report_item_id, horizon_sessions in sorted(seen_pairs):
        judgment_row = rows_by_key.get((report_item_id, horizon_sessions, "judgment"))
        actual_row = rows_by_key.get((report_item_id, horizon_sessions, "actual"))
        if judgment_row is None or actual_row is None:
            continue
        if judgment_row.get("status") != "evaluated" or actual_row.get("status") != "evaluated":
            continue

        judgment_entry_price = _sanitize_comparison_number(judgment_row.get("entry_price_used"))
        actual_entry_price = _sanitize_comparison_number(actual_row.get("entry_price_used"))
        judgment_return_pct = _sanitize_comparison_number(judgment_row.get("return_pct"))
        actual_return_pct = _sanitize_comparison_number(actual_row.get("return_pct"))
        judgment_excess_return_pct = _sanitize_comparison_number(
            judgment_row.get("excess_return_pct")
        )
        actual_excess_return_pct = _sanitize_comparison_number(
            actual_row.get("excess_return_pct")
        )

        return_gap_pct = None
        if judgment_return_pct is not None and actual_return_pct is not None:
            return_gap_pct = actual_return_pct - judgment_return_pct

        excess_return_gap_pct = None
        if judgment_excess_return_pct is not None and actual_excess_return_pct is not None:
            excess_return_gap_pct = actual_excess_return_pct - judgment_excess_return_pct

        comparison_rows.append(
            {
                "report_item_id": report_item_id,
                "종목명": actual_row.get("item_name") or judgment_row.get("item_name"),
                "ticker": actual_row.get("ticker") or judgment_row.get("ticker"),
                "market": actual_row.get("market") or judgment_row.get("market"),
                "horizon_sessions": horizon_sessions,
                "judgment_entry_price": judgment_entry_price,
                "actual_entry_price": actual_entry_price,
                "judgment_return_pct": judgment_return_pct,
                "actual_return_pct": actual_return_pct,
                "return_gap_pct": return_gap_pct,
                "judgment_excess_return_pct": judgment_excess_return_pct,
                "actual_excess_return_pct": actual_excess_return_pct,
                "excess_return_gap_pct": excess_return_gap_pct,
            }
        )

    return comparison_rows


# ---- 판단 잔차 분석용 원자료 (DB 접근/네트워크 조회/UI 출력/통계/자동 판정/점수화 없음) ----
# report_item_outcomes를 수정하지 않으며, 좋음/나쁨·실수·기회손실·손실회피 같은 라벨이나
# 임계값·점수는 만들지 않는다 — judgment 성과와 실제 행동/actual 성과를 나란히 놓은
# 원시 수치 자료만 만든다.

def build_decision_residual_rows(outcome_rows):
    """db.get_report_outcomes(report_id) 형식의 행 목록에서 report_item_id+horizon_sessions
    단위로 저장된 judgment 성과와 실제 행동(actual_action)/actual 성과를 결합해 판단 잔차
    분석용 원자료 list[dict]를 만드는 순수 함수다. DB 연결/INSERT/UPDATE, 가격·벤치마크
    네트워크 조회, UI 출력을 전혀 하지 않는다. 입력 outcome_rows와 그 안의 각 행 dict는
    수정하지 않는다(읽기만 함).

    judgment 행이 있고 status='evaluated'인 (report_item_id, horizon_sessions)만 결과를
    만든다(judgment가 없거나 미완료면 그 키는 제외). actual 행은 있으면 결합하되 status가
    'evaluated'가 아니면 actual 값을 쓰지 않고(judgment 행 자체는 그대로 유지), actual
    행이 아예 없어도 judgment 원자료 행은 유지한다 — 매수했지만 아직 actual 성과가
    계산되지 않은 경우도 포함하기 위함이다. actual_action은 매수/보류/제외/미기록(None)
    그대로 사용하며 어떤 값이든 행을 제외하지 않는다.

    entry_effect_pct = actual_return_pct - judgment_return_pct (둘 다 유효할 때만),
    entry_excess_effect_pct = actual_excess_return_pct - judgment_excess_return_pct
    (둘 다 유효할 때만). non_buy_return_pct/non_buy_excess_return_pct는 actual_action이
    '보류' 또는 '제외'일 때만 judgment_return_pct/judgment_excess_return_pct를 그대로
    옮기고, 그 외에는 None이다. 수익률의 양수/음수만으로 성공/실패를 자동 판정하지
    않으며, 좋음/나쁨·실수·기회손실·손실회피 같은 라벨이나 임계값·점수는 만들지 않는다.

    같은 (report_item_id, horizon_sessions, entry_basis) 키가 입력에 두 번 이상 나오면
    조용히 임의로 고르지 않고 ValueError를 던진다. 정렬은 report_item_id,
    horizon_sessions 오름차순이다.

    저장 당시 판단 맥락(report_id/report_saved_at/trade_mode/verdict/signal_type/
    event_name/briefing_stage/timing_class)을 judgment 행에서 그대로 옮겨 담는다 —
    입력 행에 있는 값을 그대로 전달할 뿐 임의로 보정하지 않으며, 키가 없으면 None이다
    (빈 문자열을 다른 값으로 바꾸지 않음). 기존 수익률·진입 효과·미매수 성과 계산과
    반환 필드는 전혀 바뀌지 않는다 — 이 맥락 필드들은 순수 추가다.
    """
    rows_by_key = {}
    for row in outcome_rows:
        entry_basis = row.get("entry_basis")
        if entry_basis not in ("judgment", "actual"):
            continue
        key = (row.get("report_item_id"), row.get("horizon_sessions"), entry_basis)
        if key in rows_by_key:
            raise ValueError(
                "duplicate (report_item_id, horizon_sessions, entry_basis) in "
                f"outcome_rows: {key!r}"
            )
        rows_by_key[key] = row

    judgment_pairs = sorted(
        {
            (report_item_id, horizon_sessions)
            for (report_item_id, horizon_sessions, entry_basis) in rows_by_key
            if entry_basis == "judgment"
        }
    )

    residual_rows = []
    for report_item_id, horizon_sessions in judgment_pairs:
        judgment_row = rows_by_key[(report_item_id, horizon_sessions, "judgment")]
        if judgment_row.get("status") != "evaluated":
            continue

        actual_row = rows_by_key.get((report_item_id, horizon_sessions, "actual"))
        actual_evaluated = actual_row is not None and actual_row.get("status") == "evaluated"

        judgment_entry_price = _sanitize_comparison_number(judgment_row.get("entry_price_used"))
        judgment_return_pct = _sanitize_comparison_number(judgment_row.get("return_pct"))
        judgment_excess_return_pct = _sanitize_comparison_number(
            judgment_row.get("excess_return_pct")
        )

        actual_entry_price = None
        actual_return_pct = None
        actual_excess_return_pct = None
        if actual_evaluated:
            actual_entry_price = _sanitize_comparison_number(actual_row.get("entry_price_used"))
            actual_return_pct = _sanitize_comparison_number(actual_row.get("return_pct"))
            actual_excess_return_pct = _sanitize_comparison_number(
                actual_row.get("excess_return_pct")
            )

        entry_effect_pct = None
        if judgment_return_pct is not None and actual_return_pct is not None:
            entry_effect_pct = actual_return_pct - judgment_return_pct

        entry_excess_effect_pct = None
        if judgment_excess_return_pct is not None and actual_excess_return_pct is not None:
            entry_excess_effect_pct = actual_excess_return_pct - judgment_excess_return_pct

        actual_action = judgment_row.get("actual_action")

        non_buy_return_pct = None
        non_buy_excess_return_pct = None
        if actual_action in ("보류", "제외"):
            non_buy_return_pct = judgment_return_pct
            non_buy_excess_return_pct = judgment_excess_return_pct

        residual_rows.append(
            {
                "report_item_id": report_item_id,
                "report_id": judgment_row.get("report_id"),
                "report_saved_at": judgment_row.get("report_saved_at"),
                "trade_mode": judgment_row.get("trade_mode"),
                "verdict": judgment_row.get("verdict"),
                "signal_type": judgment_row.get("signal_type"),
                "event_name": judgment_row.get("event_name"),
                "briefing_stage": judgment_row.get("briefing_stage"),
                "timing_class": judgment_row.get("timing_class"),
                "종목명": judgment_row.get("item_name"),
                "ticker": judgment_row.get("ticker"),
                "market": judgment_row.get("market"),
                "theme_tags": judgment_row.get("theme_tags"),
                "actual_action": actual_action,
                "horizon_sessions": horizon_sessions,
                "judgment_entry_price": judgment_entry_price,
                "judgment_return_pct": judgment_return_pct,
                "judgment_excess_return_pct": judgment_excess_return_pct,
                "actual_entry_price": actual_entry_price,
                "actual_return_pct": actual_return_pct,
                "actual_excess_return_pct": actual_excess_return_pct,
                "entry_effect_pct": entry_effect_pct,
                "entry_excess_effect_pct": entry_excess_effect_pct,
                "non_buy_return_pct": non_buy_return_pct,
                "non_buy_excess_return_pct": non_buy_excess_return_pct,
            }
        )

    return residual_rows


# ---- 행동별·거래일수별 순수 집계 (DB 접근/네트워크 조회/UI 출력/자동 판정/점수화 없음) ----
# report_item_outcomes를 수정하지 않으며, 양수 비율을 승률이라 부르지 않고 성공/실패·
# 실수·기회손실·손실회피 라벨이나 최소 표본 기준·점수·추천을 만들지 않는다.

_ACTION_RESIDUAL_KNOWN_ACTIONS = ("매수", "보류", "제외")
_ACTION_RESIDUAL_ORDER = {"매수": 0, "보류": 1, "제외": 2, "미기록": 3}


def _collect_valid_finite_values(rows, field_name):
    """rows에서 field_name 값이 유한 숫자(bool 제외)인 것만 뽑아 list로 반환한다.
    None/NaN/Infinity/bool/비숫자는 제외한다(read-only, rows/row는 수정하지 않음).
    """
    return [
        row.get(field_name)
        for row in rows
        if _is_valid_finite_number(row.get(field_name), require_positive=False)
    ]


def _summarize_values(values):
    """유효 수치 list에서 (count, avg, median)을 계산한다. 표본이 0건이면 avg/median은
    None이다. 반올림하지 않고 내부 계산 정밀도를 그대로 유지한다."""
    count = len(values)
    if count == 0:
        return count, None, None
    return count, statistics.mean(values), statistics.median(values)


def build_action_residual_summary(residual_rows):
    """build_decision_residual_rows()의 결과를 여러 보고서에서 합친 행 목록을 받아
    actual_action(매수/보류/제외/미기록) × horizon_sessions 기준으로 집계하는 순수
    통계 함수다. DB 연결/INSERT/UPDATE, 네트워크 조회, UI 출력을 전혀 하지 않는다.
    입력 residual_rows와 그 안의 각 행 dict는 수정하지 않는다(읽기만 함).

    같은 종목이 여러 보고서나 horizon에 걸쳐 여러 번 나와도 입력 행 그대로 각각을
    독립 표본으로 집계한다 — 임의로 중복 제거하지 않는다. 최소 표본 수 기준을
    적용하지 않으며, 양수 비율을 승률이라 부르지 않고 성공/실패·실수·기회손실·
    손실회피 라벨이나 점수·추천은 만들지 않는다.

    entry_effect 통계는 actual_action='매수'인 그룹에서만 entry_effect_pct가 정상인
    행만 계산한다(actual 성과가 아직 없는 매수 행은 count에서 자연히 제외됨).
    non_buy 통계는 actual_action이 '보류' 또는 '제외'인 그룹에서만 non_buy_return_pct/
    non_buy_excess_return_pct를 집계하며, '매수'·'미기록' 그룹에서는 해당 값이 있어도
    집계하지 않는다.

    actual_action이 None이거나 빈(공백 포함) 문자열이면 '미기록'으로 정규화한다.
    '매수'/'보류'/'제외'/None·빈 문자열 외의 값이 오면 조용히 미기록으로 합치지 않고
    ValueError를 던진다. horizon_sessions는 bool이 아닌 양의 정수여야 하며, 아니면
    ValueError를 던진다. 이런 검증은 결과를 만들기 전에 전체 입력을 먼저 훑어 확인하므로
    잘못된 행 하나 때문에 일부만 반영된 왜곡된 통계가 반환되지 않는다.

    정렬은 horizon_sessions 오름차순, 같은 horizon 안에서는 매수 -> 보류 -> 제외 ->
    미기록 순이다.
    """
    if not isinstance(residual_rows, (list, tuple)):
        raise ValueError(
            f"residual_rows must be a list or tuple, got {type(residual_rows)!r}"
        )

    groups = {}
    for idx, row in enumerate(residual_rows):
        if not isinstance(row, dict):
            raise ValueError(f"residual_rows[{idx}] must be a dict, got {type(row)!r}")

        raw_action = row.get("actual_action")
        if raw_action is None or (isinstance(raw_action, str) and raw_action.strip() == ""):
            action = "미기록"
        elif raw_action in _ACTION_RESIDUAL_KNOWN_ACTIONS:
            action = raw_action
        else:
            raise ValueError(
                f"residual_rows[{idx}] has unknown actual_action: {raw_action!r}"
            )

        horizon_sessions = row.get("horizon_sessions")
        if (
            isinstance(horizon_sessions, bool)
            or not isinstance(horizon_sessions, int)
            or horizon_sessions <= 0
        ):
            raise ValueError(
                f"residual_rows[{idx}] horizon_sessions must be a positive int (not bool), "
                f"got {horizon_sessions!r}"
            )

        groups.setdefault((action, horizon_sessions), []).append(row)

    summary_rows = []
    for (action, horizon_sessions), rows in groups.items():
        sample_count = len(rows)

        judgment_return_values = _collect_valid_finite_values(rows, "judgment_return_pct")
        judgment_return_count, judgment_return_avg, judgment_return_median = (
            _summarize_values(judgment_return_values)
        )
        judgment_positive_count = sum(1 for v in judgment_return_values if v > 0)
        judgment_positive_rate = (
            judgment_positive_count / judgment_return_count * 100
            if judgment_return_count > 0
            else None
        )

        judgment_excess_values = _collect_valid_finite_values(
            rows, "judgment_excess_return_pct"
        )
        judgment_excess_count, judgment_excess_avg, _judgment_excess_median = (
            _summarize_values(judgment_excess_values)
        )

        entry_effect_values = (
            _collect_valid_finite_values(rows, "entry_effect_pct") if action == "매수" else []
        )
        entry_effect_count, entry_effect_avg, entry_effect_median = _summarize_values(
            entry_effect_values
        )

        if action in ("보류", "제외"):
            non_buy_return_values = _collect_valid_finite_values(rows, "non_buy_return_pct")
            non_buy_excess_values = _collect_valid_finite_values(
                rows, "non_buy_excess_return_pct"
            )
        else:
            non_buy_return_values = []
            non_buy_excess_values = []

        non_buy_return_count, non_buy_return_avg, non_buy_return_median = _summarize_values(
            non_buy_return_values
        )
        non_buy_positive_count = sum(1 for v in non_buy_return_values if v > 0)
        non_buy_positive_rate = (
            non_buy_positive_count / non_buy_return_count * 100
            if non_buy_return_count > 0
            else None
        )
        non_buy_excess_count, non_buy_excess_avg, _non_buy_excess_median = _summarize_values(
            non_buy_excess_values
        )

        summary_rows.append(
            {
                "actual_action": action,
                "horizon_sessions": horizon_sessions,
                "sample_count": sample_count,
                "judgment_return_count": judgment_return_count,
                "judgment_return_avg": judgment_return_avg,
                "judgment_return_median": judgment_return_median,
                "judgment_positive_count": judgment_positive_count,
                "judgment_positive_rate": judgment_positive_rate,
                "judgment_excess_count": judgment_excess_count,
                "judgment_excess_avg": judgment_excess_avg,
                "entry_effect_count": entry_effect_count,
                "entry_effect_avg": entry_effect_avg,
                "entry_effect_median": entry_effect_median,
                "non_buy_return_count": non_buy_return_count,
                "non_buy_return_avg": non_buy_return_avg,
                "non_buy_return_median": non_buy_return_median,
                "non_buy_positive_count": non_buy_positive_count,
                "non_buy_positive_rate": non_buy_positive_rate,
                "non_buy_excess_count": non_buy_excess_count,
                "non_buy_excess_avg": non_buy_excess_avg,
            }
        )

    summary_rows.sort(
        key=lambda s: (s["horizon_sessions"], _ACTION_RESIDUAL_ORDER[s["actual_action"]])
    )
    return summary_rows


# ---- 테마 태그 × 거래일수 × 실제 행동 순수 집계 (DB 접근/네트워크 조회/UI 출력/자동 판정/
# 점수화/추천 없음) ----

_THEME_RESIDUAL_UNSPECIFIED = "미지정"


def _extract_theme_tags(value):
    """theme_tags 값(JSON 배열 문자열 또는 list/tuple)에서 정리된 태그 list를 만든다.

    각 태그는 앞뒤 공백을 제거하고 빈 문자열은 버리며, 같은 값 안에서 중복된 태그는
    한 번만 남긴다(최초 등장 순서 유지). 원본에 태그가 전혀 없으면(None/빈·공백
    문자열/빈 리스트/공백만 있던 태그들) 빈 list를 반환한다 — 호출부에서 '미지정'으로
    처리한다. JSON 파싱 실패, JSON이 리스트로 디코드되지 않는 경우, list/tuple/문자열이
    아닌 지원하지 않는 자료형, 문자열이 아닌 리스트 원소가 있으면 ValueError를 던진다
    (기존 database.py의 parse_theme_tags()는 오류를 조용히 삼키고 빈 리스트를 반환하는
    화면 렌더링용 헬퍼라 이 함수의 '잘못된 입력은 ValueError' 요구와 맞지 않아 별도로
    둔다).
    """
    if value is None:
        return []
    if isinstance(value, str):
        if value.strip() == "":
            return []
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"theme_tags is not valid JSON: {value!r} ({exc})")
        if not isinstance(parsed, list):
            raise ValueError(
                f"theme_tags JSON must decode to a list, got {type(parsed)!r}"
            )
        raw_tags = parsed
    elif isinstance(value, (list, tuple)):
        raw_tags = list(value)
    else:
        raise ValueError(
            f"theme_tags must be a JSON string, list, or tuple, got {type(value)!r}"
        )

    cleaned = []
    seen = set()
    for tag in raw_tags:
        if not isinstance(tag, str):
            raise ValueError(f"theme_tags entries must be strings, got {tag!r}")
        stripped = tag.strip()
        if not stripped or stripped in seen:
            continue
        seen.add(stripped)
        cleaned.append(stripped)
    return cleaned


def build_theme_residual_summary(residual_rows):
    """build_decision_residual_rows()의 결과를 여러 보고서에서 합친 목록을 받아
    theme_tag × horizon_sessions × actual_action(매수/보류/제외/미기록) 기준으로
    집계하는 순수 통계 함수다. DB 연결/INSERT/UPDATE, 네트워크 조회, UI 출력을 전혀
    하지 않는다. 입력 residual_rows와 그 안의 각 행 dict는 수정하지 않는다(읽기만 함).

    한 행에 태그가 여러 개면 각 테마 그룹에 한 번씩 표본으로 포함된다 — 따라서
    sample_count는 고유 종목 수가 아니라 '테마-성과 행 연결 수'다. 태그가 없는 행은
    theme_tag='미지정' 그룹에 포함된다. 여러 보고서에 같은 종목이 있어도 입력된 각
    기록을 별도 표본으로 쓰며 임의로 중복 제거하지 않는다.

    judgment 통계(수익률/초과수익률 평균·중앙값·양수 개수·비율)는 모든 행동 그룹에서
    정상값만으로 계산한다. entry_effect 통계는 actual_action='매수' 그룹에서만
    entry_effect_pct가 정상인 행으로 계산하고, non_buy 통계는 '보류' 또는 '제외'
    그룹에서만 non_buy_return_pct/non_buy_excess_return_pct로 계산한다 — '미기록'
    그룹에서는 둘 다 집계하지 않는다(다른 그룹에 오염된 값이 있어도 무시).
    None/NaN/Infinity/bool은 유효 숫자에서 제외하고, 평균·중앙값은 유효 표본이 0이면
    None이다. 반환값은 반올림하지 않고 내부 계산 정밀도를 유지한다. 양수 비율을
    승률이라 부르지 않으며, 성공/실패·기회손실·손실회피 라벨이나 최소 표본 기준·
    테마 점수·매수 추천은 만들지 않는다.

    actual_action이 None이거나 빈(공백 포함) 문자열이면 '미기록'으로 정규화한다.
    '매수'/'보류'/'제외'/None·빈 문자열 외의 값이 오면 ValueError. horizon_sessions는
    bool이 아닌 양의 정수여야 하며, 아니면 ValueError. theme_tags가 잘못된 JSON이거나
    지원하지 않는 자료형이면 ValueError. 이 검증들은 결과를 만들기 전에 전체 입력을
    먼저 훑어 확인하므로, 잘못된 행 하나 때문에 일부만 반영된 왜곡된 통계가 반환되지
    않는다.

    정렬: theme_tag 오름차순('미지정'은 항상 마지막) -> horizon_sessions 오름차순 ->
    매수 -> 보류 -> 제외 -> 미기록.
    """
    if not isinstance(residual_rows, (list, tuple)):
        raise ValueError(
            f"residual_rows must be a list or tuple, got {type(residual_rows)!r}"
        )

    prepared = []
    for idx, row in enumerate(residual_rows):
        if not isinstance(row, dict):
            raise ValueError(f"residual_rows[{idx}] must be a dict, got {type(row)!r}")

        raw_action = row.get("actual_action")
        if raw_action is None or (isinstance(raw_action, str) and raw_action.strip() == ""):
            action = "미기록"
        elif raw_action in _ACTION_RESIDUAL_KNOWN_ACTIONS:
            action = raw_action
        else:
            raise ValueError(
                f"residual_rows[{idx}] has unknown actual_action: {raw_action!r}"
            )

        horizon_sessions = row.get("horizon_sessions")
        if (
            isinstance(horizon_sessions, bool)
            or not isinstance(horizon_sessions, int)
            or horizon_sessions <= 0
        ):
            raise ValueError(
                f"residual_rows[{idx}] horizon_sessions must be a positive int (not bool), "
                f"got {horizon_sessions!r}"
            )

        try:
            tags = _extract_theme_tags(row.get("theme_tags"))
        except ValueError as exc:
            raise ValueError(f"residual_rows[{idx}] theme_tags error: {exc}")

        tag_list = tags if tags else [_THEME_RESIDUAL_UNSPECIFIED]

        prepared.append((action, horizon_sessions, tag_list, row))

    groups = {}
    for action, horizon_sessions, tag_list, row in prepared:
        for tag in tag_list:
            groups.setdefault((tag, horizon_sessions, action), []).append(row)

    summary_rows = []
    for (tag, horizon_sessions, action), rows in groups.items():
        sample_count = len(rows)

        judgment_return_values = _collect_valid_finite_values(rows, "judgment_return_pct")
        judgment_return_count, judgment_return_avg, judgment_return_median = (
            _summarize_values(judgment_return_values)
        )
        judgment_positive_count = sum(1 for v in judgment_return_values if v > 0)
        judgment_positive_rate = (
            judgment_positive_count / judgment_return_count * 100
            if judgment_return_count > 0
            else None
        )

        judgment_excess_values = _collect_valid_finite_values(
            rows, "judgment_excess_return_pct"
        )
        judgment_excess_count, judgment_excess_avg, _judgment_excess_median = (
            _summarize_values(judgment_excess_values)
        )

        entry_effect_values = (
            _collect_valid_finite_values(rows, "entry_effect_pct") if action == "매수" else []
        )
        entry_effect_count, entry_effect_avg, entry_effect_median = _summarize_values(
            entry_effect_values
        )

        if action in ("보류", "제외"):
            non_buy_return_values = _collect_valid_finite_values(rows, "non_buy_return_pct")
            non_buy_excess_values = _collect_valid_finite_values(
                rows, "non_buy_excess_return_pct"
            )
        else:
            non_buy_return_values = []
            non_buy_excess_values = []

        non_buy_return_count, non_buy_return_avg, non_buy_return_median = _summarize_values(
            non_buy_return_values
        )
        non_buy_positive_count = sum(1 for v in non_buy_return_values if v > 0)
        non_buy_positive_rate = (
            non_buy_positive_count / non_buy_return_count * 100
            if non_buy_return_count > 0
            else None
        )
        non_buy_excess_count, non_buy_excess_avg, _non_buy_excess_median = _summarize_values(
            non_buy_excess_values
        )

        summary_rows.append(
            {
                "theme_tag": tag,
                "horizon_sessions": horizon_sessions,
                "actual_action": action,
                "sample_count": sample_count,
                "judgment_return_count": judgment_return_count,
                "judgment_return_avg": judgment_return_avg,
                "judgment_return_median": judgment_return_median,
                "judgment_positive_count": judgment_positive_count,
                "judgment_positive_rate": judgment_positive_rate,
                "judgment_excess_count": judgment_excess_count,
                "judgment_excess_avg": judgment_excess_avg,
                "entry_effect_count": entry_effect_count,
                "entry_effect_avg": entry_effect_avg,
                "entry_effect_median": entry_effect_median,
                "non_buy_return_count": non_buy_return_count,
                "non_buy_return_avg": non_buy_return_avg,
                "non_buy_return_median": non_buy_return_median,
                "non_buy_positive_count": non_buy_positive_count,
                "non_buy_positive_rate": non_buy_positive_rate,
                "non_buy_excess_count": non_buy_excess_count,
                "non_buy_excess_avg": non_buy_excess_avg,
            }
        )

    def _theme_residual_sort_key(s):
        tag = s["theme_tag"]
        tag_rank = (1, "") if tag == _THEME_RESIDUAL_UNSPECIFIED else (0, tag)
        return (tag_rank, s["horizon_sessions"], _ACTION_RESIDUAL_ORDER[s["actual_action"]])

    summary_rows.sort(key=_theme_residual_sort_key)
    return summary_rows


# ---- 저장 당시 판단 맥락(단일 필드) × 거래일수 × 실제 행동 순수 집계 (DB 접근/네트워크
# 조회/UI 출력/자동 판정/점수화/순위 없음) ----

_CONTEXT_RESIDUAL_ALLOWED_GROUP_BY = (
    "trade_mode",
    "verdict",
    "signal_type",
    "event_name",
    "briefing_stage",
    "timing_class",
)
_CONTEXT_RESIDUAL_UNSPECIFIED = "미지정"


def _normalize_context_value(value):
    """맥락값을 정규화한다. None이거나 앞뒤 공백을 제거했을 때 빈 문자열이면
    '미지정'으로 취급한다. 문자열은 앞뒤 공백만 제거해서 그대로 쓰며, 대소문자나
    띄어쓰기가 다른 값을 임의로 합치거나 이름을 교정하지 않는다. 문자열이 아닌 값
    (bool/숫자/list/dict 등)은 ValueError를 던진다.
    """
    if value is None:
        return _CONTEXT_RESIDUAL_UNSPECIFIED
    if isinstance(value, bool) or not isinstance(value, str):
        raise ValueError(f"context value must be a string or None, got {value!r}")
    stripped = value.strip()
    if not stripped:
        return _CONTEXT_RESIDUAL_UNSPECIFIED
    return stripped


def build_context_residual_summary(residual_rows, group_by):
    """build_decision_residual_rows()의 결과를 여러 보고서에서 합친 목록을 받아, 저장
    당시 판단 맥락 중 group_by로 지정한 필드 하나 × horizon_sessions × actual_action
    (매수/보류/제외/미기록) 기준으로 집계하는 순수 통계 함수다. DB 연결/INSERT/UPDATE,
    네트워크 조회, UI 출력을 전혀 하지 않는다. 입력 residual_rows와 그 안의 각 행
    dict는 수정하지 않는다(읽기만 함).

    group_by는 'trade_mode'/'verdict'/'signal_type'/'event_name'/'briefing_stage'/
    'timing_class' 중 하나만 허용한다(그 외 값은 ValueError). 각 행에서 group_by
    필드값을 읽어 context_value로 쓴다 — None/빈(공백 포함) 문자열은 '미지정'으로
    정규화하고, 그 외 문자열은 앞뒤 공백만 제거한다(대소문자·띄어쓰기가 다른 값은
    별도 그룹으로 유지, 임의로 합치거나 교정하지 않음). 문자열이 아닌 값(bool/숫자/
    list/dict 등)이 있으면 ValueError. 이 함수는 group_by 하나만 다루며, 두 개 이상의
    맥락을 조합한 통계는 만들지 않는다.

    수치 집계 규칙은 build_action_residual_summary()/build_theme_residual_summary()와
    동일하다 — judgment 통계는 모든 행동 그룹에서 정상값만 계산하고, entry_effect는
    actual_action='매수' 그룹만, non_buy 통계는 '보류'/'제외' 그룹만 계산하며
    '미기록' 그룹에서는 둘 다 집계하지 않는다. None/NaN/Infinity/bool은 유효 숫자에서
    제외하고, 평균·중앙값은 유효 표본이 0이면 None이다. 반환값은 반올림하지 않는다.
    양수 비율을 승률이라 부르지 않으며, 성공/실패·좋은/나쁜 조건 라벨이나 순위·추천·
    점수는 만들지 않는다.

    actual_action이 None이거나 빈(공백 포함) 문자열이면 '미기록'으로 정규화한다.
    '매수'/'보류'/'제외'/None·빈 문자열 외의 값은 ValueError. horizon_sessions는
    bool이 아닌 양의 정수여야 하며, 아니면 ValueError. 이 검증들은 결과를 만들기
    전에 전체 입력을 먼저 훑어 확인하므로, 잘못된 행 하나 때문에 일부만 반영된
    왜곡된 통계가 반환되지 않는다.

    정렬: context_value 오름차순('미지정'은 항상 마지막) -> horizon_sessions
    오름차순 -> 매수 -> 보류 -> 제외 -> 미기록.
    """
    if group_by not in _CONTEXT_RESIDUAL_ALLOWED_GROUP_BY:
        raise ValueError(
            f"group_by must be one of {_CONTEXT_RESIDUAL_ALLOWED_GROUP_BY}, got {group_by!r}"
        )
    if not isinstance(residual_rows, (list, tuple)):
        raise ValueError(
            f"residual_rows must be a list or tuple, got {type(residual_rows)!r}"
        )

    prepared = []
    for idx, row in enumerate(residual_rows):
        if not isinstance(row, dict):
            raise ValueError(f"residual_rows[{idx}] must be a dict, got {type(row)!r}")

        raw_action = row.get("actual_action")
        if raw_action is None or (isinstance(raw_action, str) and raw_action.strip() == ""):
            action = "미기록"
        elif raw_action in _ACTION_RESIDUAL_KNOWN_ACTIONS:
            action = raw_action
        else:
            raise ValueError(
                f"residual_rows[{idx}] has unknown actual_action: {raw_action!r}"
            )

        horizon_sessions = row.get("horizon_sessions")
        if (
            isinstance(horizon_sessions, bool)
            or not isinstance(horizon_sessions, int)
            or horizon_sessions <= 0
        ):
            raise ValueError(
                f"residual_rows[{idx}] horizon_sessions must be a positive int (not bool), "
                f"got {horizon_sessions!r}"
            )

        try:
            context_value = _normalize_context_value(row.get(group_by))
        except ValueError as exc:
            raise ValueError(f"residual_rows[{idx}] {group_by} error: {exc}")

        prepared.append((context_value, horizon_sessions, action, row))

    groups = {}
    for context_value, horizon_sessions, action, row in prepared:
        groups.setdefault((context_value, horizon_sessions, action), []).append(row)

    summary_rows = []
    for (context_value, horizon_sessions, action), rows in groups.items():
        sample_count = len(rows)

        judgment_return_values = _collect_valid_finite_values(rows, "judgment_return_pct")
        judgment_return_count, judgment_return_avg, judgment_return_median = (
            _summarize_values(judgment_return_values)
        )
        judgment_positive_count = sum(1 for v in judgment_return_values if v > 0)
        judgment_positive_rate = (
            judgment_positive_count / judgment_return_count * 100
            if judgment_return_count > 0
            else None
        )

        judgment_excess_values = _collect_valid_finite_values(
            rows, "judgment_excess_return_pct"
        )
        judgment_excess_count, judgment_excess_avg, _judgment_excess_median = (
            _summarize_values(judgment_excess_values)
        )

        entry_effect_values = (
            _collect_valid_finite_values(rows, "entry_effect_pct") if action == "매수" else []
        )
        entry_effect_count, entry_effect_avg, entry_effect_median = _summarize_values(
            entry_effect_values
        )

        if action in ("보류", "제외"):
            non_buy_return_values = _collect_valid_finite_values(rows, "non_buy_return_pct")
            non_buy_excess_values = _collect_valid_finite_values(
                rows, "non_buy_excess_return_pct"
            )
        else:
            non_buy_return_values = []
            non_buy_excess_values = []

        non_buy_return_count, non_buy_return_avg, non_buy_return_median = _summarize_values(
            non_buy_return_values
        )
        non_buy_positive_count = sum(1 for v in non_buy_return_values if v > 0)
        non_buy_positive_rate = (
            non_buy_positive_count / non_buy_return_count * 100
            if non_buy_return_count > 0
            else None
        )
        non_buy_excess_count, non_buy_excess_avg, _non_buy_excess_median = _summarize_values(
            non_buy_excess_values
        )

        summary_rows.append(
            {
                "group_by": group_by,
                "context_value": context_value,
                "horizon_sessions": horizon_sessions,
                "actual_action": action,
                "sample_count": sample_count,
                "judgment_return_count": judgment_return_count,
                "judgment_return_avg": judgment_return_avg,
                "judgment_return_median": judgment_return_median,
                "judgment_positive_count": judgment_positive_count,
                "judgment_positive_rate": judgment_positive_rate,
                "judgment_excess_count": judgment_excess_count,
                "judgment_excess_avg": judgment_excess_avg,
                "entry_effect_count": entry_effect_count,
                "entry_effect_avg": entry_effect_avg,
                "entry_effect_median": entry_effect_median,
                "non_buy_return_count": non_buy_return_count,
                "non_buy_return_avg": non_buy_return_avg,
                "non_buy_return_median": non_buy_return_median,
                "non_buy_positive_count": non_buy_positive_count,
                "non_buy_positive_rate": non_buy_positive_rate,
                "non_buy_excess_count": non_buy_excess_count,
                "non_buy_excess_avg": non_buy_excess_avg,
            }
        )

    def _context_residual_sort_key(s):
        cv = s["context_value"]
        cv_rank = (1, "") if cv == _CONTEXT_RESIDUAL_UNSPECIFIED else (0, cv)
        return (cv_rank, s["horizon_sessions"], _ACTION_RESIDUAL_ORDER[s["actual_action"]])

    summary_rows.sort(key=_context_residual_sort_key)
    return summary_rows
