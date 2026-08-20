import copy

import pandas as pd
import pytest

import us_swing_selector as swing


def _ohlcv(close, *, index=None, volume=100.0):
    values = list(map(float, close))
    index = index if index is not None else pd.bdate_range("2025-01-01", periods=len(values))
    volumes = [float(volume)] * len(values) if not isinstance(volume, (list, tuple)) else volume
    return pd.DataFrame(
        {
            "Open": values,
            "High": [value * 1.01 for value in values],
            "Low": [value * 0.99 for value in values],
            "Close": values,
            "Volume": volumes,
        },
        index=index,
    )


def _market_frame(periods=400):
    index = pd.bdate_range("2024-01-02", periods=periods)
    close = [100.0] * periods
    close[210] = 89.0
    for position in range(211, 241):
        close[position] = 89.0 + (position - 210) * (12.0 / 30.0)
    for position in range(241, periods):
        close[position] = 101.0 + (position - 240) * 0.01
    return _ohlcv(close, index=index)


def _profile_frame(index, r60, r120, *, scenario="valid", pullback=7.0, rvol=2.0):
    count = len(index)
    current = 100.0
    then60 = current / (1.0 + r60)
    then120 = current / (1.0 + r120)
    close = [60.0] * count

    def fill(start, end, left, right):
        span = end - start
        for position in range(start, end + 1):
            ratio = 0.0 if span == 0 else (position - start) / span
            close[position] = left + (right - left) * ratio

    fill(0, count - 121, 60.0, then120)
    fill(count - 121, count - 61, then120, then60)
    fill(count - 61, count - 4, then60, 99.0)
    if scenario == "no_breakout":
        close = [80.0] * count
        close[count - 201] = 150.0
        fill(count - 121, count - 61, then120, then60)
        fill(count - 61, count - 1, then60, current)
    else:
        anchor = current / (1.0 - pullback / 100.0)
        close[-3] = anchor
        close[-2] = anchor * 0.98
        close[-1] = current
    volume = [100.0] * count
    if scenario != "no_breakout":
        volume[-3] = 100.0 * rvol
    return _ohlcv(close, index=index, volume=volume)


def _integration_scan():
    ixic = _market_frame()
    index = ixic.index[-300:]
    prices = {
        "A": _profile_frame(index, .60, 1.00, pullback=7.0),
        "B": _profile_frame(index, .40, .05, pullback=7.0, rvol=3.0),
        "C": _profile_frame(index, .45, .70, scenario="no_breakout"),
        "D": _profile_frame(index, .55, .90, pullback=2.4),
        "E": _profile_frame(index, .50, .80, pullback=11.2),
    }
    for number in range(25):
        prices[f"F{number:02d}"] = _profile_frame(
            index, .35 - number * .01, .65 - number * .02, pullback=7.0
        )
    records = [
        {"ticker": ticker, "name": ticker, "asset_type": "COMMON_STOCK"}
        for ticker in prices
    ]
    memberships = {
        ticker: [f"THEME{position % 4}"]
        for position, ticker in enumerate(prices)
    }
    return swing.scan_eod(
        prices, ixic, memberships, universe_records=records,
        universe_mode="LEGACY_RESEARCH_200",
    )


def test_config_weights_sum_to_100():
    assert sum(swing.DEFAULT_CONFIG["weights"].values()) == 100


def test_config_rejects_wrong_total():
    with pytest.raises(ValueError, match="100"):
        swing.merged_config({"weights": {**swing.DEFAULT_CONFIG["weights"], "theme": 9}})


def test_config_rejects_negative_weight_even_if_total_is_100():
    weights = copy.deepcopy(swing.DEFAULT_CONFIG["weights"])
    weights["theme"] = -1
    weights["rebound"] = 18
    with pytest.raises(ValueError, match="0 이상"):
        swing.merged_config({"weights": weights})


def test_relative_strength_formula():
    stock = [100.0] * 60 + [130.0]
    index = [100.0] * 60 + [110.0]
    assert swing.relative_strength_raw(stock, index, 60) == pytest.approx(.20)


def test_relative_strength_uses_same_benchmark_dates():
    dates = pd.bdate_range("2025-01-01", periods=62)
    stock = pd.Series(range(62), index=dates, dtype=float).drop(dates[1])
    index = pd.Series(range(62), index=dates, dtype=float)
    assert swing.relative_strength_raw(stock, index, 60) is None


@pytest.mark.parametrize(
    ("percentile", "points"),
    [(95, 25), (90, 23), (80, 20), (70, 12), (60, 6), (59.999, 0)],
)
def test_rs_score_boundaries(percentile, points):
    assert swing.rs_points(percentile) == points


def test_percentile_formula_descending():
    assert swing.percentile_ranks({"A": 3, "B": 2, "C": 1}) == {"A": 100, "B": 50, "C": 0}


def test_percentile_ties_use_average_rank():
    ranked = swing.percentile_ranks({"A": 3, "B": 3, "C": 1})
    assert ranked["A"] == ranked["B"] == 75


def test_percentile_single_value_is_100():
    assert swing.percentile_ranks({"A": 3}) == {"A": 100}


def test_breakout_requires_252_prior_closes():
    result = swing.latest_breakout(_ohlcv([100] * 252))
    assert not result["valid"]


def test_breakout_uses_prior_closes_and_strict_greater_than():
    equal = swing.latest_breakout(_ohlcv([100] * 253))
    above = swing.latest_breakout(_ohlcv([100] * 252 + [100.01]))
    assert not equal["has_breakout"]
    assert above["has_breakout"]
    assert above["previous_252_high_close"] == 100


def test_latest_new_high_resets_anchor_to_day_zero():
    result = swing.latest_breakout(_ohlcv([90] * 252 + [100, 99, 101]))
    assert result["anchor_close"] == 101
    assert result["days_since_anchor"] == 0


def test_days_since_anchor_uses_market_sessions_when_stock_has_gap():
    market_days = pd.bdate_range("2025-01-01", periods=255)
    stock_days = market_days.delete(-2)
    result = swing.latest_breakout(
        _ohlcv([90] * 252 + [100, 94], index=stock_days),
        trading_index=market_days,
    )
    assert result["days_since_anchor"] == 2


@pytest.mark.parametrize(
    ("value", "state", "points"),
    [
        (3.0, "VALID_PULLBACK", 16),
        (6.0, "PRIORITY_PULLBACK", 20),
        (10.0, "PRIORITY_PULLBACK", 20),
        (10.0001, "TOO_DEEP", 0),
        (2.4, "WAIT_SHALLOW", 6),
        (1.0, "WAIT_SHALLOW", 2),
        (-.01, "NEW_HIGH", 0),
    ],
)
def test_pullback_boundaries(value, state, points):
    assert swing.pullback_state(value) == state
    assert swing.pullback_points(value) == points


@pytest.mark.parametrize(
    ("anchor", "current", "state"),
    [(1.10, .99, "PRIORITY_PULLBACK"), (2.50, 2.35, "PRIORITY_PULLBACK"),
     (10.10, 9.797, "VALID_PULLBACK")],
)
def test_economic_exact_boundaries_survive_float_representation(anchor, current, state):
    value = (anchor - current) / anchor * 100
    assert swing.pullback_state(value) == state


@pytest.mark.parametrize("value,points", [(90, 10), (75, 7), (50, 3), (49.99, 0)])
def test_theme_score_tiers(value, points):
    assert swing.theme_points(value) == points


@pytest.mark.parametrize("value,points", [(70, 5), (50, 3), (30, 1), (29.99, 0)])
def test_breadth_score_tiers(value, points):
    assert swing.breadth_points(value) == points


@pytest.mark.parametrize("value,points", [(2, 8), (1.5, 6), (1.2, 3), (1.19, 0)])
def test_volume_score_tiers(value, points):
    assert swing.volume_points(value) == points


def test_rebound_uses_only_highest_single_state():
    assert swing.rebound_points("PRIOR_DAY_HIGH_RECLAIM") == 7
    assert swing.rebound_points("FIRST_GREEN") == 5
    assert swing.rebound_points("PULLBACK_TOUCH") == 3


def test_market_exact_ten_percent_correction_and_strict_reclaim():
    close = [10.10] * 205 + [9.09, 10.00, 10.11]
    result = swing.market_gate(_ohlcv(close))
    assert result["market_status"] == "MARKET_ON"


def test_market_history_short_is_invalid():
    result = swing.market_gate(_ohlcv([100] * 199))
    assert not result["valid"]
    assert result["reason"] == "INSUFFICIENT_INDEX_HISTORY"


def test_breakout_volume_excludes_breakout_day():
    volume = [100.0] * 252 + [200.0, 100.0]
    result = swing.latest_breakout(_ohlcv([90] * 252 + [100, 95], volume=volume))
    assert result["volume_avg20"] == 100
    assert result["breakout_rvol"] == 2


def test_breakout_volume_needs_all_twenty_values():
    volume = [100.0] * 252 + [200.0, 100.0]
    volume[-10] = float("nan")
    result = swing.latest_breakout(_ohlcv([90] * 252 + [100, 95], volume=volume))
    assert not result["volume_valid"]


def test_grade_is_only_for_hard_gate_eligible_rows():
    assert swing.grade_for(95, False) is None
    assert swing.grade_for(95, True) == "S"


def test_candidate_sort_tie_break_order():
    base = {"eligible_primary": True, "total_score": 80, "core_score": 60,
            "rs120_percentile": 90, "rs60_percentile": 90, "pullback_score": 16,
            "avg_dollar_volume_20": 100}
    rows = [{**base, "ticker": "B"}, {**base, "ticker": "A", "pullback_score": 20}]
    assert [row["ticker"] for row in sorted(rows, key=swing.candidate_sort_key)] == ["A", "B"]


def test_explanation_payload_has_required_fields_for_every_metric():
    payload = swing.explanation_payload({})
    assert set(payload) == {"market", "rs60", "rs120", "breakout", "pullback",
                            "theme", "volume", "breadth", "rebound"}
    required = {"title", "score", "max_score", "current_value", "display_value",
                "one_line_explanation", "detail_explanation", "status", "confidence"}
    assert all(required <= set(item) for item in payload.values())


def test_asset_types_exclude_etf_by_default_and_accept_enum():
    market = _market_frame()
    index = market.index[-300:]
    frame = _profile_frame(index, .5, .8)
    result = swing.scan_eod(
        {"ETF": frame, "STK": frame}, market, {},
        universe_records=[
            {"ticker": "ETF", "asset_type": swing.AssetType.ETF},
            {"ticker": "STK", "asset_type": swing.AssetType.COMMON_STOCK},
        ], universe_mode=swing.UniverseMode.LEGACY_RESEARCH_200,
        config={"rs": {"min_cross_section": 1}},
    )
    assert [row["ticker"] for row in result["all_rows"]] == ["STK"]


def test_pit_universe_requires_effective_dates():
    market = _market_frame()
    frame = _profile_frame(market.index[-300:], .5, .8)
    result = swing.scan_eod(
        {"A": frame}, market, {},
        universe_records=[{"ticker": "A", "asset_type": "COMMON_STOCK"}],
        universe_mode="PIT_NASDAQ_TOP200",
    )
    assert not result["ok"]
    assert "effective_from" in result["error"]


def test_future_rows_do_not_change_past_scan():
    market = _market_frame()
    index = market.index[-300:]
    frame = _profile_frame(index, .5, .8)
    config = {"rs": {"min_cross_section": 1}}
    records = [{"ticker": "A", "asset_type": "COMMON_STOCK"}]
    first = swing.scan_eod({"A": frame}, market, {}, universe_records=records,
                           universe_mode="LEGACY_RESEARCH_200", as_of=index[-2], config=config)
    changed = frame.copy()
    changed.loc[index[-1], "Close"] = 9999
    second = swing.scan_eod({"A": changed}, market, {}, universe_records=records,
                            universe_mode="LEGACY_RESEARCH_200", as_of=index[-2], config=config)
    assert first["all_rows"][0]["total_score"] == second["all_rows"][0]["total_score"]
    assert first["all_rows"][0]["anchor_date"] == second["all_rows"][0]["anchor_date"]


def test_non_overlap_and_all_signals_modes():
    signals = [
        {"ticker": "A", "date": "2025-01-01", "signal_index": 1},
        {"ticker": "A", "date": "2025-01-02", "signal_index": 2},
        {"ticker": "A", "date": "2025-12-31", "signal_index": 253},
    ]
    assert len(swing.suppress_overlapping_signals(signals, holding_days=252)) == 2
    assert len(swing.suppress_overlapping_signals(signals, mode="ALL_SIGNALS")) == 3


def test_five_symbol_eod_integration_statuses_scores_and_gate_separation():
    result = _integration_scan()
    assert result["ok"]
    assert result["market"]["market_status"] == "MARKET_ON"
    rows = {row["ticker"]: row for row in result["all_rows"]}
    assert rows["A"]["eligible_primary"] is True
    assert rows["A"]["primary_status"] == "PRIMARY_CANDIDATE"
    assert rows["B"]["eligible_primary"] is False
    assert rows["B"]["primary_status"] == "RS120_WEAK"
    assert rows["C"]["primary_status"] == "BREAKOUT_WAIT"
    assert rows["D"]["primary_status"] == "PULLBACK_WAIT"
    assert rows["D"]["pullback_score"] == 6
    assert rows["E"]["primary_status"] == "TOO_DEEP"
    for row in rows.values():
        assert row["core_score"] + row["support_score"] == pytest.approx(row["total_score"])
        assert row["total_score"] <= 100
        assert len(row["explanations"]) == 9


def test_rs_cross_section_under_30_never_becomes_primary():
    result = _integration_scan()
    prices = {row["ticker"]: None for row in result["all_rows"][:0]}
    market = _market_frame()
    index = market.index[-300:]
    one = _profile_frame(index, .5, .8)
    small = swing.scan_eod(
        {"A": one}, market, {},
        universe_records=[{"ticker": "A", "asset_type": "COMMON_STOCK"}],
        universe_mode="LEGACY_RESEARCH_200",
    )
    row = small["all_rows"][0]
    assert row["rs_rank_status"] == "RS_RANK_UNRELIABLE"
    assert not row["eligible_primary"]
# ── 지시문 61번 시험 목록에서 아직 이름 그대로 없던 것들 (2026-08-20) ────────
# 위 시험들이 계산을 이미 덮고 있지만, 지시문은 **각각을 따로 확인하라**고 적었다.
# 그래야 나중에 배점을 손댈 때 어느 규칙이 깨졌는지 이름만 보고 알 수 있다.


def _theme_scan(memberships, *, prices=None, records=None, config=None):
    """테마 규칙만 보려고 만드는 최소 스캔 — 횡단면 30종목 조건을 채운다."""
    ixic = _market_frame()
    index = ixic.index[-300:]
    prices = dict(prices or {})
    for number in range(32):
        ticker = f"T{number:02d}"
        prices.setdefault(
            ticker,
            _profile_frame(index, .50 - number * .012, .90 - number * .022),
        )
    records = records or [
        {"ticker": ticker, "asset_type": "COMMON_STOCK"} for ticker in prices
    ]
    return swing.scan_eod(
        prices, ixic, memberships, universe_records=records,
        universe_mode="LEGACY_RESEARCH_200", config=config,
    )


def test_relative_strength_formula_at_120_days():
    """TEST 2 — 6개월 창도 같은 식이다(종목 수익률 - 같은 날짜 나스닥 수익률)."""
    stock = [100.0] * 120 + [150.0]
    index = [100.0] * 120 + [120.0]
    assert swing.relative_strength_raw(stock, index, 120) == pytest.approx(.30)


@pytest.mark.parametrize("gap", [1, 2, 3])
def test_days_since_anchor_counts_day_one_two_and_three(gap):
    """TEST 7 — 신고가 당일이 day0이고 다음 거래일이 day1이다."""
    close = [100.0] * 260
    close[-1 - gap] = 130.0
    for position in range(len(close) - gap, len(close)):
        close[position] = 124.0
    result = swing.latest_breakout(_ohlcv(close))
    assert result["valid"]
    assert result["days_since_anchor"] == gap


@pytest.mark.parametrize(
    ("percentile", "points"),
    [(95, 25), (90, 23), (80, 20), (70, 12), (60, 6), (59.999, 0)],
)
def test_rs120_uses_the_same_ladder_and_the_same_maximum(percentile, points):
    """TEST 15 — RS120도 RS60과 같은 계단이고 만점도 같은 25점이다."""
    weights = swing.DEFAULT_CONFIG["weights"]
    assert weights["rs120"] == weights["rs60"] == 25
    assert swing.rs_points(percentile, max_points=weights["rs120"]) == points


def test_theme_strength_leaves_the_target_ticker_out():
    """TEST 18 — 제 상승이 제 테마 점수를 부풀리면 안 된다.

    같은 테마에 아주 강한 종목 하나(T00)와 평범한 일곱을 둔다. 제대로 빼고
    계산하면 **T00 자신이 보는 테마 강도**는 평범한 일곱만 본 값이고,
    **이웃(T01)이 보는 테마 강도**는 T00을 품은 값이라 훨씬 높아야 한다.
    """
    ixic = _market_frame()
    index = ixic.index[-300:]
    prices = {"T00": _profile_frame(index, 3.00, 5.00)}
    memberships = {f"T{number:02d}": [f"TH{number // 8}"] for number in range(32)}
    result = _theme_scan(memberships, prices=prices)
    rows = {row["ticker"]: row for row in result["all_rows"]}
    assert rows["T00"]["theme_id"] == rows["T01"]["theme_id"] == "TH0"
    assert rows["T00"]["theme_strength_raw"] < rows["T01"]["theme_strength_raw"]
    # 트림 평균·가운데 값도 같이 남겨야 나중에 다시 재 볼 수 있다.
    for name in ("theme_strength_median", "theme_strength_trimmed_mean"):
        assert rows["T00"][name] is not None


def test_theme_with_too_few_other_members_is_not_scored():
    """TEST 19 — 다른 구성종목이 셋도 안 되면 테마 점수를 매기지 않는다."""
    memberships = {f"T{number:02d}": [f"TH{number // 8}"] for number in range(32)}
    memberships["T00"] = ["TINY"]
    memberships["T01"] = ["TINY"]           # 대상을 빼면 남는 것이 하나뿐이다
    result = _theme_scan(memberships)
    rows = {row["ticker"]: row for row in result["all_rows"]}
    assert rows["T00"]["theme_valid"] is False
    assert rows["T00"]["theme_score"] == 0
    assert rows["T00"]["breadth_valid"] is False
    assert rows["T00"]["breadth_score"] == 0


def test_missing_rs_history_blocks_the_candidate_instead_of_scoring_zero():
    """TEST 20 — 못 잰 것을 0점으로 조용히 바꾸지 않는다. 자격에서 뺀다."""
    ixic = _market_frame()
    index = ixic.index[-300:]
    short = _profile_frame(index, .60, 1.00).tail(100)
    memberships = {f"T{number:02d}": [f"TH{number // 8}"] for number in range(32)}
    memberships["SHORT"] = ["TH0"]
    result = _theme_scan(memberships, prices={"SHORT": short})
    row = next(item for item in result["all_rows"] if item["ticker"] == "SHORT")
    assert row["rs120_valid"] is False
    assert row["eligible_primary"] is False
    assert "INSUFFICIENT" in row["primary_status"] or "WEAK" in row["primary_status"]


def test_missing_theme_does_not_block_the_candidate():
    """TEST 21 — 테마는 보조점수다. 못 쟀다고 종목을 탈락시키지 않는다."""
    memberships = {f"T{number:02d}": [f"TH{number // 8}"] for number in range(32)}
    memberships.pop("T00")                  # 어느 테마에도 안 든 종목
    result = _theme_scan(memberships)
    row = next(item for item in result["all_rows"] if item["ticker"] == "T00")
    assert row["theme_valid"] is False
    assert row["theme_score"] == 0
    assert row["eligible_primary"] is True
    assert row["primary_status"] == "PRIMARY_CANDIDATE"


def test_high_support_score_can_never_bypass_the_rs_gate():
    """TEST 22 — 보조점수가 아무리 높아도 RS 자격을 대신하지 못한다."""
    result = _integration_scan()
    rows = {row["ticker"]: row for row in result["all_rows"]}
    weak = rows["B"]                        # RS120만 모자란 종목
    assert weak["rs120_percentile"] < 80
    assert weak["volume_score"] == 8        # 돌파 거래량은 만점이다
    assert weak["eligible_primary"] is False
    assert weak["primary_status"] == "RS120_WEAK"
    assert weak["grade"] is None
    assert weak["ticker"] not in {row["ticker"] for row in result["primary_rows"]}


def test_every_item_score_sums_into_core_support_and_total():
    """TEST 23·24 — 일곱 항목 합이 핵심·보조로 갈라지고 그 합이 총점이다."""
    result = _integration_scan()
    weights = swing.DEFAULT_CONFIG["weights"]
    for row in result["all_rows"]:
        core = row["rs60_score"] + row["rs120_score"] + row["pullback_score"]
        support = (row["theme_score"] + row["volume_score"]
                   + row["breadth_score"] + row["rebound_score"])
        assert row["core_score"] == pytest.approx(core)
        assert row["support_score"] == pytest.approx(support)
        assert row["total_score"] == pytest.approx(core + support)
        assert core <= sum(weights[name] for name in ("rs60", "rs120", "pullback"))
        assert support <= sum(
            weights[name] for name in ("theme", "volume", "breadth", "rebound"))
        # 배점표 일곱 줄도 같은 값을 말해야 한다.
        assert [maximum for _n, _v, maximum, _t in row["score_parts"]] == [
            weights[name] for name in
            ("rs60", "rs120", "pullback", "theme", "volume", "breadth", "rebound")
        ]
        assert sum(value for _n, value, _m, _t in row["score_parts"]) == pytest.approx(
            row["total_score"])


def test_score_model_version_rides_on_every_row_and_the_scan():
    """TEST 29 — 어떤 배점으로 뽑은 줄인지 줄마다 남는다(지시문 55번)."""
    result = _integration_scan()
    assert result["score_model_version"] == swing.SCORE_MODEL_VERSION == "US_SWING_V1"
    for row in result["all_rows"]:
        assert row["score_model_version"] == "US_SWING_V1"
