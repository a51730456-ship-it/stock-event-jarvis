"""상단 줄에 들어가는 반원 게이지 박스 (공용).

공포·탐욕 지수, 시장 국면, 미국 전일이 모두 같은 모양을 쓴다(2026-07-24 사용자 지시).
그림 그리는 계산은 여기 한 곳에만 두고, 각 화면은 구간과 오른쪽 줄만 넘긴다.

세 박스가 나란히 붙으면 서로 구별이 안 되므로 제목 색을 다르게 준다
(공포·탐욕은 파랑, 시장 국면은 밝은 초록, 미국 전일은 진한 초록).

이 파일은 그림만 만든다. 점수 계산이나 판정은 하지 않는다.
"""

from __future__ import annotations

import html
import math

MODULE_REVISION = 2026080620

# 제목 색 — 세 박스를 눈으로 구별하기 위한 것.
TITLE_BLUE = "#4da6ff"
TITLE_GREEN = "#44f0a1"
TITLE_GREEN_DEEP = "#22c55e"

_WIDTH = 320
# 점수 글자는 바늘 아래에 둔다 — 반원 안에 넣으면 바늘이 숫자를 가로지른다.
# 구간 이름을 26px로 키우니 숫자와 겹쳤다(2026-08-06 실측: 14단위 겹침).
# 글자 자리를 아래로 내리면서 그림 높이도 214 → 256으로 늘린다.
#
# **주의** — CSS의 font-size는 화면 픽셀이라, 그림이 작게 그려질수록 viewBox 안에서는
# 그만큼 커진다(124px 폭에서 26px 글자 = viewBox 67단위). 그래서 눈대중으로 8~10단위쯤
# 띄우면 실제로는 겹친다. 고칠 때는 반드시 브라우저에서 재 볼 것.
_HEIGHT = 256
_CENTER_X = _WIDTH / 2
_CENTER_Y = 132
_OUTER = 118
_INNER = 78


def zone_of(score, zones) -> tuple[str, str]:
    """점수가 속한 구간의 이름과 색. zones는 (끝값, 이름, 색) 목록이다."""
    if score is None:
        return "자료 부족", "#9aa0aa"
    value = max(0.0, min(100.0, float(score)))
    for limit, name, color in zones:
        if value <= limit:
            return name, color
    return zones[-1][1], zones[-1][2]


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


def gauge_svg(
    score,
    zones,
    *,
    label: str | None = None,
    ticks=(0, 25, 50, 75, 100),
    show_score: bool = True,
) -> str:
    """반원 게이지 하나. score가 없으면 바늘 없이 구간만 그린다.

    show_score=False는 숫자가 없는 판정에 쓴다 — 시장 신호 카드처럼 0~100 점수가
    아니라 '네 단계 중 어디인가'만 나타낼 때는 숫자를 지어내지 않는다.
    """
    parts = [
        f"<svg class='fg-gauge' viewBox='0 0 {_WIDTH} {_HEIGHT}' role='img' "
        f"aria-label='{'' if score is None else round(float(score))}'>"
    ]
    start = 0.0
    for limit, _name, color in zones:
        end = limit / 100
        parts.append(_arc(start + 0.004, end - 0.004, color))
        start = end

    for tick in ticks:
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
        name, color = zone_of(value, zones)
        if show_score:
            parts.append(
                f"<text x='{_CENTER_X}' y='{_CENTER_Y + 44}' class='fg-score' "
                f"text-anchor='middle' fill='{color}'>{value:.0f}</text>"
            )
        # 숫자 아래 68 → 104. 위 _HEIGHT 주석 참고 — 여기 숫자를 줄이면 겹친다.
        parts.append(
            f"<text x='{_CENTER_X}' y='{_CENTER_Y + (104 if show_score else 46)}' class='fg-zone' "
            f"text-anchor='middle' fill='{color}'>{html.escape(label or name)}</text>"
        )
    else:
        parts.append(
            f"<text x='{_CENTER_X}' y='{_CENTER_Y + 44}' class='fg-zone' "
            "text-anchor='middle' fill='#9aa0aa'>자료 부족</text>"
        )
    parts.append("</svg>")
    return "".join(parts)


def rows_html(rows) -> str:
    """게이지 오른쪽 줄 목록. rows는 (왼쪽 글, 가운데 글, 알약 글, 색, 흐리게) 묶음이다."""
    out = []
    for label, middle, pill, color, dim in rows:
        # 흐린 줄에 이름표를 붙여 둔다 — 폰·태블릿에서 지금 칸만 남기고 접는 데 쓴다
        # (2026-08-05). 글자색·투명도는 그대로라 노트북 화면은 달라지지 않는다.
        opacity = " style='opacity:.42'" if dim else ""
        dim_class = " fg-hist-dim" if dim else ""
        out.append(
            f"<div class='fg-hist-row{dim_class}'{opacity}>"
            f"<span class='fg-hist-label'>{html.escape(str(label))}</span>"
            f"<span class='fg-hist-zone' style='color:{color}'>{html.escape(str(middle))}</span>"
            f"<span class='fg-hist-value' style='background:{color}'>{html.escape(str(pill))}</span>"
            "</div>"
        )
    return "".join(out)


def _title_html(title: str) -> str:
    """제목 본문은 기본색, 앞이나 끝의 '(미국)'만 밝은 초록색으로 출력한다."""
    country = "(미국)"
    if title.startswith(country):
        rest = title[len(country):]
        return (
            f"<span style='color:{TITLE_GREEN}'>{html.escape(country)}</span>"
            f"{html.escape(rest)}"
        )
    if title.endswith(country):
        base = title[:-len(country)]
        return (
            f"{html.escape(base)}"
            f"<span style='color:{TITLE_GREEN}'>{html.escape(country)}</span>"
        )
    return html.escape(title)


def box_html(
    title: str,
    score,
    zones,
    rows,
    *,
    label: str | None = None,
    title_color: str = TITLE_BLUE,
    note: str = "",
    note_color: str | None = None,
    note_prefix: str = " · ",
    footer: str = "",
    footer_color: str | None = None,
) -> str:
    """상단 지표 줄에 끼워 넣는 게이지 박스. 가로로 길어지지 않게 폭을 고정한다.

    footer는 **상자 맨 아래 한 줄**이다. 제목에는 지금 상태 이름을 적고, '그래서
    무엇을 하라'는 말은 아래로 내린다(2026-08-06 사용자 지시) — 제목이 행동 지침을
    말하면 무슨 상자인지 알 수 없다.
    """
    suffix = (
        f"{note_prefix}<span style='color:{note_color}'>{html.escape(note)}</span>"
        if note and note_color else f"{note_prefix}{html.escape(note)}" if note else ""
    )
    foot = (
        f"<div class='fg-box-foot'"
        + (f" style='color:{footer_color}'" if footer_color else "")
        + f">{html.escape(footer)}</div>"
        if footer else ""
    )
    return (
        "<div class='fg-box'>"
        f"<div class='fg-box-title' style='color:{title_color}'>"
        f"{_title_html(title)}{suffix}</div>"
        "<div class='fg-box-body'>"
        f"<div class='fg-box-gauge'>{gauge_svg(score, zones, label=label)}</div>"
        f"<div class='fg-box-hist'>{rows_html(rows)}</div>"
        f"</div>{foot}</div>"
    )


CSS = """
/* 상단 지표 줄에는 게이지 박스가 최대 세 개까지 들어간다. 폭이 넓으면 줄이
   넘어가므로 필요한 만큼만 차지하게 한다(2026-07-24 실측 후 조정). */
.fg-box { border: 1px solid rgba(255,255,255,0.12); border-radius: 0.6rem;
    background: rgba(255,255,255,0.03); padding: 0.45rem 0.6rem 0.4rem;
    display: inline-block; }
.fg-box-title { font-size: 0.92rem; font-weight: 800; margin-bottom: 0.1rem; }
/* 상자 맨 아래 한 줄 — '그래서 무엇을 하라'는 말이 들어간다(2026-08-06). */
.fg-box-foot { font-size: 0.88rem; font-weight: 800; margin-top: 0.22rem;
    padding-top: 0.22rem; border-top: 1px solid rgba(255,255,255,0.1); }
.fg-box-body { display: flex; align-items: center; gap: 0.6rem; }
.fg-box-gauge { flex: 0 0 auto; }
/* 높이는 auto로 둔다 — 픽셀로 박아 두면 _HEIGHT를 고칠 때마다 반원이 찌그러진다
   (2026-08-06). SVG가 viewBox 비율대로 알아서 잡는다. */
.fg-box-gauge .fg-gauge { width: 124px; height: auto; }
.fg-box-gauge .fg-score { font-size: 46px; }
/* 점수 밑 구간 이름이 너무 작아 안 읽혔다(2026-08-06 사용자 지시). 20px → 26px.
   **여기 주석에 판정 이름을 예로 적지 말 것** — 이 CSS는 화면에 글자로 나가므로
   '자료도 없이 판정을 지어냈나'를 보는 시험(test_market_judgment_page)이 걸린다. */
.fg-box-gauge .fg-zone { font-size: 26px; }
.fg-box-gauge .fg-tick { font-size: 14px; }
.fg-box-hist { min-width: 132px; }
.fg-score { font-weight: 800; }
.fg-zone { font-weight: 800; }
.fg-tick { fill: #9aa0aa; font-weight: 700; }
.fg-needle { stroke: #e6e6e6; stroke-width: 3.5; stroke-linecap: round; }
/* 손을 올리면 바늘이 좌우로 살짝 흔들렸다 제자리로 온다(2026-08-06 사용자 요청).
   회전 중심은 바늘이 꽂힌 축(_CENTER_X, _CENTER_Y = 160,132)이다. */
@keyframes fg-needle-wiggle {
  0%   { transform: rotate(0deg); }
  22%  { transform: rotate(-5deg); }
  52%  { transform: rotate(3.5deg); }
  78%  { transform: rotate(-1.5deg); }
  100% { transform: rotate(0deg); }
}
.fg-box:hover .fg-needle, .fg-gauge-wrap:hover .fg-needle {
  transform-origin: 160px 132px;
  animation: fg-needle-wiggle .7s cubic-bezier(.3,.7,.4,1);
}
.fg-hub { fill: #e6e6e6; }
.fg-hist-row { display: flex; align-items: center; gap: 0.45rem; padding: 0.14rem 0;
    border-bottom: 1px solid rgba(255,255,255,0.06); }
.fg-hist-row:last-child { border-bottom: none; }
.fg-hist-label { color: #9aa0aa; font-size: 0.8rem; flex: 1 1 auto; }
.fg-hist-zone { font-size: 0.8rem; font-weight: 800; }
.fg-hist-value { color: #10141b; font-weight: 800; font-size: 0.76rem;
    border-radius: 999px; padding: 0.02rem 0.45rem; min-width: 1.9rem; text-align: center; }
"""
