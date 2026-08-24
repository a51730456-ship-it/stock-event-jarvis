"""자비스3 종목 브리핑의 사용자 종목 설정 저장소.

기존 report·거래 테이블과 분리된 작은 설정 테이블만 쓴다.
"""

from __future__ import annotations

import threading
from datetime import datetime

import db_runtime
from database import DB_PATH


SELECTED_SLOTS = 4
EXTRA_LIMIT = 8
DEFAULT_SELECTED = (("NVDA", "NVIDIA"), ("TSLA", "Tesla"),
                    ("PLTR", "Palantir"), ("AMD", "AMD"))
_LOCK = threading.Lock()
_READY = False


def _connection():
    return db_runtime.connect(DB_PATH)


def ensure_tables() -> None:
    global _READY
    if _READY:
        return
    with _LOCK:
        if _READY:
            return
        conn = _connection()
        try:
            conn.execute("""CREATE TABLE IF NOT EXISTS jarvis3_briefing_stocks (
                group_name TEXT NOT NULL, position INTEGER NOT NULL, ticker TEXT NOT NULL,
                stock_name TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY (group_name, position), UNIQUE (group_name, ticker))""")
            conn.commit()
            _READY = True
        finally:
            conn.close()


def _clean(ticker, name):
    ticker = str(ticker or "").strip().upper()
    if not ticker or len(ticker) > 16 or not all(ch.isalnum() or ch in "-_." for ch in ticker):
        raise ValueError("올바른 미국 티커를 선택하세요")
    return ticker, (str(name or "").strip() or ticker)[:100]


def _list(group: str) -> list[dict]:
    ensure_tables()
    conn = _connection()
    try:
        return [{"position": int(row["position"]), "ticker": row["ticker"], "name": row["stock_name"]}
                for row in conn.execute("SELECT position,ticker,stock_name FROM jarvis3_briefing_stocks WHERE group_name=? ORDER BY position", (group,)).fetchall()]
    finally:
        conn.close()


def selected_stocks() -> list[dict]:
    rows = {row["position"]: row for row in _list("selected")}
    for position, (ticker, name) in enumerate(DEFAULT_SELECTED, 1):
        if position not in rows:
            replace_selected(position, ticker, name)
    rows = {row["position"]: row for row in _list("selected")}
    return [rows[position] for position in range(1, SELECTED_SLOTS + 1)]


def extra_stocks() -> list[dict]:
    return _list("extra")


def all_stocks() -> dict:
    return {"selected": selected_stocks(), "extra": extra_stocks()}


def replace_selected(position: int, ticker, name) -> None:
    if position not in range(1, SELECTED_SLOTS + 1):
        raise ValueError("사용자 선정 슬롯 번호가 올바르지 않습니다")
    ticker, name = _clean(ticker, name)
    ensure_tables()
    now = datetime.now().isoformat(timespec="seconds")
    conn = _connection()
    try:
        duplicate = conn.execute("SELECT 1 FROM jarvis3_briefing_stocks WHERE group_name='selected' AND ticker=? AND position<>?", (ticker, position)).fetchone()
        if duplicate:
            raise ValueError("사용자 선정 종목에는 이미 등록되어 있습니다")
        # 일부 libSQL/Turso 연결은 SQLite의 ON CONFLICT 절에서 간헐적으로 실패했다.
        # 설정 저장은 드문 작업이므로 명시적인 UPDATE/INSERT가 더 안전하다.
        exists = conn.execute(
            "SELECT 1 FROM jarvis3_briefing_stocks WHERE group_name='selected' AND position=?",
            (position,),
        ).fetchone()
        if exists:
            conn.execute(
                "UPDATE jarvis3_briefing_stocks SET ticker=?,stock_name=?,updated_at=? "
                "WHERE group_name='selected' AND position=?",
                (ticker, name, now, position),
            )
        else:
            conn.execute(
                "INSERT INTO jarvis3_briefing_stocks "
                "(group_name,position,ticker,stock_name,created_at,updated_at) "
                "VALUES ('selected',?,?,?,?,?)",
                (position, ticker, name, now, now),
            )
        conn.commit()
    finally:
        conn.close()


def add_extra(ticker, name) -> None:
    ticker, name = _clean(ticker, name)
    ensure_tables()
    conn = _connection()
    try:
        count = conn.execute("SELECT COUNT(*) FROM jarvis3_briefing_stocks WHERE group_name='extra'").fetchone()[0]
        if count >= EXTRA_LIMIT:
            raise ValueError("최대 8개까지 등록할 수 있습니다")
        if conn.execute("SELECT 1 FROM jarvis3_briefing_stocks WHERE group_name='extra' AND ticker=?", (ticker,)).fetchone():
            raise ValueError("추가 검색 종목에 이미 등록되어 있습니다")
        now = datetime.now().isoformat(timespec="seconds")
        conn.execute("INSERT INTO jarvis3_briefing_stocks (group_name,position,ticker,stock_name,created_at,updated_at) VALUES ('extra',?,?,?,?,?)", (count + 1, ticker, name, now, now))
        conn.commit()
    finally:
        conn.close()


def remove_extra(position: int) -> None:
    ensure_tables()
    conn = _connection()
    try:
        cur = conn.execute("DELETE FROM jarvis3_briefing_stocks WHERE group_name='extra' AND position=?", (int(position),))
        if not cur.rowcount:
            raise ValueError("삭제할 추가 검색 종목을 찾지 못했습니다")
        conn.execute("UPDATE jarvis3_briefing_stocks SET position=position-1 WHERE group_name='extra' AND position>?", (int(position),))
        conn.commit()
    finally:
        conn.close()
