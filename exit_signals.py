"""보유 종목의 매도 시점 표시 — 미국테마·한국테마가 같이 쓴다 (2026-07-30).

**앱이 '팔아라'라고 정하지 않는다.** 살 때 사용자가 정해 둔 선(무효화가격·목표가)에
지금 값이 닿았는지 알려줄 뿐이다. 새 숫자를 만들지 않는다.

미국과 한국을 다르게 두는 이유(2026-07-30 조사):
- Kaminski & Lo — 손절은 '오르던 게 계속 오르는' 시장에서만 이득이고,
  '빠진 게 되돌아오는' 시장에서는 오히려 손해다(반등 직전에 털린다).
- 한국은 2000년 이후 되돌아오는 성격이 뚜렷하고, 특히 2008년 이후 그쪽으로 넘어갔다.
  미국은 이어지는 성격이 남아 있다.
→ 미국: 손절선을 고점 따라 **올린다**(번 것을 지킨다).
→ 한국: 손절선을 처음 값 **그대로 둔다**. 대신 20일선과 보유일수를 앞에 놓는다.
  눌림목은 되돌아오길 기다리고 산 것이라 손절선을 올려 붙이면 우리가 노린 반등
  직전에 털린다.

여기 숫자는 전부 사용자가 정했거나 앱이 이미 쓰던 것이다. 남의 시장에서 잰 값을
점수·판정에 넣지 않는다는 규칙(CLAUDE.md)을 그대로 지킨다.
"""
from __future__ import annotations

import json
from datetime import date, datetime


def _plan(trade: dict) -> dict:
    raw = trade.get("entry_plan_json")
    if not raw:
        return {}
    try:
        return json.loads(raw) or {}
    except Exception:
        return {}


def _num(value):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out > 0 else None


def _days_held(buy_date) -> int | None:
    try:
        start = datetime.fromisoformat(str(buy_date)[:10]).date()
    except Exception:
        return None
    return (date.today() - start).days


def evaluate(trade: dict, *, current, sma20=None, peak_since_buy=None, market: str = "KR") -> dict:
    """보유 한 건의 상태를 만든다. 순수 계산 — 화면도 조회도 하지 않는다(테스트로 굳힌다)."""
    plan = _plan(trade)
    buy = _num(trade.get("buy_price"))
    now = _num(current)
    stop = _num(plan.get("invalidation"))
    target = _num(plan.get("target"))
    peak = _num(peak_since_buy)
    sma = _num(sma20)

    # 미국은 손절선을 고점 따라 올린다. 산 뒤 최고가가 매수가보다 오른 만큼 그대로 올린다.
    # 처음 손절선보다 낮아지지는 않는다.
    stop_now, stop_moved = stop, False
    if market == "US" and stop and buy and peak and peak > buy:
        lifted = stop + (peak - buy)
        if lifted > stop:
            stop_now, stop_moved = lifted, True

    signals = []
    if stop_now and now:
        if now < stop_now:
            signals.append(("🔴", "손절선 아래입니다",
                            f"살 때 정한 {stop:,.0f}"
                            + (f" → 고점 따라 {stop_now:,.0f}" if stop_moved else "")
                            + f" · 지금 {now:,.0f}"))
    if target and now and now >= target:
        signals.append(("🟢", "목표에 닿았습니다", f"살 때 정한 {target:,.0f} · 지금 {now:,.0f}"))
    if sma and now and now < sma:
        signals.append(("🟡", "20일선 아래입니다", f"20일선 {sma:,.0f} · 지금 {now:,.0f}"))

    drawdown = None
    if peak and now and peak > 0:
        drawdown = (now / peak - 1) * 100
    profit = (now / buy - 1) * 100 if (buy and now) else None

    return {
        "name": trade.get("stock_name") or trade.get("ticker") or "—",
        "style": trade.get("trade_style") or "",
        "buy_date": str(trade.get("buy_date") or "")[:10],
        "buy_price": buy,
        "current": now,
        "profit_pct": profit,
        "stop": stop,
        "stop_now": stop_now,
        "stop_moved": stop_moved,
        "target": target,
        "sma20": sma,
        "peak": peak,
        "drawdown_pct": drawdown,
        "days_held": _days_held(trade.get("buy_date")),
        "signals": signals,
        "market": market,
    }
