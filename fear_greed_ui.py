"""공포·탐욕 지수 게이지 그림 (자비스3·자비스4 공용).

CNN이 쓰는 반원 게이지를 같은 자료로 직접 그린다(2026-07-24 사용자 요청).
CNN 화면을 그대로 가져오지 않는 이유는 두 가지다 — 남의 이미지를 옮겨 쓰는
문제가 있고, 바깥 이미지 주소는 이 화면에서 뜨지 않는다. 자료(0~100 점수와
지난 값)는 이미 jarvis3_data.get_fear_greed로 받아 오고 있으므로 그림만 우리가 그린다.

구간 이름은 한국어로 적는다 — 'EXTREME FEAR' 대신 '극단적 공포'.

이 파일은 그림만 만든다. 점수·판정 계산은 하지 않으며, 이 지수는 참고용이라
자비스3·4의 조건점수와 매수 판정에 반영되지 않는다.
"""

from __future__ import annotations

import html
import math

# CNN과 같은 다섯 구간. (구간 끝값, 이름, 색)
ZONES = (
    (25, "극단적 공포", "#ff5b5b"),
    (45, "공포", "#ff9d3b"),
    (55, "중립", "#c9cfd8"),
    (75, "탐욕", "#44f0a1"),
    (100, "극단적 탐욕", "#22c55e"),
)

_WIDTH = 320
# 점수 글자는 바늘 아래에 둔다 — 반원 안에 넣으면 바늘이 숫자를 가로지른다.
_HEIGHT = 214
_CENTER_X = _WIDTH / 2
_CENTER_Y = 132
_OUTER = 118
_INNER = 78


def zone_of(score) -> tuple[str, str]:
    """점수가 속한 구간의 이름과 색."""
    if score is None:
        return "자료 부족", "#9aa0aa"
    value = max(0.0, min(100.0, float(score)))
    for limit, name, color in ZONES:
        if value <= limit:
            return name, color
    return ZONES[-1][1], ZONES[-1][2]


def _point(ratio: float, radius: float) -> tuple[float, float]:
    """0(왼쪽)~1(오른쪽) 위치를 반원 위의 좌표로 바꾼다."""
    angle = math.pi * (1 - max(0.0, min(1.0, ratio)))
    return _CENTER_X + radius * math.cos(angle), _CENTER_Y - radius * math.sin(angle)


def _arc(start_ratio: float, end_ratio: float, color: str) -> str:
    outer_start = _point(start_ratio, _OUTER)
    outer_end = _point(end_ratio, _OUTER)
    inner_end = _point(end_ratio, _INNER)
    inner_start = _point(start_ratio, _INNER)
    return (
        f"<path d='M {outer_start[0]:.2f} {outer_start[1]:.2f} "
        f"A {_OUTER} {_OUTER} 0 0 1 {outer_end[0]:.2f} {outer_end[1]:.2f} "
        f"L {inner_end[0]:.2f} {inner_end[1]:.2f} "
        f"A {_INNER} {_INNER} 0 0 0 {inner_start[0]:.2f} {inner_start[1]:.2f} Z' "
        f"fill='{color}' opacity='0.85'></path>"
    )


def gauge_svg(score, *, label: str | None = None) -> str:
    """반원 게이지 하나를 SVG로 만든다. score가 없으면 바늘 없이 구간만 그린다."""
    parts = [
        f"<svg class='fg-gauge' viewBox='0 0 {_WIDTH} {_HEIGHT}' role='img' "
        f"aria-label='공포·탐욕 지수 {'' if score is None else round(float(score))}'>"
    ]
    start = 0.0
    for limit, _name, color in ZONES:
        end = limit / 100
        parts.append(_arc(start + 0.004, end - 0.004, color))
        start = end

    # 구간 경계 눈금 숫자 (0 · 25 · 50 · 75 · 100)
    for tick in (0, 25, 50, 75, 100):
        x, y = _point(tick / 100, _OUTER + 14)
        parts.append(
            f"<text x='{x:.1f}' y='{y:.1f}' class='fg-tick' text-anchor='middle'>{tick}</text>"
        )

    if score is not None:
        value = max(0.0, min(100.0, float(score)))
        tip = _point(value / 100, _OUTER - 8)
        parts.append(
            f"<line x1='{_CENTER_X}' y1='{_CENTER_Y}' x2='{tip[0]:.2f}' y2='{tip[1]:.2f}' "
            "class='fg-needle'></line>"
        )
        parts.append(f"<circle cx='{_CENTER_X}' cy='{_CENTER_Y}' r='7' class='fg-hub'></circle>")
        name, color = zone_of(value)
        parts.append(
            f"<text x='{_CENTER_X}' y='{_CENTER_Y + 44}' class='fg-score' "
            f"text-anchor='middle' fill='{color}'>{value:.0f}</text>"
        )
        parts.append(
            f"<text x='{_CENTER_X}' y='{_CENTER_Y + 68}' class='fg-zone' "
            f"text-anchor='middle' fill='{color}'>{html.escape(label or name)}</text>"
        )
    else:
        parts.append(
            f"<text x='{_CENTER_X}' y='{_CENTER_Y + 44}' class='fg-zone' "
            "text-anchor='middle' fill='#9aa0aa'>자료 부족</text>"
        )
    parts.append("</svg>")
    return "".join(parts)


def _history_rows(data: dict) -> str:
    """오른쪽에 붙는 지난 값 목록. CNN 화면의 previous close·1주 전 …과 같은 항목."""
    items = (
        ("전일 종가", data.get("previous_close")),
        ("1주 전", data.get("previous_1_week")),
        ("1개월 전", data.get("previous_1_month")),
        ("1년 전", data.get("previous_1_year")),
    )
    rows = []
    for title, value in items:
        if value is None:
            continue
        name, color = zone_of(value)
        rows.append(
            "<div class='fg-hist-row'>"
            f"<span class='fg-hist-label'>{title}</span>"
            f"<span class='fg-hist-zone' style='color:{color}'>{html.escape(name)}</span>"
            f"<span class='fg-hist-value' style='background:{color}'>{float(value):.0f}</span>"
            "</div>"
        )
    return "".join(rows)


def card_html(data: dict | None, *, title: str = "공포·탐욕 지수") -> str:
    """게이지 + 지난 값 + 안내문을 한 덩어리로 만든다."""
    data = data or {}
    ok = bool(data.get("ok"))
    score = data.get("score") if ok else None
    label = data.get("rating_kr") if ok else None
    note = "미국 시장 심리를 0(극단적 공포)~100(극단적 탐욕)으로 나타낸 CNN 집계값입니다."
    if not ok:
        note = "지금은 값을 받아오지 못했습니다. 잠시 뒤 다시 조회됩니다."
    elif data.get("stale"):
        note += " 지금은 마지막 정상값을 보여주고 있습니다."
    return (
        "<div class='fg-card'>"
        f"<div class='fg-title'>{html.escape(title)}</div>"
        "<div class='fg-body'>"
        f"<div class='fg-gauge-wrap'>{gauge_svg(score, label=label)}</div>"
        f"<div class='fg-hist'>{_history_rows(data) if ok else ''}</div>"
        "</div>"
        f"<div class='fg-note'>{html.escape(note)} "
        "이 지수는 참고용이며 조건점수·매수 판정에는 반영하지 않습니다.</div>"
        "</div>"
    )


def box_html(data: dict | None, *, title: str = "공포·탐욕 지수") -> str:
    """상단 지표 줄에 끼워 넣는 작은 게이지 박스 (2026-07-24 사용자 지시).

    아래에 따로 큰 카드를 두지 않고 맨 위 숫자 옆에 바로 붙이려는 것이라
    가로로 길게 늘어나지 않게 폭을 고정한다. 안내 문구는 넣지 않는다 —
    화면 위쪽 조건점수 설명에 이미 같은 내용이 있다.
    """
    data = data or {}
    ok = bool(data.get("ok"))
    score = data.get("score") if ok else None
    label = data.get("rating_kr") if ok else None
    stale = " · 마지막 정상값" if ok and data.get("stale") else ""
    return (
        "<div class='fg-box'>"
        f"<div class='fg-box-title'>{html.escape(title)}{stale}</div>"
        "<div class='fg-box-body'>"
        f"<div class='fg-box-gauge'>{gauge_svg(score, label=label)}</div>"
        f"<div class='fg-box-hist'>{_history_rows(data) if ok else ''}</div>"
        "</div></div>"
    )


CSS = """
.fg-box { border: 1px solid rgba(255,255,255,0.12); border-radius: 0.6rem;
    background: rgba(255,255,255,0.03); padding: 0.5rem 0.7rem 0.45rem;
    display: inline-block; }
.fg-box-title { color: #4da6ff; font-size: 0.92rem; font-weight: 800; margin-bottom: 0.1rem; }
.fg-box-body { display: flex; align-items: center; gap: 0.9rem; }
.fg-box-gauge .fg-gauge { width: 132px; height: 88px; }
.fg-box-gauge .fg-score { font-size: 46px; }
.fg-box-gauge .fg-zone { font-size: 20px; }
.fg-box-gauge .fg-tick { font-size: 14px; }
.fg-box-hist { min-width: 168px; }
.fg-box-hist .fg-hist-row { padding: 0.14rem 0; gap: 0.45rem; }
.fg-box-hist .fg-hist-label { font-size: 0.8rem; }
.fg-box-hist .fg-hist-zone { font-size: 0.8rem; }
.fg-box-hist .fg-hist-value { font-size: 0.76rem; padding: 0.02rem 0.45rem; min-width: 1.9rem; }
.fg-card { border: 1px solid rgba(255,255,255,0.10); border-radius: 0.7rem;
    background: rgba(255,255,255,0.025); padding: 0.8rem 1rem 0.7rem; margin: 0.2rem 0 0.9rem; }
.fg-title { color: #4da6ff; font-size: 1.2rem; font-weight: 800; margin-bottom: 0.3rem; }
.fg-body { display: flex; flex-wrap: wrap; align-items: center; gap: 1.6rem; }
.fg-gauge-wrap { flex: 0 0 auto; }
.fg-gauge { width: 260px; height: 174px; }
.fg-score { font-size: 34px; font-weight: 800; }
.fg-zone { font-size: 15px; font-weight: 800; }
.fg-tick { font-size: 11px; fill: #9aa0aa; font-weight: 700; }
.fg-needle { stroke: #e6e6e6; stroke-width: 3.5; stroke-linecap: round; }
.fg-hub { fill: #e6e6e6; }
.fg-hist { flex: 1 1 220px; min-width: 200px; }
.fg-hist-row { display: flex; align-items: center; gap: 0.6rem; padding: 0.28rem 0;
    border-bottom: 1px solid rgba(255,255,255,0.06); }
.fg-hist-row:last-child { border-bottom: none; }
.fg-hist-label { color: #9aa0aa; font-size: 0.9rem; flex: 1 1 auto; }
.fg-hist-zone { font-size: 0.9rem; font-weight: 800; }
.fg-hist-value { color: #10141b; font-weight: 800; font-size: 0.85rem;
    border-radius: 999px; padding: 0.05rem 0.55rem; min-width: 2.1rem; text-align: center; }
.fg-note { color: #9aa0aa; font-size: 0.88rem; line-height: 1.55; margin-top: 0.6rem; }
@media (max-width: 720px) { .fg-body { gap: 0.8rem; } .fg-gauge { width: 220px; height: 147px; } }
"""
