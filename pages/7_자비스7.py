"""JARVIS 7 — isolated US-theme experience with nonblocking reads."""
from __future__ import annotations

import streamlit as st
import auth
import login_prism

st.set_page_config(page_title="JARVIS 7 · 미국테마",page_icon="✦",layout="wide")


def login_gate():
    auth.sync_auth()
    if login_prism.wants_guest(st):
        auth.login_as_guest()
    if st.session_state.get("authenticated"):
        return
    st.title("JARVIS 7 · 미국테마")
    st.caption("새로운 미국테마 대시보드")
    try:
        password=st.secrets.get("APP_PASSWORD")
    except Exception:
        password=None
    with st.form("j7_login"):
        entered=st.text_input("비밀번호",type="password")
        if st.form_submit_button("자비스7 로그인"):
            if password and entered==password:
                auth.login_as_owner()
                st.rerun()
            st.error("비밀번호를 확인하세요.")
    if st.button("게스트로 둘러보기"):
        auth.login_as_guest()
        st.rerun()
    st.stop()


login_gate()

import page_access
if getattr(page_access,"MODULE_REVISION",0)<2026090830:
    import importlib
    page_access=importlib.reload(page_access)
page_access.guard(st,"자비스7")

import jarvis7_data as data
import jarvis7_ui as ui
from jarvis7_app import Dashboard,apply_event
import mobile_ui
if not hasattr(mobile_ui,"jarvis7_css"):
    import importlib
    mobile_ui=importlib.reload(mobile_ui)

# Only present on J7. Never inject these rules from another page.
st.html("""<style>
body:has(.j7-mount) [data-testid="stAppViewContainer"]{background:radial-gradient(ellipse at 50% 0,#071a34 0,#020a16 65%)!important}
body:has(.j7-mount) [data-testid="stSidebar"],body:has(.j7-mount) [data-testid="stSidebarCollapsedControl"]{display:none!important}
body:has(.j7-mount) [data-testid="stHeader"]{display:none!important}
body:has(.j7-mount) .block-container{max-width:1200px;padding:1.1rem 1.6rem 0}
</style>""")


@st.cache_resource
def component(css,js):
    import streamlit.components.v2 as v2
    return v2.component("jarvis7_dashboard",html='<div class="j7-mount"></div>',
                        css=css,js=js,isolate_styles=False)


state=st.session_state.setdefault("j7_state",{
    "view":st.query_params.get("j7","home"),
    **{k:str(st.query_params.get("j7_"+k,""))[:100] for k in ("ticker","theme","strategy","origin")},
    "timeframe":st.query_params.get("j7_timeframe","당일"),
})
st.session_state["j7_render_revision"]=st.session_state.get("j7_render_revision",0)+1


def on_event():
    current=st.session_state["j7_state"]
    event=st.session_state.get("j7_dashboard",{}).get("event")
    if apply_event(event,current,guest=auth.is_guest()):
        params=dict(st.query_params)
        params["j7"]=current.get("view","home")
        params.update({"j7_"+field:current.get(field,"") for field in ("ticker","theme","strategy","origin","timeframe")})
        st.query_params.from_dict(params)


dashboard=Dashboard(state,guest=auth.is_guest())
markup=dashboard.render()
result=component(ui.CSS+mobile_ui.jarvis7_css(),ui.JS)(data={"html":markup,"pending":dashboard.pending,
                         "revision":st.session_state["j7_render_revision"],
                         "route":'|'.join(str(state.get(k,"")) for k in ("view","ticker","theme","strategy","origin"))},
                    key="j7_dashboard",on_event_change=on_event)
