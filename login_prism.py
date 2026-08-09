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
MODULE_REVISION = 2026080910

# 판을 누르면 이 표식을 달고 그 화면으로 간다. 받는 쪽(pages/*.py)이 이것을 보고
# 비밀번호 없이 게스트로 들여보낸다. 게스트는 원래도 비밀번호 없이 들어갈 수 있으므로
# 이 표식이 새로 여는 문은 없다 — 누르는 횟수만 둘에서 하나로 준다.
GUEST_PARAM = "guest"
GUEST_VALUE = "1"

PANELS = (
    ("US", "pages/2_자비스3.py", "🌎", "미국테마", "나스닥 · 테마 20 · 상승장과 급락장"),
    ("KR", "pages/3_자비스4.py", "🌏", "한국테마", "코스피 · 테마 20 · 상승장과 급락장"),
)


def _asset(name: str) -> Path | None:
    path = Path(__file__).resolve().parent / "assets" / name
    return path if path.exists() else None


def _panel_background(market: str) -> str:
    """판 배경. 사진이 있으면 사진, 없으면 프리즘 색으로 그린다."""
    photo = _asset(f"login_{market.lower()}.jpg") or _asset(f"login_{market.lower()}.png")
    if photo is not None:
        import base64

        data = base64.b64encode(photo.read_bytes()).decode("ascii")
        kind = "png" if photo.suffix == ".png" else "jpeg"
        return (f"linear-gradient(180deg, rgba(4,6,14,.30), rgba(4,6,14,.78)), "
                f"url('data:image/{kind};base64,{data}')")
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
        #7b828e 0%, #7b828e 32%,
        #c679c4 39%, #fa3d1d 44%, #ffb005 49%, #e1e1fe 54%, #0358f7 59%,
        #7b828e 66%, #7b828e 100%);
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

/* ── 빛 띠와 그 위를 흘러가는 프리즘 조각 ────────────────────────────────
   상하님이 찍어 주신 영상을 프레임으로 뜯어 보고 고쳤다(2026-08-09).
   처음에는 무지개 띠 전체를 위아래로 흔들었는데, 영상에서는 그게 아니었다 —
   **띠는 흰빛이고, 무지개 조각 하나가 그 띠를 따라 천천히 지나간다.**
   같은 화면의 두 프레임에서 띠의 색이 회청색 → 왼쪽만 금빛으로 바뀌어 있었다.
   그래서 띠(jp-band)와 프리즘 조각(jp-prism)을 나눠 겹쳤다. */
.jp-stage { position: relative; padding: 1.1rem 0 .2rem; overflow: hidden; }
.jp-band, .jp-prism {
    position: absolute; left: -14%; right: -14%; top: 52%; height: 3px;
    pointer-events: none;
    animation: jp-drift 18s ease-in-out infinite alternate;
}
.jp-band {
    background: linear-gradient(90deg, transparent 0%, rgba(185,196,216,.45) 20%,
        rgba(255,255,255,.85) 42%, rgba(185,196,216,.45) 64%, transparent 88%);
    filter: blur(9px); opacity: .7;
}
/* 무지개 조각. 띠 길이의 40%만 색이고 나머지는 투명이라, 이 조각이 왼쪽 밖에서
   오른쪽 밖으로 흘러간다. 14초에 한 번 — 상하님 말씀대로 **은은하게**. */
.jp-prism {
    background-image: linear-gradient(90deg, transparent 0%, #0358f7 16%, #e1e1fe 38%,
        #ffb005 62%, #fa3d1d 84%, transparent 100%);
    background-size: 40% 100%; background-repeat: no-repeat;
    filter: blur(12px); opacity: .85;
    animation: jp-drift 18s ease-in-out infinite alternate,
               jp-prism-travel 14s linear infinite;
}
@keyframes jp-prism-travel {
    from { background-position: -48% 0; }
    to   { background-position: 148% 0; }
}
@keyframes jp-drift {
    from { transform: translateY(-9px) skewY(-1deg) scaleX(1); }
    to   { transform: translateY(11px) skewY(1deg) scaleX(1.07); }
}

/* ── 두 판 (okaydev.co 방식) ──────────────────────────────────────────────
   화면이 뜰 때 **가운데에서 좌우로 커지며 빠르게** 퍼진다. 0.55초에
   가속이 붙었다 풀리는 곡선이라 '툭 퍼지는' 느낌이 난다. */
@keyframes jp-burst-left {
    from { opacity: 0; transform: translateX(26%) scale(.84); }
    to   { opacity: 1; transform: none; }
}
@keyframes jp-burst-right {
    from { opacity: 0; transform: translateX(-26%) scale(.84); }
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
    transform: translateY(-4px);
    border-color: rgba(255,255,255,.34) !important;
    box-shadow: 0 16px 44px rgba(0,0,0,.55);
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
    .jp-title, .jp-band, .jp-prism,
    .st-key-jp_panels a[data-testid="stPageLink-NavLink"]::after { animation: none !important; }
}

/* 폰에서는 두 판을 위아래로 쌓는다. 옆으로 두면 한 판이 손가락 하나 폭이 된다.
   퍼지는 방향도 위아래로 바꾼다 — 좌우로 밀면 화면 밖으로 나갔다 들어온다. */
@media (max-width: 640px) {
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
    @keyframes jp-burst-left  { from { opacity:0; transform: translateY(14%) scale(.9); }
                                to { opacity:1; transform:none; } }
    @keyframes jp-burst-right { from { opacity:0; transform: translateY(14%) scale(.9); }
                                to { opacity:1; transform:none; } }
}
</style>
"""


def panel_style(index: int, market: str) -> str:
    """판 하나의 배경과 퍼지는 방향. 칸마다 달라서 따로 내보낸다."""
    burst = "jp-burst-left" if index == 0 else "jp-burst-right"
    delay = 0.10 + index * 0.08
    return (
        f".st-key-jp_panel_{market} a[data-testid='stPageLink-NavLink'] {{"
        f" background-image: {_panel_background(market)} !important;"
        " background-size: cover !important; background-position: center !important;"
        f" animation: {burst} .55s cubic-bezier(.16,1,.3,1) {delay:.2f}s both;"
        "}"
    )


def render(st) -> None:
    """첫 화면의 프리즘 제목과 두 판. 누르면 비밀번호 없이 그 화면으로 간다."""
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(
        "<div class='jp-stage'><div class='jp-band'></div><div class='jp-prism'></div>"
        "<div class='jp-title'>Stock Event Jarvis</div></div>"
        "<div class='jp-sub'><b>장상하</b>의 테마 주식 기록장</div>",
        unsafe_allow_html=True,
    )
    styles = []
    # 가로 칸(st.container(horizontal=True))을 쓰면 판이 글자 폭만큼만 좁아진다
    # (2026-08-09 실측: 800px 화면에서 판이 141px). 보통 칸으로 나눈다.
    columns = st.container(key="jp_panels").columns(len(PANELS), gap="medium")
    for index, (market, page, mark, name, note) in enumerate(PANELS):
        styles.append(panel_style(index, market))
        with columns[index]:
            box = st.container(key=f"jp_panel_{market}")
            with box:
                try:
                    # width="stretch"가 없으면 링크가 글자 폭만큼만 그려진다
                    # (2026-08-09 실측: 1280px 화면에서 판이 141px). CSS로는 안 늘어난다.
                    st.page_link(page, label=f"{mark} {name}", width="stretch",
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
