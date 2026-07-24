"""시장 국면·미국 전일 게이지 박스 (자비스3·자비스4 공용).

공포·탐욕 지수와 같은 반원 게이지로 통일한다(2026-07-24 사용자 지시). 국면 이름만
크게 적으면 '방어 우선'이 25점인지 49점인지 알 수 없어서, 조건점수가 구간 어디쯤인지
바늘로 보여준다.

세 박스가 나란히 서면 구별이 안 되므로 제목 색을 다르게 준다 —
공포·탐욕은 파랑, 시장 국면은 밝은 초록, 미국 전일은 진한 초록.

이 파일은 그림만 만든다. 국면 판정과 조건점수 계산은 jarvis3_data·jarvis4_data가 한다.
"""

from __future__ import annotations

import gauge_ui

# 조건점수 구간 — jarvis3_data·jarvis4_data의 판정 기준과 같아야 한다.
# 0~49 방어 우선 · 50~74 중립·선별 · 75~100 상승 우위
ZONES = (
    (49, "방어 우선", "#ff5b5b"),
    (74, "중립·선별", "#ff9d3b"),
    (100, "상승 우위", "#44f0a1"),
)
RANGE_TEXT = {"방어 우선": "0~49", "중립·선별": "50~74", "상승 우위": "75~100"}


def color_of(score) -> str:
    """조건점수에 해당하는 국면 색. 화면 글자색을 게이지와 맞추는 데 쓴다."""
    return gauge_ui.zone_of(score, ZONES)[1] if score is not None else "#e6e6e6"


def _zone_rows(score) -> list[tuple]:
    """오른쪽 줄 — 세 구간을 늘어놓고 지금 속한 칸만 진하게 둔다."""
    current = gauge_ui.zone_of(score, ZONES)[0] if score is not None else None
    return [
        (name, RANGE_TEXT[name], "지금" if name == current else "", color, name != current)
        for _limit, name, color in ZONES
    ]


def regime_box_html(overview: dict | None, *, title: str = "시장 국면") -> str:
    """시장 국면 박스. 조건점수를 게이지로, 세 구간을 오른쪽에 보여준다."""
    overview = overview or {}
    ok = bool(overview.get("ok"))
    score = overview.get("score") if ok else None
    regime = overview.get("regime") if ok else None
    return gauge_ui.box_html(
        title,
        score,
        ZONES,
        _zone_rows(score),
        label=regime,
        title_color=gauge_ui.TITLE_GREEN,
        note=overview.get("posture") if ok else "",
    )


def _change_row(label: str, value) -> tuple:
    """등락률 한 줄. 미국장 색 규칙(+파랑 −빨강)을 쓴다."""
    if value is None:
        return (label, "자료 없음", "—", "#9aa0aa", True)
    color = "#4da6ff" if float(value) >= 0 else "#ff5b5b"
    return (label, "", f"{float(value):+.2f}%", color, False)


def us_prev_box_html(us_prev: dict | None, *, title: str = "미국 전일") -> str:
    """미국 전일 박스 — 한국장은 미국 전일과 갭 상관이 높아 함께 본다.

    이 점수는 자비스3(미국테마) 상단의 '시장 국면'과 **같은 계산**이다
    (jarvis4_data._us_previous_session이 jarvis3_data.get_market_overview를 그대로
    쓴다). 그래서 세 구간도 시장 국면 박스와 똑같이 보여준다 — 지수 등락만 적으면
    이 점수가 어느 단계인지 알 수 없다(2026-07-24 사용자 지시).
    """
    us_prev = us_prev or {}
    ok = bool(us_prev.get("ok"))
    score = us_prev.get("score") if ok else None
    regime = us_prev.get("regime") if ok else None
    rows = _zone_rows(score) + [
        _change_row("S&P500", us_prev.get("spy_change") if ok else None),
        _change_row("나스닥100", us_prev.get("qqq_change") if ok else None),
    ]
    return gauge_ui.box_html(
        title,
        score,
        ZONES,
        rows,
        label=regime,
        title_color=gauge_ui.TITLE_GREEN_DEEP,
    )


CSS = gauge_ui.CSS
