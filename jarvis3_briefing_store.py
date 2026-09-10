"""자비스3 종목 브리핑의 사용자 종목 설정 저장소.

기존 report·거래 테이블과 분리된 작은 설정 테이블만 쓴다.
"""

from __future__ import annotations

import threading
from datetime import datetime

import db_runtime
from database import DB_PATH


# 반환 키나 함수가 바뀌면 이 숫자를 올리고 페이지의 요구 판 숫자도 같이 올린다(규칙 11).
# 안 올리면 온라인에서 옛 모듈이 프로세스에 남아 새 함수(add_selected 등)를 못 찾는다.
MODULE_REVISION = 2026091010

SELECTED_SLOTS = 6
# 기본 4종목을 실제 줄로 옮겨 적으면서 자리를 8에서 12로 늘렸다. 그러지 않으면
# 기본 넷이 자리를 먹어 상하님이 넣으실 자리가 절반으로 준다(2026-08-26).
EXTRA_LIMIT = 12

# 처음 화면에 늘 보이던 네 종목. 예전에는 화면이 자리만 만들어 보여 줬고 저장고에는
# 없어서 ×로 지울 수가 없었다(상하님 — "RGTI는 x가 왜 없냐").
DEFAULT_EXTRAS = (
    ("AAPL", "애플"), ("META", "메타 플랫폼스"),
    ("AVGO", "브로드컴"), ("RGTI", "리게티 컴퓨팅"),
)
_SEED_GROUP = "extra_seed"
_SEED_GROUP_SELECTED = "selected_seed"
# 2026-08-27 상하님 지시로 둘을 더했다 — "사용자 선정 종목은 SKHY, SPCX
# 2개 더 넣으면 되겠네." 태블릿에서 3칸 2줄로 놓으면 여섯 자리가 된다.
DEFAULT_SELECTED = (("NVDA", "NVIDIA"), ("TSLA", "Tesla"),
                    ("PLTR", "Palantir"), ("AMD", "AMD"),
                    ("SKHY", "SK하이닉스"), ("SPCX", "스페이스X"))
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


def ensure_default_selected() -> None:
    """기본 선정 6종목을 **티커마다 한 번씩** 넣는다. 그래야 ×로 지울 수 있다.

    2026-09-10 상하님 지적 — "사용자 선정종목이 삭제 추가가 안 된다."

    **왜 안 됐나** — 예전 `selected_stocks()` 는 **읽을 때마다** 빈 자리를
    `DEFAULT_SELECTED` 로 도로 채웠다. 그래서 지우자마자 그 자리에 기본 종목이
    다시 앉았고, 화면에서는 아무 일도 안 일어난 것처럼 보였다.

    이제 추가 검색 종목(`ensure_default_extras`)과 **같은 방식**이다 — 티커마다
    표식을 남기고, 표식이 있는 종목은 다시 넣지 않는다. 지우신 자리는 빈 채로
    남고 `add_selected` 가 그 자리를 다시 채운다.
    """
    ensure_tables()
    conn = _connection()
    try:
        marks = {
            row["ticker"]
            for row in conn.execute(
                "SELECT ticker FROM jarvis3_briefing_stocks WHERE group_name=?",
                (_SEED_GROUP_SELECTED,),
            ).fetchall()
        }
        rows = conn.execute(
            "SELECT ticker,position FROM jarvis3_briefing_stocks WHERE group_name='selected'"
        ).fetchall()
        have = {row["ticker"] for row in rows}
        taken = {int(row["position"]) for row in rows}
        now = datetime.now().isoformat(timespec="seconds")
        changed = False
        for ticker, name in DEFAULT_SELECTED:
            if ticker in marks:
                continue
            if ticker not in have:
                free = [s for s in range(1, SELECTED_SLOTS + 1) if s not in taken]
                if free:
                    taken.add(free[0])
                    conn.execute(
                        "INSERT INTO jarvis3_briefing_stocks "
                        "(group_name,position,ticker,stock_name,created_at,updated_at) "
                        "VALUES ('selected',?,?,?,?,?)", (free[0], ticker, name, now, now))
            conn.execute(
                "INSERT INTO jarvis3_briefing_stocks "
                "(group_name,position,ticker,stock_name,created_at,updated_at) "
                "VALUES (?,?,?,'기본 선정 종목 옮겨 적음',?,?)",
                (_SEED_GROUP_SELECTED, len(marks) + 1, ticker, now, now))
            marks.add(ticker)
            changed = True
        if changed:
            conn.commit()
    finally:
        conn.close()


def selected_stocks() -> list[dict]:
    """자리 번호 순으로 돌려준다. **빈 자리를 기본값으로 도로 채우지 않는다.**

    도로 채우면 상하님이 지우신 종목이 곧바로 되살아난다(2026-09-10).
    처음 한 번 넣는 일은 `ensure_default_selected` 가 맡는다.
    """
    ensure_default_selected()
    rows = {row["position"]: row for row in _list("selected")}
    return [rows[position] for position in range(1, SELECTED_SLOTS + 1) if position in rows]


def ensure_default_extras() -> None:
    """기본 4종목을 **티커마다 한 번씩** 실제 줄로 옮겨 적는다. 그래야 ×로 지울 수 있다.

    2026-09-10 상하님 지적 — "추가 검색 종목에서 RGTI 종목은 삭제 누르는
    동그라미 × 가 없다."

    **왜 RGTI만 없었나** — 예전에는 표식이 **하나**였다. 한 번 옮겨 적으면
    `extra_seed` 줄을 하나 남기고, 다음부터는 그 줄만 보고 곧장 돌아섰다.
    그런데 RGTI는 그 표식이 찍힌 **뒤에** 기본 목록에 들어왔다. 그래서 RGTI는
    저장고에 줄이 없는 채로 화면의 하드코딩 자리(-4번)로만 떴고, 화면은
    `position > 0` 인 것만 지울 수 있게 되어 있어 ×가 안 붙었다.

    이제 표식을 **티커마다** 남긴다. 표식이 없는 기본 종목만 옮겨 적으므로
    나중에 기본 목록에 종목을 더해도 그 종목은 제대로 줄을 받는다.
    **지우신 것은 되살아나지 않는다** — 지워도 표식은 남기 때문이다.

    옛 표식(`ticker='-'`) 하나만 있는 저장고는, 지금 `extra`에 들어 있는
    티커를 '이미 옮겨 적은 것'으로 보고 표식을 나눠 적어 둔다. 그래야 그때
    옮겨 적힌 뒤 상하님이 지우신 종목이 다시 살아나지 않는다.
    """
    ensure_tables()
    conn = _connection()
    try:
        marks = {
            row["ticker"]
            for row in conn.execute(
                "SELECT ticker FROM jarvis3_briefing_stocks WHERE group_name=?",
                (_SEED_GROUP,),
            ).fetchall()
        }
        rows = conn.execute(
            "SELECT ticker,position FROM jarvis3_briefing_stocks WHERE group_name='extra'"
        ).fetchall()
        have = {row["ticker"] for row in rows}
        position = max((int(row["position"]) for row in rows), default=0)
        now = datetime.now().isoformat(timespec="seconds")

        def mark(ticker: str) -> None:
            conn.execute(
                "INSERT INTO jarvis3_briefing_stocks "
                "(group_name,position,ticker,stock_name,created_at,updated_at) "
                "VALUES (?,?,?,'기본 종목 옮겨 적음',?,?)",
                (_SEED_GROUP, len(marks) + 1, ticker, now, now))
            marks.add(ticker)

        # 옛 표식('-') 하나만 있던 저장고를 티커별 표식으로 옮겨 적는다.
        if "-" in marks:
            conn.execute(
                "DELETE FROM jarvis3_briefing_stocks WHERE group_name=? AND ticker='-'",
                (_SEED_GROUP,))
            marks.discard("-")
            for ticker, _name in DEFAULT_EXTRAS:
                if ticker in have and ticker not in marks:
                    mark(ticker)

        for ticker, name in DEFAULT_EXTRAS:
            if ticker in marks:
                continue
            if ticker not in have:
                position += 1
                conn.execute(
                    "INSERT INTO jarvis3_briefing_stocks "
                    "(group_name,position,ticker,stock_name,created_at,updated_at) "
                    "VALUES ('extra',?,?,?,?,?)", (position, ticker, name, now, now))
            mark(ticker)
        conn.commit()
    finally:
        conn.close()


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


def add_selected(ticker, name) -> None:
    """사용자 선정 종목에 **한 종목 더** 넣는다 (2026-09-10 상하님 지시).

    상하님 — "사용자 선정종목이 삭제 추가가 안 된다. 추가 검색종목처럼 되게 해줘."

    여태 이 무리는 `replace_selected` 로 **자리를 갈아 끼우는** 것만 됐다.
    자리가 여섯으로 고정이라 비어 있는 자리에 넣거나 빼는 길이 없었다.
    빈 자리 가운데 **가장 앞 번호**에 넣는다 — 화면이 번호 순으로 그리므로
    지운 자리가 그대로 다시 찬다.
    """
    ticker, name = _clean(ticker, name)
    ensure_tables()
    conn = _connection()
    try:
        rows = conn.execute(
            "SELECT ticker,position FROM jarvis3_briefing_stocks WHERE group_name='selected'"
        ).fetchall()
        if any(row["ticker"] == ticker for row in rows):
            raise ValueError("사용자 선정 종목에는 이미 등록되어 있습니다")
        taken = {int(row["position"]) for row in rows}
        free = [slot for slot in range(1, SELECTED_SLOTS + 1) if slot not in taken]
        if not free:
            raise ValueError(f"사용자 선정 종목은 최대 {SELECTED_SLOTS}개까지 등록할 수 있습니다")
        now = datetime.now().isoformat(timespec="seconds")
        conn.execute(
            "INSERT INTO jarvis3_briefing_stocks "
            "(group_name,position,ticker,stock_name,created_at,updated_at) "
            "VALUES ('selected',?,?,?,?,?)", (free[0], ticker, name, now, now))
        conn.commit()
    finally:
        conn.close()


def remove_selected(position: int) -> None:
    """사용자 선정 종목 한 자리를 지운다 (2026-09-10 상하님 지시).

    **번호를 당기지 않는다** — 추가 검색 종목(`remove_extra`)과 다른 점이다.
    선정 종목은 자리 번호가 곧 그 자리라, 당기면 남은 종목이 옆으로 밀린다.
    빈 번호는 `add_selected` 가 다시 채운다.
    """
    ensure_tables()
    conn = _connection()
    try:
        cur = conn.execute(
            "DELETE FROM jarvis3_briefing_stocks WHERE group_name='selected' AND position=?",
            (int(position),))
        if not cur.rowcount:
            raise ValueError("삭제할 사용자 선정 종목을 찾지 못했습니다")
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
            raise ValueError(f"최대 {EXTRA_LIMIT}개까지 등록할 수 있습니다")
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
