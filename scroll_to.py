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
MODULE_REVISION = 2026082920

# 자리 이름 앞에 붙이는 표식. 화면의 다른 id와 섞이지 않게 한다.
ANCHOR_PREFIX = "jarvis-anchor-"

# 어디로 갈지 담아 두는 자리. 누를 때 적어 두고, 그 판 끝에서 한 번 쓰고 지운다.
REQUEST_KEY = "jarvis_scroll_target"

# 부를 때마다 하나씩 오르는 번호를 담아 두는 자리(_stamp 참고).
COUNTER_KEY = "jarvis_scroll_seq"

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


# `now`가 쓰는 스크립트. 하는 일은 위와 같고, 한 가지만 더한다 —
# **제가 들어앉은 칸을 스스로 숨긴다.** 이 조각은 화면 **한복판**(맨 위)에
# 끼어들므로, 안 숨기면 스트림릿이 칸 사이에 넣는 16px 이 화면 맨 위에
# 빈 줄로 남는다. 2026-08-26~28에 상하님이 세 번 지적하신 그 빈자리다.
# 숨기는 것은 스크립트가 **다 돈 뒤**다 — 먼저 숨기면 브라우저에 따라
# 안 돌 수 있다.
_NOW_SCRIPT = _SCRIPT.replace("  go();", """  go();
  try {
    var box = window.frameElement && window.frameElement.closest(
      '[data-testid="stElementContainer"]');
    if (box) { box.style.display = "none"; }
  } catch (e) {}""")


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


def _stamp(st, script: str) -> str:
    """스크립트 끝에 **매번 다른 번호**를 붙인다 (2026-08-29 상하님 지적).

    상하님 — *"상승장 신고가 눌림 매수 종목에서 종목을 처음 클릭하면 선택종목
    세부사항으로 화면이 밑으로 내려가는데, 두 번째 종목 세 번째 종목을 클릭하면
    다시 안 내려간다."*

    **왜 그랬나.** 이 장치는 작은 iframe 에 스크립트를 담아 보낸다. 그런데
    첫 번째와 두 번째에 보내는 글이 **한 글자도 다르지 않다** — 둘 다
    `jarvis-anchor-detail_pullback` 으로 가라는 같은 말이기 때문이다.
    스트림릿 화면은 보낸 글이 그대로면 iframe 을 **다시 안 연다.** 안 열면
    안에 든 스크립트도 다시 안 돈다. 그래서 첫 번은 되고 두 번째부터 아무 일도
    안 일어났다(첫 번째는 그 자리에 iframe 이 아예 없다가 새로 생긴 것이라 돌았다).

    한 글자만 달라도 다시 연다. 그래서 **부를 때마다 하나씩 오르는 번호**를
    주석으로 붙인다. 화면에 보이지 않고 하는 일도 없다 — 다만 스트림릿에게
    "이건 아까 그 글이 아니다"라고 알려 주는 표시다.

    이 하나로 네 곳이 다 고쳐진다 — 상승장·급락 후 반등장·20개 테마·순위 9가
    모두 이 `run` 을 쓴다.
    """
    try:
        seq = int(st.session_state.get(COUNTER_KEY) or 0) + 1
        st.session_state[COUNTER_KEY] = seq
    except Exception:
        seq = 0
    return f"{script}<!-- {seq} -->"


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

        components.html(_stamp(st, _SCRIPT % anchor_id(name)), height=0)
    except Exception:
        # 컴포넌트가 안 되면 지금까지처럼 그 자리에 머문다. 화면은 그대로 돈다.
        pass


def now(st, name: str) -> None:
    """**이번 판 끝을 기다리지 않고 지금 바로** 그 자리로 간다 (2026-08-29 지시).

    상하님 — *"처음 시장분석 눌러 들어가면 화면 보면서 밑으로 내려가고 있는데
    20개 테마 실시간 순위 이 부분을 로딩하면서 또다시 맨 위 화면으로 올라가
    버린다."*

    **왜 그랬나.** `request`로 적어 둔 표시는 그 판의 **맨 끝**에서 쓰인다.
    그런데 시장분석 화면은 20개 테마 자료를 받느라 끝까지 그리는 데 몇 초가
    걸린다. 그동안 상하님은 이미 화면을 내려 보고 계셨고, 마지막에 표시가
    쓰이면서 그 손을 뿌리치고 맨 위로 끌어올렸다. (표시를 실제로 쓴 자리는
    테마 덩이 끝의 `run` 이었다 — 그래서 "20개 테마를 로딩하면서" 튀었다.)

    화면을 바꾸는 순간은 **그릴 것이 아직 없을 때**다. 그때 바로 올리면
    상하님이 손을 대기 전에 이미 맨 위에 서 있으므로 뿌리칠 일이 없다.

    적어 둔 표시는 **여기서 지운다** — 안 지우면 판 끝에서 또 한 번 올린다.
    실패해도 조용히 넘어간다(이 파일 맨 위 원칙).
    """
    st.session_state.pop(REQUEST_KEY, None)
    try:
        import streamlit.components.v1 as components

        components.html(_stamp(st, _NOW_SCRIPT % anchor_id(name)), height=0)
    except Exception:
        pass
