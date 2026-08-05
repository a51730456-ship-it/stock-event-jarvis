"""시장 국면·미국 전일 게이지 박스 (자비스3·자비스4 공용).

공포·탐욕 지수와 같은 반원 게이지로 통일한다(2026-07-24 사용자 지시). 국면 이름만
크게 적으면 '하락 압력 큼'이 5점인지 29점인지 알 수 없어서, 조건점수가 구간 어디쯤인지
바늘로 보여준다.

시장 국면과 공포·탐욕 제목은 같은 스카이블루로 통일한다.

이 파일은 그림만 만든다. 국면 판정과 조건점수 계산은 jarvis3_data·jarvis4_data가 한다.
"""

from __future__ import annotations

import gauge_ui

MODULE_REVISION = 2026080510

# 조건점수 구간 — jarvis3_data·jarvis4_data의 판정 기준과 같아야 한다.
# 세 칸이던 것을 다섯 칸으로 늘렸다(2026-08-05 사용자 지시). 시장판단 화면이 이미
# 5단계라서 미국테마·한국테마만 세 칸이면 같은 시장을 두 잣대로 보게 된다.
# 0~29 하락 압력 큼 · 30~49 약세 신호 우세 · 50~64 방향 엇갈림
# · 65~79 상승 신호 우세 · 80~100 상승 여건 양호
ZONES = (
    (29, "하락 압력 큼", "#ff5b5b"),
    (49, "약세 신호 우세", "#ff9d3b"),
    (64, "방향 엇갈림", "#ffd23f"),
    (79, "상승 신호 우세", "#2ee6c5"),
    (100, "상승 여건 양호", "#44f0a1"),
)
RANGE_TEXT = {
    "하락 압력 큼": "0~29",
    "약세 신호 우세": "30~49",
    "방향 엇갈림": "50~64",
    "상승 신호 우세": "65~79",
    "상승 여건 양호": "80~100",
}


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


def _previous_regime_row(overview: dict) -> tuple | None:
    previous = overview.get("previous_market") or {}
    if not previous.get("ok") or previous.get("score") is None:
        return None
    score = float(previous["score"])
    regime = previous.get("regime") or gauge_ui.zone_of(score, ZONES)[0]
    return ("전일 시장국면", regime, f"{score:.0f}점", color_of(score), False)


def regime_box_html(overview: dict | None, *, title: str = "시장 국면",
                    note_prefix: str = " · ") -> str:
    """시장 국면 박스. 조건점수를 게이지로, 세 구간을 오른쪽에 보여준다."""
    overview = overview or {}
    ok = bool(overview.get("ok"))
    score = overview.get("score") if ok else None
    regime = overview.get("regime") if ok else None
    rows = _zone_rows(score)
    previous_row = _previous_regime_row(overview)
    if previous_row:
        rows.append(previous_row)
    box = gauge_ui.box_html(
        title,
        score,
        ZONES,
        rows,
        label=regime,
        title_color=gauge_ui.TITLE_BLUE,
        note=overview.get("posture") if ok else "",
        note_color=color_of(score) if ok else None,
        note_prefix=note_prefix,
    )
    # 구간명과 구별되도록 과거 비교 항목 이름도 제목과 같은 스카이블루로 표시한다.
    return box.replace(
        "<span class='fg-hist-label'>전일 시장국면</span>",
        f"<span class='fg-hist-label' style='color:{gauge_ui.TITLE_BLUE}'>"
        "전일 시장국면</span>",
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
        title_color=gauge_ui.TITLE_BLUE,
    )


CSS = gauge_ui.CSS
