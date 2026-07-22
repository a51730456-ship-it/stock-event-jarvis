"""자비스3 — 미국 테마 레이더와 실제 매수 기록 페이지."""

from __future__ import annotations

from datetime import date

import streamlit as st

st.set_page_config(page_title="자비스3 — 미국 테마 레이더", layout="wide")

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
    /* 사이드바 순서: 시장판단 → 자비스1 → 자비스2 → 미국테마 (2026-07-22 사용자 지시) */
    [data-testid="stSidebarNav"] ul { display: flex; flex-direction: column; }
    [data-testid="stSidebarNav"] li:nth-child(1) { order: 2; }
    [data-testid="stSidebarNav"] li:nth-child(2) { order: 1; }
    [data-testid="stSidebarNav"] li:nth-child(3) { order: 3; }
    [data-testid="stSidebarNav"] li:nth-child(4) { order: 4; }
    [data-testid="stSidebarNav"] li:nth-child(4) a p { font-size: 0 !important; }
    [data-testid="stSidebarNav"] li:nth-child(4) a p::before {
        content: "미국테마";
        font-size: 1.4rem;
        font-weight: 800;
        color: #ffb020;
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
    .j3-top-row { display: flex; gap: 2rem; flex-wrap: wrap; margin-bottom: 0.3rem; }
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
    div[class*="st-key-j3tbtn_"] button p {
        font-weight: 800 !important; font-size: 0.95rem !important; margin: 0 !important;
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
    .j3-holo-cell .label { color: #9aa0aa; font-size: 0.85rem; }
    .j3-holo-cell .val { font-size: 1.5rem; font-weight: 800; color: #e6e6e6; line-height: 1.2; text-shadow: 0 0 8px rgba(77,166,255,0.45); }
    .j3-holo-corner { position: absolute; width: 14px; height: 14px; border-color: #4da6ff; }
    .j3-holo-corner.tl { top: 6px; left: 6px; border-top: 2px solid #4da6ff; border-left: 2px solid #4da6ff; }
    .j3-holo-corner.tr { top: 6px; right: 6px; border-top: 2px solid #4da6ff; border-right: 2px solid #4da6ff; }
    .j3-holo-corner.bl { bottom: 6px; left: 6px; border-bottom: 2px solid #4da6ff; border-left: 2px solid #4da6ff; }
    .j3-holo-corner.br { bottom: 6px; right: 6px; border-bottom: 2px solid #4da6ff; border-right: 2px solid #4da6ff; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _login_gate() -> None:
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

import altair as alt
import pandas as pd

import jarvis3_data as j3data
import jarvis3_store as j3store
import market_signal_ui

# ── 온라인 옛 모듈 자가복구 ──────────────────────────────────────────────────
# 스트림릿 클라우드는 배포 갱신 때 페이지 파일만 새로 읽고 import된 모듈은 옛것을
# 프로세스에 유지하는 경우가 있다(2026-07-22 '모듈 갱신 대기'·'당일 자료 없음' 실발생).
# 새 코드에만 있는 함수가 없으면 그 모듈을 파일에서 다시 읽어 재부팅 없이 복구한다.
if not hasattr(j3data, "get_fear_greed") or not hasattr(j3data, "_intraday_chart_payload"):
    j3data = importlib.reload(j3data)
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


def _fear_greed_cell() -> str:
    """공포·탐욕 지수 상단 칸. 조회 실패 시 '자료 부족'으로만 표시한다.

    온라인 배포 직후 jarvis3_data 모듈이 옛 버전으로 캐시돼 있으면 함수가 아직
    없을 수 있어 getattr로 방어한다(_leader_chart_payload와 같은 이유,
    2026-07-22 온라인 AttributeError 실제 발생).
    """
    fetcher = getattr(j3data, "get_fear_greed", None)
    if fetcher is None:
        return _top_metric("공포·탐욕 지수", "—", "#9aa0aa", "모듈 갱신 대기")
    fg = fetcher()
    if not fg.get("ok"):
        return _top_metric("공포·탐욕 지수", "—", "#9aa0aa", "자료 부족")
    color = _fear_greed_color(fg.get("score"))
    previous = fg.get("previous_close")
    sub = fg.get("rating_kr") or "—"
    if previous is not None:
        sub += f" · 전일 {previous:.0f}"
    if fg.get("stale"):
        sub += " · 마지막 정상값"
    return _top_metric("공포·탐욕 지수", f"{fg['score']:.0f}/100", color, sub, sub_color=color)


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
    regime_color = {"방어 우선": "#ff5b5b", "중립·선별": "#ff9d3b", "상승 우위": "#44f0a1"}.get(overview["regime"], "#e6e6e6")
    if phase == "정규장 시간":
        phase_color = "#44f0a1"
    elif phase in ("프리마켓", "애프터마켓"):
        phase_color = "#ff9d3b"
    else:
        phase_color = "#ff5b5b"
    spy_row, qqq_row = overview["rows"]["SPY"], overview["rows"]["QQQ"]
    vix_value = overview["rows"].get("^VIX", {}).get("current")
    top_cells = [
        _top_metric("시장 국면", overview["regime"], regime_color, f"조건 {overview['score']}/100"),
        _top_metric("SPY", _price(spy_row.get("current")), "#e6e6e6", spy_row.get("change_pct"), sub_signed=True),
        _top_metric("QQQ", _price(qqq_row.get("current")), "#e6e6e6", qqq_row.get("change_pct"), sub_signed=True),
        _top_metric("장 상태", phase, phase_color, f"VIX {_number(vix_value, 2)}"),
        _fear_greed_cell(),
    ]
    st.markdown(f"<div class='j3-top-row'>{''.join(top_cells)}</div>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="j3-score-guide">
            조건점수 {overview['score']}/100은 상승장 확인 조건에서 얻은 점수이며 승률이 아닙니다.<br>
            0~49점 방어 우선 · 50~74점 중립·선별 · 75~100점 상승 우위<br>
            {_market_score_detail(overview)}<br>
            장 상태는 미국 세션 단계입니다(뉴욕시각 기준): 프리마켓 04:00~09:30 → 정규장 09:30~16:00
            → 애프터마켓 16:00~20:00 → 장 마감 · 아래 VIX는 공포지수 현재값입니다.<br>
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


def _render_stock_detail(theme_row: dict, leader: dict, market: dict) -> None:
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

    # 위 '테마 내 종합' 박스와 한 줄 더 띄운 뒤 차트 섹션을 시작한다.
    st.markdown(
        "<div class='j3-chart-heading'>가격 차트 · 일봉/주봉/월봉 한눈에 보기</div>",
        unsafe_allow_html=True,
    )
    st.caption("주가 흐름은 하늘색 · 20일선은 붉은색 · 50일선은 보라색입니다. 일봉 거래량은 일봉 바로 아래에 표시됩니다.")
    chart_bundle = j3data.get_chart_bundle(ticker)
    if chart_bundle.get("ok"):
        daily_col, weekly_col, monthly_col = st.columns(3)
        chart_columns = {"일봉": daily_col, "주봉": weekly_col, "월봉": monthly_col}
        for timeframe, chart_column in chart_columns.items():
            payload = chart_bundle["charts"].get(timeframe, {})
            with chart_column:
                # 제목을 차트 밖에서 통일된 높이로 그려 일봉·주봉·월봉을 한 줄에 정렬한다.
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
    else:
        st.warning(f"차트 조회 실패: {_safe_error_text(chart_bundle.get('error'))}")

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

    _render_buy_form(theme_row, leader, market)


_RECORD_COLUMNS = [
    "id", "buy_date", "ticker", "stock_name", "theme_name", "trade_style",
    "buy_price", "quantity", "status", "sell_date", "sell_price", "result_pct",
    "market_regime", "market_score", "theme_score", "stock_score", "memo",
]


_RECORD_HEADERS_KR = {
    "id": "번호", "buy_date": "매수일", "ticker": "티커", "stock_name": "종목명",
    "theme_name": "테마", "trade_style": "매매유형", "buy_price": "매수가(USD)",
    "quantity": "수량", "status": "상태", "current_pl_pct": "현재 손익률(%)",
    "sell_date": "매도일", "sell_price": "매도가(USD)", "result_pct": "확정 손익률(%)",
    "market_regime": "시장 국면", "market_score": "시장점수",
    "theme_score": "테마점수", "stock_score": "종목점수", "memo": "메모",
}


def _records_view(records: list[dict]):
    """저장 기록을 한글 제목 표로 만든다(2026-07-22 사용자 지시).

    보유 중인 기록은 최근가를 조회해 '현재 손익률(%)'을 계산하고,
    이익은 파랑·손실은 빨강(미국장 색 규칙)으로 칠한다. 시세 조회가 실패한
    종목은 값을 만들지 않고 '—'로 둔다.
    """
    view = pd.DataFrame(records)
    view = view[[col for col in _RECORD_COLUMNS if col in view.columns]]

    open_tickers = sorted({
        str(record.get("ticker")) for record in records
        if record.get("status") == "보유" and record.get("ticker")
    })[:30]
    current_prices = {}
    for ticker in open_tickers:
        quote = j3data.get_live_quote(ticker)
        if quote.get("ok") and quote.get("current"):
            current_prices[ticker] = float(quote["current"])

    def _live_pl(row):
        if row.get("status") != "보유":
            return None
        current = current_prices.get(str(row.get("ticker")))
        buy_price = row.get("buy_price")
        if current and buy_price:
            return (current / float(buy_price) - 1) * 100
        return None

    if not view.empty and "status" in view.columns:
        view.insert(view.columns.get_loc("status") + 1, "current_pl_pct", view.apply(_live_pl, axis=1))
    view = view.rename(columns=_RECORD_HEADERS_KR)

    def _pl_style(value):
        try:
            if value is None or pd.isna(value):
                return ""
            return "color:#4da6ff;font-weight:700" if float(value) >= 0 else "color:#ff5b5b;font-weight:700"
        except (TypeError, ValueError):
            return ""

    pl_columns = [col for col in ("현재 손익률(%)", "확정 손익률(%)") if col in view.columns]
    formats = {col: "{:+.2f}" for col in pl_columns}
    for col in ("매수가(USD)", "매도가(USD)"):
        if col in view.columns:
            formats[col] = "{:,.2f}"
    # 수량·점수 칸은 소수점 없이 표시(2026-07-22 사용자 지시).
    for col in ("수량", "시장점수", "테마점수", "종목점수"):
        if col in view.columns:
            formats[col] = "{:,.0f}"
    # 첫 format 호출은 전체 칸에 na_rep(—)만 깔고, 두 번째가 칸별 형식을 덮는다 —
    # 형식 dict에 없는 칸(매도일·메모 등)의 None이 'None' 글자로 보이던 문제 수정.
    styler = view.style.format(na_rep="—").format(formats, na_rep="—")
    if pl_columns:
        styler = styler.map(_pl_style, subset=pl_columns)
    return styler


def _render_buy_form(theme_row: dict, leader: dict, market: dict) -> None:
    ticker = leader["ticker"]
    metrics, plan = leader["metrics"], leader["plan"]
    # 위 '추천 근거 요약' 카드와 붙어 보이지 않게 한 줄 띄운다(2026-07-22 사용자 지시).
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    # 제목 옆에서 그동안 저장한 매수 기록 현황을 바로 펼쳐볼 수 있게 한다
    # (2026-07-22 사용자 지시 — 저장 폼과 현황이 함께 있어야 한다).
    # 제목 열을 좁혀 현황 박스가 제목 바로 옆에 붙게 한다(멀리 떨어져 보인다는 지적 반영).
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
                st.dataframe(_records_view(records), hide_index=True, width="stretch")
                st.caption("청산 입력과 전체 목록은 위 ‘매수 기록 현황’ 탭에 있습니다.")
            else:
                st.caption("아직 저장된 매수 기록이 없습니다.")
    st.caption("실제로 매수한 경우에만 저장합니다. 저장 시 당시 시장·테마·종목 조건도 함께 보존됩니다.")
    with st.form(f"j3_buy_form_{ticker}", clear_on_submit=False):
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

    medal_by_rank = {1: "🥇", 2: "🥈", 3: "🥉"}
    # 상태 색은 20개 테마 순위표의 상태색과 같은 규칙(주도 초록·관찰 주황·약함 회색)을 쓴다.
    state_color_word = {"주도": "green", "관찰": "orange", "약함": "gray"}

    def _stock_label(ticker):
        item = next((cand for cand in top_candidates if cand["ticker"] == ticker), None)
        if item is None:
            return ticker
        rank = int(item["rank"])
        medal = medal_by_rank.get(rank, "")
        state = item["plan"].get("state", "")
        color_word = state_color_word.get(state, "gray")
        return (
            f"{medal} :green[**{rank}위 · {item['name']} ({ticker})**] · "
            f":red[**{item['score']:.1f}점**] · :{color_word}[**{state}**]"
        )

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
    _render_stock_detail(theme_row, selected_leader, market)


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

    st.dataframe(_records_view(records), hide_index=True, width="stretch")

    _render_close_editor(records)


def _render_close_editor(records: list[dict]) -> None:
    """보유 기록 청산을 표에서 바로 입력한다(2026-07-22 사용자 지시).

    매도일 칸을 누르면 달력이 뜨고, 매도가 칸에 금액을 넣으면 확정 손익률이
    자동 계산돼 미리보기 칸에 바로 나타난다. 매도가는 매수가 ±50% 범위만 허용한다.
    """
    saved_message = st.session_state.pop("j3_close_saved_msg", None)
    if saved_message:
        st.success(saved_message)

    open_records = [record for record in records if record.get("status") == "보유"]
    if not open_records:
        return
    st.markdown("#### 청산 입력 — 표에서 매도일·매도가를 직접 클릭해 입력")
    st.caption(
        "매도일 칸을 누르면 달력이 뜨고, 매도가를 넣는 순간 확정 손익률이 자동 계산됩니다. "
        "매도가는 매수가 ±50% 범위 안에서만 저장됩니다."
    )
    editor_key = "j3_close_editor"
    edited_rows = (st.session_state.get(editor_key) or {}).get("edited_rows", {})
    editor_rows = []
    for index, record in enumerate(open_records):
        buy_price = float(record["buy_price"])
        pending = edited_rows.get(index, {})
        pending_price = pending.get("매도가(USD)")
        preview = None
        try:
            if pending_price:
                preview = (float(pending_price) / buy_price - 1) * 100
        except (TypeError, ValueError):
            preview = None
        editor_rows.append({
            "번호": int(record["id"]),
            "티커": record["ticker"],
            "종목명": record["stock_name"],
            "매수일": record["buy_date"],
            "매수가(USD)": buy_price,
            "매도일": None,
            "매도가(USD)": None,
            "확정 손익률(%) 자동계산": preview,
            "허용 매도가 범위": f"{buy_price * 0.5:,.2f} ~ {buy_price * 1.5:,.2f}",
        })
    editor_frame = pd.DataFrame(editor_rows)
    # 빈 매도일·매도가 칸이 달력·숫자 입력으로 열리도록 자료형을 명시한다.
    editor_frame["매도일"] = pd.to_datetime(editor_frame["매도일"])
    editor_frame["매도가(USD)"] = editor_frame["매도가(USD)"].astype("float64")
    editor_frame["확정 손익률(%) 자동계산"] = editor_frame["확정 손익률(%) 자동계산"].astype("float64")
    edited = st.data_editor(
        editor_frame,
        column_config={
            "매도일": st.column_config.DateColumn("매도일", help="칸을 누르면 달력이 뜹니다"),
            "매도가(USD)": st.column_config.NumberColumn(
                "매도가(USD)", min_value=0.01, step=0.01, format="%.2f",
                help="매수가 ±50% 범위에서 입력",
            ),
            "매수가(USD)": st.column_config.NumberColumn(format="%.2f"),
            "확정 손익률(%) 자동계산": st.column_config.NumberColumn(format="%+.2f"),
        },
        disabled=[
            "번호", "티커", "종목명", "매수일", "매수가(USD)",
            "확정 손익률(%) 자동계산", "허용 매도가 범위",
        ],
        hide_index=True,
        width="stretch",
        key=editor_key,
    )
    if st.button("청산 저장 (매도일·매도가 입력된 종목만)", key="j3_close_editor_save", width="stretch"):
        saved_count = 0
        errors = []
        for index, record in enumerate(open_records):
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
    radar_tab, records_tab, method_tab = st.tabs(["테마·종목", "매수 기록 현황", "판정 기준"])
    with radar_tab:
        _render_radar_tab(market)
    with records_tab:
        _render_records_tab()
    with method_tab:
        _render_method_tab()


main()
