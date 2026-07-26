"""자비스6 기록 저장 — 눌러 둔 것과 다음 날 결과.

기존 DB(db/jarvis.sqlite3)를 건드리지 않는다. 전용 파일을 따로 쓴다.
연습 기록이 실사용 보고서와 섞이면 안 된다(CLAUDE.md 4항).
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

MODULE_REVISION = 2026072701
SCHEMA_VERSION = 1
DB_PATH = Path(__file__).parent / "db" / "jarvis6_close.sqlite3"
_SEOUL = ZoneInfo("Asia/Seoul")
_LOCK = threading.Lock()


@contextmanager
def connection(db_path=None):
    path = Path(db_path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def ensure_schema(db_path=None) -> None:
    with _LOCK, connection(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS picks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_date TEXT NOT NULL,
                decided_at TEXT NOT NULL,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                theme TEXT,
                action TEXT NOT NULL CHECK(action IN ('bought','skipped')),
                price REAL,
                day_open REAL, day_high REAL, day_low REAL,
                prev_close REAL, market_cap REAL,
                from_high_pct REAL, value_ratio REAL, upper_wick REAL,
                intraday_location REAL, days_since_high REAL,
                both_buy_days5 INTEGER, theme_advancers INTEGER,
                passed INTEGER, total INTEGER,
                reason TEXT, continuation TEXT, invalidation TEXT,
                warnings TEXT,
                warning_ignored INTEGER NOT NULL DEFAULT 0,
                snapshot TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(trade_date, code)
            );

            CREATE TABLE IF NOT EXISTS outcomes (
                pick_id INTEGER PRIMARY KEY,
                next_date TEXT,
                next_open REAL,
                price_0905 REAL,
                gross_pct REAL,
                net_pct REAL,
                after_hours_price REAL,
                after_hours_pct REAL,
                evaluated_at TEXT,
                FOREIGN KEY (pick_id) REFERENCES picks(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
            """
        )
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        conn.commit()


# 수수료·거래세·미끄러짐. 되돌아보기와 같은 값을 쓴다.
ROUND_TRIP_COST = 0.00015 * 2 + 0.0015 + 0.0005


def save_pick(row: dict, *, action: str = "bought", db_path=None) -> int:
    """클릭 한 번으로 그 순간을 통째로 저장한다. 아무것도 묻지 않는다."""
    ensure_schema(db_path)
    now = datetime.now(_SEOUL)
    evaluation = row.get("eval") or {}
    metrics = row.get("metrics") or {}
    stock = row.get("stock") or {}
    values = (
        now.date().isoformat(), now.isoformat(timespec="seconds"),
        str(row.get("code")), str(row.get("name")), row.get("theme"),
        action,
        stock.get("price"), stock.get("day_open"), stock.get("day_high"),
        stock.get("day_low"), metrics.get("prev_close"), evaluation.get("market_cap"),
        evaluation.get("from_high"), evaluation.get("value_ratio"),
        evaluation.get("upper_wick"), evaluation.get("location"),
        metrics.get("high52_days_ago"), evaluation.get("both_buy_days5"),
        (row.get("theme_row") or {}).get("advancers"),
        evaluation.get("passed"), evaluation.get("total"),
        (stock.get("reason") or "").strip() or None,
        (stock.get("continuation") or "").strip() or None,
        (stock.get("invalidation") or "").strip() or None,
        json.dumps(evaluation.get("warnings") or [], ensure_ascii=False),
        1 if evaluation.get("warnings") else 0,
        json.dumps({"stock": stock, "eval": evaluation}, ensure_ascii=False, default=str),
    )
    with _LOCK, connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO picks(
                trade_date, decided_at, code, name, theme, action,
                price, day_open, day_high, day_low, prev_close, market_cap,
                from_high_pct, value_ratio, upper_wick, intraday_location,
                days_since_high, both_buy_days5, theme_advancers,
                passed, total, reason, continuation, invalidation,
                warnings, warning_ignored, snapshot
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(trade_date, code) DO UPDATE SET
                action=excluded.action, decided_at=excluded.decided_at,
                reason=excluded.reason, continuation=excluded.continuation,
                invalidation=excluded.invalidation
            """,
            values,
        )
        conn.commit()
        return int(cursor.lastrowid or 0)


def update_notes(pick_id: int, *, reason=None, continuation=None,
                 invalidation=None, db_path=None) -> None:
    """이유는 나중에 써도 된다. 안 써도 된다."""
    ensure_schema(db_path)
    with _LOCK, connection(db_path) as conn:
        conn.execute(
            "UPDATE picks SET reason=COALESCE(?,reason), "
            "continuation=COALESCE(?,continuation), invalidation=COALESCE(?,invalidation) "
            "WHERE id=?",
            (reason, continuation, invalidation, int(pick_id)),
        )
        conn.commit()


def save_outcome(pick_id: int, *, next_date=None, next_open=None, price_0905=None,
                 entry=None, after_hours_price=None, db_path=None) -> None:
    """다음 날 결과. 사람이 입력하지 않고 자비스가 채운다."""
    ensure_schema(db_path)
    gross = net = after_pct = None
    if entry and next_open:
        gross = (float(next_open) / float(entry) - 1) * 100
        net = gross - ROUND_TRIP_COST * 100
    if entry and after_hours_price:
        after_pct = (float(after_hours_price) / float(entry) - 1) * 100
    with _LOCK, connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO outcomes(pick_id, next_date, next_open, price_0905,
                gross_pct, net_pct, after_hours_price, after_hours_pct, evaluated_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(pick_id) DO UPDATE SET
                next_date=excluded.next_date, next_open=excluded.next_open,
                price_0905=excluded.price_0905, gross_pct=excluded.gross_pct,
                net_pct=excluded.net_pct, after_hours_price=excluded.after_hours_price,
                after_hours_pct=excluded.after_hours_pct, evaluated_at=excluded.evaluated_at
            """,
            (int(pick_id), next_date, next_open, price_0905, gross, net,
             after_hours_price, after_pct,
             datetime.now(_SEOUL).isoformat(timespec="seconds")),
        )
        conn.commit()


def list_picks(*, limit: int = 200, trade_date=None, db_path=None) -> list[dict]:
    ensure_schema(db_path)
    with connection(db_path) as conn:
        if trade_date:
            rows = conn.execute(
                "SELECT p.*, o.next_open, o.net_pct, o.after_hours_pct "
                "FROM picks p LEFT JOIN outcomes o ON o.pick_id=p.id "
                "WHERE p.trade_date=? ORDER BY p.id DESC", (trade_date,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT p.*, o.next_open, o.net_pct, o.after_hours_pct "
                "FROM picks p LEFT JOIN outcomes o ON o.pick_id=p.id "
                "ORDER BY p.id DESC LIMIT ?", (int(limit),)
            ).fetchall()
        return [dict(row) for row in rows]


def pending_outcomes(db_path=None) -> list[dict]:
    """아직 결과가 안 붙은 기록. 다음 날 아침에 채운다."""
    ensure_schema(db_path)
    with connection(db_path) as conn:
        return [dict(r) for r in conn.execute(
            "SELECT p.* FROM picks p LEFT JOIN outcomes o ON o.pick_id=p.id "
            "WHERE o.pick_id IS NULL AND p.action='bought' ORDER BY p.trade_date"
        )]


MIN_SAMPLE = 30


def review(db_path=None) -> dict:
    """조건별 성적. 표본이 적으면 숫자를 숨긴다 — 10건 보고 승률을 말할 수 없다."""
    ensure_schema(db_path)
    with connection(db_path) as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT p.*, o.net_pct FROM picks p JOIN outcomes o ON o.pick_id=p.id "
            "WHERE o.net_pct IS NOT NULL AND p.action='bought'"
        )]

    def block(subset, label):
        if len(subset) < MIN_SAMPLE:
            return {"label": label, "n": len(subset), "enough": False}
        values = [r["net_pct"] for r in subset]
        wins = [v for v in values if v > 0]
        losses = [v for v in values if v <= 0]
        return {
            "label": label, "n": len(values), "enough": True,
            "win": len(wins) / len(values) * 100,
            "avg": sum(values) / len(values),
            "rr": ((sum(wins) / len(wins)) / abs(sum(losses) / len(losses)))
                  if wins and losses else None,
            "worst": min(values),
        }

    groups = [block(rows, "전체")]
    with_reason = [r for r in rows if (r.get("reason") or "").strip()]
    groups.append(block(with_reason, "이유를 적고 산 것"))
    groups.append(block([r for r in rows if not (r.get("reason") or "").strip()],
                        "이유 없이 산 것"))
    groups.append(block([r for r in rows if r.get("warning_ignored")],
                        "경고를 무시하고 산 것"))
    groups.append(block([r for r in rows if (r.get("from_high_pct") or -99) >= -3],
                        "전고점 3% 안쪽"))
    groups.append(block([r for r in rows if (r.get("from_high_pct") or 0) < -3],
                        "전고점 3% 밖"))
    return {"total": len(rows), "groups": groups, "minimum": MIN_SAMPLE}
