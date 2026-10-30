"""한국테마 파트별 성적표 — **코스피와 견줘 보기** · 자비스13 전용 (2026-10-30 · 자비스12 의 「나스닥 종합과 견줘 보기」를 한국에 맞춰 옮김).

상하님 — *「둘 다 해라」* · *「자비스4 와 자비스12 둘 다 장점을 베낌을 해야 한다」*. 자비스12 의 성적표(2026-10-07 상하님 지시로
만든 것)를 한국 저장 목록(data/picklist/*.KR.csv · 2026-08-09~)에 댄다. 잣대는 2026-09-30 상하님이 정하신 것 —
**같은 날 코스피보다 나았나 + 실제로 벌었나 둘 다**.

**셈은 자비스12(jarvis12_scorecard_compare.compute)와 같다** — 그 파일은 자비스12 것이라 부르지 않고 셈을 베꼈다
(상하님 「다른 자비스도 연결하지 말라」). 저장 목록을 **산 날마다 같은 돈으로** 다음 거래일 시가(저장된 매수금액)에 샀다고
치고, 코스피도 **같은 날 같은 돈으로** 그날 시가에 샀다고 친다.
  · 쌓인 수익(선) — 그날까지 산 것을 모두 들고 있다면 몇 % 인가(날마다 종가).
  · 산 날마다(막대) — 그날 산 것이 마지막 날까지 몇 % 인가. 주별·월별은 그 안의 산 날 평균.

한국에서 더한 것
  · **다음 날 시가가 상한가면 못 산 줄**로 빼고 그 수를 따로 센다(가격제한폭 ±30% — 그 값에는 실제로 사기 어렵다).
  · 파트는 한국 화면 이름 그대로 넷 — 순위 7 · 상승장 · 눌림목 · 급락 후 반등장(저장 갈래 top7 · breakout · pullback · crash).

값을 못 잰 줄(매수금액 없음 · 주가 없음)은 **세지 않는다. 0으로 채우지 않는다** — 0이면 본전으로 읽혀 안 잰 것과 구별이 안 된다.
"""

from __future__ import annotations

import bisect
import html
import math
from datetime import date, timedelta

# 계산이나 돌려주는 값을 바꾸면 올리고 자비스13 의 _REQUIRED_J13_SCORECARD_REVISION 도 같이 올린다(규칙 11).
MODULE_REVISION = 2026103001

PARTS = ("top7", "breakout", "pullback", "crash")
PART_NAMES = {
    "top7": "매수심사결과 높은 순위 7",
    "breakout": "상승장 (신고가 눌림매수)",
    "pullback": "눌림목 종목 찾기",
    "crash": "급락 후 반등장 (낙폭종목)",
}
# 자비스12 성적표와 같은 빛(순위 파랑 · 상승장 초록 · 급락 주황) · 눌림목은 붉은 빛.
PART_COLORS = {"top7": "#4c9bff", "breakout": "#22b884", "pullback": "#ef5b50", "crash": "#f2a33a"}
TABS = (
    ("all", "네 파트 한눈에", PARTS),
    ("pick", "순위 7 · 눌림목", ("top7", "pullback")),
    ("swing", "상승장 · 급락 후 반등장", ("breakout", "crash")),
)
TAB_PARTS = {key: parts for key, _label, parts in TABS}
PERIODS = (("d", "일별"), ("w", "주별"), ("m", "월별"))
VIEWS = (("line", "쌓인 수익 (선)"), ("bar", "산 날마다 (막대)"))
# 코스피 띠 — 굵고 옅게(자비스12 의 나스닥 띠와 같은 모양 · 상하님 「두껍게 투명도가 있게」).
INDEX_NAME = "코스피"
INDEX_COLOR = "rgba(170,182,204,.42)"
INDEX_WIDTH = 10
# 일별 막대는 한 화면에 이만큼만 — 폰 폭에 막대 다섯이 묶이면 1px 도 안 돼 뭉친다.
DAILY_BAR_KEEP = 30
# 다음 날 시가가 전날 종가보다 이만큼 넘게 올라 있으면 상한가에 붙은 것으로 본다(±30% · 끝자리 반올림 여유 0.5%p).
LIMIT_UP_OPEN = 0.295


def _num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _day(stamp) -> date:
    try:
        return stamp.date()
    except Exception:
        return date.fromisoformat(str(stamp)[:10])


def series_by_day(frame, column: str, since: date | None = None) -> dict:
    """표 한 칸을 {날짜: 값} 으로(날짜 순). 빈값·0 은 뺀다. since 앞 날은 버린다. 한국 일봉은 날짜만 있다."""
    out = {}
    if frame is None or column not in getattr(frame, "columns", ()):
        return out
    series = frame[column]
    try:
        days = list(series.index.date)
    except Exception:
        days = [_day(stamp) for stamp in series.index]
    for day, value in zip(days, series.tolist()):
        if since is not None and day < since:
            continue
        number = _num(value)
        if number is not None and number > 0:
            out[day] = number
    return dict(sorted(out.items()))


def split_unfillable(rows, frames: dict) -> tuple[list, list]:
    """(살 수 있던 줄, 다음 날 시가가 상한가라 못 산 줄). 그날 종가를 모르면 살 수 있던 줄로 둔다(빼는 근거가 없다)."""
    ok, blocked = [], []
    for row in rows or []:
        buy = _num(row.get("buy_open"))
        code = str(row.get("code") or "").strip()
        try:
            listed = date.fromisoformat(str(row.get("trade_date") or "")[:10])
        except ValueError:
            ok.append(row)
            continue
        close = series_by_day((frames or {}).get(code), "Close").get(listed)
        if buy and close and buy / close - 1.0 >= LIMIT_UP_OPEN:
            blocked.append(row)
        else:
            ok.append(row)
    return ok, blocked


def compute(rows, frames: dict, index_frame, *, last_day: date | None = None) -> dict:
    """견주기 값 한 벌 — 자비스12 jarvis12_scorecard_compare.compute 의 셈 그대로(테마 비교표만 뺐다).

    rows        — 저장 목록 줄들(이미 기간으로 골라 넘긴다). trade_date·list_kind·code·buy_open 을 본다.
    frames      — {종목코드: 일봉 표(Close 칸)}.
    index_frame — 코스피 일봉 표(Open·Close 칸).
    last_day    — 이 날까지만 센다(마지막으로 끝난 장). 없으면 받은 값 끝까지.
    """
    import numpy as np

    empty = {"days": [], "last": "", "parts": {}, "index": {}, "rows": 0}
    listed_rows = []
    for row in rows or []:
        kind = str(row.get("list_kind") or "")
        if kind not in PARTS:
            continue
        buy = _num(row.get("buy_open"))
        code = str(row.get("code") or "").strip()
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
    ix_close = series_by_day(index_frame, "Close", since)
    ix_open = series_by_day(index_frame, "Open", since)
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
        by_day = series_by_day((frames or {}).get(code), "Close", since - timedelta(days=10))
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
        stack, bars, per_stock = [], [], {}
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
            ix_last = ix_c[-1] / ix_open[bought] - 1.0
            bars.append([bought.isoformat(), round((line[-1] - 1.0) * 100.0, 2),
                         round(ix_last * 100.0, 2), len(members)])
            for place, (code, buy, name) in enumerate(members):
                value = ratio[-1, place]
                if np.isnan(value):
                    continue
                # 같은 날 두 테마에 같이 든 종목은 하루로 센다(자비스12 · 2026-10-07 상하님 「이건 이해할 수 없다」).
                slot = per_stock.setdefault(code, [name, {}])
                slot[1].setdefault(bought, ((value - 1.0) * 100.0, ix_last * 100.0))
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
            ([code, name, len(by_day), round(sum(g for g, _n in by_day.values()) / len(by_day), 2),
              round(sum(n for _g, n in by_day.values()) / len(by_day), 2),
              min(by_day).isoformat(), max(by_day).isoformat()]
             for code, (name, by_day) in per_stock.items()),
            key=lambda item: (-item[3], item[0]))
        parts[kind] = {"cum": cum, "cohorts": bars, "rows": sum(item[2] for item in stocks), "stocks": stocks}

    index_lines = {}
    for key, buy_days in union.items():
        if not buy_days:
            continue
        opens = sorted(buy_days)
        series = []
        for place, day in enumerate(days):
            held_days = [ix_open[b] for b in opens if b <= day]
            series.append(None if not held_days
                          else round((sum(ix_c[place] / value for value in held_days) / len(held_days) - 1.0) * 100.0, 2))
        index_lines[key] = series
    return {"days": [day.isoformat() for day in days], "last": days[-1].isoformat(),
            "parts": parts, "index": index_lines, "rows": sum(p["rows"] for p in parts.values())}


def part_table(rows, frames: dict, index_frame, *, last_day: date | None = None) -> dict:
    """성적표 표 한 벌 — 파트마다 {산 줄 · 이익 난 줄 · 평균 · 같은 날 코스피 평균 · 코스피보다 나은 줄}.

    줄마다 따로 센다(같은 종목을 여러 날 샀으면 여러 줄) — 「이 파트를 고른 대로 샀다면」의 그대로다.
    """
    out = {kind: {"n": 0, "win": 0, "sum": 0.0, "ix_sum": 0.0, "beat": 0} for kind in PARTS}
    if not rows:
        return out
    since = None
    for row in rows:
        try:
            listed = date.fromisoformat(str(row.get("trade_date") or "")[:10])
        except ValueError:
            continue
        since = listed if since is None or listed < since else since
    if since is None:
        return out
    ix_close = series_by_day(index_frame, "Close", since)
    ix_open = series_by_day(index_frame, "Open", since)
    calendar = [day for day in ix_close if day in ix_open and (last_day is None or day <= last_day)]
    if not calendar:
        return out
    end = calendar[-1]
    for row in rows:
        kind = str(row.get("list_kind") or "")
        buy = _num(row.get("buy_open"))
        code = str(row.get("code") or "").strip()
        if kind not in out or not buy or buy <= 0 or not code:
            continue
        try:
            listed = date.fromisoformat(str(row.get("trade_date") or "")[:10])
        except ValueError:
            continue
        place = bisect.bisect_right(calendar, listed)
        if place >= len(calendar):
            continue
        bought = calendar[place]
        closes = series_by_day((frames or {}).get(code), "Close", since - timedelta(days=10))
        seen = [value for day, value in closes.items() if day <= end]
        if not seen:
            continue
        gain = seen[-1] / buy - 1.0
        ix_gain = ix_close[end] / ix_open[bought] - 1.0
        slot = out[kind]
        slot["n"] += 1
        slot["win"] += 1 if gain > 0 else 0
        slot["sum"] += gain * 100.0
        slot["ix_sum"] += ix_gain * 100.0
        slot["beat"] += 1 if gain > ix_gain else 0
    return out


# ── 묶기(일별·주별·월별) — 자비스12 와 같다 ─────────────────────────────────────

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
    """{열쇠: (라벨, 파트 평균, 코스피 평균, 산 날 수)} — 묶음 안의 산 날 평균."""
    groups: dict = {}
    for day, gain, ix, _n in cohorts:
        key, label = bucket(day, period, many_years)
        slot = groups.setdefault(key, [label, [], []])
        slot[1].append(gain)
        slot[2].append(ix)
    return {key: (label, sum(g) / len(g), sum(n) / len(n), len(g)) for key, (label, g, n) in groups.items()}


# ── 그리기 — 자비스12 와 같은 모양(꾸밈 이름 j3vx- 를 그대로 써 폰 규칙도 같이 탄다) ───────────

def fmt(value) -> str:
    return "—" if value is None else f"{value:+.1f}%"


def tone(value) -> str:
    # 이 화면의 _sign_color 와 같다 — 오르면 파랑, 내리면 빨강(2026-07-29 상하님).
    return "#9aa0aa" if value is None else ("#4da6ff" if value >= 0 else "#ff5b5b")


def _nice_range(values: list, parts: int = 4) -> tuple:
    finite = [v for v in values if v is not None]
    low, high = (min(finite + [0.0]), max(finite + [0.0])) if finite else (-1.0, 1.0)
    if high - low < 2.0:
        middle = (high + low) / 2.0
        low, high = middle - 1.0, middle + 1.0
    raw = (high - low) / float(parts)
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
    series = {"_ix": line_points(days, data["index"].get(tab) or [None] * len(days), period)}
    for kind in parts:
        series[kind] = line_points(days, data["parts"][kind]["cum"], period)
    labels = [label for label, _v in series["_ix"]]
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
    for run in path(series["_ix"]):
        body.append(f"<polyline points='{' '.join(run)}' fill='none' stroke='{INDEX_COLOR}' "
                    f"stroke-width='{INDEX_WIDTH}' stroke-linecap='round' stroke-linejoin='round' "
                    "vector-effect='non-scaling-stroke'/>")
    dot = 6 if period != "d" or count <= 40 else 0
    for kind in parts:
        color = PART_COLORS[kind]
        for run in path(series[kind]):
            body.append(f"<polyline points='{' '.join(run)}' fill='none' stroke='{color}' "
                        "stroke-width='2.4' stroke-linejoin='round' vector-effect='non-scaling-stroke'/>")
            if dot:
                body.append(f"<path d='{''.join('M' + p + 'h0' for p in run)}' stroke='{color}' "
                            f"stroke-width='{dot}' stroke-linecap='round' fill='none' "
                            "vector-effect='non-scaling-stroke'/>")
    return _frame("".join(body), ticks, low, high, _x_labels(count, labels, lambda i: x(i) / 10.0))


def bar_chart_html(data: dict, tab: str, period: str) -> tuple:
    """(그림, 덧붙일 말). 일별은 최근 몇 날만 그린다(막대가 뭉치지 않게)."""
    parts = [kind for kind in TAB_PARTS.get(tab, PARTS) if kind in data.get("parts", {})]
    if not parts:
        return "", ""
    many = len({d[:4] for d in data.get("days") or []}) > 1
    groups = {kind: bar_groups(data["parts"][kind]["cohorts"], period, many) for kind in parts}
    ix_days: dict = {}
    for kind in parts:
        for day, _g, ix, _n in data["parts"][kind]["cohorts"]:
            ix_days[day] = ix
    ix_groups = bar_groups([[day, ix, ix, 1] for day, ix in sorted(ix_days.items())], period, many)
    keys = sorted(set(ix_groups) | {key for g in groups.values() for key in g})
    note = ""
    keep = DAILY_BAR_KEEP if 1 + len(parts) <= 4 else DAILY_BAR_KEEP * 4 // (1 + len(parts))
    if period == "d" and len(keys) > keep:
        note = f"일별 막대는 최근 {keep}일만 그립니다(주별·월별은 전부)."
        keys = keys[-keep:]
    if not keys:
        return "", ""
    labels = [(ix_groups.get(key) or next(g[key] for g in groups.values() if key in g))[0] for key in keys]
    values = [ix_groups[key][2] for key in keys if key in ix_groups]
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
        entries = [(INDEX_NAME, INDEX_COLOR, ix_groups.get(key, (None, None, None))[2])]
        entries += [(PART_NAMES[kind], PART_COLORS[kind], (groups[kind].get(key) or (None, None))[1]) for kind in parts]
        for lane, (name, color, value) in enumerate(entries):
            if value is None:
                continue
            top, bottom = sorted((y(value), y(0.0)))
            body.append(f"<rect x='{left + lane * width:.1f}' y='{top:.1f}' width='{width:.1f}' "
                        f"height='{max(bottom - top, 1.5):.1f}' fill='{color}'>"
                        f"<title>{html.escape(labels[i])} · {html.escape(name)} {fmt(value)}</title></rect>")
    return (_frame("".join(body), ticks, low, high,
                   _x_labels(len(keys), labels, lambda i: (i + 0.5) * slot / 10.0)), note)


def index_for(data: dict, buy_days: list):
    """코스피를 이 날들에만 샀다면 마지막 날 몇 % — 카드용. 막대 값(산 날마다)의 평균과 같다."""
    by_day = {}
    for part in data.get("parts", {}).values():
        for day, _g, ix, _n in part["cohorts"]:
            by_day[day] = ix
    picked = [by_day[day] for day in buy_days if day in by_day]
    return None if not picked else round(sum(picked) / len(picked), 2)


def md(iso: str) -> str:
    """2026-07-30 → 7/30."""
    try:
        return f"{int(iso[5:7])}/{int(iso[8:10])}"
    except (TypeError, ValueError):
        return html.escape(str(iso or ""))


def cards_html(data: dict, tab: str) -> str:
    cards = []
    for kind in TAB_PARTS.get(tab, PARTS):
        part = data.get("parts", {}).get(kind)
        if not part:
            cards.append(f"<div class='j3vx-card'><b style='color:{PART_COLORS[kind]}'>"
                         f"{html.escape(PART_NAMES[kind])}</b><div class='j3vx-say'>이 기간에는 산 날이 없습니다.</div></div>")
            continue
        mine = next((v for v in reversed(part["cum"]) if v is not None), None)
        solo = index_for(data, [c[0] for c in part["cohorts"]])
        days = len(part["cohorts"])
        beat = sum(1 for _d, gain, ix, _n in part["cohorts"] if gain > ix)
        if mine is None or solo is None:
            gap_text = ""
        else:
            gap = mine - solo
            gap_text = f"코스피보다 {abs(gap):.1f}% {'더 올랐습니다' if gap >= 0 else '덜 올랐습니다'} · "
        if days == 1:
            count_text = f"{md(part['cohorts'][0][0])} 한 번 산 것입니다"
        else:
            count_text = f"{days}번 산 것 중 {beat}번은 코스피보다 나았습니다"
        cards.append(
            f"<div class='j3vx-card'><b style='color:{PART_COLORS[kind]}'>{html.escape(PART_NAMES[kind])}</b>"
            f"<div class='j3vx-nums'><span class='j3vx-big' style='color:{tone(mine)}'>{fmt(mine)}</span>"
            f"<span class='j3vx-vs'>같은 날 코스피 <b style='color:{tone(solo)}'>{fmt(solo)}</b></span></div>"
            f"<div class='j3vx-say'>{gap_text}{count_text}</div></div>")
    return "<div class='j3vx-cards'>" + "".join(cards) + "</div>"


def legend_html(tab: str, data: dict) -> str:
    items = [f"<span><i class='j3vx-band'></i>{INDEX_NAME}</span>"]
    items += [f"<span><i style='border-top:3px solid {PART_COLORS[kind]}'></i>{html.escape(PART_NAMES[kind])}</span>"
              for kind in TAB_PARTS.get(tab, PARTS) if kind in data.get("parts", {})]
    return "<div class='j3vx-legend'>" + "".join(items) + "</div>"


def stocks_html(data: dict, tab: str, *, first: str = "", last: str = "") -> str:
    """「이 기간에 산 종목」 — 종목별로 묶어 잘 된 5 · 안 된 3, 나머지는 「다 보기」."""
    blocks = []
    for kind in TAB_PARTS.get(tab, PARTS):
        part = data.get("parts", {}).get(kind)
        if not part or not part.get("stocks"):
            continue
        stocks = part["stocks"]

        def line(item):
            code, name, times, gain, ix, first_day, last_day = item
            label = html.escape(name or code) + f" <small>{html.escape(code)}</small>"
            if times <= 1:
                when = md(first_day)
            else:
                when = f"{md(first_day)}~{md(last_day)}<br><small>{times}번</small>"
            return (f"<tr><td>{label}</td><td>{when}</td>"
                    f"<td style='color:{tone(gain)};font-weight:800'>{fmt(gain)}</td>"
                    f"<td style='color:{tone(ix)}'>{fmt(ix)}</td></tr>")

        head = f"<tr><th>종목</th><th>산 날</th><th>평균 수익</th><th>같은 날 {INDEX_NAME}</th></tr>"
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
            f"{html.escape(PART_NAMES[kind])} · {len(stocks)}종목</div>{table}{more}</div>")
    if not blocks:
        return ""
    when = f"{first} ~ {last}에 산 것을 모두 {last} 종가에 팔았다면" if first and last else ""
    return ("<div class='j3vx-list'><div class='j3vx-list-head'>이 기간에 산 종목"
            f"<small>{html.escape(when)}</small></div>"
            "<div class='j3vx-note' style='margin:0 0 8px'>여러 날 산 종목은 <b>산 날마다 수익을 내서 평균</b>했습니다. "
            "보기 — 9/2에 10만 원 · 9/10에 11만 원에 사서 12만 원에 팔면 +20%와 +9.1% → 평균 +14.5%.</div>"
            + "".join(blocks) + "</div>")


# 꾸밈 — 자비스12 의 그림 꾸밈(.j3vx-…)과 같다. 단추 칸 이름만 자비스13 것(j13vx_).
CSS = """
<style>
.j3vx{padding-top:12px;border-top:1px solid #1d3a63}
div[class*="st-key-j13vx_t_"] button,div[class*="st-key-j13vx_p_"] button,div[class*="st-key-j13vx_v_"] button{
  min-height:0!important;padding:.3rem .45rem!important;background:transparent!important;border:1px solid #1d3a63!important}
div[class*="st-key-j13vx_t_"] button{border-radius:10px!important}
div[class*="st-key-j13vx_p_"] button,div[class*="st-key-j13vx_v_"] button{border-radius:999px!important}
div[class*="st-key-j13vx_t_"] button p{font-size:.82rem!important;font-weight:700!important;color:#cfe0ff!important}
div[class*="st-key-j13vx_p_"] button p,div[class*="st-key-j13vx_v_"] button p{
  font-size:.76rem!important;font-weight:700!important;color:#8fb4de!important}
div[class*="st-key-j13vx_t_"] button[kind="primary"]{
  background:linear-gradient(90deg,#3b1a6b 0%,#7c3aed 100%)!important;border-color:#7c3aed!important}
div[class*="st-key-j13vx_p_"] button[kind="primary"],div[class*="st-key-j13vx_v_"] button[kind="primary"]{
  background:#2a4f8f!important;border-color:#4d7fd0!important}
div[class*="st-key-j13vx_t_"] button[kind="primary"] p,div[class*="st-key-j13vx_p_"] button[kind="primary"] p,
div[class*="st-key-j13vx_v_"] button[kind="primary"] p{color:#fff!important}
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
/* 성적표 표 — 파트마다 한 줄 */
.j13sc-tbl{width:100%;border-collapse:collapse;font-size:.86rem;margin:4px 0 8px}
.j13sc-tbl th{color:#8fb4de;font-weight:700;text-align:right;padding:5px 6px;border-bottom:1px solid #1d3a63;white-space:nowrap}
.j13sc-tbl td{padding:6px;text-align:right;color:#e6e6e6;border-bottom:1px solid rgba(157,204,255,.07);white-space:nowrap}
.j13sc-tbl th:first-child,.j13sc-tbl td:first-child{text-align:left}
.j13sc-wrap{overflow-x:auto}
.j13sc-note{font-size:.76rem;color:#8fb4de;line-height:1.55;margin:2px 0 6px}
</style>
"""
