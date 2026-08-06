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
MODULE_REVISION = 2026080610

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
.fg-box-body { gap: 0.7rem; }
.fg-box-gauge .fg-gauge { width: 104px; height: 70px; }
.fg-box-hist { min-width: 0; flex: 1 1 auto; }
.fg-box-hist .fg-hist-row { padding: 0.07rem 0; }
/* 국면 다섯 칸을 접는 규칙은 여기 두지 않는다 — 규칙 12를 어겨 갤럭시탭(1138px)까지
   접혀 단계가 통째로 사라졌다(2026-08-06 사용자 지적). CONTENT_CSS(폰 600px)로 옮겼다. */
.fg-box-title { font-size: 0.86rem; }
/* 시장 상태 카드의 당일·전일 비교는 태블릿에서는 두 줄로 정리한다. 네 칸을 한 줄에
   억지로 넣으면 갤럭시탭 세로 화면에서 전일 카드가 화면 밖으로 밀린다. */
.sig-body-comparison {
    grid-template-areas:
        "today-gauge today-story"
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
.j3-top-cell, .j4-top-cell { min-width: calc(50% - 0.6rem); }
.fg-box { width: 100%; }
"""

# 가로로 들면 폭이 배로 넓어지므로 한 줄에 네 칸, 게이지는 두 개씩 담는다.
# 세로일 때와 눈에 띄게 달라야 "돌려도 그대로"라는 말이 안 나온다.
TOP_ROW_LANDSCAPE_CSS = """
.j3-top-cell, .j4-top-cell { min-width: calc(25% - 0.8rem); }
.fg-box { width: calc(50% - 0.5rem); }
"""

# 테마 종목표(HTML 표 9칸)는 폰에서 칸이 34px까지 좁아져 '+1.76%'가 한 글자씩
# 세로로 쪼개지고 조건점수 막대는 실오라기가 됐다(2026-07-25 실측).
# 칸을 감추지 않고, 글자를 줄이고 줄바꿈을 막은 뒤 넘치면 표만 옆으로 밀어서 본다.
# 값은 하나도 바꾸지 않는다.
THEME_TABLE_CSS = """
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
/* '이 테마 기법에 대한 설명' 단추 — 폰에서 글자만 줄여 화면 밖으로 안 밀리게 한다.
   단추 모양 자체는 method_help.py에 있고, 폰 규칙만 규칙 12에 따라 여기 둔다. */
div[class*="st-key-jarvis_method_help"] button p { font-size: .86rem !important; }
div[class*="st-key-jarvis_method_help"] button { padding: .3rem .7rem !important; }
h1 { font-size: 1.5rem !important; }
h2 { font-size: 1.2rem !important; }
.j3-stock-name, .j4-stock-name { font-size: 1.3rem; }
.j3-mc, .j4-mc { min-width: calc(50% - 0.7rem); }
.j3-mc-val, .j4-mc-val { font-size: 1.15rem; }
.j3-metric-row, .j4-metric-row { gap: 0.6rem 0.9rem; }
.j3-section-title, .j4-section-title { font-size: 1.02rem; }
.j3-pull-guide, .j4-pull-guide, .j5-guide { font-size: 0.86rem; }
/* 가로로 긴 HTML 표는 글자를 줄여 옆으로 밀 거리를 줄인다 */
.j5-table-wrap, .j3-pull-table-wrap { -webkit-overflow-scrolling: touch; }
.j5-table, .j3-pull-table, .j3-theme-table, .j4-theme-table { font-size: 0.8rem; }
/* 시장 국면이 세 칸에서 다섯 칸으로 늘면서(2026-08-05) 카드가 그만큼 길어진다.
   **폰에서만** 지금 속한 칸만 남기고 나머지 네 줄을 접는다 — 값·판정은 그대로이고
   보여주는 방식만 바꾼다. 태블릿·PC에서는 다섯 칸이 다 보여야 한다(규칙 12).
   공포·탐욕의 지난 값 줄과 전일 국면 줄은 흐리게 표시하지 않으므로 여기 안 걸린다. */
.fg-box-hist .fg-hist-row.fg-hist-dim { display: none; }
/* 시장 신호 카드 */
.sig-body { gap: 0.6rem; }
.sig-gauge .fg-gauge { width: 132px; height: 88px; }
.sig-counts { min-width: 0; flex: 1 1 auto; }
.sig-text { flex: 1 1 100%; min-width: 0; }
/* 폰에서는 당일과 전일을 위아래로 하나씩 놓는다. 5단계 이름·날짜가 잘리지 않고
   카드 전체가 좌우로 밀리지 않는다. */
.sig-body-comparison {
    grid-template-areas:
        "today-gauge"
        "today-story"
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
        + f"@media (max-width: {PHONE_MAX_WIDTH}px) {{"
        + THEME_TABLE_CSS + CONTENT_CSS + "".join(table_rules)
        + "}</style>"
    )
