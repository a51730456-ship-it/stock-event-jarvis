"""자비스4 — 한국 테마 레이더와 실제 매수 기록 페이지.

화면 골격은 자비스3(미국 테마 레이더)를 그대로 따르고, 내용만 한국형으로 바꾼다.
색 규칙은 한국장 기준이다 — 상승은 붉은색, 하락은 푸른색(자비스3와 반대).
"""

from __future__ import annotations

import time
from datetime import date

import streamlit as st

st.set_page_config(page_title="자비스4 — 한국 테마 레이더", layout="wide")

st.markdown(
    """
    <style>
    [data-testid="stSidebarNav"] a { padding: 0.7rem 1rem !important; }
    [data-testid="stSidebarNav"] a,
    [data-testid="stSidebarNav"] a * {
        font-size: 1.4rem !important;
        font-weight: 800 !important;
        color: #ffb020 !important;
        line-height: 1.4 !important;
    }
    [data-testid="stSidebarNav"] li:first-child a p { font-size: 0 !important; }
    [data-testid="stSidebarNav"] li:first-child a p::before {
        content: "자비스1";
        font-size: 1.4rem;
        font-weight: 800;
        color: #ffb020;
    }
    /* 사이드바 순서: 시장판단 → 자비스1 → 자비스2 → 미국테마 → 한국테마 */
    [data-testid="stSidebarNav"] ul { display: flex; flex-direction: column; }
    [data-testid="stSidebarNav"] li:nth-child(1) { order: 2; }
    [data-testid="stSidebarNav"] li:nth-child(2) { order: 1; }
    [data-testid="stSidebarNav"] li:nth-child(3) { order: 3; }
    [data-testid="stSidebarNav"] li:nth-child(4) { order: 4; }
    [data-testid="stSidebarNav"] li:nth-child(5) { order: 5; }
    [data-testid="stSidebarNav"] li:nth-child(4) a p { font-size: 0 !important; }
    [data-testid="stSidebarNav"] li:nth-child(4) a p::before {
        content: "미국테마";
        font-size: 1.4rem; font-weight: 800; color: #ffb020;
    }
    [data-testid="stSidebarNav"] li:nth-child(5) a p { font-size: 0 !important; }
    [data-testid="stSidebarNav"] li:nth-child(5) a p::before {
        content: "한국테마";
        font-size: 1.4rem; font-weight: 800; color: #ffb020;
    }
    .j4-score-guide, .j4-market-flow {
        color: #44f0a1; font-size: 1rem; font-weight: 800; line-height: 1.65;
    }
    .j4-score-guide { margin-top: 0.35rem; }
    .j4-market-flow {
        margin: 1.9rem 0 0.8rem 0; padding: 0.75rem 1rem;
        border-left: 4px solid #44f0a1; background: rgba(34, 197, 94, 0.08); border-radius: 0.4rem;
    }
    .j4-action-box {
        color: #4da6ff; font-size: 1rem; font-weight: 800; line-height: 1.65;
        margin-top: 1.9rem; margin-bottom: 0.8rem; padding: 0.8rem 1rem;
        border: 1px solid rgba(77, 166, 255, 0.45); background: rgba(37, 99, 235, 0.13);
        border-radius: 0.55rem;
    }
    h1 { font-size: 2.05rem !important; }
    .j4-stock-name { color: #c084fc; font-size: 1.7rem; font-weight: 800; line-height: 1.2; margin-top: 0.3rem; }
    .j4-stock-sub { color: #9aa0aa; font-size: 0.95rem; margin: 0.1rem 0 0.7rem; }
    .j4-metric-row { display: flex; flex-wrap: wrap; gap: 1.6rem; margin: 0.2rem 0 0.4rem; }
    .j4-mc { min-width: 120px; }
    .j4-mc-label { color: #4da6ff; font-size: 0.92rem; font-weight: 800; }
    .j4-mc-val { font-size: 1.5rem; font-weight: 800; color: #e6e6e6; line-height: 1.25; }
    .j4-mc-sub { font-size: 0.95rem; font-weight: 800; }
    /* 한국장 색: 상승 빨강 · 하락 파랑 */
    .j4-up { color: #ff5b5b; }
    .j4-down { color: #4da6ff; }
    .j4-muted { color: #9aa0aa; }
    .j4-section-title { color: #4da6ff; font-size: 1.2rem; font-weight: 800; margin: 1rem 0 0.5rem; }
    .j4-factor-table { width: 100%; border-collapse: collapse; margin-bottom: 0.5rem; font-size: 0.95rem; }
    .j4-factor-table th { text-align: center; color: #4da6ff; font-weight: 800; padding: 0.45rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.18); }
    .j4-factor-table td { color: #44f0a1; font-weight: 700; padding: 0.4rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.06); }
    .j4-factor-table td.j4-fac-name { text-align: left; }
    .j4-factor-table td.j4-fac-val { text-align: center; }
    .j4-reason-card { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.09); border-radius: 0.55rem; padding: 0.6rem 0.75rem; height: 100%; }
    .j4-reason-title { color: #4da6ff; font-weight: 800; font-size: 0.95rem; margin-bottom: 0.25rem; }
    .j4-reason-body { color: #44f0a1; font-weight: 700; font-size: 0.9rem; line-height: 1.45; }
    .j4-chart-title { color: #e6e6e6; font-weight: 800; font-size: 1rem; margin-bottom: 0.1rem; }
    .j4-leader-name { font-size: 1.2rem; font-weight: 800; color: #e6e6e6; line-height: 1.25; }
    .j4-leader-name .j4-medal { font-size: 1.6rem; vertical-align: -2px; }
    .j4-leader-live { font-size: 1.2rem; font-weight: 800; color: #e6e6e6; margin-top: 0.35rem; }
    .j4-leader-score-label { color: #4da6ff; font-size: 0.85rem; font-weight: 800; margin-top: 0.35rem; }
    .j4-leader-score { color: #ff5b5b; font-size: 1.9rem; font-weight: 800; line-height: 1.1; }
    .j4-leader-state { color: #9aa0aa; font-size: 0.9rem; }
    .j4-green { color: #44f0a1; }
    .j4-green-strong { color: #22c55e; font-weight: 800; }
    .j4-theme-box { background: rgba(77,166,255,0.08); border: 1px solid rgba(77,166,255,0.3); border-radius: 0.55rem; padding: 0.7rem 0.9rem; font-size: 0.95rem; line-height: 1.7; margin-bottom: 0.6rem; }
    .j4-reason-mustard { background: rgba(234,179,8,0.12); border: 1px solid rgba(234,179,8,0.42); color: #e6c34a; border-radius: 0.5rem; padding: 0.6rem 0.8rem; font-weight: 700; }
    .j4-chart-heading { margin-top: 1.6rem; font-size: 1.15rem; font-weight: 800; color: #e6e6e6; }
    .j4-theme-badge { display: inline-block; background: rgba(255,176,32,0.16); color: #ffb020; border: 1px solid #ffb020; border-radius: 0.5rem; padding: 0.15rem 0.7rem; font-weight: 800; font-size: 1.05rem; margin-right: 0.4rem; }
    .j4-flow-label { color: #44f0a1; font-weight: 800; }
    .j4-flow-body { color: #4da6ff; font-weight: 800; }
    .j4-action-label { color: #4da6ff; font-weight: 800; }
    .j4-action-posture { color: #ff5b5b; font-weight: 800; }
    .j4-action-detail { color: #ff9d3b; font-weight: 800; }
    .j4-top-row { display: flex; gap: 2rem; flex-wrap: wrap; margin-bottom: 0.3rem; }
    .j4-top-cell { min-width: 150px; }
    /* 제목은 코발트, 값은 항목별 색 — 무엇이 제목이고 무엇이 결과인지 구분되게 한다
       (2026-07-22 사용자 지시). */
    .j4-top-label { color: #4da6ff; font-size: 0.92rem; font-weight: 800; }
    .j4-top-val { font-size: 1.7rem; font-weight: 800; line-height: 1.2; }
    .j4-top-sub { font-size: 0.95rem; font-weight: 700; }
    .j4-theme-table { width: 100%; border-collapse: collapse; font-size: 0.92rem; table-layout: fixed; }
    .j4-theme-table th { text-align: center; color: #9aa0aa; font-weight: 800; padding: 0.5rem 0.4rem; border-bottom: 1px solid rgba(255,255,255,0.18); }
    .j4-theme-table td { text-align: center; padding: 0.45rem 0.4rem; border-bottom: 1px solid rgba(255,255,255,0.06); color: #e6e6e6; overflow: hidden; text-overflow: ellipsis; }
    .j4-theme-table td.j4-th-name { text-align: left; padding-left: 1.2rem; font-weight: 800; }
    .j4-th-selected { background: rgba(255,176,32,0.13); }
    .j4-th-muted { color: #9aa0aa; }
    .j4-barwrap { display: flex; align-items: center; gap: 6px; width: 100%; }
    .j4-bar { position: relative; flex: 1; background: rgba(255,255,255,0.10); border-radius: 4px; height: 8px; overflow: hidden; }
    .j4-bar-fill { height: 8px; background: #ff5b5b; }
    .j4-bar-green { background: #44f0a1; }
    .j4-bar-num { font-size: 0.82rem; font-weight: 700; color: #e6e6e6; min-width: 32px; text-align: right; }
    .j4-th-head { text-align: center; color: #9aa0aa; font-weight: 800; font-size: 0.92rem;
        padding: 0.45rem 0 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.22); }
    .j4-td { text-align: center; color: #e6e6e6; font-size: 0.92rem; padding: 0;
        border-bottom: 1px solid rgba(255,255,255,0.06); min-height: 2.5rem;
        display: flex; align-items: center; justify-content: center; }
    div[class*="st-key-j4tbtn_"] button {
        background: transparent !important; border: none !important; box-shadow: none !important;
        padding: 0 !important; min-height: 2.5rem !important; width: 100% !important;
        border-bottom: 1px solid rgba(255,255,255,0.06) !important; border-radius: 0 !important;
    }
    div[class*="st-key-j4tbtn_"] button:hover { background: rgba(255,255,255,0.06) !important; }
    /* 테마명은 좌측 정렬(제목만 가운데) — 2026-07-22 사용자 지시 */
    div[class*="st-key-j4tbtn_"] button { justify-content: flex-start !important; padding-left: 0.9rem !important; }
    div[class*="st-key-j4tbtn_"] button p {
        font-weight: 800 !important; font-size: 0.95rem !important; margin: 0 !important; text-align: left !important;
    }
    div[class*="st-key-j4_stock_choice"] [data-testid="stWidgetLabel"] p {
        color: #7cc8ff !important; font-size: 1.55rem !important; font-weight: 800 !important;
    }
    .j4-holo-card {
        position: relative;
        background: linear-gradient(135deg, rgba(77,166,255,0.07), rgba(168,85,247,0.07));
        border: 1px solid rgba(77,166,255,0.55); border-radius: 10px; padding: 1.15rem 1.3rem;
        box-shadow: 0 0 14px rgba(77,166,255,0.28), inset 0 0 20px rgba(77,166,255,0.07);
    }
    .j4-holo-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1.1rem 1.8rem; }
    .j4-holo-cell { min-width: 0; }
    @media (max-width: 900px) { .j4-holo-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
    .j4-holo-score .label { color: #4da6ff !important; font-size: 0.92rem; font-weight: 800; }
    .j4-holo-score .val { color: #44f0a1 !important; font-size: 1.5rem; font-weight: 800; line-height: 1.25; }
    .j4-holo-score .state { color: #9aa0aa; font-size: 0.95rem; font-weight: 700; }
    .j4-plan-note { margin-top: 1.1rem; color: #9aa0aa; font-size: 1rem; line-height: 1.65; }
    .j4-plan-note b { color: #44f0a1; font-size: 1.1rem; font-weight: 800; }
    .j4-holo-cell .label { color: #9aa0aa; font-size: 0.85rem; }
    .j4-holo-cell .val { font-size: 1.5rem; font-weight: 800; color: #e6e6e6; line-height: 1.2; text-shadow: 0 0 8px rgba(77,166,255,0.45); }
    .j4-danta-box { border: 1px solid rgba(234,179,8,0.5); background: rgba(234,179,8,0.07);
        border-radius: 0.55rem; padding: 0.7rem 0.9rem; margin-top: 0.9rem; line-height: 1.7; }
    .j4-danta-title { color: #ff9d3b; font-weight: 800; }
    .j4-new-badge { background: rgba(255,176,32,0.16); color: #ffb020; border: 1px solid #ffb020;
        border-radius: 5px; padding: 0 6px; font-size: 0.78rem; font-weight: 800; margin-left: 6px; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _login_gate() -> None:
    if st.session_state.get("authenticated"):
        return
    st.markdown("## 자비스4 — 한국 테마 레이더")
    st.caption("승인된 사용자만 접근할 수 있습니다. 여기서 바로 로그인할 수 있습니다.")
    try:
        password = st.secrets.get("APP_PASSWORD")
    except Exception:
        password = None
    if not password:
        st.warning(".streamlit/secrets.toml에 APP_PASSWORD 설정이 필요합니다.")
        st.stop()
    entered = st.text_input("비밀번호", type="password", key="j4_login_password")
    if st.button("자비스4 로그인", key="j4_login_submit", width="stretch"):
        if entered == password:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    st.stop()


_login_gate()

import importlib

import altair as alt
import pandas as pd

import jarvis4_data as j4data
import jarvis4_store as j4store
import market_signal_ui

# 온라인 배포 갱신 때 옛 모듈이 프로세스에 남으면 스스로 새 코드를 읽는다(자비스3와 동일).
# 새 함수를 추가할 때마다 이 목록에 넣어야 한다 — 빠뜨리면 온라인에서 AttributeError가 난다
# (2026-07-22: get_us_futures_live를 빠뜨려 실제로 발생했다).
_REQUIRED_J4_FUNCTIONS = (
    "get_theme_rankings", "get_theme_leaders", "get_market_overview",
    "get_us_futures_live", "get_intraday_chart", "get_pass_candidates",
    "get_chart_bundle", "get_live_quote", "round_to_tick",
)
if any(not hasattr(j4data, name) for name in _REQUIRED_J4_FUNCTIONS):
    j4data = importlib.reload(j4data)
if not hasattr(market_signal_ui, "_STATUS_TEXT"):
    import sys

    for _dep_name in (
        "market_signal_common", "kr_intraday_flow",
        "us_market_signal_engine", "naver_market_data",
    ):
        _dep = sys.modules.get(_dep_name)
        if _dep is not None:
            importlib.reload(_dep)
    market_signal_ui = importlib.reload(market_signal_ui)


def _pct(value) -> str:
    return "—" if value is None else f"{float(value):+.2f}%"


def _won(value) -> str:
    return "—" if value is None else f"{float(value):,.0f}원"


def _eok(value) -> str:
    """금액을 억 단위로."""
    return "—" if value is None else f"{float(value) / 1e8:+,.0f}억"


def _number(value, digits=1) -> str:
    return "—" if value is None else f"{float(value):,.{digits}f}"


def _sign_class(value) -> str:
    """한국장 색: 상승(+)은 붉은색, 하락(−)은 푸른색."""
    if value is None:
        return "j4-muted"
    try:
        return "j4-up" if float(value) >= 0 else "j4-down"
    except (TypeError, ValueError):
        return "j4-muted"


def _sign_color(value) -> str:
    if value is None:
        return "#9aa0aa"
    try:
        return "#ff5b5b" if float(value) >= 0 else "#4da6ff"
    except (TypeError, ValueError):
        return "#9aa0aa"


def _top_metric(label, value, value_color, sub, *, sub_color=None, sub_signed=False) -> str:
    if sub_signed:
        sub_html = f"<div class='j4-top-sub {_sign_class(sub)}'>{_pct(sub)}</div>"
    else:
        sub_html = f"<div class='j4-top-sub' style='color:{sub_color or '#9aa0aa'}'>{sub}</div>"
    return (
        f"<div class='j4-top-cell'><div class='j4-top-label'>{label}</div>"
        f"<div class='j4-top-val' style='color:{value_color}'>{value}</div>{sub_html}</div>"
    )


def _safe_error_text(error) -> str:
    return str(error or "일시적인 온라인 조회 오류")[:220]


_STATUS_HEX = {"주도": "#44f0a1", "관찰": "#ff9d3b", "약함": "#9aa0aa"}
_THEME_COL_WIDTHS = [0.7, 2.4, 0.85, 2.0, 0.9, 1.0, 1.3, 1.6]


def _trend_position(row: dict, label: str) -> str:
    current, sma20, sma50 = row.get("current"), row.get("sma20"), row.get("sma50")
    if current is None or sma20 is None or sma50 is None:
        return f"{label} 추세 자료가 부족합니다"
    above20, above50 = current > sma20, current > sma50
    if above20 and above50:
        return f"{label}는 20·50일선 위로 단기·중기 추세가 모두 살아 있습니다"
    if above50:
        return f"{label}는 50일선 위지만 20일선 아래여서 중기 추세 속 단기 조정입니다"
    if above20:
        return f"{label}는 20일선은 회복했지만 50일선 아래라 추세 전환 확인이 필요합니다"
    return f"{label}는 20·50일선 아래로 단기·중기 흐름이 모두 약합니다"


def _market_flow_text(overview: dict) -> str:
    rows = overview.get("rows", {})
    sections = [
        _trend_position(rows.get("KOSPI", {}), "KOSPI"),
        _trend_position(rows.get("KOSDAQ", {}), "KOSDAQ"),
    ]
    foreign = overview.get("foreign") or {}
    if foreign.get("ok"):
        amount = foreign["net5_amount"]
        if amount > 0:
            sections.append(f"대표종목(삼성전자·SK하이닉스) 5일 수급이 {amount / 1e8:+,.0f}억으로 순매수 우위입니다")
        else:
            sections.append(f"대표종목 5일 수급이 {amount / 1e8:+,.0f}억으로 순매도 우위라 수급 부담이 있습니다")
    usdkrw = rows.get("USDKRW", {})
    if usdkrw.get("ok") and usdkrw.get("sma20"):
        if usdkrw["current"] <= usdkrw["sma20"]:
            sections.append(f"원/달러 {usdkrw['current']:,.1f}원은 20일선 아래로 원화 강세가 외국인 자금에 우호적입니다")
        else:
            sections.append(f"원/달러 {usdkrw['current']:,.1f}원은 20일선 위로 환율 부담이 남아 있습니다")
    us_prev = overview.get("us_prev") or {}
    if us_prev.get("ok"):
        sections.append(
            f"미국 전일은 SPY {us_prev['spy_change']:+.2f}% · 나스닥100 {us_prev['qqq_change']:+.2f}%로 "
            f"{'우호적' if (us_prev['spy_change'] or 0) >= 0 else '부담'}입니다"
        )
    return ".<br>".join(sections) + "."


_REGIME_HEX = {"방어 우선": "#ff5b5b", "중립·선별": "#ff9d3b", "상승 우위": "#44f0a1"}


def _us_futures_cell() -> str:
    """나스닥100 선물 실시간 — 한국 장중에 미국이 지금 어디로 가는지 본다.

    온라인 배포 직후 옛 모듈이 남아 함수가 없을 수 있어 getattr로 방어한다
    (2026-07-22 실제 AttributeError 발생 — 위 reload와 이중 안전장치).
    """
    fetcher = getattr(j4data, "get_us_futures_live", None)
    if fetcher is None:
        return _top_metric("나스닥100 선물", "—", "#9aa0aa", "모듈 갱신 대기")
    futures = fetcher()
    if not futures.get("ok"):
        return _top_metric("나스닥100 선물", "—", "#9aa0aa", "자료 부족")
    values = futures.get("values") or {}
    nasdaq = values.get("NQ=F") or {}
    sp500 = values.get("ES=F") or {}
    if not nasdaq.get("current"):
        return _top_metric("나스닥100 선물", "—", "#9aa0aa", "자료 부족")
    change = nasdaq.get("change_pct")
    sub = f"{_pct(change)}"
    if sp500.get("change_pct") is not None:
        sub += f" · S&P500 선물 {sp500['change_pct']:+.2f}%"
    return _top_metric(
        "나스닥100 선물",
        f"{nasdaq['current']:,.0f}",
        _sign_color(change),
        sub,
        sub_color=_sign_color(change),
    )


def _market_score_detail(overview: dict) -> str:
    """획득/미충족 항목을 색으로 구분한다 — 항목명은 흰색, 점수는 초록, 미충족은 회색."""
    breakdown = overview.get("score_breakdown") or []
    if not breakdown:
        return "세부 점수는 다음 갱신에서 표시됩니다."
    earned = [
        f"<span style='color:#e6e6e6'>{item['label']}</span> "
        f"<span style='color:#44f0a1'>{item['earned']}/{item['max']}점</span>"
        for item in breakdown if item.get("earned")
    ]
    missed = [
        f"<span style='color:#9aa0aa'>{item['label']}</span>"
        for item in breakdown if not item.get("earned")
    ]
    return (
        "<span style='color:#4da6ff'>현재 획득</span> : "
        + (" · ".join(earned) if earned else "<span style='color:#9aa0aa'>충족 신호 없음</span>")
        + "<br><span style='color:#4da6ff'>미충족</span> : "
        + (" · ".join(missed) if missed else "<span style='color:#9aa0aa'>없음</span>")
    )


def _regime_guide_html(overview: dict) -> str:
    """구간 안내를 위 '시장 국면'과 같은 색으로 칠해 지금 어디인지 바로 보이게 한다."""
    current = overview.get("regime")
    parts = []
    for label, span in (("방어 우선", "0~49점"), ("중립·선별", "50~74점"), ("상승 우위", "75~100점")):
        color = _REGIME_HEX.get(label, "#e6e6e6")
        mark = "◀ 지금" if label == current else ""
        weight = "800" if label == current else "600"
        parts.append(
            f"<span style='color:#9aa0aa'>{span}</span> "
            f"<span style='color:{color}; font-weight:{weight}'>{label}{mark}</span>"
        )
    return " · ".join(parts)


def _market_action_detail(overview: dict) -> str:
    score = float(overview.get("score") or 0)
    if score >= 75:
        return (
            "시장 추세와 수급이 충분히 확인된 구간입니다.<br>"
            "그래도 아무 종목이나 매수하지 않고, 주도 테마이면서 종목점수 70점 이상인 "
            "대장주가 기준가격을 통과할 때만 분할 진입합니다."
        )
    if score >= 50:
        return (
            "시장 일부만 강한 선별 구간입니다.<br>"
            "매수 비중을 평소보다 줄이고, 주도 테마의 1~3위 종목 중 "
            "돌파 또는 20일선 눌림 조건이 확인된 종목만 심사합니다."
        )
    return (
        "상승장 확인 조건이 부족하므로 신규 매수를 보류합니다.<br>"
        "보유 종목의 손절 기준과 비중을 먼저 관리하고,<br>"
        "KOSPI·KOSDAQ의 20·50일선 회복과 시장점수 50점 이상을 확인한 뒤 다시 매수 심사를 시작합니다."
    )


@st.fragment(run_every=60)
def _render_market_overview() -> None:
    """시장판단은 페이지 최상단에서 1분마다 독립 갱신한다."""
    overview = j4data.get_market_overview()
    st.session_state["j4_market_overview"] = overview
    st.subheader("한국 전체시장 판단")
    if not overview.get("ok"):
        st.error(f"시장 자료 조회 실패: {_safe_error_text(overview.get('error'))}")
        st.caption("네트워크가 복구되면 1분 자동 갱신에서 다시 시도합니다.")
        return

    phase = overview.get("phase", {}).get("label", "—")
    regime_color = {"방어 우선": "#ff5b5b", "중립·선별": "#ff9d3b", "상승 우위": "#44f0a1"}.get(
        overview["regime"], "#e6e6e6"
    )
    phase_color = "#44f0a1" if phase == "정규장" else "#ff9d3b" if "동시호가" in phase or "시간외" in phase else "#ff5b5b"
    rows = overview["rows"]
    kospi, kosdaq, usdkrw = rows.get("KOSPI", {}), rows.get("KOSDAQ", {}), rows.get("USDKRW", {})
    foreign = overview.get("foreign") or {}
    us_prev = overview.get("us_prev") or {}

    top_cells = [
        _top_metric("시장 국면", overview["regime"], regime_color, f"조건 {overview['score']}/100"),
        _top_metric("KOSPI", _number(kospi.get("current"), 2), "#e6e6e6", kospi.get("change_pct"), sub_signed=True),
        _top_metric("KOSDAQ", _number(kosdaq.get("current"), 2), "#e6e6e6", kosdaq.get("change_pct"), sub_signed=True),
        _top_metric(
            "시장상태", phase, phase_color,
            f"원/달러 {_number(usdkrw.get('current'), 1)}" if usdkrw.get("ok") else "원/달러 —",
        ),
        _top_metric(
            "대표종목 5일 수급",
            _eok(foreign.get("net5_amount")) if foreign.get("ok") else "—",
            _sign_color(foreign.get("net5_amount")) if foreign.get("ok") else "#9aa0aa",
            "삼성전자+SK하이닉스" if foreign.get("ok") else "자료 부족",
        ),
        _top_metric(
            "미국 전일",
            us_prev.get("regime") or "—",
            "#e6e6e6",
            (
                f"S&P500 {us_prev['spy_change']:+.2f}% · 나스닥100 {us_prev['qqq_change']:+.2f}%"
                + (f" · 공포탐욕 {us_prev['fear_greed']:.0f}" if us_prev.get("fear_greed") else "")
            ) if us_prev.get("ok") else "자료 부족",
        ),
        _us_futures_cell(),
    ]
    st.markdown(f"<div class='j4-top-row'>{''.join(top_cells)}</div>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="j4-score-guide">
            <span style="color:#4da6ff">조건점수</span>
            <span style="color:{regime_color}">{overview['score']}/100</span>
            <span style="color:#9aa0aa; font-weight:600">은 상승장 확인 조건에서 얻은 점수이며 승률이 아닙니다.</span><br>
            {_regime_guide_html(overview)}<br>
            {_market_score_detail(overview)}<br>
            <span style="color:#4da6ff">시장상태</span>
            <span style="color:#9aa0aa; font-weight:600">는 한국 세션 단계입니다 :</span>
            <span style="color:#e6e6e6">장전 동시호가 08:30~09:00 → 정규장 09:00~15:30 → 시간외 → 장 마감</span>
        </div>
        <div class="j4-market-flow">
            <span class="j4-flow-label">시장 전체 흐름</span> : <span class="j4-flow-body">{_market_flow_text(overview)}</span>
        </div>
        <div class="j4-action-box">
            <span class="j4-action-label">행동 기준</span> : <span class="j4-action-posture">{overview['posture']}</span><br>
            <span class="j4-action-detail">{_market_action_detail(overview)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        f"최근 가용 시세: {overview.get('checked_at') or '시각 확인 불가'} · 1분 자동 갱신 · "
        "네이버·FinanceDataReader 조회이므로 지연될 수 있음"
    )


def _render_theme_table(ranking: dict, selected: str | None) -> str | None:
    """테마표를 그리고, 테마 이름 버튼이 눌리면 그 테마명을 돌려준다(자비스3와 같은 방식)."""
    titles = ["순위", "테마", "종목수", "조건점수", "상태", "당일", "KOSPI 대비", "구성종목 확산"]
    for column, title in zip(st.columns(_THEME_COL_WIDTHS), titles):
        column.markdown(f"<div class='j4-th-head'>{title}</div>", unsafe_allow_html=True)

    button_css = []
    clicked = None
    for index, row in enumerate(ranking.get("rows", [])):
        name = row.get("name", "")
        color = _STATUS_HEX.get(row.get("status", ""), "#e6e6e6")
        button_key = f"j4tbtn_{index:02d}"
        button_css.append(f"div[class*='st-key-{button_key}'] button p {{ color: {color} !important; }}")
        if name == selected:
            button_css.append(
                f"div[class*='st-key-{button_key}'] button {{ background: rgba(255,176,32,0.16) !important; }}"
            )
        cols = st.columns(_THEME_COL_WIDTHS)
        cols[0].markdown(f"<div class='j4-td'>{row.get('rank', '')}</div>", unsafe_allow_html=True)
        label = name
        if row.get("is_forced"):
            label = f"{name} 🔎"   # 사용자가 직접 추가한 테마
        elif row.get("is_new"):
            label = f"{name} 🆕"
        if cols[1].button(label, key=button_key, width="stretch"):
            clicked = name
        cols[2].markdown(f"<div class='j4-td'>{row.get('stock_count', '')}</div>", unsafe_allow_html=True)
        score = float(row.get("score") or 0)
        cols[3].markdown(
            "<div class='j4-td'><div class='j4-barwrap'><div class='j4-bar'>"
            f"<div class='j4-bar-fill' style='width:{min(score, 100):.0f}%'></div></div>"
            f"<span class='j4-bar-num'>{score:.1f}</span></div></div>",
            unsafe_allow_html=True,
        )
        cols[4].markdown(
            f"<div class='j4-td' style='color:{color}; font-weight:800'>{row.get('status', '')}</div>",
            unsafe_allow_html=True,
        )
        change = row.get("change_pct")
        cols[5].markdown(
            f"<div class='j4-td' style='color:{_sign_color(change)}; font-weight:700'>{_pct(change)}</div>",
            unsafe_allow_html=True,
        )
        relative = row.get("relative")
        relative_text = "—" if relative is None else f"{float(relative):+.2f}%p"
        cols[6].markdown(
            f"<div class='j4-td' style='color:{_sign_color(relative)}; font-weight:700'>{relative_text}</div>",
            unsafe_allow_html=True,
        )
        up_ratio = row.get("up_ratio")
        breadth_cell = "—" if up_ratio is None else (
            "<div class='j4-barwrap'><div class='j4-bar'>"
            f"<div class='j4-bar-fill j4-bar-green' style='width:{min(float(up_ratio), 100):.0f}%'></div></div>"
            f"<span class='j4-bar-num'>{float(up_ratio):.0f}%</span></div>"
        )
        cols[7].markdown(f"<div class='j4-td'>{breadth_cell}</div>", unsafe_allow_html=True)

    st.markdown("<style>" + "".join(button_css) + "</style>", unsafe_allow_html=True)
    return clicked


def _leader_table_html(leaders: list[dict], selected_code: str | None) -> str:
    rank_mark = {1: "🟡 1위", 2: "⚪ 2위", 3: "🟠 3위"}
    body = []
    for leader in leaders[:6]:
        metrics, plan, flow = leader["metrics"], leader["plan"], leader["flow"]
        rank = int(leader["rank"])
        highlight = " j4-th-selected" if leader["code"] == selected_code else ""
        score = float(leader["score"])
        score_bar = (
            "<div class='j4-barwrap'><div class='j4-bar'>"
            f"<div class='j4-bar-fill' style='width:{min(score, 100):.0f}%'></div></div>"
            f"<span class='j4-bar-num'>{score:.1f}</span></div>"
        )
        change, from_high, ret20 = metrics.get("change_pct"), metrics.get("from_high_pct"), metrics.get("ret20")
        net5 = flow.get("net5_amount") if flow.get("ok") else None
        body.append(
            f"<tr class='j4-th-row{highlight}'>"
            f"<td>{rank_mark.get(rank, f'{rank}위')}</td>"
            f"<td class='j4-th-name'>{leader['name']}</td>"
            f"<td>{leader['code']}</td>"
            f"<td>{score_bar}</td>"
            f"<td style='color:{_sign_color(change)}; font-weight:700'>{_pct(change)}</td>"
            f"<td style='color:{_sign_color(from_high)}; font-weight:700'>{_pct(from_high)}</td>"
            f"<td style='color:{_sign_color(ret20)}; font-weight:700'>{_pct(ret20)}</td>"
            f"<td style='color:{_sign_color(net5)}; font-weight:700'>{_eok(net5)}</td>"
            f"<td>{plan.get('state', '')}</td></tr>"
        )
    return (
        "<table class='j4-theme-table'><colgroup>"
        "<col style='width:9%'><col style='width:19%'><col style='width:8%'>"
        "<col style='width:16%'><col style='width:9%'><col style='width:11%'>"
        "<col style='width:10%'><col style='width:10%'><col style='width:8%'></colgroup>"
        "<thead><tr><th>순위</th><th style='text-align:left; padding-left:1.2rem'>종목</th><th>코드</th>"
        "<th>조건점수</th><th>당일</th><th>52주 고가 대비</th><th>20일 수익률</th>"
        "<th>수급(외+기 5일)</th><th>매수 상태</th></tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table>"
    )


def _price_chart(payload: dict, include_volume: bool = False, height: int | None = None):
    price = payload["price"].reset_index()
    date_column = price.columns[0]
    price = price.rename(columns={date_column: "날짜", "Close": "주가", "MA20": "20일선", "MA50": "50일선"})
    available = [column for column in ("주가", "20일선", "50일선") if column in price.columns]
    long_price = price.melt(id_vars=["날짜"], value_vars=available, var_name="구분", value_name="가격").dropna()
    line_height = height if height is not None else (220 if include_volume else 315)
    line = (
        alt.Chart(long_price)
        .mark_line(strokeWidth=2)
        .encode(
            x=alt.X("날짜:T", title=None, axis=alt.Axis(format="%y-%m", labelAngle=0, tickCount=5)),
            y=alt.Y("가격:Q", title=None, scale=alt.Scale(zero=False), axis=alt.Axis(tickCount=5)),
            color=alt.Color(
                "구분:N", title=None,
                scale=alt.Scale(domain=["주가", "20일선", "50일선"], range=["#69bff8", "#ff4d4f", "#a855f7"]),
                legend=alt.Legend(orient="top", direction="horizontal"),
            ),
            tooltip=[alt.Tooltip("날짜:T", title="날짜"), alt.Tooltip("구분:N"), alt.Tooltip("가격:Q", format=",.0f")],
        )
        .properties(height=line_height)
    )
    volume = payload.get("volume")
    if not include_volume or volume is None or volume.empty:
        return line
    volume_frame = volume.reset_index()
    volume_frame = volume_frame.rename(columns={volume_frame.columns[0]: "날짜", "Volume": "거래량"})
    bars = (
        alt.Chart(volume_frame)
        .mark_bar(color="#3b82f6", opacity=0.65)
        .encode(
            x=alt.X("날짜:T", title=None, axis=alt.Axis(format="%y-%m", labelAngle=0, tickCount=5)),
            y=alt.Y("거래량:Q", title="거래량", axis=alt.Axis(format="~s", tickCount=3)),
            tooltip=[alt.Tooltip("날짜:T", title="날짜"), alt.Tooltip("거래량:Q", format=",.0f")],
        )
        .properties(height=80)
    )
    return alt.vconcat(line, bars, spacing=4).resolve_scale(x="shared")


_MEDAL_BY_RANK = {1: "🥇", 2: "🥈", 3: "🥉"}
_STATE_COLOR_WORD = {"돌파 확인": "green", "눌림목 대기": "orange", "관찰": "gray", "추격 금지": "red", "제외": "gray"}


def _stock_radio_label(item: dict) -> str:
    rank = int(item["rank"])
    medal = _MEDAL_BY_RANK.get(rank, "")
    state = item["plan"].get("state", "")
    color_word = _STATE_COLOR_WORD.get(state, "gray")
    return (
        f"{medal} :green[**{rank}위 · {item['name']} ({item['code']})**] · "
        f":red[**{item['score']:.1f}점**] · :{color_word}[**{state}**]"
    )


def _intraday_chart(payload: dict, height: int = 210):
    """당일 분봉 차트 — 전일 종가를 점선 기준선으로 그린다(한국장 색: 상승 빨강)."""
    frame = payload["price"].reset_index()
    frame.columns = ["시각", "가격"]
    prev_close = payload.get("prev_close")
    last_price = float(frame["가격"].iloc[-1])
    if prev_close:
        line_color = "#ff5b5b" if last_price >= float(prev_close) else "#4da6ff"
    else:
        line_color = "#69bff8"
    line = (
        alt.Chart(frame)
        .mark_line(strokeWidth=2, color=line_color)
        .encode(
            x=alt.X("시각:T", title=None, axis=alt.Axis(format="%H:%M", labelAngle=0, tickCount=5)),
            y=alt.Y("가격:Q", title=None, scale=alt.Scale(zero=False), axis=alt.Axis(tickCount=5)),
            tooltip=[alt.Tooltip("시각:T", title="시각", format="%H:%M"),
                     alt.Tooltip("가격:Q", format=",.0f")],
        )
        .properties(height=height)
    )
    if prev_close:
        baseline = (
            alt.Chart(pd.DataFrame({"전일 종가": [float(prev_close)]}))
            .mark_rule(strokeDash=[4, 4], color="#9aa0aa")
            .encode(y="전일 종가:Q")
        )
        return line + baseline
    return line


def _render_leader_comparison(leaders: list[dict]) -> None:
    st.markdown("<div class='j4-section-title'>대장주 1~3위 · 당일/일봉/주봉 비교</div>", unsafe_allow_html=True)
    for leader in leaders[:3]:
        metrics, plan, flow = leader["metrics"], leader["plan"], leader["flow"]
        rank = int(leader["rank"])
        medal = _MEDAL_BY_RANK.get(rank, "") if float(leader["score"]) >= 80 else ""
        medal_html = f"<span class='j4-medal'>{medal}</span> " if medal else ""
        with st.container(border=True):
            left, intraday_col, daily_col, weekly_col = st.columns([1.0, 1.15, 1.15, 1.15])
            with left:
                st.markdown(
                    f"<div class='j4-leader-name'>{medal_html}{rank}위 · {leader['name']}</div>",
                    unsafe_allow_html=True,
                )
                st.code(leader["code"])
                st.markdown(
                    "<div class='j4-leader-score-label'>현재가 · 등락률</div>"
                    f"<div class='j4-leader-live'>{_won(metrics.get('current'))} "
                    f"<span class='j4-mc-sub {_sign_class(metrics.get('change_pct'))}'>{_pct(metrics.get('change_pct'))}</span></div>"
                    "<div class='j4-leader-score-label'>종목 조건점수</div>"
                    f"<div class='j4-leader-score'>{float(leader['score']):.1f}</div>"
                    f"<div class='j4-leader-state'>{plan.get('state')}</div>",
                    unsafe_allow_html=True,
                )
                if flow.get("ok"):
                    st.caption(f"외국인+기관 5일 {_eok(flow.get('net5_amount'))} · 연속 {flow.get('buy_streak_days', 0)}일")
                st.caption(f"52주 고가 대비 {_pct(metrics.get('from_high_pct'))}")
            bundle = j4data.get_chart_bundle(leader["code"])
            charts = bundle.get("charts", {}) if bundle.get("ok") else {}
            with intraday_col:
                st.caption("당일 · 실시간(지연 가능)")
                intraday = j4data.get_intraday_chart(leader["code"])
                if intraday and intraday.get("ok"):
                    st.altair_chart(_intraday_chart(intraday), width="stretch", theme="streamlit")
                    st.caption(f"기준 {intraday.get('source_time') or '시각 확인 불가'}")
                else:
                    st.info("당일 자료 없음")
            with daily_col:
                st.caption("일봉 · 최근 120거래일")
                if charts.get("일봉", {}).get("ok"):
                    st.altair_chart(_price_chart(charts["일봉"], height=210), width="stretch", theme="streamlit")
                else:
                    st.info("일봉 자료 없음")
            with weekly_col:
                st.caption("주봉 · 최근 60주")
                if charts.get("주봉", {}).get("ok"):
                    st.altair_chart(_price_chart(charts["주봉"], height=210), width="stretch", theme="streamlit")
                else:
                    st.info("주봉 자료 없음")


def _kr_flow_hint() -> str:
    """기관 수급 반전 카드 판정을 단타 참고 문구로 옮긴다(점수에는 반영하지 않는다)."""
    result = st.session_state.get("kr_flow_result")
    if result is None:
        return "기관 수급 반전 판정은 위 ‘한국장 기관 수급 현황’ 카드에서 확인하세요."
    return f"기관 수급 반전: <b>{result.verdict_label}</b> · {result.headline}"


def _render_stock_detail(theme_row: dict, leader: dict, market: dict, top_candidates: list[dict], stock_key: str) -> None:
    code = leader["code"]
    st.session_state["j4_selected_code"] = code
    metrics, plan, flow = leader["metrics"], leader["plan"], leader["flow"]

    st.divider()
    detail_rank = int(leader.get("rank") or 0)
    detail_medal = _MEDAL_BY_RANK.get(detail_rank, "") if float(leader.get("score") or 0) >= 80 else ""
    detail_medal_html = f"<span class='j4-medal'>{detail_medal}</span> " if detail_medal else ""
    st.markdown(
        f"<div class='j4-stock-name'>{detail_medal_html}{leader['name']} · {code}</div>"
        f"<div class='j4-stock-sub'>{theme_row['name']} 대장주 {leader['rank']}위 · {plan.get('recommendation')}</div>",
        unsafe_allow_html=True,
    )

    cells = [
        f"<div class='j4-mc'><div class='j4-mc-label'>현재가</div>"
        f"<div class='j4-mc-val'>{_won(metrics.get('current'))}</div>"
        f"<div class='j4-mc-sub {_sign_class(metrics.get('change_pct'))}'>{_pct(metrics.get('change_pct'))}</div></div>",
        f"<div class='j4-mc'><div class='j4-mc-label'>52주 신고가 대비</div>"
        f"<div class='j4-mc-val {_sign_class(metrics.get('from_high_pct'))}'>{_pct(metrics.get('from_high_pct'))}</div></div>",
        f"<div class='j4-mc'><div class='j4-mc-label'>20일 수익률</div>"
        f"<div class='j4-mc-val {_sign_class(metrics.get('ret20'))}'>{_pct(metrics.get('ret20'))}</div></div>",
        f"<div class='j4-mc'><div class='j4-mc-label'>14일 변동성(ATR)</div>"
        f"<div class='j4-mc-val j4-up'>{_pct(metrics.get('atr_pct'))}</div></div>",
        f"<div class='j4-mc'><div class='j4-mc-label'>외국인+기관 5일</div>"
        f"<div class='j4-mc-val {_sign_class(flow.get('net5_amount') if flow.get('ok') else None)}'>"
        f"{_eok(flow.get('net5_amount')) if flow.get('ok') else '—'}</div>"
        f"<div class='j4-mc-sub j4-muted'>연속 {flow.get('buy_streak_days', 0)}일</div></div>",
        f"<div class='j4-mc'><div class='j4-mc-label'>종목 조건점수</div>"
        f"<div class='j4-mc-val j4-green'>{float(leader.get('score') or 0):.1f}/100</div>"
        f"<div class='j4-mc-sub j4-muted'>{plan.get('state', '')}</div></div>",
    ]
    st.markdown(f"<div class='j4-metric-row'>{''.join(cells)}</div>", unsafe_allow_html=True)

    factor_names = ["테마 대비 상대강도", "52주 신고가 위치", "추세(20·50·200일선)", "유동성(거래대금)", "변동성 안정", "수급(외국인+기관)"]
    factor_max = [20, 20, 15, 15, 10, 20]

    def _gain_cell(part, maximum, *, top_border=False):
        border = " style='border-top:4px double rgba(255,255,255,0.55)'" if top_border else ""
        return (
            f"<td class='j4-fac-val'{border}>"
            f"<span style='color:#ff5b5b; font-weight:800'>{_number(part)}</span> "
            f"<span style='color:#ff5b5b'>({maximum})</span></td>"
        )

    factor_rows = "".join(
        f"<tr><td class='j4-fac-name'>{name}</td>{_gain_cell(part, maximum)}</tr>"
        for name, part, maximum in zip(factor_names, leader["score_parts"], factor_max)
    )
    total_style = (
        "font-weight:800; font-size:1.1rem; background:rgba(134,255,203,0.12); "
        "border-top:4px double rgba(255,255,255,0.55)"
    )
    total_row = (
        f"<tr><td class='j4-fac-name' style='{total_style}'>총점</td>"
        f"<td class='j4-fac-val' style='{total_style}'>"
        f"<span style='color:#ff5b5b; font-weight:800'>{_number(leader.get('score'))}</span> "
        "<span style='color:#ff5b5b'>(100)</span></td></tr>"
    )

    score_col, plan_col = st.columns([1, 1], gap="large")
    with score_col:
        st.markdown("<div class='j4-section-title'>종목 선정 근거 (한국형 6개 항목)</div>", unsafe_allow_html=True)
        st.markdown(
            "<table class='j4-factor-table'><thead><tr>"
            "<th>심사 항목</th><th>획득(최대)</th></tr></thead>"
            f"<tbody>{factor_rows}{total_row}</tbody></table>",
            unsafe_allow_html=True,
        )
        st.markdown(f"<div class='j4-reason-mustard'>{leader['stock_reason']}</div>", unsafe_allow_html=True)
    with plan_col:
        st.markdown("<div class='j4-section-title'>매수 심사 결과 (원화 · 호가단위 반올림)</div>", unsafe_allow_html=True)
        plan_cells = [
            ("조건 기준가", _won(plan.get("trigger")), "#e6e6e6"),
            ("매수 허용 상단", _won(plan.get("zone_high")), "#e6e6e6"),
            ("무효화 가격", _won(plan.get("invalidation")), "#4da6ff"),
            ("2R 목표 참고", _won(plan.get("target")), "#ff5b5b"),
        ]
        plan_boxes = [
            f"<div class='j4-holo-cell'><div class='label'>{label}</div>"
            f"<div class='val' style='color:{color}'>{value}</div></div>"
            for label, value, color in plan_cells
        ]
        score_box = (
            "<div class='j4-holo-cell j4-holo-score'>"
            "<div class='label'>종목 조건점수</div>"
            f"<div class='val'>{float(leader.get('score') or 0):.1f}/100</div>"
            f"<div class='state'>{plan.get('state', '')}</div></div>"
        )
        plan_grid = (
            plan_boxes[0] + plan_boxes[1] + score_box
            + plan_boxes[2] + plan_boxes[3] + "<div class='j4-holo-cell'></div>"
        )
        st.markdown(
            f"<div class='j4-holo-card'><div class='j4-holo-grid'>{plan_grid}</div></div>",
            unsafe_allow_html=True,
        )
        if plan.get("trigger") is None:
            hints = []
            high52, sma20 = metrics.get("high52"), metrics.get("sma20")
            if high52:
                hints.append(f"돌파 조건 도달가 <b>{_won(j4data.round_to_tick(float(high52) * 0.97))}</b> (52주 고가 −3%)")
            if sma20:
                hints.append(f"눌림목 조건 도달가 <b>{_won(j4data.round_to_tick(sma20))}</b> (20일선)")
            hint_text = f"참고 — {' · '.join(hints)}. " if hints else ""
            st.markdown(
                f"<div class='j4-plan-note'>※ 지금은 ‘{plan.get('state')}’ 상태라 확정 기준가·목표가가 "
                f"아직 없습니다. {hint_text}이 조건이 실제로 충족되면 위 칸에 매수 가격이 표시됩니다.</div>",
                unsafe_allow_html=True,
            )
        # 가격이 있는 종목과 없는 종목이 왜 갈리는지 한 줄로 설명한다
        # (2026-07-22 사용자 질문: 삼성전자는 비었는데 기아·현대모비스는 왜 다 있나).
        st.markdown(
            f"<div class='j4-plan-note'>※ <b>가격 칸이 채워지는 기준</b> — "
            f"‘돌파 확인’이나 ‘눌림목 대기’처럼 <b>가격 셋업이 완성된 종목만</b> 기준가·손절가·목표가가 나옵니다. "
            f"‘제외’·‘관찰’·‘추격 금지’는 아직 살 자리가 없다는 뜻이라 비워 둡니다.<br>"
            f"※ <b>‘{plan.get('state')}’(가격 상태)와 ‘{plan.get('recommendation')}’(최종 판정)은 다른 말</b>입니다 — "
            f"가격 셋업이 완성돼도 시장·테마 점수가 기준 미달이면 최종 판정은 매수가 아닙니다.</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div class='j4-danta-box'><span class='j4-danta-title'>⚡ 단타 참고 신호</span> — {_kr_flow_hint()}<br>"
            "<span class='j4-muted'>수급 반전이 🟢로 바뀌고 기준가를 넘으면 장중 진입 신호로 참고합니다 "
            "(점수·판정에는 반영하지 않습니다).</span></div>",
            unsafe_allow_html=True,
        )
        st.write("")
        if plan.get("recommendation") == "조건부 후보":
            st.success(plan.get("buy_reason"))
        elif plan.get("state") == "추격 금지":
            st.error(plan.get("buy_reason"))
        else:
            st.warning(plan.get("buy_reason"))

    st.markdown("<div class='j4-chart-heading'>가격 차트 · 일봉/주봉/월봉 한눈에 보기</div>", unsafe_allow_html=True)
    st.caption("주가 흐름은 하늘색 · 20일선은 붉은색 · 50일선은 보라색입니다. 일봉 거래량은 일봉 바로 아래에 표시됩니다.")
    chart_bundle = j4data.get_chart_bundle(code)
    if chart_bundle.get("ok"):
        daily_col, weekly_col, monthly_col = st.columns(3)
        for timeframe, chart_column in (("일봉", daily_col), ("주봉", weekly_col), ("월봉", monthly_col)):
            payload = chart_bundle["charts"].get(timeframe, {})
            with chart_column:
                st.markdown(f"<div class='j4-chart-title'>{timeframe}</div>", unsafe_allow_html=True)
                if payload.get("ok"):
                    st.altair_chart(
                        _price_chart(payload, include_volume=timeframe == "일봉"),
                        width="stretch", theme="streamlit",
                    )
                else:
                    st.warning(f"{timeframe} 자료 없음")
    else:
        st.warning(f"차트 조회 실패: {_safe_error_text(chart_bundle.get('error'))}")

    st.markdown("<div class='j4-section-title'>추천 근거 요약</div>", unsafe_allow_html=True)
    reason_cards = [
        ("시장 근거", f"{market.get('regime', '자료부족')} · {market.get('score', 0)}/100"),
        ("테마 근거", theme_row.get("basis", "자료부족")),
        ("종목 근거", leader["stock_reason"]),
        ("매수 근거", plan.get("buy_reason", "자료부족")),
    ]
    for column, (title, body) in zip(st.columns(4), reason_cards):
        column.markdown(
            f"<div class='j4-reason-card'><div class='j4-reason-title'>{title}</div>"
            f"<div class='j4-reason-body'>{body}</div></div>",
            unsafe_allow_html=True,
        )

    _render_buy_form(theme_row, leader, market, top_candidates, stock_key)


# ---------------------------------------------------------------------------
# 매수 기록
# ---------------------------------------------------------------------------
def _records_live_prices(records: list[dict]) -> dict:
    fingerprint = tuple(sorted((int(r["id"]), str(r.get("status"))) for r in records))
    cache = st.session_state.get("j4_records_pl_cache") or {}
    if cache.get("fp") == fingerprint and time.time() - cache.get("at", 0) < 300:
        return cache["prices"]
    open_codes = sorted({
        str(record.get("code")) for record in records
        if record.get("status") == "보유" and record.get("code")
    })[:30]
    prices = {}
    for code in open_codes:
        quote = j4data.get_live_quote(code)
        if quote.get("ok") and quote.get("current"):
            prices[code] = float(quote["current"])
    st.session_state["j4_records_pl_cache"] = {"fp": fingerprint, "at": time.time(), "prices": prices}
    return prices


def _render_records_editor(records: list[dict], key_prefix: str = "tab") -> None:
    """매수 기록 현황 표 하나에서 바로 청산을 입력한다(자비스3와 같은 방식)."""
    saved_message = st.session_state.pop("j4_close_saved_msg", None)
    if saved_message:
        st.success(saved_message)
    st.caption(
        "보유 종목 줄에서 매도일 칸을 누르면 달력이 뜨고, 매도가(원) 칸에 금액을 넣으면 "
        "표 아래에 확정 손익률이 자동 계산됩니다. ‘청산 저장’을 눌러야 확정됩니다. "
        "매도가는 매수가 ±50% 범위만 저장됩니다."
    )

    prices = _records_live_prices(records)

    def _pl_text(value):
        # 입력형 표는 글자색 지정이 안 되므로 색깔 원으로 표시한다(한국장: 이익 🔴 / 손실 🔵).
        if value is None:
            return None
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None
        return f"{'🔴' if value >= 0 else '🔵'} {value:+.2f}%"

    editor_rows = []
    for record in records:
        is_open = record.get("status") == "보유"
        buy_price = float(record["buy_price"]) if record.get("buy_price") is not None else None
        current = prices.get(str(record.get("code"))) if is_open else None
        live_pl = (current / buy_price - 1) * 100 if current and buy_price else None
        editor_rows.append({
            "번호": int(record["id"]),
            "매수일": record.get("buy_date"),
            "코드": record.get("code"),
            "종목명": record.get("stock_name"),
            "테마": record.get("theme_name"),
            "매매유형": record.get("trade_style"),
            "매수가(원)": buy_price,
            "수량": record.get("quantity"),
            "상태": record.get("status"),
            "현재 손익률(%)": _pl_text(live_pl),
            "매도일": record.get("sell_date"),
            "매도가(원)": record.get("sell_price"),
            "확정 손익률(%)": _pl_text(record.get("result_pct")),
            "시장 국면": record.get("market_regime"),
            "시장점수": record.get("market_score"),
            "테마점수": record.get("theme_score"),
            "종목점수": record.get("stock_score"),
            "메모": record.get("memo"),
        })
    frame = pd.DataFrame(editor_rows)
    frame["매도일"] = pd.to_datetime(frame["매도일"])
    for column in ("매수가(원)", "매도가(원)", "수량", "시장점수", "테마점수", "종목점수"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    center = {"alignment": "center"}
    column_config = {
        "번호": st.column_config.NumberColumn(format="%d", **center),
        "매수일": st.column_config.TextColumn(**center),
        "코드": st.column_config.TextColumn(**center),
        "종목명": st.column_config.TextColumn(**center),
        "테마": st.column_config.TextColumn(**center),
        "매매유형": st.column_config.TextColumn(**center),
        "매수가(원)": st.column_config.NumberColumn(format="%,.0f", **center),
        "수량": st.column_config.NumberColumn(format="%.0f", **center),
        "상태": st.column_config.TextColumn(**center),
        "현재 손익률(%)": st.column_config.TextColumn(**center),
        "매도일": st.column_config.DateColumn("매도일", format="YYYY-MM-DD", help="보유 종목 칸을 누르면 달력이 뜹니다", **center),
        "매도가(원)": st.column_config.NumberColumn("매도가(원)", min_value=1.0, step=10.0, format="%,.0f", help="매수가 ±50% 범위에서 입력", **center),
        "확정 손익률(%)": st.column_config.TextColumn(**center),
        "시장 국면": st.column_config.TextColumn(**center),
        "시장점수": st.column_config.NumberColumn(format="%.0f", **center),
        "테마점수": st.column_config.NumberColumn(format="%.0f", **center),
        "종목점수": st.column_config.NumberColumn(format="%.0f", **center),
        "메모": st.column_config.TextColumn(**center),
    }
    editor_key = f"j4_records_editor_{key_prefix}"
    edited = st.data_editor(
        frame,
        column_config=column_config,
        disabled=[col for col in frame.columns if col not in ("매도일", "매도가(원)")],
        hide_index=True,
        width="stretch",
        key=editor_key,
    )

    previews = []
    for index, record in enumerate(records):
        if record.get("status") != "보유":
            continue
        row = edited.iloc[index]
        sell_price = row["매도가(원)"]
        if sell_price is None or pd.isna(sell_price) or not record.get("buy_price"):
            continue
        profit = (float(sell_price) / float(record["buy_price"]) - 1) * 100
        color = "#ff5b5b" if profit >= 0 else "#4da6ff"
        previews.append(
            f"<b>{record['stock_name']}</b> 매도가 {float(sell_price):,.0f}원 → 확정 손익률 "
            f"<span style='color:{color};font-weight:800'>{profit:+.2f}%</span>"
        )
    if previews:
        st.markdown(
            "<div class='j4-plan-note'>자동계산 미리보기 — " + " · ".join(previews)
            + " <span class='j4-muted'>(청산 저장을 누르면 확정 손익률 칸에 기록됩니다)</span></div>",
            unsafe_allow_html=True,
        )

    if st.button("청산 저장 (매도일·매도가 입력된 종목만)", key=f"j4_close_save_{key_prefix}", width="stretch"):
        saved_count = 0
        errors = []
        for index, record in enumerate(records):
            if record.get("status") != "보유":
                continue
            row = edited.iloc[index]
            sell_date, sell_price = row["매도일"], row["매도가(원)"]
            has_date = sell_date is not None and not pd.isna(sell_date)
            has_price = sell_price is not None and not pd.isna(sell_price)
            if not has_date and not has_price:
                continue
            label = f"#{record['id']} {record['stock_name']}"
            if not (has_date and has_price):
                errors.append(f"{label}: 매도일과 매도가를 모두 입력해야 저장됩니다")
                continue
            buy_price = float(record["buy_price"])
            if not buy_price * 0.5 <= float(sell_price) <= buy_price * 1.5:
                errors.append(
                    f"{label}: 매도가는 매수가 ±50% 범위"
                    f"({buy_price * 0.5:,.0f} ~ {buy_price * 1.5:,.0f}원)여야 합니다"
                )
                continue
            try:
                j4store.close_trade(
                    int(record["id"]),
                    sell_date=pd.Timestamp(sell_date).date(),
                    sell_price=float(sell_price),
                )
                saved_count += 1
            except Exception as exc:
                errors.append(f"{label}: {_safe_error_text(exc)}")
        for error in errors:
            st.error(error)
        if saved_count and not errors:
            st.session_state["j4_close_saved_msg"] = f"{saved_count}건 청산을 저장했습니다."
            st.session_state.pop(editor_key, None)
            st.session_state.pop("j4_records_pl_cache", None)
            st.rerun()
        elif saved_count:
            st.success(f"{saved_count}건 청산을 저장했습니다. 위 오류 항목은 저장되지 않았습니다.")


def _render_buy_form(theme_row: dict, leader: dict, market: dict, top_candidates: list[dict], stock_key: str) -> None:
    code = leader["code"]
    metrics, plan, flow = leader["metrics"], leader["plan"], leader["flow"]
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)

    # 상세 종목 선택(복제)은 '실제 매수 기록' 제목 위에 둔다(자비스3와 같은 배치).
    code_options = [item["code"] for item in top_candidates]
    by_code = {item["code"]: item for item in top_candidates}
    mirror_key = f"{stock_key}_form"

    def _apply_form_stock_change():
        st.session_state[stock_key] = st.session_state[mirror_key]

    if st.session_state.get(mirror_key) != code or st.session_state.get(mirror_key) not in code_options:
        st.session_state[mirror_key] = code
    st.radio(
        "상세 종목 선택",
        code_options,
        format_func=lambda value: _stock_radio_label(by_code[value]) if value in by_code else value,
        horizontal=True,
        key=mirror_key,
        on_change=_apply_form_stock_change,
    )

    title_col, status_col = st.columns([0.28, 1.72])
    with title_col:
        st.markdown("#### 실제 매수 기록")
    with status_col:
        try:
            progress = j4store.trade_progress()
            summary = (
                f"보유 {progress['open_count']}건 · 청산 {progress['closed_count']}/"
                f"{progress['minimum_sample']}건 · 전체 {progress['total_count']}건"
            )
        except Exception:
            summary = None
        expander_label = f"📋 매수 기록 현황 보기 — {summary}" if summary else "📋 매수 기록 현황 보기"
        with st.expander(expander_label, expanded=False):
            try:
                records = j4store.list_trades(limit=100)
            except Exception as exc:
                st.error(f"기록 조회 실패: {_safe_error_text(exc)}")
                records = []
            if records:
                _render_records_editor(records, key_prefix="form")
            else:
                st.caption("아직 저장된 매수 기록이 없습니다.")
    st.caption("실제로 매수한 경우에만 저장합니다. 저장 시 당시 시장·테마·종목·수급 조건도 함께 보존됩니다.")

    with st.container(border=True):
        form_rank = int(leader.get("rank") or 0)
        form_medal = _MEDAL_BY_RANK.get(form_rank, "") if float(leader.get("score") or 0) >= 80 else ""
        form_medal_html = f"<span class='j4-medal'>{form_medal}</span> " if form_medal else ""
        st.markdown(
            f"<div class='j4-stock-name'>{form_medal_html}{leader['name']} · {code}</div>"
            f"<div class='j4-stock-sub'>{theme_row['name']} 대장주 {leader['rank']}위 · {plan.get('recommendation')} · "
            f"현재가 {_won(metrics.get('current'))} "
            f"<span class='{_sign_class(metrics.get('change_pct'))}'>{_pct(metrics.get('change_pct'))}</span></div>",
            unsafe_allow_html=True,
        )
        with st.form(f"j4_buy_form_{code}", clear_on_submit=False, border=False):
            c1, c2, c3, c4 = st.columns(4)
            buy_date = c1.date_input("매수일", value=date.today(), key=f"j4_buy_date_{code}")
            default_price = float(metrics.get("current") or 1)
            # 원화는 소수점이 없지만 min_value·step과 자료형이 어긋나면 위젯이 예외를 낸다.
            buy_price = c2.number_input(
                "실제 매수가(원)", min_value=1.0, value=float(round(default_price)), step=10.0,
                key=f"j4_buy_price_{code}", format="%.0f",
            )
            quantity = c3.number_input("수량(선택)", min_value=0.0, value=0.0, step=1.0, key=f"j4_buy_qty_{code}")
            trade_style = c4.selectbox("매매유형", ["단타", "스윙", "중장기"], index=1, key=f"j4_trade_style_{code}")
            memo = st.text_area("매수 이유·메모", key=f"j4_buy_memo_{code}", height=80)
            confirmed = st.checkbox("실제 체결된 매수임을 확인합니다", key=f"j4_buy_confirm_{code}")
            submitted = st.form_submit_button("매수 기록 저장", width="stretch")

        if submitted:
            if not confirmed:
                st.error("실제 체결 확인을 체크해야 저장할 수 있습니다.")
                return
            snapshot = {
                "captured_at": market.get("checked_at"),
                "market": {"regime": market.get("regime"), "score": market.get("score")},
                "theme": {
                    "name": theme_row.get("name"), "no": theme_row.get("no"),
                    "score": theme_row.get("score"), "rank": theme_row.get("rank"),
                    "relative": theme_row.get("relative"), "up_ratio": theme_row.get("up_ratio"),
                },
                "stock": {
                    "code": code, "rank": leader.get("rank"), "score": leader.get("score"),
                    "current": metrics.get("current"), "from_high_pct": metrics.get("from_high_pct"),
                    "ret20": metrics.get("ret20"), "atr_pct": metrics.get("atr_pct"),
                    "flow_net5": flow.get("net5_amount") if flow.get("ok") else None,
                    "flow_streak": flow.get("buy_streak_days") if flow.get("ok") else None,
                },
            }
            try:
                j4store.save_trade(
                    code=code,
                    stock_name=leader["name"],
                    theme_name=theme_row["name"],
                    buy_date=buy_date,
                    buy_price=buy_price,
                    quantity=quantity or None,
                    trade_style=trade_style,
                    entry_setup=plan.get("state"),
                    recommendation_state=plan.get("recommendation"),
                    market_regime=market.get("regime"),
                    market_score=market.get("score"),
                    theme_score=theme_row.get("score"),
                    stock_score=leader.get("score"),
                    flow_score=leader["score_parts"][5] if len(leader.get("score_parts") or []) > 5 else None,
                    flow_net5_amount=flow.get("net5_amount") if flow.get("ok") else None,
                    entry_plan=plan,
                    snapshot=snapshot,
                    memo=memo,
                )
                st.success(f"{leader['name']} · {buy_date.isoformat()} · {buy_price:,.0f}원 매수 기록을 저장했습니다.")
            except Exception as exc:
                st.error(f"매수 기록 저장 실패: {_safe_error_text(exc)}")


# ---------------------------------------------------------------------------
# 탭
# ---------------------------------------------------------------------------
def _render_radar_tab(market: dict) -> None:
    action_col, note_col = st.columns([1, 4])
    with action_col:
        if st.button("온라인 자료 새로고침", key="j4_force_refresh", width="stretch"):
            j4data.clear_runtime_cache()
            st.rerun()
    with note_col:
        st.caption("테마 순위는 5분 캐시, 시장판단은 1분 자동 갱신됩니다.")

    # 사용자가 직접 고른 테마는 순위 밖이어도 반드시 심사해 목록에 넣는다
    # (2026-07-22: 금융·은행처럼 오늘 약한 테마도 눌림목을 보고 싶다는 요구).
    forced = st.session_state.get("j4_forced_themes") or []
    with st.spinner("네이버 전체 테마를 훑어 오늘 강한 테마를 고르는 중입니다…"):
        ranking = j4data.get_theme_rankings(force_names=tuple(forced))
    if not ranking.get("ok"):
        st.error(f"테마 자료 조회 실패: {_safe_error_text(ranking.get('error'))}")
        return
    st.session_state["j4_theme_rankings"] = ranking

    # 자비스3(미국)에 없고 자비스4에만 넣은 승률 보완 장치를 화면에서 바로 보이게 한다
    # (2026-07-22 사용자 질문: "승률 올리려고 뭘 찾았나? 표시는 했나?").
    with st.expander("📈 자비스4에만 있는 승률 보완 장치 7가지 (미국테마에 없는 것)", expanded=False):
        st.markdown(
            """
| # | 무엇 | 왜 승률에 도움이 되나 | 어디서 보이나 |
|---|---|---|---|
| 1 | **수급 20점** (외국인+기관) | 국내에서 가장 검증된 신호. 금액이 아니라 **5일 거래대금 대비 비율**로 재서 대형주 편향을 없앰 | 종목 점수표 6번째 항목 |
| 2 | **동적 테마 선정** | 네이버 266개 테마를 매일 전수 스캔 → 상위 20개만. 약한 테마 자동 탈락 = 낡은 테마에 물리지 않음 | 테마표 🆕 표시·탈락 안내 |
| 3 | **국내형 추격 금지** | 당일 +20%·5일 +25%·ATR 15% 이상 제외(상한가 30% 제도 반영) | 매수 상태 '추격 금지' |
| 4 | **미국 전일 게이트 15점** | 한국장은 미국 전일과 갭 상관이 높음 | 시장판단 상단 '미국 전일' |
| 5 | **호가단위 반올림** | 기준가·목표가가 실제 주문 가능한 가격으로 나옴 | 매수 심사 결과 4칸 |
| 6 | **자동 제외 필터** | 스팩·우선주·리츠는 점수와 무관하게 후보에서 뺌 | 대장주 목록에 아예 없음 |
| 7 | **기관 수급 반전 연동** | 장중 진입 타이밍 참고(점수에는 미반영) | 종목 상세 ⚡단타 참고 신호 |
| 8 | **약한 테마의 강한 종목 구제** | 국내 테마는 성격이 섞여 있어 테마 평균이 종목 품질을 대표하지 못함. **종목 85점 이상이면 테마 점수와 무관하게 후보** | 매수 심사 통과 종목 표 |

**한국 시장에 맞게 다시 잰 것** — 미국 배점을 그대로 쓰면 안 되는 게 실측으로 확인됐습니다.
국내 대형주 상당수가 52주 고가 대비 −30~−45% 구간이라 미국 기준(−25%~0)에서는 전 종목이
0점이 됐습니다. 그래서 **신고가 배점을 20→15로 줄이고 범위를 −45~0으로 넓히는 대신,
국내에서 더 잘 듣는 추세(이동평균선) 배점을 15→20으로 올렸습니다.**
            """
        )
    st.markdown("### 오늘의 강한 테마 20 · 실시간 순위")
    entered, dropped = ranking.get("entered") or [], ranking.get("dropped") or []
    change_text = ""
    if entered:
        change_text += f" · <span style='color:#ff5b5b'>신규 진입 {len(entered)}개({', '.join(entered[:3])})</span>"
    if dropped:
        change_text += f" · <span style='color:#4da6ff'>탈락 {len(dropped)}개({', '.join(dropped[:3])})</span>"
    st.markdown(
        f"<div class='j4-muted'>네이버 {ranking.get('total_scanned', 0)}개 테마 전체에서 매일 자동 선정합니다 — "
        f"강한 테마는 새로 들어오고 가장 약한 테마는 자동 탈락{change_text}</div>",
        unsafe_allow_html=True,
    )
    st.caption("표에서 테마 이름을 클릭하면 대장주·상세가 그 테마로 연결됩니다.")

    names = [row["name"] for row in ranking["rows"]]

    # 아래 '매수 심사 통과 종목' 표에서 고른 종목을 위젯 생성 전에 반영한다.
    pending = st.session_state.pop("j4_pending_pick", None)
    if pending:
        pending_theme, pending_code = pending
        if pending_theme in names:
            st.session_state["j4_theme_choice"] = pending_theme
            st.session_state["j4_theme_choice_widget"] = pending_theme
            st.session_state[f"j4_stock_choice_{pending_theme}"] = pending_code

    clicked_theme = _render_theme_table(ranking, st.session_state.get("j4_theme_choice"))
    if clicked_theme in names:
        st.session_state["j4_theme_choice"] = clicked_theme
        st.session_state["j4_theme_choice_widget"] = clicked_theme
    _render_theme_finder(forced)

    # 21위 밖으로 밀린 테마도 볼 수 있게 한다 — 찾던 테마가 왜 안 보이는지 확인용
    # (2026-07-22 사용자 지적: 금융주 테마가 목록에서 사라졌다).
    next_rows = ranking.get("next_rows") or []
    if next_rows:
        with st.expander(f"21위 밖 테마 {len(next_rows)}개 보기 (오늘 기준 미달로 빠진 테마)", expanded=False):
            lines = [
                f"<span class='j4-muted'>{index}위</span> <b>{row['name']}</b> "
                f"<span style='color:{_STATUS_HEX.get(row['status'], '#e6e6e6')}'>{row['score']:.1f}점</span> "
                f"<span style='color:{_sign_color(row['change_pct'])}'>{_pct(row['change_pct'])}</span>"
                for index, row in enumerate(next_rows, len(ranking["rows"]) + 1)
            ]
            st.markdown(" · ".join(lines), unsafe_allow_html=True)
            st.caption(
                "여기 있는 테마는 오늘 점수가 20위 안에 못 든 것뿐이며, 다음 조회에서 점수가 오르면 "
                "자동으로 다시 올라옵니다. 어제 상위권이었던 테마는 오늘 등락률이 낮아도 계속 심사합니다."
            )
    st.caption(f"테마 계산 시각: {ranking.get('checked_at') or '—'} · 한국 휴장일에는 마지막 거래일 자료")

    if st.session_state.get("j4_theme_choice_widget") not in names:
        preferred = st.session_state.get("j4_theme_choice")
        st.session_state["j4_theme_choice_widget"] = preferred if preferred in names else names[0]
    selected_theme = st.radio("테마 선택", names, horizontal=True, key="j4_theme_choice_widget")
    st.session_state["j4_theme_choice"] = selected_theme
    theme_row = next((row for row in ranking["rows"] if row["name"] == selected_theme), None)
    if theme_row is None:
        st.warning("선택한 테마 자료를 찾지 못했습니다. 다른 테마를 선택하세요.")
        return

    status_hex = _STATUS_HEX.get(theme_row.get("status", ""), "#e6e6e6")
    st.markdown(
        "<div class='j4-theme-box'>"
        f"<span class='j4-green-strong'>{selected_theme}</span> · "
        f"<span style='color:{status_hex}; font-weight:800'>{theme_row['status']}</span> : "
        f"<span class='j4-green'>{theme_row['score']:.1f}/100</span><br>"
        f"<span class='j4-green-strong'>당일</span> {theme_row['change_pct']:+.2f}% · "
        f"KOSPI 대비 {theme_row['relative']:+.2f}%p · 구성종목 상승 {theme_row['up_ratio']:.0f}% · "
        f"3%↑ 종목 {theme_row['strong_ratio']:.0f}% · 구성종목 {theme_row['stock_count']}개<br>"
        "<span class='j4-green-strong'>기준</span> : 70점 이상 주도 · 50~69점 관찰 · 50점 미만 약함"
        "</div>",
        unsafe_allow_html=True,
    )

    with st.spinner(f"{selected_theme} 대장주와 수급을 조회하는 중입니다…"):
        leader_result = j4data.get_theme_leaders(
            theme_row,
            market_score=float(market.get("score") or 0),
            theme_score=float(theme_row.get("score") or 0),
        )
    if not leader_result.get("ok"):
        st.error(f"대장주 조회 실패: {_safe_error_text(leader_result.get('error'))}")
        return
    leaders = leader_result["rows"]
    st.markdown(
        f"<div class='j4-section-title'><span class='j4-theme-badge'>{selected_theme}</span> 테마 종목 1–6위</div>",
        unsafe_allow_html=True,
    )
    st.caption("거래대금 상위 종목만 심사합니다. 상세 분석은 아래 ‘상세 종목 선택’에서 1~3위를 고르세요.")
    stock_key = f"j4_stock_choice_{selected_theme}"
    st.markdown(_leader_table_html(leaders, st.session_state.get(stock_key)), unsafe_allow_html=True)

    _render_leader_comparison(leaders)

    top_candidates = leaders[:3]
    code_options = [leader["code"] for leader in top_candidates]
    if stock_key in st.session_state and st.session_state[stock_key] not in code_options:
        del st.session_state[stock_key]

    def _label(code):
        item = next((cand for cand in top_candidates if cand["code"] == code), None)
        return _stock_radio_label(item) if item else code

    selected_code = st.radio(
        "상세 종목 선택", code_options, format_func=_label, horizontal=True, key=stock_key
    )
    selected_leader = next((item for item in top_candidates if item["code"] == selected_code), top_candidates[0])

    # 여러 테마를 가로질러 '지금 실제로 살 자리'만 모아 보여준다(2026-07-22 사용자 요청).
    # 여기서 종목을 누르면 테마 선택까지 함께 바뀌어 아래 상세가 전부 그 종목으로 교체된다.
    _render_pass_table(ranking, market)

    _render_stock_detail(theme_row, selected_leader, market, top_candidates, stock_key)


def _render_theme_finder(forced: list[str]) -> None:
    """네이버 전체 테마 중 원하는 것을 직접 골라 목록에 넣는다.

    오늘 순위가 낮아 자동 선정에서 빠진 테마(예: 은행)도 눌림목을 확인하고 싶다는
    요구(2026-07-22)에 맞춘 기능이다. 고른 테마는 점수와 무관하게 심사·표시된다.
    """
    listing = j4data.get_all_themes()
    if not listing.get("ok"):
        return
    themes = listing["themes"]
    names = [
        theme["name"] for theme in
        sorted(themes.values(), key=lambda t: t["change_pct"], reverse=True)
    ]
    with st.expander(
        f"🔎 전체 {len(names)}개 테마에서 직접 찾기"
        + (f" — 지금 추가된 테마: {', '.join(forced)}" if forced else ""),
        expanded=False,
    ):
        st.caption(
            "오늘 순위가 낮아 자동 선정에서 빠진 테마도 여기서 고르면 표에 들어옵니다. "
            "점수가 낮으면 '약함'으로 표시되며, 판정 기준은 다른 테마와 똑같습니다."
        )
        picked = st.multiselect(
            "찾아볼 테마 (여러 개 가능)", names, default=forced, key="j4_theme_finder"
        )
        col_add, col_clear = st.columns(2)
        with col_add:
            if st.button("이 테마들 목록에 추가", key="j4_theme_finder_add", width="stretch"):
                st.session_state["j4_forced_themes"] = list(picked)
                st.rerun()
        with col_clear:
            if st.button("직접 추가한 테마 비우기", key="j4_theme_finder_clear", width="stretch"):
                st.session_state["j4_forced_themes"] = []
                st.rerun()


def _render_pullback_finder() -> None:
    """상승추세 중 조정받은 눌림목 종목 (2026-07-22 사용자 스펙).

    조건: 2개 이상 테마 + 52주 신고가 15일 전(±8일) + 50일선 위 + 고점 대비 -3~-20%.
    조회량이 있어 버튼을 누를 때만 실행하고, 결과는 10분간 유지한다.
    """
    st.markdown(
        "<div class='j4-section-title'>📉 눌림목 종목 찾기 (상승추세 중 조정)</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "조건 3가지 — **52주 최고가를 찍고 1~20일 지난 종목** · **2개 이상 테마에 속한 종목** · "
        "**신고가 찍던 시점의 종목 점수 75점 이상**. 테마 순위와 무관하게 전체에서 찾으므로 은행처럼 "
        "순위 밖 테마도 포함됩니다. 하락장 판단은 상단 ‘한국 전체시장 판단’에서 직접 보고 정하십시오."
    )
    # 페이지에 들어오면 자동으로 뜬다(2026-07-22 사용자 지시). 결과는 10분 캐시라
    # 두 번째부터는 즉시 표시되고, 다시 계산하려면 아래 버튼을 누른다.
    if st.button("눌림목 다시 찾기", key="j4_pullback_find", width="stretch"):
        j4data.clear_pullback_cache()
        st.rerun()

    with st.spinner("전체 테마의 구성종목에서 눌림목 조건을 확인하는 중입니다…"):
        result = j4data.find_pullback_stocks()
    if not result.get("ok"):
        st.error(f"눌림목 조회 실패: {_safe_error_text(result.get('error'))}")
        return
    rows = result.get("rows") or []
    window = result.get("window") or (1, 20)
    st.caption(
        f"2개 이상 테마 종목 {result.get('multi_theme_count', 0)}개 중 거래대금 상위 "
        f"{result.get('scanned_count', 0)}개를 심사 → 신고가 {window[0]}~{window[1]}일 전 "
        f"{result.get('screened_count', 0)}개 → 75점 이상 {len(rows)}개"
    )
    if not rows:
        st.info("지금 조건에 맞는 눌림목 종목이 없습니다. 조건을 낮추지 않고 그대로 둡니다.")
        return

    widths = [0.6, 2.1, 0.9, 1.5, 1.2, 1.2, 1.1, 0.9, 1.3, 1.3, 1.2]
    titles = ["순위", "종목", "코드", "눌림 점수", "신고가", "고점 대비", "20일선 이격",
              "테마수", "수급(외+기 5일)", "신고가 때 점수", "지금 점수"]
    for column, title in zip(st.columns(widths), titles):
        column.markdown(f"<div class='j4-th-head'>{title}</div>", unsafe_allow_html=True)

    for index, row in enumerate(rows):
        quality, flow = row["pullback"], row.get("flow") or {}
        cols = st.columns(widths)
        cols[0].markdown(f"<div class='j4-td'>{row['pullback_rank']}</div>", unsafe_allow_html=True)
        # 종목을 누르면 그 종목이 속한 테마를 목록에 넣고(순위 밖일 수 있으므로) 선택까지 옮긴다.
        if cols[1].button(row["name"], key=f"j4pbf_{index:02d}", width="stretch"):
            themes = row.get("themes") or []
            if themes:
                forced = list(st.session_state.get("j4_forced_themes") or [])
                if themes[0] not in forced:
                    forced.append(themes[0])
                st.session_state["j4_forced_themes"] = forced
                st.session_state["j4_pending_pick"] = (themes[0], row["code"])
            st.rerun()
        cols[2].markdown(f"<div class='j4-td'>{row['code']}</div>", unsafe_allow_html=True)
        score = float(quality["score"])
        cols[3].markdown(
            "<div class='j4-td'><div class='j4-barwrap'><div class='j4-bar'>"
            f"<div class='j4-bar-fill j4-bar-green' style='width:{min(score, 100):.0f}%'></div></div>"
            f"<span class='j4-bar-num'>{score:.1f}</span></div></div>", unsafe_allow_html=True)
        cols[4].markdown(
            f"<div class='j4-td' style='color:#44f0a1; font-weight:700'>"
            f"{quality.get('high52_days_ago')}일 전</div>", unsafe_allow_html=True)
        cols[5].markdown(
            f"<div class='j4-td' style='color:{_sign_color(quality['from_high_pct'])}; font-weight:700'>"
            f"{_pct(quality['from_high_pct'])}</div>", unsafe_allow_html=True)
        gap = quality["gap_pct"]
        gap_color = "#44f0a1" if abs(gap) <= 3 else "#ff9d3b"
        cols[6].markdown(
            f"<div class='j4-td' style='color:{gap_color}; font-weight:700'>{gap:+.2f}%</div>",
            unsafe_allow_html=True)
        cols[7].markdown(
            f"<div class='j4-td' style='color:#ffb020; font-weight:700'>{len(row.get('themes') or [])}</div>",
            unsafe_allow_html=True)
        net5 = flow.get("net5_amount") if flow.get("ok") else None
        cols[8].markdown(
            f"<div class='j4-td' style='color:{_sign_color(net5)}; font-weight:700'>{_eok(net5)}</div>",
            unsafe_allow_html=True)
        peak = row.get("peak_score")
        cols[9].markdown(
            f"<div class='j4-td' style='color:#44f0a1; font-weight:800'>"
            f"{f'{float(peak):.1f}' if peak is not None else '—'}</div>", unsafe_allow_html=True)
        cols[10].markdown(
            f"<div class='j4-td' style='color:#ff5b5b; font-weight:700'>{float(row['score']):.1f}</div>",
            unsafe_allow_html=True)
    st.markdown(
        "<style>"
        "div[class*='st-key-j4pbf_'] button { background: transparent !important; border: none !important;"
        " box-shadow: none !important; padding: 0 0 0 0.9rem !important; min-height: 2.5rem !important;"
        " width: 100% !important; justify-content: flex-start !important;"
        " border-bottom: 1px solid rgba(255,255,255,0.06) !important; border-radius: 0 !important; }"
        "div[class*='st-key-j4pbf_'] button:hover { background: rgba(255,255,255,0.06) !important; }"
        "div[class*='st-key-j4pbf_'] button p { font-weight: 800 !important; font-size: 0.95rem !important;"
        " margin: 0 !important; color: #7cc8ff !important; text-align: left !important; }"
        "</style>",
        unsafe_allow_html=True,
    )
    st.caption(
        "**‘신고가 때 점수’가 판정 기준입니다** — 눌림목은 그때 좋았던 종목이 지금 눌린 것이라, "
        "지금 점수로 자르면 눌렸다는 이유로 탈락합니다. 일봉을 신고가 시점까지 잘라 같은 계산을 "
        "다시 돌린 값이며, 수급은 현재 값을 씁니다(가격 항목만 정확히 역산). "
        "종목 이름을 누르면 그 종목의 테마가 위 목록에 추가되고 아래 상세가 그 종목으로 바뀝니다."
    )


def _render_pass_table(ranking: dict, market: dict) -> None:
    """매수 심사 통과 종목 1~10위 — 클릭하면 아래 상세가 그 종목으로 바뀐다."""
    st.markdown(
        "<div class='j4-section-title'>✅ 매수 심사 통과 종목 (전체 테마 교차 · 최대 10위)</div>",
        unsafe_allow_html=True,
    )
    # 표에 보이는 20개가 아니라 '심사된 전체 테마'를 넘긴다 — 은행처럼 순위 밖 테마의
    # 좋은 눌림목을 놓치지 않기 위함이다(2026-07-22 사용자 지적).
    scan_rows = ranking.get("all_scored") or ranking.get("rows") or []
    with st.spinner(f"{len(scan_rows)}개 테마의 종목을 한꺼번에 심사하는 중입니다…"):
        result = j4data.get_pass_candidates(scan_rows, float(market.get("score") or 0))
    if not result.get("ok"):
        st.info(f"통과 종목 심사를 하지 못했습니다: {_safe_error_text(result.get('error'))}")
        return
    rows = result.get("rows") or []
    if not rows:
        st.info(
            f"지금은 상위 {result.get('scanned_themes', 0)}개 테마에서 매수 심사를 통과한 종목도, "
            "가격 셋업이 완성된 대기 종목도 없습니다."
        )
        return

    if result.get("blocked_reason"):
        st.warning(f"⏸ 통과 0건 — {result['blocked_reason']}")
    st.caption(
        f"상위 {result.get('scanned_themes', 0)}개 테마를 교차 심사한 결과입니다. "
        "종목 이름을 누르면 아래 상세·매수 기록이 그 종목으로 바뀝니다."
    )
    widths = [0.6, 2.2, 0.9, 2.0, 1.6, 1.0, 1.1, 1.3, 1.2, 1.1]
    titles = ["순위", "종목", "코드", "조건점수", "테마", "당일", "52주 고가 대비",
              "수급(외+기 5일)", "기준가", "상태"]
    for column, title in zip(st.columns(widths), titles):
        column.markdown(f"<div class='j4-th-head'>{title}</div>", unsafe_allow_html=True)

    for index, row in enumerate(rows):
        metrics, plan, flow = row["metrics"], row["plan"], row["flow"]
        cols = st.columns(widths)
        cols[0].markdown(f"<div class='j4-td'>{row['pass_rank']}</div>", unsafe_allow_html=True)
        if cols[1].button(row["name"], key=f"j4pass_{index:02d}", width="stretch"):
            # 이 표는 테마·종목 라디오보다 아래에 그려지므로, 위젯이 이미 만들어진
            # 뒤에 세션 값을 바꾸면 StreamlitAPIException이 난다. 그래서 선택은
            # pending에만 적어두고, 다음 실행의 위젯 생성 '전'에 반영한다.
            st.session_state["j4_pending_pick"] = (row["theme_name"], row["code"])
            st.rerun()
        cols[2].markdown(f"<div class='j4-td'>{row['code']}</div>", unsafe_allow_html=True)
        score = float(row.get("score") or 0)
        cols[3].markdown(
            "<div class='j4-td'><div class='j4-barwrap'><div class='j4-bar'>"
            f"<div class='j4-bar-fill' style='width:{min(score, 100):.0f}%'></div></div>"
            f"<span class='j4-bar-num'>{score:.1f}</span></div></div>",
            unsafe_allow_html=True,
        )
        cols[4].markdown(
            f"<div class='j4-td j4-muted'>{row['theme_name']}</div>", unsafe_allow_html=True
        )
        change = metrics.get("change_pct")
        cols[5].markdown(
            f"<div class='j4-td' style='color:{_sign_color(change)}; font-weight:700'>{_pct(change)}</div>",
            unsafe_allow_html=True,
        )
        from_high = metrics.get("from_high_pct")
        cols[6].markdown(
            f"<div class='j4-td' style='color:{_sign_color(from_high)}; font-weight:700'>{_pct(from_high)}</div>",
            unsafe_allow_html=True,
        )
        net5 = flow.get("net5_amount") if flow.get("ok") else None
        cols[7].markdown(
            f"<div class='j4-td' style='color:{_sign_color(net5)}; font-weight:700'>{_eok(net5)}</div>",
            unsafe_allow_html=True,
        )
        cols[8].markdown(
            f"<div class='j4-td' style='color:#44f0a1; font-weight:700'>{_won(plan.get('trigger'))}</div>",
            unsafe_allow_html=True,
        )
        if row.get("gate_blocked"):
            state_text, state_color = "게이트 대기", "#ff9d3b"
        else:
            state_text, state_color = "통과", "#44f0a1"
        cols[9].markdown(
            f"<div class='j4-td' style='color:{state_color}; font-weight:800'>{state_text}</div>",
            unsafe_allow_html=True,
        )
    _render_pullback_finder()

    st.markdown(
        "<style>"
        "div[class*='st-key-j4pass_'] button { background: transparent !important; border: none !important;"
        " box-shadow: none !important; padding: 0 0 0 0.9rem !important; min-height: 2.5rem !important;"
        " width: 100% !important; justify-content: flex-start !important;"
        " border-bottom: 1px solid rgba(255,255,255,0.06) !important; border-radius: 0 !important; }"
        "div[class*='st-key-j4pass_'] button:hover { background: rgba(255,255,255,0.06) !important; }"
        "div[class*='st-key-j4pass_'] button p { font-weight: 800 !important; font-size: 0.95rem !important;"
        " margin: 0 !important; color: #44f0a1 !important; text-align: left !important; }"
        "</style>",
        unsafe_allow_html=True,
    )


def _render_records_tab() -> None:
    st.subheader("매수 기록 현황")
    try:
        progress = j4store.trade_progress()
        records = j4store.list_trades(limit=300)
    except Exception as exc:
        st.error(f"기록 DB 조회 실패: {_safe_error_text(exc)}")
        return
    st.progress(
        min(progress["closed_count"] / progress["minimum_sample"], 1.0),
        text=f"청산 표본 {progress['closed_count']}/30건 · 전체 매수 {progress['total_count']}건 · 보유 {progress['open_count']}건",
    )
    if progress["closed_count"] < 30:
        st.info("청산 30건 전에는 승률·기대값을 확정하지 않고 원자료만 축적합니다.")
    if not records:
        st.caption("아직 저장된 자비스4 매수 기록이 없습니다.")
        return
    _render_records_editor(records)


def _render_method_tab() -> None:
    st.subheader("판정 기준과 데이터 정책")
    st.markdown(
        """
        1. **시장 게이트** — KOSPI·KOSDAQ의 20/50일선, 미국 전일, 외국인·기관 수급, 원/달러로
           신규 매수 가능 국면을 먼저 판단합니다.
        2. **테마 강도(동적 선정)** — 네이버 전체 테마를 매일 훑어 KOSPI 대비 상대강도, 구성종목
           확산도, 3%↑ 종목 비중, 거래대금으로 상위 20개를 뽑습니다. 약한 테마는 자동 탈락합니다.
        3. **대장주 품질(6개 항목)** — 테마 대비 상대강도 20 + 52주 신고가 위치 15 + 추세 20 +
           유동성 15 + 변동성 10 + **수급(외국인·기관) 20** = 100점.
           테마 점수가 낮아도 **종목 점수가 85점을 넘으면 테마 게이트를 면제**합니다 —
           국내 테마는 성격이 섞여 있어(예: 은행 테마 22점인데 하나금융지주 95점)
           테마 평균이 종목 품질을 대표하지 못하기 때문입니다. 시장 게이트는 면제되지 않습니다.
        4. **매수 타이밍** — 신고가 거래량 돌파 또는 상승추세 내 20일선 눌림만 조건부 후보로 봅니다.
        5. **국내형 추격 금지** — 당일 +20% 이상, 5일 +25% 이상, ATR 15% 이상은 점수와 무관하게
           추격을 금지합니다(상한가 30% 제도 반영).
        6. **호가단위 반올림** — 모든 기준가·목표가는 KRX 호가단위로 반올림해 실제 주문 가능한
           가격으로 표시합니다.
        7. **자동 제외** — 스팩·리츠·우선주는 후보에서 제외합니다.
        """
    )
    st.warning(
        "조건점수는 상승확률이 아닙니다. 실제 매수·청산 표본이 30건 이상 쌓인 뒤 "
        "셋업별 기대값과 최대손실을 검증해 가중치를 조정합니다."
    )
    st.caption(
        "시세는 FinanceDataReader, 테마·수급은 네이버 금융 공개 화면을 읽습니다. "
        "pykrx는 KRX 로그인 요구로 사용하지 않습니다. 개인 연구용이며 거래소 정식 실시간 "
        "피드가 아니므로 지연·누락 가능성이 있습니다."
    )


def main() -> None:
    st.title("자비스4 — 한국 테마 레이더")
    try:
        j4store.ensure_tables()
    except Exception as exc:
        st.error(f"자비스4 기록 테이블 준비 실패: {_safe_error_text(exc)}")

    _render_market_overview()
    market = st.session_state.get("j4_market_overview") or {"ok": False, "score": 0, "regime": "자료부족"}
    st.divider()
    # 시장판단 화면의 한국장 기관 수급 반전 카드를 그대로 가져온다(자비스4 전용).
    market_signal_ui.render_kr_flow_card()
    st.divider()
    radar_tab, records_tab, method_tab = st.tabs(["테마·종목", "매수 기록 현황", "판정 기준"])
    with radar_tab:
        _render_radar_tab(market)
    with records_tab:
        _render_records_tab()
    with method_tab:
        _render_method_tab()


main()
