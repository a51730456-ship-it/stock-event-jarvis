"""자비스12 관심종목 「넣은 날부터 성적」 — S&P 500 과 나란히 (2026-10-31 상하님 「자비스12에도 넣어라」).

자비스13 관심종목 카드의 「지금까지 · 같은 사이 코스피 · 코스피보다」(jarvis13_watch)를 미국 쪽으로 옮긴 것이다.
카드 모양은 건드리지 않고, 카드 묶음 밑에 표 하나로 붙인다 — 카드가 다 그려진 뒤에 센다(CLAUDE.md 0-0 ①).

넣은 날 — 저장고(jarvis3_briefing_store · 얼린 파일이라 **읽기만** 한다)의 updated_at.
  자리를 갈아 끼우면(replace_selected) updated_at 만 바뀌고 created_at 은 옛 종목의 날이 남는다.
  자리 번호를 당길 때(remove_extra)는 updated_at 을 안 건드린다. 그래서 updated_at 이 「그 종목이 들어온 때」다.
기준 값 — 넣은 날 **전** 마지막 종가. 저장 시각은 서버 시계라 그 순간 미국장이 열려 있었는지 알 수 없다.
  한국 낮에 넣으면 날짜가 미국 날짜보다 하루 앞서는데, 「그 날 전 마지막 종가」면 두 경우 모두 넣을 때 보던 종가다.
같은 사이 S&P 500 — 같은 날 전 마지막 종가 → 지금.
보여 주기만 한다 — 점수·판정·목록에 안 쓴다. 못 잰 칸은 「—」로 둔다(0 으로 채우지 않는다).
"""

from __future__ import annotations

import html
import threading
import time
from datetime import date

import pandas as pd

MODULE_REVISION = 2026103101
BENCH = "^GSPC"
BENCH_NAME = "S&P 500"
_MEMO_SECONDS = 60.0
_MEMO: dict = {"at": 0.0, "version": None, "value": None}
_LOCK = threading.Lock()


def _day(text) -> date | None:
    try:
        return pd.Timestamp(str(text or "")[:10]).date()
    except Exception:
        return None


def added_map(store) -> dict[str, date]:
    """티커 → 넣은 날. 선정·추가 두 곳에 다 있으면 앞선 날. 못 읽으면 빈 것(화면은 표를 안 그린다)."""
    version = getattr(store, "_ALL_MEMO", {}).get("version")
    now = time.time()
    with _LOCK:
        if _MEMO["value"] is not None and _MEMO["version"] == version and now - _MEMO["at"] < _MEMO_SECONDS:
            return dict(_MEMO["value"])
    out: dict[str, date] = {}
    try:
        store.ensure_tables()
        conn = store._connection()
        try:
            rows = conn.execute(
                "SELECT ticker,updated_at FROM jarvis3_briefing_stocks WHERE group_name IN ('selected','extra')"
            ).fetchall()
        finally:
            conn.close()
    except Exception:
        return {}
    for ticker, stamp in ((row[0], row[1]) for row in rows):
        day = _day(stamp)
        key = str(ticker or "").strip().upper()
        if key and day and (key not in out or day < out[key]):
            out[key] = day
    with _LOCK:
        _MEMO.update({"at": now, "version": version, "value": dict(out)})
    return out


def _closes(frame) -> pd.Series | None:
    if frame is None or getattr(frame, "empty", True) or "Close" not in frame:
        return None
    closes = frame["Close"].dropna().astype(float)
    return None if closes.empty else closes


def _before(closes: pd.Series | None, day: date | None):
    """그 날 전 마지막 장의 (날짜, 종가). 자료가 그 날까지 안 닿으면 None."""
    if closes is None or day is None:
        return None
    found = None
    for stamp, value in closes.items():
        if pd.Timestamp(stamp).date() >= day:
            break
        found = (pd.Timestamp(stamp).date(), float(value))
    return found


def row(ticker: str, name: str, added: date | None, frame, bench, *, price_now=None) -> dict:
    """표 한 줄. 6개월 자료보다 앞서 넣은 종목은 기준 값을 못 찾아 「—」."""
    out = {"ticker": ticker, "name": name or ticker, "added": added, "base_day": None, "base": None,
           "now": None, "days": None, "since_pct": None, "bench_pct": None, "beat_pp": None}
    closes = _closes(frame)
    if closes is not None:
        out["now"] = float(price_now) if isinstance(price_now, (int, float)) and price_now > 0 else float(closes.iloc[-1])
        found = _before(closes, added)
        if found:
            out["base_day"], out["base"] = found
            out["days"] = int(sum(1 for stamp in closes.index if pd.Timestamp(stamp).date() > found[0]))
            out["since_pct"] = (out["now"] / out["base"] - 1.0) * 100.0
    b_closes = _closes(bench)
    b_found = _before(b_closes, added)
    if b_found and b_closes is not None:
        out["bench_pct"] = (float(b_closes.iloc[-1]) / b_found[1] - 1.0) * 100.0
    if out["since_pct"] is not None and out["bench_pct"] is not None:
        out["beat_pp"] = out["since_pct"] - out["bench_pct"]
    return out


def _tone(value) -> str:
    if value is None:
        return "j12ws-muted"
    return "j12ws-up" if value > 0 else ("j12ws-down" if value < 0 else "j12ws-muted")


def _pct(value, unit: str = "%") -> str:
    return "—" if value is None else f"{value:+.1f}{unit}"


def _usd(value) -> str:
    return "—" if value is None else f"{value:,.2f}"


def table_html(rows: list[dict]) -> str:
    if not rows:
        return ""
    body = []
    for item in rows:
        added = item.get("added")
        when = f"{added.month}월 {added.day}일" if added else "—"
        held = f"<small>{item['days']}거래일째</small>" if item.get("days") else ("<small>오늘 넣음</small>" if item.get("days") == 0 else "")
        if item.get("base") is None and item.get("now") is not None:
            held = "<small>6개월보다 앞 — 셈 안 함</small>"
        body.append(
            "<tr>"
            f"<td><b>{html.escape(str(item['ticker']))}</b><small>{html.escape(str(item['name']))}</small></td>"
            f"<td>{when}{held}</td>"
            f"<td>{_usd(item.get('base'))}</td>"
            f"<td>{_usd(item.get('now'))}</td>"
            f"<td class='{_tone(item.get('since_pct'))}'>{_pct(item.get('since_pct'))}</td>"
            f"<td class='{_tone(item.get('bench_pct'))}'>{_pct(item.get('bench_pct'))}</td>"
            f"<td class='{_tone(item.get('beat_pp'))}'><b>{_pct(item.get('beat_pp'), '%p')}</b></td>"
            "</tr>")
    head = ("<tr><th>종목</th><th>넣은 날</th><th>기준 값</th><th>지금</th><th>지금까지</th>"
            f"<th>같은 사이 {BENCH_NAME}</th><th>{BENCH_NAME}보다</th></tr>")
    note = (f"기준 값은 넣은 날 <b>전</b> 마지막 종가입니다 · 같은 사이 {BENCH_NAME}도 같은 날에서 잽니다 · "
            "보여 주기만 하고 점수·판정에는 안 씁니다")
    return (CSS + "<div class='j12ws-box'><div class='j12ws-title'>📈 넣은 날부터 성적</div>"
            f"<div class='j12ws-scroll'><table class='j12ws-table'><thead>{head}</thead>"
            f"<tbody>{''.join(body)}</tbody></table></div><div class='j12ws-note'>{note}</div></div>")


CSS = """<style>
.j12ws-box{margin:.4rem 0 1rem;padding:12px 14px;border:1px solid #bf925470;border-radius:15px;
  background:linear-gradient(180deg,#06294d,#031c38);color:#e7edf2;min-width:0}
.j12ws-title{font-size:1.15rem;font-weight:850;margin-bottom:8px;color:#ffc94f}
.j12ws-scroll{overflow-x:auto;max-width:100%}
.j12ws-table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums;font-size:.92rem}
.j12ws-table th{color:#9fb6c8;font-weight:600;font-size:.8rem;text-align:right;padding:4px 8px;white-space:nowrap;
  border-bottom:1px solid #94b5c52a}
.j12ws-table td{text-align:right;padding:6px 8px;white-space:nowrap;border-bottom:1px solid #94b5c51a}
.j12ws-table th:first-child,.j12ws-table td:first-child{text-align:left}
.j12ws-table small{display:block;color:#9fb6c8;font-size:.74rem}
.j12ws-up{color:#7de143}
.j12ws-down{color:#ff5c55}
.j12ws-muted{color:#9fb6c8}
.j12ws-note{margin-top:7px;color:#9fb6c8;font-size:.8rem;line-height:1.5}
</style>"""
