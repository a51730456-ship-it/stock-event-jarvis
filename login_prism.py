"""첫 화면의 프리즘과 '미국테마 · 한국테마' 두 판 (2026-08-09 상하님 지시).

무엇을 바꿨나
-------------
첫 화면에 돌던 **지구를 프리즘으로 바꿨다.** 그리고 그 아래에 큰 판 둘을 뒀다 —
왼쪽 미국테마, 오른쪽 한국테마. 판을 누르면 **비밀번호 없이 바로 들어간다.**

상하님이 보여 주신 두 홈페이지
------------------------------
* **octolane.com** — 프리즘. 코드를 직접 읽어 그대로 따랐다. 은색 띠 안에 좁은
  무지개 구간(보라 → 주홍 → 호박 → 흰보라 → 파랑)이 있고, 그것이 오른쪽에서
  왼쪽으로 쓸고 지나간다. 한 번 지나가고 몇 초 쉬는 것을 되풀이한다.
  상하님 말씀이 "**은은하게**"라서 저쪽(5초)보다 느리게 7초로 뒀다.
* **okaydev.co** — 화면이 뜰 때 그림이 **가운데에서 바깥으로 커지며 빠르게**
  퍼진다(실측: 사진들이 가운데 x≈530~640에 모여 있다가 흩어진다).
  두 판이 가운데에서 좌우로 퍼지게 한 것이 그것이다.

왜 CSS로만 만들었나
-------------------
저쪽은 WebGL(캔버스)도 쓰지만, 이 화면은 **폰에서 제일 먼저 뜨는 화면**이다.
무거운 것을 올리면 첫 화면이 늦어진다. 여기 있는 것은 전부 CSS라 그림 파일도
스크립트도 받지 않는다.

사진을 넣고 싶으면
------------------
`assets/`에 `login_us.jpg`·`login_kr.jpg`를 넣으면 자동으로 판 배경이 된다.
없으면 지금처럼 프리즘 색으로 그린다 — 코드는 안 고쳐도 된다.
"""

from __future__ import annotations

from pathlib import Path

# 화면 구성이나 문구를 바꾸면 이 숫자를 올린다(CLAUDE.md 11번 규칙).
MODULE_REVISION = 2026080940

# 판을 누르면 이 표식을 달고 그 화면으로 간다. 받는 쪽(pages/*.py)이 이것을 보고
# 비밀번호 없이 게스트로 들여보낸다. 게스트는 원래도 비밀번호 없이 들어갈 수 있으므로
# 이 표식이 새로 여는 문은 없다 — 누르는 횟수만 둘에서 하나로 준다.
GUEST_PARAM = "guest"
GUEST_VALUE = "1"

PANELS = (
    ("US", "pages/2_자비스3.py", "미국테마", "나스닥 · 테마 20 · 상승장과 급락장"),
    ("KR", "pages/3_자비스4.py", "한국테마", "코스피 · 테마 20 · 상승장과 급락장"),
)

# ── 국기 (2026-08-09 상하님 지적 "국기를 왜 지구로 바꿨냐") ────────────────
# **이모지 국기(🇺🇸·🇰🇷)를 쓰지 않는다.** 윈도우에는 나라 깃발 글꼴이 없어서
# 크롬이 깃발 대신 'US'·'KR' 두 글자를 그대로 찍는다(상하님 노트북 캡처로 확인).
# 폰·태블릿에서는 보이고 노트북에서는 안 보이니 기기마다 달라진다.
# 그래서 **그림(SVG)으로 직접 그린다** — 어느 기기에서나 똑같이 국기로 보인다.
# 글자보다 조금 크게 그린다(글자 1.5rem · 국기 1.85rem, 상하님 지시).
_FLAG_US = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 60 40'>"
    "<rect width='60' height='40' fill='#fff'/>"
    "<g fill='#b22234'>"
    "<rect width='60' height='3.08'/><rect y='6.15' width='60' height='3.08'/>"
    "<rect y='12.3' width='60' height='3.08'/><rect y='18.46' width='60' height='3.08'/>"
    "<rect y='24.6' width='60' height='3.08'/><rect y='30.77' width='60' height='3.08'/>"
    "<rect y='36.92' width='60' height='3.08'/></g>"
    "<rect width='24' height='21.5' fill='#3c3b6e'/>"
    "<g fill='#fff'>"
    "<circle cx='4' cy='4' r='1.5'/><circle cx='12' cy='4' r='1.5'/><circle cx='20' cy='4' r='1.5'/>"
    "<circle cx='8' cy='9' r='1.5'/><circle cx='16' cy='9' r='1.5'/>"
    "<circle cx='4' cy='14' r='1.5'/><circle cx='12' cy='14' r='1.5'/><circle cx='20' cy='14' r='1.5'/>"
    "<circle cx='8' cy='18.5' r='1.5'/><circle cx='16' cy='18.5' r='1.5'/></g></svg>"
)
_FLAG_KR = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 60 40'>"
    "<rect width='60' height='40' fill='#fff'/>"
    # 태극 — 위 빨강, 아래 파랑이 S자로 맞물린다.
    "<path d='M22,20 A8,8 0 0,1 38,20 A4,4 0 0,1 30,20 A4,4 0 0,0 22,20' fill='#cd2e3a'/>"
    "<path d='M22,20 A8,8 0 0,0 38,20 A4,4 0 0,0 30,20 A4,4 0 0,1 22,20' fill='#0047a0'/>"
    # 네 모서리의 괘. 작은 그림이라 막대 굵기만 살려 놓는다.
    "<g fill='#000'>"
    "<g transform='rotate(-56 10 10)'><rect x='6' y='8' width='8' height='1.4'/>"
    "<rect x='6' y='10.3' width='8' height='1.4'/><rect x='6' y='12.6' width='8' height='1.4'/></g>"
    "<g transform='rotate(56 50 10)'><rect x='46' y='8' width='8' height='1.4'/>"
    "<rect x='46' y='10.3' width='3.4' height='1.4'/><rect x='50.6' y='10.3' width='3.4' height='1.4'/>"
    "<rect x='46' y='12.6' width='8' height='1.4'/></g>"
    "<g transform='rotate(-124 10 30)'><rect x='6' y='26' width='3.4' height='1.4'/>"
    "<rect x='10.6' y='26' width='3.4' height='1.4'/><rect x='6' y='28.3' width='8' height='1.4'/>"
    "<rect x='6' y='30.6' width='3.4' height='1.4'/><rect x='10.6' y='30.6' width='3.4' height='1.4'/></g>"
    "<g transform='rotate(124 50 30)'><rect x='46' y='26' width='3.4' height='1.4'/>"
    "<rect x='50.6' y='26' width='3.4' height='1.4'/><rect x='46' y='28.3' width='3.4' height='1.4'/>"
    "<rect x='50.6' y='28.3' width='3.4' height='1.4'/><rect x='46' y='30.6' width='3.4' height='1.4'/>"
    "<rect x='50.6' y='30.6' width='3.4' height='1.4'/></g></g></svg>"
)
FLAGS = {"US": _FLAG_US, "KR": _FLAG_KR}


def flag_url(market: str) -> str:
    """국기 그림을 CSS에 바로 넣을 수 있는 주소로 바꾼다."""
    from urllib.parse import quote

    return "data:image/svg+xml," + quote(FLAGS.get(market, ""), safe="")


def _asset(name: str) -> Path | None:
    path = Path(__file__).resolve().parent / "assets" / name
    return path if path.exists() else None


# -- 판에 까는 주식 그림 (2026-08-09 상하님 지시 "대충 주식 그림 넣으면 되지") --
# 사진 파일을 받아 오지 않고 **그림도 SVG로 직접 그린다.** 첫 화면이라 무거운 것을
# 올리면 늦어지고, 남의 사진을 가져다 쓰면 출처 문제가 생긴다.
# 미국은 봉차트(캔들), 한국은 선차트+막대로 **서로 다르게** 그린다(상하님 지시).
_CHART_US = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 260'>"
    "<g stroke='#7ea6ff' stroke-width='1' opacity='.16'>"
    "<path d='M0 60H400M0 110H400M0 160H400M0 210H400'/></g>"
    "<g stroke='#9fc0ff' stroke-width='2' opacity='.55'>"
    "<path d='M40 205V150M80 195V140M120 200V125M160 175V105M200 165V95"
    "M240 140V80M280 150V70M320 120V52M360 105V38'/></g>"
    "<g fill='#4da6ff' opacity='.62'>"
    "<rect x='33' y='163' width='14' height='30'/><rect x='73' y='152' width='14' height='32'/>"
    "<rect x='113' y='140' width='14' height='48'/><rect x='153' y='120' width='14' height='42'/>"
    "<rect x='193' y='110' width='14' height='44'/><rect x='233' y='92' width='14' height='38'/>"
    "<rect x='273' y='84' width='14' height='52'/><rect x='313' y='66' width='14' height='44'/>"
    "<rect x='353' y='52' width='14' height='42'/></g>"
    "<polyline fill='none' stroke='#e6efff' stroke-width='2.4' opacity='.7'"
    " points='40,178 80,168 120,164 160,141 200,132 240,111 280,110 320,88 360,73'/>"
    "</svg>"
)
_CHART_KR = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 260'>"
    "<defs><linearGradient id='kg' x1='0' y1='0' x2='0' y2='1'>"
    "<stop offset='0' stop-color='#ffb005' stop-opacity='.42'/>"
    "<stop offset='1' stop-color='#fa3d1d' stop-opacity='0'/></linearGradient></defs>"
    "<g stroke='#ffbe6a' stroke-width='1' opacity='.15'>"
    "<path d='M0 60H400M0 110H400M0 160H400M0 210H400'/></g>"
    "<path fill='url(#kg)' d='M0,120 L50,150 L100,195 L150,215 L200,196 L250,168"
    " L300,140 L350,104 L400,86 L400,260 L0,260 Z'/>"
    "<polyline fill='none' stroke='#ffd479' stroke-width='2.6' opacity='.85'"
    " points='0,120 50,150 100,195 150,215 200,196 250,168 300,140 350,104 400,86'/>"
    "<g fill='#fa3d1d' opacity='.42'>"
    "<rect x='24' y='232' width='11' height='20'/><rect x='74' y='224' width='11' height='28'/>"
    "<rect x='124' y='214' width='11' height='38'/><rect x='174' y='222' width='11' height='30'/>"
    "<rect x='224' y='228' width='11' height='24'/><rect x='274' y='218' width='11' height='34'/>"
    "<rect x='324' y='210' width='11' height='42'/><rect x='374' y='202' width='11' height='50'/></g>"
    "</svg>"
)
CHARTS = {"US": _CHART_US, "KR": _CHART_KR}


def chart_url(market: str) -> str:
    """주식 그림을 CSS에 바로 넣을 수 있는 주소로 바꾼다."""
    from urllib.parse import quote

    return "data:image/svg+xml," + quote(CHARTS.get(market, ""), safe="")


def _panel_background(market: str) -> str:
    """판 배경. 사진이 있으면 사진, 없으면 주식 그림 + 프리즘 색으로 그린다."""
    photo = _asset("login_%s.jpg" % market.lower()) or _asset("login_%s.png" % market.lower())
    if photo is not None:
        import base64

        data = base64.b64encode(photo.read_bytes()).decode("ascii")
        kind = "png" if photo.suffix == ".png" else "jpeg"
        return ("linear-gradient(180deg, rgba(4,6,14,.30), rgba(4,6,14,.78)), "
                "url('data:image/%s;base64,%s')" % (kind, data))
    # 주식 그림은 여기 넣지 않는다 — ::before에 따로 넣어야 **그림만** 움직인다.
    if market == "US":
        # 미국은 파랑·보라 쪽. 프리즘의 차가운 절반이다.
        return ("radial-gradient(120% 90% at 22% 18%, rgba(3,88,247,.42), transparent 60%),"
                "radial-gradient(110% 80% at 82% 78%, rgba(198,121,196,.34), transparent 62%),"
                "linear-gradient(150deg, #070b18 0%, #0d1430 52%, #070a16 100%)")
    # 한국은 주홍·호박 쪽. 프리즘의 따뜻한 절반이다.
    return ("radial-gradient(120% 90% at 24% 20%, rgba(250,61,29,.34), transparent 60%),"
            "radial-gradient(110% 80% at 80% 76%, rgba(255,176,5,.32), transparent 62%),"
            "linear-gradient(150deg, #14070a 0%, #2a1108 52%, #120609 100%)")


CSS = """
<style>
/* ── 프리즘 (octolane.com 방식) ───────────────────────────────────────────
   은색 띠 안에 좁은 무지개 구간을 넣고 그 띠를 오른쪽에서 왼쪽으로 민다.
   글자에 배경을 오려 붙여(background-clip:text) 글자 자체가 프리즘이 된다.
   **은은하게**가 상하님 지시라 한 바퀴를 7초로 뒀다 — 지나가는 데 1.2초,
   나머지 5.8초는 쉰다. 저쪽 홈페이지는 5초였다. */
@keyframes jp-sweep {
    0%   { background-position: 130% 0; }
    17%  { background-position: -30% 0; }
    100% { background-position: -30% 0; }
}
.jp-title {
    font-size: clamp(1.9rem, 5.2vw, 3.4rem);
    font-weight: 800;
    letter-spacing: -.02em;
    line-height: 1.18;
    text-align: center;
    margin: .2rem 0 .5rem;
    background-image: linear-gradient(90deg,
        #cfd6e2 0%, #cfd6e2 32%,
        #c679c4 39%, #fa3d1d 44%, #ffb005 49%, #e1e1fe 54%, #0358f7 59%,
        #cfd6e2 66%, #cfd6e2 100%);
    background-size: 320% 100%;
    background-position: -30% 0;
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    color: transparent;
    animation: jp-sweep 7s ease-in-out 1s infinite;
}
.jp-sub { text-align: center; color: #9aa0aa; font-size: .96rem; margin-bottom: 1.5rem; }
.jp-sub b { color: #c9d1dc; font-weight: 800; }

/* ── 눕힌 S자 빛줄기와 그 위를 흘러가는 프리즘 ───────────────────────────
   곧은 막대였던 것을 **눕혀 놓은 S자 곡선**으로 바꿨다(2026-08-09 상하님 지시).
   상하님이 보여 주신 octolane.com도 곧은 선이 아니라 굽이치는 줄기였다.

   움직이는 방법도 저쪽과 같게 했다 — 저쪽 코드의 `beam-life`가 선을 점선으로
   만들어 그 **점선 자리를 밀어(stroke-dashoffset)** 빛이 흐르게 한다. 여기서도
   무지개 줄기를 '색 있는 한 토막 + 긴 빈칸'으로 만들고 그 토막을 곡선을 따라
   밀어 준다. 그래서 굽이를 따라 빛이 흘러간다. */
/* 줄기가 제목 글자를 가로지르지 않게 아래를 넉넉히 비운다. 처음에는 겹쳐서
   글자 위로 빛줄기가 지나갔다(2026-08-09 실측: 제목 y110~174, 줄기 y118~250). */
.jp-stage { position: relative; padding: 1.2rem 0 7.4rem; overflow: hidden; }
.jp-wave {
    position: absolute; left: -6%; right: -6%; bottom: .3rem;
    width: 112%; height: 120px; pointer-events: none;
}
.jp-wave-glow { filter: blur(16px); opacity: .5; }
.jp-wave-base { filter: blur(5px); opacity: .85; }
.jp-wave-prism {
    filter: blur(4px); opacity: 1;
    /* 색 있는 토막 320 + 빈칸 2200. 이 토막이 곡선을 따라 흘러간다. */
    stroke-dasharray: 320 2200;
    animation: jp-flow 14s linear infinite;
}
@keyframes jp-flow {
    from { stroke-dashoffset: 320; }
    to   { stroke-dashoffset: -2200; }
}

/* ── 두 판이 올라오는 모습 ────────────────────────────────────────────────
   **왼쪽이 먼저 올라오고 오른쪽이 바로 뒤따라 올라온다**(2026-08-09 상하님 지시).
   처음에는 가운데에서 좌우로 퍼지게 했는데(okaydev 방식) 그게 아니라고 하셨다.
   아래에서 위로 밀려 올라오며 살짝 커진다. 왼쪽 0.10초, 오른쪽 0.24초에 시작해
   **뒤따라오는 것이 눈에 보이게** 0.14초를 벌려 뒀다. */
@keyframes jp-burst-left {
    from { opacity: 0; transform: translateY(34px) scale(.94); }
    to   { opacity: 1; transform: none; }
}
@keyframes jp-burst-right {
    from { opacity: 0; transform: translateY(34px) scale(.94); }
    to   { opacity: 1; transform: none; }
}
/* 첫 화면의 바깥 칸이 '내용만큼만'(align-items:start)이라 판이 글자 폭으로
   쪼그라들었다(2026-08-09 실측: 601px 화면에서 판이 136px). 판 줄은 폭을 다 쓴다. */
.st-key-jp_panels { gap: 1rem !important; width: 100% !important; }
.st-key-jp_panels [data-testid="stHorizontalBlock"] { width: 100% !important; }
.st-key-jp_panels [data-testid="stColumn"] { min-width: 0 !important; }
.st-key-jp_panels a[data-testid="stPageLink-NavLink"] {
    display: flex !important;
    flex-direction: column;
    align-items: flex-start;
    justify-content: flex-end;
    min-height: 15.5rem;
    width: 100% !important;
    padding: 1.15rem 1.25rem !important;
    border-radius: 1rem !important;
    border: 1px solid rgba(255,255,255,.14) !important;
    text-decoration: none !important;
    position: relative;
    overflow: hidden;
    box-shadow: 0 10px 34px rgba(0,0,0,.45);
    transition: transform .18s ease-out, box-shadow .18s ease-out,
                border-color .18s ease-out !important;
}
.st-key-jp_panels a[data-testid="stPageLink-NavLink"]:hover {
    /* 손을 올리면 **판이 살짝 떠오른다**(2026-08-09 상하님 지시). 4px은 티가 안 나
       9px로 키우고 그림자도 같이 깊게 준다. */
    transform: translateY(-9px);
    border-color: rgba(255,255,255,.42) !important;
    box-shadow: 0 22px 54px rgba(0,0,0,.6);
}
/* 판 안의 주식 그림. 배경에 깔지 않고 따로 떼어 놓았다 — 그래야 **그림만**
   위아래로 움직일 수 있다(2026-08-09 상하님 지시 "차트가 위로 움직이는 것처럼").
   평소에는 9초에 걸쳐 아주 조금 떠올랐다 내려가고, 손을 올리면 더 크게 올라온다. */
.st-key-jp_panels a[data-testid="stPageLink-NavLink"]::before {
    content: ""; position: absolute; left: 0; right: 0; bottom: -6%;
    height: 78%;
    background-repeat: no-repeat;
    background-position: center bottom;
    background-size: 118% auto;
    opacity: .92; pointer-events: none;
    animation: jp-chart-rise 9s ease-in-out infinite alternate;
    transition: transform .25s ease-out, opacity .25s ease-out;
}
@keyframes jp-chart-rise {
    from { transform: translateY(6px); }
    to   { transform: translateY(-6px); }
}
.st-key-jp_panels a[data-testid="stPageLink-NavLink"]:hover::before {
    animation: none;
    transform: translateY(-16px) scale(1.04);
    opacity: 1;
}
/* 판 위를 프리즘 한 줄이 천천히 지나간다 — 손을 안 올려도 살아 있게 보인다. */
.st-key-jp_panels a[data-testid="stPageLink-NavLink"]::after {
    content: ""; position: absolute; left: -40%; right: -40%; top: 38%; height: 2px;
    background: linear-gradient(90deg, transparent, #e1e1fe, #ffb005, transparent);
    filter: blur(7px); opacity: .5;
    animation: jp-drift 13s ease-in-out infinite alternate;
    pointer-events: none;
}
.st-key-jp_panels a[data-testid="stPageLink-NavLink"] p,
.st-key-jp_panels a[data-testid="stPageLink-NavLink"] span {
    color: #ffffff !important;
    font-size: 1.5rem !important;
    font-weight: 800 !important;
    margin: 0 !important;
    text-shadow: 0 2px 12px rgba(0,0,0,.6);
    white-space: nowrap !important;
}
.jp-panel-note { color: #aeb6c2; font-size: .9rem; margin: .25rem 0 0; }
.jp-hint { text-align: center; color: #7f8794; font-size: .88rem; margin: .9rem 0 1.4rem; }

/* 움직임을 싫어하는 설정을 켜 둔 사람에게는 돌리지 않는다. */
@media (prefers-reduced-motion: reduce) {
    .jp-title, .jp-wave-prism, .jp-wave,
    .st-key-jp_panels a[data-testid="stPageLink-NavLink"]::before,
    .st-key-jp_panels a[data-testid="stPageLink-NavLink"]::after { animation: none !important; }
}

/* 폰에서는 두 판을 위아래로 쌓는다. 옆으로 두면 한 판이 손가락 하나 폭이 된다.
   퍼지는 방향도 위아래로 바꾼다 — 좌우로 밀면 화면 밖으로 나갔다 들어온다. */
@media (max-width: 640px) {
    /* 폰에서는 빛줄기 자리를 줄인다 — 첫 화면에서 판이 밀려 내려가면 안 된다. */
    .jp-stage { padding-bottom: 5.2rem; }
    .jp-wave { height: 86px; }
    /* 폰에서는 판을 **위아래로 쌓는다.** 옆으로 두면 한 판이 156px이 되어 글자가
       잘렸다(2026-08-09 실측: 글자가 필요한 폭 216px). 스트림릿이 이 폭에서
       칸을 저절로 쌓아 주지 않으므로 여기서 직접 세운다. */
    .st-key-jp_panels [data-testid="stHorizontalBlock"] { flex-direction: column !important; }
    .st-key-jp_panels [data-testid="stColumn"] {
        width: 100% !important; flex: 1 1 100% !important;
    }
    .st-key-jp_panels a[data-testid="stPageLink-NavLink"] { min-height: 9rem; }
    .st-key-jp_panels a[data-testid="stPageLink-NavLink"] p,
    .st-key-jp_panels a[data-testid="stPageLink-NavLink"] span { font-size: 1.3rem !important; }
    /* 폰에서도 올라오는 방향은 같다 — 위아래로 쌓이므로 그대로 위로 밀려 올라온다. */
}
</style>
"""


# 눕힌 S자 빛줄기. 같은 굽이를 세 겹으로 겹친다 —
#   ① 넓게 번지는 바탕 빛  ② 흰 줄기  ③ 그 위를 흘러가는 무지개 토막
# 곡선 하나만 고치면 셋이 같이 따라온다.
_WAVE_PATH = "M0,96 C180,34 330,18 520,58 C700,96 850,120 1010,84 C1120,60 1170,44 1200,36"

WAVE_SVG = (
    "<svg class='jp-wave' viewBox='0 0 1200 132' preserveAspectRatio='none'"
    " aria-hidden='true'>"
    "<defs>"
    "<linearGradient id='jpBeam' x1='0' y1='0' x2='1' y2='0'>"
    "<stop offset='0' stop-color='#ffffff' stop-opacity='0'/>"
    "<stop offset='.28' stop-color='#dfe6f2' stop-opacity='.85'/>"
    "<stop offset='.5' stop-color='#ffffff' stop-opacity='1'/>"
    "<stop offset='.72' stop-color='#dfe6f2' stop-opacity='.85'/>"
    "<stop offset='1' stop-color='#ffffff' stop-opacity='0'/>"
    "</linearGradient>"
    "<linearGradient id='jpPrism' x1='0' y1='0' x2='1' y2='0'>"
    "<stop offset='0' stop-color='#0358f7'/><stop offset='.28' stop-color='#e1e1fe'/>"
    "<stop offset='.52' stop-color='#ffb005'/><stop offset='.76' stop-color='#fa3d1d'/>"
    "<stop offset='1' stop-color='#c679c4'/>"
    "</linearGradient>"
    "</defs>"
    f"<path class='jp-wave-glow' d='{_WAVE_PATH}' fill='none'"
    " stroke='url(#jpBeam)' stroke-width='16' stroke-linecap='round'/>"
    f"<path class='jp-wave-base' d='{_WAVE_PATH}' fill='none'"
    " stroke='url(#jpBeam)' stroke-width='4' stroke-linecap='round'/>"
    f"<path class='jp-wave-prism' d='{_WAVE_PATH}' fill='none'"
    " stroke='url(#jpPrism)' stroke-width='5' stroke-linecap='round'/>"
    "</svg>"
)


def panel_style(index: int, market: str) -> str:
    """판 하나의 배경과 퍼지는 방향. 칸마다 달라서 따로 내보낸다."""
    burst = "jp-burst-left" if index == 0 else "jp-burst-right"
    delay = 0.10 + index * 0.14      # 왼쪽 0.10초 · 오른쪽 0.24초 (뒤따라 올라온다)
    return (
        f".st-key-jp_panel_{market} a[data-testid='stPageLink-NavLink'] {{"
        f" background-image: {_panel_background(market)} !important;"
        " background-size: cover !important; background-position: center !important;"
        f" animation: {burst} .55s cubic-bezier(.16,1,.3,1) {delay:.2f}s both;"
        "}"
        # 주식 그림은 배경이 아니라 ::before에 넣는다 — 그림만 따로 움직이게.
        f".st-key-jp_panel_{market} a[data-testid='stPageLink-NavLink']::before {{"
        f" background-image: url(\"{chart_url(market)}\");"
        "}"
        # 국기는 글자 왼쪽에 붙인다. 글자(1.5rem)보다 조금 크게 1.85rem으로.
        f".st-key-jp_panel_{market} a[data-testid='stPageLink-NavLink'] p,"
        f".st-key-jp_panel_{market} a[data-testid='stPageLink-NavLink'] span {{"
        f" background-image: url(\"{flag_url(market)}\") !important;"
        " background-repeat: no-repeat !important;"
        " background-position: left center !important;"
        " background-size: auto 1.85rem !important;"
        " padding-left: 3.3rem !important;"
        " display: inline-block !important;"
        "}"
    )


def render(st) -> None:
    """첫 화면의 프리즘 제목과 두 판. 누르면 비밀번호 없이 그 화면으로 간다."""
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(
        "<div class='jp-stage'>"
        "<div class='jp-title'>Stock Event Jarvis</div>"
        + WAVE_SVG +
        "</div>"
        "<div class='jp-sub'><b>장상하</b>의 테마 주식 기록장</div>",
        unsafe_allow_html=True,
    )
    styles = []
    # 가로 칸(st.container(horizontal=True))을 쓰면 판이 글자 폭만큼만 좁아진다
    # (2026-08-09 실측: 800px 화면에서 판이 141px). 보통 칸으로 나눈다.
    columns = st.container(key="jp_panels").columns(len(PANELS), gap="medium")
    for index, (market, page, name, note) in enumerate(PANELS):
        styles.append(panel_style(index, market))
        with columns[index]:
            box = st.container(key=f"jp_panel_{market}")
            with box:
                try:
                    # width="stretch"가 없으면 링크가 글자 폭만큼만 그려진다
                    # (2026-08-09 실측: 1280px 화면에서 판이 141px). CSS로는 안 늘어난다.
                    st.page_link(page, label=name, width="stretch",
                                 query_params={GUEST_PARAM: GUEST_VALUE})
                except Exception:
                    # 페이지 목록이 없는 자리(시험용)에서는 조용히 건너뛴다 —
                    # 아래 비밀번호 로그인은 그대로 돈다.
                    pass
            st.markdown(f"<div class='jp-panel-note'>{note}</div>", unsafe_allow_html=True)
    st.markdown("<style>" + "".join(styles) + "</style>", unsafe_allow_html=True)
    st.markdown(
        "<div class='jp-hint'>판을 누르면 비밀번호 없이 바로 들어갑니다. "
        "기록을 남기려면 아래에서 로그인하십시오.</div>",
        unsafe_allow_html=True,
    )


def wants_guest(st) -> bool:
    """주소에 게스트 표식이 달려 왔나. 이미 로그인한 사람은 건드리지 않는다."""
    if st.session_state.get("authenticated"):
        return False
    try:
        value = st.query_params.get(GUEST_PARAM)
    except Exception:
        return False
    if isinstance(value, (list, tuple)):
        value = value[0] if value else None
    return str(value) == GUEST_VALUE
