"""자비스13 「📑 재무 한눈에」 — 한국 종목 재무 (2026-11-03 상하님 「자비스12 형식을 따라라 · 재무현황 등도 없고」 · 「DART 빼고」).

자비스12 의 「재무 한눈에」(us_fundamentals · 야후)를 한국 쪽으로 옮긴 것이다. 자료는 **네이버 증권 종목 첫 화면의
「기업실적분석」 표** — 연간 4년 · 분기 6개의 매출액 · 영업이익 · 당기순이익 · ROE · 부채비율 · 당좌비율 · EPS · BPS ·
주당배당금 · 시가배당률(단위 억원 · 원 · %). 증권사 추정치(E 표시 칸)는 **안 쓴다** — 실제로 나온 값만.

**화면은 받으러 가지 않는다** — 깃허브(「자비스13 한국 재무 모으기」 · 주 1회 토요일 아침)가 테마 명부(data/kr_roster.json)
종목을 모아 data/fundamentals/KR.json 에 둔다. 화면은 그 파일만 읽는다(자비스12 와 같다 · CLAUDE.md 10-2).
못 받은 값은 빈칸(None) — 0 으로 채우지 않는다. 못 받은 종목은 파일의 옛 값을 그대로 둔다. 점수·판정에 안 쓴다.
"""

from __future__ import annotations

import html as _html
import io
import json
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

MODULE_REVISION = 2026110301
ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "fundamentals" / "KR.json"
ROSTER_PATH = ROOT / "data" / "kr_roster.json"
URL = "https://finance.naver.com/item/main.naver?code={code}"
SEOUL = timezone(timedelta(hours=9))
ROWS = {"매출액": "rev", "영업이익": "op", "당기순이익": "net", "영업이익률": "opm", "ROE(지배주주)": "roe",
        "ROE": "roe", "부채비율": "debt", "당좌비율": "quick", "EPS(원)": "eps", "BPS(원)": "bps",
        "주당배당금(원)": "dps", "시가배당률(%)": "dy"}
_MEMO: dict = {"at": 0.0, "mtime": None, "value": {}}
_LOCK = threading.Lock()


# ── 받기(깃허브만 부른다) ─────────────────────────────────────────────────────────────

def _num(text):
    """'1,234' · '-56.7' · '' · '-' → 숫자 또는 None."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return None if text != text else float(text)
    text = str(text).strip().replace(",", "")
    if not text or text in ("-", "N/A", "nan"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _decode(content: bytes, header_charset: str | None) -> str:
    for charset in (header_charset, "utf-8", "euc-kr", "cp949"):
        if not charset:
            continue
        try:
            return content.decode(charset)
        except (LookupError, UnicodeDecodeError):
            continue
    return content.decode("utf-8", errors="replace")


def _label(text: str) -> str:
    return re.sub(r"\s+", "", str(text or ""))


def parse(page: str) -> dict | None:
    """네이버 종목 첫 화면 → {"annual": [...], "quarter": [...], "latest": {...}, "mcap", "px", "name"}. 표가 없으면 None."""
    import pandas as pd

    try:
        tables = pd.read_html(io.StringIO(page), match="매출액", flavor="lxml")
    except (ValueError, ImportError):
        return None
    table = next((t for t in tables if any("매출액" in _label(v) for v in t.iloc[:, 0].astype(str))), None)
    if table is None:
        return None
    columns = list(table.columns)
    # 머리글 두 줄(「최근 연간 실적」·「최근 분기 실적」 / 결산 달) — 칸마다 (무리, 달, 추정인가)
    heads = []
    for col in columns[1:]:
        parts = [str(part) for part in (col if isinstance(col, tuple) else (col,))]
        group = "quarter" if any("분기" in part for part in parts) else "annual"
        stamp = next((m.group(0) for part in parts for m in [re.search(r"\d{4}\.\d{2}", part)] if m), None)
        estimate = any("(E)" in part.replace(" ", "") for part in parts)
        heads.append((group, stamp, estimate))
    values: dict[str, list] = {}
    for _index, row in table.iterrows():
        key = ROWS.get(_label(row.iloc[0]))
        if key and key not in values:
            values[key] = [_num(v) for v in list(row.iloc[1:])]
    if "rev" not in values and "op" not in values:
        return None
    out = {"annual": [], "quarter": [], "latest": {}}
    for place, (group, stamp, estimate) in enumerate(heads):
        if not stamp or estimate:
            continue                                    # 추정치는 안 쓴다
        cell = {key: (series[place] if place < len(series) else None) for key, series in values.items()}
        if all(cell.get(k) is None for k in ("rev", "op", "net")):
            continue
        label = stamp[2:4] + "." + stamp[5:7]            # '2025.12' → '25.12'
        out[group].append([label, cell.get("rev"), cell.get("op"), cell.get("net")])
        if group == "annual":
            out["latest"] = {k: cell.get(k) for k in ("opm", "roe", "debt", "quick", "eps", "bps", "dps", "dy")}
            out["latest_at"] = stamp
    # 분기 쪽 값이 더 새로우면(부채비율 등) 그것을 쓴다 — 연간 값이 없을 때만 채운다
    for place, (group, stamp, estimate) in enumerate(heads):
        if group == "quarter" and stamp and not estimate:
            for key in ("debt", "quick"):
                series = values.get(key) or []
                if place < len(series) and series[place] is not None:
                    out.setdefault("latest_q", {})[key] = series[place]
    out["annual"], out["quarter"] = out["annual"][-4:], out["quarter"][-6:]
    match = re.search(r'id="_market_sum"[^>]*>(.*?)</em>', page, re.S)
    if match:
        text = re.sub(r"<[^>]+>|\s", "", match.group(1))
        jo = re.search(r"([\d,]+)조", text)
        rest = re.search(r"(?:조)?([\d,]+)$", text)
        eok = (_num(jo.group(1)) or 0) * 10000 if jo else 0
        if rest and not (jo and rest.group(1) == jo.group(1)):
            eok += _num(rest.group(1)) or 0
        out["mcap"] = eok or None                          # 억원
    price = re.search(r'<p class=["\']no_today["\']>.*?<span class=["\']blind["\']>([\d,]+)</span>', page, re.S)
    out["px"] = _num(price.group(1)) if price else None
    name = re.search(r'<div class=["\']wrap_company["\']>\s*<h2>\s*<a[^>]*>([^<]+)</a>', page)
    out["name"] = name.group(1).strip() if name else None
    return out


def fetch_one(code: str, session=None) -> dict | None:
    import requests

    session = session or requests
    response = session.get(URL.format(code=code), timeout=15, headers={"User-Agent": "Mozilla/5.0 (jarvis13-fundamentals)"})
    if response.status_code != 200:
        return None
    charset = None
    match = re.search(r"charset=([\w-]+)", response.headers.get("content-type", ""), re.I)
    if match:
        charset = match.group(1)
    return parse(_decode(response.content, charset))


def roster_codes(path: Path = ROSTER_PATH) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {code: (info or {}).get("name") or code for code, info in (data.get("stocks") or {}).items()}


def collect(codes: dict, *, path: Path = DATA_PATH, workers: int = 6, limit: int | None = None) -> dict:
    """codes 의 재무를 받아 파일을 고친다. 못 받은 종목은 옛 값을 그대로 둔다. 숫자 요약을 돌려준다."""
    import requests
    from concurrent.futures import ThreadPoolExecutor

    old = load_file(path)
    stocks = dict(old.get("stocks") or {})
    todo = list(codes.items())[:limit] if limit else list(codes.items())
    today = datetime.now(SEOUL).date().isoformat()
    session = requests.Session()
    got = failed = 0

    def _one(item):
        code, name = item
        try:
            return code, name, fetch_one(code, session)
        except Exception:
            return code, name, None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for code, name, result in pool.map(_one, todo):
            if not result:
                failed += 1
                continue
            got += 1
            result["at"] = today
            result["name"] = result.get("name") or name
            stocks[code] = result
    data = {"version": 1, "updated": today, "source": "네이버 증권 기업실적분석", "stocks": stocks}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return {"asked": len(todo), "got": got, "failed": failed, "total": len(stocks)}


# ── 읽기(화면) ──────────────────────────────────────────────────────────────────────

def load_file(path: Path = DATA_PATH) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def load(path: Path = DATA_PATH) -> dict:
    """파일을 한 번만 읽어 둔다(파일이 바뀌면 다시)."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return {}
    with _LOCK:
        if _MEMO["mtime"] == mtime and _MEMO["value"]:
            return _MEMO["value"]
    value = (load_file(path).get("stocks") or {})
    with _LOCK:
        _MEMO.update({"at": time.time(), "mtime": mtime, "value": value})
    return value


def summary(code: str, price_now=None, *, path: Path = DATA_PATH) -> dict | None:
    """화면에 적을 값. 파일에 없으면 None. price_now 를 주면 시가총액·PER·PBR·배당률을 지금 주가로 다시 센다."""
    entry = load(path).get(str(code or "").strip())
    if not isinstance(entry, dict):
        return None
    latest = dict(entry.get("latest") or {})
    latest.update({k: v for k, v in (entry.get("latest_q") or {}).items() if v is not None})
    px, now = _num(entry.get("px")), _num(price_now)
    price = now or px
    mcap = _num(entry.get("mcap"))
    mcap_now = mcap * (now / px) if (mcap and now and px) else mcap
    eps, bps, dps = latest.get("eps"), latest.get("bps"), latest.get("dps")
    loss = eps is not None and eps <= 0
    return {
        "code": code, "name": entry.get("name") or code, "at": entry.get("at"), "latest_at": entry.get("latest_at"),
        "rescaled": bool(now and px), "mcap": mcap_now,
        "per": None if (loss or not eps or not price) else price / eps, "loss": loss,
        "pbr": None if (not bps or bps <= 0 or not price) else price / bps, "equity_bad": bps is not None and bps <= 0,
        "roe": latest.get("roe"), "opm": latest.get("opm"), "debt": latest.get("debt"), "quick": latest.get("quick"),
        "dy": (dps / price * 100.0) if (dps is not None and price) else latest.get("dy"),
        "annual": [row for row in entry.get("annual") or [] if isinstance(row, list) and len(row) == 4],
        "quarter": [row for row in entry.get("quarter") or [] if isinstance(row, list) and len(row) == 4],
    }


def _won_cap(eok) -> str:
    if eok is None:
        return "—"
    return f"{eok / 10000:,.1f}조 원" if eok >= 10000 else f"{eok:,.0f}억 원"


def _eok(value) -> str:
    return "—" if value is None else f"{value:,.0f}"


def _times(value) -> str:
    return "—" if value is None else (f"{value:,.0f}배" if value >= 1000 else f"{value:.1f}배")


def _pct(value) -> str:
    return "—" if value is None else f"{value:.1f}%"


def _bars_svg(rows) -> str:
    values = [v for row in rows for v in (row[1], row[2]) if v is not None]
    if not values:
        return ""
    high, low = max(values + [0.0]), min(values + [0.0])
    reach = (high - low) or 1.0

    def y(value):
        return 2.0 + (high - value) / reach * 96.0

    body = [f"<line x1='0' x2='{len(rows) * 100}' y1='{y(0.0):.1f}' y2='{y(0.0):.1f}' "
            "stroke='rgba(255,255,255,.3)' stroke-width='1' vector-effect='non-scaling-stroke'/>"]
    for place, (_label_, revenue, operating, _net) in enumerate(rows):
        # 한국장 색 — 매출 파랑 · 영업이익 노랑(적자면 파랑 진하게가 아니라 빨강이면 오름과 헷갈려 회색 테두리)
        for offset, value, color in ((20, revenue, "#4da6ff"),
                                     (52, operating, "#ffb020" if (operating or 0) >= 0 else "#9aa0aa")):
            if value is None:
                continue
            top, bottom = sorted((y(value), y(0.0)))
            body.append(f"<rect x='{place * 100 + offset}' y='{top:.1f}' width='28' "
                        f"height='{max(bottom - top, 1.0):.1f}' fill='{color}' rx='2'/>")
    return (f"<svg class='j13fn-bars' viewBox='0 0 {len(rows) * 100} 100' preserveAspectRatio='none'>"
            + "".join(body) + "</svg>")


def _results_html(title: str, rows) -> str:
    if not rows:
        return (f"<div class='j13fn-chart'><div class='j13fn-ct'>{title}</div>"
                "<div class='j13fn-foot'>자료가 없습니다.</div></div>")
    head = "".join(f"<th>{_html.escape(str(row[0]))}</th>" for row in rows)
    revenue = "".join(f"<td>{_eok(row[1])}</td>" for row in rows)
    operating = "".join(f"<td style='color:{'#ffb020' if (row[2] or 0) >= 0 else '#9aa0aa'}'>{_eok(row[2])}</td>"
                        for row in rows)
    net = "".join(f"<td>{_eok(row[3])}</td>" for row in rows)
    return (f"<div class='j13fn-chart'><div class='j13fn-ct'>{title}<span><span><i style='background:#4da6ff'></i>매출</span>"
            "<span><i style='background:#ffb020'></i>영업이익</span></span></div>" + _bars_svg(rows)
            + f"<table class='j13fn-t'><tr><th></th>{head}</tr><tr><td>매출</td>{revenue}</tr>"
            f"<tr><td>영업이익</td>{operating}</tr><tr><td>순이익</td>{net}</tr></table></div>")


def card_html(info: dict) -> str:
    """지표 여덟 칸 · 연간/분기 실적 · 맨 밑 한 줄. 이름표는 증권사 앱 그대로 + 한 줄 뜻."""
    def cell(name, value, note, color="#ffffff"):
        return (f"<div class='j13fn-cell'><b>{name}</b><i style='color:{color}'>{value}</i>"
                f"<small>{note}</small></div>")

    bad = bool(info.get("equity_bad"))
    roe, opm, debt, quick = info.get("roe"), info.get("opm"), info.get("debt"), info.get("quick")
    cells = [
        cell("시가총액", _won_cap(info.get("mcap")), "회사 전체 값"),
        cell("PER", "적자" if info.get("loss") else _times(info.get("per")),
             "1년 이익이 마이너스" if info.get("loss") else "주가 ÷ 1년 주당이익", "#9aa0aa" if info.get("loss") else "#ffffff"),
        cell("PBR", "자본잠식" if bad else _times(info.get("pbr")), "주가 ÷ 주당 자기 돈(장부)"),
        cell("ROE", _pct(roe), "자기 돈으로 1년에 번 이익"),
        cell("영업이익률", _pct(opm), "매출 100에 남긴 영업이익"),
        cell("배당", "없음" if info.get("dy") == 0 else _pct(info.get("dy")), "1년 배당 ÷ 주가"),
        cell("부채비율", _pct(debt) if debt is None else f"{debt:.0f}%",
             "—" if debt is None else f"자기 돈 100에 빚 {debt:.0f}", "#ffb020" if (debt or 0) >= 200 else "#ffffff"),
        cell("당좌비율", _pct(quick) if quick is None else f"{quick:.0f}%", "곧 갚을 빚 100에 곧 쓸 돈"),
    ]
    foot = [f"{_html.escape(str(info.get('at') or ''))} 모은 재무(네이버 증권 기업실적분석 · 추정치는 뺌)"]
    if info.get("latest_at"):
        foot.append(f"지표는 {_html.escape(str(info['latest_at']))} 결산 기준")
    if info.get("rescaled"):
        foot.append("시가총액·PER·PBR·배당은 지금 주가로 다시 셈")
    return ("<div class='j13fn'><div class='j13fn-grid'>" + "".join(cells) + "</div><div class='j13fn-charts'>"
            + _results_html("연간 실적", info.get("annual") or []) + _results_html("분기 실적", info.get("quarter") or [])
            + "</div><div class='j13fn-foot'>단위 억 원 · 칸 위는 결산한 달 · " + " · ".join(foot) + "</div></div>")


CSS = """<style>
.j13fn{display:grid;gap:10px;color:#e6e6e6}
.j13fn-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}
.j13fn-cell{background:#0b1626;border:1px solid #22324a;border-radius:10px;padding:7px 9px;display:grid;gap:2px;min-width:0}
.j13fn-cell b{color:#9fb6c8;font-size:.78rem;font-weight:700}
.j13fn-cell i{font-style:normal;font-size:1.05rem;font-weight:800;font-variant-numeric:tabular-nums}
.j13fn-cell small{color:#8b96a8;font-size:.7rem;line-height:1.3}
.j13fn-charts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
.j13fn-chart{background:#0b1626;border:1px solid #22324a;border-radius:10px;padding:8px;min-width:0;overflow-x:auto}
.j13fn-ct{display:flex;justify-content:space-between;gap:6px;font-weight:800;font-size:.88rem;margin-bottom:4px}
.j13fn-ct span span{font-weight:500;font-size:.72rem;color:#9fb6c8;margin-left:6px}
.j13fn-ct i{display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:3px}
.j13fn-bars{width:100%;height:70px;display:block}
.j13fn-t{width:100%;border-collapse:collapse;font-size:.74rem;font-variant-numeric:tabular-nums}
.j13fn-t th,.j13fn-t td{text-align:right;padding:2px 3px;white-space:nowrap}
.j13fn-t th:first-child,.j13fn-t td:first-child{text-align:left;color:#9fb6c8}
.j13fn-foot{color:#8b96a8;font-size:.74rem;line-height:1.5}
@media (max-width: 600px){.j13fn-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.j13fn-charts{grid-template-columns:1fr}}
</style>"""
