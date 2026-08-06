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
MODULE_REVISION = 2026080640

BUTTON_LABEL = "📘 이 테마 기법에 대한 설명"
CLOSE_HINT = "닫으려면 위 ‘📘 이 테마 기법에 대한 설명’ 단추를 다시 누르십시오."

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
언제 사고파나 — 신호가 난 날 <b>종가를 확인하고 다음 거래일 시가</b>에 사서 정해진
거래일 뒤 <b>종가</b>에 팝니다.
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
<div>평소에는 <b>신고가 뒤 1~3일에 10~15% 눌린 종목</b>을 사서 <b>6개월</b>.</div>
<div>나스닥이 <b>6~12% 빠졌을 때</b>가 가장 자주 오고(7개월에 한 번) 가장 좋았습니다.</div>
<div>매수는 항상 <b>종가 확인 후 다음 거래일 시가</b>에 합니다.</div>
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
<div class="mh-note-h">※ 검증 안내</div>
규칙은 미국장 설명서의 것을 쓰되 <b>숫자는 한국 자료로 직접 쟀습니다</b> — 대형주 197종목의
<b>2014-05 ~ 2026-07(12년)</b> 일봉, 다음 거래일 시가 매수·정해진 날 종가 매도.
<b>지금 살아남은 종목</b>만 봤기에 성적 옆에 늘 ‘아무 날이나 샀으면’을 붙입니다 —
그 치우침이 양쪽에 똑같이 걸려 상쇄되므로 <u>그 차이</u>로만 값을 했는지 알 수 있습니다.
</div>
<div class="mh-h2"><span class="mh-no">1</span><span>상승장 (<u>신고가 눌림매수</u>)</span></div>
<div class="mh-box mh-buy-box">
<div class="mh-box-h">▸ 매수</div>
<div class="mh-step">52주 <b>신고가 돌파</b></div>
<div class="mh-arrow">▼</div>
<div class="mh-step"><b>3~5거래일</b> 기다림</div>
<div class="mh-arrow">▼</div>
<div class="mh-step">그 고점에서 <b>4~6% 하락한 날</b> 종가 확인</div>
<div class="mh-arrow">▼</div>
<div class="mh-step mh-go">다음 거래일 <u>시가 매수</u></div>
</div>
<div class="mh-box mh-sell-box">
<div class="mh-box-h">▸ 매도</div>
<div class="mh-step"><b>120거래일</b> 보유 후 매도</div>
<div class="mh-sub">※ 약 6개월</div>
</div>
<div class="mh-box mh-warn-box">
<div class="mh-box-h">⚠ 주의</div>
<ul class="mh-list">
<li>신고가 <b>당일에는 사지 않습니다.</b></li>
<li>4~6% 눌리지 않고 올라가면 <b>추격 매수하지 않습니다.</b></li>
</ul>
</div>
<div class="mh-box mh-data-box">
<div class="mh-box-h">▸ 한국에서 재 본 성적</div>
<div class="mh-kv"><span class="mh-k">이 규칙</span><span class="mh-v mh-pos">승률 56.3%(1,816건) · 가운데 값 +4.3%</span></div>
<div class="mh-kv"><span class="mh-k">아무 날이나 샀으면</span><span class="mh-v">승률 53.6% · 가운데 값 +2.1%</span></div>
<div class="mh-kv"><span class="mh-k">기준선보다 나았던 해</span><span class="mh-v mh-neg">12년 중 7년</span></div>
<div class="mh-sub">조금 나았지만 해마다 뒤집힙니다.</div>
</div>
<div class="mh-h2"><span class="mh-no">2</span><span>급락 후 반등장 (<u>낙폭종목</u>)</span></div>
<div class="mh-box mh-buy-box">
<div class="mh-box-h">▸ 매수</div>
<div class="mh-step">시장 <b>급락</b> 뒤 코스피 <b>종가 반등</b> 확인</div>
<div class="mh-arrow">▼</div>
<div class="mh-step">52주 고점 대비 <b>낙폭</b> 확인</div>
<div class="mh-arrow">▼</div>
<div class="mh-step mh-go">다음 거래일 <u>시가 매수</u></div>
</div>
<div class="mh-box mh-data-box">
<div class="mh-box-h">▸ 고점 대비 -40~-50% → 20거래일 보유</div>
<div class="mh-kv"><span class="mh-k">이 규칙</span><span class="mh-v mh-pos">승률 68.6%(175건) · 가운데 값 +7.5%</span></div>
<div class="mh-kv"><span class="mh-k">그날 아무 종목이나 샀으면</span><span class="mh-v">승률 59.0% · 가운데 값 +2.5%</span></div>
<div class="mh-sub">두 갈래 중 이쪽이 값을 했습니다.</div>
</div>
<div class="mh-box mh-warn-box">
<div class="mh-box-h">▸ 고점 대비 -30~-40% → 60거래일 보유</div>
<div class="mh-kv"><span class="mh-k">이 규칙</span><span class="mh-v">승률 66.0%(215건) · 가운데 값 +5.7%</span></div>
<div class="mh-kv"><span class="mh-k">그날 아무 종목이나 샀으면</span><span class="mh-v">승률 66.2% · 가운데 값 +7.1%</span></div>
<div class="mh-sub"><b>기준선보다 못했습니다</b> — 낙폭을 골라 봐야 아무 대형주나 산 것과 같았습니다.</div>
</div>
<div class="mh-box mh-warn-box">
<div class="mh-box-h">⚠ 주의</div>
<ul class="mh-list">
<li>신고가가 <b>언제 나왔는지는 보지 않습니다.</b></li>
<li>고점 대비 <b>얼마나 하락했는지만</b> 봅니다.</li>
<li>두 갈래 모두 <b>이동평균을 보지 않습니다</b> — 설명서에 없는 조건입니다.</li>
<li>코스피가 급락했다가 처음 반등한 날은 12년 동안 <b>여덟 번</b>뿐이라, 승률을 앞으로의 확률로 읽으면 안 됩니다.</li>
</ul>
</div>
<div class="mh-box mh-data-box">
<div class="mh-box-h">▸ 순위와 점수 — <u>두 갈래가 다릅니다</u> (한국 자료로 쟀습니다)</div>
<div class="mh-hold">
<div class="mh-hold-h">급락 반등장</div>
<div class="mh-kv"><span class="mh-k">같은 테마에서 함께 걸린 종목 수</span><span class="mh-v mh-pos">40점</span></div>
<div class="mh-kv"><span class="mh-k">낙폭 갈래(-40~-50%가 만점)</span><span class="mh-v">25점</span></div>
<div class="mh-kv"><span class="mh-k">거래대금이 평소 위에 며칠 연속</span><span class="mh-v">20점</span></div>
<div class="mh-kv"><span class="mh-k">사고팔기 쉬운가</span><span class="mh-v">15점</span></div>
<div class="mh-sub">테마 동반 0~1개 49번 → 4개 이상 55번. 거래대금 연속 11일 이상 61번, 단 <b>이미 오른 종목은 깎습니다</b>.</div>
</div>
<div class="mh-hold">
<div class="mh-hold-h">상승장</div>
<div class="mh-kv"><span class="mh-k">거래대금(500억 이상)</span><span class="mh-v mh-pos">30점</span></div>
<div class="mh-kv"><span class="mh-k">같은 테마에서 함께 걸린 종목 수</span><span class="mh-v mh-pos">30점</span></div>
<div class="mh-kv"><span class="mh-k">최근 60일에 얼마나 올랐나</span><span class="mh-v">25점</span></div>
<div class="mh-kv"><span class="mh-k">거래대금이 평소 위에 며칠 연속</span><span class="mh-v">15점</span></div>
<div class="mh-sub">거래대금 500억 이상 100번 중 69~72번(미만 55번). 테마 동반 혼자 55번 → 2개 70번. 60일 상승폭 40% 넘으면 61번. 거래대금 연속 11일 이상 63번 — <b>미국에서는 거꾸로였습니다.</b></div>
</div>
</div>
<div class="mh-box mh-warn-box">
<div class="mh-box-h">⚠ 외국인+기관 동반은 점수에 넣지 않습니다</div>
<div class="mh-step">12년치로 재 보니 <b>거꾸로였습니다.</b> 둘이 같이 산 날이 <u>많을수록</u> 나빴습니다 — 100번 중 안 산 종목 52번, 닷새 다 산 종목 46번.</div>
<div class="mh-sub">표에는 보여 주되 순위·점수에서는 뺐습니다. docs/KR_RULE_BACKTEST.md</div>
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


def _close_button(st, market: str) -> None:
    """설명 창 맨 아래 '창닫기' 단추 (2026-08-06 사용자 지시).

    오른쪽 아래에 두되 화면 끝에 딱 붙이지는 않는다(사용자 지시 "너무 오른쪽 말고").
    그래서 3:1로 나눈 오른쪽 칸에 놓는다.

    **예전에는 안 통했다** — 2026-07-30에 눌러도 창이 열린 채 남았다. 스트림릿
    판이 올라가며 동작이 바뀌었을 수 있어 다시 넣는다. 눌러도 안 닫히면 이 단추를
    빼고 안내문(CLOSE_HINT)으로 되돌린다.
    """
    st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)
    left, right = st.columns([3, 1.15])
    with right:
        st.button("✕ 창닫기", key=f"jarvis_method_help_close_{market}",
                  width="stretch")
    with left:
        st.caption(CLOSE_HINT)


def render(st, market: str) -> None:
    """최상단 오른쪽에 설명 단추를 놓는다. market은 'US' 또는 'KR'."""
    st.markdown(BUTTON_CSS, unsafe_allow_html=True)
    box = st.container(key="jarvis_method_help")
    with box:
        with st.popover(BUTTON_LABEL):
            # 닫는 방법은 맨 아래 '창닫기' 단추에 있다(2026-08-06) — 위에도 적으면
            # 같은 말이 두 번이라 글만 길어진다.
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
