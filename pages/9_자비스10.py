"""자비스10 · 한국증시 (2026-09-30 상하님 지시).

상하님 — *"기존에 한국테마 스마트폰이나 테블릿에서 빼고 너가 한국증시 새로 만들어 올려라 …
한국증시는 가벼우니 손가락으로 넘기기 기능 넣어라."* · *"종합주가지수를 사라는 건지 개별 종목을
사라는 건지 … 한국증시에 이 부분을 정확히 해라."*

설명서: docs/JARVIS10_SPEC.md · 숫자의 근거: docs/JARVIS10_KR_RESEARCH.md

- 개별 종목을 추천하지 않는다. "사라·쉬어라" 신호를 두지 않는다. 판단 자료만 보여 준다.
- 두 판(코스피 · 시장분석)을 **한 번에 다 그려 두고** 손가락으로 넘긴다 — 넘길 때 서버에 묻지 않는다.
"""

from __future__ import annotations

import secrets
from concurrent.futures import ThreadPoolExecutor

import streamlit as st

import auth  # 로그인 유지(쿠키). 쿠키가 안 되면 조용히 세션 기반 동작으로 남는다.
import login_prism  # 첫 화면의 '판 누르고 왔나' 표식을 읽는다.

# 배포 갱신 중 옛 auth 가 프로세스에 남으면 함수 모양이 안 맞아 화면이 죽는다. 낮으면 다시 읽는다.
_REQUIRED_AUTH_REVISION = 2026080301
if int(getattr(auth, "MODULE_REVISION", 0)) < _REQUIRED_AUTH_REVISION:
    import importlib as _importlib

    auth = _importlib.reload(auth)

st.set_page_config(page_title="자비스10 — 한국증시", layout="centered")

import page_access  # noqa: E402

if int(getattr(page_access, "MODULE_REVISION", 0)) < 2026093001:
    import importlib as _importlib

    page_access = _importlib.reload(page_access)
# 맨 앞에서 막는다 — 닫아 두면 아래 시세 조회가 한 줄도 안 돈다.
page_access.guard(st, "한국증시")


def _login_gate() -> None:
    # 첫 화면의 큰 판을 누르고 온 사람은 비밀번호를 묻지 않는다(한국테마와 같다).
    try:
        if login_prism.wants_guest(st):
            auth.login_as_guest()
    except Exception:
        pass
    auth.sync_auth()  # 쿠키에 로그인이 남아 있으면 되살린다(폰 복귀 시 재로그인 방지).
    if st.session_state.get("authenticated"):
        return
    st.markdown("## 자비스10 — 한국증시")
    st.caption("승인된 사용자만 접근할 수 있습니다. 여기서 바로 로그인할 수 있습니다.")
    try:
        password = st.secrets.get("APP_PASSWORD")
    except Exception:
        password = None
    if not password:
        st.warning(".streamlit/secrets.toml에 APP_PASSWORD 설정이 필요합니다.")
        st.stop()
    entered = st.text_input("비밀번호", type="password", key="j10_login_password")
    if st.button("자비스10 로그인", key="j10_login_submit", width="stretch"):
        if entered == password:
            auth.login_as_owner()
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    st.stop()


_login_gate()

import importlib  # noqa: E402

import jarvis10_data as j10data  # noqa: E402
import jarvis10_ui as j10ui  # noqa: E402

# 계산·화면 조각을 바꾸면 그 모듈의 MODULE_REVISION 과 여기 숫자를 같이 올린다(CLAUDE.md 11).
_REQUIRED_J10_DATA_REVISION = 2026093001
_REQUIRED_J10_UI_REVISION = 2026093001
if int(getattr(j10data, "MODULE_REVISION", 0)) < _REQUIRED_J10_DATA_REVISION:
    j10data = importlib.reload(j10data)
if int(getattr(j10ui, "MODULE_REVISION", 0)) < _REQUIRED_J10_UI_REVISION:
    j10ui = importlib.reload(j10ui)


def _keep_state() -> None:
    """↻ — 보던 판(코스피·시장분석)은 그대로 두고 지금 값만 새로 받는다."""
    st.session_state["j10_keep"] = True
    try:
        j10data.forget_live()
    except Exception:
        pass


# 이번 판 표시 — 다른 화면에 갔다 오면 새로 바뀌어 늘 코스피 판부터 보인다(jarvis10_ui.page_css).
if not st.session_state.pop("j10_keep", False) or "j10_nonce" not in st.session_state:
    st.session_state["j10_nonce"] = secrets.token_hex(4)
_nonce = st.session_state["j10_nonce"]


def _overview():
    """한국 시장 국면 · 외국인+기관 · 미국 게이지 — 한국테마와 같은 계산을 그대로 부른다."""
    try:
        import jarvis4_data

        return jarvis4_data.get_market_overview()
    except Exception:
        return None


# 시장분석 판 자료는 **코스피 판을 그리는 동안** 뒤에서 받는다. 두 판 다 이 화면이 그리는 것이라
# 화면이 기다리는 일을 밀어내지 않는다(CLAUDE.md 0-0-1).
_pool = ThreadPoolExecutor(max_workers=2)
_f_cards = _pool.submit(j10data.market_cards)
_f_overview = _pool.submit(_overview)

_kospi = j10data.kospi_panel()
_phase = j10data.market_phase()

st.markdown(
    j10ui.page_css(_nonce, j10ui.gauge_css().replace("\n", " "))
    + j10ui.banner_html(_kospi.get("history_monthly"), _phase),
    unsafe_allow_html=True,
)
with st.container(horizontal=True, key="j10_row_links"):
    try:
        st.page_link("pages/2_자비스3.py", label="🌎 미국테마 →")
    except Exception:
        pass     # 페이지 목록이 없는 자리(시험)에서는 조용히 넘어간다
    st.markdown(j10ui.help_button_html(), unsafe_allow_html=True)

with st.container(key="j10_page_kospi"):
    st.markdown(j10ui.kospi_panel_html(_kospi, _nonce, _phase), unsafe_allow_html=True)
# 넘기기 코드는 코스피 판 바로 뒤에 심는다 — 시장분석 판 자료를 기다리는 동안에도 홈 쪽 넘기기·↻ 는 된다.
j10ui.inject_js(st)

_cards = _f_cards.result()
_ov = _f_overview.result()
_pool.shutdown(wait=False)
with st.container(key="j10_page_market"):
    st.markdown(j10ui.market_panel_html(_cards, _ov, _kospi.get("card"), _nonce), unsafe_allow_html=True)

st.markdown(j10ui.help_sheet_html(), unsafe_allow_html=True)
st.markdown(j10ui.nav_html(), unsafe_allow_html=True)
with st.container(key="j10_home_link"):
    try:
        st.page_link("app.py", label="홈")
    except Exception:
        pass
with st.container(key="j10_hidden"):
    st.button("다시 받기", key="j10_refresh", on_click=_keep_state)

try:
    import build_stamp

    build_stamp.render(st)
except Exception:
    pass
