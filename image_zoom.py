"""그림을 누르면 화면 가득 키워 보여준다 (2026-08-27 상하님 지시).

상하님 — "그림 과 액셀은 클릭이나 터치하면 확대해서 볼수 있게."

**왜 이렇게 만들었나 — 주소를 새로 만들면 안 된다.**
2026-08-27에 두 번 딴 길로 갔다가 둘 다 온라인에서 그림을 죽였다.

  ① `static/` 폴더 + `app/static/…` 주소 — 노트북에서는 200으로 열렸는데
     온라인에서는 그림이 아니라 앱 화면을 내줘 로딩만 돌았다.
  ② 스트림릿 속 이름(`image_to_url`)으로 `/media/…` 주소를 직접 만들기 —
     노트북에서는 됐지만 온라인에서는 만화도 엑셀 표도 **둘 다 사라졌다.**
     그 주소는 스트림릿이 **스스로 그릴 때만** 살아 있다.

그래서 여기서는 **주소를 안 만든다.** `st.image`가 이미 그려 놓은 `<img>`에서
그 그림이 쓰고 있는 주소를 그대로 읽어다 쓴다. 그리는 것은 스트림릿이 하고,
우리는 키우기만 한다. 그림이 사라질 길이 없다.

**어떻게 바깥 화면을 만지나** — `scroll_to.py`와 같은 방식이다. 스트림릿이 정식으로
내주는 `components.html`(작은 iframe)에 스크립트를 담아 보내면, 같은 출처라
바깥 화면(`window.parent.document`)의 요소를 찾아 손댈 수 있다.

**왜 손잡이를 바깥 화면에 심나 — 이것이 2026-08-27에 세 번째로 실패한 까닭이다.**
`components.html`이 만드는 iframe은 스트림릿이 화면을 다시 그릴 때 **없어진다.**
iframe이 없어지면 **거기서 만든 손잡이(이벤트 리스너)도 같이 죽는다.** 그런데
"이미 붙였다"는 표시는 바깥 화면에 남아 있어서 다시 붙이지도 않는다. 그래서 처음
한 번만 되고 그다음부터는 영영 안 된다 — 제 시험에서는 되고 상하님이 쓰실 때는
안 되던 까닭이 이것이다.
그래서 iframe에서는 **바깥 화면에 `<script>`를 심기만** 한다. 심어 놓은 글은
바깥 화면의 것이 되므로 iframe이 사라져도 그대로 산다.
`scroll_to.py`는 한 번 부르고 끝나는 일이라 이 문제가 없다 — 그래서 그건 지금도
잘 돈다. 오래 사는 손잡이는 이야기가 다르다.

**절대 원칙 — 실패해도 아무 일도 일어나지 않아야 한다.**
브라우저가 막거나 그림을 못 찾으면 조용히 넘어간다. 지금 보이는 그림은 그대로 있고,
누르면 아무 일도 안 일어날 뿐이다(쿠키 로그인과 같은 원칙, CLAUDE.md 13번).
"""

from __future__ import annotations

# 표시 방식을 바꾸면 이 숫자를 올리고 부르는 쪽의 요구 리비전도 올린다(규칙 11).
MODULE_REVISION = 2026082705

# 바깥 화면에 심을 글. 여기 있는 `document`는 **바깥 화면**의 것이다.
_PARENT_CODE = r"""
(function () {
  if (window.__jarvisZoom) { return; }
  window.__jarvisZoom = 1;
  var openedAt = 0;

  var style = document.createElement("style");
  style.textContent =
    'div[class*="st-key-jarvis_method_pic"] img{cursor:zoom-in}' +
    /* **굴리기를 브라우저에 분명히 알려 준다.** 안 알려 주면 손가락으로 미는 것을
       화면 확대로 알아들어 밑을 못 본다(2026-08-27 상하님 지적). */
    '#jarvis-zoom{position:fixed;inset:0;z-index:2147483647;background:#000;' +
    'overflow:auto;-webkit-overflow-scrolling:touch;' +
    'touch-action:pan-x pan-y pinch-zoom;overscroll-behavior:contain;display:block}' +
    '#jarvis-zoom .jz-wrap{min-height:100%;padding:52px 0 20px}' +
    '#jarvis-zoom img{display:block;margin:0 auto;max-width:none;height:auto}' +
    '#jarvis-zoom .jz-bar{position:fixed;top:0;left:0;right:0;height:48px;display:flex;' +
    'align-items:center;justify-content:flex-end;gap:8px;padding:0 10px;' +
    'background:rgba(0,0,0,.85);z-index:2}' +
    '#jarvis-zoom .jz-btn{border:0;border-radius:8px;padding:9px 15px;font-weight:800;' +
    'font-size:15px;background:#cfe9ff;color:#c15f3c;cursor:pointer;' +
    'touch-action:manipulation}';
  document.head.appendChild(style);

  function close() {
    var old = document.getElementById("jarvis-zoom");
    if (old) { old.remove(); }
  }

  function open(src, natural) {
    close();
    openedAt = Date.now();
    var box = document.createElement("div");
    box.id = "jarvis-zoom";

    var bar = document.createElement("div");
    bar.className = "jz-bar";
    var wide = document.createElement("button");
    wide.className = "jz-btn";
    var shut = document.createElement("button");
    shut.className = "jz-btn";
    shut.textContent = "\u2715 \ub2eb\uae30";
    bar.appendChild(wide);
    bar.appendChild(shut);

    var wrap = document.createElement("div");
    wrap.className = "jz-wrap";
    var big = document.createElement("img");
    big.src = src;
    wrap.appendChild(big);

    var full = false;
    function apply() {
      var w = big.naturalWidth || natural || 0;
      big.style.width = (full && w) ? (w + "px") : "100%";
      wide.textContent = full ? "\ud654\uba74\uc5d0 \ub9de\ucd94\uae30" : "\uc6d0\ub798 \ud06c\uae30\ub85c";
    }
    big.addEventListener("load", apply);
    apply();

    wide.addEventListener("click", function (e) {
      e.preventDefault(); e.stopPropagation();
      full = !full; apply(); box.scrollTop = 0; box.scrollLeft = 0;
    });
    shut.addEventListener("click", function (e) {
      e.preventDefault(); e.stopPropagation(); close();
    });
    // **그림을 눌러도 안 닫는다**(2026-08-27 상하님 지적 — "한번더 클릭하면 아예
    // 이 테마 설명에서 빠져나가버린다"). 닫는 길은 ✕ 단추와 Esc 둘뿐이다.
    // 굴려 보시다가 손이 그림에 닿아 닫히면 안 된다.

    box.appendChild(bar);
    box.appendChild(wrap);
    document.body.appendChild(box);
  }

  function grab(e) {
    var img = e.target;
    if (!img || img.tagName !== "IMG") { return; }
    if (img.closest("#jarvis-zoom")) { return; }
    if (!img.closest('div[class*="st-key-jarvis_method_pic"]')) { return; }
    if (document.getElementById("jarvis-zoom")) { return; }
    e.preventDefault();
    e.stopPropagation();
    open(img.currentSrc || img.src, img.naturalWidth);
  }

  // **손가락은 신호를 두 번 보낸다.** 대는 순간(pointerdown) 한 번, 0.3초쯤 뒤에
  // '클릭' 한 번 더. 두 번째가 이미 열린 덮개나 그 뒤 화면에 떨어져 설명 창까지
  // 닫아 버렸다(2026-08-27 상하님 지적). 연 직후 0.7초 동안은 그 신호를 삼킨다.
  document.addEventListener("click", function (e) {
    if (document.getElementById("jarvis-zoom") && Date.now() - openedAt < 700) {
      if (!e.target.closest || !e.target.closest(".jz-btn")) {
        e.preventDefault(); e.stopPropagation();
        return;
      }
    }
    grab(e);
  }, true);
  document.addEventListener("pointerdown", grab, true);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") { close(); } });
})();
"""

# iframe이 하는 일은 **위 글을 바깥 화면에 심는 것뿐**이다. 심고 나면 iframe이
# 사라져도 손잡이는 바깥 화면의 것이라 그대로 산다.
_SCRIPT = """
<script>
(function () {
  var doc;
  try { doc = window.parent && window.parent.document; } catch (e) { return; }
  if (!doc) { return; }
  if (doc.getElementById("jarvis-zoom-code")) { return; }
  try {
    var s = doc.createElement("script");
    s.id = "jarvis-zoom-code";
    s.textContent = __CODE__;
    (doc.body || doc.documentElement).appendChild(s);
  } catch (e) {}
})();
</script>
"""


def run(st) -> None:
    """설명 창 안 그림에 '눌러서 키우기'를 붙인다. 창을 그린 뒤 한 번 부른다."""
    try:
        import json
        import streamlit.components.v1 as components

        components.html(_SCRIPT.replace("__CODE__", json.dumps(_PARENT_CODE)), height=0)
    except Exception:
        # 컴포넌트가 안 되면 지금까지처럼 그냥 보인다. 화면은 그대로 돈다.
        pass
