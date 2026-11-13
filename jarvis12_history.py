"""자비스12 기능 ⑤ · ⑥ — QQQ 긴 일봉으로 보는 지난 급락 · 해마다 연중 최대 하락 (2026-11-13 상하님 「너의 추천 차례로 다 해라」).

⑤ 지난 급락 기록표 — 본뜬 곳 Schwab 「Market Corrections Are More Common Than You Think」.
   급락을 찾는 규칙은 jarvis12_crash.episodes 와 **같다**(QQQ 종가 ÷ 52주 최고가(장중 고가) − 1 이 −5% 이하면 시작 · 더 깊은 날이
   오면 기준일을 그날로 · 종가가 52주 최고 종가에 닿으면 끝). 다른 것은 기간뿐이다 — 화면 목록은 2년치, 여기는 QQQ 상장 뒤 전부.
   급락마다 「처음 −5% 닿은 다음 장 시가에 샀다면」과 「가장 깊은 날(바닥) 다음 장 시가에 샀다면」 1년(252장) 뒤 수익률을 나란히.
   바닥은 지나고 나서야 안다 — 두 줄의 차이가 「바닥을 맞혀야 얻는 몫」이다.
⑥ 해마다 한 번은 빠진다 — 본뜬 곳 J.P. Morgan 「Guide to the Markets」(S&P 500 연중 최대 하락). 같은 그림을 QQQ 로.
   연중 최대 하락 = 그해 안에서 그해 최고 종가 → 그 뒤 최저 종가. 그해 결과 = 그해 마지막 종가 ÷ 전해 마지막 종가 − 1.

**보여 주기만 한다** — 점수 · 판정 · 목록 · 성적표에 안 쓴다. 화면은 단추를 누를 때만 이 계산을 부른다(QQQ 전체 일봉 한 종목 · 6시간 기억).
"""
from __future__ import annotations

import threading
import time

import pandas as pd

import jarvis3_data as j3

MODULE_REVISION = 2026111301

SYMBOL = "QQQ"
THRESHOLD = -5.0               # jarvis12_crash.THRESHOLD 와 같다
HOLD = 252                     # 1년
TTL = 21600.0
_MEMO: dict = {}
_LOCK = threading.Lock()


def _dates(index) -> list:
    out = []
    for stamp in index:
        stamp = pd.Timestamp(stamp)
        if stamp.tzinfo is not None:
            stamp = stamp.tz_convert("America/New_York")
        out.append(stamp.date())
    return out


def find_episodes(frame) -> list:
    """jarvis12_crash.episodes 와 같은 규칙으로 급락을 찾는다(기간만 받은 표 전부)."""
    close = frame["Close"].astype(float)
    high52 = frame["High"].astype(float).rolling(252, min_periods=252).max()
    close52 = close.rolling(252, min_periods=252).max()
    drop = (close / high52 - 1.0) * 100.0
    days = _dates(frame.index)
    found, current = [], None
    for place, day in enumerate(days):
        value = drop.iloc[place]
        if pd.isna(value):
            continue
        value = float(value)
        if current is not None and float(close.iloc[place]) >= float(close52.iloc[place]) - 1e-9:
            current["recovered_on"] = day.isoformat()
            found.append(current)
            current = None
        if value <= THRESHOLD:
            if current is None:
                current = {"start": day.isoformat(), "reference": day.isoformat(), "reference_drop": value,
                           "first_drop": value, "last_below": day.isoformat(), "recovered_on": None}
            else:
                if value < current["reference_drop"]:
                    current["reference"], current["reference_drop"] = day.isoformat(), value
                current["last_below"] = day.isoformat()
    if current is not None:
        found.append(current)
    return found


def _after(frame, days: list, iso: str, hold: int = HOLD):
    """iso 다음 장 시가에 사서 hold 장 뒤 종가까지 수익률(%) — 아직 그만큼 안 지났으면 None."""
    after = [place for place, day in enumerate(days) if day.isoformat() > iso]
    if not after:
        return None
    buy = after[0]
    sell = buy + hold
    if sell >= len(days):
        return None
    try:
        open_ = float(frame["Open"].iloc[buy])
        close = float(frame["Close"].iloc[sell])
    except Exception:
        return None
    if not open_ or open_ != open_ or close != close:
        return None
    return round((close / open_ - 1.0) * 100.0, 1)


def crash_table(frame) -> dict:
    """⑤ 급락마다 첫날 · 바닥 · 걸린 날 · 1년 뒤(처음 산 날 / 바닥 산 날)와 요약."""
    days = _dates(frame.index)
    position = {day.isoformat(): place for place, day in enumerate(days)}
    rows = []
    for item in find_episodes(frame):
        start, ref = item["start"], item["reference"]
        rows.append({
            "start": start, "reference": ref, "recovered_on": item["recovered_on"],
            "first_drop": round(item["first_drop"], 1), "bottom_drop": round(item["reference_drop"], 1),
            "between": round(item["reference_drop"] - item["first_drop"], 1),
            "days": position.get(ref, 0) - position.get(start, 0),
            "first_1y": _after(frame, days, start), "bottom_1y": _after(frame, days, ref),
            "ongoing": item["recovered_on"] is None,
        })
    both = [row for row in rows if row["first_1y"] is not None and row["bottom_1y"] is not None]

    def stat(key):
        values = [row[key] for row in both]
        if not values:
            return None
        return {"mean": round(sum(values) / len(values), 1), "wins": sum(1 for v in values if v > 0), "n": len(values)}

    between = sorted(row["between"] for row in rows if not row["ongoing"])
    return {"ok": bool(rows), "rows": rows, "first": stat("first_1y"), "bottom": stat("bottom_1y"),
            "median_between": between[len(between) // 2] if between else None,
            "since": days[0].isoformat() if days else "", "as_of": days[-1].isoformat() if days else ""}


def yearly(frame) -> dict:
    """⑥ 해마다 연중 최대 하락(그해 최고 종가 → 그 뒤 최저 종가)과 그해 결과."""
    close = frame["Close"].astype(float).dropna()
    years = pd.Series(close.values, index=[d.year for d in _dates(close.index)])
    out, previous_last = [], None
    first_year = int(years.index[0]) if len(years) else None
    last_year = int(years.index[-1]) if len(years) else None
    for year in sorted(set(years.index)):
        values = years[years.index == year].values
        if len(values) < 2:
            previous_last = float(values[-1]) if len(values) else previous_last
            continue
        peak, worst = values[0], 0.0
        for value in values:
            peak = max(peak, value)
            worst = min(worst, value / peak - 1.0)
        result = (float(values[-1]) / previous_last - 1.0) * 100.0 if previous_last else None
        out.append({"year": int(year), "drawdown": round(worst * 100.0, 1),
                    "result": round(result, 1) if result is not None else None,
                    "partial": int(year) in (first_year, last_year)})
        previous_last = float(values[-1])
    full = [row for row in out if not row["partial"] and row["result"] is not None]
    summary = None
    if full:
        summary = {"n": len(full), "mean_drawdown": round(sum(r["drawdown"] for r in full) / len(full), 1),
                   "up_years": sum(1 for r in full if r["result"] > 0),
                   "from": full[0]["year"], "to": full[-1]["year"]}
    return {"ok": bool(out), "years": out, "summary": summary}


def _load():
    daily, _meta = j3._download_cached((SYMBOL,), period="max", interval="1d", ttl_seconds=TTL)
    return daily.get(SYMBOL)


def history() -> dict:
    """화면이 부르는 한 벌(⑤ · ⑥ 같이) — 6시간 기억. 못 받으면 ok=False 와 까닭."""
    with _LOCK:
        hit = _MEMO.get("all")
        if hit and time.time() - hit[0] < TTL:
            return hit[1]
    try:
        frame = _load()
    except Exception as exc:
        return {"ok": False, "reason": f"QQQ 일봉을 못 받았습니다 ({exc})"}
    if frame is None or getattr(frame, "empty", True) or len(frame) < 300:
        return {"ok": False, "reason": "QQQ 일봉을 못 받았습니다"}
    value = {"ok": True, "crashes": crash_table(frame), "years": yearly(frame)}
    with _LOCK:
        _MEMO["all"] = (time.time(), value)
    return value


def _md(iso) -> str:
    try:
        y, m, d = str(iso).split("-")
        return f"{y[2:]}.{int(m)}.{int(d)}"
    except Exception:
        return str(iso or "")


def _pct(value, digits=1) -> str:
    if value is None:
        return "—"
    color = "#3ddc97" if value > 0 else "#ff6b6b" if value < 0 else "#e8f0fb"
    return f"<span style='color:{color}'>{value:+.{digits}f}%</span>"


CSS = (
    "<style>"
    ".j12hs-box{background:#0d2340;border:1px solid #1f3a5f;border-radius:12px;padding:.6rem .75rem;margin:.35rem 0 .6rem;}"
    ".j12hs-title{font-weight:900;font-size:.95rem;color:#e8f0fb;}"
    ".j12hs-sub{color:#8fa6c4;font-size:.76rem;margin:.1rem 0 .45rem;}"
    ".j12hs-cmp{display:grid;grid-template-columns:auto 1fr auto;gap:.3rem .5rem;align-items:center;font-size:.84rem;margin:.2rem 0 .5rem;}"
    ".j12hs-track{height:.7rem;border-radius:5px;background:#16304f;overflow:hidden;}"
    ".j12hs-fill{height:100%;border-radius:5px;}"
    ".j12hs-wrap{overflow-x:auto;}"
    ".j12hs-tbl{border-collapse:collapse;width:100%;font-size:.8rem;font-variant-numeric:tabular-nums;}"
    ".j12hs-tbl th{color:#8fa6c4;font-weight:600;text-align:right;padding:.25rem .35rem;border-bottom:1px solid #1f3a5f;white-space:nowrap;}"
    ".j12hs-tbl td{text-align:right;padding:.25rem .35rem;border-bottom:1px solid #132b49;white-space:nowrap;color:#e8f0fb;}"
    ".j12hs-tbl th:first-child,.j12hs-tbl td:first-child{text-align:left;}"
    ".j12hs-now td{background:#1a2f12;}"
    ".j12hs-note{color:#6f86a4;font-size:.72rem;margin-top:.35rem;}"
    ".j12hs-more summary{cursor:pointer;color:#4cc3ff;font-size:.8rem;margin-top:.3rem;}"
    "</style>"
)


def crash_html(table: dict) -> str:
    """⑤ 화면 덩이 — 1년 뒤 두 막대 + 최근 급락 표(나머지는 눌러서)."""
    if not table or not table.get("ok"):
        return ""
    first, bottom = table.get("first"), table.get("bottom")
    bars = ""
    if first and bottom:
        top = max(abs(first["mean"]), abs(bottom["mean"]), 1.0)

        def bar(label, stat, color):
            width = max(3.0, abs(stat["mean"]) / top * 100.0)
            return (f"<span style='color:{color};font-weight:700'>{label}</span>"
                    f"<div class='j12hs-track'><div class='j12hs-fill' style='width:{width:.0f}%;background:{color}'></div></div>"
                    f"<span>{_pct(stat['mean'])} <span style='color:#8fa6c4'>· {stat['n']}번 중 {stat['wins']}번 이익</span></span>")
        bars = ("<div class='j12hs-cmp'>"
                + bar("처음 −5% 다음 날 샀다면", first, "#ffcf5c")
                + bar("바닥 다음 날 샀다면", bottom, "#3ddc97")
                + "</div>")
    rows = list(reversed(table.get("rows") or []))

    def tr(row):
        status = "진행 중" if row["ongoing"] else ""
        cls = " class='j12hs-now'" if row["ongoing"] else ""
        return (f"<tr{cls}><td>{_md(row['start'])}{(' · ' + status) if status else ''}</td>"
                f"<td>{row['first_drop']:.1f}%</td><td style='color:#ff6b6b'>{row['bottom_drop']:.1f}%</td>"
                f"<td>{row['days']}일</td><td>{_pct(row['first_1y'])}</td><td>{_pct(row['bottom_1y'])}</td></tr>")
    head = ("<tr><th>시작</th><th>첫날</th><th>바닥</th><th>바닥까지</th><th>1년 뒤(처음)</th><th>1년 뒤(바닥)</th></tr>")
    recent = "".join(tr(row) for row in rows[:8])
    older = "".join(tr(row) for row in rows[8:])
    more = (f"<details class='j12hs-more'><summary>그 전 급락 {len(rows) - 8}번 더 보기</summary>"
            f"<div class='j12hs-wrap'><table class='j12hs-tbl'>{head}{older}</table></div></details>") if older else ""
    median = table.get("median_between")
    lead = (f"가운데 값으로 첫날 뒤 {median:.1f}%p 더 빠졌다가 바닥 · " if median is not None else "")
    return ("<div class='j12hs-box'><div class='j12hs-title'>📜 지난 급락 기록표 — 처음 빠진 날 대 바닥</div>"
            f"<div class='j12hs-sub'>QQQ {_md(table.get('since'))} 뒤 급락 {len(rows)}번 · {lead}1년 뒤 = 다음 장 시가에 사서 252장 뒤 종가</div>"
            + bars
            + f"<div class='j12hs-wrap'><table class='j12hs-tbl'>{head}{recent}</table></div>{more}"
            "<div class='j12hs-note'>바닥은 지나고 나서야 압니다 · 두 줄의 차이가 바닥을 맞혀야 얻는 몫 · "
            "규칙은 급락 목록과 같음(52주 최고가 대비 −5%) · 보여 주기만</div></div>")


def years_html(data: dict) -> str:
    """⑥ 화면 덩이 — 해마다 막대(연중 최대 하락) + 점(그해 결과) 그림."""
    if not data or not data.get("ok"):
        return ""
    years = data.get("years") or []
    n = len(years)
    width, height, top_pad, mid = 640, 230, 18, 110
    step = width / max(n, 1)
    scale = 1.6                   # 1% = 1.6px
    parts = [f"<line x1='0' y1='{mid}' x2='{width}' y2='{mid}' stroke='#3a5578' stroke-width='1'/>"]
    for index, row in enumerate(years):
        x = index * step + step * 0.18
        w = step * 0.64
        depth = min(abs(row["drawdown"]) * scale, height - mid - 22)
        fill = "#ff6b6b" if not row["partial"] else "#8a5560"
        parts.append(f"<rect x='{x:.1f}' y='{mid}' width='{w:.1f}' height='{depth:.1f}' fill='{fill}' rx='1.5'/>")
        if row["result"] is not None:
            y = mid - max(-mid + top_pad, min(mid - top_pad, row["result"] * scale * 0.5))
            y = max(top_pad - 6, min(height - 8, y))
            dot = "#3ddc97" if row["result"] > 0 else "#ffcf5c"
            parts.append(f"<circle cx='{x + w / 2:.1f}' cy='{y:.1f}' r='{max(2.4, step * 0.18):.1f}' fill='{dot}'/>")
        if row["year"] % 5 == 0 or index in (0, n - 1):
            parts.append(f"<text x='{x + w / 2:.1f}' y='{height - 2}' text-anchor='middle' font-size='11' fill='#8fa6c4'>{row['year']}</text>")
    svg = (f"<svg viewBox='0 0 {width} {height}' width='100%' role='img' aria-label='QQQ 해마다 연중 최대 하락과 그해 결과'>"
           + "".join(parts) + "</svg>")
    summary = data.get("summary") or {}
    line = ""
    if summary:
        line = (f"<div class='j12hs-sub' style='font-size:.84rem;color:#e8f0fb'>{summary['from']}~{summary['to']} "
                f"{summary['n']}해 — 해마다 평균 <b style='color:#ff6b6b'>{abs(summary['mean_drawdown']):.1f}%</b> 빠졌지만 "
                f"<b style='color:#3ddc97'>{summary['up_years']}해</b>는 올랐습니다</div>")
    last = years[-1] if years else None
    now = ""
    if last and last["partial"]:
        now = (f"<div class='j12hs-sub'>올해({last['year']} · 진행 중) 지금까지 가장 깊이 {abs(last['drawdown']):.1f}% · "
               f"올해 결과 {_pct(last['result'])}</div>")
    return ("<div class='j12hs-box'><div class='j12hs-title'>📅 해마다 한 번은 빠진다 — QQQ</div>"
            + line + now + svg
            + "<div class='j12hs-note'>빨간 막대 = 그해 가장 깊이 빠진 폭(그해 최고 종가 → 그 뒤 최저 종가) · "
            "점 = 그해 결과(초록 오름 · 노랑 내림) · 첫해 · 올해는 한 해가 다 안 차 흐리게 · 보여 주기만</div></div>")
