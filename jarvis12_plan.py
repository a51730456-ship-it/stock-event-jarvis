"""자비스12 기능 ③ — 내 계획 한 장 (2026-11-13 상하님 「너의 추천 차례로 다 해라」).

본뜬 곳 — Fidelity Active Trader Pro 「Trade Armor」. 상하님이 **직접 적은** 산 값 · 손절 · 목표 · 수량을 최근 주가 그림 위에 선으로
긋고, 목표에 닿으면 얼마를 벌고 손절에 닿으면 얼마를 잃는지 금액으로 보여 준다.
**앱은 손절 · 목표 · 수량을 정하지 않는다**(CLAUDE.md 0-1 바) — 빈칸으로 열고, 적은 값만 그린다. 점수 · 판정에 안 쓴다.

기록은 자비스12 전용 표 `jarvis12_plans`(같은 DB · 표만 새로 · 옛 표는 안 건드림)에 종목마다 한 줄. 온라인은 원격 DB 라 남는다.
"""
from __future__ import annotations

import math
import threading
from datetime import datetime

import db_runtime
from database import DB_PATH

MODULE_REVISION = 2026111301

_LOCK = threading.Lock()
_READY = False


def _connection():
    return db_runtime.connect(DB_PATH)


def ensure_table() -> None:
    global _READY
    if _READY:
        return
    with _LOCK:
        if _READY:
            return
        conn = _connection()
        try:
            conn.execute("""CREATE TABLE IF NOT EXISTS jarvis12_plans (
                ticker TEXT PRIMARY KEY, buy REAL, stop REAL, target REAL, qty REAL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
            conn.commit()
            _READY = True
        finally:
            conn.close()


def _ticker(ticker) -> str:
    ticker = str(ticker or "").strip().upper()
    if not ticker or len(ticker) > 16 or not all(ch.isalnum() or ch in "-_." for ch in ticker):
        raise ValueError("올바른 미국 티커가 아닙니다")
    return ticker


def _positive(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value > 0 else None


def check(buy, stop, target, qty) -> tuple[dict | None, str | None]:
    """적은 값 확인 — 산 값은 꼭 · 손절은 산 값보다 아래 · 목표는 산 값보다 위 · 수량은 선택. (값, 문제 글)."""
    buy, stop, target, qty = _positive(buy), _positive(stop), _positive(target), _positive(qty)
    if buy is None:
        return None, "산 값(또는 살 값)을 적어 주십시오."
    if stop is not None and stop >= buy:
        return None, "손절은 산 값보다 낮아야 합니다."
    if target is not None and target <= buy:
        return None, "목표는 산 값보다 높아야 합니다."
    if stop is None and target is None:
        return None, "손절이나 목표 중 하나는 적어 주십시오."
    return {"buy": buy, "stop": stop, "target": target, "qty": qty}, None


def get(ticker) -> dict | None:
    ensure_table()
    conn = _connection()
    try:
        row = conn.execute("SELECT ticker, buy, stop, target, qty, updated_at FROM jarvis12_plans WHERE ticker = ?",
                           (_ticker(ticker),)).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return {"ticker": row[0], "buy": row[1], "stop": row[2], "target": row[3], "qty": row[4], "updated_at": row[5]}


def save(ticker, buy, stop, target, qty) -> dict:
    values, problem = check(buy, stop, target, qty)
    if problem:
        raise ValueError(problem)
    ensure_table()
    ticker = _ticker(ticker)
    now = datetime.now().isoformat(timespec="seconds")
    conn = _connection()
    try:
        conn.execute("DELETE FROM jarvis12_plans WHERE ticker = ?", (ticker,))
        conn.execute("INSERT INTO jarvis12_plans (ticker, buy, stop, target, qty, created_at, updated_at) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (ticker, values["buy"], values["stop"], values["target"], values["qty"], now, now))
        conn.commit()
    finally:
        conn.close()
    return {"ticker": ticker, **values, "updated_at": now}


def delete(ticker) -> None:
    ensure_table()
    conn = _connection()
    try:
        conn.execute("DELETE FROM jarvis12_plans WHERE ticker = ?", (_ticker(ticker),))
        conn.commit()
    finally:
        conn.close()


def outcome(plan: dict) -> dict:
    """목표 · 손절에 닿으면 % 와 금액(수량이 있을 때만) · 위아래 비율."""
    buy = float(plan["buy"])
    qty = _positive(plan.get("qty"))
    out = {}
    for key in ("target", "stop"):
        level = _positive(plan.get(key))
        if level is None:
            continue
        pct = (level / buy - 1.0) * 100.0
        out[key] = {"price": level, "pct": round(pct, 1), "money": round((level - buy) * qty, 2) if qty else None}
    if "target" in out and "stop" in out and out["stop"]["pct"]:
        out["ratio"] = round(abs(out["target"]["pct"] / out["stop"]["pct"]), 1)
    return out


def _money(value) -> str:
    if value is None:
        return ""
    sign = "+" if value >= 0 else "−"
    return f" · {sign}{abs(value):,.0f} 달러"


def html(plan: dict, closes: list | None = None, current: float | None = None) -> str:
    """최근 주가(있으면) 위에 목표 · 산 값 · 손절 선 · 지금 값 점 · 금액."""
    if not plan:
        return ""
    result = outcome(plan)
    buy = float(plan["buy"])
    levels = [buy] + [v["price"] for v in (result.get("target"), result.get("stop")) if v]
    series = [float(c) for c in (closes or []) if c and math.isfinite(float(c))][-60:]
    values = levels + series + ([float(current)] if current else [])
    low, high = min(values), max(values)
    pad = (high - low) * 0.12 or high * 0.05
    low, high = low - pad, high + pad
    width, height, right = 320, 150, 250

    def y(price):
        return 8 + (high - price) / (high - low) * (height - 16)

    parts = []
    if len(series) >= 2:
        step = right / (len(series) - 1)
        points = " ".join(f"{i * step:.1f},{y(p):.1f}" for i, p in enumerate(series))
        parts.append(f"<polyline fill='none' stroke='#4cc3ff' stroke-width='2' points='{points}'/>")
    rows = [("target", "목표", "#3ddc97", "5 4"), (None, "산 값", "#e8f0fb", "2 3"), ("stop", "손절", "#ff6b6b", "5 4")]
    for key, label, color, dash in rows:
        item = result.get(key) if key else {"price": buy, "pct": 0.0, "money": None}
        if not item:
            continue
        yy = y(item["price"])
        parts.append(f"<line x1='0' y1='{yy:.1f}' x2='{width}' y2='{yy:.1f}' stroke='{color}' stroke-dasharray='{dash}'/>")
        text = f"{label} {item['price']:,.2f}" + (f" ({item['pct']:+.1f}%)" if key else "")
        parts.append(f"<text x='{width - 2}' y='{yy - 4:.1f}' text-anchor='end' font-size='11' font-weight='700' fill='{color}'>{text}</text>")
    if current:
        parts.append(f"<circle cx='{right:.1f}' cy='{y(float(current)):.1f}' r='4.5' fill='#ffcf5c'/>")
    svg = (f"<svg viewBox='0 0 {width} {height}' width='100%' role='img' aria-label='내 계획 — 목표 · 산 값 · 손절 선'>"
           + "".join(parts) + "</svg>")
    lines = []
    if result.get("target"):
        lines.append(f"<span style='color:#3ddc97'>목표에 닿으면 {result['target']['pct']:+.1f}%{_money(result['target']['money'])}</span>")
    if result.get("stop"):
        lines.append(f"<span style='color:#ff6b6b'>손절에 닿으면 {result['stop']['pct']:+.1f}%{_money(result['stop']['money'])}</span>")
    if result.get("ratio") is not None:
        lines.append(f"<span style='color:#8fa6c4'>버는 폭 ÷ 잃는 폭 = {result['ratio']:.1f}배</span>")
    qty = _positive(plan.get("qty"))
    now_line = ""
    if current:
        now_pct = (float(current) / buy - 1.0) * 100.0
        now_line = (f"<span style='color:#ffcf5c'>지금 {float(current):,.2f} ({now_pct:+.1f}%"
                    + (f"{_money((float(current) - buy) * qty)}" if qty else "") + ")</span>")
    return (
        "<div class='j12pl-box'><div class='j12pl-title'>📝 내 계획 한 장 "
        f"<span class='j12pl-sub'>{plan.get('ticker') or ''} · 상하님이 적은 값 · 수량 {f'{qty:,.0f}주' if qty else '안 적음'}</span></div>"
        + svg
        + "<div class='j12pl-lines'>" + "".join(f"<div>{line}</div>" for line in lines + ([now_line] if now_line else [])) + "</div>"
        "<div class='j12pl-sub'>앱은 손절 · 목표 · 수량을 정하지 않습니다 · 점수 · 판정에 안 씀</div></div>")


CSS = (
    "<style>"
    ".j12pl-box{background:#0d2340;border:1px solid #1f3a5f;border-radius:12px;padding:.55rem .7rem;margin:.35rem 0 .45rem;}"
    ".j12pl-title{font-weight:900;font-size:.9rem;color:#e8f0fb;margin-bottom:.2rem;}"
    ".j12pl-sub{color:#8fa6c4;font-size:.72rem;font-weight:400;}"
    ".j12pl-lines{display:grid;gap:.1rem;font-size:.84rem;font-weight:700;margin:.25rem 0;}"
    "</style>"
)
