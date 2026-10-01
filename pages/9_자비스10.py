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

import streamlit as st

import auth  # 로그인 유지(쿠키). 쿠키가 안 되면 조용히 세션 기반 동작으로 남는다.
import login_prism  # 첫 화면의 '판 누르고 왔나' 표식을 읽는다.

# 배포 갱신 중 옛 auth 가 프로세스에 남으면 함수 모양이 안 맞아 화면이 죽는다. 낮으면 다시 읽는다.
_REQUIRED_AUTH_REVISION = 2026080301
if int(getattr(auth, "MODULE_REVISION", 0)) < _REQUIRED_AUTH_REVISION:
    import importlib as _importlib

    auth = _importlib.reload(auth)
# 로그인 첫 화면의 큰 판(폰·태블릿 = 한국증시)도 여기서 판 번호를 본다 — 첫 화면(app.py)은 모듈을 다시
# 읽지 않는 규칙이라(test_reference_panel_guard), 온라인에 옛 login_prism 이 남으면 한국테마 판이 그대로
# 나왔다(2026-10-01 온라인 실측). 이 화면이 한 번 열리면 서버 전체가 새 판으로 바뀐다(CLAUDE.md 11).
_REQUIRED_LOGIN_PRISM_REVISION = 2026093001
if int(getattr(login_prism, "MODULE_REVISION", 0)) < _REQUIRED_LOGIN_PRISM_REVISION:
    import importlib as _importlib

    login_prism = _importlib.reload(login_prism)

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
_REQUIRED_J10_DATA_REVISION = 2026100101
_REQUIRED_J10_UI_REVISION = 2026100103
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
_fresh = not st.session_state.pop("j10_keep", False) or "j10_nonce" not in st.session_state
if _fresh:
    st.session_state["j10_nonce"] = secrets.token_hex(4)
_nonce = st.session_state["j10_nonce"]

# 시장분석 판의 칸들(코스닥·환율·미국 지수·외국인·기관)은 **코스피 판을 만드는 동안** 받는다 — 받기만 하는
# 일이라(계산이 거의 없다) 코스피 판을 늦추지 않는다. 계산이 무거운 시장 국면(한국테마 계산)은 코스피 판과
# 이동막대를 다 보낸 **뒤에** 시작한다(CLAUDE.md 0-0-1 · 2026-10-01 느린 폰 실측).
_card_jobs = j10data.market_cards_start()

_kospi = j10data.kospi_panel()
_phase = j10data.market_phase()

st.markdown(
    j10ui.page_css(_nonce) + j10ui.banner_html(_kospi.get("history_monthly"), _phase),
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
# 넘기기 코드는 코스피 판 바로 뒤에 심는다 — 시장분석 판 자료를 기다리는 동안에도 넘기기·↻ 는 된다.
j10ui.inject_js(st)

# 시장분석 판 자리를 먼저 만들어 두고, 설명 창·아래 이동막대를 **자료를 기다리기 전에** 그린다 (2026-10-01).
# 예전에는 시장분석 자료가 다 와야 이동막대가 그려져, 폰에서 막대가 코스피 판보다 늦게 떴다.
# 자리에는 「받는 중」을 두어 그동안 넘겨도 빈 화면이 아니다. ↻ 로 다시 받을 때는 빈 자리(st.empty)를 만들지
# 않는다 — 만드는 순간 보던 판이 비워진다. 그때는 보던 판이 새 판으로 덮일 때까지 그대로 남는다.
_market_box = st.container(key="j10_page_market")
_market_slot = None
if _fresh:
    with _market_box:
        _market_slot = st.empty()
    _market_slot.markdown(j10ui.market_loading_html(_nonce), unsafe_allow_html=True)

# 설명 창도 꾸러미로 보낸다 — 첫 묶음이 커지면 그만큼 코스피 판이 늦게 뜬다(2026-10-01 노트북 느린 폰 실측).
# 「📘 한국증시 설명」을 먼저 누르면 넘기기 코드가 그 자리에서 펼쳐 바로 열린다.
st.markdown(j10ui.deferred_html(j10ui.help_sheet_html()), unsafe_allow_html=True)
st.markdown(j10ui.nav_html(), unsafe_allow_html=True)
with st.container(key="j10_home_link"):
    try:
        st.page_link("app.py", label="홈")
    except Exception:
        pass
with st.container(key="j10_hidden"):
    st.button("다시 받기", key="j10_refresh", on_click=_keep_state)

_overview_job = j10data.overview_start()
_cards = j10data.market_cards_collect(_card_jobs)
_ov = _overview_job.result()
# 게이지 꾸밈은 게이지가 있는 이 판에 싣는다 — 첫 화면(코스피 판)이 읽을 꾸밈 글자가 그만큼 준다.
# 판은 **글자 꾸러미로** 보낸다 — 폰이 첫 화면을 그린 뒤 넘기기 코드가 펼친다(jarvis10_ui.deferred_html).
_market_html = j10ui.deferred_html("<style>" + j10ui.gauge_css().replace("\n", " ") + "</style>"
                                   + j10ui.market_panel_html(_cards, _ov, _kospi.get("card"), _nonce))
if _market_slot is not None:
    _market_slot.markdown(_market_html, unsafe_allow_html=True)
else:
    with _market_box:
        st.markdown(_market_html, unsafe_allow_html=True)

try:
    import build_stamp

    build_stamp.render(st)
except Exception:
    pass
