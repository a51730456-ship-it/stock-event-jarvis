"""자비스3 실제 매수 기록 저장소.

기존 reports/report_items/playbook 테이블은 건드리지 않고 ``jarvis3_trades``라는
독립 테이블만 생성한다. Turso 설정이 있으면 원격 DB, 없으면 기존 로컬 SQLite 파일에
연결된다.
"""

from __future__ import annotations

import json
import hashlib
import math
import threading
from datetime import date, datetime

import db_runtime
from database import DB_PATH

_SCHEMA_LOCK = threading.Lock()
_tables_ready = False


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
        CREATE TABLE IF NOT EXISTS jarvis3_trades (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            recorded_at          TEXT NOT NULL,
            updated_at           TEXT NOT NULL,
            ticker               TEXT NOT NULL,
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
            score_model_version  TEXT,
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
        "CREATE INDEX IF NOT EXISTS idx_jarvis3_trades_buy_date ON jarvis3_trades(buy_date DESC)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_jarvis3_trades_ticker ON jarvis3_trades(ticker, buy_date DESC)"
    )
    # 기존 사용자 거래행은 그대로 두고 새 swing 매수부터 버전만 선택 저장한다.
    trade_columns = {
        str(row["name"] if "name" in row.keys() else row[1])
        for row in connection.execute("PRAGMA table_info(jarvis3_trades)").fetchall()
    }
    if "score_model_version" not in trade_columns:
        connection.execute("ALTER TABLE jarvis3_trades ADD COLUMN score_model_version TEXT")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS jarvis3_swing_scan_runs (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_key                TEXT NOT NULL UNIQUE,
            as_of_date              TEXT NOT NULL,
            universe_mode           TEXT NOT NULL,
            requested_universe_mode TEXT,
            score_model_version     TEXT NOT NULL,
            config_hash             TEXT NOT NULL,
            config_json             TEXT NOT NULL,
            source_fingerprint      TEXT NOT NULL,
            market_status           TEXT,
            ixic_close              REAL,
            ixic_sma200             REAL,
            ixic_above_sma200       INTEGER,
            market_drawdown         REAL,
            distance_from_running_ath REAL,
            days_since_market_reclaim INTEGER,
            primary_count           INTEGER NOT NULL,
            watch_count             INTEGER NOT NULL,
            universe_count          INTEGER NOT NULL,
            data_count              INTEGER NOT NULL,
            checked_at              TEXT,
            created_at              TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS jarvis3_swing_candidates (
            id                              INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id                          INTEGER NOT NULL,
            scan_date                       TEXT NOT NULL,
            ticker                          TEXT NOT NULL,
            stock_name                      TEXT,
            asset_type                      TEXT,
            universe_mode                   TEXT NOT NULL,
            market_status                   TEXT,
            ixic_close                      REAL,
            ixic_sma200                     REAL,
            ixic_above_sma200               INTEGER,
            market_drawdown                 REAL,
            distance_from_running_ath       REAL,
            days_since_market_reclaim       INTEGER,
            rs60_raw                        REAL,
            rs60_percentile                 REAL,
            rs60_valid                      INTEGER NOT NULL DEFAULT 0,
            rs60_reason                     TEXT,
            rs60_score                      REAL NOT NULL,
            rs120_raw                       REAL,
            rs120_percentile                REAL,
            rs120_valid                     INTEGER NOT NULL DEFAULT 0,
            rs120_reason                    TEXT,
            rs120_score                     REAL NOT NULL,
            rs_rank_status                  TEXT,
            rs_core_status                  TEXT,
            breakout_date                   TEXT,
            breakout_close                  REAL,
            previous_252_high_close         REAL,
            breakout_pct_above_prior_high   REAL,
            breakout_reason                 TEXT,
            anchor_date                     TEXT,
            anchor_close                    REAL,
            days_since_anchor               INTEGER,
            pullback_pct_close              REAL,
            pullback_pct_low                REAL,
            pullback_status                 TEXT,
            pullback_score                  REAL NOT NULL,
            theme_id                        TEXT,
            theme_memberships_json          TEXT NOT NULL,
            theme_strength_raw              REAL,
            theme_strength_median           REAL,
            theme_strength_trimmed_mean     REAL,
            theme_percentile                REAL,
            theme_valid                     INTEGER NOT NULL DEFAULT 0,
            theme_reason                    TEXT,
            theme_score                     REAL NOT NULL,
            breadth_pct                     REAL,
            breadth_valid                   INTEGER NOT NULL DEFAULT 0,
            breadth_reason                  TEXT,
            breadth_score                   REAL NOT NULL,
            breakout_volume                 REAL,
            volume_avg20                    REAL,
            breakout_rvol                   REAL,
            volume_valid                    INTEGER NOT NULL DEFAULT 0,
            volume_reason                   TEXT,
            volume_score                    REAL NOT NULL,
            rebound_status                  TEXT,
            rebound_score                   REAL NOT NULL,
            avg_dollar_volume_20            REAL,
            core_score                      REAL NOT NULL,
            support_score                   REAL NOT NULL,
            total_score                     REAL NOT NULL,
            eligible_primary                INTEGER NOT NULL DEFAULT 0,
            primary_status                  TEXT,
            failed_gates_json               TEXT NOT NULL,
            grade                           TEXT,
            score_model_version             TEXT NOT NULL,
            confidence_json                 TEXT NOT NULL,
            explanation_payload_json        TEXT NOT NULL,
            snapshot_json                   TEXT NOT NULL,
            created_at                      TEXT NOT NULL,
            updated_at                      TEXT NOT NULL,
            UNIQUE(run_id, ticker)
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_j3_swing_runs_date ON jarvis3_swing_scan_runs(as_of_date DESC)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_j3_swing_candidates_date ON jarvis3_swing_candidates(scan_date DESC, eligible_primary DESC, total_score DESC)"
    )
    connection.commit()


def ensure_tables(connection=None) -> None:
    """자비스3 독립 테이블을 준비한다. 전달된 연결은 호출자가 닫는다."""
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
    ticker: str,
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
    score_model_version: str | None = None,
    entry_plan: dict | None = None,
    snapshot: dict | None = None,
    memo: str | None = None,
    connection=None,
) -> int | None:
    ticker = str(ticker or "").strip().upper()
    stock_name = str(stock_name or "").strip()
    theme_name = str(theme_name or "").strip()
    if not ticker or not stock_name or not theme_name:
        raise ValueError("티커·종목명·테마명은 필수입니다")
    buy_date_text = _valid_date(buy_date, "매수일")
    buy_price_number = _positive_number(buy_price, "매수가")
    quantity_number = _positive_number(quantity, "수량", allow_none=True)
    trade_style = str(trade_style or "").strip()
    if trade_style not in {"단타", "스윙", "중장기"}:
        raise ValueError("매매유형은 단타·스윙·중장기 중 하나여야 합니다")

    def optional_score(value):
        if value is None:
            return None
        number = float(value)
        if not math.isfinite(number) or not 0 <= number <= 100:
            raise ValueError("점수는 0~100 범위여야 합니다")
        return number

    now = datetime.now().isoformat(timespec="seconds")
    params = (
        now, now, ticker, stock_name, theme_name, buy_date_text, buy_price_number,
        quantity_number, trade_style, str(entry_setup or "").strip() or None,
        str(recommendation_state or "").strip() or None,
        str(market_regime or "").strip() or None,
        optional_score(market_score), optional_score(theme_score), optional_score(stock_score),
        str(score_model_version or "").strip() or None,
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
            INSERT INTO jarvis3_trades (
                recorded_at, updated_at, ticker, stock_name, theme_name,
                buy_date, buy_price, quantity, trade_style, entry_setup,
                recommendation_state, market_regime, market_score, theme_score,
                stock_score, score_model_version, entry_plan_json, snapshot_json, memo, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '보유')
            """,
            params,
        )
        conn.commit()
        return getattr(cursor, "lastrowid", None)
    finally:
        if own_connection:
            conn.close()


def _json_ready(value):
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _json_text(value, *, sort_keys: bool = False) -> str:
    return json.dumps(
        _json_ready(value), ensure_ascii=False, separators=(",", ":"), sort_keys=sort_keys
    )


def save_swing_scan(scan: dict, *, connection=None) -> int:
    """US_SWING 후보 원자료를 버전별 불변 run으로 저장한다.

    같은 날짜라도 입력자료나 config가 달라지면 새 run을 남긴다. 동일 fingerprint를
    다시 저장하면 기존 run을 반환하며 과거 버전 행을 UPDATE하지 않는다.
    """

    if not isinstance(scan, dict) or not scan.get("ok"):
        raise ValueError("정상 완료된 미국 스윙 스캔만 저장할 수 있습니다")
    rows = list(scan.get("all_rows") or [])
    if not rows:
        raise ValueError("저장할 미국 스윙 종목 원자료가 없습니다")
    as_of_date = _valid_date(scan.get("date"), "스캔일")
    score_version = str(scan.get("score_model_version") or "").strip()
    universe_mode = str(scan.get("universe_mode") or "").strip()
    if not score_version or not universe_mode:
        raise ValueError("universe_mode와 score_model_version은 필수입니다")
    tickers = [str(row.get("ticker") or "").strip().upper() for row in rows]
    if any(not ticker for ticker in tickers) or len(set(tickers)) != len(tickers):
        raise ValueError("스캔 원자료의 ticker는 비어 있지 않고 run 안에서 고유해야 합니다")
    required_scores = (
        "rs60_score", "rs120_score", "pullback_score", "theme_score", "volume_score",
        "breadth_score", "rebound_score", "core_score", "support_score", "total_score",
    )
    for row in rows:
        missing = [field for field in required_scores if row.get(field) is None]
        if missing:
            raise ValueError(f"{row.get('ticker')} 필수 점수 누락: {', '.join(missing)}")

    import us_swing_selector

    config_json = _json_text(
        scan.get("config") or us_swing_selector.DEFAULT_CONFIG, sort_keys=True
    )
    config_hash = hashlib.sha256(config_json.encode("utf-8")).hexdigest()
    # 일부 필드만 hash하면 pullback_low·theme median·IXIC 상태 등이 달라져도 같은
    # run으로 합쳐질 수 있다. 계산에 사용한 시장값과 canonical 전체 행을 묶는다.
    fingerprint_payload = {
        "market": scan.get("market") or {},
        "rows": sorted(rows, key=lambda item: str(item.get("ticker") or "")),
    }
    source_fingerprint = hashlib.sha256(
        _json_text(fingerprint_payload, sort_keys=True).encode("utf-8")
    ).hexdigest()
    scan_key = hashlib.sha256(
        "|".join((as_of_date, universe_mode, score_version, config_hash, source_fingerprint)).encode("utf-8")
    ).hexdigest()
    now = datetime.now().isoformat(timespec="seconds")
    market = scan.get("market") or {}

    own_connection = connection is None
    conn = connection or _new_connection()
    try:
        ensure_tables(conn)
        conn.execute(
            """
            INSERT OR IGNORE INTO jarvis3_swing_scan_runs (
                scan_key, as_of_date, universe_mode, requested_universe_mode,
                score_model_version, config_hash, config_json, source_fingerprint,
                market_status, ixic_close, ixic_sma200, ixic_above_sma200,
                market_drawdown, distance_from_running_ath, days_since_market_reclaim,
                primary_count, watch_count, universe_count, data_count,
                checked_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scan_key, as_of_date, universe_mode, scan.get("requested_universe_mode"),
                score_version, config_hash, config_json, source_fingerprint,
                market.get("market_status"), market.get("ixic_close"), market.get("ixic_sma200"),
                int(bool(market.get("ixic_above_sma200"))), market.get("market_drawdown"),
                market.get("distance_from_running_ath"), market.get("days_since_market_reclaim"),
                int(scan.get("primary_count") or 0),
                int(scan.get("watch_count") or 0), int(scan.get("universe_count") or 0),
                int(scan.get("data_count") or 0), scan.get("checked_at"), now,
            ),
        )
        run_row = conn.execute(
            "SELECT id FROM jarvis3_swing_scan_runs WHERE scan_key=?", (scan_key,)
        ).fetchone()
        if run_row is None:
            raise RuntimeError("미국 스윙 scan run을 저장하지 못했습니다")
        run_id = int(run_row["id"])
        for row in rows:
            explanations = row.get("explanations") or {}
            confidence = {
                metric: payload.get("confidence")
                for metric, payload in explanations.items() if isinstance(payload, dict)
            }
            candidate = {
                "run_id": run_id, "scan_date": as_of_date, "ticker": row.get("ticker"),
                "stock_name": row.get("name"), "asset_type": row.get("asset_type"),
                "universe_mode": universe_mode, "market_status": row.get("market_status"),
                "ixic_close": row.get("ixic_close"), "ixic_sma200": row.get("ixic_sma200"),
                "ixic_above_sma200": int(bool(row.get("ixic_above_sma200"))),
                "market_drawdown": row.get("market_drawdown"),
                "distance_from_running_ath": row.get("distance_from_running_ath"),
                "days_since_market_reclaim": row.get("days_since_market_reclaim"),
                "rs60_raw": row.get("rs60_raw"), "rs60_percentile": row.get("rs60_percentile"),
                "rs60_valid": int(bool(row.get("rs60_valid"))), "rs60_reason": row.get("rs60_reason"),
                "rs60_score": row.get("rs60_score"), "rs120_raw": row.get("rs120_raw"),
                "rs120_percentile": row.get("rs120_percentile"),
                "rs120_valid": int(bool(row.get("rs120_valid"))), "rs120_reason": row.get("rs120_reason"),
                "rs120_score": row.get("rs120_score"), "rs_rank_status": row.get("rs_rank_status"),
                "rs_core_status": row.get("rs_core_status"), "breakout_date": row.get("breakout_date"),
                "breakout_close": row.get("breakout_close"),
                "previous_252_high_close": row.get("previous_252_high_close"),
                "breakout_pct_above_prior_high": row.get("breakout_pct_above_prior_high"),
                "breakout_reason": row.get("breakout_reason"), "anchor_date": row.get("anchor_date"),
                "anchor_close": row.get("anchor_close"), "days_since_anchor": row.get("days_since_anchor"),
                "pullback_pct_close": row.get("pullback_pct_close"),
                "pullback_pct_low": row.get("pullback_pct_low"),
                "pullback_status": row.get("pullback_status"), "pullback_score": row.get("pullback_score"),
                "theme_id": row.get("theme_id"), "theme_memberships_json": _json_text(row.get("themes") or []),
                "theme_strength_raw": row.get("theme_strength_raw"),
                "theme_strength_median": row.get("theme_strength_median"),
                "theme_strength_trimmed_mean": row.get("theme_strength_trimmed_mean"),
                "theme_percentile": row.get("theme_percentile"),
                "theme_valid": int(bool(row.get("theme_valid"))), "theme_reason": row.get("theme_reason"),
                "theme_score": row.get("theme_score"), "breadth_pct": row.get("breadth_pct"),
                "breadth_valid": int(bool(row.get("breadth_valid"))),
                "breadth_reason": row.get("breadth_reason"), "breadth_score": row.get("breadth_score"),
                "breakout_volume": row.get("breakout_volume"), "volume_avg20": row.get("volume_avg20"),
                "breakout_rvol": row.get("breakout_rvol"),
                "volume_valid": int(bool(row.get("volume_valid"))), "volume_reason": row.get("volume_reason"),
                "volume_score": row.get("volume_score"), "rebound_status": row.get("rebound_status"),
                "rebound_score": row.get("rebound_score"),
                "avg_dollar_volume_20": row.get("avg_dollar_volume_20"),
                "core_score": row.get("core_score"), "support_score": row.get("support_score"),
                "total_score": row.get("total_score"),
                "eligible_primary": int(bool(row.get("eligible_primary"))),
                "primary_status": row.get("primary_status"),
                "failed_gates_json": _json_text(row.get("failed_gates") or []),
                "grade": row.get("grade"), "score_model_version": score_version,
                "confidence_json": _json_text(confidence, sort_keys=True),
                "explanation_payload_json": _json_text(explanations, sort_keys=True),
                "snapshot_json": _json_text(row, sort_keys=True), "created_at": now, "updated_at": now,
            }
            columns = tuple(candidate)
            conn.execute(
                f"INSERT OR IGNORE INTO jarvis3_swing_candidates ({','.join(columns)}) "
                f"VALUES ({','.join('?' for _column in columns)})",
                tuple(candidate[column] for column in columns),
            )
        saved_count = int(conn.execute(
            "SELECT COUNT(*) FROM jarvis3_swing_candidates WHERE run_id=?", (run_id,)
        ).fetchone()[0])
        if saved_count != len(rows):
            raise RuntimeError(
                f"미국 스윙 후보 저장 불일치: 기대 {len(rows)}개, 실제 {saved_count}개"
            )
        conn.commit()
        return run_id
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        if own_connection:
            conn.close()


def list_swing_candidates(*, run_id: int | None = None, limit: int = 5000, connection=None) -> list[dict]:
    """저장된 selector snapshot을 원점수 순으로 읽는다."""

    limit = max(1, min(int(limit), 10000))
    own_connection = connection is None
    conn = connection or _new_connection()
    try:
        ensure_tables(conn)
        if run_id is None:
            latest = conn.execute(
                "SELECT id FROM jarvis3_swing_scan_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if latest is None:
                return []
            run_id = int(latest["id"])
        rows = conn.execute(
            """
            SELECT * FROM jarvis3_swing_candidates
            WHERE run_id=?
            ORDER BY eligible_primary DESC, total_score DESC, core_score DESC,
                     rs120_percentile DESC, rs60_percentile DESC,
                     pullback_score DESC, avg_dollar_volume_20 DESC, ticker ASC
            LIMIT ?
            """,
            (int(run_id), limit),
        ).fetchall()
        return [dict(row) for row in rows]
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
                "SELECT * FROM jarvis3_trades ORDER BY buy_date DESC, id DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM jarvis3_trades WHERE status=? ORDER BY buy_date DESC, id DESC LIMIT ?",
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
            "SELECT buy_date, buy_price, status FROM jarvis3_trades WHERE id=?", (trade_id,)
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
            UPDATE jarvis3_trades
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
            FROM jarvis3_trades
            """
        ).fetchone()
        return {
            "total_count": int(row["total_count"] or 0),
            "open_count": int(row["open_count"] or 0),
            "closed_count": int(row["closed_count"] or 0),
            "minimum_sample": 30,
        }
    finally:
        if own_connection:
            conn.close()
