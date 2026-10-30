"""자비스13 한국 관심종목 저장소 (2026-10-30 상하님 「자비스13 관심종목(5단계) — 다해라」).

미국 관심종목(jarvis3_briefing_store — 자비스3 과 같이 쓰는 얼린 파일)과 **섞이지 않게** 표를 따로 둔다.
표를 새로 만들 뿐 다른 기록은 건드리지 않는다(CLAUDE.md 2 — DB 삭제·초기화 금지).

넣을 때 그 순간의 값과 코스피를 같이 적는다 — 「넣은 날부터 성적」(코스피와 나란히)을 그 값으로 센다
(상하님 「다 넣어라」 · 자비스에 넣을 기능 ② · Motley Fool 이 추천일부터 S&P 500 과 견주는 방식).
target_price 는 텔레그램 알림(정한 값 도달)에 쓴다 — 값은 상하님이 정하신다.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import db_runtime
from database import DB_PATH

# 반환 키나 함수가 바뀌면 올리고 화면의 요구 번호도 같이 올린다(규칙 11).
MODULE_REVISION = 2026103001

LIMIT = 20                          # 미국 「추가 검색 종목」 한도와 같다
_SEOUL = ZoneInfo("Asia/Seoul")
_LOCK = threading.Lock()
_READY = False

# 목록을 서버 기억에도 둔다 — 온라인은 원격 DB 라 물을 때마다 0.2~0.3초가 든다(자비스12 저장고 실측).
# 넣기·빼기·값 정하기 뒤에는 바로 지운다. 다른 곳에서 바꿔도 늦어야 5분이면 새로 읽는다.
_TTL = 300.0
_MEMO: dict = {"at": 0.0, "value": None, "version": 0}
_MEMO_LOCK = threading.Lock()


def _forget() -> None:
    with _MEMO_LOCK:
        _MEMO.update({"at": 0.0, "value": None, "version": _MEMO["version"] + 1})


def _connection():
    return db_runtime.connect(DB_PATH)


def _now() -> str:
    return datetime.now(_SEOUL).isoformat(timespec="seconds")


def ensure_tables() -> None:
    global _READY
    if _READY:
        return
    with _LOCK:
        if _READY:
            return
        conn = _connection()
        try:
            conn.execute("""CREATE TABLE IF NOT EXISTS jarvis13_watch_stocks (
                code TEXT PRIMARY KEY, stock_name TEXT NOT NULL, position INTEGER NOT NULL,
                added_at TEXT NOT NULL, added_price REAL, kospi_at_add REAL, target_price REAL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
            conn.commit()
            _forget()
            _READY = True
        finally:
            conn.close()


def clean_code(code) -> str:
    """한국 종목코드 — 6자(숫자, 요즘 새로 생긴 영문 섞인 코드도). 틀리면 ValueError."""
    code = str(code or "").strip().upper()
    if len(code) != 6 or not code.isalnum():
        raise ValueError("올바른 한국 종목코드(6자)를 고르세요")
    return code


def _row(row) -> dict:
    def num(key):
        value = row[key]
        return None if value is None else float(value)

    return {"code": row["code"], "name": row["stock_name"], "position": int(row["position"]),
            "added_at": row["added_at"], "added_price": num("added_price"),
            "kospi_at_add": num("kospi_at_add"), "target_price": num("target_price")}


def list_stocks() -> list[dict]:
    """넣은 차례대로. 서버 기억(5분)을 먼저 본다."""
    ensure_tables()
    with _MEMO_LOCK:
        if _MEMO["value"] is not None and time.monotonic() - _MEMO["at"] < _TTL:
            return [dict(item) for item in _MEMO["value"]]
        version = _MEMO["version"]
    conn = _connection()
    try:
        rows = [_row(row) for row in conn.execute(
            "SELECT code,stock_name,position,added_at,added_price,kospi_at_add,target_price "
            "FROM jarvis13_watch_stocks ORDER BY position, added_at").fetchall()]
    finally:
        conn.close()
    with _MEMO_LOCK:
        if _MEMO["version"] == version:            # 읽는 사이 누가 바꿨으면 기억에 두지 않는다
            _MEMO.update({"at": time.monotonic(), "value": [dict(item) for item in rows]})
    return rows


def has(code) -> bool:
    try:
        code = clean_code(code)
    except ValueError:
        return False
    return any(item["code"] == code for item in list_stocks())


def add(code, name, *, price=None, kospi=None) -> dict:
    """넣는다 — 이미 있거나 자리가 차면 ValueError(넣지 않는다). 넣은 그 순간의 값·코스피를 같이 적는다."""
    code = clean_code(code)
    name = (str(name or "").strip() or code)[:100]
    ensure_tables()
    conn = _connection()
    try:
        rows = conn.execute("SELECT code, position FROM jarvis13_watch_stocks").fetchall()
        if any(row["code"] == code for row in rows):
            raise ValueError(f"{name} 은(는) 이미 관심종목에 있습니다.")
        if len(rows) >= LIMIT:
            raise ValueError(f"관심종목은 {LIMIT}개까지입니다. 하나를 빼고 넣으십시오.")
        position = max((int(row["position"]) for row in rows), default=0) + 1
        now = _now()
        conn.execute(
            "INSERT INTO jarvis13_watch_stocks (code,stock_name,position,added_at,added_price,kospi_at_add,"
            "target_price,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (code, name, position, now, _num(price), _num(kospi), None, now, now))
        conn.commit()
    finally:
        conn.close()
    _forget()
    return {"code": code, "name": name, "position": position, "added_at": now,
            "added_price": _num(price), "kospi_at_add": _num(kospi), "target_price": None}


def remove(code) -> bool:
    """뺀다 — 없으면 False."""
    code = clean_code(code)
    ensure_tables()
    conn = _connection()
    try:
        cur = conn.execute("DELETE FROM jarvis13_watch_stocks WHERE code=?", (code,))
        conn.commit()
        removed = bool(getattr(cur, "rowcount", 1))
    finally:
        conn.close()
    _forget()
    return removed


def set_target(code, price) -> None:
    """알림에 쓸 「정한 값」 — None 이면 지운다."""
    code = clean_code(code)
    ensure_tables()
    conn = _connection()
    try:
        conn.execute("UPDATE jarvis13_watch_stocks SET target_price=?, updated_at=? WHERE code=?",
                     (_num(price), _now(), code))
        conn.commit()
    finally:
        conn.close()
    _forget()


def _num(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if value == value and value > 0 else None
