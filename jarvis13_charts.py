"""자비스13 종목 차트 — 자비스12 형식 그림 · **누르면 크게 뜨고 다시 누르면 닫힘** (2026-11-04 상하님).

상하님 — 「각 차트 전체 다 확인하고 미국테마 형식처럼 누르면 확대 열리고 닫히고 따라 하고」.

자비스12(pages/11_자비스12.py 「종목 차트」 · _pretty_chart_svg · _candle_svg · _chart_zoom_html · _ZOOM_CLONE_JS)의 그림과
여닫이를 **글자 그대로 옮기고 이름표만 j13** 으로 바꿨다(자비스12 파일은 안 고친다 · CLAUDE.md 0-3 ③).
  · 그림 — 시작한 값(당일은 전일 종가) 점선 위는 빨강 · 아래는 파랑(한국장 색) · 20선 주황 · 50선 보라 · 일봉은 봉차트(여섯 달)
  · 여닫이 — 칸을 누르면 숨은 스위치가 켜져 창이 튀어 오르고, 창이나 어두운 바탕을 누르면 닫힌다. 서버에 다시 묻지 않는다.
    창에는 그림을 한 벌 더 싣지 않는다 — 누르는 순간 작은 칸의 그림을 베껴 넣는다(CLONE_JS · 자비스12 2026-09-24 「테마 클릭하면 3초」).
  · 덤 — 예전 알테어(Vega) 그림 대신 서버가 만든 SVG 한 조각이라 브라우저가 읽을 것이 없어 빨리 뜬다(자비스12 2026-08-28).

값은 하나도 안 바꾼다 — 자비스4 와 같은 자료(jarvis4_data.get_chart_bundle · get_intraday_chart · get_daily_frame)를 그대로 그린다.
폰 전용 규칙(@media max-width:600px)은 두지 않는다(CLAUDE.md 12 — 폰 규칙은 mobile_ui 에만).
"""

from __future__ import annotations

import html

MODULE_REVISION = 2026110401

# 색은 **한국장 색**이다 — 오른 쪽 빨강 · 내린 쪽 파랑(자비스13 표·지수 칸·당일 차트와 같다 · j4-up/j4-down). 자비스12 는 미국 색
# (초록·빨강)이라 그대로 옮기면 한 화면에서 같은 빨강이 「올랐다」와 「내렸다」 두 뜻이 된다. 모양만 자비스12 형식이다.
UP = "#ff5b5b"        # 기준선 위
DOWN = "#4da6ff"      # 기준선 아래
MA20 = "#ffb020"      # 20선 — 주황
MA50 = "#c084fc"      # 50선 — 보라
CANDLE_SESSIONS = 120  # 일봉 봉차트 여섯 달(자비스12 와 같다 — 180개면 폰 작은 칸에서 봉이 1px 도 안 돼 뭉친다)

CSS = """<style>
.j13-chart-grid{display:grid;gap:.7rem;margin:.3rem 0 .6rem;grid-template-columns:repeat(2,minmax(0,1fr))}
@media (min-width:1201px){.j13-chart-grid{grid-template-columns:repeat(4,minmax(0,1fr))}}
.j13-chart-box{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.14);border-radius:12px;padding:.45rem .55rem .35rem;min-width:0}
.j13-chart-name{color:#9dccff;font-size:.95rem;font-weight:800;margin-bottom:.15rem}
.j13-chart-when{color:#7d8798;font-size:.72rem;font-weight:700;margin-top:.2rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.j13-pretty-chart{display:block;width:100%;height:132px;border-radius:8px;background:rgba(0,0,0,.22)}
.j13cz{position:relative}
.j13cz-tap{position:absolute;opacity:0;pointer-events:none;width:0;height:0;margin:0}
label.j13cz-cell{display:block;cursor:zoom-in}
.j13cz-scrim{position:fixed;inset:0;z-index:2147483646;cursor:zoom-out;background:rgba(1,8,22,.8);opacity:0;visibility:hidden;
  transition:opacity .3s ease,visibility 0s linear .56s}
.j13cz-pop{position:fixed;left:50%;top:50%;z-index:2147483647;cursor:zoom-out;width:min(calc(100vw - 16px),960px);
  height:min(calc(100dvh - 16px),760px);box-sizing:border-box;padding:16px 14px 12px;border-radius:22px;background:#0d2344;
  border:1px solid rgba(157,204,255,.45);box-shadow:0 18px 50px rgba(0,0,0,.6);display:flex;flex-direction:column;gap:8px;
  opacity:0;visibility:hidden;pointer-events:none;transform:translate(-50%,-50%) scale(.55);
  transition:transform .56s cubic-bezier(.5,-.18,.72,.18),opacity .56s cubic-bezier(.7,0,.84,0),visibility 0s linear .56s}
.j13cz-t0:checked ~ .j13cz-s0,.j13cz-t1:checked ~ .j13cz-s1,.j13cz-t2:checked ~ .j13cz-s2,.j13cz-t3:checked ~ .j13cz-s3{
  opacity:1;visibility:visible;transition:opacity .3s ease,visibility 0s}
.j13cz-t0:checked ~ .j13cz-p0,.j13cz-t1:checked ~ .j13cz-p1,.j13cz-t2:checked ~ .j13cz-p2,.j13cz-t3:checked ~ .j13cz-p3{
  opacity:1;visibility:visible;pointer-events:auto;transform:translate(-50%,-50%) scale(1);
  transition:transform .9s cubic-bezier(.34,1.56,.64,1),opacity .36s ease,visibility 0s}
.j13cz-name{color:#9dccff;font-size:1.15rem;font-weight:800}
.j13cz-draw{display:none}
.j13cz-pop svg.j13-pretty-chart{flex:1 1 auto!important;height:auto!important;min-height:0!important}
.j13cz-when{color:#7d8798;font-size:.78rem;font-weight:700}
.j13cz-close{align-self:center;font-size:.78rem;color:#8fb4de}
body:has(.j13cz-tap:checked) div.st-key-j13b_nav_controls,body:has(.j13cz-tap:checked) .j13b-bottom-nav{visibility:hidden!important}
@media (orientation:portrait){.j13cz-pop{height:calc((100dvh - 16px) / 2)}}
@media (prefers-reduced-motion:reduce){.j13cz-pop,.j13cz-scrim{transition:none!important}}
</style>"""

# 칸을 누르면(숨은 스위치가 켜지면) 그 칸의 그림을 큰 창의 빈자리 앞에 베껴 넣는다 — 자비스12 _ZOOM_CLONE_JS 와 같다(이름만 j13).
CLONE_JS = """
(function () {
  if (window.__j13ZoomClone) { return; }
  window.__j13ZoomClone = 1;
  document.addEventListener('change', function (ev) {
    var tap = ev.target;
    if (!tap || !tap.classList || !tap.classList.contains('j13cz-tap') || !tap.checked) { return; }
    var m = /(?:^|\\s)j13cz-t(\\d+)(?:\\s|$)/.exec(tap.className);
    var root = tap.closest('.j13cz');
    if (!m || !root) { return; }
    var pop = root.querySelector('.j13cz-p' + m[1]);
    var slot = pop && pop.querySelector('.j13cz-draw');
    if (!slot || pop.querySelector('svg')) { return; }
    var cell = root.querySelectorAll('.j13cz-cell')[+m[1]];
    var svg = cell && cell.querySelector('svg');
    if (svg) { pop.insertBefore(svg.cloneNode(true), slot); }
  }, true);
})();
"""


def _clean(values) -> list:
    out = []
    for value in values or []:
        try:
            number = float(value)
        except (TypeError, ValueError):
            out.append(None)
            continue
        out.append(None if number != number else number)
    return out


def payload_series(payload: dict, column: str) -> list:
    """차트 자료(price 표)에서 한 줄을 꺼낸다. 없으면 빈 목록."""
    frame = payload.get("price") if isinstance(payload, dict) else None
    if frame is None or column not in getattr(frame, "columns", []):
        return []
    return _clean(frame[column].tolist())


def _split_pieces(values: list, base: float) -> list:
    """기준선을 넘는 자리에서 선을 끊어 (위/아래, 점들)로 나눈다(자비스12 와 같은 계산)."""
    pieces, current, sign = [], [(0.0, base if values[0] == base else values[0])], None
    for index in range(len(values) - 1):
        now_value, next_value = values[index], values[index + 1]
        sign_now = 1 if now_value >= base else -1
        sign_next = 1 if next_value >= base else -1
        if sign is None:
            sign = sign_now if now_value != base else sign_next
        if sign_next == sign or next_value == base:
            current.append((float(index + 1), next_value))
            continue
        share = (base - now_value) / (next_value - now_value) if next_value != now_value else 0.0
        crossing = index + share
        current.append((crossing, base))
        pieces.append((sign, current))
        sign, current = sign_next, [(crossing, base), (float(index + 1), next_value)]
    pieces.append((sign if sign is not None else 1, current))
    return pieces


def pretty_svg(closes, *, base=None, ma20=None, ma50=None, height: int = 150) -> str:
    """시작가(당일은 전일 종가) 기준선 위아래를 갈라 그린 차트 · 20선 · 50선. 늘려도 선이 안 굵어진다(vector-effect)."""
    values = [v for v in _clean(closes) if v is not None]
    if len(values) < 2:
        return ""
    base = float(base) if base is not None else values[0]
    lines = []
    for color, series in ((MA20, ma20), (MA50, ma50)):
        cleaned = [(index, v) for index, v in enumerate(_clean(series)) if v is not None]
        if len(cleaned) >= 2:
            lines.append((color, cleaned))
    span_values = values + [base] + [v for _c, pairs in lines for _i, v in pairs]
    low, high = min(span_values), max(span_values)
    reach = (high - low) or 1.0
    pad = height * 0.06
    inner = height - pad * 2
    width = 300.0
    step = width / (len(values) - 1)

    def _y(value):
        return pad + inner - (float(value) - low) / reach * inner

    body = [f'<line x1="0" y1="{_y(base):.2f}" x2="{width:.0f}" y2="{_y(base):.2f}" stroke="rgba(255,255,255,.42)" '
            'stroke-width="1" stroke-dasharray="4 4" vector-effect="non-scaling-stroke"/>']
    for piece_sign, piece in _split_pieces(values, base):
        if len(piece) < 2:
            continue
        color = UP if piece_sign >= 0 else DOWN
        path = " ".join(f"{x * step:.2f},{_y(v):.2f}" for x, v in piece)
        area = f"{piece[0][0] * step:.2f},{_y(base):.2f} " + path + f" {piece[-1][0] * step:.2f},{_y(base):.2f}"
        body.append(f'<polygon points="{area}" fill="{color}" fill-opacity="0.16"/>')
        body.append(f'<polyline points="{path}" fill="none" stroke="{color}" stroke-width="1.9" vector-effect="non-scaling-stroke"/>')
    for color, pairs in lines:
        path = " ".join(f"{index * step:.2f},{_y(v):.2f}" for index, v in pairs)
        body.append(f'<polyline points="{path}" fill="none" stroke="{color}" stroke-width="1.4" stroke-opacity=".95" '
                    'vector-effect="non-scaling-stroke"/>')
    return (f'<svg class="j13-pretty-chart" viewBox="0 0 {width:.0f} {height}" preserveAspectRatio="none">'
            + "".join(body) + "</svg>")


def candle_svg(frame, *, sessions: int = CANDLE_SESSIONS) -> str:
    """일봉 **봉차트** — Open·High·Low·Close 칸이 있는 표(자비스4 get_daily_frame). 오른 날 빨강 · 내린 날 파랑 ·
    20선·50선은 그 표 종가로 센다(get_chart_bundle 과 같은 셈 · rolling 20/50). 못 그리면 빈 글자(부르는 쪽이 선 그림으로)."""
    try:
        if frame is None or not {"Open", "High", "Low", "Close"}.issubset(frame.columns):
            return ""
        closes = frame["Close"].astype(float)
        ma20_all, ma50_all = closes.rolling(20).mean(), closes.rolling(50).mean()
        tail = frame.tail(sessions)
        ma20s, ma50s = _clean(ma20_all.tail(sessions).tolist()), _clean(ma50_all.tail(sessions).tolist())
        rows = [_clean([o, h, l, c]) for o, h, l, c in zip(tail["Open"], tail["High"], tail["Low"], tail["Close"])]
    except Exception:
        return ""
    keep = [index for index, row in enumerate(rows) if all(v is not None and v > 0 for v in row)]
    if len(keep) < 2:
        return ""
    lines = []
    for color, series in ((MA20, ma20s), (MA50, ma50s)):
        cleaned = [(place, series[index]) for place, index in enumerate(keep) if index < len(series) and series[index] is not None]
        if len(cleaned) >= 2:
            lines.append((color, cleaned))
    picked = [rows[index] for index in keep]
    width, height = 10 * len(picked), 600
    span_values = [v for row in picked for v in (row[1], row[2])] + [v for _c, pairs in lines for _i, v in pairs]
    low, high = min(span_values), max(span_values)
    reach = (high - low) or 1.0
    pad = height * 0.06
    inner = height - pad * 2

    def _y(value):
        return round(pad + inner - (float(value) - low) / reach * inner)

    wicks, bodies = {True: [], False: []}, {True: [], False: []}
    for index, (o, h, l, c) in enumerate(picked):
        rising = c >= o
        wicks[rising].append(f"M{index * 10 + 5} {_y(h)}V{_y(l)}")
        top, bottom = _y(max(o, c)), _y(min(o, c))
        bodies[rising].append(f"M{index * 10 + 2} {top}h6v{max(bottom - top, 2)}h-6z")
    body = []
    for rising, color in ((True, UP), (False, DOWN)):
        if wicks[rising]:
            body.append(f'<path d="{"".join(wicks[rising])}" stroke="{color}" stroke-width="1" fill="none" '
                        'vector-effect="non-scaling-stroke"/>')
            body.append(f'<path d="{"".join(bodies[rising])}" fill="{color}"/>')
    for color, pairs in lines:
        path = " ".join(f"{place * 10 + 5},{_y(v)}" for place, v in pairs)
        body.append(f'<polyline points="{path}" fill="none" stroke="{color}" stroke-width="1.4" stroke-opacity=".95" '
                    'vector-effect="non-scaling-stroke"/>')
    return (f'<svg class="j13-pretty-chart j13-candle-chart" viewBox="0 0 {width} {height}" preserveAspectRatio="none">'
            + "".join(body) + "</svg>")


def zoom_html(boxes: list, zoom: str) -> str:
    """(이름, 그림 svg, 기준 시각) 칸 여럿을 **누르면 크게 뜨는** 한 판으로 싼다. zoom 은 한 화면에서 겹치면 안 된다(체크칸 id 앞머리).
    스위치는 맨 앞에 둔다 — 뒤의 칸·창을 「~」로 집으려면 스위치가 앞서야 한다. 칸은 넷까지(CSS t0~t3)."""
    boxes = list(boxes)[:4]

    def _when(when, tag):
        return (f"<{tag} class='j13-chart-when' >기준 {html.escape(str(when)[:16].replace('T', ' '))}</{tag}>"
                if when else "")

    taps = "".join(f"<input type='checkbox' id='{zoom}-{index}' class='j13cz-tap j13cz-t{index}'>" for index in range(len(boxes)))
    cells = "".join(
        f"<label for='{zoom}-{index}' class='j13-chart-box j13cz-cell'><div class='j13-chart-name'>{html.escape(name)}</div>{drawing}"
        + _when(when, "div") + "</label>"
        for index, (name, drawing, when) in enumerate(boxes))
    pops = "".join(
        f"<label for='{zoom}-{index}' class='j13cz-scrim j13cz-s{index}' aria-hidden='true'></label>"
        f"<label for='{zoom}-{index}' class='j13cz-pop j13cz-p{index}'><span class='j13cz-name'>{html.escape(name)}</span>"
        "<i class='j13cz-draw'></i>"
        + (f"<span class='j13cz-when'>기준 {html.escape(str(when)[:16].replace('T', ' '))}</span>" if when else "")
        + "<span class='j13cz-close'>다시 누르면 닫힘</span></label>"
        for index, (name, drawing, when) in enumerate(boxes))
    return f"{CSS}<div class='j13cz'>{taps}<div class='j13-chart-grid'>{cells}</div>{pops}</div>"


def boxes_for(code: str, data) -> list:
    """한 종목의 당일 · 일봉(봉차트) · 주봉 · 월봉 칸 — 자비스12 「📊 당일 · 일봉 · 주봉 · 월봉」과 같은 차례.
    data 는 jarvis4_data(얼린 파일 · 부르기만). 못 받은 칸은 빼고(없는 것을 있는 것처럼 그리지 않는다)."""
    boxes = []
    try:
        intraday = data.get_intraday_chart(code)
    except Exception:
        intraday = None
    if isinstance(intraday, dict) and intraday.get("ok"):
        frame = intraday.get("price")
        column = frame.columns[0] if frame is not None and len(getattr(frame, "columns", [])) else None
        drawing = pretty_svg(frame[column].tolist(), base=intraday.get("prev_close")) if column is not None else ""
        if drawing:
            boxes.append(("당일", drawing, intraday.get("source_time") or ""))
    try:
        bundle = data.get_chart_bundle(code)
    except Exception:
        bundle = {}
    charts = (bundle or {}).get("charts") or {}
    for name in ("일봉", "주봉", "월봉"):
        payload = charts.get(name) or {}
        drawing = ""
        if name == "일봉":
            try:
                drawing = candle_svg(data.get_daily_frame(code, ttl_seconds=300))
            except Exception:
                drawing = ""
        if not drawing and payload.get("ok"):
            drawing = pretty_svg(payload_series(payload, "Close"), ma20=payload_series(payload, "MA20"),
                                 ma50=payload_series(payload, "MA50"))
        if drawing:
            boxes.append((name, drawing, ""))
    return boxes
