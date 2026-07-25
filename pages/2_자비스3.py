"""자비스3 — 미국 테마 레이더와 실제 매수 기록 페이지."""

from __future__ import annotations

from datetime import date
import html

import streamlit as st

import auth  # 로그인 유지(쿠키). 쿠키가 안 되면 조용히 세션 기반 동작으로 남는다.

st.set_page_config(page_title="자비스3 — 미국 테마 레이더", layout="wide")

st.markdown(
    """
    <style>
    /* 왼쪽 메뉴는 좁게, 오른쪽 본문은 넓게 (2026-07-24 사용자 지시). j-narrow-sidebar */
    [data-testid="stSidebar"],
    section[data-testid="stSidebar"] {
        width: 10rem !important; min-width: 10rem !important; max-width: 10rem !important;
    }
    [data-testid="stSidebar"] > div,
    [data-testid="stSidebarContent"],
    section[data-testid="stSidebar"] > div {
        width: 10rem !important; min-width: 10rem !important;
    }
    /* 메뉴 글자가 만드는 자동 최소폭 때문에 사이드바가 안 좁아지는 것을 막는다 */
    [data-testid="stSidebarNav"],
    [data-testid="stSidebarNav"] ul,
    [data-testid="stSidebarNav"] li,
    [data-testid="stSidebarNav"] a { min-width: 0 !important; max-width: 100% !important; }
    [data-testid="stSidebarNav"] a p { overflow-wrap: anywhere; }
    [data-testid="stSidebarNav"] li { margin: 0 !important; }
    [data-testid="stSidebarNav"] a { padding: 0.45rem 0.6rem !important; }
    [data-testid="stSidebarNav"] a,
    [data-testid="stSidebarNav"] a * {
        font-size: 1.15rem !important;
        font-weight: 800 !important;
        color: #ffb020 !important;
        line-height: 1.4 !important;
    }
    [data-testid="stSidebarNav"] li:first-child a p { font-size: 0 !important; }
    [data-testid="stSidebarNav"] li:first-child a p::before {
        content: "자비스1";
        font-size: 1.15rem;
        font-weight: 800;
        color: #ffb020;
    }
    /* 사이드바 순서: 시장판단 → 자비스1 → 자비스2 → 미국테마 (2026-07-22 사용자 지시) */
    [data-testid="stSidebarNav"] ul { display: flex; flex-direction: column; }
    [data-testid="stSidebarNav"] li:nth-child(1) { order: 2; }
    [data-testid="stSidebarNav"] li:nth-child(2) { order: 1; }
    [data-testid="stSidebarNav"] li:nth-child(3) { order: 3; }
    [data-testid="stSidebarNav"] li:nth-child(4) { order: 4; }
    [data-testid="stSidebarNav"] li:nth-child(5) { order: 5; }
    [data-testid="stSidebarNav"] li:nth-child(6) { order: 6; }
    [data-testid="stSidebarNav"] li:nth-child(4) a p { font-size: 0 !important; }
    [data-testid="stSidebarNav"] li:nth-child(4) a p::before {
        content: "미국테마";
        font-size: 1.15rem;
        font-weight: 800;
        color: #ffb020;
    }
    [data-testid="stSidebarNav"] li:nth-child(5) a p { font-size: 0 !important; }
    [data-testid="stSidebarNav"] li:nth-child(5) a p::before {
        content: "한국테마";
        font-size: 1.15rem;
        font-weight: 800;
        color: #ffb020;
    }
    [data-testid="stSidebarNav"] li:nth-child(6) a p { font-size: 0 !important; }
    [data-testid="stSidebarNav"] li:nth-child(6) a p::before {
        content: "한국테마\\A(선행감지)"; white-space: pre; line-height: 1.2; font-size: 1.15rem; font-weight: 800; color: #ffb020;
    }
    div[class*="st-key-j3_theme_choice"] [data-baseweb="button-group"] {
        gap: 0.35rem;
    }
    .j3-score-guide, .j3-market-flow {
        color: #44f0a1;
        font-size: 1rem;
        font-weight: 800;
        line-height: 1.65;
    }
    .j3-score-guide { margin-top: 0.35rem; }
    .j3-market-flow {
        margin: 1.9rem 0 0.8rem 0;
        padding: 0.75rem 1rem;
        border-left: 4px solid #44f0a1;
        background: rgba(34, 197, 94, 0.08);
        border-radius: 0.4rem;
    }
    .j3-action-box {
        color: #4da6ff;
        font-size: 1rem;
        font-weight: 800;
        line-height: 1.65;
        margin-top: 1.9rem;
        margin-bottom: 0.8rem;
        padding: 0.8rem 1rem;
        border: 1px solid rgba(77, 166, 255, 0.45);
        background: rgba(37, 99, 235, 0.13);
        border-radius: 0.55rem;
    }
    h1 { font-size: 2.05rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.65rem !important; }
    /* 종목 상세 색 규칙: 종목명 밝은 보라, 라벨 코발트, +파랑/−빨강, 내용 초록 */
    .j3-stock-name { color: #c084fc; font-size: 1.7rem; font-weight: 800; line-height: 1.2; margin-top: 0.3rem; }
    .j3-stock-sub { color: #9aa0aa; font-size: 0.95rem; margin: 0.1rem 0 0.7rem; }
    .j3-metric-row { display: flex; flex-wrap: wrap; gap: 1.6rem; margin: 0.2rem 0 0.4rem; }
    .j3-mc { min-width: 120px; }
    .j3-mc-label { color: #4da6ff; font-size: 0.92rem; font-weight: 800; }
    .j3-mc-val { font-size: 1.5rem; font-weight: 800; color: #e6e6e6; line-height: 1.25; }
    .j3-mc-sub { font-size: 0.95rem; font-weight: 800; }
    .j3-up { color: #4da6ff; }
    .j3-down { color: #ff5b5b; }
    .j3-muted { color: #9aa0aa; }
    .j3-section-title { color: #4da6ff; font-size: 1.2rem; font-weight: 800; margin: 1rem 0 0.5rem; }
    .j3-factor-table { width: 100%; border-collapse: collapse; margin-bottom: 0.5rem; font-size: 0.95rem; }
    .j3-factor-table th { text-align: center; color: #4da6ff; font-weight: 800; padding: 0.45rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.18); }
    .j3-factor-table td { color: #44f0a1; font-weight: 700; padding: 0.4rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.06); }
    .j3-factor-table td.j3-fac-name { text-align: left; }
    .j3-factor-table td.j3-fac-val { text-align: center; }
    .j3-reason-card { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.09); border-radius: 0.55rem; padding: 0.6rem 0.75rem; height: 100%; }
    .j3-reason-title { color: #4da6ff; font-weight: 800; font-size: 0.95rem; margin-bottom: 0.25rem; }
    .j3-reason-body { color: #44f0a1; font-weight: 700; font-size: 0.9rem; line-height: 1.45; }
    .j3-chart-title { color: #e6e6e6; font-weight: 800; font-size: 1rem; margin-bottom: 0.1rem; }
    .j3-leader-name { font-size: 1.2rem; font-weight: 800; color: #e6e6e6; line-height: 1.25; }
    .j3-leader-live { font-size: 1.2rem; font-weight: 800; color: #e6e6e6; margin-top: 0.35rem; }
    .j3-leader-live .j3-mc-sub { font-size: 1rem; }
    .j3-leader-name .j3-medal { font-size: 1.6rem; vertical-align: -2px; }
    .j3-leader-score-label { color: #4da6ff; font-size: 0.85rem; font-weight: 800; margin-top: 0.35rem; }
    .j3-leader-score { color: #ff5b5b; font-size: 1.9rem; font-weight: 800; line-height: 1.1; }
    .j3-leader-state { color: #9aa0aa; font-size: 0.9rem; }
    .j3-green { color: #44f0a1; }
    .j3-green-strong { color: #22c55e; font-weight: 800; }
    .j3-theme-box { background: rgba(77,166,255,0.08); border: 1px solid rgba(77,166,255,0.3); border-radius: 0.55rem; padding: 0.7rem 0.9rem; font-size: 0.95rem; line-height: 1.7; margin-bottom: 0.6rem; }
    .j3-reason-mustard { background: rgba(234,179,8,0.12); border: 1px solid rgba(234,179,8,0.42); color: #e6c34a; border-radius: 0.5rem; padding: 0.6rem 0.8rem; font-weight: 700; }
    .j3-chart-heading { margin-top: 1.6rem; font-size: 1.15rem; font-weight: 800; color: #e6e6e6; }
    .j3-theme-badge { display: inline-block; background: rgba(255,176,32,0.16); color: #ffb020; border: 1px solid #ffb020; border-radius: 0.5rem; padding: 0.15rem 0.7rem; font-weight: 800; font-size: 1.05rem; margin-right: 0.4rem; }
    .j3-flow-label { color: #44f0a1; font-weight: 800; }
    .j3-flow-body { color: #4da6ff; font-weight: 800; }
    .j3-action-label { color: #4da6ff; font-weight: 800; }
    .j3-action-posture { color: #ff5b5b; font-weight: 800; }
    .j3-action-detail { color: #ff9d3b; font-weight: 800; }
    .j3-top-row { display: flex; gap: 2rem; flex-wrap: wrap; margin-bottom: 0.3rem;
        align-items: center; }
    .j3-top-cell { min-width: 150px; }
    .j3-top-label { color: #9aa0aa; font-size: 0.9rem; }
    .j3-top-val { font-size: 1.7rem; font-weight: 800; line-height: 1.2; }
    .j3-top-sub { font-size: 0.95rem; font-weight: 700; }
    .j3-theme-table { width: 100%; border-collapse: collapse; font-size: 0.92rem; table-layout: fixed; }
    .j3-theme-table th { text-align: center; color: #9aa0aa; font-weight: 800; padding: 0.5rem 0.4rem; border-bottom: 1px solid rgba(255,255,255,0.18); }
    .j3-theme-table td { text-align: center; padding: 0.45rem 0.4rem; border-bottom: 1px solid rgba(255,255,255,0.06); color: #e6e6e6; overflow: hidden; text-overflow: ellipsis; }
    .j3-theme-table td.j3-th-name { text-align: left; padding-left: 1.2rem; font-weight: 800; }
    .j3-theme-table th.j3-th-left { text-align: left; padding-left: 1.2rem; }
    .j3-th-link { display: block; text-decoration: none; }
    .j3-th-link:hover { text-decoration: underline; }
    .j3-th-selected { background: rgba(255,176,32,0.13); }
    .j3-th-muted { color: #9aa0aa; }
    .j3-barwrap { display: flex; align-items: center; gap: 6px; }
    .j3-bar { position: relative; flex: 1; background: rgba(255,255,255,0.10); border-radius: 4px; height: 8px; overflow: hidden; }
    .j3-bar-fill { height: 8px; background: #ff5b5b; }
    .j3-bar-blue { background: #4da6ff; }
    .j3-bar-green { background: #44f0a1; }
    .j3-bar-num { font-size: 0.82rem; font-weight: 700; color: #e6e6e6; min-width: 32px; text-align: right; }
    /* 클릭 가능한 테마표: 머리글·칸은 가운데 정렬, 테마명은 버튼 */
    .j3-th-head { text-align: center; color: #9aa0aa; font-weight: 800; font-size: 0.92rem;
        padding: 0.45rem 0 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.22); }
    /* 테마명 버튼 행과 나머지 HTML 칸의 세로 라인을 맞춘다(2026-07-22 사용자 지시:
       "Line 일치시킬 것") — 양쪽 다 같은 고정 높이(2.5rem)에 수직 가운데 정렬. */
    .j3-td { text-align: center; color: #e6e6e6; font-size: 0.92rem; padding: 0;
        border-bottom: 1px solid rgba(255,255,255,0.06); min-height: 2.5rem;
        display: flex; align-items: center; justify-content: center; }
    .j3-td > .j3-barwrap { width: 100%; }
    div[class*="st-key-j3tbtn_"] button {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
        min-height: 2.5rem !important;
        width: 100% !important;
        border-bottom: 1px solid rgba(255,255,255,0.06) !important;
        border-radius: 0 !important;
    }
    div[class*="st-key-j3tbtn_"] button:hover { background: rgba(255,255,255,0.06) !important; }
    /* 테마명은 좌측 정렬(제목만 가운데) — 2026-07-22 사용자 지시 */
    div[class*="st-key-j3tbtn_"] button { justify-content: flex-start !important; padding-left: 0.9rem !important; }
    div[class*="st-key-j3tbtn_"] button p {
        font-weight: 800 !important; font-size: 0.95rem !important; margin: 0 !important; text-align: left !important;
    }
    /* 상세 종목 선택: 라벨은 스카이블루·두 치수 크게, 보기 글자는 한 치수 크게 */
    div[class*="st-key-j3_stock_choice"] [data-testid="stWidgetLabel"] p {
        color: #7cc8ff !important;
        font-size: 1.55rem !important;
        font-weight: 800 !important;
    }
    div[class*="st-key-j3_stock_choice"] label p,
    div[class*="st-key-j3_stock_choice"] label div,
    div[class*="st-key-j3_stock_choice"] label span {
        font-size: 1.12rem !important;
    }
    .j3-holo-card {
        position: relative;
        background: linear-gradient(135deg, rgba(77,166,255,0.07), rgba(168,85,247,0.07));
        border: 1px solid rgba(77,166,255,0.55);
        border-radius: 10px;
        padding: 1.15rem 1.3rem;
        box-shadow: 0 0 14px rgba(77,166,255,0.28), inset 0 0 20px rgba(77,166,255,0.07);
    }
    /* 3열: 1열 가격 · 2열 가격 · 3열 종목 조건점수. 칸 사이 가로 간격을 넉넉히 두고
       (2026-07-22 사용자 지시: 화면이 작으면 글자가 붙어버림), 좁은 화면에서는
       2열로 바꿔 절대 겹치지 않게 한다. */
    .j3-holo-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1.1rem 1.8rem; }
    .j3-holo-cell { min-width: 0; }
    @media (max-width: 900px) {
        .j3-holo-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    /* 종목 조건점수는 2R 목표(참고) 바로 아래, 같은 열에 둔다 */
    /* 종목 조건점수는 같은 그리드의 오른쪽 열에 넣어 2R 목표와 라인을 맞춘다 */
    .j3-holo-score .label { color: #4da6ff !important; font-size: 0.92rem; font-weight: 800; }
    .j3-holo-score .val { color: #44f0a1 !important; font-size: 1.5rem; font-weight: 800; line-height: 1.25; }
    .j3-holo-score .state { color: #9aa0aa; font-size: 0.95rem; font-weight: 700; }
    /* 참고 안내: 위 카드와 간격 + 글자 키움 */
    .j3-plan-note { margin-top: 1.1rem; color: #9aa0aa; font-size: 1rem; line-height: 1.65; }
    .j3-plan-note b { color: #44f0a1; font-size: 1.1rem; font-weight: 800; }
    .j3-danta-box { border: 1px solid rgba(234,179,8,0.5); background: rgba(234,179,8,0.07);
        border-radius: 0.55rem; padding: 0.7rem 0.9rem; margin-top: 0.9rem; line-height: 1.7; }
    .j3-danta-title { color: #ff9d3b; font-weight: 800; }
    .j3-holo-cell .label { color: #9aa0aa; font-size: 0.85rem; }
    .j3-holo-cell .val { font-size: 1.5rem; font-weight: 800; color: #e6e6e6; line-height: 1.2; text-shadow: 0 0 8px rgba(77,166,255,0.45); }
    .j3-holo-corner { position: absolute; width: 14px; height: 14px; border-color: #4da6ff; }
    .j3-holo-corner.tl { top: 6px; left: 6px; border-top: 2px solid #4da6ff; border-left: 2px solid #4da6ff; }
    .j3-holo-corner.tr { top: 6px; right: 6px; border-top: 2px solid #4da6ff; border-right: 2px solid #4da6ff; }
    .j3-holo-corner.bl { bottom: 6px; left: 6px; border-bottom: 2px solid #4da6ff; border-left: 2px solid #4da6ff; }
    .j3-holo-corner.br { bottom: 6px; right: 6px; border-bottom: 2px solid #4da6ff; border-right: 2px solid #4da6ff; }
    .j3-pull-guide { border-left: 4px solid #4da6ff; background: rgba(77,166,255,.07);
        border-radius: .45rem; padding: .7rem .9rem; color: #b7c0ce; line-height: 1.6;
        margin: .15rem 0 .65rem; }
    .j3-pull-guide b { color: #44f0a1; }
    .j3-pull-stats { color: #9dccff; font-size: .93rem; line-height: 1.55;
        margin: .15rem 0 .65rem; text-align: left; }
    .j3-pull-table-wrap { overflow-x: auto; border: 1px solid rgba(255,255,255,.08);
        border-radius: .55rem; margin-top: .25rem; }
    .j3-pull-table { width: 100%; min-width: 1120px; border-collapse: collapse;
        table-layout: fixed; font-size: .9rem; }
    .j3-pull-table th { text-align: center; color: #7cc8ff; font-weight: 800;
        padding: .58rem .42rem; background: rgba(77,166,255,.07);
        border-bottom: 1px solid rgba(77,166,255,.32); }
    .j3-pull-table td { text-align: center; color: #e6e6e6; padding: .52rem .42rem;
        border-bottom: 1px solid rgba(255,255,255,.06); vertical-align: middle;
        overflow: hidden; text-overflow: ellipsis; }
    .j3-pull-table tr:last-child td { border-bottom: none; }
    .j3-pull-table th.j3-pull-left, .j3-pull-table td.j3-pull-left { text-align: left; }
    .j3-pull-name { color: #c084fc !important; font-weight: 800; }
    .j3-pull-theme { color: #9dccff !important; }
    .j3-pull-amber { color: #ffb020 !important; font-weight: 800; }
    .j3-pull-detail { border: 1px solid rgba(192,132,252,.45);
        background: linear-gradient(135deg, rgba(192,132,252,.08), rgba(77,166,255,.06));
        border-radius: .65rem; padding: .75rem 1rem; margin: 1rem 0 .4rem; }
    .j3-pull-detail-title { color: #c084fc; font-size: 1.35rem; font-weight: 800; }
    .j3-pull-detail-sub { color: #9dccff; font-size: .92rem; margin-top: .15rem; }
    div[class*="st-key-j3pbf_"] button {
        background: transparent !important; border: none !important; box-shadow: none !important;
        padding: 0 0 0 .8rem !important; min-height: 2.5rem !important; width: 100% !important;
        justify-content: flex-start !important; border-bottom: 1px solid rgba(255,255,255,.06) !important;
        border-radius: 0 !important;
    }
    div[class*="st-key-j3pbf_"] button:hover { background: rgba(77,166,255,.09) !important; }
    div[class*="st-key-j3pbf_"] button p {
        color: #c084fc !important; font-weight: 800 !important; font-size: .94rem !important;
        margin: 0 !important; text-align: left !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _login_gate() -> None:
    auth.sync_auth()  # 쿠키에 로그인이 남아 있으면 되살린다(폰 복귀 시 재로그인 방지).
    if st.session_state.get("authenticated"):
        return
    st.markdown("## 자비스3 — 미국 테마 레이더")
    st.caption("승인된 사용자만 접근할 수 있습니다. 여기서 바로 로그인할 수 있습니다.")
    try:
        password = st.secrets.get("APP_PASSWORD")
    except Exception:
        password = None
    if not password:
        st.warning(".streamlit/secrets.toml에 APP_PASSWORD 설정이 필요합니다.")
        st.stop()
    entered = st.text_input("비밀번호", type="password", key="j3_login_password")
    if st.button("자비스3 로그인", key="j3_login_submit", width="stretch"):
        if entered == password:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    st.stop()


_login_gate()

import importlib
import time

import altair as alt
import pandas as pd

import fear_greed_ui
import mobile_ui
import regime_gauge_ui
import jarvis3_data as j3data
import jarvis3_store as j3store
import market_signal_ui

# ── 온라인 옛 모듈 자가복구 ──────────────────────────────────────────────────
# 스트림릿 클라우드는 배포 갱신 때 페이지 파일만 새로 읽고 import된 모듈은 옛것을
# 프로세스에 유지하는 경우가 있다(2026-07-22 '모듈 갱신 대기'·'당일 자료 없음' 실발생).
# 새 코드에만 있는 함수가 없으면 그 모듈을 파일에서 다시 읽어 재부팅 없이 복구한다.
_REQUIRED_J3_REVISION = 2026072406
if (
    not hasattr(j3data, "get_fear_greed")
    or not hasattr(j3data, "_intraday_chart_payload")
    or not hasattr(j3data, "find_pullback_stocks")
    or not hasattr(j3data, "analyze_pullback_stock")
    # 이름은 그대로인데 내용만 옛것인 모듈도 걸러낸다(2026-07-24 자비스4에서 실제 발생).
    or int(getattr(j3data, "MODULE_REVISION", 0)) < _REQUIRED_J3_REVISION
):
    j3data = importlib.reload(j3data)
_REQUIRED_SIGNAL_UI_REVISION = 2026072407
if (
    not hasattr(market_signal_ui, "_STATUS_TEXT")
    # 이름은 그대로인데 내용만 옛것인 모듈도 걸러낸다(2026-07-24 온라인 실발생).
    or int(getattr(market_signal_ui, "MODULE_REVISION", 0)) < _REQUIRED_SIGNAL_UI_REVISION
):
    import sys

    # 게이지 그림 모듈도 함께 다시 읽는다 — 카드가 이것들을 쓰므로 하나만 옛것이면
    # 화면 일부만 옛 모습으로 남는다.
    for _dep_name in (
        "market_signal_common", "kr_intraday_flow",
        "us_market_signal_engine", "naver_market_data",
        "gauge_ui", "fear_greed_ui", "regime_gauge_ui",
    ):
        _dep = sys.modules.get(_dep_name)
        if _dep is not None:
            importlib.reload(_dep)
    market_signal_ui = importlib.reload(market_signal_ui)
    fear_greed_ui = sys.modules.get("fear_greed_ui", fear_greed_ui)
    regime_gauge_ui = sys.modules.get("regime_gauge_ui", regime_gauge_ui)


def _pct(value) -> str:
    return "—" if value is None else f"{float(value):+.2f}%"


def _price(value) -> str:
    return "—" if value is None else f"${float(value):,.2f}"


def _number(value, digits=1) -> str:
    return "—" if value is None else f"{float(value):,.{digits}f}"


def _sign_class(value) -> str:
    """미국장 색: 상승(+)은 푸른색, 하락(−)은 붉은색."""
    if value is None:
        return "j3-muted"
    try:
        return "j3-up" if float(value) >= 0 else "j3-down"
    except (TypeError, ValueError):
        return "j3-muted"


def _signed_pct_html(value) -> str:
    return f"<span class='{_sign_class(value)}'>{_pct(value)}</span>"


def _sign_color(value) -> str:
    """미국장 색 hex: 상승(+) 밝은 코발트, 하락(−) 붉은색 (인라인 지정용)."""
    if value is None:
        return "#9aa0aa"
    try:
        return "#4da6ff" if float(value) >= 0 else "#ff5b5b"
    except (TypeError, ValueError):
        return "#9aa0aa"


def _top_metric(label, value, value_color, sub, *, sub_color=None, sub_signed=False) -> str:
    if sub_signed:
        sub_html = f"<div class='j3-top-sub {_sign_class(sub)}'>{_pct(sub)}</div>"
    else:
        sub_html = f"<div class='j3-top-sub' style='color:{sub_color or '#9aa0aa'}'>{sub}</div>"
    return (
        f"<div class='j3-top-cell'><div class='j3-top-label'>{label}</div>"
        f"<div class='j3-top-val' style='color:{value_color}'>{value}</div>{sub_html}</div>"
    )


_STATUS_HEX = {"주도": "#44f0a1", "관찰": "#ff9d3b", "약함": "#9aa0aa"}


def _fear_greed_color(score) -> str:
    """CNN 게이지 구간색: 공포는 붉게, 탐욕은 초록으로."""
    if score is None:
        return "#9aa0aa"
    score = float(score)
    if score <= 25:
        return "#ff5b5b"
    if score < 45:
        return "#ff9d3b"
    if score <= 55:
        return "#e6e6e6"
    if score < 75:
        return "#44f0a1"
    return "#22c55e"


_THEME_COL_WIDTHS = [0.75, 2.3, 0.9, 2.2, 0.95, 1.05, 1.35, 1.45]


def _render_theme_table(ranking: dict, selected: str | None) -> str | None:
    """테마표를 그리고, 테마 이름 버튼이 눌리면 그 테마명을 돌려준다.

    테마명만 st.button이라 클릭이 확실히 되고(세션도 안 끊김),
    나머지 칸은 HTML이라 가운데 정렬·색·막대를 그대로 쓸 수 있다.
    """
    titles = ["순위", "테마", "ETF", "조건점수", "상태", "당일", "20일 상대강도", "구성종목 확산"]
    for column, title in zip(st.columns(_THEME_COL_WIDTHS), titles):
        column.markdown(f"<div class='j3-th-head'>{title}</div>", unsafe_allow_html=True)

    # 테마명 버튼 색을 상태색과 맞춘다(선택된 테마는 주황 배경으로 표시).
    # 키는 2자리 고정폭(j3tbtn_01)으로 만든다 — class*= 부분일치 선택자라서
    # j3tbtn_1이 j3tbtn_10~19에도 매칭돼 안 고른 행에 배경이 묻던 버그 수정
    # (2026-07-22 사용자 제보: "클릭 후 흔적이 남음").
    button_css = []
    clicked = None
    for index, row in enumerate(ranking.get("rows", [])):
        name = row.get("name", "")
        color = _STATUS_HEX.get(row.get("status", ""), "#e6e6e6")
        button_key = f"j3tbtn_{index:02d}"
        button_css.append(f"div[class*='st-key-{button_key}'] button p {{ color: {color} !important; }}")
        if name == selected:
            button_css.append(
                f"div[class*='st-key-{button_key}'] button {{ background: rgba(255,176,32,0.16) !important; }}"
            )
        cols = st.columns(_THEME_COL_WIDTHS)
        cols[0].markdown(f"<div class='j3-td'>{row.get('rank', '')}</div>", unsafe_allow_html=True)
        if cols[1].button(name, key=button_key, width="stretch"):
            clicked = name
        cols[2].markdown(f"<div class='j3-td'>{row.get('etf', '')}</div>", unsafe_allow_html=True)
        if not row.get("ok"):
            for cell in cols[3:]:
                cell.markdown("<div class='j3-td j3-th-muted'>자료 부족</div>", unsafe_allow_html=True)
            continue
        score = float(row.get("score") or 0)
        breadth, change, rs20 = row.get("breadth"), row.get("change_pct"), row.get("rs20")
        cols[3].markdown(
            "<div class='j3-td'><div class='j3-barwrap'><div class='j3-bar'>"
            f"<div class='j3-bar-fill' style='width:{min(score, 100):.0f}%'></div></div>"
            f"<span class='j3-bar-num'>{score:.1f}</span></div></div>",
            unsafe_allow_html=True,
        )
        cols[4].markdown(
            f"<div class='j3-td' style='color:{color}; font-weight:800'>{row.get('status', '')}</div>",
            unsafe_allow_html=True,
        )
        cols[5].markdown(
            f"<div class='j3-td' style='color:{_sign_color(change)}; font-weight:700'>{_pct(change)}</div>",
            unsafe_allow_html=True,
        )
        rs_text = "—" if rs20 is None else f"{float(rs20):+.1f}%p"
        cols[6].markdown(
            f"<div class='j3-td' style='color:{_sign_color(rs20)}; font-weight:700'>{rs_text}</div>",
            unsafe_allow_html=True,
        )
        breadth_cell = "—" if breadth is None else (
            "<div class='j3-barwrap'><div class='j3-bar'>"
            f"<div class='j3-bar-fill j3-bar-green' style='width:{min(float(breadth), 100):.0f}%'></div></div>"
            f"<span class='j3-bar-num'>{float(breadth):.0f}%</span></div>"
        )
        cols[7].markdown(f"<div class='j3-td'>{breadth_cell}</div>", unsafe_allow_html=True)

    st.markdown("<style>" + "".join(button_css) + "</style>", unsafe_allow_html=True)
    return clicked


def _safe_error_text(error) -> str:
    text = str(error or "일시적인 온라인 조회 오류")
    return text[:220]


def _trend_position(row: dict, label: str) -> str:
    current = row.get("current")
    sma20, sma50 = row.get("sma20"), row.get("sma50")
    if current is None or sma20 is None or sma50 is None:
        return f"{label} 추세 자료가 부족합니다"
    above20, above50 = current > sma20, current > sma50
    if above20 and above50:
        return f"{label}은 20·50일선 위로 단기·중기 추세가 모두 살아 있습니다"
    if above50:
        return f"{label}은 50일선 위지만 20일선 아래여서 중기 추세 속 단기 조정입니다"
    if above20:
        return f"{label}은 20일선은 회복했지만 50일선 아래라 추세 전환 확인이 필요합니다"
    return f"{label}은 20·50일선 아래로 단기·중기 흐름이 모두 약합니다"


def _market_flow_text(overview: dict) -> str:
    rows = overview.get("rows", {})
    sections = [
        _trend_position(rows.get("SPY", {}), "S&P500"),
        _trend_position(rows.get("QQQ", {}), "나스닥100"),
    ]
    iwm = rows.get("IWM", {})
    if iwm.get("current") is not None and iwm.get("sma50") is not None:
        if iwm["current"] > iwm["sma50"]:
            sections.append("IWM이 50일선 위여서 중소형주도 중기 추세를 지킨다는 ‘중소형주 동행’ 조건은 충족했습니다")
        else:
            sections.append("IWM이 50일선 아래라 중소형주는 대형주 상승에 충분히 동참하지 못하고 있습니다")
    vix_value = rows.get("^VIX", {}).get("current")
    if vix_value is not None:
        if vix_value < 25:
            sections.append(f"VIX {vix_value:.1f}은 25 미만으로 공포·변동성은 과열 구간이 아닙니다")
        elif vix_value < 35:
            sections.append(f"VIX {vix_value:.1f}은 25~35 경계 구간이라 변동성 확대에 주의해야 합니다")
        else:
            sections.append(f"VIX {vix_value:.1f}은 35 이상으로 시장 공포와 급변 위험이 매우 높습니다")
    # 문장이 한 덩어리로 붙으면 너무 빽빽하다는 지적(2026-07-22 캡처 빗금 표시)에 따라
    # 문장마다 줄을 바꿔 보여준다.
    return ".<br>".join(sections) + "."


def _market_score_detail(overview: dict) -> str:
    breakdown = overview.get("score_breakdown") or []
    if not breakdown:
        return "세부 점수는 다음 온라인 갱신에서 표시됩니다."
    earned = [f"{item['label']} {item['earned']}/{item['max']}점" for item in breakdown if item.get("earned")]
    missed = [item["label"] for item in breakdown if not item.get("earned")]
    earned_text = ", ".join(earned) if earned else "충족 신호 없음"
    missed_text = ", ".join(missed) if missed else "없음"
    return f"현재 획득: {earned_text} · 미충족: {missed_text}"


def _market_action_detail(overview: dict) -> str:
    # 문장마다 <br>로 줄을 바꾼다 — 글자가 너무 빽빽하다는 지적(2026-07-22 캡처 빗금) 반영.
    score = float(overview.get("score") or 0)
    if score >= 75:
        return (
            "시장 추세와 위험선호가 충분히 확인된 구간입니다.<br>"
            "그래도 아무 종목이나 매수하지 않고, 주도 테마이면서 종목점수 75점 이상인 "
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
        "SPY·QQQ의 20·50일선 회복과 시장점수 50점 이상을 확인한 뒤 다시 매수 심사를 시작합니다."
    )


def _relative_strength_guide(value) -> tuple[str, str]:
    if value is None:
        return "판단 불가", "상대강도 자료가 부족합니다."
    value = float(value)
    if value >= 10:
        level = "매우 강함"
    elif value >= 5:
        level = "강함"
    elif value >= 0:
        level = "시장 대비 우위"
    elif value >= -5:
        level = "시장 대비 약세"
    else:
        level = "매우 약함"
    meaning = f"최근 20거래일 동안 해당 테마 ETF가 SPY보다 {abs(value):.1f}%p {'더 올랐거나 덜 내렸습니다' if value >= 0 else '뒤처졌습니다'}."
    return level, meaning


def _reference_plan(metrics: dict):
    """확정 셋업 전 종목의 '조건 도달 기준' 참고 가격을 계산한다.

    돌파 조건(52주 고가 −2%)과 눌림목 조건(20일선) 중 현재가에 가까운 쪽을 기준가로 본다.
    실제 매수 판정(state·recommendation)은 바꾸지 않는다.
    """
    current = metrics.get("current")
    if not current:
        return None, None, None, None
    current = float(current)
    high52, sma20, atr = metrics.get("high52"), metrics.get("sma20"), metrics.get("atr")
    candidates = []
    if high52:
        candidates.append(float(high52) * 0.98)
    if sma20:
        candidates.append(float(sma20))
    if not candidates:
        return None, None, None, None
    trigger = min(candidates, key=lambda price: abs(price - current))
    invalidation = current - max((float(atr) if atr else current * 0.03) * 2, current * 0.03)
    zone_high = trigger * 1.007
    target = trigger + 2 * (trigger - invalidation)
    return trigger, zone_high, invalidation, target


def _leader_chart_payload(value):
    """대장주 비교 차트 자료를 payload 형식으로 통일한다.

    온라인에서 jarvis3_data 모듈이 옛 버전으로 캐시되면 DataFrame이 올 수 있어
    (payload dict / DataFrame) 두 형식을 모두 받아들인다.
    """
    if isinstance(value, dict):
        return value if value.get("ok") else None
    columns = getattr(value, "columns", None)
    if value is None or columns is None or getattr(value, "empty", True) or "Close" not in columns:
        return None
    frame = value.copy()
    if "MA20" not in frame.columns:
        frame["MA20"] = frame["Close"].rolling(20).mean()
    if "MA50" not in frame.columns:
        frame["MA50"] = frame["Close"].rolling(50).mean()
    return {"ok": True, "price": frame[["Close", "MA20", "MA50"]], "volume": None, "stale": False}


def _leader_table_html(leaders: list[dict], selected_ticker: str | None) -> str:
    """대장주 1~6위를 HTML 표로 그린다(가운데 정렬, 당일·52주·20일 +파랑/−빨강)."""
    rank_mark = {1: "🟡 1위", 2: "⚪ 2위", 3: "🟠 3위"}
    body = []
    for leader in leaders[:6]:
        metrics, plan = leader["metrics"], leader["plan"]
        rank = int(leader["rank"])
        ticker = leader["ticker"]
        score = float(leader["score"])
        highlight = " j3-th-selected" if ticker == selected_ticker else ""
        score_bar = (
            "<div class='j3-barwrap'><div class='j3-bar'>"
            f"<div class='j3-bar-fill' style='width:{min(score, 100):.0f}%'></div></div>"
            f"<span class='j3-bar-num'>{score:.1f}</span></div>"
        )
        change, from_high, ret20 = metrics.get("change_pct"), metrics.get("from_high_pct"), metrics.get("ret20")
        detail = "상세 분석 대상" if rank <= 3 else "예비 관찰"
        body.append(
            f"<tr class='j3-th-row{highlight}'>"
            f"<td>{rank_mark.get(rank, f'{rank}위')}</td>"
            f"<td class='j3-th-name'>{leader['name']}</td>"
            f"<td>{ticker}</td>"
            f"<td>{score_bar}</td>"
            f"<td style='color:{_sign_color(change)}; font-weight:700'>{_pct(change)}</td>"
            f"<td style='color:{_sign_color(from_high)}; font-weight:700'>{_pct(from_high)}</td>"
            f"<td style='color:{_sign_color(ret20)}; font-weight:700'>{_pct(ret20)}</td>"
            f"<td>{plan.get('state', '')}</td>"
            f"<td class='j3-th-muted'>{detail}</td></tr>"
        )
    return (
        "<table class='j3-theme-table'><colgroup>"
        "<col style='width:9%'><col style='width:18%'><col style='width:8%'>"
        "<col style='width:17%'><col style='width:9%'><col style='width:11%'>"
        "<col style='width:11%'><col style='width:9%'><col style='width:8%'></colgroup>"
        "<thead><tr><th>순위</th><th class='j3-th-left'>종목</th><th>티커</th>"
        "<th>조건점수</th><th>당일</th><th>52주 고가 대비</th><th>20일 수익률</th>"
        "<th>매수 상태</th><th>상세 연결</th></tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table>"
    )


def _price_chart(payload: dict, timeframe: str, include_volume: bool = False, height: int | None = None):
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
                "구분:N",
                title=None,
                scale=alt.Scale(
                    domain=["주가", "20일선", "50일선"],
                    range=["#69bff8", "#ff4d4f", "#a855f7"],
                ),
                legend=alt.Legend(orient="top", direction="horizontal"),
            ),
            tooltip=[alt.Tooltip("날짜:T", title="날짜"), alt.Tooltip("구분:N"), alt.Tooltip("가격:Q", format=",.2f")],
        )
        .properties(height=line_height)
    )
    volume = payload.get("volume")
    if not include_volume or volume is None or volume.empty:
        return line
    volume_frame = volume.reset_index()
    volume_date_column = volume_frame.columns[0]
    volume_frame = volume_frame.rename(columns={volume_date_column: "날짜", "Volume": "거래량"})
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


def _render_day_price_row(metrics: dict) -> None:
    """당일 가격 한 줄 — 현재가·전일 종가·시가·고가·저가·종가(자비스4와 같은 칸).

    2026-07-24 사용자 요청. 고가·저가 옆 백분율은 전일 종가 대비이며
    미국시장 색 규칙(+파랑 −빨강)을 쓴다.
    """
    prev_close = metrics.get("prev_close")
    current = metrics.get("current")
    day_open = metrics.get("day_open")
    day_high = metrics.get("day_high")
    day_low = metrics.get("day_low")
    day_close = metrics.get("day_close")
    phase = (j3data.market_phase() or {}).get("label", "")
    intraday = phase in ("정규장 시간", "프리마켓", "애프터마켓")

    def _vs_prev(value):
        if value is None or not prev_close:
            return None
        return (float(value) / float(prev_close) - 1) * 100

    def _cell(label, value, change, *, sub_text=None, value_color=None):
        if value_color:
            color = value_color
        elif change is not None:
            color = _sign_color(change)
        else:
            color = "#e6e6e6"
        if change is not None:
            sub = f"<div class='j3-mc-sub' style='color:{_sign_color(change)}'>{_pct(change)}</div>"
        elif sub_text:
            sub = f"<div class='j3-mc-sub j3-muted'>{sub_text}</div>"
        else:
            sub = ""
        return (
            f"<div class='j3-mc'><div class='j3-mc-label'>{label}</div>"
            f"<div class='j3-mc-val' style='color:{color}'>{_price(value)}</div>{sub}</div>"
        )

    note = (
        "장중이라 고가·저가·종가는 지금까지의 값입니다"
        if metrics.get("day_is_today")
        else "오늘 일봉이 아직 없어 마지막 거래일 값입니다"
    )
    st.markdown(
        "<div class='j3-chart-heading'>당일 가격 · 시가/고가/저가 한눈에 보기</div>",
        unsafe_allow_html=True,
    )
    st.caption(f"고가·저가 옆 백분율은 전일 종가 대비입니다. {note}.")
    cells = [
        _cell("현재가", current, metrics.get("change_pct")),
        _cell("전일 종가", prev_close, None, sub_text="어제 마감", value_color="#e6e6e6"),
        _cell("당일 시가", day_open, _vs_prev(day_open)),
        _cell("당일 고가", day_high, _vs_prev(day_high)),
        _cell("당일 저가", day_low, _vs_prev(day_low)),
        _cell(
            "당일 종가(장중)" if intraday else "당일 종가",
            current if intraday else day_close,
            _vs_prev(current if intraday else day_close),
        ),
    ]
    st.markdown(f"<div class='j3-metric-row'>{''.join(cells)}</div>", unsafe_allow_html=True)


def _render_price_chart_bundle(ticker: str) -> None:
    """선택 종목의 일봉·주봉·월봉을 한 번의 10년 일봉 조회로 그린다."""
    st.markdown(
        "<div class='j3-chart-heading'>가격 차트 · 일봉/주봉/월봉 한눈에 보기</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "주가 흐름은 하늘색 · 20일선은 붉은색 · 50일선은 보라색입니다. "
        "일봉 거래량은 일봉 바로 아래에 표시됩니다."
    )
    chart_bundle = j3data.get_chart_bundle(ticker)
    if not chart_bundle.get("ok"):
        st.warning(f"차트 조회 실패: {_safe_error_text(chart_bundle.get('error'))}")
        return
    daily_col, weekly_col, monthly_col = st.columns(3)
    chart_columns = {"일봉": daily_col, "주봉": weekly_col, "월봉": monthly_col}
    for timeframe, chart_column in chart_columns.items():
        payload = chart_bundle["charts"].get(timeframe, {})
        with chart_column:
            st.markdown(f"<div class='j3-chart-title'>{timeframe}</div>", unsafe_allow_html=True)
            if payload.get("ok"):
                st.altair_chart(
                    _price_chart(payload, timeframe, include_volume=timeframe == "일봉"),
                    width="stretch",
                    theme="streamlit",
                )
            else:
                st.warning(f"{timeframe} 자료 없음")
    if chart_bundle.get("stale"):
        st.warning("온라인 재조회가 실패해 마지막 정상 차트 자료를 표시하고 있습니다.")


def _intraday_chart(payload: dict, height: int = 200):
    """당일 1분봉 흐름 차트 — 자비스1 코스피/코스닥 당일 차트와 같은 단순 라인.

    전일 종가는 회색 점선 기준선으로 그리고, 선 색은 전일 종가 대비
    상승이면 파랑·하락이면 빨강(미국장 색 규칙)으로 칠한다.
    """
    frame = payload["price"].reset_index()
    frame.columns = ["시각", "가격"]
    prev_close = payload.get("prev_close")
    last_price = float(frame["가격"].iloc[-1])
    if prev_close:
        line_color = "#4da6ff" if last_price >= float(prev_close) else "#ff5b5b"
    else:
        line_color = "#69bff8"
    line = (
        alt.Chart(frame)
        .mark_line(strokeWidth=2, color=line_color)
        .encode(
            x=alt.X("시각:T", title=None, axis=alt.Axis(format="%H:%M", labelAngle=0, tickCount=5)),
            y=alt.Y("가격:Q", title=None, scale=alt.Scale(zero=False), axis=alt.Axis(tickCount=5)),
            tooltip=[
                alt.Tooltip("시각:T", title="시각(뉴욕)", format="%H:%M"),
                alt.Tooltip("가격:Q", format=",.2f"),
            ],
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


@st.fragment(run_every=60)
def _render_market_overview() -> None:
    """시장판단은 페이지 최상단에서 1분마다 독립 갱신한다."""
    overview = j3data.get_market_overview()
    st.session_state["j3_market_overview"] = overview
    st.subheader("미국 전체시장 판단")
    if not overview.get("ok"):
        st.error(f"시장 자료 조회 실패: {_safe_error_text(overview.get('error'))}")
        st.caption("네트워크가 복구되면 1분 자동 갱신에서 다시 시도합니다.")
        return

    phase = overview.get("phase", {}).get("label", "—")
    if phase == "정규장 시간":
        phase_color = "#44f0a1"
    elif phase in ("프리마켓", "애프터마켓"):
        phase_color = "#ff9d3b"
    else:
        phase_color = "#ff5b5b"
    spy_row, qqq_row = overview["rows"]["SPY"], overview["rows"]["QQQ"]
    vix_row = overview["rows"].get("^VIX", {})
    vix_value = vix_row.get("current")
    vix_change = vix_row.get("change_pct")
    # VIX는 '현재 수준(18.70)'과 '전일 대비 변동률(+12.38%)'이 서로 다른 값이다.
    # 아래 선행신호 카드가 변동률만 보여줘 혼동이 생긴다는 지적(2026-07-24)에 따라
    # 여기서 두 값을 한 줄에 같이 보여준다. VIX는 오르면 위험이라 색을 뒤집는다.
    vix_sub = (
        f"VIX {_number(vix_value, 2)} "
        f"<span style='color:{_sign_color(None if vix_change is None else -float(vix_change))}'>"
        f"{_pct(vix_change)}</span>"
    )
    top_cells = [
        # 시장 국면도 공포·탐욕과 같은 반원 게이지로 통일한다 — 국면 이름만 크게
        # 적으면 '방어 우선'이 25점인지 49점인지 알 수 없다(2026-07-24 사용자 지시).
        regime_gauge_ui.regime_box_html(overview),
        _top_metric("SPY", _price(spy_row.get("current")), "#e6e6e6", spy_row.get("change_pct"), sub_signed=True),
        _top_metric("QQQ", _price(qqq_row.get("current")), "#e6e6e6", qqq_row.get("change_pct"), sub_signed=True),
        _top_metric("시장 상황", phase, phase_color, vix_sub, sub_color="#ff5b5b"),
        _fear_greed_box(),
    ]
    # 게이지 스타일은 지표 줄과 따로 내보낸다. 줄 안에 <style>을 끼워 넣으면
    # 스트림릿 마크다운이 그 덩어리를 HTML로 안 보고 글로 흘려버려서, CSS가 글자로
    # 찍히고 SPY·QQQ의 '$' 두 개가 수식으로 잡혔다(2026-07-24 실제 깨짐).
    st.markdown(f"<style>{fear_greed_ui.CSS}</style>", unsafe_allow_html=True)
    st.markdown(f"<div class='j3-top-row'>{''.join(top_cells)}</div>", unsafe_allow_html=True)
    _render_us_index_row(overview, phase)
    st.markdown(
        f"""
        <div class="j3-score-guide">
            조건점수 {overview['score']}/100은 상승장 확인 조건에서 얻은 점수이며 승률이 아닙니다.<br>
            0~49점 방어 우선 · 50~74점 중립·선별 · 75~100점 상승 우위<br>
            {_market_score_detail(overview)}<br>
            시장 상황은 미국 세션 단계입니다(뉴욕시각 기준): 프리마켓 04:00~09:30 → 정규장 09:30~16:00
            → 애프터마켓 16:00~20:00 → 장 마감<br>
            VIX 두 값은 서로 다른 것입니다 — 위 <b>VIX 18.70 같은 숫자는 공포지수 현재 수준</b>(25 미만이면
            과열 아님)이고, 아래 선행신호 카드의 <b>VIX +12.38% 같은 값은 전일 종가 대비 변동률</b>입니다.
            수준은 낮은데 하루 변동만 큰 날이 있어 두 값이 함께 있어도 모순이 아닙니다.<br>
            공포·탐욕 지수는 CNN이 7개 심리 지표로 집계한 값(0 극단적 공포 ~ 100 극단적 탐욕)으로
            참고용이며 점수·판정에는 반영하지 않습니다.
        </div>
        <div class="j3-market-flow">
            <span class="j3-flow-label">시장 전체 흐름</span> : <span class="j3-flow-body">{_market_flow_text(overview)}</span>
        </div>
        <div class="j3-action-box">
            <span class="j3-action-label">행동 기준</span> : <span class="j3-action-posture">{overview['posture']}</span><br>
            <span class="j3-action-detail">{_market_action_detail(overview)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    stale_text = " · 마지막 정상 자료 표시 중" if overview.get("stale") else ""
    st.caption(
        f"최근 가용 시세: {overview.get('checked_at') or '시각 확인 불가'}{stale_text} · "
        "1분 자동 갱신 · 거래소 정식 실시간 피드가 아니므로 지연될 수 있음"
    )


def _render_us_index_row(overview: dict, phase: str) -> None:
    """4대 지수 줄 — S&P 500 · 나스닥 종합 · 다우존스 · 나스닥 100 (2026-07-24 추가).

    ETF(SPY·QQQ)가 아니라 지수를 그대로 쓴다. 정규장이 아니면 마지막으로 끝난
    정규장의 종가와 등락을 보여준다 — 지수는 시간외 거래가 없어서 '지금 값'을
    쓰면 등락이 0%로 나온다.
    """
    display = getattr(j3data, "US_INDEX_DISPLAY", ())
    if not display:
        return
    live = phase == "정규장 시간"
    rows = overview.get("rows") or {}
    cells = []
    for symbol, name in display:
        row = rows.get(symbol) or {}
        if not row.get("ok"):
            cells.append(_top_metric(name, "—", "#9aa0aa", "자료 부족"))
            continue
        change = row.get("change_pct") if live else row.get("last_session_change_pct")
        note = "정규장" if live else "장 마감 기준"
        cells.append(
            f"<div class='j3-top-cell'><div class='j3-top-label'>{name}</div>"
            f"<div class='j3-top-val' style='color:#e6e6e6'>{_number(row.get('current'), 2)}</div>"
            f"<div class='j3-top-sub {_sign_class(change)}'>{_pct(change)} "
            f"<span class='j3-muted'>· {note}</span></div></div>"
        )
    st.markdown(f"<div class='j3-top-row'>{''.join(cells)}</div>", unsafe_allow_html=True)


def _fear_greed_box() -> str:
    """상단 줄에 들어가는 공포·탐욕 게이지 박스. CNN 그림을 직접 그린 것이다.

    스타일도 함께 실어 보낸다 — 페이지 맨 위 <style> 덩어리는 로그인 문 앞이라
    fear_greed_ui를 아직 import하기 전이다.
    """
    fetcher = getattr(j3data, "get_fear_greed", None)
    data = fetcher() if fetcher else {"ok": False}
    return fear_greed_ui.box_html(data)


@st.fragment(run_every=60)
def _render_selected_live_quote(stock_score=None, entry_state=None) -> None:
    ticker = st.session_state.get("j3_selected_ticker")
    if not ticker:
        return
    quote = j3data.get_live_quote(ticker)
    st.session_state["j3_selected_live_quote"] = quote
    if not quote.get("ok"):
        st.warning(f"{ticker} 실시간 시세 갱신 실패: {_safe_error_text(quote.get('error'))}")
        return
    # 최근가·52주대비·20일수익률·14일변동성·종목조건점수를 한 줄에 표시한다.
    # 라벨은 코발트, 증감 부호는 미국장 색(+파랑/−빨강), 종목조건점수는 우측 끝.
    score_val = f"{float(stock_score):.1f}/100" if stock_score is not None else "—"
    state_sub = f"<div class='j3-mc-sub j3-muted'>{entry_state}</div>" if entry_state else ""
    change_sub = f"<div class='j3-mc-sub {_sign_class(quote.get('change_pct'))}'>{_pct(quote.get('change_pct'))}</div>"
    cells = [
        f"<div class='j3-mc'><div class='j3-mc-label'>최근가</div>"
        f"<div class='j3-mc-val'>{_price(quote.get('current'))}</div>{change_sub}</div>",
        f"<div class='j3-mc'><div class='j3-mc-label'>52주 신고가 대비</div>"
        f"<div class='j3-mc-val {_sign_class(quote.get('from_high_pct'))}'>{_pct(quote.get('from_high_pct'))}</div></div>",
        f"<div class='j3-mc'><div class='j3-mc-label'>20일 수익률</div>"
        f"<div class='j3-mc-val {_sign_class(quote.get('ret20'))}'>{_pct(quote.get('ret20'))}</div></div>",
        f"<div class='j3-mc'><div class='j3-mc-label'>14일 변동성(ATR)</div>"
        f"<div class='j3-mc-val {_sign_class(quote.get('atr_pct'))}'>{_pct(quote.get('atr_pct'))}</div></div>",
        f"<div class='j3-mc'><div class='j3-mc-label'>종목 조건점수</div>"
        f"<div class='j3-mc-val j3-green'>{score_val}</div>{state_sub}</div>",
    ]
    st.markdown(f"<div class='j3-metric-row'>{''.join(cells)}</div>", unsafe_allow_html=True)
    stale_text = " · 마지막 정상 자료" if quote.get("stale") else ""
    st.caption(f"시세 기준 {quote.get('source_time') or '—'}{stale_text} · 1분 자동 갱신")


def _load_theme_rankings() -> dict:
    with st.spinner("미국 20개 테마와 구성종목을 조회하는 중입니다…"):
        return j3data.get_theme_rankings()


def _render_leader_comparison(leaders: list[dict]) -> None:
    st.markdown("<div class='j3-section-title'>대장주 1~3위 · 당일/일봉/주봉 비교</div>", unsafe_allow_html=True)
    medal_by_rank = {1: "🥇", 2: "🥈", 3: "🥉"}
    for leader in leaders[:3]:
        metrics, plan = leader["metrics"], leader["plan"]
        rank = int(leader["rank"])
        # 메달은 종합점수 80점 이상인 대장주에만 붙인다.
        medal = medal_by_rank.get(rank, "") if float(leader["score"]) >= 80 else ""
        medal_html = f"<span class='j3-medal'>{medal}</span> " if medal else ""
        with st.container(border=True):
            left, intraday_col, daily_col, weekly_col = st.columns([1.0, 1.15, 1.15, 1.15])
            with left:
                st.markdown(
                    f"<div class='j3-leader-name'>{medal_html}{rank}위 · {leader['name']}</div>",
                    unsafe_allow_html=True,
                )
                st.code(leader["ticker"])
                # 당일 주가와 등락률 — 제목은 '종목 조건점수' 라벨과 같은 크기·색
                # (2026-07-22 사용자 지시).
                change_pct = metrics.get("change_pct")
                st.markdown(
                    "<div class='j3-leader-score-label'>현재가 · 등락률</div>"
                    f"<div class='j3-leader-live'>{_price(metrics.get('current'))} "
                    f"<span class='j3-mc-sub {_sign_class(change_pct)}'>{_pct(change_pct)}</span></div>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    "<div class='j3-leader-score-label'>종목 조건점수</div>"
                    f"<div class='j3-leader-score'>{float(leader['score']):.1f}</div>"
                    f"<div class='j3-leader-state'>{plan.get('state')}</div>",
                    unsafe_allow_html=True,
                )
                st.caption(f"52주 고가 대비 {_pct(metrics.get('from_high_pct'))}")
            with intraday_col:
                st.caption("당일 · 실시간(지연 가능)")
                intraday_payload = leader.get("intraday_chart")
                if isinstance(intraday_payload, dict) and intraday_payload.get("ok"):
                    st.altair_chart(
                        _intraday_chart(intraday_payload, height=210),
                        width="stretch",
                        theme="streamlit",
                    )
                    # 차트 밑에 기준 날짜·시간 표시 (2026-07-22 사용자 지시).
                    st.caption(f"기준 {intraday_payload.get('source_time') or '시각 확인 불가'}")
                else:
                    st.info("당일 자료 없음")
            with daily_col:
                st.caption("일봉 · 최근 60거래일")
                daily_payload = _leader_chart_payload(leader.get("daily_chart"))
                if daily_payload:
                    st.altair_chart(
                        _price_chart(daily_payload, "일봉", include_volume=False, height=210),
                        width="stretch",
                        theme="streamlit",
                    )
                else:
                    st.info("일봉 자료 없음")
            with weekly_col:
                st.caption("주봉 · 최근 52주")
                weekly_payload = _leader_chart_payload(leader.get("weekly_chart"))
                if weekly_payload:
                    st.altair_chart(
                        _price_chart(weekly_payload, "주봉", include_volume=False, height=210),
                        width="stretch",
                        theme="streamlit",
                    )
                else:
                    st.info("주봉 자료 없음")


_MEDAL_BY_RANK = {1: "🥇", 2: "🥈", 3: "🥉"}
# 상태 색은 20개 테마 순위표의 상태색과 같은 규칙(주도 초록·관찰 주황·약함 회색)을 쓴다.
_STATE_COLOR_WORD = {"주도": "green", "관찰": "orange", "약함": "gray"}


def _stock_radio_label(item: dict) -> str:
    """상세 종목 선택 라디오 한 항목의 표시 문구(위·아래 라디오가 같은 형식을 쓴다)."""
    rank = int(item["rank"])
    medal = _MEDAL_BY_RANK.get(rank, "")
    state = item["plan"].get("state", "")
    color_word = _STATE_COLOR_WORD.get(state, "gray")
    return (
        f"{medal} :green[**{rank}위 · {item['name']} ({item['ticker']})**] · "
        f":red[**{item['score']:.1f}점**] · :{color_word}[**{state}**]"
    )


def _render_stock_detail(
    theme_row: dict, leader: dict, market: dict, top_candidates: list[dict], stock_key: str
) -> None:
    ticker = leader["ticker"]
    st.session_state["j3_selected_ticker"] = ticker
    metrics, plan = leader["metrics"], leader["plan"]

    st.divider()
    # 대장주 비교와 동일하게, 80점 이상 1~3위 종목이면 종목명에도 메달을 붙인다.
    detail_rank = int(leader.get("rank") or 0)
    detail_medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(detail_rank, "") if float(leader.get("score") or 0) >= 80 else ""
    detail_medal_html = f"<span class='j3-medal'>{detail_medal}</span> " if detail_medal else ""
    st.markdown(
        f"<div class='j3-stock-name'>{detail_medal_html}{leader['name']} · {ticker}</div>"
        f"<div class='j3-stock-sub'>{theme_row['name']} 대장주 {leader['rank']}위 · {plan.get('recommendation')}</div>",
        unsafe_allow_html=True,
    )

    # 종목조건점수는 위로 빼지 않고 아래 한 줄 지표에 함께 표시한다.
    _render_selected_live_quote(leader.get("score"), plan.get("state"))

    factor_names = ["테마 대비 상대강도", "52주 신고가 위치", "추세", "유동성", "변동성 안정"]
    factor_max = [25, 25, 20, 15, 15]

    def _gain_cell(part, maximum, *, top_border=False):
        # 획득값과 (최대) 모두 붉은색, 사이 한 칸 띄운다. 총점 행은 위에 이중선.
        border = " style='border-top:4px double rgba(255,255,255,0.55)'" if top_border else ""
        return (
            f"<td class='j3-fac-val'{border}>"
            f"<span style='color:#ff5b5b; font-weight:800'>{_number(part)}</span> "
            f"<span style='color:#ff5b5b'>({maximum})</span></td>"
        )

    factor_rows = "".join(
        f"<tr><td class='j3-fac-name'>{name}</td>{_gain_cell(part, maximum)}</tr>"
        for name, part, maximum in zip(factor_names, leader["score_parts"], factor_max)
    )
    # 총점 행: 글자 한 치수 크게 + 배경 밝은 초록
    total_style = (
        "font-weight:800; font-size:1.1rem; background:rgba(134,255,203,0.12); "
        "border-top:4px double rgba(255,255,255,0.55)"
    )
    total_row = (
        f"<tr><td class='j3-fac-name' style='{total_style}'>총점</td>"
        f"<td class='j3-fac-val' style='{total_style}'>"
        f"<span style='color:#ff5b5b; font-weight:800'>{_number(leader.get('score'))}</span> "
        "<span style='color:#ff5b5b'>(100)</span></td></tr>"
    )
    score_col, plan_col = st.columns([1, 1], gap="large")
    with score_col:
        st.markdown("<div class='j3-section-title'>종목 선정 근거</div>", unsafe_allow_html=True)
        st.markdown(
            "<table class='j3-factor-table'><thead><tr>"
            "<th>심사 항목</th><th>획득(최대)</th></tr></thead>"
            f"<tbody>{factor_rows}{total_row}</tbody></table>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div class='j3-reason-mustard'>{leader['stock_reason']}</div>",
            unsafe_allow_html=True,
        )
    with plan_col:
        st.markdown("<div class='j3-section-title'>매수 심사 결과</div>", unsafe_allow_html=True)
        if plan.get("trigger") is not None:
            plan_cells = [
                ("조건 기준가", _price(plan.get("trigger")), "#e6e6e6"),
                ("매수 허용 상단", _price(plan.get("zone_high")), "#e6e6e6"),
                ("무효화 가격", _price(plan.get("invalidation")), "#ff5b5b"),
                ("2R 목표 참고", _price(plan.get("target")), "#44f0a1"),
            ]
        else:
            # 확정 셋업 전(관찰·제외·추격금지)에는 조건 도달 기준의 참고 가격을 채워 보여준다.
            ref_trigger, ref_zone_high, ref_invalidation, ref_target = _reference_plan(metrics)
            plan_cells = [
                ("조건 기준가 (참고)", _price(ref_trigger), "#e6e6e6"),
                ("매수 허용 상단 (참고)", _price(ref_zone_high), "#e6e6e6"),
                ("무효화 가격 (참고)", _price(ref_invalidation), "#ff5b5b"),
                ("2R 목표 (참고)", _price(ref_target), "#44f0a1"),
            ]
        plan_boxes = [
            f"<div class='j3-holo-cell'><div class='label'>{label}</div>"
            f"<div class='val' style='color:{color}'>{value}</div></div>"
            for label, value, color in plan_cells
        ]
        # 3열 배치: [기준가][허용상단][종목 조건점수] / [무효화][2R 목표][빈칸]
        score_box = (
            "<div class='j3-holo-cell j3-holo-score'>"
            "<div class='label'>종목 조건점수</div>"
            f"<div class='val'>{float(leader.get('score') or 0):.1f}/100</div>"
            f"<div class='state'>{plan.get('state', '')}</div></div>"
        )
        plan_grid = (
            plan_boxes[0] + plan_boxes[1] + score_box
            + plan_boxes[2] + plan_boxes[3] + "<div class='j3-holo-cell'></div>"
        )
        st.markdown(
            "<div class='j3-holo-card'>"
            "<span class='j3-holo-corner tl'></span><span class='j3-holo-corner tr'></span>"
            "<span class='j3-holo-corner bl'></span><span class='j3-holo-corner br'></span>"
            f"<div class='j3-holo-grid'>{plan_grid}</div></div>",
            unsafe_allow_html=True,
        )
        # 가격이 '—'인 이유와 함께, 어느 가격이 되면 조건이 성립하는지 참고가를 보여준다.
        if plan.get("trigger") is None:
            hints = []
            high52, sma20 = metrics.get("high52"), metrics.get("sma20")
            if high52:
                hints.append(f"돌파 조건 도달가 <b>{_price(float(high52) * 0.98)}</b> (52주 고가 −2% 지점)")
            if sma20:
                hints.append(f"눌림목 조건 도달가 <b>{_price(sma20)}</b> (20일선)")
            hint_text = f"참고 — {' · '.join(hints)}. " if hints else ""
            # st.caption은 '$'를 LaTeX 수식으로 해석해 글자가 깨지므로 HTML로 그린다.
            st.markdown(
                f"<div class='j3-plan-note'>※ 지금은 ‘{plan.get('state')}’ 상태라 확정 기준가·목표가가 "
                f"아직 없습니다. {hint_text}이 조건이 실제로 충족되면 위 칸에 매수 가격이 표시됩니다.</div>",
                unsafe_allow_html=True,
            )
        st.write("")
        if plan.get("recommendation") == "조건부 후보":
            st.success(plan.get("buy_reason"))
        elif plan.get("state") == "추격 금지":
            st.error(plan.get("buy_reason"))
        else:
            st.warning(plan.get("buy_reason"))

    # 위 '테마 내 종합' 박스와 한 줄 더 띄운 뒤 당일 가격·차트 섹션을 시작한다.
    _render_day_price_row(metrics)
    _render_price_chart_bundle(ticker)

    st.markdown("<div class='j3-section-title'>추천 근거 요약</div>", unsafe_allow_html=True)
    reason_cards = [
        ("시장 근거", f"{market.get('regime', '자료부족')} · {market.get('score', 0)}/100"),
        ("테마 근거", theme_row.get("basis", "자료부족")),
        ("종목 근거", leader["stock_reason"]),
        ("매수 근거", plan.get("buy_reason", "자료부족")),
    ]
    for column, (title, body) in zip(st.columns(4), reason_cards):
        column.markdown(
            f"<div class='j3-reason-card'><div class='j3-reason-title'>{title}</div>"
            f"<div class='j3-reason-body'>{body}</div></div>",
            unsafe_allow_html=True,
        )

    _render_buy_form(theme_row, leader, market, top_candidates, stock_key)



def _render_buy_form(
    theme_row: dict, leader: dict, market: dict, top_candidates: list[dict], stock_key: str
) -> None:
    ticker = leader["ticker"]
    metrics, plan = leader["metrics"], leader["plan"]
    # 위 '추천 근거 요약' 카드와 붙어 보이지 않게 한 줄 띄운다(2026-07-22 사용자 지시).
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)

    # 상세 종목 선택(복제)은 네모칸 밖, '실제 매수 기록' 제목 위에 둔다
    # (2026-07-22 사용자 지시). 여기서 골라도 위 상세 전체가 같이 바뀐다.
    ticker_options = [item["ticker"] for item in top_candidates]
    by_ticker = {item["ticker"]: item for item in top_candidates}
    mirror_key = f"{stock_key}_form"

    def _apply_form_stock_change():
        # 아래 라디오에서 고른 종목을 위 라디오(진짜 선택 상태)에 반영한다.
        st.session_state[stock_key] = st.session_state[mirror_key]

    if st.session_state.get(mirror_key) != ticker or st.session_state.get(mirror_key) not in ticker_options:
        st.session_state[mirror_key] = ticker
    st.radio(
        "상세 종목 선택",
        ticker_options,
        format_func=lambda value: _stock_radio_label(by_ticker[value]) if value in by_ticker else value,
        horizontal=True,
        key=mirror_key,
        on_change=_apply_form_stock_change,
    )

    # 제목 옆에서 그동안 저장한 매수 기록 현황을 바로 펼쳐볼 수 있게 한다
    # (2026-07-22 사용자 지시 — 저장 폼과 현황이 함께 있어야 한다).
    title_col, status_col = st.columns([0.28, 1.72])
    with title_col:
        st.markdown("#### 실제 매수 기록")
    with status_col:
        try:
            progress = j3store.trade_progress()
            summary = (
                f"보유 {progress['open_count']}건 · 청산 {progress['closed_count']}/"
                f"{progress['minimum_sample']}건 · 전체 {progress['total_count']}건"
            )
        except Exception:
            summary = None
        expander_label = f"📋 매수 기록 현황 보기 — {summary}" if summary else "📋 매수 기록 현황 보기"
        with st.expander(expander_label, expanded=False):
            try:
                records = j3store.list_trades(limit=100)
            except Exception as exc:
                st.error(f"기록 조회 실패: {_safe_error_text(exc)}")
                records = []
            if records:
                # 읽기 전용 표였을 때 매도일·매도가를 눌러도 안 된다는 지적(2026-07-22)
                # → 여기서도 같은 클릭 입력형 표를 쓴다.
                _render_records_editor(records, key_prefix="form")
            else:
                st.caption("아직 저장된 매수 기록이 없습니다.")
    st.caption("실제로 매수한 경우에만 저장합니다. 저장 시 당시 시장·테마·종목 조건도 함께 보존됩니다.")
    # 화면이 길어 여기까지 내려오면 어느 종목인지 헷갈린다는 지적(2026-07-22)에 따라,
    # 네모칸 안 맨 위에 종목 이름·지표 헤더를 그대로 한 번 더 넣는다(위쪽 원본 유지).
    with st.container(border=True):
        form_rank = int(leader.get("rank") or 0)
        form_medal = _MEDAL_BY_RANK.get(form_rank, "") if float(leader.get("score") or 0) >= 80 else ""
        form_medal_html = f"<span class='j3-medal'>{form_medal}</span> " if form_medal else ""
        st.markdown(
            f"<div class='j3-stock-name'>{form_medal_html}{leader['name']} · {ticker}</div>"
            f"<div class='j3-stock-sub'>{theme_row['name']} 대장주 {leader['rank']}위 · {plan.get('recommendation')}</div>",
            unsafe_allow_html=True,
        )
        _render_selected_live_quote(leader.get("score"), plan.get("state"))
        _render_buy_form_fields(theme_row, leader, market)


def _render_buy_form_fields(theme_row: dict, leader: dict, market: dict) -> None:
    ticker = leader["ticker"]
    metrics, plan = leader["metrics"], leader["plan"]
    with st.form(f"j3_buy_form_{ticker}", clear_on_submit=False, border=False):
        c1, c2, c3, c4 = st.columns(4)
        buy_date = c1.date_input("매수일", value=date.today(), key=f"j3_buy_date_{ticker}")
        default_price = float(metrics.get("current") or 0.01)
        buy_price = c2.number_input(
            "실제 매수가(USD)", min_value=0.01, value=round(default_price, 2), step=0.01,
            key=f"j3_buy_price_{ticker}",
        )
        quantity = c3.number_input(
            "수량(선택)", min_value=0.0, value=0.0, step=1.0, key=f"j3_buy_qty_{ticker}",
        )
        trade_style = c4.selectbox(
            "매매유형", ["스윙", "단타", "중장기"], key=f"j3_trade_style_{ticker}",
        )
        memo = st.text_area("매수 이유·메모", key=f"j3_buy_memo_{ticker}", height=80)
        confirmed = st.checkbox(
            "실제 체결된 매수임을 확인합니다",
            key=f"j3_buy_confirm_{ticker}",
        )
        submitted = st.form_submit_button("매수 기록 저장", width="stretch")

    if submitted:
        if not confirmed:
            st.error("실제 체결 확인을 체크해야 저장할 수 있습니다.")
            return
        snapshot = {
            "captured_at": theme_row.get("source_time") or market.get("checked_at"),
            "market": {"regime": market.get("regime"), "score": market.get("score")},
            "theme": {
                "name": theme_row.get("name"), "etf": theme_row.get("etf"),
                "score": theme_row.get("score"), "rank": theme_row.get("rank"),
                "rs20": theme_row.get("rs20"), "breadth": theme_row.get("breadth"),
            },
            "stock": {
                "ticker": ticker, "rank": leader.get("rank"), "score": leader.get("score"),
                "current": metrics.get("current"), "from_high_pct": metrics.get("from_high_pct"),
                "ret20": metrics.get("ret20"), "atr_pct": metrics.get("atr_pct"),
            },
        }
        try:
            j3store.save_trade(
                ticker=ticker,
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
                entry_plan=plan,
                snapshot=snapshot,
                memo=memo,
            )
            st.success(f"{leader['name']} · {buy_date.isoformat()} · ${buy_price:,.2f} 매수 기록을 저장했습니다.")
        except Exception as exc:
            st.error(f"매수 기록 저장 실패: {_safe_error_text(exc)}")


def _render_radar_tab(market: dict) -> None:
    action_col, note_col = st.columns([1, 4])
    with action_col:
        if st.button("온라인 자료 새로고침", key="j3_force_refresh", width="stretch"):
            j3data.clear_runtime_cache()
            st.rerun()
    with note_col:
        st.caption("테마 순위는 5분 캐시, 선택 종목 최근가는 1분 자동 갱신됩니다.")

    ranking = _load_theme_rankings()
    if not ranking.get("ok"):
        st.error(f"테마 자료 조회 실패: {_safe_error_text(ranking.get('error'))}")
        return
    st.session_state["j3_theme_rankings"] = ranking
    if ranking.get("stale"):
        st.warning("온라인 재조회 실패로 마지막 정상 테마 자료를 표시하고 있습니다.")

    st.markdown("### 20개 테마 실시간 순위")
    st.caption("표에서 테마 이름을 클릭하면 대장주·상세가 그 테마로 연결됩니다.")
    names = [row["name"] for row in ranking["rows"] if row.get("ok")]
    clicked_theme = _render_theme_table(ranking, st.session_state.get("j3_theme_choice"))
    if clicked_theme in names:
        st.session_state["j3_theme_choice"] = clicked_theme
        st.session_state["j3_theme_choice_widget"] = clicked_theme
    st.caption(
        f"테마 계산 시각: {ranking.get('checked_at') or '—'} · ETF 상대강도와 구성종목 추세를 합산 · "
        "미국 휴장일에는 마지막 거래일 자료"
    )
    if st.session_state.get("j3_theme_choice_widget") not in names:
        preferred_theme = st.session_state.get("j3_theme_choice")
        st.session_state["j3_theme_choice_widget"] = preferred_theme if preferred_theme in names else names[0]
    # st.pills는 이 환경에서 클릭이 먹지 않아 검증된 radio로 교체한다(선택 동작만 교체).
    selected_theme = st.radio(
        "테마 선택",
        names,
        horizontal=True,
        key="j3_theme_choice_widget",
    )
    st.session_state["j3_theme_choice"] = selected_theme
    theme_row = next((row for row in ranking["rows"] if row["name"] == selected_theme), None)
    if theme_row is None:
        st.warning("선택한 테마 자료를 찾지 못했습니다. 다른 테마를 선택하세요.")
        return
    rs_level, rs_meaning = _relative_strength_guide(theme_row.get("rs20"))
    if theme_row.get("rs60") is not None and theme_row.get("breadth") is not None:
        basis_html = (
            f"<span class='j3-green-strong'>20일 상대강도</span> {theme_row['rs20']:+.1f}%p · "
            f"60일 {theme_row['rs60']:+.1f}%p · 20일선 위 {theme_row['breadth']:.0f}%"
        )
    else:
        basis_html = theme_row.get("basis", "근거 자료 부족")
    # 상태 단어(주도/관찰/약함)는 20개 테마 순위표와 같은 상태색을 쓴다
    # (2026-07-22 사용자 지시: "실시간 순위 상태와 같은 색으로").
    status_hex = _STATUS_HEX.get(theme_row.get("status", ""), "#e6e6e6")
    st.markdown(
        "<div class='j3-theme-box'>"
        f"<span class='j3-green-strong'>{selected_theme}</span> · "
        f"<span style='color:{status_hex}; font-weight:800'>{theme_row['status']}</span> : "
        f"<span class='j3-green'>{theme_row['score']:.1f}/100</span><br>"
        f"{basis_html}<br>"
        f"<span class='j3-green-strong'>20일 상대강도 해석</span> : {rs_level} — {rs_meaning}<br>"
        "<span class='j3-green-strong'>기준</span> : +10%p 이상 매우 강함 · +5–10%p 강함 · "
        "0–5%p 시장 대비 우위 · 음수는 시장 대비 약세"
        "</div>",
        unsafe_allow_html=True,
    )

    with st.spinner(f"{selected_theme} 대장주를 조회하는 중입니다…"):
        leader_result = j3data.get_theme_leaders(
            selected_theme,
            market_score=float(market.get("score") or 0),
            theme_score=float(theme_row.get("score") or 0),
        )
    if not leader_result.get("ok"):
        st.error(f"대장주 조회 실패: {_safe_error_text(leader_result.get('error'))}")
        return
    if leader_result.get("stale"):
        st.warning("일부 종목은 마지막 정상 시세로 계산했습니다.")
    leaders = leader_result["rows"]
    st.markdown(
        f"<div class='j3-section-title'><span class='j3-theme-badge'>{selected_theme}</span> 테마 종목 1–6위</div>",
        unsafe_allow_html=True,
    )
    st.caption("1–3위는 색으로 구분했습니다. 상세 분석은 아래 ‘상세 종목 선택’에서 1~3위를 고르세요.")
    top_candidates = leaders[:3]
    ticker_options = [leader["ticker"] for leader in top_candidates]
    st.markdown(
        _leader_table_html(leaders, st.session_state.get(f"j3_stock_choice_{selected_theme}")),
        unsafe_allow_html=True,
    )

    _render_leader_comparison(leaders)

    stock_key = f"j3_stock_choice_{selected_theme}"
    # 재랭킹으로 이전에 고른 종목이 top3에서 빠지면 st.radio가 예외를 낸다 → 미리 정리한다.
    if stock_key in st.session_state and st.session_state[stock_key] not in ticker_options:
        del st.session_state[stock_key]

    def _stock_label(ticker):
        item = next((cand for cand in top_candidates if cand["ticker"] == ticker), None)
        return _stock_radio_label(item) if item else ticker

    selected_ticker = st.radio(
        "상세 종목 선택",
        ticker_options,
        format_func=_stock_label,
        horizontal=True,
        key=stock_key,
    )
    selected_leader = next(
        (item for item in top_candidates if item["ticker"] == selected_ticker),
        top_candidates[0],
    )
    _render_stock_detail(theme_row, selected_leader, market, top_candidates, stock_key)
    _render_pullback_finder(market, ranking)


def _us_signal_hint() -> str:
    """미국장 선행신호 카드 판정을 단타 참고 문구로 옮긴다(점수에는 반영하지 않는다).

    한국장 자비스4의 ‘기관 수급 반전’ 자리에 들어가는 미국판이다. 미국은 장중
    투자자별 수급 공개 자료가 없어 선물·반도체·변동성·금리 방향을 대신 쓴다.
    """
    result = st.session_state.get("us_signal_result")
    if result is None:
        return "선행신호 판정은 위 ‘미국장 선행신호·시장 상태’ 카드에서 확인하세요."
    return (
        f"미국장 선행신호: <b>{html.escape(str(result.verdict_label))}</b> · "
        f"{html.escape(str(result.headline))}"
    )


def _render_pullback_detail(row: dict, market: dict, ranking: dict) -> None:
    """상단 테마 선택과 독립된 눌림목 종목 상세.

    자비스4(한국) 종목 상세와 같은 구성으로 맞춘다(2026-07-24 사용자 지시) —
    선정 근거 점수표 · 매수 심사 결과 · 일봉/주봉/월봉 차트를 함께 보여준다.
    """
    ticker = str(row.get("ticker") or "")
    metrics = row.get("metrics") or {}
    quality = row.get("pullback") or {}
    themes = " · ".join(row.get("themes") or []) or "테마 정보 없음"
    avg_value = metrics.get("avg_dollar_volume")

    # ── 선정 근거·매수 심사 (자비스4 종목 상세와 같은 구성) ──────────────────
    # 눌림목 검색은 테마를 가로지르므로 상대강도 기준은 SPY 20일 수익률을 쓴다.
    market_score = float(market.get("score") or 0)
    spy_ret20 = ((market.get("rows") or {}).get("SPY") or {}).get("ret20")
    theme_scores = {
        item.get("name"): float(item.get("score") or 0)
        for item in (ranking.get("rows") or [])
        if item.get("ok") and item.get("name")
    }
    own_scores = [theme_scores[name] for name in (row.get("themes") or []) if name in theme_scores]
    theme_score = max(own_scores) if own_scores else 0.0
    review = j3data.analyze_pullback_stock(
        row,
        benchmark_ret20=spy_ret20,
        market_score=market_score,
        theme_score=theme_score,
    )
    plan = review.get("plan") or {}

    # 종목 이름·판정은 자비스4 종목 상세와 같은 형식으로 크게 보여준다.
    st.markdown(
        f"<div class='j3-stock-name'>{html.escape(str(row.get('name') or ticker))} · "
        f"{html.escape(ticker)}</div>"
        f"<div class='j3-stock-sub'>{html.escape(themes)} 눌림목 선택 종목 · "
        f"{html.escape(str(plan.get('recommendation') or '판정 없음'))}</div>",
        unsafe_allow_html=True,
    )
    cells = [
        f"<div class='j3-mc'><div class='j3-mc-label'>현재가</div>"
        f"<div class='j3-mc-val'>{_price(metrics.get('current'))}</div>"
        f"<div class='j3-mc-sub {_sign_class(metrics.get('change_pct'))}'>"
        f"{_pct(metrics.get('change_pct'))}</div></div>",
        f"<div class='j3-mc'><div class='j3-mc-label'>52주 신고가 대비</div>"
        f"<div class='j3-mc-val {_sign_class(metrics.get('from_high_pct'))}'>"
        f"{_pct(metrics.get('from_high_pct'))}</div>"
        f"<div class='j3-mc-sub j3-muted'>{int(quality.get('high52_days_ago') or 0)}일 전 신고가</div></div>",
        f"<div class='j3-mc'><div class='j3-mc-label'>20일 수익률</div>"
        f"<div class='j3-mc-val {_sign_class(metrics.get('ret20'))}'>"
        f"{_pct(metrics.get('ret20'))}</div></div>",
        f"<div class='j3-mc'><div class='j3-mc-label'>14일 변동성(ATR)</div>"
        f"<div class='j3-mc-val j3-up'>{_pct(metrics.get('atr_pct'))}</div></div>",
        f"<div class='j3-mc'><div class='j3-mc-label'>평균 거래대금</div>"
        f"<div class='j3-mc-val j3-green'>"
        f"{f'${float(avg_value) / 1e6:,.0f}M' if avg_value is not None else '—'}</div>"
        "<div class='j3-mc-sub j3-muted'>미국은 장중 수급 공개 없음</div></div>",
        f"<div class='j3-mc'><div class='j3-mc-label'>종목 조건점수</div>"
        f"<div class='j3-mc-val j3-green'>{float(review.get('score') or 0):.1f}/100</div>"
        f"<div class='j3-mc-sub j3-muted'>{html.escape(str(plan.get('state') or ''))}</div></div>",
        f"<div class='j3-mc'><div class='j3-mc-label'>눌림 점수</div>"
        f"<div class='j3-mc-val j3-green'>{float(quality.get('score') or 0):.1f}/100</div>"
        f"<div class='j3-mc-sub {_sign_class(quality.get('gap_pct'))}'>"
        f"20일선 이격 {_pct(quality.get('gap_pct'))}</div></div>",
    ]
    st.markdown(f"<div class='j3-metric-row'>{''.join(cells)}</div>", unsafe_allow_html=True)

    factor_names = ["SPY 대비 상대강도", "52주 신고가 위치", "추세(20·50·200일선)", "유동성(거래대금)", "변동성 안정"]
    factor_max = [25, 25, 20, 15, 15]

    def _fac_cell(part, maximum):
        return (
            "<td class='j3-fac-val'>"
            f"<span style='color:#ff5b5b; font-weight:800'>{_number(part)}</span> "
            f"<span style='color:#ff5b5b'>({maximum})</span></td>"
        )

    factor_rows = "".join(
        f"<tr><td class='j3-fac-name'>{name}</td>{_fac_cell(part, maximum)}</tr>"
        for name, part, maximum in zip(factor_names, review.get("score_parts") or [], factor_max)
    )
    total_style = (
        "font-weight:800; font-size:1.1rem; background:rgba(134,255,203,0.12); "
        "border-top:4px double rgba(255,255,255,0.55)"
    )
    total_row = (
        f"<tr><td class='j3-fac-name' style='{total_style}'>총점</td>"
        f"<td class='j3-fac-val' style='{total_style}'>"
        f"<span style='color:#ff5b5b; font-weight:800'>{_number(review.get('score'))}</span> "
        "<span style='color:#ff5b5b'>(100)</span></td></tr>"
    )
    score_col, plan_col = st.columns([1, 1], gap="large")
    with score_col:
        st.markdown(
            "<div class='j3-section-title'>종목 선정 근거 (미국형 5개 항목)</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<table class='j3-factor-table'><thead><tr>"
            "<th>심사 항목</th><th>획득(최대)</th></tr></thead>"
            f"<tbody>{factor_rows}{total_row}</tbody></table>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div class='j3-reason-mustard'>{html.escape(review.get('stock_reason') or '')}</div>",
            unsafe_allow_html=True,
        )
        st.caption(
            "이 점수는 위 표의 ‘종목 조건점수’와 같은 값이며, 표의 순위를 정하는 ‘눌림 점수’와는 "
            "다른 것을 잽니다 — 눌림 점수는 지금이 눌림 자리로 좋은지, 이 점수는 종목 자체가 "
            "좋은지를 봅니다. 상대강도 기준은 테마 ETF가 아니라 SPY 20일 수익률입니다"
            "(눌림목 검색은 여러 테마를 가로질러 돌기 때문). 그래서 위 테마 대장주 표의 점수와도 "
            "다를 수 있습니다."
        )
    with plan_col:
        st.markdown("<div class='j3-section-title'>매수 심사 결과</div>", unsafe_allow_html=True)
        if plan.get("trigger") is not None:
            plan_cells = [
                ("조건 기준가", _price(plan.get("trigger")), "#e6e6e6"),
                ("매수 허용 상단", _price(plan.get("zone_high")), "#e6e6e6"),
                ("무효화 가격", _price(plan.get("invalidation")), "#ff5b5b"),
                ("2R 목표 참고", _price(plan.get("target")), "#44f0a1"),
            ]
        else:
            ref_trigger, ref_zone_high, ref_invalidation, ref_target = _reference_plan(metrics)
            plan_cells = [
                ("조건 기준가 (참고)", _price(ref_trigger), "#e6e6e6"),
                ("매수 허용 상단 (참고)", _price(ref_zone_high), "#e6e6e6"),
                ("무효화 가격 (참고)", _price(ref_invalidation), "#ff5b5b"),
                ("2R 목표 (참고)", _price(ref_target), "#44f0a1"),
            ]
        plan_boxes = [
            f"<div class='j3-holo-cell'><div class='label'>{label}</div>"
            f"<div class='val' style='color:{color}'>{value}</div></div>"
            for label, value, color in plan_cells
        ]
        score_box = (
            "<div class='j3-holo-cell j3-holo-score'>"
            "<div class='label'>종목 조건점수</div>"
            f"<div class='val'>{float(review.get('score') or 0):.1f}/100</div>"
            f"<div class='state'>{plan.get('state', '')}</div></div>"
        )
        plan_grid = (
            plan_boxes[0] + plan_boxes[1] + score_box
            + plan_boxes[2] + plan_boxes[3] + "<div class='j3-holo-cell'></div>"
        )
        st.markdown(
            "<div class='j3-holo-card'>"
            "<span class='j3-holo-corner tl'></span><span class='j3-holo-corner tr'></span>"
            "<span class='j3-holo-corner bl'></span><span class='j3-holo-corner br'></span>"
            f"<div class='j3-holo-grid'>{plan_grid}</div></div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='j3-plan-note'>※ <b>가격 칸이 채워지는 기준</b> — ‘돌파 확인’이나 ‘눌림목 대기’처럼 "
            "<b>가격 셋업이 완성된 종목만</b> 확정 기준가·손절가·목표가가 나옵니다. "
            "‘관찰’·‘제외’·‘추격 금지’는 아직 살 자리가 없다는 뜻이라 참고가로만 채웁니다.<br>"
            f"※ <b>‘{plan.get('state', '')}’(가격 상태)와 ‘{plan.get('recommendation', '')}’(최종 판정)은 "
            "다른 말</b>입니다 — 가격 셋업이 완성돼도 시장·테마 점수가 기준 미달이면 최종 판정은 매수가 "
            f"아닙니다(이 종목의 테마 점수 {theme_score:.1f}/100 · 시장 {market_score:.0f}/100).</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div class='j3-danta-box'><span class='j3-danta-title'>⚡ 단타 참고 신호</span> — "
            f"{_us_signal_hint()}<br>"
            "<span class='j3-muted'>선행신호가 위험선호로 바뀌고 기준가를 넘으면 장중 진입 신호로 "
            "참고합니다 (점수·판정에는 반영하지 않습니다). 미국은 장중 투자자별 수급 공개 자료가 없어 "
            "한국장의 ‘기관 수급 반전’ 대신 선물·반도체·변동성·금리 방향을 씁니다.</span></div>",
            unsafe_allow_html=True,
        )
        st.write("")
        if plan.get("recommendation") == "조건부 후보":
            st.success(plan.get("buy_reason"))
        elif plan.get("state") == "추격 금지":
            st.error(plan.get("buy_reason"))
        else:
            st.warning(plan.get("buy_reason"))

    st.caption(
        "이 선택은 위의 테마·대장주 선택을 바꾸지 않습니다. 종목 이름을 다시 누르면 "
        "이 상세와 일봉·주봉·월봉 차트만 즉시 교체됩니다."
    )
    _render_day_price_row(metrics)
    _render_price_chart_bundle(ticker)

    st.markdown("<div class='j3-section-title'>추천 근거 요약</div>", unsafe_allow_html=True)
    reason_cards = [
        ("시장 근거", f"{market.get('regime', '자료부족')} · {market.get('score', 0)}/100"),
        ("테마 근거", f"{themes} · 최고 테마 점수 {theme_score:.1f}/100"),
        ("종목 근거", review.get("stock_reason") or "자료부족"),
        ("매수 근거", plan.get("buy_reason", "자료부족")),
    ]
    for column, (title, body) in zip(st.columns(4), reason_cards):
        column.markdown(
            f"<div class='j3-reason-card'><div class='j3-reason-title'>{title}</div>"
            f"<div class='j3-reason-body'>{html.escape(str(body))}</div></div>",
            unsafe_allow_html=True,
        )


def _render_pullback_finder(market: dict, ranking: dict) -> None:
    """20개 미국 테마의 전체 종목에서 상승추세 조정을 찾는다."""
    st.divider()
    st.markdown(
        "<div class='j3-section-title'>📉 눌림목 종목 찾기 (상승추세 중 조정)</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='j3-pull-guide'><b>무엇을 찾나</b> — 50일선·200일선이 살아 있는 상승추세에서, "
        "52주 신고가를 찍은 뒤 1~20거래일 동안 20일선 부근으로 조정받은 종목입니다.<br>"
        "<b>표 읽는 법</b> — ‘고점 대비 <span class='j3-down'>−10%</span>’는 신고가에서 10% "
        "내려왔다는 뜻이고, ‘20일선 이격 0%’에 가까울수록 20일선 근처입니다.<br>"
        "<b>점수 두 개는 서로 다른 것을 잽니다</b> — <b>눌림 점수</b>는 <u>지금이 눌림 자리로 좋은가</u>"
        "(신고가 최근성 25 + 20일선 근접 20 + 추세 20 + 조정 깊이 20 + 거래대금 10 + 테마 가산 5)이고, "
        "<b>종목 조건점수</b>는 <u>종목 자체가 좋은가</u>"
        "(SPY 대비 상대강도 25 + 52주 신고가 위치 25 + 추세 20 + 거래대금 15 + 변동성 안정 15)입니다. "
        "<b>순위는 눌림 점수 기준</b>이라, 눌림 자리가 덜 좋아도 종목 자체 점수는 더 높을 수 있습니다 "
        "(예: 20일선에서 멀리 떨어져 있으면 눌림 점수만 크게 깎입니다). "
        "아래 상세의 점수는 이 표의 ‘종목 조건점수’와 같은 값입니다.<br>"
        "<span class='j3-up'>+ 상승은 파랑</span> · <span class='j3-down'>− 하락은 빨강</span> "
        "(미국시장 색 규칙) · 여러 테마 소속은 필수가 아니라 최대 5점 가산</div>",
        unsafe_allow_html=True,
    )
    result = j3data.find_pullback_stocks(reuse_only=True)
    if not result.get("ok"):
        st.error(f"미국 눌림목 조회 실패: {_safe_error_text(result.get('error'))}")
        return
    rows = result.get("rows") or []
    window = result.get("window") or (1, 20)
    reuse_text = "기존 일봉 배치 재사용" if result.get("reused_batch") else "일봉 1회 배치 조회"
    st.markdown(
        "<div class='j3-pull-stats'>"
        f"전체 <b>{result.get('universe_count', 0):,}개</b> → "
        f"일봉 확보 <b>{result.get('data_count', 0):,}개</b> → "
        f"상승추세 <b>{result.get('trend_count', 0):,}개</b> → "
        f"신고가 {window[0]}~{window[1]}일 전 조정 <b>{result.get('window_count', 0):,}개</b> → "
        f"최종 눌림 점수 {float(result.get('min_score') or 0):.0f}점 이상 "
        f"<b class='j3-green'>{len(rows):,}개</b>(최대 {int(result.get('result_limit') or 0)}개) "
        f"· {reuse_text}</div>",
        unsafe_allow_html=True,
    )
    if not rows:
        st.info("현재 조건에 맞는 미국 눌림목 종목이 없습니다.")
        return

    widths = [0.55, 1.7, 0.8, 1.45, 1.2, 1.0, 1.4, 1.1, 1.15, 1.25, 1.8, 0.85]
    titles = [
        "순위", "종목", "티커", "눌림 점수", "종목 조건점수", "신고가", "당일주가", "고점 대비",
        "20일선 이격", "평균 거래대금", "소속 테마", "테마 가산",
    ]
    for column, title in zip(st.columns(widths), titles):
        column.markdown(f"<div class='j3-th-head'>{title}</div>", unsafe_allow_html=True)

    # 표의 '종목 조건점수'는 아래 상세와 같은 계산이어야 한다 — 같은 함수·같은 기준(SPY 20일)을 쓴다.
    spy_ret20_for_table = ((market.get("rows") or {}).get("SPY") or {}).get("ret20")

    # 아무것도 누르지 않았거나 고른 종목이 이번 결과에서 빠졌으면 1순위를 자동으로 연다
    # (2026-07-24 사용자 지시: 클릭하지 않아도 맨 위 종목 상세가 바로 보여야 한다).
    tickers_now = [row.get("ticker") for row in rows]
    selected_ticker = st.session_state.get("j3_pullback_selected_ticker")
    if selected_ticker not in tickers_now:
        selected_ticker = rows[0].get("ticker")
    selected_css = []
    for index, row in enumerate(rows):
        quality = row["pullback"]
        from_high = quality.get("from_high_pct")
        gap = quality.get("gap_pct")
        score = float(quality.get("score") or 0)
        avg_value = row["metrics"].get("avg_dollar_volume")
        theme_bonus = float((quality.get("parts") or [0])[-1])
        themes = " · ".join(row.get("themes") or []) or "—"
        cols = st.columns(widths)
        cols[0].markdown(
            f"<div class='j3-td j3-muted'>{int(row['pullback_rank'])}</div>",
            unsafe_allow_html=True,
        )
        if cols[1].button(
            str(row.get("name") or row.get("ticker") or "—"),
            key=f"j3pbf_{index:02d}",
            width="stretch",
        ):
            st.session_state["j3_pullback_selected_ticker"] = row["ticker"]
            st.rerun()
        if row.get("ticker") == selected_ticker:
            selected_css.append(
                f"div[class*='st-key-j3pbf_{index:02d}'] button "
                "{ background: rgba(192,132,252,.16) !important; "
                "border-left: 3px solid #c084fc !important; }"
            )
        cols[2].markdown(
            f"<div class='j3-td'>{html.escape(str(row.get('ticker') or '—'))}</div>",
            unsafe_allow_html=True,
        )
        cols[3].markdown(
            "<div class='j3-td'><div class='j3-barwrap'><div class='j3-bar'>"
            f"<div class='j3-bar-fill j3-bar-green' style='width:{max(0, min(score, 100)):.0f}%'></div></div>"
            f"<span class='j3-bar-num'>{score:.1f}</span></div></div>",
            unsafe_allow_html=True,
        )
        # 종목 조건점수 — 아래 상세와 같은 값. 순위(눌림 점수)와 다른 것을 재는 점수라
        # 20위가 3위보다 높을 수 있다(2026-07-24 사용자 질문에 따라 표에 함께 표시).
        stock_score = float(
            j3data.analyze_pullback_stock(row, benchmark_ret20=spy_ret20_for_table).get("score") or 0
        )
        cols[4].markdown(
            "<div class='j3-td'><div class='j3-barwrap'><div class='j3-bar'>"
            f"<div class='j3-bar-fill' style='width:{max(0, min(stock_score, 100)):.0f}%; background:#c084fc'></div></div>"
            f"<span class='j3-bar-num'>{stock_score:.1f}</span></div></div>",
            unsafe_allow_html=True,
        )
        cols[5].markdown(
            f"<div class='j3-td j3-green'>{int(quality.get('high52_days_ago') or 0)}일 전</div>",
            unsafe_allow_html=True,
        )
        # 당일주가 — 신고가와 고점 대비 사이에서 '지금 얼마인지'를 바로 보게 한다
        # (2026-07-24 사용자 지시). 등락은 미국장 색 규칙(+파랑 −빨강)으로 진하게.
        current_price = row["metrics"].get("current")
        change_pct = row["metrics"].get("change_pct")
        # 가격과 등락을 두 줄로 쌓는다 — 한 줄이면 좁은 화면(태블릿)에서 폭이 넘쳐
        # 옆 칸 값과 겹쳤다(2026-07-25). 값은 그대로, 배치만 바꾼다.
        cols[6].markdown(
            f"<div class='j3-td' style='font-weight:800; color:#e6e6e6'>"
            f"<span style='display:inline-flex; flex-direction:column; align-items:center; line-height:1.12'>"
            f"<span>{_price(current_price)}</span>"
            f"<span style='color:{_sign_color(change_pct)}; font-weight:800; font-size:.82rem'>"
            f"{_pct(change_pct)}</span></span></div>",
            unsafe_allow_html=True,
        )
        cols[7].markdown(
            f"<div class='j3-td {_sign_class(from_high)}' style='font-weight:800'>{_pct(from_high)}</div>",
            unsafe_allow_html=True,
        )
        cols[8].markdown(
            f"<div class='j3-td {_sign_class(gap)}' style='font-weight:800'>{_pct(gap)}</div>",
            unsafe_allow_html=True,
        )
        avg_text = f"${float(avg_value) / 1e6:,.0f}M" if avg_value is not None else "—"
        cols[9].markdown(
            f"<div class='j3-td j3-green'>{avg_text}</div>",
            unsafe_allow_html=True,
        )
        cols[10].markdown(
            f"<div class='j3-td j3-pull-theme' title='{html.escape(themes)}'>"
            f"{html.escape(themes)}</div>",
            unsafe_allow_html=True,
        )
        cols[11].markdown(
            f"<div class='j3-td j3-pull-amber'>{theme_bonus:.1f}/5</div>",
            unsafe_allow_html=True,
        )
    if selected_css:
        st.markdown(f"<style>{''.join(selected_css)}</style>", unsafe_allow_html=True)
    st.caption(
        "평균 거래대금은 최근 일봉 기준 달러 거래규모입니다. 이 표는 진입가를 확정하는 매수 신호가 아니라, "
        "상승추세가 아직 유지되는 조정 후보를 좁히는 1차 목록입니다. "
        "아래 상세는 처음에 1순위 종목이 열려 있고, 보라색 종목 이름을 누르면 그 종목의 "
        "선정 근거 점수표·매수 심사 결과와 일봉·주봉·월봉 차트로 바뀝니다."
    )
    selected_row = next(
        (row for row in rows if row.get("ticker") == selected_ticker),
        rows[0],
    )
    _render_pullback_detail(selected_row, market, ranking)


def _render_records_tab() -> None:
    st.subheader("매수 기록 현황")
    try:
        progress = j3store.trade_progress()
        records = j3store.list_trades(limit=300)
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
        st.caption("아직 저장된 자비스3 매수 기록이 없습니다.")
        return

    _render_records_editor(records)


def _records_live_prices(records: list[dict]) -> dict:
    """보유 종목 최근가를 조회한다. 표 편집 중 값이 바뀌면 입력이 초기화될 수 있어
    같은 기록 구성에서는 5분 동안 세션에 고정해 둔다."""
    fingerprint = tuple(sorted((int(r["id"]), str(r.get("status"))) for r in records))
    cache = st.session_state.get("j3_records_pl_cache") or {}
    if cache.get("fp") == fingerprint and time.time() - cache.get("at", 0) < 300:
        return cache["prices"]
    open_tickers = sorted({
        str(record.get("ticker")) for record in records
        if record.get("status") == "보유" and record.get("ticker")
    })[:30]
    prices = {}
    for ticker in open_tickers:
        quote = j3data.get_live_quote(ticker)
        if quote.get("ok") and quote.get("current"):
            prices[ticker] = float(quote["current"])
    st.session_state["j3_records_pl_cache"] = {"fp": fingerprint, "at": time.time(), "prices": prices}
    return prices


def _render_records_editor(records: list[dict], key_prefix: str = "tab") -> None:
    """매수 기록 현황 표 하나에서 바로 청산을 입력한다(2026-07-22 사용자 지시).

    종목 줄의 매도일 칸을 누르면 달력이 뜨고, 매도가 칸에 금액을 넣으면 확정
    손익률이 자동 계산된다(표 아래 미리보기 → 저장 시 확정 칸에 기록).
    매도가는 매수가 ±50% 범위만 허용한다. 제목·내용은 가운데 정렬한다.
    key_prefix로 탭·매수 폼 두 곳에서 각각 독립 위젯으로 쓴다.
    """
    saved_message = st.session_state.pop("j3_close_saved_msg", None)
    if saved_message:
        st.success(saved_message)
    st.caption(
        "보유 종목 줄에서 매도일 칸을 누르면 달력이 뜨고, 매도가(USD) 칸에 금액을 넣으면 "
        "표 아래에 확정 손익률이 자동 계산됩니다. ‘청산 저장’을 눌러야 확정됩니다. "
        "매도가는 매수가 ±50% 범위만 저장됩니다."
    )

    prices = _records_live_prices(records)

    def _pl_text(value):
        # 입력형 표는 글자색 지정이 안 되는 부품이라 색깔 원으로 이익/손실을 표시한다
        # (2026-07-22 사용자 지시: 손익률에 색): 이익 🔵 파랑 · 손실 🔴 빨강.
        if value is None:
            return None
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None
        return f"{'🔵' if value >= 0 else '🔴'} {value:+.2f}%"

    editor_rows = []
    for record in records:
        is_open = record.get("status") == "보유"
        buy_price = float(record["buy_price"]) if record.get("buy_price") is not None else None
        current = prices.get(str(record.get("ticker"))) if is_open else None
        live_pl = (current / buy_price - 1) * 100 if current and buy_price else None
        editor_rows.append({
            "번호": int(record["id"]),
            "매수일": record.get("buy_date"),
            "티커": record.get("ticker"),
            "종목명": record.get("stock_name"),
            "테마": record.get("theme_name"),
            "매매유형": record.get("trade_style"),
            "매수가(USD)": buy_price,
            "수량": record.get("quantity"),
            "상태": record.get("status"),
            "현재 손익률(%)": _pl_text(live_pl),
            "매도일": record.get("sell_date"),
            "매도가(USD)": record.get("sell_price"),
            "확정 손익률(%)": _pl_text(record.get("result_pct")),
            "시장 국면": record.get("market_regime"),
            "시장점수": record.get("market_score"),
            "테마점수": record.get("theme_score"),
            "종목점수": record.get("stock_score"),
            "메모": record.get("memo"),
        })
    frame = pd.DataFrame(editor_rows)
    frame["매도일"] = pd.to_datetime(frame["매도일"])
    for column in ("매수가(USD)", "매도가(USD)", "수량", "시장점수", "테마점수", "종목점수"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    center = {"alignment": "center"}
    column_config = {
        "번호": st.column_config.NumberColumn(format="%d", **center),
        "매수일": st.column_config.TextColumn(**center),
        "티커": st.column_config.TextColumn(**center),
        "종목명": st.column_config.TextColumn(**center),
        "테마": st.column_config.TextColumn(**center),
        "매매유형": st.column_config.TextColumn(**center),
        "매수가(USD)": st.column_config.NumberColumn(format="%.2f", **center),
        "수량": st.column_config.NumberColumn(format="%.0f", **center),
        "상태": st.column_config.TextColumn(**center),
        "현재 손익률(%)": st.column_config.TextColumn(**center),
        "매도일": st.column_config.DateColumn(
            "매도일", format="YYYY-MM-DD", help="보유 종목 칸을 누르면 달력이 뜹니다", **center
        ),
        "매도가(USD)": st.column_config.NumberColumn(
            "매도가(USD)", min_value=0.01, step=0.01, format="%.2f",
            help="매수가 ±50% 범위에서 입력", **center,
        ),
        "확정 손익률(%)": st.column_config.TextColumn(**center),
        "시장 국면": st.column_config.TextColumn(**center),
        "시장점수": st.column_config.NumberColumn(format="%.0f", **center),
        "테마점수": st.column_config.NumberColumn(format="%.0f", **center),
        "종목점수": st.column_config.NumberColumn(format="%.0f", **center),
        "메모": st.column_config.TextColumn(**center),
    }
    editor_key = f"j3_records_editor_{key_prefix}"
    edited = st.data_editor(
        frame,
        column_config=column_config,
        disabled=[col for col in frame.columns if col not in ("매도일", "매도가(USD)")],
        hide_index=True,
        width="stretch",
        key=editor_key,
    )

    # 매도가를 넣는 순간 자동 계산되는 확정 손익률 미리보기(저장 전).
    previews = []
    touched_closed = []
    for index, record in enumerate(records):
        row = edited.iloc[index]
        if record.get("status") != "보유":
            same_price = pd.isna(row["매도가(USD)"]) if record.get("sell_price") is None \
                else (not pd.isna(row["매도가(USD)"]) and float(row["매도가(USD)"]) == float(record["sell_price"]))
            if not same_price:
                touched_closed.append(str(record.get("ticker")))
            continue
        sell_price = row["매도가(USD)"]
        if sell_price is None or pd.isna(sell_price) or not record.get("buy_price"):
            continue
        pl = (float(sell_price) / float(record["buy_price"]) - 1) * 100
        color = "#4da6ff" if pl >= 0 else "#ff5b5b"
        previews.append(
            f"<b>{record['ticker']}</b> 매도가 ${float(sell_price):,.2f} → 확정 손익률 "
            f"<span style='color:{color};font-weight:800'>{pl:+.2f}%</span>"
        )
    if previews:
        st.markdown(
            "<div class='j3-plan-note'>자동계산 미리보기 — " + " · ".join(previews)
            + " <span class='j3-muted'>(청산 저장을 누르면 확정 손익률 칸에 기록됩니다)</span></div>",
            unsafe_allow_html=True,
        )
    if touched_closed:
        st.warning("이미 청산된 기록은 수정되지 않습니다: " + ", ".join(sorted(set(touched_closed))))

    if st.button("청산 저장 (매도일·매도가 입력된 종목만)", key=f"j3_close_editor_save_{key_prefix}", width="stretch"):
        saved_count = 0
        errors = []
        for index, record in enumerate(records):
            if record.get("status") != "보유":
                continue
            row = edited.iloc[index]
            sell_date, sell_price = row["매도일"], row["매도가(USD)"]
            has_date = sell_date is not None and not pd.isna(sell_date)
            has_price = sell_price is not None and not pd.isna(sell_price)
            if not has_date and not has_price:
                continue
            label = f"#{record['id']} {record['ticker']}"
            if not (has_date and has_price):
                errors.append(f"{label}: 매도일과 매도가를 모두 입력해야 저장됩니다")
                continue
            buy_price = float(record["buy_price"])
            if not buy_price * 0.5 <= float(sell_price) <= buy_price * 1.5:
                errors.append(
                    f"{label}: 매도가는 매수가 ±50% 범위"
                    f"({buy_price * 0.5:,.2f} ~ {buy_price * 1.5:,.2f})여야 합니다"
                )
                continue
            try:
                j3store.close_trade(
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
            st.session_state["j3_close_saved_msg"] = f"{saved_count}건 청산을 저장했습니다."
            st.session_state.pop(editor_key, None)
            st.session_state.pop("j3_records_pl_cache", None)
            st.rerun()
        elif saved_count:
            st.success(f"{saved_count}건 청산을 저장했습니다. 위 오류 항목은 저장되지 않았습니다.")


def _render_method_tab() -> None:
    st.subheader("판정 기준과 데이터 정책")
    st.markdown(
        """
        1. **시장 게이트** — SPY·QQQ의 20/50일선, IWM 동행, VIX로 신규 매수 가능 국면을 먼저 판단합니다.
        2. **테마 강도** — ETF의 SPY 대비 20·60일 상대강도, 추세, 구성종목 확산도를 합산합니다.
        3. **대장주 품질** — 테마 대비 상대강도, 52주 신고가 위치, 추세, 유동성, 변동성을 평가합니다.
        4. **매수 타이밍** — 신고가 거래량 돌파 또는 상승추세 내 20일선 눌림만 조건부 후보로 봅니다.
        5. **위험 우선** — 5일 급등과 고변동 종목은 점수가 높아도 추격 금지합니다.
        """
    )
    st.warning(
        "조건점수는 상승확률이 아닙니다. 실제 매수·청산 표본이 30건 이상 쌓인 뒤 "
        "셋업별 기대값과 최대손실을 검증해 가중치를 조정합니다."
    )
    st.caption(
        "온라인 시세는 yfinance의 최근 가용 1분봉·일봉을 사용합니다. 개인 연구용이며 "
        "거래소 정식 유료 실시간 피드가 아니므로 지연·누락 가능성을 화면에 표시합니다."
    )


def main() -> None:
    st.markdown(
        mobile_ui.page_css(
            # 머리글 줄은 폰에서 감춘다 — 세로로 쌓이면 제목만 여러 줄이 된다.
            mobile_ui.hide_header_rows("j3-th-head"),
            # 테마표(8칸) — 폰에서는 테마·점수·상태·당일만 남긴다.
            mobile_ui.table_css("j3tbtn_", 8, {
                2: "", 4: "조건점수", 5: "상태", 6: "당일",
            }, "j3-td"),
            # 눌림목표(12칸) — 폰에서는 종목·두 점수·주가·고점 대비만 남긴다.
            mobile_ui.table_css("j3pbf_", 12, {
                2: "", 4: "눌림", 5: "종목점수", 7: "현재가", 8: "고점 대비",
            }, "j3-td"),
        ),
        unsafe_allow_html=True,
    )
    st.title("자비스3 — 미국 테마 레이더")
    try:
        j3store.ensure_tables()
    except Exception as exc:
        st.error(f"자비스3 기록 테이블 준비 실패: {_safe_error_text(exc)}")

    _render_market_overview()
    market = st.session_state.get("j3_market_overview") or {"ok": False, "score": 0, "regime": "자료부족"}
    st.divider()
    # 미국장 선행신호 카드만 자비스3에 둔다(2026-07-22 사용자 정정: 한국장 수급 카드는
    # 미국 페이지에 어울리지 않으므로 자비스4(국내)에 넣는다). 같은 렌더러·세션 상태를
    # 재사용하므로 시장판단 페이지와 판정이 항상 일치한다.
    market_signal_ui.render_us_market_signal_card()
    st.divider()
    section = st.radio(
        "자비스3 보기",
        ["테마·종목", "매수 기록 현황", "판정 기준"],
        horizontal=True,
        label_visibility="collapsed",
        key="j3_section",
    )
    if section == "테마·종목":
        _render_radar_tab(market)
    elif section == "매수 기록 현황":
        _render_records_tab()
    else:
        _render_method_tab()


main()
