"""자비스6 미국테마 — 새 디자인 화면.

**이 파일은 [pages/2_자비스3.py] 를 그대로 복사한 것이다** (2026-09-03 상하님 지시 —
"기존 자비스 미국테마 건들이지말고... 디자인만 새로 변경할꺼야").

무엇이 같고 무엇이 다른가:
  같다 — 값을 받고 점수를 매기고 판정하는 코드 전부. jarvis3_data 를 그대로 부른다.
         그래서 같은 날 두 화면을 열면 숫자가 똑같아야 한다. 다르면 그것이 버그다.
  다르다 — 껍데기(CSS)와 화면 짜임뿐이다.

옛 미국테마는 그대로 살아 있다. 이 파일을 고치는 것이 그쪽에 닿지 않는다.
반대로 그쪽을 고쳐도 여기 안 온다 — 고칠 일이 생기면 두 곳을 다 봐야 한다.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo
import base64
import html
from pathlib import Path
import re

import streamlit as st

import auth  # 로그인 유지(쿠키). 쿠키가 안 되면 조용히 세션 기반 동작으로 남는다.
import login_prism  # 첫 화면의 '판 누르고 왔나' 표식을 읽는다(2026-08-09).

# 배포 갱신 중 옛 auth가 프로세스에 남으면 함수 모양이 안 맞아 화면이 죽는다
# (2026-07-25 온라인 실발생). 리비전이 낮으면 다시 읽는다.
_REQUIRED_AUTH_REVISION = 2026080301
if int(getattr(auth, "MODULE_REVISION", 0)) < _REQUIRED_AUTH_REVISION:
    import importlib as _importlib

    auth = _importlib.reload(auth)

# 탭 그림(=폰 홈 화면 아이콘의 바탕)은 **우리가 그린 그림 파일**이다.
# 그림은 tools/make_jarvis6_icon.py 가 만든다. 못 읽으면 조용히 이모지로 남는다 —
# 그림 하나 때문에 화면이 안 열리면 안 된다.
_ICON_FILE = Path(__file__).resolve().parent.parent / "static" / "jarvis6_icon_192.png"
st.set_page_config(
    page_title="자비스6 미국테마",
    page_icon=str(_ICON_FILE) if _ICON_FILE.is_file() else "📈",
    layout="wide",
)

st.markdown(
    """
    <style>
    /* ── 왼쪽 메뉴를 통째로 없앤다 (2026-08-09 상하님 선택) ────────────────────
       미국테마↔한국테마는 맨 위 '가려면 클릭' 단추로 오간다. 나머지 다섯 화면은
       뒤로가기로 '어디로 갈까요'에 가서 고른다.
       화면이 넘어갈 때 왼쪽 바가 잠깐 번쩍이던 것도 같이 없어진다.
       되살리려면 이 블록만 지우면 된다 — 아래 폭·차례·이름표 규칙은 그대로
       남겨 뒀다(지금은 안 걸리지만, 메뉴를 되살리면 그대로 다시 산다). */
    [data-testid="stSidebar"],
    [data-testid="stSidebarNav"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapseButton"] { display: none !important; }
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
    [data-testid="stSidebarNav"] li:nth-child(7) { order: 7; }
    [data-testid="stSidebarNav"] li:nth-child(7) a p { font-size: 0 !important; }
    [data-testid="stSidebarNav"] li:nth-child(7) a p::before {
        content: "종가관찰\\A(자비스6)"; white-space: pre; line-height: 1.2;
        font-size: 1.15rem; font-weight: 800; color: #ffb020;
    }
    [data-testid="stSidebarNav"] li:nth-child(4) a p { font-size: 0 !important; }
    [data-testid="stSidebarNav"] li:nth-child(4) a p::before {
        content: "미국테마\\A(자비스3)"; white-space: pre; line-height: 1.2;
        font-size: 1.15rem;
        font-weight: 800;
        color: #ffb020;
    }
    [data-testid="stSidebarNav"] li:nth-child(5) a p { font-size: 0 !important; }
    [data-testid="stSidebarNav"] li:nth-child(5) a p::before {
        content: "한국테마\\A(자비스4)"; white-space: pre; line-height: 1.2;
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
    .j3-market-flow {
        color: #44f0a1;
        font-size: 1rem;
        font-weight: 800;
        line-height: 1.65;
    }
    /* '조건점수·시장 상황 설명'은 글이 길다. 통째로 초록에 굵게 두니 읽기 힘들었다
       (2026-08-06 사용자 지시). 본문은 흰색·보통 굵기로 두고, 중요한 곳만
       <b>로 감싸 초록으로 띄운다. */
    .j3-score-guide {
        color: #e6e6e6;
        font-size: 1rem;
        font-weight: 400;
        line-height: 1.75;
        margin-top: 0.35rem;
    }
    .j3-score-guide b { color: #44f0a1; font-weight: 800; }
    .j3-market-flow {
        margin: 1.9rem 0 0.8rem 0;
        padding: 0.75rem 1rem;
        border-left: 4px solid #44f0a1;
        background: rgba(34, 197, 94, 0.08);
        border-radius: 0.4rem;
    }
    /* ── 움직임 (2026-08-06 사용자 요청 "그냥 멋지게") ──────────────────────
       Streamlit은 누를 때마다 화면을 통째로 다시 그린다. 그래서 애니메이션은
       **짧게(0.2초)** 둔다 — 길면 클릭할 때마다 다시 재생돼 거슬린다.
       닫히는 모습은 못 만든다. 접는 순간 그 자리가 아예 안 그려지기 때문이다.
       거슬리면 이 블록만 통째로 지우면 원래대로 돌아간다. */
    /* 떠오르는 움직임(j3-rise)은 **넣었다가 뺐다**(2026-08-06). 스트림릿이 누를
       때마다 화면을 통째로 다시 그리는 탓에 표와 카드가 매번 다시 떠올라
       어지럽고 화면이 느려 보였다(상하님 실사용 지적). 다시 넣지 말 것.
       손이 닿을 때만 도는 아래 움직임은 그 문제가 없어 남긴다. */
    /* 이 화면의 **모든 단추와 접이 머리**에 같은 결을 준다(2026-08-06 사용자 지시).
       손을 올리면 살짝 뜨고 밝아지며, 누르면 눌린다. 다시 그려도 재생되지 않는
       움직임이라 클릭이 잦아도 거슬리지 않는다. */
    .stButton button, [data-testid="stExpander"] summary {
        transition: transform .12s ease-out, filter .12s ease-out,
                    box-shadow .12s ease-out, border-color .12s ease-out !important;
    }
    .stButton button:hover, [data-testid="stExpander"] summary:hover {
        transform: translateY(-2px) !important;
        filter: brightness(1.12) !important;
    }
    .stButton button:active, [data-testid="stExpander"] summary:active {
        transform: translateY(0) scale(.985) !important;
    }
    /* 위쪽 지수·ETF 칸과 게이지 상자에도 같은 결을 준다(2026-08-06 사용자 지시).
       손이 닿을 때만 도는 움직임이라 화면을 다시 그려도 재생되지 않는다. */
    .j3-top-cell, .fg-box, .j3-ndd {
        transition: transform .12s ease-out, filter .12s ease-out;
        border-radius: .6rem;
    }
    .j3-top-cell:hover, .fg-box:hover, .j3-ndd:hover {
        transform: translateY(-3px);
        filter: brightness(1.1);
    }
    /* 표 안의 종목 단추만 **옆으로** 민다 — 줄이 촘촘해 위아래로 뜨면 어지럽다.
       위 규칙보다 뒤에 둬야 이 규칙이 이긴다. */
    div[class*="st-key-j3rbf_"] button:hover,
    div[class*="st-key-j3rbw_"] button:hover,
    div[class*="st-key-j3top7_"] button:hover,
    div[class*="st-key-j3tbtn_"] button:hover,
    div[class*="st-key-j3pbf_"] button:hover,
    div[class*="st-key-j3lbtn_"] button:hover {
        transform: translateX(3px) !important;
        border-color: rgba(192,132,252,.6) !important;
        filter: none !important;
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
    /* 종목명 아래 테마 줄 — 흐린 회색이라 안 보였다(2026-08-06 사용자 지시).
       밝은 초록에 굵게. 종목명(밝은 보라)과 색이 갈려 두 줄이 구분된다. */
    .j3-stock-sub { color: #44f0a1; font-size: 0.95rem; font-weight: 800;
        margin: 0.1rem 0 0.7rem; }
    .j3-metric-row { display: flex; flex-wrap: wrap; gap: 1.6rem; margin: 0.2rem 0 0.4rem; }
    .j3-mc { min-width: 120px; }
    .j3-mc-label { color: #4da6ff; font-size: 0.92rem; font-weight: 800; }
    .j3-mc-val { font-size: 1.5rem; font-weight: 800; color: #e6e6e6; line-height: 1.25; }
    .j3-mc-sub { font-size: 0.95rem; font-weight: 800; }
    .j3-up { color: #4da6ff; }
    .j3-down { color: #ff5b5b; }
    .j3-muted { color: #9aa0aa; }
    .j3-section-title { color: #4da6ff; font-size: 1.2rem; font-weight: 800; margin: 1rem 0 0.5rem; }
    /* 제목 **앞말**은 어느 화면에서나 같은 스카이블루(#4da6ff)다 —
       「종목 선정 근거」와 「매수 심사 결과」가 같은 색이어야 한다(상하님 지시).
       **괄호 안 갈래 이름만** 위 '종목 찾기' 두 단추와 같은 색으로 칠한다
       (2026-08-14 상하님 지시 — "(신고가 눌림 전용 배점) 이 글자 부분만
       그라데이션 하라고"). 글을 보고 어느 갈래인지 눈으로 가리기 위한 것이다.
       단추는 흰 글씨를 얹으려고 어두운 쪽(#075d46·#6b2d05)에서 시작하는데 글자에
       그대로 쓰면 검은 바탕에 묻힌다. 그래서 **단추의 밝은 쪽에서 시작해 더 밝게** 간다. */
    .j3-title-tag {
        -webkit-background-clip: text;
        background-clip: text;
        -webkit-text-fill-color: transparent;
        color: transparent;
    }
    .j3-title-breakout { background-image: linear-gradient(90deg, #18bf87 0%, #8ef7cd 100%); }
    .j3-title-crash { background-image: linear-gradient(90deg, #e67813 0%, #ffd39a 100%); }
    .j3-factor-table { width: 100%; border-collapse: collapse; margin-bottom: 0.5rem; font-size: 0.95rem; }
    .j3-factor-table th { text-align: center; color: #4da6ff; font-weight: 800; padding: 0.45rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.18); }
    .j3-factor-table td { color: #44f0a1; font-weight: 700; padding: 0.4rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.06); }
    .j3-factor-table td.j3-fac-name { text-align: left; }
    /* 항목 이름 밑에 글을 붙이던 자리. **2026-08-21에 걷어냈다** — 상하님 지시
       "심사항목 밑에 하얀색 설명 빼라, 초록색 글자만 둬라". 설명은 「설명」·
       「자세히」 창에만 둔다. 규칙을 되살리려면 여기 다시 넣으면 된다. */
    .j3-factor-table td.j3-fac-val { text-align: center; }
    .j3-reason-card { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.09); border-radius: 0.55rem; padding: 0.6rem 0.75rem; height: 100%; }
    .j3-reason-title { color: #4da6ff; font-weight: 800; font-size: 0.95rem; margin-bottom: 0.25rem; }
    .j3-reason-body { color: #44f0a1; font-weight: 700; font-size: 0.9rem; line-height: 1.45; }
    /* 「이 화면 설명 보기」의 항목 카드. **중요한 한 줄만 진하게 초록**이고 나머지
       설명은 옅은 회색 보통 굵기다(2026-08-21 상하님 지적 — 초록 글이 통째로
       굵으니 가독성이 떨어진다). 맨 위 파란 상자와 같은 방식이다. */
    .j3-help-line { display: block; color: #44f0a1; font-weight: 800;
        font-size: .93rem; line-height: 1.5; margin-bottom: .2rem; }
    .j3-help-detail { display: block; color: #b9c0cb; font-weight: 400;
        font-size: .89rem; line-height: 1.62; }
    .j3-help-detail b { color: #e6e6e6; font-weight: 800; }
    /* 같은 카드 안의 '이건 다른 자다' 같은 곁글. 본문보다 작고 흐리게 둬서
       숫자를 가리지 않게 한다(2026-08-07). */
    .j3-reason-sub { color: #9aa0aa; font-weight: 600; font-size: 0.8rem;
        line-height: 1.42; margin-top: 0.3rem; }
    .j3-reason-sub b { color: #cfd4da; }
    .j3-chart-title { color: #e6e6e6; font-weight: 800; font-size: 1rem; margin-bottom: 0.1rem; }
    /* 맨 위 큰 차트의 제목 — 아래 작은 셋과 구분되게 하늘색으로 조금 크게
       (2026-08-07 상하님 지시 "일봉 클릭하면 화면 위에 크게"). */
    .j3-chart-big-title { color: #7cc7ff; font-size: 1.14rem; margin: .1rem 0 .25rem; }
    /* '일봉 크게 · 주봉 크게 · 월봉 크게' 고르는 단추. 지금 크게 보고 있는 것은
       ● 를 앞에 붙이고 밝게 칠한다 — 어느 것을 보고 있는지 단추만 봐도 알게. */
    div[class*="st-key-j3_bundle_pick_"] button {
        background: rgba(255,255,255,.04) !important;
        border: 1px solid rgba(255,255,255,.18) !important;
        border-radius: .45rem !important;
        min-height: 0 !important; padding: .2rem .6rem !important;
    }
    div[class*="st-key-j3_bundle_pick_"] button p {
        font-size: .86rem !important; font-weight: 700 !important; color: #b9c0c8 !important;
    }
    div[class*="st-key-j3_bundle_pick_"] button:hover {
        border-color: #7cc7ff !important; background: rgba(124,199,255,.10) !important;
    }
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
    /* 겨자색 상자 — **글 전체를 진하게 하지 않는다**(2026-08-07 상하님 지시).
       전부 굵으면 어디가 중요한지 알 수 없다. 바탕글은 보통 굵기로 두고,
       숫자와 꼭 봐야 할 말만 굵게·색으로 뽑는다. */
    .j3-reason-mustard { background: rgba(234,179,8,0.12); border: 1px solid rgba(234,179,8,0.42); color: #e6c34a; border-radius: 0.5rem; padding: 0.6rem 0.8rem; font-weight: 500; line-height: 1.62; }
    /* 오른 값은 스카이블루, 빠진 값은 붉은색. 겨자색 바탕이라 흐린 색은 묻힌다 —
       진한 색으로 뽑는다(2026-08-07 지시 "색깔 진하게"). */
    .j3-reason-mustard .j3-mn-up { color: #4fb8ff; font-weight: 900; }
    .j3-reason-mustard .j3-mn-down { color: #ff4d4f; font-weight: 900; }
    .j3-reason-mustard .j3-mn-key { color: #ffd479; font-weight: 900; }
    /* 점수(66.0/70)는 **초록**이다 — 오르내림(파랑·빨강)·중요한 말(노랑)과
       한눈에 갈라진다(2026-08-21 상하님 지시). */
    .j3-reason-mustard .j3-mn-score { color: #44f0a1; font-weight: 900; }
    .j3-chart-heading { margin-top: 1.6rem; font-size: 1.15rem; font-weight: 800; color: #e6e6e6; }
    .j3-theme-badge { display: inline-block; background: rgba(255,176,32,0.16); color: #ffb020; border: 1px solid #ffb020; border-radius: 0.5rem; padding: 0.15rem 0.7rem; font-weight: 800; font-size: 1.05rem; margin-right: 0.4rem; }
    /* 제목은 한 줄로 세우고 내용은 그 아래에 둔다(2026-08-06 사용자 지시 — 제목
       뒤에 ' : '를 붙여 한 줄로 이어 붙이던 것을 뺐다). */
    .j3-flow-label { color: #44f0a1; font-weight: 800; margin-bottom: .25rem; }
    .j3-flow-body { color: #4da6ff; font-weight: 800; }
    .j3-action-label { color: #4da6ff; font-weight: 800; margin-bottom: .25rem; }
    .j3-action-posture { color: #ff5b5b; font-weight: 800; }
    .j3-action-detail { color: #ff9d3b; font-weight: 800; margin-top: .15rem; }
    .j3-top-row { display: flex; gap: 2rem; flex-wrap: wrap; margin-bottom: 0.3rem;
        align-items: center; }
    .j3-top-cell { min-width: 150px; padding-left: 1.6rem; position: relative; }
    /* **손을 올린 칸을 통째로 위로 올린다**(2026-08-06 상하님 지적 "화면이 겹쳐진다").
       칸마다 position:relative라 뒤에 오는 칸이 앞 칸의 떠 있는 그림 위에 덮여
       그려졌다. 팝업에만 z-index를 줘도 소용없다 — 칸 자체를 올려야 한다. */
    .j3-top-cell:hover { z-index: 50; }
    /* 나스닥 고점 대비 낙폭 한 줄 — 위 지수 칸 바로 아래(2026-08-01).
       막대는 0%에서 25%까지이고, 세로 눈금이 12% 문턱 자리다. */
    .j3-ndd { border: 1px solid rgba(255,255,255,.14); border-radius: 10px;
        padding: .5rem .8rem; margin: .1rem 0 .6rem; background: rgba(255,255,255,.03); }
    .j3-ndd-head { display: flex; align-items: baseline; gap: .5rem; flex-wrap: wrap; }
    .j3-ndd-title { color: #c084fc; font-weight: 850; }
    .j3-ndd-val { font-size: 1.45rem; font-weight: 900; }
    .j3-ndd-state { font-size: .95rem; font-weight: 800; }
    /* 막대 한가운데가 전고점이다(2026-08-09 상하님 지시). 왼쪽 끝은 고점에서
       25% 아래, 오른쪽 끝은 고점 위 25%다. 채워진 길이가 길수록 고점에 가깝다 —
       예전에는 길수록 많이 빠졌다는 뜻이라 거꾸로 읽혔다. */
    .j3-ndd-bar { position: relative; height: 10px; border-radius: 5px;
        background: rgba(255,255,255,.10); margin: .35rem 0 .2rem; overflow: hidden; }
    .j3-ndd-fill { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 5px;
        background: linear-gradient(90deg, #ffd166 0%, #44f0a1 100%);
        transform-origin: left center; }
    /* 문턱(사는 자리) 눈금 */
    .j3-ndd-mark { position: absolute; top: -3px; bottom: -3px; width: 2px;
        background: #ffffff; opacity: .85; }
    /* 한가운데 = 전고점. 문턱 눈금과 구별되게 굵고 밝게 세운다. */
    .j3-ndd-center { position: absolute; left: 50%; top: -4px; bottom: -4px; width: 3px;
        margin-left: -1.5px; background: #c084fc; border-radius: 2px;
        box-shadow: 0 0 6px rgba(192,132,252,.7); }
    .j3-ndd-scale { display: flex; justify-content: space-between;
        color: #8a9099; font-size: .78rem; font-weight: 700; margin-bottom: .25rem; }
    .j3-ndd-scale-mid { color: #c084fc; }
    /* 손을 대면 막대가 **왼쪽에서 오른쪽으로 다시 차오른다**(2026-08-09 지시).
       길이(width)가 아니라 scaleX를 쓰므로 값이 얼마든 같은 규칙 하나로 된다.
       손가락으로 눌렀을 때도 돌게 :active를 같이 둔다 — 폰은 hover가 없다.
       0.55초는 **너무 빨랐다**(2026-08-09 상하님 지적). 1.4초로 늦추고, 끝에서
       급히 멈추지 않게 ease-in-out으로 바꿨다 — 차오르는 과정이 눈에 보여야
       '어디까지 왔나'가 읽힌다. */
    @keyframes j3-ndd-grow { from { transform: scaleX(0); } to { transform: scaleX(1); } }
    .j3-ndd:hover .j3-ndd-fill, .j3-ndd:active .j3-ndd-fill {
        animation: j3-ndd-grow 1.4s cubic-bezier(.33,0,.2,1);
    }
    @media (prefers-reduced-motion: reduce) {
        .j3-ndd:hover .j3-ndd-fill, .j3-ndd:active .j3-ndd-fill { animation: none; }
    }
    .j3-ndd-sub { color: #9aa0aa; font-size: 1rem; font-weight: 700; }
    .j3-ndd-note { color: #aeb6c2; font-size: .92rem; margin-top: .3rem; line-height: 1.55; }
    .j3-ndd-key { color: #4da6ff; font-weight: 850; }
    /* 검색 종목 배점 안내 (2026-08-28) — 표 바로 위에 붙는다. */
    .j3-score-origin { background: rgba(192,132,252,0.10);
        border: 1px solid rgba(192,132,252,0.42); border-radius: .5rem;
        padding: .55rem .75rem; margin: .1rem 0 .5rem; color: #d8c4f5;
        font-size: .95rem; font-weight: 600; line-height: 1.62; }
    .j3-score-origin b { color: #f0e3ff; }
    .j3-theme-open-guide { color: #c084fc; font-size: 1.08rem; font-weight: 850;
        margin: .15rem 0 .65rem; text-shadow: 0 0 8px rgba(192,132,252,.18); }
    /* 오늘 1~5위 테마를 한 줄로 적는다(2026-08-14 상하님 지시) — 순위표를 닫아
       두셔도 이 한 줄은 보인다. 크기는 위 보라색 안내와 같게, 색만 초록이다. */
    .j3-theme-top5 { color: #44f0a1; font-size: 1.08rem; font-weight: 850;
        margin: .15rem 0 .5rem; text-shadow: 0 0 8px rgba(68,240,161,.18); }
    /* 테마 이름만 연한 붉은색(2026-08-14 상하님 지시) — 초록 문장 안에서 이름이
       바로 눈에 들어온다. 등락률의 붉은색(#ff5b5b)보다 연하게 해 헷갈리지 않는다. */
    .j3-theme-top5 .j3-top5-names { color: #ff9d9d;
        text-shadow: 0 0 8px rgba(255,157,157,.20); }
    .j3-leader-head-gap { height: .55rem; }
    .j3-top-label { color: #9aa0aa; font-size: 1rem; font-weight: 800; letter-spacing: -.01em; }
    .j3-top-val { font-size: 1.7rem; font-weight: 800; line-height: 1.2; }
    .j3-top-sub { font-size: 0.95rem; font-weight: 700; }
    /* 지수·ETF 여섯 칸(S&P 500·나스닥 종합·다우존스·나스닥 100·SPY·QQQ)만 따로
       입히는 옷이다(2026-08-01 사용자 지시): 이름은 초록에 한 치수 크게,
       숫자는 한 치수 작게, 등락률은 한 치수 크게, '장 마감 기준'은 한 치수 작게.
       '시장 상황'·게이지 칸은 그대로 두라고 했으므로 j3-top-*를 건드리지 않고
       전용 클래스로만 건다. 이 규칙은 위 j3-top-* 뒤에 와야 색이 덮인다.
       폰·태블릿(≤1200px) 크기는 mobile_ui의 TOP_ROW_CSS가 나중에 실려 이긴다 —
       규칙 12대로 폰 크기는 계속 그쪽이 정한다. */
    .j3-idx-label { color: #44f0a1; font-size: 1.15rem; }
    .j3-idx-val { font-size: 1.5rem; }
    .j3-idx-sub { font-size: 1.1rem; }
    .j3-idx-note { font-size: 0.82rem; }
    /* SPY·QQQ는 그림이 둘이라 칸을 조금 넓게 잡는다. */
    .j3-idx-wide { min-width: 240px; }
    /* ── 종목 차트 넷을 한 판에 (2026-08-28 상하님 지시) ───────────────────
       "스마트폰 기준으로 당일·일봉 차트 같은 선상에 2개 해 주고 그 밑에 주·월봉."
       스트림릿 칸은 폰에서 위아래로 쌓여 한 줄에 하나가 되므로 CSS 격자로 둔다 —
       맨 위 지수 칸과 같은 방식이다. 노트북에서는 넷이 한 줄에 선다. */
    .j3-chart-grid { display: grid; gap: .7rem; margin: .3rem 0 .6rem;
        grid-template-columns: repeat(2, minmax(0, 1fr)); }
    @media (min-width: 1201px) {
        .j3-chart-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
    }
    .j3-chart-box { background: rgba(255,255,255,.03);
        border: 1px solid rgba(255,255,255,.14); border-radius: 12px;
        padding: .45rem .55rem .35rem; min-width: 0; }
    .j3-chart-name { color: #9dccff; font-size: .95rem; font-weight: 800;
        margin-bottom: .15rem; }
    .j3-chart-when { color: #7d8798; font-size: .72rem; font-weight: 700;
        margin-top: .2rem; overflow: hidden; text-overflow: ellipsis;
        white-space: nowrap; }
    /* 폰에서 낮추는 규칙은 mobile_ui 에 있다(규칙 12) — 여기 두면 태블릿·PC까지
       같이 바뀔 위험이 있고, 폰 규칙이 두 군데로 갈린다. */
    .j3-pretty-chart { display: block; width: 100%; height: 132px;
        border-radius: 8px; background: rgba(0,0,0,.22); }
    /* ── 시장 현황(업종 지도) 2026-08-28 ────────────────────────────────
       상자 자리는 서버가 계산해 %로 준다. 칸의 가로:세로를 CSS에서 못박아야
       그 계산과 화면이 어긋나지 않는다 — 비율이 달라지면 상자가 찌그러진다.
       글자 크기는 지도 칸의 font-size 하나만 바꾸면 상자 글자가 다 따라온다. */
    .j3-sector-map { flex: 1 1 100%; max-width: 620px; font-size: 13px; }
    .j3-sector-sub { color: #8f9bb0; font-size: 0.86em; font-weight: 700; margin: .1rem 0 .35rem; }
    .j3-sector-grid { position: relative; width: 100%; aspect-ratio: 100 / 58;
        border-radius: 10px; overflow: hidden; background: rgba(255,255,255,.04); }
    .j3-sector-tile { position: absolute; box-sizing: border-box;
        border: 1px solid rgba(2,11,30,.85); border-radius: 4px;
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        gap: .1em; overflow: hidden; text-align: center; color: #f4f8ff; padding: 2px; }
    .j3-sector-name { font-weight: 800; line-height: 1.15; }
    .j3-sector-pct { font-weight: 800; line-height: 1.1; opacity: .95; }
    .j3-sector-tile.big .j3-sector-name { font-size: 1.15em; }
    .j3-sector-tile.big .j3-sector-pct { font-size: 1.05em; }
    .j3-sector-tile.mid .j3-sector-name { font-size: 0.92em; }
    .j3-sector-tile.mid .j3-sector-pct { font-size: 0.86em; }
    .j3-sector-tile.small .j3-sector-name { font-size: 0.74em; }
    .j3-sector-bar { display: flex; height: 7px; border-radius: 4px; overflow: hidden;
        margin: .4rem 0 .25rem; background: rgba(255,255,255,.08); }
    .j3-sector-bar span { display: block; height: 100%; }
    .j3-sector-foot { display: flex; flex-wrap: wrap; gap: .1rem .7rem;
        font-size: 0.86em; font-weight: 800; }
    .j3-sector-note { color: #7d8798; font-weight: 700; }
    .j3-sector-wait { color: #9aa0aa; font-weight: 700; padding: .6rem 0; }
    .j3-idx-charts { display: flex; gap: 0.5rem; flex-wrap: wrap; }
    /* 손을 올리면 '일봉 6개월'이 **오른쪽에서 밀려 들어와 같은 자리에서 바뀐다**
       (2026-08-06 상하님 지시 "오른쪽으로 하되 겹치지 않게").
       여기까지 온 과정 — ① 칸 아래로 펼쳤더니 아래 화면이 통째로 밀려 어지러웠고,
       ② 옆에 띄웠더니 이웃 칸을 덮었다. 같은 자리에서 바꾸면 **밀리지도 덮지도**
       않는다. 자리를 새로 만들지 않기 때문이다.
       들어올 때는 빠르게(.24초), 나갈 때는 천천히(.5초). */
    .j3-idx-swap { position: relative; overflow: hidden; border-radius: .5rem; }
    .j3-idx-swap > div { transition: opacity .5s ease, transform .5s ease; }
    .j3-idx-swap .j3-idx-now { opacity: 1; transform: translateX(0); }
    .j3-idx-swap .j3-idx-more {
        position: absolute; inset: 0;
        opacity: 0; transform: translateX(26px); pointer-events: none;
    }
    /* '일봉 6개월' 그림에는 스카이블루 테두리를 두른다(2026-08-06 사용자 지시) —
       늘 보이는 '당일' 그림과 한눈에 갈린다. */
    .j3-idx-more svg {
        border: 2px solid #4da6ff !important;
        border-radius: .5rem;
        box-shadow: 0 0 10px rgba(77,166,255,.28);
    }
    /* ── 손가락으로도 되게(2026-08-07 상하님 지적) ────────────────────────
       폰에서 한 번 누르면 '일봉 6개월'이 나오는데 **다시 눌러도 당일로 안 돌아왔고**,
       태블릿은 손으로는 아예 안 바뀌었다. 마우스 전용 규칙(:hover)만 있었기 때문이다.
       손으로 누른 자리는 브라우저가 '계속 올려 둔 것'으로 붙잡아 둬서(sticky hover)
       두 번째 누름이 먹지 않는다.

       그래서 **숨긴 체크상자**를 하나 두고 그림 위를 덮은 label을 누르면 켜졌다
       꺼졌다 하게 한다. 자바스크립트 없이 되고, 누를 때마다 확실히 뒤집힌다.
       :hover 규칙은 **마우스가 주된 장치일 때만** 남긴다 — 안 그러면 손으로 눌러
       붙잡힌 hover와 체크상자가 서로 싸워 다시 안 돌아온다. */
    .j3-idx-tap { position: absolute; opacity: 0; width: 0; height: 0; margin: 0; }
    .j3-idx-tapzone { position: absolute; inset: 0; z-index: 3; cursor: pointer; }
    .j3-idx-swap .j3-idx-tap:checked ~ .j3-idx-now {
        opacity: 0; transform: translateX(-26px);
        transition: opacity .24s ease-out, transform .24s ease-out;
    }
    .j3-idx-swap .j3-idx-tap:checked ~ .j3-idx-more {
        opacity: 1; transform: translateX(0);
        transition: opacity .24s ease-out, transform .24s ease-out;
    }
    @media (hover: hover) and (pointer: fine) {
        .j3-top-cell:hover .j3-idx-swap .j3-idx-now {
            opacity: 0; transform: translateX(-26px);
            transition: opacity .24s ease-out, transform .24s ease-out;
        }
        .j3-top-cell:hover .j3-idx-swap .j3-idx-more {
            opacity: 1; transform: translateX(0);
            transition: opacity .24s ease-out, transform .24s ease-out;
        }
    }
    .j3-idx-cap { color: #9aa0aa; font-size: 0.78rem; font-weight: 700; text-align: center; }
    /* '일봉 6개월'은 손을 올려야 보이는 그림이라 이름을 스카이블루로 띄운다
       (2026-08-06 사용자 지시) — 늘 보이는 '당일'과 구분된다. */
    .j3-idx-cap-daily { color: #4da6ff; font-weight: 800; }
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
    /* 제목이 두 줄이 되면 한 줄짜리와 밑줄이 어긋났다(2026-07-25 사용자 지적).
       모두 같은 높이를 갖고 글자는 아래에 붙여 밑줄을 한 줄로 맞춘다. */
    .j3-th-head { display: flex; align-items: flex-end; justify-content: center;
        min-height: 3.1rem; text-align: center; color: #9aa0aa; font-weight: 800; font-size: 0.92rem;
        padding: 0.45rem 0 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.22); }
    /* 테마명 버튼 행과 나머지 HTML 칸의 세로 라인을 맞춘다(2026-07-22 사용자 지시:
       "Line 일치시킬 것") — 양쪽 다 같은 고정 높이(2.5rem)에 수직 가운데 정렬. */
    .j3-td { text-align: center; color: #e6e6e6; font-size: 0.92rem; padding: 0;
        border-bottom: 1px solid rgba(255,255,255,0.06); min-height: 2.5rem;
        display: flex; align-items: center; justify-content: center; }
    .j3-td > .j3-barwrap { width: 100%; }
    /* 좁은 화면에서는 칸을 쥐어짜 글자를 자르는 대신 표를 원래 폭으로 두고
       손가락으로 옆으로 민다(2026-07-25 사용자 지시). 화면 전체는 안 밀린다. */
    /* 종목표(j3_leader_table)도 이름을 누를 수 있게 칸 방식으로 바꾸면서
       이미 폰·태블릿에서 잘 도는 위 두 표와 똑같은 규칙에 얹었다(2026-07-29). */
    /* 순위 7 표도 같은 규칙에 얹는다(2026-08-01 사용자 지시) — 폰에서 한 종목이
       여섯 줄로 쌓이던 것을, 나머지 세 표처럼 옆으로 밀어서 보게 한다.
       설명서 두 갈래 표(j3_rulebook_table)도 같은 규칙에 얹는다 — 빠뜨렸더니
       폰에서 순위·종목이 따로 쌓이고 값이 서로 겹쳐 찍혔다(2026-08-01 캡처).
       **새 표를 만들면 반드시 이 세 목록에 다 넣는다.** */
    /* '11위~20위 더 보기'로 접은 자리(j3_theme_rest·j3_rulebook_rest)도 같은 규칙을
       받는다. 접이(st.expander) 자체는 이 상자들 밖에 있어서, 빠뜨리면 접힌 쪽만
       칸이 세로로 쌓여 위 표와 딴판이 된다(2026-08-09 상하님 캡처).
       한국테마는 테마표만 이미 이렇게 감싸 두었다 — 급락 표는 거기도 빠져 있었다. */
    .st-key-j3_pullback_table,
    .st-key-j3_theme_rest,
    .st-key-j3_rulebook_rest,
    .st-key-j3_leader_table,
    .st-key-j3_top7_table,
    .st-key-j3_rulebook_table,
    .st-key-j3_theme_table { overflow-x: auto; -webkit-overflow-scrolling: touch; }
    /* ── 접은 자리(11위~20위)가 옆으로 안 밀리던 것 (2026-08-19 상하님 지적) ──
       상하님 — "첫 번째 캡처에서 옆으로 옮기면 두 번째 캡처처럼 오류난다."

       **원인** — 스트림릿이 접이(st.expander) 안쪽 <details>에 `overflow: hidden`을
       걸어 둔다. 표는 1180px인데 그 상자가 968px에서 **잘라 버려서**, 우리가
       바깥에 걸어 둔 `overflow-x: auto`까지 넓이가 전해지지 않는다. 그래서 상자는
       "밀 것이 없다"고 여기고(scrollWidth 968 = clientWidth 968) 표만 삐져나온다.
       1~10위 표는 접이가 아니라서 멀쩡했다 — 접은 쪽만 깨져 있었다.

       **고침** — 자르던 그 <details>를 **미는 상자로 바꾼다.** 접이 테두리는
       제자리에 있고 표만 그 안에서 옆으로 움직인다.
       클래스 이름(st-emotion-cache-…)은 스트림릿 판이 바뀌면 달라지므로 쓰지 않는다
       (2026-07-18에 판 차이로 한 번 데었다). 지금 판은 <details>인데 판이 바뀌면
       <div>일 수 있어 **둘 다** 짚어 둔다. */
    .st-key-j3_rulebook_rest [data-testid="stExpander"] > details,
    .st-key-j3_rulebook_rest [data-testid="stExpander"] > div,
    .st-key-j3_theme_rest [data-testid="stExpander"] > details,
    .st-key-j3_theme_rest [data-testid="stExpander"] > div {
        overflow-x: auto !important;
        -webkit-overflow-scrolling: touch;
    }
    /* ── 표 밑 미는 막대를 **두껍고 눈에 띄게** (2026-08-19 상하님 지시) ────
       상하님 — "밑에 바 두껍게 해야 마우스로 찍어 옆으로 보내지."

       **`::-webkit-scrollbar`로는 안 된다.** 요즘 크롬은 표준 속성
       (`scrollbar-width`·`scrollbar-color`)이 있으면 웹킷 쪽을 **무시한다.**
       실제로 넣어 보니 두께가 10px 그대로였다(2026-08-19 실측).
       표준 속성으로 바꾸니 **10px → 15px**이 되고 색도 들어간다.

       옛 사파리를 위해 웹킷 쪽도 남겨 둔다 — 표준을 아는 브라우저는 이쪽을
       거들떠보지 않으므로 같이 있어도 탈이 없다. */
    .st-key-j3_pullback_table,
    .st-key-j3_theme_rest,
    .st-key-j3_rulebook_rest,
    .st-key-j3_leader_table,
    .st-key-j3_top7_table,
    .st-key-j3_rulebook_table,
    .st-key-j3_theme_table,
    .st-key-j3_rulebook_rest [data-testid="stExpander"] > details,
    .st-key-j3_theme_rest [data-testid="stExpander"] > details {
        scrollbar-width: auto;
        scrollbar-color: rgba(124, 200, 255, .70) rgba(255, 255, 255, .08);
    }
    .st-key-j3_pullback_table::-webkit-scrollbar,
    .st-key-j3_theme_rest::-webkit-scrollbar,
    .st-key-j3_rulebook_rest::-webkit-scrollbar,
    .st-key-j3_leader_table::-webkit-scrollbar,
    .st-key-j3_top7_table::-webkit-scrollbar,
    .st-key-j3_rulebook_table::-webkit-scrollbar,
    .st-key-j3_theme_table::-webkit-scrollbar,
    .st-key-j3_rulebook_rest [data-testid="stExpander"] > details::-webkit-scrollbar,
    .st-key-j3_theme_rest [data-testid="stExpander"] > details::-webkit-scrollbar {
        height: 15px;
        background: rgba(255, 255, 255, .08);
    }
    .st-key-j3_pullback_table::-webkit-scrollbar-thumb,
    .st-key-j3_theme_rest::-webkit-scrollbar-thumb,
    .st-key-j3_rulebook_rest::-webkit-scrollbar-thumb,
    .st-key-j3_leader_table::-webkit-scrollbar-thumb,
    .st-key-j3_top7_table::-webkit-scrollbar-thumb,
    .st-key-j3_rulebook_table::-webkit-scrollbar-thumb,
    .st-key-j3_theme_table::-webkit-scrollbar-thumb,
    .st-key-j3_rulebook_rest [data-testid="stExpander"] > details::-webkit-scrollbar-thumb,
    .st-key-j3_theme_rest [data-testid="stExpander"] > details::-webkit-scrollbar-thumb {
        background: rgba(124, 200, 255, .70);
        border-radius: 8px;
        min-width: 60px;
    }
    @media (max-width: 1200px) {
        .st-key-j3_pullback_table [data-testid="stHorizontalBlock"] {
            flex-wrap: nowrap !important; min-width: 1150px;
        }
        .st-key-j3_rulebook_rest [data-testid="stHorizontalBlock"] {
            flex-wrap: nowrap !important; min-width: 1180px;
        }
        .st-key-j3_theme_rest [data-testid="stHorizontalBlock"],
        .st-key-j3_leader_table [data-testid="stHorizontalBlock"],
        .st-key-j3_top7_table [data-testid="stHorizontalBlock"],
        .st-key-j3_theme_table [data-testid="stHorizontalBlock"] {
            flex-wrap: nowrap !important; min-width: 900px;
        }
        /* 상승장·급락 표는 2026-08-06에 '점수' 칸이 하나 늘어 아홉 칸이 됐다.
           900px로는 글자가 짓눌려 1000px로 넓혔고, 2026-08-07에 급락 낙폭이
           세 칸으로 갈리면서 열한 칸이 돼 1180px로 다시 넓힌다(상하님 지시
           "칸을 두 개 더"). 폰·태블릿에서는 어차피 옆으로 밀어서 본다. */
        .st-key-j3_rulebook_table [data-testid="stHorizontalBlock"] {
            flex-wrap: nowrap !important; min-width: 1180px;
        }
        .st-key-j3_pullback_table [data-testid="stColumn"],
        .st-key-j3_theme_rest [data-testid="stColumn"],
        .st-key-j3_rulebook_rest [data-testid="stColumn"],
        .st-key-j3_leader_table [data-testid="stColumn"],
        .st-key-j3_top7_table [data-testid="stColumn"],
        .st-key-j3_rulebook_table [data-testid="stColumn"],
        .st-key-j3_theme_table [data-testid="stColumn"] { min-width: 0 !important; }
    }
    .j3-td { white-space: nowrap; }
    /* 설명서 두 갈래 표의 칸은 제 폭 안에서 잘린다 — 테마 이름이 길어 옆 칸을
       덮던 것을 막는다(2026-08-01, 한국테마와 같은 처리). */
    .st-key-j3_rulebook_table .j3-td { overflow: hidden; }
    .j3-rb-clip {
        display: block; max-width: 100%;
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    /* 상승장 후보표는 급락표보다 칸이 적다. 공통 1180px 폭을 그대로 쓰면
       노트북·태블릿·폰 모두 항목 사이가 불필요하게 벌어지므로 이 표만 별도 폭을 쓴다. */
    .st-key-j3_swing_table,
    .st-key-j3_swing_rest {
        max-width: 1080px;
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
    }
    .st-key-j3_swing_rest [data-testid="stExpander"] > details,
    .st-key-j3_swing_rest [data-testid="stExpander"] > div {
        overflow-x: auto !important;
        -webkit-overflow-scrolling: touch;
    }
    .st-key-j3_swing_table .j3-td,
    .st-key-j3_swing_rest .j3-td { overflow: hidden; }
    /* ── 표를 한 덩이로 그릴 때 줄이 어긋나지 않게 (2026-08-26) ─────────────────
       표 한 벌에 칸을 한 번만 만들고 값들을 세로로 쌓으면, **옆 칸의 단추와
       높이가 정확히 같아야** 줄이 맞는다. 실측으로 어긋남을 잡았다 —
       테마 표의 단추는 43.2px(2.7rem)인데 값 칸은 40px이라 줄마다 3.2px씩
       밀려 열 줄이면 30px가 어긋났다.
       그래서 단추와 값 칸을 **같은 높이로 못박는다.** 43.2px 은 테마 표 단추의
       지금 높이 그대로다 — 보이는 모양은 안 바뀐다. 폰 375 · 태블릿 800 ·
       노트북 1400 모두 같은 값이었다. */
    .st-key-j3_theme_table .j3-td,
    .st-key-j3_theme_rest .j3-td,
    .st-key-j3_top7_table .j3-td { min-height: 2.7rem; }
    .st-key-j3_theme_table div[class*="st-key-j3tbtn_"] button,
    .st-key-j3_theme_rest div[class*="st-key-j3tbtn_"] button,
    .st-key-j3_top7_table div[class*="st-key-j3top7_"] button {
        height: 2.7rem !important;
        min-height: 2.7rem !important;
    }
    /* ── 접이칸이 폰에서 느리게 열리던 것 (2026-08-26 상하님 지적) ──────────────
       상하님 — "관찰만 조건을 다 못 넘은 15개 보기, 클릭하면 너무 느리게 열린다.
       로딩 걸린다."
       실측 — 이 접이칸을 눌러도 **서버에는 한 번도 안 간다**(도는 중 표시 0번).
       느린 것은 브라우저다. 접이칸 안에 화면 조각이 673개 들어 있고, 열리는
       순간 그것을 한꺼번에 자리 잡아 그려야 한다. 노트북은 5ms 만에 하지만
       폰은 훨씬 오래 걸려 손가락이 멈춘 것처럼 느껴진다.
       content-visibility 는 **화면 밖에 있는 줄은 자리만 잡고 안 그리라**는
       뜻이다. 열 때는 눈에 보이는 두세 줄만 그리고, 나머지는 굴려 내려갈 때
       그린다. contain-intrinsic-size 는 안 그린 줄의 어림 높이라 굴림막대가
       요동치지 않는다.
       값·점수·판정은 건드리지 않는다 — 그리는 시점만 미룬다. */
    /* **앞 여덟 줄은 미루지 않는다** (2026-08-26 상하님 지적 — "종목 1번부터
       여전히 순서대로 천천히 열린다"). 모든 줄을 미루면 폰 한 화면에 들어오는
       줄까지 하나씩 나타나 그것이 눈에 띈다. 머리글 + 일곱 줄은 한꺼번에 그리고,
       화면 밖에 있는 아홉 번째부터만 미룬다. 줄들은 모두 형제라 차례로 셀 수 있다
       (실측 — 관찰만 표는 머리글 1 + 줄 15 = 형제 16개). */
    .st-key-j3_swing_rest [data-testid="stExpander"] [data-testid="stLayoutWrapper"]:nth-child(n+9) > [data-testid="stHorizontalBlock"],
    .st-key-j3_theme_rest [data-testid="stExpander"] [data-testid="stLayoutWrapper"]:nth-child(n+9) > [data-testid="stHorizontalBlock"],
    .st-key-j3_rulebook_rest [data-testid="stExpander"] [data-testid="stLayoutWrapper"]:nth-child(n+9) > [data-testid="stHorizontalBlock"] {
        content-visibility: auto;
        contain-intrinsic-size: auto 46px;
    }
    /* 20개 테마 순위표도 화면 전체를 억지로 채우지 않는다. 가장 긴 테마명인
       「유전체·정밀의료」가 한 칸에 들어가는 폭을 기준으로 간격을 줄인다. */
    .st-key-j3_theme_table,
    .st-key-j3_theme_rest { max-width: 1200px; }
    @media (max-width: 1200px) {
        .st-key-j3_swing_table [data-testid="stHorizontalBlock"],
        .st-key-j3_swing_rest [data-testid="stHorizontalBlock"] {
            flex-wrap: nowrap !important;
            min-width: 760px;
        }
        .st-key-j3_swing_table [data-testid="stColumn"],
        .st-key-j3_swing_rest [data-testid="stColumn"] { min-width: 0 !important; }
        .st-key-j3_theme_table [data-testid="stHorizontalBlock"],
        .st-key-j3_theme_rest [data-testid="stHorizontalBlock"] {
            min-width: 800px;
        }
    }
    /* 급락 표의 낙폭은 **칸 셋**이다(2026-08-07 상하님 지시 "칸을 두 개 더").
       처음에는 한 칸에 한 줄로 붙였다가 잘려서 세 줄로 겹쳐 놨는데, 그것도
       빽빽하다고 해서 아예 칸을 나눴다. 칸 이름이 곧 그 숫자의 뜻이다.
       (칸 이름 문자열은 여기 적지 않는다 — 이 CSS는 화면에 markdown으로
        실려 나가서, 적어 두면 '그 이름이 화면에 있나' 보는 시험이 이 주석을
        먼저 집는다. 2026-08-07 실제로 걸렸다. 이름은 drop_heads에 있다.) */
    /* 구역 맨 아래 닫기 단추 — 위 여는 단추보다 작고 조용하게(2026-08-01 지시).
       폰에서 구역 끝까지 내려갔을 때 그 자리에서 접으라고 둔 것이라,
       눈에 띄어 화면을 어지럽히면 안 된다. */
    div[class*="st-key-close_"] button {
        background: transparent !important;
        border: 1px solid rgba(255,255,255,.22) !important;
        border-radius: .45rem !important;
        min-height: 0 !important;
        padding: .18rem .7rem !important;
        width: auto !important;
        box-shadow: none !important;
    }
    div[class*="st-key-close_"] button:hover {
        background: rgba(255,255,255,.07) !important;
        border-color: rgba(255,255,255,.4) !important;
    }
    div[class*="st-key-close_"] button p {
        color: #9aa0aa !important;
        font-size: .82rem !important;
        font-weight: 700 !important;
        margin: 0 !important;
        white-space: nowrap !important;
    }
    div[class*="st-key-close_"] { margin: .1rem 0 .8rem; }
    /* 테마 종목 화면 닫기 — 기존 작은 크기는 유지하고 경고형 붉은 옷만 입힌다. */
    div[class*="st-key-close_j3_theme_panel_open"] button {
        background: linear-gradient(90deg, #7f1d1d 0%, #b4232c 52%, #ef4b55 100%) !important;
        border-color: transparent !important;
        box-shadow: 0 0 0 1px rgba(239,75,85,.12) !important;
    }
    div[class*="st-key-close_j3_theme_panel_open"] button:hover {
        background: linear-gradient(90deg, #991b1b 0%, #c72d36 52%, #ff5964 100%) !important;
        border-color: transparent !important;
    }
    div[class*="st-key-close_j3_theme_panel_open"] button p {
        color: #ffffff !important;
        font-size: .82rem !important;
        font-weight: 850 !important;
    }
    /* 눌림목 찾기 버튼 — 순위 7 단추와 같은 모양(글자만큼만)에 진한 푸른색
       그라데이션(2026-07-30 사용자 지시). 한국테마와 같은 모양이다. */
    div[class*="st-key-j3_pullback_find"] button {
        background: linear-gradient(90deg, #0b2a4a 0%, #123a63 38%, #1d6fc4 100%) !important;
        border: none !important;
        border-radius: .5rem !important;
        min-height: 3rem !important;
        box-shadow: 0 2px 10px rgba(29,111,196,.25) !important;
    }
    div[class*="st-key-j3_pullback_find"] button:hover {
        background: linear-gradient(90deg, #0e3559 0%, #164876 38%, #2a86e0 100%) !important;
    }
    /* 설명서 두 갈래 단추(2026-08-01) — 눌림목 찾기와 같은 모양에 색만 다르게.
       상승장은 초록, 급락 반등장은 주황. 어느 갈래를 보고 있는지 색으로 안다. */
    div[class*="st-key-j3_pullback_breakout"] button {
        background: linear-gradient(90deg, #063b2c 0%, #0b5137 38%, #12a06a 100%) !important;
        border: none !important; border-radius: .5rem !important;
        min-height: 3rem !important;
        box-shadow: 0 2px 10px rgba(18,160,106,.25) !important;
    }
    div[class*="st-key-j3_pullback_crash"] button {
        background: linear-gradient(90deg, #4a2408 0%, #7a3c0d 38%, #e07f1f 100%) !important;
        border: none !important; border-radius: .5rem !important;
        min-height: 3rem !important;
        box-shadow: 0 2px 10px rgba(224,127,31,.25) !important;
    }
    /* 「20개 테마 실시간 순위 보기」 — 위 두 단추와 **같은 크기**에 붉은색
       그라데이션(2026-08-14 상하님 지시). 순위표를 닫아 두면 '종목 찾기' 바로
       위에 이 단추가 나온다. 붉은색은 대장주 1~3위 비교와 같은 결이다. */
    div[class*="st-key-btn_j3_theme_rank_open"] button,
    div[class*="st-key-close_j3_theme_rank_open"] button {
        background: linear-gradient(90deg, #4a0f12 0%, #8a1c22 38%, #e0474f 100%) !important;
        border: none !important; border-radius: .5rem !important;
        box-shadow: 0 2px 10px rgba(224,71,79,.25) !important;
    }
    /* 크게 세우는 것은 **맨 위 단추만**이다(2026-08-14 상하님 지시 "크기는 예전
       크기로 하고"). 아래 닫기 단추는 색만 같고 크기는 다른 닫기 단추들과 같다. */
    div[class*="st-key-btn_j3_theme_rank_open"] button {
        min-height: 3rem !important;
    }
    div[class*="st-key-btn_j3_theme_rank_open"] button:hover,
    div[class*="st-key-close_j3_theme_rank_open"] button:hover {
        background: linear-gradient(90deg, #5c1418 0%, #a8232b 38%, #f06a71 100%) !important;
    }
    div[class*="st-key-j3_pullback_breakout"] button p,
    div[class*="st-key-j3_pullback_crash"] button p,
    div[class*="st-key-btn_j3_theme_rank_open"] button p {
        color: #ffffff !important;
        font-size: 1.14rem !important;
        font-weight: 800 !important;
        letter-spacing: .01em !important;
        margin: 0 !important;
    }
    /* 아래 닫기 단추 글자는 **예전 크기 그대로**다 — 위 '테마 종목 화면 닫기'와 같다. */
    div[class*="st-key-close_j3_theme_rank_open"] button p {
        color: #ffffff !important;
        font-size: .82rem !important;
        font-weight: 850 !important;
    }
    /* 「종목검색」 위의 순위 9 닫기도 같은 옷을 입는다(2026-08-26 상하님 지시 —
       "20개 테마 실시간 순위 닫기처럼 만들라고"). */
    div[class*="st-key-close_j3_top7_open_above_search"] button {
        background: linear-gradient(90deg, #4a0f12 0%, #8a1c22 38%, #e0474f 100%) !important;
        border: none !important; border-radius: .5rem !important;
        box-shadow: 0 2px 10px rgba(224,71,79,.28) !important;
    }
    div[class*="st-key-close_j3_top7_open_above_search"] button:hover {
        background: linear-gradient(90deg, #5c1418 0%, #a8232b 38%, #f06a71 100%) !important;
    }
    div[class*="st-key-close_j3_top7_open_above_search"] button p {
        color: #ffffff !important;
        font-size: .82rem !important;
        font-weight: 850 !important;
    }
    /* 낙폭 두 갈래는 색으로 가른다(2026-08-01 사용자 지시) — 위 설명 카드와 표의
       같은 갈래가 같은 색이라, 카드를 보고 표에서 그 줄을 바로 찾을 수 있다.
       깊은 갈래(-40~-50%)는 주황, 얕은 갈래(-30~-40%)는 하늘색이다.
       상승·하락 색(파랑/빨강)과 겹치지 않는 색을 골라 등락률과 헷갈리지 않는다. */
    .j3-band-deep, .j3-band-mid {
        display: inline-block; border-radius: .4rem; padding: .05rem .45rem;
        font-weight: 800; white-space: nowrap;
    }
    .j3-band-deep { color: #ff9d3b; background: rgba(255,157,59,.16);
        border: 1px solid rgba(255,157,59,.55); }
    .j3-band-mid { color: #7cc8ff; background: rgba(124,200,255,.14);
        border: 1px solid rgba(124,200,255,.5); }
    .j3-card-deep { border-color: rgba(255,157,59,.55) !important; }
    .j3-card-deep .j3-reason-title { color: #ff9d3b !important; }
    .j3-card-mid { border-color: rgba(124,200,255,.5) !important; }
    .j3-card-mid .j3-reason-title { color: #7cc8ff !important; }
    /* 점수 — 순위 다음 따로 칸에 적는다(2026-08-06 사용자 지시. 순위 칸에 같이
       넣었더니 '1'과 '58점'이 붙어 158점처럼 읽혔다).
       70점 위가 노랑, 50점 위가 파랑, 그 아래는 흐리게. */
    .j3-score { font-size: .95rem; line-height: 1; font-weight: 850; }
    .j3-score-hi { color: #ffc740; }
    .j3-score-mid { color: #7cc8ff; }
    .j3-score-low { color: #8a8f98; }
    .j3-reason-row { display: flex; flex-wrap: wrap; gap: .5rem; margin: .35rem 0 .6rem; }
    .j3-reason-row .j3-reason-card { flex: 1 1 220px; }
    /* 배점표 한 줄 — '무엇 / 몇 점 / 왜' 세 토막을 한 줄에 둔다. */
    .j3-weight { display: flex; align-items: baseline; gap: .5rem; padding: .18rem 0;
        border-bottom: 1px solid rgba(255,255,255,.05); font-size: .84rem; }
    /* 이름 칸을 고정폭으로 둬야 점수가 세로로 줄을 맞춘다. 가장 긴 이름
       ('테마 ETF가 오르는 중인가')이 들어갈 폭이다. */
    .j3-weight b { color: #e6e6e6; min-width: 10.4rem; flex: 0 0 auto; }
    .j3-weight .j3-w-pt { color: #ffc740; font-weight: 850; min-width: 2.6rem;
        text-align: right; }
    .j3-weight .j3-w-why { color: #9aa0a8; }
    .j3-weight.j3-w-zero b, .j3-weight.j3-w-zero .j3-w-pt { color: #7d838b; }
    /* 하락폭 숫자는 붉은색 진하게(2026-08-06 사용자 지시) — 눈에 먼저 들어와야 한다. */
    .j3-drop { color: #ff5b5b; font-weight: 900; }
    .j3-hold-20 { color: #ff9d3b; font-weight: 850; }
    .j3-hold-60 { color: #7cc8ff; font-weight: 850; }
    .j3-hold-120 { color: #44f0a1; font-weight: 850; }
    /* 설명서 두 갈래 표의 종목 단추 — 눌림목 표(j3pbf_)와 똑같은 모양으로 둔다.
       모양이 다르면 같은 자리에서 달라 보여 어색하다(2026-08-01).
       2026-08-09 상하님 지시로 **테마 단추(j3tbtn_)와 같은 네모 테두리**를 준다 —
       "테마 테두리에 손을 올리면 보라색이 되는 게 좋다, 표마다 다 그렇게 해라".
       테두리가 없으면 손을 올려도 보라색이 될 자리가 없다. */
    div[class*="st-key-j3rbf_"] button {
        background: rgba(255,255,255,.025) !important;
        border: 1px solid rgba(255,255,255,.24) !important; box-shadow: none !important;
        padding: .2rem .7rem !important; min-height: 2.5rem !important; width: 100% !important;
        justify-content: flex-start !important;
        border-radius: .55rem !important;
    }
    div[class*="st-key-j3rbf_"] button:hover {
        background: rgba(192,132,252,.09) !important;
        border-color: rgba(192,132,252,.55) !important;
    }
    div[class*="st-key-j3rbf_"] button p {
        color: #c084fc !important; font-weight: 800 !important; font-size: .94rem !important;
        margin: 0 !important; text-align: left !important;
    }
    div[class*="st-key-j3_pullback_find"] button p {
        color: #ffffff !important;
        font-size: 1.02rem !important;
        font-weight: 800 !important;
        letter-spacing: .01em !important;
        margin: 0 !important;
    }
    div[class*="st-key-j3tbtn_"] button {
        background: rgba(255,255,255,.025) !important;
        border: 1px solid rgba(255,255,255,.24) !important;
        box-shadow: none !important;
        padding: .2rem .7rem !important;
        min-height: 2.7rem !important;
        width: 100% !important;
        border-radius: .55rem !important;
    }
    div[class*="st-key-j3tbtn_"] button:hover {
        background: rgba(192,132,252,.09) !important;
        border-color: rgba(192,132,252,.55) !important;
    }
    /* 테마 종목표의 MPC·VLO 단추와 같은 네모 카드·가운데 정렬. */
    div[class*="st-key-j3tbtn_"] button { justify-content: center !important; }
    div[class*="st-key-j3tbtn_"] button p {
        font-weight: 800 !important; font-size: 0.95rem !important; margin: 0 !important;
        text-align: center !important;
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
    /* '매수심사결과 높은 순위 7' 단추 — 2026-08-06 사용자 지시로 초록에서
       스카이블루 그라데이션으로 바꿨다. 옆 두 단추(상승장 초록 · 급락 주황)와
       색이 갈려야 세 갈래가 눈으로 구분된다. */
    div[class*="st-key-j3_top7_find"] button {
        background: linear-gradient(90deg, #0a2740 0%, #12507f 38%, #4da6ff 100%) !important;
        border: none !important;
        border-radius: .5rem !important;
        min-height: 3rem !important;
        box-shadow: 0 2px 10px rgba(77,166,255,.25) !important;
    }
    div[class*="st-key-j3_top7_find"] button:hover {
        background: linear-gradient(90deg, #0e3455 0%, #17629b 38%, #7cc8ff 100%) !important;
    }
    div[class*="st-key-j3_top7_find"] button p {
        color: #ffffff !important;
        font-size: 1.14rem !important;
        font-weight: 800 !important;
        letter-spacing: .01em !important;
    }
    /* 분야 이름이 길면 옆 칸을 덮어썼다 — 한 줄로 자른다(2026-07-30). */
    .j3-top7-src {
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
        max-width: 100%;
    }
    /* '어느 분야' 칸의 글자색은 그 갈래를 여는 **단추 색**을 따른다
       (2026-08-06 사용자 지시). 테마 대장주=스카이블루(순위 7 단추),
       상승장=초록, 급락 후 반등장=주황. */
    .j3-top7-leader { color: #4da6ff; font-weight: 800; }
    .j3-top7-up { color: #12a06a; font-weight: 800; }
    .j3-top7-crash { color: #e67813; font-weight: 800; }
    /* '선택종목 세부사항 보기' — 눌림목 단추와 같은 모양에 진한 황금색
       (2026-07-30 사용자 지시, 한국테마와 같은 모양). */
    div[class*="st-key-btn_j3_detail_open_"] button {
        background: linear-gradient(90deg, #3a2705 0%, #6b4a0e 38%, #d9a521 100%) !important;
        border: none !important;
        border-radius: .5rem !important;
        min-height: 3rem !important;
        box-shadow: 0 2px 10px rgba(217,165,33,.28) !important;
    }
    div[class*="st-key-btn_j3_detail_open_"] button:hover {
        background: linear-gradient(90deg, #4a3208 0%, #855c14 38%, #efc04a 100%) !important;
    }
    div[class*="st-key-btn_j3_detail_open_"] button p {
        color: #ffffff !important;
        font-size: 1.02rem !important;
        font-weight: 800 !important;
        letter-spacing: .01em !important;
        margin: 0 !important;
    }
    /* 안쪽 구역 단추(당일 차트 · 일봉/주봉/월봉 · 매수기록)도 같은 황금색으로.
       다만 위 단추보다 한 단계 연하게 하고 크기는 원래대로 둔다
       (2026-07-30 사용자 지시, 한국테마와 같은 모양). */
    div[class*="st-key-btn_j3_intraday_open_"] button,
    div[class*="st-key-btn_j3_bundle_open_"] button,
    div[class*="st-key-btn_j3_buyform_open_"] button {
        background: linear-gradient(90deg, #6b4d16 0%, #9a7420 38%, #e8c264 100%) !important;
        border: none !important;
        border-radius: .5rem !important;
    }
    div[class*="st-key-btn_j3_intraday_open_"] button:hover,
    div[class*="st-key-btn_j3_bundle_open_"] button:hover,
    div[class*="st-key-btn_j3_buyform_open_"] button:hover {
        background: linear-gradient(90deg, #7d5b1c 0%, #b28829 38%, #f3d489 100%) !important;
    }
    div[class*="st-key-btn_j3_intraday_open_"] button p,
    div[class*="st-key-btn_j3_bundle_open_"] button p,
    div[class*="st-key-btn_j3_buyform_open_"] button p {
        color: #ffffff !important;
        font-weight: 700 !important;
    }
    /* 대장주 1~3위 비교 — 붉은색 그라데이션(2026-07-30 사용자 지시, 한국테마와 같다). */
    div[class*="st-key-btn_j3_leadercmp_open"] button {
        background: linear-gradient(90deg, #4a0f12 0%, #8a1c22 38%, #e0474f 100%) !important;
        border: none !important;
        border-radius: .5rem !important;
    }
    div[class*="st-key-btn_j3_leadercmp_open"] button:hover {
        background: linear-gradient(90deg, #5c1418 0%, #a8232b 38%, #f06a71 100%) !important;
    }
    div[class*="st-key-btn_j3_leadercmp_open"] button p {
        color: #ffffff !important;
        font-weight: 700 !important;
    }
    /* 제목 띠 — 단추가 아니라 제목이다(누를 곳이 아니다). 순위 7 단추(초록)·
       눌림목 단추(파랑)와 같은 결로 맞춘 보라색. 한국테마와 같은 모양이다. */
    .j3-band {
        display: inline-block;
        border-radius: .5rem;
        padding: .6rem 1.1rem;
        margin: .2rem 0 .6rem;
        color: #ffffff;
        font-size: 1.02rem;
        font-weight: 800;
        letter-spacing: .01em;
    }
    .j3-band-purple {
        background: linear-gradient(90deg, #2a1450 0%, #3d1f74 38%, #7c3aed 100%);
        box-shadow: 0 2px 10px rgba(124,58,237,.25);
    }
    /* 종목검색 칸 이름 — 바로 위 보라색 띠와 같은 계열로 진하게(2026-08-01 지시).
       어두운 화면에서도 읽히도록 띠의 밝은 쪽 보라를 쓴다. */
    div[class*="st-key-j3_my_stock_query"] [data-testid="stWidgetLabel"] p {
        color: #a855f7 !important;
        font-size: 1.08rem !important;
        font-weight: 900 !important;
    }
    /* '지금 할 일' 지침 상자 — 매수 심사 결과 표 바로 위. 테두리 색은
       guidance.py가 판정에 따라 정한다(초록 진입 · 노랑 대기 · 빨강 금지).
       한국테마(j4-guide)와 같은 모양이다. */
    .j3-guide {
        border: 2px solid; border-radius: 10px; padding: .6rem .85rem;
        margin: 0 0 .7rem; background: rgba(255,255,255,0.03);
    }
    .j3-guide-tag {
        font-size: .74rem; font-weight: 800; letter-spacing: .04em;
        border: 1px solid currentColor; border-radius: .4rem;
        padding: .05rem .4rem; margin-right: .5rem;
    }
    .j3-guide-head { font-size: 1.02rem; font-weight: 800; }
    .j3-guide-body { margin-top: .35rem; font-size: .92rem; line-height: 1.5; color: #e6e6e6; }
    /* 「배점 미달」 표 — 매수 심사 결과 상자 **바로 위**에 붙는다
       (2026-08-28 상하님 지시 — "70점 넘지 않으면 배점 미달이라고 표시해라").
       상자 안이 아니라 위에 두는 까닭 — 상자 안의 색은 판정을 따라 바뀌는데,
       이것은 판정과 별개로 늘 같은 뜻이라 색이 섞이면 안 읽힌다. */
    .j3-guide-short {
        border: 2px solid #ff8f3b; border-radius: 10px;
        padding: .5rem .8rem; margin: 0 0 .5rem;
        background: rgba(255,143,59,.10);
        color: #ffb673; font-size: .95rem; font-weight: 800; line-height: 1.45;
    }
    .j3-guide-short b { color: #ffd7a8; }
    /* 테두리는 노랑 — 매수 심사 결과가 이 화면에서 제일 먼저 눈에 띄어야 한다
       (2026-07-30 사용자 지시, 한국테마와 같은 색). */
    .j3-holo-card {
        position: relative;
        background: linear-gradient(135deg, rgba(255,209,102,0.07), rgba(255,176,32,0.07));
        border: 1px solid rgba(255,199,64,0.75);
        border-radius: 10px;
        padding: 1.15rem 1.3rem;
        box-shadow: 0 0 14px rgba(255,199,64,0.30), inset 0 0 20px rgba(255,199,64,0.08);
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
    /* 숫자가 아니라 **말**이 들어가는 칸은 두 치수 낮춘다(2026-08-21 상하님 지시 —
       "미국장 종가 확정 뒤 신규매수 관찰 글자 너무 크다"). 1.5rem으로 그리면
       긴 말이 한 글자씩 줄바꿈되어 칸이 세로로 늘어난다. */
    .j3-holo-cell .val .j3-holo-words { font-size: 1.05rem; line-height: 1.45;
        font-weight: 800; }
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
    /* 눌림목 표의 종목 단추도 같은 네모 테두리로(2026-08-09 상하님 "모든 곳에"). */
    div[class*="st-key-j3pbf_"] button {
        background: rgba(255,255,255,.025) !important;
        border: 1px solid rgba(255,255,255,.24) !important; box-shadow: none !important;
        padding: .2rem .7rem !important; min-height: 2.5rem !important; width: 100% !important;
        justify-content: flex-start !important;
        border-radius: .55rem !important;
    }
    div[class*="st-key-j3pbf_"] button:hover {
        background: rgba(192,132,252,.09) !important;
        border-color: rgba(192,132,252,.55) !important;
    }
    div[class*="st-key-j3pbf_"] button p {
        color: #c084fc !important; font-weight: 800 !important; font-size: .94rem !important;
        margin: 0 !important; text-align: left !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _login_gate() -> None:
    # 첫 화면의 큰 판(미국테마·한국테마)을 누르고 온 사람은 비밀번호를 묻지 않는다
    # (2026-08-09 상하님 지시 "게스트 비번 필요 없는 것 기준"). 주소에 달려 오는
    # 표식 하나로 가른다 — 게스트는 원래도 비밀번호 없이 들어올 수 있으므로
    # 이 표식이 새로 여는 문은 없고, 누르는 횟수만 둘에서 하나로 준다.
    # 이미 로그인한 사람은 건드리지 않는다(login_prism.wants_guest가 막는다).
    try:
        if login_prism.wants_guest(st):
            auth.login_as_guest()
    except Exception:
        pass      # 표식을 못 읽어도 아래 예전 흐름으로 그대로 간다
    auth.sync_auth()  # 쿠키에 로그인이 남아 있으면 되살린다(폰 복귀 시 재로그인 방지).
    if st.session_state.get("authenticated"):
        return
    st.markdown("## 자비스6 미국테마")
    st.caption("승인된 사용자만 접근할 수 있습니다. 여기서 바로 로그인할 수 있습니다.")
    try:
        password = st.secrets.get("APP_PASSWORD")
    except Exception:
        password = None
    if not password:
        st.warning(".streamlit/secrets.toml에 APP_PASSWORD 설정이 필요합니다.")
        st.stop()
    entered = st.text_input("비밀번호", type="password", key="j6_login_password")
    if st.button("자비스6 로그인", key="j6_login_submit", width="stretch"):
        if entered == password:
            auth.login_as_owner()
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    st.stop()


_login_gate()

if auth.is_guest():
    # 게스트는 사이드바를 통해 다른 자비스 화면으로 우회하지 못하고 미국·한국
    # 테마 두 화면만 오갈 수 있다. 실제 자료·계산에는 손대지 않는 표시 제한이다.
    st.markdown(
        """
        <style>
        [data-testid="stSidebarNav"] li:not(:nth-child(4)):not(:nth-child(5)) {
            display: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

import importlib
import os
import threading
import time

_PAGE_SEOUL = ZoneInfo("Asia/Seoul")

import altair as alt
import pandas as pd

import fear_greed_ui
import mobile_ui

# 옛 mobile_ui가 프로세스에 남으면 폰 수정이 온라인에 하나도 반영되지 않는다
# (2026-07-25 실발생). CLAUDE.md 11번 규칙에 따라 리비전이 낮으면 다시 읽는다.
_REQUIRED_MOBILE_REVISION = 2026082861
if int(getattr(mobile_ui, "MODULE_REVISION", 0)) < _REQUIRED_MOBILE_REVISION:
    mobile_ui = importlib.reload(mobile_ui)
import guidance

# 지침 문구를 바꾸면 guidance의 리비전을 올린다(규칙 11).
_REQUIRED_GUIDANCE_REVISION = 2026080110
if int(getattr(guidance, "MODULE_REVISION", 0)) < _REQUIRED_GUIDANCE_REVISION:
    guidance = importlib.reload(guidance)

import method_help

# 설명 단추 문구·숫자를 바꾸면 method_help의 리비전을 올린다.
# 안 올리면 온라인에서 옛 문구가 그대로 남는다(규칙 11).
_REQUIRED_METHOD_HELP_REVISION = 2026082712
if int(getattr(method_help, "MODULE_REVISION", 0)) < _REQUIRED_METHOD_HELP_REVISION:
    method_help = importlib.reload(method_help)

import picklist_ui

# 날짜별로 저장해 둔 목록을 보는 자리(2026-08-09). 표시 칸을 바꾸면 같이 올린다.
_REQUIRED_PICKLIST_REVISION = 2026090230
if (
    # 2026-08-29 「상위 테마 5개」를 화면에서도 남기는 데 쓴다. 옛 모듈이면
    # 이 이름이 없어 그 갈래가 또 통째로 빠진다.
    not hasattr(picklist_ui, "needs_autosave")
    or int(getattr(picklist_ui, "MODULE_REVISION", 0)) < _REQUIRED_PICKLIST_REVISION
):
    picklist_ui = importlib.reload(picklist_ui)

import scroll_to

# 종목을 누르면 상세 자리로 화면을 내려 주는 장치(2026-08-09).
_REQUIRED_SCROLL_REVISION = 2026082920
if (
    # 2026-08-29 화면을 바꿀 때 **바로** 맨 위로 올리는 데 쓴다. 옛 모듈이면
    # 이 이름이 없어 화면이 통째로 죽는다.
    not hasattr(scroll_to, "now")
    or int(getattr(scroll_to, "MODULE_REVISION", 0)) < _REQUIRED_SCROLL_REVISION
):
    scroll_to = importlib.reload(scroll_to)

import hero_banner

# 시장분석 맨 위의 눈밭 캠프 배너(2026-08-28 상하님 지시). 그림·글귀를 바꾸면
# hero_banner의 리비전을 올리고 이 숫자도 같이 올린다(규칙 11).
_REQUIRED_HERO_REVISION = 2026090310
if int(getattr(hero_banner, "MODULE_REVISION", 0)) < _REQUIRED_HERO_REVISION:
    hero_banner = importlib.reload(hero_banner)
import regime_gauge_ui
import back_nav  # 폰·태블릿 뒤로가기 (2026-08-21). 실패하면 조용히 예전처럼 돈다.
import jarvis3_data as j3data
import jarvis3_briefing_news as briefing_news
import jarvis3_briefing_store as briefing_store
import us_company_logos
import us_swing_selector as us_swing
import jarvis3_store as j3store
import market_signal_ui

_REQUIRED_REGIME_GAUGE_REVISION = 2026081310
if int(getattr(regime_gauge_ui, "MODULE_REVISION", 0)) < _REQUIRED_REGIME_GAUGE_REVISION:
    regime_gauge_ui = importlib.reload(regime_gauge_ui)

# ── 온라인 옛 모듈 자가복구 ──────────────────────────────────────────────────
# 스트림릿 클라우드는 배포 갱신 때 페이지 파일만 새로 읽고 import된 모듈은 옛것을
# 프로세스에 유지하는 경우가 있다(2026-07-22 '모듈 갱신 대기'·'당일 자료 없음' 실발생).
# 새 코드에만 있는 함수가 없으면 그 모듈을 파일에서 다시 읽어 재부팅 없이 복구한다.
_REQUIRED_J3_REVISION = 2026090320
if (
    not hasattr(j3data, "get_fear_greed")
    # 2026-08-01 SPY·QQQ 칸의 당일·일봉 그림에서 쓴다.
    or not hasattr(j3data, "get_etf_sparklines")
    # 2026-08-01 설명서 두 갈래(상승장 신고가 눌림 · 급락 후 낙폭)에서 쓴다.
    or not hasattr(j3data, "find_breakout_pullback_stocks")
    or not hasattr(j3data, "find_crash_rebound_stocks")
    or not hasattr(j3data, "_intraday_chart_payload")
    or not hasattr(j3data, "find_pullback_stocks")
    or not hasattr(j3data, "analyze_pullback_stock")
    or not hasattr(j3data, "get_intraday_chart")
    or not hasattr(j3data, "get_index_sparklines")
    # 2026-07-29 '내 종목 현재상황'에서 쓴다. 빠뜨리면 온라인에서 AttributeError가 난다.
    or not hasattr(j3data, "search_stocks")
    or not hasattr(j3data, "get_briefing_cards")
    or not hasattr(j3data, "analyze_one_stock")
    # 2026-07-30 '매수심사결과 높은 순위 7'에서 쓴다.
    or not hasattr(j3data, "find_top_reviewed_stocks")
    # 2026-08-29 상승장 단추가 순위 9의 기억을 같이 쓰는 데 쓴다. 옛 모듈이면
    # 이 이름이 없어 단추가 죽는다.
    or not hasattr(j3data, "breakout_scan")
    # 2026-08-29 시장분석 화면이 상승장을 미리 데우는 데 쓴다.
    or not hasattr(j3data, "warm_breakout_scan")
    # 이름은 그대로인데 내용만 옛것인 모듈도 걸러낸다(2026-07-24 자비스4에서 실제 발생).
    or int(getattr(j3data, "MODULE_REVISION", 0)) < _REQUIRED_J3_REVISION
):
    j3data = importlib.reload(j3data)
_REQUIRED_SIGNAL_UI_REVISION = 2026082810
if (
    not hasattr(market_signal_ui, "_STATUS_TEXT")
    # 2026-08-28 접었다 펴는 미국장 카드에서 쓴다. 옛 모듈이면 foldable 인자를
    # 몰라 화면이 통째로 죽는다.
    or not hasattr(market_signal_ui, "_peek_gauge_html")
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


# ── 폰·태블릿 뒤로가기 (2026-08-21 상하님 지시) ─────────────────────────────
# 상하님 — "한번 누르면 방금 화면 전으로 가게 하고 두번 누르면 메인메뉴로."
# 구역을 그리기 **전에** 불러야 한다 — 아래 화면들이 열림/닫힘 값을 읽기 때문이다.
_backnav_closed = back_nav.sync(st)


# 화면에 적는 **테마 개수**. 명부(jarvis3_data.US_THEMES)를 그대로 센다.
# 손으로 「20개」라고 적어 두면 테마를 더하거나 뺄 때마다 화면 글이 조용히
# 틀린다 — 2026-08-29에 제약·헬스케어를 더해 20 → 21이 되었다.
# 명부를 못 읽는 판에서도 화면이 죽지 않게 20을 받쳐 둔다.
_THEME_COUNT = len(getattr(j3data, "US_THEMES", ())) or 20


# 겨자색 상자에서 굵게 뽑을 말들(2026-08-07 상하님 지시 "중요부분만 진하게").
# 여기 없는 말은 보통 굵기로 둔다 — 다 굵으면 아무것도 강조되지 않는다.
_MUSTARD_NUMBER = re.compile(r"[+\-−]\d+(?:[.,]\d+)?%")
_MUSTARD_HOLD = re.compile(r"\d+거래일 뒤 종가")
# **점수도 뽑아 준다**(2026-08-21 상하님 지시 "점수와 프로테이지 색깔 구분").
# 66.0/70 · 17.0/30 · 83.0/100 꼴을 초록으로 굵게 칠한다.
_MUSTARD_SCORE = re.compile(r"\d+(?:\.\d+)?/\d+")
_MUSTARD_KEYS = (
    "그날 낙폭으로 정합니다",
    "다음 거래일 시가",
    "손절가가 없습니다",
    "손절가는 없습니다",
    # 2026-08-12 — 파는 시점을 앱이 정하지 않는다는 말이 눈에 띄어야 한다.
    "파는 시점은 규칙에 없습니다",
    # 2026-08-21 — 상승장 갈래에서 꼭 읽어야 하는 두 마디.
    "지난 1년 최고가를 넘은 날",
    "손절과 파는 시점은 앱이 정하지 않습니다",
)


def _mustard_html(text) -> str:
    """겨자색 상자의 글 — 숫자와 중요한 말만 굵게·색으로 뽑는다.

    오른 값(+)은 스카이블루, 빠진 값(−)은 붉은색이다. 화면 다른 곳과 같은 약속이다.

    **글은 먼저 escape한다** — 여기 들어오는 글은 jarvis3_data가 만든 평문이고,
    그 뒤에 우리가 만든 태그만 얹는다. 순서를 바꾸면 우리가 얹은 태그까지
    글자로 보이게 된다.
    """
    safe = html.escape(str(text or ""))
    safe = _MUSTARD_NUMBER.sub(
        lambda match: (
            f"<span class='j3-mn-{'up' if match.group()[0] == '+' else 'down'}'>"
            f"{match.group()}</span>"
        ),
        safe,
    )
    safe = _MUSTARD_HOLD.sub(
        lambda match: f"<span class='j3-mn-key'>{match.group()}</span>", safe)
    safe = _MUSTARD_SCORE.sub(
        lambda match: f"<span class='j3-mn-score'>{match.group()}</span>", safe)
    for phrase in _MUSTARD_KEYS:
        safe = safe.replace(phrase, f"<span class='j3-mn-key'>{phrase}</span>")
    return safe


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


# 화면 큰 제목 두 개(「미국 전체시장 판단」·「미국장 시장 상태」)가 쓰는 옷.
# **한 곳에서만 정한다** — 두 군데 적어 두면 한쪽만 고쳐 크기가 어긋난다
# (2026-08-21 상하님 지시 "동일하게 할 것").
_SECTION_TITLE_CLASS = "j3-page-title"
_SECTION_TITLE_CSS = (
    "<style>.j3-page-title{font-size:16px; font-weight:800; color:#c084fc;"
    " margin:.25rem 0 .4rem; letter-spacing:-.01em;}</style>"
)


def _top_metric(label, value, value_color, sub, *, sub_color=None, sub_signed=False,
                extra_class: str = "") -> str:
    """지표 한 칸. ``extra_class``는 폰에서 칸 차례를 정하는 이름표다.

    자료를 못 받아 '—'로 나오는 칸도 **같은 자리**에 서야 한다. 이름표를 안 붙이면
    그 칸만 차례가 어긋나 딴 데 가서 붙는다.
    """
    if sub_signed:
        sub_html = f"<div class='j3-top-sub {_sign_class(sub)}'>{_pct(sub)}</div>"
    else:
        sub_html = f"<div class='j3-top-sub' style='color:{sub_color or '#9aa0aa'}'>{sub}</div>"
    cell_class = f"j3-top-cell {extra_class}".strip()
    return (
        f"<div class='{cell_class}'><div class='j3-top-label'>{label}</div>"
        f"<div class='j3-top-val' style='color:{value_color}'>{value}</div>{sub_html}</div>"
    )


# 2026-08-14에 이름표를 '주도·관찰'에서 '강함·보통'으로 바꿨다(앞날을 말하지
# 않는 말로). **옛 이름도 남겨 둔다** — 저장해 둔 기록에는 옛 이름이 들어 있다.
_STATUS_HEX = {"강함": "#44f0a1", "보통": "#ff9d3b", "약함": "#9aa0aa",
               "주도": "#44f0a1", "관찰": "#ff9d3b"}


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


_THEME_COL_WIDTHS = [0.42, 1.55, 0.55, 1.4, 0.62, 0.78, 1.0, 1.1]
# 한 줄을 세 칸으로만 나눈다 — 순위 · 테마(단추) · 나머지를 묶은 한 덩이.
# 칸마다 요소를 만들면 폰이 느려진다(2026-07-30 실측, 한국테마와 같은 처리).
_THEME_ROW_WIDTHS = [_THEME_COL_WIDTHS[0], _THEME_COL_WIDTHS[1], sum(_THEME_COL_WIDTHS[2:])]
_THEME_REST_WIDTHS = _THEME_COL_WIDTHS[2:]


def _stacked(cells: list[str]) -> str:
    """칸 여럿을 **한 덩이 HTML**로 세로로 쌓는다 (2026-08-26 상하님 지시).

    상하님 지적 — "관찰만 15개 보기, 종목 1번부터 여전히 순서대로 천천히
    열린다."

    지금까지는 **줄마다** st.columns 를 새로 만들었다. 그러면 스트림릿이 줄마다
    껍데기를 네 벌씩 만들어 15줄이면 화면 조각이 673개가 된다. 그 조각들이 여러
    뭉치로 나뉘어 도착하기 때문에 줄이 하나씩 나타나 보인다(브라우저에서 실측 —
    세 뭉치로 2.5초에 걸쳐 도착했다. 폰은 그 몇 배다).

    이제 표 하나에 칸을 **한 번만** 만들고, 각 칸의 값들을 여기서 한 덩이로
    쌓는다. 틈 16px 은 스트림릿이 단추와 단추 사이에 두는 값과 같다 —
    그래야 옆 칸의 종목 단추와 줄이 딱 맞는다(실측: 단추 40px · 틈 16px ·
    .j3-td 40px).
    """
    return ("<div style='display:flex; flex-direction:column; gap:16px'>"
            + "".join(cells) + "</div>")


def _flex_row(widths: list[float], cells: list[str], *, head: bool = False,
              muted_from: int | None = None) -> str:
    """여러 칸을 한 덩이 HTML로 그린다. 칸 폭은 원래 비율을 그대로 쓴다."""
    kind = "j3-th-head" if head else "j3-td"
    parts = []
    for index, (width, cell) in enumerate(zip(widths, cells)):
        extra = " j3-th-muted" if muted_from is not None and index >= muted_from else ""
        parts.append(
            f"<div class='{kind}{extra}' style='flex:{width} 1 0; min-width:0'>{cell}</div>"
        )
    return f"<div style='display:flex; align-items:center; gap:.15rem'>{''.join(parts)}</div>"

# 테마 순위표에서 처음부터 보여줄 개수. 나머지는 접어 두고 눌러서 본다
# (2026-07-25 사용자 지시). 자비스4도 같은 값을 쓴다.
_THEME_VISIBLE_COUNT = 10


def _render_theme_table(ranking: dict, selected: str | None) -> str | None:
    """테마표를 그리고, 테마 이름 버튼이 눌리면 그 테마명을 돌려준다.

    테마명만 st.button이라 클릭이 확실히 되고(세션도 안 끊김),
    나머지 칸은 HTML이라 가운데 정렬·색·막대를 그대로 쓸 수 있다.
    """
    # 폰·태블릿에서 세로로 쌓지 않고 옆으로 밀어 본다(2026-07-25, 한국테마와 같은 방식).
    theme_box = st.container(key="j3_theme_table")
    head = theme_box.columns(_THEME_ROW_WIDTHS)
    head[0].markdown("<div class='j3-th-head'>순위</div>", unsafe_allow_html=True)
    head[1].markdown("<div class='j3-th-head'>테마</div>", unsafe_allow_html=True)
    head[2].markdown(
        _flex_row(_THEME_REST_WIDTHS, ["ETF", "테마점수", "상태", "당일",
                                       "6개월 시장대비", "강한 종목 비율"], head=True),
        unsafe_allow_html=True,
    )
    # 머리글 '테마'와 첫 행(석유·가스 등)이 붙어 보이지 않도록 대장주 표와
    # 같은 간격을 둔다. 표 전체를 함께 밀어 열 정렬은 그대로 유지한다.
    theme_box.markdown("<div class='j3-leader-head-gap'></div>", unsafe_allow_html=True)

    # 테마명 버튼 색을 상태색과 맞춘다(선택된 테마는 주황 배경으로 표시).
    # 키는 2자리 고정폭(j3tbtn_01)으로 만든다 — class*= 부분일치 선택자라서
    # j3tbtn_1이 j3tbtn_10~19에도 매칭돼 안 고른 행에 배경이 묻던 버그 수정
    # (2026-07-22 사용자 제보: "클릭 후 흔적이 남음").
    button_css = []
    clicked = None
    # 11위부터는 접어 둔다 — 20개가 다 펼쳐져 있으면 폰에서 화면을 다 먹는다
    # (2026-07-25 사용자 지시). 값·순위·계산은 그대로이고, 그리는 자리만 바꾼다.
    all_rows = list(ranking.get("rows", []))
    rest_box = None
    if len(all_rows) > _THEME_VISIBLE_COUNT:
        # 키를 가진 칸으로 한 번 감싼다 — 그래야 위 표와 같은 '옆으로 밀기' CSS가
        # 이 안에도 걸린다(한국테마 j4_theme_rest와 같은 방식). 감싸지 않았더니
        # 폰에서 접힌 쪽만 순위·테마·값이 세로로 쌓였다(2026-08-09 상하님 캡처).
        rest_box = st.container(key="j3_theme_rest").expander(
            f"{_THEME_VISIBLE_COUNT + 1}위~{len(all_rows)}위 테마 더 보기", expanded=False
        )
    # **표 한 벌에 칸을 한 번만 만든다** (2026-08-26 상하님 지시로 관찰만 표와
    # 같은 방식으로 바꿨다). 예전에는 줄마다 st.columns 를 새로 만들어서, 스트림릿이
    # 껍데기를 줄마다 세 벌씩 만들었다. 20줄이면 그것만으로 조각이 수백 개다.
    # 이제 순위·나머지는 각각 한 덩이로 쌓고, 테마 이름 단추만 진짜 단추로 둔다.
    # **값·순위·색·차례는 하나도 안 바뀐다.** 몇 덩이로 나누어 보내느냐만 바뀐다.
    def _theme_cells(row, color):
        """한 줄의 '순위' 칸과 '나머지 여섯 칸'을 만든다. 계산은 하지 않는다."""
        etf = str(row.get("etf", ""))
        rank_cell = f"<div class='j3-td'>{row.get('rank', '')}</div>"
        if not row.get("ok"):
            return rank_cell, _flex_row(_THEME_REST_WIDTHS, [etf] + ["자료 부족"] * 5, muted_from=1)
        score = float(row.get("score") or 0)
        strong_share = row.get("strong_members")
        change, strength120 = row.get("change_pct"), row.get("strength_120")
        strength_text = "—" if strength120 is None else f"{float(strength120):+.1f}%p"
        strong_cell = "—" if strong_share is None else (
            "<div class='j3-barwrap'><div class='j3-bar'>"
            f"<div class='j3-bar-fill j3-bar-green' style='width:{min(float(strong_share), 100):.0f}%'></div></div>"
            f"<span class='j3-bar-num'>{float(strong_share):.0f}%</span></div>"
        )
        return rank_cell, _flex_row(_THEME_REST_WIDTHS, [
            etf,
            "<div class='j3-barwrap'><div class='j3-bar'>"
            f"<div class='j3-bar-fill' style='width:{max(0.0, min(score, 100.0)):.0f}%'></div></div>"
            f"<span class='j3-bar-num'>{score:.1f}</span></div>",
            f"<span style='color:{color}; font-weight:800'>{row.get('status', '')}</span>",
            f"<span style='color:{_sign_color(change)}; font-weight:700'>{_pct(change)}</span>",
            f"<span style='color:{_sign_color(strength120)}; font-weight:700'>{strength_text}</span>",
            strong_cell,
        ])

    # 앞 열 줄과 접어 둔 나머지를 나눈다. 각자 제 칸 한 벌을 쓴다.
    groups = [(theme_box, list(enumerate(all_rows))[:_THEME_VISIBLE_COUNT])]
    if rest_box is not None:
        groups.append((rest_box, list(enumerate(all_rows))[_THEME_VISIBLE_COUNT:]))
    for target, part in groups:
        if not part:
            continue
        cols = target.columns(_THEME_ROW_WIDTHS)
        ranks, rests, names = [], [], []
        for index, row in part:
            name = row.get("name", "")
            color = _STATUS_HEX.get(row.get("status", ""), "#e6e6e6")
            button_key = f"j3tbtn_{index:02d}"
            button_css.append(f"div[class*='st-key-{button_key}'] button p {{ color: {color} !important; }}")
            if name == selected:
                button_css.append(
                    f"div[class*='st-key-{button_key}'] button {{ background: rgba(255,176,32,0.16) !important; }}"
                )
            rank_cell, rest_cell = _theme_cells(row, color)
            ranks.append(rank_cell)
            rests.append(rest_cell)
            names.append((name, button_key))
        cols[0].markdown(_stacked(ranks), unsafe_allow_html=True)
        for name, button_key in names:
            if cols[1].button(name, key=button_key, width="stretch"):
                clicked = name
        cols[2].markdown(_stacked(rests), unsafe_allow_html=True)

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


def _regime_range_text() -> str:
    """구간 안내 한 줄. 이름·점수는 regime_gauge_ui가 원본이라 여기서 따로 적지 않는다."""
    return " · ".join(
        f"{regime_gauge_ui.RANGE_TEXT[name]}점 {name}"
        for _limit, name, _color in regime_gauge_ui.ZONES
    )


def _market_score_detail(overview: dict) -> str:
    breakdown = overview.get("score_breakdown") or []
    if not breakdown:
        return "세부 점수는 다음 온라인 갱신에서 표시됩니다."
    earned = [f"{item['label']} {item['earned']}/{item['max']}점" for item in breakdown if item.get("earned")]
    missed = [item["label"] for item in breakdown if not item.get("earned")]
    earned_text = ", ".join(earned) if earned else "충족 신호 없음"
    missed_text = ", ".join(missed) if missed else "없음"
    # <b>는 이 설명 상자에서 초록으로 띄우는 표시다(위 .j3-score-guide b 참고).
    return f"<b>현재 획득</b>: {earned_text} · <b>미충족</b>: {missed_text}"


def _market_action_detail(overview: dict) -> str:
    # 문장마다 <br>로 줄을 바꾼다 — 글자가 너무 빽빽하다는 지적(2026-07-22 캡처 빗금) 반영.
    score = float(overview.get("score") or 0)
    if score >= 75:
        return (
            "시장 추세와 위험선호가 충분히 확인된 구간입니다.<br>"
            "그래도 아무 종목이나 매수하지 않고, 주도 테마이면서 "
            f"종목 조건점수 {_number(getattr(j3data, 'LEADER_GATE_MARK', 60.0))}점 이상인 "
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


_LEADER_COL_WIDTHS = [0.75, 1.9, 0.85, 1.6, 0.95, 1.25, 1.15, 1.1]
# 테마표와 같은 이유로 세 칸만 쓴다 — 순위 · 종목(단추) · 나머지를 묶은 한 덩이.
_LEADER_ROW_WIDTHS = [_LEADER_COL_WIDTHS[0], _LEADER_COL_WIDTHS[1], sum(_LEADER_COL_WIDTHS[2:])]
_LEADER_REST_WIDTHS = _LEADER_COL_WIDTHS[2:]


def _render_leader_table(leaders: list[dict], selected_ticker: str | None) -> str | None:
    """종목표를 그리고, 종목 이름 버튼이 눌리면 그 티커를 돌려준다.

    한국테마(자비스4)와 같은 방식이다(2026-07-29 지시). 예전에는 순수 HTML 표라
    이름을 눌러도 아무 일이 없었다. 아래 '상세 종목 선택'은 그대로 둔다.
    폰·태블릿 규칙은 이미 도는 테마표·눌림목표와 같은 CSS 묶음에 얹었다.
    """
    box = st.container(key="j3_leader_table")
    head = box.columns(_LEADER_ROW_WIDTHS)
    head[0].markdown("<div class='j3-th-head'>순위</div>", unsafe_allow_html=True)
    head[1].markdown("<div class='j3-th-head'>종목</div>", unsafe_allow_html=True)
    head[2].markdown(
        _flex_row(_LEADER_REST_WIDTHS, ["티커", "최종점수", "당일", "52주 고가 대비",
                                        "20일 수익률", "매수 상태"], head=True),
        unsafe_allow_html=True,
    )
    # 머리글 '종목'과 첫 행 MPC가 붙어 보이지 않도록 한 줄만 띄운다.
    box.markdown("<div class='j3-leader-head-gap'></div>", unsafe_allow_html=True)

    rank_mark = {1: "🟡 1위", 2: "⚪ 2위", 3: "🟠 3위"}
    button_keys = []
    clicked = None
    for index, leader in enumerate(leaders[:6]):
        metrics, plan = leader["metrics"], leader["plan"]
        rank = int(leader.get("rank") or 0)
        ticker = leader["ticker"]
        score = float(leader.get("score") or 0)
        button_key = f"j3lbtn_{index:02d}"
        button_keys.append((button_key, ticker))
        cols = box.columns(_LEADER_ROW_WIDTHS)
        cols[0].markdown(
            f"<div class='j3-td'>{rank_mark.get(rank, f'{rank}위')}</div>", unsafe_allow_html=True)
        if cols[1].button(leader["name"], key=button_key, width="stretch"):
            clicked = ticker
        # 나머지 여섯 칸은 한 덩이로 그린다(2026-07-30 — 요소 수를 줄여 폰을 빠르게).
        cols[2].markdown(
            _flex_row(_LEADER_REST_WIDTHS, [
                ticker,
                "<div class='j3-barwrap'><div class='j3-bar'>"
                f"<div class='j3-bar-fill' style='width:{max(0.0, min(score, 100.0)):.0f}%'></div></div>"
                f"<span class='j3-bar-num'>{score:.1f}/100</span></div>",
                *(
                    f"<span style='color:{_sign_color(value)}; font-weight:700'>{_pct(value)}</span>"
                    for value in (metrics.get("change_pct"), metrics.get("from_high_pct"),
                                  metrics.get("ret20"))
                ),
                str(plan.get("state", "")),
            ]),
            unsafe_allow_html=True,
        )

    # 주황 표시는 **줄을 다 그린 뒤에** 한 번에 붙인다. 그래서 이 판에서 방금 누른
    # 줄도 곧바로 표시할 수 있다 — 예전에는 표를 그리기 전의 선택만 알고 있어서
    # 화면을 통째로 다시 돌려야(st.rerun) 표시가 옮겨졌다(2026-08-21).
    highlight = clicked or selected_ticker
    button_css = [
        f"div[class*='st-key-{key}'] button "
        "{ background: rgba(255,176,32,0.16) !important; }"
        for key, ticker in button_keys if ticker == highlight
    ]
    if button_css:
        st.markdown("<style>" + "".join(button_css) + "</style>", unsafe_allow_html=True)
    return clicked


def _leader_table_html(leaders: list[dict], selected_ticker: str | None) -> str:
    """(지금은 안 씀) 예전 HTML 표.

    2026-07-29에 이름을 누를 수 있게 _render_leader_table로 바꿨다. 폰에서
    새 표가 이상하면 호출부 한 줄만 되돌리면 예전 화면으로 돌아간다.
    """
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
            f"<div class='j3-bar-fill' style='width:{_leader_bar_pct(score):.0f}%'></div></div>"
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


# ── 종목 차트 (2026-08-28 상하님 지시) ──────────────────────────────────────
#
# 상하님 — "20개 테마, 신고가 눌림매수, 급락 후 반등장, 매수심사결과 높은 순위의
# 각 파트별로 종목에 차트들이 나오는데 당일·일봉(거래량 빼라)·주봉·월봉 이렇게
# 나오는데 너무 못생겼다. 첫 번째 캡처처럼 하되 일·주·월봉은 20선 50선은 넣어 줘."
#
# 첫 번째 캡처는 관심종목 카드의 「일봉 6개월」이다 — 시작가에 점선을 긋고 그 위는
# 초록, 아래는 빨강으로 채운 그림. 그 방식을 종목 상세의 네 그림에 그대로 옮긴다.
#
# **덤으로 빨라진다.** 예전 그림은 Vega(알테어)라 그림 하나에 규격 뭉치를 통째로
# 브라우저에 보내고 브라우저가 그걸 읽어 그린다. 종목을 누르면 그런 그림이 네 개씩
# 만들어졌다(상하님 지적 — "정식 후보 종목을 클릭하면 15초 정도"). 이 그림은
# 서버가 만든 SVG 한 조각이라 브라우저가 읽을 것이 없다.
_CHART_UP = "#70e64a"        # 기준선 위 (관심종목 카드와 같은 초록)
_CHART_DOWN = "#ff5b5b"      # 기준선 아래
_CHART_MA20 = "#ffb020"      # 20선 — 주황
_CHART_MA50 = "#c084fc"      # 50선 — 보라


def _split_pieces(values: list[float], base: float) -> list[tuple[int, list]]:
    """기준선을 넘는 자리에서 선을 끊어 (위/아래, 점들)로 나눈다.

    관심종목 카드 그림과 종목 상세 그림이 **같은 계산**을 쓴다. 칸마다 따로
    그리면 조각이 수백 개가 되지만, 가로지르는 자리만 끊으면 보통 서넛이다.
    돌려주는 x는 **칸 번호**다 — 실제 좌표는 부르는 쪽이 정한다.
    """
    pieces, current, sign = [], [(0.0, base if values[0] == base else values[0])], None
    for index in range(len(values) - 1):
        now_value, next_value = values[index], values[index + 1]
        sign_now = 1 if now_value >= base else -1
        sign_next = 1 if next_value >= base else -1
        if sign is None:
            sign = sign_now if now_value != base else sign_next
        if sign_next == sign or next_value == base:
            current.append((float(index + 1), next_value))
            continue
        share = (base - now_value) / (next_value - now_value) if next_value != now_value else 0.0
        crossing = index + share
        current.append((crossing, base))
        pieces.append((sign, current))
        sign, current = sign_next, [(crossing, base), (float(index + 1), next_value)]
    pieces.append((sign if sign is not None else 1, current))
    return pieces


def _pretty_chart_svg(closes, *, base=None, ma20=None, ma50=None,
                      height: int = 150) -> str:
    """시작가 기준선 위아래를 갈라 그린 종목 차트. 20선·50선도 함께 그린다.

    가로는 화면을 채우고(preserveAspectRatio="none") 세로만 못박는다. 늘려도
    선이 굵어지지 않게 vector-effect 를 건다 — 2026-08-26에 카드 그림에서
    7.9px 로 굵어진 것을 겪었다.
    """
    values = [float(v) for v in (closes or []) if v is not None and v == v]
    if len(values) < 2:
        return ""
    base = float(base) if base is not None else values[0]
    lines = []
    for color, series in ((_CHART_MA20, ma20), (_CHART_MA50, ma50)):
        cleaned = [(index, float(v)) for index, v in enumerate(series or [])
                   if v is not None and v == v]
        if len(cleaned) >= 2:
            lines.append((color, cleaned))

    span_values = values + [base] + [v for _c, pairs in lines for _i, v in pairs]
    low, high = min(span_values), max(span_values)
    reach = (high - low) or 1.0
    pad = height * 0.06
    inner = height - pad * 2
    width = 300.0
    step = width / (len(values) - 1)

    def _y(value):
        return pad + inner - (float(value) - low) / reach * inner

    body = [
        f'<line x1="0" y1="{_y(base):.2f}" x2="{width:.0f}" y2="{_y(base):.2f}" '
        'stroke="rgba(255,255,255,.42)" stroke-width="1" stroke-dasharray="4 4" '
        'vector-effect="non-scaling-stroke"/>'
    ]
    for piece_sign, piece in _split_pieces(values, base):
        if len(piece) < 2:
            continue
        color = _CHART_UP if piece_sign >= 0 else _CHART_DOWN
        path = " ".join(f"{x * step:.2f},{_y(v):.2f}" for x, v in piece)
        area = (f"{piece[0][0] * step:.2f},{_y(base):.2f} " + path
                + f" {piece[-1][0] * step:.2f},{_y(base):.2f}")
        body.append(f'<polygon points="{area}" fill="{color}" fill-opacity="0.16"/>')
        body.append(f'<polyline points="{path}" fill="none" stroke="{color}" '
                    'stroke-width="1.9" vector-effect="non-scaling-stroke"/>')
    for color, pairs in lines:
        path = " ".join(f"{index * step:.2f},{_y(v):.2f}" for index, v in pairs)
        body.append(f'<polyline points="{path}" fill="none" stroke="{color}" '
                    'stroke-width="1.4" stroke-opacity=".95" '
                    'vector-effect="non-scaling-stroke"/>')
    return (f'<svg class="j3-pretty-chart" viewBox="0 0 {width:.0f} {height}" '
            'preserveAspectRatio="none">' + "".join(body) + "</svg>")


def _payload_series(payload: dict, column: str):
    """차트 자료에서 한 줄을 꺼낸다. 없으면 빈 목록."""
    frame = payload.get("price") if isinstance(payload, dict) else None
    if frame is None or column not in getattr(frame, "columns", []):
        return []
    return [None if value != value else float(value) for value in frame[column].tolist()]


def _price_chart(payload: dict, timeframe: str, include_volume: bool = False,
                 height: int | None = None, compact: bool = False):
    """주가·20일선·50일선 한 장.

    compact를 켜면 눈금과 범례를 빼고 선만 남긴다 — 손톱만 한 그림에서는 눈금
    글자가 그림보다 자리를 더 먹는다(2026-08-07 상하님 지시 "캡쳐처럼 적게").
    """
    price = payload["price"].reset_index()
    date_column = price.columns[0]
    price = price.rename(columns={date_column: "날짜", "Close": "주가", "MA20": "20일선", "MA50": "50일선"})
    available = [column for column in ("주가", "20일선", "50일선") if column in price.columns]
    long_price = price.melt(id_vars=["날짜"], value_vars=available, var_name="구분", value_name="가격").dropna()
    # **셋을 같은 키로 맞춘다** (2026-08-27 상하님 지적 — 노트북 선택종목
    # 세부사항에서 차트 넷이 90·242·108·108px 로 제각각이었다).
    # 일봉만 아래에 거래량 칸이 더 붙어서 108 + 4 + 80 = 192px 가 되고, 눈금까지
    # 더하면 242px 였다. 키를 정해 주면 그 안에서 나눠 쓴다 — 위 주가 7, 아래
    # 거래량 3이다. 그러면 일봉·주봉·월봉이 모두 같은 키가 된다.
    # 키를 안 정해 주면(크게 보는 화면) 예전 그대로다.
    volume_height = 0
    if height is not None and include_volume:
        volume_height = max(24, int(round(height * 0.3)))
        line_height = max(40, height - volume_height - 4)
    else:
        line_height = height if height is not None else (220 if include_volume else 315)
    line = (
        alt.Chart(long_price)
        .mark_line(strokeWidth=1.4 if compact else 2)
        .encode(
            x=alt.X("날짜:T", title=None,
                    axis=None if compact
                    else alt.Axis(format="%y-%m", labelAngle=0, tickCount=5)),
            y=alt.Y("가격:Q", title=None, scale=alt.Scale(zero=False),
                    axis=None if compact else alt.Axis(tickCount=5)),
            color=alt.Color(
                "구분:N",
                title=None,
                scale=alt.Scale(
                    domain=["주가", "20일선", "50일선"],
                    range=["#69bff8", "#ff4d4f", "#a855f7"],
                ),
                legend=None if compact
                else alt.Legend(orient="top", direction="horizontal"),
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
            # 작게 그릴 때는 **날짜 눈금을 빼고 세로 눈금도 두 칸만** 둔다.
            # 바로 위 주가 그림과 같은 날짜라 두 번 적을 까닭이 없고, 그 눈금이
            # 30px 을 먹어 일봉만 옆 그림보다 커 보였다(2026-08-27 실측 161 vs 108).
            x=alt.X("날짜:T", title=None,
                    axis=None if compact
                    else alt.Axis(format="%y-%m", labelAngle=0, tickCount=5)),
            y=alt.Y("거래량:Q", title=None if compact else "거래량",
                    axis=alt.Axis(format="~s", tickCount=2 if compact else 3)),
            tooltip=[alt.Tooltip("날짜:T", title="날짜"), alt.Tooltip("거래량:Q", format=",.0f")],
        )
        .properties(height=volume_height or 80)
    )
    return alt.vconcat(line, bars, spacing=4).resolve_scale(x="shared")


def _render_day_price_row(metrics: dict, ticker: str | None = None,
                          *, panel: str = "") -> None:
    """**2주간 일별 시세 보기** — 눌러야 펴진다 (2026-09-02 상하님 지시).

    상하님 — *"선택종목 세부사항란의 「당일 가격 시가/고가/저가 한눈에 보기」를
    없애고, 제목을 「2주간 일별 시세 보기」란을 만들고, 클릭하면 「이 테마 설명」
    처럼 화면이 밑으로 내려가도록 만들어라. 그리고 닫힘 화면."*

    표는 네이버 증권의 「일별 시세」와 같은 칸이다 — 날짜 · 종가 · 전일대비 ·
    등락률. 거래일 **열흘**(2주)치를 최근 날이 맨 위로 오게 적는다.

    **없앤 것** — 「당일 가격 · 시가/고가/저가 한눈에 보기」 한 줄(현재가·전일
    종가·시가·고가·저가·지금 시간외). 그 값들은 바로 위 요약 줄과 아래 차트가
    이미 말하고, 폰에서 여섯 칸이 화면을 한 장 먹었다.

    **새로 받아 오는 것이 없다** — 카드가 쓰는 6개월 일봉을 다시 읽는다.
    못 받으면 표를 안 그린다(없는 것을 있는 것처럼 적지 않는다).
    """
    key = f"j3_daily_prices_{panel or 'x'}_{str(ticker or 'x').lower()}"
    if not _section_toggle(
        "📅 2주간 일별 시세 보기 — 클릭하면 볼 수 있습니다", key,
        close_label="2주간 일별 시세 닫기",
    ):
        return
    rows = []
    try:
        rows = j3data.daily_price_rows(ticker, days=10) or []
    except Exception:
        rows = []
    if not rows:
        st.caption("일별 시세를 불러오지 못했습니다.")
        _section_close(key, "2주간 일별 시세 닫기")
        return
    # **색은 앱 규칙을 그대로 쓴다** (2026-09-02 상하님 — "화면은 흰색으로
    # 하라는 게 아니다"). 칸 짜임만 네이버 「일별 시세」와 같게 하고, 흰 바탕·
    # 빨강 칩은 안 가져온다. 오른 값·빠진 값 색은 화면 다른 곳과 같은
    # `_sign_color` 하나로 정한다.
    body = []
    for row in rows:
        pct = row.get("pct")
        diff = row.get("diff") or 0.0
        tone = _sign_color(pct)
        arrow = "▲" if (pct or 0) >= 0 else "▼"
        pct_text = "—" if pct is None else _pct(pct)
        body.append(
            f"<tr><td class='j3dp-d'>{html.escape(str(row.get('date') or ''))}</td>"
            f"<td class='j3dp-c'>{_price(row.get('close'))}</td>"
            f"<td style='color:{tone}'>{arrow} {abs(diff):,.2f}</td>"
            f"<td style='color:{tone};font-weight:800'>{pct_text}</td></tr>"
        )
    st.markdown(
        "<style>"
        ".j3dp{width:100%;border-collapse:collapse;font-size:.93rem;margin:.2rem 0 .4rem;"
        "background:transparent}"
        ".j3dp th{color:#9aa0aa;font-weight:800;text-align:right;padding:.35rem .5rem;"
        "border-bottom:1px solid rgba(255,255,255,.18)}"
        ".j3dp th:first-child{text-align:left}"
        ".j3dp td{text-align:right;padding:.34rem .5rem;color:#e6e6e6;"
        "border-bottom:1px solid rgba(255,255,255,.06)}"
        ".j3dp .j3dp-d{text-align:left;color:#9aa0aa;font-weight:700}"
        ".j3dp .j3dp-c{font-weight:800;color:#e6e6e6}"
        "</style>"
        f"<table class='j3dp'><thead><tr><th>날짜</th><th>종가</th>"
        f"<th>전일대비</th><th>등락률</th></tr></thead><tbody>{''.join(body)}</tbody></table>",
        unsafe_allow_html=True,
    )
    st.caption("거래일 열흘치입니다. 최근 날이 맨 위입니다.")
    _section_close(key, "2주간 일별 시세 닫기")


# 일봉·주봉·월봉 셋의 높이. 상하님이 보여 준 지수 카드의 작은 그림(124×117)에
# 맞춘 값이다(2026-08-07). 이보다 키우면 '적게 해 달라'던 지적으로 돌아간다.
# **맨 위 큰 그림은 2026-08-21에 뺐다** — 같은 일봉이 한 화면에 두 번 있었다.
THUMB_CHART_HEIGHT = 108


def _render_price_chart_bundle(ticker: str, *, panel: str = "theme") -> None:
    """선택 종목의 **당일·일봉·주봉·월봉 넷을 한 판에** 그린다 (2026-08-28).

    상하님 지시 두 가지를 한 번에 담았다.
      · "당일·일봉(거래량 빼라)·주봉·월봉이 너무 못생겼다. 첫 번째 캡처처럼
         하되 일·주·월봉은 20선 50선은 넣어 줘."
      · "스마트폰 기준으로 당일·일봉 차트 같은 선상에 2개 해 주고 그 밑에
         주·월봉 차트. 맨 위 미국 전체시장 판단에 S&P500 옆에 나스닥 종합
         있는 것처럼."

    **스트림릿 칸(st.columns)을 안 쓴다.** 그것은 폰에서 위아래로 쌓여 한 줄에
    하나가 된다. 맨 위 지수 칸과 같은 방식으로 CSS 격자에 넣어야 폰에서도 두
    개씩 선다.

    **거래량은 뺐다**(상하님 지시). 그림 아래 막대가 차지하던 자리만큼 주가
    흐름이 커진다.

    눌러야 받아 온다(2026-07-30 사용자 지시 + 로딩 단축) — 늘 그리면 종목을 고를
    때마다 20년치를 받아 와 느려진다. 당일 그림도 이 안에서 함께 받는다.
    """
    if not _section_toggle(
        "📊 당일 · 일봉 · 주봉 · 월봉 보기", f"j3_bundle_open_{panel}",
        close_label="차트 닫기",
    ):
        return
    st.caption(
        "시작한 값에 회색 점선을 긋고, 그보다 위는 초록·아래는 붉은색입니다. "
        "20선은 주황색 · 50선은 보라색입니다."
    )
    boxes = []
    # 당일 그림 — 기준선은 전일 종가다. 20선·50선은 없다(하루치라 잴 수 없다).
    try:
        intraday = j3data.get_intraday_chart(ticker)
    except Exception:
        intraday = None
    if isinstance(intraday, dict) and intraday.get("ok"):
        closes = _payload_series(intraday, intraday["price"].columns[0])
        drawing = _pretty_chart_svg(closes, base=intraday.get("prev_close"), height=150)
        if drawing:
            boxes.append(("당일", drawing, intraday.get("source_time") or ""))
    chart_bundle = j3data.get_chart_bundle(ticker)
    if not chart_bundle.get("ok"):
        if not boxes:
            st.warning(f"차트 조회 실패: {_safe_error_text(chart_bundle.get('error'))}")
            _section_close(f"j3_bundle_open_{panel}", "차트 닫기")
            return
    else:
        for timeframe in ("일봉", "주봉", "월봉"):
            payload = chart_bundle["charts"].get(timeframe, {})
            if not payload.get("ok"):
                continue
            drawing = _pretty_chart_svg(
                _payload_series(payload, "Close"),
                ma20=_payload_series(payload, "MA20"),
                ma50=_payload_series(payload, "MA50"),
                height=150,
            )
            if drawing:
                boxes.append((timeframe, drawing, ""))
    if not boxes:
        st.warning("차트 자료가 없습니다.")
        _section_close(f"j3_bundle_open_{panel}", "차트 닫기")
        return
    cells = "".join(
        f"<div class='j3-chart-box'><div class='j3-chart-name'>{name}</div>{drawing}"
        + (f"<div class='j3-chart-when'>기준 {html.escape(str(when)[:16].replace('T', ' '))}</div>"
           if when else "")
        + "</div>"
        for name, drawing, when in boxes
    )
    st.markdown(f"<div class='j3-chart-grid'>{cells}</div>", unsafe_allow_html=True)
    if chart_bundle.get("stale"):
        st.warning("온라인 재조회가 실패해 마지막 정상 차트 자료를 표시하고 있습니다.")
    _section_close(f"j3_bundle_open_{panel}", "차트 닫기")


def _intraday_chart(payload: dict, height: int = 200, *, small: bool = False):
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
    # **작게 그릴 때는 눈금을 뺀다**(2026-08-21 상하님 지시 — 당일 차트를 위
    # 지수 카드 그림 크기로). 120×90에 축 글자까지 넣으면 그림이 안 보인다.
    if small:
        x_axis = alt.X("시각:T", title=None, axis=None)
        y_axis = alt.Y("가격:Q", title=None, scale=alt.Scale(zero=False), axis=None)
        shape = {"width": 120, "height": height}
    else:
        x_axis = alt.X("시각:T", title=None,
                       axis=alt.Axis(format="%H:%M", labelAngle=0, tickCount=5))
        y_axis = alt.Y("가격:Q", title=None, scale=alt.Scale(zero=False),
                       axis=alt.Axis(tickCount=5))
        shape = {"height": height}
    line = (
        alt.Chart(frame)
        .mark_line(strokeWidth=2, color=line_color)
        .encode(
            x=x_axis,
            y=y_axis,
            tooltip=[
                alt.Tooltip("시각:T", title="시각(뉴욕)", format="%H:%M"),
                alt.Tooltip("가격:Q", format=",.2f"),
            ],
        )
        .properties(**shape)
    )
    if prev_close:
        baseline = (
            alt.Chart(pd.DataFrame({"전일 종가": [float(prev_close)]}))
            .mark_rule(strokeDash=[4, 4], color="#9aa0aa")
            .encode(y="전일 종가:Q")
        )
        return line + baseline
    return line


# **5분마다 갱신한다**(2026-08-21 상하님 지시). 1분마다 돌면 화면이 쉴 새 없이
# 다시 그려지고, 그때마다 지수·선물·공포탐욕을 다시 받는다. 선물도 5분봉이라
# 1분 간격으로 볼 새 값이 없다.
@st.fragment(run_every=300)
def _render_market_overview() -> None:
    """시장판단은 페이지 최상단에서 5분마다 독립 갱신한다."""
    overview = j3data.get_market_overview()
    st.session_state["j3_market_overview"] = overview
    # 제목은 **절반 크기**다(2026-08-21 상하님 지시). st.subheader는 28px인데
    # 그만한 글씨가 필요한 자리가 아니다 — 아래 칸들이 주인공이다.
    st.markdown(
        f"<div class='{_SECTION_TITLE_CLASS}'>미국 전체시장 판단</div>",
        unsafe_allow_html=True,
    )
    if not overview.get("ok"):
        st.error(f"시장 자료 조회 실패: {_safe_error_text(overview.get('error'))}")
        st.caption("네트워크가 복구되면 5분 자동 갱신에서 다시 시도합니다.")
        return

    phase = overview.get("phase", {}).get("label", "—")
    if phase == "정규장 시간":
        phase_color = "#44f0a1"
    elif phase in ("프리마켓", "애프터마켓"):
        phase_color = "#ff9d3b"
    else:
        phase_color = "#ff5b5b"
    vix_row = overview["rows"].get("^VIX", {})
    vix_value = vix_row.get("current")
    # **직전 완료 장의 등락률을 쓴다** (2026-08-12 상하님 지적 "지금은 왜 0.00이
    # 되어 있나? 기준이 없냐?"). 원인은 야후다 — 미국장이 끝난 뒤 프리마켓 시간에
    # 야후가 **오늘 일봉을 전일 종가와 같은 값으로 미리 넣어** 둔다. 그것을 그대로
    # 쓰면 등락률이 0.00%가 된다. `last_session_change_pct`는 완성된 장만 보므로
    # 마감 뒤부터 다음 마감까지 안 흔들린다(2026-07-24에 같은 이유로 만들어 둔 값).
    # **장이 열려 있는 동안에는 오늘 값으로 움직인다** (2026-08-22 상하님 지적 —
    # "오늘 장중인데도 오늘값이 어제값 그대로다. 장이 끝나야 바뀐다").
    # 여기만 지수 카드와 달리 언제나 '직전 완료 장'을 쓰고 있어서, 정규장이
    # 돌아가는 내내 어제 등락률이 붙어 있었다. 지수 카드가 하는 대로 맞춘다.
    #
    # 정규장이 아닐 때 완료 장을 쓰는 까닭은 그대로다 — 야후가 프리마켓 시간에
    # **오늘 일봉을 전일 종가와 같은 값으로 미리 넣어** 둬서, 그것을 쓰면
    # 등락률이 0.00%가 된다(2026-08-12 상하님 지적 "지금은 왜 0.00이냐").
    vix_live = phase == "정규장 시간"
    vix_change = (vix_row.get("change_pct") if vix_live
                  else vix_row.get("last_session_change_pct"))
    if vix_change is None:
        vix_change = (vix_row.get("last_session_change_pct") if vix_live
                      else vix_row.get("change_pct"))
    # VIX는 '지금 수준(15.28)'과 '전일 대비(-1.16%)'가 서로 다른 값이다. 둘 다
    # 크게 적는다(2026-08-12 상하님 지시 "수치와 +− 글자 둘 다 크게").
    # VIX는 오르면 위험이라 색을 뒤집는다.
    # **VIX 글자와 숫자는 보라색**이다(2026-08-21 상하님 지시). 오르내림 표시는
    # 지금까지대로 둔다 — VIX는 오르면 위험이라 색이 뒤집혀 있다.
    vix_sub = (
        f"<span style='font-size:1.25rem;font-weight:800;color:#b98cff'>"
        f"VIX {_number(vix_value, 2)}</span> "
        f"<span style='font-size:1.25rem;font-weight:800;"
        f"color:{_sign_color(None if vix_change is None else -float(vix_change))}'>"
        f"{_pct(vix_change)}</span>"
    )
    top_cells = [
        # 시장 국면도 공포·탐욕과 같은 반원 게이지로 통일한다 — 국면 이름만 크게
        # 적으면 '하락 압력 큼'이 5점인지 29점인지 알 수 없다(2026-07-24 사용자 지시).
        # 4대 지수를 게이지 앞에 둔다 — '시장 국면' 카드 위에 올려 달라는 요청
        # (2026-07-25). 폰에서는 숫자 칸이 앞, 게이지가 뒤로 가는 규칙 그대로다.
        # 선물이 **맨 앞**이다(2026-08-19 상하님 지시). 4대 지수는 정규장이 끝나면
        # 멈추는데 선물은 밤새 움직여, 장 열리기 전 방향을 먼저 알려 준다.
        _us_futures_cell(),
        *_us_index_cells(overview, phase),
        # 바늘은 **직전 완료 미국장**에 세운다(2026-08-12 상하님 지시) — 프리마켓·
        # 장중 값으로 매번 다시 재면 하루 종일 조금씩 움직인다. 실시간 값은 상자
        # 아래 '지금 (참고)' 줄로 남는다. 한국테마는 지금까지대로 실시간이다.
        regime_gauge_ui.regime_box_html(overview, freeze=True),
        # **SPY·QQQ 두 칸은 뺐다** (2026-08-28 상하님 지시 — 캡처에 ×표).
        # 지수 넷(S&P500·나스닥 종합·다우·나스닥100)이 같은 것을 이미 말하고 있어
        # 화면만 길어졌다. 값 자체는 그대로 받는다 — 시장 판단 점수가 SPY·QQQ의
        # 이동평균을 쓰기 때문이다(overview["rows"]). 화면에서만 안 보인다.
        # 되살리려면 이 줄의 주석을 풀면 된다: *_us_etf_cells(overview),
        _market_phase_cell(phase, phase_color, vix_sub),
        # 시장 현황(업종 지도)은 **시장 상황 바로 뒤, 게이지 앞**이다
        # (2026-08-28 상하님 지시). 폰에서는 게이지 둘이 order:10 으로 맨 뒤에
        # 가므로, 이 칸에 order:5 를 주어 그 사이에 서게 한다(mobile_ui).
        _sector_map_cell(phase),
        _fear_greed_box(),
        # 나스닥 고점 대비도 **이 묶음 안**이다(2026-09-03 새 디자인). 밖에 두면
        # 시장 국면·공포탐욕과 한 줄에 세울 수가 없다. 그리는 내용은 그대로다.
        _nasdaq_drawdown_html(),
    ]
    # 게이지 스타일은 지표 줄과 따로 내보낸다. 줄 안에 <style>을 끼워 넣으면
    # 스트림릿 마크다운이 그 덩어리를 HTML로 안 보고 글로 흘려버려서, CSS가 글자로
    # 찍히고 SPY·QQQ의 '$' 두 개가 수식으로 잡혔다(2026-07-24 실제 깨짐).
    st.markdown(_SECTION_TITLE_CSS, unsafe_allow_html=True)
    st.markdown(f"<style>{fear_greed_ui.CSS}</style>", unsafe_allow_html=True)
    st.markdown(f"<div class='j3-top-row'>{''.join(top_cells)}</div>", unsafe_allow_html=True)
    # 긴 설명은 접어 둔다 — 폰에서 이 글이 첫 화면을 다 먹었다(2026-07-25 사용자 지시:
    # "클릭하면 내용이 나오도록"). 값·판정은 그대로이고 보여주는 방식만 바꾼다.
    with st.expander("조건점수·시장 상황 설명 보기", expanded=False):
        st.markdown(
            f"""
            <div class="j3-score-guide">
                <b>조건점수 {overview['score']}/100</b>은 상승장 확인 조건에서 얻은 점수이며
                <b>승률이 아닙니다</b>.<br>
                {_regime_range_text()}<br>
                {_market_score_detail(overview)}<br>
                이 점수와 아래 <b>선행신호 카드는 서로 다른 것을 잽니다</b>(2026-07-30 질문).
                이 점수는 <b>주가가 20·50일선 위에 있는지</b>를 보고, 선행신호는 <b>오늘 선물·반도체가
                오르는지</b>를 봅니다. 그래서 한참 빠져 있던 자리에서 오늘 반등이 시작되면
                선행신호는 켜지는데 이 점수는 아직 낮습니다 — 둘이 달라도 모순이 아닙니다.
                "오늘 방향"과 "평균선 위/아래"는 다른 이야기입니다.<br>
                시장 상황은 미국 세션 단계입니다(뉴욕시각 기준): 프리마켓 04:00~09:30 → 정규장 09:30~16:00
                → 애프터마켓 16:00~20:00 → 장 마감<br>
                VIX 두 값은 서로 다른 것입니다 — 위 <b>VIX 18.70 같은 숫자는 공포지수 현재 수준</b>(25 미만이면
                과열 아님)이고, 아래 선행신호 카드의 <b>VIX +12.38% 같은 값은 전일 종가 대비 변동률</b>입니다.
                수준은 낮은데 하루 변동만 큰 날이 있어 두 값이 함께 있어도 모순이 아닙니다.<br>
                공포·탐욕 지수는 CNN이 7개 심리 지표로 집계한 값(0 극단적 공포 ~ 100 극단적 탐욕)으로
                참고용이며 점수·판정에는 반영하지 않습니다.
            </div>
            """,
            unsafe_allow_html=True,
        )
    # 시장 전체 흐름·행동 기준도 접는다(2026-07-25 사용자 지시: "다 숨겨라").
    with st.expander("시장 전체 흐름 · 행동 기준 보기", expanded=False):
        st.markdown(
            f"""
            <div class="j3-market-flow">
                <div class="j3-flow-label">시장 전체 흐름</div>
                <div class="j3-flow-body">{_market_flow_text(overview)}</div>
            </div>
            <div class="j3-action-box">
                <div class="j3-action-label">행동 기준</div>
                <div class="j3-action-posture">{overview['posture']}</div>
                <div class="j3-action-detail">{_market_action_detail(overview)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    # **맨 아래 「최근 가용 시세…」 한 줄은 뺐다** (2026-08-28 상하님 지시 —
    # 캡처에 ×표, "여백 두지 말고 위로 올려라"). 줄을 지우면 그 자리가 차지하던
    # 여백도 같이 없어져 아래 「미국장 시장 상태」가 위로 붙는다.
    # 자료가 낡았을 때는 화면 곳곳(테마·상승장)에서 따로 알린다.



def _sparkline_svg(payload, up_color: str, down_color: str,
                   width: float = 120.0, height: int = 90) -> str:
    """네이버 금융식 그림 — 당일 분봉 + 전일 종가 기준선(2026-07-25 사용자 지적 반영).

    기준선 위 구간과 아래 구간을 다른 색으로 그린다. 색은 시장 규칙을 부르는 쪽이
    준다(미국은 오르면 파랑, 한국은 오르면 빨강).
    """
    if not isinstance(payload, dict):
        return ""
    points = [float(v) for v in (payload.get("points") or []) if v is not None]
    base = payload.get("base")
    if len(points) < 2 or not base:
        return ""
    low, high = min(points + [base]), max(points + [base])
    span = (high - low) or 1.0
    pad = 6.0
    inner = height - pad * 2
    step = width / (len(points) - 1)

    def _y(value):
        return pad + inner - (value - low) / span * inner

    base_y = _y(base)
    segments = []
    for index in range(len(points) - 1):
        first, second = points[index], points[index + 1]
        color = up_color if (first + second) / 2 >= base else down_color
        segments.append(
            f"<line x1='{index * step:.1f}' y1='{_y(first):.1f}' "
            f"x2='{(index + 1) * step:.1f}' y2='{_y(second):.1f}' "
            f"stroke='{color}' stroke-width='1.6' stroke-linecap='round' "
            f"vector-effect='non-scaling-stroke'/>"
        )
    fill = up_color if points[-1] >= base else down_color
    area = f"0,{base_y:.1f} " + " ".join(
        f"{i * step:.1f},{_y(v):.1f}" for i, v in enumerate(points)
    ) + f" {width:.1f},{base_y:.1f}"
    # **가로로 늘려도 선이 굵어지지 않는다** (2026-08-28).
    # 태블릿에서는 이 그림이 칸 폭을 채우도록 CSS가 늘린다(mobile_ui). 늘리면
    # preserveAspectRatio='none' 이 그림을 옆으로 잡아당기는데, 그때 선까지 같이
    # 굵어진다 — 카드 그림에서 이미 겪은 일이다(7.9px → 1.8px, 2026-08-26).
    # vector-effect 는 "선은 늘리지 말고 적어 준 굵기 그대로"라는 뜻이다.
    return (
        f"<svg viewBox='0 0 {width:.0f} {height}' width='{width:.0f}' height='{height}' "
        f"preserveAspectRatio='none' "
        f"style='display:block; margin:.4rem 0 .1rem;"
        f" border:1px solid rgba(255,255,255,.22); border-radius:8px;"
        f" background:rgba(255,255,255,.03)'>"
        f"<polygon points='{area}' fill='{fill}' fill-opacity='0.14'/>"
        f"<line x1='0' y1='{base_y:.1f}' x2='{width:.0f}' y2='{base_y:.1f}' "
        f"stroke='rgba(255,255,255,.38)' stroke-width='1' stroke-dasharray='4 4' "
        f"vector-effect='non-scaling-stroke'/>"
        + "".join(segments) + "</svg>"
    )


# 폰·태블릿에서 이 두 칸은 **나란히 선다** (2026-08-28 상하님 지시 — "나스닥100
# 선물과 시장상황 VIX를 같이 둬라, S&P500과 같이 있으니 키높이가 안 맞다").
#
# 둘 다 밑줄이 길어 두 줄로 접히는 칸이라, 한 줄짜리 지수 칸과 짝을 지으면 키가
# 어긋난다. 차례는 mobile_ui 가 정한다(선물 1 · 시장 상황 2 · 업종 지도 5 ·
# 게이지 10). 노트북은 한 줄에 다섯 칸이 들어가 짝이 안 생기므로 그대로 둔다.
_FUTURES_CLASS = "j3-idx-futures"
_PHASE_CLASS = "j3-idx-phase"


def _us_futures_cell() -> str:
    """나스닥100 선물 최신 1분봉 — **미국 화면 맨 앞 칸** (2026-08-19 상하님 지시).

    상하님 — "한국테마에 있는 미국 나스닥100 선물 미국테마에도 넣어라 가장 위에."

    **왜 맨 앞인가** — 4대 지수는 정규장이 끝나면 멈춘다. 선물은 밤새 움직이므로
    장 열리기 전에 미국이 어느 쪽으로 갈지 먼저 보여주는 칸이다.

    **자료는 한국테마 모듈에서 읽어 온다**(jarvis4_data.get_us_futures_live).
    한국 파일을 고치지 않는다 — 읽기만 한다(2026-08-19 상하님 지시 "한국테마는
    하지 말라"). 같은 것을 여기 새로 쓰면 야후에 같은 요청을 두 번 보내게 되고,
    두 화면의 숫자가 조용히 갈라진다.

    모듈이 없거나 조회가 실패해도 **화면을 죽이지 않는다** — 칸만 '—'로 둔다.
    """
    # **5분봉이다**(2026-08-21 상하님 지시 — "1분마다 로딩하니 너무 자주 로딩하는
    # 듯하다"). 한국테마는 1분봉 그대로다 — 부르는 쪽이 정하게 해 두었다.
    label = "나스닥100 선물 (5분봉)"
    try:
        import jarvis4_data as j4data
    except Exception:
        return _top_metric(label, "—", "#9aa0aa", "자료 없음", extra_class=_FUTURES_CLASS)
    fetcher = getattr(j4data, "get_us_futures_live", None)
    if fetcher is None:
        return _top_metric(label, "—", "#9aa0aa", "모듈 갱신 대기", extra_class=_FUTURES_CLASS)
    try:
        # 5분봉이므로 공책도 5분 동안 쓴다 — 1분마다 다시 받을 까닭이 없다.
        futures = fetcher(ttl_seconds=300, interval="5m")
    except TypeError:
        # 옛 모듈이 프로세스에 남아 있으면 인자를 모른다 — 그때는 예전처럼 부른다.
        try:
            futures = fetcher()
        except Exception:
            return _top_metric(label, "—", "#9aa0aa", "자료 부족", extra_class=_FUTURES_CLASS)
    except Exception:
        return _top_metric(label, "—", "#9aa0aa", "자료 부족", extra_class=_FUTURES_CLASS)
    if not futures.get("ok"):
        return _top_metric(label, "—", "#9aa0aa", "자료 부족", extra_class=_FUTURES_CLASS)
    values = futures.get("values") or {}
    nasdaq = values.get("NQ=F") or {}
    sp500 = values.get("ES=F") or {}
    if not nasdaq.get("current"):
        return _top_metric(label, "—", "#9aa0aa", "자료 부족", extra_class=_FUTURES_CLASS)
    change = nasdaq.get("change_pct")
    # **미국은 오르면 파랑**이다(이 화면의 약속). 한국 화면과 색이 반대다 —
    # _sign_class가 그 규칙을 갖고 있으므로 그것을 쓴다.
    sub = f"<span class='{_sign_class(change)}'>{_pct(change)}</span>"
    if sp500.get("change_pct") is not None:
        sub += (f" <span class='j3-muted'>· S&P500 선물</span> "
                f"<span class='{_sign_class(sp500['change_pct'])}'>"
                f"{float(sp500['change_pct']):+.2f}%</span>")
    # **바꿔 보여주는 틀을 쓰지 않는다**(2026-08-21 상하님 지적 — 눌렀더니 그림이
    # 사라졌다). 선물에는 '일봉 6개월' 그림이 없어서, 틀에 넣으면 손을 올렸을 때
    # 당일 그림만 감추고 보여줄 것이 없다. 그림은 그대로 두고 지수 칸과 밑선을
    # 맞추는 '당일' 글자만 붙인다.
    chart = _sparkline_svg(nasdaq.get("chart") or {}, "#4da6ff", "#ff5b5b")
    if chart:
        chart += "<div class='j3-idx-cap'>당일</div>"
    return (
        f"<div class='j3-top-cell {_FUTURES_CLASS}'>"
        f"<div class='j3-top-label j3-idx-label'>{label}</div>"
        f"<div class='j3-top-val j3-idx-val {_sign_class(change)}'>"
        f"{float(nasdaq['current']):,.0f}</div>"
        f"<div class='j3-top-sub j3-idx-sub'>{sub}</div>"
        + chart
        + "</div>"
    )


def _us_index_cells(overview: dict, phase: str) -> list:
    """4대 지수 줄 — S&P 500 · 나스닥 종합 · 다우존스 · 나스닥 100 (2026-07-24 추가).

    ETF(SPY·QQQ)가 아니라 지수를 그대로 쓴다. 정규장이 아니면 마지막으로 끝난
    정규장의 종가와 등락을 보여준다 — 지수는 시간외 거래가 없어서 '지금 값'을
    쓰면 등락이 0%로 나온다.
    """
    display = getattr(j3data, "US_INDEX_DISPLAY", ())
    if not display:
        return []
    try:
        sparklines = j3data.get_index_sparklines()
    except Exception:
        sparklines = {}
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
            f"<div class='j3-top-cell'>"
            f"<div class='j3-top-label j3-idx-label'>{name}</div>"
            f"<div class='j3-top-val j3-idx-val' style='color:#e6e6e6'>{_number(row.get('current'), 2)}</div>"
            f"<div class='j3-top-sub j3-idx-sub {_sign_class(change)}'>{_pct(change)} "
            f"<span class='j3-muted j3-idx-note'>· {note}</span></div>"
            # 손을 올리면 같은 자리에서 '일봉 6개월'로 바뀐다(2026-08-06 사용자 지시).
            # 클릭으로 안 하는 이유 — 스트림릿은 누르면 화면을 통째로 다시 그려서
            # 움직임이 버벅거린다.
            + _index_chart_swap(sparklines.get(symbol), key=f"idx{symbol}")
            + "</div>"
        )
    return cells


def _index_chart_swap(spark: dict | None, *, width: float = 120.0,
                      height: int = 90, key: str = "") -> str:
    """'당일' 그림과 '일봉 6개월' 그림을 같은 자리에 겹쳐 두고 바꿔 보여 준다.

    두 그림이 한 틀 안에 포개져 있어 **자리를 새로 만들지 않는다** — 그래서
    나타나고 사라져도 아래 화면이 밀리지 않고 옆 칸을 덮지도 않는다.

    바꾸는 길이 둘이다 — 마우스는 올리기만 하면 되고, **손가락은 눌렀다 다시
    누르면 돌아온다**(2026-08-07 상하님 지적). 손가락 쪽은 숨긴 체크상자가 맡는다.
    자리마다 이름이 달라야 하나만 눌러도 옆 칸까지 같이 바뀌지 않는다.
    """
    spark = spark or {}
    today = _sparkline_svg(spark, "#4da6ff", "#ff5b5b", width=width, height=height)
    if not today:
        return ""
    daily_points = spark.get("daily_points") or []
    daily = _sparkline_svg(
        {"points": daily_points, "base": spark.get("daily_base")},
        "#4da6ff", "#ff5b5b", width=width, height=height,
    ) if len(daily_points) >= 2 else ""
    # id에 쓸 수 없는 글자(^ 같은 것)를 걸러 낸다 — 지수 이름은 '^IXIC' 꼴이다.
    tap_id = "j3idx_" + re.sub(r"[^0-9A-Za-z]+", "", str(key) or str(int(width)))
    if not daily:
        # 바꿔 보여줄 두 번째 그림이 없으면 **틀을 씌우지 않는다.** 씌우면 손을
        # 올렸을 때 당일 그림만 감추고 보여줄 것이 없어 칸이 비어 버린다
        # (2026-08-21 상하님 지적). 키를 맞출 자리는 부르는 쪽이 붙인다.
        return today
    return (
        "<div class='j3-idx-swap'>"
        f"<input type='checkbox' id='{tap_id}' class='j3-idx-tap'>"
        f"<label for='{tap_id}' class='j3-idx-tapzone'></label>"
        f"<div class='j3-idx-now'>{today}<div class='j3-idx-cap'>당일</div></div>"
        f"<div class='j3-idx-more'>{daily}"
        "<div class='j3-idx-cap j3-idx-cap-daily'>일봉 6개월</div></div>"
        "</div>"
    )


def _render_nasdaq_drawdown() -> None:
    """나스닥 고점 대비 줄을 그린다. 만드는 일은 아래 함수가 한다."""
    drawn = _nasdaq_drawdown_html()
    if drawn:
        st.markdown(drawn, unsafe_allow_html=True)


def _nasdaq_drawdown_html() -> str:
    """나스닥이 고점에서 얼마나 내려와 있나 — 한 줄 (2026-08-01 사용자 지시).

    **글자로 돌려준다**(2026-09-03). 새 디자인에서 이 줄을 시장 국면·공포탐욕과
    **한 줄에 나란히** 세우려면, 그 셋이 같은 묶음 안에 있어야 한다. 그러려면
    이 줄이 제 자리에서 바로 그려지지 말고 글자로 넘어와야 한다.
    돌려줄 것이 없으면 빈 글자다.

    55년치로 재 보니 '고점 대비 낙폭' 하나가 다른 어떤 신호보다 잘 들었다.
    12% 넘게 빠지면 2년 뒤 100번 중 86번(아무 날이나 샀으면 81번)이었고,
    8% 정도로는 오히려 기준선보다 못했다. 그래서 문턱을 12%로 둔다.
    숫자와 문턱은 `jarvis3_data`가 정한다 — 화면은 받아 적기만 한다.
    """
    state = j3data.get_nasdaq_drawdown()
    if not state.get("ok"):
        return ""
    pct = float(state.get("drawdown_pct") or 0)
    entry = float(state.get("entry_pct") or -12)
    reached = pct <= entry
    # **막대 한가운데가 전고점이다**(2026-08-09 상하님 지시).
    #   왼쪽 끝 = 고점에서 25% 아래 · 한가운데 = 고점 그 자리 · 오른쪽 끝 = 고점 위 25%
    # 그래서 지금 -1.5%면 막대가 한가운데에 조금 못 미치고, 전고점을 넘으면
    # 한가운데를 지나 오른쪽으로 간다. 예전에는 왼쪽 0 ~ 오른쪽 25%(낙폭)이라
    # 막대가 길수록 나쁜 뜻이어서 거꾸로 읽혔다.
    span = 25.0
    center = 50.0
    fill = max(0.0, min(100.0, center + (pct / span) * center))
    mark = max(0.0, min(100.0, center + (entry / span) * center))
    # 한가운데를 넘었으면 '얼마나 넘었나'로 말이 바뀐다.
    above = pct > 0
    headline = "전고점 위" if above else "나스닥 고점 대비"
    return (
        "<div class='j3-ndd'>"
        f"<div class='j3-ndd-head'><b class='j3-ndd-title'>{headline}</b> "
        f"<span class='j3-ndd-val' style='color:{_sign_color(pct)}'>{pct:+.1f}%</span> "
        f"<span class='j3-ndd-state' style='color:{state.get('color')}'>"
        f"{html.escape(str(state.get('state') or ''))}</span></div>"
        # 막대 안에 한가운데 선(전고점)과 문턱 선(사는 자리)을 같이 세운다.
        f"<div class='j3-ndd-bar'><span class='j3-ndd-fill' style='width:{fill:.1f}%'></span>"
        f"<span class='j3-ndd-mark' style='left:{mark:.1f}%'></span>"
        "<span class='j3-ndd-center'></span></div>"
        "<div class='j3-ndd-scale'><span>고점 −25%</span>"
        "<span class='j3-ndd-scale-mid'>전고점</span><span>고점 +25%</span></div>"
        # '지금 · 1년 최고 · 문턱 …' 줄은 2026-08-06에 뺐다(사용자 지시). 막대와
        # 위 % 숫자가 같은 말을 하고 있어 줄만 길었다.
        # 예전에는 '100번 중 86번이었습니다'로 끝나 **무엇이 86번인지**가 빠져
        # 있었다(2026-08-06 상하님 지적). '86번 이익'으로 채운다.
        "<div class='j3-ndd-note'><span class='j3-ndd-key'>55년치</span>로 재 보니 "
        "<span class='j3-ndd-key'>12% 넘게 빠졌을 때</span> 사서 2년 뒤에 팔면 "
        "<span class='j3-ndd-key'>100번 중 86번 이익</span>이었습니다"
        "(아무 날이나 샀으면 81번 이익). "
        "<span class='j3-ndd-key'>8% 정도로는 기준선보다 못했습니다.</span> "
        "12%냐 15%냐는 자료로 가릴 수 없어 <span class='j3-ndd-key'>‘12% 넘게’</span>까지만 봅니다. "
        "다이버전스는 6개 설정 중 0개에서 져서 쓰지 않습니다."
        "</div></div>"
    )


def _us_etf_cells(overview: dict) -> list:
    """SPY·QQQ 칸 — 지수 칸과 같은 옷을 입히고 그림을 둘 넣는다(2026-08-01 지시).

    당일 그림의 기준선은 전일 종가, 일봉 그림의 기준선은 석 달 전 종가다.
    그림 자료를 못 받으면 그 칸은 지금까지처럼 숫자만 보여준다.
    """
    try:
        charts = j3data.get_etf_sparklines()
    except Exception:
        charts = {}
    rows = overview.get("rows") or {}
    cells = []
    display_name = {"SPY": "SPY (미국 대표주)", "QQQ": "QQQ (미국 기술주)"}
    for symbol in ("SPY", "QQQ"):
        row = rows.get(symbol) or {}
        change = row.get("change_pct")
        pair = charts.get(symbol) or {}
        # 위 지수 칸과 같게 — 손을 올리면 같은 자리에서 '일봉 6개월'로 바뀐다
        # (2026-08-06). 두 그림을 늘 펴 두니 칸이 넓어 화면 위쪽이 길었다.
        chart_html = _index_chart_swap(
            {**(pair.get("intraday") or {}),
             "daily_points": ((pair.get("daily") or {}).get("points") or []),
             "daily_base": (pair.get("daily") or {}).get("base")},
            width=104, height=78, key=f"etf{symbol}",
        )
        cells.append(
            f"<div class='j3-top-cell j3-idx-wide'>"
            f"<div class='j3-top-label j3-idx-label'>{display_name[symbol]}</div>"
            f"<div class='j3-top-val j3-idx-val' style='color:#e6e6e6'>{_price(row.get('current'))}</div>"
            f"<div class='j3-top-sub j3-idx-sub {_sign_class(change)}'>{_pct(change)}</div>"
            + chart_html + "</div>"
        )
    return cells


# 지도 칸의 세로:가로 비율. 상자 자리를 서버에서 계산하므로 화면에서도 이 비율을
# 지켜야 상자가 찌그러지지 않는다(CSS aspect-ratio 로 같은 값을 건다).
_SECTOR_MAP_W = 100.0
_SECTOR_MAP_H = 58.0


def _squarify(areas: list[float], x: float, y: float, width: float, height: float,
              out: list) -> None:
    """넓이가 값에 비례하는 상자로 칸을 채운다(squarify).

    큰 것부터 넣으면서 **정사각형에 가깝게** 되도록 한 줄에 몇 개를 담을지 정한다.
    한 줄로 죽 자르는 방법보다 글자가 들어갈 자리가 잘 나온다 — 네이버 업종 지도가
    쓰는 것과 같은 방식이다.
    """
    if not areas:
        return
    if len(areas) == 1 or width <= 0 or height <= 0:
        offset = y
        total = sum(areas) or 1.0
        for area in areas:
            share = area / total * height
            out.append((x, offset, width, share))
            offset += share
        return

    def _worst(row: list[float], side: float) -> float:
        total = sum(row)
        if total <= 0 or side <= 0:
            return float("inf")
        return max(side * side * max(row) / (total * total),
                   (total * total) / (side * side * min(row)))

    side = min(width, height)
    row, index = [areas[0]], 1
    while index < len(areas) and _worst(row + [areas[index]], side) <= _worst(row, side):
        row.append(areas[index])
        index += 1
    total = sum(row)
    if width >= height:
        band = total / height
        offset = y
        for area in row:
            share = area / total * height
            out.append((x, offset, band, share))
            offset += share
        _squarify(areas[index:], x + band, y, width - band, height, out)
    else:
        band = total / width
        offset = x
        for area in row:
            share = area / total * width
            out.append((offset, y, share, band))
            offset += share
        _squarify(areas[index:], x, y + band, width, height - band, out)


def _sector_tone(change) -> str:
    """오르면 파랑, 내리면 빨강. 많이 움직일수록 진하다(미국 화면 색 규칙)."""
    if change is None:
        return "#22304a"
    try:
        value = float(change)
    except (TypeError, ValueError):
        return "#22304a"
    strength = min(abs(value) / 2.0, 1.0)          # 2% 이상이면 가장 진한 색
    target = (77, 166, 255) if value >= 0 else (255, 91, 91)
    dark = (12, 28, 52)
    mixed = tuple(round(base + (tip - base) * (0.22 + 0.78 * strength))
                  for base, tip in zip(dark, target))
    return "#%02x%02x%02x" % mixed


def _sector_map_cell(phase: str) -> str:
    """시장 현황 — 미국 업종 지도 (2026-08-28 상하님 지시).

    상하님 — "시장국면·상승여건양호 사이에 세 번째 캡처처럼 시장현황을 미국 자료
    찾아서 넣어 줘."

    칸 크기는 그 업종이 **미국 시장에서 차지하는 몫**(야후가 매번 새로 계산해 준다),
    색과 숫자는 그 업종 대표 ETF의 등락이다. 밑줄은 자비스가 보는 미국 명부에서
    오늘 오른 종목·내린 종목 수다.

    **자료를 여기서 기다리지 않는다.** 공책에 없으면 한 줄만 적고 넘어간다 —
    뒤에서 받아 두므로 다음 판에는 채워져 있다(jarvis3_data.get_us_sector_map).
    """
    try:
        sector = j3data.get_us_sector_map()
    except Exception:
        return ""
    rows = [row for row in (sector.get("rows") or []) if row.get("weight")]
    if not rows:
        note = "업종 지도를 받는 중입니다" if sector.get("pending") else "업종 자료를 아직 못 받았습니다"
        return ("<div class='j3-top-cell j3-sector-map'>"
                "<div class='j3-top-label j3-idx-label'>시장 현황</div>"
                f"<div class='j3-sector-wait'>{note}</div></div>")

    live = phase == "정규장 시간"
    for row in rows:
        change = row.get("change_pct") if live else row.get("last_session_change_pct")
        if change is None:
            change = row.get("last_session_change_pct") if live else row.get("change_pct")
        row["shown_change"] = change
    rows.sort(key=lambda item: float(item["weight"]), reverse=True)

    total_weight = sum(float(row["weight"]) for row in rows) or 1.0
    scale = (_SECTOR_MAP_W * _SECTOR_MAP_H) / total_weight
    boxes: list = []
    _squarify([float(row["weight"]) * scale for row in rows],
              0.0, 0.0, _SECTOR_MAP_W, _SECTOR_MAP_H, boxes)

    tiles = []
    for row, (x, y, width, height) in zip(rows, boxes):
        change = row.get("shown_change")
        # 상자가 작으면 글자가 삐져나온다 — 작은 칸은 이름만, 더 작으면 아무것도 안 적는다.
        size = "big" if (width >= 22 and height >= 18) else "mid" if (width >= 13 and height >= 11) else "small"
        text = f"<div class='j3-sector-name'>{row['name']}</div>"
        if size != "small":
            text += (f"<div class='j3-sector-pct'>{_pct(change)}</div>")
        tiles.append(
            f"<div class='j3-sector-tile {size}' title='{row['name']} · {row['etf']} · {_pct(change)}' "
            f"style='left:{x / _SECTOR_MAP_W * 100:.3f}%;top:{y / _SECTOR_MAP_H * 100:.3f}%;"
            f"width:{width / _SECTOR_MAP_W * 100:.3f}%;height:{height / _SECTOR_MAP_H * 100:.3f}%;"
            f"background:{_sector_tone(change)}'>{text}</div>"
        )

    breadth = sector.get("breadth") or {}
    foot = ""
    if breadth.get("total"):
        total = float(breadth["total"])
        up, flat, down = breadth["up"], breadth["flat"], breadth["down"]
        foot = (
            "<div class='j3-sector-bar'>"
            f"<span style='width:{up / total * 100:.1f}%;background:#4da6ff'></span>"
            f"<span style='width:{flat / total * 100:.1f}%;background:#7a8494'></span>"
            f"<span style='width:{down / total * 100:.1f}%;background:#ff5b5b'></span></div>"
            f"<div class='j3-sector-foot'><span class='j3-up'>▲ 오름 {up}</span>"
            f"<span class='j3-muted'>― 그대로 {flat}</span>"
            f"<span class='j3-down'>▼ 내림 {down}</span>"
            f"<span class='j3-sector-note'>자비스가 보는 미국 {breadth['total']}종목 기준</span></div>"
        )
    return (
        "<div class='j3-top-cell j3-sector-map'>"
        "<div class='j3-top-label j3-idx-label'>시장 현황</div>"
        "<div class='j3-sector-sub'>칸 크기 = 미국 시장에서 차지하는 몫 · "
        f"색 = {'오늘' if live else '직전 장'} 오르내림</div>"
        f"<div class='j3-sector-grid'>{''.join(tiles)}</div>"
        + foot + "</div>"
    )


def _market_phase_cell(phase: str, phase_color: str, vix_sub: str) -> str:
    """시장 상황 칸 — VIX 그림을 지수 칸과 같은 모양으로 붙인다(2026-08-21 지시).

    상하님 — "시장상황 vix지수 이것도 나스닥 종합처럼 그래프 넣어라. 당일 그래프
    그리고 클릭하면 일봉 6개월 나오게 하고 … 옆에 QQQ 지수와 키높이하고."

    그림이 없으면 지금까지처럼 숫자만 보여준다 — 자료 탓에 칸이 사라지면 안 된다.
    """
    try:
        spark = (j3data.get_index_sparklines() or {}).get("^VIX")
    except Exception:
        spark = None
    # 그림 높이를 QQQ 칸보다 4px 낮춘다 — VIX 숫자 줄이 1.25rem이라 그만큼 높아서,
    # 그냥 두면 이 칸만 196px가 되어 옆 칸과 밑선이 어긋난다(2026-08-21 실측).
    chart = _index_chart_swap(spark, width=104, height=74, key="vix") if spark else ""
    if not chart:
        return _top_metric("시장 상황", phase, phase_color, vix_sub, sub_color="#ff5b5b",
                           extra_class=_PHASE_CLASS)
    return (
        f"<div class='j3-top-cell j3-idx-wide {_PHASE_CLASS}'>"
        "<div class='j3-top-label j3-idx-label'>시장 상황</div>"
        f"<div class='j3-top-val j3-idx-val' style='color:{phase_color}'>{phase}</div>"
        f"<div class='j3-top-sub j3-idx-sub'>{vix_sub}</div>"
        + chart + "</div>"
    )


def _fear_greed_box() -> str:
    """상단 줄에 들어가는 공포·탐욕 게이지 박스. CNN 그림을 직접 그린 것이다.

    스타일도 함께 실어 보낸다 — 페이지 맨 위 <style> 덩어리는 로그인 문 앞이라
    fear_greed_ui를 아직 import하기 전이다.
    """
    fetcher = getattr(j3data, "get_fear_greed", None)
    data = fetcher() if fetcher else {"ok": False}
    return fear_greed_ui.box_html(data)


def _leader_max() -> float:
    """대장주 조건점수 만점. **모듈에서 읽는다** — 화면에 박아 두면 어긋난다.

    **여기에 @st.fragment 를 붙이면 안 된다.** 2026-08-26까지 바로 위에 있던
    @st.fragment(run_every=60) 을 이 함수가 가로채고 있었다. 87e0d77 이 이 함수를
    데코레이터와 그 임자(_render_selected_live_quote) **사이에** 끼워 넣은 탓이다.
    빈 줄이 하나 있어서 눈에 안 띄었지만, 파이썬은 빈 줄을 건너뛰고 다음 def 에
    붙인다. 그래서 숫자 하나 돌려주는 이 도우미가 '1분마다 저절로 다시 그리는
    조각'이 되었다. 부르는 자리가 세 곳이고 줄마다 불리니, 화면에 조각 타이머가
    여러 개 깔려 1분마다 서버를 계속 다녀왔다(상하님 지적 — "관찰만 15개 부분
    클릭하면 너무 느리게 열린다, 로딩 걸린다", "닫기를 여러 번 눌러야 된다").
    """
    return float(getattr(j3data, "LEADER_SCORE_MAX", 80.0))


def _leader_bar_pct(score) -> float:
    """점수 막대를 만점 기준으로 채운다. 100으로 나누면 80점 만점이 늘 짧아 보인다."""
    return max(0.0, min(float(score or 0) / max(_leader_max(), 1.0) * 100.0, 100.0))


# 화면에 「1분 자동 갱신」이라고 적어 둔 그 카드다. 데코레이터를 제자리로 돌려놨다.
@st.fragment(run_every=60)
def _render_selected_live_quote(stock_score=None, entry_state=None, *, general_theme=False) -> None:
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
    # 만점은 모듈에서 읽는다 — /100으로 박아 뒀더니 아래 매수심사 칸(/80)과
    # 한 화면에서 서로 다른 값을 말했다(2026-08-13 상하님 캡처).
    score_max = 100.0 if general_theme else _leader_max()
    score_val = (
        f"{float(stock_score):.1f}/100" if general_theme and stock_score is not None
        else f"{float(stock_score):.1f}/{_number(score_max)}" if stock_score is not None
        else "—"
    )
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
        f"<div class='j3-mc'><div class='j3-mc-label'>{'일반 테마 최종점수' if general_theme else '종목 조건점수'}</div>"
        f"<div class='j3-mc-val j3-green'>{score_val}</div>{state_sub}</div>",
    ]
    st.markdown(f"<div class='j3-metric-row'>{''.join(cells)}</div>", unsafe_allow_html=True)
    stale_text = " · 마지막 정상 자료" if quote.get("stale") else ""
    st.caption(f"시세 기준 {quote.get('source_time') or '—'}{stale_text} · 1분 자동 갱신")


def _load_theme_rankings() -> dict:
    with st.spinner(f"미국 {_THEME_COUNT}개 테마와 구성종목을 조회하는 중입니다…"):
        return j3data.get_theme_rankings()


def _render_leader_comparison(leaders: list[dict]) -> None:
    # 눌러야 열린다(2026-07-30 사용자 지시, 한국테마와 같다). 세 종목 × 차트 세 벌이라
    # 늘 그리면 화면도 길고 받아 오는 것도 많다. 제목은 그대로 두고 안내만 뒤에 붙인다.
    if not _section_toggle(
        "🏅 대장주 1~3위 · 당일/일봉/주봉/월봉 비교 — 클릭하면 볼 수 있습니다",
        "j3_leadercmp_open",
        close_label="대장주 1~3위 · 당일/일봉/주봉/월봉 비교 — 다시 클릭하면 닫힙니다",
    ):
        return
    # 세 종목의 일봉·주봉·월봉을 **한 번에 묶어** 받아 둔다(2026-08-28). 아래에서
    # 종목마다 get_chart_bundle을 부르는데, 묶어 두면 그것들이 캐시를 나눠 쓴다.
    # 못 받아도 조용히 넘어간다 — 그때는 종목마다 따로 받는다.
    try:
        j3data.prefetch_charts([leader.get("ticker") for leader in leaders[:3]])
    except Exception:
        pass
    medal_by_rank = {1: "🥇", 2: "🥈", 3: "🥉"}
    for leader in leaders[:3]:
        metrics, plan = leader["metrics"], leader["plan"]
        rank = int(leader["rank"])
        # 메달은 종합점수 80점 이상인 대장주에만 붙인다.
        medal = medal_by_rank.get(rank, "") if float(leader["score"]) >= 80 else ""
        medal_html = f"<span class='j3-medal'>{medal}</span> " if medal else ""
        # **선택종목 세부사항과 같은 그림·같은 자리**다 (2026-08-28 상하님 지시 —
        # "20개 테마에서 각 테마 클릭하면 1~3위 종목 나오고 당일·일봉·주봉 나오는데
        # 그것도 선택종목 세부사항의 당일·일봉·주봉처럼 해 줘").
        #
        # 스트림릿 칸 넷(왼쪽 글 + 그림 셋)을 쓰지 않는다 — 폰에서 위아래로 쌓여
        # 한 줄에 하나가 되고, 알테어 그림이 종목마다 셋씩(모두 아홉) 만들어졌다.
        # 이제 글은 한 덩이, 그림은 CSS 격자 한 판이다.
        with st.container(border=True):
            change_pct = metrics.get("change_pct")
            st.markdown(
                f"<div class='j3-leader-name'>{medal_html}{rank}위 · {leader['name']} "
                f"<span class='j3-muted'>{html.escape(str(leader['ticker']))}</span></div>"
                "<div class='j3-leader-score-label'>현재가 · 등락률</div>"
                f"<div class='j3-leader-live'>{_price(metrics.get('current'))} "
                f"<span class='j3-mc-sub {_sign_class(change_pct)}'>{_pct(change_pct)}</span></div>"
                "<div class='j3-leader-score-label'>종목 조건점수</div>"
                f"<div class='j3-leader-score'>{float(leader['score']):.1f}</div>"
                f"<div class='j3-leader-state'>{plan.get('state')}</div>"
                f"<div class='j3-chart-when'>52주 고가 대비 {_pct(metrics.get('from_high_pct'))}</div>",
                unsafe_allow_html=True,
            )
            boxes = []
            intraday_payload = leader.get("intraday_chart")
            if isinstance(intraday_payload, dict) and intraday_payload.get("ok"):
                closes = _payload_series(intraday_payload,
                                         intraday_payload["price"].columns[0])
                drawing = _pretty_chart_svg(
                    closes, base=intraday_payload.get("prev_close"), height=150)
                if drawing:
                    boxes.append(("당일", drawing,
                                  intraday_payload.get("source_time") or ""))
            # **선택종목 세부사항과 같은 묶음**을 쓴다 (2026-08-28 상하님 지시 —
            # "당일 일봉 주봉까지 있는데 월봉도 넣어줘").
            # 대장주 전용 자료(daily_chart·weekly_chart)는 2년치라 월봉 120개월을
            # 만들 수가 없다. 같은 묶음을 쓰면 넷이 다 나오고, 두 화면의 그림이
            # 서로 달라질 일도 없다.
            bundle = {}
            try:
                got = j3data.get_chart_bundle(leader["ticker"])
                if got.get("ok"):
                    bundle = got.get("charts") or {}
            except Exception:
                bundle = {}
            for name in ("일봉", "주봉", "월봉"):
                payload = bundle.get(name) or {}
                if not payload.get("ok"):
                    continue
                drawing = _pretty_chart_svg(
                    _payload_series(payload, "Close"),
                    ma20=_payload_series(payload, "MA20"),
                    ma50=_payload_series(payload, "MA50"),
                    height=150,
                )
                if drawing:
                    boxes.append((name, drawing, ""))
            if boxes:
                cells = "".join(
                    f"<div class='j3-chart-box'><div class='j3-chart-name'>{name}</div>"
                    f"{drawing}"
                    + (f"<div class='j3-chart-when'>기준 "
                       f"{html.escape(str(when)[:16].replace('T', ' '))}</div>" if when else "")
                    + "</div>"
                    for name, drawing, when in boxes
                )
                st.markdown(f"<div class='j3-chart-grid'>{cells}</div>",
                            unsafe_allow_html=True)
            else:
                st.info("차트 자료 없음")


_MEDAL_BY_RANK = {1: "🥇", 2: "🥈", 3: "🥉"}
# 상태 색은 20개 테마 순위표의 상태색과 같은 규칙(주도 초록·관찰 주황·약함 회색)을 쓴다.
_STATE_COLOR_WORD = {"강함": "green", "보통": "orange", "약함": "gray",
                     "주도": "green", "관찰": "orange"}


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
    theme_row: dict, leader: dict, market: dict, top_candidates: list[dict], stock_key: str,
    *, panel: str = "theme", on_close=None,
) -> None:
    """종목 상세 한 벌. panel은 위젯 키를 갈라 두 상세가 서로를 덮어쓰지 않게 한다.

    ``on_close``는 닫기를 누를 때 함께 할 일이다. 종목검색에서 쓴다 — 상세를
    닫으면 위의 「찾은 종목」 줄도 같이 걷는다(2026-08-28 상하님 지시).
    """
    ticker = leader["ticker"]
    if panel == "theme":
        st.session_state["j3_selected_ticker"] = ticker
    metrics, plan = leader["metrics"], leader["plan"]

    st.divider()
    # 종목을 누르면 화면이 여기로 내려온다(2026-08-09 상하님 지시).
    scroll_to.anchor(st, f"detail_{panel}")
    # 상세 한 벌을 통째로 눌러야 열리게 한다(2026-07-30 사용자 지시, 한국테마와 같다).
    if not _section_toggle(
        "🔎 선택종목 세부사항 보기", f"j3_detail_open_{panel}",
        close_label="선택종목 세부사항 닫기", on_close=on_close,
    ):
        return
    # 대장주 비교와 동일하게, 80점 이상 1~3위 종목이면 종목명에도 메달을 붙인다.
    detail_rank = int(leader.get("rank") or 0)
    detail_medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(detail_rank, "") if float(leader.get("score") or 0) >= 80 else ""
    detail_medal_html = f"<span class='j3-medal'>{detail_medal}</span> " if detail_medal else ""
    st.markdown(
        f"<div class='j3-stock-name'>{detail_medal_html}{leader['name']} · {ticker}</div>"
        f"<div class='j3-stock-sub'>{theme_row['name']} 대장주 {leader['rank']}위 · {plan.get('recommendation')}</div>",
        unsafe_allow_html=True,
    )

    # 게스트도 종목명·가격·차트는 본다. 사용자가 지정한 세 캡처 영역
    # (점수/선정 근거·매수 심사·추천 근거)만 만들지 않는다.
    if auth.is_guest():
        _render_day_price_row(metrics, ticker, panel=panel)
        _render_price_chart_bundle(ticker, panel=panel)
        _section_close(f"j3_detail_open_{panel}", "선택종목 세부사항 닫기",
                       on_close=on_close)
        return

    # GENERAL은 종목 100점과 테마 100점을 먼저 각각 만든 뒤
    # 60:40으로 합친다. 다른 갈래의 옛 /80 표와 섞지 않는다.
    general_stock_parts = leader.get("stock_score_parts")
    general_theme_parts = theme_row.get("score_parts")
    is_general_score = (
        isinstance(general_stock_parts, (list, tuple))
        and isinstance(general_theme_parts, (list, tuple))
    )
    _render_selected_live_quote(
        leader.get("score"), plan.get("state"), general_theme=is_general_score,
    )

    if is_general_score:
        stock_factor_spec = list(getattr(j3data, "GENERAL_STOCK_SCORE_PARTS", ()))
        theme_factor_spec = list(getattr(j3data, "GENERAL_THEME_SCORE_PARTS", ()))
    else:
        # 상승장·급락반등·기존 fixture는 여전히 옛 표시 경로를 쓴다.
        factor_spec = list(getattr(j3data, "LEADER_SCORE_PARTS",
                                   (("테마 대비 상대강도", 25.0), ("52주 신고가 위치", 25.0),
                                    ("추세", 0.0), ("유동성", 15.0), ("변동성 안정", 15.0))))
        factor_values = list(leader.get("score_parts") or ())
        leader_max = float(getattr(j3data, "LEADER_SCORE_MAX", 80.0))

    def _gain_cell(part, maximum, *, top_border=False):
        # 획득값과 (최대) 모두 붉은색, 사이 한 칸 띄운다. 총점 행은 위에 이중선.
        border = " style='border-top:4px double rgba(255,255,255,0.55)'" if top_border else ""
        return (
            f"<td class='j3-fac-val'{border}>"
            f"<span style='color:#ff5b5b; font-weight:800'>{_number(part)}</span> "
            f"<span style='color:#ff5b5b'>({maximum})</span></td>"
        )

    general_factor_notes = {
        "최근 3개월 강도": "최근 3개월 동안 시장보다 강했는지 봅니다.",
        "최근 6개월 강도": "반년 동안 꾸준히 시장보다 강했는지 봅니다.",
        "1년 최고가 근접": "최근 1년 최고가 가까이에 있는지 봅니다.",
        "테마 6개월 강도": "반년 동안 강한 테마인지 봅니다.",
        "테마 3개월 강도": "최근에도 테마 힘이 살아 있는지 봅니다.",
        "강한 종목 수": "같은 테마의 여러 종목이 함께 강한지 봅니다.",
        "최근 힘 증가": "최근 들어 테마 힘이 더 좋아지는지 봅니다.",
    }

    if is_general_score:
        def _general_group_row(label, score, color, note=""):
            note_html = (
                f"<div class='j3-general-factor-note'>{note}</div>" if note else ""
            )
            return (
                "<tr><td class='j3-fac-name j3-general-group'>"
                f"<span style='color:{color}'>{label}</span>{note_html}</td>"
                "<td class='j3-fac-val j3-general-group'>"
                f"<span style='color:{color}'>{float(score or 0):.1f}/100</span></td></tr>"
            )

        def _general_rows(spec, values):
            return "".join(
                f"<tr><td class='j3-fac-name'>{name}"
                f"<div class='j3-general-factor-note'>{general_factor_notes[name]}</div></td>"
                "<td class='j3-fac-val'><span style='color:#ff5b5b; font-weight:800'>"
                f"{_number(part)}</span> <span style='color:#ff5b5b'>/ {_number(maximum)}</span></td></tr>"
                for (name, maximum), part in zip(spec, values)
            )

        factor_rows = (
            _general_group_row("종목점수", leader.get("stock_score"), "#4da6ff")
            + _general_rows(stock_factor_spec, general_stock_parts)
            + _general_group_row("테마점수", theme_row.get("score"), "#44f0a1")
            + _general_rows(theme_factor_spec, general_theme_parts)
        )
        total_row = _general_group_row(
            "최종점수", leader.get("score"), "#44f0a1", "종목 60% + 테마 40%",
        )
    else:
        factor_rows = "".join(
            f"<tr><td class='j3-fac-name'>{name}</td>"
            + f"{_gain_cell(part, '0점' if not maximum else _number(maximum))}</tr>"
            for (name, maximum), part in zip(factor_spec, factor_values)
        )
        total_style = (
            "font-weight:800; font-size:1.1rem; background:rgba(134,255,203,0.12); "
            "border-top:4px double rgba(255,255,255,0.55)"
        )
        total_row = (
            f"<tr><td class='j3-fac-name' style='{total_style}'>총점</td>"
            f"<td class='j3-fac-val' style='{total_style}'>"
            f"<span style='color:#ff5b5b; font-weight:800'>{_number(leader.get('score'))}</span> "
            f"<span style='color:#ff5b5b'>({_number(leader_max)})</span></td></tr>"
        )
    score_col, plan_col = st.columns([1, 1], gap="large")
    with score_col:
        if is_general_score:
            st.markdown("<div class='j3-section-title'>일반 테마매매 점수</div>", unsafe_allow_html=True)
            st.markdown(
                _general_theme_score_help_html(
                    factor_rows, total_row, f"j3_general_theme_help_{panel}",
                ),
                unsafe_allow_html=True,
            )
            score_summary = (
                f"테마 내 일반 점수 {leader['rank']}위 · "
                f"종목점수 {float(leader.get('stock_score') or 0):.1f}/100 · "
                f"테마점수 {float(theme_row.get('score') or 0):.1f}/100 · "
                f"최종점수 {float(leader.get('score') or 0):.1f}/100"
            )
            st.markdown(
                f"<div class='j3-reason-mustard'>{_mustard_html(score_summary)}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown("<div class='j3-section-title'>종목 선정 근거</div>", unsafe_allow_html=True)
            if panel == "mystock":
                # **어느 배점인지 표 바로 위에 적는다** (2026-08-28 상하님 지적 —
                # "종목검색 후 선택종목 세부사항의 배점기준은 어느 형식의 배점을
                # 따르는지 알 수가 없다").
                #
                # 여기만 **옛 80점 배점**을 쓴다. 테마 대장주는 새 100점 배점
                # (종목 60% + 테마 40%)이다. 게다가 직접 찾은 종목은 견줄 테마가
                # 없어 「테마 대비 상대강도 25점」이 언제나 0점이라, 표에 (80)이라
                # 적혀 있어도 실제로 받을 수 있는 최대는 55점이다.
                # 상하님 지시대로 **배점은 그대로 두고 설명만 붙인다**(2026-08-28).
                st.markdown(
                    "<div class='j3-score-origin'>"
                    "이 표는 <b>직접 검색한 종목 전용 배점</b>입니다 — 80점 만점.<br>"
                    "위 테마 대장주가 쓰는 <b>100점 배점</b>(종목 60% + 테마 40%)과 "
                    "<b>다른 자</b>입니다. 두 점수를 나란히 놓고 비교하지 마십시오.<br>"
                    "견줄 테마가 없어 <b>「테마 대비 상대강도」 25점은 언제나 0점</b>입니다. "
                    "그래서 이 종목이 실제로 받을 수 있는 가장 높은 점수는 "
                    "<b>55점</b>입니다."
                    "</div>",
                    unsafe_allow_html=True,
                )
            st.markdown(
                _factor_table_html(
                    factor_rows, total_row,
                    [name for name, _maximum in factor_spec],
                    f"j3_factor_help_{panel}",
                ),
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<div class='j3-reason-mustard'>{_mustard_html(leader['stock_reason'])}</div>",
                unsafe_allow_html=True,
            )
    with plan_col:
        st.markdown("<div class='j3-section-title'>매수 심사 결과</div>", unsafe_allow_html=True)
        # 점수·상태만 있고 '뭘 하라는 건지'가 없다는 지적(2026-07-30). 판정을 사람
        # 말로 다시 쓴 한 줄을 표 위에 얹는다 — 새 판정을 만들지는 않는다.
        guide = guidance.build(plan, money=_price, market_score=market.get("score"))
        # ── 테마 점수가 70에 못 미치면 **「배점 미달」이라고 적는다** ────────────
        # 2026-08-28 상하님 지시 — "70점 넘지 않으면 배점 미달이라고 표시해라."
        #
        # **문턱 자체는 안 건드린다**(CLAUDE.md 0-1 — 매매 규칙을 바꾸는 것은 먼저
        # 여쭙는다). 사는 것을 막지 않고, 화면에 그 사실을 적기만 한다.
        #
        # 70 은 지어낸 숫자가 아니다. `jarvis3_data._entry_plan` 이 **다른 갈래에서
        # 이미 쓰고 있는 문턱**이다 —
        #     market_score >= 50 and theme_score >= 70 and score >= LEADER_GATE_MARK
        # 20개 테마 갈래만 그 둘을 안 보고 시장 50 하나로 통과시켰고, 그래서 테마
        # 46.7점짜리도 「좋은 후보」라고 적혔다(2026-08-28 상하님 캡처 · 빅테크10).
        _THEME_SCORE_MARK = 70.0
        _theme_score = theme_row.get("score")
        _theme_short = (_theme_score is not None
                        and float(_theme_score) < _THEME_SCORE_MARK)
        if is_general_score and _theme_short:
            st.markdown(
                "<div class='j3-guide-short'>⚠ 배점 미달 — 테마점수 "
                f"<b>{float(_theme_score):.1f}</b>/100 으로 기준 "
                f"<b>{_THEME_SCORE_MARK:g}</b>점에 못 미칩니다.</div>",
                unsafe_allow_html=True,
            )
        if is_general_score and plan.get("state") == "눌림목 대기":
            # ── 여기 있던 두 문장은 **숫자를 안 보고 늘 같은 말**을 했다 ──────────
            # 2026-08-28 상하님 지적 — "테마 순위 밖, 즉 11위 빅테크10을 클릭했는데
            # 배점 점수가 저런데 매수심사결과 밑에 「좋은 후보입니다」. 이거 너무
            # 안 맞는 것 아니냐. 전부 다 저런 식으로 멘트 넣은 거 아니냐."
            #
            # 맞다. 앞서는 눌림 구간이기만 하면 점수와 상관없이 늘
            #   "좋은 후보입니다" · "종목과 테마 점수는 높지만"
            # 이라고 적었다. 상하님이 보신 것은 최종점수 65.3(테마 46.7)인데도
            # 같은 문장이 나왔다.
            #
            # **이 갈래가 실제로 무엇을 보고 통과시키는지 적는다.**
            # 문턱은 `jarvis3_data._entry_plan` 에 있다 —
            #     gates_ok = (market_score >= 50 if general_theme_trading else
            #                 market_score >= 50 and theme_score >= 70
            #                 and score >= LEADER_GATE_MARK)
            # 20개 테마(general_theme_trading=True)는 **시장 점수 50 하나만** 본다.
            # 테마 70점·종목 60점 문턱은 이 갈래에서 안 본다. 그래서 테마 46.7점인
            # 종목도 "통과"가 됐고, 화면은 그것을 "좋은 후보"라고 적었다.
            # 무엇을 보고 통과시켰는지를 그대로 적어, 화면이 실제보다 더 많이
            # 본 것처럼 보이지 않게 한다.
            _final = leader.get("score")
            _theme_rank = theme_row.get("rank")
            _bits = []
            if _final is not None:
                _bits.append(f"최종점수 <b>{float(_final):.1f}/100</b>")
            if _theme_score is not None:
                _mark = " — <b>배점 미달</b>" if _theme_short else ""
                _bits.append(f"테마점수 <b>{float(_theme_score):.1f}/100</b>{_mark}")
            if _theme_rank:
                _bits.append("오늘 <b>{}위</b> 테마".format(int(_theme_rank))
                             + ("(상위 10 밖)" if int(_theme_rank) > 10 else ""))
            guide = {
                **guide,
                "headline": ("배점 미달 — 아직 매수 신호는 아닙니다."
                             if _theme_short else "아직 매수 신호는 아닙니다."),
                "detail": ("지금은 눌림 구간입니다. "
                           + (" · ".join(_bits) + ". " if _bits else "")
                           + "이 갈래에서 앱이 막는 문턱은 <b>시장 점수 50</b> 하나입니다 — "
                           "테마 점수가 미달이어도 앱이 막지는 않습니다. "
                           "살 만한지는 위 배점표를 보고 상하님이 정하십시오."),
            }
        st.markdown(guidance.html(guide, css_class="j3-guide"), unsafe_allow_html=True)
        if is_general_score:
            market_ok = float(market.get("score") or 0) >= 50.0
            price_state = "눌림 구간" if plan.get("state") == "눌림목 대기" else str(plan.get("state") or "자료 부족")
            conclusion = (
                "아직 매수 신호 아님" if plan.get("state") == "눌림목 대기"
                else "매수 조건 충족" if plan.get("state") == "돌파 확인"
                else str(plan.get("recommendation") or "관찰")
            )
            # 「종목선정: 통과」는 늘 '통과'라고 적혀 있어 아무것도 안 알려 줬다
            # (2026-08-28 상하님 지적). 그 자리에 **실제 점수**를 적는다.
            _sc = leader.get("score")
            _sc_text = f"{float(_sc):.1f}/100" if _sc is not None else "자료 부족"
            _th_text = (
                f"{float(_theme_score):.1f}/100"
                + (f" · 기준 {_THEME_SCORE_MARK:g} 미달" if _theme_short else "")
                if _theme_score is not None else "자료 부족"
            )
            st.caption(
                f"최종점수: {_sc_text} · 테마점수: {_th_text} · "
                f"시장상태: {'통과' if market_ok else '대기'} · "
                f"가격자리: {price_state} · 결론: {conclusion}"
            )
            plan_cells = [
                ("현재가", _price(metrics.get("current")), "#e6e6e6"),
                ("가격자리", price_state, "#e6e6e6"),
                ("매수 계획 취소 참고가격", _price(plan.get("invalidation")), "#ff5b5b"),
                ("수익 목표 참고가격", _price(plan.get("target")), "#44f0a1"),
            ]
        elif plan.get("trigger") is not None:
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
            f"<div class='val{' j3-holo-words' if label == '가격자리' else ''}' style='color:{color}'>{value}</div></div>"
            for label, value, color in plan_cells
        ]
        # 3열 배치: [기준가][허용상단][종목 조건점수] / [무효화][2R 목표][빈칸]
        score_box = (
            "<div class='j3-holo-cell j3-holo-score'>"
            f"<div class='label'>{'일반 테마 최종점수' if is_general_score else '종목 조건점수'}</div>"
            f"<div class='val'>{float(leader.get('score') or 0):.1f}/{100 if is_general_score else _number(_leader_max())}</div>"
            f"<div class='state'>{price_state if is_general_score else plan.get('state', '')}</div></div>"
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
        if is_general_score:
            st.markdown(
                "<div class='j3-plan-note'>※ 참고 가격 — 매수 계획 취소 참고가격은 주가가 크게 "
                "무너졌는지 판단할 때, 수익 목표 참고가격은 매수했을 경우 목표를 잡을 때 참고합니다.</div>",
                unsafe_allow_html=True,
            )
        # 가격이 '—'인 이유와 함께, 어느 가격이 되면 조건이 성립하는지 참고가를 보여준다.
        if not is_general_score and plan.get("trigger") is None:
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
    _render_day_price_row(metrics, ticker, panel=panel)
    # 당일 차트가 이 상세에만 없었다(2026-08-06 상하님 지적) — 순위 7에서 테마
    # 대장주를 고르면 여기로 오는데 당일 차트가 안 나왔다.
    # panel을 넘겨야 같은 종목을 위·아래 두 상세에서 열어도 단추 키가 안 겹친다.
    _render_price_chart_bundle(ticker, panel=panel)

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

    _render_buy_form(theme_row, leader, market, top_candidates, stock_key, panel=panel)
    # 이 상세 한 벌의 맨 끝 — 여기서 바로 접을 수 있게 한다(2026-08-01 사용자 지시).
    _section_close(f"j3_detail_open_{panel}", "선택종목 세부사항 닫기", on_close=on_close)
    if panel == "top7":
        # 「매수심사결과 높은 순위 9 닫기」는 **✕ 선택종목 세부사항 닫기 바로 밑**이다.
        # 2026-08-26 상하님이 자리를 바로잡아 주셨다 — "너가 지금 매수심사결과 높은
        # 순위 9 닫기를 위에 두니 내가 안 보이지. 선택종목 세부사항 닫기 밑에 넣어야
        # 된다." 앞서 '실제 매수기록 저장' 위에 뒀더니 금빛 저장 단추에 눈이 가려
        # 회색 닫기 단추가 묻혔다. 누르면 열린 화면을 다 닫고 맨 위로 올라간다.
        _section_close("j3_top7_open", "매수심사결과 높은 순위 9 닫기",
                       slot="_detail", on_close=_close_all_from_fragment)



# 테마 화면에서 **한 번에 같이 펴는 네 구역** (2026-08-14 상하님 지시).
# 테마 이름을 눌러도, 표에서 종목을 눌러도, 아래 '상세 종목 선택'으로 골라도
# 이 넷이 함께 열린다. 셋이 따로 놀면 어떤 길로 들어왔느냐에 따라 화면이 달라진다.
# 「20개 테마 실시간 순위」 표를 열어 둘까(2026-08-14 상하님 지시). **기본은 열림.**
# 여닫는 단추는 '종목 찾기' 바로 위에 있다(_render_pullback_finder 맨 앞).
_THEME_RANK_OPEN = "j3_theme_rank_open"
_RADAR_MAIN_ANCHOR = "radar_main"

_THEME_PANEL_OPEN_KEYS = (
    "j3_leadercmp_open",        # 🏅 대장주 1~3위 · 당일/일봉/주봉 비교
    "j3_detail_open_theme",     # 🔎 선택종목 세부사항 보기
    "j3_intraday_open_theme",   # 📈 당일 · 실시간 차트 보기
    "j3_bundle_open_theme",     # 📊 일봉 · 주봉 · 월봉 보기
)


# 「종목 찾기」의 세 갈래 단추. 20개 테마 순위를 닫을 때 이것들도 같이 닫는다.
_FINDER_OPEN_KEYS = ("j3_pullback_open", "j3_top7_open")
# 상세 한 벌 안에서 열리는 창들. 갈래마다 이름 뒤가 다르다.
_DETAIL_OPEN_PREFIXES = ("j3_detail_open_", "j3_intraday_open_", "j3_bundle_open_",
                         "j3_leadercmp_open_", "j3_buyform_open_")
_DETAIL_PANELS = ("theme", "top7", "pullback")


def _close_full_theme_rank() -> None:
    """「종목 찾기」에서 연 화면을 하나도 남기지 않고 다 닫고 메인으로 돌아간다.

    2026-08-26 상하님 지시 — "20개 테마 실시간 순위 닫기 버튼 누르면 20개 테마
    관련 열린 창 다 닫고 캡처 화면으로 되돌아가도록."

    예전에는 **테마 쪽만** 닫았다. 그래서 매수심사결과 순위 9에서 골라 둔 종목
    상세가 그대로 남았다(상하님 캡처 — 순위를 닫았는데 '순위 7에서 고른 종목 ·
    ILMN'이 그대로 있었다). 이제 세 갈래와 그 안에서 연 창, 골라 둔 값까지 비운다.
    """
    st.session_state[_THEME_RANK_OPEN] = False
    st.session_state["j3_theme_panel_open"] = False
    for opened in _THEME_PANEL_OPEN_KEYS:
        st.session_state[opened] = False
    for opened in _FINDER_OPEN_KEYS:
        st.session_state[opened] = False
    for panel in _DETAIL_PANELS:
        for prefix in _DETAIL_OPEN_PREFIXES:
            st.session_state[f"{prefix}{panel}"] = False
    # 선택값까지 남아 있으면 다음에 열었을 때 직전 상세가 되살아난 것처럼 보인다.
    for state_key in list(st.session_state):
        if str(state_key).startswith("j3_stock_choice_"):
            st.session_state.pop(state_key, None)
    for state_key in ("j3_theme_choice", "j3_theme_choice_widget",
                      "j3_top7_pick_row", "j3_top7_detail_choice"):
        st.session_state.pop(state_key, None)
    scroll_to.request(st, _RADAR_MAIN_ANCHOR)


def _close_all_from_fragment() -> None:
    """프래그먼트 안에서 「다 닫기」를 눌렀을 때 쓴다.

    매수심사결과 순위 9는 `@st.fragment` 안에 있다. 그 안에서 단추를 누르면
    스트림릿이 **그 조각만** 다시 그린다. 그래서 상태로는 닫혔는데 바깥에 있는
    20개 테마 순위·상승장·급락장이 화면에 그대로 남았다(2026-08-26 상하님 —
    "아직 안 되어 있다"). 판 전체를 다시 그리라고 적어 두고 조각 끝에서 실행한다.
    """
    _close_full_theme_rank()
    st.session_state["j3_close_all_pending"] = True


def _close_theme_rank_from_fragment() -> None:
    """덩이 안에 있는 「20개 테마 실시간 순위 닫기」 전용 (2026-08-27).

    이 단추는 덩이 **밖**에 있는 상승장·급락 후 반등장·매수심사결과 순위 9까지
    끈다. 그것들이 열려 있었다면 덩이만 다시 그려서는 화면에서 안 접힌다 —
    그때만 판 전체를 다시 그리라고 적어 둔다. 열린 것이 하나도 없으면 안 적는다.
    그 편이 훨씬 빠르다(판 전체 다시 그리기는 온라인에서 3초다).
    """
    outside_open = any(bool(st.session_state.get(key)) for key in _FINDER_OPEN_KEYS)
    _close_full_theme_rank()
    if outside_open:
        st.session_state["j3_close_all_pending"] = True


def _run_close_all_if_requested() -> None:
    """적어 둔 '판 전체 다시 그리기'를 한 번 실행한다. 프래그먼트 끝에서 부른다."""
    if not st.session_state.pop("j3_close_all_pending", False):
        return
    try:
        st.rerun(scope="app")
    except Exception:
        st.rerun()


def _section_toggle(
    label: str,
    key: str,
    *,
    close_label: str | None = None,
    close_return_to: str | None = None,
    on_close=None,
) -> bool:
    """눌러야 열리는 구역. 열려 있으면 닫는 단추를 보여준다(2026-07-30 사용자 지시).

    st.expander는 접혀 있어도 안을 다 그린다 — 시세·차트를 미리 받아 오므로
    여는 시간이 안 줄어든다. 그래서 아예 그리지 않는 방식으로 둔다.
    한국테마(자비스4)와 같은 장치다.

    여닫기는 on_click으로 처리한다. 단추가 만들어진 뒤에 상태를 뒤집으면 그 판에
    이미 옛 글자가 찍혀 있어, 닫았는데도 '닫기'가 그대로 남는다
    (2026-07-30 사용자 지적). on_click은 화면을 다시 그리기 **전에** 돌아서
    글자와 속내용이 같은 판에서 맞는다.
    """
    def _flip():
        now_open = not bool(st.session_state.get(key))
        st.session_state[key] = now_open
        # 열 때만 방문기록을 쌓는다 — 닫을 때 주소를 되돌리면 그것이 또 기록에
        # 쌓여서 뒤로가기가 도로 열어 버린다(back_nav 설명 참고).
        if now_open:
            back_nav.opened(st, key)
        else:
            if on_close:
                on_close()
            elif close_return_to:
                scroll_to.request(st, close_return_to)

    is_open = bool(st.session_state.get(key))
    st.button(
        ("✕ " + (close_label or label)) if is_open else label,
        key=f"btn_{key}", on_click=_flip,
    )
    return is_open


def _section_close(
    key: str,
    label: str,
    *,
    slot: str = "",
    return_to: str | None = None,
    on_close=None,
) -> None:
    """구역 **맨 아래**에 두는 작은 닫기 단추 (2026-08-01 사용자 지시).

    폰에서는 구역 하나가 화면 몇 장이라, 끝까지 내려가면 위에 있는 여는 단추가
    화면 밖으로 나간다. 닫으려고 다시 위로 올라가야 했다. 같은 값을 끄는 단추를
    아래에도 하나 둬서 그 자리에서 접을 수 있게 한다. 한국테마와 같은 장치다.

    slot은 **같은 값을 끄는 단추를 한 화면에 둘 이상** 둘 때 쓴다(2026-08-15
    상하님 지시 — 상승장·급락 갈래는 목록 위와 상세 아래 두 곳에 닫기가 있다).
    스트림릿은 열쇠가 같은 단추를 두 번 그리면 오류를 낸다. 색을 입히는 CSS는
    `class*='st-key-close_j3_pullback_open'`처럼 **앞부분만** 맞추므로 slot이
    붙어도 같은 색이 그대로 간다.
    """
    def _close():
        st.session_state[key] = False
        if on_close:
            on_close()
        elif return_to:
            scroll_to.request(st, return_to)

    st.button(f"✕ {label}", key=f"close_{key}{slot}", on_click=_close)


# ── 「심사항목 기준」 여닫이 (2026-08-14 상하님 지시) ─────────────────────────
# 상하님 — "종목 선정 근거에 '심사항목 기준'이란 조그만 버튼 만들고 간략하게 쉽게
# 설명을 만들어라. 신고가 눌림 전용 배점도, 급락 후 반등장도, 테마 실시간
# 종목선정 근거에도."
#
# **st.button을 쓰지 않는다**(2026-08-14 상하님 지적 — "열고 닫는데 로딩시간이 너무
# 많이 걸린다"). st.button은 누를 때마다 **화면 전체를 다시 그린다.** 이 설명은
# 글자뿐이라 다시 그릴 것이 없는데도 표·차트·시세를 통째로 다시 그리느라 몇 초씩
# 걸렸다. 그래서 브라우저가 혼자 여닫는 <details>를 쓴다 — **다시 그리지 않으므로
# 기다림이 없다.**
#
# 대신 여는 모양은 '이 테마 기법에 대한 설명'과 **같게** 맞췄다(상하님 지시) —
# 단추 색(하늘색 바탕·주황 글씨)도, 위에서 아래로 커튼처럼 펼치는 것도 같다.
# 펼치는 규칙은 method_help.py의 mh-drop과 같은 방식이되 **이름을 갈라 둔다** —
# 같은 이름을 쓰면 한쪽을 고칠 때 다른 쪽이 조용히 따라 바뀐다.
#
# **한 가지 다른 점** — <details>는 화면을 다시 그리면 닫힌다. 스트림릿이 다시
# 그리는 것은 상하님이 다른 단추를 누르셨을 때뿐이라 실제로는 걸리지 않는다.
# 열린 채로 남기려면 st.button으로 돌아가야 하고, 그러면 다시 느려진다.
_FACTOR_HELP_CSS = """
<style>
/* 위에서 아래로 커튼처럼 펼친다. transform은 쓰지 않는다 — 창이 옆으로 튄다. */
@keyframes j3fh-drop {
    from { opacity: .35; clip-path: inset(0 0 100% 0); }
    to   { opacity: 1;   clip-path: inset(0 0 0 0); }
}
/* 표 안 심사항목 이름 옆에 붙는 **작은 '설명'** (2026-08-14 상하님 지시).
   '이 테마 기법에 대한 설명' 단추와 같은 색이되 글자 크기만 작게 둔다. */
.j3fh-chip {
    display: inline-block;
    /* 오른쪽으로 두 칸 떨어뜨린다(2026-08-14 상하님 지시). */
    margin-left: 1.5rem;
    background: #cfe9ff;
    border: 1px solid #8ec9f5;
    border-radius: .45rem;
    padding: .12rem .6rem;
    color: #c15f3c !important;
    /* 한 치수 크게(2026-08-14 상하님 지시). */
    font-size: .84rem;
    font-weight: 800;
    text-decoration: none !important;
    vertical-align: middle;
    white-space: nowrap;
    cursor: pointer;
    user-select: none;
    transition: background .12s ease-out, border-color .12s ease-out;
}
.j3fh-chip:hover { background: #b9dfff; border-color: #6db6ee; }
.j3fh-chip:active { filter: brightness(.95); }
/* 창은 **표 아래(총점 밑)**에 두고 평소에는 숨겨 둔다. 상하님이 '설명'을 누르면
   그 칸의 창만 열린다 — 브라우저가 혼자 하는 일이라 **화면을 다시 그리지 않는다.**
   st.button을 쓰면 표·차트·시세를 통째로 다시 그려 느리다
   (2026-08-14 상하님 지적 "열고 닫는데 로딩시간이 너무 많이 걸린다").
   장치는 이 화면이 이미 쓰고 있는 것과 같다(위 .j3-idx-tap — 지수 그림 바꾸기).
   숨긴 확인칸을 label이 켜고 끈다. 주소(#)를 안 건드리므로 화면이 튀지 않고
   뒤로가기 기록도 안 쌓인다.
   **확인칸·표·창을 한 묶음(.j3fh-swap) 안에 넣는다.** 따로 넣으면 안 눌린다
   (2026-08-14 상하님 "버튼 안눌린다"). 지수 그림 바꾸기도 한 묶음이라 된다. */
.j3fh-cb { position: absolute; opacity: 0; width: 0; height: 0; margin: 0; }
.j3fh-p { display: none; }
.j3fh-swap .j3fh-cb:checked ~ .j3fh-p {
    display: block;
    animation: j3fh-drop .24s ease-out;
}
/* ── 태블릿·스마트폰에서는 **화면 아래에서 위로 올라오며** 열린다 ─────────────
   2026-08-14 상하님 지시 — "테블릿과 스마트폰에서 설명을 클릭하면 화면 위로
   가면서 설명창이 열리도록 해 줘."
   좁은 화면에서는 표 아래에 열어 봐야 화면 밖이라 손으로 굴려 내려야 했다.
   자바스크립트로 굴리려면 스트림릿이 그 코드를 지우므로, **창을 화면에 띄우는**
   쪽으로 푼다 — 누르는 즉시 눈앞에 있고, 굴릴 것이 없다.
   경계 1200px은 이 앱의 다른 태블릿 규칙과 같은 값이다(method_help.py).
   폰 전용이 아니라 태블릿까지 걸리는 규칙이라 mobile_ui.py가 아니라 여기 둔다
   (CLAUDE.md 12번은 '폰 전용' 규칙에 대한 것이다). */
@media (max-width: 1200px) {
    @keyframes j3fh-up {
        from { transform: translateY(100%); opacity: .4; }
        to   { transform: translateY(0); opacity: 1; }
    }
    .j3fh-swap .j3fh-cb:checked ~ .j3fh-p {
        position: fixed;
        left: 0; right: 0; bottom: 0;
        z-index: 1000;
        margin: 0;
        padding: .85rem .9rem .6rem;
        max-height: 78vh;
        overflow-y: auto;
        -webkit-overflow-scrolling: touch;
        background: #12161f;
        border-top: 3px solid #6ee7b7;
        border-radius: 14px 14px 0 0;
        box-shadow: 0 -10px 40px rgba(0, 0, 0, .6);
        animation: j3fh-up .26s ease-out;
    }
    /* 창 안에서는 왼쪽 초록 띠를 뺀다 — 창 위쪽 띠가 이미 그 몫을 한다. */
    .j3fh-swap .j3fh-cb:checked ~ .j3fh-p .j3fh-item { border-left: none; }
    /* 닫기 단추는 손가락으로 누르기 쉽게 넓게, **창 바닥에 붙여 둔다** —
       글이 길어 창 안을 굴려야 하는데, 안 붙여 두면 닫으려고 끝까지 내려야 한다
       (2026-08-14 실측: 375px에서 닫기가 화면 밖이었다). */
    .j3fh-swap .j3fh-cb:checked ~ .j3fh-p .j3fh-x {
        display: block; text-align: center; margin: .6rem 0 0; padding: .5rem;
        position: sticky; bottom: 0;
    }
}
/* 닫기 — 같은 확인칸을 다시 꺼서 창을 접는다. 표의 '설명'을 다시 눌러도 접힌다.
   **색은 그 파트의 갈래 색**이다(2026-08-14 상하님 지시 — "각 파트별 제목처럼
   그라데이션 색깔을 넣고, 즉 상승장·급락 후 반등장 등 버튼의 그라데이션 색깔").
   **크기는 그대로 둔다**(상하님 "크기는 그대로 하고").
   아래 여백은 다음 칸과 붙어 보이지 않게 한 줄 띄운 것이다(같은 지시). */
.j3fh-x {
    display: inline-block;
    margin: .55rem 0 1.5rem;
    padding: .18rem .7rem;
    border-radius: .4rem;
    color: #ffffff;
    font-size: .85rem;
    font-weight: 800;
    cursor: pointer;
    background: linear-gradient(90deg, #3a3f4a 0%, #565d6b 38%, #8b94a5 100%);
}
.j3fh-x-breakout { background: linear-gradient(90deg, #063b2c 0%, #0b5137 38%, #12a06a 100%); }
.j3fh-x-crash { background: linear-gradient(90deg, #4a2408 0%, #7a3c0d 38%, #e07f1f 100%); }
.j3fh-x:hover { filter: brightness(1.12); }
.j3fh-item {
    border-left: 3px solid #6ee7b7;
    background: rgba(110, 231, 183, .06);
    padding: .6rem .85rem;
    margin: .55rem 0;
    border-radius: 6px;
}
/* 항목 이름 — 민트. 표의 '심사 항목' 이름과 같은 글자다. */
.j3fh-name { font-weight: 800; color: #6ee7b7; margin-bottom: .4rem; font-size: .97rem; }
.j3fh-txt { line-height: 1.75; font-size: .92rem; }
/* 배점표에서 내려온 '이 종목의 값' 한 줄 (2026-08-21 상하님 지시 —
   "심사항목에 초록색 제목만 두고 나머지 흰색 내용 다 빼라").
   표에서는 뺐지만 값 자체는 버리지 않는다 — 여기로 옮긴다. */
.j3fh-now { line-height: 1.7; font-size: .92rem; color: #9aa0aa;
    margin-top: .35rem; padding-top: .35rem;
    border-top: 1px dashed rgba(255,255,255,0.14); }
/* 소제목 — 연한 파랑. 항목마다 서너 개뿐이다. */
.j3fh-h { color: #93c5fd; font-weight: 800; }
/* 꼭 짚을 한 마디 — 노랑. **항목당 한두 곳만.** 남발하면 아무것도 안 보인다. */
.j3fh-k { color: #fbbf24; font-weight: 800; }
/* '왜 0점인가' 소제목 — 주황. 통과한 항목의 소제목(파랑)과 눈으로 갈린다. */
.j3fh-z { color: #fb923c; font-weight: 800; }
/* 머리말 — 항목 설명 맨 위에 한 번. "왜 이렇게 배점했는지"를 먼저 읽으시게 한다
   (2026-08-15 상하님 지시 — "왜 그렇게 했는지 나스닥 어떻게 조사했고 결과가
   그렇다 이런 내용을 맨 위에 표시하고"). */
.j3fh-head {
    border-left: 3px solid #93c5fd;
    background: rgba(147, 197, 253, .08);
    padding: .7rem .9rem;
    margin: .2rem 0 .9rem;
    border-radius: 6px;
    line-height: 1.8;
    font-size: .92rem;
}
.j3fh-head-t { color: #93c5fd; font-weight: 800; font-size: 1.0rem; display: block;
               margin-bottom: .35rem; }
/* 설명 창 안에 넣는 **참고표** (2026-08-19 상하님 지시 — 파는 시점 참고표).
   배점표(.j3-factor-table)와 눈에 띄게 달라야 한다 — 저쪽은 점수를 매기는 표이고
   이쪽은 **앱이 정하지 않는 것**을 참고로만 보여주는 표다. 그래서 테두리를 흐리게
   두고 글자도 한 치수 작게 둔다. */
.j3fh-ref { width: 100%; border-collapse: collapse; font-size: .86rem;
            margin: .45rem 0 .3rem; }
.j3fh-ref th { color: #93c5fd; font-weight: 800; text-align: right;
               padding: .3rem .45rem; border-bottom: 1px solid rgba(255,255,255,.18); }
.j3fh-ref th:first-child { text-align: left; }
.j3fh-ref td { color: #e6e6e6; text-align: right; padding: .28rem .45rem;
               border-bottom: 1px solid rgba(255,255,255,.06); }
.j3fh-ref td:first-child { text-align: left; color: #9aa0aa; font-weight: 700; }
.j3fh-ref .j3fh-ref-hi { color: #fbbf24; font-weight: 800; }
/* ── 창 맨 위의 닫기 (2026-08-26 상하님 지적) ────────────────────────────────
   상하님 — "스마트폰 화면인데 설명이 너무 길어 닫는 버튼이 겹쳐 누를 자리가
   없다." 폰·태블릿에서 설명 창은 화면 아래에 붙어 열린다. 그런데 하단
   이동막대(.j3b-bottom-nav)가 z-index 2147483646으로 훨씬 위층에 떠 있어서
   창 바닥의 닫기를 통째로 덮었다. 창 z-index를 올려 막대를 가리는 대신,
   막대 자리를 비켜 주고 맨 위에도 닫기를 하나 둔다 — 글이 아무리 길어도
   손가락이 바로 닿는다.
   노트북에서는 안 보인다. 거기서는 막대가 겹치지 않고 창이 표 아래 그대로
   펼쳐지므로 닫기가 하나면 충분하다. */
.j3fh-x-top { display: none; }
@media (max-width: 1200px) {
    .j3fh-swap .j3fh-cb:checked ~ .j3fh-p .j3fh-x-top {
        display: block; text-align: center;
        margin: 0 0 .55rem; padding: .5rem;
        position: sticky; top: 0; bottom: auto; z-index: 2;
    }
    /* **아래 닫기는 폰·태블릿에서 없앤다** (2026-08-26 상하님 지적 —
       "설명 닫기 두 개나 있다, 밑에 거 없애라"). 그것도 창 바닥에 붙는
       단추(sticky)라, 글을 굴리는 동안 화면 한가운데에 떠서 글을 가렸다.
       위에 하나면 충분하다. 노트북에서는 반대로 위 것이 안 보이므로
       아래 것을 그대로 둔다 — 어느 화면에서나 닫기는 **하나**다. */
    .j3fh-swap .j3fh-cb:checked ~ .j3fh-p .j3fh-x:not(.j3fh-x-top) { display: none; }
    /* 이동막대는 bottom:8px 에 높이 64px = 바닥에서 72px 을 먹는다.
       마지막 줄이 그 밑에 깔리지 않게 그만큼 자리를 만든다. */
    .j3fh-swap .j3fh-cb:checked ~ .j3fh-p { padding-bottom: 5.8rem; }
}
</style>
"""

# **이름은 앞부분만 맞춰 본다.** 급락 항목 이름에는 '(상위 5등)'처럼 등수가 붙는데
# 그 숫자는 다시 잴 때마다 바뀐다. 이름을 통째로 맞추면 그때 설명이 조용히 사라진다.
#
# **점수 숫자를 여기 적을 때는 조심한다.** 배점을 고치면 이 글도 같이 고쳐야 한다.
# 2026-08-14에 「테마 상황」 카드가 사라진 항목을 계속 가리키고 있었다.
#
# **'무리'라고 쓰지 않는다**(2026-08-14 상하님 지시). 화면 어디에도 없는 말이라
# 상하님이 무엇을 가리키는지 되물으셔야 했다. 표에 있는 말 그대로 '관련 테마'라 쓴다.
# 「설명」 창에 들어가는 글. **핵심만 적는다**(2026-08-21 상하님 지시 —
# "설명란 내용이 너무 많다 핵심만 넣어라"). 남기는 것은 세 가지뿐이다 —
#   무엇을 보는가 · 배점(문턱) · 0점이면 왜 0점인가.
# 「왜 보는가」·「재어 보니」·「이렇게 읽으십시오」 같은 뒷이야기는 뺐다.
# 그 내력은 docs/US_THEME_SPEC.md와 git 기록에 남아 있다.
#
# **표에는 이 글을 안 붙인다**(같은 지시 — "심사항목에 초록색 글자만 나타내라").
# 항목 이름 밑에 흰 글씨로 붙이던 것을 걷어냈고, 여기 「설명」에서만 본다.
_FACTOR_HELP = (
    # 2026-08-26 상하님 지시로 급락 네 항목의 글을 두 줄 안으로 줄였다
    # ("설명 줄인 것 맞나? 너무 많다"). 무엇을 보는지와 몇 점인지만 남긴다.
    ("이 종목이 평소 크게 움직이나",
     "<b class='j3fh-k'>최근 3개월 동안 하루에 몇 %씩 움직였는지</b> — 오늘 목록에서 위쪽 절반이면 점수를 줍니다."),
    ("테마가 같이 오르는가",
     "<span class='j3fh-h'>무엇을 보는가</span> — 앱은 이 종목의 관련 테마가 최근 5일 동안 다른 테마보다 <b "
     "class='j3fh-k'>더 올랐는지</b> 보고, 테마 20개를 줄 세워 위쪽 5등 안에 들면 점수를 주려 했습니다.<br><span "
     "class='j3fh-z'>왜 0점인가</span> — 상승장 자리에서 재 보니 <b class='j3fh-k'>이 잣대로 고른 쪽이 더 벌지 "
     "않았습니다.</b> 최근 5일은 너무 짧아 그날그날 오르내림에 휘둘립니다. 대신 앱은 같은 ‘테마를 본다’는 생각을 훨씬 긴 잣대(반년 수익률·30주선)로 "
     "바꿔 급락 갈래에서만 점수를 줍니다."),
    ("이 테마가 이미 오름세로 돌아섰나",
     "같은 테마 회사들 중 <b class='j3fh-k'>몇 %가 30주선(150일 평균) 위</b>인지 — 테마 20개 중 3등 안이면 점수를 줍니다."),
    ("이 테마가 통째로 떨어졌나",
     "<b class='j3fh-k'>같은 테마 회사가 네 개 이상</b> 오늘 이 목록에 같이 올라왔는지 — 중간 점수는 없습니다."),
    ("이 테마가 지난 반년에 많이 올랐나",
     "같은 테마 회사들이 <b class='j3fh-k'>지난 반년에 평균 몇 % 올랐는지</b> — 테마 20개 중 3등 안이면 점수를 줍니다."),
    ("테마가 30주선 위에 있나",
     "<span class='j3fh-h'>무엇을 보는가</span> — 앱은 이 종목의 관련 테마에 든 회사 중 <b class='j3fh-k'>몇 %가 "
     "30주선(150일 평균) 위에 있는지</b> 세어, 테마 20개를 줄 세웁니다. 위에서 <b class='j3fh-k'>3등 안</b>에 들면 30점, "
     "아니면 0점입니다."),
    ("테마가 덜 빠졌나",
     "<span class='j3fh-h'>무엇을 보는가</span> — 앱은 이 종목의 관련 테마가 다른 테마보다 <b class='j3fh-k'>덜 "
     "떨어졌는지</b> 보고, 테마 20개를 줄 세워 위쪽 몇 등 안에 들면 점수를 주려 했습니다.<br><span class='j3fh-z'>왜 "
     "0점인가</span> — 앱은 2026-08-13까지 이 잣대에 점수를 주고 있었습니다. 그런데 나스닥이 −12%·−18%·−24%에 처음 닿은 날 "
     "기준으로 다시 재 보니 <b class='j3fh-k'>100번 중 34~44번</b>밖에 못 맞혔습니다. 오히려 <b class='j3fh-k'>많이 "
     "빠진 테마가 더 크게 되돌아왔습니다.</b> 그래서 앱은 0점으로 내렸습니다. 상승장 자리에서도 따로 재 봤지만 마찬가지로 통과하지 못했습니다."),
    ("테마 주봉이 오름세인가",
     "<span class='j3fh-h'>무엇을 보는가</span> — 앱은 관련 테마 회사들 중 몇 %가 아직 <b class='j3fh-k'>오름세 "
     "모양</b>인지 봅니다. 오름세 모양이란 지금 값이 50일 평균 위 · 50일 평균이 150일 평균 위 · 150일 평균이 200일 평균 위이고, 200일 "
     "평균이 오르는 중인 것입니다.<br><span class='j3fh-z'>왜 0점인가</span> — 나스닥이 −12%·−18%·−24%에 처음 닿은 날 "
     "기준으로 다시 재 보니 <b class='j3fh-k'>100번 중 34~44번</b>밖에 못 맞혔습니다. 네 조건을 다 채우려면 이미 한참 오른 뒤여야 "
     "해서, <b class='j3fh-k'>급락 바로 뒤에는 이 조건을 채우는 테마가 거의 없습니다.</b> 값은 그대로 적어 두니 참고로만 보십시오."),
    ("테마가 20일선 위에 있나",
     "<span class='j3fh-h'>무엇을 보는가</span> — 앱은 관련 테마 회사들 중 몇 %가 최근 한 달 평균값(20일선) 위에 있는지 세어 "
     "테마 20개를 줄 세웁니다.<br><span class='j3fh-z'>왜 0점인가</span> — 20일선은 한 달짜리라 급락 뒤에는 <b "
     "class='j3fh-k'>며칠 반등만으로도 금세 넘어섭니다.</b> 다시 재 보니 20일선 위에 있던 종목이 1년 뒤 오히려 <b "
     "class='j3fh-k'>23% 덜 올랐습니다.</b> 앱은 같은 생각을 훨씬 긴 잣대(30주선 30점)로 바꿔 주고 있습니다."),
    ("테마 대비 상대강도",
     "<span class='j3fh-h'>무엇을 보는가</span> — 앱은 이 종목이 최근 20일 동안 <b class='j3fh-k'>자기 관련 테마 "
     "평균보다 더 올랐는지</b> 봅니다."),
    ("SPY 대비 상대강도",
     "<span class='j3fh-h'>무엇을 보는가</span> — 앱은 이 종목이 최근 20일 동안 <b class='j3fh-k'>미국 시장 "
     "전체(SPY)보다 더 올랐는지</b> 봅니다."),
    ("52주 신고가 위치",
     "<span class='j3fh-h'>무엇을 보는가</span> — 앱은 지금 값이 <b class='j3fh-k'>지난 1년 최고가에 얼마나 "
     "가까운지</b> 봅니다. 가까울수록 점수가 높습니다."),
    ("추세",
     "<span class='j3fh-h'>무엇을 보는가</span> — 앱은 짧은 평균선이 긴 평균선 위에 있는지 봅니다(20일 · 50일 · 200일). "
     "위에서부터 차례로 놓여 있으면 오르는 중입니다.<br><span class='j3fh-z'>왜 0점인가</span> — 앱이 지난 10년을 창 96개로 "
     "잘라 재 보니, <b class='j3fh-k'>20일선 위는 96개 중 5개, 50일선 위는 12개</b>에서만 이겼습니다. 거의 거꾸로였습니다. "
     "여기까지 올라온 종목은 대부분 이미 오름세라 <b class='j3fh-k'>이 잣대로는 서로를 가려낼 수 없습니다.</b> 뺀 20점은 다른 항목에 나눠 "
     "주지 않았습니다 — 그래서 이 표의 만점은 100점이 아니라 80점입니다."),
    ("유동성",
     "<span class='j3fh-h'>무엇을 보는가</span> — 앱은 이 종목이 하루에 얼마나 많이 사고팔리는지 봅니다. 적으면 상하님이 사고팔 때 "
     "값이 크게 흔들립니다."),
    ("변동성 안정",
     "<span class='j3fh-h'>무엇을 보는가</span> — 앱은 값이 하루에 얼마나 크게 흔들리는지 봅니다."),
)


# ── 설명 창 **머리말** ──────────────────────────────────────────────────────
# 2026-08-15 상하님 지시 — "왜 그렇게 했는지 나스닥 어떻게 조사했고 결과가 그렇다
# 이런 내용을 맨 위에 표시하고 그다음 세부항목별 간단한 이유 넣어라."
#
# 항목 설명만 늘어놓으면 **왜 어떤 항목은 40점이고 어떤 항목은 0점인지**를 알 수
# 없다. 그 답은 항목 하나에 있지 않고 '어떻게 조사했나'에 있다. 그래서 파트마다
# 조사 방법과 결과를 맨 위에 한 번 적는다.
#
# **여기 적힌 숫자는 실제로 돌려서 나온 값이다**(CLAUDE.md 0-1 가). 배점을 다시
# 재면 이 글도 같이 고친다.
_FACTOR_HELP_HEAD = (
    ("_breakout",
     "상승장 (신고가 눌림매수) — 앱은 이렇게 조사했습니다",
     "<b>앱이 무엇을 했나</b> — 앱은 나스닥 명부 200종목의 지난 10년 일봉을 놓고, "
     "<b class='j3fh-k'>1년 최고가를 뚫은 뒤 −10~−15% 눌린 날</b>을 전부 찾아냈습니다. "
     "그리고 <b class='j3fh-k'>같은 날 뽑힌 종목끼리만</b> 견줬습니다 — 잘 오른 해에 "
     "뽑힌 종목과 빠진 해에 뽑힌 종목을 섞으면, 시장이 좋았던 것을 종목이 좋았던 "
     "것으로 착각하게 됩니다. 사고 나서 3개월·6개월·1년 들고 있었을 때를 각각 "
     "봤습니다.<br>"
     "<b>결과가 그렇습니다</b> — 종목 하나만 보는 잣대(지금 눌린 폭 · 거래대금 · "
     "하루 오르내림 폭)는 <b class='j3fh-k'>세 보유기간 어디에서도 갈라내지 "
     "못했습니다.</b> 갈린 것은 둘뿐이었습니다. 하나는 그 종목이 아니라 "
     "<b class='j3fh-k'>관련 테마</b>가 1년 최고에 얼마나 붙어 있나(70점), 다른 하나는 "
     "<b class='j3fh-k'>뚫던 날</b> 기준 앞 60일에 얼마나 올랐나(30점)입니다. "
     "둘을 더해 100점 만점입니다.<br>"
     "<b>0점 항목을 왜 남겨 뒀나</b> — 앱이 무엇을 보고 무엇을 버렸는지 상하님이 "
     "아셔야 하기 때문입니다. 0점은 '안 쟀다'가 아니라 <b class='j3fh-k'>'재 봤는데 "
     "통과하지 못했다'</b>는 뜻입니다."),
    ("_crash",
     "급락 후 반등장 (낙폭종목) — 앱은 이렇게 조사했습니다",
     # ── 2026-08-26 상하님 지시로 3분의 1로 줄였다 ─────────────────────────
     # 상하님 — "급락반등 전용배점에 설명보기인데 너무 길다. 1/3로 줄이고
     # 핵심 내용만 넣어라." 3,050자였다.
     # **남긴 것과 그 까닭** (지우면 규칙을 어긴다)
     #  · 점수를 주는 넷과 점수 — CLAUDE.md 0-1 마
     #  · 안 쓰는 것 — 0-1 마 "재 보고 버린 항목은 설명에 남긴다"
     #  · 보유기간 참고표 — 0-1 바 "앱은 파는 시점을 정하지 않는다.
     #    3개월·6개월·1년 성적을 나란히 보여줄 뿐이다"
     # **뺀 것** — 조사 방법 문단, 한계 두 문단, 표 뒤 세 문단. 숫자는
     # research/us_crash_holding.py 에 그대로 있다.
     "지난 10년 <b class='j3fh-k'>나스닥 바닥 아홉 번</b>에서 739종목을 재 "
     "봤습니다.<br>"
     "<b>점수를 주는 넷 (100점)</b><br>"
     "· <b class='j3fh-k'>주가 변동성 40점</b> — 크게 출렁이던 종목이 크게 "
     "튑니다.<br>"
     "· <b class='j3fh-k'>테마가 30주선 위 30점</b> — 업종이 흐름을 지키면 "
     "회복도 빠릅니다.<br>"
     "· <b class='j3fh-k'>같은 테마 4개 동시 하락 20점</b> — 업종째 밀려야 "
     "업종째 돌아옵니다.<br>"
     "· <b class='j3fh-k'>테마 6개월 수익률 10점</b> — 짧게 보면 덜 맞습니다."
     "<br>"
     "<b>안 쓰는 것</b> — <b class='j3fh-z'>20일선 위</b>와 "
     "<b class='j3fh-z'>대형기술주 감점</b>은 반대였고, "
     "<b class='j3fh-z'>고점 대비 낙폭</b>은 이미 쓴 값이며, "
     "<b class='j3fh-z'>위 테마 순위표</b>는 6개월에 무너졌습니다.<br>"
     "<b class='j3fh-k'>둘 다 점수를 받은 종목</b>이 특히 좋았습니다.<br>"
     # ── 2026-08-26 상하님 지시로 **한계와 참고표를 뺐다** ────────────────
     # 상하님 — "설명 줄인 것 맞나? 너무 많다." → 제가 못 빼는 넷을 여쭈었고
     # "한계랑 참고표 빼라"고 정해 주셨다.
     #
     # 이 둘은 원래 상하님이 넣으라 하셨던 것이라 제 판단으로는 못 뺐다 —
     #  · 한계의 실측값(바닥 하나씩 빼고 다시 재기 · 생존편향 +51.6/+74.6%)
     #    은 2026-08-19 지시였다.
     #  · 보유기간 참고표(3개월·6개월·1년·1년 반)는 CLAUDE.md 0-1 바가
     #    "앱은 파는 시점을 정하지 않고 지난 성적을 나란히 보여줄 뿐"이라고
     #    적어 둔 그 표다.
     # 오늘 상하님이 직접 빼라 하셨으므로 뺀다. **숫자는 그대로 살아 있다** —
     # research/us_crash_holding.py (보유기간) · research/us_crash_leaveout.py
     # (한계). 되살리려면 이 주석 자리에 그대로 도로 넣으면 된다.
     "<span class='j3fh-z'>앱은 파는 시점을 정하지 않습니다.</span>"),
    ("_theme",
     "테마 안에서 어느 종목을 볼까 — 앱은 이렇게 조사했습니다",
     f"<b>이 표가 하는 일</b> — 위 「{_THEME_COUNT}개 테마 실시간 순위」에서 테마를 고르셨으면, "
     "이 표는 <b class='j3fh-k'>그 테마 안에서 어느 종목을 볼지</b>를 매깁니다.<br>"
     "<b>앱이 무엇을 했나</b> — 앱은 나스닥 명부 종목의 지난 10년을 창(기간) "
     "<b class='j3fh-k'>96개</b>로 잘라, 잣대마다 '이 잣대가 높은 쪽이 정말 더 "
     "벌었나'를 창마다 따로 봤습니다. 한 기간에서만 통하는 값은 기간이 바뀌면 "
     "뒤집히기 때문입니다.<br>"
     "<b>결과가 그렇습니다</b> — 평균선 줄서기(추세)는 96개 창 중 "
     "<b class='j3fh-k'>20일선은 5개, 50일선은 12개</b>에서만 이겼습니다. 거의 "
     "거꾸로였습니다. 그래서 앱은 추세를 <b class='j3fh-z'>0점</b>으로 내렸습니다. "
     "남은 넷을 더해 <b class='j3fh-k'>80점 만점</b>입니다. 뒤의 둘(유동성 · 변동성 "
     "안정)은 더 벌 종목을 맞히는 잣대가 아니라 '상하님이 사고파실 수 있는 종목인가'를 "
     "거르는 잣대입니다.<br>"
     "<b>위 테마 점수(100점)에 대해</b> — 앱은 그 점수도 따로 재 봤습니다. 거래일 "
     "2,500일 동안 날마다 테마 20개를 그 점수로 줄 세우고 5일·10일·20일·3개월·"
     "6개월·1년 뒤 성적과 견줬는데, <b class='j3fh-k'>어느 기간에서도 앞날을 맞히지 "
     "못했습니다.</b> 그래서 그 점수는 앞날이 아니라 <b class='j3fh-k'>지금 달아오른 "
     "정도</b>로만 읽으십시오. 이름표를 '주도/관찰'에서 '강함/보통'으로 바꾼 것도 "
     "그 때문입니다."),
    ("",
     "이 종목 배점 — 앱은 이렇게 조사했습니다",
     "<b>앱이 무엇을 했나</b> — 앱은 나스닥 명부 종목의 지난 10년을 창(기간) "
     "<b class='j3fh-k'>96개</b>로 잘라, 잣대마다 '이 잣대가 높은 쪽이 정말 더 "
     "벌었나'를 창마다 따로 봤습니다.<br>"
     "<b>결과가 그렇습니다</b> — 평균선 줄서기(추세)는 96개 창 중 "
     "<b class='j3fh-k'>20일선은 5개, 50일선은 12개</b>에서만 이겼습니다. 거의 "
     "거꾸로여서 앱은 <b class='j3fh-z'>0점</b>으로 내렸습니다. 남은 넷을 더해 "
     "<b class='j3fh-k'>80점 만점</b>입니다. 뒤의 둘(유동성 · 변동성 안정)은 더 벌 "
     "종목을 맞히는 잣대가 아니라 '상하님이 사고파실 수 있는 종목인가'를 거릅니다."),
)


def _factor_help_close(key: str) -> str:
    """설명 창 **맨 위**의 닫기 (2026-08-26 상하님 지적).

    상하님 — "스마트폰 화면인데 설명이 너무 길어 닫는 버튼이 겹쳐 누를 자리가
    없다." 폰·태블릿에서 설명 창은 화면 아래에 붙어 열리는데, 그 위로 하단
    이동막대(홈·관심종목·시장분석)가 더 높은 층에 떠 있어서 창 바닥의 닫기를
    덮었다. 맨 위에도 하나 두면 글이 아무리 길어도 바로 닫을 수 있다.
    """
    return f"<label class='j3fh-x j3fh-x-top' for='{key}'>✕ 설명 닫기</label>"


def _factor_help_head(key: str) -> str:
    """이 배점표가 붙은 파트의 머리말. 열쇠 이름 끝으로 파트를 가른다."""
    text = str(key)
    for suffix, title, body in _FACTOR_HELP_HEAD:
        if suffix and text.endswith(suffix):
            return (f"<div class='j3fh-head'><span class='j3fh-head-t'>{title}</span>"
                    f"{body}</div>")
    _suffix, title, body = _FACTOR_HELP_HEAD[-1]
    return (f"<div class='j3fh-head'><span class='j3fh-head-t'>{title}</span>"
            f"{body}</div>")


def _factor_help_body(name) -> str:
    """이 심사항목의 설명 글. 설명이 없는 항목이면 빈 글자."""
    for prefix, body in _FACTOR_HELP:
        if str(name).startswith(prefix):
            return body
    return ""


def _factor_table_html(factor_rows: str, total_row: str, names, key: str,
                       notes=None) -> str:
    """배점표 한 벌 — 표 + 제목 옆 '설명' + 총점 아래 설명 창을 **한 덩어리로** 만든다.

    상하님 — "제목 심사항목 옆에 넣으라고." · "버튼 안눌린다."

    **한 덩어리여야 눌린다.** 확인칸·'설명'·창을 st.markdown 세 번에 나눠 넣으면
    스트림릿이 각각 다른 묶음에 그려서 브라우저가 서로를 못 찾는다. 이 화면의
    지수 그림 바꾸기(.j3-idx-swap)도 한 묶음이라 눌린다 — 같은 짜임으로 맞췄다.

    설명이 있는 항목이 하나도 없으면 표만 돌려준다 — 열 것이 없는데 '설명'만
    보이면 상하님이 없는 것을 찾으시게 된다.
    """
    # ``notes``는 배점표에 붙어 있던 '이 종목의 값' 줄이다. 표에서는 뺐고
    # (2026-08-21 상하님 지시 — "초록색 제목만 두고 나머지 흰색 내용 다 빼라")
    # 값은 여기 설명 창으로 내린다. 버리면 왜 이 점수인지가 화면에서 사라진다.
    names = [str(name) for name in (names or ())]
    note_list = [str(note or "").strip() for note in (notes or ())]
    note_list += [""] * (len(names) - len(note_list))
    picked = [(name, _factor_help_body(name), note)
              for name, note in zip(names, note_list)]
    picked = [item for item in picked if item[1] or item[2]]
    # 닫기 단추 색은 **그 파트의 갈래 색**이다(2026-08-14 상하님 지시). 갈래는 열쇠
    # 이름으로 안다 — j3_factor_help_pullback_breakout / …_crash. 테마 실시간·순위 7은
    # 갈래가 아니라 회색 그대로다(초록=상승장, 주황=급락이라는 약속이 흐려진다).
    close_tone = ("j3fh-x-breakout" if str(key).endswith("_breakout")
                  else "j3fh-x-crash" if str(key).endswith("_crash") else "")
    chip = f"<label class='j3fh-chip' for='{key}'>설명</label>"
    table = (
        "<table class='j3-factor-table'><thead><tr>"
        f"<th>심사 항목{chip}</th><th>획득(최대)</th></tr></thead>"
        f"<tbody>{factor_rows}{total_row}</tbody></table>"
    )
    items = "".join(
        f"<div class='j3fh-item'><div class='j3fh-name'>{html.escape(name)}</div>"
        + (f"<div class='j3fh-txt'>{body}</div>" if body else "")
        + (f"<div class='j3fh-now'>{html.escape(note)}</div>" if note else "")
        + "</div>"
        for name, body, note in picked
    )
    return (
        _FACTOR_HELP_CSS
        + "<div class='j3fh-swap'>"
        + f"<input type='checkbox' class='j3fh-cb' id='{key}'>"
        + table
        + f"<div class='j3fh-p'>{_factor_help_close(key)}{_factor_help_head(key)}{items}"
        + f"<label class='j3fh-x {close_tone}' for='{key}'>✕ 설명 닫기</label></div></div>"
    )


def _general_theme_score_help_html(factor_rows: str, total_row: str, key: str) -> str:
    """GENERAL 배점표 + 아래로 펼쳐지는 설명 카드.

    **급락·상승장과 똑같은 확인칸(checkbox) 방식이다** (2026-08-26 상하님 지시 —
    "일반테마에 설명보기 클릭하면 급락반등 전용배점의 설명보기처럼 설명이
    열리도록 해라").

    예전에는 여기만 <button> 에 자바스크립트로 손잡이를 달았다. 그 스크립트는
    작은 iframe 안에서 바깥 화면(window.parent)을 찾아 들어가야 하는데,
    스트림릿이 표를 다시 그리면 손잡이가 붙어 있던 자리가 통째로 갈려서 단추가
    죽었다. 확인칸 방식은 브라우저가 CSS로만 여닫으므로 다시 그려도 안 죽는다.
    """
    chip = f"<label class='j3fh-chip' for='{key}'>설명 보기</label>"
    table = (
        "<table class='j3-factor-table'><thead><tr>"
        f"<th>상세 배점{chip}</th><th>획득(최대)</th></tr></thead>"
        f"<tbody>{factor_rows}{total_row}</tbody></table>"
    )
    head = (
        "<div class='j3fh-head'><span class='j3fh-head-t'>"
        "📘 일반 테마매매 — 앱은 이렇게 종목을 고릅니다</span>"
        "<span class='j3fh-k'>좋은 테마 안에 있는 좋은 종목</span>을 찾습니다. "
        "종목 힘 <span class='j3fh-h'>60%</span> + 테마 힘 "
        "<span class='j3fh-k'>40%</span>로 최종점수를 만듭니다.<br>"
        "<span class='j3fh-z'>점수가 높다고 바로 매수하라는 뜻은 아닙니다.</span></div>"
    )
    cards = (
        ("종목점수 — <span class='j3fh-k'>100점</span>",
         "<span class='j3fh-h'>3개월 40점</span> · <span class='j3fh-h'>6개월 40점</span> · "
         "<span class='j3fh-h'>1년 최고가 근접 20점</span><br>시장보다 지속적으로 강하고 "
         "높은 가격대에 있는 종목인지 봅니다."),
        ("테마점수 — <span class='j3fh-k'>100점</span>",
         "<span class='j3fh-h'>6개월 35점</span> · <span class='j3fh-h'>3개월 30점</span> · "
         "<span class='j3fh-h'>강한 종목 수 25점</span> · <span class='j3fh-h'>최근 힘 증가 10점</span><br>"
         "테마의 중기·최근 힘과 여러 종목이 함께 강한지 봅니다."),
        ("최종점수", "<span class='j3fh-h'>종목 60%</span> + <span class='j3fh-k'>테마 40%</span>입니다. "
         "예: 종목 90점, 테마 80점이면 <span class='j3fh-k'>최종 86점</span>입니다.<br>"
         "실제 매수 여부는 시장상태와 현재 가격자리를 따로 확인합니다."),
    )
    items = "".join(
        f"<div class='j3fh-item'><div class='j3fh-name'>{title}</div>"
        f"<div class='j3fh-txt'>{body}</div></div>" for title, body in cards
    )
    general_css = (
        "<style>"
        ".j3-general-group{border-top:2px solid rgba(255,255,255,.35)!important;font-weight:800!important}"
        ".j3-general-factor-note{color:#9aa0aa;font-size:.78rem;font-weight:500;margin-top:.22rem}"
        "</style>"
    )
    return (
        _FACTOR_HELP_CSS + general_css
        + "<div class='j3fh-swap'>"
        + f"<input type='checkbox' class='j3fh-cb' id='{key}'>"
        + table
        + f"<div class='j3fh-p'>{_factor_help_close(key)}{head}{items}"
        + f"<label class='j3fh-x' for='{key}'>✕ 설명 닫기</label></div></div>"
    )


# **_bind_general_theme_help_scroll 은 걷어냈다** (2026-08-26).
# 일반 테마 설명을 <button> + 자바스크립트로 여닫던 장치였다. 그 스크립트는 작은
# iframe 안에서 바깥 화면(window.parent)을 찾아 들어가 손잡이를 달아야 했는데,
# 스트림릿이 표를 다시 그리면 손잡이가 붙어 있던 자리가 통째로 갈려서 단추가
# 죽었다(상하님 — "일반테마에 설명보기 클릭하면 급락반등 전용배점의 설명보기처럼
# 열리도록 해라"). 이제 급락과 같은 확인칸(checkbox) 방식이라 브라우저가 CSS로만
# 여닫는다. 다시 그려도 안 죽고, 작은 iframe 하나가 줄어 화면도 가벼워진다.


def _swing_factor_table_html(
    factor_rows: str, total_row: str, explanations: dict, key: str,
) -> str:
    """US_SWING_V1 표와 selector 중앙 설명 payload를 한 덩어리로 표시한다."""

    order = ("market", "rs60", "rs120", "breakout", "pullback",
             "theme", "volume", "breadth", "rebound")
    items = []
    for metric in order:
        payload = (explanations or {}).get(metric) or {}
        if not payload:
            continue
        title = html.escape(str(payload.get("title") or metric))
        current = html.escape(str(payload.get("display_value") or "자료부족"))
        one_line = html.escape(str(payload.get("one_line_explanation") or ""))
        detail = html.escape(str(payload.get("detail_explanation") or ""))
        status = html.escape(str(payload.get("status") or ""))
        confidence = html.escape(str(payload.get("confidence") or ""))
        sureness = us_swing.plain_confidence(payload.get("confidence"))
        items.append(
            "<div class='j3fh-item'>"
            f"<div class='j3fh-name'>{title} · {current}</div>"
            "<div class='j3fh-txt'>"
            f"<span class='j3-help-line'>{one_line}</span>"
            f"<span class='j3-help-detail'>{detail}</span>"
            f"<span class='j3-muted'>지금 {status or '—'}"
            + (f" · {html.escape(sureness)}" if sureness else "")
            + "</span></div></div>"
        )
    chip = f"<label class='j3fh-chip' for='{key}'>자세히</label>"
    table = (
        "<table class='j3-factor-table'><thead><tr>"
        f"<th>심사 항목{chip}</th><th>획득(최대)</th></tr></thead>"
        f"<tbody>{factor_rows}{total_row}</tbody></table>"
    )
    head = (
        "<div class='j3fh-head'><span class='j3fh-head-t'>"
        "상승장 (신고가 눌림매수) — 항목마다 무엇을 보고 준 점수인가</span>"
        "점수보다 **통과조건**이 먼저입니다. 여섯 가지를 다 넘지 못하면 뒤쪽 네 항목이 "
        "아무리 좋아도 등급을 붙이지 않습니다. 총점은 승률이 아닙니다.</div>"
    )
    return (
        _FACTOR_HELP_CSS
        + "<div class='j3fh-swap'>"
        + f"<input type='checkbox' class='j3fh-cb' id='{key}'>"
        + table
        # **창 맨 위에도 닫기를 둔다** (2026-08-29 상하님 지적 — "상승장 신고가
        # 눌림 전용배점 밑에 심사항목 옆에 자세히 클릭하면 설명문이 내려오는데
        # 설명문에 닫기 버튼이 없어졌다").
        #
        # 폰·태블릿(≤1200px)에서는 창 **바닥**의 닫기를 숨긴다 — 하단 이동막대에
        # 가려 누를 수가 없어서 2026-08-26에 그렇게 막았다(.j3fh-x:not(.j3fh-x-top)).
        # 그때 맨 위 닫기(_factor_help_close)를 급락·일반 테마 표에는 넣었는데
        # **이 표에만 안 넣었다.** 그래서 폰에서 이 창만 닫는 자리가 하나도
        # 없어졌다. 나머지 둘과 같은 자리에 같은 것을 넣는다.
        + f"<div class='j3fh-p'>{_factor_help_close(key)}{head}{''.join(items)}"
        + f"<label class='j3fh-x j3fh-x-breakout' for='{key}'>✕ 닫기</label>"
          "</div></div>"
    )


def _render_saved_trades_header() -> None:
    """저장해 둔 목록 구역 **맨 위**에 내가 남긴 매수 기록을 보여준다.

    2026-08-14 상하님 지시 — "날짜별로 저장해 둔 목록 보기에 제일 위에 자동 저장된
    게 나오도록 해 줘."

    **주문 기록이 아니다.** 상하님이 '지금 값으로 바로 저장'을 누르셨을 때 남는
    줄이다(_save_trade_now). 최근 것이 위로 온다.
    """
    try:
        records = j3store.list_trades(limit=10)
    except Exception as exc:
        st.caption(f"매수 기록을 읽지 못했습니다: {_safe_error_text(exc)}")
        return
    st.markdown(
        f"<div class='pl-kind'>🧾 내가 저장한 매수 기록 · 최근 {len(records)}건</div>",
        unsafe_allow_html=True,
    )
    if not records:
        st.caption(
            "아직 저장한 매수 기록이 없습니다. 종목 상세에서 "
            "‘🧾 지금 값으로 바로 저장’을 누르시면 여기 맨 위에 쌓입니다."
        )
        return

    def _money(value):
        try:
            return f"{float(value):,.2f}"
        except (TypeError, ValueError):
            return "—"

    head = "".join(
        f"<th>{name}</th>"
        for name in ("매수일", "종목", "티커", "매수가", "매매유형", "상태", "테마")
    )
    body = "".join(
        "<tr>"
        f"<td>{html.escape(str(row.get('buy_date') or '—'))}</td>"
        f"<td><span class='pl-name'>{html.escape(str(row.get('stock_name') or ''))}</span></td>"
        f"<td>{html.escape(str(row.get('ticker') or ''))}</td>"
        f"<td>{_money(row.get('buy_price'))}</td>"
        f"<td>{html.escape(str(row.get('trade_style') or '—'))}</td>"
        f"<td>{html.escape(str(row.get('status') or '—'))}</td>"
        f"<td><span class='pl-theme'>{html.escape(str(row.get('theme_name') or '—'))}</span></td>"
        "</tr>"
        for row in records
    )
    st.markdown(
        f"<div class='pl-wrap'><table class='pl-table'><thead><tr>{head}</tr></thead>"
        f"<tbody>{body}</tbody></table></div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "이 표는 **상하님이 눌러 남기신 기록**입니다. 아래 날짜별 목록은 그날 화면에 "
        "떠 있던 후보를 그대로 옮겨 둔 것이라 서로 다른 것입니다."
    )


def _trade_snapshot(theme_row: dict, leader: dict, market: dict) -> dict:
    """저장할 때 함께 남기는 **그때의 시장·테마·종목 상태**.

    한 곳에 모아 둔다 — 예전에는 폼 안에만 있어서, 다른 자리에서 저장하면 남기는
    내용이 조용히 달라질 수 있었다.
    """
    metrics = leader.get("metrics") or {}
    return {
        "captured_at": theme_row.get("source_time") or market.get("checked_at"),
        "market": {"regime": market.get("regime"), "score": market.get("score")},
        "theme": {
            "name": theme_row.get("name"), "etf": theme_row.get("etf"),
            "score": theme_row.get("score"), "rank": theme_row.get("rank"),
            "rs20": theme_row.get("rs20"), "breadth": theme_row.get("breadth"),
        },
        "stock": {
            "ticker": leader.get("ticker"), "rank": leader.get("rank"),
            "score": leader.get("score"), "current": metrics.get("current"),
            "score_model_version": leader.get("score_model_version"),
            "core_score": leader.get("core_score"),
            "support_score": leader.get("support_score"),
            "primary_status": leader.get("primary_status"),
            "from_high_pct": metrics.get("from_high_pct"),
            "ret20": metrics.get("ret20"), "atr_pct": metrics.get("atr_pct"),
        },
    }


def _save_trade_now(theme_row: dict, leader: dict, market: dict) -> tuple[bool, str]:
    """**지금 화면 값 그대로** 매수 기록 한 줄을 남긴다 (2026-08-14 상하님 지시).

    상하님 — "실제 매수 기록 부분은 클릭하면 그 시점에 자동매수 한 걸로 저장되게."

    **주문은 내지 않는다.** 이 앱은 증권사에 아무것도 보내지 않고 기록만 한다
    (CLAUDE.md 2번 — 자동매매·주문 API 금지). '자동매수'는 **그때 값으로 샀다고
    치고 적어 둔다**는 뜻이다.

    값은 지금 보고 계신 화면 그대로다 — 매수가는 현재가, 매수일은 오늘, 수량은
    비워 둔다. 실제 체결가가 다르면 아래 '값을 직접 적어 저장'에서 고쳐 적으시면 된다.
    """
    metrics, plan = leader.get("metrics") or {}, leader.get("plan") or {}
    price = metrics.get("current")
    if not price:
        return False, "지금 값을 못 읽어 저장하지 못했습니다. 잠시 뒤 다시 눌러 주십시오."
    buy_date = date.today()
    try:
        j3store.save_trade(
            ticker=leader["ticker"],
            stock_name=leader.get("name") or leader["ticker"],
            theme_name=theme_row.get("name") or "",
            buy_date=buy_date,
            buy_price=float(price),
            quantity=None,
            trade_style="스윙",
            entry_setup=plan.get("state"),
            recommendation_state=plan.get("recommendation"),
            market_regime=market.get("regime"),
            market_score=market.get("score"),
            theme_score=theme_row.get("score"),
            stock_score=leader.get("score"),
            score_model_version=leader.get("score_model_version"),
            entry_plan=plan,
            snapshot=_trade_snapshot(theme_row, leader, market),
            memo="화면에서 바로 저장(그때 값 그대로)",
        )
    except Exception as exc:
        return False, f"매수 기록 저장 실패: {_safe_error_text(exc)}"
    return True, (f"{leader.get('name') or leader['ticker']} · {buy_date.isoformat()} · "
                  f"${float(price):,.2f} 매수 기록을 저장했습니다.")


def _render_buy_form(
    theme_row: dict, leader: dict, market: dict, top_candidates: list[dict], stock_key: str,
    *, panel: str = "theme",
) -> None:
    ticker = leader["ticker"]
    metrics, plan = leader["metrics"], leader["plan"]
    # 위 '추천 근거 요약' 카드와 붙어 보이지 않게 한 줄 띄운다(2026-07-22 사용자 지시).
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    # 매수 기록은 눌러야 열린다 — 늘 펴 두면 화면이 길고 기록 조회도 매번 돈다
    # (2026-07-30 사용자 지시, 한국테마와 같은 처리).
    if not _section_toggle(
        "💾 실제 매수기록 저장하시겠습니까?", f"j3_buyform_open_{panel}",
        close_label="매수기록 닫기",
    ):
        return

    # **한 번 눌러 바로 저장**(2026-08-14 상하님 지시). 매수가는 지금 값, 매수일은
    # 오늘이다. 아래 자세한 폼은 그대로 뒀다 — 실제 체결가가 화면 값과 다를 때
    # 고쳐 적으실 자리다. **주문은 내지 않는다**(_save_trade_now 설명 참고).
    quick_msg_key = f"j3_quick_buy_msg_{panel}"

    def _quick_save():
        st.session_state[quick_msg_key] = _save_trade_now(theme_row, leader, market)

    price_now = (leader.get("metrics") or {}).get("current")
    st.button(
        f"🧾 지금 값으로 바로 저장 — {leader.get('name') or ticker}"
        + (f" ${float(price_now):,.2f}" if price_now else "")
        + f" · {date.today().isoformat()}",
        key=f"j3_quick_buy_{panel}", on_click=_quick_save,
    )
    quick_msg = st.session_state.pop(quick_msg_key, None)
    if quick_msg:
        (st.success if quick_msg[0] else st.error)(quick_msg[1])

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
                _render_records_editor(records, key_prefix=f"form_{panel}")
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
        _render_buy_form_fields(theme_row, leader, market, panel=panel)


def _render_buy_form_fields(theme_row: dict, leader: dict, market: dict,
                            *, panel: str = "theme") -> None:
    ticker = leader["ticker"]
    metrics, plan = leader["metrics"], leader["plan"]
    with st.form(f"j3_buy_form_{panel}_{ticker}", clear_on_submit=False, border=False):
        c1, c2, c3, c4 = st.columns(4)
        buy_date = c1.date_input("매수일", value=date.today(), key=f"j3_buy_date_{panel}_{ticker}")
        default_price = float(metrics.get("current") or 0.01)
        buy_price = c2.number_input(
            "실제 매수가(USD)", min_value=0.01, value=round(default_price, 2), step=0.01,
            key=f"j3_buy_price_{panel}_{ticker}",
        )
        quantity = c3.number_input(
            "수량(선택)", min_value=0.0, value=0.0, step=1.0, key=f"j3_buy_qty_{panel}_{ticker}",
        )
        trade_style = c4.selectbox(
            "매매유형", ["스윙", "단타", "중장기"], key=f"j3_trade_style_{panel}_{ticker}",
        )
        memo = st.text_area("매수 이유·메모", key=f"j3_buy_memo_{panel}_{ticker}", height=80)
        confirmed = st.checkbox(
            "실제 체결된 매수임을 확인합니다",
            key=f"j3_buy_confirm_{panel}_{ticker}",
        )
        submitted = st.form_submit_button("매수 기록 저장", width="stretch")

    if submitted:
        if not confirmed:
            st.error("실제 체결 확인을 체크해야 저장할 수 있습니다.")
            return
        snapshot = _trade_snapshot(theme_row, leader, market)
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
                score_model_version=leader.get("score_model_version"),
                entry_plan=plan,
                snapshot=snapshot,
                memo=memo,
            )
            st.success(f"{leader['name']} · {buy_date.isoformat()} · ${buy_price:,.2f} 매수 기록을 저장했습니다.")
        except Exception as exc:
            st.error(f"매수 기록 저장 실패: {_safe_error_text(exc)}")


def _render_radar_tail(market: dict, ranking: dict) -> None:
    """테마 구역 **뒤에 오는 화면들**을 한 곳에 모은다 (2026-08-27).

    상승장·급락 후 반등장 · 매수심사결과 높은 순위 9 · 종목검색 · 날짜별 목록이다.

    예전에는 이 다섯이 **두 군데에 똑같이** 적혀 있었다 — 테마 판이 닫혔을 때
    한 벌, 열렸을 때 한 벌. 그래서 테마 구역만 따로 떼어 낼 수가 없었다.

    **덤으로 흠 하나가 고쳐진다** — 테마 자료나 대장주 조회가 실패하면 예전에는
    그 자리에서 되돌아가 버려 상승장·순위 9·종목검색이 통째로 사라졌다.
    이제는 테마 쪽이 어떻게 되든 이 다섯은 늘 그려진다.
    """
    guest_mode = auth.is_guest()
    _render_pullback_finder(market, ranking)
    # 매수심사결과 높은 순위 7 — 한국테마(자비스4)와 같은 자리·같은 화면이다.
    if not guest_mode:
        _render_top7_section(market, ranking)
    _render_top7_close_above_search()
    _render_my_stock_panel(market, ranking)
    # 날짜별로 저장해 둔 목록(2026-08-09 상하님 지시). 네 갈래를 다 지나온 뒤에 둔다 —
    # 오늘 것을 먼저 보고, 지난 날 것은 그 아래에서 펴 본다.
    # **맨 위 「내가 저장한 매수 기록」 표는 뺐다** (2026-08-29 상하님 지시 —
    # "위에 캡처 화면은 날려라. 내가 저장하는 게 없잖아, 자동 저장되니.
    #  「어느 날 목록을 볼까요」 바로 위에까지 잘라라").
    # 그 표는 상하님이 종목 상세에서 「지금 값으로 바로 저장」을 누르셨을 때만
    # 쌓이는 줄인데, 목록은 이제 장 마감 뒤 저절로 저장되므로 누를 일이 없다.
    # 그래서 화면만 먹고 있었다. header 를 안 넘기면 그 자리가 통째로 빈다.
    # **기록 자체는 안 지운다** — DB(j3store)에 그대로 있고, 되살리려면 여기에
    # header=_render_saved_trades_header 를 도로 넣으면 된다.
    picklist_ui.render(
        st, "US", toggle=_section_toggle, close=_section_close,
        # 그 줄이 어느 파트에서 나왔는지에 따라 **다른 배점표**로 보내야 한다.
        # market·ranking 이 있어야 그 파트의 상세를 그리므로 여기서 싸서 넘긴다.
        on_pick=lambda code, name, kind, row: _picklist_detail(
            market, ranking, code, name, kind, row),
    )


# 저장해 둔 줄이 **어느 파트에서 나왔나**.
_PICKLIST_PART_BY_KIND = {
    "theme15": "테마 대장주",
    "breakout": "상승장",
    "crash": "급락 후 반등장",
    "pullback": "눌림목",
}

# **`origin` 칸은 갈래마다 다른 것이 들어 있다** (2026-09-02 실측).
#   순위 9(top7) 줄 — 「테마 대장주」·「상승장」·「급락 후 반등장」 (매수 파트)
#   상위 테마(theme15) 줄 — 「사이버보안」처럼 **테마 이름**
#   상승장·급락 줄 — 빈칸
# 그래서 origin 을 그냥 파트로 믿으면 theme15 줄이 「사이버보안」이라는 파트로
# 읽혀 어느 배점표로도 못 간다. **아는 파트 이름일 때만** 파트로 쓴다.
_PICKLIST_PARTS = ("테마 대장주", "상승장", "급락 후 반등장", "눌림목")


def _picklist_part(kind: str, row: dict) -> str:
    origin = str((row or {}).get("origin") or "").strip()
    if origin in _PICKLIST_PARTS:
        return origin
    return _PICKLIST_PART_BY_KIND.get(str(kind or ""), "")


def _picklist_theme_name(row: dict) -> str:
    """그 줄의 테마 이름. 상위 테마 줄은 `origin` 에, 나머지는 「테마」 칸에 있다."""
    origin = str((row or {}).get("origin") or "").strip()
    if origin and origin not in _PICKLIST_PARTS:
        return origin
    return str((row or {}).get("themes") or "").split("·")[0].strip()


def _find_scan_row(found: dict, code: str) -> dict | None:
    """오늘 그 파트 목록에서 이 종목 줄을 찾는다. 없으면 None."""
    if not isinstance(found, dict) or not found.get("ok"):
        return None
    want = str(code or "").upper()
    for row in (found.get("rows") or []):
        if str(row.get("ticker") or "").upper() == want:
            return row
    return None


def _picklist_detail(market: dict, ranking: dict, code: str, name: str,
                     kind: str, row: dict) -> None:
    """저장해 둔 목록에서 누른 종목을 **그 줄이 나온 파트의 배점표**로 연다.

    2026-09-02 상하님 지적 — *"CrowdStrike CRWD 종목을 내가 테마에서 클릭하면
    테마의 배점 기준으로 나와야 되고, 그같이 상승장에서 종목을 누르면 상승장의
    배점이 나와야지."*

    **전에는 어느 줄을 누르든 종목검색 길(`analyze_one_stock`)로 보냈다.** 그래서
    상승장에서 나온 CRWD 인데 테마 대장주 배점, 그것도 견줄 테마가 없어 상대강도
    25점이 통째로 0인 반쪽(80점 만점)으로 나왔다 — 표에 적힌 그날 점수 89.0 과
    아무 상관없는 숫자다. 「대장주 0위 · 추천 제외」도 같은 탓이었다.

    상하님 말씀대로 **같은 종목이라도 파트가 다르면 배점이 다른 것이 정상**이다
    (테마 대장주 94.9 · 상승장 89.0). 견주시려고 만든 것이므로 줄마다 그 줄의
    자로 재야 한다.

    **배점을 새로 만들지 않는다.** 순위 9가 이미 쓰는 길을 그대로 빌린다 —
    상승장·급락은 `_render_pullback_detail`(전용배점), 테마 대장주는
    `_render_stock_detail`(테마 배점)이다.

    **오늘 그 파트 목록에 없으면 없다고 적는다.** 저장된 줄은 지난 날 것이라
    오늘 그물에 안 걸릴 수 있다. 그때 엉뚱한 자로 재서 숫자를 만들어 내지 않는다
    (CLAUDE.md 0-1 바 — 빈 자리를 딴 것으로 채우지 않는다).
    """
    part = _picklist_part(kind, row)
    # 고른 종목이 바뀌면 상세·차트가 저절로 열리고 화면이 그 자리로 내려간다.
    if st.session_state.get("j3_picklist_shown") != code:
        st.session_state["j3_picklist_shown"] = code
        # **제 이름표(picklist)만 켠다.** 예전에는 눌림목 쪽 열쇠까지 같이 켰는데,
        # 그러면 위쪽 급락 구역의 상세까지 열려 같은 열쇠가 한 판에 두 번 생겼다
        # (2026-09-02 상하님 화면 — "multiple elements with the same key").
        # 이제 상세가 제 이름표로 그려지므로 남의 열쇠를 건드릴 까닭이 없다.
        for opened in ("j3_detail_open_picklist", "j3_intraday_open_picklist",
                       "j3_bundle_open_picklist"):
            st.session_state[opened] = True
        back_nav.opened(st, "j3_detail_open_picklist",
                        "j3_intraday_open_picklist", "j3_bundle_open_picklist")
        scroll_to.request(st, "detail_picklist")
    # 여기가 그 자리다 — 위쪽 눌림목 상세와 이름이 겹치면 엉뚱한 데로 내려간다.
    # 안쪽 상세도 같은 이름으로 한 번 더 그리지만, **먼저 그린 이곳**으로 간다
    # (getElementById 규칙). 제목 위로 내려와야 무엇을 보고 있는지 보인다.
    scroll_to.anchor(st, "detail_picklist")
    saved_score = row.get("score")
    saved_text = f" · 그날 점수 {float(saved_score):.1f}" if saved_score not in (None, "") else ""
    st.markdown(
        f"<div class='j3-section-title'>저장해 둔 목록에서 고른 종목 · "
        f"{html.escape(str(name or code))}"
        f"{html.escape(part and ' · ' + part or '')}{html.escape(saved_text)}</div>",
        unsafe_allow_html=True,
    )

    if part in ("상승장", "눌림목"):
        with st.spinner(f"{name or code} — 상승장 배점으로 심사 중입니다…"):
            found = _find_scan_row(j3data.breakout_scan(), code)
        if found:
            _render_pullback_detail(found, market, ranking, mode="breakout",
                                    panel="picklist")
            return
        _picklist_not_today(part, name or code)
        return

    if part == "급락 후 반등장":
        with st.spinner(f"{name or code} — 급락 후 반등장 배점으로 심사 중입니다…"):
            found = _find_scan_row(j3data.find_crash_rebound_stocks(), code)
        if found:
            _render_pullback_detail(found, market, ranking, mode="crash",
                                    panel="picklist")
            return
        _picklist_not_today(part, name or code)
        return

    if part == "테마 대장주":
        # 그 줄의 테마 이름으로 그 테마 대장주 목록을 부른다.
        theme_name = _picklist_theme_name(row)
        theme_row = next(
            (item for item in (ranking.get("rows") or [])
             if str(item.get("name") or "") == theme_name),
            None,
        )
        if theme_name:
            with st.spinner(f"{theme_name} 대장주를 다시 세는 중입니다…"):
                leaders = j3data.get_theme_leaders(
                    theme_name, market_score=float(market.get("score") or 0),
                    theme_score=float((theme_row or {}).get("score") or 0),
                )
            found = _find_scan_row(leaders, code)
            if found:
                _render_stock_detail(
                    theme_row or {"name": theme_name}, found, market, [found],
                    "j3_picklist_detail_choice", panel="picklist",
                    on_close=_forget_picklist_pick,
                )
                return
        _picklist_not_today(part or "테마 대장주", name or code)
        return

    # 파트를 알 수 없는 옛 줄(2026-08-15 이전 저장분)은 그렇게 적는다.
    st.info(
        f"이 줄에는 **매수 파트가 적혀 있지 않습니다**(2026-08-15 이전 저장분). "
        f"어느 배점으로 재야 할지 알 수 없어 배점표를 그리지 않습니다. "
        f"표에 적힌 그날 점수는 그대로 보실 수 있습니다."
    )
    _section_close("j3_detail_open_picklist", "선택종목 세부사항 닫기",
                   on_close=_forget_picklist_pick)


def _forget_picklist_pick() -> None:
    """상세를 닫으면 고른 표시도 같이 걷는다 (종목검색과 같은 방식)."""
    st.session_state.pop(picklist_ui.pick_key("US"), None)
    st.session_state.pop("j3_picklist_shown", None)


def _picklist_not_today(part: str, name: str) -> None:
    """오늘 그 파트 그물에 안 걸린 종목. **딴 자로 재지 않는다.**"""
    st.warning(
        f"**{html.escape(str(name))}** 는 오늘 「{html.escape(str(part))}」 목록에 "
        f"없습니다 — 저장된 날에는 걸렸지만 오늘 그물에는 안 걸렸습니다. "
        f"그 파트의 배점은 그날 목록 안에서만 잴 수 있어서, 여기서는 배점표를 "
        f"그리지 않습니다. 다른 자로 재면 표에 적힌 그날 점수와 어긋난 숫자가 "
        f"나옵니다."
    )
    _section_close("j3_detail_open_picklist", "선택종목 세부사항 닫기",
                   on_close=_forget_picklist_pick)


def _render_theme_panel(market: dict, ranking: dict, names: list) -> None:
    """고른 테마의 종목 표와 그 종목 상세 (2026-08-27에 따로 떼어 냈다).

    예전에는 이 몸통이 _render_radar_tab 안에 그대로 있었고, 중간에 return 이
    둘 있어서(테마 자료 없음·대장주 조회 실패) 그 뒤의 상승장·순위 9·종목검색
    까지 같이 건너뛰었다. 따로 떼어 내니 여기서 되돌아가도 뒤쪽은 그대로 그려진다.

    `names` 를 **받아서** 쓴다 — 2026-08-27에 안 넘겨주고 떼어 냈다가 시험
    스물아홉 개가 깨졌다. 이 목록은 부르는 쪽이 이미 만들어 둔 것이다.
    """

    # **테마에서 연 것을 하나도 남기지 않고 다 닫는다** (2026-08-28 상하님 지시).
    #
    # 상하님 — "20개 테마 닫기 하면 첫 번째 캡처 화면으로 가는데 그렇게 되면 안
    # 되고, 20테마 관련 열었던 거 다 닫고 세 번째 캡처 화면으로 돌아가야 한다."
    #
    # 예전에는 이 단추가 **테마 종목 판만** 닫아서, 위의 20개 순위표가 그대로
    # 열린 화면(첫 번째 캡처)에 남았다. 이제 「20개 테마 실시간 순위 닫기」와
    # 똑같이 순위표·상승장·급락장·순위 9까지 다 접고 미국테마 기본 화면으로
    # 돌아간다(세 번째 캡처). 두 단추가 같은 일을 하므로 한 함수를 같이 쓴다.
    st.button(
        "✕ 테마 종목 화면 닫기",
        key="close_j3_theme_panel_open_top",
        on_click=_close_theme_rank_from_fragment,
    )
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
    # 20개 순위표에서 테마 이름을 누르면 화면이 **여기까지 내려온다**
    # (2026-08-21 상하님 지시 — "석유·가스 테마를 클릭하면 두 번째 화면으로
    # 자동 내려가도록"). 표가 20줄이라 그 아래에 열리는 테마 종목 화면이
    # 두 화면 밑에 있었다.
    scroll_to.anchor(st, "theme_stocks")
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
    # 테마를 누르면 대장주 셋의 차트가 함께 열린다(_THEME_PANEL_OPEN_KEYS).
    # 그 자료를 **한 번에 묶어** 미리 받아 둔다 — 종목마다 따로 받으면 여섯 번을
    # 줄 서서 기다린다(2026-08-14 실측 4.5초, 그중 CPU는 0.2초뿐이었다).
    # 값은 안 만든다. 받아 두기만 하면 아래 차트들이 캐시를 그대로 쓴다.
    if any(st.session_state.get(key) for key in _THEME_PANEL_OPEN_KEYS):
        j3data.prefetch_charts([row.get("ticker") for row in leaders[:3]])
    st.markdown(
        f"<div class='j3-section-title'><span class='j3-theme-badge'>{selected_theme}</span> 테마 종목 1–6위</div>",
        unsafe_allow_html=True,
    )
    st.caption("표에서 종목 이름을 누르거나 아래 ‘상세 종목 선택’에서 1~6위 아무 종목이나 고르면 상세가 그 종목으로 바뀝니다.")
    # 표에 1~6위를 보여주면서 상세는 1~3위만 고를 수 있었다(2026-07-29 지적,
    # 한국테마와 같은 문제). 표에 나온 여섯 개를 그대로 고를 수 있게 한다.
    top_candidates = leaders[:6]
    ticker_options = [leader["ticker"] for leader in top_candidates]
    stock_key = f"j3_stock_choice_{selected_theme}"
    clicked_ticker = _render_leader_table(leaders, st.session_state.get(stock_key))
    if clicked_ticker:
        st.session_state[stock_key] = clicked_ticker
        # 이미 선택된 1위 종목을 다시 눌러도 상세가 열려야 한다. 이전에는 선택값과
        # 같으면 이 블록을 건너뛰어, 첫 행(MPC 등)을 눌러도 아무 일도 일어나지 않았다.
        # 상세만 열고 차트는 안 열려서 단추를 또 눌러야 했다(2026-08-06 상하님 지시).
        # 상승장·급락·순위 7 표와 같이 당일 차트와 일봉·주봉·월봉까지 한 번에 편다.
        for opened in _THEME_PANEL_OPEN_KEYS:
            st.session_state[opened] = True
        scroll_to.request(st, "detail_theme")
        # **st.rerun()을 부르지 않는다**(2026-08-21 상하님 지적 — "종목 클릭 후
        # 5초 걸린다"). 부르면 화면 한 판을 통째로 더 그린다(실측 1.8초, 그중
        # CPU 0.9초 — 온라인은 코어가 적어 더 걸린다). 안 불러도 결과는 같다 —
        # 아래 '상세 종목 선택'(key=stock_key)은 **이 줄보다 뒤에** 만들어지므로
        # 방금 넣은 값을 그대로 집어 들고, 상세도 그 종목으로 그려진다.
        # 표의 주황 표시는 _render_leader_table이 이 판에서 스스로 옮긴다.

    _render_leader_comparison(leaders)
    if leaders:
        # 재랭킹으로 이전에 고른 종목이 top3에서 빠지면 st.radio가 예외를 낸다 → 미리 정리한다.
        if stock_key in st.session_state and st.session_state[stock_key] not in ticker_options:
            del st.session_state[stock_key]

        def _stock_label(ticker):
            item = next((cand for cand in top_candidates if cand["ticker"] == ticker), None)
            return _stock_radio_label(item) if item else ticker

        def _open_selected_theme_stock():
            # 아래 '상세 종목 선택'으로 골라도 표에서 누른 것과 똑같이 편다.
            for opened in _THEME_PANEL_OPEN_KEYS:
                st.session_state[opened] = True
            scroll_to.request(st, "detail_theme")

        selected_ticker = st.radio(
            "상세 종목 선택",
            ticker_options,
            format_func=_stock_label,
            horizontal=True,
            key=stock_key,
            on_change=_open_selected_theme_stock,
        )
        selected_leader = next(
            (item for item in top_candidates if item["ticker"] == selected_ticker),
            top_candidates[0],
        )
        _render_stock_detail(theme_row, selected_leader, market, top_candidates, stock_key)
    # 맨 아래 닫기도 위 단추와 **같은 일**을 한다 — 어디서 닫든 같은 화면으로
    # 돌아가야 한다(2026-08-28 상하님 지시).
    _section_close("j3_theme_panel_open", "테마 종목 화면 닫기",
                   on_close=_close_theme_rank_from_fragment)


@st.fragment
def _render_theme_section(market: dict) -> None:
    """20개 테마 순위와 그 아래 테마 종목 화면을 **한 덩이**로 묶는다 (2026-08-27).

    상하님 실측 — "테마 클릭하면 테마 로딩 3초, 종목 클릭 2초." 자료를 새로 받는
    시간이 아니었다. 스트림릿은 무엇을 누르든 **화면을 처음부터 다시 만든다** —
    테마 하나를 눌러도 시장 판단·신호 카드·지수 넷·상승장·급락장·순위 9·종목검색
    까지 전부 다시 만들었다. 아무것도 안 바꾸고 다시 그리기만 해도 노트북에서
    0.6초, 코어가 적은 온라인에서 3초다(2026-08-26 실측).

    덩이로 묶으면 이 안에서 누른 것은 **이 안만** 다시 그린다. 뒤쪽 화면
    (상승장·급락 후 반등장·순위 9·종목검색·날짜별 목록)은 손대지 않으므로
    그대로 남는다. 순위 9(_render_top7_section)·상승장(_render_pullback_finder)과
    같은 장치다.

    **자료를 이 안에서 싣는다.** 밖에서 실어 넘기면 덩이만 다시 돌 때 밖이 안
    돌아, 마지막 판의 옛 순위가 언제까지고 그대로 나온다. 실은 것은
    `j3_theme_rankings`에 적어 둬서 뒤쪽 화면이 같은 것을 쓰게 한다.
    """
    ranking = _load_theme_rankings()
    st.session_state["j3_theme_rankings"] = ranking
    if not ranking.get("ok"):
        st.error(f"테마 자료 조회 실패: {_safe_error_text(ranking.get('error'))}")
        return
    if ranking.get("stale"):
        st.warning("온라인 재조회 실패로 마지막 정상 테마 자료를 표시하고 있습니다.")

    names = [row["name"] for row in ranking["rows"] if row.get("ok")]
    # 순위표는 **맨 위 단추로 여닫는다**(2026-08-14 상하님 지시 — "맨위에 20개 테마
    # 실시간 순위를 상승장·급락 후 반등장처럼 버튼을 만들어라. 클릭하면 창이
    # 열리도록"). 표가 열 줄이라 아래 구역까지 오려면 매번 한참 굴려야 했다.
    # 제목 대신 단추가 그 자리에 선다 — 상승장·급락 단추와 같은 크기·같은 장치다.
    # 닫는 단추는 '종목 찾기' 바로 위에도 하나 더 있다(_render_pullback_finder).
    #
    # **기본은 닫힘**(2026-08-14 상하님 지시 — "화면 처음 열릴 때 순위가 열려 있게
    # 하지 말고 닫아라. 그거 클릭해야 열리지"). 표가 열 줄이라 화면을 열자마자
    # 아래 구역이 전부 밀려 내려가지 않게 한다.
    # ── 강한 테마 순위 TOP 10 — **늘 보인다** (2026-09-03 새 디자인) ────────────
    # 그림의 시장분석 화면에 있는 그 자리다. **자료를 새로 받지 않는다** —
    # 바로 위에서 이미 받은 `ranking` 을 그대로 읽어 열 줄만 그린다.
    # 아래 「21개 테마 실시간 순위」 단추는 그대로 둔다 — 그것은 점수·등락·
    # 구성종목까지 다 있는 **전체 표**이고, 여기 있는 것은 순위만 보는 요약이다.
    st.markdown('<div class="j6-sec">⚡ 강한 테마 순위 TOP 10</div>',
                unsafe_allow_html=True)
    st.markdown(_j6_theme_rows(ranking, limit=10), unsafe_allow_html=True)

    rank_open = _section_toggle(
        f"📊 {_THEME_COUNT}개 테마 실시간 순위 열기", _THEME_RANK_OPEN,
        close_label=f"{_THEME_COUNT}개 테마 실시간 순위 닫기",
        on_close=_close_theme_rank_from_fragment,
    )
    if not rank_open:
        clicked_theme = None
        # 20개 순위를 닫을 때는 순위표만 숨기지 않고, 그 순위표에서 열었던
        # 테마 종목과 종목 세부 판도 같이 닫아 미국테마 기본화면으로 돌아간다.
        st.session_state["j3_theme_panel_open"] = False
        for opened in _THEME_PANEL_OPEN_KEYS:
            st.session_state[opened] = False
    else:
        clicked_theme = _render_theme_table(ranking, st.session_state.get("j3_theme_choice"))
        # **이 점수가 무엇인지 정직하게 적는다**(2026-08-14). 재 보니 점수가 높은
        # 테마가 그 뒤에 더 오르지 않았다 — 평상시 1,708일에서 5일부터 1년까지
        # 여섯 기간 모두 오차가 0을 걸쳤다(research/us_theme_rank_check.py).
        # 그래서 배점 숫자는 그대로 두되(바꿀 근거가 없다) **화면이 앞날을 말하지
        # 않게** 한다. 갈래별 배점(상승장·급락)이 앞날을 재는 자리다.
        st.caption(
            f"테마 계산 시각: {ranking.get('checked_at') or '—'} · "
            "구성종목이 20일선 위인 비율 40 · 최근 5일 오른 비율 30 · "
            "최근 20일 오른 비율 20 · 덜 빠졌나 10으로 매깁니다"
        )
        st.markdown(
            "<div class='j3-pull-guide'><b>이 점수는 오늘 그 테마가 어떤 "
            "상태인지를 요약한 것입니다. <u>앞날을 맞히는 점수가 아닙니다.</u></b> "
            "제가 10년치로 재 보니, 이 점수가 높은 테마가 그 뒤에 더 오르지는 "
            "않았습니다(5일 뒤부터 1년 뒤까지 여섯 기간 모두).<br>"
            "<b>앞날을 재는 자리는 아래 ‘종목 찾기’입니다</b> — 상승장과 급락 후 "
            "반등장은 각자 따로 잰 배점을 씁니다.</div>",
            unsafe_allow_html=True,
        )
    if clicked_theme in names:
        st.session_state["j3_theme_choice"] = clicked_theme
        st.session_state["j3_theme_choice_widget"] = clicked_theme
        st.session_state["j3_theme_panel_open"] = True
        # 테마 하나를 누르면 **아래 네 구역까지 한 번에 편다**(2026-08-14 상하님 지시 —
        # "대장주 1~3위까지 자동 클릭되게, 선택종목 세부사항 보기까지, 당일 실시간
        # 차트 보기·일봉·주봉·월봉 보기까지"). 그전에는 단추를 네 번 더 눌러야 했다.
        # 종목은 안 고르셨으면 그 테마 **1위**가 열린다(아래 라디오의 첫 값).
        # 표에서 종목을 누를 때(아래 clicked_ticker)와 **같은 열쇠 묶음**이다 —
        # 하나를 고치면 둘 다 고쳐야 한다.
        for opened in _THEME_PANEL_OPEN_KEYS:
            st.session_state[opened] = True
        # 연 자리가 표 아래 두 화면 밑이라 직접 굴려 내려가야 했다. 열면서 같이
        # 내려간다(2026-08-21 상하님 지시).
        scroll_to.request(st, "theme_stocks")
    if (st.session_state.get("j3_theme_panel_open")
            and st.session_state.get("j3_theme_choice_widget") not in names):
        preferred_theme = st.session_state.get("j3_theme_choice")
        st.session_state["j3_theme_choice_widget"] = preferred_theme if preferred_theme in names else names[0]

    # 선택 테마 설명·종목 1~6위·상세 종목 선택은 평소에는 닫아 둔다. 20개 순위표의
    # 테마 이름을 눌렀을 때만 한 화면으로 열고, 아래 독립 영역들은 그대로 보여준다.
    if st.session_state.get("j3_theme_panel_open"):
        _render_theme_panel(market, ranking, names)

    # 덩이 안에서 「다 닫기」를 눌렀으면 여기서 판 전체를 다시 그린다.
    # **화면 내려주기보다 먼저** 부른다 — 순서를 바꾸면 내려갈 자리를 적어 둔
    # 표시가 버려지는 판에서 소모돼 화면이 안 내려간다(2026-08-26 실측).
    _run_close_all_if_requested()
    # 덩이는 페이지 맨 끝이 안 돌아온다 — 여기서 내려 준다.
    scroll_to.run(st)


def _render_radar_tab(market: dict) -> None:
    # 네 개의 긴 목록을 닫으면 이 미국테마 메인 시작점으로 돌아온다.
    scroll_to.anchor(st, _RADAR_MAIN_ANCHOR)
    # 테마 구역은 따로 도는 덩이다. 테마 자료도 그 안에서 싣는다.
    _render_theme_section(market)
    ranking = st.session_state.get("j3_theme_rankings") or {}
    if not ranking.get("ok"):
        # 오류 문구는 덩이 안에서 이미 보여줬다. 뒤쪽 화면은 이 자료를 쓰므로 건너뛴다.
        return
    _render_radar_tail(market, ranking)


@st.fragment
def _render_top7_section(market: dict, ranking: dict) -> None:
    """순위 7과 그 상세를 한 덩이로 묶는다 (2026-07-30 폰 실측: 닫는 데 3초).

    이 덩이 안에서 단추를 누르면 스트림릿이 여기만 다시 그린다. 묶기 전에는 단추
    한 번에 지수 카드·게이지·테마 20줄까지 판 전체를 다시 그렸다 — 자료를 하나도
    안 가져오는 '닫기'가 3초 걸린 이유가 그것이다.
    상세도 같이 넣어야 한다. 표만 묶으면 종목 이름을 눌러도 덩이 밖에 있는 상세가
    다시 안 그려져 아무 일도 안 일어난 것처럼 보인다.
    """
    _render_top_reviewed(market, ranking)
    _render_top_reviewed_detail(market, ranking)
    _run_close_all_if_requested()
    # 이 덩이도 프래그먼트라 페이지 끝이 안 돌아간다 — 여기서 내려 준다.
    # finally로 감싸지 않는다(위 _render_pullback_finder의 주석 참고).
    scroll_to.run(st)


def _kept_recently(key: str, seconds: float = 300) -> bool:
    """방금 찾아 둔 결과가 아직 쓸 만한가 (기본 5분).

    닫았다 바로 다시 열 때 같은 결과를 다시 찾느라 몇 초를 또 내던 것을 없앤다.
    단추는 그대로 하나다 — 5분이 지나면 알아서 새로 찾는다(2026-07-31).
    """
    at = st.session_state.get(key)
    try:
        return bool(at) and (time.time() - float(at)) < seconds
    except (TypeError, ValueError):
        return False


# 순위 7의 자리 배분 (2026-08-06 사용자 지시).
# 세 군데에서 갖고 오는데 **자가 서로 다르다.** 하나의 자로 다시 재면 급락 종목이
# 영원히 못 올라온다 — 종목 조건점수 100점 중 45점이 '52주 신고가에 가까운가'(25)와
# '이동평균 위인가'(20)인데, 고점에서 20~50% 빠진 종목은 정의상 그 45점을 못 받는다.
# 실제로 2026-08-06에 두 갈래 27종목을 넣고 돌려 보니 상위 7에 하나도 못 들었다.
# 그래서 섞어 재지 않고 **자리를 나눠 각자 자기 자로 뽑는다.**
# 2026-08-12 상하님 지시로 3·3·3 아홉 자리가 됐다 — "대장주 3개 상승장 3개
# 급락 3개씩 해라. 급락하는 시장에서는 상승장이 없잖아. 없으면 없는 대로 하면 돼.
# 그 대신 설명을 해야겠지."
# 자리 배분은 **모듈이 정한다** — 화면과 클라우드 수집기가 같은 값을 봐야 한다.
_TOP7_QUOTA = tuple(getattr(j3data, "TOP_PICK_QUOTA",
                            (("테마 대장주", 3), ("상승장", 3), ("급락 후 반등장", 3))))
_TOP_TOTAL = int(getattr(j3data, "TOP_PICK_TOTAL",
                         sum(quota for _name, quota in _TOP7_QUOTA)))

# 상승장·급락 표에서 처음부터 펴 두는 줄 수. 나머지는 접어 둔다
# (2026-08-06 사용자 지시 — 급락은 20줄이라 화면이 너무 길었다).
# 2026-08-07에 15 → 10으로 더 줄였다(상하님 지시). 아래 접는 칸 이름은 이 값에서
# 자동으로 만든다 — '11위~20위 더 보기'.
_RULEBOOK_OPEN_ROWS = 10


def _blend_top7(market: dict, ranking: dict) -> dict:
    """세 파트에서 각자 자기 자로 3개씩 뽑아 아홉 개를 만든다(2026-08-06).

    **뽑는 일은 jarvis3_data.collect_top_picks가 한다** — 2026-08-15에 여기서 그리로
    옮겼다. 여기 있는 동안에는 클라우드 수집기가 같은 것을 부를 수 없어서, 화면은
    3·3·3을 보여 주는데 **저장은 한 통에서 위에서 아홉을 뽑은 딴 목록**을 남겼다
    (상하님 지적 — "왜 순위가 123 123 123 이렇게 되어야지 1~9위가 나오냐").
    이 함수가 하는 일은 이제 **화면에서만 아는 것을 넘겨 주는 것**뿐이다 —
    상하님이 이미 열어 두신 갈래 결과를 넘겨 같은 조회를 두 번 하지 않게 한다.
    """
    market_score = float(market.get("score") or 0)
    opened = st.session_state.get("j3_pullback_result") or {}
    opened_mode = str(st.session_state.get("j3_pullback_mode") or "")
    result = j3data.collect_top_picks(
        ranking.get("rows") or [],
        market_score=market_score,
        breakout=opened if opened_mode == "breakout" else None,
        crash=opened if opened_mode == "crash" else None,
    )
    # **저장은 화면이 보여 주는 그 목록이다**(CLAUDE.md 10-1). 예전에는 섞기 전
    # 재료(find_top_reviewed_stocks)를 저장해서 저장 목록과 화면이 갈라져 있었다.
    picklist_ui.autosave("US", "top7", result)
    return result


def _render_top_reviewed(market: dict, ranking: dict) -> None:
    """매수심사결과 높은 순위 9 (2026-08-12 상하님 지시로 7 → 9).

    세 군데에서 각자 자기 자로 뽑아 합친다 — 테마 대장주 3 · 상승장 3 · 급락 3.
    **점수를 다시 재지 않는다.** 각 목록이 제 자로 잰 값을 그대로 쓴다.
    **빈 자리는 딴 갈래로 메우지 않고 왜 비었는지 적는다.**
    표는 위 '테마 종목' 표와 같은 모양으로 화면에 바로 편다.
    """
    # 재료는 셋이다(2026-08-06 사용자 지시 — "누르든 안 누르든 둘 다 자동으로").
    #   ① 20개 테마의 대장주
    #   ② 상승장(신고가 눌림매수) 결과
    #   ③ 급락 후 반등장(낙폭종목) 결과
    # 예전에는 ②·③ 중 **마지막에 누른 하나만** 썼다. 이제 단추를 안 눌러도 둘 다
    # 자동으로 모은다. 두 갈래는 같은 일봉 묶음을 쓰므로 한 번만 받아 온다.
    # 단추는 하나다 — 열려 있으면 접고, 닫혀 있으면 새로 뽑아 편다
    # (2026-07-30 사용자 지시: '새로 뽑기'를 따로 두지 말고 예전처럼 하나로).
    is_open = bool(st.session_state.get("j3_top7_open"))
    run_requested = st.button("매수심사결과 높은 순위 9", key="j3_top7_find")
    if run_requested and is_open:
        # 닫기 — 조회는 하지 않는다. 열린 것을 모두 닫고 메인 시작점으로 올라간다
        # (2026-08-26 상하님 지시). 이 단추도 프래그먼트 안이라 판 전체를 다시
        # 그려야 바깥의 20개 테마 순위·상승장·급락장이 화면에서 사라진다.
        _close_all_from_fragment()
        run_requested = False
    if (
        run_requested
        and _kept_recently("j3_top7_at")
        and st.session_state.get("j3_top7_result") is not None
    ):
        # 방금 뽑아 둔 것이 있으면 그대로 편다 — 다시 여는 데 몇 초를 또 내지 않는다.
        st.session_state["j3_top7_open"] = True
        run_requested = False
    if run_requested:
        with st.spinner("테마 대장주와 두 갈래 종목을 각각 줄 세우는 중입니다…"):
            found = _blend_top7(market, ranking)
        st.session_state["j3_top7_result"] = found
        st.session_state["j3_top7_at"] = time.time()
        st.session_state["j3_top7_open"] = True
        # 1위 종목 상세를 미리 펴 두지 않는다 — 상세 한 벌이 분봉·일봉·주봉·월봉을
        # 다 받아 오느라 여는 시간이 그만큼 늘어난다(2026-07-30).
        st.session_state.pop("j3_top7_pick_row", None)
        # 여기서 st.rerun()을 부르지 않는다. 단추를 누르면 스트림릿이 이미 화면을
        # 한 번 다시 그리는 중이고, 상세는 이 아래에서 그려지므로 지금 넣은 값이
        # 그대로 쓰인다. rerun을 부르면 통째로 한 번 더 그려 시간이 두 배가 된다.

    if not st.session_state.get("j3_top7_open"):
        return
    result = st.session_state.get("j3_top7_result")
    if result is None:
        return
    rows = result.get("rows") or []
    if not rows:
        st.warning("심사할 대장주를 한 종목도 못 모았습니다. 테마 순위를 먼저 갱신해 보십시오.")
        return

    errors = result.get("errors") or []
    st.caption(
        f"테마 {result.get('scanned_themes', 0)}개 심사 · 후보 {result.get('candidate_count', 0)}개 → "
        f"{len(rows)}종목 (자리 {_TOP_TOTAL}개)"
        + (f" · 자료를 못 받은 테마 {len(errors)}개" if errors else "")
    )
    # **빈 자리는 감추지 않는다**(2026-08-12 상하님 지시). 자리를 못 채웠으면
    # 왜 비었는지 적는다 — 급락장에 상승장 자리가 없는 것은 알아야 할 정보다.
    for note in result.get("empty_notes") or []:
        st.caption(f"🔸 {note} — 다른 갈래로 채우지 않습니다.")

    st.caption("종목 이름을 누르면 아래에 그 종목 상세와 차트가 한꺼번에 열립니다.")
    widths = [0.6, 2.0, 1.2, 1.2, 1.3, 1.6]
    # '조건점수'는 갈래마다 다른 자로 잰 값이라 이름을 바꿨다(2026-08-06 사용자 물음).
    titles = ["순위", "종목", "점수 (갈래 자)", "매수 상태", "현재가", "어느 분야"]
    box = st.container(key="j3_top7_table")
    for column, title in zip(box.columns(widths), titles):
        column.markdown(f"<div class='j3-th-head'>{title}</div>", unsafe_allow_html=True)
    # **표 한 벌에 칸을 한 번만 만든다** (2026-08-26 상하님 지시로 관찰만 표와
    # 같은 방식으로 바꿨다). 이 표는 한 줄에 칸이 여섯이라 가장 무거웠다 —
    # 줄마다 칸을 새로 만들면 스트림릿이 껍데기를 줄마다 여섯 벌씩 만든다.
    # 이제 순위·점수·매수 상태·현재가·어느 분야는 각각 한 덩이로 쌓고,
    # 종목 이름 단추만 진짜 단추로 둔다.
    # **값·점수·차례·색은 하나도 안 바뀐다.** 몇 덩이로 나누어 보내느냐만 바뀐다.
    cols = box.columns(widths)
    rank_cells, score_cells, state_cells, price_cells, source_cells = [], [], [], [], []
    labels = []
    for index, row in enumerate(rows):
        plan = row.get("plan") or {}
        guide = guidance.build(plan, money=_price, market_score=market.get("score"))
        dot = {"go": "🟩", "wait": "🟨", "stop": "🟥"}.get(guide["level"], "🟨")
        rank_cells.append(
            f"<div class='j3-td'>{dot} {row.get('pick_rank', index + 1)}위</div>"
        )
        labels.append((f"{row.get('name') or row['ticker']} ({row['ticker']})", index, row))
        score = float(row.get("score") or 0)
        score_cells.append(
            "<div class='j3-td'><div class='j3-barwrap'><div class='j3-bar'>"
            f"<div class='j3-bar-fill j3-bar-green' style='width:{min(score, 100):.0f}%'></div>"
            f"</div><span class='j3-bar-num'>{score:.1f}</span></div></div>"
        )
        state_cells.append(f"<div class='j3-td'>{plan.get('state', '—')}</div>")
        price_cells.append(
            f"<div class='j3-td' style='font-weight:700'>"
            f"{_price(row['metrics'].get('current'))}</div>"
        )
        # 분야 이름이 길면 옆 칸(현재가)을 덮어썼다(2026-07-30 캡처로 확인).
        # 어느 갈래에서 왔는지를 **먼저** 적는다(2026-08-06 사용자 지시) — 점수가
        # 갈래마다 다른 자로 잰 값이라, 어느 자로 잰 것인지 알아야 읽을 수 있다.
        origin = str(row.get("top7_origin") or "")
        themes = " · ".join(row.get("sources") or row.get("themes") or [])
        source_text = " · ".join(part for part in (origin, themes) if part) or "—"
        origin_class = {
            "상승장": "j3-top7-up", "급락 후 반등장": "j3-top7-crash",
        }.get(origin, "j3-top7-leader")
        source_cells.append(
            f"<div class='j3-td {origin_class} j3-top7-src'"
            f" title='{html.escape(source_text)}'>{html.escape(source_text)}</div>"
        )

    cols[0].markdown(_stacked(rank_cells), unsafe_allow_html=True)
    for label, index, row in labels:
        if cols[1].button(label, key=f"j3top7_{index:02d}", width="stretch"):
            # rerun 없이 값만 바꾼다 — 상세는 이 아래에서 그려지므로 곧바로 반영된다.
            st.session_state["j3_top7_pick_row"] = row
            # 종목을 누르면 세부사항과 차트까지 한 번에 열린다(2026-08-06 사용자 지시,
            # 상승장·급락 표와 같은 동작). 누르고 또 눌러야 보이던 것을 없앤다.
            # 갈래에서 온 줄은 눌림목 상세(panel="pullback")가 그리고 대장주 줄은
            # 종목 상세(panel="top7")가 그리므로 양쪽 열쇠를 다 켠다.
            for opened in ("j3_detail_open_top7", "j3_bundle_open_top7",
                           "j3_intraday_open_top7",
                           "j3_detail_open_pullback", "j3_bundle_open_pullback",
                           "j3_intraday_open_pullback"):
                st.session_state[opened] = True
            scroll_to.request(st, "detail_top7")
    cols[2].markdown(_stacked(score_cells), unsafe_allow_html=True)
    cols[3].markdown(_stacked(state_cells), unsafe_allow_html=True)
    cols[4].markdown(_stacked(price_cells), unsafe_allow_html=True)
    cols[5].markdown(_stacked(source_cells), unsafe_allow_html=True)
    # 종목 이름 단추는 '테마 종목' 표와 같은 옷을 입힌다.
    st.markdown(
        "<style>"
        "div[class*='st-key-j3top7_'] button { background: rgba(255,255,255,.025) !important;"
        " border: 1px solid rgba(255,255,255,.24) !important; box-shadow: none !important;"
        " border-radius: .55rem !important;"
        " min-height: 2.4rem !important; width: 100% !important; }"
        # 손을 올리면 테두리가 보라색 — 테마 단추와 같은 결이다(2026-08-09 지시).
        "div[class*='st-key-j3top7_'] button:hover {"
        " background: rgba(192,132,252,.09) !important;"
        " border-color: rgba(192,132,252,.55) !important; }"
        "div[class*='st-key-j3top7_'] button p { color: #e6e6e6 !important;"
        " font-weight: 700 !important; }"
        "</style>",
        unsafe_allow_html=True,
    )
    # 구역 맨 아래 닫기 단추 — 다른 구역에는 다 있는데 여기만 없었다
    # (2026-08-06 사용자 지적). 폰에서 표 끝까지 내려가면 위 단추가 화면 밖으로 나간다.
    _section_close(
        "j3_top7_open", "매수심사결과 높은 순위 9 닫기",
        on_close=_close_all_from_fragment,
    )


def _render_top_reviewed_detail(market: dict, ranking: dict) -> None:
    """순위 7에서 고른 종목의 상세. 위 테마 상세·눌림목 상세와 완전히 별개다."""
    # 구역이 닫혔으면 상세도 그리지 않는다. 예전에는 골라 둔 줄(j3_top7_pick_row)만
    # 보고 그려서, 순위 9를 닫아도 상세가 화면에 그대로 남았다(2026-08-26 상하님 캡처).
    if not st.session_state.get("j3_top7_open"):
        return
    picked = st.session_state.get("j3_top7_pick_row")
    if not picked:
        return
    # 순위 7은 제 이름의 자리를 따로 갖는다 — 안에서 눌림목 상세를 다시 그릴 때
    # 같은 이름이 두 번 생겨 위쪽(갈래 표 밑) 자리로 잘못 내려가는 것을 막는다.
    scroll_to.anchor(st, "detail_top7")
    st.markdown(
        f"<div class='j3-section-title'>순위 7에서 고른 종목 · "
        f"{html.escape(str(picked.get('name') or picked.get('ticker') or ''))}</div>",
        unsafe_allow_html=True,
    )
    # 갈래에서 온 줄은 눌림목 상세가 그리고, 테마 대장주 줄은 종목 상세가 그린다.
    # 어느 갈래에서 왔는지는 top7_origin에 적혀 있다 — 위 표에서 지금 무엇을 보고
    # 있느냐(j3_pullback_mode)와 다를 수 있으므로 **줄에 적힌 갈래로** 잰다
    # (2026-08-06). 안 그러면 급락 종목을 상승장 자로 재는 일이 생긴다.
    origin_mode = {"상승장": "breakout", "급락 후 반등장": "crash"}.get(
        str(picked.get("top7_origin") or "")
    )
    if origin_mode or "pullback" in picked:
        _render_pullback_detail(picked, market, ranking, mode=origin_mode)
        return
    theme_name = (picked.get("sources") or ["—"])[0]
    # **테마 줄을 그대로 찾아서 넘긴다** (2026-08-26 상하님 지적 — "매수심사결과
    # 높은 순위 9 리스트 종목 중에 테마 부분 클릭하면 배점 종류가 안 나온다,
    # 합계만 나온다").
    #
    # 여기서 이름만 든 빈 껍데기 {"name": ...} 를 넘기고 있었다. 그러면
    # _render_stock_detail 이 테마 배점(score_parts)을 못 찾아 「일반 테마매매
    # 점수」 표로 못 가고, 옛 80점짜리 표로 떨어진다. 그 표는 종목 배점
    # (score_parts)을 쓰는데 일반 점수 종목에는 그 칸이 없어 **줄이 하나도 안
    # 그려지고 총점만 남았다.** 96.1/80.0 처럼 획득이 만점보다 큰 숫자가 나온
    # 것도 100점짜리 점수를 80점 자로 잰 탓이다.
    #
    # 점수를 새로 계산하지 않는다 — 이미 20개 테마 순위가 만들어 둔 줄을 그대로
    # 찾아 넘길 뿐이다. 못 찾으면 예전처럼 이름만 넘긴다.
    theme_row = next(
        (row for row in (ranking.get("rows") or [])
         if str(row.get("name") or "") == str(theme_name)),
        {"name": theme_name},
    )
    _render_stock_detail(
        theme_row, picked, market, [picked],
        "j3_top7_detail_choice", panel="top7",
    )


def _render_top7_close_above_search() -> None:
    """「종목검색」 바로 위에 두는 매수심사결과 순위 9 닫기 (2026-08-26 상하님 지시).

    상하님 — "맨 밑에 종목검색 위에 매수심사결과 높은 순위 9 닫기 버튼 만들고
    20개 테마 실시간 순위 닫기처럼 만들라고."
    「20개 테마 실시간 순위 닫기」가 '종목 찾기' 바로 위에 있는 것과 같은 자리다.
    이 단추는 프래그먼트 **밖**이라 누르면 판 전체가 저절로 다시 그려진다 —
    따로 다시 그리라고 시킬 필요가 없다.
    """
    if not st.session_state.get("j3_top7_open"):
        return
    st.button(
        "✕ 매수심사결과 높은 순위 9 닫기",
        key="close_j3_top7_open_above_search",
        on_click=_close_full_theme_rank,
    )


# 종목검색에서 고를 수 있는 자들. 맨 앞이 여태 쓰던 것이라 기본으로 둔다.
_SEARCH_RULER_DEFAULT = "테마 없는 대장주 (80점)"
_SEARCH_RULERS = (
    _SEARCH_RULER_DEFAULT,
    "테마 대장주",
    "상승장",
    "급락 후 반등장",
)


def _render_search_by_part(ruler: str, code: str, found_row: dict,
                           market: dict, ranking: dict) -> None:
    """고르신 파트의 **그 파트 배점표**로 검색 종목을 보여 준다.

    파트 배점은 그 파트의 **오늘 목록 안에서만** 잴 수 있다 — 순위·백분위가
    목록 안에서 매겨지기 때문이다. 그래서 오늘 그 그물에 안 걸린 종목은
    **없다고 적는다.** 딴 자로 재서 숫자를 만들어 내지 않는다(CLAUDE.md 0-1 바).
    """
    name = str(found_row.get("name") or code)
    if ruler == "상승장":
        with st.spinner(f"{name} — 상승장 배점으로 심사 중입니다…"):
            hit = _find_scan_row(j3data.breakout_scan(), code)
        if hit:
            _render_pullback_detail(hit, market, ranking, mode="breakout",
                                    panel="mystock")
            return
    elif ruler == "급락 후 반등장":
        with st.spinner(f"{name} — 급락 후 반등장 배점으로 심사 중입니다…"):
            hit = _find_scan_row(j3data.find_crash_rebound_stocks(), code)
        if hit:
            _render_pullback_detail(hit, market, ranking, mode="crash",
                                    panel="mystock")
            return
    elif ruler == "테마 대장주":
        # 그 종목이 든 테마를 **명부(US_THEMES)에서** 찾는다 — 그것이 원본이다.
        # 여러 테마에 들면 오늘 순위가 가장 높은 테마로 잰다.
        want = str(code).upper()
        mine = [str(theme.get("name") or "")
                for theme in getattr(j3data, "US_THEMES", ())
                if want in {str(t).upper() for t in (theme.get("stocks") or ())}]
        order = {str(item.get("name") or ""): index
                 for index, item in enumerate(ranking.get("rows") or [])}
        mine.sort(key=lambda title: order.get(title, 999))
        theme_name = mine[0] if mine else ""
        if theme_name:
            theme_row = next(
                (item for item in (ranking.get("rows") or [])
                 if str(item.get("name") or "") == theme_name),
                None,
            )
            with st.spinner(f"{theme_name} 대장주를 다시 세는 중입니다…"):
                leaders = j3data.get_theme_leaders(
                    theme_name, market_score=float(market.get("score") or 0),
                    theme_score=float((theme_row or {}).get("score") or 0),
                )
            hit = _find_scan_row(leaders, code)
            if hit:
                _render_stock_detail(
                    theme_row or {"name": theme_name}, hit, market, [hit],
                    "j3_search_part_choice", panel="mystock",
                )
                return
        else:
            st.warning(
                f"**{html.escape(name)}** 는 20개 테마 명부에 없는 종목이라 "
                f"테마 대장주 배점으로는 잴 수 없습니다. 위에서 다른 자를 "
                f"고르시거나 「테마 없는 대장주 (80점)」로 보십시오."
            )
            return
    st.warning(
        f"**{html.escape(name)}** 는 오늘 「{html.escape(str(ruler))}」 목록에 "
        f"없습니다. 그 파트의 배점은 그날 목록 안에서만 잴 수 있어서 "
        f"(순위·백분위가 목록 안에서 매겨집니다) 여기서는 배점표를 그리지 "
        f"않습니다. 위에서 다른 자를 고르십시오."
    )


def _render_my_stock_panel(market: dict, ranking: dict) -> None:
    """내 종목 현재상황 — 티커나 회사 이름을 치면 그 종목 상세가 열린다.

    한국테마(자비스4)와 같은 자리·같은 화면이다(2026-07-29 요청). 미국 종목이라
    티커·회사명은 영어지만, 널리 쓰는 한글 이름(엔비디아·애플…)도 받아 준다.
    """
    st.divider()
    st.markdown(
        # 제목을 보라색 그라데이션 띠로 — 순위 7(초록)·눌림목(파랑)과 나란히 구분된다
        # (2026-07-30 사용자 지시). 여기는 누를 곳이 아니라 제목이므로 단추가 아니다.
        "<div class='j3-band j3-band-purple'>종목검색 (검색종목 세부사항 보기)</div>", unsafe_allow_html=True)
    # **누를 단추를 둔다**(2026-08-21 상하님 지시 — "종목이름 치고 검색 누르는
    # 단추가 없다"). 글자만 치면 한 글자마다 화면을 다시 그려 느리기도 했다.
    # 칸 안에서 엔터를 쳐도 같이 눌린다.
    # 입력칸과 글자를 키운다(2026-08-21 상하님 지시).
    st.markdown(
        "<style>"
        "div[class*='st-key-j3_my_stock_query'] input{font-size:1.15rem !important;"
        " padding:.85rem .9rem !important; font-weight:700 !important;}"
        "div[class*='st-key-j3_my_stock_query'] label p{font-size:1.02rem !important;}"
        "</style>", unsafe_allow_html=True,
    )
    with st.form("j3_my_stock_form", clear_on_submit=False, border=False):
        typed = st.text_input(
            # 무엇을 어디에 넣어야 하는지 칸 이름이 직접 말하게 한다(2026-08-01 지시).
            "종목이름 또는 티커 (아래에 종목이름을 넣어보세요)", key="j3_my_stock_query",
            placeholder="예: 엔비디아, NVDA, apple, 팔란티어",
        )
        searched = st.form_submit_button("🔎 검색", type="primary")
    if searched:
        st.session_state["j3_my_stock_asked"] = str(typed or "").strip()
    query = str(st.session_state.get("j3_my_stock_asked") or "")
    if not query.strip():
        st.caption("종목 이름을 넣고 **🔎 검색**을 누르십시오.")
        return

    found = j3data.search_stocks(query)
    if not found.get("ok"):
        st.error(f"종목 목록 조회 실패: {_safe_error_text(found.get('error'))}")
        return
    rows = found.get("rows") or []
    if not rows:
        st.warning(f"‘{query}’와 비슷한 종목을 못 찾았습니다. 티커나 이름 일부만 쳐 보세요.")
        return

    options = [row["ticker"] for row in rows]
    by_ticker = {row["ticker"]: row for row in rows}
    chosen = st.radio(
        "찾은 종목",
        options,
        format_func=lambda t: f"{by_ticker[t]['name']} ({t})",
        horizontal=True,
        key="j3_my_stock_pick",
    )
    # **고른 종목이 바뀌면 차트가 저절로 열린다**(2026-08-21 상하님 지시).
    # 눌림목 표에서 종목을 누를 때와 같은 동작이다 — 거기서는 이미 그렇게 한다.
    # 열어 둔 뒤 상하님이 닫으시면 그대로 닫혀 있고, 다른 종목을 고르면 다시 열린다.
    if st.session_state.get("j3_my_stock_shown") != chosen:
        st.session_state["j3_my_stock_shown"] = chosen
        for opened in ("j3_detail_open_mystock", "j3_intraday_open_mystock",
                       "j3_bundle_open_mystock"):
            st.session_state[opened] = True
        back_nav.opened(st, "j3_detail_open_mystock",
                        "j3_intraday_open_mystock", "j3_bundle_open_mystock")
    # ── **어느 배점으로 볼지 고르신다** (2026-09-02 상하님 지시) ────────────────
    # 상하님 — "종목 검색에서 나오면 어디 배점을 기준으로 할 거냐고 물어보든지
    # 해야지."
    #
    # 종목검색은 **속한 파트가 없다.** 그래서 여태 대장주 배점을 말없이 썼는데,
    # 그것도 견줄 테마가 없어 상대강도 25점이 통째로 0인 반쪽(80점 만점)이었다.
    # 어느 자로 재는지 모르고 보시면 다른 파트 점수와 헛되이 견주시게 된다.
    #
    # **배점을 새로 만들지 않는다.** 파트별 배점은 그 파트의 오늘 목록 안에서만
    # 잴 수 있다(순위는 그 목록 안의 등수로 매기므로). 그래서 고른 파트의 오늘
    # 목록에 그 종목이 있으면 그 배점표로 보내고, 없으면 **없다고 적는다.**
    ruler = st.radio(
        "어느 배점으로 볼까요",
        _SEARCH_RULERS,
        horizontal=True,
        key="j3_my_stock_ruler",
        help="같은 종목이라도 파트가 다르면 점수가 다릅니다 — 견주시라고 나눠 둔 것입니다.",
    )
    if ruler != _SEARCH_RULER_DEFAULT:
        _render_search_by_part(ruler, chosen, by_ticker[chosen], market, ranking)
        return
    with st.spinner(f"{by_ticker[chosen]['name']} 심사 중입니다…"):
        result = j3data.analyze_one_stock(
            chosen, market_score=float(market.get("score") or 0))
    if not result.get("ok"):
        st.error(_safe_error_text(result.get("error")))
        return
    leader = result["row"]
    st.caption(
        "지금 자: **테마 없는 대장주 배점(80점 만점)** — 견줄 테마가 없어 "
        "테마 대비 상대강도 25점이 통째로 빠져 있습니다. "
        "위 테마 대장주 점수(100점 만점)와 나란히 비교하지 마세요. "
        "다른 자로 보시려면 위에서 고르십시오."
    )
    def _forget_search():
        """상세를 닫으면 「찾은 종목」 줄도 같이 걷는다 (2026-08-28 상하님 지시).

        상하님 — "종목 다 보고 닫기 했는데도 찾은 종목 화면이 그대로 있다."
        찾은 목록은 상세를 보려고 고르는 자리라, 상세를 닫으면 남아 있을 까닭이
        없다. 검색어는 그대로 둔다 — 다시 찾아보실 때 또 치지 않으시게.
        """
        st.session_state.pop("j3_my_stock_asked", None)
        st.session_state.pop("j3_my_stock_shown", None)

    _render_stock_detail(
        {"name": "내 종목"}, leader, market, [leader],
        "j3_my_stock_detail_choice", panel="mystock", on_close=_forget_search,
    )


def _us_signal_hint() -> str:
    """미국장 선행신호 카드 판정을 단타 참고 문구로 옮긴다(점수에는 반영하지 않는다).

    한국장 자비스4의 ‘기관 수급 반전’ 자리에 들어가는 미국판이다. 미국은 장중
    투자자별 수급 공개 자료가 없어 선물·반도체·변동성·금리 방향을 대신 쓴다.
    """
    result = st.session_state.get("us_signal_result")
    if result is None:
        return "미국장 시장 상태는 위 ‘미국장 시장 상태’ 카드에서 확인하세요."
    return (
        f"미국장 시장 상태: <b>{html.escape(str(result.verdict_label))}</b> · "
        f"{html.escape(str(result.headline))}"
    )


def _render_pullback_detail(row: dict, market: dict, ranking: dict,
                            *, mode: str | None = None,
                            panel: str = "pullback") -> None:
    """상단 테마 선택과 독립된 눌림목 종목 상세.

    자비스4(한국) 종목 상세와 같은 구성으로 맞춘다(2026-07-24 사용자 지시) —
    선정 근거 점수표 · 매수 심사 결과 · 일봉/주봉/월봉 차트를 함께 보여준다.

    mode를 넘기면 그 갈래의 자로 잰다. 안 넘기면 위 표에서 지금 보고 있는 갈래를
    쓴다. 순위 7에서 부를 때는 **줄에 적힌 갈래**를 넘겨야 한다(2026-08-06) —
    안 그러면 급락 종목을 상승장 자로 재는 일이 생긴다.
    """
    ticker = str(row.get("ticker") or "")
    # **열쇠에 이름표를 붙인다** (2026-09-02 상하님 화면 —
    # "There are multiple elements with the same key='btn_j3_detail_open_pullback'").
    # 저장해 둔 목록에서도 이 상세를 부르게 되면서, 위쪽 급락 구역이 열려 있으면
    # 같은 열쇠가 한 판에 두 번 생겨 터졌다. 이름표가 다르면 겹치지 않는다.
    # **기본값은 여태 쓰던 그 이름이라 다른 곳은 한 글자도 안 바뀐다.**
    detail_key = f"j3_detail_open_{panel}"
    danta_key = f"j3_danta_open_{panel}"
    # 종목을 누르면 화면이 여기로 내려온다(2026-08-09 상하님 지시).
    scroll_to.anchor(st, f"detail_{panel}")
    # 상세 한 벌을 통째로 눌러야 열리게 한다(2026-07-30 사용자 지시).
    if not _section_toggle(
        "🔎 선택종목 세부사항 보기", detail_key,
        close_label="선택종목 세부사항 닫기",
    ):
        return
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
    # 설명서 두 갈래는 **다른 자로 잰다**(2026-08-01 사용자 지시).
    # 기존 조건점수는 '신고가에 가까운가·이동평균 위인가'로 절반을 주는데, 낙폭 종목은
    # 그 조건을 정의상 하나도 못 맞춰 전부 14~26점 '제외'로 나왔다(실측). 찾아 놓고
    # 사지 말라는 화면이 되므로 갈래마다 전용 배점·전용 심사를 쓴다.
    mode = mode or st.session_state.get("j3_pullback_mode") or "기본"
    if mode == "crash":
        scored = j3data.crash_rebound_score(row)
        plan = j3data.crash_rebound_plan(row)
    elif mode == "breakout":
        scored = j3data.breakout_score(row)
        plan = j3data.breakout_plan(row)
    else:
        scored = None
    if scored is not None:
        review = {
            "score": scored["score"],
            "score_parts": [value for _n, value, _m, _t in scored["parts"]],
            "stock_reason": plan.get("buy_reason", ""),
            "plan": plan,
        }
        factor_names = [name for name, _v, _m, _t in scored["parts"]]
        factor_max = [maximum for _n, _v, maximum, _t in scored["parts"]]
        factor_notes = [note for _n, _v, _m, note in scored["parts"]]
        # 만점은 **모듈이 정한다.** 갈래마다 다르다(상승장 90점 · 급락 100점) —
        # 합격한 항목만 점수를 주고 남는 점수를 다른 항목에 나눠 주지 않기 때문이다
        # (CLAUDE.md 0-1 마). 화면에 100을 박아 두면 90점 만점 갈래가 낮아 보인다.
        score_max = float(scored.get("max") or 100.0)
    else:
        review = j3data.analyze_pullback_stock(
            row,
            benchmark_ret20=spy_ret20,
            market_score=market_score,
            theme_score=theme_score,
        )
        plan = review.get("plan") or {}
        # 만점은 모듈에서 읽어 온다 — 숫자를 여기 박아 두면 배점을 고칠 때
        # 표만 옛 숫자로 남는다(2026-08-12에 실제로 그래서 '31.1 (25)'가 나왔다).
        spec = list(getattr(j3data, "LEADER_SCORE_PARTS", ()))
        long_names = ["SPY 대비 상대강도", "52주 신고가 위치", "추세(20·50·200일선)",
                      "유동성(거래대금)", "변동성 안정"]
        # 검증 결과가 아니라 **무엇을 재는지**를 적는다 — 검증 결과는 위 배점표에
        # 이미 있고, 여기서 알아야 할 것은 '유동성이 뭔데'다(2026-08-12 상하님).
        note_map = getattr(j3data, "LEADER_SCORE_NOTES", {})
        notes = [note_map.get(name, "") for name, _p in spec]
        # **0점 항목도 남긴다**(2026-08-15 상하님 지시). 빼 버리면 앱이 무엇을
        # 봤는지 상하님이 못 보시고, 기준이 두 개뿐인 것처럼 보인다.
        keep = list(range(len(spec)))
        factor_names = [long_names[i] for i in keep]
        factor_max = [round(spec[i][1], 1) for i in keep]
        factor_notes = [notes[i] for i in keep]
        parts_all = list(review.get("score_parts") or [])
        review = {**review, "score_parts": [parts_all[i] for i in keep
                                            if i < len(parts_all)]}
        score_max = float(getattr(j3data, "LEADER_SCORE_MAX", 80.0)) or 100.0

    # 종목 이름·판정은 자비스4 종목 상세와 같은 형식으로 크게 보여준다.
    st.markdown(
        f"<div class='j3-stock-name'>{html.escape(str(row.get('name') or ticker))} · "
        f"{html.escape(ticker)}</div>"
        f"<div class='j3-stock-sub'>{html.escape(themes)} 눌림목 선택 종목 · "
        f"{html.escape(str(plan.get('recommendation') or '판정 없음'))}</div>",
        unsafe_allow_html=True,
    )
    if auth.is_guest():
        _render_day_price_row(metrics, ticker, panel=panel)
        # 당일 그림은 이제 아래 네 그림 판에 함께 들어간다(2026-08-28).
        _render_price_chart_bundle(ticker, panel=panel)
        _section_close(detail_key, "선택종목 세부사항 닫기")
        return
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
        # 금액만 보여주면 알 수가 없다는 지적(2026-08-06). 큰 회사는 늘 크기 때문이다.
        # **얼마나 늘었나**로 바꾼다. 미국은 외국인·기관 수급을 종가 뒤에도 공개하지
        # 않으므로(한국만 있는 제도), 돈이 몰리는지 볼 수 있는 값은 이것뿐이다.
        "<div class='j3-mc'><div class='j3-mc-label'>거래량 (어제 대비)</div>"
        f"<div class='j3-mc-val {_sign_class(metrics.get('volume_vs_prev'))}'>"
        f"{_pct(metrics.get('volume_vs_prev'))}</div>"
        "<div class='j3-mc-sub j3-muted'>지난 5일 평균 대비 "
        f"{_pct(metrics.get('volume_vs_week'))}</div></div>",
    ]
    if mode == "breakout":
        # US_SWING_V1은 중요 70·보조 30을 숨기지 않고 실제 등수·눌림과 나란히 둔다.
        # 등수는 selector가 적어 둔 값을 그대로 쓴다 — 화면이 다시 세지 않는다.
        total_ranked = row.get("rs_ranked_count")

        def _rank_text(key):
            rank = row.get(key)
            if not rank:
                return "—"
            return f"{int(rank)}등" + (f" / {int(total_ranked)}" if total_ranked else "")

        pullback_pct = row.get("pullback_pct_close")
        cells = [
            f"<div class='j3-mc'><div class='j3-mc-label'>현재가</div>"
            f"<div class='j3-mc-val'>{_price(metrics.get('current'))}</div></div>",
            f"<div class='j3-mc'><div class='j3-mc-label'>최근 3개월 등수</div>"
            f"<div class='j3-mc-val j3-green'>{_rank_text('rs60_rank')}</div>"
            "<div class='j3-mc-sub j3-muted'>나스닥보다 강한 차례</div></div>",
            f"<div class='j3-mc'><div class='j3-mc-label'>최근 6개월 등수</div>"
            f"<div class='j3-mc-val j3-green'>{_rank_text('rs120_rank')}</div>"
            "<div class='j3-mc-sub j3-muted'>나스닥보다 강한 차례</div></div>",
            f"<div class='j3-mc'><div class='j3-mc-label'>신고가 후 눌림</div>"
            f"<div class='j3-mc-val j3-up'>{'—' if pullback_pct is None else f'-{float(pullback_pct):.1f}%'}</div>"
            f"<div class='j3-mc-sub j3-muted'>최고가 넘고 {int(row.get('days_since_anchor') or 0)}거래일째</div></div>",
            f"<div class='j3-mc'><div class='j3-mc-label'>중요 점수</div>"
            f"<div class='j3-mc-val j3-green'>{float(row.get('core_score') or 0):.0f}/70</div></div>",
            f"<div class='j3-mc'><div class='j3-mc-label'>보조 점수</div>"
            f"<div class='j3-mc-val'>{float(row.get('support_score') or 0):.0f}/30</div>"
            "<div class='j3-mc-sub j3-muted'>추가검증 중</div></div>",
            f"<div class='j3-mc'><div class='j3-mc-label'>총점</div>"
            f"<div class='j3-mc-val j3-green'>{float(review.get('score') or 0):.0f}/100</div>"
            f"<div class='j3-mc-sub j3-muted'>{html.escape(str(row.get('status_text') or ''))}</div></div>",
        ]
    elif mode == "crash":
        # 점수는 **하나만** 둔다(2026-08-06 상하님 지적 "이 갈래 점수가 뭔말이냐").
        # 예전에는 한 화면에 셋('이 갈래 점수'·'눌림 점수'·위 표의 '종목 조건점수')이
        # 있었는데, 그중 '눌림 점수'는 이 화면에서 순위에 쓰지 않는 A 규칙 값이다.
        cells.append(
            f"<div class='j3-mc'><div class='j3-mc-label'>이 종목 점수</div>"
            f"<div class='j3-mc-val j3-green'>{float(review.get('score') or 0):.0f}점 "
            f"<span style='font-size:1rem; color:#9aa0aa'>/ {score_max:g}</span></div>"
            f"<div class='j3-mc-sub j3-muted'>{html.escape(str(plan.get('state') or ''))}"
            "</div></div>"
        )
    else:
        cells.extend([
            f"<div class='j3-mc'><div class='j3-mc-label'>종목 조건점수</div>"
            f"<div class='j3-mc-val j3-green'>{float(review.get('score') or 0):.1f}"
            f"/{score_max:g}</div>"
            f"<div class='j3-mc-sub j3-muted'>{html.escape(str(plan.get('state') or ''))}"
            "</div></div>",
            f"<div class='j3-mc'><div class='j3-mc-label'>눌림 점수</div>"
            f"<div class='j3-mc-val j3-green'>{float(quality.get('score') or 0):.1f}/100</div>"
            f"<div class='j3-mc-sub {_sign_class(quality.get('gap_pct'))}'>"
            f"20일선 이격 {_pct(quality.get('gap_pct'))}</div></div>",
        ])
    st.markdown(f"<div class='j3-metric-row'>{''.join(cells)}</div>", unsafe_allow_html=True)

    def _fac_cell(part, maximum):
        # 만점이 0인 줄은 숫자 대신 '0점'이라 적는다 — 왜 0점인지는 「설명」에 있다.
        shown = "0점" if not maximum else maximum
        return (
            "<td class='j3-fac-val'>"
            f"<span style='color:#ff5b5b; font-weight:800'>{_number(part)}</span> "
            f"<span style='color:#ff5b5b'>({shown})</span></td>"
        )

    # **심사 항목 칸에는 초록 이름만 둔다**(2026-08-21 상하님 지시 — 처음에는
    # "심사항목 밑에 하얀색 설명 빼라", 그다음 급락 표를 보시고 "초록색 제목만
    # 두고 나머지 흰색 내용 다 빼라"). 이름 옆에 붙던 값 줄까지 걷어냈다.
    #
    # **값을 버리지는 않는다.** 그 줄(하루 평균 3.7%씩 · 오늘 목록 58개 중 26등
    # 같은 것)은 제목 옆 「설명」 창으로 내린다. 없애 버리면 왜 이 점수인지가
    # 화면 어디에도 안 남는다(CLAUDE.md 0-1 마 — 버린 것은 「설명」에 남긴다).
    parts_values = review.get("score_parts") or []
    notes_padded = factor_notes + [""] * len(factor_names)
    factor_rows = "".join(
        f"<tr><td class='j3-fac-name'>{html.escape(name)}</td>"
        f"{_fac_cell(part, maximum)}</tr>"
        for name, part, maximum in zip(factor_names, parts_values, factor_max)
    )
    total_style = (
        "font-weight:800; font-size:1.1rem; background:rgba(134,255,203,0.12); "
        "border-top:4px double rgba(255,255,255,0.55)"
    )
    total_row = (
        f"<tr><td class='j3-fac-name' style='{total_style}'>총점</td>"
        f"<td class='j3-fac-val' style='{total_style}'>"
        f"<span style='color:#ff5b5b; font-weight:800'>{_number(review.get('score'))}</span> "
        f"<span style='color:#ff5b5b'>({score_max:g})</span></td></tr>"
    )
    # 시장·테마는 배점표 **위**에 둔다(2026-08-07). 차트 뒤 맨 아래 있던 것을
    # 올렸다 — 종목 점수를 보기 전에 어떤 시장·어떤 테마인지부터 알아야 한다.
    st.markdown("<div class='j3-section-title'>이 종목을 찾은 배경</div>",
                unsafe_allow_html=True)
    for column, (title, body) in zip(
        st.columns(2),
        _pullback_backdrop_cards(
            mode=mode, market=market, themes=themes, theme_score=theme_score,
            scored=scored, review=review, plan=plan, row=row,
        ),
    ):
        column.markdown(
            f"<div class='j3-reason-card'><div class='j3-reason-title'>{title}</div>"
            f"<div class='j3-reason-body'>{body}</div></div>",
            unsafe_allow_html=True,
        )
    st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)
    score_col, plan_col = st.columns([1, 1], gap="large")
    with score_col:
        # 앞말은 스카이블루 그대로, **괄호 안 갈래 이름만** 갈래 색으로 칠한다
        # (2026-08-14 상하님 지시). 순위 7의 '(미국형 5개 항목)'은 갈래가 아니라
        # 색을 안 준다 — 초록이면 상승장, 주황이면 급락이라는 약속이 흐려진다.
        tag, tone = (
            ("(급락 반등 전용 배점)", "j3-title-tag j3-title-crash") if mode == "crash"
            else ("(신고가 눌림 전용 배점)", "j3-title-tag j3-title-breakout")
            if mode == "breakout" else ("(미국형 5개 항목)", "")
        )
        st.markdown(
            "<div class='j3-section-title'>종목 선정 근거 "
            + (f"<span class='{tone}'>{tag}</span>" if tone else tag)
            + "</div>",
            unsafe_allow_html=True,
        )
        # '설명'은 **제목 칸 「심사 항목」 옆**에 하나만 둔다(2026-08-14 상하님 지시).
        # 갈래마다 열쇠를 갈라 둔다 — 상승장 상세와 급락 상세가 서로를 덮어쓰지 않게.
        factor_html = (
            _swing_factor_table_html(
                factor_rows, total_row, row.get("explanations") or {},
                f"j3_factor_help_{panel}_breakout",
            )
            if mode == "breakout" else
            _factor_table_html(
                factor_rows, total_row, factor_names,
                f"j3_factor_help_pullback_{mode}",
                notes=notes_padded[:len(factor_names)],
            )
        )
        st.markdown(factor_html, unsafe_allow_html=True)
        st.markdown(
            f"<div class='j3-reason-mustard'>{_mustard_html(review.get('stock_reason'))}</div>",
            unsafe_allow_html=True,
        )
        # 갈래 화면에는 여기에 아무 말도 붙이지 않는다(2026-08-07 상하님 지시
        # "중요하지 않으면 빼라"). 예전에는 "표 위 '이 화면 설명 보기'에 있습니다"라고
        # 적어 뒀는데, 이 상세는 **순위 7에서도 열려** 거기에는 그 단추가 없었다.
        # 없는 것을 가리키느니 빼는 게 낫다 — 배점표는 표 위 설명 구역에 그대로 있고,
        # 무슨 항목에 몇 점인지는 바로 위 '종목 선정 근거' 표가 이미 다 보여준다.
        if mode not in ("crash", "breakout"):
            st.caption(
                "이 점수는 위 표의 ‘종목 조건점수’와 같은 값이며, 표의 순위를 정하는 ‘눌림 점수’와는 "
                "다른 것을 잽니다 — 눌림 점수는 지금이 눌림 자리로 좋은지, 이 점수는 종목 자체가 "
                "좋은지를 봅니다. 상대강도 기준은 테마 ETF가 아니라 SPY 20일 수익률입니다"
                "(눌림목 검색은 여러 테마를 가로질러 돌기 때문). 그래서 위 테마 대장주 표의 점수와도 "
                "다를 수 있습니다."
            )
    with plan_col:
        st.markdown("<div class='j3-section-title'>매수 심사 결과</div>", unsafe_allow_html=True)
        # 점수·상태만 있고 '뭘 하라는 건지'가 없다는 지적(2026-07-30). 판정을 사람
        # 말로 다시 쓴 한 줄을 표 위에 얹는다 — 새 판정을 만들지는 않는다.
        st.markdown(
            guidance.html(
                guidance.build(plan, money=_price, market_score=market.get("score")),
                css_class="j3-guide",
            ),
            unsafe_allow_html=True,
        )
        if mode == "breakout":
            anchor = row.get("anchor_date") or "—"
            pullback = row.get("pullback_pct_close")
            pullback_text = "—" if pullback is None else f"{float(pullback):.1f}%"
            # **두 값이 한 칸에 들어가는 자리는 색으로 가른다**(2026-08-21 상하님
            # 지적 — "26년8.19 / 1거래일 숫자 구분이 안 되어 있다"). 앞뒤 색을
            # 다르게 주고 가운데 빗금은 흐리게 둬서 어디까지가 앞값인지 보이게 한다.
            def _pair(left, left_color, right, right_color, right_words=False):
                right_class = " class='j3-holo-words'" if right_words else ""
                return (f"<span style='color:{left_color}'>{left}</span>"
                        "<span style='color:#6f757e; font-weight:600'> / </span>"
                        f"<span{right_class} style='color:{right_color}'>{right}</span>")

            plan_cells = [
                ("진입 관찰",
                 f"<span class='j3-holo-words'>"
                 f"{html.escape(str(plan.get('entry') or '—'))}</span>",
                 "#44f0a1"),
                ("최고가 넘은 날 / 그 뒤",
                 _pair(anchor, "#9dccff",
                       f"{int(row.get('days_since_anchor') or 0)}거래일째", "#44f0a1",
                       right_words=True),
                 "#e6e6e6"),
                ("중요 / 보조 점수",
                 _pair(f"{float(row.get('core_score') or 0):.0f}/70", "#44f0a1",
                       f"{float(row.get('support_score') or 0):.0f}/30", "#ffb020"),
                 "#e6e6e6"),
                ("눌림 / 손절",
                 _pair(pullback_text, "#ffd23f", "앱이 안 정함", "#9aa0aa",
                       right_words=True),
                 "#ffd23f"),
            ]
        elif mode == "crash":
            # 이 규칙에는 넘어야 할 기준가도 손절도 없다. 없는 것을 있는 것처럼
            # 적지 않고, 규칙이 실제로 정한 것을 적는다.
            # **파는 시점은 앱이 정하지 않는다**(2026-08-12 상하님 확정).
            # 자리 하나에 3개월·6개월·1년 과거 성적을 나란히 놓고, 고르는 것은
            # 상하님이 하신다. 상하님 표 1·2가 원래 그 모양이다.
            spans = " · ".join(
                f"{item['label']} {item['median_return']:+.1f}%"
                for item in (plan.get("hold_results") or ())
            )
            # 네 칸 다 **숫자가 아니라 말**이다. 1.5rem으로 그리면 "다음 거 래일
            # 시 가"처럼 한 글자씩 줄바꿈된다(2026-08-21 상하님 지적). 상승장
            # 카드와 같은 j3-holo-words(1.05rem)로 맞춘다.
            def _words(text):
                return f"<span class='j3-holo-words'>{html.escape(str(text))}</span>"

            plan_cells = [
                ("사는 때", _words(plan.get("entry") or "—"), "#44f0a1"),
                ("파는 때", _words("규칙에 없음"), "#ffd23f"),
                ("이 자리 과거 성적", _words(spans or "—"), "#e6e6e6"),
                ("손절가", _words("이 규칙에는 없음"), "#ff5b5b"),
            ]
        elif plan.get("trigger") is not None:
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
        # 라벨과 만점을 갈래에 맞춘다 — 급락·상승은 그 갈래 배점(둘 다 100점),
        # 미국형 5개 항목은 대장주 조건점수(80점)다. 숫자는 모듈에서 읽는다.
        score_label = ("이 종목 점수" if mode in ("crash", "breakout")
                       else "종목 조건점수")
        score_box = (
            "<div class='j3-holo-cell j3-holo-score'>"
            f"<div class='label'>{score_label}</div>"
            f"<div class='val'>{float(review.get('score') or 0):.1f}/{score_max:g}</div>"
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
        if mode in ("crash", "breakout"):
            # 여기 있던 ※ 두 줄은 뺐다(2026-08-06 상하님 지적 "반복되는 내용 없애라").
            # 첫 줄은 바로 위 카드의 '손절가 — 이 규칙에는 없음'이 이미 말하고,
            # 둘째 줄은 왼쪽 점수표 아래 설명과 같은 말이었다.
            pass
        else:
            st.markdown(
                "<div class='j3-plan-note'>※ <b>가격 칸이 채워지는 기준</b> — ‘돌파 확인’이나 ‘눌림목 대기’처럼 "
                "<b>가격 셋업이 완성된 종목만</b> 확정 기준가·손절가·목표가가 나옵니다. "
                "‘관찰’·‘제외’·‘추격 금지’는 아직 살 자리가 없다는 뜻이라 참고가로만 채웁니다.<br>"
                f"※ <b>‘{plan.get('state', '')}’(가격 상태)와 ‘{plan.get('recommendation', '')}’(최종 판정)은 "
                "다른 말</b>입니다 — 가격 셋업이 완성돼도 시장·테마 점수가 기준 미달이면 최종 판정은 매수가 "
                f"아닙니다(이 종목의 테마 점수 {theme_score:.1f}/100 · 시장 {market_score:.0f}/100).</div>",
                unsafe_allow_html=True,
            )
        # 단타 참고 신호는 접어 둔다 — 점수·판정에 안 쓰는 참고값인데 늘 펴 놓으니
        # 화면이 길어졌다(2026-08-06 상하님 지적).
        if _section_toggle(
            "⚡ 단타 참고 신호 보기", danta_key,
            close_label="단타 참고 신호 닫기",
        ):
            st.markdown(
                f"<div class='j3-danta-box'>{_us_signal_hint()}<br>"
                "<span class='j3-muted'>선행신호가 위험선호로 바뀌고 기준가를 넘으면 장중 진입 신호로 "
                "참고합니다 (점수·판정에는 반영하지 않습니다). 미국은 투자자별 수급을 "
                "<b>종가 뒤에도 공개하지 않아</b> 한국장의 ‘기관 수급 반전’ 대신 "
                "선물·반도체·변동성·금리 방향을 씁니다.</span></div>",
                unsafe_allow_html=True,
            )
        # 갈래 화면에서는 이 상자를 뺀다 — 왼쪽 점수표 아래 겨자색 상자와 **똑같은
        # 문장**이었다(2026-08-06 상하님 캡처).
        if mode not in ("crash", "breakout"):
            st.write("")
            if plan.get("recommendation") == "조건부 후보":
                st.success(plan.get("buy_reason"))
            elif plan.get("state") == "추격 금지":
                st.error(plan.get("buy_reason"))
            else:
                st.warning(plan.get("buy_reason"))

    st.caption(
        "이 선택은 위의 테마·대장주 선택을 바꾸지 않습니다. 종목 이름을 다시 누르면 "
        "이 상세와 당일·일봉·주봉·월봉 차트만 즉시 교체됩니다."
    )
    _render_day_price_row(metrics, ticker, panel=panel)
    _render_price_chart_bundle(ticker, panel=panel)

    # 이 상세 한 벌의 맨 끝 — 여기서 바로 접을 수 있게 한다(2026-08-01 사용자 지시).
    _section_close(detail_key, "선택종목 세부사항 닫기")


def _pullback_backdrop_cards(
    *, mode: str, market: dict, themes: str, theme_score: float,
    scored: dict | None, review: dict, plan: dict, row: dict | None = None,
) -> list[tuple[str, str]]:
    """상세 맨 위에 놓을 '시장 · 테마' 두 칸을 만든다.

    **왜 넷에서 둘로 줄였나(2026-08-07 상하님 물음 "이게 여기 있는 게 맞나").**
    예전에는 시장·테마·종목·매수 네 칸이 차트 뒤 맨 아래 있었는데,
      * '종목' 칸은 바로 위 배점표를 소리 내어 다시 읽는 것이었고,
      * '매수' 칸은 매수 심사 카드·지금 할 일 상자·겨자색 상자에 이어 **네 번째**로
        같은 말을 했다.
    남은 시장·테마 둘만 이 상세에서 처음 나오는 이야기다. 그래서 둘만 남기고,
    자리도 배점표 **위로** 올린다 — 시장 → 테마 → 종목 순으로 읽어야 배점이
    무슨 뜻인지 알고 볼 수 있다.
    """

    def _red(text) -> str:
        """하락폭은 붉은색 진하게(2026-08-06 사용자 지시) — 눈에 먼저 들어와야 한다."""
        return (f"<span style='color:#ff5b5b; font-weight:900'>"
                f"{html.escape(str(text))}</span>")

    if mode in ("crash", "breakout"):
        # 이 두 갈래는 **다른 자로 잰다**. 그런데 예전에는 네 칸 중 '시장 근거'가
        # 눌림목(A 규칙)의 조건점수를, '종목 근거'와 '매수 근거'가 **똑같은 문장**을
        # 보여줬다(2026-08-06 상하님 캡처). 셋 다 이 갈래의 값으로 바꾼다.
        if mode == "crash":
            # **기준일로 찾아 놓고 오늘 낙폭으로 판정하면 앞뒤가 안 맞는다**
            # (2026-08-06 상하님 지적). 표는 7/29(-11.5%) 기준으로 찾아 놓고
            # 이 칸만 "오늘 -4.1%라 쓸 자리가 아닙니다"라고 말하고 있었다.
            # 표와 **같은 기준일**로 말한다.
            reference = j3data.crash_reference_day()
            if reference.get("armed"):
                ref_day = html.escape(str(reference.get("reference_date") or ""))
                ref_drop = _red(f"{float(reference.get('reference_drop') or 0):.1f}%")
                now_drop = _red(f"{float(reference.get('today_drop') or 0):.1f}%")
                market_body = (
                    f"{ref_day} 기준으로 찾았습니다 — 그날 나스닥이 고점에서 "
                    f"{ref_drop}였습니다. 오늘은 {now_drop}입니다."
                )
            else:
                # 기준일이 없으면 오늘 낙폭으로 찾은 것이다. 그 사실을 그대로 적는다.
                state = j3data.crash_market_state()
                drop_pct = state.get("drop_pct")
                if drop_pct is None:
                    market_body = html.escape(
                        str(state.get("reason") or "나스닥 상태를 못 읽었습니다"))
                else:
                    low, high = getattr(j3data, "CRASH_MARKET_BAND", (-12.0, -6.0))
                    band = _red(f"{abs(high):.0f}~{abs(low):.0f}%")
                    market_body = (
                        f"최근 한 달에 나스닥이 {band} 내려온 날이 없었습니다. "
                        f"지금은 {_red(f'{float(drop_pct):.1f}%')}입니다. "
                        "그래서 오늘 낙폭으로 찾은 결과입니다."
                    )
        else:
            # 목록을 계산한 같은 EOD snapshot을 쓴다. 상세을 열 때 시장을 재조회하면
            # 목록의 Gate와 상세 설명이 서로 다른 시각을 말할 수 있다.
            state = row or {}
            market_body = html.escape(
                str(
                    (state.get("explanations") or {}).get("market", {}).get("one_line_explanation")
                    or state.get("status_text")
                    or "나스닥 시장 Gate 상태를 확인합니다."
                )
            )
            market_body += (
                "<div class='j3-reason-sub'>"
                f"지금 <b>{html.escape(us_swing.plain_state(state.get('market_status')) or '자료부족')}</b>"
                " · 나스닥이 이 상태일 때만 새로 살 후보를 냅니다.</div>"
            )
    else:
        market_body = f"{market.get('regime', '자료부족')} · {market.get('score', 0)}/100"
    # 여기 담기는 글은 **이미 안전하게 만들어 둔 것**이다(붉은 숫자 span이 들어간다).
    # 그래서 아래에서 다시 escape하지 않는다 — 새 글을 넣을 때는 html.escape를
    # 거쳐서 넣어야 한다.
    # 여기 70.7/100만 적어 뒀더니 왼쪽 배점표의 테마 40점과 어긋나 보였다
    # (2026-08-07 상하님 지적 "이거 맞냐"). 둘 다 맞는 값인데 **자가 다르다** —
    # 이쪽은 위 테마 순위표가 테마 자체를 100점으로 잰 값이고, 저쪽은 이 종목의
    # 급락 배점 100점 중 테마 몫이다. 그 사실을 카드에 적어 둔다.
    # (옛 문구를 주석에 그대로 옮겨 적지 않는다 — '그 말이 화면에 남아 있나' 보는
    #  시험이 주석을 먼저 집는다. 2026-08-07 실제로 걸렸다.)
    if mode == "breakout":
        swing_row = row or {}
        theme_percentile = swing_row.get("theme_percentile")
        breadth = swing_row.get("breadth_pct")
        theme_body = html.escape(
            f"{swing_row.get('theme_id') or themes} · 테마 보조점수 "
            f"{float(swing_row.get('theme_score') or 0):.0f}/10"
        )
        theme_body += (
            "<div class='j3-reason-sub'>대상 종목을 뺀 다른 구성종목으로 계산 · "
            f"테마 등수 상위 {'—' if theme_percentile is None else f'{max(0.0, 100.0 - float(theme_percentile)):.0f}%'}"
            f" · 50일선 위 {'—' if breadth is None else f'{float(breadth):.1f}%'}"
            "</div>"
        )
    else:
        theme_body = (
            html.escape(f"{themes} · 테마 자체 점수 {theme_score:.1f}/100")
        # 여기에 배점 항목 이름이나 점수를 **적지 않는다.** 적어 두면 배점을 고칠 때마다
        # 이 줄이 조용히 옛말을 하게 된다(2026-08-14에 실제로 그랬다 — 배점에서
        # 사라진 항목을 이 줄이 계속 가리키고 있었다).
            + "<div class='j3-reason-sub'>위 <b>테마 순위표</b>가 이 테마를 100점으로 잰 "
          "값입니다. 왼쪽 배점표의 <b>테마 점수</b>와는 <b>다른 자</b>입니다.</div>"
        )
    return [("시장 상황", market_body), ("테마 상황", theme_body)]


# 낙폭 두 갈래의 색 (2026-08-01 사용자 지시: "-30~-40과 -40~-50 색깔 구분하고").
# 설명 카드와 표의 같은 갈래가 같은 색이라 카드를 보고 표에서 그 줄을 바로 찾는다.
# 갈래 이름은 2026-08-06에 바뀌었다 — 옛 deep/mid(-40~-50 / -30~-40)에서
# shallow/deep(-20~-30 / -30~-50)으로. 옛 이름도 남겨 둬야 저장해 둔 기록이 안 깨진다.
_BAND_CARD_CLASS = {"shallow": "j3-card-mid", "deep": "j3-card-deep", "mid": "j3-card-mid"}
_BAND_CELL_CLASS = {"shallow": "j3-band-mid", "deep": "j3-band-deep", "mid": "j3-band-mid"}

# 배점표 — 화면에 그대로 뿌린다(2026-08-06 사용자 지시 "기준을 세부적으로 화면에").
#
# **숫자는 여기 적지 않고 jarvis3_data에서 읽는다** (2026-08-09에 고쳤다).
# 그전에는 숫자를 여기 박아 뒀는데, 2026-08-07에 급락 배점을 다시 재면서
# 모듈만 고치고 이 표를 안 고쳐 **화면이 두 날 동안 옛 배점을 설명했다**
# (화면 '같은 테마 동반 40점' · 실제 30점, '테마 등수' 줄은 아예 없었다).
# 이제 모듈의 값을 그대로 읽으므로 다시는 어긋나지 않는다.
# 0점 항목도 지우지 않고 남긴다 — 왜 뺐는지 모르면 나중에 다시 넣게 된다.
#
# (이름, 배점 열쇠 또는 None, 왜) — 열쇠가 None이면 배점에 아예 없는 항목이라 0점이다.
_SCORE_TABLE = {
    "crash": (
        ("이 종목이 평소 크게 움직이나", "volatility",
         "<b>무엇을 보나</b> — 이 회사 주가가 <b>최근 3개월 동안 하루에 몇 %씩 "
         "움직였는지</b> 봅니다. 오늘 목록에 오른 종목끼리 줄을 세워 "
         "<b>위쪽 절반</b>에 들면 점수를 줍니다.<br>"
         "<b>왜 보나</b> — 평소 크게 출렁이던 종목이 바닥에서도 크게 튑니다. "
         "얌전한 종목은 올라올 때도 얌전하게 올라옵니다.<br>"
         "<b>과거에 어땠나</b> — 나스닥이 바닥을 찍고 돌아선 날 아홉 번 중 "
         "<b>3개월로 보면 아홉 번 다</b>, 1년으로 봐도 <b>여덟 번 다</b> 이렇게 고른 "
         "쪽이 나머지보다 더 벌었습니다. 네 항목 중 가장 꾸준합니다.<br>"
         "<b>주의</b> — 바닥이 <u>아홉 번뿐</u>입니다. 확실한 숫자가 아닙니다"),
        ("이 테마가 이미 오름세로 돌아섰나", "above150",
         "<b>무엇을 보나</b> — 그 분야에 속한 회사들 중 <b>몇 %가 30주선 위에 "
         "있는지</b> 세어, 분야 20개를 줄 세웁니다. <b>위에서 3등 안</b>이면 "
         "점수를 줍니다.<br>"
         "<b>30주선이란</b> 최근 30주(약 150거래일) 평균값을 이어 그린 선입니다. "
         "주가가 그 위에 있으면 <u>반년 평균보다 지금이 비싸다</u>는 뜻입니다.<br>"
         "<b>왜 보나</b> — 스탠 와인스타인은 1988년에 주가가 바닥을 다지고 "
         "<b>30주선 위로 올라설 때가 오름세의 시작</b>이라고 했습니다. 급락 후 "
         "반등이 바로 그 자리입니다.<br>"
         "<b>과거에 어땠나</b> — 바닥에서 <b>1년으로 보면 일곱 번 중 일곱 번</b> "
         "다 이겼습니다. 3개월은 여덟 번 중 일곱 번입니다.<br>"
         "<b>왜 3등까지만인가</b> — 5등까지 넓혀 보니 무너졌습니다"),
        ("이 테마가 통째로 떨어졌나", "together",
         "<b>무엇을 보나</b> — 이 회사와 <b>같은 분야 회사가 네 개 이상</b> 이 목록에 "
         "같이 올라왔으면 점수를 줍니다. 한두 개만 떨어졌으면 그 회사 사정이고, "
         "네 개가 같이 떨어졌으면 <b>그 분야가 통째로 밀린 것</b>입니다. 분야째 "
         "밀린 것은 돌아올 때도 분야째 돌아옵니다.<br>"
         "<b>과거에 어땠나</b> — <b>3개월로 보면 아홉 번 다</b> 이겼는데, "
         "6개월·1년으로 길게 보면 여덟 번 중 여섯 번으로 약해집니다. 그래서 "
         "20점입니다.<br>"
         "<b>주의</b> — 바닥이 <u>아홉 번뿐</u>입니다. 확실한 숫자가 아닙니다"),
        ("이 테마가 지난 반년에 많이 올랐나", "theme_ret120",
         "<b>무엇을 보나</b> — 그 분야 회사들이 <b>최근 반년에 평균 몇 % 올랐는지</b>로 "
         "분야 20개를 줄 세워, <b>위에서 3등 안</b>이면 점수를 줍니다.<br>"
         "<b>과거에 어땠나</b> — <b>1년으로 보면 여섯 번 중 여섯 번</b>으로 네 항목 중 "
         "가장 잘 맞혔습니다. 그런데 <b>3개월로 보면 일곱 번 중 네 번</b>뿐입니다. "
         "짧게 보면 잘 안 맞아서 10점만 줍니다.<br>"
         "<b>주의</b> — 바닥이 <u>여덟 번뿐</u>입니다. 확실한 숫자가 아닙니다"),
        ("고점 대비 낙폭", "bucket",
         "<u>점수를 주지 않습니다.</u> 이 목록에 올릴 때 <b>이미 쓴 값</b>입니다 — "
         "1년 최고가보다 20~50% 내려온 종목만 올리고 있습니다. 그 안에서 더 많이 "
         "떨어진 쪽에 또 점수를 주면 한 가지를 두 번 세는 셈입니다.<br>"
         "<b>게다가 겹칩니다</b> — 많이 떨어진 종목의 <b>71%</b>가 위 "
         "<b>주가 변동성</b> 항목에도 걸립니다. 거의 같은 종목입니다.<br>"
         "대신 낙폭 칸마다 과거 성적을 따로 보여 드립니다"),
        ("테마가 20일선 위에 있나", "above20",
         "<u>점수를 주지 않습니다 — 반대였습니다.</u> 20일선 위에 있던 종목이 1년 뒤 "
         "오히려 <b>23% 덜 올랐습니다</b>. 나스닥이 바닥을 찍고 돌아선 날 아홉 번 중 "
         "네 번밖에 못 맞혔습니다.<br>"
         "<b>주가 변동성이 비슷한 종목끼리만 모아서 다시 봐도 같았습니다</b> — "
         "20일선 위는 1년 뒤 53% 올랐고 아래는 76% 올랐습니다.<br>"
         "<b>왜 그런가</b> — 20일선은 한 달짜리라 급락 뒤에는 며칠 반등만으로도 "
         "금세 넘어섭니다. 그래서 앱은 이것을 <b>점수가 같을 때 순서를 가르는 데만</b> "
         "씁니다"),
        (f"위 「{_THEME_COUNT}개 테마 실시간 순위」", "theme_rank",
         "<u>점수를 주지 않습니다.</u> 그 순위 위쪽 테마의 종목을 사면 어땠는지 "
         "재 봤더니, 3개월과 1년은 맞는데 <b>6개월에 일곱 번 중 세 번</b>으로 "
         "무너집니다.<br>"
         "<b>왜 그런가</b> — 그 순위 점수 안에 <b>20일선 위 비율이 40점</b>으로 가장 "
         "크게 들어 있습니다. 그런데 바로 위에서 보셨듯 급락 뒤 20일선은 거꾸로입니다. "
         "그래서 이 자리에서는 구조적으로 맞지 않습니다.<br>"
         "<b>그 순위표는 상승장 기준입니다</b> — 급락 목록을 고르실 때 그대로 "
         "따라가시면 안 됩니다"),
        ("테마가 덜 빠졌나", "less_drop",
         "<u>2026-08-14에 뺐습니다.</u> 제가 잰 자리가 틀렸었습니다 — 나스닥이 "
         "조금이라도 빠진 날을 <b>전부</b> 넣고 쟀는데, 그 대부분은 "
         "<b>아직 더 떨어지는 중인 날</b>이었습니다. 떨어지는 중에는 덜 빠진 분야가 "
         "덜 손해 보는 것이 당연합니다.<br>"
         "실제로 사시는 자리에서 다시 재니 <b>100번 중 36번</b>이었습니다 — "
         "거꾸로였습니다"),
        ("테마 주봉이 오름세인가", "aligned",
         "<u>2026-08-14에 뺐습니다.</u> 이 잣대로 보려면 종가가 50일선 위 · "
         "50일선이 150일선 위 · 150일선이 200일선 위 · 200일선까지 오르는 중, "
         "이 넷을 다 맞춰야 합니다. <b>상승이 한창일 때의 모습</b>입니다.<br>"
         "<b>급락 직후에는 그 조건을 맞추는 분야가 거의 없습니다</b> — 잴 수 있는 "
         "사건이 한두 번뿐이었습니다. 위 30주선 하나가 훨씬 느슨해서 그 자리를 "
         "잡습니다"),
        ("테마가 같이 오르는가", "spread5",
         "<u>2026-08-12에 뺐습니다</u> — 이걸로 고른 종목은 20% 오르는 데 "
         "<b>46일</b> 걸려 아무거나 산 것(45일)보다 <b>느렸습니다</b>"),
        ("대형기술주 감점 · 여행 분야 감점", None,
         "<u>넣지 않았습니다.</u> 2026-08-19에 상하님이 주신 지시문에 있던 것인데, "
         "앱 명부로 재 보니 대형기술주 여섯 개는 <b>오히려 1년 뒤 6.6% 더 올랐고</b> "
         "걸린 경우도 29번뿐이라 가를 수 없었습니다. 여행 분야는 앱 테마 20개에 "
         "<b>그 이름이 아예 없습니다</b>"),
        ("거래대금 · 사고팔기 쉬운가", "liquidity",
         "세 보유기간 전부 미달이었습니다"),
    ),
}

_SCORE_WEIGHT_SOURCE = {
    "breakout": "BREAKOUT_SCORE_WEIGHTS",
    "crash": "CRASH_SCORE_WEIGHTS",
}

# 배점표 맨 위 **한 줄 요약** (2026-08-12 상하님 지시 — "쉽게 알아먹게 한 줄 넣어라").
# 아래 표를 안 읽어도 이 한 줄이면 무엇으로 순위를 매기는지 알 수 있어야 한다.
_SCORE_TABLE_PLAIN = {
    "crash": ("<b>쉽게 말해</b> — 크게 빠진 종목 중에서 <b>평소 크게 출렁이던 종목</b>과 "
              "<b>그 종목이 속한 분야가 이미 몸을 일으킨 종목</b>을 위로 올립니다. "
              "<b>40점이 그 종목의 출렁임</b>, <b>60점이 분야</b>, 더해서 100점입니다.<br>"
              "<b>2026-08-19에 새로 짰습니다.</b> 그전에는 셋 다 분야만 봤는데, 상하님이 "
              "주신 지시문의 <b>주가 변동성</b>을 앱 명부로 재 보니 넷 중 가장 꾸준했습니다. "
              "이 자리에서 <b>종목 자체를 보는 항목이 점수를 받은 것은 처음</b>입니다.<br>"
              "<b>위 테마 순위표 점수는 상승장 기준입니다</b> — 이 자리에서는 6개월에 무너집니다. "
              "순위표 위쪽을 그대로 고르시면 안 됩니다.<br>"
              "<b>0점은 나쁜 종목이라는 뜻이 아닙니다</b> — 점수는 <b>먼저 볼 순서</b>를 "
              "정할 뿐이고, 0점도 조건에 걸려 올라온 종목입니다. 같은 점수는 분야를 "
              "번갈아 놓습니다."),
}


def _score_table_rows(mode: str):
    """(이름, 점수, 왜) — 점수는 **모듈에서 읽는다**(위 설명 참고)."""
    weights = getattr(j3data, _SCORE_WEIGHT_SOURCE.get(mode, ""), {}) or {}
    for name, key, why in _SCORE_TABLE.get(mode, ()):
        points = float(weights.get(key) or 0) if key else 0.0
        # 47.0처럼 소수 첫 자리가 0이면 정수로 적는다 — 화면이 지저분해진다.
        text = f"{points:.0f}" if abs(points - round(points)) < 0.05 else f"{points:.1f}"
        yield name, points, text, why


def _score_table_html(mode: str, base_win_rate=None) -> str:
    """배점표를 화면에 뿌린다. **점수를 주는 항목만** 적는다.

    2026-08-15에 상하님이 "0점짜리도 표시하고 점수 미달인 이유 넣고"라고 하셔서
    재 보고 버린 항목까지 다 적어 두었다. **2026-08-21에 상하님이 빼라고 하셨다** —
    급락 배점표의 열한 줄 중 일곱이 0점이라 표가 그 일곱에 묻혔다.

    버린 항목이 무엇이었는지는 `docs/US_THEME_SPEC.md` 3-3에 그대로 남아 있다.
    되살리려면 아래 한 줄(points를 거르는 곳)만 지우면 된다.
    """
    lines = "".join(
        f"<div class='j3-weight'>"
        f"<b>{name}</b><span class='j3-w-pt'>{text}점</span>"
        f"<span class='j3-w-why'>{why}</span></div>"
        for name, points, text, why in _score_table_rows(mode)
        if points
    )
    base = (
        f" 기준은 <b>그날 아무 종목이나</b> 샀을 때 100번 중 {base_win_rate:.0f}번입니다."
        if base_win_rate else ""
    )
    plain = _SCORE_TABLE_PLAIN.get(mode, "")
    head = (f"<div class='j3-pull-guide' style='padding-bottom:.15rem'>{plain}</div>"
            if plain else "")
    return (
        f"{head}"
        "<div class='j3-pull-guide'><b>점수를 매기는 기준</b>(2026-08-12에 다시 쟀습니다) — "
        "2년·3년·4년 창을 한 달씩 밀어 가며 재고, <u>어느 창에서나</u> 이겨야 점수를 "
        "줍니다. 한 시기에서만 통한 값은 그 시기에만 맞는 자리를 1등으로 올립니다."
        f"{base}</div>"
        f"<div class='j3-pull-guide' style='padding-top:.2rem'>{lines}</div>"
    )


# 명부 이름도 화면에는 사람 말로 적는다(2026-08-20 상하님 지시).
_UNIVERSE_TEXT = {
    "LEGACY_RESEARCH_200": "미국 대형주 200",
    "LIVE_NASDAQ_COMMON": "나스닥 보통주 전체",
    "PIT_NASDAQ_TOP200": "그때그때 나스닥 200",
}


# 관찰 목록에 펴 두는 줄 수. **20개는 너무 많다**(2026-08-21 상하님 지시).
_SWING_WATCH_ROWS = 15

# 「등급 / 상태」 칸의 색. **종류별로 갈라 놓는다**(2026-08-21 상하님 지시).
#   초록 — 통과했다 · 주황 — 거의 다 왔다 · 하늘 — 오늘 막 넘었다
#   붉음 — 이 자리가 아니다 · 보라 — 아직 최고가를 못 넘었다 · 회색 — 힘이 모자라다
_SWING_STATUS_TONE = {
    "PRIMARY_CANDIDATE": "#22c55e",
    "PULLBACK_WAIT": "#ffb020",
    "ENTRY_WINDOW_NOT_STARTED": "#9dccff",
    "TOO_DEEP": "#ff5b5b",
    "MARKET_BLOCKED": "#ff5b5b",
    "BREAKOUT_WAIT": "#b98cff",
    "ENTRY_WINDOW_EXPIRED": "#8a8f98",
    "RS60_WEAK": "#9aa0aa",
    "RS120_WEAK": "#9aa0aa",
    "RS_BOTH_WEAK": "#6f757e",
    "INSUFFICIENT_DATA": "#6f757e",
}
_SWING_GRADE_TONE = {"S": "#22c55e", "A": "#44f0a1", "B": "#ffb020", "C": "#9dccff"}


def _render_us_swing_finder(result: dict, market: dict, ranking: dict) -> None:
    """US_SWING_V1 전용 PRIMARY/WATCH 목록. 기존 급락 렌더와 완전히 분리한다."""

    primary = list(result.get("primary_rows") or result.get("rows") or [])
    watch = list(result.get("watch_rows") or [])
    market_state = result.get("market") or {}
    market_status = str(market_state.get("market_status") or "자료부족")
    ixic = market_state.get("ixic_close")
    drawdown = market_state.get("market_drawdown")

    # **노란 경고 상자로 두지 않는다**(2026-08-21 상하님 물음 — "저거는 무슨 말인지
    # 모르겠다, 지금 찾을 수 없다는 말인가?"). 문제가 난 것이 아니라 어느 명부로
    # 찾았는지 알려 주는 곁글이라, 아래 기준일 줄 옆에 조용히 붙인다.
    notes = [str(w) for w in (result.get("universe_warning"),
                              result.get("market_history_warning")) if w]
    market_line = (
        f"나스닥 지수 — {us_swing.plain_state(market_status)}"
        + (f" · 지금 {float(ixic):,.2f}" if ixic is not None else "")
        + (f" · 지금까지의 최고 대비 {float(drawdown) * 100:+.1f}%"
           if drawdown is not None else "")
    )
    if market_status == "MARKET_ON" and market_state.get("valid"):
        st.success(market_line + " — 오늘은 새로 살 후보를 낼 수 있는 장입니다.")
    else:
        st.error(market_line + " — 점수가 높아도 오늘은 새로 살 후보를 내지 않습니다.")

    # 저장 알림과 기준일·명부 줄은 2026-08-21에 뺐다(상하님 지시 — "설명 없애라").
    # 그 값들은 아래 표가 이미 보여준다(정식 후보 수 · 관찰 수 · 종목별 기준일).
    # **빈 자리를 남기지 않는다** — 그리는 코드를 통째로 지워 아래 칸이 위로 붙는다.
    # 저장이 **실패**했을 때만 알린다. 조용히 넘어가면 그날 자료가 빈 줄로 남는다.
    if result.get("snapshot_saved") is False:
        st.warning("후보는 다 찾았는데 그날 값을 저장하지 못했습니다: "
                   f"{result.get('snapshot_error') or '원인을 확인해야 합니다'}")

    # **접이칸이다. 단추가 아니다**(2026-08-22 상하님 지적 — "이 화면 설명
    # 보기를 클릭하는데도 25초 걸린다"). 단추는 누를 때마다 서버가 화면을
    # 다시 그린다. 이 칸은 글자뿐이라(시세도 그림도 없다) 미리 만들어 두고
    # 접어 두면 여닫는 데 **서버를 안 거친다** — 브라우저가 바로 편다.
    # 다른 구역이 아직 단추인 까닭은 그 안에 시세·차트가 들어 있어서다.
    with st.expander(
        "📘 이 화면 설명 보기 (통과조건 여섯 · 중요 70점 · 거드는 30점)",
        expanded=False,
    ):
        config = result.get("config") or {}
        rs_cfg = config.get("rs") or {}
        entry_cfg = config.get("entry") or {}
        st.markdown(
            "<div class='j3-pull-guide'><b>먼저 자격, 그다음 순위</b> — "
            "나스닥이 살 만한 장인가 · 최근 3개월 강했나 · 최근 6개월 강했나 · "
            "종가로 지난 1년 최고가를 넘었나 · 그 뒤 1~3거래일인가 · "
            "종가가 3~10% 내려왔나 — <b>여섯 가지를 다 넘어야</b> 정식 후보가 됩니다. "
            "뒤쪽 네 항목이 아무리 좋아도 이 여섯을 대신하지 못합니다.<br>"
            f"지금 기준: 최근 3개월 상위 "
            f"{100 - float(rs_cfg.get('rs60_min_percentile', 80)):.0f}% · 최근 6개월 상위 "
            f"{100 - float(rs_cfg.get('rs120_min_percentile', 80)):.0f}% · "
            f"신고가 뒤 {int(entry_cfg.get('watch_start_day', 1))}~"
            f"{int(entry_cfg.get('watch_end_day', 3))}거래일 · "
            f"눌림 {float(entry_cfg.get('pullback_min', .03)) * 100:.0f}~"
            f"{float(entry_cfg.get('pullback_max', .10)) * 100:.0f}%<br>"
            "<b>점수</b> — 최근 3개월 25 + 최근 6개월 25 + 눌림 20 = <b>중요 점수 70</b>, "
            "테마 10 + 돌파 거래량 8 + 테마 확산도 5 + 반등 7 = <b>보조 점수 30</b>입니다. "
            "총점은 승률이나 보장수익이 아닙니다.</div>",
            unsafe_allow_html=True,
        )
        catalog = result.get("explanation_catalog") or {}
        for metric in ("market", "rs60", "rs120", "breakout", "pullback",
                       "theme", "volume", "breadth", "rebound"):
            payload = catalog.get(metric) or {}
            if not payload:
                continue
            st.markdown(
                "<div class='j3-reason-card'>"
                f"<div class='j3-reason-title'>{html.escape(str(payload.get('title') or metric))} "
                f"<span class='j3-muted'>· "
                f"{html.escape(us_swing.plain_confidence(payload.get('confidence')))}</span></div>"
                f"<span class='j3-help-line'>{html.escape(str(payload.get('one_line') or ''))}</span>"
                f"<span class='j3-help-detail'>{html.escape(str(payload.get('detail') or ''))}</span>"
                "</div>",
                unsafe_allow_html=True,
            )

    st.markdown(
        "<style>div[class*='st-key-close_j3_pullback_open'] button {"
        "background:linear-gradient(90deg,#075d46,#18bf87) !important;color:#fff !important;"
        "border:1px solid rgba(255,255,255,.28) !important;}"
        "div[class*='st-key-close_j3_pullback_open'] button p {color:#fff !important;font-weight:800 !important;}"
        "</style>", unsafe_allow_html=True,
    )
    _section_close(
        "j3_pullback_open", "상승장 (신고가 눌림매수) 닫기",
        return_to=_RADAR_MAIN_ANCHOR,
    )

    all_selectable = primary + watch
    # **목록을 열 때 아무 종목도 고르지 않는다** (2026-08-22 상하님 지적 —
    # "그건 내가 한 적 없다. 그냥 종목 클릭하면 열리도록 하라고 했지").
    #
    # 지금까지는 목록이 뜨면 1등 종목을 저절로 골라 **상세와 차트 넷까지 같이**
    # 그렸다. 재 보니 그것이 5배였다 — 목록만 그리면 0.36초, 상세·차트까지
    # 그리면 1.75초다(노트북·자료 없이 그리기만). 폰에서는 차트가 더 비싸다.
    # 20개 테마 순위표가 빠른 까닭도 같다 — 거기는 목록만 그린다.
    #
    # 목록은 목록만 그리고, 상세와 차트는 **종목을 누를 때** 열린다.
    selected_ticker = st.session_state.get("j3_pullback_selected_ticker")
    tickers = [str(row.get("ticker") or "") for row in all_selectable]
    if selected_ticker not in tickers:
        selected_ticker = None
    selected_css = []
    button_keys = []          # (단추 열쇠, 티커) — 보라색 표시를 나중에 붙인다

    # **3개월·6개월 등수와 중요·보조 점수 칸은 뺐다**(2026-08-21 상하님 지시 —
    # "선택종목 세부사항에 보면 나온다"). 표에는 고를 때 필요한 것만 남긴다 —
    # 번호·점수·종목·티커·등급/상태·눌림·테마. 옆으로 밀리던 것도 사라진다.
    # 이 갈래는 일곱 칸뿐이다. 급락표의 넓은 공통 폭을 쓰지 않고 가장 긴 상태말
    # 「3·6개월 약함」이 들어가는 정도만 남겨 항목 사이 빈 폭을 줄인다.
    widths = [0.42, 0.62, 1.55, 0.72, 1.3, 1.2, 1.45]
    row_widths = [widths[0], widths[1], widths[2], sum(widths[3:])]
    rest_widths = widths[3:]
    # **「핵심」·「보조」가 무슨 말인지 모르겠다**(2026-08-21 상하님). 둘 다 점수인데
    # 이름만 봐서는 알 수 없었다. 무엇을 재는 점수인지 이름이 직접 말하게 한다.
    heads = ["티커", "등급 / 상태", "눌림 / 며칠째", "테마"]

    def draw_rows(rows: list[dict], box, *, watch_mode: bool) -> None:
        """표 한 벌을 **칸 넷으로 한 번에** 그린다 (2026-08-26 상하님 지시).

        예전에는 줄마다 st.columns 를 새로 만들었다. 15줄이면 화면 조각이 673개가
        되고, 그것이 여러 뭉치로 나뉘어 도착해 줄이 하나씩 나타나 보였다
        (상하님 — "종목 1번부터 여전히 순서대로 천천히 열린다").

        이제 칸은 한 번만 만들고, 번호·점수·나머지는 각각 한 덩이로 쌓는다.
        종목 단추 15개만 예전 그대로 진짜 단추로 둔다 — 눌러야 하기 때문이다.

        **값·점수·차례·보이는 모양은 하나도 안 바뀐다.** 같은 글자를 몇 덩이로
        나누어 보내느냐만 바뀐다.
        """
        # 줄을 누르면 바깥의 selected_ticker를 그 자리에서 바꾼다 — 그래야
        # 아래 상세가 **같은 판에서** 그 종목으로 그려진다(다시 그리기 없이).
        nonlocal selected_ticker
        prefix = "j3rbw" if watch_mode else "j3rbf"
        cols = box.columns(row_widths)
        # **「번호 · 점수」다. 「순위 · 총점」이 아니다**(2026-08-07 상하님 지시,
        # 2026-08-20에 다시 확인하심). 검증되지 않은 차례를 1위·2위처럼 보이면
        # 화면이 거짓말을 한다. 이 배점은 상하님 지시문이 정해 준 것이지 제가
        # 과거차트로 "이 차례가 맞다"를 확인한 것이 아니다. 그냥 번호다.
        cols[0].markdown("<div class='j3-th-head'>번호</div>", unsafe_allow_html=True)
        cols[1].markdown("<div class='j3-th-head'>점수</div>", unsafe_allow_html=True)
        cols[2].markdown("<div class='j3-th-head'>종목</div>", unsafe_allow_html=True)
        cols[3].markdown(_flex_row(rest_widths, heads, head=True), unsafe_allow_html=True)

        number_cells: list[str] = []
        score_cells: list[str] = []
        rest_cells: list[str] = []
        for index, row in enumerate(rows):
            rank = str(index + 1) if watch_mode else str(int(row.get("primary_rank") or index + 1))
            number_cells.append(f"<div class='j3-td j3-muted'>{rank}</div>")
            # 점수 색은 급락 표와 같은 자를 쓴다 — 70↑ 금색, 50↑ 하늘색, 그 아래 회색.
            total = float(row.get("total_score") or 0)
            score_class = ("j3-score-hi" if total >= 70 else
                           "j3-score-mid" if total >= 50 else "j3-score-low")
            score_cells.append(
                f"<div class='j3-td'><span class='j3-score {score_class}'>"
                f"{total:.0f}점</span></div>"
            )
            # 3개월·6개월 등수는 이 표에 안 적는다 — 종목을 누르면 「선택종목
            # 세부사항」에 그대로 나온다(2026-08-21 상하님 지시).
            pullback = row.get("pullback_pct_close")
            pullback_text = "—" if pullback is None else f"-{float(pullback):.1f}%"
            # 눌림은 3~10%가 **좋은 자리**다. 좋으면 초록, 너무 깊으면 붉게.
            pullback_tone = (
                "j3-muted" if pullback is None
                else "j3-green-strong" if 6.0 <= float(pullback) <= 10.0
                else "j3-green" if 3.0 <= float(pullback) < 6.0
                else "j3-down" if float(pullback) > 10.0
                else "j3-muted"
            )
            # 칸에는 **짧은 말**만 넣는다(2026-08-21). 긴 설명은 손을 올리면 뜨게
            # 두고, 칸 안에서는 잘라 준다 — 안 자르면 옆 칸 글자를 덮는다.
            long_label = (
                str(row.get("status_text") or "조건을 다 넘지 못했습니다")
                if watch_mode else
                str(row.get("grade_text") or "정식 후보")
            )
            short_label = (
                us_swing.short_status(row.get("primary_status")) if watch_mode
                else f"{row.get('grade') or '—'}등급"
            )
            tone = (
                _SWING_STATUS_TONE.get(str(row.get("primary_status") or ""), "#9aa0aa")
                if watch_mode else
                _SWING_GRADE_TONE.get(str(row.get("grade") or ""), "#9aa0aa")
            )
            label = (f"<span class='j3-rb-clip' style='font-weight:800; color:{tone}'"
                     f" title='{html.escape(long_label)}'>"
                     f"{html.escape(short_label)}</span>")
            theme_text = str(row.get("theme_id") or "자료부족")
            rest_cells.append(_flex_row(rest_widths, [
                f"<span style='font-weight:800'>{html.escape(str(row.get('ticker') or '—'))}</span>",
                label,
                f"<span class='{pullback_tone}' style='font-weight:800'>"
                f"{html.escape(pullback_text)}</span>"
                f" <span class='j3-muted'>· {int(row.get('days_since_anchor') or 0)}일째</span>",
                f"<span class='j3-pull-theme j3-rb-clip' title='{html.escape(theme_text)}'>"
                f"{html.escape(theme_text)}</span>",
            ]))

        cols[0].markdown(_stacked(number_cells), unsafe_allow_html=True)
        cols[1].markdown(_stacked(score_cells), unsafe_allow_html=True)
        # 종목 단추만 진짜 단추다 — 눌러야 아래 상세가 열린다.
        for index, row in enumerate(rows):
            key = f"{prefix}_{index:02d}"
            button_keys.append((key, row.get("ticker")))
            if cols[2].button(str(row.get("name") or row.get("ticker") or "—"), key=key, width="stretch"):
                selected_ticker = row.get("ticker")
                st.session_state["j3_pullback_selected_ticker"] = selected_ticker
                for opened in ("j3_detail_open_pullback", "j3_intraday_open_pullback", "j3_bundle_open_pullback"):
                    st.session_state[opened] = True
                scroll_to.request(st, "detail_pullback")
                # **다시 그리지 않는다**(2026-08-22 상하님 지적 — "종목 클릭하면
                # 18초"). 부르면 이 덩이를 **한 번 더** 그린다 — 표 서른다섯 줄과
                # 상세를 두 번씩 그리는 셈이다. 안 불러도 결과는 같다: 아래 상세는
                # 이 줄보다 **뒤에서** selected_ticker를 읽고, 보라색 표시는 줄을
                # 다 그린 뒤에 붙인다. 테마 대장주 표에서 이미 같은 방식으로 뺐다.
        cols[3].markdown(_stacked(rest_cells), unsafe_allow_html=True)

    if primary:
        st.markdown("<div class='j3-section-title'>정식 후보</div>", unsafe_allow_html=True)
        draw_rows(primary, st.container(key="j3_swing_table"), watch_mode=False)
    else:
        st.info("오늘은 여섯 가지를 다 넘은 정식 후보가 없습니다. "
                "자리를 채우려고 기준을 느슨하게 바꾸지 않습니다.")

    if watch:
        # **급락 표의 '11위~20위 더 보기'와 같은 열쇠를 쓴다**(2026-08-21 상하님
        # 지적 — 관찰 목록이 글자끼리 겹쳐 보였다). 그 열쇠에는 칸을 제 폭 안에
        # 가두고 표를 옆으로 미는 규칙이 이미 붙어 있다. 두 갈래는 한 번에 하나만
        # 그려지므로 열쇠가 겹치지 않는다.
        watch = watch[:_SWING_WATCH_ROWS]
        # **접이칸으로 되돌렸다** (2026-08-22 상하님 지적 — "누르지도 않았는데
        # 자동으로 열린다. 이거 잘못됐다").
        #
        # 오늘 오전에 제가 이걸 잠깐 뺐었다. 접이칸이 **펼 때 서버를 한 번 더
        # 다녀와서** 10~20초가 걸렸기 때문이다. 그런데 그 값의 대부분은 접이칸
        # 자체가 아니라, 그때 같이 다시 그리던 **종목 상세와 차트 넷**이었다.
        # 그 자동 선택을 뺀 지금은 펴는 값이 표 열다섯 줄뿐이라 싸다.
        #
        # 그러니 접이칸은 그대로 두는 것이 맞다 — 안 누르면 안 열린다.
        watch_box = st.container(key="j3_swing_rest").expander(
            f"관찰만 · 조건을 다 못 넘은 {len(watch)}개 보기"
        )
        draw_rows(watch, watch_box, watch_mode=True)
    # 고른 줄은 **보라색**이다 — 테마표·급락표와 같은 약속(2026-08-21 상하님 지시).
    # 줄을 다 그린 **뒤에** 붙이므로, 이 판에서 방금 누른 줄도 곧바로 표시된다.
    selected_css += [
        f"div[class*='st-key-{key}'] button "
        "{ background: rgba(192,132,252,.16) !important; "
        "border-left: 3px solid #c084fc !important; }"
        for key, ticker in button_keys if ticker and ticker == selected_ticker
    ]
    if selected_css:
        st.markdown(f"<style>{''.join(selected_css)}</style>", unsafe_allow_html=True)

    st.caption(
        "**중요 점수(70점)** 는 최근 3개월·6개월에 시장보다 강했나와 신고가 뒤 알맞게 "
        "쉬었나 셋을 더한 것이고, **보조 점수(30점)** 는 테마·돌파 거래량·테마 "
        "확산도·반등 넷을 더한 것입니다. 둘을 더하면 왼쪽 「점수」입니다. "
        "정식 후보에만 등급을 붙이고, 관찰 줄은 무엇이 모자란가를 먼저 적습니다. "
        "점수는 승률이 아닙니다."
    )
    if all_selectable and selected_ticker:
        selected = next(
            (row for row in all_selectable if row.get("ticker") == selected_ticker),
            all_selectable[0],
        )
        _render_pullback_detail(selected, market, ranking, mode="breakout")
    _section_close(
        "j3_pullback_open", "상승장 (신고가 눌림매수) 닫기", slot="_bottom",
        return_to=_RADAR_MAIN_ANCHOR,
    )


def _render_rulebook_finder(result: dict, market: dict, ranking: dict, mode: str) -> None:
    """설명서 두 갈래의 결과 표 (2026-08-01 사용자 지시).

    기본 눌림목 표와 칸이 다르다 — 여기서는 '눌림 점수'가 아니라 설명서가 실제로
    보는 값(신고가 며칠 전 · 고점 대비 · 보유일수)을 보여준다. 승률·평균수익은
    설명서에 적힌 검증값을 그대로 옮긴 참고치이며, 이 종목들의 성적이 아니다.
    """
    # 단추를 누르면 화면이 여기로 내려온다(2026-08-28). 두 갈래가 함께 쓰는
    # 자리라 여기 하나만 둔다 — 상승장은 아래 _render_us_swing_finder 로 간다.
    scroll_to.anchor(st, "finder_top")
    if not result.get("ok"):
        st.error(f"조회 실패: {_safe_error_text(result.get('error'))}")
        return
    if mode == "breakout":
        _render_us_swing_finder(result, market, ranking)
        return
    rows = result.get("rows") or []
    breakout = mode == "breakout"
    # 늘 보이는 것은 **오늘 이야기 한 줄**뿐이다. 설명은 전부 접는다
    # (2026-08-06 사용자 지시 — 설명이 첫 화면을 다 먹었다).
    wait_min, wait_max = 1, 5
    if breakout:
        rule = result.get("rule") or {}
        wait_min, wait_max = rule.get("wait_days", (1, 5))
        drop_low, drop_high = rule.get("drop_band", (-15.0, -4.0))
        # 표를 잰 자리인지 먼저 알려준다(2026-08-06 사용자 결정). **막지 않는다** —
        # 표 1의 '장세' 칸은 원래 설명서의 규칙이 아니라 그 숫자를 잰 범위였다.
        breakout_market = result.get("market") or {}
        if breakout_market.get("reason"):
            if breakout_market.get("armed"):
                st.success(breakout_market["reason"])
            else:
                st.error(breakout_market["reason"])
    else:
        counts = result.get("bucket_counts") or {}
        # 이름을 market으로 두면 이 함수의 인자(시장 조건점수)를 덮어쓴다.
        crash_market = result.get("market") or {}
        reference = result.get("reference") or {}
        drop_now = crash_market.get("drop_pct")
        ref_date = reference.get("reference_date")
        # 하락폭 숫자는 붉게(2026-08-06 사용자 지시). 스트림릿 글자색 표시를 쓴다.
        if ref_date and drop_now is not None:
            # 며칠 지났는지 함께 적는다(2026-08-16) — 표의 '테마 반등' 칸이
            # 기준일에서 잰 값이라, 며칠째인지 모르면 그 숫자를 읽을 수 없다.
            passed = result.get("days_since_reference")
            passed_text = (f" 그날부터 **{int(passed)}거래일** 지났습니다."
                           if isinstance(passed, (int, float)) else "")
            st.info(
                f"**{ref_date} 기준으로 찾았습니다** — 그날 나스닥이 고점에서 "
                f":red[**{reference.get('reference_drop', 0):.1f}%**]였고 오늘은 "
                f":red[**{drop_now:.1f}%**]입니다. "
                "그날 걸렸던 종목을 그대로 보여드립니다."
                + passed_text
            )
        elif drop_now is not None:
            st.info(
                "**최근 한 달에 나스닥이 :red[**-6~-12%**] 내려온 날이 없었습니다** — 지금은 "
                f":red[**{drop_now:.1f}%**]입니다. 그래서 오늘 낙폭으로 찾은 결과입니다."
            )
        # 이 갈래만 붙이는 경고다(2026-08-06 사용자 승인). 점수가 96·95·92처럼 크게
        # 찍혀 1등이 확실히 좋아 보이는데, 재 보면 1등과 10등의 성적 차이가 100번에
        # 1~3번뿐이다. 상승장은 테마 하나로 앞 +8.6 / 뒤 +2.5라 이 경고를 안 붙인다.
        st.caption(
            "⚠️ 이 화면은 순위가 성적을 거의 못 가립니다. 위에 있다고 더 좋은 자리가 "
            "아닙니다 — 10년치로 재 보면 1등과 10등의 차이가 100번에 1~3번입니다. "
            "목록으로 보시고 고르시는 것은 상하님이 하십시오."
        )
    # **접이칸이다. 단추가 아니다**(2026-08-22 상하님 지적 — "이 화면 설명
    # 보기를 클릭하는데도 25초 걸린다"). 단추는 누를 때마다 서버가 화면을
    # 다시 그린다. 이 칸은 글자뿐이라(시세도 그림도 없다) 미리 만들어 두고
    # 접어 두면 여닫는 데 **서버를 안 거친다** — 브라우저가 바로 편다.
    # 다른 구역이 아직 단추인 까닭은 그 안에 시세·차트가 들어 있어서다.
    with st.expander(
        "📘 이 화면 설명 보기 (찾는 그물 · 점수 매기는 기준)",
        expanded=False,
    ):
        if breakout:
            st.markdown(
                "<div class='j3-pull-guide'>"
                f"<b>찾는 그물</b> — 52주 신고가 뒤 <b>{wait_min}~{wait_max}거래일</b> 안에 "
                f"그 고점에서 <b>{abs(drop_high):.0f}~{abs(drop_low):.0f}%</b> 내려온 종목을 "
                "<u>모두</u> 보여줍니다. 이동평균은 보지 않습니다.<br>"
                "<b>점수가 곧 순위입니다</b> — 그물에 걸린 뒤 100점 배점으로 차례를 매깁니다. "
                "점수가 낮은 줄도 <u>참고로</u> 올려 두니 보시고 판단하십시오.<br>"
                f"같은 기간 <u>아무 날 아무 종목이나</u> 샀으면 6개월에 100번 중 "
                f"{result.get('base_win_rate')}번 이익 · 가운데 값 "
                f"+{result.get('base_median_return')}%였습니다. 아래 숫자는 "
                "<u>과거를 잰 것</u>이며 이 종목들의 성적이 아닙니다.<br>"
                # 2026-08-07 — 그물 자체를 격자로 다 재 보고 알게 된 것. 감추면 안 된다.
                "<b class='j3-down'>⚠ 이 그물은 아직 검증되지 않았습니다.</b> "
                "2026-08-07에 기다린 날·눌린 폭·보유기간·시장조건을 바꿔 가며 "
                "<b>144가지</b>를 3년 창으로 다 재 봤는데 <b>하나도 기준선을 넘지 "
                "못했습니다</b>(가장 나은 조합도 가운데 +2.1%p). 지난 10년 나스닥이 "
                "해마다 20.9%씩 올라 <u>아무 대형주나 사도 6개월에 100번 중 65번</u> "
                "벌던 시장이라, 골라내는 값이 표시가 안 납니다. "
                "<b>순위는 참고로만 보시고, 목록으로 읽으십시오.</b> "
                "같은 방법으로 한국은 192가지 중 41가지가 통과했습니다"
                "(docs/KR_RULE_BACKTEST.md).</div>",
                unsafe_allow_html=True,
            )
        else:
            cards = []
            for rule in result.get("rules") or []:
                # 카드와 표의 같은 갈래가 같은 색이어야 눈으로 이어진다(2026-08-01 지시).
                cards.append(
                    f"<div class='j3-reason-card {_BAND_CARD_CLASS.get(rule['key'], '')}'>"
                    f"<div class='j3-reason-title'>{rule['label']}</div>"
                    # **파는 날을 적지 않는다**(2026-08-12 상하님 확정). 대신
                    # 3개월·6개월·1년 과거 성적을 나란히 놓는다.
                    f"<div class='j3-reason-body'>"
                    + " · ".join(
                        f"{item['label']} <b>{item['median_return']:+.1f}%</b>"
                        f"(100번 중 {item['win_rate']:.0f}번)"
                        for item in rule.get("results") or ())
                    + f" · 지금 해당 종목 {counts.get(rule['key'], 0)}개</div></div>"
                )
            if ref_date:
                st.caption(
                    f"오늘이 아니라 {ref_date} 기준으로 갈래를 나눴습니다"
                    f"(최근 {reference.get('days_in_band', 0)}일이 그 자리였고 마지막은 "
                    f"{reference.get('last_in_band', '—')}). 오늘 기준으로 다시 재면 "
                    "이미 오른 종목이 목록에서 사라집니다."
                )
            st.markdown(
                "<div class='j3-pull-guide'><b>찾는 그물</b> — 나스닥이 "
                "<span class='j3-drop'>-6~-12%</span>였던 날을 기준으로, 고점에서 "
                "<span class='j3-drop'>-20~-50%</span> 빠진 종목을 찾습니다.</div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                "<div class='j3-pull-guide'>"
                "<b>찾는 그물</b> — 신고가가 언제였는지는 <u>보지 않고</u> "
                "<b>고점 대비 얼마나 내려왔는지만</b> 봅니다. 이동평균도 보지 않습니다.<br>"
                "<b>점수가 곧 순위입니다</b> — 그물에 걸린 뒤 100점 배점으로 차례를 매깁니다. "
                "아래 갈래별 성적은 <u>갈래끼리 견준 것</u>이고, 순위는 배점표가 정합니다.<br>"
                # 낙폭 칸 셋이 무엇인지 화면 어디에도 설명이 없었다(2026-08-07 지적).
                + (f"<b>낙폭 칸 셋</b> — <b>고점 대비</b>는 기준일({ref_date})에 "
                   "고점에서 얼마나 빠져 있었나, <b>고점대비현재</b>는 오늘 얼마나 "
                   "빠져 있나, <b>종목저점후</b>는 그 기준일 종가에서 지금까지 얼마나 "
                   "움직였나입니다(그 종목 스스로의 저점이 아니라 <u>기준일</u>이 "
                   "출발점입니다). <u>갈래와 점수는 ‘고점 대비’로 정합니다</u> — 오늘 "
                   "값으로 정하면 이미 반등한 종목이 목록에서 사라집니다.<br>"
                   if ref_date else "")
                + "<b>아래 성적은 10년치(2016.8~2026.8)를 잰 것</b>이며 앞으로의 승률이 아닙니다."
                "</div>"
                f"<div class='j3-metric-row'>{''.join(cards)}</div>",
                unsafe_allow_html=True,
            )
        # 배점표를 화면에 그대로 뿌린다(2026-08-06 사용자 지시). 0점 항목도 왜 뺐는지
        # 같이 보여야 나중에 같은 실수를 되풀이하지 않는다.
        base_rate = result.get("base_win_rate") if breakout else (
            (result.get("rules") or [{}])[0].get("base_win_rate")
        )
        # **깊은 급락에서는 점수가 순위를 못 가른다**(2026-08-12 상하님 지적으로
        # 갈라서 재 봤다 — research/us_crash_depth_check.py). 나스닥 -24% 아래에서는
        # 세 항목이 전부 무너진다. 그럴 때는 감추지 말고 그렇다고 적는다.
        if result.get("score_blind"):
            drop = (result.get("market") or {}).get("drop_pct")
            limit = getattr(j3data, "CRASH_SCORE_BLIND_BELOW", -24.0)
            st.markdown(
                "<div class='j3-pull-guide'><b class='j3-down'>⚠ 오늘은 점수로 "
                "순위를 가를 수 없습니다.</b> 나스닥이 고점 대비 "
                + (_red(f"{float(drop):.1f}%") if drop is not None else "크게")
                + f"까지 빠져 있습니다. 이만큼(<b>{abs(limit):.0f}% 아래</b>) 깊은 "
                "자리에서는 배점 세 항목이 <u>전부 무너집니다</u> — 10년치를 낙폭 칸별로 "
                "갈라 재서 확인했습니다.<br><b>아래 목록은 순서 없이 보십시오.</b> "
                "이런 날은 어느 자리를 사도 크게 올랐습니다(그물 전체 1년 가운데 +32%).</div>",
                unsafe_allow_html=True)
        # **얕은 급락(6~12%)에서도 순위가 약하다.** 그런데 여기가 급락 목록이 뜨는
        # 날의 41%, 제일 자주 오는 자리다. 2026-08-12 저녁 상하님 물음 —
        # "답이 없다는 말이 뭐냐. 내보고 어쩌라고." 화면이 아무 말도 안 하고 있던
        # 것이 문제였다. 깊은 급락과 달리 아주 못 쓰는 것은 아니라 문구를 달리한다.
        elif result.get("score_weak"):
            drop = (result.get("market") or {}).get("drop_pct")
            low, high = getattr(j3data, "CRASH_SCORE_WEAK_BAND", (-12.0, -6.0))
            st.markdown(
                "<div class='j3-pull-guide'><b class='j3-down'>⚠ 오늘은 순위가 "
                "약합니다.</b> 나스닥이 고점 대비 "
                + (_red(f"{float(drop):.1f}%") if drop is not None else "조금")
                + f" 빠져 있습니다. 이 정도(<b>{abs(high):.0f}~{abs(low):.0f}%</b>) "
                "얕은 자리는 <u>급락 목록이 뜨는 날의 41%</u>로 제일 자주 오는데, "
                "10년치로 재 보면 배점 세 항목 중 <b>‘테마가 덜 빠졌나’만 1년 보유에서 "
                "걸립니다.</b><br><b>1등과 5등을 크게 다르게 보지 마십시오.</b> "
                "짧게 들고 나오실 생각이면 특히 그렇습니다.</div>",
                unsafe_allow_html=True)
        st.markdown(
            _score_table_html("breakout" if breakout else "crash", base_rate)
            + "<div class='j3-pull-guide'>"
            "<b class='j3-down'>미국에는 외국인·기관 수급 자료가 없습니다.</b> 대신 쓸 값 여섯 가지를 "
            "재 봤지만 하나도 갈리지 않아 넣지 않았습니다(docs/US_RANK_BACKTEST.md).</div>",
            unsafe_allow_html=True,
        )
    reuse_text = "기존 일봉 배치 재사용" if result.get("reused_batch") else "일봉 1회 배치 조회"
    funnel = (
        f"신고가 {wait_min}~{wait_max}일 전 <b>{result.get('window_count', 0):,}개</b> → "
        if breakout else ""
    )
    st.markdown(
        "<div class='j3-pull-stats'>"
        f"대형주 <b>{result.get('universe_count', 0):,}개</b> → "
        f"일봉 확보 <b>{result.get('data_count', 0):,}개</b> → "
        f"{funnel}기준 통과 <b class='j3-green'>{len(rows):,}개</b>"
        f"(최대 {int(result.get('result_limit') or 0)}개) · {reuse_text}</div>",
        unsafe_allow_html=True,
    )
    # 사용자가 지정한 정확한 자리: '대형주 → 일봉 확보 → 기준 통과' 통계 바로
    # 아래이면서, '순위 · 종목 · 티커' 표 머리글 바로 위에 둔다.
    mode_close_label = (
        "상승장 (신고가 눌림매수) 닫기"
        if breakout else "급락 후 반등장 (낙폭종목) 닫기"
    )
    close_background = (
        "linear-gradient(90deg,#075d46,#18bf87)"
        if breakout else "linear-gradient(90deg,#6b2d05,#e67813)"
    )
    st.markdown(
        "<style>div[class*='st-key-close_j3_pullback_open'] button {"
        f"background:{close_background} !important; color:#fff !important;"
        "border:1px solid rgba(255,255,255,.28) !important;"
        "box-shadow:0 0 12px rgba(230,120,19,.20) !important;}"
        "div[class*='st-key-close_j3_pullback_open'] button p {"
        "color:#fff !important; font-weight:800 !important;}</style>",
        unsafe_allow_html=True,
    )
    _section_close(
        "j3_pullback_open", mode_close_label,
        return_to=_RADAR_MAIN_ANCHOR,
    )
    if not rows:
        st.info(
            "지금은 이 기준에 맞는 종목이 없습니다. 기준을 느슨하게 바꾸지 않습니다 — "
            "설명서 그대로 찾은 결과입니다."
        )
        return

    # 급락 갈래에서 기준일이 있으면 낙폭을 **세 칸으로 나눈다**(2026-08-07 상하님
    # 지시 "너무 촘촘하니 칸을 두 개 더"). 한 칸에 세 줄을 겹쳐 넣었더니 빽빽했다.
    split_drop = bool(not breakout and (result.get("reference") or {}).get("reference_date"))
    if split_drop:
        # '테마 반등' 칸을 '종목저점후' 바로 뒤에 넣었다(2026-08-16 상하님 지시).
        # 둘 다 기준일에서 잰 값이라 나란히 둬야 읽힌다 — 앞은 이 종목 하나,
        # 뒤는 그 테마 전체다. **점수는 아니다.**
        widths = [0.55, 1.75, 0.75, 1.25, 1.15, 1.35, 1.25, 1.25, 1.75, 1.2, 1.0, 1.15, 1.5]
    else:
        widths = [0.55, 1.75, 0.75, 1.25, 1.15, 1.75, 1.2, 1.0, 1.15, 1.5]
    # 점수는 순위 **다음 칸**에 따로 둔다(2026-08-06 사용자 지시). 순위 칸에 같이
    # 넣었더니 '1'과 '58점'이 붙어 158점처럼 읽혔다(상하님 캡처).
    row_widths = [widths[0], 0.7, widths[1], sum(widths[2:])]
    rest_widths = widths[2:]
    # 상승장에서 이 칸이 실제로 고르는 자리다 — 거르는 기준은 눌린 폭 하나이고,
    # 며칠 지났는지는 보여만 주고 사람이 판단한다(2026-08-06 사용자 지시).
    third = "고점 후 며칠" if breakout else "갈래"
    # 칸 이름은 상하님이 정한 그대로 쓴다(2026-08-07).
    #   고점 대비     — 기준일 그날의 낙폭. **갈래와 15점을 정하는 값이다.**
    #   고점대비현재  — 오늘 낙폭.
    #   종목저점후    — 기준일 종가에서 지금까지의 변동.
    #   테마 반등     — 기준일 이후 그 테마 명부 종목 몇 개 중 몇 개가 올라 있나.
    #                   **점수에 안 쓴다**(2026-08-16). 보시는 그 시점의 사실이다.
    drop_heads = (["고점 대비", "고점대비현재", "종목저점후", "테마 반등"] if split_drop
                  else ["고점 대비"])
    # 마지막 칸은 두 갈래가 같다(2026-08-06). 배점 25점짜리 '최근 11일에 빠졌나'를
    # 보여준다 — 예전에 여기 있던 '거래대금 연속'과 '최근 60일 상승폭'은 앞뒤로
    # 갈라 재니 뒤 5년에서 져서 배점이 0점이 됐다. 점수에 안 쓰는 값을 표에 두면
    # 화면이 순위와 다른 것을 설명하게 된다.
    volume_head = "최근 11일"
    head_cells = (["티커", "당일주가"] + drop_heads
                  + ["소속 테마", third, "1년 성적", "같이 걸린 종목", volume_head])
    # **상승장은 '순위'라고 부르지 않는다**(2026-08-07). 그물을 144가지로 다 재도
    # 하나도 기준선을 못 넘었다 — 그 위에서 매긴 차례를 1위·2위로 보이면 화면이
    # 검증되지 않은 것을 검증된 것처럼 말하게 된다. 그냥 번호다.
    # 급락 후 반등장은 그물이 통과했으므로 '순위' 그대로 쓴다.
    rank_head = "번호" if breakout else "순위"
    table_box = st.container(key="j3_rulebook_table")
    head = table_box.columns(row_widths)
    head[0].markdown(f"<div class='j3-th-head'>{rank_head}</div>", unsafe_allow_html=True)
    head[1].markdown(
        f"<div class='j3-th-head'>점수</div>",
        unsafe_allow_html=True)
    head[2].markdown("<div class='j3-th-head'>종목</div>", unsafe_allow_html=True)
    head[3].markdown(
        _flex_row(rest_widths, head_cells, head=True),
        unsafe_allow_html=True,
    )

    tickers_now = [row.get("ticker") for row in rows]
    selected_ticker = st.session_state.get("j3_pullback_selected_ticker")
    if selected_ticker not in tickers_now:
        selected_ticker = rows[0].get("ticker")
    selected_css = []
    # 20줄을 다 펴 놓으면 화면이 길다(2026-08-06 사용자 지시). 앞 15줄만 펴 두고
    # 나머지는 접는다 — 위 '11위~20위 테마 더 보기'와 같은 방식이다.
    overflow_box = None
    for index, row in enumerate(rows):
        if index == _RULEBOOK_OPEN_ROWS and len(rows) > _RULEBOOK_OPEN_ROWS:
            # 테마표와 같은 이유로 키를 가진 칸으로 감싼다 — 접힌 쪽도 옆으로
            # 밀어서 보게 한다(2026-08-09 상하님 지적, 폰·태블릿 둘 다 쌓였다).
            overflow_box = st.container(key="j3_rulebook_rest").expander(
                f"{_RULEBOOK_OPEN_ROWS + 1}위~{len(rows)}위 더 보기"
            )
            # 접힌 쪽에도 머리글을 한 번 붙인다 — 없으면 어느 칸이 무엇인지 모른다.
            over_head = overflow_box.columns(row_widths)
            for column, title in zip(
                    over_head,
                    (rank_head, "점수", "종목")):
                column.markdown(f"<div class='j3-th-head'>{title}</div>",
                                unsafe_allow_html=True)
            over_head[3].markdown(
                _flex_row(rest_widths, head_cells, head=True),
                unsafe_allow_html=True,
            )
        row_box = table_box if index < _RULEBOOK_OPEN_ROWS else overflow_box
        metrics = row.get("metrics") or {}
        from_high = metrics.get("from_high_pct")
        cols = row_box.columns(row_widths)
        # 점수는 순위 다음 **따로 칸**에 둔다(2026-08-06 사용자 지시).
        score = row.get("score")
        score_class = (
            "j3-score-hi" if (score or 0) >= 70
            else "j3-score-mid" if (score or 0) >= 50
            else "j3-score-low"
        )
        cols[0].markdown(
            f"<div class='j3-td j3-muted'>{int(row.get('pullback_rank') or index + 1)}</div>",
            unsafe_allow_html=True,
        )
        cols[1].markdown(
            f"<div class='j3-td'><span class='j3-score {score_class}'>"
            + (f"{float(score):.0f}점" if score is not None else "—")
            + "</span></div>",
            unsafe_allow_html=True,
        )
        if cols[2].button(
            str(row.get("name") or row.get("ticker") or "—"),
            key=f"j3rbf_{index:02d}",
            width="stretch",
        ):
            st.session_state["j3_pullback_selected_ticker"] = row["ticker"]
            # 종목을 누르면 상세와 차트까지 한 번에 열린다(2026-08-01 사용자 지시).
            for opened in ("j3_detail_open_pullback", "j3_intraday_open_pullback",
                           "j3_bundle_open_pullback"):
                st.session_state[opened] = True
            back_nav.opened(st, "j3_detail_open_pullback",
                            "j3_intraday_open_pullback", "j3_bundle_open_pullback")
            # 열기만 하면 그 자리가 화면 한참 아래라 직접 굴려야 했다(2026-08-09).
            scroll_to.request(st, "detail_pullback")
            # **이 덩이만 다시 그린다.** scope를 안 주면 판 전체가 돈다.
            _rerun_here()
        if row.get("ticker") == selected_ticker:
            selected_css.append(
                f"div[class*='st-key-j3rbf_{index:02d}'] button "
                "{ background: rgba(192,132,252,.16) !important; "
                "border-left: 3px solid #c084fc !important; }"
            )
        price_cell = (
            "<span style='display:inline-flex; flex-direction:column; align-items:center;"
            " line-height:1.12; font-weight:800; color:#e6e6e6'>"
            f"<span>{_price(metrics.get('current'))}</span>"
            f"<span style='color:{_sign_color(metrics.get('change_pct'))};"
            f" font-weight:800; font-size:.82rem'>{_pct(metrics.get('change_pct'))}</span></span>"
        )
        if breakout:
            third_cell = f"<span class='j3-green'>{int(row.get('wait_days') or 0)}일 전</span>"
        else:
            # 칸이 좁아 '고점 대비 -40~-50%'는 옆 칸을 덮었다(2026-08-01 폰 캡처).
            # '고점 대비'는 바로 왼쪽 칸 이름이 이미 말하므로 숫자만 남긴다.
            band = str(row.get("bucket_label") or "—").replace("고점 대비 ", "")
            band_class = _BAND_CELL_CLASS.get(str(row.get("bucket")), "j3-pull-amber")
            third_cell = f"<span class='{band_class}'>{html.escape(band)}</span>"
        # 순위를 정한 값(테마 동반)과 참고값(거래대금)을 표에 그대로 보여 준다.
        tier = int(row.get("together_tier") or 0)
        tier_class = ("j3-muted", "j3-pull-theme", "j3-pull-amber", "j3-green-strong")[tier]
        together_cell = (
            f"<span class='{tier_class}' style='font-weight:850'"
            f" title='{html.escape(str(row.get('together_theme') or ''))}'>"
            f"{int(row.get('together_count') or 0)}개</span>"
        )
        # 2026-08-12부터 파는 날을 규칙으로 정하지 않는다. 그래서 이 칸에는
        # 며칠이 아니라 **이 자리를 1년 들었을 때의 과거 성적**을 적는다.
        year = next((item for item in (row.get("hold_results") or ())
                     if item.get("days") == 250), None)
        hold_cell = (f"<span class='j3-hold-120'>1년 {year['median_return']:+.0f}%</span>"
                     if year else "<span class='j3-muted'>—</span>")
        # 달러 거래대금은 숨기고 이 화면에서 실제 순위에 쓰는 값만 남긴다.
        # 최근 11일에 빠진 쪽이 만점이므로, 빠진 것을 초록으로 둔다(값이 좋다는 뜻).
        gain11 = row.get("recent_gain_pct")
        gain_class = (
            "j3-muted" if gain11 is None
            else "j3-green-strong" if float(gain11) <= -5.0
            else "j3-up" if float(gain11) <= 0.0
            else "j3-muted"
        )
        volume_cell = (
            f"<span class='{gain_class}' style='font-weight:850'>"
            f"{'—' if gain11 is None else f'{float(gain11):+.1f}%'}</span>"
        )
        themes_all = [name for name in (row.get("themes") or []) if name]
        lead = str(row.get("together_theme") or "") or (themes_all[0] if themes_all else "")
        rest_n = max(len(themes_all) - 1, 0)
        theme_text = (f"{lead} 외 {rest_n}" if rest_n else lead) or "—"
        # 급락 갈래에서 기준일이 있으면 '그날 → 지금'을 한 칸에 같이 보여 준다.
        # 오늘 숫자만 보면 이미 오른 종목이 왜 목록에 있는지 알 수 없다(2026-08-06).
        judged = row.get("judged_from_high_pct")
        since = row.get("since_reference_pct")
        if split_drop:
            # 한 칸에 세 줄을 겹쳐 넣었더니 빽빽했다(2026-08-07 상하님 지적).
            # **칸을 셋으로 나눈다** — 칸 이름이 곧 그 숫자의 뜻이다.
            # 오늘 낙폭은 jarvis3_data가 따로 적어 둔 값을 먼저 쓴다 — metrics의
            # 값과 같아야 하지만, 적어 둔 쪽이 이 화면이 쓰라고 만든 값이다.
            now_drop = row.get("now_from_high_pct")
            if now_drop is None:
                now_drop = from_high
            # 테마 반등 — '5개 중 3개'. 명부에 그 테마가 없거나 기준일 값을 못 낸
            # 종목뿐이면 '—'다. **0으로 채우지 않는다**(CLAUDE.md 10-1).
            up_total = int(row.get("theme_up_total") or 0)
            up_count = int(row.get("theme_up_count") or 0)
            if up_total:
                # 넷 중 셋 넘게 오른 테마만 밝게 — 엑셀 실측에서 값이 있던 자리다.
                spread_class = ("j3-green-strong" if up_count / up_total >= 0.8
                                else "j3-pull-theme" if up_count / up_total >= 0.5
                                else "j3-muted")
                spread_cell = (
                    f"<span class='{spread_class}'"
                    f" title='{html.escape(str(row.get('theme_up_name') or ''))}"
                    f" · 기준일 이후 오른 종목'>{up_total}개 중 {up_count}개</span>"
                )
            else:
                spread_cell = "<span class='j3-muted'>—</span>"
            # ── 1년 최고가가 바뀐 종목은 표시한다 (2026-08-19 상하님 지적) ──
            # 「고점 대비」와 「고점대비현재」가 **서로 다른 고점**을 쓰게 되면
            # 두 값을 견줄 수 없다. 20종목 중 셋이 그랬다(MDB·DELL·NOW).
            # 값은 그대로 두고 ˟표만 붙인다 — 각 숫자는 제 뜻대로 맞다.
            moved_mark = ""
            if row.get("high52_moved"):
                then_high = row.get("high52_then")
                now_high = row.get("high52_now")
                moved_mark = (
                    "<span class='j3-pull-amber' style='font-size:.8rem'"
                    f" title='기준일 뒤 1년 최고가가 바뀌었습니다"
                    f" ({float(then_high):,.2f} → {float(now_high):,.2f}).'"
                    " '>˟</span>"
                )
            drop_cells = [
                f"<span class='{_sign_class(judged)}'"
                f" style='font-weight:800'>{_pct(judged)}</span>",
                f"<span class='{_sign_class(now_drop)}'>{_pct(now_drop)}</span>"
                + moved_mark,
                (f"<span class='{_sign_class(since)}'>{float(since):+.1f}%</span>"
                 if since is not None else "<span class='j3-muted'>—</span>"),
                spread_cell,
            ]
        else:
            drop_cells = [
                f"<span class='{_sign_class(from_high)}'"
                f" style='font-weight:800'>{_pct(from_high)}</span>"
            ]
        cols[3].markdown(
            _flex_row(rest_widths, [
                html.escape(str(row.get("ticker") or "—")),
                price_cell,
                *drop_cells,
                f"<span class='j3-rb-clip j3-pull-theme'"
                f" title='{html.escape(' · '.join(themes_all))}'>{html.escape(theme_text)}</span>",
                third_cell,
                hold_cell,
                together_cell,
                volume_cell,
            ]),
            unsafe_allow_html=True,
        )
    if selected_css:
        st.markdown(f"<style>{''.join(selected_css)}</style>", unsafe_allow_html=True)
    st.caption(
        "매수는 설명서대로 종가를 확인한 뒤 다음 거래일 시가에 합니다. 이 표는 "
        "그 자리에 와 있는 종목을 좁혀 준 목록이며, 사라는 신호가 아닙니다. "
        + ("**0점**은 나쁘다는 뜻이 아니라 "
           "**점수 주는 세 자리 중 하나도 안 맞다**는 뜻입니다. "
           "**「테마 반등」 칸은 점수에 안 들어갑니다** — 기준일 이후 그 테마에서 "
           "몇 종목이 올라 있는지 보여드릴 뿐이고, 순위를 바꾸지 않습니다. "
           # 2026-08-19 상하님 지적 — 세 숫자가 빼기로 안 맞는다는 물음.
           # 셋 다 맞는데 재는 자리가 다르다. 그 말을 표 밑에 한 번 적어 둔다.
           "**「고점 대비」와 「고점대비현재」는 1년 최고가에서 잰 값**이고, "
           "**「종목저점후」는 기준일 종가에서 잰 값**입니다. 기준이 서로 달라 "
           "두 낙폭을 빼도 「종목저점후」가 나오지 않습니다 — 값이 내려간 만큼 "
           "나중에 오른 폭은 더 크게 보입니다. "
           "**˟ 표가 붙은 종목**은 기준일 뒤 1년 최고가가 바뀌어 두 낙폭이 "
           "서로 다른 고점을 쓴 종목입니다(표에 손을 올리면 그 값이 보입니다).")
    )
    selected_row = next(
        (row for row in rows if row.get("ticker") == selected_ticker), rows[0]
    )
    _render_pullback_detail(selected_row, market, ranking)
    # 이 갈래의 **맨 끝** 닫기 단추 (2026-08-15 상하님 지시 — "매수심사결과 높은
    # 순위 9 위와 ✕ 선택종목 세부사항 닫기 밑, 두 개 사이에 하나 더 만들어라").
    # 위쪽 닫기는 목록 머리글 바로 위에 있어서, 상세까지 다 내려보고 나면 화면
    # 몇 장을 도로 올라가야 접을 수 있었다.
    _section_close(
        "j3_pullback_open", mode_close_label, slot="_bottom",
        return_to=_RADAR_MAIN_ANCHOR,
    )



# **'차트 미리 받기'는 걷어냈다** (2026-08-22).
#
# 상하님 지적 — "상승장 클릭하면 또 35초." 제가 오늘 넣었다가 두 번 다 더
# 느리게 만든 것이다.
#   · 뒤 일꾼에게 넘겼더니 → 내려받기가 한 줄로 서서 돌기 때문에, 화면이 지금
#     쓸 자료가 그 뒤에 섰다(10초).
#   · 그 자리에서 받게 했더니 → 세 종목의 **전체 이력**을 목록 뜨기 전에
#     받느라 35초가 됐다.
#
# 목록은 목록만 그리고, 차트는 종목을 누를 때 그 한 종목만 받는다 —
# 2026-08-21 저녁 상태(상승장 열기 4초)로 되돌린 것이다.
# 누른 뒤가 느린 것은 따로 재서 잡는다. 여는 것이 먼저다.


def _rerun_here() -> None:
    """지금 덩이(프래그먼트)만 다시 그린다. 안 되는 판이면 예전처럼 판 전체를.

    scope="fragment"는 프래그먼트 밖에서 부르면 예외가 난다. 그때는 조용히
    예전 방식으로 넘어간다 — 화면이 죽으면 안 된다.
    """
    try:
        st.rerun(scope="fragment")
    except Exception:
        st.rerun()


@st.fragment
def _render_pullback_finder(market: dict, ranking: dict) -> None:
    """상승장·급락 덩이. 그리고 **덩이 안에서 화면을 내려 준다.**

    2026-08-21에 이 덩이를 프래그먼트로 묶으면서 종목을 눌러도 화면이 안
    내려가게 만들었다(상하님 지적 — "선택종목 세부사항으로 자동으로 내려가야
    되는데 또 변동 없다"). 화면 내려가기는 페이지 **맨 끝**에서 도는데,
    프래그먼트만 다시 그리면 그 끝이 안 돌아간다.

    그래서 덩이가 끝날 때 여기서 한 번 더 부른다. 자리 표시(anchor)는 이 안에서
    이미 그려졌으므로 브라우저가 찾을 수 있다. 먼저 부르는 쪽이 표시를 지우므로
    페이지 끝의 것과 두 번 내려가지 않는다.
    """
    _render_pullback_finder_body(market, ranking)
    # 「다 닫기」가 **먼저**다 (2026-08-26 상하님 지적 — "20개 테마 실시간 순위
    # 닫기 하면 두 번째 캡처처럼 가는 게 아니라 첫 번째 캡처처럼 가야 된다고").
    # 차례가 반대였다. scroll_to.run 이 먼저 돌면 '그 자리로 내려가라'는 표시를
    # **지우면서** 내려가는 쪽지를 이 조각 안에 그린다. 그런데 바로 뒤의
    # _run_close_all_if_requested()가 판 전체를 다시 그려 그 조각을 통째로 버린다.
    # 표시는 이미 지워졌으니 다시 그린 판은 아무 데도 안 가고, 상하님은 닫기 전
    # 그 자리(두 번째 캡처)에 그대로 서 계셨다.
    # 다시 그리기가 먼저면 이 판은 여기서 멈추고, 표시가 살아남아 페이지 끝
    # (main 의 scroll_to.run)에서 제자리로 데려간다. 순위 9 쪽
    # (_render_top7_section)이 원래 이 차례라서 그쪽만 잘 됐다.
    _run_close_all_if_requested()
    # **try/finally로 감싸면 안 된다**(2026-08-22 상하님 지적 — "관찰 15개에서
    # 종목을 눌러도 세부사항으로 안 간다"). _rerun_here()는 예외를 던져 이 판을
    # 멈추는데, finally는 그 예외가 지나갈 때도 실행된다. 그러면 **버려질 판에서**
    # 내려가라는 표시를 지워 버려서, 정작 다시 그린 판에는 표시가 없다.
    # 그냥 뒤에 둔다 — 다시 그리기로 멈춘 판은 여기까지 안 오고, 다음 판에서 돈다.
    scroll_to.run(st)


def _render_pullback_finder_body(market: dict, ranking: dict) -> None:
    """상승장·급락 두 갈래와 그 상세를 **한 덩이로 묶는다** (2026-08-21).

    상하님 지적 — "상승장은 닫는 데도 8초 걸리는데 순위 9는 닫는 게 금방이다."
    맞는 관찰이다. 순위 9는 이미 프래그먼트라 그 덩이만 다시 그리는데, 여기는
    안 묶여 있어서 단추 한 번에 **판 전체**를 다시 그렸다 — 지수 카드·게이지·
    미국장 신호·테마 20줄까지. 자료를 하나도 안 가져오는 '닫기'가 8초 걸린
    까닭이 그것이다.

    상세도 이 안에 들어 있어야 한다. 표만 묶으면 종목을 눌러도 덩이 밖 상세가
    다시 안 그려져 아무 일도 안 일어난 것처럼 보인다(순위 9에 적힌 그대로다).
    """
    # st.divider()는 뺐다(2026-08-06 상하님 지시 "제목을 위로 올려라") — 가로줄과
    # 그 아래 빈 자리가 제목을 한참 밀어내렸다. 제목 자체가 구역을 갈라 준다.
    # 제목과 맨 위 설명은 2026-08-06에 뺐다(상하님 지적).
    #
    # '눌림목 종목 찾기(상승추세 중 조정)'는 없앤 A 규칙의 이름이고, 그 아래 설명도
    # A 규칙의 배점(눌림 점수 25+20+20+20+10+5)을 말하고 있었다. 단추만 빼고 제목·
    # 설명을 안 지워서 화면이 없는 기능을 설명하고 있었다.
    #
    # **맨 위에서 통째로 설명하지 않는다.** 지금 이 자리에는 서로 다른 자를 쓰는
    # 갈래가 둘(상승장·급락) 있고, 아래 순위 7은 또 다른 자다. 갈래마다 제 설명이
    # 이미 자기 안에 있다 — 상승장·급락은 '이 화면 설명 보기', 순위 7은 제목 아래
    # 문단이다. 맨 위 설명은 그 셋을 뭉뚱그려 오해를 만든다.
    #
    # **「20개 테마 실시간 순위」 여닫이는 여기, '종목 찾기' 바로 위에 둔다**
    # (2026-08-14 상하님 지시). 순위표가 열 줄이라 이 구역까지 오려면 매번 한참
    # 굴려야 했다. 상승장·급락 닫기 단추와 같은 장치(_section_close)를 쓴다.
    # 여는 단추는 **맨 위**에 있다(순위표 자리). 여기에는 닫는 단추만 둔다 —
    # 상승장·급락과 같은 규칙이다(위에서 열고, 아래에서도 닫는다).
    if st.session_state.get(_THEME_RANK_OPEN):
        # 이 단추는 프래그먼트 안에 있다. 상태만 바꾸면 그 조각만 다시 그려져
        # 위쪽 순위표·테마 상세가 화면에 그대로 남는다.
        # **콜백(on_click) 안에서 st.rerun을 부르면 스트림릿이 무시한다.**
        # 2026-08-26까지 그렇게 되어 있어서, 맨 밑 닫기를 눌러도 순위표가 남았다
        # (상하님 캡처 — 닫았는데 첫 번째 화면처럼 그대로였다).
        # 그래서 콜백은 '판 전체를 다시 그려라'만 적어 두고, 조각이 끝날 때
        # (_run_close_all_if_requested) 실제로 다시 그린다.
        st.button(
            f"✕ {_THEME_COUNT}개 테마 실시간 순위 닫기",
            key=f"close_{_THEME_RANK_OPEN}",
            on_click=_close_all_from_fragment,
        )
    st.markdown(
        "<div class='j3-section-title'>📉 종목 찾기</div>",
        unsafe_allow_html=True,
    )
    # 한국테마(자비스4)와 같이 버튼을 눌러야 펼쳐진다(2026-07-25 사용자 지시).
    # 페이지를 여는 것만으로 20종목 표가 통째로 쏟아지면 폰에서 화면을 다 먹었다.
    # 제목은 '눌림목 찾기'만, 폭도 글자만큼만 둔다(2026-07-30 사용자 지시).
    # 열려 있을 때 다시 누르면 접는다(2026-07-30 사용자 지적: 두 번째 클릭이 안 먹었다).
    # 설명서(‘이 테마 기법에 대한 설명’)가 말하는 두 갈래를 옆에 단추로 둔다
    # (2026-08-01 사용자 지시). 어느 단추를 눌렀느냐에 따라 같은 자리의 표가 바뀐다.
    # 세 단추 모두 열려 있을 때 다시 누르면 접힌다.
    # 지금 어느 갈래를 보고 있는지 단추만 봐서는 알 수 없었다(2026-08-01 사용자 지적).
    # 열려 있는 갈래의 단추에는 앞에 ●를 붙이고, 아래 CSS가 그 단추를 밝게 칠한다.
    guest_mode = auth.is_guest()
    if guest_mode and st.session_state.get("j3_pullback_mode") not in ("breakout", "crash"):
        st.session_state["j3_pullback_open"] = False
    open_mode = (
        (st.session_state.get("j3_pullback_mode") or "기본")
        if st.session_state.get("j3_pullback_open") else None
    )
    # '눌림목 찾기'(옛 A 규칙)는 2026-08-06에 뺐다(사용자 지시).
    # 목적이 '상승장(신고가 눌림매수)'과 같은데 10년치로 재 보니 기준선을 못 이겼다 —
    # 평상시 100번 중 57번(기준선 57번), 급락장 54번(기준선 61번)으로 네 사건 모두 졌다.
    # 상위 8개만 추려도 55번이라 순위가 거꾸로 매겨졌다(docs/US_THREE_RULES_COMPARE.md).
    # 함수(find_pullback_stocks)는 지우지 않는다 — 한국테마(자비스4)가 아직 쓴다.
    mode_options = (
        ("breakout", "상승장 (신고가 눌림매수)", "j3_pullback_breakout"),
        ("crash", "급락 후 반등장 (낙폭종목)", "j3_pullback_crash"),
    )
    finder_cols = st.columns(len(mode_options))
    pressed = None
    for column, (mode, label, key) in zip(finder_cols, mode_options):
        with column:
            if st.button(("● " if open_mode == mode else "") + label, key=key):
                pressed = mode
        if open_mode == mode:
            # 열린 단추만 밝게 — 색이 아니라 테두리와 밝기로 갈라 색 규칙을 안 건드린다.
            st.markdown(
                f"<style>div[class*='st-key-{key}'] button {{"
                " outline: 3px solid #ffffff !important; outline-offset: 1px;"
                " filter: brightness(1.25) !important; }</style>",
                unsafe_allow_html=True,
            )
    if pressed:
        already_open = (
            st.session_state.get("j3_pullback_open")
            and st.session_state.get("j3_pullback_mode") == pressed
        )
        if already_open:
            # 닫기 — 조회도 rerun도 하지 않는다(2026-07-30 사용자 실측: 닫는 데 1.5초).
            st.session_state["j3_pullback_open"] = False
            st.session_state.pop("j3_pullback_selected_ticker", None)
        else:
            st.session_state["j3_pullback_open"] = True
            st.session_state["j3_pullback_mode"] = pressed
            st.session_state.pop("j3_pullback_selected_ticker", None)
            # **화면을 결과 자리로 살짝 내린다** (2026-08-28 상하님 지시 —
            # "상승장 신고가 눌림매수 클릭하면 두 번째 화면처럼 되는데 살짝
            # 내려라, 그러면 첫 번째 캡처 화면처럼 되게").
            # 단추가 화면 위쪽에 있어서 누르면 그 자리에 그대로 서 있었고,
            # 결과(나스닥 지수 줄·정식 후보)는 단추 여섯 개 아래에 있었다.
            scroll_to.request(st, "finder_top")
            # 폰·태블릿 뒤로가기 — 이 목록이 열린 것을 방문기록에 한 칸 쌓는다.
            # 이 단추는 _section_toggle을 안 거치므로 여기서 따로 알려야 한다.
            back_nav.opened(st, "j3_pullback_open")
            # **방금 찾아 둔 것이 있으면 다시 안 찾는다** (2026-08-22 상하님 지적
            # — "상승장 클릭도 조금 줄었지만 여전히 느리다").
            #
            # 닫았다 다시 열 때마다 200종목을 처음부터 다시 찾고 있었다. 5분 안에
            # 다시 열면 결과가 어차피 같다 — 이 화면의 순위 9는 2026-07-31부터
            # 이미 그렇게 돌고 있다(_kept_recently). 같은 장치를 여기에도 둔다.
            # 5분이 지나면 알아서 새로 찾는다.
            kept = (
                _kept_recently(f"j3_pullback_at_{pressed}")
                and isinstance(st.session_state.get(f"j3_pullback_kept_{pressed}"), dict)
            )
            if kept:
                st.session_state["j3_pullback_result"] = (
                    st.session_state[f"j3_pullback_kept_{pressed}"]
                )
            elif pressed == "breakout":
                # **순위 9가 만들어 둔 것을 그대로 쓴다** (2026-08-29 상하님 —
                # "상승장 신고가 눌림매수 첫 클릭하면 로딩 너무 오래 걸린다").
                # 여태 이 단추는 find_breakout_pullback_stocks 를 직접 불러
                # 200종목을 처음부터 다시 훑었다. 그 결과는 순위 9가 이미 만들어
                # `top_finder:상승장` 으로 5분간 기억해 두는데도 그것을 안 봤다 —
                # 같은 판에서 같은 계산을 두 번 한 셈이다. breakout_scan 이
                # 그 기억을 본다. 없으면 예전처럼 그때 찾으므로 늦어지지 않는다.
                with st.spinner("미국 대형주 200개에서 신고가 뒤 눌린 종목을 찾는 중입니다…"):
                    st.session_state["j3_pullback_result"] = j3data.breakout_scan()
            else:
                with st.spinner("미국 대형주 200개에서 고점 대비 낙폭이 큰 종목을 찾는 중입니다…"):
                    st.session_state["j3_pullback_result"] = (
                        j3data.find_crash_rebound_stocks()
                    )
            if not kept:
                found = st.session_state.get("j3_pullback_result")
                if isinstance(found, dict) and found.get("ok"):
                    st.session_state[f"j3_pullback_kept_{pressed}"] = found
                    st.session_state[f"j3_pullback_at_{pressed}"] = time.time()
                # 그날 것이 아직 없으면 여기서 한 판 남긴다(2026-08-09). 자동 저장의
                # 본체는 클라우드 작업이고, 이건 그것이 실패한 날을 메우는 보조다.
                picklist_ui.autosave("US", pressed, found)
    if not st.session_state.get("j3_pullback_open"):
        return
    result = st.session_state.get("j3_pullback_result")
    mode = st.session_state.get("j3_pullback_mode") or "기본"
    if mode in ("breakout", "crash") and isinstance(result, dict):
        _render_rulebook_finder(result, market, ranking, mode)
        return
    if result is None:
        return
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
    # 테마표·대장주표와 같은 이유로 한 줄을 세 칸으로만 나눈다 — 칸마다 요소를
    # 만들면 폰이 느려진다(2026-07-30 실측). 나머지 열 칸은 한 덩이로 그린다.
    row_widths = [widths[0], widths[1], sum(widths[2:])]
    rest_widths = widths[2:]
    # 머리글과 줄이 같이 밀려야 하므로 한 상자에 담는다(2026-07-25).
    table_box = st.container(key="j3_pullback_table")
    head = table_box.columns(row_widths)
    head[0].markdown("<div class='j3-th-head'>순위</div>", unsafe_allow_html=True)
    head[1].markdown("<div class='j3-th-head'>종목</div>", unsafe_allow_html=True)
    head[2].markdown(
        _flex_row(rest_widths, ["티커", "눌림 점수", "종목 조건점수", "신고가", "당일주가",
                                "고점 대비", "20일선 이격", "평균 거래대금", "소속 테마",
                                "테마 가산"], head=True),
        unsafe_allow_html=True,
    )

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
        cols = table_box.columns(row_widths)
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
            # 종목을 누르면 상세와 차트까지 한 번에 열린다(2026-08-09 상하님 지시
            # "모든 곳에 적용" — 상승장·급락 표는 이미 이렇게 돌고 있었다).
            for opened in ("j3_detail_open_pullback", "j3_intraday_open_pullback",
                           "j3_bundle_open_pullback"):
                st.session_state[opened] = True
            back_nav.opened(st, "j3_detail_open_pullback",
                            "j3_intraday_open_pullback", "j3_bundle_open_pullback")
            scroll_to.request(st, "detail_pullback")
            # **이 덩이만 다시 그린다.** scope를 안 주면 판 전체가 돈다.
            _rerun_here()
        if row.get("ticker") == selected_ticker:
            selected_css.append(
                f"div[class*='st-key-j3pbf_{index:02d}'] button "
                "{ background: rgba(192,132,252,.16) !important; "
                "border-left: 3px solid #c084fc !important; }"
            )
        # 종목 조건점수 — 아래 상세와 같은 값. 순위(눌림 점수)와 다른 것을 재는 점수라
        # 20위가 3위보다 높을 수 있다(2026-07-24 사용자 질문에 따라 표에 함께 표시).
        stock_score = float(
            j3data.analyze_pullback_stock(row, benchmark_ret20=spy_ret20_for_table).get("score") or 0
        )
        avg_text = f"${float(avg_value) / 1e6:,.0f}M" if avg_value is not None else "—"
        # 당일주가 — 가격과 등락을 두 줄로 쌓는다. 한 줄이면 좁은 화면에서 폭이 넘쳐
        # 옆 칸 값과 겹쳤다(2026-07-25). 등락은 미국장 색 규칙(+파랑 −빨강)이다.
        price_cell = (
            "<span style='display:inline-flex; flex-direction:column; align-items:center;"
            " line-height:1.12; font-weight:800; color:#e6e6e6'>"
            f"<span>{_price(row['metrics'].get('current'))}</span>"
            f"<span style='color:{_sign_color(row['metrics'].get('change_pct'))};"
            f" font-weight:800; font-size:.82rem'>{_pct(row['metrics'].get('change_pct'))}</span></span>"
        )
        cols[2].markdown(
            _flex_row(rest_widths, [
                html.escape(str(row.get("ticker") or "—")),
                "<div class='j3-barwrap'><div class='j3-bar'>"
                f"<div class='j3-bar-fill j3-bar-green' style='width:{max(0, min(score, 100)):.0f}%'></div>"
                f"</div><span class='j3-bar-num'>{score:.1f}</span></div>",
                "<div class='j3-barwrap'><div class='j3-bar'>"
                f"<div class='j3-bar-fill' style='width:{max(0, min(stock_score, 100)):.0f}%;"
                f" background:#c084fc'></div></div>"
                f"<span class='j3-bar-num'>{stock_score:.1f}</span></div>",
                f"<span class='j3-green'>{int(quality.get('high52_days_ago') or 0)}일 전</span>",
                price_cell,
                f"<span class='{_sign_class(from_high)}' style='font-weight:800'>{_pct(from_high)}</span>",
                f"<span class='{_sign_class(gap)}' style='font-weight:800'>{_pct(gap)}</span>",
                f"<span class='j3-green'>{avg_text}</span>",
                f"<span class='j3-pull-theme' title='{html.escape(themes)}'>{html.escape(themes)}</span>",
                f"<span class='j3-pull-amber'>{theme_bonus:.1f}/5</span>",
            ]),
            unsafe_allow_html=True,
        )
    if selected_css:
        st.markdown(f"<style>{''.join(selected_css)}</style>", unsafe_allow_html=True)
    with st.expander("표 읽는 법 보기", expanded=False):
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


def _warm_finders() -> None:
    """상승장 한 벌을 뒤에서 미리 만들어 둔다 (2026-08-29 상하님 지시).

    **이미 받아 둔 자료만 쓴다** — 네트워크를 한 번도 안 쓰므로 이 판에서
    상하님이 기다리실 것을 밀어내지 않는다(jarvis3_data.warm_breakout_scan).
    옛 모듈이 프로세스에 남아 이 이름이 없어도 화면은 그대로 돈다.
    """
    warm = getattr(j3data, "warm_breakout_scan", None)
    if not callable(warm):
        return
    try:
        warm()
    except Exception:
        pass


def _autosave_theme15() -> None:
    """저장해 둔 목록의 「상위 테마 5개 · 각 종목 1~3위」를 **화면에서도** 남긴다.

    2026-08-29 상하님 지적 — *"08-28일자에 상위 테마 5개 각 종목 1~3위 15종목
    리스트가 왜 또 빠지냐!"*

    **까닭은 화면에 저장하는 자리가 아예 없었기 때문이다.** 2026-08-15에 이 갈래를
    만들 때 클라우드 수집기(picklist_collector)에만 넣고 화면 쪽 보조 저장에는
    안 넣었다. 화면의 `autosave` 는 순위 9와 상승장·급락 셋뿐이었다.
    그래서 **깃허브 예약이 제때 뜬 날에만** 15줄이 들어가고, 예약이 밀려 화면
    자동 저장만 걸린 날에는 이 갈래가 통째로 빠졌다 — 8/26과 8/28이 그랬다.

    **저장할 때만 만든다.** 이 목록을 만드는 데는 대장주 조회 다섯 판이 든다.
    그래서 먼저 `needs_autosave` 로 물어보고 남길 때만 만든다 — 장이 끝난 뒤
    하루에 한 번이다.

    **그 한 번도 뒤 일꾼에게 맡긴다** (2026-08-29 · CLAUDE.md 0-0).
    처음에는 화면 그리는 길에 그대로 두었는데, 그러면 그날 딱 한 번이라도
    상하님이 대장주 조회 다섯 판을 통째로 기다리셔야 한다. 실제로 화면 시험이
    그 조회를 기다리다 시간 초과로 깨졌다 — 상하님 폰에서는 그것이 '오늘따라
    시장분석이 안 열린다'로 보인다.
    **세션에서 읽을 것은 일꾼을 띄우기 전에 다 꺼내 둔다** — 세션 기억은
    뒤 일꾼이 만지면 안 된다.

    **수집기가 부르는 함수를 같은 인자로 부른다**(CLAUDE.md 10-1). 여기에 고르는
    계산을 따로 쓰면 저장된 목록이 수집기가 찍은 것과 조용히 갈라진다.

    실패해도 조용히 넘어간다 — 이것 때문에 화면이 죽으면 안 된다.
    """
    try:
        if not picklist_ui.needs_autosave("US", "theme15"):
            return
        rows = list((st.session_state.get("j3_theme_rankings") or {}).get("rows") or [])
        if not rows:
            return           # 테마 자료를 못 받은 판이다. 다음 판에 다시 본다.
        overview = st.session_state.get("j3_market_overview") or {}
        score = float(overview.get("score") or 0)
    except Exception:
        return

    def _save() -> None:
        try:
            picklist_ui.autosave("US", "theme15",
                                 j3data.find_theme_top_picks(rows, market_score=score))
        except Exception:
            pass             # 못 남겨도 화면은 그대로다. 클라우드 수집기가 또 찍는다.

    try:
        threading.Thread(target=_save, name="theme15-save", daemon=True).start()
    except Exception:
        pass


def _render_existing_theme_content() -> None:
    # 새 껍데기 표식 (2026-09-03). 규칙은 길잡이가 이미 내보냈고, 이 표식이
    # 있어야 `body:has(.j6-skin)` 규칙이 이 화면에도 걸린다.
    st.markdown('<div class="j6-skin"></div>', unsafe_allow_html=True)
    st.markdown(
        # 두 표 모두 세로로 쌓지 않고 옆으로 밀어 본다(2026-07-25 사용자 지시).
        # 머리글을 숨기던 규칙도 뺐다 — 숨기면 '종목·눌림 점수'가 안 보인다.
        # 순위 7 표를 세로로 쌓던 규칙(table_css·hide_own_header)은 2026-08-01에 뺐다.
        # 사용자 지시 — 나머지 세 표(오늘의 강한테마·테마 종목 1~6위·눌림목 찾기)처럼
        # 표를 원래 폭으로 두고 손가락으로 옆으로 밀어서 보게 한다. 그 규칙은
        # 페이지 위 <style>의 .st-key-j3_top7_table 줄에 있다.
        mobile_ui.page_css(),
        unsafe_allow_html=True,
    )
    # 종목을 누르면 상세 자리로 내려가는 장치의 자리 표시 규칙(2026-08-09).
    st.markdown(scroll_to.CSS, unsafe_allow_html=True)
    # 종목 브리핑에서 들어온 미국 시장분석 화면만 위쪽 여백을 줄인다.
    # 공용 method_help.py와 한국테마 화면에는 퍼지지 않게 페이지 표식을 쓴다.
    #
    # ⚠ 아래 <style> 안에 **빈 줄을 넣지 않는다.** 2026-08-26에 거기에 설명을
    # 적으면서 주석 가운데 빈 줄을 하나 넣었더니 화면이 깨졌다(상하님 캡처 —
    # CSS 글자가 화면에 그대로 쏟아졌다).
    #
    # 이유 — 이 덩어리는 <div class="j3-market-top">로 시작한다. 마크다운은
    # <div> 로 시작한 HTML 덩어리를 **빈 줄에서 끝낸다.** 그래서 빈 줄 뒤부터는
    # <style> 안이 아니라 그냥 글로 읽혀 화면에 그대로 그려졌다. 그 글 안의
    # 역따옴표는 회색 상자로, 별표 두 개는 굵은 글씨로 바뀌어 있었다.
    # (<style> 로 **시작하는** 덩어리는 </style> 를 만나야 끝나므로 빈 줄이
    #  있어도 괜찮다. 이 덩어리만 앞에 <div> 가 붙어 있어서 다르다.)
    #
    # 설명은 전부 여기 파이썬 주석에 쓴다 — 여기서는 무엇을 써도 안전하다.
    #
    # ── 화면 맨 위 빈자리 224px의 진짜 이유 (2026-08-26 실측) ─────────────────
    # 이 화면 맨 위에는 **눈에 안 보이는 <style> 덩어리가 14개** 줄지어 있다.
    # 높이는 0이지만 스트림릿이 칸과 칸 사이에 16px씩 틈을 넣기 때문에
    # 14 × 16px = 224px 이 통째로 빈 자리가 된다. 상하님 지적 —
    # "스마트폰·태블릿 상단에 여백 좀 (줄이라고) 하라니깐".
    #
    # **<style> 하나만 들어 있는 칸**만 없앤다. `style:only-child` 는 그 칸에
    # style 말고는 아무것도 없다는 뜻이라, 보이는 것을 잘못 숨길 수가 없다.
    # 글이 같이 든 칸은 자식이 둘이라 이 조건에 안 걸린다.
    # 숨겨도 <style> 안의 규칙은 그대로 작동한다 — 화면에 안 그려질 뿐이다.
    # `.j3-market-top` 은 표식일 뿐이라 같이 없앤다(body:has 는 숨겨도 찾는다).
    # `.jarvis-anchor` 는 **남긴다** — 숨기면 '맨 위로' 가 작동하지 않는다.
    #
    # ── 폰·태블릿은 위를 **58px** 띄운다 (2026-08-27 상하님 지적) ─────────────
    # 상하님 — "시장분석 맨 위 화면 아직도 그거 해결 안 하고 있다."
    #
    # 상하님 캡처 맨 위에 「Fork」와 GitHub 표시가 있다. 그건 온라인 서비스가
    # **앱 위에 덮어 놓는 띠**다. 내 쪽 주소(/~/+/)로 열면 그 띠가 없어서 여태
    # 못 봤다. 폰 크기 열한 가지(360·375·390·412·600·690·800·1138·1240·1400·
    # 1920)를 다 재도 줄은 늘 y=10 에 있었는데, 상하님 화면에서는 그 y=10 이
    # **띠 밑**이었다.
    #
    # 2026-08-25 캡처에는 위에 224px 빈자리가 있어 단추가 띠 아래로 밀려나
    # 보였다. 그 빈자리를 없애자 단추가 띠 밑으로 들어가 가려졌다.
    # 그래서 띠 높이만큼만 띄운다 — 224px 이 아니라 68px 이다.
    # (58px 로 했더니 「한국테마 →」 사각 테두리 위가 조금 잘렸다 —
    #  상하님 실물 확인. 10px 더 내렸다.)
    # 노트북(1200px 이상)은 10px 그대로다 — 거기서는 띠가 안 덮는다.
    #
    # ── 위 여백은 **0이 아니라 10px** (2026-08-27 상하님 지시) ────────────────
    # 상하님 — "맨 위에 화면 사라진 거 나타나게 하되, 위에 여백을 너무 많이
    # 두지 말라." 0으로 두면 맨 위 두 단추(「🌏 한국테마 →」·「📘 이 테마 설명」)가
    # 화면 끝에 딱 붙어, 폰 브라우저 주소창이 오르내릴 때 가려진다.
    # 예전 224px 과는 비교가 안 되는 10px 이다.
    st.markdown(
        """
        <div class="j3-market-top"></div>
        <style>
        body:has(.j3-market-top) [data-testid="stMainBlockContainer"],
        body:has(.j3-market-top) .block-container { padding-top:0!important; }
        body:has(.j3-market-top) [data-testid="stElementContainer"]:has(> [data-testid="stMarkdown"] style:only-child),
        body:has(.j3-market-top) [data-testid="stElementContainer"]:has(> [data-testid="stMarkdown"] .j3-market-top) {
          display:none!important;
        }
        body:has(.j3-market-top) .st-key-jarvis_method_help_row {
          gap:.35rem!important;
          row-gap:.35rem!important;
          margin-top:-1rem!important;
          margin-bottom:0!important;
        }
        @media (max-width:1200px) {
          body:has(.j3-market-top) .st-key-jarvis_method_help_row {
            margin-top:-1rem!important;
          }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    # ── 시장분석 화면도 관심종목 화면과 **같은 옷**을 입는다 (2026-08-28 상하님 지시)
    #
    # 상하님 — "미국테마를 캡쳐4처럼 디자인을 좀 바꾸고 싶다. 테두리를 캡쳐4처럼
    # 하고 싶다는 이야기이야."
    #
    # 여태 한 페이지 안에서 두 화면이 서로 다른 옷을 입고 있었다. 관심종목 쪽은
    # 금색 테두리를 두른 남색 카드(.j3b-card)인데, 시장분석 쪽 지수 칸은 테두리도
    # 바탕도 없는 맨 글자였다. 같은 앱으로 안 보인다.
    #
    # 색·굵기·둥글기를 .j3b-card 에서 그대로 가져온다. **한 곳에서 베껴 오지
    # 않고 여기 다시 적는 까닭** — 저쪽은 .j3b-home 표식이 있어야 걸리는 규칙이라
    # 이 화면에는 안 걸린다. 표식을 여기 붙이면 카드·격자 규칙까지 통째로 따라와
    # 지수 칸이 246px 짜리 카드가 된다.
    #
    # **값·숫자·순서는 하나도 안 건드린다** — 옷만 갈아입힌다.
    st.markdown(
        """
        <style>
        /* ── 맨 위 검은 띠를 없앤다 (2026-08-28 상하님 지적) ────────────────────
           상하님 — "이거 왜 짤리지 비교화면 봐라... 저거 지난번에도 무슨 문제
           있었다 다시 잘봐라 **위에 뭔가 있다**."
           그 '뭔가'는 스트림릿이 화면 맨 위에 **띄워 놓는 띠**(stHeader)다.
           온라인에서는 거기에 「Fork」와 GitHub 표시까지 얹힌다.
           이 띠는 자리를 차지하는 것이 아니라 **덮는다.** 그래서 배너를 맨 위로
           올리자 배너 윗부분(「JARVIS 3」 줄)이 띠 밑으로 들어가 잘렸다.
           2026-08-27에 여백 68px 을 넣어 막았던 것이 바로 이것이었는데, 나는 그
           여백이 하던 일을 배너가 대신한다고 잘못 봤다 — 덮는 것은 밑에 무엇을
           놓아도 안 밀린다.
           **관심종목 화면은 이 띠를 아예 없앤다**(body:has(.j3b-home) 쪽에 같은
           줄이 있다). 그래서 거기 배너는 안 잘린다. 같게 맞춘다.
           왼쪽 메뉴는 이 화면에서 이미 감춰 두었으므로 잃는 것이 없다. */
        body:has(.j3-market-top) [data-testid="stHeader"] { display:none !important; }
        body:has(.j3-market-top),
        body:has(.j3-market-top) .stApp { background:#020b1e !important; }
        body:has(.j3-market-top) .stApp {
            background-image:
                radial-gradient(circle at 51% 1%, #0c3d78 0, transparent 27%),
                linear-gradient(160deg, #020a1c 0%, #031a3b 53%, #020b21 100%) !important;
        }

        /* 지수 칸·게이지 상자·나스닥 낙폭 줄 — 관심종목 카드와 같은 테두리 */
        body:has(.j3-market-top) .j3-top-cell,
        body:has(.j3-market-top) .fg-box,
        body:has(.j3-market-top) .j3-ndd {
            background: linear-gradient(145deg, #06345f 0%, #03264a 58%, #001d3c 100%);
            border: 1px solid #bf9254a8;
            border-radius: 17px;
            box-shadow: inset 0 1px #7bc9ff35, 0 6px 16px #0006;
            padding: 12px 13px 11px;
            box-sizing: border-box;
        }

        /* 칸에 테두리가 생겼으니 칸 사이는 좁혀도 갈린다. 예전 2rem 은 테두리가
           없을 때 칸을 갈라 보이게 하려던 것이다. */
        body:has(.j3-market-top) .j3-top-row { gap: 0.85rem; }

        /* 손을 올리면 살짝 밝아진다 — 관심종목 카드와 같은 결이다. */
        body:has(.j3-market-top) .j3-top-cell:hover {
            border-color: #d8ab68; box-shadow: inset 0 1px #7bc9ff55, 0 8px 20px #0008;
        }

        /* 구분선이 차지하는 자리를 줄인다 (2026-08-28 상하님 지시 — "여백 두지
           말고 위로 올려라"). 줄 자체는 남긴다 — 「미국 전체시장 판단」과
           「미국장 시장 상태」를 가르는 표시다. 위아래 여백만 좁힌다.
           실측 85px → 36px.
           **이 규칙은 여기(<style>로 시작하는 덩어리) 있어야 한다.** 위의
           `j3-market-top` 덩어리는 <div>로 시작해서 주석을 넣으면 안 된다 —
           2026-08-26에 거기 주석을 넣었다가 CSS가 글자로 쏟아졌다. */
        body:has(.j3-market-top) hr { margin: .35rem 0 !important; }

        /* 접었다 펴는 설명 상자도 같은 테두리로 맞춘다. */
        body:has(.j3-market-top) [data-testid="stExpander"] details {
            border: 1px solid #bf925266 !important;
            border-radius: 15px !important;
            background: linear-gradient(145deg, #06304f26, #001d3c40) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    # 뒤로가기를 눌렀을 때 돌아올 **화면 맨 위** 자리(2026-08-21 상하님 지시 —
    # "한번 누르면 밑으로 화면 내린 부분에서 바로 위로").
    scroll_to.anchor(st, "top")
    # ── 시장분석 **맨 위**의 눈밭 캠프 배너 (2026-08-28 상하님 지시) ──────────
    # 상하님 — "시장분석 맨 위에 넣어라."
    # 상하님이 그록·제미나이로 만드신 영상 위에 6개월 일봉 봉차트를 얹은 그림이다.
    # 봉은 **지어낸 값**이라 숫자를 한 개도 안 적는다. 자세한 것은 hero_banner.py.
    # 두 단추(「🌏 한국테마 →」·「📘 이 테마 설명」)보다 먼저 그려야 맨 위에 선다.
    if hero_banner.render(st, refresh_key="j3hero_refresh", mark="6"):
        # ↻ 를 누르셨다. 관심종목 배너의 ↻ 와 **똑같이** 움직인다 —
        # 서버가 담아 둔 것을 비우고 화면을 통째로 새로 연다
        # (2026-08-28 상하님 — "그거 누르면 리셋 되던데?").
        st.session_state["j3b_hard_reload"] = True
        for _forget in (getattr(j3data, "clear_runtime_cache", None),
                        getattr(briefing_news, "clear_cache", None)):
            try:
                if _forget:
                    _forget()
            except Exception:
                pass          # 못 비워도 화면은 새로 연다
        st.rerun()
    # 최상단 오른쪽에 '이 테마 설명'을 둔다(2026-07-29 사용자 지시).
    # 제목보다 먼저 그려야 화면 맨 위 오른쪽에 붙는다.
    method_help.render(st, "US")
    # 맨 위 제목은 뺐다(2026-07-30 사용자 지시) — 사이드바에 같은 이름이 있고
    # 첫 화면 높이만 먹었다. 페이지 이름은 파일명이 그대로 쓴다.
    try:
        j3store.ensure_tables()
    except Exception as exc:
        st.error(f"자비스3 기록 테이블 준비 실패: {_safe_error_text(exc)}")

    # 뒤로가기로 무언가 닫혔으면 화면을 맨 위로 올린다 — 상하님이 아래까지
    # 내려가 보시던 자리에 그대로 서 있으면 아무 일도 안 일어난 것처럼 보인다.
    if _backnav_closed:
        scroll_to.request(st, "top")
    _render_market_overview()
    market = st.session_state.get("j3_market_overview") or {"ok": False, "score": 0, "regime": "자료부족"}
    st.divider()
    # 미국장 선행신호 카드만 자비스3에 둔다(2026-07-22 사용자 정정: 한국장 수급 카드는
    # 미국 페이지에 어울리지 않으므로 자비스4(국내)에 넣는다). 같은 렌더러·세션 상태를
    # 재사용하므로 시장판단 페이지와 판정이 항상 일치한다.
    # 계기판만 먼저 보이고 나머지는 눌러서 연다(2026-08-28 상하님 지시).
    # 시장 판단 화면은 예전처럼 다 펴 둔다 — 거기는 화면 하나가 통째로 이 카드다.
    market_signal_ui.render_us_market_signal_card(foldable=True)
    # 폰에서 화면만 먹던 상단 '테마·종목 / 매수 기록 / 판정 기준' 선택줄은
    # 보이지 않고 미국테마 본화면을 바로 그린다.
    _render_radar_tab(market)
    # 저장해 둔 목록의 「상위 테마 5개」를 아직 안 남겼으면 여기서 남긴다.
    # **화면을 다 그린 뒤**다 — 앞에 두면 보실 것이 그만큼 밀린다.
    _autosave_theme15()
    # 상승장 한 벌을 **뒤 일꾼이** 미리 만들어 둔다 (2026-08-29).
    #
    # 상하님 — "상승장 신고가 눌림매수 첫 클릭하면 로딩 너무 오래 걸린다."
    # 이 미리 만들기는 여태 관심종목 화면에만 있었다(_warm_after_news). 그래서
    # 시장분석으로 바로 들어오시면 아무것도 안 데워져 있어, 첫 클릭이 200종목
    # 스캔을 통째로 기다렸다.
    #
    # **맨 끝에서 부른다.** 여기까지 오면 화면은 다 그려졌고, 이 함수는 뒤
    # 일꾼을 띄우고 바로 돌아온다. 앞에 두면 상하님이 보실 것이 밀린다
    # (CLAUDE.md 0-0 — 2026-08-26에 그 실수를 했다).
    # **네트워크를 한 번도 안 쓴다** — 이 화면을 그리며 이미 받아 둔 200종목
    # 2년치와 나스닥 이력만 다시 읽어 계산만 해 둔다. 공책에 없으면 그 자리에서
    # 빈손으로 돌아가고, 그때는 예전처럼 단추가 그때 받는다.
    # 5분에 한 번만 돈다(warm_breakout_scan 안의 자물쇠).
    _warm_finders()


def _briefing_secret(name: str) -> str:
    """키가 없거나 secrets 접근이 막혀도 화면은 정상 표시한다."""
    try:
        return str(st.secrets.get(name) or os.getenv(name) or "").strip()
    except Exception:
        return str(os.getenv(name) or "").strip()


@st.cache_data(show_spinner=False)
def _briefing_asset_uri(filename: str) -> str:
    """첫 화면 전용 로컬 장식·로고를 HTML 안에서 안전하게 쓴다.

    외부 hotlink 없이 배포본에도 같은 자산을 보여 주기 위한 data URI다.
    """
    asset = Path(__file__).resolve().parents[1] / "assets" / "briefing" / filename
    if not asset.is_file():
        return ""
    mime = {".svg": "image/svg+xml", ".webp": "image/webp"}.get(asset.suffix.lower(), "image/png")
    encoded = base64.b64encode(asset.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _briefing_logo_uri(ticker: str) -> str:
    return _briefing_asset_uri(f"{ticker.upper()}.svg")


def _briefing_css() -> None:
    st.markdown(
        """
        <style>
        /* 종목 브리핑 첫 화면: 화면 셸만 교체하고 기존 데이터 흐름은 유지한다. */
        /* PC에서는 **화면 폭에 따라 늘어난다** (2026-08-27 상하님 지시 —
           "노트북은 그냥 화면 크기 비율대로 하면 안 되나? 노트북은 화면이 더
           크고 16:9 화면이니, 게다가 화면 설정도 모니터에 따라 다르니 신축성
           있게 해야 되지 않나?"). 맞는 말씀이다.
           예전에는 PC에서도 430px 짜리 폰 화면으로 못박아 두었다.
           이제 폭은 화면을 따라가고, 카드 칸 수도 폭이 정한다 — 한 칸이
           340px 아래로 좁아지지 않는 선에서 들어갈 만큼 들어간다.
           1240px 이면 3칸 · 1600px 이면 4칸 · 1920px 이면 5칸이다. */
        body:has(.j3b-home), body:has(.j3b-home) .stApp { background:#020b1e !important; }
        body:has(.j3b-home) .stApp { background-image:radial-gradient(circle at 51% 1%,#0c3d78 0,transparent 27%),linear-gradient(160deg,#020a1c 0%,#031a3b 53%,#020b21 100%) !important; }
        body:has(.j3b-home) [data-testid="stMainBlockContainer"],body:has(.j3b-home) .block-container { max-width:min(1500px,94vw) !important;padding:0 10px 94px !important;margin:0 auto !important; }
        body:has(.j3b-home) .block-container > .stVerticalBlock { gap:0 !important; }
        body:has(.j3b-home) [data-testid="stHeader"] { display:none !important; }
        .j3b-app { color:#fbf5e9;font-family:"Noto Sans KR","Malgun Gothic",sans-serif; }
        .j3b-hero { position:relative;height:236px;overflow:hidden;border-radius:0 0 24px 24px;padding:26px 23px;background:radial-gradient(circle at 16% 9%,#fff6d6 0 1.6px,transparent 2.4px),radial-gradient(circle at 35% 17%,#ffd681 0 1.2px,transparent 1.9px),radial-gradient(circle at 57% 11%,#ffffff 0 1.6px,transparent 2.4px),radial-gradient(circle at 79% 18%,#ffd681 0 1.2px,transparent 1.9px),radial-gradient(circle at 93% 7%,#fff2c1 0 1.5px,transparent 2.3px),radial-gradient(circle at 8% 26%,#ffe9a8 0 1px,transparent 1.7px),radial-gradient(circle at 24% 34%,#ffffff 0 1.1px,transparent 1.8px),radial-gradient(circle at 45% 6%,#ffd681 0 1px,transparent 1.7px),radial-gradient(circle at 66% 25%,#fff6d6 0 1.3px,transparent 2px),radial-gradient(circle at 88% 31%,#ffffff 0 1px,transparent 1.7px),radial-gradient(circle at 5% 14%,#ffd681 0 1px,transparent 1.7px),radial-gradient(circle at 50% 22%,#ffe9a8 0 1px,transparent 1.7px),radial-gradient(circle at 72% 8%,#ffffff 0 1.2px,transparent 1.9px),radial-gradient(circle at 30% 4%,#fff2c1 0 1px,transparent 1.7px),linear-gradient(158deg,#01091f 0%,#03204d 42%,#063a7d 72%,#04173a 100%);border:1px solid #8fc8f088;box-shadow:inset 0 -18px 31px #00132da8,0 9px 22px #0008; }
        .j3b-hero:before { content:"";position:absolute;z-index:0;width:630px;height:210px;left:50%;bottom:-142px;transform:translateX(-50%);border-radius:50%;background:radial-gradient(ellipse at 50% 0,#5fd6ff 0,#12a0e8 18%,#0a63b4 40%,#063666 62%,#01142e 76%);border-top:2.5px solid #8ce6ff;box-shadow:0 -14px 44px #14a0f0c4,inset 0 8px 26px #9fe8ff33; }
        .j3b-hero:after { content:"";position:absolute;z-index:1;left:96px;bottom:38px;width:172px;height:30px;opacity:.9;background:repeating-linear-gradient(90deg,transparent 0 4px,#e2b853 4px 6px,transparent 6px 11px);clip-path:polygon(0 100%,0 75%,5% 75%,5% 25%,9% 25%,9% 68%,15% 68%,15% 5%,20% 5%,20% 70%,28% 70%,28% 36%,34% 36%,34% 72%,42% 72%,42% 13%,49% 13%,49% 72%,56% 72%,56% 32%,62% 32%,62% 70%,70% 70%,70% 18%,77% 18%,77% 67%,85% 67%,85% 42%,92% 42%,92% 72%,100% 72%,100% 100%); }
        .j3b-head-copy,.j3b-head-actions,.j3b-hero-catbus { position:absolute;z-index:3; }.j3b-head-copy{left:23px;top:29px}.j3b-title{margin:0!important;font-size:39px!important;line-height:1!important;font-weight:900!important;letter-spacing:-2.4px!important;color:#fff8e9!important;text-shadow:0 2px 6px #000!important}.j3b-title b{color:#78ccff!important}.j3b-sub{margin:10px 0 0!important;color:#beeaff!important;font-size:21px!important;font-weight:800!important;letter-spacing:-1.4px!important}.j3b-head-actions{right:16px;top:22px;display:flex;gap:8px}.j3b-round,.j3b-live{height:43px;display:flex;align-items:center;justify-content:center;border:1px solid #c89550;border-radius:24px;background:#061d40dd;color:#fff8e8;box-shadow:0 2px 8px #0007}.j3b-round{width:43px;font-size:26px}.j3b-live{padding:0 13px;gap:7px;font-size:15px;font-weight:800}.j3b-live i{width:10px;height:10px;border-radius:50%;background:#64d84d;box-shadow:0 0 8px #4cf059;display:block}.j3b-hero-catbus{right:-5px;bottom:8px;width:169px;height:auto;filter:drop-shadow(0 5px 6px #000b)}/* 견본(visual_reference.png)에서 잘라 낸 밤하늘 장면. 지구·도시·구름·고양이버스가   한 그림에 다 들어 있어 CSS로 그리던 지구와 도시는 감춘다(2026-08-26 상하님 지시 —   "맨 위에 디자인 지피티 챗이 디자인한 것 그대로"). */.j3b-hero-scene{position:absolute;z-index:1;right:-4%;bottom:-1px;width:116%;max-width:none!important;height:auto;pointer-events:none}
        /* ── 고양이버스를 도는 회사 로고 (2026-08-28 상하님 지시) ───────────
           팔이 돌면서 로고를 끌고 다닌다. 팔을 세로로 눌러(scaleY .32) 동그라미를
           타원으로 만들고(.23), 로고 쪽에서 거꾸로 돌고 거꾸로 늘려 로고만 똑바로 선다.
           눌린 값 .23 은 **로고가 배너 밖으로 안 잘리게** 실물에서 재어 정했다 —
           .32 로 두니 폭 1370px 화면에서 아래쪽 로고가 21px 잘렸다.
           아래쪽 반 바퀴는 버스 앞(z-index 2 · 크고 또렷), 위쪽 반 바퀴는 버스
           뒤(z-index 0 · 작고 흐릿)다. 버스 그림이 1이라 그 사이로 지나간다.
           제목·↻ 단추는 3이라 로고가 그 위를 덮지 않는다.
           가로 반지름을 min(42%,250px) 로 묶어 둔다 — 안 묶으면 노트북에서
           타원이 배너보다 높아져 위아래가 잘린다. */
        .j3b-orbit{position:absolute;inset:0;pointer-events:none}
        .j3b-orbit:before{content:"";position:absolute;left:50%;top:50%;width:min(84%,500px);aspect-ratio:1/.23;transform:translate(-50%,-50%);border:1px solid #8fc8f026;border-radius:50%;box-shadow:inset 0 0 26px #4da6ff12}
        .j3b-orbit-arm,.j3b-orbit-pod{position:absolute;width:100%;height:0;transform-origin:0 0}
        .j3b-orbit-arm{left:50%;top:50%;animation:j3b-orbit-arm 26s linear infinite,j3b-orbit-depth 26s linear infinite}
        .j3b-orbit-pod{left:0;top:0;animation:j3b-orbit-pod 26s linear infinite}
        .j3b-orbit-logo{position:absolute;left:0;top:0;display:flex;flex-direction:column;align-items:center;gap:3px;animation:j3b-orbit-logo 26s linear infinite}
        .j3b-orbit-logo .j3b-logo{width:34px;height:34px;border-radius:10px;box-shadow:inset 0 1px #b4efff77,0 3px 9px #000a}
        .j3b-orbit-tag{font-size:9px;font-weight:900;letter-spacing:-.2px;color:#dbeeff;text-shadow:0 1px 3px #000c;white-space:nowrap}
        @keyframes j3b-orbit-arm{from{transform:scaleY(.23) rotate(0deg)}to{transform:scaleY(.23) rotate(360deg)}}
        @keyframes j3b-orbit-pod{from{transform:translateX(min(42%,250px)) rotate(0deg) scaleY(4.348)}to{transform:translateX(min(42%,250px)) rotate(-360deg) scaleY(4.348)}}
        @keyframes j3b-orbit-depth{0%,49.99%{z-index:2}50%,100%{z-index:0}}
        @keyframes j3b-orbit-logo{0%{transform:translate(-50%,-50%) scale(.84);opacity:.75}25%{transform:translate(-50%,-50%) scale(1.18);opacity:1}50%{transform:translate(-50%,-50%) scale(.84);opacity:.75}75%{transform:translate(-50%,-50%) scale(.6);opacity:.4}100%{transform:translate(-50%,-50%) scale(.84);opacity:.75}}
        @media (max-width:600px){.j3b-orbit-logo .j3b-logo{width:26px;height:26px;border-radius:8px}.j3b-orbit-tag{font-size:8px}}
        /* 움직임을 줄여 달라고 해 둔 기기에서는 멈춰 세운다. 시작 시각이 저마다
           달라 멈춰도 로고가 궤도에 고르게 흩어져 있다. */
        @media (prefers-reduced-motion:reduce){.j3b-orbit-arm,.j3b-orbit-pod,.j3b-orbit-logo{animation-play-state:paused}}.j3b-hero:has(.j3b-hero-scene):before,.j3b-hero:has(.j3b-hero-scene):after{display:none}
        .j3b-section {display:flex;align-items:center;gap:8px;color:#f8f4e9;margin:18px 4px 9px;font-size:20px;font-weight:850;letter-spacing:-1.2px}.j3b-section .j3b-section-icon{width:29px;height:29px;display:inline-flex;align-items:center;justify-content:center;border-radius:50%;background:linear-gradient(135deg,#1cc9ff,#1265e9);box-shadow:inset 0 0 0 3px #d3f6ff;font-size:0}.j3b-section .j3b-section-icon:after{content:"";width:12px;height:12px;border:2px solid #f3fbff;border-radius:50%;box-sizing:border-box}.j3b-section .j3b-more{margin-left:auto;color:#e7e2d8;font-size:14px;font-weight:500}.j3b-section .j3b-flag{font-size:23px;line-height:1;filter:drop-shadow(0 1px 2px #0009)}.j3b-section.search .j3b-section-icon{background:transparent;box-shadow:none;border:3px solid #2ebfff}.j3b-section.search .j3b-section-icon:after{width:10px;height:10px;border-color:#2ebfff}.j3b-section.search .j3b-section-icon:before{content:"";width:11px;height:3px;position:absolute;transform:translate(11px,12px) rotate(48deg);background:#2ebfff;border-radius:2px}
        div.st-key-j3b_selected_heading{position:relative}div.st-key-j3b_go_market{position:absolute!important;right:0;top:16px;z-index:4}div.st-key-j3b_go_market button{border:0!important;background:transparent!important;color:transparent!important;width:68px!important;min-height:28px!important;padding:0!important;box-shadow:none!important}
        .j3b-news{min-height:53px;display:flex;align-items:center;gap:10px;background:linear-gradient(90deg,#062947ed,#042243f3);border:1px solid #bd905266;border-radius:17px;margin:7px 0;padding:8px 13px;color:#f7f4ed;font-size:14px;line-height:1.27;box-shadow:inset 0 1px #6aaee52b}.j3b-news-icon{width:31px;height:31px;border-radius:50%;display:grid;place-items:center;background:#0b3a48;color:#7ee86a;font-size:17px;flex:0 0 auto}.j3b-news-dot{width:14px;height:14px;margin-left:auto;border-radius:50%;flex:0 0 auto}.j3b-news-dot.positive{background:#79d955}.j3b-news-dot.negative{background:#f34b3f}.j3b-news-dot.neutral{background:#ffc144}.j3b-news small{display:none}
        .j3b-card{height:246px;background:linear-gradient(145deg,#06345f 0%,#03264a 58%,#001d3c 100%);border:1px solid #bf9254a8;border-radius:17px;padding:12px 11px 10px;margin:0 0 10px;box-shadow:inset 0 1px #7bc9ff35,0 6px 16px #0006;position:relative;overflow:hidden}.j3b-card:after{content:"";position:absolute;right:-28px;bottom:-55px;width:130px;height:96px;border-radius:50%;background:radial-gradient(ellipse at 32% 24%,#0e5a843d,transparent 70%);pointer-events:none}.j3b-card-top{display:flex;align-items:flex-start;gap:8px;min-height:49px}.j3b-logo{width:48px;height:48px;border-radius:12px;display:grid;place-items:center;background:linear-gradient(145deg,#216eab,#052b55);box-shadow:inset 0 1px #b4efff77,0 2px 5px #0008;overflow:hidden;flex:0 0 auto}.j3b-logo img{width:72%;height:72%;object-fit:contain;filter:brightness(0) invert(1)}.j3b-logo-text{display:grid;place-items:center;width:100%;height:100%;color:#f4faff;font-weight:900;font-size:.62em;letter-spacing:-.03em}.j3b-logo.photo{background:linear-gradient(145deg,#ffffff,#dde6f3)!important}.j3b-logo.photo img{width:80%;height:80%;object-fit:contain;filter:none!important}.j3b-logo.nvda{background:linear-gradient(145deg,#7bbf35,#0c5b2e)}.j3b-logo.tsla{background:linear-gradient(145deg,#ed4b42,#a40d13)}.j3b-logo.pltr{background:linear-gradient(145deg,#f2ede2,#aca69d)}.j3b-logo.pltr img{filter:none}.j3b-logo.amd,.j3b-logo.aapl{background:linear-gradient(145deg,#5f6870,#151a20)}.j3b-logo.meta{background:linear-gradient(145deg,#1768d6,#06347f)}.j3b-logo.avgo{background:linear-gradient(145deg,#df4943,#8f1014)}.j3b-logo.rgti{background:linear-gradient(145deg,#117d70,#053c42)}.j3b-logo.rgti img{width:86%}.j3b-symbol{display:block;font-size:25px;line-height:1;font-weight:900;letter-spacing:-1px}.j3b-name{display:block;color:#d6e4ed;margin-top:4px;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.j3b-price{font-size:21px;font-weight:850;letter-spacing:-1px;margin:9px 0 4px}.j3b-up{color:#7de143;margin-left:5px}.j3b-down{color:#ff5c55;margin-left:5px}.j3b-neutral{color:#ffc94f;margin-left:5px}.j3b-chart{position:absolute;top:63px;right:10px;width:46%;height:48px;opacity:.96}/* 접힌 카드의 당일 그림은 선을 얇게 (2026-08-28 상하님 지적 — "선이 너무 굵다, 원래 선 크기로"). 분봉이라 점이 촘촘해서 2.1px 로는 선이 굵은 띠처럼 보인다. 크게 연 카드의 6개월 그림은 .j3b-open-card 쪽 규칙이 따로 있어 안 건드린다(상하님 — "선택하면 나오는 건 건드리지 말고"). */.j3b-card .j3b-chart polyline{stroke-width:1.4px}.j3b-card .j3b-chart polygon{fill-opacity:.11}.j3b-card-notes{margin-top:17px;padding-top:5px;border-top:1px solid #94b5c52a}.j3b-note{font-size:11.5px;color:#e7edf2;line-height:1.72;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding-right:4px}.j3b-note:before{content:"•";color:#7ee24b;margin-right:5px}.j3b-card.decline .j3b-note:before{color:#ff5b4e}.j3b-lamp{position:absolute;right:5px;bottom:2px;width:31px;height:auto;z-index:2;opacity:.9;filter:drop-shadow(0 2px 3px #0009)}.j3b-lamp.left{right:auto;left:4px}.j3b-delete-visual{position:absolute;right:9px;top:9px;z-index:3;width:27px;height:27px;display:grid;place-items:center;border:1px solid #a9c7df;border-radius:50%;background:#062448;color:#fff;font-size:19px;line-height:1}.j3b-delete{position:absolute;right:10px;top:10px;z-index:3}.j3b-delete button{min-height:30px!important;width:30px!important;padding:0!important;border-radius:50%!important;border:1px solid #a9c7df!important;background:#062448!important;color:#fff!important;font-size:18px!important}
        div[class*="st-key-j3b_grid_"]{display:grid!important;grid-template-columns:repeat(auto-fill,minmax(165px,1fr))!important;column-gap:9px!important;row-gap:34px!important;align-items:start!important}/* 카드 제 아래 여백은 격자 안에서 끈다 — 격자 틈과 겹쳐 위아래가 붙어 보였다(2026-08-27 상하님 지적 — "종목이 위아래 너무 붙어 있지"). 실측 -1px. */div[class*="st-key-j3b_grid_"] .j3b-card{margin-bottom:0!important}/* 칸이 카드보다 작으면 카드가 삐져나와 아래 줄과 붙는다(실측 칸 132 · 카드 148).   칸에 박힌 높이를 풀어 카드 크기를 그대로 따라가게 한다. */div[class*="st-key-j3b_grid_"]>*,div[class*="st-key-j3b_grid_"]>*>[data-testid="stMarkdown"],div[class*="st-key-j3b_grid_"]>*>[data-testid="stMarkdown"]>div{height:auto!important;min-height:0!important;max-height:none!important}div[class*="st-key-j3b_search_row"] [data-testid="stHorizontalBlock"]{display:flex!important;flex-wrap:nowrap!important;gap:9px!important}div[class*="st-key-j3b_search_row"] [data-testid="column"],div[class*="st-key-j3b_search_row"] [data-testid="stColumn"]{min-width:0!important;flex:1 1 auto!important}div[class*="st-key-j3b_search_row"] [data-testid="stColumn"]:last-child{flex:0 0 40px!important}div[class*="st-key-j3b_search_row"]{margin:0 0 10px}div[class*="st-key-j3b_search_row"] label{display:none}div[class*="st-key-j3b_search_row"] input{height:39px!important;border:1px solid #b9965c!important;border-radius:21px!important;background:#062448!important;color:#eaf5ff!important;font-size:13px!important}div[class*="st-key-j3b_search_row"] .stButton button{width:40px;height:40px;min-height:40px;padding:0;border-radius:50%;border:1px solid #b9965c;background:#062448;color:#fff;font-size:27px}div[class*="st-key-j3b_extra_"]{position:relative}div[class*="st-key-j3b_extra_"] div[class*="st-key-j3b_del_"]:not([class*="st-key-j3b_del_yes_"]):not([class*="st-key-j3b_del_no_"]){position:absolute!important;right:7px!important;top:7px!important;z-index:8!important;width:25px!important;height:25px!important;margin:0!important}div[class*="st-key-j3b_extra_"] div[class*="st-key-j3b_del_"]:not([class*="st-key-j3b_del_yes_"]):not([class*="st-key-j3b_del_no_"]) button{min-height:25px!important;width:25px!important;padding:0!important;border-radius:50%!important;border:1px solid #a9c7df!important;background:#062448!important;color:#fff!important;font-size:16px!important;line-height:1!important}.j3b-empty{border:1px dashed #7091af99;border-radius:14px;padding:14px;color:#c3d7e7;font-size:13px;text-align:center;margin-bottom:10px}
        .j3b-disclaimer{margin:14px 0 10px;padding:11px 10px;border:1px solid #c1975b99;border-radius:13px;background:#06264ad9;text-align:center;color:#e7e6df;font-size:12px}.j3b-bottom-nav{position:fixed;z-index:2147483646;bottom:8px;left:50%;transform:translateX(-50%);width:min(430px,100vw);height:64px;padding:5px 6px;display:flex;justify-content:space-around;background:linear-gradient(180deg,#0a2f5cf2,#03162eee);border:1.6px solid #e2b25ecc;border-radius:20px;backdrop-filter:blur(10px);box-sizing:border-box;box-shadow:0 6px 18px #000a,inset 0 1px #ffd88a44}.j3b-nav-item{display:grid;place-items:center;gap:2px;color:#d6e2f0;font-size:12px;font-weight:700;line-height:1.1;min-width:0;width:25%;min-height:54px}.j3b-nav-item b{font-size:27px;font-weight:500}.j3b-nav-item b .j3b-pie{display:block;width:1.18em;height:1.18em}.j3b-nav-item.active{color:#4cc6ff;text-shadow:0 0 8px #1f9fe066}.j3b-nav-item.active b{filter:drop-shadow(0 0 5px #21b9ff)}
        div.st-key-j3b_nav_controls{position:fixed!important;z-index:2147483647!important;left:50%!important;bottom:0!important;transform:translateX(-50%)!important;width:min(430px,100vw)!important;height:68px!important;pointer-events:none!important}div.st-key-j3b_nav_controls [data-testid="stHorizontalBlock"]{gap:0!important;width:100%!important;height:68px!important}div.st-key-j3b_nav_controls [data-testid="stColumn"]{width:25%!important;min-width:0!important;height:68px!important;flex:0 0 25%!important}div.st-key-j3b_nav_controls [data-testid="stColumn"]>[data-testid="stVerticalBlock"],div.st-key-j3b_nav_controls [data-testid="stColumn"] [data-testid="stElementContainer"],div.st-key-j3b_nav_controls [data-testid="stColumn"] [data-testid="stButton"]{width:100%!important;max-width:none!important}div.st-key-j3b_nav_controls button{width:100%!important;height:68px!important;min-height:68px!important;padding:0!important;border:0!important;background:transparent!important;color:transparent!important;box-shadow:none!important;pointer-events:auto!important;touch-action:manipulation!important}
        div.stElementContainer:has(.j3b-debug-overlay){position:absolute!important;height:0!important;min-height:0!important;margin:0!important}.j3b-debug-overlay{position:fixed;z-index:10000;inset:0;pointer-events:none;display:flex;justify-content:center;background:rgba(0,0,0,.1)}.j3b-debug-overlay img{width:min(430px,100vw);height:auto;align-self:flex-start;opacity:.33;object-fit:contain;object-position:top center}
        @media (max-width:600px){body:has(.j3b-home) [data-testid="stMainBlockContainer"],body:has(.j3b-home) .block-container{padding-left:8px!important;padding-right:8px!important}.j3b-hero{height:230px}.j3b-title{font-size:37px}.j3b-sub{font-size:19px}.j3b-hero-catbus{width:155px}.j3b-hero-scene{width:114%}.j3b-section{font-size:20px}.j3b-card{height:238px;padding:10px 9px}.j3b-logo{width:43px;height:43px}.j3b-symbol{font-size:23px}.j3b-price{font-size:20px}.j3b-note{font-size:11px}}
        /* 941×1680 기준 캡처를 430×764 CSS viewport에 맞춘 실제 모바일 밀도. */
        .j3b-hero{height:150px!important;margin-bottom:-5px!important;padding:16px 19px!important;border-radius:0 0 20px 20px!important}.j3b-hero:before{width:580px;height:168px;bottom:-110px}.j3b-hero:after{left:104px;bottom:26px;width:140px;height:25px}.j3b-head-copy{left:20px!important;top:18px!important}.j3b-title{font-size:29px!important;letter-spacing:-1.7px!important}.j3b-title b{font-size:inherit!important;line-height:inherit!important}.j3b-sub{margin-top:6px!important;font-size:15px!important}.j3b-head-actions{right:15px!important;top:12px!important;gap:6px!important}.j3b-round,.j3b-live{height:31px!important;border-radius:18px!important}.j3b-round{width:31px!important;font-size:19px!important}.j3b-live{padding:0 9px!important;gap:5px!important;font-size:11px!important}.j3b-live i{width:8px!important;height:8px!important}.j3b-hero-catbus{right:-3px!important;bottom:2px!important;width:162px!important}.j3b-hero-scene{right:-4%!important;bottom:-1px!important;width:118%!important;max-width:none!important}
        .j3b-section{margin:8px 4px 4px!important;font-size:17px!important;gap:6px!important;line-height:22px!important}.j3b-section .j3b-section-icon{width:24px!important;height:24px!important}.j3b-section .j3b-section-icon:after{width:10px!important;height:10px!important}.j3b-section .j3b-more{font-size:11px!important}.j3b-news{min-height:18px!important;margin:3px 0!important;padding:3px 8px!important;border-radius:12px!important;gap:7px!important;font-size:9px!important;line-height:1.1!important}.j3b-news-icon{width:18px!important;height:18px!important;font-size:10px!important}.j3b-news-dot{width:9px!important;height:9px!important}
        .j3b-card{height:108px!important;border-radius:12px!important;padding:6px 7px!important;margin-bottom:6px!important}.j3b-card-top{min-height:32px!important;gap:6px!important}.j3b-logo{width:32px!important;height:32px!important;border-radius:8px!important}.j3b-logo img{width:72%!important;height:72%!important}.j3b-symbol{font-size:17px!important;color:#fff9eb!important;letter-spacing:-.7px!important}.j3b-name{margin-top:2px!important;font-size:9px!important;color:#e6eef5!important}.j3b-price{margin:5px 0 1px!important;font-size:14px!important;color:#fff9eb!important}.j3b-up,.j3b-down,.j3b-neutral{margin-left:3px!important}.j3b-chart{top:34px!important;right:7px!important;width:45%!important;height:31px!important}.j3b-card-notes{margin-top:5px!important;padding-top:3px!important}.j3b-note{font-size:8.1px!important;line-height:1.48!important;color:#f1f5f7!important}.j3b-note:before{margin-right:3px!important}.j3b-lamp{width:17px!important;bottom:0!important;right:3px!important}.j3b-lamp.left{left:3px!important}.j3b-delete-visual{width:18px!important;height:18px!important;right:5px!important;top:5px!important;font-size:13px!important}.j3b-card.compact{height:79px!important}.j3b-card.compact .j3b-card-top{min-height:27px!important}.j3b-card.compact .j3b-logo{width:28px!important;height:28px!important}.j3b-card.compact .j3b-symbol{font-size:15px!important}.j3b-card.compact .j3b-name{font-size:8.5px!important}.j3b-card.compact .j3b-price{font-size:11.5px!important;margin:3px 0 0!important}.j3b-card.compact .j3b-card-notes{margin-top:3px!important;padding-top:1px!important}.j3b-card.compact .j3b-note{font-size:7.5px!important;line-height:1.35!important}.j3b-card.compact .j3b-lamp{width:15px!important}
        div[class*="st-key-j3b_grid_"]{column-gap:7px!important}div[class*="st-key-j3b_search_row"]{height:30px!important;margin:-28px 0 -27px 202px!important}div[class*="st-key-j3b_search_row"] input{height:29px!important;font-size:9px!important}div[class*="st-key-j3b_search_row"] .stButton button{width:30px!important;height:30px!important;min-height:30px!important;font-size:20px!important}.j3b-disclaimer{margin:5px 0 5px!important;padding:6px!important;border-radius:9px!important;font-size:8px!important}.j3b-bottom-nav{height:56px!important;padding:4px 7px!important}.j3b-nav-item{font-size:11px!important;min-width:44px!important}.j3b-nav-item b{font-size:25px!important}
        </style>
        """,
        unsafe_allow_html=True,
    )
    # Android Chrome의 글자 확대·작은 CSS viewport에서도 가로 넘침과 카드 겹침을 막는다.
    st.markdown(
        """
        <style>
        html:has(.j3b-home),body:has(.j3b-home){overflow-x:hidden!important;max-width:100vw!important}
        body:has(.j3b-home) [data-testid="stMainBlockContainer"],body:has(.j3b-home) .block-container{width:100%!important;max-width:min(1500px,100vw)!important;min-width:0!important;box-sizing:border-box!important;overflow-x:hidden!important;padding-bottom:96px!important}@media (max-width:600px){body:has(.j3b-home) [data-testid="stMainBlockContainer"],body:has(.j3b-home) .block-container{max-width:min(430px,100vw)!important}div[class*="st-key-j3b_grid_"]{grid-template-columns:repeat(2,minmax(0,1fr))!important}div.st-key-j3b_grid_selected>*:nth-child(n+5){display:none!important}}@media (min-width:1200px){div[class*="st-key-j3b_grid_"]{grid-template-columns:repeat(auto-fill,minmax(340px,1fr))!important;column-gap:12px!important}}
        body:has(.j3b-home) [data-testid="stHorizontalBlock"],body:has(.j3b-home) [data-testid="stColumn"],body:has(.j3b-home) [data-testid="column"]{min-width:0!important;max-width:100%!important;box-sizing:border-box!important}
        .j3b-hero{height:174px!important;margin:0!important;padding:18px 18px!important;border-radius:0 0 24px 24px!important}.j3b-hero:before{width:620px!important;height:190px!important;bottom:-124px!important}.j3b-hero:after{left:96px!important;bottom:28px!important;width:150px!important;height:27px!important}.j3b-head-copy{left:20px!important;top:20px!important}.j3b-title{font-size:31px!important;line-height:1!important}.j3b-title b{font-size:inherit!important;line-height:inherit!important}.j3b-sub{margin-top:7px!important;font-size:16px!important;line-height:1.1!important}.j3b-head-actions{right:14px!important;top:15px!important}.j3b-round,.j3b-live{height:33px!important}.j3b-round{width:33px!important;font-size:20px!important}.j3b-live{padding:0 9px!important;font-size:12px!important}.j3b-hero-catbus{width:172px!important;right:-4px!important;bottom:4px!important}.j3b-hero-scene{right:-4%!important;bottom:-1px!important;width:116%!important;max-width:none!important}
        .j3b-section{margin:12px 4px 7px!important;font-size:18px!important;line-height:25px!important}.j3b-section .j3b-section-icon{width:25px!important;height:25px!important}.j3b-section .j3b-more{font-size:12px!important}.j3b-news{display:block!important;min-height:0!important;margin:5px 0!important;padding:0!important;border-radius:14px!important;font-size:10.5px!important;line-height:1.25!important}.j3b-news-link{min-height:33px!important;display:flex!important;align-items:center!important;gap:7px!important;padding:5px 10px!important;text-decoration:none!important;color:#f7f4ed!important}.j3b-news-link>span:nth-child(2){flex:1 1 auto!important;min-width:0!important;overflow:hidden!important;text-overflow:ellipsis!important;white-space:nowrap!important}.j3b-news-icon{width:21px!important;height:21px!important;font-size:12px!important}.j3b-news-dot{width:10px!important;height:10px!important}
        .j3b-card{height:auto!important;min-height:142px!important;min-width:0!important;box-sizing:border-box!important;border-radius:14px!important;padding:9px 7px 10px!important;margin:0 0 7px!important}.j3b-card-top{min-height:34px!important;gap:6px!important}.j3b-logo{width:34px!important;height:34px!important;border-radius:9px!important}.j3b-symbol{font-size:18px!important;line-height:1!important;color:#fff9eb!important}.j3b-name{margin-top:3px!important;font-size:10px!important;line-height:1.1!important}.j3b-price{position:absolute!important;left:7px!important;top:49px!important;max-width:55%!important;margin:0!important;color:#fff9eb!important;font-size:14px!important;line-height:1.15!important;white-space:nowrap!important}.j3b-chart{top:44px!important;right:7px!important;width:42%!important;height:34px!important}.j3b-card-notes{position:absolute!important;left:7px!important;right:7px!important;bottom:10px!important;margin:0!important;padding-top:3px!important}.j3b-card:has(.j3b-decor-img) .j3b-card-notes{right:58px!important}.j3b-card.compact:has(.j3b-decor-img) .j3b-card-notes{right:62px!important}.j3b-card:has(.j3b-decor-img.left) .j3b-card-notes{left:62px!important;right:7px!important}.j3b-note{display:block;color:#f1f5f7!important;text-decoration:none!important;font-size:9px!important;line-height:1.48!important;padding-right:0!important}.j3b-lamp{display:none!important}.j3b-decor-img{position:absolute;right:-2px;bottom:-1px;width:56px;height:auto;z-index:2;pointer-events:none;filter:drop-shadow(0 2px 3px #0007)}.j3b-decor-img.left{left:-2px;right:auto}.j3b-delete-visual{width:21px!important;height:21px!important;right:6px!important;top:6px!important;font-size:15px!important}
        .j3b-card.compact{height:auto!important;min-height:174px!important;box-sizing:border-box!important;padding-bottom:14px!important}.j3b-card.compact .j3b-card-top{min-height:32px!important}.j3b-card.compact .j3b-logo{width:31px!important;height:31px!important}.j3b-card.compact .j3b-symbol{font-size:16px!important}.j3b-card.compact .j3b-name{font-size:9px!important}.j3b-card.compact .j3b-price{top:42px!important;font-size:12px!important}.j3b-card.compact .j3b-chart{display:block!important;top:42px!important;right:7px!important;width:42%!important;height:34px!important}.j3b-card.compact .j3b-card-notes{bottom:14px!important;max-height:none!important;overflow:visible!important}.j3b-card.compact .j3b-note{font-size:8.5px!important;line-height:1.36!important}.j3b-card.compact .j3b-decor-img{width:58px!important;bottom:4px!important}
        div[class*="st-key-j3b_grid_"]{overflow:visible!important;padding-top:6px!important;padding-bottom:6px!important}div[class*="st-key-j3b_grid_"] [data-testid="stVerticalBlock"],div[class*="st-key-j3b_grid_"] [data-testid="stElementContainer"]{overflow:visible!important}
        div[class*="st-key-j3b_extra_header"] .j3b-section{margin:0!important;gap:4px!important;white-space:nowrap!important;font-size:15px!important;letter-spacing:-1px!important}div[class*="st-key-j3b_extra_header"] .j3b-section .j3b-section-icon{width:22px!important;height:22px!important}div[class*="st-key-j3b_extra_header"] .j3b-section.search .j3b-section-icon:before{transform:translate(9px,10px) rotate(48deg)!important}div[class*="st-key-j3b_search_row"]{height:auto!important;margin:0!important;width:100%!important;max-width:100%!important}div[class*="st-key-j3b_search_row"] [data-testid="stHorizontalBlock"]{gap:6px!important;overflow:hidden!important}div[class*="st-key-j3b_search_row"] input{width:100%!important;min-width:0!important;height:35px!important;font-size:11px!important}div[class*="st-key-j3b_search_row"] .stButton button{width:35px!important;height:35px!important;min-height:35px!important;font-size:22px!important}
        .j3b-bottom-nav{width:100vw!important;max-width:430px!important;height:64px!important;padding:5px 6px!important;box-sizing:border-box!important}.j3b-nav-item{min-width:0!important;min-height:54px!important;font-size:12px!important}.j3b-nav-item b{font-size:27px!important}
        /* 선택 4종목의 뉴스·하단 테두리와 하단 3메뉴의 실제 터치 영역을 확보한다. */
        .j3b-card:not(.compact){min-height:148px!important;padding-bottom:12px!important;margin-bottom:8px!important}.j3b-card:not(.compact) .j3b-card-notes{bottom:13px!important}
        div.st-key-j3b_grid_selected{padding-top:14px!important;padding-bottom:14px!important}
        .j3b-card.compact{min-height:164px!important}
        .j3b-bottom-nav{height:50px!important;padding:1px 6px!important}.j3b-nav-item{width:25%!important;min-height:46px!important;font-size:12px!important;gap:1px!important}.j3b-nav-item b{font-size:27px!important}
        div.st-key-j3b_nav_controls{height:50px!important;bottom:4px!important}div.st-key-j3b_nav_controls [data-testid="stHorizontalBlock"]{height:50px!important}div.st-key-j3b_nav_controls [data-testid="stColumn"]{width:25%!important;height:50px!important;flex:0 0 25%!important}div.st-key-j3b_nav_controls button{height:50px!important;min-height:50px!important}
        @media (max-width:1200px){
        body:has(.j3b-home) [data-testid="stMainBlockContainer"],body:has(.j3b-home) .block-container{padding-bottom:72px!important}
        .j3b-bottom-nav,div.st-key-j3b_nav_controls{bottom:4px!important;left:50%!important;transform:translateX(-75%)!important;margin-left:8px!important;width:min(286.667px,66.667vw)!important}
        [data-testid="stStatusWidget"],[data-testid="stAppDeployButton"],.stAppDeployButton{display:none!important;visibility:hidden!important;pointer-events:none!important}
        }
        @media (max-width:380px){.j3b-title{font-size:31px!important}.j3b-sub{font-size:16px!important}.j3b-hero-catbus{width:158px!important}.j3b-hero-scene{width:120%!important}.j3b-section{font-size:18px!important}.j3b-card:not(.compact){height:auto!important;min-height:148px!important}.j3b-card.compact{height:auto!important;min-height:160px!important}.j3b-note{font-size:9px!important}.j3b-card.compact .j3b-note{font-size:8.5px!important}}
        /* 시장판단 카드의 '살짝 뜨는' 결만 브리핑에 재사용한다. 시장판단 원본은 건드리지 않는다. */
        .j3b-news,.j3b-card-shell>.j3b-card-summary .j3b-card{transition:transform .12s ease-out,filter .12s ease-out,box-shadow .12s ease-out!important}
        .j3b-card-shell>.j3b-card-summary{display:block;list-style:none;cursor:zoom-in;outline:0}.j3b-card-shell>.j3b-card-summary::-webkit-details-marker{display:none}
        .j3b-news:hover,.j3b-card-shell:not([open])>.j3b-card-summary:hover .j3b-card{filter:brightness(1.1)!important;box-shadow:inset 0 1px #7bc9ff35,0 10px 20px #0008!important}
        .j3b-news:active,.j3b-card-shell:not([open])>.j3b-card-summary:active .j3b-card{transform:translateY(0) scale(.99)!important}
        /* 카드 클릭 확대는 브라우저 기본 details 상태만 쓴다. 재조회·rerun·자바스크립트가 없다. */
        .j3b-card-shell[open]>.j3b-card-summary{position:fixed!important;inset:0!important;z-index:2147483647!important;display:flex!important;align-items:center!important;justify-content:center!important;padding:16px!important;background:rgba(0,9,25,.9)!important;cursor:zoom-out!important;box-sizing:border-box!important}
        .j3b-card-shell[open]>.j3b-card-summary:after{content:none!important}
        .j3b-card-shell[open] .j3b-card,.j3b-card-shell[open] .j3b-card.compact{width:min(680px,calc(100vw - 32px))!important;height:auto!important;min-height:440px!important;max-height:calc(100dvh - 40px)!important;margin:0!important;padding:20px 20px 108px!important;border-radius:20px!important;overflow:auto!important;transform:none!important;filter:none!important;box-sizing:border-box!important;box-shadow:inset 0 1px #7bc9ff55,0 18px 48px #000c!important}
        .j3b-card-shell[open] .j3b-card:before{content:"× 다시 누르면 닫힘";position:absolute;right:12px;top:12px;z-index:6;padding:6px 10px;border:1px solid #9bcfff;border-radius:16px;background:#062448;color:#f5fbff;font-size:12px;font-weight:800;pointer-events:none}
        .j3b-card-shell[open] .j3b-card-top{min-height:58px!important;gap:10px!important;padding-right:132px!important}.j3b-card-shell[open] .j3b-logo{width:58px!important;height:58px!important;border-radius:14px!important}.j3b-card-shell[open] .j3b-symbol{font-size:28px!important}.j3b-card-shell[open] .j3b-name{font-size:14px!important;white-space:normal!important;overflow:visible!important;text-overflow:clip!important}.j3b-card-shell[open] .j3b-price{position:static!important;max-width:none!important;margin:12px 0 8px!important;font-size:22px!important}.j3b-card-shell[open] .j3b-chart{position:relative!important;inset:auto!important;display:block!important;width:100%!important;height:100px!important;margin:4px 0 14px!important}.j3b-card-shell[open] .j3b-card-notes{position:static!important;inset:auto!important;max-height:none!important;margin:0!important;padding-top:10px!important;overflow:visible!important}.j3b-card-shell[open] .j3b-note{display:block!important;margin:0 0 9px!important;font-size:14px!important;line-height:1.55!important;white-space:normal!important;overflow:visible!important;text-overflow:clip!important}.j3b-card-shell[open] .j3b-decor-img{width:96px!important;right:10px!important;bottom:6px!important}
        /* 시장 한줄 브리핑도 링크 이동 없이 같은 화면에서 전체 한글 요약을 펼친다. */
        .j3b-market-news-shell{display:block;margin:7px 0}.j3b-market-news-summary{display:block;list-style:none;cursor:zoom-in;outline:0}.j3b-market-news-summary::-webkit-details-marker{display:none}.j3b-market-news-shell .j3b-news{margin:7px 0!important}.j3b-market-news-shell .j3b-news-link{display:flex;align-items:center;gap:10px;width:100%;color:inherit;text-decoration:none}.j3b-market-news-shell .j3b-news-link>span:nth-child(2){flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.j3b-market-news-expanded{display:none}
        .j3b-market-news-shell[open]>.j3b-market-news-summary{position:fixed!important;inset:0!important;z-index:2147483647!important;display:flex!important;align-items:center!important;justify-content:center!important;padding:16px!important;background:rgba(0,9,25,.9)!important;cursor:zoom-out!important;box-sizing:border-box!important}
        .j3b-market-news-shell[open] .j3b-news{display:none!important}.j3b-market-news-shell[open] .j3b-market-news-expanded{position:relative;display:block;width:min(620px,calc(100vw - 32px));max-height:calc(100dvh - 76px);overflow:auto;box-sizing:border-box;padding:26px 22px 22px;border:1px solid #bd9052;border-radius:20px;background:linear-gradient(145deg,#06345f,#03264a 58%,#001d3c);color:#f5fbff;box-shadow:inset 0 1px #7bc9ff55,0 18px 48px #000c}
        .j3b-market-news-close{position:absolute;right:12px;top:12px;padding:6px 10px;border:1px solid #9bcfff;border-radius:16px;background:#062448;color:#f5fbff;font-size:12px;font-weight:800}.j3b-market-news-title{padding-right:130px;color:#61baff;font-size:18px;font-weight:900}.j3b-market-news-text{margin-top:18px;padding-top:18px;border-top:1px solid #8ab7d633;color:#f5f1e8;font-size:18px;line-height:1.6;font-weight:650;white-space:normal;overflow-wrap:anywhere}.j3b-market-news-number{color:#6edbff;font-weight:900;margin-right:8px}
        @media (max-width:600px){.j3b-market-news-shell{margin:5px 0}.j3b-market-news-shell[open] .j3b-market-news-expanded{padding:24px 18px 20px}.j3b-market-news-title{font-size:16px}.j3b-market-news-text{font-size:17px;line-height:1.65}}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(_BRIEFING_OPEN_CSS, unsafe_allow_html=True)
    st.markdown(_decor_css(), unsafe_allow_html=True)
    st.markdown(_BRIEFING_TABLET_CSS, unsafe_allow_html=True)
    st.markdown(_BRIEFING_GESTURE_CSS, unsafe_allow_html=True)
    st.markdown(_BRIEFING_TOUCH_CSS, unsafe_allow_html=True)


_BRIEFING_OPEN_CSS = """
<style>
/* 크게 연 화면 — 2026-08-26 상하님 지시로 구조를 바꿨다.
   예전에는 큰 판이 summary 안에 있었다. 그러면 그 안의 뉴스를 눌러도
   브라우저가 details 를 닫아 버려 원문을 펼칠 수 없었다.
   이제 큰 판은 summary 밖에 있다. 어두운 바탕(summary)을 누르면 닫히고,
   판 안의 뉴스를 누르면 그 줄만 펼쳐진다. */
.j3b-card-open{display:none}
.j3b-card-shell[open]>.j3b-card-summary,
.j3b-market-news-shell[open]>.j3b-market-news-summary{z-index:2147483646!important}
.j3b-card-shell[open]>.j3b-card-summary>*{visibility:hidden!important}
.j3b-card-shell[open]>.j3b-card-open,
.j3b-market-news-shell[open]>.j3b-card-open{position:fixed;inset:0;z-index:2147483647;
 display:flex;align-items:center;justify-content:center;padding:16px;
 box-sizing:border-box;pointer-events:none}
.j3b-open-card{position:relative;pointer-events:auto;width:min(680px,calc(100vw - 32px));
 max-height:calc(100dvh - 40px);overflow:auto;padding:20px 20px 104px;
 border:1px solid rgba(123,201,255,.45);border-radius:20px;box-sizing:border-box;
 background:radial-gradient(circle at 100% 0,rgba(15,85,147,.37),transparent 44%),
  linear-gradient(145deg,rgba(7,41,87,.99),rgba(3,23,55,.99));
 box-shadow:inset 0 1px #7bc9ff55,0 18px 48px #000c}
/* 닫기 단추는 **카드 안 오른쪽 위**에 그대로 둔다(2026-08-26 상하님 지시 —
   "원래 화면대로 하되 안에서 클릭하도록").

   <details>는 어두운 바탕(summary)을 눌러야 닫힌다. 그래서 큰 판은 손가락을
   받지 않게 두고, 뉴스 목록만 받게 한다. 그러면 단추든 카드 어디든 누르면 그
   손가락이 바탕까지 내려가 닫히고, 뉴스 줄을 누르면 그 줄만 펼쳐진다. */
.j3b-open-card{pointer-events:none}
.j3b-open-list,.j3b-open-link{pointer-events:auto}
.j3b-open-close{position:absolute;right:12px;top:12px;z-index:6;padding:6px 12px;
 border:1px solid #9bcfff;border-radius:16px;background:#062448;color:#f5fbff;
 font-size:12px;font-weight:800;pointer-events:none;white-space:nowrap}
/* **아래에도 하나 더** (2026-08-29 상하님 지시 — 캡처에 위 단추를 동그라미 치고
   아래로 화살표, "간단하게 1개 더 만들어라").
   글을 끝까지 읽고 나면 손가락이 화면 아래에 있는데, 닫으려고 다시 맨 위
   오른쪽까지 올라가야 했다. 폰에서는 그 자리가 제일 멀다.
   글자는 **짧게** 둔다 — 위에 이미 긴 안내가 있어 여기서 되풀이할 것이 없다.
   자리는 **왼쪽 아래**다. 오른쪽 아래에는 장식 그림(.j3b-decor-img)이 96px 로
   앉아 있어 거기 두면 겹친다.
   창 바닥에 **붙이지 않는다**(sticky 아님) — 2026-08-26에 그렇게 했다가 글을
   굴리는 동안 화면 한가운데에 떠서 글을 가렸다. 카드 안 여백(아래 96~112px)에
   가만히 놓는다.
   누르는 방식은 위 것과 똑같다 — 큰 판이 손가락을 안 받으므로(.j3b-open-card
   pointer-events:none) 여기를 눌러도 그 손가락이 바탕까지 내려가 닫힌다. */
.j3b-open-close-b{right:auto;left:16px;top:auto;bottom:16px;padding:9px 18px;font-size:13px}
.j3b-open-card .j3b-card-top{display:flex;gap:10px;align-items:center;min-height:58px;padding-right:132px}
.j3b-open-card .j3b-logo{width:58px;height:58px;border-radius:14px}
.j3b-open-card .j3b-symbol{display:block;font-size:28px;font-weight:900;color:#fff8e9}
.j3b-open-card .j3b-name{display:block;margin-top:2px;color:#c9e8ff;font-size:14px;white-space:normal}
.j3b-open-card .j3b-price{margin:12px 0 8px;font-size:22px;font-weight:900;color:#fff}
.j3b-open-card .j3b-chart{position:relative;inset:auto;display:block;width:100%;height:100px;margin:4px 0 6px}/* 크게 연 그림은 선을 가늘게 — 늘어난 그림에 굵은 선은 뭉개져 보인다. */.j3b-open-card .j3b-chart polyline{stroke-width:1.8px}/* 선 둘레에 은은한 번짐을 준다. */.j3b-open-card .j3b-chart{filter:drop-shadow(0 0 4px #70e64a55)}.j3b-chart-cap{color:#4da6ff;font-size:15px;font-weight:800;text-align:center;margin:0 0 10px}
.j3b-open-card .j3b-decor-img{position:absolute;right:10px;bottom:6px;width:96px;height:auto;pointer-events:none}
.j3b-market-news-title{padding-right:130px;color:#61baff;font-size:18px;font-weight:900}
.j3b-open-list{margin-top:14px}
.j3b-open-news{border-top:1px solid rgba(181,219,255,.2)}
.j3b-open-news>summary{list-style:none;cursor:pointer;position:relative;
 padding:11px 26px 11px 0;color:#eaf4fc;font-size:14px;line-height:1.55;outline:0}
.j3b-open-news>summary::-webkit-details-marker{display:none}
.j3b-open-news>summary:before{content:'•';color:#72e55b;margin-right:7px}
.j3b-open-news>summary:after{content:'＋';position:absolute;right:2px;top:11px;color:#8fc4ea;font-size:13px}
.j3b-open-news[open]>summary{color:#9fd8ff;font-weight:800}
.j3b-open-news[open]>summary:after{content:'－'}
.j3b-open-body{padding:0 0 13px 15px}
.j3b-open-label{margin-bottom:4px;color:#7fc4ff;font-size:11px;font-weight:800}
.j3b-open-orig{color:#cfe0ef;font-size:13px;line-height:1.6;overflow-wrap:anywhere}
.j3b-open-src{margin-top:6px;color:#93a9bd;font-size:11px}
.j3b-open-link{display:inline-block;margin-top:9px;padding:5px 12px;border:1px solid #4f9fd8;
 border-radius:14px;color:#8fd9ff!important;font-size:12px;font-weight:800;text-decoration:none}
@media (max-width:600px){
 .j3b-open-card{padding:18px 16px 96px}
 .j3b-open-card .j3b-symbol{font-size:24px}
 .j3b-open-news>summary{font-size:15px;line-height:1.6}
 .j3b-open-orig{font-size:14px}
 .j3b-market-news-title{font-size:16px}
}
</style>
"""


_BRIEFING_TABLET_CSS = """
<style>
/* ── 태블릿(갤럭시탭 S8+) 세로·가로 ─────────────────────────────────────────
   세로는 CSS 폭 약 800px, 가로는 약 1138px이다. 폰 기준 430px를 그대로 쓰면
   양옆이 텅 비고 글자가 작아 보인다. 폭을 넓히고 글자·카드를 그만큼 키운다.
   숫자·점수·판정은 건드리지 않는다 — 보이는 크기만 바꾼다. */
@media (min-width:601px) and (max-width:1199px){
 /* 폭을 넓힌다(2026-08-27 상하님 지적 — "태블릿 화면인데 좌우 여백이 너무
    많다"). 760px 이면 1138px 화면에서 양옆이 190px 씩 비었다. 카드를 세 칸으로
    놓으려면 폭도 그만큼 있어야 한다. **갤럭시탭 S8+ 에만 걸리는 규칙이다** —
    폰과 노트북은 예전 그대로 두 칸이다. */
 body:has(.j3b-home) [data-testid="stMainBlockContainer"],
 body:has(.j3b-home) .block-container{max-width:min(1060px,96vw)!important;
  padding:0 14px 108px!important}
 /* **카드를 세 칸으로 놓는다** (2026-08-27 상하님 지시 — "태블릿 화면에는
    종목선정 2줄씩 되어 있는데 3칸씩 넣으면 안 되나?"). 갤럭시탭 S8+ 에만
    걸리는 규칙이다 — 폰과 노트북은 예전 그대로 두 칸이다.
    사용자 선정 종목 3칸 x 2줄 = 6종목 · 추가 검색 종목 3칸 x 4줄 = 12종목. */
 div[class*="st-key-j3b_grid_"]{grid-template-columns:repeat(3,minmax(0,1fr))!important;
  column-gap:10px!important}
 /* **칸이 좁아진 만큼 카드 속도 다시 놓는다** (2026-08-27 상하님 캡처).
    두 칸일 때는 카드가 370px 이라 차트를 오른쪽 위에 겹쳐 놓아도 글자를 안
    덮었다. 세 칸이 되어 카드가 214px 로 좁아지자 차트가 종목명·가격 위를
    지나갔다(실측 — 차트 x=117~206, 종목명 82~158, 가격 8~125).
    또 카드 높이가 250·270px 로 박혀 있어 가운데가 140px 이나 비었다.
    이제 위에서 아래로 흐르게 한다 — 이름 · 가격 · 차트 · 뉴스 차례다.
    높이는 속 내용이 정한다. */
 body:has(.j3b-home) .j3b-card,
 body:has(.j3b-home) .j3b-card.compact{height:auto!important;min-height:0!important;
  padding-bottom:11px!important}
 body:has(.j3b-home) .j3b-card .j3b-chart,
 body:has(.j3b-home) .j3b-card.compact .j3b-chart{position:relative!important;
  inset:auto!important;top:auto!important;right:auto!important;left:auto!important;
  bottom:auto!important;display:block!important;width:100%!important;
  height:46px!important;margin:7px 0 3px!important}
 body:has(.j3b-home) .j3b-card .j3b-price,
 body:has(.j3b-home) .j3b-card.compact .j3b-price{position:static!important;
  max-width:none!important;margin:7px 0 0!important}
 /* 카드를 조금 더 줄인다 (2026-08-27 상하님 지시 — "태블릿은 각 종목들
    테두리부터 아주 조금 더 축소시켜라"). 테두리 안 여백부터 줄이고 글자·그림도
    한 치수씩 내린다. 값·점수는 그대로다. */
 body:has(.j3b-home) .j3b-card{padding:9px 8px 9px!important;border-radius:14px!important}
 body:has(.j3b-home) .j3b-card .j3b-card-top{min-height:0!important;gap:7px!important}
 body:has(.j3b-home) .j3b-card .j3b-logo{width:38px!important;height:38px!important;
  border-radius:10px!important}
 body:has(.j3b-home) .j3b-card .j3b-symbol{font-size:20px!important}
 body:has(.j3b-home) .j3b-card .j3b-name{font-size:11px!important;margin-top:2px!important}
 body:has(.j3b-home) .j3b-card .j3b-price{font-size:16px!important;margin:5px 0 0!important}
 body:has(.j3b-home) .j3b-card .j3b-chart{height:40px!important;margin:5px 0 2px!important}
 body:has(.j3b-home) .j3b-card .j3b-note{font-size:10.5px!important;line-height:1.5!important}
 body:has(.j3b-home) .j3b-card .j3b-decor-img{width:46px!important}
 /* **종목 검색칸을 왼쪽으로 한 칸 옮기고 + 를 줄인다** (2026-08-27 상하님 지시 —
    "종목 검색 후 추가 옆에 동그라미는 왜 짤리지? 검색란은 왼쪽으로 한 칸 옮기고
    동그라미 크기 줄이면 되겠네"). 오른쪽 끝에 자리를 넉넉히 남긴다. */
 div[class*="st-key-j3b_extra_header"]{padding-right:10px!important}
 div[class*="st-key-j3b_search_row"]{margin-right:6px!important}
 div[class*="st-key-j3b_search_row"] [data-testid="stColumn"]:last-child{
  flex:0 0 36px!important;min-width:36px!important}
 body:has(.j3b-home) div[class*="st-key-j3b_search_row"] .stButton button,
 body:has(.j3b-home) div[class*="st-key-j3b_search_row"] button{width:34px!important;
  height:34px!important;min-height:34px!important;max-width:34px!important;
  padding:0!important;font-size:21px!important;border-radius:50%!important}
 body:has(.j3b-home) .j3b-card .j3b-card-notes,
 body:has(.j3b-home) .j3b-card.compact .j3b-card-notes{position:static!important;
  inset:auto!important;margin:7px 0 0!important;padding-top:6px!important;
  left:auto!important;right:auto!important;bottom:auto!important;max-height:none!important}
 /* **하단 이동막대를 옆 단추 키에 맞춘다** (2026-08-27 상하님 지시 —
    "밑에 하단에 홈·관심종목·시장분석 테두리 너무 크다. 옆에 왕관 모양 붉은색
    배경과 키 높이 맞춰라. 스마트폰은 괜찮다"). 실측 76px 이었다.
    폰은 안 건드린다 — 이 블록은 601~1199px 에만 걸린다. */
 body:has(.j3b-home) nav.j3b-bottom-nav,
 body:has(.j3-market-top) nav.j3b-bottom-nav{height:48px!important;padding:3px 10px!important;
  border-radius:19px!important;bottom:12px!important}
 body:has(.j3b-home) nav.j3b-bottom-nav .j3b-nav-item,
 body:has(.j3-market-top) nav.j3b-bottom-nav .j3b-nav-item{min-height:40px!important;
  font-size:11px!important;gap:1px!important}
 body:has(.j3b-home) nav.j3b-bottom-nav .j3b-nav-item b,
 body:has(.j3-market-top) nav.j3b-bottom-nav .j3b-nav-item b{font-size:21px!important}
 body:has(.j3b-home) nav.j3b-bottom-nav .j3b-nav-item b .j3b-pie,
 body:has(.j3-market-top) nav.j3b-bottom-nav .j3b-nav-item b .j3b-pie{width:1.05em!important;height:1.05em!important}
 /* 눈에 안 보이는 '누르는 자리'도 막대 키에 맞춘다 — 막대보다 크면 그 밑의
    글을 못 누른다. 막대가 바닥에서 12px 위에 48px 이므로 60px 이다. */
 body:has(.j3b-home) div.st-key-j3b_nav_controls,
 body:has(.j3-market-top) div.st-key-j3b_nav_controls{height:60px!important}
 body:has(.j3b-home) div.st-key-j3b_nav_controls [data-testid="stHorizontalBlock"],
 body:has(.j3-market-top) div.st-key-j3b_nav_controls [data-testid="stHorizontalBlock"]{height:60px!important}
 body:has(.j3b-home) div.st-key-j3b_nav_controls [data-testid="stColumn"],
 body:has(.j3-market-top) div.st-key-j3b_nav_controls [data-testid="stColumn"]{height:60px!important}
 body:has(.j3b-home) div.st-key-j3b_nav_controls button,
 body:has(.j3-market-top) div.st-key-j3b_nav_controls button{height:60px!important;min-height:60px!important}
 .j3b-hero{height:250px!important;padding:26px 28px!important;border-radius:0 0 30px 30px!important}
 .j3b-hero-scene{right:-4%!important;bottom:-1px!important;width:112%!important}
 .j3b-title{font-size:46px!important;letter-spacing:-2.6px!important}
 .j3b-sub{margin-top:11px!important;font-size:24px!important}
 .j3b-head-copy{left:28px!important;top:26px!important}
 .j3b-head-actions{right:22px!important;top:22px!important;gap:10px!important}
 .j3b-round,.j3b-live{height:46px!important;border-radius:26px!important}
 .j3b-round{width:46px!important;font-size:27px!important}
 .j3b-live{padding:0 15px!important;gap:8px!important;font-size:16px!important}
 .j3b-live i{width:11px!important;height:11px!important}
 .j3b-section{margin:20px 6px 12px!important;font-size:26px!important;line-height:34px!important}
 .j3b-section .j3b-flag{font-size:32px!important}
 .j3b-section .j3b-section-icon{width:34px!important;height:34px!important}
 .j3b-section .j3b-more{font-size:17px!important}
 .j3b-news{margin:9px 0!important;border-radius:20px!important}
 .j3b-news-link{min-height:52px!important;padding:9px 18px!important;gap:12px!important;font-size:16px!important}
 .j3b-news-icon{width:30px!important;height:30px!important;font-size:16px!important}
 .j3b-news-dot{width:15px!important;height:15px!important}
 .j3b-card:not(.compact){height:auto!important;min-height:250px!important;padding:16px 15px!important;border-radius:22px!important}
 .j3b-card.compact{height:auto!important;min-height:270px!important;padding:16px 15px!important;border-radius:22px!important}
 .j3b-logo{width:60px!important;height:60px!important;border-radius:16px!important}
 .j3b-symbol{font-size:32px!important}
 .j3b-name{font-size:17px!important}
 .j3b-price{font-size:28px!important;margin-top:12px!important}
 .j3b-change{font-size:22px!important}
 .j3b-chart{height:74px!important}
 .j3b-note{font-size:15px!important;line-height:1.6!important}
 .j3b-card-notes{bottom:16px!important;left:15px!important;right:15px!important}
 .j3b-decor-img{width:86px!important}
 .j3b-bottom-nav,div.st-key-j3b_nav_controls{bottom:12px!important;left:50%!important;
  transform:translateX(-50%)!important;margin-left:-60px!important;
  width:min(520px,62vw)!important}
 .j3b-bottom-nav{height:76px!important;padding:7px 12px!important;border-radius:26px!important}
 .j3b-nav-item{min-height:62px!important;font-size:16px!important;gap:4px!important}
 .j3b-nav-item b{font-size:27px!important}
 div.st-key-j3b_nav_controls{height:76px!important}
 div.st-key-j3b_nav_controls [data-testid="stHorizontalBlock"]{height:76px!important}
 div.st-key-j3b_nav_controls [data-testid="stColumn"]{height:76px!important}
 div.st-key-j3b_nav_controls button{height:76px!important;min-height:76px!important}
 div[class*="st-key-j3b_extra_header"] .j3b-section{font-size:21px!important}
 div[class*="st-key-j3b_search_row"] input{height:50px!important;font-size:16px!important}
 div[class*="st-key-j3b_search_row"] .stButton button{width:50px!important;height:50px!important;
  min-height:50px!important;font-size:28px!important}
 .j3b-open-card{width:min(680px,calc(100vw - 40px))!important;padding:22px 22px 112px!important}
 .j3b-open-news>summary{font-size:17px!important;line-height:1.6!important}
 .j3b-open-orig{font-size:16px!important}
}
</style>
"""


_BRIEFING_GESTURE_CSS = """
<style>
/* ── 손가락으로 위에서 아래로 당겨도 새로고침되지 않게 한다 ────────────────
   2026-08-26 상하님 지시 — "맨 위 화면에서 뒤로 당기면 로그인 화면으로 갔다가
   다시 메인으로 돌아온다. 이거 안 되게 할 수 없냐."
   안드로이드 크롬은 맨 위에서 아래로 당기면 페이지를 통째로 다시 불러온다.
   그러면 로그인 확인을 다시 거치느라 화면이 한 번 깜빡인다.
   overscroll-behavior 로 그 몸짓만 막는다. 손가락으로 굴려 보는 것은 그대로다. */
html, body { overscroll-behavior: none !important; }
body [data-testid="stMainBlockContainer"],
body section[data-testid="stMain"],
body [data-testid="stAppViewContainer"] { overscroll-behavior-y: contain !important; }

/* 찾은 종목을 보여 주는 줄 */
div[class*="st-key-j3b_search_confirm"]{margin:6px 0 2px!important;
  padding:10px 12px!important;border:1px solid rgba(240,177,67,.45)!important;
  border-radius:14px!important;background:rgba(6,33,75,.72)!important}
.j3b-found{color:#ffe0a3;font-size:15px;font-weight:800;margin-bottom:6px}
div[class*="st-key-j3b_search_confirm"] button{min-height:38px!important;font-size:13px!important}

/* ↻ 되돌리기 — 보이는 것은 머리띠 안의 동그라미이고, 그 위에 속이 비치는
   진짜 단추를 겹쳐 둔다. 눌리는 것은 이 단추다. */
div[class*="st-key-j3b_hero_box"] { position: relative !important; }
div[class*="st-key-j3b_hero_box"] [data-testid="stElementContainer"]:has(button) {
  position: absolute !important; right: 87px; top: 16px; z-index: 6;
  width: auto !important; margin: 0 !important; }
div[class*="st-key-j3b_hero_box"] .stButton,
div[class*="st-key-j3b_hero_box"] button {
  width: 33px !important; height: 33px !important; min-height: 33px !important;
  padding: 0 !important; border: 0 !important; border-radius: 50% !important;
  background: transparent !important; color: transparent !important;
  box-shadow: none !important; }
div[class*="st-key-j3b_hero_box"] button:hover,
div[class*="st-key-j3b_hero_box"] button:focus { background: #ffffff1f !important; }
@media (min-width:601px) and (max-width:1199px){
  div[class*="st-key-j3b_hero_box"] [data-testid="stElementContainer"]:has(button){right:128px;top:23px}
  div[class*="st-key-j3b_hero_box"] .stButton,
  div[class*="st-key-j3b_hero_box"] button{width:46px!important;height:46px!important;min-height:46px!important}
}
</style>
"""


_BRIEFING_TOUCH_CSS = """
<style>
/* ── 손을 올리면 살짝 앞으로 나온다 (2026-08-26 상하님 지시) ────────────────
   상하님 — "시장분석의 시장 상황·시장 국면처럼 관심종목 각 부분에도 마우스 갖다
   대면 그렇게 할 수 없냐."
   시장분석 쪽과 같은 결로 맞춘다 — 0.12초, 위로 살짝, 밝기 1.1.
   (market_signal_ui.py 의 .sig-head-box / .sig-gauge-shell / .sig-story 규칙)
   카드는 시장분석 상자보다 크므로 4px 뜨고 테두리가 함께 밝아진다.
   숫자·점수·판정은 건드리지 않는다 — 보이는 움직임만이다. */
.j3b-card, .j3b-news, .j3b-logo, .j3b-nav-item, .j3b-round, .j3b-live,
.j3b-decor-img, .j3b-open-news > summary, .j3b-section .j3b-more,
.j3b-card-shell:not([open]) > .j3b-card-summary {
  transition: transform .12s ease-out, filter .12s ease-out,
              border-color .12s ease-out, box-shadow .12s ease-out;
}

/* **미디어 조건을 걸지 않는다.** 시장분석(market_signal_ui.py)의 카드에는
   @media (hover:...) 가 하나도 없다. 그래서 폰·태블릿에서 손가락으로 누르면
   브라우저가 :hover 를 걸어 줘 카드가 그대로 떠오른다. 내가 조건을 걸어 두는
   바람에 터치 기기가 통째로 빠졌다(2026-08-26 상하님 지적 —
   "시장분석은 스마트폰 태블릿에서 되는데, 시장분석 코딩을 봐라"). 조건을 걷는다. */
/* 카드 — 통째로 뜨고 테두리가 밝아진다.
   **뜨는 것은 껍데기(summary)에 건다.** 안쪽 .j3b-card 에 걸면 다른 규칙에 눌려
   테두리만 바뀌고 움직이지 않았다(2026-08-26 실측). */
.j3b-card-shell:not([open]) > .j3b-card-summary:hover {
  transform: translateY(-6px);
  filter: brightness(1.14);
}
.j3b-card-shell:not([open]) > .j3b-card-summary:hover .j3b-card {
  border-color: rgba(150,220,255,.95) !important;
  box-shadow: inset 0 1px #7bc9ff55, 0 0 0 1px rgba(110,200,255,.35),
              0 16px 30px #000b !important;
}
/* 시장국면 계기판 바늘처럼, 로고가 한 번 살짝 흔들린다
   (market_signal_ui.py 의 sig-needle-wiggle 과 같은 결). */
.j3b-card-shell:not([open]) > .j3b-card-summary:hover .j3b-logo {
  transform: scale(1.09);
  animation: j3b-logo-wiggle .55s cubic-bezier(.3,.7,.4,1);
}
/* 카드 안의 로고와 캐릭터도 조금 더 나온다 */
.j3b-card-shell:not([open]) > .j3b-card-summary:hover .j3b-decor-img { transform: translateY(-2px) scale(1.05); }
/* 브리핑 한 줄 */
.j3b-news:hover {
  transform: translateY(-3px) !important;
  filter: brightness(1.12) !important;
  border-color: rgba(255,214,129,.85) !important;
}
/* 크게 연 화면의 뉴스 줄 */
.j3b-open-news > summary:hover { filter: brightness(1.25); transform: translateX(2px); }
/* 하단 이동표 */
.j3b-nav-item:hover { transform: translateY(-3px); filter: brightness(1.25); }
/* 머리띠의 ↻ 와 실시간 */
.j3b-round:hover, .j3b-live:hover {
  transform: translateY(-2px); filter: brightness(1.15);
  border-color: #ffd88a !important;
}
.j3b-section .j3b-more:hover { filter: brightness(1.4); transform: translateX(2px); }

@keyframes j3b-logo-wiggle {
  0%   { transform: scale(1.09) rotate(0deg); }
  25%  { transform: scale(1.09) rotate(-6deg); }
  55%  { transform: scale(1.09) rotate(4deg); }
  80%  { transform: scale(1.09) rotate(-1.5deg); }
  100% { transform: scale(1.09) rotate(0deg); }
}

@media (hover:none) {
  /* 터치 화면에는 '마우스를 올린다'가 없다. 그래서 화면이 뜰 때 카드가 아래에서
     살짝 올라오며 나타나게 해 움직임을 보여 준다. */
  @keyframes j3b-card-in {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  .j3b-card-shell > .j3b-card-summary { animation: j3b-card-in .34s ease-out both; }
  .j3b-news { animation: j3b-card-in .3s ease-out both; }
}

/* 손가락으로 누를 때 — 폰·태블릿. 마우스가 없으니 '뜨는' 대신 **눌리는** 것을 준다.
   2026-08-26 상하님 — "노트북에는 되네, 태블릿 스마트폰에서는 안 된다."
   손가락 기기에는 :hover 가 아예 없다. 그래서 :active 를 더 뚜렷하게 준다. */
@media (hover:none) {
  .j3b-card-shell:not([open]) > .j3b-card-summary:active {
    transform: scale(.955) !important; filter: brightness(1.22) !important;
  }
  .j3b-card-shell:not([open]) > .j3b-card-summary:active .j3b-card {
    border-color: rgba(150,220,255,.95) !important;
    box-shadow: inset 0 1px #7bc9ff55, 0 0 0 1px rgba(110,200,255,.45) !important;
  }
  .j3b-card-shell:not([open]) > .j3b-card-summary:active .j3b-logo {
    animation: j3b-logo-wiggle .55s cubic-bezier(.3,.7,.4,1);
  }
  .j3b-market-news-shell > .j3b-market-news-summary:active .j3b-news {
    transform: scale(.97) !important; filter: brightness(1.22) !important;
    border-color: rgba(255,214,129,.9) !important;
  }
  div[class*="st-key-j3b_nav_controls"] button:active { background: #ffffff22 !important; }
}
.j3b-card-summary, .j3b-market-news-summary, .j3b-news, .j3b-nav-item {
  -webkit-tap-highlight-color: rgba(120,205,255,.22);
}

/* 손가락으로 누를 때 — 폰·태블릿. 눌리는 느낌만 준다. */
.j3b-card-shell:not([open]) > .j3b-card-summary:active {
  transform: scale(.985); filter: brightness(1.06);
}
.j3b-news:active { transform: translateY(0) scale(.99) !important; filter: brightness(1.06) !important; }
.j3b-nav-item:active { transform: scale(.94); filter: brightness(1.3); }
.j3b-open-news > summary:active { filter: brightness(1.3); }

/* 움직임을 줄여 달라는 설정이면 다 멈춘다 */
@media (prefers-reduced-motion: reduce) {
  .j3b-card, .j3b-news, .j3b-logo, .j3b-nav-item, .j3b-round, .j3b-live,
  .j3b-decor-img, .j3b-open-news > summary { transition: none !important; }
  .j3b-card-shell:not([open]) > .j3b-card-summary:hover .j3b-logo { animation: none !important; }
}
</style>
"""


# 일봉 6개월 그림의 색 — **초록 하나로 고정** (2026-08-26 상하님 지시).
# 처음에는 오렌지 형광으로 했다가 "안 되겠다, 그냥 초록색으로 하자"고 정하셨다.
# 오늘 오르내림에 따라 색이 바뀌던 것을 없앤 뜻은 그대로다 — 반년 흐름을
# 하루 색으로 말하면 안 된다.
_SIX_MONTH_STROKE = "#70e64a"


# 기준선 위는 초록, 아래는 빨강 (2026-08-28 상하님 지시 · 야후 파이낸스와 같은 색).
_BASE_UP_STROKE = "#70e64a"
_BASE_DOWN_STROKE = "#ff5b5b"


def _briefing_chart_split(values, low: float, span: float, *, base=None) -> str:
    """시작가에 기준선을 긋고 위·아래를 다른 색으로 그린다.

    선이 기준선을 가로지르는 **바로 그 자리**에서 색을 바꾼다. 칸마다 선을 따로
    그리는 방법도 있지만, 그러면 6개월 그림 하나가 125조각이 되어 화면에 실어
    보내는 글자가 그만큼 늘어난다. 가로지르는 자리만 끊으면 보통 서넛으로 끝난다.
    """
    # 기준선은 보통 **그림이 시작한 값**이다. 당일 그림만 전일 종가를 밖에서 준다 —
    # 오늘 오르내림을 재는 자리가 거기이기 때문이다(카드에 적힌 등락률과 같은 자).
    base = values[0] if base is None else float(base)
    step = 100.0 / (len(values) - 1)

    def _y(value):
        return 42 - (value - low) * 38 / span

    base_y = _y(base)
    pieces, current, sign = [], [(0.0, base)], None
    for index in range(len(values) - 1):
        x_now, v_now = index * step, values[index]
        x_next, v_next = (index + 1) * step, values[index + 1]
        sign_now = 1 if v_now >= base else -1
        sign_next = 1 if v_next >= base else -1
        if sign is None:
            sign = sign_now if v_now != base else sign_next
        if sign_next == sign or v_next == base:
            current.append((x_next, v_next))
            continue
        # 기준선을 넘는다 — 만나는 자리를 계산해 넣고 거기서 색을 바꾼다.
        share = (base - v_now) / (v_next - v_now) if v_next != v_now else 0.0
        x_cross = x_now + (x_next - x_now) * share
        current.append((x_cross, base))
        pieces.append((sign, current))
        sign, current = sign_next, [(x_cross, base), (x_next, v_next)]
    pieces.append((sign if sign is not None else 1, current))

    body = []
    for piece_sign, piece in pieces:
        if len(piece) < 2:
            continue
        color = _BASE_UP_STROKE if piece_sign >= 0 else _BASE_DOWN_STROKE
        line = " ".join(f"{x:.2f},{_y(v):.2f}" for x, v in piece)
        area = (f"{piece[0][0]:.2f},{base_y:.2f} " + line
                + f" {piece[-1][0]:.2f},{base_y:.2f}")
        body.append(f'<polygon points="{area}" fill="{color}" fill-opacity="0.15"/>')
        body.append(f'<polyline points="{line}" fill="none" stroke="{color}" '
                    'stroke-width="2.1" vector-effect="non-scaling-stroke"/>')
    # 기준선은 **가로로 늘어나도 점 간격이 그대로**여야 한다 — 그래서 여기도
    # vector-effect 를 건다. 안 걸면 크게 연 카드에서 점선이 실선처럼 보인다.
    guide = (f'<line x1="0" y1="{base_y:.2f}" x2="100" y2="{base_y:.2f}" '
             'stroke="rgba(255,255,255,.42)" stroke-width="1" stroke-dasharray="4 4" '
             'vector-effect="non-scaling-stroke"/>')
    return ('<svg class="j3b-chart" viewBox="0 0 100 45" preserveAspectRatio="none">'
            + guide + "".join(body) + "</svg>")


def _six_month_caption(six_month) -> str:
    """「일봉 6개월」 이름표 — **그 6개월 수익률을 같이 적는다** (2026-09-02 지시).

    상하님 — *"관심종목에서 종목을 누르면 일봉 6개월 차트가 나오는데 6개월에
    대한 수익률은 안 나온다."*

    그림만 있고 숫자가 없어서, 반년 동안 얼마나 올랐는지를 눈대중으로 재셔야
    했다. 그림의 **첫 점과 끝 점**으로 잰다 — 그림에 그린 그 구간 그대로다.
    새로 받아 오는 것은 없다.

    6개월치가 아직 안 왔으면 이름표를 아예 안 붙인다(예전 그대로) — 없는 것을
    있는 것처럼 적으면 안 된다.
    """
    points = [float(value) for value in (six_month or []) if value is not None]
    if not points:
        return ""
    first, last = points[0], points[-1]
    if not first:
        return "<div class='j3b-chart-cap'>일봉 6개월</div>"
    ratio = (last / first - 1.0) * 100.0
    tone = "j3b-up" if ratio >= 0 else "j3b-down"
    sign = "+" if ratio >= 0 else ""
    return (f"<div class='j3b-chart-cap'>일봉 6개월 "
            f"<b class='{tone}'>{sign}{ratio:.1f}%</b></div>")


def _briefing_chart(values, change, *, stroke: str = "", baseline: bool = False,
                    base=None) -> str:
    """카드의 작은 그림. ``stroke``를 주면 그 색으로 그린다.

    2026-08-26 상하님 지시 — "관심종목에 일봉 6개월 색깔이 당일 차트 색에 따라
    달라진다." 접힌 카드의 최근 30일 그림은 예전대로 **오늘 오르내림에 따라**
    초록·빨강이고, 크게 연 일봉 6개월만 늘 초록이다. 6개월 그림에 오늘 색을 입히면 반년 흐름을 하루 색으로 말하게 된다.

    ``baseline=True`` 면 **시작가에 점선을 긋고 위아래를 다른 색으로** 그린다
    (2026-08-28 상하님 지시 — 야후 파이낸스 폰 화면의 6개월 그림처럼).
    상하님 — "시작가 위로 초록색이고 밑으로는 붉은색인데 이것처럼 기준선이
    있어야 되지 않나?" 반년 전 종가보다 위인지 아래인지가 선 색으로 바로 읽힌다.
    선이 기준선을 가로지르는 자리는 **정확히 그 지점에서** 색을 바꾼다 — 칸마다
    따로 그리지 않으므로 그림이 무거워지지 않는다(6개월 126칸이 조각 서넛으로 끝난다).

    지수 칸의 `_sparkline_svg`와 **같은 규칙**이다. 다만 이 그림은 가로로 늘여
    그리므로(preserveAspectRatio="none") 선 굵기·점선 간격은 화면 기준으로 못박는다.
    """
    values = [float(item) for item in (values or []) if item is not None]
    if len(values) < 2:
        return ""
    low, high = min(values), max(values)
    span = high - low or 1
    points = " ".join(f"{index * 100 / (len(values)-1):.1f},{42 - (value-low) * 38/span:.1f}" for index, value in enumerate(values))
    if baseline:
        # 기준선을 밖에서 주면(당일 그림의 전일 종가) 그 값도 그림 안에 들어와야
        # 한다 — 안 그러면 기준선이 그림 밖으로 나가 안 보인다.
        if base is not None:
            low = min(low, float(base))
            span = (max(high, float(base)) - low) or 1
        return _briefing_chart_split(values, low, span, base=base)
    stroke = stroke or ("#70e64a" if (change or 0) >= 0 else "#ff5b5b")
    # **선 굵기를 화면 기준으로 못박는다**(2026-08-26 상하님 지적 — "종목 클릭하면
    # 나오는 차트 선이 너무 굵다").
    # 이 그림은 preserveAspectRatio="none" 으로 늘려 그린다. 그러면 선도 같이
    # 늘어난다 — 크게 연 카드는 가로로 6.3배가 되어 선이 7.9px 로 그려지고 있었다
    # (브라우저 실측). vector-effect="non-scaling-stroke" 는 "선은 늘리지 말고
    # 화면 굵기 그대로 그려라"는 뜻이라, 어느 크기에서나 적어 준 만큼만 굵다.
    # 실제 굵기는 CSS에서 정한다 — 접힌 카드와 크게 연 카드가 다르다.
    return (f'<svg class="j3b-chart" viewBox="0 0 100 45" preserveAspectRatio="none">'
            f'<polyline points="{points}" fill="none" stroke="{stroke}" '
            f'stroke-width="2.1" vector-effect="non-scaling-stroke"/></svg>')


def _briefing_items(kind: str, ticker: str | None = None) -> dict:
    result = briefing_news.get_or_schedule(
        kind, ticker, finnhub_key=_briefing_secret("FINNHUB_API_KEY"),
        groq_key=_briefing_secret("GROQ_API_KEY"),
        deepl_key=_briefing_secret("DEEPL_API_KEY"),
        naver_client_id=_briefing_secret("NAVER_CLIENT_ID"),
        naver_client_secret=_briefing_secret("NAVER_CLIENT_SECRET"),
    )
    if result.get("pending"):
        st.session_state["j3b_news_pending"] = True
    return result


def _news_original_html(item: dict) -> str:
    """번역 밑에 펼쳐 보일 원문·출처·기사 링크."""
    brief = str(item.get("brief") or "")
    headline = str(item.get("headline") or "")
    url = str(item.get("url") or "")
    source = str(item.get("source") or "")
    published = str(item.get("published_at") or "")[:16].replace("T", " ")
    parts = []
    if headline and headline != brief:
        parts.append('<div class="j3b-open-label">원문</div>'
                     f'<div class="j3b-open-orig">{html.escape(headline)}</div>')
    if source or published:
        parts.append(f'<div class="j3b-open-src">{html.escape(source)}'
                     f'{" · " + html.escape(published) if published else ""}</div>')
    if url:
        parts.append(f'<a class="j3b-open-link" href="{html.escape(url, quote=True)}" '
                     'target="_blank" rel="noopener noreferrer">원문 기사 열기 ↗</a>')
    if not parts:
        parts.append('<div class="j3b-open-src">원문 주소를 받지 못했습니다.</div>')
    return f'<div class="j3b-open-body">{"".join(parts)}</div>'


def _news_accordion_html(items: list[dict]) -> str:
    """크게 연 화면에서 한 줄을 누르면 원문이 펼쳐지는 목록."""
    rows = []
    for item in items[:3]:
        brief = html.escape(str(item.get("brief") or item.get("headline") or ""))
        rows.append(f'<details class="j3b-open-news"><summary>{brief}</summary>'
                    f'{_news_original_html(item)}</details>')
    return "".join(rows)


def _render_briefing_news(kind: str, ticker: str | None = None) -> list[dict]:
    result = _briefing_items(kind, ticker)
    items = result.get("items") or []
    if not items:
        message = ("뉴스를 불러오는 중입니다" if result.get("pending")
                   else "뉴스를 못 받았습니다 · 맨 위 ↻ 를 누르십시오")
        items = [{"sentiment": "neutral", "brief": message}]
    marks = {"positive": "↗", "negative": "▥", "neutral": "○"}
    collapsed_rows = []
    for item in items[:3]:
        sentiment = item.get("sentiment") if item.get("sentiment") in {"positive", "negative", "neutral"} else "neutral"
        brief = html.escape(str(item.get("brief") or item.get("headline") or ""))
        # 접힌 줄은 **링크가 아니다**. 누르면 기사로 튀지 않고 화면만 커진다
        # (2026-08-26 상하님 지시). 원문은 커진 화면에서 한 줄을 눌러 본다.
        collapsed_rows.append(
            f'<div class="j3b-news"><span class="j3b-news-link"><span class="j3b-news-icon">{marks[sentiment]}</span>'
            f'<span>{brief}</span><span class="j3b-news-dot {sentiment}"></span></span></div>'
        )
    st.markdown(
        '<details class="j3b-market-news-shell">'
        f'<summary class="j3b-market-news-summary">{"".join(collapsed_rows)}</summary>'
        '<div class="j3b-card-open"><div class="j3b-open-card">'
        '<span class="j3b-open-close">× 다시 누르면 닫힘</span>'
        '<div class="j3b-market-news-title">미국시장 한줄 브리핑</div>'
        f'<div class="j3b-open-list">{_news_accordion_html(items)}</div>'
        '<span class="j3b-open-close j3b-open-close-b">✕ 닫기</span>'
        '</div></div></details>',
        unsafe_allow_html=True,
    )
    return items



# (이름표, 파일, 가로:세로) — 이름표는 CSS 갈래 이름으로 쓴다.
_DECOR_IMAGES = (
    ("soot", "soot_lamp_cut.webp", "75/72"),
    ("catlamp", "small_cat_lamp_cut.webp", "102/75"),
    ("totoro", "small_totoro_cut.webp", "99/73"),
    ("bunny", "bunny_bench_cut.webp", "133/101"),
)
_DECOR_BY_TICKER = {
    "NVDA": "soot", "TSLA": "totoro", "PLTR": "catlamp", "AMD": "totoro",
    "AAPL": "catlamp", "META": "soot", "AVGO": "catlamp", "RGTI": "bunny",
}


@st.cache_data(show_spinner=False)
def _decor_css() -> str:
    """캐릭터 그림 네 장을 CSS에 **한 번씩만** 싣는다.

    예전에는 카드마다 그림을 통째로 넣어서, 카드 열두 장이면 같은 그림이 스물네 번
    실려 나갔다. 화면이 무거워진 원인이다(2026-08-26 상하님 지적).
    """
    rules = []
    for name, filename, ratio in _DECOR_IMAGES:
        uri = _briefing_asset_uri(filename)
        if uri:
            rules.append(f".j3b-decor-img.{name}{{background-image:url('{uri}');aspect-ratio:{ratio}}}")
    if not rules:
        return ""
    return ("<style>.j3b-decor-img{background-size:contain;background-repeat:no-repeat;"
            "background-position:bottom right;height:auto!important}" + "".join(rules) + "</style>")

# 로고 그림이 없는 종목의 글자표 — (보일 글자, 바탕색 시작, 바탕색 끝, 글자색).
# 그 회사가 실제로 쓰는 글자와 브랜드 색을 따랐다.
_BRAND_MARKS = {
    "GOOGL": ("G", "#ffffff", "#e6ebf5", "#1a73e8"),
    "GOOG": ("G", "#ffffff", "#e6ebf5", "#1a73e8"),
    "TSM": ("tsmc", "#ee2b39", "#8f0f1a", "#ffffff"),
    "QCOM": ("Q", "#3653dc", "#132a86", "#ffffff"),
    "IONQ": ("IonQ", "#e0348a", "#75104a", "#ffffff"),
    "MSFT": ("MS", "#00a4ef", "#0b4d78", "#ffffff"),
    "AMZN": ("a", "#ff9900", "#8a4b00", "#111827"),
    "INTC": ("intel", "#0068b5", "#023a68", "#ffffff"),
    "MU": ("MU", "#0a2896", "#04123f", "#ffffff"),
    "ARM": ("arm", "#0091bd", "#014a61", "#ffffff"),
    "NFLX": ("N", "#e50914", "#7a0207", "#ffffff"),
    "ORCL": ("O", "#c74634", "#6d1d13", "#ffffff"),
    "SMCI": ("SMCI", "#00843d", "#024420", "#ffffff"),
    "COIN": ("C", "#0052ff", "#012a85", "#ffffff"),
    "MSTR": ("MS", "#f7931a", "#8a4c04", "#111827"),
    "CRWD": ("CS", "#e01f3d", "#73071a", "#ffffff"),
    "PANW": ("PA", "#fa582d", "#822309", "#ffffff"),
    "ADBE": ("A", "#ed2224", "#7c070a", "#ffffff"),
    "UBER": ("Uber", "#111827", "#000000", "#ffffff"),
}


def _briefing_logo_face(ticker: str) -> tuple[str, str]:
    """카드와 궤도가 **함께 쓰는** 회사 로고 한 장.

    회사 로고 **그림**은 앱 안에 넣어 둔 여덟 종목만 있다. 나머지는 그 회사가
    실제로 쓰는 글자표(워드마크)와 브랜드 색으로 보여 준다 — 티커 두 글자만
    잘라 쓰면 무슨 회사인지 알 수 없다(2026-08-26 상하님 지적 — "왜 로고가
    이상하지, 그 회사 로고 맞냐?"). 여기에 없는 종목만 티커 두 글자로 간다.

    앱에 그림이 없는 종목은 companiesmarketcap에서 한 번 받아 두고 그다음부터
    그 그림을 쓴다(2026-08-26 상하님이 알려 주신 곳). 아직 안 왔으면 이번 판은
    글자표로 보여 주고, 다음 판에 그림이 나온다.

    돌려주는 것은 (안에 넣을 HTML, 틀에 붙일 갈래 이름) 둘이다. 2026-08-28에
    고양이버스 궤도가 같은 로고를 쓰게 되면서 카드에서 떼어 냈다 — 두 군데에
    따로 적어 두면 한쪽만 고쳐진다.
    """
    logo_uri = _briefing_logo_uri(ticker)
    logo_kind = ""
    if not logo_uri:
        fetched = us_company_logos.get_or_schedule(ticker)
        if fetched:
            logo_uri = "data:image/webp;base64," + base64.b64encode(fetched).decode("ascii")
            logo_kind = " photo"
    if logo_uri:
        return f'<img src="{logo_uri}" alt="{html.escape(ticker)} logo">', logo_kind
    mark = _BRAND_MARKS.get(ticker.upper())
    if mark:
        text, start, end, ink = mark
    else:
        text, ink = ticker[:2].upper(), "#f4faff"
        hue = sum(ord(letter) for letter in ticker.upper()) * 37 % 360
        start, end = f"hsl({hue} 52% 42%)", f"hsl({hue} 60% 20%)"
    size = ".62em" if len(text) <= 2 else (".40em" if len(text) <= 4 else ".33em")
    return (
        f'<span class="j3b-logo-text" style="background:linear-gradient(145deg,{start},{end});'
        f'color:{ink};font-size:{size}">{html.escape(text)}</span>'
    ), logo_kind


# 궤도를 한 바퀴 도는 데 걸리는 시간. 느긋해야 화면이 안 어지럽다.
_ORBIT_SECONDS = 26.0


def _briefing_orbit_html(stocks: list[dict]) -> str:
    """고양이버스 둘레를 도는 회사 로고들 (2026-08-28 상하님 지시).

    상하님 — "고양이버스에 사용자 선정 종목의 회사 로고들이 조그맣게 해서
    고양이버스 앞에서 움직이면서 고양이 버스에 타는 것을 넣어 줘" · 보내 주신
    영상(catbus_logo_orbit_preview.mp4)처럼 하되 "좀 더 멋있게".

    **어떻게 도나** — 로고마다 팔이 하나씩 있고, 팔이 돌면서 로고를 끌고 다닌다.
    팔을 세로로 눌러 두면(scaleY) 동그라미가 타원이 된다. 로고가 같이 눌리지
    않게 로고 쪽에서 **거꾸로 돌고 거꾸로 늘린다** — 그래서 로고는 늘 똑바로
    선 채로 타원을 돈다.

    **앞뒤가 있다.** 아래쪽 반 바퀴는 버스 **앞**이라 크고 또렷하게, 위쪽 반
    바퀴는 버스 **뒤**라 작고 흐릿하게 지나간다. 버스 그림이 z-index 1이므로
    앞은 5, 뒤는 0을 준다 — 로고가 버스 뒤로 사라졌다 앞으로 나온다.

    **자바스크립트를 안 쓴다.** 스트림릿은 st.markdown 안의 <script>를 지운다.
    움직이는 것은 전부 CSS이고, 브라우저가 그리는 일이라 서버를 다시 안 부른다.
    """
    riders = [stock for stock in (stocks or []) if str(stock.get("ticker") or "").strip()][:5]
    if not riders:
        return ""
    pods = []
    for index, stock in enumerate(riders):
        ticker = str(stock["ticker"]).upper()
        face, kind = _briefing_logo_face(ticker)
        # 다 같은 자리에서 출발하면 한 덩어리로 몰려 다닌다. 시작 시각을 한 바퀴
        # 나눠 주면 서로 같은 간격으로 벌어진다.
        delay = -_ORBIT_SECONDS * index / len(riders)
        pods.append(
            f'<span class="j3b-orbit-arm" style="animation-delay:{delay:.2f}s">'
            f'<span class="j3b-orbit-pod" style="animation-delay:{delay:.2f}s">'
            f'<span class="j3b-orbit-logo" style="animation-delay:{delay:.2f}s">'
            f'<span class="j3b-logo{kind} {html.escape(ticker.lower())}">{face}</span>'
            f'<span class="j3b-orbit-tag">{html.escape(ticker)}</span>'
            "</span></span></span>"
        )
    return f'<div class="j3b-orbit" aria-hidden="true">{"".join(pods)}</div>'


def _render_briefing_card(stock: dict, card: dict, *, removable: bool = False, compact: bool = False) -> None:
    ticker = stock["ticker"]
    price, change = card.get("price"), card.get("change_pct")
    tone = "j3b-up" if (change or 0) > 0 else "j3b-down" if (change or 0) < 0 else "j3b-neutral"
    price_text = f"{price:,.2f}" if isinstance(price, (float, int)) else "시세 준비 중"
    change_text = f"{change:+.2f}%" if isinstance(change, (float, int)) else "—"
    news_result = _briefing_items("company", ticker)
    items = news_result.get("items") or []
    if items:
        notes = items[:3]
    elif news_result.get("pending"):
        notes = [{"brief": "뉴스를 불러오는 중입니다"}]
    else:
        # 2026-08-26 상하님 지적 — 「불러오는 중」에서 굳어 있으면 손쓸 데가 없었다.
        # 무엇을 누르면 되는지 적는다. 맨 위 ↻ 가 다시 받아 온다.
        notes = [{"brief": "뉴스를 못 받았습니다 · 맨 위 ↻ 를 누르십시오"}]
    # 접힌 카드의 뉴스 줄은 **링크가 아니다**(2026-08-26 상하님 지시 — "기본 작은
    # 화면에서 종목 밑에 뉴스 클릭하면 바로 뉴스로 들어가지 않게 화면만 크게 하고").
    # 원문은 커진 화면에서 그 줄을 다시 눌러 본다.
    note_html = "".join(
        f'<div class="j3b-note">{html.escape(str(item.get("brief") or item.get("headline") or "뉴스 브리핑 준비 중"))}</div>'
        for item in notes
    )
    logo_html, logo_kind = _briefing_logo_face(ticker)
    direction = "decline" if (change or 0) < 0 else ""
    # 캐릭터는 **모든 카드**에 붙인다(2026-08-26 상하님 — "각 종목에 캐릭터랑
    # 똑같게 다 넣어줘"). 익숙한 여덟 종목은 쓰던 캐릭터를 그대로 두고, 새로
    # 넣으신 종목은 티커에서 뽑아 늘 같은 캐릭터가 나오게 한다.
    decor_name = _DECOR_BY_TICKER.get(ticker.upper()) or _DECOR_IMAGES[
        sum(ord(letter) for letter in ticker.upper()) % len(_DECOR_IMAGES)
    ][0]
    decor_side = " left" if ticker == "AAPL" else ""
    decor_html = f'<span class="j3b-decor-img {decor_name}{decor_side}"></span>'
    # 삭제는 저장된 추가 종목의 실제 Streamlit 버튼만 보여 준다.
    delete_visual = ""
    card_body = (
        f'<div class="j3b-card {direction}{" compact" if compact else ""}"><div class="j3b-card-top">'
        f'<span class="j3b-logo{logo_kind} {html.escape(ticker.lower())}">{logo_html}</span><div>'
        f'<span class="j3b-symbol">{html.escape(ticker)}</span>'
        f'<span class="j3b-name">{html.escape(stock.get("name") or card.get("name") or ticker)}</span></div></div>'
        f'<div class="j3b-price">{price_text} <span class="{tone}">{change_text}</span></div>'
        # **접힌 카드 그림은 당일이다**(2026-08-28 상하님 지적 — "각 종목들 차트가
        # 종가 기준 일봉 차트 맞냐? 뭐가 뭔지 모르겠다. 당일 종가가 되면 당일
        # 차트를 해 줘야지"). 바로 왼쪽에 적히는 값·등락률이 오늘 것인데 그림만
        # 최근 30일이라 둘이 다른 이야기를 하고 있었다. 기준선은 전일 종가다 —
        # 등락률을 재는 자리와 같다. 당일 자료가 없는 날(주말·휴장)에는 예전처럼
        # 최근 30일을 그린다.
        f'{_briefing_chart(card.get("chart_today") or card.get("chart"), change, baseline=bool(card.get("chart_today")), base=card.get("prev_close"))}'
        f'<div class="j3b-card-notes">{note_html}</div>'
        f'{delete_visual}{decor_html}</div>'
    )
    six_month = [float(v) for v in (card.get("chart6m") or []) if v is not None]
    open_card = (
        f'<div class="j3b-open-card {direction}">'
        '<span class="j3b-open-close">× 다시 누르면 닫힘</span>'
        f'<div class="j3b-card-top"><span class="j3b-logo{logo_kind} {html.escape(ticker.lower())}">{logo_html}</span><div>'
        f'<span class="j3b-symbol">{html.escape(ticker)}</span>'
        f'<span class="j3b-name">{html.escape(stock.get("name") or card.get("name") or ticker)}</span></div></div>'
        f'<div class="j3b-price">{price_text} <span class="{tone}">{change_text}</span></div>'
        # 크게 열면 **일봉 6개월**이다(2026-08-26 상하님 지시 — "관심종목에 종목
        # 클릭하면 일봉 6개월 차트 나오고 밑에 종목 뉴스 나오게 해 줘").
        # 접힌 카드의 작은 그림은 예전 그대로 최근 30일이다. 6개월치가 아직 안
        # 왔으면 그 30일 그림을 그대로 쓰고 이름표도 안 붙인다 — 없는 것을 있는
        # 것처럼 적으면 안 된다.
        f'{_briefing_chart(six_month or card.get("chart"), change, baseline=bool(six_month))}'
        f'{_six_month_caption(six_month)}'
        f'<div class="j3b-open-list">{_news_accordion_html(notes)}</div>'
        '<span class="j3b-open-close j3b-open-close-b">✕ 닫기</span>'
        f'{decor_html}</div>'
    )
    card_html = (
        '<details class="j3b-card-shell"><summary class="j3b-card-summary" '
        'title="누르면 크게 보기">'
        f'{card_body}</summary>'
        f'<div class="j3b-card-open">{open_card}</div></details>'
    )
    if removable:
        position = int(stock["position"])
        with st.container(key=f"j3b_extra_{position}"):
            st.markdown(card_html, unsafe_allow_html=True)
            confirm = st.session_state.get("j3b_delete_confirm") == position
            if confirm:
                left, right = st.columns(2)
                if left.button("삭제 확인", key=f"j3b_del_yes_{position}"):
                    briefing_store.remove_extra(position)
                    st.session_state.pop("j3b_delete_confirm", None)
                    st.rerun()
                if right.button("취소", key=f"j3b_del_no_{position}"):
                    st.session_state.pop("j3b_delete_confirm", None)
                    st.rerun()
            elif st.button("×", key=f"j3b_del_{position}"):
                st.session_state["j3b_delete_confirm"] = position
                st.rerun()
        return
    st.markdown(card_html, unsafe_allow_html=True)


def _render_briefing_grid(stocks: list[dict], cards: dict, *, removable: bool, key: str, compact: bool = False) -> None:
    """카드를 **한 통에 죽 넣고 자리는 CSS가 잡는다** (2026-08-27 상하님 지시).

    상하님 — "태블릿 화면에는 종목선정 2줄씩 되어 있는데 3칸씩 넣으면 안 되나?"

    예전에는 파이썬이 **두 개씩 묶어** st.columns(2)로 그렸다. 그러면 몇 칸으로
    놓을지가 파이썬에 박혀 버려서, 화면 폭에 따라 바꿀 수가 없다 — 파이썬은
    상하님 화면이 얼마나 넓은지 모른다.
    이제 카드를 한 줄로 죽 넣고, 몇 칸으로 놓을지는 CSS가 정한다.
    폰 2칸 · 태블릿 3칸이다. 줄마다 만들던 껍데기도 같이 없어진다.
    """
    with st.container(key=f"j3b_grid_{key}"):
        for stock in stocks:
            can_remove = removable and int(stock.get("position", 0)) > 0
            _render_briefing_card(stock, cards.get(stock["ticker"], {}), removable=can_remove, compact=compact)


_BRIEFING_FIRST_VIEW_EXTRAS = (
    {"position": -1, "ticker": "AAPL", "name": "애플"},
    {"position": -2, "ticker": "META", "name": "메타 플랫폼스"},
    {"position": -3, "ticker": "AVGO", "name": "브로드컴"},
    {"position": -4, "ticker": "RGTI", "name": "리게티 컴퓨팅"},
)


def _briefing_home_extras(extras: list[dict]) -> list[dict]:
    """기본 4종목을 유지하고 저장된 추가 종목은 중복 없이 뒤에 붙인다."""
    merged = [dict(item) for item in _BRIEFING_FIRST_VIEW_EXTRAS]
    positions = {item["ticker"]: index for index, item in enumerate(merged)}
    for extra in extras:
        ticker = str(extra.get("ticker") or "").upper()
        if ticker in positions:
            merged[positions[ticker]] = dict(extra)
        else:
            positions[ticker] = len(merged)
            merged.append(dict(extra))
    return merged


def _briefing_local_search(query: str) -> list[dict]:
    """이미 보유한 미국 종목 명부에서 즉시 찾는다.

    브리핑 화면의 ``+`` 버튼 때문에 미국 거래소 명부를 인터넷에서 다시 받으면
    첫 클릭이 오래 걸린다. 기존 약 200종목 명부와 한글 별칭만 재사용한다.
    """
    text = str(query or "").strip()
    if not text:
        return []
    aliases = getattr(j3data, "KOREAN_TICKER_ALIASES", {})
    names = getattr(j3data, "STOCK_NAMES", {})
    universe = tuple(getattr(j3data, "US_LARGE_CAP_UNIVERSE", ()))
    normalized = text.replace(" ", "")
    alias_ticker = aliases.get(normalized)
    upper = normalized.upper()
    lowered = normalized.lower()
    ordered = []
    if alias_ticker:
        ordered.append(alias_ticker)
    ordered.extend(ticker for ticker in universe if ticker == upper)
    ordered.extend(ticker for ticker in universe if ticker.startswith(upper))
    ordered.extend(
        ticker for ticker in universe
        if str(names.get(ticker, ticker)).lower().replace(" ", "").startswith(lowered)
    )
    ordered.extend(
        ticker for ticker in universe
        if lowered in str(names.get(ticker, ticker)).lower().replace(" ", "")
    )
    rows, seen = [], set()
    for ticker in ordered:
        if ticker in seen:
            continue
        seen.add(ticker)
        rows.append({"ticker": ticker, "name": names.get(ticker, ticker), "market": "US"})
        if len(rows) >= 12:
            break
    if rows:
        return rows
    # 앱이 들고 있는 200종목 명부에 없으면 **미국 거래소 전체 명부**에서 찾는다.
    # 2026-08-26 상하님 지적 — SPCX(스페이스X)가 안 들어갔다. 200종목에 없어서였다.
    # 처음 한 번은 명부를 받느라 몇 초 걸리고, 그다음부터는 바로 나온다.
    try:
        found = j3data.search_stocks(query, limit=12)
    except Exception:
        return []
    return list(found.get("rows") or []) if found.get("ok") else []


def _render_briefing_manage(selected: list[dict], extras: list[dict]) -> None:
    """종목을 찾아 보여 주고, **맞는지 확인한 뒤에** 넣는다.

    2026-08-26 상하님 지시 — "종목 검색은 조회 후 종목 나타나고 이 종목이 맞는지
    확인 버튼을 누르고 등록되도록 해야지."
    예전에는 ＋를 누르면 찾은 첫 종목이 곧바로 들어갔다. 이름이 비슷한 다른 회사가
    들어가도 알 수가 없었다.
    """
    with st.container(key="j3b_search_row"):
        query_col, plus_col = st.columns([7, 1])
        with query_col:
            query = st.text_input("종목 검색", placeholder="종목 검색 후 추가",
                                  key="j3b_search", label_visibility="collapsed")
        with plus_col:
            add_clicked = st.button("+", key="j3b_manage_toggle")
    if add_clicked:
        st.session_state.pop("j3b_search_found", None)
        if not query.strip():
            st.session_state["j3b_search_message"] = "추가할 종목명이나 티커를 먼저 넣으십시오."
        else:
            with st.spinner("미국 종목 명부에서 찾는 중입니다…"):
                rows = _briefing_local_search(query)
            if rows:
                st.session_state["j3b_search_found"] = rows[:5]
            else:
                st.session_state["j3b_search_message"] = "그 이름으로는 미국 종목을 찾지 못했습니다."

    found = st.session_state.get("j3b_search_found") or []
    if found:
        with st.container(key="j3b_search_confirm"):
            labels = {f'{row["ticker"]} · {row["name"]}': row for row in found}
            names = list(labels)
            picked = names[0]
            if len(names) > 1:
                picked = st.radio("찾은 종목 가운데 고르십시오", names, key="j3b_search_pick")
            else:
                st.markdown(f"<div class='j3b-found'>{html.escape(picked)}</div>",
                            unsafe_allow_html=True)
            yes_col, no_col = st.columns(2)
            if yes_col.button("이 종목이 맞습니다 · 추가", key="j3b_search_ok", type="primary"):
                chosen = labels[picked]
                try:
                    briefing_store.add_extra(chosen["ticker"], chosen["name"])
                    st.session_state["j3b_search_message"] = f'{chosen["ticker"]} 종목을 넣었습니다.'
                    st.session_state.pop("j3b_search_found", None)
                    st.rerun()
                except ValueError as exc:
                    st.session_state["j3b_search_message"] = str(exc)
            if no_col.button("아닙니다 · 취소", key="j3b_search_cancel"):
                st.session_state.pop("j3b_search_found", None)
                st.rerun()

    message = st.session_state.pop("j3b_search_message", "")
    if message:
        st.caption(message)



def _schedule_briefing_news_refresh(keys: tuple = ()) -> None:
    """뉴스가 다 온 뒤에 화면을 딱 한 번만 다시 그린다.

    예전에는 2.5초마다 `window.parent.location.reload()`로 브라우저를 통째로
    새로고침했다. 통째 새로고침이라 자비스3 계산이 처음부터 다시 돌고, 화면이 튀고,
    스크롤이 맨 위로 돌아갔다(2026-08-26 상하님 — "화면이 계속 버벅거리더라").
    이 조각은 '뉴스가 다 왔나'만 조용히 살피고, 다 왔을 때 한 번 다시 그린다.
    """
    if not st.session_state.get("j3b_news_pending"):
        st.session_state.pop("j3b_news_wait", None)
        st.session_state.pop("j3b_news_ready", None)
        return
    waited = int(st.session_state.get("j3b_news_wait", 0)) + 1
    st.session_state["j3b_news_wait"] = waited
    try:
        ready = briefing_news.ready_count(keys)
    except Exception:
        ready = len(keys)
    # 다 오기를 기다리지 않는다. 새로 도착한 자리가 생길 때마다 그만큼 채워 그려서
    # 위쪽 시장 브리핑과 사용자 선정 종목이 먼저 차고 추가 검색 종목이 뒤따르게 한다.
    # 2분이 넘으면 더 기다리지 않는다. 못 온 자리는 ↻ 를 눌러 다시 받으면 된다.
    if ready <= int(st.session_state.get("j3b_news_ready", 0)) and waited < 60:
        return
    st.session_state["j3b_news_ready"] = ready
    if ready >= len(keys) or waited >= 60:
        st.session_state["j3b_news_pending"] = False
        st.session_state.pop("j3b_news_wait", None)
        st.session_state.pop("j3b_news_ready", None)
    st.rerun()


@st.fragment(run_every=2)
def _briefing_news_watcher(keys: tuple = ()) -> None:
    """뉴스가 **도착하는지 지켜보다가** 왔을 때 화면을 다시 그린다 (2026-09-02).

    상하님 — *"관심종목에 「뉴스 불러오는 중이다」라고 계속 떠 있다. 위에
    다시 실행하기 하면 그제서야 뉴스가 나온다."*

    **왜 굳어 있었나.** 뉴스는 뒤 일꾼이 받아 온다. 화면은 그걸 기다리며
    「불러오는 중」이라고 적어 두는데, **기다리는 동안 화면을 다시 그려 보는
    것이 아무것도 없었다.** `_schedule_briefing_news_refresh` 는 아직 안 왔으면
    그냥 되돌아가고 끝난다 — 다음 판이 없으니 영영 그 자리다. 그래서 ↻ 를 눌러
    사람이 손으로 다음 판을 만들어 주어야만 뉴스가 나왔다.

    예전에는 2.5초마다 브라우저를 통째로 새로고침해서 이 문제가 없었다. 그런데
    통째 새로고침은 화면이 튀고 스크롤이 맨 위로 돌아가 2026-08-26에 걷어냈고,
    그 자리를 채울 것을 안 두었다.

    **이 조각이 그 자리를 채운다.** 2초마다 도는데, 도는 것은 **이 조각뿐**이다
    (프래그먼트라 판 전체를 안 그린다). 하는 일도 이미 받아 둔 것을 세는 것뿐이라
    시세를 새로 부르지 않는다. **새로 도착한 것이 있을 때만** 판 전체를 한 번
    다시 그린다 — 그때가 화면에 뉴스가 채워지는 순간이다.

    2분이 지나도 안 오면 기다리기를 그만둔다. 그러면 카드에 「못 받았습니다 ·
    맨 위 ↻ 를 누르십시오」가 뜬다 — 지금까지와 같다.

    **실패해도 아무 일도 일어나지 않아야 한다.** 세다가 터지면 조용히 넘어가고,
    화면은 지금 그대로 있는다(CLAUDE.md 13번과 같은 원칙).
    """
    if not st.session_state.get("j3b_news_pending"):
        return
    try:
        ready = int(briefing_news.ready_count(keys))
    except Exception:
        return                      # 못 세면 다음 2초에 다시 본다
    seen = st.session_state.get("j3b_news_watch_seen")
    if seen is None:
        # 처음 한 바퀴는 기준만 잡는다. 여기서 바로 다시 그리면 화면이 헛돈다.
        st.session_state["j3b_news_watch_seen"] = ready
        st.session_state["j3b_news_watch_since"] = time.monotonic()
        return
    since = float(st.session_state.get("j3b_news_watch_since") or time.monotonic())
    over = (time.monotonic() - since) > 120
    if ready <= int(seen) and not over:
        return                      # 아직 새로 온 것이 없다 — 화면을 안 건드린다
    st.session_state["j3b_news_watch_seen"] = ready
    if over or ready >= len(keys):
        st.session_state["j3b_news_pending"] = False
        st.session_state.pop("j3b_news_watch_seen", None)
        st.session_state.pop("j3b_news_watch_since", None)
    # 판 전체를 다시 그린다 — 카드가 프래그먼트 밖에 있어서 여기만 그리면
    # 뉴스가 화면에 안 나타난다. scope 를 못 받는 판이면 그냥 전체다.
    try:
        st.rerun(scope="app")
    except Exception:
        st.rerun()


def _warm_after_news(keys: tuple) -> None:
    """뉴스가 다 온 **뒤에** 순위 9와 나스닥 25년치를 미리 챙긴다.

    **뉴스보다 먼저 시작하면 안 된다** (2026-08-26 상하님 지적 — "노트북 메인화면
    관심종목 로딩이 오래 걸린다", "관심종목에 뉴스 전부 다 안 나온다").

    오늘 제가 이 미리 계산을 화면 그리기 **맨 앞**에 두었다. 파이썬은 한 번에 한
    가지만 계산한다. 그래서 뒤 일꾼이 테마 20개와 순위 9를 계산하는 동안(17초)
    첫 화면 그리기와 뉴스 받기가 그만큼 밀렸다. 시장분석 화면은 이 도우미를
    안 불러서 멀쩡했고, 그것이 "시장분석은 잘 열리는데 관심종목만 느리다"의
    까닭이다.

    이제 뉴스가 **다 온 뒤에만** 시작한다. 그때는 상하님이 화면을 보고 계실
    때라 뒤에서 무엇을 하든 기다리실 것이 없다.
    """
    try:
        if not briefing_news.all_ready(keys):
            return
    except Exception:
        return
    # 시장분석 화면이 그 판에서 처음 열릴 때 받는 신호 시세 13개도 같이 미리
    # 받아 둔다(2026-08-26 상하님 지적 — "관심종목에서 시장분석 클릭하면 로딩 3초").
    signal_warm = getattr(market_signal_ui, "warm_us_signal_quotes", None)
    if callable(signal_warm):
        try:
            signal_warm()
        except Exception:
            pass
    # 시장분석 화면의 업종 지도도 여기서 미리 받아 둔다(2026-08-28). 2초쯤
    # 걸리는 조회라 그 화면에서 받으면 화면이 그만큼 밀린다.
    sector_warm = getattr(j3data, "warm_sector_map", None)
    if callable(sector_warm):
        try:
            sector_warm()
        except Exception:
            pass
    warm = getattr(j3data, "warm_top_picks", None)
    if not callable(warm):
        return
    try:
        warm()
    except Exception:
        pass


# 지금 보고 있는 화면(관심종목 home · 시장분석 market)을 **주소에도 적어 둔다**
# (2026-08-29 상하님 지시).
#
# 상하님 — *"스마트폰에서 멀티스크린, 즉 다른 화면 예를 들면 네이버 화면 잠깐
# 보고 돌아오면 또 리셋되며 로딩시간이 걸린다. 그리고 시장분석 보고 있다가
# 다른 화면 갔다가 다시 오면 관심종목으로 가버린다."*
#
# **왜 그랬나.** 폰은 다른 앱으로 넘어가면 뒷화면을 메모리에서 버린다. 돌아오면
# 브라우저가 그 주소를 **처음부터 다시** 연다. 스트림릿의 세션 기억
# (`st.session_state`)은 그때 통째로 비므로, 어느 화면을 보고 있었는지도 같이
# 사라져 기본값인 관심종목으로 돌아갔다.
#
# **주소는 안 사라진다.** 다시 열 때 브라우저가 같은 주소를 그대로 쓰기 때문이다.
# 그래서 화면 이름을 주소 끝에 적어 둔다(`?s=market`). 세션이 비어도 주소가
# 남아 있으면 보시던 화면으로 돌아간다.
#
# 로딩 시간 자체는 이걸로 줄지 않는다 — 다시 여는 것은 브라우저가 하는 일이다.
# 다만 **엉뚱한 화면을 다시 그리느라 두 번 기다리는 일**은 없어진다.
#
# 뒤로가기와도 어긋나지 않는다. 주소가 바뀌면 방문기록이 한 칸 쌓이므로,
# 시장분석에서 뒤로가기를 누르면 앞 메뉴가 아니라 **관심종목**으로 온다.
# (`back_nav`의 표식은 그대로 두어 관심종목에서 또 눌러도 안 빠져나간다.)
_BRIEFING_PAGE_PARAM = "s"
# 화면 넷 — 홈(새) · 관심종목(옛 첫 화면) · 시장분석 · 기록/성과.
_BRIEFING_PAGES = ("home", "watch", "market", "record")


def _briefing_page() -> str:
    """지금 볼 화면. **세션 기억이 먼저**, 없을 때만 주소를 본다.

    **차례가 중요하다** (2026-08-29 상하님 지시 — "뒤로가기 버튼 누르더라도
    안 되게 하라니깐"). 주소를 먼저 보면, 뒤로가기가 주소에서 `s=market` 을
    지웠을 때 그것을 '관심종목으로 가라'로 읽어 화면이 바뀐다. 상하님은
    **아무 일도 안 일어나기를** 바라신다.
    세션 기억을 먼저 보면 뒤로가기로 주소가 바뀌어도 보시던 화면 그대로다.
    바로 아래 `_set_briefing_page` 가 주소를 도로 적으므로, 몇 번을 눌러도
    앱 밖으로 나가지 않는다.

    **주소는 그래도 필요하다** — 폰이 화면을 버렸다 다시 열면 세션 기억이
    통째로 비는데, 그때 주소에 적힌 것이 보시던 화면을 되살린다.

    주소를 못 읽으면 조용히 세션 기억만으로 돈다 — 이 장치 때문에 화면이
    막히면 안 된다(CLAUDE.md 13번 쿠키 규칙과 같은 뜻).
    """
    page = str(st.session_state.get("j3_briefing_page") or "")
    if page in _BRIEFING_PAGES:
        return page
    try:
        marked = str(st.query_params.get(_BRIEFING_PAGE_PARAM) or "").strip()
    except Exception:
        marked = ""
    if marked in _BRIEFING_PAGES:
        st.session_state["j3_briefing_page"] = marked
        return marked
    return "home"


def _set_briefing_page(page: str) -> None:
    """볼 화면을 정하고 **주소에도 적는다.** 이미 같으면 안 적는다.

    같은 값을 또 적으면 방문기록만 한 칸 더 쌓여 뒤로가기가 헛돈다.
    """
    page = page if page in _BRIEFING_PAGES else "home"
    st.session_state["j3_briefing_page"] = page
    try:
        if str(st.query_params.get(_BRIEFING_PAGE_PARAM) or "") != page:
            st.query_params[_BRIEFING_PAGE_PARAM] = page
    except Exception:
        pass


def _render_briefing_bottom_nav(active: str) -> None:
    """종목 브리핑과 시장분석에서 같이 보이는 하단 이동표."""
    # 시장분석 그림만 글자가 아니라 **직접 그린 그림**이다(2026-08-26 상하님 지시 —
    # "하단 시장분석 크기 봐라... 노트북처럼 크게 좀 하고, 전체 하단 크기는 맞다,
    # 그 크기 안에 피자 동그라미 모양을 크게 좀 하라고").
    # 이유 — ◕ 라는 글자는 기기마다 다른 글꼴이 그린다. 갤럭시는 이 글자를 작게
    # 그리고 노트북은 크게 그려서, 같은 27px 을 줘도 폰에서만 작아 보였다.
    # 직접 그리면 어느 기기에서나 같은 크기다.
    pie = ('<svg class="j3b-pie" viewBox="0 0 32 32" aria-hidden="true">'
           '<circle cx="16" cy="16" r="13.2" fill="none" stroke="currentColor" stroke-width="2.6"/>'
           '<path d="M16 16 L16 4.2 A11.8 11.8 0 1 1 4.2 16 Z" fill="currentColor"/></svg>')
    # 기록/성과 그림도 **직접 그린다** — 이모지는 기기마다 크기가 달라진다
    # (시장분석의 동그라미를 직접 그린 것과 같은 까닭).
    clip = ('<svg class="j3b-pie" viewBox="0 0 32 32" aria-hidden="true">'
            '<rect x="7" y="5.5" width="18" height="22" rx="2.6" fill="none" '
            'stroke="currentColor" stroke-width="2.4"/>'
            '<rect x="12" y="2.6" width="8" height="5" rx="1.6" fill="currentColor"/>'
            '<path d="M11.5 17.2 L14.6 20.3 L20.8 13.4" fill="none" stroke="currentColor" '
            'stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>')
    labels = (("home", "⌂", "홈"), ("watch", "★", "관심종목"),
              ("market", pie, "시장분석"), ("record", clip, "기록/성과"))
    items = "".join(
        f'<span class="j3b-nav-item{" active" if key == active else ""}"><b>{icon}</b>{label}</span>'
        for key, icon, label in labels
    )
    st.markdown(f'<nav class="j3b-bottom-nav">{items}</nav>', unsafe_allow_html=True)
    with st.container(key="j3b_nav_controls"):
        home_col, watch_col, market_col, record_col = st.columns(4, gap="small")
        # **홈은 이 화면 안이다.** 옛 미국테마에서는 이 단추가 「어디로 갈까요」로
        # 나갔지만, 새 디자인의 홈은 오늘의 판단이 있는 첫 화면이다.
        if home_col.button("홈", key="j3b_nav_home"):
            _set_briefing_page("home")
            st.rerun()
        # **화면을 바꾸면 맨 위로 올라간다** (2026-08-27 상하님 지적 — "맨 위에
        # 화면이 다 사라졌다"). 브라우저는 화면을 바꿔도 굴려 둔 자리를 그대로
        # 들고 간다. 관심종목에서 아래로 내려보시다 시장분석을 누르면 그 자리에
        # 그대로 서서, 맨 위의 「한국테마 →」·「이 테마 설명」 두 단추를 지나친
        # 자리가 보였다. 예전에는 위에 224px 빈자리가 있어 그것이 가려 줬는데,
        # 그 빈자리를 없애니 드러났다.
        # 맨 위로 올리는 일은 **여기서 적어 두지 않는다** (2026-08-29).
        # _render_stock_briefing 이 화면이 바뀐 것을 보고 그 판 **맨 앞에서**
        # 바로 올린다. 여기서 적어 두면 그 표시가 판 끝(20개 테마를 다 받은 뒤)
        # 에서 쓰여, 그동안 내려 보고 계시던 화면을 뿌리치고 끌어올린다.
        if watch_col.button("관심종목", key="j3b_nav_watch"):
            _set_briefing_page("watch")
            st.rerun()
        if market_col.button("시장분석", key="j3b_nav_market"):
            _set_briefing_page("market")
            st.rerun()
        if record_col.button("기록/성과", key="j3b_nav_record"):
            _set_briefing_page("record")
            st.rerun()


# ── 새 디자인 (자비스6 미국테마) ────────────────────────────────────────────
# 2026-09-03 상하님 지시로 만든 껍데기다. **값을 만드는 코드는 하나도 없다** —
# 위쪽에 그대로 옮겨 온 함수들이 만든 값을 받아 다르게 그리기만 한다.
# 그래서 옛 미국테마와 같은 날 열면 숫자가 똑같아야 한다. 다르면 그것이 버그다.
#
# 이름은 `j6-` 로 시작한다. 옛 껍데기(`j3-`·`j3b-`)와 이름이 겹치지 않으니
# 한쪽을 고쳐도 다른 쪽이 딸려 바뀌지 않는다.
_J6_CSS = """
<style>
.j6-sec {
    display: flex; align-items: center; gap: .45rem;
    margin: 1.15rem 0 .55rem; color: #eaf2ff;
    font-size: 1.06rem; font-weight: 800; letter-spacing: -.01em;
}
.j6-sec .j6-sec-more { margin-left: auto; color: #7fb6ff; font-size: .86rem; font-weight: 700; }

/* ── 위 여백 ──────────────────────────────────────────────────────────────
   스트림릿이 화면 맨 위에 제 막대(60px · 불투명)를 **덮어 그린다**. 그것을
   비켜 주지 않으면 머리띠가 그 밑에 깔려 안 보인다(2026-09-03 폰에서 실측 —
   머리띠는 top 8px 에 멀쩡히 있는데 z-index 999990 짜리 막대가 덮고 있었다).
   노트북에서는 원래 위 여백이 커서 안 가려졌지만, 그 여백이 화면 한 판을
   먹고 있었다. 양쪽을 같은 값으로 맞춘다. */
body:has(.j6-app) [data-testid="stMainBlockContainer"],
body:has(.j6-app) .block-container {
    padding-top: 68px !important;
    /* 하단 이동표가 화면에 붙어 떠 있다 — 그만큼 아래를 비워 두지 않으면
       마지막 칸이 그 밑에 깔린다(2026-09-03 폰에서 실측). */
    padding-bottom: 84px !important;
}

/* 규칙만 담은 빈 칸이 자리를 먹고 있었다 (2026-09-03 실측 — 176px).
   스트림릿은 칸을 세로로 쌓으면서 **칸마다 16px 을 벌린다.** `<style>` 만 든
   칸은 높이가 0인데도 그 벌림은 그대로 들어가, 규칙 열한 벌이 화면 한 판을
   먹었다. 안 보이게 하면 벌림도 같이 사라진다 —
   `<style>` 은 안 보이는 칸 안에 있어도 그대로 걸린다. */
body:has(.j6-app) [data-testid="stElementContainer"]:has(
    [data-testid="stMarkdownContainer"] > style:only-child) { display: none !important; }

/* 「맨 위로」가 데려다 주는 자리는 **상단 막대만큼 낮춰 둔다.** 안 그러면
   머리띠가 그 막대 밑으로 들어가 안 보인다(2026-09-03 폰에서 실측). */
body:has(.j6-app) .jarvis-anchor { scroll-margin-top: 76px; }

/* ── 머리띠 ───────────────────────────────────────────────────────────── */
.j6-head { display: flex; align-items: center; gap: .55rem; padding: .55rem .2rem .35rem; }
.j6-brand { font-size: 1.5rem; font-weight: 900; color: #ffffff; letter-spacing: -.02em; }
.j6-brand b { color: #4da6ff; }
.j6-chip {
    padding: .16rem .5rem; border-radius: .45rem; font-size: .8rem; font-weight: 800;
    color: #cfe3ff; border: 1px solid rgba(120,180,255,.45); background: rgba(77,166,255,.10);
}
.j6-live {
    margin-left: auto; display: inline-flex; align-items: center; gap: .35rem;
    padding: .22rem .62rem; border-radius: 999px; font-size: .82rem; font-weight: 800;
    color: #d8f5e6; border: 1px solid rgba(68,240,161,.45); background: rgba(68,240,161,.08);
}
.j6-live i { width: 7px; height: 7px; border-radius: 50%; background: #44f0a1; display: inline-block; }

/* ── 판(카드) 공통 ────────────────────────────────────────────────────── */
.j6-panel {
    border: 1px solid rgba(120,180,255,.22); border-radius: 16px;
    background: linear-gradient(160deg, rgba(23,38,68,.92) 0%, rgba(12,20,38,.92) 100%);
    box-shadow: inset 0 1px rgba(150,200,255,.10), 0 8px 22px rgba(0,0,0,.45);
    padding: .9rem 1rem;
}

/* ── 오늘의 판단 — 안은 시장분석의 그 상자(fg-box) 그대로다 ──────────────
   상자를 새로 만들지 않고 **겉옷만 벗긴다.** 그래야 점수·국면·행동 한 줄이
   시장분석과 늘 같은 것으로 남는다. */
.j6-verdict { padding: .75rem .9rem; }
/* **앞에 `body:has(.j6-app)` 를 붙이는 까닭** — 아래 새 껍데기(_J6_SKIN_CSS)가
   `.fg-box` 를 판으로 만드는데, 그 규칙이 더 세서 판 안에 판이 하나 더 생겼다
   (2026-09-03 폰에서 실측). 여기가 더 세야 겉옷을 벗길 수 있다. */
body:has(.j6-app) .j6-verdict .fg-box {
    display: block !important; width: 100% !important;
    border: 0 !important; background: transparent !important;
    padding: 0 !important; box-shadow: none !important; border-radius: 0 !important;
}
body:has(.j6-app) .j6-verdict .fg-box:hover { transform: none; filter: none; }
.j6-verdict .fg-box-title { font-size: 1rem !important; }
.j6-verdict .fg-box-body { gap: 1rem; flex-wrap: wrap; }
/* '그래서 무엇을 하라' 한 줄이 이 화면의 주인공이다 — 크게 띄운다. */
.j6-verdict .fg-box-foot {
    font-size: 1.45rem !important; font-weight: 900 !important;
    line-height: 1.35 !important; margin-top: .55rem !important; padding-top: .5rem !important;
}

/* ── 지수 넉 장 ───────────────────────────────────────────────────────── */
.j6-idx-row { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: .55rem; }
@media (max-width: 600px) { .j6-idx-row { grid-template-columns: repeat(2, minmax(0,1fr)); } }
.j6-idx {
    border: 1px solid rgba(120,180,255,.20); border-radius: 13px;
    background: linear-gradient(165deg, rgba(20,34,60,.9) 0%, rgba(11,18,34,.9) 100%);
    padding: .6rem .65rem .45rem; overflow: hidden;
}
.j6-idx-name { color: #cfe0f5; font-size: .84rem; font-weight: 800; }
.j6-idx-val { color: #ffffff; font-size: 1.12rem; font-weight: 900; margin-top: .1rem; }
.j6-idx-chg { font-size: .84rem; font-weight: 800; }
.j6-idx-note { color: #7f8a9b; font-size: .72rem; font-weight: 700; }
.j6-idx-spark { margin-top: .25rem; line-height: 0; }
.j6-idx-spark svg { width: 100%; height: auto; }

/* ── 강한 테마 순위 ───────────────────────────────────────────────────── */
.j6-th { display: flex; align-items: center; gap: .6rem; padding: .42rem 0; }
.j6-th + .j6-th { border-top: 1px solid rgba(255,255,255,.06); }
.j6-th-rank { width: 1.2rem; color: #9fb0c6; font-size: .92rem; font-weight: 800; text-align: center; }
.j6-th-name { width: 6.6rem; color: #ffffff; font-size: .95rem; font-weight: 800;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.j6-th-bar { flex: 1; height: 9px; border-radius: 5px; background: rgba(255,255,255,.10); overflow: hidden; }
.j6-th-bar i { display: block; height: 9px; border-radius: 5px;
    background: linear-gradient(90deg, #2a6bd4 0%, #4da6ff 100%); }
.j6-th-score { width: 3rem; text-align: right; color: #ffffff; font-size: .95rem; font-weight: 900; }

/* ── 움직임 — 옛 화면과 **같은 결**이다 ───────────────────────────────
   0.12초 · 살짝 뜨고 1.1배 밝게 · 누르면 눌린다.
   @media (hover:...) 를 걸지 않는다 — 걸면 폰·태블릿이 통째로 빠진다
   (2026-08-26 상하님 지적, 옛 화면 _BRIEFING_TOUCH_CSS 참고). */
.j6-idx, .j6-panel {
    transition: transform .12s ease-out, filter .12s ease-out, border-color .12s ease-out;
}
.j6-idx:hover, .j6-panel:hover { transform: translateY(-3px); filter: brightness(1.1); }
.j6-idx:active, .j6-panel:active { transform: translateY(0) scale(.99); filter: brightness(1.06); }
@media (prefers-reduced-motion: reduce) { .j6-idx, .j6-panel { transition: none !important; } }

/* ── 아직 안 받은 자리 ───────────────────────────────────────────────── */
.j6-later {
    border: 1px dashed rgba(150,190,240,.35); border-radius: 13px;
    padding: .85rem .9rem; color: #9fb0c6; font-size: .92rem; line-height: 1.7;
}
.j6-later b { color: #7fb6ff; }
</style>
"""


_J6_SKIN_CSS = """
<style>
/* ── 새 껍데기 (2026-09-03 상하님 지시 "나머지 세 화면 디자인 바꿔라") ──────────
   **네 화면에 같이 입힌다** — 홈·관심종목·시장분석·기록/성과.
   여기 있는 것은 **보이는 방식뿐이다.** 값·점수·판정은 한 개도 안 건드린다.
   오르내림 색(파랑·빨강)도 그대로 둔다 — 그것은 뜻을 담은 색이다.

   `body:has(.j6-skin)` 로 묶어 두어 **옛 미국테마에는 한 줄도 안 걸린다.**
   그 화면에는 `.j6-skin` 표식이 없다.                                        */

/* 바탕 — 그림에 맞춘 짙은 남색 */
body:has(.j6-skin) .stApp,
body:has(.j6-skin) [data-testid="stAppViewContainer"] {
    background: radial-gradient(1200px 700px at 50% -12%, #12213f 0%, #070d1a 62%, #05080f 100%) !important;
}

/* 판(카드) 공통 결 — 모서리를 크게, 테두리는 옅은 하늘색, 안쪽에 실선 한 줄 */
body:has(.j6-skin) .j3b-card,
body:has(.j6-skin) .j3b-news,
body:has(.j6-skin) .j3-top-cell,
body:has(.j6-skin) .fg-box,
body:has(.j6-skin) .fg-card,
body:has(.j6-skin) .j3-ndd {
    border-radius: 16px !important;
    border: 1px solid rgba(120,180,255,.22) !important;
    background: linear-gradient(160deg, rgba(23,38,68,.92) 0%, rgba(12,20,38,.92) 100%) !important;
    box-shadow: inset 0 1px rgba(150,200,255,.10), 0 8px 22px rgba(0,0,0,.45) !important;
}
/* 지수 칸은 원래 테두리가 없어 여백이 좁다 — 판이 되었으니 안쪽을 벌린다. */
body:has(.j6-skin) .j3-top-cell {
    padding: .7rem .8rem .6rem 1.1rem !important;
    box-sizing: border-box;
}
/* 게이지 상자는 원래 '글자 길이만큼'이라 판으로 만들면 폭이 들쭉날쭉하다. */
body:has(.j6-skin) .fg-box { padding: .7rem .9rem .65rem !important; }

/* 구역 제목 — 홈의 「✦ 오늘의 판단」과 같은 결로 맞춘다 */
body:has(.j6-skin) .j3b-section {
    color: #eaf2ff !important;
    font-size: 1.06rem !important;
    font-weight: 800 !important;
    letter-spacing: -.01em !important;
}
body:has(.j6-skin) .j3b-section .j3b-more { color: #7fb6ff !important; }

/* 배너 — 모서리를 판과 같게 */
body:has(.j6-skin) .j3b-hero,
body:has(.j6-skin) .j3hero { border-radius: 18px !important; overflow: hidden !important; }

/* 접었다 펴는 머리와 단추 — 판과 같은 결로 */
body:has(.j6-skin) [data-testid="stExpander"] {
    border-radius: 14px !important;
    border: 1px solid rgba(120,180,255,.20) !important;
    background: rgba(18,30,54,.55) !important;
}
body:has(.j6-skin) .stButton button {
    border-radius: 12px !important;
    border: 1px solid rgba(120,180,255,.30) !important;
}
/* 색을 따로 입혀 둔 단추(갈래별 그라데이션)는 건드리지 않는다 — 그 색이
   어느 갈래인지 알려 주는 표시다. 모서리만 같이 둥글게 한다. */
body:has(.j6-skin) div[class*="st-key-btn_"] button,
body:has(.j6-skin) div[class*="st-key-close_"] button { border: 0 !important; }

/* 표 — 줄 사이를 옅게, 머리글은 흐리게 */
body:has(.j6-skin) .j3-theme-table th {
    color: #8ea3bd !important;
    border-bottom: 1px solid rgba(150,200,255,.22) !important;
}
body:has(.j6-skin) .j3-theme-table td {
    border-bottom: 1px solid rgba(255,255,255,.055) !important;
}
body:has(.j6-skin) [data-testid="stDataFrame"] {
    border-radius: 14px !important;
    border: 1px solid rgba(120,180,255,.20) !important;
    overflow: hidden !important;
}

/* ── 세 요약 칸을 한 줄에 (그림의 시장분석 위쪽) ──────────────────────────
   시장 국면 · 공포·탐욕 · 나스닥 고점 대비 셋을 나란히 세운다.
   **폰(≤600px)은 그대로 세로로 쌓는다** — 375px 에서 셋을 나란히 놓으면 한 칸이
   115px 이라 게이지도 구간표도 안 읽힌다. 적힌 것을 줄이면 읽을 수 있지만,
   그러면 구간표·1주 전/1개월 전 줄·55년치 설명이 빠진다. 그것은 상하님께
   여쭙고 정할 일이라 여기서는 안 줄였다. */
@media (min-width: 601px) {
    body:has(.j6-skin) .j3-top-row .fg-box,
    body:has(.j6-skin) .j3-top-row .j3-ndd {
        order: 20 !important;
        flex: 1 1 calc(33.333% - 1.4rem) !important;
        min-width: 250px !important;
        box-sizing: border-box !important;
    }
}

/* ── 두 갈래를 큰 판으로 (그림의 시장분석 아래쪽) ─────────────────────────
   글자만 있던 단추를 판으로 키우고, 그 아래 한 줄을 붙인다. **색은 그대로다** —
   초록은 상승장, 주황은 급락 후 반등장으로 이미 정해 두신 색이다. */
body:has(.j6-skin) div[class*="st-key-j3_pullback_breakout"] button,
body:has(.j6-skin) div[class*="st-key-j3_pullback_crash"] button {
    min-height: 104px !important;
    border-radius: 18px !important;
    flex-direction: column !important;
    align-items: flex-start !important;
    justify-content: center !important;
    padding: .9rem 1.05rem !important;
    text-align: left !important;
    white-space: normal !important;
}
body:has(.j6-skin) div[class*="st-key-j3_pullback_breakout"] button p,
body:has(.j6-skin) div[class*="st-key-j3_pullback_crash"] button p {
    font-size: 1.05rem !important; font-weight: 900 !important; text-align: left !important;
}
body:has(.j6-skin) div[class*="st-key-j3_pullback_breakout"] button::after,
body:has(.j6-skin) div[class*="st-key-j3_pullback_crash"] button::after {
    display: block; margin-top: .4rem; text-align: left;
    font-size: .84rem; font-weight: 700; line-height: 1.55; opacity: .85;
}
body:has(.j6-skin) div[class*="st-key-j3_pullback_breakout"] button::after {
    content: "오르는 흐름이 이어지는 종목을 찾습니다";
}
body:has(.j6-skin) div[class*="st-key-j3_pullback_crash"] button::after {
    content: "많이 빠진 뒤 되돌아설 종목을 찾습니다";
}

/* ── 종목 찾는 칸을 위로, 넓게 (그림의 검색/관리 화면) ────────────────────
   여태 「추가 검색 종목」 제목 옆에 좁게 끼어 있었다. 한 줄을 통째로 쓰게 하고
   둥근 테두리를 두른다. 폰 규칙이 `!important` 로 자리를 잡아 두어 여기서도
   같은 세기로 되돌린다. */
body:has(.j6-skin) div[class*="st-key-j3b_extra_header"] [data-testid="stHorizontalBlock"] {
    flex-direction: column !important; gap: .4rem !important;
}
body:has(.j6-skin) div[class*="st-key-j3b_extra_header"] [data-testid="stColumn"] {
    width: 100% !important; flex: 0 0 100% !important; min-width: 0 !important;
}
body:has(.j6-skin) div[class*="st-key-j3b_search_row"] {
    height: auto !important; margin: 0 !important; width: 100% !important;
}
body:has(.j6-skin) div[class*="st-key-j3b_search_row"] input {
    height: 44px !important; font-size: 1rem !important;
    border-radius: 14px !important;
    border: 1px solid rgba(120,180,255,.45) !important;
    background: rgba(12,20,38,.85) !important;
}
body:has(.j6-skin) div[class*="st-key-j3b_search_row"] .stButton button {
    width: 100% !important; height: 44px !important; min-height: 44px !important;
    border-radius: 14px !important;
}
/* 검색 칸 **안**은 가로로 둔다 — 칸과 ＋ 가 나란히 서야 한다.
   위의 '세로로 세운다'가 이 안쪽까지 내려와 ＋ 가 아래로 떨어졌다
   (2026-09-03 폰에서 실측). */
body:has(.j6-skin) div[class*="st-key-j3b_search_row"] [data-testid="stHorizontalBlock"] {
    flex-direction: row !important; gap: .4rem !important; align-items: center !important;
    flex-wrap: nowrap !important;
}
body:has(.j6-skin) div[class*="st-key-j3b_search_row"] [data-testid="stColumn"] {
    flex: 1 1 auto !important; width: auto !important; min-width: 0 !important;
}
body:has(.j6-skin) div[class*="st-key-j3b_search_row"] [data-testid="stColumn"]:last-child {
    flex: 0 0 52px !important; width: 52px !important;
}

/* 움직임은 **옛 화면과 같은 결**이다 — 0.12초·살짝 뜨고 1.1배 밝게.
   여기서는 판이 된 칸에만 더한다(카드·뉴스는 이미 제 규칙이 있다). */
body:has(.j6-skin) .j3-top-cell,
body:has(.j6-skin) .fg-box,
body:has(.j6-skin) .j3-ndd {
    transition: transform .12s ease-out, filter .12s ease-out, border-color .12s ease-out;
}
body:has(.j6-skin) .j3-top-cell:hover,
body:has(.j6-skin) .fg-box:hover,
body:has(.j6-skin) .j3-ndd:hover {
    transform: translateY(-3px); filter: brightness(1.1);
    border-color: rgba(150,220,255,.6) !important;
}
body:has(.j6-skin) .j3-top-cell:active,
body:has(.j6-skin) .fg-box:active,
body:has(.j6-skin) .j3-ndd:active { transform: translateY(0) scale(.99); }
@media (prefers-reduced-motion: reduce) {
    body:has(.j6-skin) .j3-top-cell,
    body:has(.j6-skin) .fg-box,
    body:has(.j6-skin) .j3-ndd { transition: none !important; }
}
</style>
"""


def _j6_index_cards(overview: dict) -> str:
    """지수 넉 장. 값은 옛 화면(`_us_index_cells`)이 쓰는 것과 **같은 자리**에서 꺼낸다.

    정규장이 아니면 마지막으로 끝난 정규장의 등락을 쓴다 — 지수는 시간외 거래가
    없어서 '지금 값'을 쓰면 등락이 0%로 나온다(옛 화면과 같은 규칙).
    """
    display = getattr(j3data, "US_INDEX_DISPLAY", ())
    rows = overview.get("rows") or {}
    live = (overview.get("phase") or {}).get("label") == "정규장 시간"
    try:
        sparklines = j3data.get_index_sparklines()
    except Exception:
        sparklines = {}
    # 그림에 있던 넷 가운데 달러/원은 이 앱이 받는 자료에 없다. 대신 VIX 를
    # 넷째 자리에 둔다 — 옛 화면도 VIX 를 같은 줄에서 보여 준다.
    wanted = [(symbol, name) for symbol, name in display
              if symbol in ("^GSPC", "^NDX", "^DJI")] + [("^VIX", "VIX")]
    cards = []
    for symbol, name in wanted:
        row = rows.get(symbol) or {}
        if not row.get("ok"):
            cards.append(
                f"<div class='j6-idx'><div class='j6-idx-name'>{html.escape(name)}</div>"
                f"<div class='j6-idx-val'>—</div>"
                f"<div class='j6-idx-note'>자료 부족</div></div>"
            )
            continue
        change = row.get("change_pct") if live else row.get("last_session_change_pct")
        spark = _sparkline_svg(sparklines.get(symbol) or {}, "#4da6ff", "#ff5b5b",
                               width=150.0, height=48)
        cards.append(
            f"<div class='j6-idx'>"
            f"<div class='j6-idx-name'>{html.escape(name)}</div>"
            f"<div class='j6-idx-val'>{_number(row.get('current'), 2)}</div>"
            f"<div class='j6-idx-chg {_sign_class(change)}'>{_pct(change)}</div>"
            f"<div class='j6-idx-note'>{'정규장' if live else '장 마감 기준'}</div>"
            f"<div class='j6-idx-spark'>{spark}</div>"
            f"</div>"
        )
    return f"<div class='j6-idx-row'>{''.join(cards)}</div>"


def _j6_theme_rows(ranking: dict, limit: int = 5) -> str:
    """강한 테마 순위. 값은 시장분석이 이미 받아 둔 것을 그대로 쓴다.

    홈은 다섯 줄, 시장분석은 열 줄이다(그림대로). **자료를 새로 받지 않는다** —
    시장분석이 이미 받아 둔 `j3_theme_rankings` 를 그대로 읽는다.
    """
    rows = list(ranking.get("rows") or [])[:limit]
    if not rows:
        return ""
    scores = [float(row.get("score") or 0) for row in rows]
    top = max(scores + [1.0])
    lines = []
    for index, row in enumerate(rows, start=1):
        score = float(row.get("score") or 0)
        width = max(4.0, min(100.0, score / top * 100.0))
        lines.append(
            f"<div class='j6-th'><span class='j6-th-rank'>{index}</span>"
            f"<span class='j6-th-name'>{html.escape(str(row.get('name') or '—'))}</span>"
            f"<span class='j6-th-bar'><i style='width:{width:.1f}%'></i></span>"
            f"<span class='j6-th-score'>{score:.1f}</span></div>"
        )
    return f"<div class='j6-panel'>{''.join(lines)}</div>"


def _render_j6_home() -> None:
    """새 디자인 첫 화면.

    **여기서 21개 테마를 받지 않는다.** 「강한 테마 순위」와 「강한 종목 후보」는
    시장분석에서 받는 값인데, 그것을 첫 화면에서 부르면 21개 테마를 다 받은 뒤에야
    첫 화면이 뜬다(CLAUDE.md 0-0 — 새로 넣는 것이 무엇을 밀어내는지 먼저 잰다).
    그래서 **이미 받아 둔 것이 있을 때만** 그리고, 없으면 시장분석으로 보낸다.
    """
    scroll_to.anchor(st, "top")
    back_nav.opened(st, "j3b_backstop")

    st.markdown(
        '<div class="j6-app"></div><div class="j6-skin"></div>'
        '<div class="j6-head">'
        '<span class="j6-brand">JARVIS <b>6</b></span>'
        '<span class="j6-chip">미국테마</span>'
        '<span class="j6-live"><i></i>실시간</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    overview = j3data.get_market_overview()
    st.session_state["j3_market_overview"] = overview

    st.markdown('<div class="j6-sec">✦ 오늘의 판단</div>', unsafe_allow_html=True)
    if not overview.get("ok"):
        st.error(f"시장 자료 조회 실패: {_safe_error_text(overview.get('error'))}")
    else:
        # 게이지 그림 규칙은 시장분석 쪽에서 내보내는데(_render_market_overview),
        # 이 화면은 그 함수를 부르지 않는다. 여기서 따로 한 번 내보낸다 —
        # 안 그러면 상자가 껍데기 없이 글자만 흘러나온다.
        st.markdown(f"<style>{fear_greed_ui.CSS}</style>", unsafe_allow_html=True)
        # **시장분석과 같은 상자를 그대로 쓴다.** 점수·국면·행동 한 줄을 여기서
        # 따로 만들면 두 화면이 조용히 갈라진다. freeze=True 도 옛 화면과 같다.
        st.markdown(
            '<div class="j6-panel j6-verdict">'
            + regime_gauge_ui.regime_box_html(overview, freeze=True)
            + '</div>',
            unsafe_allow_html=True,
        )
        st.markdown(_j6_index_cards(overview), unsafe_allow_html=True)

    ranking = st.session_state.get("j3_theme_rankings") or {}
    st.markdown('<div class="j6-sec">⚡ 강한 테마 순위</div>', unsafe_allow_html=True)
    if ranking.get("rows"):
        st.markdown(_j6_theme_rows(ranking), unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="j6-later">21개 테마 시세는 <b>시장분석</b>에서 받습니다. '
            '여기서 받으면 첫 화면이 그만큼 늦게 뜹니다.<br>'
            '아래 <b>시장분석</b>을 한 번 열고 오시면 이 자리에 순위가 그대로 남습니다.</div>',
            unsafe_allow_html=True,
        )

    _render_briefing_bottom_nav("home")


def _render_j6_record() -> None:
    """기록/성과 — 날짜별로 저장해 둔 목록. 옛 화면이 쓰는 그 함수 그대로다.

    **여기서 21개 테마를 받지 않는다.** 줄을 누르셨을 때만 배점표에 필요한
    시장·테마 값을 그때 받는다(아래 `on_pick` 안). 목록만 보실 때는 안 받는다.
    """
    scroll_to.anchor(st, "top")
    back_nav.opened(st, "j3b_backstop")
    st.markdown(
        '<div class="j6-app"></div><div class="j6-skin"></div>'
        '<div class="j6-head">'
        '<span class="j6-brand">JARVIS <b>6</b></span>'
        '<span class="j6-chip">기록 · 성과</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown(mobile_ui.page_css(), unsafe_allow_html=True)

    def _detail(code, name, kind, row) -> None:
        market = st.session_state.get("j3_market_overview") or j3data.get_market_overview()
        ranking = st.session_state.get("j3_theme_rankings") or _load_theme_rankings()
        _picklist_detail(market, ranking, code, name, kind, row)

    picklist_ui.render(st, "US", toggle=_section_toggle, close=_section_close,
                       on_pick=_detail)
    _render_briefing_bottom_nav("record")


# ── 폰 홈 화면에 「앱」으로 얹히게 한다 (2026-09-03 상하님 지시) ──────────────
# 상하님 — *"어플 디자인까지 해서 만들고, 내가 어플 누르면 자동으로 들어가게."*
#
# 폰은 화면 머리(head)에 적힌 것을 보고 이름·그림·여는 방식을 정한다. 스트림릿은
# 그 자리를 제 것으로 채우므로, 우리가 만든 것을 거기에 얹어야 한다.
# 얹는 길은 `components.html` 이 내주는 작은 창이다 — 그 창은 바깥 화면과 **같은
# 집**이라(sandbox 에 allow-same-origin 이 있다 · 2026-09-03 실측) 바깥 머리에
# 손이 닿는다. 이 화면이 이미 ↻ 새로고침에 같은 길을 쓰고 있다.
#
# **실패해도 조용히 넘어간다** — 아이콘 하나 때문에 화면이 안 열리면 안 된다.
_APP_MANIFEST_URL = "/app/static/jarvis6_app_manifest.json"
_APP_ICON_180 = "/app/static/jarvis6_icon_180.png"
_APP_ICON_192 = "/app/static/jarvis6_icon_192.png"


def _install_app_head() -> None:
    """홈 화면 아이콘·이름·바탕색을 바깥 화면 머리에 얹는다. 판마다 한 번이면 된다."""
    if st.session_state.get("j6_app_head_done"):
        return
    st.session_state["j6_app_head_done"] = True
    try:
        import streamlit.components.v1 as components

        components.html(
            "<script>(function(){try{"
            "var d=window.parent.document;"
            "function tag(name,rel,href,attrs){"
            " var q='[data-j6=\"'+name+'\"]';"
            " var el=d.head.querySelector(q);"
            " if(!el){el=d.createElement(rel?'link':'meta');"
            "  el.setAttribute('data-j6',name);d.head.appendChild(el);}"
            " if(rel){el.rel=rel;el.href=href;}else{el.name=name;el.content=href;}"
            " if(attrs){for(var k in attrs){el.setAttribute(k,attrs[k]);}}"
            "}"
            f"tag('manifest','manifest','{_APP_MANIFEST_URL}');"
            f"tag('apple','apple-touch-icon','{_APP_ICON_180}');"
            f"tag('icon192','icon','{_APP_ICON_192}',"
            "{'sizes':'192x192','type':'image/png'});"
            "tag('theme-color',null,'#05080f');"
            "tag('apple-mobile-web-app-capable',null,'yes');"
            "tag('apple-mobile-web-app-status-bar-style',null,'black-translucent');"
            "tag('apple-mobile-web-app-title',null,'자비스6');"
            "}catch(e){}})();</script>",
            height=0,
        )
    except Exception:
        pass


def _render_stock_briefing() -> None:
    # 미리 계산은 이 화면 **맨 끝**에서, 그것도 뉴스가 다 온 뒤에 시작한다
    # (_warm_after_news). 여기 맨 앞에 두면 첫 화면과 뉴스가 밀린다.
    _briefing_css()
    # 폰이 이 화면을 「앱」으로 알아보게 하는 표시. 판마다 한 번이면 된다.
    _install_app_head()
    # 새 껍데기는 **네 화면이 다 지나는 여기서 한 번만** 내보낸다
    # (2026-09-03). 화면마다 따로 내보내면 같은 규칙이 여러 벌 실린다.
    #
    # **`_J6_CSS` 도 같이 내보낸다.** 앞서 홈·기록에서만 내보냈더니, 시장분석에
    # 새로 넣은 「강한 테마 순위 TOP 10」이 규칙 없이 글자로만 나왔다
    # ("1사이버보안92.0" — 2026-09-03 폰에서 실측). 그 안의 자리잡기 규칙
    # (`body:has(.j6-app)`)은 표식이 있는 화면에서만 걸리므로 여기 있어도 안전하다.
    st.markdown(_J6_CSS + _J6_SKIN_CSS, unsafe_allow_html=True)
    # 보시던 화면은 **주소에서** 읽는다 — 폰이 화면을 버렸다 다시 열어도
    # 관심종목으로 돌아가지 않게 한다(2026-08-29, _briefing_page 참고).
    page = _briefing_page()
    _set_briefing_page(page)
    # **화면이 바뀌면 어느 길로 왔든 맨 위로 올린다** (2026-08-27 상하님 지적 —
    # "시장분석 맨 위 화면 아직도 그거 해결 안 하고 있다").
    #
    # 앞서 단추마다 하나씩 넣었는데, 하나를 빠뜨리면(「더보기 ›」가 그랬다) 그
    # 길로 들어오실 때 맨 위 두 단추를 지나친 자리에 서게 된다. 브라우저는
    # 화면을 바꿔도 굴려 둔 자리를 그대로 들고 오기 때문이다.
    # 이제 단추마다 챙기지 않고 **여기 한 곳에서** 챙긴다 — 직전 화면과 다르면
    # 무조건 맨 위다. 새 길이 생겨도 빠뜨릴 수가 없다.
    #
    # **적어 두지 않고 바로 올린다**(2026-08-29 상하님 지적 — "20개 테마 실시간
    # 순위 이 부분을 로딩하면서 또다시 맨 위 화면으로 올라가버린다").
    # 적어 두면 그 표시가 판 **끝**에서 쓰이는데, 시장분석은 20개 테마 자료를
    # 받느라 끝까지 그리는 데 몇 초가 걸린다. 그동안 상하님은 이미 내려 보고
    # 계셨고, 마지막에 표시가 쓰이면서 그 손을 뿌리쳤다. 지금 올리면 아직
    # 그릴 것이 없을 때라 뿌리칠 일이 없다.
    if st.session_state.get("j3b_last_page") != page:
        st.session_state["j3b_last_page"] = page
        scroll_to.now(st, "top")
    if page == "market":
        # **시장분석에서도 뒤로가기가 앱 밖으로 나가지 않게 한다**
        # (2026-08-29 상하님 지시 — "관심종목에서 뒤로 가기 버튼을 시장분석
        # 에서도 적용시켜라. 모르고 습관적으로 자꾸 누르게 되는데 캡처 화면으로
        # 자꾸 돌아간다").
        # 여태 이 표식은 관심종목 화면에만 있었다. 그래서 시장분석에서 처음
        # 뒤로가기를 누르면 곧장 「어디로 갈까요」 화면으로 빠져나갔다.
        # 관심종목과 **같은 표식**을 쓴다 — 열쇠가 같으므로 방문기록은
        # 여전히 한 칸만 쌓인다.
        back_nav.opened(st, "j3b_backstop")
        _render_existing_theme_content()
        _render_briefing_bottom_nav("market")
        return
    if page == "home":
        _render_j6_home()
        return
    if page == "record":
        _render_j6_record()
        return
    st.session_state["j3b_news_pending"] = False
    try:
        briefing_store.ensure_tables()
        # 기본 4종목을 실제 줄로 옮겨 적어 ×로 지울 수 있게 한다(2026-08-26).
        briefing_store.ensure_default_extras()
        setup = briefing_store.all_stocks()
    except Exception:
        st.error("종목 브리핑 설정을 불러오지 못했습니다. 기존 미국테마 기능은 계속 사용할 수 있습니다.")
        _render_existing_theme_content()
        return
    selected, extras = setup["selected"], setup["extra"]
    home_extras = _briefing_home_extras(extras)
    visible_stocks = selected + home_extras
    cards = j3data.get_briefing_cards(visible_stocks)
    try:
        visual_debug = str(st.query_params.get("visual_debug", "")).strip() == "1"
    except Exception:
        visual_debug = False
    with st.container():
        if visual_debug:
            reference_uri = _briefing_asset_uri("visual_reference.png")
            if reference_uri:
                st.markdown(
                    f'<div class="j3b-debug-overlay"><img src="{reference_uri}" alt=""></div>',
                    unsafe_allow_html=True,
                )
        catbus_uri = _briefing_asset_uri("hero_scene.webp")
        catbus_html = f'<img class="j3b-hero-scene" src="{catbus_uri}" alt="">' if catbus_uri else ""
        # ↻ 는 그림이 아니라 **진짜 단추**다(2026-08-26 상하님 지시 — "맨 위 상단
        # 실시간 옆 되돌리기 버튼 저것만 작동하게"). 보이는 것은 아래 span 그대로 두고,
        # 그 위에 속이 비치는 스트림릿 단추를 겹쳐 둔다. 하단 이동표와 같은 장치다.
        # 뒤로가기를 한 번 눌러도 이 화면에 머문다(2026-08-26 상하님 지시 —
        # "뒤로가기 버튼을 누르면 로그인 화면으로 갔다가 다시 메인으로 돌아온다").
        # 방문기록에 표식을 하나 쌓아 두면 첫 뒤로가기가 그 표식을 지우고 제자리에
        # 선다. 앞 화면(로그인·메뉴)으로 나가려면 두 번 누르면 된다.
        back_nav.opened(st, "j3b_backstop")
        # 시장분석에서 관심종목으로 돌아올 때 데려올 '맨 위' 자리.
        # 시장분석 쪽에는 이미 같은 이름의 자리가 있다(_render_existing_theme_content).
        scroll_to.anchor(st, "top")
        with st.container(key="j3b_hero_box"):
            st.markdown(
                '<div class="j3b-app j3b-home"></div><div class="j6-skin"></div><div class="j3b-hero"><div class="j3b-head-copy">'
                '<div class="j3b-title">JARVIS <b>6</b></div><div class="j3b-sub">미국테마</div></div>'
                '<div class="j3b-head-actions"><span class="j3b-round">↻</span><span class="j3b-live"><i></i>실시간</span></div>'
                # 사용자 선정 종목의 로고가 버스 둘레를 돈다(2026-08-28 상하님 지시).
                f'{catbus_html}{_briefing_orbit_html(selected)}</div>',
                unsafe_allow_html=True,
            )
            if st.button("↻", key="j3b_hero_refresh"):
                # 서버가 담아 둔 것을 비우고, **화면도 통째로 새로 연다.**
                #
                # 2026-08-27 상하님 지적 — "맨 위 두 단추가 안 나타난다."
                # 온라인에는 이미 고쳐져 올라가 있었는데 폰만 옛 화면을 붙잡고
                # 있었다. 어제 상하님 지시로 **손가락으로 당겨 새로고침하는 것을
                # 막았고**("맨 위 ↻ 저것만 작동하게 할 수 없냐"), 그런데 이 단추는
                # 서버 기억만 비우고 화면은 안 열었다. 그래서 폰이 새 판을 받을
                # 길이 없어졌다.
                #
                # 이제 이 단추가 진짜 새로고침이다. **누를 때만** 연다 —
                # 2026-08-26에 이것을 2.5초마다 부르다 화면이 버벅였다.
                st.session_state["j3b_hard_reload"] = True
                try:
                    j3data.clear_runtime_cache()
                except Exception:
                    pass
                try:
                    briefing_news.clear_cache()
                except Exception:
                    pass
                st.rerun()
        st.markdown('<div class="j3b-section"><span class="j3b-flag">🇺🇸</span> 미국시장 한줄 브리핑</div>', unsafe_allow_html=True)
        _render_briefing_news("market")
        with st.container(key="j3b_selected_heading"):
            st.markdown('<div class="j3b-section"><span class="j3b-section-icon"></span> 사용자 선정 종목 <span class="j3b-more">더보기 ›</span></div>', unsafe_allow_html=True)
            if st.button("더보기", key="j3b_go_market"):
                # **여기도 맨 위로 올린다** (2026-08-27 상하님 지적 — "맨 위에
                # 메뉴 2개 안 나오는 것 언제 해결할 거냐"). 「더보기 ›」는 화면을
                # 아래로 내려야 보이는 자리라, 누르면 브라우저가 그 자리를 그대로
                # 들고 시장분석으로 간다. 그러면 맨 위의 「🌏 한국테마 →」·
                # 「📘 이 테마 설명」 두 단추를 지나친 자리에 선다.
                # 하단 이동막대 쪽만 고쳐 두고 이 길을 빠뜨렸다.
                _set_briefing_page("market")
                st.rerun()
        _render_briefing_grid(selected, cards, removable=False, key="selected")
        with st.container(key="j3b_extra_header"):
            heading_col, search_col = st.columns([4, 6], gap="small")
            with heading_col:
                st.markdown('<div class="j3b-section search"><span class="j3b-section-icon"></span> 추가 검색 종목</div>', unsafe_allow_html=True)
            with search_col:
                _render_briefing_manage(selected, extras)
        _render_briefing_grid(home_extras, cards, removable=True, key="extra1", compact=True)
        _render_briefing_bottom_nav("watch")
        news_keys = tuple([("market", None)] + [("company", stock["ticker"]) for stock in visible_stocks])
        _schedule_briefing_news_refresh(news_keys)
        # 아직 오는 중이면 **2초마다 지켜본다** (2026-09-02 상하님 —
        # "「뉴스 불러오는 중」이라고 계속 떠 있다"). 다 왔으면 안 그린다 —
        # 그러면 이 조각도 더 안 돈다.
        if st.session_state.get("j3b_news_pending"):
            _briefing_news_watcher(news_keys)
        # 뉴스가 다 온 뒤에야 순위 9·나스닥 25년치를 미리 챙긴다. 위 줄이 화면을
        # 다시 그리라고 하면 이 줄까지 오지 않는다 — 그것이 맞다. 아직 뉴스가
        # 오는 중이라는 뜻이기 때문이다.
        _warm_after_news(news_keys)


def _run_hard_reload_if_requested() -> None:
    """맨 위 ↻ 를 누르셨으면 브라우저 화면을 통째로 새로 연다 (2026-08-27).

    스트림릿은 `st.markdown`의 `<script>`를 지우므로, 정식으로 내주는
    `components.html`(작은 iframe)에 한 줄을 담아 바깥 화면을 새로 연다.
    실패해도 조용히 넘어간다 — 그때는 예전처럼 서버 기억만 비운 셈이다.
    """
    if not st.session_state.pop("j3b_hard_reload", False):
        return
    try:
        import streamlit.components.v1 as components

        components.html(
            "<script>try{window.parent.location.reload();}catch(e){}</script>",
            height=0,
        )
    except Exception:
        pass


def main() -> None:
    _render_stock_briefing()
    _run_hard_reload_if_requested()


main()
# 이번 판에 '거기로 내려가라'가 적혀 있으면 한 번 내려가고 지운다(2026-08-09).
scroll_to.run(st)
# **이 화면이 언제 판인지** 맨 밑에 작게 적는다 (2026-09-02 상하님 지시).
# 노트북과 폰을 나란히 놓고 견주시는 자리다 — 같은 숫자면 같은 판이다.
try:
    import build_stamp

    build_stamp.render(st)
except Exception:
    pass
