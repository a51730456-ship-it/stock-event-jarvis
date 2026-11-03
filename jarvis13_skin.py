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

MODULE_REVISION = 2026110302
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
body:has(.j13-market-top) [data-testid="stMarkdownContainer"],
body:has(.j13-market-top) [data-testid="stCaptionContainer"],
body:has(.j13-market-top) label,
body:has(.j13-watch-top) [data-testid="stMarkdownContainer"],
body:has(.j13-watch-top) label { color:#e7edf2; }
body:has(.j13-market-top) [data-testid="stCaptionContainer"] { color:#9fb6c8 !important; }
body:has(.j13-market-top) h1, body:has(.j13-market-top) h2, body:has(.j13-market-top) h3 { color:#e7edf2 !important; }
/* 단추는 건드리지 않는다 — 2026-11-03 첫 사진에서 단추 규칙이 밑 막대(홈·시장분석·관심종목)까지 덮어 아이콘이 사라졌다 */
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
