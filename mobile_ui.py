"""폰 화면에서만 적용되는 표시 규칙 (자비스3·4·5 공용).

2026-07-24 사용자 요청. 갤럭시 S21 울트라(412px)·갤럭시탭 S8+(1138px) 두 기기에서
같이 보기 위해 만들었다. 실측 결과 탭은 지금도 쓸 만하고 폰만 문제였다.

폰(412px)에서 잰 값:
  * 상단 지표 줄이 6줄 838px — 화면(915px)을 거의 다 먹어 KOSPI·수급이 한참 밑으로 밀림
  * 눌림목 표는 한 종목이 12줄 480px — 20종목이면 9,600px라 사실상 못 씀

여기서 하는 일은 **보여주는 방식**뿐이다. 값·점수·판정은 하나도 바꾸지 않는다.
숨긴 칸의 자료도 그대로 계산에 쓰이며, 종목을 누르면 나오는 상세에는 다 들어 있다.

파이썬 렌더링 코드도 건드리지 않는다 — 표의 각 줄은 그 안에 있는 버튼 키로
:has()로 집어낸다. :has()를 모르는 낡은 브라우저에서는 규칙이 무시되고 지금과
똑같이 보일 뿐 깨지지 않는다.

PHONE_MAX_WIDTH보다 넓은 화면(태블릿·PC)에는 아무 영향이 없다.
"""

from __future__ import annotations

# 실행 중인 프로세스에 옛 모듈이 남아 있는지 페이지가 알아채기 위한 표식이다
# (jarvis3_data·market_signal_ui와 같은 장치, CLAUDE.md 11번 규칙).
# 이 표식이 없어서 2026-07-25 온라인에 폰 수정이 하나도 반영되지 않았다 —
# 페이지 파일만 새로 읽히고 mobile_ui는 옛것이 프로세스에 남아 있었다.
# 내보내는 CSS가 바뀌면 이 숫자를 올리고, 페이지의 _REQUIRED_MOBILE_REVISION도 올린다.
MODULE_REVISION = 2026082840

# 이 폭 이하를 '폰'으로 본다. 갤럭시탭 S8+는 1138px라 걸리지 않는다.
PHONE_MAX_WIDTH = 600

_BLOCK = "[data-testid='stHorizontalBlock']"


def hide_header_rows(*head_classes: str) -> str:
    """머리글 줄을 통째로 감춘다 — 세로로 쌓이면 제목만 열두 줄이 된다."""
    selector = ", ".join(f"{_BLOCK}:has(.{name})" for name in head_classes)
    return f"{selector} {{ display: none !important; }}"


def hide_own_header(container_key: str, button_prefix: str) -> str:
    """그 표의 머리글 줄만 감춘다 — 다른 표의 머리글은 건드리지 않는다.

    2026-07-25에 클래스로 머리글을 숨겼다가 다른 표의 머리글까지 사라져 되돌렸다.
    그래서 '이 표 상자 안에서, 종목 단추가 없는 줄'만 집어낸다. 머리글 줄에는
    단추가 없고 종목 줄에는 있다. 세로로 쌓이는 표에서는 이름표를 칸마다 붙이므로
    (table_css) 머리글이 없어도 어느 값인지 알 수 있다.
    """
    return (
        f"div[class*='st-key-{container_key}'] {_BLOCK}"
        f":not(:has(div[class*='st-key-{button_prefix}']))"
        " { display: none !important; }"
    )


def table_css(button_prefix: str, total: int, keep: dict[int, str], cell_class: str) -> str:
    """폰에서 표의 중요한 칸만 남기고 이름표를 붙이는 CSS.

    스트림릿은 폰에서 st.columns를 세로로 쌓는다. 12칸이면 한 종목이 12줄이 되므로
    중요한 칸만 남긴다. 쌓이면 어느 값인지 알 수 없어 이름표를 앞에 붙인다.

    button_prefix : 그 표의 줄마다 들어 있는 버튼 키 앞부분(예: "j3pbf_")
    total         : 표의 전체 칸 수
    keep          : {칸 번호(1부터): 이름표}. 빈 문자열이면 이름표 없이 값만 보인다.
    cell_class    : 값 칸에 붙은 클래스(j3-td / j4-td)
    """
    row = f"{_BLOCK}:has(div[class*='st-key-{button_prefix}'])"
    bar_class = cell_class.split("-")[0] + "-barwrap"  # j3-td -> j3-barwrap
    rules = [
        # 종목 사이를 선으로 나눠 카드처럼 보이게 한다.
        f"{row} {{ border-bottom: 1px solid rgba(255,255,255,0.14) !important;"
        " padding: 0.3rem 0 0.4rem !important; row-gap: 0 !important; }",
        # 쌓인 칸은 낮고 왼쪽 정렬로 — 가운데 정렬이면 이름표와 값이 흩어져 보인다.
        f"{row} .{cell_class} {{ min-height: 1.65rem !important;"
        " justify-content: flex-start !important; text-align: left !important; }",
        # 칸을 감싸는 그릇에도 같은 높이를 준다. 이게 없으면 그릇만 10px로 눌린 채
        # 26px짜리 글자가 넘쳐, 조건점수·상태·당일 글자가 서로 겹쳐 찍힌다
        # (2026-07-25 폰 412px 실측: 겹친 칸 3쌍 → 0쌍).
        f"{row} div:has(> [data-testid='stMarkdownContainer'])"
        " { min-height: 1.75rem !important; }",
        # 점수 막대 칸: 폰에서는 값 앞에 이름표가 붙는데, 막대가 폭 100%를 다
        # 먹으면 이름표 자리가 없어 한 글자씩 세로로 쪼개진다("눌림"→"눌"/"림").
        # 막대를 이름표 옆에서 줄어들게 해 한 줄에 나란히 둔다.
        f"{row} .{bar_class} {{ width: auto !important; flex: 1 1 auto;"
        " min-width: 0 !important; }",
        # 종목 이름 버튼은 한 줄을 다 쓰고 크게.
        f"{row} div[class*='st-key-{button_prefix}'] button p"
        " { font-size: 1.02rem !important; }",
    ]
    hidden = [index for index in range(1, total + 1) if index not in keep]
    if hidden:
        rules.append(
            ", ".join(f"{row} > div:nth-child({index})" for index in hidden)
            + " { display: none !important; }"
        )
    for index, label in keep.items():
        if not label:
            continue
        rules.append(
            f"{row} > div:nth-child({index}) [data-testid='stMarkdownContainer'] > div::before"
            f" {{ content: '{label} '; color: #9aa0aa; font-weight: 700;"
            " margin-right: .35rem; font-size: .82rem; white-space: nowrap; }"
        )
    return "\n".join(rules)


# 폰·태블릿에서는 사이드바 메뉴를 **미국테마(자비스3)·한국테마(자비스4) 둘만**
# 남긴다(2026-08-01 사용자 지시. 그전에는 선행감지까지 셋이었다).
# li 번호는 파일 순서다 — 1 자비스1 · 2 시장판단 · 3 자비스2 · 4 미국테마 ·
# 5 한국테마 · 6 선행감지 · 7 종가관찰. 그래서 1~3과 6~7을 감춘다.
# nth-child는 감춰도 번호가 밀리지 않으므로, app.py의 순서·이름표 규칙
# (nth-child 4/5/6/7)은 그대로 맞는다.
#
# 이 규칙만 태블릿까지(≤1200px) 넓게 잡는다 — 사용자가 "스마트폰과 태블릿"이라고
# 지시했다. 표·글자 규칙(600px)과 기준이 달라서 따로 둔다.
# app.py에도 같은 규칙이 있다(자비스1 화면용). 한쪽만 고치면 화면마다 메뉴가
# 달라지므로 둘을 같이 고쳐야 한다.
SIDEBAR_MAX_WIDTH = 1200

SIDEBAR_NAV_CSS = f"""
@media (max-width: {SIDEBAR_MAX_WIDTH}px) {{
[data-testid="stSidebarNav"] li:nth-child(1),
[data-testid="stSidebarNav"] li:nth-child(2),
[data-testid="stSidebarNav"] li:nth-child(3),
[data-testid="stSidebarNav"] li:nth-child(6),
[data-testid="stSidebarNav"] li:nth-child(7) {{ display: none !important; }}
}}
"""

# 상단 지표 줄 — 글자를 줄이고 게이지를 숫자 뒤로 보낸다.
# 태블릿까지(≤1200px) 걸리게 따로 뺐다 — 폰은 정갈한데 태블릿만 흩어져 보인다는
# 지적을 따랐다(2026-07-25). 표·글자 규칙(600px)과 기준이 달라 분리해 둔다.
# 한 줄에 몇 칸을 담을지는 아래 방향별 묶음이 정한다.
TOP_ROW_CSS = """
.j3-top-row, .j4-top-row { gap: 0.8rem 1rem; }
.j3-top-val, .j4-top-val { font-size: 1.3rem; }
.j3-top-label, .j4-top-label { font-size: 0.84rem; }
.j3-top-sub, .j4-top-sub { font-size: 0.84rem; }
/* 게이지는 숫자 뒤로 보낸다 — 폰에서 게이지 세 개가 430px를 먹어 KOSPI·수급이
   첫 화면 밖으로 밀려났다(2026-07-24 실측). 순서만 바꿀 뿐 값은 그대로다. */
.fg-box { order: 10; box-sizing: border-box; }
/* 나스닥100 선물과 시장 상황(VIX)은 **나란히 선다** (2026-08-28 상하님 지시 —
   "나스닥100 선물과 시장상황 VIX를 같이 둬라, S&P500과 같이 있으니 키높이가 안 맞다").
   둘 다 밑줄이 두 줄로 접히는 칸이라, 한 줄짜리 지수 칸과 짝을 지으면 키가 어긋났다.
   지수 넷과 SPY·QQQ(차례 0)가 먼저 서고, 그다음이 이 둘이다. */
.j3-idx-futures { order: 1; }
.j3-idx-phase { order: 2; }
/* 시장 현황(업종 지도)은 숫자 칸들 뒤, 게이지 둘 앞이다 (2026-08-28 상하님 지시 —
   "시장국면·상승여건양호 사이에 넣어 줘"). 게이지가 order:10 이라 그 사이 값을 준다. */
.j3-sector-map { order: 5; width: 100% !important; min-width: 100% !important;
    max-width: 100% !important; font-size: 11px; }
.fg-box-body { gap: 0.7rem; }
.fg-box-gauge .fg-gauge { width: 104px; height: auto; }
.fg-box-hist { min-width: 0; flex: 1 1 auto; }
.fg-box-hist .fg-hist-row { padding: 0.07rem 0; }
/* 국면 다섯 칸을 접는 규칙은 여기 두지 않는다 — 규칙 12를 어겨 갤럭시탭(1138px)까지
   접혀 단계가 통째로 사라졌다(2026-08-06 사용자 지적). CONTENT_CSS(폰 600px)로 옮겼다. */
.fg-box-title { font-size: 0.86rem; }
/* 시장 상태 카드의 당일·전일 비교는 태블릿에서는 두 줄로 정리한다. 네 칸을 한 줄에
   억지로 넣으면 갤럭시탭 세로 화면에서 전일 카드가 화면 밖으로 밀린다.
   **머리 칸도 제 짝 바로 위에 둔다**(2026-08-07 상하님 지적) — 예전에는 머리 칸
   둘이 맨 위에 나란히 있어서 전일 머리 칸과 전일 계기판 사이에 당일 계기판·설명이
   끼어 있었다. */
.sig-body-comparison {
    grid-template-areas:
        "today-head today-head"
        "today-gauge today-story"
        "previous-head previous-head"
        "previous-gauge previous-story" !important;
    grid-template-columns: minmax(220px, .85fr) minmax(0, 1.15fr) !important;
    overflow-x: visible !important;
}
.sig-gauge-shell .sig-gauge .fg-gauge { width: 100% !important; height: auto !important; }
.sig-gauge-title { white-space: normal !important; }
"""

# 한 줄에 몇 칸을 담을지는 '들고 있는 방향'을 따른다
# (2026-08-01 사용자 지시: "가로로 보면 세로로 고정되어 불편하다").
#
# 갤럭시탭 S8+는 가로로 들면 1138px, 세로로 들면 그보다 훨씬 좁다. 둘 다 위
# 1200px 규칙에 걸려서 돌려도 화면이 똑같이 2칸씩으로 남아 있었다. 그래서 칸 수
# 규칙만 방향별로 갈라 둔다 — 글자 크기·게이지 순서는 위 묶음 그대로다.
# 폭이 아니라 방향을 보므로 태블릿을 돌리는 즉시 따라 바뀐다.
TOP_ROW_PORTRAIT_CSS = """
/* 칸 너비를 **정확히 반**으로 못박는다 (2026-08-28 상하님 지적 — "맨 위쪽
   오른쪽이 비어 있고 시장상황 vix 지수 오른쪽이 비어 있다, 이거 맞춰줘").
   원인 — min-width 만 주면 최소값일 뿐이라 **글이 길면 칸이 그만큼 넓어진다.**
   밑줄이 긴 두 칸이 절반을 넘어 그 줄을 혼자 썼다.
     나스닥100 선물 — "+0.57% · S&P500 선물 +0.35%" 한 줄
     시장 상황     — "VIX 14.51 -4.60%" (1.25rem 굵게)
   이제 그 두 줄은 칸 안에서 접히고, 한 줄에 늘 두 칸이 선다.
   값·색·순서는 하나도 안 바뀐다 — 접히는 자리만 달라진다(규칙 12). */
.j3-top-cell, .j4-top-cell {
    width: calc(50% - 0.6rem); min-width: calc(50% - 0.6rem);
    max-width: calc(50% - 0.6rem); box-sizing: border-box;
}
/* SPY·QQQ·시장 상황은 그림이 둘이라 240px 를 따로 잡아 두었다. 폰에서는 그
   240px 이 절반보다 넓어 같은 일이 난다 — 여기서 풀어 준다. */
.j3-idx-wide { min-width: calc(50% - 0.6rem) !important; }
/* 칸끼리 키가 달라도 **밑선이 아니라 윗선**을 맞춘다. 접힌 줄 때문에 한 칸이
   한 줄 높아졌을 때, 가운데 맞추기로 두면 이름표 높이가 서로 어긋난다. */
.j3-top-row, .j4-top-row { align-items: flex-start; }
.fg-box { width: 100%; min-width: 100%; max-width: 100%; }
"""

# 가로로 들면 폭이 배로 넓어지므로 한 줄에 네 칸, 게이지는 두 개씩 담는다.
# 세로일 때와 눈에 띄게 달라야 "돌려도 그대로"라는 말이 안 나온다.
TOP_ROW_LANDSCAPE_CSS = """
.j3-top-cell, .j4-top-cell { min-width: calc(25% - 0.8rem); }
.fg-box { width: calc(50% - 0.5rem); }
"""

# ── 태블릿(601~1200px)만 — 미국테마 지수 칸의 빈자리를 줄인다 (2026-08-28) ──
#
# 상하님 지적 — "태블릿 세로 가로 화면인데 노란색 그린 부분이 여백이 너무 많다.
# 스마트폰은 괜찮은데… 차라리 세로 화면에 하나 더 넣으면 여백이 줄지 않을까?"
#
# **빈자리의 진짜 까닭은 칸이 넓어서가 아니라 그림이 120px 에 못박혀 있어서다.**
# 태블릿 세로에서 칸은 345px 인데 그림은 120px 이라 오른쪽 200px 이 통째로 빈다.
# 상하님이 노란색으로 그리신 자리가 바로 거기다. 그래서 둘 다 한다.
#   ① 세로는 한 줄에 **셋**. 마지막 줄에 둘만 남으면 그 둘이 늘어나 자리를 메운다
#      (flex-grow) — 안 그러면 폰에서 고쳐 놓은 '빈 오른쪽'이 태블릿에 생긴다.
#   ② 그림이 **칸 폭을 채운다.** 가로로 늘려도 선이 굵어지지 않게 못박아 두었다
#      (_sparkline_svg 의 vector-effect).
#
# **한국테마(.j4-top-cell)는 안 건드린다** — 한 시장을 고치면서 다른 시장을 같이
# 고치지 않는다(CLAUDE.md 0-1 다). 그래서 여기 규칙은 .j3- 만 잡는다.
# 가로는 지금처럼 넷이다 — 여덟 칸이 두 줄로 딱 맞아 빈자리가 안 생긴다.
# 다섯으로 늘리면 5+3 이 되어 둘째 줄만 칸이 커진다.
TABLET_US_FILL_CSS = """
.j3-top-cell .j3-idx-swap { width: 100%; }
.j3-top-cell .j3-idx-swap svg, .j3-top-cell > svg { width: 100% !important; }
"""

TABLET_US_PORTRAIT_CSS = """
.j3-top-cell {
    flex: 1 1 calc(33.333% - 0.7rem);
    width: auto; min-width: calc(33.333% - 0.7rem); max-width: none;
}
.j3-idx-wide { min-width: calc(33.333% - 0.7rem) !important; }
.j3-sector-map { flex: 1 1 100%; }
"""

# 테마 종목표(HTML 표 9칸)는 폰에서 칸이 34px까지 좁아져 '+1.76%'가 한 글자씩
# 세로로 쪼개지고 조건점수 막대는 실오라기가 됐다(2026-07-25 실측).
# 칸을 감추지 않고, 글자를 줄이고 줄바꿈을 막은 뒤 넘치면 표만 옆으로 밀어서 본다.
# 값은 하나도 바꾸지 않는다.
THEME_TABLE_CSS = """
/* 시장 신호 표(칸 7개)는 폰에서 화면 밖으로 나갔다 — 2026-08-07 실측: 표 오른쪽
   끝 386px인데 화면은 375px이라 마지막 칸이 11px 잘렸다. 여기 테마 표와 같은
   방식으로 고친다: **칸은 감추지 않고** 글자를 줄이고, 그래도 넘치면 표만
   옆으로 밀어서 본다. 값·점수·판정은 건드리지 않는다(규칙 12). */
.msig-table { font-size: 0.74rem !important; display: block; overflow-x: auto; }
.msig-table thead, .msig-table tbody { display: table; width: 100%; }
.msig-table th, .msig-table td { padding: 0.35rem 0.2rem !important; }
.msig-table td.msig-reason { font-size: 0.72rem !important; }

.j3-theme-table, .j4-theme-table { table-layout: auto !important; }
.j3-theme-table col, .j4-theme-table col { width: auto !important; }
/* 칸은 감추지 않는다 — 감췄더니 "다른 항목은 어디 갔나"라는 말이 나왔다
   (2026-07-25 사용자 지적). 대신 글자를 줄이고 줄바꿈을 막아 한 줄로 읽히게 하고,
   넘치면 표만 옆으로 밀어서 본다(아래 wrap 규칙). */
.j3-theme-table, .j4-theme-table { font-size: 0.74rem !important; }
.j3-theme-table th, .j3-theme-table td,
.j4-theme-table th, .j4-theme-table td {
    white-space: nowrap !important; padding: 0.4rem 0.25rem !important;
}
/* 종목명도 한 줄로 둔다 — 줄바꿈을 허용했더니 'DB손해보험'이 한 글자씩 세로로
   쪼개졌다(2026-07-25 폰 실측). 표가 넘치면 아래 규칙대로 옆으로 밀어서 본다. */
.j3-theme-table td.j3-th-name, .j4-theme-table td.j4-th-name {
    white-space: nowrap !important; padding-left: 0.4rem !important;
}
.j3-theme-table th.j3-th-left, .j4-theme-table th.j4-th-left { padding-left: 0.4rem !important; }
/* 조건점수 막대가 실오라기로 보이던 것을 막는다. */
.j3-theme-table .j3-barwrap, .j4-theme-table .j4-barwrap { min-width: 68px; }
/* 칸을 다 보여주니 폭이 넘칠 수 있다 — 표만 옆으로 밀어서 본다(화면 전체는 안 밀린다). */
.j3-theme-table, .j4-theme-table { display: block; overflow-x: auto; white-space: nowrap; }
"""

# 종목 상세·신호 카드 등 나머지 자리.
CONTENT_CSS = """
/* 종목 차트 넷(당일·일봉·주봉·월봉)은 폰에서 조금 낮춘다 — 한 줄에 둘씩 서므로
   칸이 좁아 132px 은 세로로 길쭉해 보인다 (2026-08-28). */
.j3-pretty-chart { height: 104px !important; }

/* 「이 화면 설명 보기」의 배점 줄 — 폰에서 이름 칸이 10.4rem으로 못박혀 있어
   설명 글이 들어갈 자리가 70px밖에 안 남았다. 그래서 "무엇을 / 보나 / — 이 /
   회사 주"처럼 한두 글자씩 끊겨 내려갔다(2026-08-21 상하님 캡처).
   폰에서는 줄을 접어, 첫 줄에 이름과 점수를 놓고 설명은 아랫줄 전체 폭으로 쓴다.
   노트북·태블릿은 지금 그대로다 — 이 규칙은 600px 아래에서만 돈다. */
.j3-weight { flex-wrap: wrap !important; row-gap: .1rem !important; }
.j3-weight b { min-width: 0 !important; flex: 1 1 auto !important; }
.j3-weight .j3-w-pt { flex: 0 0 auto !important; }
.j3-weight .j3-w-why { flex: 1 1 100% !important; line-height: 1.55 !important; }
/* '이 테마 기법에 대한 설명' 단추 — 폰에서 글자만 줄여 화면 밖으로 안 밀리게 한다.
   단추 모양 자체는 method_help.py에 있고, 폰 규칙만 규칙 12에 따라 여기 둔다. */
div[class*="st-key-jarvis_method_help"] button p { font-size: .86rem !important; }
div[class*="st-key-jarvis_method_help"] button { padding: .3rem .7rem !important; }
/* '창닫기'는 폰에서 왼쪽으로 간다 — 스트림릿이 좁은 화면에서 좌우 칸을 위아래로
   쌓아 버려 오른쪽 칸이 화면 전체 너비가 되기 때문이다(2026-08-07 실측, 375px).
   오른쪽으로 밀어 노트북에서 보이던 자리와 같게 맞춘다. */
div[class*="st-key-jarvis_method_help_close"] { text-align: right !important; }
div[class*="st-key-jarvis_method_help_close"] button { margin-left: auto !important; margin-right: .3rem !important; }
h1 { font-size: 1.5rem !important; }
h2 { font-size: 1.2rem !important; }
.j3-stock-name, .j4-stock-name { font-size: 1.3rem; }
.j3-mc, .j4-mc { min-width: calc(50% - 0.7rem); }
.j3-mc-val, .j4-mc-val { font-size: 1.15rem; }
.j3-metric-row, .j4-metric-row { gap: 0.6rem 0.9rem; }
.j3-section-title, .j4-section-title { font-size: 1.02rem; }
.j3-pull-guide, .j4-pull-guide, .j5-guide { font-size: 0.86rem; }
/* 순위표 단추 밑 두 줄 — 보라색 '표에서 테마 이름을 클릭하면…'과 초록색
   '오늘 테마 종목 순위는…'이다. **둘은 늘 같은 크기여야 한다**(2026-08-14 상하님
   지시 "크기는 보라색 글자 그 크기로"). 폰에서는 한 치수 줄여 두 줄 다 한 줄에
   들어가게 한다 — 1.08rem이면 375px에서 석 줄로 접힌다. */
.j3-theme-open-guide, .j3-theme-top5 { font-size: 0.92rem; }
/* 심사항목 설명 창(2026-08-14) — 글이 길어 폰에서 화면을 다 먹는다. 한 치수 줄인다.
   값·점수는 건드리지 않는다(규칙 12). */
.j3fh-txt { font-size: 0.86rem; }
.j3fh-name { font-size: 0.92rem; }
/* 가로로 긴 HTML 표는 글자를 줄여 옆으로 밀 거리를 줄인다 */
.j5-table-wrap, .j3-pull-table-wrap { -webkit-overflow-scrolling: touch; }
.j5-table, .j3-pull-table, .j3-theme-table, .j4-theme-table { font-size: 0.8rem; }
/* 시장 국면 다섯 칸 — **폰에서도 다 보여준다** (2026-08-12 상하님 지시).
   2026-08-05에 카드가 길어진다는 이유로 폰에서만 지금 속한 칸 하나만 남기고
   네 줄을 숨겨 뒀는데, 상하님이 태블릿과 견주시고 "스마트폰은 안 나온다,
   나오게 해라"고 하셨다. 0~29 · 30~49 같은 **수치 안내가 폰에서만 사라져** 지금
   점수가 어느 자리인지 알 수 없었다.
   숨기는 대신 **줄을 얇게** 만들어 길이를 줄인다 — 값·판정은 그대로다(규칙 12). */
.fg-box-hist .fg-hist-row.fg-hist-dim {
    font-size: 0.78rem;
    padding: 0.02rem 0;
    opacity: 0.62;
}
/* 날짜별로 저장해 둔 목록 표(2026-08-09) — 칸이 열넷이라 폰에서 1,300px까지
   늘어난다(실측). 테마 표와 같은 방식으로 **칸은 감추지 않고** 글자를 줄여
   옆으로 밀 거리를 줄인다. 값은 하나도 바꾸지 않는다. */
.pl-table { font-size: 0.78rem !important; }
.pl-table th, .pl-table td { padding: 0.3rem 0.25rem !important; }
.pl-table td.pl-c-themes { max-width: 9rem !important; }
.pl-note { font-size: 0.82rem; }
.pl-kind { font-size: 0.95rem; }
/* 시장 신호 카드 */
.sig-body { gap: 0.6rem; }
.sig-gauge .fg-gauge { width: 100%; max-width: 132px; height: auto; }
.sig-counts { min-width: 0; flex: 1 1 auto; }
.sig-text { flex: 1 1 100%; min-width: 0; }
/* 폰에서는 당일과 전일을 위아래로 하나씩 놓는다. 5단계 이름·날짜가 잘리지 않고
   카드 전체가 좌우로 밀리지 않는다.
   머리 칸도 제 짝 바로 위에 둔다(2026-08-07) — 예전에는 머리 칸 둘이 위에 붙어
   있어서 전일 머리 칸 다음에 당일 계기판이 나왔다. */
.sig-body-comparison {
    grid-template-areas:
        "today-head"
        "today-gauge"
        "today-story"
        "previous-head"
        "previous-gauge"
        "previous-story" !important;
    grid-template-columns: minmax(0, 1fr) !important;
    overflow-x: visible !important;
}
.sig-gauge-shell { width: 100%; box-sizing: border-box; }
.sig-gauge-shell .sig-gauge { display: flex; justify-content: center; }
.sig-gauge-shell .sig-gauge .fg-gauge { width: min(100%, 250px) !important; height: auto !important; }
.sig-gauge-title { white-space: normal !important; line-height: 1.35; }
.sig-story { padding: .35rem .55rem .45rem; }
"""


def page_css(*table_rules: str) -> str:
    """폰에서만 도는 <style> 한 덩어리. 표 규칙은 화면마다 달라 받아서 넣는다."""
    return (
        # 메뉴 규칙은 태블릿까지(≤1200px) 걸려야 해서 폰 묶음 밖에 따로 둔다.
        # 안에 넣으면 두 미디어쿼리가 겹쳐 600px로 좁아진다.
        "<style>" + SIDEBAR_NAV_CSS
        + f"@media (max-width: {SIDEBAR_MAX_WIDTH}px) {{" + TOP_ROW_CSS + "}"
        # 칸 수만 방향을 따라간다 — 태블릿을 돌리면 바로 바뀐다(2026-08-01).
        + f"@media (max-width: {SIDEBAR_MAX_WIDTH}px) and (orientation: portrait) {{"
        + TOP_ROW_PORTRAIT_CSS + "}"
        + f"@media (max-width: {SIDEBAR_MAX_WIDTH}px) and (orientation: landscape) {{"
        + TOP_ROW_LANDSCAPE_CSS + "}"
        # 태블릿만(폰 위 ~ 1200px). 미국테마 지수 칸의 빈자리를 줄인다(2026-08-28).
        + f"@media (min-width: {PHONE_MAX_WIDTH + 1}px) and (max-width: {SIDEBAR_MAX_WIDTH}px) {{"
        + TABLET_US_FILL_CSS + "}"
        + f"@media (min-width: {PHONE_MAX_WIDTH + 1}px) and (max-width: {SIDEBAR_MAX_WIDTH}px)"
        + " and (orientation: portrait) {" + TABLET_US_PORTRAIT_CSS + "}"
        + f"@media (max-width: {PHONE_MAX_WIDTH}px) {{"
        + THEME_TABLE_CSS + CONTENT_CSS + "".join(table_rules)
        + "}</style>"
    )
