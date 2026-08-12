"""시장 국면·미국 전일 게이지 박스 (자비스3·자비스4 공용).

공포·탐욕 지수와 같은 반원 게이지로 통일한다(2026-07-24 사용자 지시). 국면 이름만
크게 적으면 '하락 압력 큼'이 5점인지 29점인지 알 수 없어서, 조건점수가 구간 어디쯤인지
바늘로 보여준다.

시장 국면과 공포·탐욕 제목은 같은 스카이블루로 통일한다.

이 파일은 그림만 만든다. 국면 판정과 조건점수 계산은 jarvis3_data·jarvis4_data가 한다.
"""

from __future__ import annotations

import gauge_ui

MODULE_REVISION = 2026081210

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


def _paint(box: str) -> str:
    """구간명과 구별되도록 과거·참고 줄의 이름을 제목과 같은 스카이블루로."""
    for label in ("전일 시장국면", "지금 (참고)"):
        box = box.replace(
            f"<span class='fg-hist-label'>{label}</span>",
            f"<span class='fg-hist-label' style='color:{gauge_ui.TITLE_BLUE}'>"
            f"{label}</span>",
        )
    return box


def _live_regime_row(overview: dict) -> tuple | None:
    """얼린 게이지 아래에 붙는 '지금' 한 줄. 실시간 값을 버리지 않는다."""
    if not overview.get("ok") or overview.get("score") is None:
        return None
    score = float(overview["score"])
    regime = overview.get("regime") or gauge_ui.zone_of(score, ZONES)[0]
    return ("지금 (참고)", regime, f"{score:.0f}점", color_of(score), True)


def regime_box_html(overview: dict | None, *, title: str = "시장 국면",
                    note_prefix: str = " · ", freeze: bool = False) -> str:
    """시장 국면 박스. 조건점수를 게이지로, 다섯 구간을 오른쪽에 보여준다.

    ``freeze=True``면 **직전 완료 장의 값**으로 바늘을 세운다 (2026-08-12 상하님 지시:
    "시장국면은 전날 종가에 마감되고 변동이 없어야 한다"). 실시간 값은 버리지 않고
    상자 아래 '지금 (참고)' 한 줄로 남긴다.

    **기본값은 False다** — 한국테마(자비스4)는 지금까지대로 실시간으로 둔다.
    한 시장을 고치면서 다른 시장을 같이 건드리지 않는다(CLAUDE.md 0-1 다).
    """
    overview = overview or {}
    ok = bool(overview.get("ok"))
    score = overview.get("score") if ok else None
    regime = overview.get("regime") if ok else None
    posture = overview.get("posture") if ok else ""

    frozen = overview.get("previous_market") or {}
    use_frozen = bool(freeze and frozen.get("ok") and frozen.get("score") is not None)
    if use_frozen:
        live_row = _live_regime_row(overview)
        score = float(frozen["score"])
        regime = frozen.get("regime") or gauge_ui.zone_of(score, ZONES)[0]
        posture = frozen.get("posture") or posture
        ok = True
        rows = _zone_rows(score)
        if live_row:
            rows.append(live_row)
        return _paint(gauge_ui.box_html(
            title, score, ZONES, rows,
            label=regime,
            title_color=gauge_ui.TITLE_BLUE,
            note=regime,
            note_color=color_of(score),
            note_prefix=note_prefix,
            footer=posture,
            footer_color=color_of(score),
        ))

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
        # 제목에는 **국면 이름**을 적는다. 예전에는 여기에 '조건 충족 종목만 매수
        # 심사' 같은 행동 지침이 들어가 무슨 상자인지 알 수 없었다(2026-08-06 지시).
        note=regime if ok else "",
        note_color=color_of(score) if ok else None,
        note_prefix=note_prefix,
        # '그래서 무엇을 하라'는 말은 상자 맨 아래 한 줄로 내린다.
        footer=overview.get("posture") if ok else "",
        footer_color=color_of(score) if ok else None,
    )
    return _paint(box)


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
