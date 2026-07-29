"""시장 판단 — 자비스1·2·3과 분리된 독립 화면.

한국장 기관 수급과 미국장 선행신호를 읽어 지금 시장 상태와 흐름을 보여준다.
종목을 고르는 화면이 아니다. 여기서 시장을 먼저 확인하고, 무엇을 할지는
사용자가 자비스1·2·3을 오가며 스스로 정한다.
"""

from __future__ import annotations

import streamlit as st

import auth  # 로그인 유지(쿠키). 쿠키가 안 되면 조용히 세션 기반 동작으로 남는다.

# 배포 갱신 중 옛 auth가 프로세스에 남으면 함수 모양이 안 맞아 화면이 죽는다
# (2026-07-25 온라인 실발생). 리비전이 낮으면 다시 읽는다.
_REQUIRED_AUTH_REVISION = 2026072503
if int(getattr(auth, "MODULE_REVISION", 0)) < _REQUIRED_AUTH_REVISION:
    import importlib as _importlib

    auth = _importlib.reload(auth)

st.set_page_config(page_title="시장 판단", layout="wide")

# 사이드바 표기는 자비스2·3 페이지와 같은 규칙을 따른다(첫 항목 'app' → '자비스1').
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
    [data-testid="stSidebarNav"] a {
        padding: 0.45rem 0.6rem !important;
    }
    [data-testid="stSidebarNav"] a,
    [data-testid="stSidebarNav"] a * {
        font-size: 1.15rem !important;
        font-weight: 800 !important;
        color: #ffb020 !important;
        line-height: 1.4 !important;
    }
    [data-testid="stSidebarNav"] a:hover,
    [data-testid="stSidebarNav"] a:hover * {
        color: #ffcf6b !important;
    }
    [data-testid="stSidebarNav"] li:first-child a p {
        font-size: 0 !important;
    }
    [data-testid="stSidebarNav"] li:first-child a p::before {
        content: "자비스1";
        font-size: 1.15rem;
        font-weight: 800;
        color: #ffb020;
    }
    [data-testid="stSidebarNav"] li:first-child a:hover p::before {
        color: #ffcf6b;
    }
    /* 사이드바 순서: 시장판단 → 자비스1 → 자비스2 → 미국테마 (2026-07-22 사용자 지시) */
    [data-testid="stSidebarNav"] ul { display: flex; flex-direction: column; }
    [data-testid="stSidebarNav"] li:nth-child(1) { order: 2; }
    [data-testid="stSidebarNav"] li:nth-child(2) { order: 1; }
    [data-testid="stSidebarNav"] li:nth-child(3) { order: 3; }
    [data-testid="stSidebarNav"] li:nth-child(4) { order: 4; }
    [data-testid="stSidebarNav"] li:nth-child(5) { order: 5; }
    [data-testid="stSidebarNav"] li:nth-child(6) { order: 6; }
    [data-testid="stSidebarNav"] li:nth-child(7) { order: 7; }
    [data-testid="stSidebarNav"] li:nth-child(7) a p { font-size: 0 !important; }
    [data-testid="stSidebarNav"] li:nth-child(7) a p::before {
        content: "종가관찰\\A(자비스6)"; white-space: pre; line-height: 1.2;
        font-size: 1.15rem; font-weight: 800; color: #ffb020;
    }
    [data-testid="stSidebarNav"] li:nth-child(4) a p {
        font-size: 0 !important;
    }
    [data-testid="stSidebarNav"] li:nth-child(4) a p::before {
        content: "미국테마\\A(자비스3)"; white-space: pre; line-height: 1.2;
        font-size: 1.15rem;
        font-weight: 800;
        color: #ffb020;
    }
    [data-testid="stSidebarNav"] li:nth-child(4) a:hover p::before {
        color: #ffcf6b;
    }
    [data-testid="stSidebarNav"] li:nth-child(5) a p {
        font-size: 0 !important;
    }
    [data-testid="stSidebarNav"] li:nth-child(5) a p::before {
        content: "한국테마\\A(자비스4)"; white-space: pre; line-height: 1.2;
        font-size: 1.15rem;
        font-weight: 800;
        color: #ffb020;
    }
    [data-testid="stSidebarNav"] li:nth-child(5) a:hover p::before {
        color: #ffcf6b;
    }
    [data-testid="stSidebarNav"] li:nth-child(6) a p { font-size: 0 !important; }
    [data-testid="stSidebarNav"] li:nth-child(6) a p::before {
        content: "한국테마\\A(선행감지)"; white-space: pre; line-height: 1.2; font-size: 1.15rem; font-weight: 800; color: #ffb020;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── 인증 게이트 — 여기서 바로 로그인 가능 (자비스1 경유 불필요) ─────────────────
auth.sync_auth()  # 쿠키에 로그인이 남아 있으면 되살린다(폰 복귀 시 재로그인 방지).
if not st.session_state.get("authenticated"):
    st.markdown("## 🧭 시장 판단")
    st.caption("승인된 사용자만 접근할 수 있습니다. 여기서 바로 로그인하세요.")
    try:
        _app_password = st.secrets.get("APP_PASSWORD")
    except Exception:
        _app_password = None
    if not _app_password:
        st.warning("비밀번호 설정이 필요합니다. .streamlit/secrets.toml에 APP_PASSWORD를 설정하세요.")
        st.stop()
    _pw = st.text_input("비밀번호", type="password", key="market_login_password")
    if st.button("로그인", key="market_login_submit", use_container_width=True):
        if _pw == _app_password:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    st.stop()

import market_signal_ui

# 온라인 배포 갱신 때 페이지만 새로 읽히고 모듈은 옛것이 남는 경우 자가복구
# (자비스3 페이지와 같은 이유·같은 방식, 2026-07-22).
_REQUIRED_SIGNAL_UI_REVISION = 2026072910
if (
    not hasattr(market_signal_ui, "_STATUS_TEXT")
    # 이름은 그대로인데 내용만 옛것인 모듈도 걸러낸다(2026-07-24 온라인 실발생).
    or int(getattr(market_signal_ui, "MODULE_REVISION", 0)) < _REQUIRED_SIGNAL_UI_REVISION
):
    import importlib
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

market_signal_ui.render_market_judgment_page()
