"""‘이 테마 기법에 대한 설명’ 단추와 그 내용.

자비스3(미국)·자비스4(한국)가 같이 쓴다. 단추와 옷(CSS)은 공용이고, 글은 시장마다
따로다(US_TEXT · KR_TEXT). 한쪽을 고쳐도 다른 쪽은 그대로여야 한다 — 두 시장은
서로 다른 자료로 잰 것이라 숫자를 옮겨 적으면 화면이 거짓말을 한다.

**숫자는 어디서 왔나**
  * 미국(US_TEXT) — 2026-08-01에 사용자가 준 '미국장 눌림목 매매 설명서'의 검증값.
    미국 대형주 200개로 잰 것이며, 그대로 옮겨 적었다.
  * 한국(KR_TEXT) — 2026-07-29에 실제로 잰 값. 코스피 5,253거래일(2005-03 ~ 2026-06)
    일봉으로, 그날까지의 자료로만 신호를 만들고 20일 뒤 종가로 채점했다.
    부트스트랩 1,500회로 우연인지도 확인했다.
    한국은 아직 미국식(눌림목 매매) 검증을 하지 않았다.

숫자를 고칠 일이 생기면 반드시 다시 재고 나서 고친다. 지어내지 않는다.
"""

from __future__ import annotations

# 계산 결과나 문구를 바꾸면 이 숫자를 올리고, 페이지의 요구 리비전도 같이 올린다.
MODULE_REVISION = 2026080950

BUTTON_LABEL = "📘 이 테마 기법에 대한 설명"

# 설명 단추 줄 **맨 왼쪽**에 두는 '건너가기' 단추 (2026-08-09 상하님 지시).
# 미국테마에서는 한국테마로, 한국테마에서는 미국테마로 간다. 폰·태블릿에서는
# 사이드바를 펴야만 화면을 옮길 수 있어 한 번에 못 갔다.
#
# **st.switch_page가 아니라 st.page_link(진짜 링크)를 쓴다.** 실측(2026-08-09):
# switch_page는 브라우저 기록에 같은 주소를 하나 더 쌓아서, 폰 뒤로가기를 눌러도
# 같은 화면이 한 번 더 나온다. 링크는 기록을 하나만 쌓아 뒤로가기가 바로 앞
# 화면으로 간다.
# 글자는 '지금 여기'가 아니라 '누르면 저기로 간다'라고 읽혀야 한다
# (2026-08-09 상하님 지적 — 미국테마 맨 위에 '한국테마'라고만 있으니 지금 화면이
# 한국테마인 줄 알았다). 그래서 '~로 가려면 클릭'까지 적는다.
#
# **깃발 이모지는 쓰지 않는다.** 윈도우에는 나라 깃발 글꼴이 아예 없어서 크롬이
# 깃발 대신 'US'·'KR' 두 글자를 그대로 찍는다(2026-08-09 상하님 노트북 캡처로 확인 —
# 'US 미국테마'로 보였다). 폰(안드로이드)에서는 깃발이 보이므로 기기마다 달라진다.
# 지구본은 윈도우·안드로이드·아이폰 어디서나 그림으로 나온다 — 🌎는 아메리카,
# 🌏는 아시아 쪽이 보이는 지구본이라 뜻도 맞는다.
CROSS_PAGES = {
    "US": ("pages/3_자비스4.py", "🌏 한국테마로 가려면 클릭"),
    "KR": ("pages/2_자비스3.py", "🌎 미국테마로 가려면 클릭"),
}
CLOSE_HINT = "다 읽으셨으면 오른쪽 ‘✕ 창닫기’를 누르십시오. 위 단추를 다시 눌러도 닫힙니다."

# 단추는 눌림목 찾기 단추와 같은 옷을 입힌다(밝은 스카이 블루 바탕·주황 글씨).
# 다만 좌우로 늘리지 않고 글자 크기만큼만 차지하게 두고, 오른쪽 끝에 붙인다.
BUTTON_CSS = """
<style>
/* 오른쪽 끝으로 붙이기.
   스트림릿 컨테이너는 세로 방향 flex라 justify-content는 '세로'에 걸리고,
   align-items는 스트림릿이 start로 못박아 둬서 덮어써지지 않는다(2026-07-29 실측).
   그래서 자식에 margin-left:auto를 줘 밀어낸다 — 이건 정렬 규칙을 안 타고 확실히 먹는다. */
.st-key-jarvis_method_help { margin: .1rem 0 .35rem; }
.st-key-jarvis_method_help > div { margin-left: auto !important; width: auto !important; }
.st-key-jarvis_method_help [data-testid="stPopover"] { width: auto !important; }
/* ── 맨 왼쪽 '건너가기' 단추 (2026-08-09) ─────────────────────────────
   진짜 링크(st.page_link)라서 뒤로가기가 바로 앞 화면으로 간다. 옆 설명 단추와
   같은 크기·같은 모서리로 두되, 색만 갈라 두 단추가 하는 일이 다름을 보인다. */
/* 두 단추는 **글자 크기만큼만** 차지한다. 스트림릿 기본값(flex:1 1 0)으로 두면
   폰(375px)에서 칸이 반반으로 쪼개져 설명 단추 글자가 칸 밖으로 40px 삐져나갔다
   (2026-08-09 실측). 자리가 모자라면 줄을 바꿔 아래로 내려간다 — 그러면 폰에서는
   왼쪽 건너가기 단추 아래에 설명 단추가 오른쪽 끝으로 붙는다(예전 자리 그대로). */
.st-key-jarvis_method_help_row { align-items: center; flex-wrap: wrap; }
.st-key-jarvis_method_help_row > div { flex: 0 0 auto !important; width: auto !important; }
/* 설명 단추는 오른쪽 끝에 붙인다. 스트림릿이 가로 칸의 자식마다 껍데기 div를 하나
   더 씌우기 때문에(2026-08-09 실측) 안쪽이 아니라 **그 껍데기**를 밀어야 한다. */
.st-key-jarvis_method_help_row > div:last-child { margin-left: auto !important; }
.st-key-jarvis_cross_market { margin: .1rem 0 .35rem; }
.st-key-jarvis_cross_market a[data-testid="stPageLink-NavLink"] {
    background: #e9dcff !important;
    border: 1px solid #c6a9f5 !important;
    border-radius: .5rem !important;
    padding: .35rem .9rem !important;
    text-decoration: none !important;
    transition: transform .12s ease-out, filter .12s ease-out,
                background .12s ease-out, border-color .12s ease-out !important;
}
.st-key-jarvis_cross_market a[data-testid="stPageLink-NavLink"]:hover {
    background: #dcc7ff !important;
    border-color: #a06bff !important;
    transform: translateY(-2px) !important;
}
.st-key-jarvis_cross_market a[data-testid="stPageLink-NavLink"] span,
.st-key-jarvis_cross_market a[data-testid="stPageLink-NavLink"] p {
    color: #4a2a86 !important;
    font-size: .95rem !important;
    font-weight: 800 !important;
    margin: 0 !important;
    white-space: nowrap !important;
}
/* 앞의 그림만 조금 더 크게(2026-08-09 상하님 지시). 글자 전체를 키우면 단추가
   길어져 폰에서 줄이 바뀌므로, 맨 앞 한 글자(지구본)만 키운다.
   안 먹는 브라우저에서는 그냥 지금 크기로 보일 뿐 깨지지 않는다. */
.st-key-jarvis_cross_market a[data-testid="stPageLink-NavLink"] p::first-letter {
    font-size: 1.5em;
    line-height: 1;
}
div[class*="st-key-jarvis_method_help"] button {
    background: #cfe9ff !important;
    border: 1px solid #8ec9f5 !important;
    border-radius: .5rem !important;
    padding: .35rem .9rem !important;
    min-height: 0 !important;
    width: auto !important;
    /* 손을 올리면 살짝 뜬다(2026-08-06 사용자 지시). 이 단추는 팝오버라
       페이지 쪽 '.stButton button' 규칙에 안 걸려 여기서 직접 준다. */
    transition: transform .12s ease-out, filter .12s ease-out,
                background .12s ease-out, border-color .12s ease-out !important;
}
div[class*="st-key-jarvis_method_help"] button:hover {
    background: #b9dfff !important;
    border-color: #6db6ee !important;
    transform: translateY(-2px) !important;
    filter: brightness(1.05) !important;
}
div[class*="st-key-jarvis_method_help"] button:active {
    transform: translateY(0) scale(.985) !important;
}
/* 창이 '팍' 뜨지 않고 **위에서 아래로 스르륵** 열리게 한다(2026-08-06 사용자 지시).
   0.22초 — 더 길면 글을 읽으려는데 기다리는 느낌이 난다. */
/* 위에서 아래로 커튼처럼 펼친다. transform을 안 써야 창이 안 튄다(위 설명 참고). */
@keyframes mh-drop {
    from { opacity: .35; clip-path: inset(0 0 100% 0); }
    to   { opacity: 1; clip-path: inset(0 0 0 0); }
}
div[class*="st-key-jarvis_method_help"] button p {
    color: #c15f3c !important;
    font-size: .95rem !important;
    font-weight: 800 !important;
    margin: 0 !important;
    white-space: nowrap !important;
}
/* 폰 전용 규칙은 여기 두지 않는다 — CLAUDE.md 12번 규칙에 따라 mobile_ui.py의
   폰 묶음 안에만 둔다. 밖으로 새면 태블릿·PC까지 바뀐다.
   (이 주석에 폰 미디어쿼리 문자열을 그대로 쓰면 '폰 규칙 묶음은 하나여야 한다'는
   테스트가 이 주석까지 세어 버린다 — 2026-07-29 실제로 걸렸다.) */

/* ── 화면 맨 위 빈 자리를 줄인다(2026-07-30 사용자 지시) ──────────────────
   제목을 뺐는데 그 자리가 그대로 비어 있었다. 실측(폰 412px) — 스트림릿 기본
   위 여백이 96px인데 도구막대(Stop·Fork·GitHub·⋮)는 60px밖에 안 된다.
   그래서 본문이 도구막대보다 한참 아래에서 시작했다.
   도구막대만 피하면 되므로 64px로 줄인다 — 도구막대는 그대로 눌러
   화면을 어둡게 바꿀 수 있어야 하므로 그 위로는 올리지 않는다.
   폰·태블릿·PC 모두 같은 문제라 폰 묶음이 아니라 여기 둔다(규칙 12는 폰 전용
   규칙에 대한 것이고, 이건 모든 화면에 걸리는 규칙이다). */
[data-testid="stMainBlockContainer"],
.block-container {
    padding-top: 4rem !important;
}

/* ── 설명 창은 본문을 따라 내려오지 않는다(2026-07-30 사용자 지시) ────────
   앞서 화면에 붙박아 뒀더니 굴릴 때마다 따라와 본문을 가려 불편하다고 했다.
   그래서 스트림릿 기본대로 단추 옆에 두고, 본문을 내리면 같이 위로 사라지게 둔다.
   내용을 두 쪽 분량으로 줄였으므로(아래 글) 단추가 화면에서 멀어질 일이 없다 —
   닫을 때는 같은 단추를 다시 누르면 된다.
   높이만 화면의 절반으로 묶어 둔다. 나머지 절반으로 실제 표를 봐야 하기 때문이다. */
[data-testid="stPopoverBody"] {
    width: min(680px, calc(100vw - 2rem)) !important;
    max-width: calc(100vw - 2rem) !important;
    max-height: 50vh !important;
    overflow-y: auto !important;
    box-shadow: 0 10px 40px rgba(0, 0, 0, .55) !important;
    /* '팍' 뜨지 않고 **위에서 아래로 스르륵** 열린다(2026-08-06 사용자 지시).
       **transform은 절대 건드리지 말 것** — 스트림릿이 팝오버 위치를 transform으로
       잡는다. 처음에 translateY를 줬더니 창이 왼쪽으로 퍽 튀었다가 제자리로
       돌아왔다(상하님 지적). 그래서 위치를 안 건드리는 clip-path로 펼친다.
       규칙을 따로 만들지 말고 **여기 안에** 둘 것: 같은 선택자로 블록을 하나 더
       만들면 'max-height 50vh가 있나' 보는 시험이 새 블록을 먼저 집어 깨진다
       (2026-08-06 실제로 걸렸다). */
    animation: mh-drop .24s ease-out;
    /* **창은 맨 위에서 열려야 한다**(2026-08-06 상하님 지적 — 열자마자 맨 아래가
       보였다). 표 그림이 늦게 뜨면서 브라우저가 아래쪽을 붙잡는 '스크롤 앵커링'
       때문이다. 꺼 두면 그림이 채워져도 보던 자리가 안 밀린다. */
    overflow-anchor: none !important;
}
[data-testid="stPopoverBody"] * { overflow-anchor: none !important; }

/* ── 폰·태블릿에서는 화면 크기에 맞춘다(2026-08-07 상하님 지시) ──────────
   기본값 680px은 노트북 기준이다. 태블릿을 **옆으로 눕히면** 세로가 짧아져
   50vh로는 서너 줄밖에 안 보인다 — 그래서 눕혔을 때는 높이를 더 준다.
   경계 1200px은 메뉴·상단줄 규칙(mobile_ui.SIDEBAR_MAX_WIDTH)과 같은 값이다.
   노트북·PC는 손대지 않는다.
   폰 전용 규칙이 아니라 태블릿까지 걸리는 규칙이라 mobile_ui.py가 아니라
   여기 둔다(CLAUDE.md 12번은 '폰 전용' 규칙에 대한 것이다). */
@media (max-width: 1200px) {
    /* 폰·태블릿은 위의 CSS 전용 블록 간격만으로도 도구막대와 충분히 떨어진다.
       390px 실측: 8px이면 첫 단추 y=88px, 도구막대 아래 44px가 남는다. */
    [data-testid="stMainBlockContainer"],
    .block-container {
        padding-top: .5rem !important;
    }
    [data-testid="stPopoverBody"] {
        width: calc(100vw - 1.2rem) !important;
        max-width: calc(100vw - 1.2rem) !important;
        max-height: 64vh !important;
    }
}
@media (max-width: 1200px) and (orientation: landscape) {
    [data-testid="stPopoverBody"] {
        max-height: 82vh !important;
    }
}

/* ── 글 색 구분(2026-07-30 사용자 지시) ──────────────────────────────
   큰 제목은 초록, 번호 항목(①②③)은 파랑, 강조는 붉은색.
   번호 항목만 파랑으로 뽑으려고 단계 제목은 h5(#####)로, 나머지 제목은
   h3(###)으로 통일했다. 이 규칙이 깨지면 색이 엉킨다.
   앱에 테마 설정 파일이 없어 화면이 보는 사람의 밝기 설정을 따라간다.
   그래서 밝은 화면·어두운 화면 두 벌을 다 둔다. */
[data-testid="stPopoverBody"] {
    --j-title: #0f7a3d;
    --j-step: #0b5ed7;
    --j-mark: #c62828;
}
@media (prefers-color-scheme: dark) {
    [data-testid="stPopoverBody"] {
        --j-title: #44f0a1;
        --j-step: #4da6ff;
        --j-mark: #ff6b6b;
    }
}
[data-testid="stPopoverBody"] h3 { color: var(--j-title) !important; }
[data-testid="stPopoverBody"] h5 { color: var(--j-step) !important; font-size: 1.02rem !important; }
/* 붉은색은 '문단과 인용문의 굵은 글씨'에만 준다.
   표와 목록의 굵은 글씨까지 붉히면 화면이 온통 붉어져 강조가 강조가 아니게 된다
   (2026-07-30 사용자 지적: "붉은색이 너무 많다"). */
[data-testid="stPopoverBody"] p > strong,
[data-testid="stPopoverBody"] blockquote strong { color: var(--j-mark) !important; }
[data-testid="stPopoverBody"] td strong,
[data-testid="stPopoverBody"] th strong,
[data-testid="stPopoverBody"] li strong { color: inherit !important; }

/* ── 미국장 눌림목 매매 설명서 전용 옷 (2026-08-01 사용자 지시) ───────────────
   "제목·중요내용을 보고 색·기호·밑줄·진하기·크기를 만들어 달라"는 요청이다.
   규칙은 하나 — 큰 제목은 초록, 단계 제목은 파랑, 매수는 초록·매도는 주황,
   숫자는 파랑 칸, 주의는 붉은색. 위 세 변수(--j-title/--j-step/--j-mark)를 그대로
   쓰고 여기서 모자란 색만 더한다. 밝은 화면·어두운 화면 두 벌을 다 둔다. */
[data-testid="stPopoverBody"] {
    --mh-line: rgba(127, 127, 127, .30);
    --mh-buy: #0f7a3d;
    --mh-sell: #b3541e;
    --mh-data: #0b5ed7;
    --mh-key: #6d28d9;
    --mh-dim: #6b7280;
    --mh-pos: #0f7a3d;
    --mh-neg: #c62828;
}
@media (prefers-color-scheme: dark) {
    [data-testid="stPopoverBody"] {
        --mh-line: rgba(255, 255, 255, .18);
        --mh-buy: #44f0a1;
        --mh-sell: #ff9d3b;
        --mh-data: #4da6ff;
        --mh-key: #c084fc;
        --mh-dim: #9aa0aa;
        --mh-pos: #44f0a1;
        --mh-neg: #ff6b6b;
    }
}
.mh-doc { line-height: 1.58; font-size: .95rem; }
.mh-h1 { font-size: 1.34rem; font-weight: 900; color: var(--j-title);
    border-bottom: 3px solid var(--j-title); padding-bottom: .28rem; margin: 0 0 .75rem; }
.mh-note { border: 1px dashed var(--mh-line); border-radius: .5rem;
    padding: .55rem .7rem; font-size: .85rem; color: var(--mh-dim); margin-bottom: .5rem; }
.mh-note-h { font-weight: 900; color: var(--mh-data); margin-bottom: .15rem; }
.mh-note b { color: var(--mh-data); font-weight: 900; }
.mh-h2 { display: flex; align-items: center; gap: .45rem; flex-wrap: wrap;
    font-size: 1.14rem; font-weight: 900; color: var(--j-step); margin: 1.15rem 0 .45rem; }
.mh-no { display: inline-flex; align-items: center; justify-content: center;
    width: 1.55rem; height: 1.55rem; border-radius: 50%; background: var(--j-step);
    color: #fff; font-size: .92rem; font-weight: 900; }
.mh-h2 u { text-decoration-thickness: 2px; text-underline-offset: 3px; }
.mh-box { border-left: 4px solid var(--mh-line); padding-left: .7rem; margin: .45rem 0 .7rem; }
.mh-box-h { font-weight: 900; font-size: 1rem; margin-bottom: .15rem; }
.mh-buy-box { border-left-color: var(--mh-buy); }
.mh-buy-box .mh-box-h { color: var(--mh-buy); }
.mh-sell-box { border-left-color: var(--mh-sell); }
.mh-sell-box .mh-box-h { color: var(--mh-sell); }
.mh-data-box { border-left-color: var(--mh-data); }
.mh-data-box .mh-box-h { color: var(--mh-data); }
.mh-warn-box { border-left-color: var(--j-mark); }
.mh-warn-box .mh-box-h { color: var(--j-mark); }
.mh-step b { font-weight: 900; color: var(--j-mark); }
.mh-arrow { color: var(--mh-dim); font-size: .78rem; line-height: 1.1; }
.mh-go { font-weight: 900; color: var(--mh-buy); }
.mh-sub { color: var(--mh-dim); font-size: .84rem; }
/* 값이 길면 줄을 바꿔 아래로 내려간다. nowrap으로 묶어 뒀더니 폰(412px)에서 줄이
   화면 밖으로 25px 삐져나갔다(2026-08-01 실측). 짧은 숫자는 어차피 안 쪼개진다. */
.mh-kv { display: flex; justify-content: space-between; gap: .5rem .8rem; align-items: baseline;
    flex-wrap: wrap; padding: .12rem 0; border-bottom: 1px dotted var(--mh-line); }
.mh-k { color: var(--mh-dim); min-width: 0; }
.mh-v { font-weight: 900; min-width: 0; overflow-wrap: anywhere; }
.mh-pos { color: var(--mh-pos); }
.mh-neg { color: var(--mh-neg); }
.mh-list { margin: .1rem 0 0; padding-left: 1.15rem; }
.mh-list li { padding: .05rem 0; }
.mh-hold { border: 1px solid var(--mh-line); border-radius: .5rem;
    padding: .45rem .6rem; margin: .45rem 0; }
.mh-hold-h { font-weight: 900; color: var(--mh-data); margin-bottom: .1rem; }
.mh-key { border: 2px solid var(--mh-key); border-radius: .6rem;
    padding: .55rem .7rem; margin-top: 1.1rem; }
.mh-key-h { font-weight: 900; color: var(--mh-key); margin-bottom: .2rem; }
.mh-key b { color: var(--mh-key); font-weight: 900; }
</style>
"""

# 2026-08-01에 두 설명서를 각자 HTML로 갈아 끼우면서, 두 화면이 나눠 쓰던
# 마크다운 꼬리말(_COMMON_TAIL)은 없앴다. 같은 글을 두 시장이 함께 쓰면 한쪽만
# 고쳐야 할 때 다른 쪽까지 바뀌어서다. 그 내용은 한국 설명서 안으로 옮겼다.

# 미국 설명은 2026-08-06에 **표 그림 두 장**으로 바꿨다(사용자 지시).
#
# 왜 그림인가 — 사용자가 직접 만든 표를 그대로 쓴다. 전에 있던 숫자
# (승률 59.7%(119건)·100.0%(12건)·92.6%(27건)·평균 +18.0%)는 표본이 119건·12건이고
# 급락 쪽은 2025년 4월 한 번을 잰 값이라, 10년으로 넓히면 유지되지 않았다.
# 다시 잰 과정과 결과는 docs/REMEASURE_20260805.md, 표 숫자는 docs/US_METHOD_TABLES.md.
#
# 그림을 바꾸려면 assets/의 같은 이름 파일을 덮어쓰면 된다. 코드는 안 고쳐도 된다.
# 다만 표 숫자가 바뀌면 docs/US_METHOD_TABLES.md도 같이 고친다.
US_IMAGES = (
    ("us_method_uptrend.png", "정상적인 상승일때"),
    ("us_method_drawdown.png", "나스닥 하락율대비 상승수익률"),
)


def _image_path(name: str):
    """assets 안의 그림 경로. 온라인에서 파일이 빠져도 화면이 죽지 않게 확인만 한다."""
    from pathlib import Path

    path = Path(__file__).resolve().parent / "assets" / name
    return path if path.exists() else None


# 줄 사이에 빈 줄을 넣지 않는다. 빈 줄이 있으면 스트림릿 마크다운이 그 사이를
# 문단으로 갈라 <p>를 끼워 넣어 칸 간격이 어긋난다.
US_TEXT = """
<div class="mh-doc">
<div class="mh-h1">미국장 눌림목 매매 설명서</div>
<div class="mh-note">
언제 사나 — 신호가 난 날 <b>종가를 확인하고 다음 거래일 시가</b>에 삽니다.<br>
언제 파나 — <b>앱이 정하지 않습니다.</b> 아래 표의 3개월·6개월·1년 성적을 보시고
<u>상하님이 정하십니다</u>(2026-08-12 결정). 손절 규칙도 없습니다.
</div>
</div>
"""

# 그림 사이·아래에 붙는 짧은 글. 표에 없는 것만 적는다.
US_MID_TEXT = """
<div class="mh-doc">
<div class="mh-box mh-warn-box">
<div class="mh-box-h">⚠ 1~2개월 만에 팔지 않습니다</div>
<div class="mh-step">10~15% 눌린 종목은 <b>한두 달은 더 밀립니다.</b> 그 구간이 가장 나빴습니다.
표에 3개월부터 있는 까닭입니다. 중간에 끊으면 가장 나쁜 자리에 걸립니다.</div>
</div>
</div>
"""

US_TAIL_TEXT = """
<div class="mh-doc">
<div class="mh-box mh-warn-box">
<div class="mh-box-h">⚠ 꼭 같이 기억할 것</div>
<ul class="mh-list">
<li>이 10년은 나스닥이 <b>해마다 20.9%씩 오른 기간</b>입니다. 앞으로도 이렇다는 뜻이 아닙니다.</li>
<li><b>손절 규칙은 없습니다.</b> 정해진 기간을 들고 있는 것이 전부입니다.</li>
<li>지금 살아 있는 회사만 봤습니다. 망한 회사는 빼고 쟀습니다.</li>
</ul>
</div>
<div class="mh-key">
<div class="mh-key-h">핵심</div>
<div>평소에는 <b>신고가 뒤 1~5일에 10~15% 눌린 종목</b>입니다 —
1년 기준 <b>27.8%</b>, 4~6% 눌린 자리는 14.7%로 <u>아무 종목이나 산 것(14.1%)과 같습니다.</u></div>
<div>나스닥이 <b>6% 아래로 빠졌을 때</b>는 <b>30~50% 빠진 종목</b>까지 봅니다 —
1년 기준 32.2%로 20~30%(26.6%)보다 낫습니다.</div>
<div>매수는 항상 <b>종가 확인 후 다음 거래일 시가</b>. <b>파는 시점은 상하님이 정하십니다.</b></div>
</div>
</div>
"""

# 한국 설명도 2026-08-01에 미국과 같은 옷(HTML·색·기호)으로 갈아입혔다.
# **내용은 지어내지 않았다** — 사용자가 준 한국 눌림목 매매 검증 원고가 아직 없어서,
# 지금까지 화면에 있던 한국 숫자(2026-07-29 실측)를 그대로 옮기고 보여주는 방식만
# 미국 설명서와 맞췄다. 한국 원고를 받으면 미국처럼 통째로 갈아 끼운다.
# 빈 줄을 넣지 않는다(미국 설명서와 같은 이유).
KR_TEXT = """
<div class="mh-doc">
<div class="mh-h1">한국장 눌림목 매매 설명서</div>
<div class="mh-note">
<div class="mh-note-h">※ 검증 안내 (2026-08-07 전면 재측정)</div>
화면이 뒤지는 <b>테마 명부 2,272종목</b>의 <b>2014-05 ~ 2026-08</b> 일봉으로 다시 쟀습니다.
<b>3년 창을 한 달씩 밀며</b> 100번 넘게 재고, 창 2·3·4년 <u>모두</u>에서 이긴 것만 점수를 줍니다.
</div>
<div class="mh-h2"><span class="mh-no">1</span><span>상승장 (<u>신고가 눌림매수</u>)</span></div>
<div class="mh-box mh-buy-box">
<div class="mh-box-h">▸ 매수</div>
<div class="mh-step">하루 평균 거래대금 <b>50억 이상</b>인 종목만</div>
<div class="mh-arrow">▼</div>
<div class="mh-step">52주 <b>신고가 돌파</b></div>
<div class="mh-arrow">▼</div>
<div class="mh-step"><b>3~10거래일</b> 기다림</div>
<div class="mh-arrow">▼</div>
<div class="mh-step">그 고점에서 <b>4~6% 하락한 날</b> 종가 확인</div>
<div class="mh-arrow">▼</div>
<div class="mh-step mh-go">다음 거래일 <u>시가 매수</u></div>
</div>
<div class="mh-box mh-sell-box">
<div class="mh-box-h">▸ 매도</div>
<div class="mh-step"><b>250거래일</b> 보유 후 매도</div>
<div class="mh-sub">※ 약 1년. 6개월(120거래일)보다 세 창 모두에서 나았습니다.</div>
</div>
<div class="mh-box mh-data-box">
<div class="mh-box-h">▸ 한국에서 재 본 성적</div>
<div class="mh-kv"><span class="mh-k">이 규칙</span><span class="mh-v mh-pos">승률 43.4%(7,410건) · 가운데 값 -6.6%</span></div>
<div class="mh-kv"><span class="mh-k">아무 종목이나 샀으면</span><span class="mh-v">승률 35.1% · 가운데 값 -14.0%</span></div>
<div class="mh-kv"><span class="mh-k">기준선보다 나았던 해</span><span class="mh-v mh-pos">11년 중 9년</span></div>
<div class="mh-kv"><span class="mh-k">기준선보다 나았던 창</span><span class="mh-v mh-pos">321개 중 321개</span></div>
</div>
<div class="mh-box mh-warn-box">
<div class="mh-box-h">⚠ 이기는 것과 버는 것은 다릅니다</div>
<div class="mh-step">가운데 값이 <b>-6.6%</b>입니다. 아무 종목이나 사면 -14.0%이니 <u>훨씬 덜 잃지만</u>
그래도 <b>절반 넘게는 잃습니다.</b> 신고가 당일에는 사지 않고, 안 눌리면 추격하지 않습니다.</div>
</div>
<div class="mh-h2"><span class="mh-no">2</span><span>급락 후 반등장 (<u>낙폭종목</u>)</span></div>
<div class="mh-box mh-buy-box">
<div class="mh-box-h">▸ 매수</div>
<div class="mh-step">코스피가 고점 대비 <b>15% 넘게</b> 빠진 국면</div>
<div class="mh-arrow">▼</div>
<div class="mh-step">그 국면에서 <b>가장 깊었던 날</b></div>
<div class="mh-arrow">▼</div>
<div class="mh-step">그날 고점 대비 <b>40~60% 빠진</b> 종목 (거래대금 50억↑)</div>
<div class="mh-arrow">▼</div>
<div class="mh-step mh-go">다음 거래일 <u>시가 매수</u> → <b>20거래일</b> 뒤 종가 매도</div>
</div>
<div class="mh-box mh-data-box">
<div class="mh-box-h">▸ 한국에서 재 본 성적</div>
<div class="mh-kv"><span class="mh-k">이 규칙</span><span class="mh-v mh-pos">승률 66.6%(3,739건) · 가운데 값 +6.1%</span></div>
<div class="mh-kv"><span class="mh-k">그날 아무 종목이나 샀으면</span><span class="mh-v">승률 62.1% · 가운데 값 +4.1%</span></div>
<div class="mh-kv"><span class="mh-k">기준선보다 나았던 해</span><span class="mh-v mh-pos">8년 중 7년</span></div>
<div class="mh-kv"><span class="mh-k">기준선보다 나았던 창</span><span class="mh-v mh-pos">306개 중 306개</span></div>
</div>
<div class="mh-box mh-warn-box">
<div class="mh-box-h">⚠ 주의</div>
<ul class="mh-list">
<li>신고가가 언제였는지도, 이동평균도 <b>보지 않습니다.</b> 고점 대비 낙폭만 봅니다.</li>
<li>이 신호는 12년 동안 <b>스물아홉 번</b> 났습니다. 사실상 스물아홉 번의 사건이라, 승률을 앞으로의 확률로 읽으면 안 됩니다.</li>
</ul>
</div>
<div class="mh-box mh-data-box">
<div class="mh-box-h">▸ 순위와 점수 — <u>두 갈래가 다릅니다</u> (2026-08-07 재측정)</div>
<div class="mh-hold">
<div class="mh-hold-h">두 갈래 모두 — 배점은 화면에서 봅니다</div>
<div class="mh-step"><b>몇 점씩 주는지는 여기 적지 않습니다.</b> 갈래 단추를 누르고
<b>‘📘 이 화면 설명 보기’</b>를 열면 그 자리에 <u>지금 실제로 쓰는 배점</u>이 나옵니다.</div>
<div class="mh-sub">여기에 숫자를 또 적어 두면 배점을 다시 잴 때 한쪽만 고쳐져 화면이 거짓말을
합니다. 2026-08-07에 실제로 그런 일이 생겨(테마 등수를 넣었는데 글은 안 고쳤습니다),
2026-08-09에 숫자를 <b>한 곳에서만 읽도록</b> 바꿨습니다.</div>
</div>
<div class="mh-hold">
<div class="mh-hold-h">그때 알게 된 것 둘</div>
<div class="mh-step"><b>테마 쪽이 종목보다 잘 들었습니다.</b> 테마 등수가 두 갈래 모두에서
가장 크거나 두 번째로 큰 값이 됐습니다.</div>
<div class="mh-step"><b>이미 반등을 시작한 종목은 사지 않습니다.</b> 급락 갈래에서 최근 11일에
5% 넘게 오른 종목은 창 306개 중 거의 전부에서 졌습니다(가장 나쁜 창 -43.7%p).</div>
</div>
</div>
<div class="mh-box mh-warn-box">
<div class="mh-box-h">⚠ 점수에서 뺀 것</div>
<div class="mh-step"><b>낙폭 갈래</b>(그물로 이미 씀) · <b>거래대금 평소 위 연속</b>(새 그물에서 안 붙음)
· <b>외국인+기관 동반</b>(거꾸로였습니다 — 같이 산 날이 많을수록 나빴습니다).</div>
<div class="mh-sub">근거: docs/KR_RULE_BACKTEST.md · research/kr_net_grid.py</div>
</div>
<div class="mh-key">
<div class="mh-key-h">핵심</div>
<div>매수는 두 갈래 모두 <b>종가 확인 후 다음 거래일 시가</b>에 한다.</div>
</div>
<div class="mh-h2"><span class="mh-no">3</span><span>눌림목 찾기 표는 <u>다른 기준</u>입니다</span></div>
<div class="mh-box mh-data-box">
<div class="mh-box-h">▸ 조건점수로 고릅니다</div>
<div class="mh-kv"><span class="mh-k">언제 사나</span><span class="mh-v">시장 50점↑ · 분야 60점↑ · 종목 70점↑</span></div>
<div class="mh-kv"><span class="mh-k">분야 면제</span><span class="mh-v">종목이 85점을 넘으면 분야를 안 봅니다</span></div>
</div>
<div class="mh-box mh-warn-box">
<div class="mh-box-h">⚠ 한국은 미국과 결론이 다릅니다</div>
<div class="mh-step">코스피 21년치로 재보니 시장 점수가 <b>미국만큼 듣지 않았습니다.</b></div>
<div class="mh-kv"><span class="mh-k">20일 안에 10% 깨질 확률(50일선 위/아래)</span><span class="mh-v mh-neg">한국 2.9% vs 3.6%</span></div>
<div class="mh-kv"><span class="mh-k">미국은</span><span class="mh-v mh-pos">1.1% vs 3.5%</span></div>
</div>
<div class="mh-box mh-buy-box">
<div class="mh-box-h">▸ 그래서 이렇게 보강했습니다</div>
<div class="mh-step"><b>외국인·기관 수급</b>을 종목 점수 100점 중 <b>20점</b>으로 넣었습니다</div>
<div class="mh-step mh-go">→ 시장 점수는 <u>참고로만</u>, 수급과 종목 점수를 무겁게</div>
</div>
<div class="mh-key">
<div class="mh-key-h">이 화면이 하는 일</div>
<div>“이걸 사라”가 아니라 <b>“지금 사면 얼마나 위험한가”</b>를 재 줍니다.</div>
</div>
<div class="mh-h2"><span class="mh-no">4</span>지금 할 일 — 테두리 색이 곧 답</div>
<div class="mh-box mh-data-box">
<div class="mh-box-h">▸ ‘매수 심사 결과’ 칸 맨 위 상자</div>
<div class="mh-kv"><span class="mh-k">🟩 이 기법이 말하는 진입 자리입니다</span><span class="mh-v mh-pos">기준가를 넘으면 산다</span></div>
<div class="mh-kv"><span class="mh-k">🟨 오늘은 새로 사지 않습니다</span><span class="mh-v">시장 점수가 문턱 미달</span></div>
<div class="mh-kv"><span class="mh-k">🟨 가격 자리는 맞지만 아직 아닙니다</span><span class="mh-v">모자란 것이 상자에 적힘</span></div>
<div class="mh-kv"><span class="mh-k">🟨 사지 않고 지켜봅니다</span><span class="mh-v">아직 자리가 아님</span></div>
<div class="mh-kv"><span class="mh-k">🟥 손대지 않습니다 · 후보에서 뺍니다</span><span class="mh-v mh-neg">점수가 높아도 예외 없음</span></div>
</div>
<div class="mh-box mh-warn-box">
<div class="mh-box-h">⚠ 두 갈래는 이 상자가 다릅니다</div>
<div class="mh-step">기준가도 손절가도 <b>규칙에 없어</b> <b>사는 때 · 보유 기간 · 파는 때</b>만 적습니다.</div>
</div>
<div class="mh-h2"><span class="mh-no">5</span>점수를 잘못 읽는 흔한 경우</div>
<div class="mh-box mh-warn-box">
<div class="mh-box-h">⚠ 점수는 앞일을 맞히는 숫자가 아닙니다</div>
<ul class="mh-list">
<li>90점 = “이 종목은 오른다” → <b>틀린 말</b></li>
<li>30점 = “이걸 사면 크게 깨질 수 있다” → 맞는 말</li>
</ul>
<div class="mh-sub">못 가져온 값은 지어내지 않습니다.</div>
</div>
<div class="mh-h2"><span class="mh-no">6</span>어디서 왔나 · 언제 파나</div>
<div class="mh-box mh-sell-box">
<div class="mh-step"><b>한 편의 논문에서 나온 기법이 아닙니다.</b> 논문(Moskowitz &amp; Grinblatt 1999 · George &amp; Hwang 2004)과 실무(Weinstein · O'Neil · Minervini)가 겹치는 자리입니다.</div>
<div class="mh-step"><b>파는 때는 아직 이 화면에 없습니다</b> — 눌림목 찾기 표 이야기이고, 위 두 갈래에는 보유일수가 있습니다.</div>
<div class="mh-sub">근거: docs/METHOD_ORIGINS.md · docs/KR_RULE_BACKTEST.md</div>
</div>
</div>
"""


def popover_key(market: str) -> str:
    """설명 창의 열림/닫힘을 담아 두는 자리 이름."""
    return f"jarvis_method_help_open_{str(market).upper()}"


def _shut(st, market: str) -> None:
    """'창닫기'를 누르면 설명 창을 닫는다.

    **왜 이렇게 하나 — 세 번 헤맨 자리다(2026-08-06 ~ 08-07).**
    처음에는 그냥 `st.button`만 놓고 '단추를 누르면 화면이 다시 그려지니 알아서
    닫히겠지' 하고 기대했다. 그래서 될 때도 있고 안 될 때도 있었고, 단추를 위·아래
    둘로 늘리자 **양쪽 다 안 닫혔다**(상하님 지적).

    스트림릿 1.58의 `st.popover`는 `key`와 `on_change`를 주면 **열림 상태가
    `session_state`에 담기는 정식 위젯**이 된다. 그래서 여기서 그 자리를 False로
    바꿔 준다 — 단추가 몇 개든, 위에 있든 아래 있든 확실히 닫힌다.
    """
    st.session_state[popover_key(market)] = False


def _close_button(st, market: str, *, where: str = "bottom") -> None:
    """설명 창의 '창닫기' 단추 (2026-08-06).

    화면 끝에 딱 붙이지 않는다(사용자 지시 "너무 오른쪽 말고") — 3:1로 나눈
    오른쪽 칸에 놓는다.

    위·아래 둘 다 둔다. 아래 것은 글을 다 읽고 바로 닫으라고, 위 것은 창이
    맨 위에서 열리게 붙잡아 주려고 둔다(아래에만 두었더니 열자마자 맨 아래가
    보였다 — 2026-08-06 상하님 지적).
    """
    market = str(market).upper()
    if where != "top":
        st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)
    left, right = st.columns([3, 1.15])
    with right:
        st.button("✕ 창닫기", key=f"jarvis_method_help_close_{where}_{market}",
                  width="stretch", on_click=_shut, args=(st, market))
    if where != "top":
        with left:
            st.caption(CLOSE_HINT)


def cross_link(st, market: str) -> None:
    """줄 맨 왼쪽의 '건너가기' 단추 (2026-08-09 상하님 지시).

    미국테마 ↔ 한국테마를 한 번에 오간다. 링크(st.page_link)여야 브라우저 기록이
    하나만 쌓여 폰 뒤로가기가 바로 앞 화면으로 돌아온다(위 CROSS_PAGES 설명 참고).
    """
    target = CROSS_PAGES.get(str(market).upper())
    if not target:
        return
    page, label = target
    try:
        with st.container(key="jarvis_cross_market"):
            st.page_link(page, label=label)
    except Exception:
        # 페이지 목록이 없는 자리(시험용 AppTest 등)에서는 st.page_link가
        # KeyError로 죽는다. 쿠키 로그인과 같은 원칙으로 **조용히 넘어간다** —
        # 단추 하나가 없을 뿐 화면은 그대로 돌고, 사이드바로 옮겨 갈 수 있다.
        pass


def render(st, market: str) -> None:
    """맨 왼쪽에 건너가기 단추, 오른쪽에 설명 단추를 놓는다. market은 'US' 또는 'KR'."""
    st.markdown(BUTTON_CSS, unsafe_allow_html=True)
    # 두 단추를 한 줄에 둔다. st.columns가 아니라 가로 칸을 쓰는 까닭은, 설명 창
    # 안에서 다시 st.columns(창닫기 자리)를 쓰기 때문이다 — 칸 안의 칸은 깊이
    # 제한에 걸릴 수 있다(2026-08-09 실물로 확인하고 이 방식으로 정했다).
    row = st.container(horizontal=True, key="jarvis_method_help_row")
    with row:
        cross_link(st, market)
        box = st.container(key="jarvis_method_help")
    with box:
        # key·on_change를 줘야 열림 상태가 session_state에 담긴다 — '창닫기'가
        # 그 자리를 False로 바꿔 닫는다(위 _shut 설명 참고).
        with st.popover(BUTTON_LABEL, key=popover_key(market), on_change="rerun"):
            # 맨 위 단추는 **창이 위에서 열리게 붙잡는 구실**도 한다(위 설명 참고).
            _close_button(st, market, where="top")
            if str(market).upper() != "US":
                # 한국 설명은 색·기호·밑줄을 직접 입힌 HTML 그대로다(2026-08-01).
                st.markdown(KR_TEXT, unsafe_allow_html=True)
                _close_button(st, "KR")
                return
            # 미국은 사용자가 만든 표 그림 두 장을 그대로 보여준다(2026-08-06).
            # 순서는 '정상적인 상승일때'가 먼저다(사용자 지시).
            st.markdown(US_TEXT, unsafe_allow_html=True)
            for index, (name, caption) in enumerate(US_IMAGES):
                path = _image_path(name)
                if path is None:
                    # 온라인에 그림이 안 올라갔을 때 화면이 죽지 않게 알려만 준다.
                    st.warning(f"표 그림을 찾지 못했습니다 — assets/{name}")
                    continue
                st.markdown(
                    f"<div class='mh-doc'><div class='mh-h2'>"
                    f"<span class='mh-no'>{index + 1}</span><span>{caption}</span>"
                    "</div></div>",
                    unsafe_allow_html=True,
                )
                st.image(str(path), use_container_width=True)
                if index == 0:
                    st.markdown(US_MID_TEXT, unsafe_allow_html=True)
            st.markdown(US_TAIL_TEXT, unsafe_allow_html=True)
            _close_button(st, "US")
