"""자비스12 기능 ② — 종목 성적표 A~F (2026-11-13 상하님 「너의 추천 차례로 다 해라」).

본뜬 곳 — Schwab 「Equity Ratings」(A 위 10% · B 20% · C 40% · D 20% · F 10%) · Fidelity 「Equity Summary Score」.
미국테마 명부(재무 파일 data/fundamentals/US.json 의 종목들) **안에서** 다섯 과목 등수를 매긴다.

  성장     — 최근 연간 매출 ÷ 그 전해 매출 − 1               (클수록 좋음)
  수익     — 영업이익률(opm)                                 (클수록 좋음)
  가격     — PER(pe · 0 보다 클 때만)                         (작을수록 좋음 · 적자는 빈칸)
  주가 힘  — 최근 6개월(126장) 수익률                         (클수록 좋음)
  흔들림   — 최근 60장 날마다 수익률의 표준편차                (작을수록 좋음 · A = 가장 조용)

못 잰 과목은 빈칸(—) — 0 이나 F 로 채우지 않는다. **보여 주기만** — 점수 · 판정 · 차례에 안 쓴다.
재무는 파일만 읽고, 주가는 화면이 받아 둔 200종목 2년 일봉만 읽는다(새로 받으러 가지 않는다).
"""
from __future__ import annotations

import json
import math
import threading
import time
from pathlib import Path

import jarvis3_data as j3

MODULE_REVISION = 2026111301

PATH = Path(__file__).resolve().parent / "data" / "fundamentals" / "US.json"
SUBJECTS = (("growth", "성장"), ("margin", "수익"), ("value", "가격"), ("momentum", "주가 힘"), ("calm", "흔들림"))
CUTS = ((0.10, "A"), (0.30, "B"), (0.70, "C"), (0.90, "D"), (1.01, "F"))
_MEMO: dict = {}
_LOCK = threading.Lock()
_MEMO_SECONDS = 3600.0


def _finite(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def raw_values(stocks: dict, daily: dict | None) -> dict:
    """종목마다 다섯 과목 원래 값(못 재면 None)."""
    out = {}
    for ticker, info in (stocks or {}).items():
        info = info or {}
        annual = info.get("annual") or []
        growth = None
        if len(annual) >= 2:
            now, before = _finite(annual[-1][1]), _finite(annual[-2][1])
            if now is not None and before and before > 0:
                growth = (now / before - 1.0) * 100.0
        pe = _finite(info.get("pe"))
        values = {"growth": growth, "margin": (_finite(info.get("opm")) or None),
                  "value": pe if pe is not None and pe > 0 else None, "momentum": None, "calm": None}
        if values["margin"] is not None:
            values["margin"] *= 100.0
        frame = (daily or {}).get(ticker)
        if frame is not None:
            try:
                close = frame["Close"].astype(float).dropna()
                if len(close) > 126:
                    values["momentum"] = (float(close.iloc[-1]) / float(close.iloc[-127]) - 1.0) * 100.0
                returns = close.pct_change().dropna().tail(60)
                if len(returns) >= 40:
                    values["calm"] = float(returns.std()) * 100.0
            except Exception:
                pass
        out[ticker] = values
    return out


def grade_table(raw: dict) -> dict:
    """과목마다 명부 안 등수 → A~F. 좋은 쪽: 성장 · 수익 · 주가 힘은 큰 값, 가격 · 흔들림은 작은 값."""
    grades = {ticker: {} for ticker in raw}
    for key, _label in SUBJECTS:
        known = [(ticker, values[key]) for ticker, values in raw.items() if values.get(key) is not None]
        if len(known) < 10:
            continue
        reverse = key not in ("value", "calm")
        known.sort(key=lambda item: item[1], reverse=reverse)
        total = len(known)
        for place, (ticker, _value) in enumerate(known):
            share = (place + 1) / total
            grades[ticker][key] = next(letter for cut, letter in CUTS if share <= cut + 1e-9)
    return grades


def _load_stocks() -> dict:
    try:
        return (json.loads(PATH.read_text(encoding="utf-8")) or {}).get("stocks") or {}
    except Exception:
        return {}


def table() -> dict:
    """명부 전체 성적표 — 1시간 기억. {"grades": {티커: {과목: 글자}}, "raw": …, "count": 종목 수}."""
    with _LOCK:
        hit = _MEMO.get("all")
        if hit and time.time() - hit[0] < _MEMO_SECONDS:
            return hit[1]
    stocks = _load_stocks()
    try:
        daily, _meta, _members = j3._universe_daily(True)
    except Exception:
        daily = {}
    raw = raw_values(stocks, daily)
    value = {"grades": grade_table(raw), "raw": raw, "count": len(raw), "has_prices": bool(daily)}
    # 주가를 아직 못 읽은 판(막 켜진 앱)은 오래 기억하지 않는다 — 다음에 다시 센다.
    with _LOCK:
        _MEMO["all"] = (time.time() if daily else time.time() - _MEMO_SECONDS + 60, value)
    return value


_COLORS = {"A": "#3ddc97", "B": "#9be564", "C": "#ffcf5c", "D": "#ff9f5c", "F": "#ff6b6b"}


def _value_text(key: str, value) -> str:
    if value is None:
        return "—"
    if key == "value":
        return f"PER {value:.0f}"
    if key == "calm":
        return f"하루 {value:.1f}%"
    if key == "margin":
        return f"{value:.0f}%"
    return f"{value:+.0f}%"


def card_html(ticker: str, data: dict | None = None) -> str:
    """세부사항 「재무 한눈에」 위 다섯 칸. 이 종목이 명부에 없거나 다섯 과목 다 못 재면 빈 글."""
    data = data or table()
    ticker = str(ticker or "").upper()
    grades = (data.get("grades") or {}).get(ticker)
    raw = (data.get("raw") or {}).get(ticker) or {}
    if grades is None or not grades:
        return ""
    cells = []
    for key, label in SUBJECTS:
        letter = grades.get(key)
        color = _COLORS.get(letter or "", "#5d7594")
        cells.append(
            f"<div class='j12gr-cell'><b style='color:{color}'>{letter or '—'}</b>"
            f"<span class='j12gr-l'>{label}</span><span class='j12gr-v'>{_value_text(key, raw.get(key))}</span></div>")
    count = int(data.get("count") or 0)
    return (
        "<div class='j12gr-box'><div class='j12gr-title'>🎓 종목 성적표 "
        f"<span class='j12gr-sub'>명부 {count}종목 안 등수 · A 위 10% · B 20% · C 40% · D 20% · F 10%</span></div>"
        f"<div class='j12gr-row'>{''.join(cells)}</div>"
        "<details class='j12gr-more'><summary>과목 뜻</summary><div class='j12gr-sub'>"
        "성장 = 최근 연간 매출이 그 전해보다 · 수익 = 영업이익률 · 가격 = PER 이 낮을수록 좋음(적자는 —) · "
        "주가 힘 = 최근 6개월 수익률 · 흔들림 = 최근 60일 하루 움직임이 작을수록 A · 보여 주기만(점수 · 판정 안 바꿈)"
        "</div></details></div>")


CSS = (
    "<style>"
    ".j12gr-box{background:#0d2340;border:1px solid #1f3a5f;border-radius:12px;padding:.55rem .7rem;margin:.35rem 0 .45rem;}"
    ".j12gr-title{font-weight:900;font-size:.9rem;color:#e8f0fb;}"
    ".j12gr-sub{color:#8fa6c4;font-size:.72rem;font-weight:400;}"
    ".j12gr-row{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.35rem;margin-top:.4rem;}"
    ".j12gr-cell{background:#10294a;border-radius:9px;padding:.35rem .1rem;text-align:center;display:flex;flex-direction:column;}"
    ".j12gr-cell b{font-size:1.35rem;font-weight:900;line-height:1.1;}"
    ".j12gr-l{font-size:.74rem;color:#e8f0fb;}"
    ".j12gr-v{font-size:.66rem;color:#8fa6c4;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}"
    ".j12gr-more summary{cursor:pointer;color:#4cc3ff;font-size:.76rem;margin-top:.3rem;}"
    "</style>"
)
