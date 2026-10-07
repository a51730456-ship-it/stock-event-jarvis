"""미국 종목 재무 한눈에 — 모아 두기와 읽기 (2026-10-07 상하님 지시).

상하님 — *"선택종목 세부사항에서 재무사항이나 기타 메이저 회사들이 만든 주식 관련
프로그램처럼 로딩 안 걸리게 뭘 넣을 수 있는 방법"* · *"재무구조는 중요한 것만
메이저 증권사들처럼 간단하게 도표 같은 걸로"*.

**화면은 재무를 받으러 가지 않는다.** 야후에서 재무를 받으면 종목당 1.1~1.5초가
든다(2026-10-07 노트북 실측 — NVDA 1.5 · TSM 1.1 · ASML 1.1 · SKHY 1.2초). 종목을
누를 때마다 그만큼 늦어지면 안 되므로, 깃허브 컴퓨터가 미국 목록을 저장할 때
(`.github/workflows/picklist_collect.yml`) 이 파일로 미리 모아 `data/fundamentals/US.json`
하나에 적어 둔다. 화면은 그 파일만 읽는다(`load` · 앱 안에서 한 번만 읽는다).

**달러로 바꿔 적는다.** TSMC(대만 달러)·ASML(유로)·SK하이닉스(원)처럼 장부를 다른
돈으로 쓰는 회사가 있다. 모을 때 그날 환율로 달러로 바꿔 적고, 어느 돈이었는지와
환율을 같이 남긴다. 야후의 「자산 대비 주가(PBR)」는 이런 회사에서 달러 주가를 현지
돈 장부로 나눠 99배·1,593배처럼 엉터리로 나온다(2026-10-07 실측 — TSM · ASML).
그래서 PBR 은 쓰지 않고 **시가총액 ÷ 자기 돈(달러로 바꾼 것)** 으로 직접 센다.

**주가가 들어가는 값은 화면에서 지금 주가로 다시 센다.** 시가총액·PER·PBR 은 주가에
따라 날마다 바뀐다. 모은 날 주가(px)를 같이 적어 두고, 화면은 지금 주가 ÷ 모은 날
주가만큼 늘이거나 줄인다. 이익·자기 돈은 실적 발표 때만 바뀌므로 이 셈이 맞다.

못 받은 값은 **빈칸(None)으로 둔다. 0으로 채우지 않는다.**

쓰는 법
    python us_fundamentals.py                     # 209종목 전부
    python us_fundamentals.py --max 60 --older-than-days 5   # 오래된 것부터 60개만
    python us_fundamentals.py --tickers NVDA TSM
"""

from __future__ import annotations

import argparse
import html
import json
import math
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# 읽는 값이나 돌려주는 값을 바꾸면 올린다 — 페이지가 옛 모듈을 다시 읽게.
MODULE_REVISION = 2026100702

_SEOUL = ZoneInfo("Asia/Seoul")
ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "fundamentals" / "US.json"
SCHEMA_VERSION = 1
# 화면에 그리는 칸 수 — 연간 4년 · 분기 5개(1년 전 같은 분기와 견줄 수 있게).
ANNUAL_KEEP = 4
QUARTER_KEEP = 5
# 돈 값은 백만 달러 단위로 적는다 — 파일이 작아지고, 화면은 억 달러로 적는다.
_MILLION = 1_000_000.0

# 다른 돈으로 장부를 쓰는 회사의 이름(화면 맨 밑 한 줄에 적는다).
CURRENCY_NAMES = {
    "USD": "달러", "TWD": "대만 달러", "EUR": "유로", "KRW": "원", "JPY": "엔",
    "CNY": "위안", "HKD": "홍콩 달러", "GBP": "파운드", "CAD": "캐나다 달러",
    "CHF": "스위스 프랑", "DKK": "덴마크 크로네", "SEK": "스웨덴 크로나",
    "ILS": "셰켈", "INR": "루피", "BRL": "헤알", "AUD": "호주 달러",
    "SGD": "싱가포르 달러", "MXN": "페소", "NOK": "노르웨이 크로네",
}

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _log(message: str) -> None:
    print(f"[{datetime.now(_SEOUL):%H:%M:%S}] {message}", flush=True)


def _num(value):
    """숫자면 float, 아니면(빈칸·NaN·글자) None."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


# ── 모으기 (깃허브 컴퓨터 · 노트북에서만 돈다. 화면은 안 부른다) ─────────────────────

def _row(frame, names):
    """재무표에서 이름이 맞는 첫 줄을 {날짜: 값} 으로. 없으면 빈 것."""
    if frame is None or getattr(frame, "empty", True):
        return {}
    for name in names:
        if name in frame.index:
            series = frame.loc[name]
            return {stamp: _num(value) for stamp, value in series.items()}
    return {}


def _periods(frame, fx: float, keep: int, label_format: str) -> list:
    """[라벨, 매출, 영업이익, 순이익] 줄들 — **옛날 → 최근** 순서, 백만 달러."""
    revenue = _row(frame, ("Total Revenue", "Operating Revenue"))
    operating = _row(frame, ("Operating Income", "Total Operating Income As Reported"))
    net = _row(frame, ("Net Income", "Net Income Common Stockholders"))
    stamps = sorted(set(revenue) | set(operating) | set(net), reverse=True)
    rows = []
    for stamp in stamps:
        values = [revenue.get(stamp), operating.get(stamp), net.get(stamp)]
        if values[0] is None and values[1] is None:
            continue                    # 매출도 영업이익도 없는 칸(야후가 빈 해를 붙인다)
        try:
            label = stamp.strftime(label_format)
        except Exception:
            label = str(stamp)[:7].replace("-", ".")
        rows.append([label] + [None if v is None else round(v * fx / _MILLION, 1) for v in values])
        if len(rows) >= keep:
            break
    return list(reversed(rows))


def _fx_to_usd(currency: str, cache: dict):
    """1 (그 돈) = ? 달러. 달러면 1. 못 받으면 None."""
    currency = (currency or "USD").upper()
    if currency == "USD":
        return 1.0
    if currency in cache:
        return cache[currency]
    rate = None
    try:
        import yfinance as yf

        frame = yf.download(f"{currency}USD=X", period="5d", interval="1d",
                            progress=False, auto_adjust=False, threads=False)
        closes = frame["Close"].dropna()
        if hasattr(closes, "columns"):
            closes = closes.iloc[:, 0]
        if len(closes):
            rate = _num(closes.iloc[-1])
    except Exception as exc:
        _log(f"환율 실패 {currency}: {exc}")
    cache[currency] = rate
    return rate


def fetch_one(ticker: str, fx_cache: dict) -> dict | None:
    """한 종목. 못 받으면 None (파일의 옛 값을 그대로 둔다)."""
    import yfinance as yf

    handle = yf.Ticker(ticker)
    info = handle.info or {}
    if not info or info.get("quoteType") not in (None, "EQUITY"):
        return None
    currency = str(info.get("financialCurrency") or "USD").upper()
    fx = _fx_to_usd(currency, fx_cache)
    if fx is None:
        return None
    annual = _periods(handle.income_stmt, fx, ANNUAL_KEEP, "%Y.%m")
    quarter = _periods(handle.quarterly_income_stmt, fx, QUARTER_KEEP, "%y.%m")
    balance = handle.quarterly_balance_sheet
    if balance is None or getattr(balance, "empty", True):
        balance = handle.balance_sheet

    def latest(names):
        values = _row(balance, names)
        for stamp in sorted(values, reverse=True):
            if values[stamp] is not None:
                return values[stamp], stamp
        return None, None

    equity, eq_at = latest(("Stockholders Equity", "Common Stock Equity",
                            "Total Equity Gross Minority Interest"))
    liabilities, _ = latest(("Total Liabilities Net Minority Interest",))
    current_assets, _ = latest(("Current Assets",))
    current_liabilities, _ = latest(("Current Liabilities",))
    price = _num(info.get("currentPrice")) or _num(info.get("regularMarketPrice"))
    eps = _num(info.get("trailingEps"))
    return {
        "at": datetime.now(_SEOUL).strftime("%Y-%m-%d"),
        "name": str(info.get("shortName") or info.get("longName") or ticker),
        "cur": currency,
        "fx": round(fx, 8),
        "px": price,
        "mcap": None if _num(info.get("marketCap")) is None
        else round(_num(info.get("marketCap")) / _MILLION, 1),
        "pe": _num(info.get("trailingPE")),
        "eps": eps,
        "roe": _num(info.get("returnOnEquity")),
        "opm": _num(info.get("operatingMargins")),
        "div": _num(info.get("dividendYield")),
        "eq": None if equity is None else round(equity * fx / _MILLION, 1),
        "eq_at": None if eq_at is None else eq_at.strftime("%Y.%m"),
        "debt_ratio": None if not equity or liabilities is None or equity <= 0
        else round(liabilities / equity * 100.0, 1),
        "cur_ratio": None if not current_liabilities or current_assets is None
        else round(current_assets / current_liabilities, 2),
        "annual": annual,
        "quarter": quarter,
    }


def _read_file(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict) and isinstance(data.get("stocks"), dict):
            return data
    except Exception:
        pass
    return {"version": SCHEMA_VERSION, "stocks": {}}


def universe() -> list:
    """모을 종목 — 미국테마 명부(jarvis3_data.US_LARGE_CAP_UNIVERSE) 그대로."""
    import jarvis3_data

    return list(jarvis3_data.US_LARGE_CAP_UNIVERSE)


def collect(tickers, *, path: Path = DATA_PATH, older_than_days: float | None = None,
            limit: int | None = None, pause: float = 0.4) -> dict:
    """오래된 것부터 받아 파일에 덮어 적는다. **못 받은 종목은 옛 값을 그대로 둔다.**"""
    data = _read_file(path)
    stocks = data["stocks"]
    today = datetime.now(_SEOUL).date()

    def age(code):
        try:
            return (today - datetime.strptime(stocks[code]["at"], "%Y-%m-%d").date()).days
        except Exception:
            return 10_000

    wanted = [str(t).strip().upper() for t in tickers if str(t).strip()]
    wanted = list(dict.fromkeys(wanted))
    if older_than_days is not None:
        wanted = [code for code in wanted if age(code) >= older_than_days]
    wanted.sort(key=lambda code: -age(code))           # 가장 오래된 것부터
    if limit:
        wanted = wanted[:limit]
    fx_cache: dict = {}
    done = failed = 0
    if not wanted:
        _log("다시 받을 종목이 없습니다(모두 최근에 받음)")
        return {"done": 0, "failed": 0, "total": len(stocks), "wanted": 0}
    started = time.time()
    for code in wanted:
        entry = None
        for attempt in range(2):
            try:
                entry = fetch_one(code, fx_cache)
                break
            except Exception as exc:
                _log(f"{code} 실패({attempt + 1}): {exc}")
                time.sleep(3.0)
        if entry:
            stocks[code] = entry
            done += 1
        else:
            failed += 1
        time.sleep(pause)
    data["version"] = SCHEMA_VERSION
    data["updated"] = datetime.now(_SEOUL).strftime("%Y-%m-%d %H:%M")
    data["stocks"] = dict(sorted(stocks.items()))
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))
    os.replace(temp, path)
    _log(f"받음 {done} · 못 받음 {failed} · 파일 {len(stocks)}종목 · {time.time() - started:.0f}초")
    return {"done": done, "failed": failed, "total": len(stocks), "wanted": len(wanted)}


# ── 읽기 (화면이 부른다 · 받으러 가지 않는다) ─────────────────────────────────────

_LOADED = {"mtime": None, "data": None}


def load(path: Path = DATA_PATH) -> dict:
    """파일을 읽는다. 파일이 바뀌지 않았으면 앱 안에 들고 있는 것을 그대로 준다."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return {}
    if _LOADED["mtime"] == mtime and _LOADED["data"] is not None:
        return _LOADED["data"]
    data = _read_file(path).get("stocks") or {}
    _LOADED.update(mtime=mtime, data=data)
    return data


def summary(ticker: str, price_now=None, *, path: Path = DATA_PATH) -> dict | None:
    """화면에 적을 값. 그 종목이 파일에 없으면 None.

    price_now 를 주면 시가총액·PER·PBR 을 지금 주가로 다시 센다(위 머리말).
    """
    entry = load(path).get(str(ticker or "").strip().upper())
    if not isinstance(entry, dict):
        return None
    px = _num(entry.get("px"))
    now = _num(price_now)
    scale = now / px if (now and px) else 1.0
    mcap = _num(entry.get("mcap"))
    mcap_now = None if mcap is None else mcap * scale
    eps = _num(entry.get("eps"))
    pe = _num(entry.get("pe"))
    if eps is not None and eps <= 0:
        pe_now, loss = None, True                      # 적자 — PER 을 셀 수 없다
    else:
        pe_now, loss = (None if pe is None else pe * scale), False
    equity = _num(entry.get("eq"))
    pbr = None if (mcap_now is None or not equity or equity <= 0) else mcap_now / equity
    # 자기 돈(자본)이 마이너스 — 「자본잠식」. 이때는 PBR·ROE·부채비율을 셀 수 없다.
    equity_bad = equity is not None and equity <= 0
    return {
        "ticker": str(ticker).upper(),
        "name": entry.get("name") or str(ticker).upper(),
        "at": entry.get("at"),
        "currency": entry.get("cur") or "USD",
        "currency_name": CURRENCY_NAMES.get(str(entry.get("cur") or "USD"), entry.get("cur")),
        "fx": _num(entry.get("fx")),
        "rescaled": bool(now and px),
        "mcap": mcap_now,                                # 백만 달러
        "pe": pe_now,
        "loss": loss,
        "pbr": pbr,
        "equity_bad": equity_bad,
        "roe": _num(entry.get("roe")),
        "opm": _num(entry.get("opm")),
        "div": _num(entry.get("div")),
        "debt_ratio": _num(entry.get("debt_ratio")),
        "cur_ratio": _num(entry.get("cur_ratio")),
        "eq_at": entry.get("eq_at"),
        "annual": [row for row in entry.get("annual") or [] if isinstance(row, list) and len(row) == 4],
        "quarter": [row for row in entry.get("quarter") or [] if isinstance(row, list) and len(row) == 4],
    }


# ── 그리기 (화면의 「📑 재무 한눈에」 창 안) ─────────────────────────────────────────
# 상하님 — "중요한 것만 메이저 증권사들처럼 간단하게 도표 같은 걸로". 증권사 앱의 「투자 지표」
# 칸과 「실적」 막대 그림을 그대로 줄여 담는다. 지표 이름(PER 등)은 증권사 앱 그대로 쓰고,
# 그 밑에 **한 줄로 뜻**을 적는다(화면 용어는 쉬운 말로 — 상하님 규칙).

def _eok(million) -> str:
    """백만 달러 → 「억 달러」 숫자(단위는 칸 밖에 한 번만 적는다)."""
    if million is None:
        return "—"
    eok = million / 100.0
    return f"{eok:,.0f}" if abs(eok) >= 100 else f"{eok:,.1f}"


def _cap(million) -> str:
    if million is None:
        return "—"
    if million >= 1_000_000:
        return f"{million / 1_000_000:.2f}조 달러"
    eok = million / 100.0
    return f"{eok:,.0f}억 달러" if eok >= 10 else f"{eok:,.1f}억 달러"


def _times(value) -> str:
    if value is None:
        return "—"
    return f"{value:,.0f}배" if value >= 1000 else f"{value:.1f}배"


def _ratio_pct(value) -> str:
    return "—" if value is None else f"{value * 100:.0f}%"


def _bars_svg(rows) -> str:
    """매출(파랑)·영업이익(노랑, 적자면 빨강) 막대. 가로로 늘려 그린다 — 칸은 아래 표와 맞춘다."""
    values = [v for row in rows for v in (row[1], row[2]) if v is not None]
    if not values:
        return ""
    high = max(values + [0.0])
    low = min(values + [0.0])
    reach = (high - low) or 1.0

    def y(value):
        return 2.0 + (high - value) / reach * 96.0

    body = [f"<line x1='0' x2='{len(rows) * 100}' y1='{y(0.0):.1f}' y2='{y(0.0):.1f}' "
            "stroke='rgba(255,255,255,.3)' stroke-width='1' vector-effect='non-scaling-stroke'/>"]
    for place, (_label, revenue, operating, _net) in enumerate(rows):
        for offset, value, color in ((20, revenue, "#4da6ff"),
                                     (52, operating, "#ffb020" if (operating or 0) >= 0 else "#ff5b5b")):
            if value is None:
                continue
            top, bottom = sorted((y(value), y(0.0)))
            body.append(f"<rect x='{place * 100 + offset}' y='{top:.1f}' width='28' "
                        f"height='{max(bottom - top, 1.0):.1f}' fill='{color}' rx='2'/>")
    return (f"<svg class='j3fn-bars' viewBox='0 0 {len(rows) * 100} 100' preserveAspectRatio='none'>"
            + "".join(body) + "</svg>")


def _results_html(title: str, rows) -> str:
    if not rows:
        return (f"<div class='j3fn-chart'><div class='j3fn-ct'>{title}</div>"
                "<div class='j3fn-foot'>자료가 없습니다.</div></div>")
    head = "".join(f"<th>{label}</th>" for label, *_rest in rows)
    revenue = "".join(f"<td>{_eok(row[1])}</td>" for row in rows)
    operating = "".join(
        f"<td style='color:{'#ffb020' if (row[2] or 0) >= 0 else '#ff5b5b'}'>{_eok(row[2])}</td>" for row in rows)
    margins = "".join(
        "<td>—</td>" if not row[1] or row[2] is None
        else f"<td style='color:{'#e6e6e6' if row[2] >= 0 else '#ff5b5b'}'>{row[2] / row[1] * 100:.0f}%</td>"
        for row in rows)
    return (
        f"<div class='j3fn-chart'><div class='j3fn-ct'>{title}<span><span><i style='background:#4da6ff'></i>매출</span>"
        "<span><i style='background:#ffb020'></i>영업이익</span></span></div>"
        + _bars_svg(rows)
        + f"<table class='j3fn-t'><tr><th></th>{head}</tr><tr><td>매출</td>{revenue}</tr>"
        f"<tr><td>영업이익</td>{operating}</tr><tr><td>이익률</td>{margins}</tr></table></div>")


def card_html(info: dict) -> str:
    """창 안에 넣을 한 판 — 지표 여덟 칸 · 연간/분기 실적 · 맨 밑 한 줄."""
    import html as _html

    equity_bad = bool(info.get("equity_bad"))

    def cell(name, value, note, color="#ffffff"):
        return (f"<div class='j3fn-cell'><b>{name}</b><i style='color:{color}'>{value}</i>"
                f"<small>{note}</small></div>")

    pe_value = "적자" if info.get("loss") else _times(info.get("pe"))
    pe_note = "1년 이익이 마이너스" if info.get("loss") else "주가 ÷ 1년 이익"
    roe, opm = info.get("roe"), info.get("opm")
    div = info.get("div")
    debt, current = info.get("debt_ratio"), info.get("cur_ratio")
    cells = [
        cell("시가총액", _cap(info.get("mcap")), "회사 전체 값"),
        cell("PER", pe_value, pe_note, "#ff8a8a" if info.get("loss") else "#ffffff"),
        cell("PBR", "자본잠식" if equity_bad else _times(info.get("pbr")),
             "자기 돈이 마이너스" if equity_bad else "주가 ÷ 자기 돈(장부)",
             "#ff8a8a" if equity_bad else "#ffffff"),
        cell("ROE", "—" if equity_bad else _ratio_pct(roe), "자기 돈으로 1년에 번 이익",
             "#ff8a8a" if (roe is not None and roe < 0) else "#ffffff"),
        cell("영업이익률", _ratio_pct(opm), "매출 100에 남긴 영업이익",
             "#ff8a8a" if (opm is not None and opm < 0) else "#ffffff"),
        cell("배당", "없음" if div == 0 else ("—" if div is None else f"{div:.2f}%"), "1년 배당 ÷ 주가"),
        cell("부채비율", "자본잠식" if equity_bad else ("—" if debt is None else f"{debt:.0f}%"),
             "자기 돈이 마이너스" if equity_bad else
             ("—" if debt is None else f"자기 돈 100에 빚 {debt:.0f}"),
             "#ff8a8a" if equity_bad or (debt is not None and debt >= 200) else "#ffffff"),
        cell("유동비율", "—" if current is None else f"{current:.1f}배", "곧 갚을 빚의 몇 배를 곧 쓸 돈으로 가졌나",
             "#ff8a8a" if (current is not None and current < 1) else "#ffffff"),
    ]
    foot = [f"{_html.escape(str(info.get('at') or ''))} 모은 재무(야후 파이낸스)"]
    if info.get("rescaled"):
        foot.append("시가총액·PER·PBR 은 지금 주가로 다시 셈")
    currency = str(info.get("currency") or "USD")
    fx = info.get("fx")
    if currency != "USD" and fx:
        name = _html.escape(str(info.get("currency_name") or currency))
        rate = f"1,000{name} = {fx * 1000:.2f}달러" if fx < 0.01 else f"1{name} = {fx:.3f}달러"
        foot.append(f"장부는 {name} — 그날 환율({rate})로 달러로 바꿔 적음")
    return (
        "<div class='j3fn'><div class='j3fn-grid'>" + "".join(cells) + "</div>"
        "<div class='j3fn-charts'>"
        + _results_html("연간 실적", info.get("annual") or [])
        + _results_html("분기 실적", info.get("quarter") or [])
        + "</div><div class='j3fn-foot'>단위 억 달러 · 칸 위 날짜는 결산한 달 · "
        + " · ".join(foot) + "</div></div>")


CARD_CSS = """<style>
label.j3fn-open{display:flex;align-items:center;justify-content:center;width:100%;box-sizing:border-box;
  min-height:2.5rem;padding:.35rem .75rem;border-radius:.5rem;border:1px solid rgba(255,255,255,.22);
  cursor:pointer;color:#fff;font-weight:700;
  background:linear-gradient(90deg,rgba(32,201,151,.30) 0%,rgba(77,166,255,.34) 55%,rgba(124,58,237,.34) 100%)}
.j3cz-pop.j3fn-pop{height:auto;max-height:calc(100dvh - 16px);overflow-y:auto}
.j3fn-tap:checked ~ .j3fn-scrim{opacity:1;visibility:visible;transition:opacity .3s ease,visibility 0s}
.j3fn-tap:checked ~ .j3fn-pop{opacity:1;visibility:visible;pointer-events:auto;
  transform:translate(-50%,-50%) scale(1);
  transition:transform .9s cubic-bezier(.34,1.56,.64,1),opacity .36s ease,visibility 0s}
.j3fn{display:flex;flex-direction:column;gap:8px}
/* 닫혀 있는 동안은 창 속을 그리지 않는다(2026-10-07 실측 — 숨은 창을 늘 그려 두니 느린 폰 4배에서 테마를
   누를 때 세부사항이 0.08~0.09초 늦게 떴다). 열면 곧바로 그리고, 닫을 때는 줄어드는 움직임(.56초)이
   끝난 뒤에 거둔다. 이 규칙을 모르는 옛 브라우저는 예전처럼 늘 그린다 — 보이는 것은 같다. */
.j3fn-pop .j3fn{content-visibility:hidden;transition:content-visibility 0s linear .56s allow-discrete}
.j3fn-tap:checked ~ .j3fn-pop .j3fn{content-visibility:visible;transition-delay:0s}
.j3fn-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}
.j3fn-cell{border:1px solid #1d3a63;border-radius:10px;padding:7px 9px;background:rgba(255,255,255,.03);min-width:0}
.j3fn-cell b{display:block;font-size:.74rem;color:#8fb4de;font-weight:700}
.j3fn-cell i{display:block;font-style:normal;font-size:1.05rem;font-weight:900;margin-top:1px;white-space:nowrap}
.j3fn-cell small{display:block;font-size:.66rem;color:#6f93bd;margin-top:1px;line-height:1.3}
.j3fn-charts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
.j3fn-chart{border:1px solid #1d3a63;border-radius:10px;padding:8px 9px;min-width:0}
.j3fn-ct{display:flex;align-items:center;gap:8px;font-size:.84rem;font-weight:800;color:#fff;margin-bottom:4px}
.j3fn-ct > span{margin-left:auto;display:flex;gap:8px;font-size:.68rem;font-weight:700;color:#8fb4de}
.j3fn-ct i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:3px;vertical-align:-1px}
.j3fn-bars{display:block;width:calc(100% - 52px);margin-left:52px;height:84px}
.j3fn-t{width:100%;border-collapse:collapse;table-layout:fixed;font-size:.72rem;margin:4px 0 0!important;border:none!important}
.j3fn-t th,.j3fn-t td{border:none!important;border-bottom:1px solid rgba(157,204,255,.08)!important}
.j3fn-t th{color:#6f93bd;font-weight:700;text-align:center;padding:2px 0;white-space:nowrap;overflow:hidden}
.j3fn-t td{color:#e6e6e6;text-align:center;padding:2px 0;font-weight:700;white-space:nowrap}
.j3fn-t th:first-child,.j3fn-t td:first-child{width:52px;text-align:left;color:#8fb4de}
.j3fn-foot{font-size:.7rem;color:#6f93bd;line-height:1.5}
</style>"""


# ── 표 칸 「연간 실적」·「분기 실적」 (2026-10-07 상하님 지시) ─────────────────────────
# 상하님 — "테마 종목 1~6위의 칸에 연간 실적(이익률 포함)과 분기 실적(이익률 포함)을 넣을 수 있나" ·
# "상승장 리스트에도 · 급락 후 반등장 리스트에도" · "위아래 커져도 보기 싫지만 않으면".
# 칸 하나 = 작은 막대(매출 파랑 · 영업이익 노랑, 적자는 빨강) + 「매출 ±○%」·「이익률 ○%」 두 줄.
# 표 줄 높이(40px) 안에 들어가게 막대와 글자를 **옆으로** 나란히 둔다 — 결산한 달은 적지 않고,
# 그 표에서 혼자 오래된 분기(야후에 최신 분기가 아직 없는 종목)만 「(26.03)」처럼 붙인다.

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


def _result_cell(rows, previous, stale: str | None = None) -> str:
    if not rows:
        return "<span class='j3-muted'>—</span>"
    _label, revenue, operating, _net = rows[-1]
    growth = (None if not previous or not previous[1] or revenue is None
              else (revenue / previous[1] - 1.0) * 100.0)
    tone = "#9aa0aa" if growth is None else ("#4da6ff" if growth >= 0 else "#ff5b5b")
    growth_text = "매출 —" if growth is None else f"매출 {growth:+.1f}%"
    if operating is None or not revenue:
        margin = "<i>이익률 —</i>"
    elif operating < 0:
        margin = "<i style='color:#ff5b5b'>영업적자</i>"
    else:
        margin = f"<i>이익률 {operating / revenue * 100:.0f}%</i>"
    stale_html = f"<small>({html.escape(str(stale))})</small>" if stale else ""
    return (f"<span class='j3rc'>{_mini_bars(rows)}<span class='j3rc-t'>"
            f"<b style='color:{tone}'>{growth_text}</b><span>{margin}{stale_html}</span></span></span>")


def results_cells(tickers) -> dict:
    """{티커: (연간 칸 HTML, 분기 칸 HTML)} — 표 한 벌에 한 번 부른다(재무 파일만 읽는다).

    연간 = 최근 결산 해 매출이 그 앞 해보다 몇 % · 그 해 이익률.
    분기 = 최근 분기 매출이 1년 전 같은 분기보다 몇 % · 그 분기 이익률.
    """
    from collections import Counter

    data = load()
    entries = {str(t or "").strip().upper(): data.get(str(t or "").strip().upper()) for t in tickers or []}

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
    dash = "<span class='j3-muted'>—</span>"
    out = {}
    for code, entry in entries.items():
        if not isinstance(entry, dict):
            out[code] = (dash, dash)
            continue
        annual, quarter = clean(entry.get("annual")), clean(entry.get("quarter"))
        # 그 표의 다른 종목들보다 **두 달 넘게 오래된** 분기만 달을 붙인다 — 결산하는 달이 한 달 다른 회사
        # (26.05 · 26.07)는 오래된 것이 아니다(2026-10-07 화면 확인 — 26.07 에 붙었었다).
        own, usual = (months(quarter[-1][0]) if quarter else None), months(common)
        stale = quarter[-1][0] if (own is not None and usual is not None and usual - own >= 2) else None
        out[code] = (_result_cell(annual, annual[-2] if len(annual) > 1 else None),
                     _result_cell(quarter, _same_quarter_last_year(quarter) if quarter else None, stale))
    return out


RESULTS_CSS = """<style>
.j3rc{display:inline-flex;align-items:center;gap:5px;line-height:1.12;white-space:nowrap}
.j3rc svg{flex:0 0 auto;display:block}
.j3rc-t{display:flex;flex-direction:column;align-items:flex-start;gap:1px;font-size:.7rem}
.j3rc-t b{font-weight:800}
.j3rc-t i{font-style:normal;font-weight:600;color:#cfe0f5}
.j3rc-t small{color:#6f93bd;font-size:.66rem;margin-left:3px}
</style>"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="미국 종목 재무를 모아 data/fundamentals/US.json 에 적는다")
    parser.add_argument("--tickers", nargs="*", help="이 종목만 (없으면 미국테마 명부 전부)")
    parser.add_argument("--max", type=int, default=None, help="한 번에 받을 종목 수(오래된 것부터)")
    parser.add_argument("--older-than-days", type=float, default=None,
                        help="이 날수보다 오래된 것만 다시 받는다")
    args = parser.parse_args(argv)
    tickers = args.tickers or universe()
    result = collect(tickers, older_than_days=args.older_than_days, limit=args.max)
    # 하나도 못 받았으면 실패로 알린다(깃허브 작업이 빨갛게 뜬다). 옛 파일은 그대로다.
    return 0 if result["done"] or not result.get("wanted") else 1


if __name__ == "__main__":
    raise SystemExit(main())
