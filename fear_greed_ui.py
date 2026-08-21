"""공포·탐욕 지수 게이지 그림 (자비스3·자비스4 공용).

CNN이 쓰는 반원 게이지를 같은 자료로 직접 그린다(2026-07-24 사용자 요청).
CNN 화면을 그대로 가져오지 않는 이유는 두 가지다 — 남의 이미지를 옮겨 쓰는
문제가 있고, 바깥 이미지 주소는 이 화면에서 뜨지 않는다. 자료(0~100 점수와
지난 값)는 이미 jarvis3_data.get_fear_greed로 받아 오고 있으므로 그림만 우리가 그린다.

구간 이름은 한국어로 적는다 — 'EXTREME FEAR' 대신 '극단적 공포'.

반원을 그리는 계산은 gauge_ui가 맡는다. 시장 국면·미국 전일 박스도 같은 그림을 쓴다.

이 파일은 그림만 만든다. 점수·판정 계산은 하지 않으며, 이 지수는 참고용이라
자비스3·4의 조건점수와 매수 판정에 반영되지 않는다.
"""

from __future__ import annotations

import html

import gauge_ui

# CNN과 같은 다섯 구간. (구간 끝값, 이름, 색)
ZONES = (
    (25, "극단적 공포", "#ff5b5b"),
    (45, "공포", "#ff9d3b"),
    (55, "중립", "#c9cfd8"),
    (75, "탐욕", "#44f0a1"),
    (100, "극단적 탐욕", "#22c55e"),
)

# 게이지 좌표는 gauge_ui가 갖고 있다. 테스트가 쓰는 이름을 그대로 열어 둔다.
_CENTER_X = gauge_ui._CENTER_X


def zone_of(score) -> tuple[str, str]:
    """점수가 속한 구간의 이름과 색."""
    return gauge_ui.zone_of(score, ZONES)


def gauge_svg(score, *, label: str | None = None) -> str:
    """반원 게이지 하나를 SVG로 만든다. score가 없으면 바늘 없이 구간만 그린다."""
    return gauge_ui.gauge_svg(score, ZONES, label=label)


def _history_rows(data: dict):
    """오른쪽에 붙는 지난 값 목록. CNN 화면의 previous close·1주 전 …과 같은 항목."""
    # '전일 종가'는 **맨 아래**에 둔다(2026-08-06 사용자 지시). 위 셋은 오래된 것부터
    # 훑는 참고값이고, 전일은 바로 어제라 성격이 달라 따로 떼어 놓는다.
    items = (
        ("1주 전", data.get("previous_1_week")),
        ("1개월 전", data.get("previous_1_month")),
        ("1년 전", data.get("previous_1_year")),
        ("전일 종가", data.get("previous_close")),
    )
    rows = []
    for title, value in items:
        if value is None:
            continue
        name, color = zone_of(value)
        # 맨 아랫줄('전일 종가')만 보라색이다(2026-08-21 상하님 지시 — "전일
        # 부분, 즉 맨 밑에 보라색으로"). 시장 국면 상자와 같은 처리다.
        if title == "전일 종가":
            color = gauge_ui.PREV_PURPLE
        rows.append((title, name, f"{float(value):.0f}", color, False))
    return rows


def box_html(data: dict | None, *, title: str = "공포·탐욕 지수") -> str:
    """상단 지표 줄에 끼워 넣는 작은 게이지 박스 (2026-07-24 사용자 지시).

    아래에 따로 큰 카드를 두지 않고 맨 위 숫자 옆에 바로 붙이려는 것이라
    가로로 길게 늘어나지 않게 폭을 고정한다. 안내 문구는 넣지 않는다 —
    화면 위쪽 조건점수 설명에 이미 같은 내용이 있다.
    """
    data = data or {}
    ok = bool(data.get("ok"))
    box = gauge_ui.box_html(
        title,
        data.get("score") if ok else None,
        ZONES,
        _history_rows(data) if ok else [],
        label=data.get("rating_kr") if ok else None,
        title_color=gauge_ui.TITLE_BLUE,
        note="마지막 정상값" if ok and data.get("stale") else "",
    )
    return _paint_previous(box)


def _paint_previous(box: str) -> str:
    """'전일 종가' 이름만 보라색 굵게로(2026-08-21 상하님 지시).

    2026-08-06에는 스카이블루였다. 시장 국면 상자의 '전일 종가'와 같은 색이다.
    작은 상자와 큰 카드가 **같은 색**이어야 해서 여기 한 곳에 둔다.
    """
    return box.replace(
        "<span class='fg-hist-label'>전일 종가</span>",
        f"<span class='fg-hist-label' style='color:{gauge_ui.PREV_PURPLE};"
        " font-weight:800'>전일 종가</span>",
    )


def card_html(data: dict | None, *, title: str = "공포·탐욕 지수") -> str:
    """게이지 + 지난 값 + 안내문을 한 덩어리로 만든다(넓게 쓰는 자리용)."""
    data = data or {}
    ok = bool(data.get("ok"))
    score = data.get("score") if ok else None
    label = data.get("rating_kr") if ok else None
    note = "미국 시장 심리를 0(극단적 공포)~100(극단적 탐욕)으로 나타낸 CNN 집계값입니다."
    if not ok:
        note = "지금은 값을 받아오지 못했습니다. 잠시 뒤 다시 조회됩니다."
    elif data.get("stale"):
        note += " 지금은 마지막 정상값을 보여주고 있습니다."
    return _paint_previous(
        "<div class='fg-card'>"
        f"<div class='fg-title'>{html.escape(title)}</div>"
        "<div class='fg-body'>"
        f"<div class='fg-gauge-wrap'>{gauge_svg(score, label=label)}</div>"
        f"<div class='fg-hist'>{gauge_ui.rows_html(_history_rows(data)) if ok else ''}</div>"
        "</div>"
        f"<div class='fg-note'>{html.escape(note)} "
        "이 지수는 참고용이며 조건점수·매수 판정에는 반영하지 않습니다.</div>"
        "</div>"
    )


CSS = gauge_ui.CSS + """
.fg-card { border: 1px solid rgba(255,255,255,0.10); border-radius: 0.7rem;
    background: rgba(255,255,255,0.025); padding: 0.8rem 1rem 0.7rem; margin: 0.2rem 0 0.9rem; }
.fg-title { color: #4da6ff; font-size: 1.2rem; font-weight: 800; margin-bottom: 0.3rem; }
.fg-body { display: flex; flex-wrap: wrap; align-items: center; gap: 1.6rem; }
.fg-gauge-wrap { flex: 0 0 auto; }
.fg-gauge { width: 260px; height: auto; }
.fg-score { font-size: 34px; }
.fg-zone { font-size: 15px; }
.fg-tick { font-size: 11px; }
.fg-hist { flex: 1 1 220px; min-width: 200px; }
.fg-note { color: #9aa0aa; font-size: 0.88rem; line-height: 1.55; margin-top: 0.6rem; }
@media (max-width: 720px) { .fg-body { gap: 0.8rem; } .fg-gauge { width: 220px; height: auto; } }
"""
