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
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# 읽는 값이나 돌려주는 값을 바꾸면 올린다 — 페이지가 옛 모듈을 다시 읽게.
MODULE_REVISION = 2026100913

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
        # 종목 개요의 본사·직원 수·최고경영자(2026-10-09) — 바뀔 수 있어 재무와 같이 모은다.
        "co": company_facts(info),
        # 실적 발표 · 애널리스트 · 공매도·내부자 · 배당(2026-10-09) — 0.1초짜리 넷을 더 받는다.
        **street_facts(handle, info),
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


# ── 종목 개요 (2026-10-09 상하님 지시) ──────────────────────────────────────────────
# 상하님 — "선택종목 세부사항에 종목 개요 — 테마가 뭔지, 이 회사가 뭐 하는 회사인지 등등 · 메이저 증권사에 있는 것" ·
# 가안 두 장을 보시고 "가안 1로 하고 너가 쓴 두 줄로 해라".
#   · 가안 1 = 이름 밑 초록 줄 바로 밑에 **늘 보이는 짧은 소개 카드**(누를 것 없음).
#   · 소개 두 줄은 **Claude 가 네이버 증권·야후의 회사 소개를 읽고 쉬운 말로 다시 쓴 것**이다
#     (data/fundamentals/US_about.json). 남의 회사 소개 글을 그대로 옮기면 공개 저장소에 그 글 209개를 올리게
#     되어 쓰지 않는다 — 원문은 카드 맨 밑 링크로 네이버 증권 「기업개요」 화면을 연다.
#   · 회사 이름(한글)·업종·거래소·상장 연월도 그 파일에 적어 둔다(잘 안 바뀐다). 상장 연월은 **야후와 네이버
#     날짜가 한 달 안으로 맞는 회사만** 적는다 — 오래된 회사는 두 곳 다 자료 시작일(1962-01-02 · 1980-03-17 등)을
#     상장일처럼 적어 두어 IBM 이 1980년 상장으로 나왔다(2026-10-09 실측 — 16개 회사가 같은 1980-03-17).
#   · 본사·직원 수·최고경영자는 바뀔 수 있어 재무와 같이 깃허브가 모은다(US.json 의 co · company_facts).
#   · 명부에 종목이 늘면 US_about.json 에도 한 줄을 써 넣는다(test_us_fundamentals 가 빠진 종목을 잡는다).
# 화면은 받으러 가지 않는다 — 두 파일만 읽는다.

ABOUT_PATH = ROOT / "data" / "fundamentals" / "US_about.json"
NAVER_OVERVIEW_URL = "https://m.stock.naver.com/worldstock/stock/{code}/overview"

_CEO_TITLE = re.compile(r"\bCEO\b|Chief Executive", re.I)
# 군 계급(Brig.Gen. 등)은 점이 붙은 것만 뗀다 — 「Gen」이 이름일 수도 있다.
_NAME_HEAD = re.compile(r"^(?:(?:Mr|Ms|Mrs|Dr|Prof|Sir)\b\.?\s*|(?:Brig|Gen|Adm|Col|Lt)\.\s*)+", re.I)
_NAME_TAIL = re.compile(r",?\s+(M\.?\s?B\.?\s?A|Ph\.?\s?D|M\.?\s?D|C\.?P\.?A|J\.?\s?D|C\.?F\.?A|Sc\.?\s?D|"
                        r"B\.?\s?Sc|M\.?\s?Sc|Esq|M\.?\s?S|B\.?\s?S|LL\.?\s?B|LL\.?\s?M|DBA|P\.?\s?E|D\.?\s?V\.?\s?M|CBE|OBE)\.?$", re.I)


def _person(name) -> str | None:
    """「Mr. Stéphane  Bancel M.B.A.」 → 「Stéphane Bancel」. 호칭·학위만 떼고 이름은 그대로."""
    text = " ".join(str(name or "").split())
    text = _NAME_HEAD.sub("", text)
    # 쉼표 뒤는 학위·자격이다(「Leigh Robert Curyer ACA, BA (Acc)」) — Jr. · II 같은 것만 남긴다.
    head, comma, tail = text.partition(",")
    if comma and not re.match(r"\s*(Jr|Sr|II|III|IV)\b", tail):
        text = head
    for _ in range(4):
        cleaned = _NAME_TAIL.sub("", text).strip(" ,")
        # 끝의 대문자 자격 줄임말(FASN · CEBS · ACA)과 「BSc(Hon)」 — II · III 은 이름이라 둔다.
        cleaned = re.sub(r"\s+(?!(?:II|III|IV)$)[A-Z]{3,6}$|\s+\S*\([^)]*\)$", "", cleaned).strip(" ,")
        if cleaned == text:
            break
        text = cleaned
    return text or None


def company_facts(info: dict) -> dict:
    """회사 사실(야후 · 모을 때만) — 본사(주·나라) · 직원 수 · 최고경영자. 못 받은 칸은 빈칸."""
    ceo = next((_person(officer.get("name")) for officer in info.get("companyOfficers") or []
                if isinstance(officer, dict) and _CEO_TITLE.search(str(officer.get("title") or ""))), None)
    employees = _num(info.get("fullTimeEmployees"))
    return {
        "state": info.get("state") or None,
        "country": info.get("country") or None,
        "emp": None if employees is None or employees <= 0 else int(employees),
        "ceo": ceo,
    }


_ABOUT_LOADED = {"mtime": None, "data": None}


def load_about(path: Path | None = None) -> dict:
    """US_about.json — 파일이 바뀌지 않았으면 앱 안에 들고 있는 것을 그대로 준다."""
    path = path or ABOUT_PATH
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return {}
    if _ABOUT_LOADED["mtime"] == mtime and _ABOUT_LOADED["data"] is not None:
        return _ABOUT_LOADED["data"]
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle).get("stocks") or {}
    except Exception:
        data = {}
    _ABOUT_LOADED.update(mtime=mtime, data=data)
    return data


US_STATES = {
    "AL": "앨라배마", "AK": "알래스카", "AZ": "애리조나", "AR": "아칸소", "CA": "캘리포니아", "CO": "콜로라도",
    "CT": "코네티컷", "DE": "델라웨어", "FL": "플로리다", "GA": "조지아", "HI": "하와이", "ID": "아이다호",
    "IL": "일리노이", "IN": "인디애나", "IA": "아이오와", "KS": "캔자스", "KY": "켄터키", "LA": "루이지애나",
    "ME": "메인", "MD": "메릴랜드", "MA": "매사추세츠", "MI": "미시간", "MN": "미네소타", "MS": "미시시피",
    "MO": "미주리", "MT": "몬태나", "NE": "네브래스카", "NV": "네바다", "NH": "뉴햄프셔", "NJ": "뉴저지",
    "NM": "뉴멕시코", "NY": "뉴욕", "NC": "노스캐롤라이나", "ND": "노스다코타", "OH": "오하이오",
    "OK": "오클라호마", "OR": "오리건", "PA": "펜실베이니아", "RI": "로드아일랜드", "SC": "사우스캐롤라이나",
    "SD": "사우스다코타", "TN": "테네시", "TX": "텍사스", "UT": "유타", "VT": "버몬트", "VA": "버지니아",
    "WA": "워싱턴주", "WV": "웨스트버지니아", "WI": "위스콘신", "WY": "와이오밍", "DC": "워싱턴 D.C.",
}
COUNTRY_NAMES = {
    "United States": "미국", "Taiwan": "대만", "Netherlands": "네덜란드", "South Korea": "한국",
    "Ireland": "아일랜드", "United Kingdom": "영국", "Canada": "캐나다", "Switzerland": "스위스",
    "Israel": "이스라엘", "Chile": "칠레", "Australia": "호주", "Brazil": "브라질", "China": "중국",
    "Bermuda": "버뮤다", "Germany": "독일", "France": "프랑스", "Japan": "일본", "Denmark": "덴마크",
    "Uruguay": "우루과이", "Argentina": "아르헨티나", "Singapore": "싱가포르", "Luxembourg": "룩셈부르크",
    "Cayman Islands": "케이맨 제도", "Sweden": "스웨덴", "Spain": "스페인", "Italy": "이탈리아",
    "India": "인도", "Hong Kong": "홍콩", "Mexico": "멕시코", "Belgium": "벨기에", "Norway": "노르웨이",
    "Finland": "핀란드", "Jersey": "저지섬",
}


def _place(co: dict) -> str | None:
    country = co.get("country")
    if not country:
        return None
    name = COUNTRY_NAMES.get(country, country)
    if country == "United States" and co.get("state"):
        return f"{name} {US_STATES.get(str(co['state']).upper(), co['state'])}"
    return name


def overview_html(ticker: str, themes=()) -> str:
    """세부사항 이름 밑 「🏢 종목 개요」 카드 한 장. 두 파일에 그 종목이 없으면 빈 글(카드를 안 그린다).

    themes — 앱 명부에서 이 종목이 든 테마 이름들(페이지가 jarvis3_data.US_THEMES 로 넘긴다).
    """
    code = str(ticker or "").strip().upper()
    about = load_about().get(code) or {}
    co = (load().get(code) or {}).get("co") or {}
    if not about and not co:
        return ""
    esc = html.escape
    title = about.get("ko") or (load().get(code) or {}).get("name") or code
    head = [about.get("en"), about.get("exch")]
    listed = str(about.get("listed") or "")
    if len(listed) == 7 and listed[4] == ".":
        head.append(f"{listed[:4]}년 {int(listed[5:])}월 상장")
    chips = "".join(f"<span class='j3ov-chip j3ov-t'>앱 테마 · {esc(str(name))}</span>" for name in themes or ())
    if about.get("ind"):
        chips += f"<span class='j3ov-chip'>업종 · {esc(str(about['ind']))}</span>"
    facts = []
    place = _place(co)
    if place:
        facts.append(f"본사 {place}")
    if co.get("emp"):
        facts.append(f"직원 {int(co['emp']):,}명")
    if co.get("ceo"):
        facts.append(f"최고경영자 {co['ceo']}")
    link = ""
    if about.get("naver"):
        url = NAVER_OVERVIEW_URL.format(code=about["naver"])
        link = (f"<a class='j3ov-more' href='{esc(url)}' target='_blank' rel='noopener noreferrer'>"
                "▸ 네이버 증권에서 회사 소개 원문 보기</a>")
    return (
        "<div class='j3ov'>"
        f"<div class='j3ov-h'><b>🏢 {esc(str(title))}</b>"
        f"<span>{esc(' · '.join(str(bit) for bit in head if bit))}</span></div>"
        + (f"<div class='j3ov-p'>{esc(str(about['about']))}</div>" if about.get("about") else "")
        + (f"<div class='j3ov-chips'>{chips}</div>" if chips else "")
        + (f"<div class='j3ov-facts'>{esc(' · '.join(facts))}</div>" if facts else "")
        + link + "</div>"
    )


OVERVIEW_CSS = """<style>
.j3ov{margin:10px 0 4px;border:1px solid #2b4f80;border-radius:13px;padding:10px 12px 9px;
  background:rgba(77,127,208,.10)}
.j3ov-h{display:flex;align-items:baseline;gap:4px 8px;flex-wrap:wrap}
.j3ov-h b{font-size:1rem;font-weight:900;color:#fff}
.j3ov-h span{font-size:.78rem;color:#8fb4de}
.j3ov-p{margin:6px 0 8px;font-size:.88rem;line-height:1.6;color:#dfe9ff}
.j3ov-chips{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:7px}
.j3ov-chip{font-size:.78rem;font-weight:700;padding:1px 9px;border-radius:999px;border:1px solid #2b4f80;color:#cfe0ff}
.j3ov-chip.j3ov-t{border-color:#7c3aed;background:rgba(124,58,237,.18);color:#e9d5ff}
.j3ov-facts{font-size:.78rem;color:#9fb8d8;line-height:1.6}
a.j3ov-more{display:inline-block;margin-top:5px;font-size:.78rem;font-weight:700;color:#c084fc!important;
  text-decoration:none!important}
</style>"""


# ── 증권사 화면에 있는 것 — 실적 발표 · 애널리스트 · 공매도·내부자 · 배당 · 다가오는 일정 (2026-10-09) ──
# 상하님 — "메이저 증권회사에서 중요한 것 뭐 빠진 것 있나 · 화면으로 디자인해서 브리핑" → 시안을 보시고
# "1~5번 다 넣어라 · 로딩 오래 걸리는 것 있으면 고민해야 된다".
#   · **모을 때만 받는다**(street_facts — 깃허브가 재무와 같이). 화면은 이 파일만 읽어 종목을 누를 때
#     기다리는 것이 없다. 더 받는 것은 하나에 0.1초짜리 넷(실적 일정 · 지난 실적 · 애널리스트 의견 ·
#     내부자 매매)이다 — 2026-10-09 실측. 날짜마다 예상치를 주는 get_earnings_dates 는 1~2초라 안 쓴다.
#   · **다음 실적일은 calendar 로 받는다.** info 의 earningsTimestamp 는 지난 발표일이 남아 있는 종목이
#     많았다(같은 날 실측 — META 7/29 · AMZN 7/30 · CRWD 8/26 …).
#   · 애널리스트 의견·목표주가는 **남의 의견이라 점수·판정에 안 쓴다.** 보여 드리기만 한다.
#   · 못 받은 값은 빈칸. 0으로 채우지 않는다.

_NY = ZoneInfo("America/New_York")
MACRO_PATH = ROOT / "data" / "calendar" / "US_macro.json"
EARNINGS_BADGE_DAYS = 7          # 표 이름 옆 「실적 D-○」 딱지 — 오늘부터 7일 뒤까지(D-0~D-7)
UPCOMING_DAYS = 14               # 「다가오는 일정」 — 종목 실적은 2주 안
MACRO_DAYS = 31                  # 금리 결정·물가·고용은 한 달 안(드물고 시장 전체가 흔들린다)
_WEEKDAYS = "월화수목금토일"


def _iso(value) -> str | None:
    try:
        return value.isoformat()[:10]
    except Exception:
        return None


def street_facts(handle, info: dict) -> dict:
    """모을 때만 부른다 — {"earn", "ana", "own", "divd"} 중 받은 것만. 하나가 실패해도 나머지는 받는다."""
    out: dict = {}
    try:
        calendar = handle.calendar or {}
    except Exception:
        calendar = {}
    if not isinstance(calendar, dict):
        calendar = {}

    # 실적 발표 — 다음 날짜(·장 전/장 마감 뒤) · 이번 예상 주당 이익 · 지난 4번 예상 대비
    earn: dict = {}
    # 시각까지 든 값(info)이 **앞날**이면 그것을 뉴욕 날짜로 쓴다. calendar 의 날짜는 받는 컴퓨터의 시계로
    # 바뀌어 나온다 — 한국 노트북에서는 장 마감 뒤 발표가 하루 밀렸다(NVDA 11/17 → 11/18 · 2026-10-09 실측).
    # info 값이 지난 날이면(지난 발표일이 남아 있는 종목) calendar 의 날짜를 쓴다 — 그것은 시각 없는 예정일이다.
    stamp = _num(info.get("earningsTimestampStart")) or _num(info.get("earningsTimestamp"))
    dates = calendar.get("Earnings Date") or []
    if stamp and stamp >= time.time() - 6 * 3600:
        when = datetime.fromtimestamp(stamp, _NY)
        earn["next"] = when.date().isoformat()
        if not info.get("isEarningsDateEstimate"):
            # 야후는 장 마감 뒤 발표를 15:00 으로 적어 두기도 한다(NVDA 11/17 15:00 · 실제는 마감 뒤).
            # 장중 발표는 드물어 적지 않는다 — 9:30 전이면 장 전, 15:00 부터는 장 마감 뒤.
            minutes = when.hour * 60 + when.minute
            if minutes < 9 * 60 + 30:
                earn["when"] = "장 전"
            elif minutes >= 15 * 60:
                earn["when"] = "장 마감 뒤"
    elif isinstance(dates, (list, tuple)) and dates and _iso(dates[0]):
        earn["next"] = _iso(dates[0])
    estimate = _num(calendar.get("Earnings Average"))
    if estimate is not None:
        earn["eps_est"] = round(estimate, 3)
    try:
        history = handle.earnings_history
    except Exception:
        history = None
    rows = []
    if history is not None and not getattr(history, "empty", True):
        for stamp, row in history.iterrows():
            actual, expected = _num(row.get("epsActual")), _num(row.get("epsEstimate"))
            if actual is None or expected is None:
                continue
            surprise = _num(row.get("surprisePercent"))
            try:
                label = stamp.strftime("%y.%m")
            except Exception:
                label = str(stamp)[:7]
            rows.append([label, round(actual, 3), round(expected, 3),
                         None if surprise is None else round(surprise * 100.0, 1)])
    if rows:
        earn["hist"] = rows[-4:]
    if earn:
        out["earn"] = earn

    # 애널리스트 — 몇 명 · 목표주가(평균·최고·최저) · 사라/들고 있어라/팔아라 명수(이번 달)
    count = _num(info.get("numberOfAnalystOpinions"))
    if count and count > 0:
        ana = {"n": int(count), "mean": _num(info.get("targetMeanPrice")),
               "hi": _num(info.get("targetHighPrice")), "lo": _num(info.get("targetLowPrice")),
               "key": info.get("recommendationKey") or None}
        try:
            recs = handle.recommendations
        except Exception:
            recs = None
        if recs is not None and not getattr(recs, "empty", True):
            pick = recs[recs["period"] == "0m"] if "period" in recs.columns else recs
            row = (pick if len(pick) else recs).iloc[0]
            numbers = [_num(row.get(name)) or 0 for name in ("strongBuy", "buy", "hold", "sell", "strongSell")]
            if sum(numbers) > 0:
                ana.update(buy=int(numbers[0] + numbers[1]), hold=int(numbers[2]),
                           sell=int(numbers[3] + numbers[4]))
        out["ana"] = ana

    # 공매도 · 기관 · 내부자 — 내부자는 **시장에서 사고판 것만** 센다(스톡옵션 행사·증여는 안 센다)
    own: dict = {}
    for key, name in (("short", "shortPercentOfFloat"), ("inst", "heldPercentInstitutions"),
                      ("insider", "heldPercentInsiders")):
        value = _num(info.get(name))
        if value is not None:
            own[key] = round(value * 100.0, 2)
    try:
        trades = handle.insider_transactions
    except Exception:
        trades = None
    if trades is not None and not getattr(trades, "empty", True) and "Text" in trades.columns:
        since = datetime.now(_NY).date().toordinal() - 183
        buys = sells = 0
        bought = sold = 0.0
        for _index, row in trades.iterrows():
            try:
                day = row.get("Start Date")
                day = day.date() if hasattr(day, "date") else datetime.fromisoformat(str(day)[:10]).date()
            except Exception:
                continue
            if day.toordinal() < since:
                continue
            text = str(row.get("Text") or "")
            value = _num(row.get("Value")) or 0.0
            if text.startswith("Purchase at price"):
                buys, bought = buys + 1, bought + value
            elif text.startswith("Sale at price"):
                sells, sold = sells + 1, sold + value
        own["ins6m"] = [buys, round(bought / _MILLION, 2), sells, round(sold / _MILLION, 2)]
    if own:
        out["own"] = own

    # 배당 — 배당락일 · 지급일(배당하는 회사만)
    if (_num(info.get("dividendYield")) or 0) > 0:
        # 열쇠는 "divd" — "div" 는 배당수익률(재무 한눈에)이 이미 쓴다.
        dates_div = {key: _iso(calendar.get(name)) for key, name in (("ex", "Ex-Dividend Date"), ("pay", "Dividend Date"))
                     if _iso(calendar.get(name))}
        if dates_div:
            out["divd"] = dates_div
    return out


def _ny_today():
    return datetime.now(_NY).date()


def _day(iso):
    try:
        return datetime.fromisoformat(str(iso)[:10]).date()
    except Exception:
        return None


def _kday(day) -> str:
    """2026-11-17 → 「11월 17일(화)」."""
    return f"{day.month}월 {day.day}일({_WEEKDAYS[day.weekday()]})"


def earnings_days(ticker: str, today=None):
    """다음 실적 발표까지 남은 날(미국 날짜 · 오늘 = 0). 지났거나 모르면 None."""
    entry = load().get(str(ticker or "").strip().upper()) or {}
    day = _day((entry.get("earn") or {}).get("next"))
    if day is None:
        return None
    left = (day - (today or _ny_today())).days
    return left if left >= 0 else None


def earnings_chip_css(keys, today=None) -> str:
    """표 이름 단추 옆 「실적 D-○」 딱지 — [(단추 열쇠, 티커)] 중 7일 안에 발표하는 것만. 점수·순위는 그대로."""
    rules = []
    for key, ticker in keys or ():
        left = earnings_days(ticker, today)
        if left is None or left > EARNINGS_BADGE_DAYS:
            continue
        text = "실적 오늘" if left == 0 else "실적 내일" if left == 1 else f"실적 D-{left}"
        rules.append(
            f"div[class*='st-key-{key}'] button p::after{{content:'{text}';display:inline-block;margin-left:6px;"
            "padding:0 7px;border-radius:999px;background:#ffd166;color:#2a1c00;font-size:.68rem;"
            "font-weight:900;line-height:1.55;vertical-align:1px;white-space:nowrap}")
    return "".join(rules)


def _usd_money(million) -> str:
    """백만 달러 → 「1,169만 달러」·「2.3억 달러」."""
    if million is None:
        return "—"
    if abs(million) >= 100:
        return f"{million / 100:.1f}억 달러"
    return f"{million * 100:,.0f}만 달러"


def _eps(value) -> str:
    return "—" if value is None else (f"-${abs(value):.2f}" if value < 0 else f"${value:.2f}")


def _earn_box(earn: dict, today) -> str:
    esc = html.escape
    lines = []
    day = _day(earn.get("next"))
    if day is not None and day >= today:
        left = (day - today).days
        tail = "오늘" if left == 0 else "내일" if left == 1 else f"{left}일 남음"
        when = f" {earn['when']}" if earn.get("when") else ""
        lines.append(("다음 발표", f"<span class='j3st-hl'>{_kday(day)}{esc(when)}</span> · {tail}"))
    elif day is not None:
        # 야후에 다음 날짜가 아직 없는 회사(지난 발표일만 남아 있다 — 2026-10-09 HPE·TOL·RIO 등 5종목).
        lines.append(("다음 발표", f"<span class='j3st-dim'>다음 날짜 아직 안 나옴 · 지난 발표 {day.month}/{day.day}</span>"))
    else:
        lines.append(("다음 발표", "<span class='j3st-dim'>회사가 아직 날짜를 안 냈습니다</span>"))
    if earn.get("eps_est") is not None:
        estimate = float(earn["eps_est"])
        lines.append(("이번 예상", f"주당 이익 {_eps(estimate)}"
                      + (" (적자 예상)" if estimate < 0 else "") + " · 애널리스트 평균"))
    # **지난 분기 — 막대 대신 표** (2026-10-09 상하님 테슬라 캡처 — "그래프는 뭘 의미하는지 모르겠다 · 분기 실적과도
    # 그래프가 안 맞다"). 막대는 「예상과의 차이 %」였는데 설명이 없어, 매출·영업이익을 그린 「재무 한눈에」 분기
    # 그림과 견주게 됐다. 이제 분기마다 예상·실제·차이를 숫자로 적고, 무엇을 견준 것인지 한 줄로 적는다.
    history = [row for row in earn.get("hist") or [] if isinstance(row, list) and len(row) == 4]
    table = ""
    if history:
        better = sum(1 for _label, actual, expected, _s in history if actual > expected)
        tone = "j3st-up" if better * 2 >= len(history) else "j3st-dn"
        lines.append((f"지난 {len(history)}번",
                      f"예상보다 <span class='{tone}'>좋았음 {len(history)}번 중 {better}번</span>"))
        heads, guesses, actuals, gaps = [], [], [], []
        for label, actual, expected, surprise in history:
            if surprise is None and expected:
                surprise = (actual - expected) / abs(expected) * 100.0
            color = "#4cc9f0" if actual > expected else "#ff6b6b" if actual < expected else "#cfe0ff"
            heads.append(f"<th>{esc(str(label))}</th>")
            guesses.append(f"<td>{_eps(expected)}</td>")
            actuals.append(f"<td>{_eps(actual)}</td>")
            # 예상이 0 에 가까우면 %가 터무니없이 커진다(COIN 26.03 예상 $0.04 → 실제 -$1.49 = -3459%) — 300% 넘으면 줄여 적는다.
            if surprise is None:
                gap_text = "—"
            elif abs(surprise) >= 300:
                gap_text = "+300%↑" if surprise > 0 else "-300%↓"
            else:
                gap_text = f"{surprise:+.0f}%"
            gaps.append(f"<td style='color:{color}'>{gap_text}</td>")
        table = ("<table class='j3st-eps'><thead><tr><th>분기</th>" + "".join(heads) + "</tr></thead><tbody>"
                 "<tr><td>예상</td>" + "".join(guesses) + "</tr>"
                 "<tr><td>실제</td>" + "".join(actuals) + "</tr>"
                 "<tr><td>차이</td>" + "".join(gaps) + "</tr></tbody></table>"
                 "<div class='j3st-note'>주당 이익(회사가 번 돈 ÷ 주식 수)이 증권사 예상보다 높았나 · 분기는 「재무 한눈에」 "
                 "분기 실적과 같은 칸이고, 그쪽은 매출·영업이익의 크기입니다.</div>")
    rows = "".join(f"<div class='j3st-row'><b>{title}</b><span>{body}</span></div>" for title, body in lines)
    return f"<div class='j3st-box'><div class='j3st-h'>📅 실적 발표</div>{rows}{table}</div>"


def _ana_box(ana: dict, price_now) -> str:
    # 의견(사라·팔아라) 낸 사람과 목표주가 낸 사람은 수가 다르다(2026-10-09 실측 — ASML 42명 · 16명).
    votes = [ana.get(name) for name in ("buy", "hold", "sell")]
    has_votes = all(isinstance(v, int) for v in votes) and sum(votes) > 0
    parts = [f"<div class='j3st-h'>👥 애널리스트 의견"
             + (f" <span class='j3st-dim'>· {sum(votes)}명</span>" if has_votes else "") + "</div>"]
    if has_votes:
        parts.append(
            "<div class='j3st-split'>"
            + "".join(f"<i style='flex:{v};background:{c}'></i>"
                      for v, c in zip(votes, ("#06d6a0", "#ffd166", "#ff6b6b")) if v)
            + "</div><div class='j3st-legend'>"
            f"<span style='color:#06d6a0'>사라 {votes[0]}명</span>"
            f"<span style='color:#ffd166'>들고 있어라 {votes[1]}명</span>"
            f"<span style='color:#ff6b6b'>팔아라 {votes[2]}명</span></div>")
    low, mean, high = ana.get("lo"), ana.get("mean"), ana.get("hi")
    if low and mean and high and high > low:
        now = _num(price_now)
        left_edge, right_edge = min(low, now or low), max(high, now or high)
        span = (right_edge - left_edge) or 1.0

        def place(value):
            return max(0.0, min(100.0, (value - left_edge) / span * 100.0))

        def mark(css, value, text):
            # 끝에 붙은 표시는 글자를 안쪽으로 붙인다 — 가운데 맞추면 상자 밖으로 삐져나갔다
            # (2026-10-09 폰 412px 실측 — MRNA 지금 $197 이 최고 $170 보다 높아 오른쪽 끝).
            spot = place(value)
            shift = ("left:auto;right:0;transform:none" if spot > 85 else
                     "left:0;transform:none" if spot < 15 else "")
            return (f"<i class='j3st-mk {css}' style='left:{spot:.1f}%'>"
                    f"<em style='{shift}'>{text}</em></i>")

        marks = mark("j3st-mean", mean, f"평균 ${mean:,.0f}")
        if now:
            marks = mark("j3st-now", now, f"지금 ${now:,.0f}") + marks
        parts.append(
            f"<div class='j3st-h2'>🎯 목표주가 <span class='j3st-dim'>· {int(ana['n'])}명 · 1년 뒤 예상</span></div>"
            f"<div class='j3st-range'><div class='j3st-line'></div>{marks}"
            f"<span class='j3st-lab' style='left:0'>최저 ${low:,.0f}</span>"
            f"<span class='j3st-lab' style='right:0'>최고 ${high:,.0f}</span></div>")
        if now:
            gap = (mean / now - 1.0) * 100.0
            parts.append(f"<div class='j3st-row'><b>평균까지</b><span class='{'j3st-up' if gap >= 0 else 'j3st-dn'}'>"
                         f"지금보다 {gap:+.0f}%</span></div>")
    parts.append("<div class='j3st-note'>※ 증권사 애널리스트 의견입니다. 자비스 점수·판정에는 들어가지 않습니다.</div>")
    return f"<div class='j3st-box'>{''.join(parts)}</div>"


def _own_box(own: dict, div: dict, today) -> str:
    lines = []
    if own.get("short") is not None:
        lines.append(("공매도", f"유통 주식의 {own['short']:.1f}% <span class='j3st-dim'>· 주가가 내릴 쪽에 건 몫</span>"))
    trades = own.get("ins6m")
    if isinstance(trades, list) and len(trades) == 4:
        buys, bought, sells, sold = trades
        if buys or sells:
            body = (f"시장에서 산 것 {buys}번" + (f"({_usd_money(bought)})" if buys else "")
                    + f" · 판 것 {sells}번" + (f"({_usd_money(sold)})" if sells else ""))
        else:
            body = "시장에서 사고판 것 없음"
        lines.append(("내부자", body + " <span class='j3st-dim'>· 최근 6개월 임원·대주주</span>"))
    if own.get("inst") is not None:
        lines.append(("기관", f"기관이 가진 몫 {own['inst']:.0f}%"))
    ex, pay = _day((div or {}).get("ex")), _day((div or {}).get("pay"))
    if ex is not None and (today - ex).days <= 100:
        lines.append(("배당", f"배당락 {ex.month}월 {ex.day}일"
                      + (f" · 지급 {pay.month}월 {pay.day}일" if pay is not None else "")
                      + " <span class='j3st-dim'>· 배당락 전날까지 가진 사람이 받음</span>"))
    if not lines:
        return ""
    rows = "".join(f"<div class='j3st-row'><b>{title}</b><span>{body}</span></div>" for title, body in lines)
    return f"<div class='j3st-box'><div class='j3st-h'>🔍 공매도 · 내부자 · 배당</div>{rows}</div>"


def street_html(ticker: str, price_now=None, today=None) -> str:
    """세부사항 종목 개요 밑 상자 셋 — 실적 발표 · 애널리스트 · 공매도·내부자·배당. 없는 것은 안 그린다."""
    entry = load().get(str(ticker or "").strip().upper()) or {}
    today = today or _ny_today()
    boxes = []
    if entry.get("earn"):
        boxes.append(_earn_box(entry["earn"], today))
    if (entry.get("ana") or {}).get("n"):
        boxes.append(_ana_box(entry["ana"], price_now))
    boxes.append(_own_box(entry.get("own") or {}, entry.get("divd") or {}, today))
    boxes = [box for box in boxes if box]
    return f"<div class='j3st'>{''.join(boxes)}</div>" if boxes else ""


_MACRO_LOADED = {"mtime": None, "data": None}


def load_macro(path: Path | None = None) -> dict:
    """data/calendar/US_macro.json — 금리 결정·물가·고용 발표 날짜(나라가 미리 낸 일정표)."""
    path = path or MACRO_PATH
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return {}
    if _MACRO_LOADED["mtime"] == mtime and _MACRO_LOADED["data"] is not None:
        return _MACRO_LOADED["data"]
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        data = {}
    _MACRO_LOADED.update(mtime=mtime, data=data)
    return data


def upcoming_events(today=None, days: int = UPCOMING_DAYS, macro_days: int = MACRO_DAYS) -> list:
    """종목 실적은 days 일 · 큰 발표는 macro_days 일 안 — [{date, macro: [(이름, 갈래)…], stocks: [(한글 이름, 티커,
    장 전/뒤)…]}] (날짜 차례)."""
    today = today or _ny_today()
    last = today.toordinal() + days - 1
    macro_last = today.toordinal() + macro_days - 1
    by_day: dict = {}
    for event in (load_macro().get("events") or []):
        day = _day(event.get("date"))
        if day is not None and today.toordinal() <= day.toordinal() <= macro_last:
            by_day.setdefault(day, {"macro": [], "stocks": []})["macro"].append(
                (str(event.get("label") or ""), str(event.get("kind") or "")))
    about = load_about()
    for code, entry in load().items():
        day = _day(((entry or {}).get("earn") or {}).get("next"))
        if day is None or not (today.toordinal() <= day.toordinal() <= last):
            continue
        name = (about.get(code) or {}).get("ko") or code
        by_day.setdefault(day, {"macro": [], "stocks": [], "_cap": {}})["stocks"].append(
            (name, code, (entry.get("earn") or {}).get("when")))
        by_day[day].setdefault("_cap", {})[code] = _num(entry.get("mcap")) or 0.0
    out = []
    for day in sorted(by_day):
        row = by_day[day]
        caps = row.pop("_cap", {})
        # 한 날에 여럿이면 **큰 회사부터** 적는다(이름 몇 개만 보이고 나머지는 「외 ○종목」이다).
        row["stocks"].sort(key=lambda item: -caps.get(item[1], 0.0))
        out.append({"date": day, **row})
    return out


def upcoming_html(today=None, days: int = UPCOMING_DAYS, max_names: int = 3) -> str:
    """시장분석 맨 위 「📆 다가오는 일정」 — 금리 결정·물가·고용 + 명부 종목 실적 날. 아무것도 없으면 빈 글."""
    today = today or _ny_today()
    events = upcoming_events(today, days)
    if not events:
        return ""
    esc = html.escape
    rows = []
    for event in events:
        day = event["date"]
        left = (day - today).days
        label = "오늘" if left == 0 else "내일" if left == 1 else f"{day.month}/{day.day}({_WEEKDAYS[day.weekday()]})"
        first = True
        for name, kind in event["macro"]:
            rows.append(f"<div class='j3up-row'><b>{label if first else ''}</b>"
                        f"<span class='{'j3up-fomc' if kind == 'fomc' else 'j3up-macro'}'>{esc(name)}</span></div>")
            first = False
        stocks = event["stocks"]
        if stocks:
            names = "·".join(esc(name) for name, _code, _when in stocks[:max_names])
            more = f" 외 {len(stocks) - max_names}종목" if len(stocks) > max_names else ""
            whens = {when for _n, _c, when in stocks if when}
            when = f" <span class='j3up-when'>{esc(next(iter(whens)))}</span>" if len(whens) == 1 else ""
            tickers = " ".join(code for _n, code, _w in stocks)
            rows.append(f"<div class='j3up-row'><b>{label if first else ''}</b>"
                        f"<span title='{esc(tickers)}'>{names}{more} 실적{when}</span></div>")
    known = load_macro().get("known_until") or {}
    gaps = [name for key, name in (("cpi", "물가"), ("jobs", "고용")) if _day(known.get(key)) and
            _day(known.get(key)).toordinal() < today.toordinal() + MACRO_DAYS - 1]
    note = ("명부 209종목 실적 날 + 미국 금리 결정·물가·고용 발표 · 미국 날짜 · 실적 날은 회사가 바꾸기도 합니다"
            + (f" · {'·'.join(gaps)} 발표는 노동부가 다음 해 일정을 내면 채웁니다" if gaps else ""))
    return (f"<div class='j3up'><div class='j3up-h'>📆 다가오는 일정 "
            f"<span>· 종목 실적 앞으로 {days}일 · 금리·물가·고용 한 달</span></div>"
            f"{''.join(rows)}<div class='j3up-note'>{note}</div></div>")


STREET_CSS = """<style>
.j3st{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:8px;margin:8px 0 4px}
.j3st-box{border:1px solid #2b4f80;border-radius:13px;padding:10px 12px 9px;background:rgba(77,127,208,.10);min-width:0}
.j3st-h{font-size:.95rem;font-weight:900;color:#fff;margin-bottom:5px}
.j3st-h2{font-size:.88rem;font-weight:900;color:#fff;margin:10px 0 0}
.j3st-row{display:flex;align-items:baseline;gap:8px;font-size:.82rem;line-height:1.75;color:#e6edf8}
.j3st-row > b{flex:0 0 66px;color:#8fb4de;font-weight:700}
.j3st-row > span{min-width:0}
.j3st-hl{color:#ffd166;font-weight:900}
.j3st-up{color:#4cc9f0;font-weight:800}
.j3st-dn{color:#ff6b6b;font-weight:800}
.j3st-dim{color:#7f9cc0;font-size:.74rem}
.j3st-eps{width:100%;border-collapse:collapse;table-layout:fixed;font-size:.76rem;margin:4px 0 0!important;border:none!important}
.j3st-eps th,.j3st-eps td{border:none!important;text-align:right;padding:2px 4px;white-space:nowrap}
.j3st-eps th{color:#8fb4de;font-weight:700;border-bottom:1px solid rgba(157,204,255,.18)!important}
.j3st-eps td{color:#e6edf8;font-weight:700;border-bottom:1px solid rgba(157,204,255,.06)!important}
.j3st-eps th:first-child,.j3st-eps td:first-child{text-align:left;color:#8fb4de;width:44px}
.j3st-split{display:flex;height:12px;border-radius:6px;overflow:hidden;margin:2px 0 3px}
.j3st-split i{display:block}
.j3st-legend{display:flex;justify-content:space-between;gap:6px;font-size:.76rem;font-weight:800}
.j3st-range{position:relative;height:40px;margin:16px 4px 0}
.j3st-line{position:absolute;left:0;right:0;top:12px;height:4px;border-radius:2px;
  background:linear-gradient(90deg,#ff6b6b,#ffd166,#06d6a0)}
.j3st-mk{position:absolute;top:5px;width:2px;height:18px;background:#fff;font-style:normal}
.j3st-mk.j3st-mean{background:#ffd166}
.j3st-mk em{position:absolute;top:-15px;left:50%;transform:translateX(-50%);font-style:normal;font-size:.7rem;
  font-weight:800;white-space:nowrap;color:#fff}
.j3st-mk.j3st-mean em{top:auto;bottom:-15px;color:#ffd166}
.j3st-lab{position:absolute;top:26px;font-size:.68rem;color:#8fb4de;white-space:nowrap}
.j3st-note{font-size:.72rem;color:#6f93bd;margin-top:6px;line-height:1.5}
.j3up{margin:10px 0 4px;border:1px solid #2b4f80;border-radius:13px;padding:10px 12px 9px;background:rgba(77,127,208,.08)}
.j3up-h{font-size:.95rem;font-weight:900;color:#fff;margin-bottom:4px}
.j3up-h span{font-size:.74rem;font-weight:600;color:#8fb4de}
.j3up-row{display:flex;gap:8px;font-size:.84rem;line-height:1.75;color:#e6edf8}
.j3up-row > b{flex:0 0 70px;color:#8fb4de;font-weight:800}
.j3up-row > span{min-width:0}
.j3up-fomc{color:#ffd166;font-weight:900}
.j3up-macro{color:#f6c177;font-weight:800}
.j3up-when{color:#8fb4de;font-size:.76rem}
.j3up-note{font-size:.72rem;color:#6f93bd;margin-top:5px;line-height:1.5}
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
