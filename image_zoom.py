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

**절대 원칙 — 실패해도 아무 일도 일어나지 않아야 한다.**
브라우저가 막거나 그림을 못 찾으면 조용히 넘어간다. 지금 보이는 그림은 그대로 있고,
누르면 아무 일도 안 일어날 뿐이다(쿠키 로그인과 같은 원칙, CLAUDE.md 13번).
"""

from __future__ import annotations

# 표시 방식을 바꾸면 이 숫자를 올리고 부르는 쪽의 요구 리비전도 올린다(규칙 11).
MODULE_REVISION = 2026082702

# 스크립트는 한 판에 한 번만 붙인다. 두 번 붙어도 같은 표시를 보고 그냥 넘어간다.
_SCRIPT = """
<script>
(function () {
  var doc;
  try { doc = window.parent && window.parent.document; } catch (e) { return; }
  if (!doc || doc.__jarvisZoomReady) { return; }
  doc.__jarvisZoomReady = true;

  var style = doc.createElement("style");
  style.textContent =
    'div[class*="st-key-jarvis_method_pic"] img{cursor:zoom-in}' +
    '#jarvis-zoom{position:fixed;inset:0;z-index:2147483647;background:rgba(0,0,0,.94);' +
    'overflow:auto;-webkit-overflow-scrolling:touch;touch-action:auto;' +
    'display:block;padding:0;margin:0}' +
    '#jarvis-zoom img{display:block;margin:0 auto;max-width:none;height:auto;cursor:zoom-out}' +
    '#jarvis-zoom .jz-bar{position:fixed;top:0;left:0;right:0;height:46px;' +
    'display:flex;align-items:center;justify-content:space-between;gap:8px;' +
    'padding:0 10px;background:rgba(0,0,0,.72);color:#fff;font-weight:800;' +
    'font-size:14px;z-index:2}' +
    '#jarvis-zoom .jz-btn{border:0;border-radius:8px;padding:7px 13px;font-weight:800;' +
    'font-size:14px;background:#cfe9ff;color:#c15f3c;cursor:pointer}' +
    '#jarvis-zoom .jz-pad{height:46px}';
  doc.head.appendChild(style);

  function close() {
    var old = doc.getElementById("jarvis-zoom");
    if (old) { old.remove(); }
  }

  function open(src) {
    close();
    var box = doc.createElement("div");
    box.id = "jarvis-zoom";

    var bar = doc.createElement("div");
    bar.className = "jz-bar";
    var hint = doc.createElement("span");
    hint.textContent = "두 손가락으로 벌리거나 밀어서 보십시오";
    var wide = doc.createElement("button");
    wide.className = "jz-btn";
    var shut = doc.createElement("button");
    shut.className = "jz-btn";
    shut.textContent = "✕ 닫기";
    bar.appendChild(hint);
    bar.appendChild(wide);
    bar.appendChild(shut);

    var pad = doc.createElement("div");
    pad.className = "jz-pad";

    var big = doc.createElement("img");
    big.src = src;

    // 처음에는 **화면 폭에 맞춰** 한 장을 다 보여준다. 단추를 누르면 원래 크기가
    // 되어 손으로 밀어 보게 된다. 벌리기는 둘 다에서 된다.
    var full = false;
    function apply() {
      big.style.width = full ? (big.naturalWidth + "px") : "100%";
      wide.textContent = full ? "화면에 맞추기" : "원래 크기로";
    }
    big.addEventListener("load", apply);
    apply();

    wide.addEventListener("click", function (e) {
      e.stopPropagation();
      full = !full;
      apply();
      box.scrollTop = 0;
    });
    shut.addEventListener("click", function (e) { e.stopPropagation(); close(); });
    big.addEventListener("click", function () { close(); });
    box.addEventListener("click", function (e) { if (e.target === box) { close(); } });

    box.appendChild(bar);
    box.appendChild(pad);
    box.appendChild(big);
    doc.body.appendChild(box);
  }

  doc.addEventListener("keydown", function (e) {
    if (e.key === "Escape") { close(); }
  });

  // 설명 창은 눌러야 열리므로 그림이 나중에 생긴다. 그래서 **한 곳에서 받는다** —
  // 그림마다 손잡이를 달면 새로 그려질 때마다 다시 달아야 한다.
  function grab(e) {
    var img = e.target;
    if (!img || img.tagName !== "IMG") { return; }
    if (img.closest("#jarvis-zoom")) { return; }
    // **우리 이름표로 찾는다.** data-testid는 스트림릿 판마다 달라서 온라인에서
    // 안 걸렸다(2026-08-27 상하님 — "마우스로도 안되고 손가락으로 해도 안 된다").
    if (!img.closest('div[class*="st-key-jarvis_method_pic"]')) { return; }
    e.preventDefault();
    e.stopPropagation();
    open(img.currentSrc || img.src);
  }
  // **누르는 순간에 받는다.** click까지 기다리면 창이 먼저 닫히는 판에서는 놓친다.
  // 둘 다 걸어 두되 덮개가 이미 있으면 두 번째는 그냥 넘어간다.
  doc.addEventListener("pointerdown", function (e) {
    if (doc.getElementById("jarvis-zoom")) { return; }
    grab(e);
  }, true);
  doc.addEventListener("click", function (e) {
    if (doc.getElementById("jarvis-zoom")) { return; }
    grab(e);
  }, true);
})();
</script>
"""


def run(st) -> None:
    """설명 창 안 그림에 '눌러서 키우기'를 붙인다. 창을 그린 뒤 한 번 부른다."""
    try:
        import streamlit.components.v1 as components

        components.html(_SCRIPT, height=0)
    except Exception:
        # 컴포넌트가 안 되면 지금까지처럼 그냥 보인다. 화면은 그대로 돈다.
        pass
