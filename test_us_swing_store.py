import copy
import json
import sqlite3

import pytest

import jarvis3_store as store
import us_swing_selector as swing


def _connection():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    return connection


def _row(ticker="AAA", **changes):
    row = {
        "ticker": ticker,
        "name": ticker,
        "asset_type": "COMMON_STOCK",
        "market_status": "MARKET_ON",
        "ixic_close": 20000.0,
        "ixic_sma200": 19000.0,
        "ixic_above_sma200": True,
        "market_drawdown": 0.0,
        "distance_from_running_ath": 0.0,
        "days_since_market_reclaim": 12,
        "rs60_raw": .20,
        "rs60_percentile": 96.0,
        "rs60_valid": True,
        "rs60_reason": "OK",
        "rs60_score": 25.0,
        "rs120_raw": .15,
        "rs120_percentile": 92.0,
        "rs120_valid": True,
        "rs120_reason": "OK",
        "rs120_score": 23.0,
        "rs_rank_status": "OK",
        "rs_core_status": "ELITE",
        "breakout_date": "2026-08-17",
        "breakout_close": 100.0,
        "previous_252_high_close": 99.0,
        "breakout_pct_above_prior_high": 1.0101,
        "breakout_reason": "OK",
        "anchor_date": "2026-08-17",
        "anchor_close": 100.0,
        "days_since_anchor": 2,
        "pullback_pct_close": 7.0,
        "pullback_pct_low": 8.0,
        "pullback_status": "PRIORITY_PULLBACK",
        "pullback_score": 20.0,
        "theme_id": "AI",
        "themes": ["AI"],
        "theme_strength_raw": .12,
        "theme_strength_median": .11,
        "theme_strength_trimmed_mean": .115,
        "theme_percentile": 80.0,
        "theme_valid": True,
        "theme_reason": "OK",
        "theme_score": 7.0,
        "breadth_pct": 75.0,
        "breadth_valid": True,
        "breadth_reason": "OK",
        "breadth_score": 5.0,
        "breakout_volume": 2_000_000.0,
        "volume_avg20": 1_000_000.0,
        "breakout_rvol": 2.0,
        "volume_valid": True,
        "volume_reason": "OK",
        "volume_score": 8.0,
        "rebound_status": "FIRST_GREEN",
        "rebound_score": 5.0,
        "avg_dollar_volume_20": 100_000_000.0,
        "core_score": 68.0,
        "support_score": 25.0,
        "total_score": 93.0,
        "eligible_primary": True,
        "primary_status": "PRIMARY_CANDIDATE",
        "failed_gates": [],
        "grade": "S",
        "explanations": swing.explanation_payload({}),
    }
    row.update(changes)
    return row


def _scan(rows=None, **changes):
    rows = rows or [_row()]
    scan = {
        "ok": True,
        "date": "2026-08-19",
        "universe_mode": "LEGACY_RESEARCH_200",
        "requested_universe_mode": "LIVE_NASDAQ_COMMON",
        "score_model_version": "US_SWING_V1",
        "config": copy.deepcopy(swing.DEFAULT_CONFIG),
        "all_rows": rows,
        "market": {
            "market_status": "MARKET_ON",
            "ixic_close": 20000.0,
            "ixic_sma200": 19000.0,
            "ixic_above_sma200": True,
            "market_drawdown": 0.0,
            "distance_from_running_ath": 0.0,
            "days_since_market_reclaim": 12,
        },
        "primary_count": sum(bool(row["eligible_primary"]) for row in rows),
        "watch_count": sum(not bool(row["eligible_primary"]) for row in rows),
        "universe_count": len(rows),
        "data_count": len(rows),
        "checked_at": "2026-08-20T06:30:00+09:00",
    }
    scan.update(changes)
    return scan


def test_schema_and_round_trip_keep_raw_status_score_and_version():
    connection = _connection()
    run_id = store.save_swing_scan(_scan(), connection=connection)
    saved = store.list_swing_candidates(run_id=run_id, connection=connection)[0]
    assert saved["rs60_raw"] == pytest.approx(.20)
    assert saved["pullback_pct_low"] == 8.0
    assert saved["primary_status"] == "PRIMARY_CANDIDATE"
    assert saved["score_model_version"] == "US_SWING_V1"
    assert json.loads(saved["failed_gates_json"]) == []
    assert saved["created_at"] == saved["updated_at"]


def test_identical_scan_is_idempotent():
    connection = _connection()
    first = store.save_swing_scan(_scan(), connection=connection)
    second = store.save_swing_scan(_scan(), connection=connection)
    assert first == second
    assert connection.execute("SELECT COUNT(*) FROM jarvis3_swing_scan_runs").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM jarvis3_swing_candidates").fetchone()[0] == 1


def test_any_raw_change_creates_new_immutable_run():
    connection = _connection()
    first = store.save_swing_scan(_scan(), connection=connection)
    second = store.save_swing_scan(_scan([_row(pullback_pct_low=8.1)]), connection=connection)
    assert first != second
    assert connection.execute("SELECT COUNT(*) FROM jarvis3_swing_scan_runs").fetchone()[0] == 2


def test_score_versions_do_not_overwrite_each_other():
    connection = _connection()
    first = store.save_swing_scan(_scan(), connection=connection)
    second = store.save_swing_scan(
        _scan(score_model_version="US_SWING_V2"), connection=connection
    )
    assert first != second
    versions = {
        row[0] for row in connection.execute(
            "SELECT score_model_version FROM jarvis3_swing_scan_runs"
        ).fetchall()
    }
    assert versions == {"US_SWING_V1", "US_SWING_V2"}


def test_actual_scan_config_is_hashed_and_stored():
    connection = _connection()
    config = copy.deepcopy(swing.DEFAULT_CONFIG)
    config["weights"]["rs60"] = 24.0
    config["weights"]["theme"] = 11.0
    run_id = store.save_swing_scan(_scan(config=config), connection=connection)
    saved = connection.execute(
        "SELECT config_json FROM jarvis3_swing_scan_runs WHERE id=?", (run_id,)
    ).fetchone()[0]
    assert json.loads(saved)["weights"]["rs60"] == 24.0


def test_missing_required_score_rolls_back_instead_of_silent_ignore():
    connection = _connection()
    row = _row()
    row["total_score"] = None
    with pytest.raises(ValueError, match="total_score"):
        store.save_swing_scan(_scan([row]), connection=connection)
    tables = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='jarvis3_swing_scan_runs'"
    ).fetchall()
    assert not tables


def test_duplicate_ticker_is_rejected():
    connection = _connection()
    with pytest.raises(ValueError, match="고유"):
        store.save_swing_scan(_scan([_row(), _row()]), connection=connection)


def test_db_list_uses_full_documented_tie_breaker():
    connection = _connection()
    rows = [
        _row("LOWVOL", pullback_score=16, avg_dollar_volume_20=500),
        _row("HIGHVOL", pullback_score=20, avg_dollar_volume_20=100),
    ]
    run_id = store.save_swing_scan(_scan(rows), connection=connection)
    ordered = store.list_swing_candidates(run_id=run_id, connection=connection)
    assert [row["ticker"] for row in ordered] == ["HIGHVOL", "LOWVOL"]


def test_trade_schema_can_store_score_model_version():
    connection = _connection()
    trade_id = store.save_trade(
        ticker="AAA", stock_name="AAA", theme_name="AI", buy_date="2026-08-19",
        buy_price=100, score_model_version="US_SWING_V1", connection=connection,
    )
    saved = connection.execute(
        "SELECT score_model_version FROM jarvis3_trades WHERE id=?", (trade_id,)
    ).fetchone()[0]
    assert saved == "US_SWING_V1"

