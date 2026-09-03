"""지금 열어 둔 화면만 들어가게 한다 (2026-08-28 상하님 지시).

상하님 — "이 테마 지금 미국테마만 로딩되게 하고 나머지는 다 접근 금지하도록
해라" · "나머지 화면은 접근 금지로 해라."

**로딩과는 상관이 없다.** 2026-08-28에 재 두었다 — 스트림릿은 `pages/` 방식에서
고른 화면 하나만 실행하므로, 미국테마를 열면 다른 화면은 한 줄도 안 돈다
(streamlit+pandas+altair+yfinance 9.1초는 미국테마 자신이 쓰는 값이다).
그래도 막아 두는 것은 상하님이 정하신 것이다. 남는 효과가 하나 있기는 하다 —
다른 화면에 들렀다 오면 그 자료가 온라인 메모리에 남고, 메모리가 차면 서버가
재시작돼 그 9초를 다시 낸다.

**되살리는 법은 한 줄이다** — 아래 `OPEN_PAGES` 에 이름을 다시 넣으면 된다.
지우지 않고 `ALL_PAGES` 에 그대로 남겨 두었다.

막는 자리는 둘이다.
  ① 「어디로 갈까요」 목록에서 뺀다(app.py).
  ② 주소로 바로 들어와도 막는다(각 화면 맨 앞 `guard`).
②가 없으면 북마크나 뒤로가기로 그냥 들어가진다.
"""

from __future__ import annotations

# 화면 이름을 바꾸면 이 숫자를 올리고 부르는 쪽의 요구 리비전도 올린다(규칙 11).
MODULE_REVISION = 2026090310

# 이 앱에 있는 화면 전부. 되살릴 때 여기서 이름을 가져다 쓴다.
ALL_PAGES = (
    "시장판단",
    "자비스1",
    "자비스2",
    "미국테마",
    "한국테마",
    "자비스5",
    "자비스6",
    # 새 디자인 미국테마 (2026-09-03). 옛 "자비스6"(종가관찰)과 **다른 화면**이다 —
    # 이름이 비슷하니 헷갈리지 않게 적어 둔다. 파일은 pages/6_자비스6_미국테마.py.
    "자비스6미국테마",
)

# **지금 열어 둔 화면.** 여기 없는 것은 주소로 들어와도 막힌다.
#
# 한국테마를 남긴 까닭 — 미국테마 맨 위의 「🌏 한국테마 →」 단추가 그리로 간다.
# 그것까지 막으면 그 단추가 막힌 화면으로 가는 죽은 단추가 된다.
OPEN_PAGES = ("미국테마", "한국테마", "자비스6미국테마")

# 막힌 화면에서 안내할 곳.
HOME_PAGE = "pages/2_자비스3.py"
HOME_LABEL = "미국테마로 가기"


def is_open(name: str) -> bool:
    """그 화면이 지금 열려 있나."""
    return str(name) in OPEN_PAGES


def guard(st, name: str) -> None:
    """막힌 화면이면 안내만 그리고 거기서 멈춘다.

    **화면 맨 앞에서 부른다.** 뒤에서 부르면 그 앞의 시세 조회가 이미 다 돌아
    막은 뜻이 없어진다.
    """
    if is_open(name):
        return
    # 닫힌 화면에서는 왼쪽 메뉴도 감춘다 — 거기 이름을 눌러 다른 닫힌 화면으로
    # 옮겨 다니게 두면 막아 둔 뜻이 흐려진다. 미국테마 화면과 같은 규칙이다.
    st.markdown(
        "<style>"
        '[data-testid="stSidebar"],[data-testid="stSidebarNav"],'
        '[data-testid="stSidebarCollapsedControl"],[data-testid="collapsedControl"],'
        '[data-testid="stSidebarCollapseButton"]{display:none !important}'
        "</style>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='max-width:520px;margin:3rem auto;padding:1.6rem 1.4rem;"
        "border:1px solid rgba(255,255,255,.16);border-radius:14px;"
        "background:rgba(255,255,255,.03);text-align:center'>"
        "<div style='font-size:1.25rem;font-weight:800;color:#e6e6e6'>"
        "이 화면은 지금 닫혀 있습니다</div>"
        "<div style='margin-top:.6rem;color:#9aa0aa;font-size:1rem;line-height:1.7'>"
        f"지금 열어 둔 곳은 {' · '.join(OPEN_PAGES)}입니다.</div></div>",
        unsafe_allow_html=True,
    )
    try:
        st.page_link(HOME_PAGE, label=HOME_LABEL)
    except Exception:
        pass          # 링크가 안 되어도 안내 글은 남는다
    st.stop()
