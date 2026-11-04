"""자비스13 「📑 재무 한눈에」 — 한국 종목 재무 (2026-11-03 상하님 「자비스12 형식을 따라라 · 재무현황 등도 없고」 · 「DART 빼고」).

자비스12 의 「재무 한눈에」(us_fundamentals · 야후)를 한국 쪽으로 옮긴 것이다. 자료는 **네이버 증권(모바일) 재무 자료** — 처음에는 종목 첫 화면
「기업실적분석」 표로 하려 했으나 2026-11-03 그 표가 첫 화면에서 빠져 있었다(깃허브 시험). 같은 값 — 연간 4년 · 분기 6개의 매출액 · 영업이익 · 당기순이익 · ROE · 부채비율 · 당좌비율 · EPS · BPS ·
주당배당금 · 시가배당률(단위 억원 · 원 · %). 증권사 추정치(E 표시 칸)는 **안 쓴다** — 실제로 나온 값만.

**화면은 받으러 가지 않는다** — 깃허브(「자비스13 한국 재무 모으기」 · 주 1회 토요일 아침)가 테마 명부(data/kr_roster.json)
종목을 모아 data/fundamentals/KR.json 에 둔다. 화면은 그 파일만 읽는다(자비스12 와 같다 · CLAUDE.md 10-2).
못 받은 값은 빈칸(None) — 0 으로 채우지 않는다. 못 받은 종목은 파일의 옛 값을 그대로 둔다. 점수·판정에 안 쓴다.
"""

from __future__ import annotations

import html as _html
import json
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

MODULE_REVISION = 2026110501
ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "fundamentals" / "KR.json"
ROSTER_PATH = ROOT / "data" / "kr_roster.json"
SEOUL = timezone(timedelta(hours=9))
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


def _label(text: str) -> str:
    return re.sub(r"\s+", "", str(text or ""))


API = "https://m.stock.naver.com/api/stock/{code}/{tail}"
JSON_ROWS = {"매출액": "rev", "영업이익": "op", "당기순이익": "net", "영업이익률": "opm", "ROE": "roe", "부채비율": "debt",
             "당좌비율": "quick", "EPS": "eps", "BPS": "bps", "주당배당금": "dps"}


def _won_text(text):
    """'1,297조 8,739억' · '4,078억' → 억원."""
    text = re.sub(r"\s", "", str(text or ""))
    if not text:
        return None
    jo = re.search(r"([\d,.]+)조", text)
    eok = re.search(r"([\d,.]+)억", text)
    value = (_num(jo.group(1)) or 0) * 10000 if jo else 0
    value += (_num(eok.group(1)) or 0) if eok else 0
    return value or None


def parse_finance(data: dict, group: str) -> tuple[list, dict, str | None]:
    """네이버 모바일 재무(JSON) → (줄[[달, 매출, 영업이익, 순이익] …], 마지막 실제 칸 지표, 그 달). 추정치(isConsensus Y)는 뺀다."""
    info = (data or {}).get("financeInfo") or {}
    heads = [h for h in info.get("trTitleList") or [] if str(h.get("isConsensus") or "N") != "Y" and h.get("key")]
    heads.sort(key=lambda h: str(h["key"]))
    values: dict[str, dict] = {}
    for row in info.get("rowList") or []:
        key = JSON_ROWS.get(_label(row.get("title")))
        if key and key not in values:
            values[key] = {k: _num((v or {}).get("value")) for k, v in (row.get("columns") or {}).items()}
    rows, latest, latest_at = [], {}, None
    for head in heads:
        k = str(head["key"])
        cell = {name: series.get(k) for name, series in values.items()}
        if all(cell.get(n) is None for n in ("rev", "op", "net")):
            continue
        rows.append([f"{k[2:4]}.{k[4:6]}", cell.get("rev"), cell.get("op"), cell.get("net")])
        latest = {n: cell.get(n) for n in ("opm", "roe", "debt", "quick", "eps", "bps", "dps")}
        latest_at = f"{k[:4]}.{k[4:6]}"
    return rows[-(4 if group == "annual" else 6):], latest, latest_at


def parse_consensus(whole: dict) -> dict | None:
    """integration 의 consensusInfo → {"recomm": 투자의견 평균(1~5) · "target": 목표주가 평균(원) · "at": 기준일}. 없으면 None."""
    info = (whole or {}).get("consensusInfo") or {}
    recomm, target = _num(info.get("recommMean")), _num(info.get("priceTargetMean"))
    if not recomm and not target:
        return None
    return {"recomm": recomm, "target": target, "at": str(info.get("createDate") or "")[:10] or None}


def parse_reports(whole: dict, keep: int = 3) -> list:
    """integration 의 researches → [[증권사, 날짜]] 최근 keep 건(제목은 안 옮긴다)."""
    out = []
    for item in (whole or {}).get("researches") or []:
        if not isinstance(item, dict):
            continue
        broker, day = str(item.get("bnm") or "").strip(), str(item.get("wdt") or "").strip()
        if broker:
            out.append([broker, day])
        if len(out) >= keep:
            break
    return out


def parse_estimate(data: dict) -> dict | None:
    """네이버 모바일 재무(분기)의 증권사 예상(E) 칸 → {"at": "2026.09", "rev": 억원, "op": 억원}. 없으면 None.
    「📅 실적 발표」 상자의 「이번 예상」에만 쓴다 — 재무 표에는 여전히 실제 값만 둔다(CLAUDE.md 10-3)."""
    info = (data or {}).get("financeInfo") or {}
    heads = [h for h in info.get("trTitleList") or [] if str(h.get("isConsensus") or "N") == "Y" and h.get("key")]
    if not heads:
        return None
    key = sorted(str(h["key"]) for h in heads)[0]
    out = {"at": f"{key[:4]}.{key[4:6]}"}
    for row in info.get("rowList") or []:
        name = JSON_ROWS.get(_label(row.get("title")))
        if name in ("rev", "op"):
            out[name] = _num(((row.get("columns") or {}).get(key) or {}).get("value"))
    return out if (out.get("op") is not None or out.get("rev") is not None) else None


def parse_wise_count(html_text: str):
    """와이즈리포트(네이버 기업정보) 투자의견 표(cTB15)의 「추정기관수」 → 정수. 못 읽으면 None."""
    at = str(html_text or "").find('id="cTB15"')
    if at < 0:
        return None
    table = html_text[at:html_text.find("</table>", at)]
    cells = [" ".join(re.sub(r"<[^>]+>", " ", c).split()) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", table, re.S)]
    if "추정기관수" not in cells:
        return None
    idx = cells.index("추정기관수")
    labels = [c for c in cells[:idx + 1] if re.search(r"[가-힣A-Za-z]", c)]     # 글자 칸만 머리글(앞의 「4.00」 바늘 값은 뺀다)
    values = cells[idx + 1:]
    try:
        value = values[labels.index("추정기관수")]
        number = int(float(str(value).replace(",", "")))
    except (IndexError, ValueError):
        return None
    return number if number > 0 else None


DART_API = "https://opendart.fss.or.kr/api/"
INSIDER_DAYS = 183


def dart_extra(api_key: str, corp_code: str, session, today=None) -> dict:
    """DART 에서 「📅 실적 발표 · 🔍 내부자 · 배당」 자료(2026-11-04 밤 상하님 「왜 이거 안 넣냐」). 못 받은 것은 빼고 돌려준다.
      · earn — 잠정실적 공시일(정정 빼고 · 최근 8번) · divdays — 현금 · 현물배당결정 공시일(최근 4번)
      · ins — 최근 6개월 임원 · 주요주주 소유보고: 늘림/줄임 횟수 · 주식 수(장내 매매가 아닌 것도 섞인다)
      · divd — 지난 사업보고서의 주당 현금배당금 · 현금배당수익률(보통주) · 현금배당성향"""
    from datetime import date as _date, timedelta as _td

    today = today or datetime.now(SEOUL).date()
    out: dict = {}

    def get(name, **params):
        response = session.get(DART_API + name, params={"crtfc_key": api_key, "corp_code": corp_code, **params}, timeout=15)
        data = response.json() if response.status_code == 200 else {}
        return data if str(data.get("status")) in ("000", "013") else None

    try:
        listed = get("list.json", bgn_de=(today - _td(days=760)).strftime("%Y%m%d"), end_de=today.strftime("%Y%m%d"),
                     pblntf_ty="I", page_count=100)
        rows = (listed or {}).get("list") or []
        def day(row):
            raw = re.sub(r"\D", "", str(row.get("rcept_dt") or ""))[:8]
            return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}" if len(raw) == 8 else ""
        earn = sorted({day(r) for r in rows if "잠정" in str(r.get("report_nm")) and "실적" in str(r.get("report_nm"))
                       and "정정" not in str(r.get("report_nm")) and day(r)}, reverse=True)
        divdays = sorted({day(r) for r in rows if "배당결정" in str(r.get("report_nm")) and "정정" not in str(r.get("report_nm"))
                          and day(r)}, reverse=True)
        if listed is not None:
            out["earn"] = earn[:8]
            out["divdays"] = divdays[:4]
    except Exception:
        pass
    try:
        owned = get("elestock.json")
        if owned is not None:
            since = (today - _td(days=INSIDER_DAYS)).isoformat()
            since_digits = since.replace("-", "")
            up = down = up_sh = down_sh = 0
            for row in owned.get("list") or []:
                filed = re.sub(r"\D", "", str(row.get("rcept_dt") or ""))[:8]     # 「20260505」 · 「2026-05-05」 둘 다
                if len(filed) != 8 or filed < since_digits:
                    continue
                change = _num(row.get("sp_stock_lmp_irds_cnt"))
                if not change:
                    continue
                if change > 0:
                    up, up_sh = up + 1, up_sh + change
                else:
                    down, down_sh = down + 1, down_sh - change
            out["ins"] = {"since": since, "up": up, "down": down, "up_sh": up_sh, "down_sh": down_sh}
    except Exception:
        pass
    for year in (today.year - 1, today.year - 2):
        try:
            matter = get("alotMatter.json", bsns_year=str(year), reprt_code="11011")
        except Exception:
            matter = None
        items = (matter or {}).get("list") or []
        if not items:
            continue
        found: dict = {"year": year}
        for item in items:
            label, value = str(item.get("se") or ""), _num(item.get("thstrm"))
            if value is None:
                continue
            if "주당 현금배당금" in label and "dps" not in found:
                found["dps"] = value
            elif "현금배당수익률" in label and "yield" not in found:
                found["yield"] = value
            elif "현금배당성향" in label and "payout" not in found:
                found["payout"] = value
        out["divd"] = found
        break
    return out


def fetch_one(code: str, session=None) -> dict | None:
    """연간 · 분기 재무와 시총 · 주가 · 이름. 재무를 못 받으면 None(옛 값을 둔다)."""
    import requests

    session = session or requests
    headers = {"User-Agent": "Mozilla/5.0 (jarvis13-fundamentals)"}

    def get(tail):
        response = session.get(API.format(code=code, tail=tail), timeout=15, headers=headers)
        return response.json() if response.status_code == 200 else None

    annual, quarter = get("finance/annual"), get("finance/quarter")
    if not annual and not quarter:
        return None
    a_rows, a_latest, a_at = parse_finance(annual or {}, "annual")
    q_rows, q_latest, _q_at = parse_finance(quarter or {}, "quarter")
    if not a_rows and not q_rows:
        return None
    out = {"annual": a_rows, "quarter": q_rows, "latest": a_latest, "latest_at": a_at,
           "latest_q": {k: q_latest.get(k) for k in ("debt", "quick") if q_latest.get(k) is not None}}
    try:
        whole = get("integration") or {}
    except Exception:
        whole = {}
    infos = {str(item.get("code")): item.get("value") for item in whole.get("totalInfos") or [] if isinstance(item, dict)}
    out["name"] = whole.get("stockName")
    out["mcap"] = _won_text(infos.get("marketValue"))
    # 증권사 앱 맨 위 칸 셋(2026-11-03 · 같은 integration 자료 — 새로 받는 곳 없음) — 모은 날 기준이라 화면에 그날을 적는다
    out["hi52"] = _num(infos.get("highPriceOf52Weeks"))
    out["lo52"] = _num(infos.get("lowPriceOf52Weeks"))
    out["foreign"] = _num(str(infos.get("foreignRate") or "").replace("%", ""))
    # 증권사 의견(2026-11-04 상하님 「3번째 캡쳐 빠졌고」 — 자비스12 「애널리스트 의견 · 목표주가」 자리) — 같은 integration 자료라
    # 새로 받는 곳이 없다. 점수 · 판정에 안 쓴다(보여 주기만). 리포트는 증권사 · 날짜만 둔다(제목은 남의 글이라 안 옮긴다 · 저장소 공개).
    out["consensus"] = parse_consensus(whole)
    out["reports"] = parse_reports(whole)
    out["est"] = parse_estimate(quarter or {})
    if out["consensus"]:
        # 증권사 의견 몇 곳(추정기관 수) — 의견이 있는 종목만 한 번 더 묻는다(와이즈리포트 · 네이버 기업정보 첫 화면)
        try:
            page = session.get(f"https://navercomp.wisereport.co.kr/v2/company/c1010001.aspx?cmp_cd={code}", timeout=15,
                               headers=headers)
            out["consensus"]["n"] = parse_wise_count(page.content.decode("utf-8", errors="replace"))
        except Exception:
            pass
    try:
        basic = get("basic") or {}
    except Exception:
        basic = {}
    out["px"] = _num(basic.get("closePrice"))
    return out


def roster_codes(path: Path = ROSTER_PATH) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {code: (info or {}).get("name") or code for code, info in (data.get("stocks") or {}).items()}


def collect(codes: dict, *, path: Path = DATA_PATH, workers: int = 6, limit: int | None = None,
            dart_key: str | None = None) -> dict:
    """codes 의 재무를 받아 파일을 고친다. 못 받은 종목은 옛 값을 그대로 둔다. 숫자 요약을 돌려준다.
    dart_key 가 있으면 DART(잠정실적 공시일 · 내부자 · 배당)도 같이 받는다 — 못 받으면 그 칸만 옛 값 그대로."""
    import requests
    from concurrent.futures import ThreadPoolExecutor

    old = load_file(path)
    stocks = dict(old.get("stocks") or {})
    todo = list(codes.items())[:limit] if limit else list(codes.items())
    today = datetime.now(SEOUL).date().isoformat()
    session = requests.Session()
    got = failed = 0
    corp_map: dict = {}
    if dart_key:
        try:
            import disclosure_data

            mapped = disclosure_data.fetch_dart_corp_code_map(dart_key)
            corp_map = mapped.get("data") if isinstance(mapped, dict) and isinstance(mapped.get("data"), dict) else {}
        except Exception:
            corp_map = {}

    def _one(item):
        code, name = item
        try:
            result = fetch_one(code, session)
        except Exception:
            return code, name, None
        corp = (corp_map.get(code) or {}).get("corp_code") if result else None
        if corp:
            try:
                result.update(dart_extra(dart_key, corp, session))
            except Exception:
                pass
        return code, name, result

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for code, name, result in pool.map(_one, todo):
            if not result:
                failed += 1
                continue
            got += 1
            result["at"] = today
            result["name"] = result.get("name") or name
            # 이번에 못 받은 DART 칸은 옛 값을 그대로 둔다(있던 것을 지우지 않는다 · CLAUDE.md 0-0 ②)
            for field in ("earn", "divdays", "ins", "divd"):
                if field not in result and field in (stocks.get(code) or {}):
                    result[field] = stocks[code][field]
            stocks[code] = result
    data = {"version": 1, "updated": today, "source": "네이버 증권 재무(모바일)", "stocks": stocks}
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
        "dps": dps,
        "hi52": _num(entry.get("hi52")), "lo52": _num(entry.get("lo52")), "foreign": _num(entry.get("foreign")),
        "price": price,
        "consensus": entry.get("consensus") if isinstance(entry.get("consensus"), dict) else None,
        "est": entry.get("est") if isinstance(entry.get("est"), dict) else None,
        "earn": [str(day) for day in entry.get("earn") or []],
        "divdays": [str(day) for day in entry.get("divdays") or []],
        "ins": entry.get("ins") if isinstance(entry.get("ins"), dict) else None,
        "divd": entry.get("divd") if isinstance(entry.get("divd"), dict) else None,
        "reports": [row for row in entry.get("reports") or [] if isinstance(row, list) and len(row) == 2],
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
    operating = "".join(f"<td style='color:{'#ffb020' if (row[2] or 0) >= 0 else NEG}'>{_eok(row[2])}</td>"
                        for row in rows)
    net = "".join(f"<td style='color:{NEG if (row[3] or 0) < 0 else '#e6e6e6'}'>{_eok(row[3])}</td>" for row in rows)
    return (f"<div class='j13fn-chart'><div class='j13fn-ct'>{title}<span><span><i style='background:#4da6ff'></i>매출</span>"
            "<span><i style='background:#ffb020'></i>영업이익</span></span></div>" + _bars_svg(rows)
            + f"<table class='j13fn-t'><tr><th></th>{head}</tr><tr><td>매출</td>{revenue}</tr>"
            f"<tr><td>영업이익</td>{operating}</tr><tr><td>순이익</td>{net}</tr></table></div>")


# 색 — 마이너스 숫자는 한국 「내림」 파랑 · 위험 비율은 주의색. 문턱은 자비스12 와 같다(부채 200% · 유동/당좌 100%=1배).
NEG = "#5aa9ff"
UP = "#ff5b5b"
WARN = "#ffb020"
DEBT_WARN = 200.0
QUICK_WARN = 100.0


def card_html(info: dict) -> str:
    """지표 여덟 칸 · 연간/분기 실적 · 맨 밑 한 줄. 이름표는 증권사 앱 그대로 + 한 줄 뜻."""
    def cell(name, value, note, color="#ffffff"):
        return (f"<div class='j13fn-cell'><b>{name}</b><i style='color:{color}'>{value}</i>"
                f"<small>{note}</small></div>")

    bad = bool(info.get("equity_bad"))
    roe, opm, debt, quick = info.get("roe"), info.get("opm"), info.get("debt"), info.get("quick")
    # 색 기준 — 자비스12(us_fundamentals.card_html)와 같은 문턱(2026-11-04 상하님 「부채비율 유동비율 색깔 봐라 · 기준이 안 되어
    # 색깔이 같은 거냐?」). 한국 화면은 빨강이 「오름」이라 마이너스는 파랑(NEG) · 위험 비율은 주의색(WARN).
    neg = lambda value: NEG if (value is not None and value < 0) else "#ffffff"          # noqa: E731
    cells = [
        cell("시가총액", _won_cap(info.get("mcap")), "회사 전체 값"),
        cell("PER", "적자" if info.get("loss") else _times(info.get("per")),
             "1년 이익이 마이너스" if info.get("loss") else "주가 ÷ 1년 주당이익", NEG if info.get("loss") else "#ffffff"),
        cell("PBR", "자본잠식" if bad else _times(info.get("pbr")),
             "자기 돈이 마이너스" if bad else "주가 ÷ 주당 자기 돈(장부)", WARN if bad else "#ffffff"),
        cell("ROE", _pct(roe), "자기 돈으로 1년에 번 이익", neg(roe)),
        cell("영업이익률", _pct(opm), "매출 100에 남긴 영업이익", neg(opm)),
        cell("배당", "없음" if info.get("dy") == 0 else _pct(info.get("dy")), "1년 배당 ÷ 주가"),
        cell("부채비율", _pct(debt) if debt is None else f"{debt:.0f}%",
             "—" if debt is None else f"자기 돈 100에 빚 {debt:.0f} · {DEBT_WARN:.0f}↑ 주의",
             WARN if bad or (debt or 0) >= DEBT_WARN else "#ffffff"),
        cell("당좌비율", _pct(quick) if quick is None else f"{quick:.0f}%",
             f"곧 갚을 빚 100에 곧 쓸 돈 · {QUICK_WARN:.0f}↓ 주의",
             WARN if (quick is not None and quick < QUICK_WARN) else "#ffffff"),
    ]
    # 52주 최고·최저 · 외국인 비율 — 값이 있을 때만 한 줄(없으면 줄 자체를 안 그린다 · 0 으로 안 채움)
    hi, lo, price, foreign = info.get("hi52"), info.get("lo52"), info.get("price"), info.get("foreign")
    extra = []
    if hi:
        gap = f" · 지금 {price / hi * 100 - 100:+.1f}%" if price else ""
        extra.append(cell("52주 최고", f"{hi:,.0f}원", "1년 안 가장 높은 값" + gap))
    if lo:
        gap = f" · 지금 {price / lo * 100 - 100:+.1f}%" if price else ""
        extra.append(cell("52주 최저", f"{lo:,.0f}원", "1년 안 가장 낮은 값" + gap))
    if foreign is not None:
        extra.append(cell("외국인 비율", f"{foreign:.1f}%", "외국인이 가진 몫(한도 대비 소진율)"))
    if extra:
        cells = extra + cells
    foot = [f"{_html.escape(str(info.get('at') or ''))} 모은 재무(네이버 증권 · 추정치는 뺌)"]
    foot.append(f"<span style='color:{NEG}'>파랑</span> 마이너스 · <span style='color:{WARN}'>주황</span> 주의")
    if info.get("latest_at"):
        foot.append(f"지표는 {_html.escape(str(info['latest_at']))} 결산 기준")
    if info.get("rescaled"):
        foot.append("시가총액·PER·PBR·배당은 지금 주가로 다시 셈")
    return ("<div class='j13fn'><div class='j13fn-grid'>" + "".join(cells) + "</div><div class='j13fn-charts'>"
            + _results_html("연간 실적", info.get("annual") or []) + _results_html("분기 실적", info.get("quarter") or [])
            + "</div><div class='j13fn-foot'>단위 억 원 · 칸 위는 결산한 달 · " + " · ".join(foot) + "</div></div>")


RECOMM_WORDS = ((4.5, "강력 매수"), (3.5, "매수"), (2.5, "중립"), (1.5, "매도"), (0.0, "강력 매도"))


def recomm_word(value) -> str:
    """투자의견 평균(5 강력 매수 · 4 매수 · 3 중립 · 2 매도 · 1 강력 매도) → 가장 가까운 말."""
    for floor, word in RECOMM_WORDS:
        if value is not None and value >= floor:
            return word
    return "—"


def _md(day) -> str:
    """리포트 날짜 「20261030」 · 「2026-10-30」 → 「10/30」. 못 읽으면 빈 글(지어내지 않는다)."""
    digits = re.sub(r"\D", "", str(day or ""))
    return f"{int(digits[4:6])}/{int(digits[6:8])}" if len(digits) == 8 else ""


def _box(title: str, rows: list, extra: str = "") -> str:
    body = "".join(f"<div class='j13st-row'><b>{name}</b><span>{value}</span></div>" for name, value in rows)
    return f"<div class='j13st-box'><div class='j13st-h'>{title}</div>{body}{extra}</div>"


def _quarter_of(day: str) -> str:
    """잠정실적 공시일 → 그 실적의 분기 「YY.MM」(공시일 바로 앞의 분기 끝). 1~3월 공시는 앞해 12월."""
    try:
        year, month = int(day[:4]), int(day[5:7])
    except (TypeError, ValueError):
        return ""
    end_month = ((month - 1) // 3) * 3
    if end_month == 0:
        year, end_month = year - 1, 12
    return f"{str(year)[2:]}.{end_month:02d}"


def reaction(frame, day: str):
    """발표 앞뒤 주가 — 발표일 **앞 장** 종가 → 발표일 **뒤 장** 종가 % (공시 시각을 몰라 앞뒤 하루씩 넓게 잰다). 못 재면 None."""
    try:
        closes = frame["Close"].dropna()
        days = [str(stamp)[:10] for stamp in closes.index]
        values = [float(v) for v in closes.tolist()]
    except Exception:
        return None
    before = [v for d, v in zip(days, values) if d < day]
    after = [v for d, v in zip(days, values) if d > day]
    if not before or not after or not before[-1]:
        return None
    return (after[0] / before[-1] - 1.0) * 100.0


def _first_per_quarter(earn: list) -> list:
    """분기마다 **첫** 잠정실적 공시일만(최근 것부터). 삼성전자처럼 한 분기에 두 번(10/8 잠정 · 10/29 확정 앞 잠정) 내는 회사가 있다
    (2026-11-04 깃허브 실제 자료) — 주가가 먼저 움직이는 것은 첫 발표다."""
    first: dict = {}
    for day in earn:
        quarter = _quarter_of(day)
        if quarter and (quarter not in first or day < first[quarter]):
            first[quarter] = day
    return sorted(first.values(), reverse=True)


def _next_guess(earn: list, today) -> str:
    """다음 잠정실적 발표 어림 — 작년 같은 때 발표일 + 1년(없으면 마지막 발표 + 91일). 「추정」으로만 적는다."""
    from datetime import date as _date, timedelta as _td

    days = []
    for raw in _first_per_quarter(earn):
        try:
            days.append(_date.fromisoformat(raw))
        except ValueError:
            continue
    if not days:
        return ""
    last = max(days)
    target = last + _td(days=91)
    yearly = [d + _td(days=364) for d in days if abs(((d + _td(days=364)) - target).days) <= 30]
    guess = min(yearly, key=lambda d: abs((d - target).days)) if yearly else target
    if guess <= today:
        return "곧 · 지난해 이맘때 발표"
    return f"{guess.month}월 {guess.day}일쯤 · {(guess - today).days}일 남음"


def _earn_box(info: dict, frame, today) -> str:
    earn = _first_per_quarter([d for d in info.get("earn") or [] if d])[:4]
    est = info.get("est") or {}
    if not earn and not est:
        return ""
    rows = []
    guess = _next_guess(info.get("earn") or [], today)
    if guess:
        rows.append(("다음 발표", f"<span class='j13st-hl'>{guess.split(' · ')[0]}</span>"
                     + (f" · {guess.split(' · ')[1]}" if " · " in guess else "") + " <span class='j13st-dim'>· 추정</span>"))
    if est.get("op") is not None:
        rows.append(("이번 예상", f"{_html.escape(str(est.get('at') or ''))[2:]} 영업이익 <b>{_won_cap(est['op'])}</b>"
                     + (f" · 매출 {_won_cap(est['rev'])}" if est.get("rev") is not None else "")
                     + " <span class='j13st-dim'>· 증권사 평균</span>"))
    table = ""
    if earn:
        op_by_q = {str(row[0]): row[2] for row in info.get("quarter") or [] if len(row) >= 3}
        cols = list(reversed(earn))
        moves = [reaction(frame, d) if frame is not None else None for d in cols]
        head = "".join(f"<th>{_quarter_of(d)}</th>" for d in cols)
        dates = "".join(f"<td>{int(d[5:7])}/{int(d[8:10])}</td>" for d in cols)
        ops = "".join(f"<td>{_eok(op_by_q.get(_quarter_of(d)))}</td>" for d in cols)
        move_cells = "".join("<td>—</td>" if m is None else
                             f"<td style='color:{UP if m > 0 else NEG}'>{m:+.1f}%</td>" for m in moves)
        table = (f"<table class='j13st-eps'><tr><th>분기</th>{head}</tr><tr><td>발표일</td>{dates}</tr>"
                 f"<tr><td>영업이익</td>{ops}</tr><tr class='j13st-move'><td>앞뒤 주가</td>{move_cells}</tr></table>"
                 "<div class='j13st-note'>발표일 = DART 잠정실적 공시 · 영업이익 = 실제(억 원) · 앞뒤 주가 = 발표 전날 → 다음 날 종가. "
                 "지난 분기 증권사 예상은 남지 않아 「예상 대 실제」는 못 적습니다.</div>")
    body = "".join(f"<div class='j13st-row'><b>{name}</b><span>{value}</span></div>" for name, value in rows)
    return f"<div class='j13st-box'><div class='j13st-h'>📅 실적 발표</div>{body}{table}</div>"


def _ana_box(info: dict) -> str:
    consensus = info.get("consensus") or {}
    reports = info.get("reports") or []
    recomm, target, price = _num(consensus.get("recomm")), _num(consensus.get("target")), _num(info.get("price"))
    count = consensus.get("n")
    if not (recomm or target or reports):
        return ""
    at = _html.escape(str(consensus.get("at") or ""))
    parts = [f"<div class='j13st-h'>👥 애널리스트 의견" + (f" <span class='j13st-dim'>· {int(count)}곳</span>" if count else "")
             + (f" <span class='j13st-dim'>· {at[5:].replace('-', '/')} 기준</span>" if at else "") + "</div>"]
    if recomm:
        place = max(0.0, min(100.0, (recomm - 1.0) / 4.0 * 100.0))
        parts.append(
            f"<div class='j13st-row'><b>투자의견</b><span><span class='j13st-hl'>{recomm:.2f}</span> / 5 · "
            f"<b class='j13st-word'>{recomm_word(recomm)}</b> <span class='j13st-dim'>· 여러 증권사 평균</span></span></div>"
            f"<div class='j13st-range'><div class='j13st-line'></div><i class='j13st-mk' style='left:{place:.1f}%'></i>"
            "<span class='j13st-lab' style='left:0'>1 강력 매도</span><span class='j13st-lab' style='left:50%;transform:translateX(-50%)'>3 중립</span>"
            "<span class='j13st-lab' style='right:0'>5 강력 매수</span></div>")
    if target:
        parts.append(f"<div class='j13st-h2'>🎯 목표주가 <span class='j13st-dim'>· 평균"
                     + (f" · {int(count)}곳" if count else "") + " · 1년 뒤 예상</span></div>"
                     f"<div class='j13st-row'><b>평균</b><span><span class='j13st-hl'>{target:,.0f}원</span>"
                     + (f" <span class='j13st-dim'>· 지금 {price:,.0f}원</span>" if price else "") + "</span></div>")
        if price:
            gap = target / price * 100.0 - 100.0
            parts.append(f"<div class='j13st-row'><b>평균까지</b><span class='{'j13st-up' if gap >= 0 else 'j13st-dn'}'>"
                         f"지금보다 {gap:+.0f}%</span></div>")
    if reports:
        listed = " · ".join(f"{_html.escape(str(b))} {_html.escape(_md(d))}" for b, d in reports)
        parts.append(f"<div class='j13st-row'><b>최근 리포트</b><span>{listed}</span></div>")
    parts.append("<div class='j13st-note'>※ 증권사 애널리스트 의견입니다(네이버 증권 · 주 1회 모음). 자비스 점수·판정에는 들어가지 않습니다.</div>")
    return f"<div class='j13st-box'>{''.join(parts)}</div>"


def _own_box(info: dict) -> str:
    rows = []
    foreign = _num(info.get("foreign"))
    ins = info.get("ins") or {}
    if ins:
        up, down = int(ins.get("up") or 0), int(ins.get("down") or 0)
        if up or down:
            body = (f"늘림 {up}번" + (f"({_shares(ins.get('up_sh'))})" if up else "")
                    + f" · 줄임 {down}번" + (f"({_shares(ins.get('down_sh'))})" if down else ""))
        else:
            body = "보고된 늘림 · 줄임 없음"
        rows.append(("내부자", body + " <span class='j13st-dim'>· 최근 6개월 임원·주요주주 보고(DART)</span>"))
    divd = info.get("divd") or {}
    if divd.get("dps"):
        bits = [f"주당 {divd['dps']:,.0f}원"]
        if divd.get("yield") is not None:
            bits.append(f"배당수익률 {divd['yield']:.1f}%")
        if divd.get("payout") is not None:
            bits.append(f"배당성향 {divd['payout']:.0f}%")
        days = info.get("divdays") or []
        tail = f" · 최근 배당 결정 {int(days[0][5:7])}/{int(days[0][8:10])}" if days else ""
        rows.append(("배당", " · ".join(bits) + f" <span class='j13st-dim'>· {divd.get('year')}년 사업보고서{tail}</span>"))
    elif divd:
        rows.append(("배당", f"{divd.get('year')}년 현금배당 없음"))
    else:
        dps, dy = _num(info.get("dps")), _num(info.get("dy"))
        if dps:
            rows.append(("배당", f"주당 {dps:,.0f}원" + (f" · 지금 주가로 {dy:.2f}%" if dy else "")))
    if foreign is not None:
        rows.append(("외국인", f"외국인이 가진 몫 {foreign:.1f}% <span class='j13st-dim'>· 한도 대비 소진율</span>"))
    if not rows:
        return ""
    # 자비스12 차례 — 공매도 · 내부자 · 배당(한국은 공매도를 못 받아 그렇다고 적고, 외국인 몫을 끝에 더한다)
    rows.insert(0, ("공매도", "<span class='j13st-dim'>못 받음 — 거래소가 로그인한 사람에게만 보여 줌</span>"))
    body = "".join(f"<div class='j13st-row'><b>{name}</b><span>{value}</span></div>" for name, value in rows)
    return (f"<div class='j13st-box'><div class='j13st-h'>🔍 공매도 · 내부자 · 배당</div>{body}"
            "<div class='j13st-note'>내부자 늘림 · 줄임에는 장내 매매 아닌 것(상여 · 상속 등)도 섞입니다.</div></div>")


def _shares(value) -> str:
    number = _num(value) or 0
    return f"{number / 10000:,.1f}만 주" if number >= 10000 else f"{number:,.0f}주"


def street_html(info: dict, frame=None, today=None) -> str:
    """종목 개요 밑 상자 셋 — 자비스12 「📅 실적 발표 · 👥 애널리스트 의견 · 🔍 공매도·내부자·배당」 자리 · 차례(2026-11-04 상하님
    「위치 등 이 형식을 따르지」 · 밤 「왜 이거 안 넣냐 말 좀 들어라」). 「📑 재무 한눈에 보기」 단추 **위**에 따로 선다.
    한국에서 받을 수 있는 것만 — 없는 칸은 안 그린다(지어내지 않는다)."""
    today = today or datetime.now(SEOUL).date()
    boxes = [box for box in (_earn_box(info, frame, today), _ana_box(info), _own_box(info)) if box]
    return f"<div class='j13st'>{''.join(boxes)}</div>" if boxes else ""


NAVER_COINFO_URL = "https://finance.naver.com/item/coinfo.naver?code={code}"
OVERVIEW_THEMES = 6


def roster_themes(code: str, path: Path = ROSTER_PATH) -> list:
    """테마 명부에서 이 종목이 든 테마 이름들(없으면 빈 목록)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return list(((data.get("stocks") or {}).get(str(code or "").strip()) or {}).get("themes") or [])


def overview_html(code: str, name: str = "", *, theme: str = "", themes=None, info: dict | None = None) -> str:
    """세부사항 이름 밑 「🏢 종목 개요」 — 자비스12(us_fundamentals.overview_html) 자리 · 모양(2026-11-04 상하님 「미국테마 형식을
    따라서 해라」). 한국은 회사 소개 글 · 업종 · 본사 · 직원 자료가 앱에 없어 **지어내지 않고** 있는 것만 — 앱 테마 · 시가총액 ·
    네이버 기업 개요 원문 주소. 지금 보는 테마를 맨 앞에 둔다."""
    code = str(code or "").strip()
    esc = _html.escape
    names = list(themes if themes is not None else roster_themes(code))
    if theme and theme in names:
        names.remove(theme)
    if theme:
        names.insert(0, theme)
    shown, rest = names[:OVERVIEW_THEMES], len(names) - OVERVIEW_THEMES
    chips = "".join(f"<span class='j13ov-chip j13ov-t'>앱 테마 · {esc(str(n))}</span>" for n in shown)
    if rest > 0:
        chips += f"<span class='j13ov-chip'>외 {rest}개</span>"
    head = [code]
    mcap = _num((info or {}).get("mcap"))
    if mcap:
        head.append(f"시가총액 {_won_cap(mcap)}")
    url = NAVER_COINFO_URL.format(code=esc(code))
    return (OVERVIEW_CSS + "<div class='j13ov'>"
            f"<div class='j13ov-h'><b>🏢 {esc(str(name or (info or {}).get('name') or code))}</b>"
            f"<span>{esc(' · '.join(head))}</span></div>"
            + (f"<div class='j13ov-chips'>{chips}</div>" if chips else "")
            + f"<a class='j13ov-more' href='{url}' target='_blank' rel='noopener noreferrer'>▸ 네이버 증권에서 기업 개요 원문 보기</a>"
            "</div>")


OVERVIEW_CSS = """<style>
.j13ov{margin:10px 0 4px;border:1px solid #2b4f80;border-radius:13px;padding:10px 12px 9px;background:rgba(77,127,208,.10)}
.j13ov-h{display:flex;align-items:baseline;gap:4px 8px;flex-wrap:wrap}
.j13ov-h b{font-size:1rem;font-weight:900;color:#fff}
.j13ov-h span{font-size:.78rem;color:#8fb4de}
.j13ov-chips{display:flex;flex-wrap:wrap;gap:6px;margin:7px 0}
.j13ov-chip{font-size:.78rem;font-weight:700;padding:1px 9px;border-radius:999px;border:1px solid #2b4f80;color:#cfe0ff}
.j13ov-chip.j13ov-t{border-color:#7c3aed;background:rgba(124,58,237,.18);color:#e9d5ff}
a.j13ov-more{display:inline-block;margin-top:2px;font-size:.78rem;font-weight:700;color:#c084fc!important;text-decoration:none!important}
</style>"""


def street_block(code: str, price_now=None, *, frame=None, path: Path = DATA_PATH) -> str:
    """화면이 부르는 한 덩이(꾸밈 + 상자). 파일에 없으면 빈 글. frame — 일봉(실적 발표 앞뒤 주가를 잰다 · 세부사항이 이미 받은 것)."""
    info = summary(code, price_now, path=path)
    html_text = street_html(info, frame) if info else ""
    return (STREET_CSS + html_text) if html_text else ""


STREET_CSS = """<style>
.j13st{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:8px;margin:8px 0 4px}
.j13st-box{border:1px solid #2b4f80;border-radius:13px;padding:10px 12px 9px;background:rgba(77,127,208,.10);min-width:0}
.j13st-h{font-size:.95rem;font-weight:900;color:#fff;margin-bottom:5px}
.j13st-h2{font-size:.88rem;font-weight:900;color:#fff;margin:10px 0 0}
.j13st-row{display:flex;align-items:baseline;gap:8px;font-size:.82rem;line-height:1.75;color:#e6edf8}
.j13st-row > b{flex:0 0 74px;color:#8fb4de;font-weight:700;white-space:nowrap}
.j13st-row > span{min-width:0}
.j13st-hl{color:#ffd166;font-weight:900}
.j13st-word{color:#06d6a0;font-weight:900}
.j13st-up{color:#ff5b5b;font-weight:800}
.j13st-dn{color:#5aa9ff;font-weight:800}
.j13st-dim{color:#7f9cc0;font-size:.74rem}
.j13st-range{position:relative;height:34px;margin:6px 4px 0}
.j13st-line{position:absolute;left:0;right:0;top:6px;height:4px;border-radius:2px;
  background:linear-gradient(90deg,#ff6b6b,#ffd166,#06d6a0)}
.j13st-mk{position:absolute;top:0;width:3px;height:16px;background:#fff;border-radius:2px;transform:translateX(-50%)}
.j13st-lab{position:absolute;top:20px;font-size:.68rem;color:#8fb4de;white-space:nowrap}
.j13st-eps{width:100%;border-collapse:collapse;table-layout:fixed;font-size:.76rem;margin:6px 0 0!important;border:none!important}
.j13st-eps th,.j13st-eps td{border:none!important;text-align:right;padding:2px 4px;white-space:nowrap;color:#e6edf8;font-weight:700}
.j13st-eps th{color:#8fb4de;border-bottom:1px solid rgba(157,204,255,.18)!important}
.j13st-eps th:first-child,.j13st-eps td:first-child{text-align:left;color:#8fb4de;width:62px}
.j13st-eps tr.j13st-move td{border-top:1px solid rgba(157,204,255,.18)!important;font-weight:900}
.j13st-note{font-size:.72rem;color:#8b96a8;margin-top:6px;line-height:1.45}
</style>"""


# 칸 모양은 자비스12 재무 창(us_fundamentals.CARD_CSS)과 같은 값(2026-11-04 상하님 「미국테마와 비교해 봐라」 — 폰에서 두 칸씩
# 크게 쌓여 창이 길었다 · 자비스12 는 네 칸 · 그림 두 칸). 화면 폭에 따라 바뀌는 규칙(@media)은 두지 않는다(CLAUDE.md 12).
CSS = """<style>
.j13fn-box{margin:.35rem 0 .5rem}
.j13fn-box>summary{display:inline-block;cursor:pointer;list-style:none;padding:.35rem .9rem;border-radius:15px;
  border:1px solid #b9965c;background:#062448;color:#eaf5ff;font-weight:800;font-size:.9rem}
.j13fn-box>summary::-webkit-details-marker{display:none}
.j13fn-box[open]>summary{margin-bottom:.5rem}
.j13fn-name{font-weight:800;color:#ffc94f;margin:.2rem 0 .4rem}
.j13fn{display:grid;gap:10px;color:#e6e6e6}
.j13fn-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}
.j13fn-cell{border:1px solid #1d3a63;border-radius:10px;padding:7px 9px;background:rgba(255,255,255,.03);min-width:0}
.j13fn-cell b{display:block;font-size:.74rem;color:#8fb4de;font-weight:700}
.j13fn-cell i{display:block;font-style:normal;font-size:1.05rem;font-weight:900;margin-top:1px;white-space:nowrap;font-variant-numeric:tabular-nums}
.j13fn-cell small{display:block;font-size:.66rem;color:#6f93bd;margin-top:1px;line-height:1.3}
.j13fn-charts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
.j13fn-chart{border:1px solid #1d3a63;border-radius:10px;padding:8px 9px;min-width:0;overflow-x:auto}
.j13fn-ct{display:flex;justify-content:space-between;gap:6px;font-weight:800;font-size:.88rem;margin-bottom:4px}
.j13fn-ct span span{font-weight:500;font-size:.72rem;color:#9fb6c8;margin-left:6px}
.j13fn-ct i{display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:3px}
.j13fn-bars{width:100%;height:70px;display:block}
.j13fn-t{width:100%;border-collapse:collapse;font-size:.74rem;font-variant-numeric:tabular-nums}
.j13fn-t th,.j13fn-t td{text-align:right;padding:2px 3px;white-space:nowrap}
.j13fn-t th:first-child,.j13fn-t td:first-child{text-align:left;color:#9fb6c8}
.j13fn-foot{color:#8b96a8;font-size:.74rem;line-height:1.5}
/* 폰처럼 카드가 좁으면 자비스12 폰 배치(mobile_ui 의 j3fn — 두 칸 · 실적 그림 한 칸 가득)와 같게 (2026-11-04 상하님 캡처 — 표가 잘려
   옛 칸 23.12·24.12 만 보였다). 화면 폭 규칙이 아니라 이 카드 폭으로 본다 — PC·태블릿은 카드가 넓어 그대로다(CLAUDE.md 12). */
.j13fn{container-type:inline-size}
.j13fn-t{table-layout:fixed}
@container (max-width: 620px){
  .j13fn-grid{grid-template-columns:1fr 1fr}
  .j13fn-charts{grid-template-columns:1fr}
  .j13fn-t{font-size:.7rem}
  .j13fn-t th,.j13fn-t td{padding:2px 1px}
}
</style>"""


# ── 표 칸 「연간 실적」·「분기 실적」 (2026-11-04 상하님 「연간 실적 분기 실적 등 캡처 화면처럼 각 파트별로 다 해라」) ──────────
# 자비스12(us_fundamentals.results_cells · 2026-10-07)와 같은 칸 — 작은 막대(매출 파랑 · 영업이익 노랑, 적자는 빨강) +
# 「매출 ±○%」·「이익률 ○%」 두 줄. 연간 = 최근 결산 해 매출이 그 앞 해보다 몇 % · 분기 = 최근 분기 매출이 1년 전 같은 분기보다 몇 %.
# **이 파일(KR.json)만 읽는다** — 화면이 받으러 가지 않는다. 매출 늘고 줄음의 글자색만 한국장 색(늘면 빨강 · 줄면 파랑 · j4-up/j4-down)이다.
# 막대 색은 오르내림이 아니라 무엇인지(매출·영업이익)를 가르는 색이라 자비스12 그대로 둔다. 점수·판정에 안 쓴다.
RESULTS_CSS = """<style>
.j13rc{display:inline-flex;align-items:center;gap:5px;line-height:1.12;white-space:nowrap}
.j13rc svg{flex:0 0 auto;display:block}
.j13rc-t{display:flex;flex-direction:column;align-items:flex-start;gap:1px;font-size:.7rem}
.j13rc-t b{font-weight:800}
.j13rc-t i{font-style:normal;font-weight:600;color:#cfe0f5}
.j13rc-t small{color:#6f93bd;font-size:.66rem;margin-left:3px}
.j13rc-none{color:#6f93bd}
</style>"""


def _same_quarter_last_year(rows):
    """「26.06」의 1년 전 「25.06」 줄. 없으면 None — 다른 분기와 견주지 않는다."""
    try:
        year, month = str(rows[-1][0]).split(".")
        target = f"{int(year) - 1:02d}.{month}"
    except (ValueError, IndexError):
        return None
    return next((row for row in rows[:-1] if row[0] == target), None)


def _mini_bars(rows) -> str:
    values = [v for row in rows for v in (row[1], row[2]) if v is not None]
    if not values:
        return ""
    high, low = max(values + [0.0]), min(values + [0.0])
    reach = (high - low) or 1.0

    def y(value):
        return 1.0 + (high - value) / reach * 20.0

    width = len(rows) * 9
    body = [f"<line x1='0' x2='{width}' y1='{y(0.0):.1f}' y2='{y(0.0):.1f}' stroke='rgba(255,255,255,.3)' stroke-width='.6'/>"]
    for place, (_label, revenue, operating, _net) in enumerate(rows):
        for offset, value, color in ((0.5, revenue, "#4da6ff"),
                                     (4.5, operating, "#ffb020" if (operating or 0) >= 0 else "#ff5b5b")):
            if value is None:
                continue
            top, bottom = sorted((y(value), y(0.0)))
            body.append(f"<rect x='{place * 9 + offset}' y='{top:.1f}' width='3.5' "
                        f"height='{max(bottom - top, 1.0):.1f}' fill='{color}' rx='1'/>")
    return f"<svg width='{width}' height='22' viewBox='0 0 {width} 22'>" + "".join(body) + "</svg>"


def _result_cell(rows, previous, stale=None) -> str:
    import html as _html

    if not rows:
        return "<span class='j13rc-none'>—</span>"
    _label, revenue, operating, _net = rows[-1]
    growth = (None if not previous or not previous[1] or revenue is None
              else (revenue / previous[1] - 1.0) * 100.0)
    tone = "#9aa0aa" if growth is None else ("#ff5b5b" if growth >= 0 else "#4da6ff")
    growth_text = "매출 —" if growth is None else f"매출 {growth:+.1f}%"
    if operating is None or not revenue:
        margin = "<i>이익률 —</i>"
    elif operating < 0:
        margin = "<i style='color:#ff5b5b'>영업적자</i>"
    else:
        margin = f"<i>이익률 {operating / revenue * 100:.0f}%</i>"
    stale_html = f"<small>({_html.escape(str(stale))})</small>" if stale else ""
    return (f"<span class='j13rc'>{_mini_bars(rows)}<span class='j13rc-t'>"
            f"<b style='color:{tone}'>{growth_text}</b><span>{margin}{stale_html}</span></span></span>")


def results_cells(codes, *, path: Path = DATA_PATH) -> dict:
    """{종목코드: (연간 칸 HTML, 분기 칸 HTML)} — 표 한 벌에 한 번 부른다. 모아 둔 재무가 없는 종목은 「—」 두 칸.
    그 표의 다른 종목들보다 **두 달 넘게 오래된** 분기만 「(26.03)」처럼 달을 붙인다(자비스12 와 같다)."""
    from collections import Counter

    data = load(path)
    entries = {str(c or "").strip(): data.get(str(c or "").strip()) for c in codes or []}

    def clean(rows):
        return [row for row in rows or [] if isinstance(row, list) and len(row) == 4]

    def months(label):
        try:
            year, month = str(label).split(".")
            return int(year) * 12 + int(month)
        except ValueError:
            return None

    latest = [clean(entry.get("quarter"))[-1][0] for entry in entries.values()
              if isinstance(entry, dict) and clean(entry.get("quarter"))]
    common = Counter(latest).most_common(1)[0][0] if latest else None
    dash = "<span class='j13rc-none'>—</span>"
    out = {}
    for code, entry in entries.items():
        if not isinstance(entry, dict):
            out[code] = (dash, dash)
            continue
        annual, quarter = clean(entry.get("annual")), clean(entry.get("quarter"))
        own, usual = (months(quarter[-1][0]) if quarter else None), months(common)
        stale = quarter[-1][0] if (own is not None and usual is not None and usual - own >= 2) else None
        out[code] = (_result_cell(annual, annual[-2] if len(annual) > 1 else None),
                     _result_cell(quarter, _same_quarter_last_year(quarter) if quarter else None, stale))
    return out
