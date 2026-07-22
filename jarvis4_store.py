"""자비스4(한국 테마) 실제 매수 기록 저장소.

기존 reports/report_items/playbook/jarvis3_trades 테이블은 건드리지 않고
``jarvis4_trades``라는 독립 테이블만 생성한다. Turso 설정이 있으면 원격 DB,
없으면 기존 로컬 SQLite 파일에 연결된다(온라인·노트북 이원화는 사용자 결정).

금액 단위는 원(KRW)이며, 자비스3(USD)와 섞지 않는다.
"""

from __future__ import annotations

import json
import math
import threading
from datetime import date, datetime

import db_runtime
from database import DB_PATH

_SCHEMA_LOCK = threading.Lock()
_tables_ready = False

MINIMUM_SAMPLE = 30
TRADE_STYLES = {"단타", "스윙", "중장기"}


def _new_connection():
    return db_runtime.connect(DB_PATH)


def _valid_date(value, field_name: str) -> str:
    text = str(value or "").strip()
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValueError(f"{field_name}은 YYYY-MM-DD 형식이어야 합니다") from exc


def _positive_number(value, field_name: str, *, allow_none: bool = False) -> float | None:
    if value in (None, "") and allow_none:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field_name}은 0보다 큰 숫자여야 합니다")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name}은 0보다 큰 숫자여야 합니다") from exc
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{field_name}은 0보다 큰 숫자여야 합니다")
    return number


def _initialize_on(connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS jarvis4_trades (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            recorded_at          TEXT NOT NULL,
            updated_at           TEXT NOT NULL,
            code                 TEXT NOT NULL,
            stock_name           TEXT NOT NULL,
            theme_name           TEXT NOT NULL,
            buy_date             TEXT NOT NULL,
            buy_price            REAL NOT NULL,
            quantity             REAL,
            trade_style          TEXT NOT NULL,
            entry_setup          TEXT,
            recommendation_state TEXT,
            market_regime        TEXT,
            market_score         REAL,
            theme_score          REAL,
            stock_score          REAL,
            flow_score           REAL,
            flow_net5_amount     REAL,
            entry_plan_json      TEXT,
            snapshot_json        TEXT,
            memo                 TEXT,
            status               TEXT NOT NULL DEFAULT '보유',
            sell_date            TEXT,
            sell_price           REAL,
            result_pct           REAL
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_jarvis4_trades_buy_date ON jarvis4_trades(buy_date DESC)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_jarvis4_trades_code ON jarvis4_trades(code, buy_date DESC)"
    )
    connection.commit()


def ensure_tables(connection=None) -> None:
    """자비스4 독립 테이블을 준비한다. 전달된 연결은 호출자가 닫는다."""
    global _tables_ready
    if connection is not None:
        _initialize_on(connection)
        return
    if _tables_ready:
        return
    with _SCHEMA_LOCK:
        if _tables_ready:
            return
        conn = _new_connection()
        try:
            _initialize_on(conn)
            _tables_ready = True
        finally:
            conn.close()


def save_trade(
    *,
    code: str,
    stock_name: str,
    theme_name: str,
    buy_date,
    buy_price,
    quantity=None,
    trade_style: str = "스윙",
    entry_setup: str | None = None,
    recommendation_state: str | None = None,
    market_regime: str | None = None,
    market_score=None,
    theme_score=None,
    stock_score=None,
    flow_score=None,
    flow_net5_amount=None,
    entry_plan: dict | None = None,
    snapshot: dict | None = None,
    memo: str | None = None,
    connection=None,
) -> int | None:
    code = str(code or "").strip()
    stock_name = str(stock_name or "").strip()
    theme_name = str(theme_name or "").strip()
    if not code or not stock_name or not theme_name:
        raise ValueError("종목코드·종목명·테마명은 필수입니다")
    buy_date_text = _valid_date(buy_date, "매수일")
    buy_price_number = _positive_number(buy_price, "매수가")
    quantity_number = _positive_number(quantity, "수량", allow_none=True)
    trade_style = str(trade_style or "").strip()
    if trade_style not in TRADE_STYLES:
        raise ValueError("매매유형은 단타·스윙·중장기 중 하나여야 합니다")

    def optional_score(value):
        if value is None:
            return None
        number = float(value)
        if not math.isfinite(number) or not 0 <= number <= 100:
            raise ValueError("점수는 0~100 범위여야 합니다")
        return number

    def optional_amount(value):
        if value is None:
            return None
        number = float(value)
        return number if math.isfinite(number) else None

    now = datetime.now().isoformat(timespec="seconds")
    params = (
        now, now, code, stock_name, theme_name, buy_date_text, buy_price_number,
        quantity_number, trade_style, str(entry_setup or "").strip() or None,
        str(recommendation_state or "").strip() or None,
        str(market_regime or "").strip() or None,
        optional_score(market_score), optional_score(theme_score), optional_score(stock_score),
        optional_score(flow_score), optional_amount(flow_net5_amount),
        json.dumps(entry_plan or {}, ensure_ascii=False, separators=(",", ":")),
        json.dumps(snapshot or {}, ensure_ascii=False, separators=(",", ":"), default=str),
        str(memo or "").strip() or None,
    )
    own_connection = connection is None
    conn = connection or _new_connection()
    try:
        ensure_tables(conn)
        cursor = conn.execute(
            """
            INSERT INTO jarvis4_trades (
                recorded_at, updated_at, code, stock_name, theme_name,
                buy_date, buy_price, quantity, trade_style, entry_setup,
                recommendation_state, market_regime, market_score, theme_score,
                stock_score, flow_score, flow_net5_amount, entry_plan_json,
                snapshot_json, memo, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '보유')
            """,
            params,
        )
        conn.commit()
        return getattr(cursor, "lastrowid", None)
    finally:
        if own_connection:
            conn.close()


def list_trades(*, status: str | None = None, limit: int = 200, connection=None) -> list[dict]:
    limit = max(1, min(int(limit), 1000))
    if status not in (None, "보유", "청산"):
        raise ValueError("상태 필터는 보유·청산만 지원합니다")
    own_connection = connection is None
    conn = connection or _new_connection()
    try:
        ensure_tables(conn)
        if status is None:
            rows = conn.execute(
                "SELECT * FROM jarvis4_trades ORDER BY buy_date DESC, id DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM jarvis4_trades WHERE status=? ORDER BY buy_date DESC, id DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        if own_connection:
            conn.close()


def close_trade(trade_id: int, *, sell_date, sell_price, connection=None) -> None:
    try:
        trade_id = int(trade_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("유효한 기록 ID가 필요합니다") from exc
    sell_date_text = _valid_date(sell_date, "매도일")
    sell_price_number = _positive_number(sell_price, "매도가")
    own_connection = connection is None
    conn = connection or _new_connection()
    try:
        ensure_tables(conn)
        row = conn.execute(
            "SELECT buy_date, buy_price, status FROM jarvis4_trades WHERE id=?", (trade_id,)
        ).fetchone()
        if row is None:
            raise ValueError("해당 매수 기록을 찾지 못했습니다")
        if row["status"] == "청산":
            raise ValueError("이미 청산된 기록입니다")
        if sell_date_text < row["buy_date"]:
            raise ValueError("매도일은 매수일보다 빠를 수 없습니다")
        result_pct = (sell_price_number / float(row["buy_price"]) - 1) * 100
        conn.execute(
            """
            UPDATE jarvis4_trades
            SET status='청산', sell_date=?, sell_price=?, result_pct=?, updated_at=?
            WHERE id=?
            """,
            (
                sell_date_text,
                sell_price_number,
                result_pct,
                datetime.now().isoformat(timespec="seconds"),
                trade_id,
            ),
        )
        conn.commit()
    finally:
        if own_connection:
            conn.close()


def trade_progress(connection=None) -> dict:
    """표본 진행 상황만 반환한다. 30건 미만에서 승률·기대값을 계산하지 않는다."""
    own_connection = connection is None
    conn = connection or _new_connection()
    try:
        ensure_tables(conn)
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total_count,
                SUM(CASE WHEN status='보유' THEN 1 ELSE 0 END) AS open_count,
                SUM(CASE WHEN status='청산' THEN 1 ELSE 0 END) AS closed_count
            FROM jarvis4_trades
            """
        ).fetchone()
        return {
            "total_count": int(row["total_count"] or 0),
            "open_count": int(row["open_count"] or 0),
            "closed_count": int(row["closed_count"] or 0),
            "minimum_sample": MINIMUM_SAMPLE,
        }
    finally:
        if own_connection:
            conn.close()
