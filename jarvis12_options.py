"""자비스12 기능 ① — 실적 날 흔들림 예보 (2026-11-13 상하님 「너의 추천 차례로 다 해라」).

본뜬 곳 — Schwab thinkorswim 「Market Maker Move」. 실적 발표가 걸린 가장 가까운 옵션 만기의 **ATM 스트래들 값 ÷ 주가**로
「시장이 매긴 위아래 움직임 크기」를 어림한다(오를지 내릴지는 모른다 · 크기만).
  · 만기 — 발표일이 「장 마감 뒤」면 발표일 **다음 날 이후** 첫 만기, 아니면 발표일 이후 첫 만기. 발표일에서 10일 넘게 먼 만기는 안 쓴다.
  · 값 — 매수 · 매도 호가가 둘 다 있으면 가운데 값, 없으면 마지막 체결가. 콜 · 풋이 같은 행사가에 둘 다 있어야 한다.

**화면은 파일(data/fundamentals/US_implied.json)만 읽는다** — 옵션 값은 깃허브 「자비스12 실적 흔들림 모으기」가 장 마감 뒤
발표가 14일 안에 있는 종목만 받아 올린다(`python jarvis12_options.py collect`). 못 받은 종목은 옛 값을 두고(발표일이 안 지났으면),
0 으로 채우지 않는다. **보여 주기만** — 점수 · 판정 · 차례에 안 쓴다.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

MODULE_REVISION = 2026111302

ROOT = Path(__file__).resolve().parent
FUND = ROOT / "data" / "fundamentals" / "US.json"
OUT = ROOT / "data" / "fundamentals" / "US_implied.json"
AHEAD_DAYS = 14
MAX_EXPIRY_GAP = 10
_NY = ZoneInfo("America/New_York")


def _today() -> date:
    return datetime.now(_NY).date()


def _finite(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value > 0 else None


def pick_expiry(expiries, earn: date, after_close: bool):
    """발표를 품는 가장 가까운 만기(문자열) — 없거나 너무 멀면 None."""
    first = earn + timedelta(days=1) if after_close else earn
    for text in sorted(expiries or ()):
        try:
            day = date.fromisoformat(str(text))
        except ValueError:
            continue
        if day >= first:
            return text if (day - earn).days <= MAX_EXPIRY_GAP else None
    return None


def _price(row) -> float | None:
    bid, ask = _finite(row.get("bid")), _finite(row.get("ask"))
    if bid and ask and ask >= bid:
        return (bid + ask) / 2.0
    return _finite(row.get("lastPrice"))


def straddle_move(calls, puts, spot: float) -> dict | None:
    """ATM(주가에 가장 가까운, 콜 · 풋 둘 다 있는) 행사가의 스트래들 값 ÷ 주가(%)."""
    spot = _finite(spot)
    if not spot or calls is None or puts is None or len(calls) == 0 or len(puts) == 0:
        return None
    call_by = {float(r["strike"]): r for r in calls.to_dict("records") if _finite(r.get("strike"))}
    put_by = {float(r["strike"]): r for r in puts.to_dict("records") if _finite(r.get("strike"))}
    strikes = sorted(set(call_by) & set(put_by), key=lambda k: abs(k - spot))
    for strike in strikes[:3]:
        c, p = _price(call_by[strike]), _price(put_by[strike])
        if c and p:
            move = (c + p) / spot * 100.0
            if 0 < move < 60:
                return {"strike": strike, "straddle": round(c + p, 2), "move": round(move, 1)}
    return None


def implied_move(ticker: str, earn: date, after_close: bool) -> dict | None:
    """야후 옵션으로 한 종목 — 깃허브 모으기에서만 부른다(화면은 부르지 않는다)."""
    import yfinance as yf

    tk = yf.Ticker(ticker)
    expiry = pick_expiry(tk.options, earn, after_close)
    if not expiry:
        return None
    try:
        spot = float(tk.fast_info["last_price"])
    except Exception:
        hist = tk.history(period="5d")
        spot = float(hist["Close"].iloc[-1]) if len(hist) else None
    chain = tk.option_chain(expiry)
    found = straddle_move(chain.calls, chain.puts, spot)
    if not found:
        return None
    return {"expiry": expiry, "spot": round(float(spot), 2), **found}


def upcoming(stocks: dict, today: date, days: int = AHEAD_DAYS) -> list:
    """발표가 오늘 ~ days 일 안에 있는 종목 [(티커, 발표일, 장 마감 뒤?)] — 가까운 차례."""
    out = []
    for ticker, info in (stocks or {}).items():
        earn = (info or {}).get("earn") or {}
        try:
            day = date.fromisoformat(str(earn.get("next")))
        except (TypeError, ValueError):
            continue
        if today <= day <= today + timedelta(days=days):
            out.append((ticker, day, str(earn.get("when") or "") == "장 마감 뒤", str(earn.get("when") or "")))
    return sorted(out, key=lambda item: (item[1], item[0]))


def collect(*, dry: bool = False, limit: int | None = None) -> dict:
    stocks = (json.loads(FUND.read_text(encoding="utf-8")) or {}).get("stocks") or {}
    today = _today()
    try:
        old = (json.loads(OUT.read_text(encoding="utf-8")) or {}).get("moves") or {}
    except Exception:
        old = {}
    # 발표일이 지난 옛 값은 버린다 — 지난 실적의 예보를 다음 실적처럼 보이면 안 된다.
    moves = {t: v for t, v in old.items() if str(v.get("earn") or "") >= today.isoformat()}
    targets = upcoming(stocks, today)
    if limit:
        targets = targets[:limit]
    got, failed = 0, []
    for ticker, day, after_close, when in targets:
        started = time.time()
        try:
            found = implied_move(ticker, day, after_close)
        except Exception as exc:
            found = None
            print(f"  {ticker} 못 받음 — {type(exc).__name__}: {str(exc)[:80]}", flush=True)
        if found:
            moves[ticker] = {"at": today.isoformat(), "earn": day.isoformat(),
                             "when": when, **found}             # 재무 파일에 적힌 그대로(모르면 빈칸 — 「장 전」으로 채우지 않음)
            got += 1
            print(f"  {ticker} 발표 {day} · 만기 {found['expiry']} · 주가 {found['spot']} · 행사가 {found['strike']} · "
                  f"±{found['move']}% · {time.time() - started:.1f}초", flush=True)
        else:
            failed.append(ticker)
    summary = {"targets": len(targets), "got": got, "failed": failed}
    print(f"발표 14일 안 {len(targets)}종목 · 받음 {got} · 못 받음 {len(failed)} {failed[:20]}", flush=True)
    if not dry:
        OUT.write_text(json.dumps({"version": 1, "updated": today.isoformat(), "moves": moves},
                                  ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def load() -> dict:
    try:
        return (json.loads(OUT.read_text(encoding="utf-8")) or {}).get("moves") or {}
    except Exception:
        return {}


_FUND_CACHE: dict = {}


def reactions_for(ticker: str) -> dict:
    """재무 파일의 지난 실적 「다음 날 주가」(earn.react) — 파일이 바뀌지 않았으면 다시 안 읽는다."""
    try:
        stamp = FUND.stat().st_mtime
        if _FUND_CACHE.get("stamp") != stamp:
            _FUND_CACHE.update(stamp=stamp, stocks=(json.loads(FUND.read_text(encoding="utf-8")) or {}).get("stocks") or {})
        info = (_FUND_CACHE.get("stocks") or {}).get(str(ticker or "").upper()) or {}
        return dict(((info.get("earn") or {}).get("react") or {}))
    except Exception:
        return {}


def move_for(ticker: str, moves: dict | None = None, today: date | None = None) -> dict | None:
    """그 종목의 다가오는 실적 예보 — 발표일이 지났거나 5일 넘게 묵은 값이면 None."""
    entry = (moves if moves is not None else load()).get(str(ticker or "").upper())
    if not entry:
        return None
    today = today or _today()
    try:
        earn, at = date.fromisoformat(entry["earn"]), date.fromisoformat(entry["at"])
    except (KeyError, ValueError):
        return None
    if earn < today or (today - at).days > 5:
        return None
    return entry


CSS = (
    "<style>"
    ".j12im-box{background:#0d2340;border:1px solid #1f3a5f;border-radius:12px;padding:.55rem .7rem;margin:.35rem 0 .45rem;}"
    ".j12im-title{font-weight:900;font-size:.9rem;color:#e8f0fb;}"
    ".j12im-sub{color:#8fa6c4;font-size:.72rem;}"
    ".j12im-track{position:relative;height:2.4rem;margin:.35rem .4rem 0;}"
    ".j12im-band{position:absolute;top:.85rem;height:.75rem;border-radius:5px;background:rgba(76,195,255,.28);border:1px solid #4cc3ff;}"
    ".j12im-mid{position:absolute;top:.6rem;width:2px;height:1.25rem;background:#e8f0fb;}"
    ".j12im-lb{position:absolute;top:0;transform:translateX(-50%);font-size:.7rem;color:#4cc3ff;white-space:nowrap;}"
    ".j12im-dot{position:absolute;top:.97rem;width:.5rem;height:.5rem;border-radius:50%;transform:translateX(-50%);}"
    ".j12im-cap{position:absolute;top:1.75rem;transform:translateX(-50%);font-size:.66rem;color:#8fa6c4;white-space:nowrap;}"
    ".j12im-more summary{cursor:pointer;color:#4cc3ff;font-size:.76rem;margin-top:.3rem;}"
    "</style>"
)


def html(entry: dict | None, reactions: dict | None = None) -> str:
    """세부사항 덩이 — ±예상 띠 · 지난 실적 다음 날 실제 움직임 점. entry 가 없으면 빈 글."""
    if not entry:
        return ""
    move = float(entry["move"])
    reacts = [float(v) for v in (reactions or {}).values() if isinstance(v, (int, float))][-4:]
    span = max([move * 1.6] + [abs(v) * 1.15 for v in reacts] + [5.0])

    def at(value):
        return 50.0 + float(value) / span * 50.0

    dots = "".join(
        f"<span class='j12im-dot' style='left:{at(v):.1f}%;background:{'#3ddc97' if v > 0 else '#ff6b6b'}'"
        f" title='지난 실적 다음 날 {v:+.1f}%'></span>" for v in reacts)
    try:
        when = date.fromisoformat(entry["earn"])
        earn_text = f"{when.month}월 {when.day}일 {entry.get('when') or ''}".strip()
    except Exception:
        earn_text = str(entry.get("earn") or "")
    beyond = sum(1 for v in reacts if abs(v) > move)
    react_line = (f" · 지난 {len(reacts)}번 중 {beyond}번은 이 폭보다 크게 움직였음" if reacts else "")
    return (
        "<div class='j12im-box'><div class='j12im-title'>🌦 실적 날 흔들림 예보 "
        f"<span class='j12im-sub'>{earn_text} 발표 · 옵션이 매긴 크기</span></div>"
        "<div class='j12im-track'>"
        f"<div class='j12im-band' style='left:{at(-move):.1f}%;width:{at(move) - at(-move):.1f}%'></div>"
        "<div class='j12im-mid' style='left:50%'></div>"
        f"<span class='j12im-lb' style='left:{at(-move):.1f}%'>−{move:.1f}%</span>"
        f"<span class='j12im-lb' style='left:{at(move):.1f}%'>+{move:.1f}%</span>"
        f"{dots}<span class='j12im-cap' style='left:50%'>지금 값</span></div>"
        f"<div class='j12im-sub' style='margin-top:.15rem'>위아래 어느 쪽인지는 모릅니다 · 크기만{react_line}</div>"
        "<details class='j12im-more'><summary>어떻게 셌나</summary><div class='j12im-sub'>"
        f"발표를 품는 가장 가까운 옵션 만기({entry.get('expiry')}) · 행사가 {entry.get('strike')} 콜 + 풋 값 "
        f"{entry.get('straddle')} ÷ 주가 {entry.get('spot')} · {entry.get('at')} 장 마감 뒤 깃허브가 모음 · "
        "점 = 지난 실적 다음 날 실제로 움직인 크기(초록 오름 · 빨강 내림) · 보여 주기만(점수 · 판정 안 바꿈)"
        "</div></details></div>")


if __name__ == "__main__":
    if sys.argv[1:2] == ["collect"]:
        dry = bool(os.environ.get("J12_DRY"))
        result = collect(dry=dry, limit=8 if dry else None)
        sys.exit(0 if (result["got"] or not result["targets"]) else 1)
    print("쓰는 법: python jarvis12_options.py collect")
