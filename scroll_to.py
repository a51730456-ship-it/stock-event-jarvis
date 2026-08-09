"""종목을 누르면 그 상세가 있는 자리로 화면을 내려 준다 (2026-08-09 상하님 지시).

상하님 말씀 — "종목을 클릭하면 선택 종목 세부사항으로 가야지, 그냥 화면 그 자리에
있으면 안 되지."

지금까지는 종목을 누르면 상세가 **열리기는 했지만** 그 자리가 화면 한참 아래라,
직접 굴려 내려가야 보였다. 표가 20줄이면 상세는 두세 화면 아래에 있다.

**왜 이렇게 만들었나 — 스트림릿에는 '거기로 내려가라'가 없다.**
`st.markdown`은 `<script>`를 지워 버린다. 그래서 스트림릿이 정식으로 내주는
`components.html`(작은 iframe)에 한 줄짜리 스크립트를 담아 보낸다. 이 iframe은
같은 출처라 바깥 화면(`window.parent`)의 요소를 찾아 `scrollIntoView`를 부를 수
있다 — 2026-08-09에 실물로 확인했다(찾은 자리로 3707px 중 1857px까지 내려갔다).

**절대 원칙 — 실패해도 아무 일도 일어나지 않아야 한다.**
브라우저가 막거나 자리를 못 찾으면 조용히 넘어간다. 화면이 죽거나 엉뚱한 데로
튀면 안 된다(쿠키 로그인과 같은 원칙, CLAUDE.md 13번).
"""

from __future__ import annotations

# 표시 방식을 바꾸면 이 숫자를 올리고 페이지의 요구 리비전도 올린다(규칙 11).
MODULE_REVISION = 2026080910

# 자리 이름 앞에 붙이는 표식. 화면의 다른 id와 섞이지 않게 한다.
ANCHOR_PREFIX = "jarvis-anchor-"

# 어디로 갈지 담아 두는 자리. 누를 때 적어 두고, 그 판 끝에서 한 번 쓰고 지운다.
REQUEST_KEY = "jarvis_scroll_target"

# 자리 표시는 눈에 보이지 않아야 한다. scroll-margin-top은 **맨 위에 붙어 있는
# 도구막대에 제목이 가리지 않게** 그만큼 띄워 세우는 값이다.
CSS = """
<style>
.jarvis-anchor { display: block; height: 0; scroll-margin-top: 84px; }
</style>
"""

# 화면이 아직 그려지는 중일 수 있어 몇 번 다시 찾아본다(최대 2초).
_SCRIPT = """
<script>
(function () {
  var target = "%s";
  var tries = 0;
  function go() {
    tries += 1;
    var doc;
    try { doc = window.parent && window.parent.document; } catch (e) { return; }
    if (!doc) { return; }
    var el = doc.getElementById(target);
    if (el) {
      try { el.scrollIntoView({ behavior: "smooth", block: "start" }); } catch (e) {
        try { el.scrollIntoView(); } catch (e2) {}
      }
      // 부드럽게 미는 것이 안 도는 브라우저가 있다. 0.6초 뒤에도 그 자리에
      // 안 왔으면 한 번에 데려간다 — 못 가는 것보다 툭 가는 편이 낫다.
      setTimeout(function () {
        try {
          if (Math.abs(el.getBoundingClientRect().top) > 200) {
            el.scrollIntoView({ block: "start" });
          }
        } catch (e) {}
      }, 600);
      return;
    }
    if (tries < 40) { setTimeout(go, 50); }
  }
  go();
})();
</script>
"""


def anchor_id(name: str) -> str:
    return f"{ANCHOR_PREFIX}{name}"


def anchor(st, name: str) -> None:
    """'여기가 그 자리다' 표시. 상세 구역 바로 위에 한 번 그린다.

    같은 이름을 두 곳에 그리면 **먼저 그린 쪽**으로 간다(getElementById 규칙).
    그래서 순위 7 안에서 다시 그려지는 눌림목 상세에는 다른 이름을 준다.
    """
    st.markdown(
        f"<div id='{anchor_id(name)}' class='jarvis-anchor'></div>",
        unsafe_allow_html=True,
    )


def request(st, name: str) -> None:
    """이번 판이 끝나면 그 자리로 내려가 달라고 적어 둔다."""
    st.session_state[REQUEST_KEY] = str(name)


def run(st) -> None:
    """적어 둔 자리가 있으면 한 번 내려가고 지운다. 페이지 맨 끝에서 부른다.

    표시를 **먼저 지운다** — 스트림릿은 무엇을 누르든 화면을 다시 그리므로,
    안 지우면 다음 판에도 또 내려가 화면이 붙잡힌 것처럼 느껴진다.
    """
    name = st.session_state.pop(REQUEST_KEY, None)
    if not name:
        return
    try:
        import streamlit.components.v1 as components

        components.html(_SCRIPT % anchor_id(name), height=0)
    except Exception:
        # 컴포넌트가 안 되면 지금까지처럼 그 자리에 머문다. 화면은 그대로 돈다.
        pass
