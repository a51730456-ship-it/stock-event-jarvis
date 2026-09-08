"""J7-only watchlist. Read J3 settings initially; never write J3 settings/reports."""
from __future__ import annotations

import json
import re
import threading

_LOCK = threading.Lock()
DEFAULTS = {
    "selected": [{"ticker": t, "name": n} for t, n in (
        ("NVDA", "NVIDIA"), ("TSLA", "Tesla"), ("PLTR", "Palantir"),
        ("AMD", "AMD"), ("SKHY", "SK하이닉스"), ("SPCX", "스페이스X"))],
    "extra": [{"ticker": t, "name": n} for t, n in (
        ("AAPL", "애플"), ("META", "메타 플랫폼스"), ("AVGO", "브로드컴"), ("RGTI", "리게티 컴퓨팅"))],
}


def connect():
    import db_runtime
    from database import DB_PATH
    return db_runtime.connect(DB_PATH)


def _exists(conn, name):
    return bool(conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())


def _read(conn):
    if _exists(conn, "jarvis7_settings"):
        row = conn.execute("SELECT payload FROM jarvis7_settings WHERE name='watchlist'").fetchone()
        if row:
            return json.loads(row[0])
    value = json.loads(json.dumps(DEFAULTS))
    if _exists(conn, "jarvis3_briefing_stocks"):
        rows = conn.execute("SELECT group_name,ticker,stock_name FROM jarvis3_briefing_stocks ORDER BY position").fetchall()
        for group in ("selected", "extra"):
            found = [{"ticker": r[1], "name": r[2]} for r in rows if r[0] == group]
            if found or (group == "extra" and any(r[0] == "extra_seed" for r in rows)):
                value[group] = found
    return value


def watchlist():
    conn = connect()
    try:
        return _read(conn)
    finally:
        conn.close()


def edit(action, ticker, name="", slot=0):
    ticker = str(ticker).strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-^=]{0,15}", ticker):
        raise ValueError("올바른 티커를 선택하세요.")
    item = {"ticker": ticker, "name": (str(name).strip() or ticker)[:100]}
    with _LOCK:
        conn = connect()
        try:
            value = _read(conn)
            if action == "add":
                if ticker not in {r["ticker"] for r in value["selected"] + value["extra"]}:
                    if len(value["extra"]) >= 24:
                        raise ValueError("추가 종목은 24개까지 저장할 수 있습니다.")
                    value["extra"].append(item)
            elif action == "remove":
                value["extra"] = [r for r in value["extra"] if r["ticker"] != ticker]
            elif action == "replace":
                if not 0 <= slot < len(value["selected"]):
                    raise ValueError("변경할 자리를 선택하세요.")
                if any(r["ticker"] == ticker for i, r in enumerate(value["selected"]) if i != slot):
                    raise ValueError("이미 선정된 종목입니다.")
                value["selected"][slot] = item
            else:
                raise ValueError("지원하지 않는 변경입니다.")
            conn.execute("CREATE TABLE IF NOT EXISTS jarvis7_settings (name TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            conn.execute("INSERT INTO jarvis7_settings(name,payload) VALUES ('watchlist',?) ON CONFLICT(name) DO UPDATE SET payload=excluded.payload", (json.dumps(value, ensure_ascii=False),))
            conn.commit()
        finally:
            conn.close()


def existing_trades():
    conn = connect()
    try:
        if not _exists(conn, "jarvis3_trades"):
            return []
        return [dict(r) for r in conn.execute("SELECT * FROM jarvis3_trades ORDER BY buy_date DESC,id DESC LIMIT 200").fetchall()]
    finally:
        conn.close()
