"""자비스12 설명 글 — 색 칩 한 줄 + 「자세히 ▾」 접기 (2026-11-04 상하님 「설명서도 이해하기 쉽게 · 색깔도 구분해서 직관적으로 ·
전체 내용을 줄여라」).

긴 설명 글을 지우지 않는다 — 0점 까닭·재 보고 뺀 것은 설명에 남겨야 한다(CLAUDE.md 0-1 마). 맨 위에 **핵심 몇 개만 색 칩**으로
보이고, 원래 글은 「자세히 ▾」 안에 그대로 둔다(누르면 펴짐 · 서버에 안 묻는다). 값·숫자는 부르는 쪽이 준 그대로다.

색 — good 초록(나은 것 · 통과) · bad 빨강(주의 · 나쁜 것) · key 금색(기준 · 숫자) · info 파랑(뜻 · 방법).
이름은 j12br(자비스13 j13br 와 안 섞이게 · CLAUDE.md 0-3 ⑤).
"""

from __future__ import annotations

MODULE_REVISION = 2026110401

TONES = {
    "good": ("#44f0a1", "rgba(68,240,161,.10)", "rgba(68,240,161,.38)"),
    "bad": ("#ff7b7b", "rgba(255,91,91,.10)", "rgba(255,91,91,.40)"),
    "key": ("#ffd166", "rgba(255,209,102,.10)", "rgba(255,209,102,.40)"),
    "info": ("#8fc7ff", "rgba(77,166,255,.10)", "rgba(77,166,255,.34)"),
}

CSS = """<style>
.j12br{margin:.2rem 0 .35rem}
.j12br-chips{display:flex;flex-direction:column;gap:5px}
.j12br-chip{display:flex;gap:8px;align-items:baseline;border-radius:10px;padding:5px 10px;font-size:.84rem;
  line-height:1.45;color:#e6eefb;border:1px solid}
.j12br-chip>b{flex:0 0 auto;font-weight:900;white-space:nowrap}
.j12br-chip>span{flex:1 1 auto;min-width:0}
details.j12br-more{margin-top:5px;font-size:.8rem;color:#9fb6d6;line-height:1.6}
details.j12br-more>summary{cursor:pointer;color:#c084fc;font-weight:800;list-style:none;padding:2px 0}
details.j12br-more>summary::-webkit-details-marker{display:none}
details.j12br-more[open]>summary{margin-bottom:4px}
</style>"""


def chips_html(points) -> str:
    """points = [(tone, 머리, 글)] — 한 줄씩 색 칩. 글에는 <b> 등 HTML 이 들어가도 된다(부르는 쪽 글)."""
    rows = []
    for tone, head, text in points:
        color, back, line = TONES.get(tone, TONES["info"])
        rows.append(f"<div class='j12br-chip' style='background:{back};border-color:{line}'>"
                    f"<b style='color:{color}'>{head}</b><span>{text}</span></div>")
    return "<div class='j12br-chips'>" + "".join(rows) + "</div>"


def wrap(points, detail_html: str = "", summary: str = "자세히 보기 ▾") -> str:
    """색 칩 + (있으면) 원래 글을 접은 「자세히」."""
    more = (f"<details class='j12br-more'><summary>{summary}</summary>{detail_html}</details>"
            if detail_html else "")
    return CSS + "<div class='j12br'>" + chips_html(points) + more + "</div>"
