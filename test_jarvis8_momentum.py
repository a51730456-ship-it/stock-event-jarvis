"""Independent J8 momentum selector checks against the frozen research selections."""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from jarvis8_momentum import select


ROOT = Path(__file__).resolve().parent


def _frame(close, dates=None, volume=500_000):
    c = np.asarray(close, dtype=float)
    if dates is None:
        dates = pd.bdate_range("2023-01-02", periods=len(c))
    return pd.DataFrame({"Open": c, "High": c * 1.01,
                         "Low": c * .99, "Close": c,
                         "Volume": np.full(len(c), volume, dtype=float)}, index=dates)


def _sample():
    dates = pd.bdate_range("2023-01-02", periods=300)
    frames = {"QQQ": _frame(np.linspace(100, 150, 300), dates),
              "BBB": _frame(np.linspace(100, 190, 300), dates),
              "AAA": _frame(np.linspace(100, 190, 300), dates)}
    return frames, dates[-1]


def test_equal_momentum_tickers_are_alphabetical_and_json_safe():
    frames, day = _sample()
    result = select(frames, day, ["BBB", "AAA"])
    assert result["market_ok"] is True
    assert result["eligible_count"] == 2
    assert [r["ticker"] for r in result["top5"]] == ["AAA", "BBB"]
    row = result["top5"][0]
    assert row["momentum"] == pytest.approx(frames["AAA"].Close.iloc[-22] / frames["AAA"].Close.iloc[-253] - 1)
    assert row["c_252"] == frames["AAA"].Close.iloc[-253]
    assert row["c_21"] == frames["AAA"].Close.iloc[-22]
    json.dumps(result, ensure_ascii=False, allow_nan=False)


def test_future_prices_cannot_change_signal():
    frames, day = _sample()
    before = select(frames, day)
    later = pd.bdate_range(pd.Timestamp(day).normalize() + pd.Timedelta(days=1), periods=12)
    for symbol in frames:
        frames[symbol] = pd.concat([frames[symbol], _frame([1000] * len(later), later)])
    assert select(frames, day) == before


def test_market_below_200_day_mean_returns_no_candidates():
    frames, day = _sample()
    frames["QQQ"] = _frame([100.0] * 300, frames["QQQ"].index)
    result = select(frames, day)
    assert not result["market_ok"]
    assert result["top5"] == []
    assert result["eligible_count"] == 0
    assert "QQQ" in result["excluded"]["AAA"]


def test_missing_session_and_invalid_ohlc_are_excluded():
    frames, day = _sample()
    frames["AAA"] = frames["AAA"].drop(frames["AAA"].index[-100])
    frames["BBB"].loc[frames["BBB"].index[-2], "High"] = 1.0
    result = select(frames, day)
    assert result["top5"] == []
    assert "자료 부족" in result["excluded"]["AAA"]
    assert "모순" in result["excluded"]["BBB"]


def test_large_daily_jump_and_weak_liquidity_are_excluded():
    frames, day = _sample()
    # One 81% jump in the 252 daily returns is a data-quality exclusion.
    old = float(frames["AAA"].Close.iloc[-3])
    for field, factor in (("Open", 1), ("High", 1.01), ("Low", .99), ("Close", 1)):
        frames["AAA"].loc[frames["AAA"].index[-2], field] = old * 1.81 * factor
    frames["BBB"].loc[frames["BBB"].index[-20:], "Volume"] = 1.0
    result = select(frames, day)
    assert "80%" in result["excluded"]["AAA"]
    assert "2천만" in result["excluded"]["BBB"]


def test_missing_benchmark_today_is_error_not_market_off():
    frames, day = _sample()
    frames["QQQ"] = frames["QQQ"].iloc[:-1]
    with pytest.raises(ValueError, match="QQQ"):
        select(frames, day)


@pytest.fixture(scope="module")
def archived_research():
    base = ROOT / "output/jarvis3_audit_20260909"
    study = ROOT / "output/independent_research/high_screen_20260922/selections.json"
    roster = ROOT / "data/jarvis8/universe.json"
    if not all((base / f"fresh_{name}.parquet").exists() for name in ("open", "high", "low", "close", "volume")):
        pytest.skip("원본 parquet 없음")
    if not study.exists() or not roster.exists():
        pytest.skip("원본 연구 선정표 또는 명부 없음")
    wide = {field: pd.read_parquet(base / f"fresh_{field.lower()}.parquet")
            for field in ("Open", "High", "Low", "Close", "Volume")}
    symbols = sorted(set(json.loads(roster.read_text(encoding="utf-8"))["tickers"]) - {"QQQ", "SPY", "^IXIC"})
    frames = {symbol: pd.DataFrame({name: wide[name][symbol] for name in wide}, index=wide["Close"].index)
              for symbol in ["QQQ", *symbols] if symbol in wide["Close"].columns}
    original = [r for r in json.loads(study.read_text(encoding="utf-8")) if r["offset"] == 0]
    return frames, symbols, original


def test_archived_research_signal_reproduction(archived_research):
    frames, symbols, original = archived_research
    assert len(original) == 121
    # Fixed checkpoints span the full decade, including possible market-off days.
    for position in (0, 20, 40, 60, 80, 100, 120):
        expected = original[position]
        actual = select(frames, expected["day"], symbols)
        assert actual["eligible_count"] == expected["eligible"], expected["day"]
        assert [r["ticker"] for r in actual["top5"]] == expected["momentum"], expected["day"]


@pytest.mark.skipif(os.environ.get("J8_FULL_REPLAY") != "1", reason="명시적으로 요청한 경우 121개 전체 재생")
def test_archived_research_all_121_signal_days(archived_research):
    frames, symbols, original = archived_research
    for expected in original:
        actual = select(frames, expected["day"], symbols)
        assert actual["eligible_count"] == expected["eligible"], expected["day"]
        assert [r["ticker"] for r in actual["top5"]] == expected["momentum"], expected["day"]
