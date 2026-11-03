"""자비스13 화면 옷 — 자비스12 와 같은 바탕·테두리·맨 위 띠 (2026-11-03 상하님 「자비스12 형식을 따라라」).

상하님 — 「디자인과 사용 직관이 별로 · 자비스12 에 비해 너무 불편 · 자비스12 디자인이 더 괜찮은 듯」.
자비스12(pages/11_자비스12.py 「시장분석 화면도 관심종목 화면과 같은 옷」 · j12-market-top 덩어리)의 규칙을 **글자 그대로
옮기고 이름표만 j13 으로** 바꿨다. 자비스12 파일은 안 고친다. **값·숫자·순서는 하나도 안 건드린다 — 옷만 갈아입힌다.**

  · 바탕 — 남색 그러데이션(흰 바탕을 따르던 판에서는 흐린 글씨가 안 보였다 · 2026-11-03 깃허브 사진)
  · 맨 위 띠(Deploy · ⋮)를 숨긴다 — 자비스12 와 같다
  · 지수 칸 · 게이지 · 코스피 낙폭 상자 · 접는 상자에 금색 테두리(관심종목 카드와 같은 결)
  · 「🌏 미국테마 →」 · 「📘 이 테마 설명」 단추를 맨 위 그림 띠 안으로

주의 — <div> 로 시작하는 덩어리 안에는 빈 줄 · 주석을 넣지 않는다(자비스12 2026-08-26 — 마크다운이 빈 줄에서 끊어 CSS 가
글자로 쏟아졌다). 그래서 표식 덩어리(MARK)와 규칙 덩어리(<style> 로 시작)를 나눈다.
"""

from __future__ import annotations

MODULE_REVISION = 2026110402
TITLE_CLASS = "j13-page-title"

# 표식 + 맨 위 여백 · 숨은 칸 · 단추 자리 — 자비스12 j12-market-top 덩어리와 같은 줄(이름표만 j13).
MARK = """<div class="j13-market-top"></div>
<style>
body:has(.j13-market-top) .stMainBlockContainer,
body:has(.j13-market-top) .block-container { padding-top:0!important; }
body:has(.j13-market-top) .stElementContainer:has(> [data-testid="stMarkdown"] style:only-child),
body:has(.j13-market-top) .stElementContainer:has(> [data-testid="stMarkdown"] .j13-market-top) {
  display:none!important;
}
body:has(.j13-market-top) .stElementContainer:has(hr) {
  margin-top:-8px!important;
  margin-bottom:-8px!important;
}
body:has(.j13-market-top) .st-key-jarvis_method_help_row {
  gap:.35rem!important;
  row-gap:.35rem!important;
  position:relative!important;
  z-index:5!important;
  flex:0 0 auto!important;
  margin-top:-61px!important;
  margin-bottom:0px!important;
}
</style>"""

SKIN = """<style>
/* 맨 위 띠를 숨기고 바탕을 남색으로 — 자비스12 와 같다 */
body:has(.j13-market-top) .stAppHeader,
body:has(.j13-watch-top) .stAppHeader { display:none !important; }
body:has(.j13-market-top), body:has(.j13-market-top) .stApp,
body:has(.j13-watch-top), body:has(.j13-watch-top) .stApp { background:#020b1e !important; color:#e7edf2; }
body:has(.j13-market-top) .stApp, body:has(.j13-watch-top) .stApp {
    background-image:
        radial-gradient(circle at 51% 1%, #0c3d78 0, transparent 27%),
        linear-gradient(160deg, #020a1c 0%, #031a3b 53%, #020b21 100%) !important;
}
/* 지수 칸 · 게이지 상자 · 코스피 낙폭 상자 — 관심종목 카드와 같은 테두리 */
body:has(.j13-market-top) .j4-top-cell,
body:has(.j13-market-top) .fg-box,
body:has(.j13-market-top) .j4-ndd {
    background: linear-gradient(145deg, #06345f 0%, #03264a 58%, #001d3c 100%);
    border: 1px solid #bf9254a8;
    border-radius: 17px;
    box-shadow: inset 0 1px #7bc9ff35, 0 6px 16px #0006;
    padding: 12px 13px 11px;
    box-sizing: border-box;
}
body:has(.j13-market-top) .j4-top-row { gap: 0.85rem; }
body:has(.j13-market-top) .j4-top-cell:hover {
    border-color: #d8ab68; box-shadow: inset 0 1px #7bc9ff55, 0 8px 20px #0008;
}
body:has(.j13-market-top) hr { margin: .35rem 0 !important; border-color: #94b5c52a !important; }
/* 접었다 펴는 설명 상자도 같은 테두리 */
body:has(.j13-market-top) [data-testid="stExpander"] details,
body:has(.j13-watch-top) [data-testid="stExpander"] details {
    border: 1px solid #bf925266 !important;
    border-radius: 15px !important;
    background: linear-gradient(145deg, #06304f26, #001d3c40) !important;
}
/* 글자 — 흰 바탕을 따르던 판에서 어둡게 그려지던 곳을 밝게 */
/* 단추 안 글자는 빼고(:not(.stButton *)) — 밑 막대의 숨은 단추 글자가 밝아져 「홈 홈」처럼 두 번 보였다(2026-11-03 사진) */
body:has(.j13-market-top) [data-testid="stMarkdownContainer"]:not(.stButton *),
body:has(.j13-market-top) [data-testid="stCaptionContainer"],
body:has(.j13-market-top) label:not(.stButton *),
body:has(.j13-watch-top) [data-testid="stMarkdownContainer"]:not(.stButton *),
body:has(.j13-watch-top) label:not(.stButton *) { color:#e7edf2; }
body:has(.j13-market-top) [data-testid="stCaptionContainer"] { color:#9fb6c8 !important; }
body:has(.j13-market-top) h1, body:has(.j13-market-top) h2, body:has(.j13-market-top) h3 { color:#e7edf2 !important; }
/* 보통 단추 — 흰 바탕에 흐린 글씨로 안 읽히던 것(2026-11-03 사진 「수급 다시 확인」 · 「온라인 자료 새로고침」)을 남색으로.
   밑 막대(j13b_nav)와 맨 위 띠의 ↻(j3hero_box)는 **빼고** — 처음 판에서 단추 규칙이 밑 막대를 덮어 아이콘이 사라졌다.
   !important 를 안 쓴다 — 자기 색을 !important 로 가진 단추(「🌏 미국테마 →」 · 「📘 이 테마 설명」 등)는 그대로 둔다. */
body:has(.j13-market-top) .stButton button:not([class*="st-key-j13b_nav"] *):not(.st-key-j3hero_box *),
body:has(.j13-watch-top) .stButton button:not([class*="st-key-j13b_nav"] *):not(.st-key-j3hero_box *) {
    background: linear-gradient(145deg, #0a3a66, #052849);
    color: #f2f6fa;
    border: 1px solid #bf9254a8;
}
body:has(.j13-market-top) [data-testid="stTextInput"] input,
body:has(.j13-watch-top) [data-testid="stTextInput"] input {
    background:#06213f !important; color:#e7edf2 !important; border:1px solid #2b3d5a !important;
}
/* 표 — 어두운 바탕에서 읽히게 */
body:has(.j13-market-top) [data-testid="stTable"] table,
body:has(.j13-market-top) table { color:#e7edf2; }
/* 맨 밑 판 표시 상자 */
body:has(.j13-market-top) .stApp [data-testid="stMarkdownContainer"] div[style*="판 "],
body:has(.j13-watch-top) .stApp [data-testid="stMarkdownContainer"] div[style*="판 "] { background:transparent !important; }
/* 지수 칸 — 자비스12 「미국 전체시장 판단」 칸과 같은 모양(2026-11-04 상하님 캡처 — 「비교 좀 하면서 해라」).
   이름표 초록 · 그림이 칸 폭을 꽉 채움 · 「당일」·「일봉 6개월」 글은 그림 **안** 가운데에 옅은 노랑(선이 글 위로 지나감) ·
   태블릿(601~1200px)은 한 줄에 셋 · PC 는 칸 폭을 고르게. 폰(≤600px)은 mobile_ui 규칙 그대로(CLAUDE.md 12). 값·순서는 그대로. */
body:has(.j13-market-top) .j4-top-label{color:#44f0a1;font-size:1.15rem}
body:has(.j13-market-top) .j4-top-cell svg{width:100%!important}
body:has(.j13-market-top) .j4-idx-now,body:has(.j13-market-top) .j4-idx-more,body:has(.j13-market-top) .j4-idx-solo{position:relative}
body:has(.j13-market-top) .j4-idx-now>svg,body:has(.j13-market-top) .j4-idx-more>svg,body:has(.j13-market-top) .j4-idx-solo>svg{position:relative;z-index:1}
body:has(.j13-market-top) .j4-idx-cap{position:absolute;left:0;right:0;top:50%;transform:translateY(-54%);color:rgba(255,209,102,.55);
  font-size:.7rem;font-weight:800;letter-spacing:-.02em;text-align:center;pointer-events:none;z-index:0;text-shadow:0 1px 3px rgba(0,0,0,.7)}
body:has(.j13-market-top) .j4-idx-cap-daily{color:rgba(255,209,102,.55)}
@media (min-width:601px) and (max-width:1200px){
  body:has(.j13-market-top) .j4-top-cell{flex:1 1 calc(33.333% - .7rem);width:auto;min-width:calc(33.333% - .7rem);max-width:none}
}
@media (min-width:1201px){
  body:has(.j13-market-top) .j4-top-cell{flex:1 1 150px;min-width:150px;max-width:240px}
}
.j13-page-title{font-size:16px; font-weight:800; color:#c084fc; margin:.25rem 0 .4rem; letter-spacing:-.01em;}
body:has(.j13-market-top) [data-testid="stMarkdownContainer"]>div.j13-page-title{ margin-top:10px!important }
</style>"""

# 관심종목 화면 — 맨 위 띠를 숨긴 자리만큼 위 여백을 줄인다(2026-11-03 사진에서 맨 위가 빈 채 약 200px).
WATCH_MARK = """<div class="j13-watch-top"></div>
<style>
body:has(.j13-watch-top) .stMainBlockContainer,
body:has(.j13-watch-top) .block-container { padding-top:1.2rem!important; }
body:has(.j13-watch-top) .stElementContainer:has(> [data-testid="stMarkdown"] style:only-child),
body:has(.j13-watch-top) .stElementContainer:has(> [data-testid="stMarkdown"] .j13-watch-top) { display:none!important; }
</style>"""


def market_css() -> str:
    return MARK + SKIN


def watch_css() -> str:
    return WATCH_MARK + SKIN


# ── 「⚡ 강한 테마 TOP 5」 카드 (2026-11-03 · 자비스12 _render_strong_theme_top5 를 옮김) ─────────────────────────────
# 바로 밑 「오늘의 강한 테마」 표가 쓰는 그 순위(ranking)를 그대로 받는다 — 새로 받거나 다시 세지 않으니 카드와 표 숫자가
# 갈라질 수 없다. 보여 주기만 한다(표가 바로 밑에 늘 펴져 있어 누르는 자리는 두지 않는다).
_TOP5_ICONS = {
    "shield": '<path d="m12 2 8 4v6c0 5-8 10-8 10S4 17 4 12V6zm-4 9 3 3 5-6"/>',
    "chip": '<rect x="5" y="5" width="14" height="14" rx="2"/>'
            '<path d="M9 2v3m6-3v3M9 19v3m6-3v3M2 9h3m-3 6h3m14-6h3m-3 6h3M9 9h6v6H9z"/>',
    "cloud": '<path d="M6 18a5 5 0 0 1-1-10 7 7 0 0 1 13-1 6 6 0 0 1 0 11z"/>',
    "bolt": '<path d="m14 2-10 12h7l-1 8L21 9h-8z"/>',
}


def _top5_icon(name) -> str:
    text = str(name or "")
    if any(word in text for word in ("반도체", "AI", "양자", "HBM", "PCB")):
        key = "chip"
    elif any(word in text for word in ("보안", "방산", "방위")):
        key = "shield"
    elif any(word in text for word in ("클라우드", "소프트", "SaaS", "플랫폼")):
        key = "cloud"
    else:
        key = "bolt"
    return ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{_TOP5_ICONS[key]}</svg>')


def top5_html(ranking: dict, anchor_html: str = "") -> str:
    """순위의 앞 다섯(자료를 받은 것만). 못 받았으면 빈 글 — 빈 카드가 자리만 먹지 않게.

    anchor_html — 카드를 눌러 순위표를 열 때 화면이 올라올 자리 표시. 자비스12 처럼 **카드 안에** 찍는다(따로 칸을 만들면
    높이 0 짜리가 한 칸으로 세어져 틈이 벌어진다 · 자비스12 2026-09-11 실측)."""
    import html as _html

    rows = [row for row in (ranking or {}).get("rows") or [] if row.get("ok")][:5]
    if not rows:
        return ""
    lines = []
    for index, row in enumerate(rows, 1):
        try:
            width = max(0.0, min(100.0, float(row.get("score"))))
            score = f"{float(row.get('score')):.1f}"
        except (TypeError, ValueError):
            width, score = 0.0, "—"
        lines.append(f'<div class="j13-st5-row"><span class="j13-st5-rank">{index:02}</span>'
                     f'<span class="j13-st5-icon">{_top5_icon(row.get("name"))}</span>'
                     f'<b>{_html.escape(str(row.get("name") or ""))}</b>'
                     f'<span class="j13-st5-bar"><i style="width:{width:.1f}%"></i></span><strong>{score}</strong></div>')
    return (TOP5_CSS + '<div class="j13-st5"><div class="j13-st5-head"><span class="j13-st5-flash">⚡</span>'
            '<b>강한 테마 TOP 5</b><span class="j13-st5-unit">테마 점수 / 100</span></div>' + "".join(lines)
            + anchor_html + "</div>")


TOP5_CSS = """<style>
.j13-st5{margin:0 0 .4rem;padding:10px 13px 2px;border:1px solid #bf9254a8;border-radius:16px;
  background:linear-gradient(160deg,#0a2a4e 0%,#061d38 60%,#041229 100%);box-shadow:0 4px 14px rgba(0,0,0,.35),inset 0 1px rgba(140,200,255,.12)}
.j13-st5-head{display:flex;align-items:center;gap:8px;margin:0 0 6px;color:#edf5ff}
.j13-st5-head b{font-size:17px;font-weight:800;letter-spacing:-.3px}
.j13-st5-flash{color:#42caff;font-size:17px}
.j13-st5-unit{margin-left:auto;color:#8fa8c6;font-size:12px;font-weight:600}
.j13-st5-row{display:grid;grid-template-columns:22px 24px minmax(96px,1.45fr) minmax(34px,.95fr) 42px;align-items:center;gap:9px;
  padding:5px 0;border-bottom:1px solid #21406066}
.j13-st5-row:last-child{border-bottom:0}
.j13-st5-rank{color:#7895ba;font-size:13px;font-variant-numeric:tabular-nums}
.j13-st5-icon{display:grid;place-items:center;width:24px;height:24px;border-radius:7px;border:1px solid #2876bc;color:#b6e8ff;
  background:linear-gradient(145deg,#1450a3,#072452)}
.j13-st5-icon svg{width:15px;height:15px}
.j13-st5-row b{color:#edf5ff;font-size:14px;font-weight:600;letter-spacing:-.3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}
.j13-st5-bar{height:6px;border-radius:3px;background:#122740;overflow:hidden}
.j13-st5-bar i{display:block;height:100%;border-radius:3px;background:linear-gradient(90deg,#0860eb,#42caff);box-shadow:0 0 10px rgba(40,180,255,.35);
  transform-origin:left center}
.j13-st5-row strong{color:#f8cc70;font-size:15px;font-weight:800;text-align:right;font-variant-numeric:tabular-nums}
@keyframes j13-st5-grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@keyframes j13-st5-regrow{from{transform:scaleX(0)}to{transform:scaleX(1)}}
.j13-st5.j13-st5-play .j13-st5-bar i{animation:j13-st5-grow 1.4s cubic-bezier(.33,0,.2,1) both}
div.st-key-j13_st5_wrap:hover .j13-st5:not(.j13-st5-play) .j13-st5-bar i{animation:j13-st5-regrow 1.4s cubic-bezier(.33,0,.2,1)}
@media (prefers-reduced-motion: reduce){.j13-st5 .j13-st5-bar i{animation:none!important}}
div.st-key-j13_st5_wrap{position:relative!important}
div.st-key-j13_st5_wrap div.st-key-j13_st5_open{position:absolute!important;inset:0!important;margin:0!important;padding:0!important;z-index:6!important}
div.st-key-j13_st5_wrap div.st-key-j13_st5_open [data-testid="stVerticalBlock"],
div.st-key-j13_st5_wrap div.st-key-j13_st5_open [data-testid="stElementContainer"],
div.st-key-j13_st5_wrap div.st-key-j13_st5_open [data-testid="stButton"]{width:100%!important;height:100%!important;margin:0!important;
  padding:0!important;gap:0!important;max-width:none!important}
div.st-key-j13_st5_wrap div.st-key-j13_st5_open button{width:100%!important;height:100%!important;min-height:0!important;margin:0!important;
  padding:0!important;border:0!important;border-radius:16px!important;background:transparent!important;box-shadow:none!important;
  color:transparent!important;pointer-events:auto!important;touch-action:manipulation!important}
div.st-key-j13_st5_wrap div.st-key-j13_st5_open button p{color:transparent!important}
div.st-key-j13_st5_wrap div.st-key-j13_st5_open button:hover{background:rgba(66,202,255,.07)!important}
</style>"""

# 막대가 화면에 들어오면 **한 번** 왼쪽에서 오른쪽으로 차오르게 — 자비스12 _ST5_WATCH 와 같은 장치(2026-11-04 상하님 「테마 5개
# 그래프 미국테마처럼」). 이름(window.__j13St5Watch · j13-st5-play · data-j13-armed)은 j13 — 자비스12 것과 같으면 먼저 연 화면의
# 장치만 심겨 다른 화면 카드가 안 돈다(CLAUDE.md 0-2 ⑤). 실패해도 막대는 그냥 서 있다(지금까지와 같다).
ST5_WATCH = """
(function(){
  if (window.__j13St5Watch) { return; }
  window.__j13St5Watch = true;
  function arm() {
    document.querySelectorAll('.j13-st5:not([data-j13-armed])').forEach(function (card) {
      card.setAttribute('data-j13-armed', '1');
      if (!('IntersectionObserver' in window)) { return; }
      var watcher = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) { return; }
          watcher.disconnect();
          card.classList.add('j13-st5-play');
          window.setTimeout(function () { card.classList.remove('j13-st5-play'); }, 1600);
        });
      }, { threshold: 0.4 });
      watcher.observe(card);
    });
  }
  arm();
  window.setInterval(arm, 800);
})();
"""
