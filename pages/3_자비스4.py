"""자비스4 — 한국 테마 레이더와 실제 매수 기록 페이지.

화면 골격은 자비스3(미국 테마 레이더)를 그대로 따르고, 내용만 한국형으로 바꾼다.
색 규칙은 한국장 기준이다 — 상승은 붉은색, 하락은 푸른색(자비스3와 반대).
"""

from __future__ import annotations

import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

# 기준일 비교는 항상 한국 시각으로 한다 — 클라우드 서버는 UTC라서
# datetime.now()를 쓰면 자정 무렵에 '오늘'이 하루 어긋난다.
_PAGE_SEOUL = ZoneInfo("Asia/Seoul")


def _now_seoul() -> datetime:
    return datetime.now(_PAGE_SEOUL)

import streamlit as st

import auth  # 로그인 유지(쿠키). 쿠키가 안 되면 조용히 세션 기반 동작으로 남는다.

# 배포 갱신 중 옛 auth가 프로세스에 남으면 함수 모양이 안 맞아 화면이 죽는다
# (2026-07-25 온라인 실발생). 리비전이 낮으면 다시 읽는다.
_REQUIRED_AUTH_REVISION = 2026072503
if int(getattr(auth, "MODULE_REVISION", 0)) < _REQUIRED_AUTH_REVISION:
    import importlib as _importlib

    auth = _importlib.reload(auth)

st.set_page_config(page_title="자비스4 — 한국 테마 레이더", layout="wide")

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
    /* 사이드바 순서: 시장판단 → 자비스1 → 자비스2 → 미국테마 → 한국테마 */
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
        font-size: 1.15rem; font-weight: 800; color: #ffb020;
    }
    [data-testid="stSidebarNav"] li:nth-child(5) a p { font-size: 0 !important; }
    [data-testid="stSidebarNav"] li:nth-child(5) a p::before {
        content: "한국테마\\A(자비스4)"; white-space: pre; line-height: 1.2;
        font-size: 1.15rem; font-weight: 800; color: #ffb020;
    }
    [data-testid="stSidebarNav"] li:nth-child(6) a p { font-size: 0 !important; }
    [data-testid="stSidebarNav"] li:nth-child(6) a p::before {
        content: "한국테마\\A(선행감지)"; white-space: pre; line-height: 1.2; font-size: 1.15rem; font-weight: 800; color: #ffb020;
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
    /* 일봉·주봉·월봉 이름은 파랑(2026-07-29 지시). 상세가 세 벌 그려지므로
       여기 한 곳만 고치면 테마 종목·눌림목·내 종목 화면에 모두 적용된다. */
    .j4-chart-title { color: #4da6ff; font-weight: 800; font-size: 1rem; margin-bottom: 0.1rem; }
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
    /* 차트 구역 제목은 초록(2026-07-29 지시) — '당일·실시간', '가격 차트 …' 등.
       상세 세 벌에 공통으로 먹는다. */
    .j4-chart-heading { margin-top: 1.6rem; font-size: 1.15rem; font-weight: 800; color: #44f0a1; }
    .j4-theme-badge { display: inline-block; background: rgba(255,176,32,0.16); color: #ffb020; border: 1px solid #ffb020; border-radius: 0.5rem; padding: 0.15rem 0.7rem; font-weight: 800; font-size: 1.05rem; margin-right: 0.4rem; }
    .j4-flow-label { color: #44f0a1; font-weight: 800; }
    .j4-flow-body { color: #4da6ff; font-weight: 800; }
    .j4-action-label { color: #4da6ff; font-weight: 800; }
    .j4-action-posture { color: #ff5b5b; font-weight: 800; }
    .j4-action-detail { color: #ff9d3b; font-weight: 800; }
    /* 줄 사이(세로) 간격을 가로보다 넉넉히 준다 — 대표종목 칸이 길어지면서 바로 위
       차트에 붙어 보였다(2026-07-25 태블릿 지적). */
    .j4-top-row { display: flex; gap: 2.6rem 2rem; flex-wrap: wrap; margin-bottom: 0.3rem;
        align-items: center; }
    .j4-top-cell { min-width: 150px; padding-left: 1.6rem; }
    /* 지수 차트 묶음과 시장상태 아래 묶음을 갈라 주는 빈 줄. 폰·태블릿(≤1200px)에서만
       쓴다 — 노트북에서는 한 줄에 여러 칸이 들어가 이 끊김이 필요 없다. */
    .j4-top-break { display: none; }
    @media (max-width: 1200px) {
        .j4-top-break { display: block; flex: 0 0 100%; height: 3rem; }
    }
    /* 제목은 코발트, 값은 항목별 색 — 무엇이 제목이고 무엇이 결과인지 구분되게 한다
       (2026-07-22 사용자 지시). */
    .j4-top-label { color: #9aa0aa; font-size: 1rem; font-weight: 800; letter-spacing: -.01em; }
    .j4-top-val { font-size: 1.7rem; font-weight: 800; line-height: 1.2; }
    .j4-top-sub { font-size: 0.95rem; font-weight: 700; }
    .j4-theme-table { width: 100%; border-collapse: collapse; font-size: 0.92rem; table-layout: fixed; }
    /* 좁은 화면(태블릿·폰)에서는 칸을 쥐어짜 글자를 자르는 대신, 표를 원래 폭으로
       두고 손가락으로 옆으로 밀어 본다(2026-07-25 사용자 지시). 화면 전체는 안 밀린다. */
    .j4-table-scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; }
    /* 눌림목 표도 같은 방식 — 좁은 화면에서 줄이 접히지 않게 폭을 지키고 옆으로 민다. */
    /* 11~20위를 담은 '더 보기'도 같은 규칙을 받아야 한다 — 빠뜨렸더니 폰에서 그 안만
       칸이 세로로 쌓였다(2026-07-25 사용자 지적). */
    /* 종목표(j4_leader_table)도 2026-07-29에 이름을 누를 수 있게 칸 방식으로 바꾸면서
       이미 폰·태블릿에서 잘 도는 위 두 표와 **똑같은 규칙**에 얹었다. 새 규칙을
       만들지 않은 것은 그래야 나중에 한 곳만 고쳐도 셋이 같이 따라오기 때문이다. */
    .st-key-j4_pullback_table,
    .st-key-j4_theme_rest,
    .st-key-j4_leader_table,
    .st-key-j4_theme_table { overflow-x: auto; -webkit-overflow-scrolling: touch; }
    @media (max-width: 1200px) {
        .st-key-j4_pullback_table [data-testid="stHorizontalBlock"] {
            flex-wrap: nowrap !important; min-width: 1180px;
        }
        .st-key-j4_theme_rest [data-testid="stHorizontalBlock"],
        .st-key-j4_leader_table [data-testid="stHorizontalBlock"],
        .st-key-j4_theme_table [data-testid="stHorizontalBlock"] {
            flex-wrap: nowrap !important; min-width: 900px;
        }
        .st-key-j4_pullback_table [data-testid="stColumn"],
        .st-key-j4_theme_rest [data-testid="stColumn"],
        .st-key-j4_leader_table [data-testid="stColumn"],
        .st-key-j4_theme_table [data-testid="stColumn"] { min-width: 0 !important; }
    }
    @media (max-width: 1200px) {
        .j4-table-scroll .j4-theme-table { min-width: 980px; }
    }
    .j4-theme-table th { text-align: center; color: #9aa0aa; font-weight: 800; padding: 0.5rem 0.4rem; border-bottom: 1px solid rgba(255,255,255,0.18); }
    .j4-theme-table td { text-align: center; padding: 0.45rem 0.4rem; border-bottom: 1px solid rgba(255,255,255,0.06); color: #e6e6e6; }
    .j4-theme-table td.j4-th-name { text-align: left; padding-left: 1.2rem; font-weight: 800; }
    /* 값이 칸 폭에 걸려 두 줄로 접히면 표가 통째로 흔들린다(2026-07-25 태블릿 실측:
       '+0.00 %', '0058 30'처럼 접혔다). 숫자·점은 한 줄로 붙들고 종목명만 줄바꿈을 허용한다. */
    .j4-theme-table td, .j4-theme-table th { white-space: nowrap; }
    .j4-theme-table td.j4-th-name { white-space: normal; }
    .j4-td { white-space: nowrap; }
    .j4-th-selected { background: rgba(255,176,32,0.13); }
    .j4-th-muted { color: #9aa0aa; }
    .j4-barwrap { display: flex; align-items: center; gap: 6px; width: 100%; }
    .j4-bar { position: relative; flex: 1; background: rgba(255,255,255,0.10); border-radius: 4px; height: 8px; overflow: hidden; }
    .j4-bar-fill { height: 8px; background: #ff5b5b; }
    .j4-bar-green { background: #44f0a1; }
    .j4-bar-num { font-size: 0.82rem; font-weight: 700; color: #e6e6e6; min-width: 32px; text-align: right; }
    /* 카드 안의 동반 수급 그림 — 표에 쓰던 점·막대를 그대로 옮겨 쓴다(2026-07-25). */
    .j4-flowmarks { display: flex; flex-direction: column; gap: 3px; margin-top: 6px; }
    .j4-fm-row { display: flex; align-items: center; gap: 6px; }
    .j4-fm-label { font-size: 0.76rem; font-weight: 700; color: #9aa0aa; white-space: nowrap; }
    .j4-fm-cell { flex: 1; min-width: 92px; }
    .j4-fm-name { font-size: 0.82rem; font-weight: 800; color: #cfd4dc; margin-top: 8px; }
    /* 동반 그림은 값 오른쪽에 세로로 세워 붙인다 — 값 밑에 쌓으면 칸이 너무 길어졌다
       (2026-07-25 지시). 자리가 모자라면 알아서 값 아래로 내려간다. */
    .j4-top-split { display: flex; flex-wrap: wrap; gap: 0.2rem 0.7rem; align-items: flex-start; }
    /* 기준 너비를 내용 크기가 아니라 작은 값으로 잡아야 좁은 폰에서도 줄이 안 접히고
       옆으로 붙는다. 150/145로는 폰(칸 폭 약 300px)에서 합이 넘쳐 그림이 값 아래로
       내려갔다(2026-07-25 실제 화면). 둘 다 min-width를 0으로 두어 모자라면 글이
       줄바꿈되게 하고, 접히는 것은 마지막 수단으로 남긴다. */
    .j4-top-main { flex: 1 1 125px; min-width: 0; }
    .j4-top-side { flex: 1 1 140px; min-width: 0; }
    .j4-fm-pair { display: flex; flex-direction: column; gap: 0.3rem; }
    .j4-fm-stock { min-width: 0; }
    .j4-fm-pair .j4-fm-stock:first-child .j4-fm-name { margin-top: 0; }
    /* 제목이 두 줄이 되면 한 줄짜리와 밑줄이 어긋났다(2026-07-25 사용자 지적).
       모두 같은 높이를 갖고 글자는 아래에 붙여 밑줄을 한 줄로 맞춘다. */
    .j4-th-head { display: flex; align-items: flex-end; justify-content: center;
        min-height: 3.1rem; text-align: center; color: #9aa0aa; font-weight: 800; font-size: 0.92rem;
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
    .j4-pull-guide { border-left: 4px solid #4da6ff; background: rgba(77,166,255,.07);
        border-radius: .45rem; padding: .7rem .9rem; color: #b7c0ce; line-height: 1.6;
        margin: .15rem 0 .65rem; }
    .j4-pull-guide b { color: #44f0a1; }
    .j4-pull-stats { color: #9dccff; font-size: .93rem; line-height: 1.55;
        margin: .15rem 0 .65rem; text-align: left; }
    /* 눌림목 찾기 버튼 — 밝은 스카이 블루 바탕에 클로드 로고 주황 글씨.
       글씨 크기·굵기는 위 섹션 제목(1.2rem/800)과 맞춘다 (2026-07-24 사용자 지시). */
    div[class*="st-key-j4_pullback_find"] button {
        background: #cfe9ff !important;
        border: 1px solid #8ec9f5 !important;
        border-radius: .5rem !important;
        min-height: 3rem !important;
    }
    div[class*="st-key-j4_pullback_find"] button:hover {
        background: #b9dfff !important;
        border-color: #6db6ee !important;
    }
    div[class*="st-key-j4_pullback_find"] button p {
        color: #c15f3c !important;
        font-size: 1.2rem !important;
        font-weight: 800 !important;
        margin: 0 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _login_gate() -> None:
    auth.sync_auth()  # 쿠키에 로그인이 남아 있으면 되살린다(폰 복귀 시 재로그인 방지).
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

import fear_greed_ui
import gauge_ui
import mobile_ui

_REQUIRED_GAUGE_UI_REVISION = 2026072901
if int(getattr(gauge_ui, "MODULE_REVISION", 0)) < _REQUIRED_GAUGE_UI_REVISION:
    gauge_ui = importlib.reload(gauge_ui)

# 옛 mobile_ui가 프로세스에 남으면 폰 수정이 온라인에 하나도 반영되지 않는다
# (2026-07-25 실발생). CLAUDE.md 11번 규칙에 따라 리비전이 낮으면 다시 읽는다.
_REQUIRED_MOBILE_REVISION = 2026072922
if int(getattr(mobile_ui, "MODULE_REVISION", 0)) < _REQUIRED_MOBILE_REVISION:
    mobile_ui = importlib.reload(mobile_ui)
import method_help

# 설명 단추 문구·숫자를 바꾸면 method_help의 리비전을 올린다.
# 안 올리면 온라인에서 옛 문구가 그대로 남는다(규칙 11).
_REQUIRED_METHOD_HELP_REVISION = 2026072923
if int(getattr(method_help, "MODULE_REVISION", 0)) < _REQUIRED_METHOD_HELP_REVISION:
    method_help = importlib.reload(method_help)
import regime_gauge_ui
import jarvis4_data as j4data
import jarvis4_store as j4store
import market_signal_ui
import us_index_data

_REQUIRED_REGIME_GAUGE_REVISION = 2026072904
if int(getattr(regime_gauge_ui, "MODULE_REVISION", 0)) < _REQUIRED_REGIME_GAUGE_REVISION:
    regime_gauge_ui = importlib.reload(regime_gauge_ui)

_REQUIRED_US_INDEX_DATA_REVISION = 2026072901
if (
    not hasattr(us_index_data, "market_overview")
    or int(getattr(us_index_data, "MODULE_REVISION", 0)) < _REQUIRED_US_INDEX_DATA_REVISION
):
    us_index_data = importlib.reload(us_index_data)

# 온라인 배포 갱신 때 옛 모듈이 프로세스에 남으면 스스로 새 코드를 읽는다(자비스3와 동일).
# 새 함수를 추가할 때마다 이 목록에 넣어야 한다 — 빠뜨리면 온라인에서 AttributeError가 난다
# (2026-07-22: get_us_futures_live를 빠뜨려 실제로 발생했다).
_REQUIRED_J4_FUNCTIONS = (
    "get_theme_rankings", "get_theme_leaders", "get_market_overview",
    "get_us_futures_live", "get_fx_intraday", "get_intraday_chart", "find_pullback_stocks",
    "get_index_sparkline", "get_index_intraday",
    "get_chart_bundle", "get_live_quote", "round_to_tick",
    # 2026-07-29 '내 종목 현재상황'에서 쓴다.
    "search_stocks", "analyze_one_stock",
)
# 함수 이름만 보면 '이름은 그대로인데 내용이 옛것'인 모듈을 못 걸러낸다 —
# 2026-07-24에 실제로 눌림목 깔때기 숫자(전체·유동성·수급 확인)가 0으로 나왔다.
# 그래서 모듈 리비전 숫자까지 확인해 낮으면 다시 읽는다.
_REQUIRED_J4_REVISION = 2026072919
if (
    any(not hasattr(j4data, name) for name in _REQUIRED_J4_FUNCTIONS)
    or int(getattr(j4data, "MODULE_REVISION", 0)) < _REQUIRED_J4_REVISION
):
    j4data = importlib.reload(j4data)
_REQUIRED_SIGNAL_UI_REVISION = 2026072911
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
    """오름(+) 파랑, 내림(−) 붉은색.

    한국 관행은 반대(+빨강 −파랑)라 예전에는 그렇게 칠했는데, 자비스3(미국)은
    +파랑 −빨강이라 같은 앱에서 색이 정반대였다. 사용자 지시는 +파랑 −빨강이므로
    한쪽으로 모은다 — 대표종목 5일 수급 -69,244억이 파랑으로 떠서 순매도인지
    순매수인지 헷갈렸다(2026-07-29 지적).
    """
    if value is None:
        return "#9aa0aa"
    try:
        return "#4da6ff" if float(value) >= 0 else "#ff5b5b"
    except (TypeError, ValueError):
        return "#9aa0aa"


def _top_metric(label, value, value_color, sub, *, sub_color=None, sub_signed=False,
                side: str = "") -> str:
    """상단 지표 칸. side를 주면 그 내용을 값 오른쪽에 나란히 붙인다.

    side는 대표종목 칸의 동반 그림에 쓴다 — 값 밑에 쌓으면 칸이 너무 길어진다
    (2026-07-25 폰 지적).
    """
    if sub_signed:
        sub_html = f"<div class='j4-top-sub {_sign_class(sub)}'>{_pct(sub)}</div>"
    else:
        sub_html = f"<div class='j4-top-sub' style='color:{sub_color or '#9aa0aa'}'>{sub}</div>"
    inner = (
        f"<div class='j4-top-label'>{label}</div>"
        f"<div class='j4-top-val' style='color:{value_color}'>{value}</div>{sub_html}"
    )
    if side:
        return (
            "<div class='j4-top-cell'><div class='j4-top-split'>"
            f"<div class='j4-top-main'>{inner}</div>"
            f"<div class='j4-top-side'>{side}</div></div></div>"
        )
    return f"<div class='j4-top-cell'>{inner}</div>"


def _safe_error_text(error) -> str:
    return str(error or "일시적인 온라인 조회 오류")[:220]


_STATUS_HEX = {"주도": "#44f0a1", "관찰": "#ff9d3b", "약함": "#9aa0aa"}
_THEME_COL_WIDTHS = [0.7, 2.4, 0.85, 2.0, 0.9, 1.0, 1.3, 1.6]

# 테마 순위표에서 처음부터 보여줄 개수. 나머지는 접어 둔다(자비스3와 같은 값).
_THEME_VISIBLE_COUNT = 10


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
    if foreign.get("live_ok"):
        amount = foreign.get("live_net5_amount") or 0
        direction = "순매수" if amount > 0 else "순매도" if amount < 0 else "보합"
        sections.append(
            f"삼성전자·SK하이닉스 최근 5거래일 수급은 현재가 환산 {_eok(amount)} "
            f"{direction}입니다(현재가 1분 자동조회)"
        )
    elif foreign.get("ok"):
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
            f"미국 시장국면(전일)은 {us_prev.get('score', '—')}점 {us_prev.get('regime', '자료 부족')} · "
            f"SPY {us_prev['spy_change']:+.2f}% · 나스닥100 {us_prev['qqq_change']:+.2f}%로 "
            f"{'우호적' if (us_prev['spy_change'] or 0) >= 0 else '부담'}입니다"
        )
    return ".<br>".join(sections) + "."


def _representative_flow_sub(foreign: dict) -> str:
    """대표종목 5일 수급의 대상·방향·자료원·기준일을 숨김없이 표시한다."""
    if not foreign.get("ok"):
        return "자료 부족"
    stocks = list(foreign.get("stocks") or [])
    if not stocks:
        return "자료 부족"
    labels = [str(stock.get("label") or stock.get("code") or "종목") for stock in stocks]
    target = "+".join(labels)
    if len(stocks) < 2:
        target += " (일부 자료)"

    live = bool(foreign.get("live_ok") and foreign.get("live_net5_amount") is not None)
    amount = float(
        foreign.get("live_net5_amount") if live else foreign.get("net5_amount") or 0
    )
    direction = "순매수" if amount > 0 else "순매도" if amount < 0 else "보합"

    latest_dates = [
        str(((stock.get("flow") or {}).get("latest_date") or "")).strip()
        for stock in stocks
    ]
    known_dates = [value for value in latest_dates if value]
    if len(known_dates) < len(stocks):
        as_of = "기준일 일부 확인 불가"
    elif len(set(known_dates)) == 1:
        as_of = f"{known_dates[0]} 기준"
    else:
        as_of = f"기준일 상이({min(known_dates)}~{max(known_dates)})"
    if live:
        # 종목별은 **하루치**를 적는다. 5일 합계만 보여 주면 "그래서 그날은
        # 팔았나 샀나"를 알 수 없다(2026-07-29 지시). 금액도 부호대로 칠한다 —
        # 회색 한 줄에 몰아 두면 어느 쪽이 파는 쪽인지 안 보인다.
        #
        # 날짜를 괄호에 같이 적는다. 종목별 당일 수급은 장중에 공개되지 않아
        # 여기 숫자는 **가장 최근 완료 거래일**의 것이다. 날짜를 빼고 '(당일)'
        # 이라고만 쓰면 오늘 것으로 읽혀 거짓말이 된다.
        # 설명 두 줄은 뺐다(2026-07-29 지시). 대신 날짜 자리에 오늘 것이면 '오늘'을
        # 적어, 굳이 읽지 않아도 오늘 것인지 아닌지 한눈에 보이게 한다. 네이버가
        # 종목별 당일 수급을 올리면 rows[0]이 오늘 줄로 바뀌어 저절로 '오늘'이 된다.
        # 완료 거래일 한 줄, 당일 한 줄. 당일이 아직 안 올라왔으면 그렇다고 적는다
        # (2026-07-29 사용자 지정 형식).
        def _stock_line(amount_key):
            parts = []
            for stock in stocks:
                amount = stock.get(amount_key)
                if amount is None:
                    continue
                parts.append(
                    f"{stock.get('label') or stock.get('code')} "
                    f"<span style='color:{_sign_color(amount)};font-weight:800'>"
                    f"{_eok(amount)}</span>"
                )
            return " · ".join(parts)

        day_dates = {str(s.get("day_date") or "").strip() for s in stocks if s.get("day_date")}
        day_label = f"({next(iter(day_dates))[5:]})" if len(day_dates) == 1 else "(직전 거래일)"
        day_line = _stock_line("day_net_amount")

        today_line = _stock_line("today_net_amount")
        if today_line:
            today_html = f"(당일) : {today_line}"
        else:
            # 종목별 당일 수급은 KRX 확정 집계가 나온 뒤에야 공개된다. 장중은 물론
            # 마감 직후에도 없다 — 언제 볼 수 있는지만 밝히고 값을 지어내지 않는다.
            today_html = (
                "<span class='j4-muted'>(당일) : 아직 안 올라왔습니다 · "
                "장 마감 뒤 집계되면 자동으로 채워집니다</span>"
            )
        stale = " · 이전 정상 현재가" if foreign.get("live_stale") else ""
        return (
            f"{target}"
            f"<br>{day_label} : {day_line}"
            f"<br>{today_html}"
            f"<br>외국인+기관 {direction}"
            f"<br><span class='j4-muted'>현재가 1분 자동조회{stale} · {as_of}</span>"
        )
    return (
        f"{target}<br>외국인+기관 {direction}"
        f"<br><span class='j4-muted'>네이버 일별 수급 · {as_of}"
        "<br>순매매수량×종가 추정(실시간 아님)</span>"
    )


def _intraday_market_flow_sub(flow: dict) -> str:
    """KOSPI 당일 장중 수급의 주체·원천·실제 표 시각을 표시한다."""
    if not flow.get("ok"):
        return "자료 부족"
    foreign = float(flow.get("foreign_eok") or 0)
    institution = float(flow.get("institution_eok") or 0)
    stale_text = " · 이전 정상값" if flow.get("stale") else ""
    return (
        f"외국인 <span style='color:{_sign_color(foreign)}'>{foreign:+,.0f}억</span>"
        f" · 기관 <span style='color:{_sign_color(institution)}'>{institution:+,.0f}억</span>"
        f"<br><span class='j4-muted'>{flow.get('as_of_time') or '—'} 기준 · 1분 자동조회{stale_text}"
        "<br>네이버 시간별 공개치(지연 가능)</span>"
    )


_REGIME_HEX = {"방어 우선": "#ff5b5b", "중립·선별": "#ff9d3b", "상승 우위": "#44f0a1"}


def _us_futures_cell() -> str:
    """나스닥100 선물 최신 1분봉 — 한국 장중에 미국 방향을 함께 본다.

    온라인 배포 직후 옛 모듈이 남아 함수가 없을 수 있어 getattr로 방어한다
    (2026-07-22 실제 AttributeError 발생 — 위 reload와 이중 안전장치).
    """
    fetcher = getattr(j4data, "get_us_futures_live", None)
    if fetcher is None:
        return _top_metric("나스닥100 선물 (1분봉)", "—", "#9aa0aa", "모듈 갱신 대기")
    futures = fetcher()
    if not futures.get("ok"):
        return _top_metric("나스닥100 선물 (1분봉)", "—", "#9aa0aa", "자료 부족")
    values = futures.get("values") or {}
    nasdaq = values.get("NQ=F") or {}
    sp500 = values.get("ES=F") or {}
    if not nasdaq.get("current"):
        return _top_metric("나스닥100 선물 (1분봉)", "—", "#9aa0aa", "자료 부족")
    change = nasdaq.get("change_pct")
    sub = f"<span style='color:{_sign_color(change)}'>{_pct(change)}</span>"
    if sp500.get("change_pct") is not None:
        sub += (f" · S&P500 선물 <span style='color:{_sign_color(sp500['change_pct'])}'>"
                f"{sp500['change_pct']:+.2f}%</span>")
    sub += f"<br><span class='j4-muted'>1분봉 기준 {nasdaq.get('as_of') or '—'}</span>"

    cell = _top_metric(
        "나스닥100 선물 (1분봉)",
        f"{nasdaq['current']:,.0f}",
        _sign_color(change),
        sub,
        sub_color=_sign_color(change),
    )
    chart = _sparkline_svg(nasdaq.get("chart") or {}, "#4da6ff", "#ff5b5b")
    cell = cell.replace("<div class='j4-top-cell'",
                        "<div class='j4-top-cell'", 1)
    return cell.replace("</div></div>", "</div>" + chart + "</div>", 1) if chart else cell


def _fx_cell() -> str:
    """원/달러 환율을 독립 카드와 당일 차트로 표시한다."""
    fetcher = getattr(j4data, "get_fx_intraday", None)
    if fetcher is None:
        return _top_metric("원/달러 환율 (1분봉)", "—", "#9aa0aa", "모듈 갱신 대기")
    fx = fetcher()
    if not fx.get("ok"):
        return _top_metric("원/달러 환율 (1분봉)", "—", "#9aa0aa", "자료 부족")
    change = fx.get("change_pct")
    sub = (f"<span style='color:{_sign_color(change)}'>{_pct(change)}</span>"
           f"<br><span class='j4-muted'>1분봉 기준 {fx.get('as_of') or '—'}</span>")
    cell = _top_metric("원/달러 환율 (1분봉)", _number(fx.get("current"), 2),
                       _sign_color(change), sub, sub_color="#e6e6e6")
    chart = _sparkline_svg(fx.get("chart") or {}, "#ff5b5b", "#4da6ff")
    return cell.replace("</div></div>", "</div>" + chart + "</div>", 1) if chart else cell


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
    # 아래 조건점수 안내문이 국면 색을 그대로 쓴다(게이지 색과 같아야 한다).
    regime_color = regime_gauge_ui.color_of(overview.get("score"))
    phase_color = "#44f0a1" if phase == "정규장" else "#ff9d3b" if "동시호가" in phase or "시간외" in phase else "#ff5b5b"
    rows = overview["rows"]
    kospi, kosdaq, usdkrw = rows.get("KOSPI", {}), rows.get("KOSDAQ", {}), rows.get("USDKRW", {})
    foreign = overview.get("foreign") or {}
    us_prev = overview.get("us_prev") or {}
    if foreign.get("live_ok"):
        flow_cell = _top_metric(
            "대표종목 5일 수급 (현재가 환산)",
            _eok(foreign.get("live_net5_amount")),
            _sign_color(foreign.get("live_net5_amount")),
            _representative_flow_sub(foreign),
            side=_leader_flow_marks(foreign),
        )
    else:
        # 장외·원천 장애 때는 완료 거래일 자료임을 분명히 하고 종전 값을 보조로 남긴다.
        flow_cell = _top_metric(
            "대표종목 5일 수급 (종가)",
            _eok(foreign.get("net5_amount")) if foreign.get("ok") else "—",
            _sign_color(foreign.get("net5_amount")) if foreign.get("ok") else "#9aa0aa",
            _representative_flow_sub(foreign),
            side=_leader_flow_marks(foreign),
        )

    # 시장 국면·미국 시장국면·공포탐욕 세 가지를 같은 반원 게이지로 통일한다.
    # 제목은 스카이블루로 두고, 미국 카드의 '(미국)'만 밝은 초록으로 구분한다.
    top_cells = [
        regime_gauge_ui.regime_box_html(overview, title="시장 국면 (한국)"),
        # 한국장보다 먼저 움직이는 나스닥100 선물을 코스피 앞에 둔다.
        _us_futures_cell(),
        # 한국장 색 규칙: 오르면 빨강, 내리면 파랑(미국과 반대).
        _top_metric("코스피", _number(kospi.get("current"), 2), "#e6e6e6", kospi.get("change_pct"),
                    sub_signed=True).replace("<div class='j4-top-cell'",
            "<div class='j4-top-cell'", 1).replace("</div></div>", "</div>"
            + _sparkline_svg(_kr_index_chart("KOSPI"), "#ff5b5b", "#4da6ff") + "</div>", 1),
        _top_metric("코스닥", _number(kosdaq.get("current"), 2), "#e6e6e6", kosdaq.get("change_pct"),
                    sub_signed=True).replace("<div class='j4-top-cell'",
            "<div class='j4-top-cell'", 1).replace("</div></div>", "</div>"
            + _sparkline_svg(_kr_index_chart("KOSDAQ"), "#ff5b5b", "#4da6ff") + "</div>", 1),
        _fx_cell(),
        # 미국 4대 지수 그림을 여기에도 붙인다(2026-07-25 사용자 지시). 값·기준선은
        # 그 분봉 자료에서 바로 뽑으므로 한국 화면이 미국 시세를 따로 조회하지 않는다.
        *_us_index_cells(),
        # 폰·태블릿에서 시장상태가 바로 위 차트에 붙어 보였다 — 여기서 줄을 끊고
        # 두 줄만큼 띄운다(2026-07-25 지시). PC에서는 이 칸이 없는 것과 같다.
        "<div class='j4-top-break'></div>",
        _top_metric(
            "시장상태", phase, phase_color,
            "한국 거래 세션",
        ),
        flow_cell,
        # 미국테마의 시장 국면 카드를 제목·문구·전일 행까지 그대로 복제한다.
        # 한국 화면용 제목이나 S&P/나스닥 별도 행을 덧붙이지 않는다.
        regime_gauge_ui.regime_box_html(
            us_prev.get("market_overview"), title="시장 국면 (미국)", note_prefix=" : "
        ),
        fear_greed_ui.box_html(
            us_prev.get("fear_greed_detail"), title="공포·탐욕 지수 (미국)"
        ),
    ]
    # 게이지 스타일은 지표 줄과 따로 내보낸다 — 줄 안에 <style>을 끼워 넣으면
    # 스트림릿 마크다운이 그 덩어리를 HTML로 안 보고 글로 흘려버린다(2026-07-24 실제 깨짐).
    st.markdown(f"<style>{fear_greed_ui.CSS}</style>", unsafe_allow_html=True)
    st.markdown(f"<div class='j4-top-row'>{''.join(top_cells)}</div>", unsafe_allow_html=True)
    # 긴 설명은 접어 둔다 — 폰·태블릿에서 이 글이 첫 화면을 다 먹었다
    # (2026-07-25 사용자 지시, 미국테마와 같은 방식). 값·판정은 그대로다.
    with st.expander("조건점수·시장 상태 설명 보기", expanded=False):
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
            <span style="color:#e6e6e6">장전 동시호가 08:30~09:00 → 정규장 09:00~15:30 → 시간외 → 장 마감</span><br>
            <span style="color:#4da6ff">공포·탐욕 지수</span>
            <span style="color:#9aa0aa; font-weight:600">는 CNN이 7개 심리 지표로 집계한 미국 시장 심리
            (0 극단적 공포 ~ 100 극단적 탐욕)이며 참고용입니다. 한국장 조건점수·매수 판정에는
            반영하지 않습니다.</span>
        </div>
            """,
            unsafe_allow_html=True,
        )
    # 시장 전체 흐름·행동 기준도 접는다(2026-07-25 사용자 지시: "다 숨겨라").
    with st.expander("시장 전체 흐름 · 행동 기준 보기", expanded=False):
        st.markdown(
            f"""
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
    # 폰에서도 태블릿처럼 옆으로 밀어 본다(2026-07-25 사용자 지시).
    theme_box = st.container(key="j4_theme_table")
    for column, title in zip(theme_box.columns(_THEME_COL_WIDTHS), titles):
        column.markdown(f"<div class='j4-th-head'>{title}</div>", unsafe_allow_html=True)

    button_css = []
    clicked = None
    # 11위부터는 접어 둔다(자비스3와 같은 규칙, 2026-07-25 사용자 지시).
    all_rows = list(ranking.get("rows", []))
    rest_box = None
    if len(all_rows) > _THEME_VISIBLE_COUNT:
        # 키를 가진 칸으로 한 번 감싼다 — 그래야 위 표와 같은 '옆으로 밀기' CSS가
        # 이 안에도 걸린다. st.expander 자체에는 key를 줄 수 없다.
        rest_box = st.container(key="j4_theme_rest").expander(
            f"{_THEME_VISIBLE_COUNT + 1}위~{len(all_rows)}위 테마 더 보기", expanded=False
        )
    for index, row in enumerate(all_rows):
        target = theme_box if index < _THEME_VISIBLE_COUNT or rest_box is None else rest_box
        name = row.get("name", "")
        color = _STATUS_HEX.get(row.get("status", ""), "#e6e6e6")
        button_key = f"j4tbtn_{index:02d}"
        button_css.append(f"div[class*='st-key-{button_key}'] button p {{ color: {color} !important; }}")
        if name == selected:
            button_css.append(
                f"div[class*='st-key-{button_key}'] button {{ background: rgba(255,176,32,0.16) !important; }}"
            )
        cols = target.columns(_THEME_COL_WIDTHS)
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


_LEADER_COL_WIDTHS = [0.7, 2.0, 1.6, 0.95, 1.15, 1.05, 1.0, 1.5, 1.7, 1.15]


def _render_leader_table(leaders: list[dict], selected_code: str | None) -> str | None:
    """종목표를 그리고, 종목 이름 버튼이 눌리면 그 종목코드를 돌려준다.

    예전에는 순수 HTML 표라 이름을 눌러도 아무 일이 없었다 — 눌림목 표는 눌리는데
    이 표만 안 눌려 고장으로 보였다(2026-07-29 지시). 테마표·눌림목표와 같은
    방식(칸 나누기 + 이름 버튼)으로 맞춘다. 아래 '상세 종목 선택'은 그대로 둔다.
    """
    titles = ["순위", "종목", "조건점수", "당일", "52주 고가 대비", "20일 수익률",
              "수급(대금%)", "동반(5일)", "동반(매수/매도/20일)", "매수 상태"]
    box = st.container(key="j4_leader_table")
    for column, title in zip(box.columns(_LEADER_COL_WIDTHS), titles):
        column.markdown(f"<div class='j4-th-head'>{title}</div>", unsafe_allow_html=True)

    rank_mark = {1: "🟡 1위", 2: "⚪ 2위", 3: "🟠 3위"}
    button_css = []
    clicked = None
    for index, leader in enumerate(leaders[:6]):
        metrics, plan, flow = leader["metrics"], leader["plan"], leader["flow"]
        rank = int(leader.get("rank") or 0)
        score = float(leader.get("score") or 0)
        button_key = f"j4lbtn_{index:02d}"
        if leader["code"] == selected_code:
            button_css.append(
                f"div[class*='st-key-{button_key}'] button "
                "{ background: rgba(255,176,32,0.16) !important; }"
            )
        cols = box.columns(_LEADER_COL_WIDTHS)
        cols[0].markdown(
            f"<div class='j4-td'>{rank_mark.get(rank, f'{rank}위')}</div>", unsafe_allow_html=True)
        if cols[1].button(leader["name"], key=button_key, width="stretch"):
            clicked = leader["code"]
        cols[2].markdown(
            "<div class='j4-td'><div class='j4-barwrap'><div class='j4-bar'>"
            f"<div class='j4-bar-fill' style='width:{min(score, 100):.0f}%'></div></div>"
            f"<span class='j4-bar-num'>{score:.1f}</span></div></div>",
            unsafe_allow_html=True,
        )
        for slot, value in (
            (3, metrics.get("change_pct")),
            (4, metrics.get("from_high_pct")),
            (5, metrics.get("ret20")),
        ):
            cols[slot].markdown(
                f"<div class='j4-td' style='color:{_sign_color(value)}; font-weight:700'>"
                f"{_pct(value)}</div>", unsafe_allow_html=True)
        cols[6].markdown(f"<div class='j4-td'>{_flow_ratio_cell(flow)}</div>", unsafe_allow_html=True)
        cols[7].markdown(f"<div class='j4-td'>{_partner5_cell(flow)}</div>", unsafe_allow_html=True)
        cols[8].markdown(f"<div class='j4-td'>{_partner20_cell(flow)}</div>", unsafe_allow_html=True)
        cols[9].markdown(
            f"<div class='j4-td'>{plan.get('state', '')}</div>", unsafe_allow_html=True)

    if button_css:
        st.markdown("<style>" + "".join(button_css) + "</style>", unsafe_allow_html=True)
    return clicked


def _leader_table_html(leaders: list[dict], selected_code: str | None) -> str:
    """(지금은 안 씀) 예전 HTML 표.

    2026-07-29에 이름을 누를 수 있게 _render_leader_table로 바꿨다. 이 함수를
    지우지 않고 남겨 둔 이유는, 폰에서 새 표가 이상하면 호출부 한 줄만 되돌리면
    바로 예전 화면으로 돌아갈 수 있게 하기 위해서다. 폰 CSS(mobile_ui.py의
    .j4-theme-table 규칙)도 그대로 살아 있다.
    """
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
        # 눌림목 표와 같은 칸을 여기에도 둔다(2026-07-25 사용자 지시).
        # 코드 칸은 뺐다 — 태블릿에서 '0058/30'처럼 두 줄로 접혔고, 코드는 아래
        # 상세와 차트 카드에 그대로 있다.
        body.append(
            f"<tr class='j4-th-row{highlight}'>"
            f"<td>{rank_mark.get(rank, f'{rank}위')}</td>"
            f"<td class='j4-th-name'>{leader['name']}</td>"
            f"<td>{score_bar}</td>"
            f"<td style='color:{_sign_color(change)}; font-weight:700'>{_pct(change)}</td>"
            f"<td style='color:{_sign_color(from_high)}; font-weight:700'>{_pct(from_high)}</td>"
            f"<td style='color:{_sign_color(ret20)}; font-weight:700'>{_pct(ret20)}</td>"
            f"<td>{_flow_ratio_cell(flow)}</td>"
            f"<td>{_partner5_cell(flow)}</td>"
            f"<td>{_partner20_cell(flow)}</td>"
            f"<td>{plan.get('state', '')}</td></tr>"
        )
    return (
        "<div class='j4-table-scroll'><table class='j4-theme-table'><colgroup>"
        "<col style='width:6%'><col style='width:16%'><col style='width:13%'>"
        "<col style='width:7%'><col style='width:9%'><col style='width:8%'>"
        "<col style='width:8%'><col style='width:11%'><col style='width:14%'>"
        "<col style='width:8%'></colgroup>"
        "<thead><tr><th>순위</th><th style='text-align:left; padding-left:1.2rem'>종목</th>"
        "<th>조건점수</th><th>당일</th><th>52주 고가 대비</th><th>20일 수익률</th>"
        "<th>수급(대금%)</th><th>동반(5일)</th><th>동반(매수/매도/20일)</th>"
        "<th>매수 상태</th></tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table></div>"
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
    rank = int(item.get("rank") or 0)
    medal = _MEDAL_BY_RANK.get(rank, "")
    state = item["plan"].get("state", "")
    color_word = _STATE_COLOR_WORD.get(state, "gray")
    # 눌림목 표에서 직접 고른 종목은 테마 대장주 순위 밖일 수 있다(rank 0).
    rank_text = f"{rank}위" if rank else "눌림목 선택"
    return (
        f"{medal} :green[**{rank_text} · {item['name']} ({item['code']})**] · "
        f":red[**{item['score']:.1f}점**] · :{color_word}[**{state}**]"
    )


def _pullback_as_candidate(row: dict, leaders: list[dict]) -> dict | None:
    """눌림목 표에서 고른 종목을 '상세 종목 선택' 후보 모양으로 바꾼다.

    거래대금 상위 3위 안에 없는 종목을 눌러도 아래 상세가 그 종목으로 바뀌어야 한다는
    2026-07-24 지시. 이미 대장주 목록에 있으면 그 항목(테마 상대강도로 재계산된 점수)을
    그대로 쓰고, 목록 밖 종목만 눌림목 자료로 후보를 만든다.
    """
    if not row or not row.get("code"):
        return None
    found = next((item for item in leaders if item["code"] == row["code"]), None)
    if found is not None:
        return found
    metrics = row.get("metrics") or {}
    flow = row.get("flow") or {}
    from_high = metrics.get("from_high_pct")
    flow_text = (
        f" · 외국인+기관 5일 {flow['net5_amount'] / 1e8:+,.0f}억"
        if flow.get("ok") else " · 수급 확인 필요"
    )
    return {
        "code": row["code"],
        "name": row.get("name") or row["code"],
        "metrics": metrics,
        "flow": flow,
        "score": row.get("score") or 0.0,
        "score_parts": row.get("score_parts") or [0] * 6,
        "plan": row.get("plan") or {},
        "rank": 0,
        "from_pullback": True,
        "stock_reason": (
            f"눌림목 선택 종목 · 52주 고가 대비 {from_high:.1f}%{flow_text}"
            if from_high is not None else f"눌림목 선택 종목{flow_text}"
        ),
    }


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
                    # 동반 숫자('1/5 · 1/1/20')는 읽히지 않는다는 지적(2026-07-25)에 따라
                    # 표에서 쓰던 점·막대 그림으로 바꾼다. 금액은 글로 남긴다.
                    st.caption(f"외국인+기관 5일 {_eok(flow.get('net5_amount'))}")
                    st.markdown(_flow_marks_html(flow), unsafe_allow_html=True)
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


# 하루 수급 점 — 한국시장 색 규칙(매수 빨강 · 매도 파랑)을 그대로 쓴다.
# 왼쪽이 최근일이다. 숫자(3/5)가 앞에 오므로 점이 잘려도 뜻은 잃지 않는다.
# 글자(●◐○)로 그렸더니 글꼴마다 크기가 달라 ◐만 커 보였다(2026-07-25 사용자 지적).
# CSS 동그라미로 그려 넷 다 같은 크기로 맞춘다. 보합만 속이 빈 원이다.
# 동그라미 하나가 그날의 '두 사람'이다 — 왼쪽 반은 외국인, 오른쪽 반은 기관.
# 각 반의 색이 그 사람의 방향이다: 빨강 샀다, 파랑 팔았다, 흰색 보합.
# 반반으로 갈라 보니 어지럽기만 하다는 지적(2026-07-25). 세 색으로 끝낸다 —
# 둘 다 사면 빨강, 둘 다 팔면 파랑, 나머지는 전부 흰색. '누가 사고 누가 팔았나'는
# 자료에는 그대로 남아 있으니(jarvis4_data의 day_marks) 나중에 되살릴 수 있다.
# 파랑이 옅어 눈에 안 든다는 지적(2026-07-25)에 따라 진한 파랑으로 내렸다.
# 동반 표시(동그라미·20일 막대·숫자)는 전부 이 색을 함께 쓴다 — 한 칸 안에서
# 두 가지 파랑이 섞이면 고장 난 것처럼 보인다.
_BUY, _SELL, _NONE = "#ff5b5b", "#1f6feb", "#ffffff"

_FLOW_MARK_STYLE = {
    "both_buy": _BUY,       # 외국인·기관 둘 다 순매수
    "both_sell": _SELL,     # 둘 다 순매도
    # 아래는 전부 흰색 — 한쪽만 움직였거나 서로 엇갈린 날이다.
    "f_buy_i_sell": _NONE,
    "f_sell_i_buy": _NONE,
    "f_buy": _NONE,
    "i_buy": _NONE,
    "f_sell": _NONE,
    "i_sell": _NONE,
    "flat": None,           # 둘 다 보합 — 빈 회색 원
}


def _flow_dots(marks) -> str:
    """동그라미 다섯. 글자(●○)는 글꼴마다 크기가 달라 SVG로 그린다(2026-07-25)."""
    dots = []
    for mark in (marks or []):
        color = _FLOW_MARK_STYLE.get(mark, None)
        body = (
            f"<circle cx='5' cy='5' r='4.5' fill='{color}'/>" if color
            else "<circle cx='5' cy='5' r='4.2' fill='none' stroke='#9aa0aa' stroke-width='1'/>"
        )
        dots.append(
            "<svg width='10' height='10' viewBox='0 0 10 10' "
            f"style='vertical-align:middle; margin-right:3px'>{body}</svg>"
        )
    return "".join(dots)



def _index_spark(symbol: str) -> list:
    try:
        return j4data.get_index_sparkline(symbol)
    except Exception:
        return []


def _kr_index_chart(symbol: str) -> dict:
    """KOSPI·KOSDAQ 그림 자료 — 마지막 장의 분봉과 그 전날 종가.

    네이버 분봉 API가 지수 심볼을 받지 않아 한동안 그림이 비어 있었다. 자료원은
    jarvis4_data.get_index_intraday로 옮겼다(야후 분봉 + 네이버 시간별 시세 꼬리).
    못 구하면 그리지 않는다 — 30일 일봉으로 대신 그렸더니 '기준선 위로 간 적이
    없는데 빨간 구간이 있다'는 지적을 받았다(2026-07-25).
    """
    try:
        payload = j4data.get_index_intraday(symbol)
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    points, base = payload.get("points"), payload.get("base")
    if not isinstance(points, list) or len(points) < 2 or base is None:
        return {}
    return {"points": points, "base": float(base)}


def _us_index_cells() -> list:
    """미국테마의 4대 지수 값과 판정을 그대로 쓰고 그림만 함께 붙인다."""
    overview = us_index_data.market_overview()
    data = us_index_data.sparklines()
    display = us_index_data.display()
    if not overview.get("ok") or not display:
        return []
    phase = (overview.get("phase") or {}).get("label", "—")
    live = phase == "정규장 시간"
    rows = overview.get("rows") or {}
    cells = []
    for symbol, name in display:
        row = rows.get(symbol) or {}
        if not row.get("ok"):
            cells.append(_top_metric(name, "—", "#9aa0aa", "자료 부족"))
            continue
        # 미국테마와 같은 규칙: 숫자는 시장 요약값, 장 마감 뒤 등락률은 마지막으로
        # 끝난 정규장 값을 쓴다. 차트 끝값으로 숫자를 다시 계산하지 않는다.
        change = row.get("change_pct") if live else row.get("last_session_change_pct")
        note = "정규장" if live else "장 마감 기준"
        # 미국 시장 색 규칙: 오르면 파랑, 내리면 빨강.
        cells.append(
            f"<div class='j4-top-cell'>"
            f"<div class='j4-top-label'>{name}</div>"
            f"<div class='j4-top-val' style='color:#e6e6e6'>{_number(row.get('current'), 2)}</div>"
            f"<div class='j4-top-sub' style='color:{'#4da6ff' if (change or 0) >= 0 else '#ff5b5b'}'>"
            f"{_pct(change)} <span class='j4-muted'>· {note}</span></div>"
            + _sparkline_svg(data.get(symbol), "#4da6ff", "#ff5b5b") + "</div>"
        )
    return cells


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
            f"stroke='{color}' stroke-width='1.6' stroke-linecap='round'/>"
        )
    fill = up_color if points[-1] >= base else down_color
    area = f"0,{base_y:.1f} " + " ".join(
        f"{i * step:.1f},{_y(v):.1f}" for i, v in enumerate(points)
    ) + f" {width:.1f},{base_y:.1f}"
    return (
        f"<svg viewBox='0 0 {width:.0f} {height}' width='{width:.0f}' height='{height}' "
        f"style='display:block; margin:.4rem 0 .1rem;"
        f" border:1px solid rgba(255,255,255,.22); border-radius:8px;"
        f" background:rgba(255,255,255,.03)'>"
        f"<polygon points='{area}' fill='{fill}' fill-opacity='0.14'/>"
        f"<line x1='0' y1='{base_y:.1f}' x2='{width:.0f}' y2='{base_y:.1f}' "
        f"stroke='rgba(255,255,255,.38)' stroke-width='1' stroke-dasharray='4 4'/>"
        + "".join(segments) + "</svg>"
    )



def _partner5_cell(flow: dict) -> str:
    """동반(5일) — 숫자 + 점 다섯. 왼쪽이 가장 최근일이다."""
    if not flow.get("ok"):
        return "<span style='color:#9aa0aa'>확인 필요</span>"
    both, window = int(flow.get("both_buy_days5") or 0), int(flow.get("window5") or 0)
    return (
        f"<span style='color:{'#ff5b5b' if both >= 3 else '#9aa0aa'}; font-weight:800'>"
        f"{both}/{window}</span> {_flow_dots((flow.get('day_marks') or [])[:5])}"
    )


def _leader_flow_marks(foreign: dict) -> str:
    """대표종목 칸 — 삼성전자·SK하이닉스 각각의 동반 그림을 이름과 함께 붙인다.

    합계 금액만으로는 두 종목 중 어느 쪽이 팔린 것인지 알 수 없다(2026-07-25 지시).
    """
    blocks = []
    for stock in (foreign.get("stocks") or []):
        # 좁은 칸에 둘을 나란히 놓아야 하므로 제목은 짧게 쓴다.
        marks = _flow_marks_html(stock.get("flow") or {}, compact=True)
        if marks:
            blocks.append(
                f"<div class='j4-fm-stock'><div class='j4-fm-name'>{stock.get('label', '')} 동반"
                f"</div>{marks}</div>"
            )
    return f"<div class='j4-fm-pair'>{''.join(blocks)}</div>" if blocks else ""


def _flow_marks_html(flow: dict, *, titled: bool = True, compact: bool = False) -> str:
    """동반(5일) 점 다섯 + 동반(매수/매도/20일) 막대를 카드 안에 넣는다(2026-07-25).

    '1/5 · 1/1/20' 같은 숫자 나열은 읽히지 않는다는 지적을 받았다. 표에서 쓰던
    그림을 그대로 옮겨 쓴다 — 표와 카드가 같은 그림이라야 눈이 옮겨 다니지 않는다.
    """
    if not isinstance(flow, dict) or not flow.get("ok"):
        return ""
    rows = (
        # 좁은 칸에서는 제목이 자리를 다 먹어 막대가 안 보인다. 종목 이름 줄에 '동반'을
        # 적어 두고 여기서는 기간만 쓴다.
        ("5일" if compact else "동반(5일)", _partner5_cell(flow)),
        ("20일" if compact else "동반(매수/매도/20일)", _partner20_cell(flow)),
    )
    body = "".join(
        "<div class='j4-fm-row'>"
        + (f"<span class='j4-fm-label'>{label}</span>" if titled else "")
        + f"<span class='j4-fm-cell'>{cell}</span></div>"
        for label, cell in rows
    )
    return f"<div class='j4-flowmarks'>{body}</div>"


def _partner20_cell(flow: dict) -> str:
    """동반(매수/매도/20일) — 막대 하나 안에 매수는 빨강, 매도는 파랑으로 같이 담는다.

    막대를 둘로 나누면 자리를 두 배로 먹고 태블릿에서 줄이 접혔다(2026-07-25).
    """
    if not flow.get("ok"):
        return "<span style='color:#9aa0aa'>확인 필요</span>"
    buy = int(flow.get("both_buy_days20") or 0)
    sell = int(flow.get("both_sell_days20") or 0)
    window = int(flow.get("window20") or 0)
    buy_pct = (buy / window * 100) if window else 0
    sell_pct = (sell / window * 100) if window else 0
    return (
        "<div class='j4-barwrap'><div class='j4-bar'>"
        "<div style='display:flex; height:8px'>"
        f"<div style='width:{min(buy_pct, 100):.0f}%; background:{_BUY}'></div>"
        f"<div style='width:{min(sell_pct, 100 - min(buy_pct, 100)):.0f}%; background:{_SELL}'></div>"
        "</div></div>"
        "<span class='j4-bar-num' style='white-space:nowrap'>"
        f"<span style='color:{_BUY}'>{buy}</span>/"
        f"<span style='color:{_SELL}'>{sell}</span>/"
        f"<span style='color:#9aa0aa'>{window}</span></span></div>"
    )


def _flow_ratio_cell(flow: dict) -> str:
    """수급 칸 — 금액 대신 '5일 거래대금의 몇 %'만 보여준다(2026-07-25 사용자 지시).

    금액(+321억)은 큰 종목인지 작은 종목인지 감이 없어서 뺐다. 절대 금액은
    종목을 누르면 나오는 상세에 그대로 있다.
    """
    if not flow.get("ok"):
        return "<span style='color:#9aa0aa'>확인 필요</span>"
    ratio = flow.get("net5_ratio_pct")
    if ratio is None:
        return "<span style='color:#9aa0aa'>—</span>"
    return f"<span style='color:{_sign_color(ratio)}; font-weight:800'>{ratio:+.1f}%</span>"


def _render_day_price_row(metrics: dict) -> None:
    """당일 가격 한 줄 — 현재가·전일 종가·시가·고가·저가·종가.

    2026-07-24 사용자 요청: 차트 위 빈자리에 그날 가격을 한눈에 본다. 고가·저가는
    전일 종가 대비 몇 %인지 함께 적고, 한국시장 색 규칙(+빨강 −파랑)을 쓴다.
    """
    prev_close = metrics.get("prev_close")
    current = metrics.get("current")
    day_open = metrics.get("day_open")
    day_high = metrics.get("day_high")
    day_low = metrics.get("day_low")
    day_close = metrics.get("day_close")
    intraday = j4data.is_regular_session()

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
        sub = (
            f"<div class='j4-mc-sub' style='color:{_sign_color(change)}'>{_pct(change)}</div>"
            if change is not None else
            (f"<div class='j4-mc-sub j4-muted'>{sub_text}</div>" if sub_text else "")
        )
        return (
            f"<div class='j4-mc'><div class='j4-mc-label'>{label}</div>"
            f"<div class='j4-mc-val' style='color:{color}'>{_won(value)}</div>{sub}</div>"
        )

    title_note = "장중이라 고가·저가·종가는 지금까지의 값입니다" if metrics.get("day_is_today") else \
        f"오늘 일봉이 아직 없어 마지막 거래일({metrics.get('last_date') or '—'}) 값입니다"
    st.markdown(
        "<div class='j4-chart-heading'>당일 가격 · 시가/고가/저가 한눈에 보기</div>",
        unsafe_allow_html=True,
    )
    st.caption(f"고가·저가 옆 백분율은 전일 종가 대비입니다. {title_note}.")
    cells = [
        _cell("현재가", current, metrics.get("change_pct")),
        _cell("전일 종가", prev_close, None, sub_text="어제 마감", value_color="#e6e6e6"),
        _cell("당일 시가", day_open, _vs_prev(day_open)),
        _cell("당일 고가", day_high, _vs_prev(day_high)),
        _cell("당일 저가", day_low, _vs_prev(day_low)),
        _cell(
            "당일 종가" if not intraday else "당일 종가(장중)",
            current if intraday else day_close,
            _vs_prev(current if intraday else day_close),
            sub_text=None,
        ),
    ]
    st.markdown(f"<div class='j4-metric-row'>{''.join(cells)}</div>", unsafe_allow_html=True)


def _render_stock_detail(theme_row: dict, leader: dict, market: dict, top_candidates: list[dict],
                         stock_key: str, *, panel: str = "theme") -> None:
    """종목 상세 한 벌. 같은 화면을 위(테마 종목)·아래(눌림목 종목) 두 곳에 그린다.

    panel은 위젯 키를 갈라 두 상세가 서로를 덮어쓰지 않게 한다 — 같은 종목을 위아래
    둘 다 고르면 매수 기록 입력칸 키가 겹쳐 화면이 죽는다(2026-07-29 분리 요청).
    """
    code = leader["code"]
    if panel == "theme":
        st.session_state["j4_selected_code"] = code
    metrics, plan, flow = leader["metrics"], leader["plan"], leader["flow"]

    st.divider()
    detail_rank = int(leader.get("rank") or 0)
    detail_medal = _MEDAL_BY_RANK.get(detail_rank, "") if float(leader.get("score") or 0) >= 80 else ""
    detail_medal_html = f"<span class='j4-medal'>{detail_medal}</span> " if detail_medal else ""
    st.markdown(
        f"<div class='j4-stock-name'>{detail_medal_html}{leader['name']} · {code}</div>"
        f"<div class='j4-stock-sub'>{theme_row['name']} "
        f"{f'대장주 {detail_rank}위' if detail_rank else '눌림목 선택 종목'} · {plan.get('recommendation')}</div>",
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
        # 금액(+488억)은 바로 아래 '종목 선정 근거' 줄에 또 나온다. 여기서는 숫자를 빼고
        # 동반 그림만 둔다(2026-07-25 지시) — 숫자 나열이 겹쳐 읽히지 않았다.
        f"<div class='j4-mc'><div class='j4-mc-label'>외국인+기관 5일</div>"
        + (_flow_marks_html(flow) or "<div class='j4-mc-val j4-muted'>—</div>")
        + "</div>",
        f"<div class='j4-mc'><div class='j4-mc-label'>종목 조건점수</div>"
        f"<div class='j4-mc-val j4-green'>{float(leader.get('score') or 0):.1f}/100</div>"
        f"<div class='j4-mc-sub j4-muted'>{plan.get('state', '')}</div></div>",
    ]
    st.markdown(f"<div class='j4-metric-row'>{''.join(cells)}</div>", unsafe_allow_html=True)

    factor_names = ["테마 대비 상대강도", "52주 신고가 위치", "추세(20·50·200일선)", "유동성(거래대금)", "변동성 안정", "수급(외국인+기관)"]
    factor_max = [20, 15, 20, 15, 10, 20]

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
        # 가격이 있는 종목과 없는 종목이 왜 갈리는지 설명한다
        # (2026-07-22 사용자 질문). 길어서 접어 둔다(2026-07-25 사용자 지시).
        with st.expander("가격 칸이 채워지는 기준 보기", expanded=False):
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

    _render_day_price_row(metrics)

    # 당일 차트 — 테마 대장주 상세에는 있는데 눌림목 상세에만 없었다(2026-07-25
    # 사용자 지적, 미국테마와 같은 처리). 대장주와 같은 자료·같은 차트를 쓴다.
    st.markdown("<div class='j4-chart-heading'>당일 · 실시간(지연 가능)</div>", unsafe_allow_html=True)
    intraday_error = ""
    try:
        intraday_payload = j4data.get_intraday_chart(code)
    except Exception as exc:  # 당일 자료가 없어도 아래 일봉·주봉·월봉은 그려야 한다
        intraday_payload = None
        intraday_error = _safe_error_text(exc)
    if isinstance(intraday_payload, dict) and intraday_payload.get("ok"):
        st.altair_chart(_intraday_chart(intraday_payload), width="stretch", theme="streamlit")
        st.caption(f"기준 {intraday_payload.get('source_time') or '시각 확인 불가'}")
    elif intraday_error:
        st.info(f"당일 자료 없음 — {intraday_error}")
    else:
        st.info("당일 자료 없음 — 한국장이 열리면 표시됩니다.")

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

    _render_buy_form(theme_row, leader, market, top_candidates, stock_key, panel=panel)


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


def _render_buy_form(theme_row: dict, leader: dict, market: dict, top_candidates: list[dict],
                     stock_key: str, *, panel: str = "theme") -> None:
    code = leader["code"]
    metrics, plan, flow = leader["metrics"], leader["plan"], leader["flow"]
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)

    # 상세 종목 선택(복제)은 '실제 매수 기록' 제목 위에 둔다(자비스3와 같은 배치).
    code_options = [item["code"] for item in top_candidates]
    by_code = {item["code"]: item for item in top_candidates}
    mirror_key = f"{stock_key}_form"
    # 위·아래 상세가 같은 종목을 열어도 입력칸 키가 겹치지 않게 한다.
    wid = f"{panel}_{code}"

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
                # 상세가 여러 벌 그려지므로 표 키도 패널별로 갈라야 한다.
                _render_records_editor(records, key_prefix=f"form_{panel}")
            else:
                st.caption("아직 저장된 매수 기록이 없습니다.")
    st.caption("실제로 매수한 경우에만 저장합니다. 저장 시 당시 시장·테마·종목·수급 조건도 함께 보존됩니다.")

    with st.container(border=True):
        form_rank = int(leader.get("rank") or 0)
        form_medal = _MEDAL_BY_RANK.get(form_rank, "") if float(leader.get("score") or 0) >= 80 else ""
        form_medal_html = f"<span class='j4-medal'>{form_medal}</span> " if form_medal else ""
        st.markdown(
            f"<div class='j4-stock-name'>{form_medal_html}{leader['name']} · {code}</div>"
            f"<div class='j4-stock-sub'>{theme_row['name']} "
            f"{f'대장주 {form_rank}위' if form_rank else '눌림목 선택 종목'} · {plan.get('recommendation')} · "
            f"현재가 {_won(metrics.get('current'))} "
            f"<span class='{_sign_class(metrics.get('change_pct'))}'>{_pct(metrics.get('change_pct'))}</span></div>",
            unsafe_allow_html=True,
        )
        with st.form(f"j4_buy_form_{wid}", clear_on_submit=False, border=False):
            c1, c2, c3, c4 = st.columns(4)
            buy_date = c1.date_input("매수일", value=date.today(), key=f"j4_buy_date_{wid}")
            default_price = float(metrics.get("current") or 1)
            # 원화는 소수점이 없지만 min_value·step과 자료형이 어긋나면 위젯이 예외를 낸다.
            buy_price = c2.number_input(
                "실제 매수가(원)", min_value=1.0, value=float(round(default_price)), step=10.0,
                key=f"j4_buy_price_{wid}", format="%.0f",
            )
            quantity = c3.number_input("수량(선택)", min_value=0.0, value=0.0, step=1.0, key=f"j4_buy_qty_{wid}")
            trade_style = c4.selectbox("매매유형", ["단타", "스윙", "중장기"], index=1, key=f"j4_trade_style_{wid}")
            memo = st.text_area("매수 이유·메모", key=f"j4_buy_memo_{wid}", height=80)
            confirmed = st.checkbox("실제 체결된 매수임을 확인합니다", key=f"j4_buy_confirm_{wid}")
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
        st.caption("테마 순위는 5분 캐시, 눌림목은 30분 캐시, 시장판단은 1분 자동 갱신됩니다.")

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
    # 처음엔 접어 둔다 — 폰에서 이 표가 첫 화면을 다 먹었다(2026-07-25 사용자 지시).
    with st.expander("📈 자비스4에만 있는 승률 보완 장치 9가지 (미국테마에 없는 것)", expanded=False):
        st.markdown(
            """
| # | 무엇 | 왜 승률에 도움이 되나 | 어디서 보이나 |
|---|---|---|---|
| 1 | **수급 20점** (외국인+기관) | 국내에서 가장 검증된 신호. 금액이 아니라 **5일 거래대금 대비 비율**로 재서 대형주 편향을 없앰 | 종목 점수표 6번째 항목 |
| 2 | **동적 테마 선정** | 네이버 266개 테마를 매일 전수 스캔 → 상위 10개만. 약한 테마 자동 탈락 = 낡은 테마에 물리지 않음 | 테마표 🆕 표시·탈락 안내 |
| 3 | **국내형 추격 금지** | 당일 +20%·5일 +25%·ATR 15% 이상 제외(상한가 30% 제도 반영) | 매수 상태 '추격 금지' |
| 4 | **미국 전일 게이트 15점** | 한국장은 미국 전일과 갭 상관이 높음 | 시장판단 상단 '미국 전일' |
| 5 | **호가단위 반올림** | 기준가·목표가가 실제 주문 가능한 가격으로 나옴 | 매수 심사 결과 4칸 |
| 6 | **자동 제외 필터** | 스팩·우선주·리츠는 점수와 무관하게 후보에서 뺌 | 대장주 목록에 아예 없음 |
| 7 | **기관 수급 반전 연동** | 장중 진입 타이밍 참고(점수에는 미반영) | 종목 상세 ⚡단타 참고 신호 |
| 8 | **약한 테마의 강한 종목 구제** | 국내 테마는 성격이 섞여 있어 테마 평균이 종목 품질을 대표하지 못함. **종목 85점 이상이면 테마 점수와 무관하게 후보** | 종목 상세 '매수 심사 결과' |
| 9 | **눌림목 자동 탐색** | 52주 신고가 1~20일 전 · 2개 이상 테마 · **신고가 때 점수 75점 이상**. 지금 눌린 점수가 아니라 **고점 때 점수를 역산**해 판정 | 눌림목 종목 찾기 표 |

**한국 시장에 맞게 다시 잰 것** — 미국 배점을 그대로 쓰면 안 되는 게 실측으로 확인됐습니다.
국내 대형주 상당수가 52주 고가 대비 −30~−45% 구간이라 미국 기준(−25%~0)에서는 전 종목이
0점이 됐습니다. 그래서 **신고가 배점을 20→15로 줄이고 범위를 −45~0으로 넓히는 대신,
국내에서 더 잘 듣는 추세(이동평균선) 배점을 15→20으로 올렸습니다.**
            """
        )
    st.markdown(f"### 오늘의 강한 테마 {len(ranking['rows'])} · 실시간 순위")
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

    # 눌림목 클릭이 테마 선택을 옮기던 장치는 없앴다(2026-07-29). 이제 눌림목 종목은
    # 자기 자리(아래 눌림목 상세)에서만 열리므로 위쪽 테마를 건드릴 이유가 없다.
    st.session_state.pop("j4_pending_pick", None)

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

    # 상장한 지 얼마 안 된 종목은 20일선·52주 고가 칸이 비어 나온다. 화면은 그대로
    # 다 그리되(2026-07-29 사용자 지시), 왜 빈 칸이 있는지와 점수를 나란히 비교하면
    # 안 된다는 것을 위에 적어 준다.
    _partial = [row for row in leaders if row.get("partial")]
    if _partial:
        _days = " · ".join(f"{row['name']} {row.get('bars')}일" for row in _partial)
        st.info(
            f"📌 상장한 지 얼마 안 된 종목이 있어 일부 칸이 비어 있습니다 ({_days}). "
            f"20일 수익률·20일선·52주 고가 대비는 {j4data.MIN_HISTORY_BARS}거래일이 "
            "쌓여야 나옵니다. 당일 등락률·현재가·차트는 그대로 맞습니다.\n\n"
            "빈 항목은 점수에서 0점으로 잡히므로, 이 종목의 조건점수를 다른 종목과 "
            "나란히 비교하지 마세요."
        )
    st.markdown(
        f"<div class='j4-section-title'><span class='j4-theme-badge'>{selected_theme}</span> 테마 종목 1–6위</div>",
        unsafe_allow_html=True,
    )
    st.caption("거래대금 상위 종목만 심사합니다. 표에서 종목 이름을 누르거나 아래 ‘상세 종목 선택’에서 고르면 상세가 그 종목으로 바뀝니다.")
    stock_key = f"j4_stock_choice_{selected_theme}"
    # 표의 종목 이름을 눌러도 상세가 바뀌어야 한다(2026-07-29 지시). 눌림목 표는
    # 눌리는데 이 표만 안 눌려 고장으로 보였다. 라디오는 그대로 둔다.
    clicked_code = _render_leader_table(leaders, st.session_state.get(stock_key))
    if clicked_code and clicked_code != st.session_state.get(stock_key):
        st.session_state[stock_key] = clicked_code
        st.rerun()

    _render_leader_comparison(leaders)

    # 위 상세는 **테마 종목만** 쓴다. 눌림목에서 고른 종목은 아래 제 자리에 따로
    # 그린다 — 예전에는 여기에 끼워 넣어 눌림목을 누르면 위 상세까지 통째로
    # 바뀌었다(2026-07-29 사용자 지시: 위·아래를 따로 보게 해 달라).
    #
    # 표에 1~6위를 보여주면서 상세는 1~3위만 고를 수 있었다. 4~6위를 눌러도
    # 아무 일이 없어 고장으로 보였다(2026-07-29 지적). 표에 나온 여섯 개를
    # 그대로 고를 수 있게 한다.
    top_candidates = leaders[:6]
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

    # ① 테마 종목 상세 — 눌림목 위에 둔다.
    _render_stock_detail(theme_row, selected_leader, market, top_candidates, stock_key,
                         panel="theme")

    # 여러 테마를 가로질러 '지금 실제로 살 자리'만 모아 보여준다(2026-07-22 사용자 요청).
    _render_pullback_finder()

    # ② 눌림목에서 고른 종목 상세 — 위 ①과 서로 영향을 주지 않는다.
    _render_pullback_detail(market)

    # ③ 내가 들고 있는 종목 상세 — 이름을 쳐서 직접 찾는다.
    _render_my_stock_panel(market)


def _render_pullback_detail(market: dict) -> None:
    """눌림목 표에서 고른 종목의 상세. 위쪽 테마 종목 상세와 완전히 별개다."""
    picked_row = st.session_state.get("j4_pullback_pick_row")
    picked = st.session_state.get("j4_pullback_pick")
    if not picked_row or not picked:
        st.caption("위 눌림목 표에서 종목 이름을 누르면 여기에 그 종목 상세가 열립니다.")
        return
    leader = _pullback_as_candidate(picked_row, [])
    if leader is None:
        return
    theme_name = (picked_row.get("themes") or [picked[0]])[0]
    st.markdown(
        f"<div class='j4-section-title'>눌림목에서 고른 종목 · {leader['name']}</div>",
        unsafe_allow_html=True,
    )
    _render_stock_detail(
        {"name": theme_name}, leader, market, [leader],
        "j4_pullback_detail_choice", panel="pullback",
    )


def _render_my_stock_panel(market: dict) -> None:
    """내 종목 현재상황 — 이름을 치면 비슷한 종목이 뜨고, 고르면 상세가 열린다."""
    st.divider()
    st.markdown("<div class='j4-section-title'>내 종목 현재상황</div>", unsafe_allow_html=True)
    st.caption(
        "들고 있는 종목 이름이나 종목코드를 치면 비슷한 이름까지 찾아 줍니다. "
        "테마 목록에 없는 종목도 됩니다."
    )
    query = st.text_input(
        "종목 이름 또는 코드", key="j4_my_stock_query", placeholder="예: 삼성전자, 하이닉스, 005930"
    )
    if not str(query or "").strip():
        return

    found = j4data.search_stocks(query)
    if not found.get("ok"):
        st.error(f"종목 목록 조회 실패: {_safe_error_text(found.get('error'))}")
        return
    rows = found.get("rows") or []
    if not rows:
        st.warning(f"‘{query}’와 비슷한 종목을 못 찾았습니다. 이름 일부만 쳐 보세요.")
        return

    options = [row["code"] for row in rows]
    by_code = {row["code"]: row for row in rows}
    chosen = st.radio(
        "찾은 종목",
        options,
        format_func=lambda code: (
            f"{by_code[code]['name']} ({code})"
            + (f" · {by_code[code]['market']}" if by_code[code].get("market") else "")
        ),
        horizontal=True,
        key="j4_my_stock_pick",
    )
    with st.spinner(f"{by_code[chosen]['name']} 심사 중입니다…"):
        result = j4data.analyze_one_stock(
            chosen, by_code[chosen]["name"],
            market_score=float(market.get("score") or 0),
        )
    if not result.get("ok"):
        st.error(_safe_error_text(result.get("error")))
        return
    leader = result["row"]
    if leader.get("partial"):
        st.info(
            f"📌 상장한 지 얼마 안 돼({leader.get('bars')}거래일) 일부 칸이 비어 있습니다. "
            f"20일 수익률·20일선·52주 고가 대비는 {j4data.MIN_HISTORY_BARS}거래일이 쌓여야 나옵니다."
        )
    st.caption(
        "이 점수에는 **테마 대비 상대강도 20점이 빠져 있습니다** — 견줄 테마가 없기 때문입니다. "
        "위 테마 대장주 점수와 나란히 비교하지 마세요."
    )
    _render_stock_detail(
        {"name": "내 종목"}, leader, market, [leader],
        "j4_my_stock_detail_choice", panel="mystock",
    )


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

    조회량이 있어 버튼을 누를 때만 실행하고, 결과는 화면 세션에 유지한다.
    """
    st.markdown(
        "<div class='j4-section-title'>📉 눌림목 종목 찾기 (상승추세 중 조정)</div>",
        unsafe_allow_html=True,
    )
    # 긴 안내는 접어 둔다 — 첫 화면을 다 먹었다(2026-07-25 사용자 지시).
    with st.expander("눌림목 종목 찾기 설명 보기", expanded=False):
        st.markdown(
            "<div class='j4-pull-guide'><b>무엇을 찾나</b> — 52주 최고가를 찍은 뒤 1~30거래일 조정 중이며, "
            "2개 이상 테마에 속하고, <b>신고가 당시 종목 점수가 75점 이상</b>이었던 종목입니다. "
            "현재 점수가 낮아졌어도 신고가 당시 가격·기술 조건이 좋았다면 남깁니다.<br>"
            "<b>표 읽는 법</b> — ‘고점 대비 <span class='j4-down'>−10%</span>’는 신고가에서 10% "
            "조정됐다는 뜻이고, ‘20일선 이격 0%’에 가까울수록 20일선 부근입니다. "
            "<span class='j4-up'>+ 상승은 빨강</span> · <span class='j4-down'>− 하락은 파랑</span> "
            "(한국시장 색 규칙). 테마 순위 밖 종목도 전체 검색에 포함됩니다.<br>"
            "<b>순위는 ‘신고가 기술점수’ 순입니다 — 눌림 점수 순이 아닙니다.</b> "
            "<b>눌림 점수</b>는 지금 자리를 참고로 보는 값이며 "
            "신고가 최근성 25 + 20일선 근접 25 + 추세 20 + 조정 깊이 25 + 수급 15을 더한 "
            "<b>최대 110점</b>이라 100점을 넘을 수 있습니다(막대는 100%에서 멈춥니다).</div>",
        unsafe_allow_html=True,
        )
    run_requested = st.button(
        "눌림목 찾기 / 최신 자료로 다시 찾기", key="j4_pullback_find", width="stretch"
    )
    if run_requested:
        j4data.clear_pullback_cache()
        # 이전 검색에서 고른 종목 자료는 여기서 버린다 — 새 결과와 섞이면 옛 점수가 남는다.
        st.session_state.pop("j4_pullback_pick", None)
        st.session_state.pop("j4_pullback_pick_row", None)
        with st.spinner("전체 테마를 갱신하고 유동성 상위 50개를 확인하는 중입니다…"):
            found = j4data.find_pullback_stocks()
        st.session_state["j4_pullback_result"] = found
        # 조회하자마자 1순위 종목 상세가 아래에 펼쳐지게 한다 — 누르지 않아도 된다
        # (2026-07-24 사용자 지시). 위젯이 만들어지기 전에 반영해야 하므로 rerun한다.
        # 1순위 종목을 아래 눌림목 상세에 바로 펼친다. 테마 목록과 테마 선택은
        # 더 이상 건드리지 않는다 — 눌림목 상세가 제 자리를 갖게 됐기 때문이다
        # (2026-07-29: 위 테마 상세와 아래 눌림목 상세를 따로 본다).
        top_row = (found.get("rows") or [None])[0] if found.get("ok") else None
        if top_row:
            top_themes = top_row.get("themes") or []
            st.session_state["j4_pullback_pick"] = (
                (top_themes[0] if top_themes else ""), top_row["code"]
            )
            st.session_state["j4_pullback_pick_row"] = top_row
            st.rerun()

    result = st.session_state.get("j4_pullback_result")
    if result is None:
        st.info("위 버튼을 누르면 조회합니다. 페이지를 여는 것만으로는 전수 검색하지 않습니다.")
        return
    if not result.get("ok"):
        st.error(f"눌림목 조회 실패: {_safe_error_text(result.get('error'))}")
        return
    rows = result.get("rows") or []
    window = result.get("window") or (1, 20)
    st.markdown(
        "<div class='j4-pull-stats'>"
        f"전체 <b>{result.get('universe_count', 0):,}개</b> → "
        f"2개 이상 테마 <b>{result.get('multi_theme_count', 0):,}개</b> → "
        f"오늘 거래대금 또는 전일거래량 환산 200억 이상 <b>{result.get('liquid_count', 0):,}개</b> → "
        f"유동성 상위 <b>{result.get('scanned_count', 0):,}개</b> 일봉 심사 → "
        f"신고가 {window[0]}~{window[1]}일 전 <b>{result.get('screened_count', 0):,}개</b> → "
        f"수급 확인 <b>{result.get('flow_checked_count', 0):,}개</b> → "
        f"최종 75점 이상 <b class='j4-green'>{len(rows):,}개</b></div>",
        unsafe_allow_html=True,
    )
    if not rows:
        st.info("지금 조건에 맞는 눌림목 종목이 없습니다. 조건을 낮추지 않고 그대로 둡니다.")
        return

    # 연속 수급 필터 — 켜고 끄며 비교하려고 버튼으로 뒀다(2026-07-25 사용자 요청).
    # 걸러내는 것뿐이고 점수·순위·계산은 하나도 바꾸지 않는다. 종목이 다 사라지면
    # 끄라고 알려 준다 — 조건을 몰래 낮추지 않는다.
    only_both = st.checkbox(
        "외국인·기관 동반 순매수 3일 이상(5일 중)만 보기",
        key="j4_pullback_only_streak",
        help="이미 2개 이상 테마·정배열·눌림목을 통과한 목록에서, 최근 5거래일 중 "
             "외국인과 기관이 '둘 다' 순매수한 날이 3일 이상이고 5일 누적 금액도 "
             "플러스인 종목만 남깁니다. 날짜 수만 보면 '3일 조금 사고 이틀에 크게 판' "
             "종목이 통과하므로 금액 조건을 함께 겁니다. 끄면 전체가 다시 보입니다.",
    )
    if only_both:
        kept = []
        for row in rows:
            flow = row.get("flow") or {}
            if not flow.get("ok"):
                continue                       # 못 가져온 값을 0으로 치지 않는다
            if int(flow.get("both_buy_days5") or 0) < 3:
                continue
            if float(flow.get("net5_amount") or 0) <= 0:
                continue
            kept.append(row)
        st.caption(f"동반 3일 이상 · 5일 누적 플러스: {len(kept)}개 / 전체 {len(rows)}개")
        if not kept:
            st.info("조건에 맞는 종목이 없습니다. 위 선택을 끄면 전체가 보입니다.")
            return
        rows = kept

    widths = [0.55, 2.0, 1.4, 1.1, 1.6, 1.15, 1.05, 0.8, 1.7, 2.0, 1.5, 1.2, 1.1]
    # 코드 칸은 뺐다 — 태블릿에서 수급·동반 칸이 서로 겹쳤다(2026-07-25 사용자 지적).
    # 종목코드는 종목을 누르면 나오는 상세에 그대로 있다.
    titles = ["순위", "종목", "눌림 점수", "신고가", "당일주가", "고점 대비", "20일선 이격",
              "테마수", "수급(대금%)", "동반(최근 → 5일 전)", "동반(매수/매도/20일)", "신고가 기술점수", "지금 종합점수"]
    # 좁은 화면에서는 칸을 쥐어짜 글자를 자르는 대신 표를 옆으로 밀어서 본다
    # (2026-07-25 사용자 지시). 머리글과 줄이 같이 밀려야 하므로 한 상자에 담는다.
    table_box = st.container(key="j4_pullback_table")
    for column, title in zip(table_box.columns(widths), titles):
        column.markdown(f"<div class='j4-th-head'>{title}</div>", unsafe_allow_html=True)

    for index, row in enumerate(rows):
        quality, flow = row["pullback"], row.get("flow") or {}
        cols = table_box.columns(widths)
        cols[0].markdown(f"<div class='j4-td'>{row['pullback_rank']}</div>", unsafe_allow_html=True)
        # 종목을 누르면 **바로 아래** 눌림목 상세만 그 종목으로 바뀐다.
        # 위쪽 테마 선택과 테마 종목 상세는 건드리지 않는다(2026-07-29 지시:
        # 위·아래가 서로 영향을 주지 않게 따로 볼 것).
        if cols[1].button(row["name"], key=f"j4pbf_{index:02d}", width="stretch"):
            themes = row.get("themes") or []
            st.session_state["j4_pullback_pick"] = (
                (themes[0] if themes else ""), row["code"]
            )
            st.session_state["j4_pullback_pick_row"] = row
            st.rerun()
        score = float(quality["score"])
        cols[2].markdown(
            "<div class='j4-td'><div class='j4-barwrap'><div class='j4-bar'>"
            f"<div class='j4-bar-fill j4-bar-green' style='width:{min(score, 100):.0f}%'></div></div>"
            f"<span class='j4-bar-num'>{score:.1f}</span></div></div>", unsafe_allow_html=True)
        cols[3].markdown(
            f"<div class='j4-td' style='color:#44f0a1; font-weight:700'>"
            f"{quality.get('high52_days_ago')}일 전</div>", unsafe_allow_html=True)
        # 당일주가 — 신고가와 고점 대비 사이에 지금 가격과 등락을 진하게 넣는다
        # (2026-07-24 사용자 지시). 한국시장 색 규칙(+빨강 −파랑)을 그대로 쓴다.
        current_price = row["metrics"].get("current")
        change_pct = row["metrics"].get("change_pct")
        # 가격과 등락을 두 줄로 쌓는다 — 한 줄이면 좁은 화면(태블릿)에서 폭이 넘쳐
        # 옆 칸 값과 겹쳤다(2026-07-25). 값은 그대로, 배치만 바꾼다.
        cols[4].markdown(
            f"<div class='j4-td' style='font-weight:800; color:#e6e6e6'>"
            f"<span style='display:inline-flex; flex-direction:column; align-items:center; line-height:1.12'>"
            f"<span>{_won(current_price)}</span>"
            f"<span style='color:{_sign_color(change_pct)}; font-weight:800; font-size:.82rem'>"
            f"{_pct(change_pct)}</span></span></div>", unsafe_allow_html=True)
        cols[5].markdown(
            f"<div class='j4-td' style='color:{_sign_color(quality['from_high_pct'])}; font-weight:800'>"
            f"{_pct(quality['from_high_pct'])}</div>", unsafe_allow_html=True)
        gap = quality["gap_pct"]
        gap_color = _sign_color(gap)
        cols[6].markdown(
            f"<div class='j4-td' style='color:{gap_color}; font-weight:800'>{gap:+.2f}%</div>",
            unsafe_allow_html=True)
        cols[7].markdown(
            f"<div class='j4-td' style='color:#ffb020; font-weight:700'>{len(row.get('themes') or [])}</div>",
            unsafe_allow_html=True)
        cols[8].markdown(
            f"<div class='j4-td'>{_flow_ratio_cell(flow)}</div>", unsafe_allow_html=True)
        # 동반 수급 — 외국인·기관이 '둘 다' 순매수한 날. 왼쪽이 가장 최근일이다.
        cols[9].markdown(f"<div class='j4-td'>{_partner5_cell(flow)}</div>", unsafe_allow_html=True)
        cols[10].markdown(f"<div class='j4-td'>{_partner20_cell(flow)}</div>", unsafe_allow_html=True)
        peak = row.get("peak_score")
        cols[11].markdown(
            f"<div class='j4-td' style='color:#44f0a1; font-weight:800'>"
            f"{f'{float(peak):.1f}' if peak is not None else '—'}</div>", unsafe_allow_html=True)
        cols[12].markdown(
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
    _flow_latest = next(
        ((row.get("flow") or {}).get("latest_date") for row in rows
         if (row.get("flow") or {}).get("latest_date")), None
    )
    with st.expander("표 읽는 법 보기", expanded=False):
        st.caption(
        (f"수급 기준일 **{_flow_latest}** · 그날부터 거꾸로 센 거래일입니다. " if _flow_latest else "")
        + "동반(5일) 동그라미는 **왼쪽이 가장 최근 거래일**입니다 — 빨강은 외국인·기관이 "
            "둘 다 순매수한 날, 파랑은 둘 다 순매도한 날, 흰색은 한쪽만 움직였거나 서로 "
            "엇갈린 날, 빈 회색은 둘 다 보합인 날입니다. "
            "수급 칸은 5일 순매수 금액이 그 기간 거래대금의 몇 %인지이고, "
            "동반(매수/매도/20일)은 20거래일 중 동반매수·동반매도 일수입니다."
        )
    st.caption(
        "**‘신고가 기술점수’가 75점 이상인지가 판정 기준입니다** — 종목 일봉과 KOSPI 일봉을 "
        "신고가 날짜까지 함께 잘라 당시 상대강도·신고가 위치·추세·유동성·변동성을 다시 계산합니다. "
        "과거 외국인·기관 수급은 복원할 수 없어 현재 수급을 섞지 않고, 가격·기술 80점을 "
        "100점으로 환산합니다. ‘지금 종합점수’에만 현재 외국인·기관 수급이 포함됩니다. "
        "종목 이름을 누르면 **바로 아래**에 그 종목 상세가 열립니다 — 위쪽 테마 종목 상세는 "
        "그대로 남아 둘을 나란히 볼 수 있습니다."
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
    st.markdown(
        mobile_ui.page_css(
            # 폰 머리글을 숨기던 규칙은 뺐다 — 세로로 쌓던 시절 규칙이라, 옆으로
            # 밀어 보는 지금은 '종목·눌림 점수·신고가…'가 안 보였다(2026-07-25 지적).
            # 두 표 모두 세로로 쌓지 않고 옆으로 밀어 보므로 칸 규칙도 두지 않는다.
        ),
        unsafe_allow_html=True,
    )
    # 최상단 오른쪽에 '이 테마 기법에 대한 설명'을 둔다(2026-07-29 사용자 지시).
    method_help.render(st, "KR")
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
    section = st.radio(
        "자비스4 보기",
        ["테마·종목", "매수 기록 현황", "판정 기준"],
        horizontal=True,
        label_visibility="collapsed",
        key="j4_section",
    )
    if section == "테마·종목":
        _render_radar_tab(market)
    elif section == "매수 기록 현황":
        _render_records_tab()
    else:
        _render_method_tab()


main()
