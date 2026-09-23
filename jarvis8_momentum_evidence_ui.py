"""Read-only, source-checked display of the independent Jarvis 8 momentum study.

The archived study is deliberately separate from the older J8 volatility-divided
momentum list. This module never downloads prices or recalculates past returns.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
STUDY = ROOT / "output/independent_research/high_screen_20260922/result.json"
RISK = ROOT / "output/independent_research/risk_check_20260923/result.json"
SELECTIONS = ROOT / "output/independent_research/high_screen_20260922/selections.json"
STUDY_SCRIPT = ROOT / "research/independent_high_screen_20260922.py"
RISK_SCRIPT = ROOT / "research/independent_risk_check_20260923.py"
DIAGNOSTICS = ROOT / "data/jarvis8/opportunity_diagnostics_20260923.json"
DIAGNOSTIC_SOURCES = {
    "script_sha256": ROOT / "research/jarvis8_opportunity_diagnostics_20260923.py",
    "study_sha256": STUDY,
    "cycles_sha256": ROOT / "output/independent_research/high_screen_20260922/cycles.csv",
    "close_sha256": ROOT / "output/jarvis3_audit_20260909/fresh_close.parquet",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _checked_file(path: Path, expected: str, missing: list[str], changed: list[str]) -> None:
    """A missing source permits an archive view; a changed source blocks numbers."""
    if not isinstance(expected, str) or len(expected) != 64:
        changed.append(f"{path.name}: 저장 해시가 잘못됨")
    elif not path.is_file():
        missing.append(path.name)
    elif _sha256(path) != expected:
        changed.append(path.name)


def load_evidence(root: Path = ROOT) -> dict[str, Any]:
    """Return valid, archive, or stale. Cross-linked result hashes are mandatory."""
    study_path = root / STUDY.relative_to(ROOT)
    risk_path = root / RISK.relative_to(ROOT)
    selection_path = root / SELECTIONS.relative_to(ROOT)
    if not study_path.is_file() or not risk_path.is_file():
        return {"state": "missing", "reason": "저장된 연구 결과 파일이 없습니다."}
    try:
        study = json.loads(study_path.read_text(encoding="utf-8"))
        risk = json.loads(risk_path.read_text(encoding="utf-8"))
        main_meta = study["metadata"]
        risk_meta = risk["metadata"]
        inputs = main_meta["input_hashes"]
        if not isinstance(inputs, dict) or not inputs:
            raise ValueError("원자료 해시 목록 누락")
        if risk_meta["original_result_sha256"] != _sha256(study_path):
            raise ValueError("위험 검사와 기본 연구 결과의 연결 해시 불일치")
        # This check also catches malformed or truncated summary files early.
        if not isinstance(study["summary"], list) or not isinstance(risk["summary"], list):
            raise ValueError("저장된 성과표 형식 오류")
        missing: list[str] = []
        changed: list[str] = []
        _checked_file(root / STUDY_SCRIPT.relative_to(ROOT), main_meta["script_sha256"], missing, changed)
        _checked_file(root / RISK_SCRIPT.relative_to(ROOT), risk_meta["script_sha256"], missing, changed)
        _checked_file(selection_path, risk_meta["selections_sha256"], missing, changed)
        for name, digest in inputs.items():
            if not isinstance(name, str):
                raise ValueError("원자료 경로 형식 오류")
            path = (root / name).resolve()
            try:
                path.relative_to(root.resolve())
            except ValueError as exc:
                raise ValueError("원자료 경로가 프로젝트 밖을 가리킴") from exc
            _checked_file(path, digest, missing, changed)
        if changed:
            return {"state": "stale", "reason": "현재 파일과 저장된 연구가 다릅니다: " + ", ".join(changed)}
        return {"state": "archive" if missing else "verified", "study": study,
                "risk": risk, "missing_sources": sorted(set(missing))}
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return {"state": "stale", "reason": f"연구 자료의 연결 관계를 확인할 수 없습니다: {exc}"}


def load_diagnostics(root: Path = ROOT) -> dict[str, Any]:
    """Check the J8-only follow-up against every source still present here."""
    path = root / DIAGNOSTICS.relative_to(ROOT)
    if not path.is_file():
        return {"state": "missing", "reason": "미국주식 기회 진단 결과가 없습니다."}
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        if result["version"] != "J8-OPPORTUNITY-DIAGNOSTICS-20260923.1":
            raise ValueError("진단 규칙 버전이 다릅니다")
        if result["method"]["active_count"] != 102 or len(result["volatility_quartiles"]) != 4:
            raise ValueError("진단 표본 형식이 다릅니다")
        missing: list[str] = []
        changed: list[str] = []
        for key, original in DIAGNOSTIC_SOURCES.items():
            _checked_file(root / original.relative_to(ROOT), result["inputs"][key], missing, changed)
        if changed:
            return {"state": "stale", "reason": "진단 자료가 저장 당시와 다릅니다: " + ", ".join(changed)}
        return {"state": "archive" if missing else "verified", "result": result,
                "missing_sources": sorted(set(missing))}
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return {"state": "stale", "reason": f"진단 자료를 확인할 수 없습니다: {exc}"}


def render_diagnostics(st: Any) -> None:
    with st.expander("미국주식 자체 검사 · 수익 집중과 시장 변동성", expanded=False):
        checked = load_diagnostics()
        if checked["state"] in ("missing", "stale"):
            st.warning(checked["reason"])
            return
        if checked["state"] == "archive":
            st.warning("저장된 연구 결과입니다. 이 서버에는 원가격 일부가 없어 현장에서 전부 다시 계산할 수 없습니다.")
        else:
            st.caption("저장된 연구 코드·구간 수익률·QQQ 가격의 해시가 현재 파일과 일치합니다.")
        result = checked["result"]
        concentration = result["concentration"]
        momentum = concentration["momentum"]
        same_qqq = concentration["qqq_on_momentum_best_dates"]
        st.write("**수익이 소수의 구간에 몰렸는가?** 20거래일·왕복비용 0.5%로 후보가 있었던 102회 가운데 "
                 "결과가 가장 좋았던 20회를 사후에 골라 제거했습니다.")
        st.metric("모멘텀 · 나머지 82회 수익 단순합",
                  f"{momentum['remaining_simple_sum_pct_points']:+.2f}%p")
        st.metric("바로 그 82회 · 같은 금액 QQQ 단순합",
                  f"{same_qqq['remaining_simple_sum_pct_points']:+.2f}%p")
        st.caption("각 구간의 가상 계좌 수익률을 단순히 더한 값입니다. 연복리나 실제 계좌 손실률이 아닙니다. "
                   "어느 20회가 좋을지는 그 기간이 끝나야 알 수 있으므로 매수·거래 회피 조건으로 쓸 수 없습니다.")
        st.write("**변동성이 큰 날에 더 나았는가?** 신호일 종가까지의 QQQ 최근 20거래일 변동성으로 102회를 "
                 "네 그룹으로 나누어, 같은 돈을 QQQ에 넣었을 때보다 얼마나 나았는지 계산했습니다.")
        for row in result["volatility_quartiles"]:
            with st.container(border=True):
                st.markdown(f"**사전 변동성 {row['quartile']}구간 · {row['signals']}회**")
                st.caption(f"연율 변동성 {row['min_prior_vol_pct']:.1f}~{row['max_prior_vol_pct']:.1f}%")
                st.write(f"QQQ 대비 평균 {row['mean_excess_pct_points']:+.2f}%p / 관측")
        st.warning("결과가 변동성 순서대로 좋아지지 않았습니다. 비트코인 거래자의 고변동성 사례를 "
                   "미국주식 자비스8의 새 가산점·매수 허가 규칙으로 넣을 근거는 없습니다. "
                   "현재 생존 종목 명부와 이미 본 과거를 쓴 탐색 결과입니다.")


def _row(rows: list[dict[str, Any]], **terms: Any) -> dict[str, Any] | None:
    matches = [r for r in rows if all(r.get(key) == value for key, value in terms.items())]
    if len(matches) != 1:
        return None
    row = matches[0]
    for key in ("cagr_pct", "mdd_pct", "basket_win_pct"):
        value = row.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return None
    return row


def _card(st: Any, title: str, row: dict[str, Any], explanation: str) -> None:
    # One vertical card per method stays legible on narrow phones.
    with st.container(border=True):
        st.markdown(f"**{title}**")
        st.caption(explanation)
        st.metric("가상 계좌 연복리", f"{row['cagr_pct']:+.2f}%")
        st.metric("종가 기준 최대 하락", f"{row['mdd_pct']:.2f}%")
        st.caption(f"후보가 있던 때의 종목 묶음 수익 비율 {row['basket_win_pct']:.1f}% · 미래 승률이 아닙니다.")


def render(st: Any) -> None:
    """Show historical evidence; no pricing/network work or app state mutation."""
    st.subheader("모멘텀 스윙 · 과거 연구 결과")
    st.write("이전부터 강했던 종목 가운데 현재 추세가 유지된 종목을 고른 실험입니다. "
             "최근 21거래일 상승분을 순위 계산에서 빼고, "
             "252거래일 전과 21거래일 전의 가격으로 상승률을 구했습니다.")
    st.caption("자비스3 배점과 독립된 전략입니다. 기존 자비스8의 ‘변동성으로 나눈 모멘텀’ 목록과도 순위 계산이 다릅니다.")

    evidence = load_evidence()
    if evidence["state"] == "missing":
        st.info(evidence["reason"])
        return
    if evidence["state"] == "stale":
        st.error("저장된 연구 수치를 현재 검증 결과로 표시할 수 없습니다. " + evidence["reason"])
        return
    if evidence["state"] == "archive":
        st.warning("연구 당시 저장된 결과 · 이 서버에서 원가격 재검증 불가. "
                   "없는 자료: " + ", ".join(evidence["missing_sources"]))
    else:
        st.success("저장된 연구 코드·원가격·종목 명부·결과 파일의 해시가 현재 파일과 일치합니다. "
                   "이는 계산 자료 확인이며 미래 수익 검증은 아닙니다.")

    study, risk = evidence["study"], evidence["risk"]
    hold = st.selectbox("보유기간 (거래일)", [1, 3, 5, 10, 20], index=4, key="j8_independent_momentum_hold")
    cost = st.selectbox("왕복 거래비용 가정 (%)", [0.2, 0.5, 1.0], index=1,
                        key="j8_independent_momentum_cost")
    momentum = _row(study["summary"], offset=0, method="momentum", hold=hold, cost=cost)
    qqq = _row(study["summary"], offset=0, method="qqq", hold=hold, cost=cost)
    high = _row(study["summary"], offset=0, method="high", hold=hold, cost=cost)
    if not all((momentum, qqq, high)):
        st.error("선택한 보유기간·비용의 원본 성과 행이 없거나 중복됩니다. 결과를 표시하지 않습니다.")
        return
    if (momentum.get("signals"), momentum.get("active")) != (qqq.get("signals"), qqq.get("active")):
        st.error("모멘텀과 QQQ 비교의 관측 횟수가 다릅니다. 결과를 표시하지 않습니다.")
        return
    meta = study["metadata"]
    st.caption(f"{meta['first_signal']}~{meta['primary_last_signal']} · "
               f"21거래일 간격 {momentum['signals']}회 중 후보 {momentum['active']}회 · "
               "다음 거래일 시가에 가상 매수")
    st.write("**해석:** 같은 날, 같은 투자금으로 QQQ를 샀을 때와 비교합니다. "
             "종목당 10%, 최대 5종목이므로 계좌의 최대 50%만 투자하고 나머지는 현금입니다.")
    _card(st, "이전 기간 상승률 상위 5종목", momentum, "조정 종가 C[t−21] ÷ C[t−252] − 1 순위")
    _card(st, "같은 금액의 QQQ", qqq, "후보 수에 따라 주식 전략과 같은 비중만 투자")
    st.caption("연복리는 선택 기간의 가상 계좌 복리입니다. 최대 하락은 매일 종가 기준입니다. "
               "수익 비율은 개별 종목 승률이 아니라 후보 묶음이 이익을 낸 관측 비율입니다.")
    render_diagnostics(st)

    if hold == 20:
        lower = _row(risk["summary"], offset=0, method="momentum", weight=0.05, cost=cost)
        lower_qqq = _row(risk["summary"], offset=0, method="qqq", weight=0.05, cost=cost)
        if lower and lower_qqq and lower.get("active") == lower_qqq.get("active"):
            with st.expander("투자금을 절반으로 줄인 후속 실험 · 20거래일", expanded=False):
                st.write("종목당 5%, 최대 25% 투자로 다시 계산했습니다. 첫 결과를 본 뒤 시험한 것이어서 독립 검증이나 최적 비중은 아닙니다.")
                _card(st, "모멘텀 · 최대 25%", lower, "종목당 5%, 남는 금액은 현금")
                _card(st, "같은 금액의 QQQ · 최대 25%", lower_qqq, "같은 날, 같은 금액, 같은 비용")
        else:
            st.warning("비중 축소 후속 검사 행을 확인할 수 없어 수치를 생략합니다.")

    with st.expander("고점 근접법과 비교 · 선정 규칙 보기"):
        st.write("같은 후보군에서 ‘1년 최고 종가에 얼마나 가까운가’도 시험했습니다. "
                 "그 결과는 선택한 보유기간·비용 조건에서 다음과 같습니다.")
        _card(st, "고점 근접법", high, "이번 모멘텀 순위와 다른 독립 실험")
        if hold == 20 and cost == 0.5:
            st.write("대표 조건(20일·왕복 0.5%)에서는 고점 근접법이 같은 투자금의 QQQ보다 낮아 채택을 보류했습니다.")
        st.write("후보 조건: QQQ와 종목이 각자의 200일 평균 위, 과거 상승률 양수, "
                 "최근 20일 조정가격×거래량 평균 2천만 이상, 정상 일봉 확인. "
                 "하나라도 통과하지 못하면 후보가 없습니다.")

    with st.expander("이 숫자로 아직 알 수 없는 것"):
        st.write("현재 살아남은 종목 명부와 이미 살펴본 약 10년의 자료로 만든 탐색 결과입니다. "
                 "상장폐지 종목을 포함한 당시 전체 시장 검증과 새 기간의 검증은 아직 없습니다.")
        st.write("과거 검사는 21거래일 간격으로 매수했습니다. 화면에서 매일 후보를 보여주더라도 "
                 "매일 매수했을 때의 성적은 아닙니다. 손절·익절·장중 최대 손실도 시험하지 않았습니다.")
        st.write("가격은 한 공급자의 조정 일봉이며, 거래 규모는 조정 종가×거래량의 대용치입니다. "
                 "호가 차이와 주문 규모에 따른 비용은 실제 거래처럼 확인하지 못했습니다.")
        st.write("이 결과만으로 앞으로의 수익, 승률, 또는 자비스3 대비 우위를 주장할 수 없습니다.")
