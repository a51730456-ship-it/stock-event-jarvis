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
MODULE_REVISION = 2026100710

PARTS = ("theme15", "breakout", "crash")
PART_NAMES = {
    "theme15": "상위 테마 5개 (1~3위)",
    "breakout": "상승장 (신고가 눌림매수)",
    "crash": "급락 후 반등장 (낙폭종목)",
}
# 성적표 막대 색(_SCORECARD_PARTS)과 같은 빛 — 어두운 바탕에서 선이 보이게 한 치수 밝게.
PART_COLORS = {"theme15": "#ef5b50", "breakout": "#22b884", "crash": "#f2a33a"}
# 「테마 비교표」는 저장 목록 파트가 아니라 테마 명부 종목의 주가로 그린다 — 견주는 파트가 없다(2026-10-07 상하님
# 지시 — "상위 테마 5개 옆에 테마 비교표 란을").
TABS = (
    ("all", "세 파트 한눈에", PARTS),
    ("theme", "상위 테마 5개", ("theme15",)),
    ("themes", "테마 비교표", ()),
    ("swing", "상승장 · 급락 후 반등장", ("breakout", "crash")),
)
TAB_PARTS = {key: parts for key, _label, parts in TABS}
PERIODS = (("d", "일별"), ("w", "주별"), ("m", "월별"))
VIEWS = (("line", "쌓인 수익 (선)"), ("bar", "산 날마다 (막대)"))
# 테마 비교표에만 하나 더 — **나스닥보다 몇 % 더·덜** (2026-10-07 상하님 지시). 산 것마다 같은 날 같은 돈으로
# 나스닥 종합을 샀을 때와 견준다 — 나스닥이 0줄이 되고, 시장 전체가 같이 오르내린 몫이 빠져 테마끼리 갈라지는
# 것(한 테마가 뜰 때 어느 테마가 빠지나)이 또렷해진다.
THEME_EXTRA_VIEWS = (("rel", "나스닥보다 더·덜"),)
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
        listed_rows.append((kind, listed, code, buy, str(row.get("name") or code),
                            str(row.get("origin") or "").strip()))
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
    for kind, listed, code, buy, name, origin in listed_rows:
        # 목록을 찍은 날 **다음 거래일**이 산 날이다(저장된 매수금액 = 그날 시가).
        place = bisect.bisect_right(calendar, listed)
        if place >= len(calendar):
            continue                    # 아직 안 산 줄(다음 장이 안 열렸다)
        picked.append((kind, calendar[place], code, buy, name, origin))
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
        for _kind, bought, code, buy, name, _origin in mine:
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
                # 종목 표는 **산 날**로 센다 — 같은 날 두 테마에 같이 든 종목(ILMN 바이오·유전체)을 두 번 세면
                # 25일 동안 「40번」이 되어 알아볼 수 없었다(2026-10-07 상하님 — "이건 이해할 수 없다").
                slot = per_stock.setdefault(code, [name, {}])
                slot[1].setdefault(bought, ((value - 1.0) * 100.0, nq_last * 100.0))
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
              round(sum(n for _g, n in by_day.values()) / len(by_day), 2)]
             for code, (name, by_day) in per_stock.items()),
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
    # ── 테마 비교표 — 「상위 테마 5개」 줄을 **테마(origin)로 나눠** 같은 셈(2026-10-07 상하님 — "결국 내가 매수하는
    # 것은 테마에서 1~3위 종목 · 표의 기준을 맞추는 게 맞는 듯"). 산 것마다 같은 돈 — 선의 끝 값이 위 표
    # (_scorecard_range_counts 의 테마별 평균)와 같다. 차례도 그 표와 같다(이익 난 확률, 같으면 평균).
    themes = []
    by_theme: dict = {}
    for kind, bought, code, buy, name, origin in picked:
        if kind == "theme15" and origin:
            by_theme.setdefault(origin, []).append((bought, code, buy))
    for origin, items in by_theme.items():
        series_list, gains, per_stock, per_day = [], [], {}, {}
        rel_list, rel_gains, beat = [], [], 0
        for bought, code, buy in items:
            ratio = closes[:, column[code]] / buy
            ratio[:index[bought]] = np.nan
            if np.isnan(ratio[-1]):
                continue                # 끝날 값을 못 잰 줄 — 세지 않는다(0으로 채우지 않는다)
            series_list.append(ratio)
            gain = (ratio[-1] - 1.0) * 100.0
            gains.append(gain)
            per_stock.setdefault(code, []).append(gain)
            nq_gain = (ix_c[-1] / ix_open[bought] - 1.0) * 100.0
            slot = per_day.setdefault(bought, [[], nq_gain])
            slot[0].append(gain)
            # 같은 날 같은 돈으로 나스닥 종합을 샀다면 — 그 차이가 「나스닥보다 몇 % 더·덜」이다.
            ix_ratio = ix_c / ix_open[bought]
            ix_ratio[:index[bought]] = np.nan
            rel_list.append(ratio - ix_ratio)
            rel_gains.append(gain - nq_gain)
            beat += 1 if gain > nq_gain else 0
        if not gains:
            continue
        matrix = np.vstack(series_list)
        active = ~np.isnan(matrix)
        held = active.sum(axis=0)
        total = np.where(active, matrix, 0.0).sum(axis=0)
        cum = [None if held[place] == 0 else round((total[place] / held[place] - 1.0) * 100.0, 2)
               for place in range(count)]
        rel_matrix = np.vstack(rel_list)
        rel_total = np.where(active, rel_matrix, 0.0).sum(axis=0)
        rel_cum = [None if held[place] == 0 else round(rel_total[place] / held[place] * 100.0, 2)
                   for place in range(count)]
        best_code, best_gains = max(per_stock.items(), key=lambda kv: sum(kv[1]) / len(kv[1]))
        themes.append({
            "name": origin, "cum": cum,
            "cohorts": [[day.isoformat(), round(sum(g) / len(g), 2), round(nq, 2), len(g)]
                        for day, (g, nq) in sorted(per_day.items())],
            "seen": len(gains), "win": sum(1 for g in gains if g > 0),
            "final": round(sum(gains) / len(gains), 2),
            "top": [best_code, round(sum(best_gains) / len(best_gains), 1)],
            "rel": rel_cum, "rel_final": round(sum(rel_gains) / len(rel_gains), 2), "beat": beat,
        })
    themes.sort(key=lambda row: (-(row["win"] / row["seen"]), -row["final"]))
    return {"days": [day.isoformat() for day in days], "last": days[-1].isoformat(),
            "parts": parts, "nasdaq": nasdaq, "themes": themes,
            "rows": sum(p["rows"] for p in parts.values())}


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


def _frame(svg_body: str, ticks: list, low: float, high: float, labels: list, extra: str = "") -> str:
    """눈금(글자)은 그림 밖 HTML 로 — 그림은 가로로 늘려 그려도 글자는 안 찌그러진다."""
    span = (high - low) or 1.0
    y_labels = "".join(
        f"<span style='top:{(high - tick) / span * 100:.2f}%'>{tick:+g}%</span>" for tick in ticks)
    x_labels = "".join(
        f"<span style='left:{left:.2f}%'>{html.escape(text)}</span>" for left, text in labels)
    return (f"<div class='j3vx-plot{(' ' + extra) if extra else ''}'><div class='j3vx-y'>{y_labels}</div>"
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
            return (f"<tr><td>{label}</td><td>{times}일</td>"
                    f"<td style='color:{_tone(gain)};font-weight:800'>{_fmt(gain)}</td>"
                    f"<td style='color:{_tone(nq)}'>{_fmt(nq)}</td></tr>")

        head = ("<tr><th>종목</th><th>산 날</th><th>평균 수익</th><th>같은 날 나스닥</th></tr>")
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
    # 표 위 설명은 **보기 하나로** 푼다(2026-10-07 상하님 — "같은 종목을 9월 2일에 사고 9월 10일에 샀다면
    # 평균을 이야기한 것인가?"). 그렇다 — 산 날마다 수익을 내서 평균한다.
    when = f"{first} ~ {last}에 산 것을 모두 {last} 종가에 팔았다면" if first and last else ""
    return ("<div class='j3vx-list'><div class='j3vx-list-head'>이 기간에 산 종목"
            f"<small>{html.escape(when)}</small></div>"
            "<div class='j3vx-note' style='margin:0 0 8px'>여러 날 산 종목은 <b>산 날마다 수익을 내서 평균</b>했습니다. "
            "보기 — 9/2에 100달러 · 9/10에 110달러에 사서 120달러에 팔면 +20%와 +9.1% → 평균 +14.5%. "
            "같은 날 두 테마에 같이 든 종목은 하루로 셉니다.</div>"
            + "".join(blocks) + "</div>")


# ── 테마 비교표 — 나스닥 종합 하나 + 「상위 테마 5개」에 든 테마들 (2026-10-07 상하님 지시) ──────────────
# 상하님 — "어느 테마가 어떤 시점에 오르고 내리는지 테마별로" · "나스닥은 1개만" · "상위 테마 5개 옆에 테마 비교표
# 란을" · 그리고 마지막으로 "결국 내가 매수하는 것은 테마에서 1~3위 종목을 매수한다고 봐야 되니 표의 기준을
# 맞추는 게 맞는 듯" · "빼기로 해라(빅테크10)".
#
# 그래서 이 그림은 **위 「이 기간 테마별 — 상위 테마 5개 줄」 표와 같은 기준**이다.
#   · 테마 — 그 기간 「상위 테마 5개」에 든 테마만(표와 같은 테마 · 같은 차례 — 이익 난 확률, 같으면 평균).
#   · 선 — 그 테마가 상위 5에 든 날마다 1~3위를 다음 날 시가에 **산 것마다 같은 돈으로** 샀다면 날마다 몇 %.
#     선의 끝 값 = 표의 「평균」과 같다.
#   · 나스닥 — 한 줄. 「상위 테마 5개」를 산 날마다 같은 돈으로 샀다면(상위 테마 5개 탭의 나스닥과 같다).
# (앞 판은 22개 테마 명부 종목 평균으로 그려 표와 테마도 숫자도 갈렸다 — 9/21~10/6 유전체 그림 +14.2% ·
#  표 −5.48%. 그 +14 가 PACB 한 종목이었고 앱은 PACB 를 9/30 에야 샀다.)
THEME_MAX = 10
# 어두운 바탕에서 서로 갈리는 열 빛.
THEME_COLORS = ("#ff6b6b", "#ffd166", "#06d6a0", "#4cc9f0", "#c77dff", "#f78fb3", "#ff9f43", "#a3e635",
                "#8ea2ff", "#ffffff")
THEME_DAILY_BAR_KEEP = 10
# 테마 비교표 눈금을 잘게 — 8칸 남짓으로 나눠 위아래를 꽉 쓰게(2026-10-07 상하님 — "너무 누워 있으니 구분이
# 힘들다 · 좀 더 세울까"). 4칸이면 맨 위가 크게 튀어 줄들이 아래에 눌렸다.
THEME_TICK_PARTS = 8


# **비교용 두 테마** (2026-10-07 상하님 — "테마 비교표 안에 빅테크10과 로봇·자동화 넣어라 · 색깔도 고민해서").
# 둘 다 이 기간 「상위 테마 5개」에 든 적이 없어 앱이 산 적이 없다 — 「1~3위를 샀다면」 선을 그릴 수 없다.
# 그래서 **점선**으로, 테마 명부 종목을 같은 돈으로 나눠 들었다면(기간 첫날 앞 종가부터) 그린다. 색은 산 테마들의
# 열 빛과 겹치지 않게 — 빅테크10 흰색(시장 대형주 · 나스닥과 견주는 잣대), 로봇·자동화 진분홍. 그 기간에 상위 5에
# 들어 산 적이 있으면 실선(산 기준)으로 이미 나오므로 점선은 안 그린다.
REFERENCE_THEMES = ("빅테크10", "로봇·자동화")
REFERENCE_COLORS = {"빅테크10": "#ffffff", "로봇·자동화": "#ff3dbb"}


def reference_lines(themes, frames: dict, ixic, days: list) -> list:
    """비교용 테마 줄 — 명부 종목 평균(기간 첫날 앞 종가부터)과 그 나스닥 대비. themes = [(이름, 종목들)]."""
    import numpy as np

    if not days:
        return []
    wanted = [date.fromisoformat(day) for day in days]
    since = wanted[0] - timedelta(days=12)
    ix_close = _series_by_day(ixic, "Close", since)
    before = [day for day in ix_close if day < wanted[0]]
    axis = ([before[-1]] if before else []) + wanted
    skip = 1 if before else 0               # 기준 종가 칸(그림에는 안 나온다)

    def aligned(by_day):
        out, last_seen = [], np.nan
        earlier = [value for day, value in by_day.items() if day < axis[0]]
        if earlier:
            last_seen = earlier[-1]
        for day in axis:
            if day in by_day:
                last_seen = by_day[day]
            out.append(last_seen)
        return np.array(out, dtype=float)

    nasdaq = aligned(ix_close)
    if not np.isfinite(nasdaq[0]) or nasdaq[0] <= 0:
        return []
    nq = nasdaq / nasdaq[0]
    rows = []
    for name, codes in themes or []:
        stack, best = [], None
        for code in codes:
            code = str(code).upper()
            series = aligned(_series_by_day((frames or {}).get(code), "Close", since))
            if not (np.isfinite(series[0]) and series[0] > 0):
                continue
            ratio = series / series[0]
            stack.append(ratio)
            last = next((float(v) for v in ratio[::-1] if np.isfinite(v)), None)
            if last is not None and (best is None or last > best[1]):
                best = (code, last)
        if not stack:
            continue
        mean = np.nanmean(np.vstack(stack), axis=0)
        cum = [None if not np.isfinite(v) else round((v - 1.0) * 100.0, 2) for v in mean[skip:]]
        rel = [None if not (np.isfinite(v) and np.isfinite(q)) else round((v - q) * 100.0, 2)
               for v, q in zip(mean[skip:], nq[skip:])]
        rows.append({
            "name": name, "cum": cum, "rel": rel, "reference": True,
            "final": next((v for v in reversed(cum) if v is not None), None),
            "rel_final": next((v for v in reversed(rel) if v is not None), None),
            "top": None if best is None else [best[0], round((best[1] - 1.0) * 100.0, 1)],
        })
    return rows


def theme_chart_html(data: dict, period: str, view: str) -> tuple:
    """(범례·그림 한 장 — 나스닥 띠 하나 + 테마 줄들, 덧붙일 말). 테마는 compute() 의 themes 그대로."""
    themes = list((data or {}).get("themes") or [])[:THEME_MAX]
    days = (data or {}).get("days") or []
    nasdaq = ((data or {}).get("nasdaq") or {}).get("theme") or []
    if not themes or not days or not nasdaq:
        return "", ""
    rel = view == "rel"
    bought = {row["name"] for row in themes}
    # 비교용 점선 두 줄 — 막대 보기(산 날마다)에는 산 날이 없으므로 안 그린다.
    refs = [] if view == "bar" else [row for row in (data.get("reference") or []) if row["name"] not in bought]
    if rel:
        # 나스닥보다 몇 % 더·덜 — 테마 줄은 차이, 나스닥은 0(같은 날 같은 돈이면 나스닥과 똑같다는 뜻).
        themes = [dict(row, cum=row["rel"], final=row["rel_final"]) for row in themes]
        refs = [dict(row, cum=row["rel"], final=row["rel_final"]) for row in refs]
        nasdaq = [0.0 if v is not None else None for v in nasdaq]
    colors = {row["name"]: THEME_COLORS[index % len(THEME_COLORS)] for index, row in enumerate(themes)}
    colors.update({row["name"]: REFERENCE_COLORS.get(row["name"], "#ffffff") for row in refs})
    themes = themes + refs
    place = {row["name"]: index for index, row in enumerate(themes)}
    nq_final = next((v for v in reversed(nasdaq) if v is not None), None)
    # **이름을 누르면 그 테마만 굵게** — 숨은 스위치(체크칸)로 여닫아 서버에 묻지 않는다. 스위치는 범례·그림보다
    # **앞에** 같은 줄로 둔다(뒤의 범례·그림을 「~」로 집으려면 앞서야 한다). 꾸밈은 CSS 의 j3vx-tk-숫자 규칙.
    taps = "".join(f"<input type='checkbox' id='j3vx-tk-{index}' class='j3vx-tk'>" for index in range(len(themes)))
    legend = [("<span><i class='j3vx-band'></i>나스닥 종합 = 0</span>" if rel else
               f"<span><i class='j3vx-band'></i>나스닥 종합 <b style='color:{_tone(nq_final)}'>{_fmt(nq_final)}</b></span>")]
    for row in themes:
        if row.get("reference"):
            count_text = "비교용 · 산 적 없음"
        else:
            count_text = (f"{row['seen']}번 중 {row['beat']}번 나스닥보다 나음" if rel
                          else f"{row['seen']}번 중 {row['win']}번")
        swatch = "dashed" if row.get("reference") else "solid"
        legend.append(f"<label for='j3vx-tk-{place[row['name']]}' class='j3vx-tchip j3vx-tc{place[row['name']]}'>"
                      f"<i style='border-top:3px {swatch} {colors[row['name']]}'></i>{html.escape(row['name'])} "
                      f"<b style='color:{_tone(row['final'])}'>{_fmt(row['final'])}</b>"
                      f"<small>{count_text}</small>{'' if rel else _top_html(row)}</label>")
    legend_html = (taps + "<div class='j3vx-legend j3vx-tlegend'>" + "".join(legend) + "</div>"
                   "<div class='j3vx-thint'>이름을 누르면 그 테마만 굵게 보입니다 · 여러 개 눌러 견줄 수 있고, "
                   "다시 누르면 풀립니다"
                   + ("" if rel else " · 괄호 안은 그 테마에서 산 1~3위 중 가장 많이 번 종목(산 날 평균)입니다"
                      + (" · 점선 두 테마는 그 명부에서 가장 많이 오른 종목입니다" if refs else ""))
                   + ".</div>")
    note = ""
    if view == "bar":
        if data.get("reference"):
            note = "비교용 두 테마(빅테크10 · 로봇·자동화)는 선 보기에만 그립니다. "
        many = len({d[:4] for d in days}) > 1
        groups = {row["name"]: bar_groups(row["cohorts"], period, many) for row in themes}
        nq_days: dict = {}
        for row in themes:
            for day, _gain, nq, _n in row["cohorts"]:
                nq_days[day] = nq
        nq_groups = bar_groups([[day, nq, nq, 1] for day, nq in sorted(nq_days.items())], period, many)
        keys = sorted(nq_groups)
        if period == "d" and len(keys) > THEME_DAILY_BAR_KEEP:
            note += f"일별 막대는 최근 {THEME_DAILY_BAR_KEEP}일만 그립니다(주별·월별은 전부)."
            keys = keys[-THEME_DAILY_BAR_KEEP:]
        if not keys:
            return "", ""
        labels = [nq_groups[key][0] for key in keys]
        values = [nq_groups[key][2] for key in keys] + [g[key][1] for g in groups.values() for key in keys if key in g]
        low, high, ticks = _nice_range(values, parts=THEME_TICK_PARTS)
        slot = 1000.0 / len(keys)
        width = slot * 0.84 / (1 + len(themes))

        def y(value):
            return (high - value) / ((high - low) or 1.0) * 400.0

        body = [_grid(ticks, y)]
        for column, key in enumerate(keys):
            left = column * slot + slot * 0.08
            entries = [("나스닥 종합", NASDAQ_COLOR, nq_groups[key][2], "")]
            entries += [(row["name"], colors[row["name"]], (groups[row["name"]].get(key) or (None, None))[1],
                         f" class='j3vx-tl j3vx-tl{place[row['name']]}'") for row in themes]
            for lane, (name, color, value, mark) in enumerate(entries):
                if value is None:
                    continue
                top, bottom = sorted((y(value), y(0.0)))
                body.append(f"<rect{mark} x='{left + lane * width:.1f}' y='{top:.1f}' width='{width:.1f}' "
                            f"height='{max(bottom - top, 1.5):.1f}' fill='{color}'>"
                            f"<title>{html.escape(labels[column])} · {html.escape(name)} {_fmt(value)}</title></rect>")
        chart = _frame("".join(body), ticks, low, high,
                       _x_labels(len(keys), labels, lambda c: (c + 0.5) * slot / 10.0), "j3vx-tplot")
        return _theme_zoom(legend_html, chart, themes, colors, nq_final), note
    nq_points = line_points(days, nasdaq, period)
    points = {row["name"]: line_points(days, row["cum"], period) for row in themes}
    count = len(nq_points)
    values = [v for _l, v in nq_points] + [v for pts in points.values() for _l, v in pts]
    low, high, ticks = _nice_range(values, parts=THEME_TICK_PARTS)

    def x(i):
        return 500.0 if count == 1 else i * 1000.0 / (count - 1)

    def y(value):
        return (high - value) / ((high - low) or 1.0) * 400.0

    def runs(pts):
        # 그 테마가 처음 상위 5에 든 날부터 선이 시작한다(그 앞은 빈칸).
        return " ".join(f"{x(i):.1f},{y(v):.1f}" for i, (_l, v) in enumerate(pts) if v is not None)

    body = [_grid(ticks, y),
            f"<polyline points='{runs(nq_points)}' fill='none' stroke='{NASDAQ_COLOR}' stroke-width='{NASDAQ_WIDTH}' "
            "stroke-linecap='round' stroke-linejoin='round' vector-effect='non-scaling-stroke'/>"]
    for row in reversed(themes):            # 첫째가 맨 위에 그려지게 거꾸로 깐다
        color = colors[row["name"]]
        line = runs(points[row["name"]])
        if not line:
            continue
        mark = f"j3vx-tl j3vx-tl{place[row['name']]}"
        dash = " stroke-dasharray='7 5'" if row.get("reference") else ""
        body.append(f"<polyline class='{mark}' points='{line}' fill='none' stroke='{color}' stroke-width='1.8'{dash} "
                    "stroke-linejoin='round' vector-effect='non-scaling-stroke'/>")
        # 점 — 주별·월별, 그리고 점이 몇 개 안 되는 줄(며칠만 상위 5에 든 테마)은 일별에서도 찍는다.
        dots = line.split()
        if not row.get("reference") and (period != "d" or len(dots) <= 3):
            body.append(f"<path class='{mark} j3vx-tdot' d='{''.join('M' + p + 'h0' for p in dots)}' "
                        f"stroke='{color}' stroke-width='6' stroke-linecap='round' fill='none' "
                        "vector-effect='non-scaling-stroke'/>")
    chart = _frame("".join(body), ticks, low, high,
                   _x_labels(count, [label for label, _v in nq_points], lambda i: x(i) / 10.0), "j3vx-tplot")
    return _theme_zoom(legend_html, chart, themes, colors, nq_final), note


def _top_html(row: dict) -> str:
    """이름 옆 「(PACB +5.1%)」 — 그 테마에서 산 1~3위 중 가장 많이 번 종목(산 날 평균)."""
    top = row.get("top")
    if not top or top[1] is None:
        return ""
    value = top[1]
    text = f"{value:+.0f}%" if abs(value) >= 10 else f"{value:+.1f}%"
    return f"<em class='j3vx-ttop'>({html.escape(str(top[0]))} {text})</em>"


def _theme_zoom(legend_html: str, chart: str, picked: list, colors: dict, nq_final) -> str:
    """그림을 누르면 **화면 가득** — 시장 현황 지도 창과 같은 장치(2026-10-07 상하님 지시 — "10개 테마 그래프
    클릭하면 스마트폰이나 태블릿에서 화면 옆으로 꽉 차게 · 시장 현황 클릭하면 옆으로 꽉 차게 튀어나오잖아").

    숨은 스위치(j3vx-zoom) 하나로 여닫아 서버에 묻지 않는다. 세로로 든 화면(폰·세운 태블릿)은 창을 눕혀 긴 쪽으로
    채운다. 창 안 그림은 바깥 그림과 같은 것이라, 바깥에서 이름을 눌러 굵게 한 테마가 창에서도 굵다.
    창 안 범례는 누르는 칸이 아니다 — 창을 누르면 닫혀야 하므로(누르는 칸 안에 누르는 칸을 둘 수 없다).
    """
    place = {row["name"]: index for index, row in enumerate(picked)}
    names = [f"<span><i class='j3vx-band'></i>나스닥 종합 <b style='color:{_tone(nq_final)}'>{_fmt(nq_final)}</b></span>"
             if nq_final else "<span><i class='j3vx-band'></i>나스닥 종합 = 0</span>"]
    names += [f"<span class='j3vx-zc{place[row['name']]}'><i style='border-top:3px "
              f"{'dashed' if row.get('reference') else 'solid'} {colors[row['name']]}'></i>"
              f"{html.escape(row['name'])} <b style='color:{_tone(row['final'])}'>{_fmt(row['final'])}</b>"
              f"{_top_html(row)}</span>"
              for row in picked]
    return (
        "<input type='checkbox' id='j3vx-zoom' class='j3cz-tap j3vx-ztap'>" + legend_html
        + f"<label for='j3vx-zoom' class='j3vx-zcell'>{chart}"
        "<span class='j3vx-zhint'>🔍 그림을 누르면 화면 가득 크게 봅니다</span></label>"
        "<label for='j3vx-zoom' class='j3vx-zscrim' aria-hidden='true'></label>"
        "<label for='j3vx-zoom' class='j3vx-zpop'><div class='j3vx-zin'>"
        "<span class='j3vx-ztitle'>테마 비교표 · 나스닥 종합과 상위 테마 5개에 든 테마 — 1~3위를 샀다면</span>"
        # 이름은 **오른쪽 세로 줄**에 — 눕힌 창은 위아래가 폰의 짧은 쪽이라, 이름을 위에 세 줄로 두면 그림이
        # 223px 로 납작해졌다(2026-10-07 노트북 실측). 옆으로 빼면 그림이 창 높이를 다 쓴다.
        f"<div class='j3vx-zbody'>{chart}<div class='j3vx-legend j3vx-zlegend'>{''.join(names)}</div></div>"
        "<span class='j3vx-zclose'>다시 누르면 닫힘</span></div></label>")

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
.j3vx-tlegend small{color:#8fb4de;font-size:.7rem;margin-right:2px}
.j3vx-tlegend b{font-weight:800;margin-left:2px}
/* 테마 비교표 — 이름을 누르면 그 테마만 굵게(여러 개 가능). 숨은 스위치 · 서버에 안 묻는다. */
.j3vx-tk{position:absolute;opacity:0;pointer-events:none;width:0;height:0;margin:0}
.j3vx-tchip{display:flex;align-items:center;gap:6px;cursor:pointer;padding:2px 8px;margin:0 -8px;white-space:nowrap;
  border:1px solid transparent;border-radius:999px;transition:background-color .15s ease,border-color .15s ease}
.j3vx-thint{font-size:.72rem;color:#6f93bd;margin:-2px 0 6px}
.j3vx-ttop{font-style:normal;font-size:.68rem;font-weight:600;color:#8fb4de;margin-left:3px;white-space:nowrap}
.j3vx-tl{opacity:.85;transition:opacity .2s ease}
.j3vx-tk:checked ~ * .j3vx-tl{opacity:.12}
#j3vx-tk-0:checked ~ * .j3vx-tl0{opacity:1}#j3vx-tk-0:checked ~ * polyline.j3vx-tl0{stroke-width:3.6px}#j3vx-tk-0:checked ~ .j3vx-tlegend .j3vx-tc0{border-color:#c084fc;background:rgba(192,132,252,.16)}#j3vx-tk-0:checked ~ .j3vx-zpop .j3vx-zc0{opacity:1}
#j3vx-tk-1:checked ~ * .j3vx-tl1{opacity:1}#j3vx-tk-1:checked ~ * polyline.j3vx-tl1{stroke-width:3.6px}#j3vx-tk-1:checked ~ .j3vx-tlegend .j3vx-tc1{border-color:#c084fc;background:rgba(192,132,252,.16)}#j3vx-tk-1:checked ~ .j3vx-zpop .j3vx-zc1{opacity:1}
#j3vx-tk-2:checked ~ * .j3vx-tl2{opacity:1}#j3vx-tk-2:checked ~ * polyline.j3vx-tl2{stroke-width:3.6px}#j3vx-tk-2:checked ~ .j3vx-tlegend .j3vx-tc2{border-color:#c084fc;background:rgba(192,132,252,.16)}#j3vx-tk-2:checked ~ .j3vx-zpop .j3vx-zc2{opacity:1}
#j3vx-tk-3:checked ~ * .j3vx-tl3{opacity:1}#j3vx-tk-3:checked ~ * polyline.j3vx-tl3{stroke-width:3.6px}#j3vx-tk-3:checked ~ .j3vx-tlegend .j3vx-tc3{border-color:#c084fc;background:rgba(192,132,252,.16)}#j3vx-tk-3:checked ~ .j3vx-zpop .j3vx-zc3{opacity:1}
#j3vx-tk-4:checked ~ * .j3vx-tl4{opacity:1}#j3vx-tk-4:checked ~ * polyline.j3vx-tl4{stroke-width:3.6px}#j3vx-tk-4:checked ~ .j3vx-tlegend .j3vx-tc4{border-color:#c084fc;background:rgba(192,132,252,.16)}#j3vx-tk-4:checked ~ .j3vx-zpop .j3vx-zc4{opacity:1}
#j3vx-tk-5:checked ~ * .j3vx-tl5{opacity:1}#j3vx-tk-5:checked ~ * polyline.j3vx-tl5{stroke-width:3.6px}#j3vx-tk-5:checked ~ .j3vx-tlegend .j3vx-tc5{border-color:#c084fc;background:rgba(192,132,252,.16)}#j3vx-tk-5:checked ~ .j3vx-zpop .j3vx-zc5{opacity:1}
#j3vx-tk-6:checked ~ * .j3vx-tl6{opacity:1}#j3vx-tk-6:checked ~ * polyline.j3vx-tl6{stroke-width:3.6px}#j3vx-tk-6:checked ~ .j3vx-tlegend .j3vx-tc6{border-color:#c084fc;background:rgba(192,132,252,.16)}#j3vx-tk-6:checked ~ .j3vx-zpop .j3vx-zc6{opacity:1}
#j3vx-tk-7:checked ~ * .j3vx-tl7{opacity:1}#j3vx-tk-7:checked ~ * polyline.j3vx-tl7{stroke-width:3.6px}#j3vx-tk-7:checked ~ .j3vx-tlegend .j3vx-tc7{border-color:#c084fc;background:rgba(192,132,252,.16)}#j3vx-tk-7:checked ~ .j3vx-zpop .j3vx-zc7{opacity:1}
#j3vx-tk-8:checked ~ * .j3vx-tl8{opacity:1}#j3vx-tk-8:checked ~ * polyline.j3vx-tl8{stroke-width:3.6px}#j3vx-tk-8:checked ~ .j3vx-tlegend .j3vx-tc8{border-color:#c084fc;background:rgba(192,132,252,.16)}#j3vx-tk-8:checked ~ .j3vx-zpop .j3vx-zc8{opacity:1}
#j3vx-tk-9:checked ~ * .j3vx-tl9{opacity:1}#j3vx-tk-9:checked ~ * polyline.j3vx-tl9{stroke-width:3.6px}#j3vx-tk-9:checked ~ .j3vx-tlegend .j3vx-tc9{border-color:#c084fc;background:rgba(192,132,252,.16)}#j3vx-tk-9:checked ~ .j3vx-zpop .j3vx-zc9{opacity:1}
#j3vx-tk-10:checked ~ * .j3vx-tl10{opacity:1}#j3vx-tk-10:checked ~ * polyline.j3vx-tl10{stroke-width:3.6px}#j3vx-tk-10:checked ~ .j3vx-tlegend .j3vx-tc10{border-color:#c084fc;background:rgba(192,132,252,.16)}#j3vx-tk-10:checked ~ .j3vx-zpop .j3vx-zc10{opacity:1}
#j3vx-tk-11:checked ~ * .j3vx-tl11{opacity:1}#j3vx-tk-11:checked ~ * polyline.j3vx-tl11{stroke-width:3.6px}#j3vx-tk-11:checked ~ .j3vx-tlegend .j3vx-tc11{border-color:#c084fc;background:rgba(192,132,252,.16)}#j3vx-tk-11:checked ~ .j3vx-zpop .j3vx-zc11{opacity:1}
/* 테마 비교표는 **더 세운다** — 줄이 위아래로 벌어져 어느 테마가 오를 때 어느 테마가 빠지는지 갈리게. */
.j3vx-tplot{height:380px}
/* 그림을 누르면 화면 가득 — 시장 현황 지도 창(.j3sm-pop)과 같은 움직임·같은 눕히기. */
label.j3vx-zcell{display:block;cursor:zoom-in}
.j3vx-zhint{display:block;text-align:right;font-size:.72rem;color:#8fb4de;margin-top:0}
.j3vx-zscrim{position:fixed;inset:0;z-index:2147483646;cursor:zoom-out;background:rgba(1,8,22,.84);
  opacity:0;visibility:hidden;transition:opacity .3s ease,visibility 0s linear .56s}
.j3vx-zpop{position:fixed;left:50%;top:50%;z-index:2147483647;cursor:zoom-out;
  width:min(calc(100vw - 16px),1280px);height:min(calc(100dvh - 16px),860px);box-sizing:border-box;
  padding:12px 14px 8px;border-radius:22px;background:#0d2344;border:1px solid rgba(157,204,255,.45);
  box-shadow:0 18px 50px rgba(0,0,0,.6);display:flex;flex-direction:column;
  opacity:0;visibility:hidden;pointer-events:none;transform:translate(-50%,-50%) scale(.55);
  transition:transform .56s cubic-bezier(.5,-.18,.72,.18),opacity .56s cubic-bezier(.7,0,.84,0),visibility 0s linear .56s}
.j3vx-ztap:checked ~ .j3vx-zscrim{opacity:1;visibility:visible;transition:opacity .3s ease,visibility 0s}
.j3vx-ztap:checked ~ .j3vx-zpop{opacity:1;visibility:visible;pointer-events:auto;transform:translate(-50%,-50%) scale(1);
  transition:transform .9s cubic-bezier(.34,1.56,.64,1),opacity .36s ease,visibility 0s}
/* 닫혀 있는 동안은 창 속을 그리지 않는다(재무 창과 같다) — 닫는 움직임 .56초 뒤에 거둔다. */
.j3vx-zin{display:flex;flex-direction:column;gap:4px;flex:1 1 auto;min-height:0;
  content-visibility:hidden;transition:content-visibility 0s linear .56s allow-discrete}
.j3vx-ztap:checked ~ .j3vx-zpop .j3vx-zin{content-visibility:visible;transition-delay:0s}
.j3vx-ztitle{color:#9dccff;font-size:1rem;font-weight:800}
.j3vx-zbody{display:flex;align-items:stretch;gap:10px;flex:1 1 auto;min-height:0}
.j3vx-zlegend{flex:0 0 auto;max-width:34%;display:flex;flex-direction:column;flex-wrap:nowrap;gap:3px;
  margin:0;font-size:.74rem;overflow:hidden}
.j3vx-zlegend span{white-space:nowrap}
.j3vx-tk:checked ~ .j3vx-zpop .j3vx-zlegend span[class*="j3vx-zc"]{opacity:.35}
.j3vx-zpop .j3vx-plot.j3vx-tplot{flex:1 1 auto;height:auto!important;min-height:0;min-width:0}
.j3vx-zclose{align-self:center;font-size:.74rem;color:#8fb4de}
@media (orientation: portrait){
  .j3vx-zpop{width:calc(100dvh - 76px);height:calc(100vw - 16px);top:calc(50% - 30px);
    transform:translate(-50%,-50%) rotate(90deg) scale(.55)}
  .j3vx-ztap:checked ~ .j3vx-zpop{transform:translate(-50%,-50%) rotate(90deg) scale(1)}
}
@media (prefers-reduced-motion: reduce){.j3vx-zpop,.j3vx-zscrim{transition:none!important}}
.j3vx-more summary{cursor:pointer;font-size:.8rem;font-weight:700;color:#c084fc;padding:4px 0;list-style:none}
.j3vx-more summary::-webkit-details-marker{display:none}
.j3vx-more[open] summary{margin-bottom:4px}
</style>
"""
