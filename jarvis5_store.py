"""자비스5 테마 선행감지 전용 SQLite 저장소.

기존 보고서 DB와 성과검증 테이블을 건드리지 않는다. 수집 원자료, 실험 신호,
신호 이후 결과를 별도 파일에 저장해 규칙을 바꾼 뒤에도 다시 검증할 수 있게 한다.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path


DB_PATH = Path(__file__).parent / "db" / "jarvis5_theme_lead.sqlite3"
SCHEMA_VERSION = 4


@contextmanager
def connection(db_path: str | Path | None = None):
    path = Path(db_path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=15000")
    try:
        yield conn
    finally:
        conn.close()


def ensure_schema(db_path: str | Path | None = None) -> None:
    with connection(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS collection_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                captured_at TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                kind TEXT NOT NULL CHECK(kind IN ('full', 'candidate')),
                status TEXT NOT NULL CHECK(status IN ('ok', 'partial', 'failed')),
                theme_count INTEGER NOT NULL DEFAULT 0,
                stock_row_count INTEGER NOT NULL DEFAULT 0,
                elapsed_seconds REAL,
                interval_seconds REAL,
                parser_version INTEGER,
                error TEXT
            );

            CREATE TABLE IF NOT EXISTS theme_snapshots (
                run_id INTEGER NOT NULL,
                theme_no INTEGER NOT NULL,
                theme_name TEXT NOT NULL,
                change_pct REAL,
                median_change_pct REAL,
                relative_change_pct REAL,
                member_count INTEGER NOT NULL DEFAULT 0,
                advancers INTEGER NOT NULL DEFAULT 0,
                decliners INTEGER NOT NULL DEFAULT 0,
                unchanged INTEGER NOT NULL DEFAULT 0,
                active_count INTEGER NOT NULL DEFAULT 0,
                total_trading_value REAL,
                interval_trading_value REAL,
                weighted_interval_value REAL,
                activity_intensity REAL,
                baseline_ratio REAL,
                top_contributor_share REAL,
                stale_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (run_id, theme_no),
                FOREIGN KEY (run_id) REFERENCES collection_runs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS theme_stock_snapshots (
                run_id INTEGER NOT NULL,
                theme_no INTEGER NOT NULL,
                stock_code TEXT NOT NULL,
                stock_name TEXT NOT NULL,
                price REAL,
                change_pct REAL,
                volume REAL,
                trading_value REAL,
                previous_volume REAL,
                interval_trading_value REAL,
                theme_count INTEGER NOT NULL DEFAULT 1,
                contribution_weight REAL NOT NULL DEFAULT 1,
                parser_version INTEGER,
                PRIMARY KEY (run_id, theme_no, stock_code),
                FOREIGN KEY (run_id) REFERENCES collection_runs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS experiment_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                theme_no INTEGER NOT NULL,
                model TEXT NOT NULL,
                model_version INTEGER NOT NULL DEFAULT 1,
                score REAL NOT NULL,
                stage TEXT NOT NULL,
                reason TEXT NOT NULL,
                feature_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(run_id, theme_no, model),
                FOREIGN KEY (run_id) REFERENCES collection_runs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS signal_outcomes (
                signal_id INTEGER NOT NULL,
                horizon_minutes INTEGER NOT NULL,
                evaluated_run_id INTEGER NOT NULL,
                forward_return_pct REAL,
                relative_forward_return_pct REAL,
                success INTEGER,
                evaluated_at TEXT NOT NULL,
                PRIMARY KEY (signal_id, horizon_minutes),
                FOREIGN KEY (signal_id) REFERENCES experiment_signals(id) ON DELETE CASCADE,
                FOREIGN KEY (evaluated_run_id) REFERENCES collection_runs(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_j5_runs_date_time
                ON collection_runs(trade_date, captured_at);
            CREATE INDEX IF NOT EXISTS idx_j5_theme_history
                ON theme_snapshots(theme_no, run_id);
            CREATE INDEX IF NOT EXISTS idx_j5_stock_history
                ON theme_stock_snapshots(theme_no, stock_code, run_id);
            CREATE INDEX IF NOT EXISTS idx_j5_signal_pending
                ON experiment_signals(created_at, theme_no);
            """
        )
        run_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(collection_runs)").fetchall()
        }
        if "interval_seconds" not in run_columns:
            conn.execute("ALTER TABLE collection_runs ADD COLUMN interval_seconds REAL")
        theme_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(theme_snapshots)").fetchall()
        }
        if "activity_intensity" not in theme_columns:
            conn.execute("ALTER TABLE theme_snapshots ADD COLUMN activity_intensity REAL")
        signal_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(experiment_signals)").fetchall()
        }
        if "model_version" not in signal_columns:
            conn.execute(
                "ALTER TABLE experiment_signals ADD COLUMN model_version INTEGER NOT NULL DEFAULT 1"
            )
        conn.execute(
            "INSERT OR REPLACE INTO metadata(key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        conn.commit()


def _iso(value) -> str:
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    return str(value)


def save_collection(
    run: dict,
    themes: list[dict],
    stocks: list[dict],
    *,
    db_path: str | Path | None = None,
) -> int:
    """한 번의 수집을 단일 트랜잭션으로 저장하고 run id를 반환한다."""
    ensure_schema(db_path)
    captured_at = _iso(run["captured_at"])
    trade_date = str(run.get("trade_date") or captured_at[:10])
    with connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO collection_runs(
                captured_at, trade_date, kind, status, theme_count,
                stock_row_count, elapsed_seconds, interval_seconds, parser_version, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                captured_at,
                trade_date,
                run.get("kind", "full"),
                run.get("status", "ok"),
                int(run.get("theme_count") or len(themes)),
                int(run.get("stock_row_count") or len(stocks)),
                run.get("elapsed_seconds"),
                run.get("interval_seconds"),
                run.get("parser_version"),
                run.get("error"),
            ),
        )
        run_id = int(cursor.lastrowid)
        conn.executemany(
            """
            INSERT INTO theme_snapshots(
                run_id, theme_no, theme_name, change_pct, median_change_pct,
                relative_change_pct, member_count, advancers, decliners,
                unchanged, active_count, total_trading_value,
                interval_trading_value, weighted_interval_value, baseline_ratio,
                activity_intensity, top_contributor_share, stale_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id,
                    int(row["theme_no"]),
                    row["theme_name"],
                    row.get("change_pct"),
                    row.get("median_change_pct"),
                    row.get("relative_change_pct"),
                    int(row.get("member_count") or 0),
                    int(row.get("advancers") or 0),
                    int(row.get("decliners") or 0),
                    int(row.get("unchanged") or 0),
                    int(row.get("active_count") or 0),
                    row.get("total_trading_value"),
                    row.get("interval_trading_value"),
                    row.get("weighted_interval_value"),
                    row.get("baseline_ratio"),
                    row.get("activity_intensity"),
                    row.get("top_contributor_share"),
                    int(row.get("stale_count") or 0),
                )
                for row in themes
            ],
        )
        conn.executemany(
            """
            INSERT INTO theme_stock_snapshots(
                run_id, theme_no, stock_code, stock_name, price, change_pct,
                volume, trading_value, previous_volume, interval_trading_value,
                theme_count, contribution_weight, parser_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id,
                    int(row["theme_no"]),
                    row["stock_code"],
                    row["stock_name"],
                    row.get("price"),
                    row.get("change_pct"),
                    row.get("volume"),
                    row.get("trading_value"),
                    row.get("previous_volume"),
                    row.get("interval_trading_value"),
                    int(row.get("theme_count") or 1),
                    float(row.get("contribution_weight") or 1),
                    row.get("parser_version"),
                )
                for row in stocks
            ],
        )
        conn.commit()
        return run_id


def save_failed_run(run: dict, *, db_path: str | Path | None = None) -> int:
    failed = dict(run, status="failed")
    return save_collection(failed, [], [], db_path=db_path)


def save_signals(run_id: int, signals: list[dict], *, db_path=None) -> int:
    if not signals:
        return 0
    ensure_schema(db_path)
    with connection(db_path) as conn:
        before = conn.total_changes
        conn.executemany(
            """
            INSERT OR IGNORE INTO experiment_signals(
                run_id, theme_no, model, model_version, score, stage, reason,
                feature_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    int(run_id),
                    int(row["theme_no"]),
                    row["model"],
                    int(row.get("model_version") or 1),
                    float(row["score"]),
                    row["stage"],
                    row["reason"],
                    json.dumps(row.get("features") or {}, ensure_ascii=False, sort_keys=True),
                    _iso(row["created_at"]),
                )
                for row in signals
            ],
        )
        conn.commit()
        return conn.total_changes - before


def latest_run(*, kind: str | None = None, db_path=None) -> dict | None:
    ensure_schema(db_path)
    query = "SELECT * FROM collection_runs"
    params: tuple = ()
    if kind:
        query += " WHERE kind = ?"
        params = (kind,)
    query += " ORDER BY id DESC LIMIT 1"
    with connection(db_path) as conn:
        row = conn.execute(query, params).fetchone()
        return dict(row) if row else None


def latest_active_run(*, minimum_ready_themes: int = 20, db_path=None) -> dict | None:
    """구간 거래활동이 실제로 잡힌 마지막 수집을 돌려준다.

    장 마감 뒤나 마감 동시호가(15:20~15:30) 구간에는 직전 수집과 견줘 늘어난
    거래가 없어 구간 지표가 전부 0이 된다. 그 수집으로 순위를 매기면 266개 테마가
    모두 0점이 되고, 화면에는 뜻 없는 1위·2위가 남는다(2026-07-23 실측).
    그래서 화면은 '마지막으로 값이 살아 있던 수집'을 기준으로 보여준다.

    '살아 있다'의 기준은 활동 종목이 하나라도 있는 것이 아니라, 참여 종목이 3개
    이상인 테마가 충분히 많은 것이다. 마감 직전 15:35 수집은 전체 6,417행 중 22개만
    움직여 테마 순위가 여전히 무의미했다(같은 날 실측).
    """
    ensure_schema(db_path)
    with connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT r.*, SUM(CASE WHEN t.active_count >= 3 THEN 1 ELSE 0 END) AS ready_themes
            FROM collection_runs r
            JOIN theme_snapshots t ON t.run_id = r.id
            WHERE r.status != 'failed' AND r.kind = 'full'
            GROUP BY r.id
            HAVING ready_themes >= ?
            ORDER BY r.id DESC
            LIMIT 1
            """,
            (int(minimum_ready_themes),),
        ).fetchone()
        return dict(row) if row else None


def latest_theme_rows(*, limit: int = 20, run_id: int | None = None, db_path=None) -> list[dict]:
    ensure_schema(db_path)
    with connection(db_path) as conn:
        if run_id is not None:
            run = {"id": int(run_id)}
        else:
            run = conn.execute(
                "SELECT id FROM collection_runs WHERE status != 'failed' ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if not run:
            return []
        rows = conn.execute(
            """
            SELECT * FROM theme_snapshots
            WHERE run_id = ?
            ORDER BY COALESCE(activity_intensity, weighted_interval_value, interval_trading_value, 0) DESC
            LIMIT ?
            """,
            (run["id"], int(limit)),
        ).fetchall()
        return [dict(row) for row in rows]


def theme_activity_history(
    theme_nos,
    *,
    limit_runs: int = 12,
    db_path=None,
) -> dict[int, list[dict]]:
    """최신 거래일의 선택 테마별 분당 활동 추이를 오래된 순서로 반환한다."""
    numbers = sorted({int(value) for value in theme_nos if value is not None})
    if not numbers:
        return {}
    ensure_schema(db_path)
    placeholders = ",".join("?" for _ in numbers)
    with connection(db_path) as conn:
        latest = conn.execute(
            """
            SELECT trade_date FROM collection_runs
            WHERE status != 'failed' ORDER BY id DESC LIMIT 1
            """
        ).fetchone()
        if not latest:
            return {}
        recent_runs = conn.execute(
            """
            SELECT id FROM collection_runs
            WHERE trade_date = ? AND status != 'failed' AND interval_seconds IS NOT NULL
            ORDER BY id DESC LIMIT ?
            """,
            (latest["trade_date"], max(2, int(limit_runs))),
        ).fetchall()
        run_ids = [int(row["id"]) for row in recent_runs]
        if not run_ids:
            return {}
        run_placeholders = ",".join("?" for _ in run_ids)
        rows = conn.execute(
            f"""
            SELECT t.theme_no, r.captured_at, r.interval_seconds,
                   t.activity_intensity, t.baseline_ratio
            FROM theme_snapshots t
            JOIN collection_runs r ON r.id = t.run_id
            WHERE t.theme_no IN ({placeholders})
              AND t.run_id IN ({run_placeholders})
            ORDER BY r.captured_at ASC
            """,
            (*numbers, *run_ids),
        ).fetchall()
    history = {number: [] for number in numbers}
    for row in rows:
        history[int(row["theme_no"])].append(dict(row))
    return history


def recent_runs(*, limit: int = 20, db_path=None) -> list[dict]:
    ensure_schema(db_path)
    with connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM collection_runs ORDER BY id DESC LIMIT ?", (int(limit),)
        ).fetchall()
        return [dict(row) for row in rows]


def recent_signals(*, limit: int = 50, db_path=None) -> list[dict]:
    ensure_schema(db_path)
    with connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT s.*, t.theme_name, r.captured_at
            FROM experiment_signals s
            JOIN theme_snapshots t ON t.run_id = s.run_id AND t.theme_no = s.theme_no
            JOIN collection_runs r ON r.id = s.run_id
            WHERE r.interval_seconds IS NOT NULL
              AND s.feature_json LIKE '%"activity_intensity"%'
            ORDER BY s.id DESC LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
        return [dict(row) for row in rows]


def previous_stock_values(
    trade_date: str,
    *,
    before_run_id: int | None = None,
    db_path=None,
) -> dict[tuple[int, str], float]:
    """같은 거래일의 직전 정상 수집값을 ``(테마, 종목)`` 기준으로 반환한다."""
    ensure_schema(db_path)
    where = "trade_date = ? AND status != 'failed'"
    params: list = [str(trade_date)]
    if before_run_id is not None:
        where += " AND id < ?"
        params.append(int(before_run_id))
    with connection(db_path) as conn:
        run = conn.execute(
            f"SELECT id FROM collection_runs WHERE {where} ORDER BY id DESC LIMIT 1",
            tuple(params),
        ).fetchone()
        if not run:
            return {}
        rows = conn.execute(
            """
            SELECT theme_no, stock_code, trading_value
            FROM theme_stock_snapshots
            WHERE run_id = ? AND trading_value IS NOT NULL
            """,
            (run["id"],),
        ).fetchall()
        return {
            (int(row["theme_no"]), row["stock_code"]): float(row["trading_value"])
            for row in rows
        }


def previous_stock_snapshot(trade_date: str, *, db_path=None) -> dict | None:
    """같은 거래일 직전 수집의 시각과 누적 거래대금을 함께 반환한다."""
    ensure_schema(db_path)
    with connection(db_path) as conn:
        run = conn.execute(
            """
            SELECT id, captured_at FROM collection_runs
            WHERE trade_date = ? AND status != 'failed'
            ORDER BY id DESC LIMIT 1
            """,
            (str(trade_date),),
        ).fetchone()
        if not run:
            return None
        rows = conn.execute(
            """
            SELECT theme_no, stock_code, trading_value
            FROM theme_stock_snapshots
            WHERE run_id = ? AND trading_value IS NOT NULL
            """,
            (run["id"],),
        ).fetchall()
        return {
            "run_id": int(run["id"]),
            "captured_at": run["captured_at"],
            "values": {
                (int(row["theme_no"]), row["stock_code"]): float(row["trading_value"])
                for row in rows
            },
        }


def same_time_interval_baselines(
    captured_at,
    *,
    minute_tolerance: int = 8,
    lookback_days: int = 10,
    db_path=None,
) -> dict[int, float]:
    """과거 거래일의 같은 시각대 테마별 구간 거래대금 중앙값을 반환한다.

    첫날에는 값이 없으므로 빈 사전을 반환한다. 기준선이 없다는 사실을 숨기지 않고
    신호 단계에서 ``학습중``으로 다루기 위한 조회다.
    """
    ensure_schema(db_path)
    stamp = datetime.fromisoformat(_iso(captured_at))
    target_minute = stamp.hour * 60 + stamp.minute
    with connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT r.trade_date, r.captured_at, t.theme_no,
                   COALESCE(t.activity_intensity, t.weighted_interval_value) AS baseline_value
            FROM collection_runs r
            JOIN theme_snapshots t ON t.run_id = r.id
            WHERE r.status != 'failed'
              AND r.trade_date < ?
              AND r.interval_seconds IS NOT NULL
              AND COALESCE(t.activity_intensity, t.weighted_interval_value) IS NOT NULL
            ORDER BY r.trade_date DESC, r.id DESC
            """,
            (stamp.date().isoformat(),),
        ).fetchall()

    closest: dict[tuple[int, str], tuple[int, float]] = {}
    all_dates: list[str] = []
    for row in rows:
        try:
            row_stamp = datetime.fromisoformat(row["captured_at"])
        except (TypeError, ValueError):
            continue
        minute = row_stamp.hour * 60 + row_stamp.minute
        distance = abs(minute - target_minute)
        if distance > int(minute_tolerance):
            continue
        trade_date = row["trade_date"]
        if trade_date not in all_dates:
            if len(all_dates) >= int(lookback_days):
                continue
            all_dates.append(trade_date)
        key = (int(row["theme_no"]), trade_date)
        current = closest.get(key)
        if current is None or distance < current[0]:
            closest[key] = (distance, float(row["baseline_value"]))

    by_theme: dict[int, list[float]] = {}
    for (theme_no, _trade_date), (_distance, value) in closest.items():
        by_theme.setdefault(theme_no, []).append(value)

    baselines = {}
    for theme_no, values in by_theme.items():
        if len(values) < 3:
            continue
        ordered = sorted(values)
        middle = len(ordered) // 2
        baselines[theme_no] = (
            ordered[middle]
            if len(ordered) % 2
            else (ordered[middle - 1] + ordered[middle]) / 2
        )
    return baselines


def theme_rows_for_run(run_id: int, *, db_path=None) -> list[dict]:
    ensure_schema(db_path)
    with connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM theme_snapshots WHERE run_id = ? ORDER BY theme_no",
            (int(run_id),),
        ).fetchall()
        return [dict(row) for row in rows]


def latest_theme_stock_rows(theme_nos, *, run_id: int | None = None, db_path=None) -> dict[int, list[dict]]:
    """가장 최근 전체 수집에서 테마별 구성종목을 한 번에 가져온다.

    화면에서 테마를 펼쳤을 때 '왜 이 테마가 올라왔는지'를 종목 단위로 보여주기
    위한 것이다. 테마마다 따로 조회하면 왕복이 늘어나므로 한 번에 받는다.
    구간 거래대금이 큰 순서로 준다 — 그 순서가 곧 기여 순서다.
    """
    numbers = [int(no) for no in theme_nos if no is not None]
    if not numbers:
        return {}
    ensure_schema(db_path)
    placeholders = ",".join("?" for _ in numbers)
    with connection(db_path) as conn:
        if run_id is not None:
            run = {"id": int(run_id)}
        else:
            run = conn.execute(
                "SELECT id FROM collection_runs WHERE kind = 'full' AND status != 'failed' "
                "ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if run is None:
            return {}
        rows = conn.execute(
            f"""
            SELECT * FROM theme_stock_snapshots
            WHERE run_id = ? AND theme_no IN ({placeholders})
            ORDER BY theme_no,
                     COALESCE(interval_trading_value, 0) DESC,
                     COALESCE(trading_value, 0) DESC
            """,
            (int(run["id"]), *numbers),
        ).fetchall()
    grouped: dict[int, list[dict]] = {}
    for row in rows:
        grouped.setdefault(int(row["theme_no"]), []).append(dict(row))
    return grouped


def pending_signals(*, horizons=(5, 10, 20, 30), db_path=None) -> list[dict]:
    """아직 한 개 이상 목표시간 성과가 기록되지 않은 실험 신호를 반환한다."""
    ensure_schema(db_path)
    placeholders = ",".join("?" for _ in horizons)
    with connection(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT s.*, r.captured_at, t.median_change_pct AS signal_change_pct
            FROM experiment_signals s
            JOIN collection_runs r ON r.id = s.run_id
            JOIN theme_snapshots t ON t.run_id = s.run_id AND t.theme_no = s.theme_no
            WHERE r.interval_seconds IS NOT NULL
              AND s.feature_json LIKE '%"activity_intensity"%'
              AND EXISTS (
                SELECT 1 FROM (
                    SELECT ? AS horizon
                    {''.join(' UNION ALL SELECT ?' for _ in horizons[1:])}
                ) wanted
                WHERE NOT EXISTS (
                    SELECT 1 FROM signal_outcomes o
                    WHERE o.signal_id = s.id AND o.horizon_minutes = wanted.horizon
                )
            )
            ORDER BY s.id
            """,
            tuple(int(value) for value in horizons),
        ).fetchall()
        return [dict(row) for row in rows]


def save_outcomes(outcomes: list[dict], *, db_path=None) -> int:
    if not outcomes:
        return 0
    ensure_schema(db_path)
    with connection(db_path) as conn:
        before = conn.total_changes
        conn.executemany(
            """
            INSERT OR IGNORE INTO signal_outcomes(
                signal_id, horizon_minutes, evaluated_run_id,
                forward_return_pct, relative_forward_return_pct,
                success, evaluated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    int(row["signal_id"]),
                    int(row["horizon_minutes"]),
                    int(row["evaluated_run_id"]),
                    row.get("forward_return_pct"),
                    row.get("relative_forward_return_pct"),
                    row.get("success"),
                    _iso(row["evaluated_at"]),
                )
                for row in outcomes
            ],
        )
        conn.commit()
        return conn.total_changes - before


def outcome_summary(*, minimum_samples: int = 20, db_path=None) -> list[dict]:
    """모델·시간대별 표본수와 성과. 소표본은 적중률을 숨기도록 표시한다."""
    ensure_schema(db_path)
    with connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT s.model, s.model_version, o.horizon_minutes,
                   COUNT(*) AS sample_count,
                   AVG(o.forward_return_pct) AS avg_forward_return_pct,
                   AVG(o.relative_forward_return_pct) AS avg_relative_forward_return_pct,
                   AVG(CASE WHEN o.success IS NOT NULL THEN o.success END) AS hit_rate
            FROM signal_outcomes o
            JOIN experiment_signals s ON s.id = o.signal_id
            JOIN collection_runs r ON r.id = s.run_id
            WHERE r.interval_seconds IS NOT NULL
              AND s.feature_json LIKE '%"activity_intensity"%'
            GROUP BY s.model, s.model_version, o.horizon_minutes
            ORDER BY s.model, s.model_version, o.horizon_minutes
            """
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["enough_samples"] = int(item["sample_count"]) >= int(minimum_samples)
        if not item["enough_samples"]:
            item["hit_rate"] = None
        result.append(item)
    return result
