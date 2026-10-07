"""파트별 성적표 — **나스닥 종합과 견줘 보기** (2026-10-07 상하님 지시).

상하님 — *"클릭하면 나스닥 종합주가와 테마 5개·상승장·하락 후 반등장 비교 그래프 /
나스닥 대 테마 5개 비교 그래프 / 나스닥 대 상승장·하락 후 반등장 비교 그래프 — 이렇게
도표로, 일별·주별·월별 차트"* · *"나스닥 그래프는 두껍게 투명도가 있게"* ·
*"기간 고르기 하면 그때 종목들이 나오게"*. 디자인 2판(같은 날 상하님께 보여 드린 것)
그대로 만든다 — 상하님이 "나머지는 너가 권하는 대로" 하셨다.

**무엇을 견주나** — 저장해 둔 목록을 **산 날마다 같은 돈으로** 다음 거래일 시가(저장된
매수금액)에 샀다고 치고, 나스닥 종합도 **같은 날 같은 돈으로** 그날 시가에 샀다고 친다.
  · 쌓인 수익(선) — 그날까지 산 것을 모두 들고 있다면 몇 % 인가(날마다 종가).
  · 산 날마다(막대) — 그날 산 것이 마지막 날까지 몇 % 인가. 주별·월별은 그 안의 산 날 평균.
나스닥은 견주는 파트가 **산 날에만** 산다 — 그래야 같은 날 같은 돈이다. 「세 파트
한눈에」의 나스닥은 세 파트 중 하나라도 산 날마다 산 것이다.

**계산은 이 파일 한 곳**이다. 화면(pages/2_자비스3.py)은 어느 줄을 넣을지(기간)만
골라 넘기고, 받은 값으로 그림만 그린다. 값을 못 잰 줄(매수금액 없음 · 주가 없음)은
**세지 않는다. 0으로 채우지 않는다** — 0이면 본전으로 읽혀 안 잰 것과 구별이 안 된다.
"""

from __future__ import annotations

import html
import math
from datetime import date, timedelta
from zoneinfo import ZoneInfo

# 계산이나 돌려주는 값을 바꾸면 올린다 — 페이지가 옛 모듈을 다시 읽게(CLAUDE.md 11과 같은 까닭).
MODULE_REVISION = 2026100701

PARTS = ("theme15", "breakout", "crash")
PART_NAMES = {
    "theme15": "상위 테마 5개 (1~3위)",
    "breakout": "상승장 (신고가 눌림매수)",
    "crash": "급락 후 반등장 (낙폭종목)",
}
# 성적표 막대 색(_SCORECARD_PARTS)과 같은 빛 — 어두운 바탕에서 선이 보이게 한 치수 밝게.
PART_COLORS = {"theme15": "#ef5b50", "breakout": "#22b884", "crash": "#f2a33a"}
TABS = (
    ("all", "세 파트 한눈에", PARTS),
    ("theme", "상위 테마 5개", ("theme15",)),
    ("swing", "상승장 · 급락 후 반등장", ("breakout", "crash")),
)
TAB_PARTS = {key: parts for key, _label, parts in TABS}
PERIODS = (("d", "일별"), ("w", "주별"), ("m", "월별"))
VIEWS = (("line", "쌓인 수익 (선)"), ("bar", "산 날마다 (막대)"))
# 나스닥 띠 — 굵고 옅게(상하님 지시). 선 굵기는 화면에서 늘려도 그대로다(vector-effect).
NASDAQ_COLOR = "rgba(170,182,204,.42)"
NASDAQ_WIDTH = 10
# 일별 막대는 한 화면에 이만큼만 — 폰 폭(약 350px)에 넷씩 묶인 막대가 이보다 많으면
# 1px 도 안 돼 뭉친다. 주별·월별은 모두 그린다.
DAILY_BAR_KEEP = 30
_NY = ZoneInfo("America/New_York")


def _num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _ny_date(stamp) -> date:
    try:
        if getattr(stamp, "tzinfo", None) is not None:
            stamp = stamp.tz_convert(_NY)
        return stamp.date()
    except Exception:
        return date.fromisoformat(str(stamp)[:10])


def _series_by_day(frame, column: str, since: date | None = None) -> dict:
    """표 한 칸을 {뉴욕 날짜: 값} 으로(날짜 순). 빈값은 뺀다. since 앞 날은 버린다."""
    out = {}
    if frame is None or column not in getattr(frame, "columns", ()):
        return out
    series = frame[column]
    try:
        index = series.index
        if getattr(index, "tz", None) is not None:
            index = index.tz_convert(_NY)
        days = list(index.date)
    except Exception:
        days = [_ny_date(stamp) for stamp in series.index]
    for day, value in zip(days, series.tolist()):
        if since is not None and day < since:
            continue
        number = _num(value)
        if number is not None and number > 0:
            out[day] = number
    return dict(sorted(out.items()))


def compute(rows, frames: dict, ixic, *, last_day: date | None = None) -> dict:
    """견주기 값 한 벌.

    rows    — 저장 목록 줄들(이미 기간으로 골라 넘긴다). trade_date·list_kind·code·buy_open 을 본다.
    frames  — {종목: 일봉 표(Close 칸)}.
    ixic    — 나스닥 종합 일봉 표(Open·Close 칸).
    last_day — 이 날까지만 센다(기간 고르기의 끝일). 없으면 받은 값 끝까지.
    """
    import bisect

    import numpy as np

    empty = {"days": [], "last": "", "parts": {}, "nasdaq": {}, "rows": 0}
    listed_rows = []
    for row in rows or []:
        kind = str(row.get("list_kind") or "")
        if kind not in PARTS:
            continue
        buy = _num(row.get("buy_open"))
        code = str(row.get("code") or "").strip().upper()
        if not buy or buy <= 0 or not code:
            continue
        try:
            listed = date.fromisoformat(str(row.get("trade_date") or "")[:10])
        except ValueError:
            continue
        listed_rows.append((kind, listed, code, buy, str(row.get("name") or code)))
    if not listed_rows:
        return empty
    since = min(item[1] for item in listed_rows)
    # 나스닥 이력은 25년치라 산 날 앞은 미리 버린다(줄마다 25년을 훑지 않게).
    ix_close = _series_by_day(ixic, "Close", since)
    ix_open = _series_by_day(ixic, "Open", since)
    calendar = [day for day in ix_close if day in ix_open and (last_day is None or day <= last_day)]
    if not calendar:
        return empty

    picked = []
    for kind, listed, code, buy, name in listed_rows:
        # 목록을 찍은 날 **다음 거래일**이 산 날이다(저장된 매수금액 = 그날 시가).
        place = bisect.bisect_right(calendar, listed)
        if place >= len(calendar):
            continue                    # 아직 안 산 줄(다음 장이 안 열렸다)
        picked.append((kind, calendar[place], code, buy, name))
    if not picked:
        return empty
    first = min(item[1] for item in picked)
    days = [day for day in calendar if day >= first]
    index = {day: place for place, day in enumerate(days)}
    count = len(days)
    codes = sorted({item[2] for item in picked})
    column = {code: place for place, code in enumerate(codes)}
    closes = np.full((count, len(codes)), np.nan)
    for code in codes:
        by_day = _series_by_day((frames or {}).get(code), "Close", since - timedelta(days=10))
        last_seen = np.nan
        # 그 종목이 쉰 날(거래 정지 등)은 앞날 값을 그대로 쓴다 — 들고 있는 값이 그대로다.
        earlier = [value for day, value in by_day.items() if day < days[0]]
        if earlier:
            last_seen = earlier[-1]
        for place, day in enumerate(days):
            if day in by_day:
                last_seen = by_day[day]
            closes[place, column[code]] = last_seen
    ix_c = np.array([ix_close[day] for day in days])

    parts = {}
    union = {key: set() for key in TAB_PARTS}
    for kind in PARTS:
        mine = [item for item in picked if item[0] == kind]
        if not mine:
            continue
        cohorts = {}
        for _kind, bought, code, buy, name in mine:
            cohorts.setdefault(bought, []).append((code, buy, name))
        stack = []
        bars = []
        per_stock = {}
        for bought in sorted(cohorts):
            start = index[bought]
            members = cohorts[bought]
            ratio = np.column_stack([closes[:, column[code]] / buy for code, buy, _n in members])
            ratio[:start, :] = np.nan
            usable = ~np.all(np.isnan(ratio), axis=1)
            line = np.full(count, np.nan)
            if usable.any():
                line[usable] = np.nanmean(ratio[usable], axis=1)
            if np.isnan(line[-1]):
                continue                # 끝날 값을 못 잰 묶음 — 세지 않는다
            stack.append(line)
            nq_last = ix_c[-1] / ix_open[bought] - 1.0
            bars.append([bought.isoformat(), round((line[-1] - 1.0) * 100.0, 2),
                         round(nq_last * 100.0, 2), len(members)])
            for place, (code, buy, name) in enumerate(members):
                value = ratio[-1, place]
                if np.isnan(value):
                    continue
                slot = per_stock.setdefault(code, [name, [], []])
                slot[1].append((value - 1.0) * 100.0)
                slot[2].append(nq_last * 100.0)
            for key, tab_parts in TAB_PARTS.items():
                if kind in tab_parts:
                    union[key].add(bought)
        if not stack:
            continue
        matrix = np.vstack(stack)
        active = ~np.isnan(matrix)
        held = active.sum(axis=0)
        total = np.where(active, matrix, 0.0).sum(axis=0)
        cum = [None if held[place] == 0 else round((total[place] / held[place] - 1.0) * 100.0, 2)
               for place in range(count)]
        stocks = sorted(
            ([code, name, len(gains), round(sum(gains) / len(gains), 2), round(sum(nqs) / len(nqs), 2)]
             for code, (name, gains, nqs) in per_stock.items()),
            key=lambda item: (-item[3], item[0]))
        parts[kind] = {"cum": cum, "cohorts": bars, "rows": sum(item[2] for item in stocks),
                       "stocks": stocks}

    nasdaq = {}
    for key, buy_days in union.items():
        if not buy_days:
            continue
        opens = sorted(buy_days)
        series = []
        for place, day in enumerate(days):
            held_days = [ix_open[b] for b in opens if b <= day]
            series.append(None if not held_days
                          else round((sum(ix_c[place] / value for value in held_days) / len(held_days) - 1.0) * 100.0, 2))
        nasdaq[key] = series
    return {"days": [day.isoformat() for day in days], "last": days[-1].isoformat(),
            "parts": parts, "nasdaq": nasdaq, "rows": sum(p["rows"] for p in parts.values())}


# ── 묶기(일별·주별·월별) ────────────────────────────────────────────────────────

def bucket(day_iso: str, period: str, many_years: bool = False) -> tuple:
    """(정렬 열쇠, 라벨). 주는 그 주 월요일, 달은 그 달."""
    day = date.fromisoformat(day_iso)
    if period == "w":
        monday = day - timedelta(days=day.weekday())
        return monday.isoformat(), f"{monday.month}/{monday.day} 주"
    if period == "m":
        label = f"{day.year % 100}.{day.month:02d}" if many_years else f"{day.month}월"
        return f"{day.year}-{day.month:02d}", label
    return day_iso, f"{day.month}/{day.day}"


def line_points(days: list, series: list, period: str) -> list:
    """[(라벨, 값)] — 묶음마다 **마지막 날** 값(쌓인 수익은 그때까지의 결과다)."""
    many = len({d[:4] for d in days}) > 1
    out: list = []
    for day, value in zip(days, series):
        key, label = bucket(day, period, many)
        if out and out[-1][0] == key:
            if value is not None:
                out[-1] = (key, label, value)
        else:
            out.append((key, label, value))
    return [(label, value) for _key, label, value in out]


def bar_groups(cohorts: list, period: str, many_years: bool = False) -> dict:
    """{열쇠: (라벨, 파트 평균, 나스닥 평균, 산 날 수)} — 묶음 안의 산 날 평균."""
    groups: dict = {}
    for day, gain, nq, _n in cohorts:
        key, label = bucket(day, period, many_years)
        slot = groups.setdefault(key, [label, [], []])
        slot[1].append(gain)
        slot[2].append(nq)
    return {key: (label, sum(g) / len(g), sum(n) / len(n), len(g)) for key, (label, g, n) in groups.items()}


# ── 그리기 ─────────────────────────────────────────────────────────────────────

def _fmt(value) -> str:
    return "—" if value is None else f"{value:+.1f}%"


def _tone(value) -> str:
    # 미국장 색 — 오르면 코발트, 내리면 붉은색(화면 다른 곳의 _sign_color 와 같다).
    return "#9aa0aa" if value is None else ("#4da6ff" if value >= 0 else "#ff5b5b")


def _nice_range(values: list) -> tuple:
    finite = [v for v in values if v is not None]
    low, high = (min(finite + [0.0]), max(finite + [0.0])) if finite else (-1.0, 1.0)
    if high - low < 2.0:
        middle = (high + low) / 2.0
        low, high = middle - 1.0, middle + 1.0
    raw = (high - low) / 4.0
    magnitude = 10 ** math.floor(math.log10(raw))
    step = next(m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= raw)
    low = math.floor(low / step) * step
    high = math.ceil(high / step) * step
    ticks, tick = [], low
    while tick <= high + step * 0.01:
        ticks.append(round(tick, 6))
        tick += step
    return low, high, ticks


def _frame(svg_body: str, ticks: list, low: float, high: float, labels: list) -> str:
    """눈금(글자)은 그림 밖 HTML 로 — 그림은 가로로 늘려 그려도 글자는 안 찌그러진다."""
    span = (high - low) or 1.0
    y_labels = "".join(
        f"<span style='top:{(high - tick) / span * 100:.2f}%'>{tick:+g}%</span>" for tick in ticks)
    x_labels = "".join(
        f"<span style='left:{left:.2f}%'>{html.escape(text)}</span>" for left, text in labels)
    return (f"<div class='j3vx-plot'><div class='j3vx-y'>{y_labels}</div>"
            f"<div class='j3vx-area'><svg viewBox='0 0 1000 400' preserveAspectRatio='none' "
            f"class='j3vx-svg'>{svg_body}</svg><div class='j3vx-x'>{x_labels}</div></div></div>")


def _grid(ticks: list, y) -> str:
    return "".join(
        f"<line x1='0' x2='1000' y1='{y(tick):.1f}' y2='{y(tick):.1f}' "
        f"stroke='{'rgba(255,255,255,.35)' if abs(tick) < 1e-9 else 'rgba(255,255,255,.07)'}' "
        "stroke-width='1' vector-effect='non-scaling-stroke'/>" for tick in ticks)


def _x_labels(count: int, texts: list, place) -> list:
    if not count:
        return []
    want = min(count, 6)
    picks = sorted({round(i * (count - 1) / max(want - 1, 1)) for i in range(want)})
    return [(place(i), texts[i]) for i in picks]


def line_chart_html(data: dict, tab: str, period: str) -> str:
    parts = [kind for kind in TAB_PARTS.get(tab, PARTS) if kind in data.get("parts", {})]
    days = data.get("days") or []
    if not parts or not days:
        return ""
    series = {"_nq": line_points(days, data["nasdaq"].get(tab) or [None] * len(days), period)}
    for kind in parts:
        series[kind] = line_points(days, data["parts"][kind]["cum"], period)
    labels = [label for label, _v in series["_nq"]]
    count = len(labels)
    values = [v for pts in series.values() for _l, v in pts]
    low, high, ticks = _nice_range(values)

    def x(i):
        return 500.0 if count == 1 else i * 1000.0 / (count - 1)

    def y(value):
        return (high - value) / ((high - low) or 1.0) * 400.0

    def path(points):
        pieces, run = [], []
        for i, (_label, value) in enumerate(points):
            if value is None:
                if run:
                    pieces.append(run)
                run = []
                continue
            run.append(f"{x(i):.1f},{y(value):.1f}")
        if run:
            pieces.append(run)
        return pieces

    body = [_grid(ticks, y)]
    for run in path(series["_nq"]):
        body.append(f"<polyline points='{' '.join(run)}' fill='none' stroke='{NASDAQ_COLOR}' "
                    f"stroke-width='{NASDAQ_WIDTH}' stroke-linecap='round' stroke-linejoin='round' "
                    "vector-effect='non-scaling-stroke'/>")
    dot = 6 if period != "d" or count <= 40 else 0
    for kind in parts:
        color = PART_COLORS[kind]
        for run in path(series[kind]):
            body.append(f"<polyline points='{' '.join(run)}' fill='none' stroke='{color}' "
                        "stroke-width='2.4' stroke-linejoin='round' vector-effect='non-scaling-stroke'/>")
            if dot:
                # 점은 길이 0 짜리 둥근 끝 선으로 찍는다 — 가로로 늘려 그려도 동그랗다.
                body.append(f"<path d='{''.join('M' + p + 'h0' for p in run)}' stroke='{color}' "
                            f"stroke-width='{dot}' stroke-linecap='round' fill='none' "
                            "vector-effect='non-scaling-stroke'/>")
    return _frame("".join(body), ticks, low, high,
                  _x_labels(count, labels, lambda i: x(i) / 10.0))


def bar_chart_html(data: dict, tab: str, period: str) -> tuple:
    """(그림, 덧붙일 말). 일별은 최근 DAILY_BAR_KEEP 일만 그린다."""
    parts = [kind for kind in TAB_PARTS.get(tab, PARTS) if kind in data.get("parts", {})]
    if not parts:
        return "", ""
    many = len({d[:4] for d in data.get("days") or []}) > 1
    groups = {kind: bar_groups(data["parts"][kind]["cohorts"], period, many) for kind in parts}
    nq_days: dict = {}
    for kind in parts:
        for day, _g, nq, _n in data["parts"][kind]["cohorts"]:
            nq_days[day] = nq
    nq_groups = bar_groups([[day, nq, nq, 1] for day, nq in sorted(nq_days.items())], period, many)
    keys = sorted(set(nq_groups) | {key for g in groups.values() for key in g})
    note = ""
    if period == "d" and len(keys) > DAILY_BAR_KEEP:
        note = f"일별 막대는 최근 {DAILY_BAR_KEEP}일만 그립니다(주별·월별은 전부)."
        keys = keys[-DAILY_BAR_KEEP:]
    if not keys:
        return "", ""
    labels = [(nq_groups.get(key) or next(g[key] for g in groups.values() if key in g))[0] for key in keys]
    values = [nq_groups[key][2] for key in keys if key in nq_groups]
    values += [g[key][1] for g in groups.values() for key in keys if key in g]
    low, high, ticks = _nice_range(values)
    slot = 1000.0 / len(keys)
    lanes = 1 + len(parts)
    width = slot * 0.78 / lanes

    def y(value):
        return (high - value) / ((high - low) or 1.0) * 400.0

    body = [_grid(ticks, y)]
    for i, key in enumerate(keys):
        left = i * slot + slot * 0.11
        entries = [("나스닥 종합", NASDAQ_COLOR, nq_groups.get(key, (None, None, None))[2])]
        entries += [(PART_NAMES[kind], PART_COLORS[kind], (groups[kind].get(key) or (None, None))[1])
                    for kind in parts]
        for lane, (name, color, value) in enumerate(entries):
            if value is None:
                continue
            top, bottom = sorted((y(value), y(0.0)))
            body.append(f"<rect x='{left + lane * width:.1f}' y='{top:.1f}' width='{width:.1f}' "
                        f"height='{max(bottom - top, 1.5):.1f}' fill='{color}'>"
                        f"<title>{html.escape(labels[i])} · {html.escape(name)} {_fmt(value)}</title></rect>")
    return (_frame("".join(body), ticks, low, high,
                   _x_labels(len(keys), labels, lambda i: (i + 0.5) * slot / 10.0)), note)


def cards_html(data: dict, tab: str) -> str:
    cards = []
    for kind in TAB_PARTS.get(tab, PARTS):
        part = data.get("parts", {}).get(kind)
        if not part:
            cards.append(f"<div class='j3vx-card'><b style='color:{PART_COLORS[kind]}'>"
                         f"{html.escape(PART_NAMES[kind])}</b><div class='j3vx-say'>이 기간에는 산 날이 없습니다.</div></div>")
            continue
        mine = next((v for v in reversed(part["cum"]) if v is not None), None)
        # 그 파트가 **산 날에만** 나스닥을 샀다면 — 카드는 파트마다 제 나스닥과 견준다.
        solo = compute_nasdaq_for(data, [c[0] for c in part["cohorts"]])
        days = len(part["cohorts"])
        beat = sum(1 for _d, gain, nq, _n in part["cohorts"] if gain > nq)
        if mine is None or solo is None:
            gap_text = ""
        else:
            gap = mine - solo
            gap_text = f"나스닥보다 {abs(gap):.1f}% {'더 올랐습니다' if gap >= 0 else '덜 올랐습니다'} · "
        # 한 장을 낮게 — 폰에서 한 줄에 한 장씩 세 장이 쌓여도 길지 않게(2026-10-07 화면 확인).
        cards.append(
            f"<div class='j3vx-card'><b style='color:{PART_COLORS[kind]}'>{html.escape(PART_NAMES[kind])}</b>"
            f"<div class='j3vx-nums'><span class='j3vx-big' style='color:{_tone(mine)}'>{_fmt(mine)}</span>"
            f"<span class='j3vx-vs'>같은 날 나스닥 종합 <b style='color:{_tone(solo)}'>{_fmt(solo)}</b></span></div>"
            f"<div class='j3vx-say'>{gap_text}산 날 {days}일 중 {beat}일은 나스닥보다 나았습니다</div></div>")
    return "<div class='j3vx-cards'>" + "".join(cards) + "</div>"


def compute_nasdaq_for(data: dict, buy_days: list):
    """나스닥을 이 날들에만 샀다면 마지막 날 몇 % — 카드용. 막대 값(산 날마다)의 평균과 같다."""
    nq_by_day = {}
    for part in data.get("parts", {}).values():
        for day, _g, nq, _n in part["cohorts"]:
            nq_by_day[day] = nq
    picked = [nq_by_day[day] for day in buy_days if day in nq_by_day]
    return None if not picked else round(sum(picked) / len(picked), 2)


def legend_html(tab: str, data: dict) -> str:
    items = [f"<span><i class='j3vx-band'></i>나스닥 종합</span>"]
    items += [f"<span><i style='border-top:3px solid {PART_COLORS[kind]}'></i>{html.escape(PART_NAMES[kind])}</span>"
              for kind in TAB_PARTS.get(tab, PARTS) if kind in data.get("parts", {})]
    return "<div class='j3vx-legend'>" + "".join(items) + "</div>"


def stocks_html(data: dict, tab: str, *, names: dict | None = None, first: str = "", last: str = "") -> str:
    """기간 고르기의 「이 기간에 산 종목」 — 종목별로 묶어 잘 된 5 · 안 된 3, 나머지는 「다 보기」."""
    names = names or {}
    blocks = []
    for kind in TAB_PARTS.get(tab, PARTS):
        part = data.get("parts", {}).get(kind)
        if not part or not part.get("stocks"):
            continue
        stocks = part["stocks"]

        def line(item):
            code, name, times, gain, nq = item
            shown = names.get(code) or (name if name and name != code else code)
            label = html.escape(shown) + ("" if shown == code else f" <small>{html.escape(code)}</small>")
            return (f"<tr><td>{label}</td><td>{times}번</td>"
                    f"<td style='color:{_tone(gain)};font-weight:800'>{_fmt(gain)}</td>"
                    f"<td style='color:{_tone(nq)}'>{_fmt(nq)}</td></tr>")

        head = ("<tr><th>종목</th><th>산 횟수</th><th>평균 수익</th><th>같은 날 나스닥</th></tr>")
        if len(stocks) <= 8:
            table = f"<table class='j3vx-tbl'>{head}{''.join(line(s) for s in stocks)}</table>"
            more = ""
        else:
            table = (f"<table class='j3vx-tbl'>{head}{''.join(line(s) for s in stocks[:5])}"
                     "<tr><td colspan='4' class='j3vx-gap'>⋯</td></tr>"
                     f"{''.join(line(s) for s in stocks[-3:])}</table>")
            more = (f"<details class='j3vx-more'><summary>{len(stocks)}종목 다 보기</summary>"
                    f"<table class='j3vx-tbl'>{head}{''.join(line(s) for s in stocks)}</table></details>")
        blocks.append(
            f"<div class='j3vx-part'><div class='j3vx-part-head' style='color:{PART_COLORS[kind]}'>"
            f"{html.escape(PART_NAMES[kind])} · {part['rows']}번 샀음 · {len(stocks)}종목</div>{table}{more}</div>")
    if not blocks:
        return ""
    when = f"{first} ~ {last} · {last} 종가에 팔았다면" if first and last else ""
    return ("<div class='j3vx-list'><div class='j3vx-list-head'>이 기간에 산 종목"
            f"<small>{html.escape(when)}</small></div>" + "".join(blocks) + "</div>")


CSS = """
<style>
.j3vx{padding-top:12px;border-top:1px solid #1d3a63}
.j3vx-body{display:block}
/* 단추 — 성적표 기간 칩과 같은 결. 고른 탭은 보라 그라데이션, 고른 일별·선 등은 파랑. */
div[class*="st-key-j3vx_t_"] button,div[class*="st-key-j3vx_p_"] button,div[class*="st-key-j3vx_v_"] button{
  min-height:0!important;padding:.3rem .45rem!important;background:transparent!important;border:1px solid #1d3a63!important}
div[class*="st-key-j3vx_t_"] button{border-radius:10px!important}
div[class*="st-key-j3vx_p_"] button,div[class*="st-key-j3vx_v_"] button{border-radius:999px!important}
div[class*="st-key-j3vx_t_"] button p{font-size:.82rem!important;font-weight:700!important;color:#cfe0ff!important}
div[class*="st-key-j3vx_p_"] button p,div[class*="st-key-j3vx_v_"] button p{
  font-size:.76rem!important;font-weight:700!important;color:#8fb4de!important}
div[class*="st-key-j3vx_t_"] button[kind="primary"]{
  background:linear-gradient(90deg,#3b1a6b 0%,#7c3aed 100%)!important;border-color:#7c3aed!important}
div[class*="st-key-j3vx_p_"] button[kind="primary"],div[class*="st-key-j3vx_v_"] button[kind="primary"]{
  background:#2a4f8f!important;border-color:#4d7fd0!important}
div[class*="st-key-j3vx_t_"] button[kind="primary"] p,div[class*="st-key-j3vx_p_"] button[kind="primary"] p,
div[class*="st-key-j3vx_v_"] button[kind="primary"] p{color:#fff!important}
.j3vx-head{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:2px}
.j3vx-head b{font-size:1rem;color:#fff;font-weight:800}
.j3vx-head span{margin-left:auto;font-size:.76rem;color:#8fb4de}
.j3vx-help{font-size:.76rem;color:#8fb4de;margin:2px 0 8px}
.j3vx-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:8px;margin:4px 0 10px}
.j3vx-card{border:1px solid #1d3a63;border-radius:12px;padding:9px 11px;background:rgba(255,255,255,.02)}
.j3vx-card>b{display:block;font-size:.82rem;font-weight:800;margin-bottom:3px}
.j3vx-nums{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.j3vx-big{font-size:1.3rem;font-weight:900;line-height:1.15}
.j3vx-vs{font-size:.76rem;color:#8fb4de;white-space:nowrap}
.j3vx-say{font-size:.74rem;color:#dfe9ff;margin-top:3px;line-height:1.45}
.j3vx-legend{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:.76rem;color:#cfe0ff;margin:2px 0 6px}
.j3vx-legend span{display:flex;align-items:center;gap:6px}
.j3vx-legend i{display:inline-block;width:16px}
.j3vx-legend i.j3vx-band{width:22px;height:8px;border-radius:4px;background:rgba(170,182,204,.45)}
.j3vx-plot{display:flex;gap:6px;height:230px;margin-bottom:22px}
.j3vx-y{position:relative;width:44px;flex:0 0 44px}
.j3vx-y span{position:absolute;right:0;transform:translateY(-50%);font-size:.68rem;color:#8fa2bf;white-space:nowrap}
.j3vx-area{position:relative;flex:1 1 auto;min-width:0}
.j3vx-svg{display:block;width:100%;height:100%;overflow:visible}
.j3vx-x{position:absolute;left:0;right:0;top:100%;height:20px}
.j3vx-x span{position:absolute;top:4px;transform:translateX(-50%);font-size:.68rem;color:#8fa2bf;white-space:nowrap}
.j3vx-x span:first-child{transform:none}
.j3vx-x span:last-child{transform:translateX(-100%)}
.j3vx-note{font-size:.74rem;color:#6f93bd;line-height:1.6;margin-top:4px}
.j3vx-list{margin-top:12px;border-top:1px solid #1d3a63;padding-top:10px}
.j3vx-list-head{font-size:.95rem;font-weight:800;color:#fff;margin-bottom:6px}
.j3vx-list-head small{display:block;font-size:.74rem;font-weight:600;color:#8fb4de;margin-top:2px}
.j3vx-part{margin-bottom:12px}
.j3vx-part-head{font-size:.86rem;font-weight:800;padding:4px 0}
.j3vx-tbl{width:100%;border-collapse:collapse;font-size:.82rem;table-layout:fixed}
.j3vx-tbl th:first-child,.j3vx-tbl td:first-child{width:36%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.j3vx-tbl th{color:#8fb4de;font-weight:700;text-align:right;padding:4px 6px;border-bottom:1px solid #1d3a63}
.j3vx-tbl td{padding:4px 6px;text-align:right;color:#e6e6e6;border-bottom:1px solid rgba(157,204,255,.07)}
.j3vx-tbl th:first-child,.j3vx-tbl td:first-child{text-align:left}
.j3vx-tbl td small{color:#6f93bd;font-size:.7rem}
.j3vx-tbl td.j3vx-gap{text-align:center;color:#6f93bd}
.j3vx-more summary{cursor:pointer;font-size:.8rem;font-weight:700;color:#c084fc;padding:4px 0;list-style:none}
.j3vx-more summary::-webkit-details-marker{display:none}
.j3vx-more[open] summary{margin-bottom:4px}
</style>
"""
