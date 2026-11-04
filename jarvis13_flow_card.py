"""자비스13 「🎯 한국장 시장 상태」(수급 카드) — 자비스12 「🌐 미국장 시장 상태」 형식 (2026-11-04 상하님).

상하님 — 「이것도 미국테마 디자인처럼 해라 · 왠만한 것 다 찾아서 디자인 미국테마 형식을 따라 해라」 · 「누르면 직전 저장이 나와야지」.

자비스12 는 `market_signal_ui.render_us_market_signal_card(foldable=True)` 로 **계기판 하나만 먼저 보이고**, 「자세히 보기 ▾」를
누르면 전일 칸까지 든 카드 전체가 열린다. 한국 카드(`market_signal_ui.render_kr_flow_card`)는 접기가 없어 당일·직전 저장이 늘
다 펴져 있었다. `market_signal_ui` 는 얼린 파일(자비스4 지킴이)이라 고치지 않고, 이 사본이 **같은 함수를 부르기만** 한다 —
판정·계산·저장은 하나도 안 바꾼다(같은 run_kr_flow_check · 같은 직전 저장 복원 · 같은 카드 그리기).

자비스12 와 다른 한 가지 — 여닫기를 HTML 체크칸이 아니라 **스트림릿 상태**로 한다. 이 카드는 1분마다 저절로 다시 그려지는
조각(fragment)이라, 체크칸이면 값이 바뀌어 다시 그릴 때마다 열어 둔 카드가 저절로 닫힌다. 닫혀 있을 때는 카드 전체를 아예
안 그린다(그만큼 가볍다).

이름은 j13 — 단추·보관함 열쇠가 자비스4(kr_flow_*) · 자비스12(us_signal_*) 것과 섞이지 않게(CLAUDE.md 0-3 ⑤).
수급 값을 담는 보관함(kr_flow_result 등)은 run_kr_flow_check 가 쓰는 그대로다 — 같은 값을 두 번 받지 않으려고.
"""

from __future__ import annotations

import streamlit as st

import gauge_ui
import jarvis13_shared
import market_signal_ui as msu

MODULE_REVISION = 2026110501
OPEN_KEY = "j13_flow_more"
SHARED_KEY = "kr_flow"
# run_kr_flow_check 가 남기는 칸 그대로(market_signal_ui) — 옮길 때 이 넷을 같이 옮긴다.
SHARED_STATE = ("kr_flow_result", "kr_flow_failures", "kr_flow_last_checked_at", "kr_flow_last_attempt_at")

TITLE_HTML = ("<div style='font-size:16px; font-weight:800; color:#c084fc; margin:.25rem 0 .4rem; "
              "letter-spacing:-.01em'>🎯 한국장 시장 상태</div>")

# 자비스12 _US_FOLD_CSS 의 단추 모양(초록 테두리 둥근 띠) · 미리보기 계기판 상자를 j13 이름으로. 여닫기 규칙은 뺐다(위 설명).
FOLD_CSS = """<style>
.j13-flow-peek { margin:.35rem 0 0; }
.j13-flow-peek .sig-gauge-shell { border:1px solid rgba(255,255,255,.16); border-radius:12px;
  padding:.6rem .7rem .2rem; background:rgba(255,255,255,.03); }
.j13-flow-peek .sig-gauge { text-align:center; }
.j13-flow-peek .sig-gauge > svg { display:block; margin-left:auto; margin-right:auto; }
div[class*="st-key-j13_flow_more_btn"] button, div[class*="st-key-j13_flow_less_btn"] button {
  width:100% !important; border:1px solid rgba(34,197,94,.45) !important; border-radius:14px !important;
  background:rgba(34,197,94,.10) !important; }
div[class*="st-key-j13_flow_more_btn"] button p, div[class*="st-key-j13_flow_less_btn"] button p {
  color:#8ef0b5 !important; font-weight:800 !important; font-size:.98rem !important; }
div[class*="st-key-j13_flow_more_btn"] button:hover, div[class*="st-key-j13_flow_less_btn"] button:hover {
  background:rgba(34,197,94,.18) !important; border-color:rgba(34,197,94,.7) !important; }
</style>"""


def _flip() -> None:
    st.session_state[OPEN_KEY] = not bool(st.session_state.get(OPEN_KEY))


def _previous_label(previous_stage) -> str:
    """render_kr_flow_card 와 같은 이름 — 「전일」 또는 「직전 저장」 + 날짜."""
    label = "전일"
    if previous_stage:
        label = str(previous_stage.get("period_label") or "전일")
        day = str(previous_stage.get("trade_date") or "")
        if len(day) >= 10:
            label += f" · {day[5:].replace('-', '.')}"
    return label


@st.fragment(run_every=60)
def render() -> None:
    """🎯 한국장 시장 상태 — 닫혀 있으면 당일 계기판 하나 · 「자세히 보기 ▾」를 누르면 직전 저장까지 든 카드 전체."""
    st.markdown(TITLE_HTML, unsafe_allow_html=True)
    clicked = st.button("수급 다시 확인", key="j13_flow_refresh")
    result = st.session_state.get("kr_flow_result")
    due = msu._kr_flow_auto_due(result, st.session_state.get("kr_flow_last_attempt_at"), msu._now_seoul())
    # 손님끼리 55초 같이 쓴다(2026-11-04 · jarvis13_shared) — 새 손님마다 수급을 새로 받던 2.3초. 방금 다른 손님이 받은 판을
    # 그대로 옮긴다(같은 run_kr_flow_check 결과). 외국인 선물을 손으로 넣은 손님은 제 값이 따로라 옮기지 않는다.
    if not clicked and due and not st.session_state.get("kr_flow_foreign_futures_manual"):
        shared = jarvis13_shared.peek((SHARED_KEY, id(msu.run_kr_flow_check)))
        if shared:
            st.session_state.update(shared)
            result = shared.get("kr_flow_result")
            due = result is None
    if clicked or due:
        with st.spinner("장중 수급 확인 중..." if clicked else "장중 수급 자동 확인 중..."):
            result = msu.run_kr_flow_check(force_refresh=True) if clicked else msu.run_kr_flow_check()
        if result is not None and not st.session_state.get("kr_flow_foreign_futures_manual"):
            jarvis13_shared.put((SHARED_KEY, id(msu.run_kr_flow_check)), {key: st.session_state.get(key) for key in SHARED_STATE})
    if result is None:
        st.info("수급 자료를 아직 못 받았습니다. 「수급 다시 확인」을 눌러 보십시오.")
        return

    # 꾸밈 덩이는 **새 줄에서** 연다(2026-11-05 · 「</style><style>」로 붙으면 뒤 덩이가 문단 글로 읽힌다 — 세부사항 상자 0개 사건과 같은 꼴).
    st.markdown(f"<style>{gauge_ui.CSS}{msu._SIGNAL_GAUGE_CSS}</style>\n" + FOLD_CSS, unsafe_allow_html=True)
    is_open = bool(st.session_state.get(OPEN_KEY))
    if not is_open:
        st.markdown(msu._peek_gauge_html(result, msu._FLOW_VERDICT_STYLE, msu.KR_VERDICT_ORDER, "당일"),
                    unsafe_allow_html=True)
        st.button("자세히 보기 ▾ (직전 저장 · 설명 · 신호 목록)", key="j13_flow_more_btn", on_click=_flip)
        return

    st.button("닫기 ▴", key="j13_flow_less_btn", on_click=_flip)
    previous_result, previous_stage = msu._previous_kr_flow_comparison()
    msu.render_market_signal_card(
        result,
        verdict_style=msu._FLOW_VERDICT_STYLE,
        core_display=msu._FLOW_CORE_DISPLAY,
        table_keys=msu._FLOW_TABLE_KEYS,
        detail_title="한국장 신호 상세",
        detail_caption=(
            "‘기금·연기금’은 KIS 원본 필드명이 기금입니다. 시장베이시스는 외국인 선물이 "
            "얼마나 사고팔았는지를 못 구했을 때 대신 보는 다른 지표이며, 수급값 자체가 "
            "아닙니다. ‘기관계’는 금융투자·투신·사모·기금을 모두 더한 값입니다."
        ),
        table_key="j13_flow_detail_table",
        falling_market=msu.falling_market_note(),
        diagnosis_text=msu.kr_flow_diagnosis,
        verdict_order=msu.KR_VERDICT_ORDER,
        previous_stage=previous_stage,
        show_position_score=True,
        comparison_result=previous_result,
        comparison_label=_previous_label(previous_stage),
        stage_guide=msu._KR_STAGE_GUIDE,
    )
    # 다 읽고 위로 되돌아가지 않아도 닫을 수 있게 밑에도 둔다(자비스12 와 같다).
    st.button("닫기 ▴", key="j13_flow_less_btn_bottom", on_click=_flip)
