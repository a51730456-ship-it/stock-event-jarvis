"""자비스12 상승장 규칙 고침 ④ 200일선 문 · ⑤ 눌림 점수 (2026-11-12 상하님 「다 해라」 · jarvis12_swing)."""
from __future__ import annotations

import pathlib
from unittest import mock

import jarvis12_rules
import jarvis12_swing
import us_swing_selector as us_swing

PAGE = pathlib.Path("pages/11_자비스12.py")


def _row(ticker, *, pull, status, rs60=95.0, rs120=95.0, support=20.0, market="MARKET_RECOVERY", above=True):
    cfg = us_swing.merged_config({"universe": {"include_adr": True}})
    weights = cfg["weights"]
    pull_score = us_swing.pullback_points(pull, max_points=weights["pullback"], config=cfg)
    rs60_score = us_swing.rs_points(rs60, max_points=weights["rs60"], config=cfg)
    rs120_score = us_swing.rs_points(rs120, max_points=weights["rs120"], config=cfg)
    core = rs60_score + rs120_score + pull_score
    row = {
        "ticker": ticker, "name": ticker, "valid": True, "market_status": market, "ixic_above_sma200": above,
        "market_valid": True, "market_reason": market, "core_data_valid": True,
        "rs60_valid": True, "rs120_valid": True, "rs60_percentile": rs60, "rs120_percentile": rs120,
        "breakout_data_valid": True, "has_valid_52w_breakout": True, "days_since_anchor": 2,
        "pullback_pct_close": pull, "pullback_status": status,
        "rs60_score": rs60_score, "rs120_score": rs120_score, "pullback_score": pull_score,
        "support_score": support, "core_score": core, "total_score": core + support, "score": core + support,
        "avg_dollar_volume_20": 1e9, "metrics": {"current": 100.0},
        "score_parts": [("3개월", rs60_score, 25.0, ""), ("6개월", rs120_score, 25.0, ""),
                        ("눌림", pull_score, 20.0, f"-{pull:.1f}%"), ("테마", 10.0, 10.0, "")],
        "pullback": {"score": pull_score, "parts": [pull_score]},
    }
    status_code, eligible = us_swing._candidate_status(row, cfg)
    row.update(primary_status=status_code, eligible_primary=eligible)
    return row


def _scan(rows, *, market="MARKET_RECOVERY", above=True):
    cfg = us_swing.merged_config({"universe": {"include_adr": True}})
    ordered = sorted(rows, key=us_swing.candidate_sort_key)
    return {"ok": True, "date": "2026-11-11", "all_rows": ordered, "config": cfg, "result_limit": 20,
            "market": {"valid": True, "market_status": market, "ixic_above_sma200": above, "ixic_sma200": 18000.0},
            "primary_rows": [r for r in ordered if r["eligible_primary"]],
            "watch_rows": [r for r in ordered if not r["eligible_primary"]],
            "explanation_catalog": {"market": {"one_line": "옛", "detail": "옛"}, "pullback": {"detail": "옛"}}}


def _switches(gate, flat):
    return mock.patch.multiple(jarvis12_rules, SWING_GATE_200=gate, SWING_FLAT_PULLBACK=flat)


def test_switches_off_return_the_frozen_scan_unchanged():
    scan = _scan([_row("AAA", pull=4.0, status="VALID_PULLBACK")])
    with _switches(False, False):
        assert jarvis12_swing.adjust(scan) is scan
        assert jarvis12_swing.top_pick_part() is None
        assert jarvis12_swing.market_words({"market_status": "MARKET_ON"}) == us_swing.plain_state("MARKET_ON")


def test_gate_200_opens_when_above_and_closes_when_below():
    # 옛 문은 「되돌아오는 중」이라 닫혀 있었다 — 200일선 위면 연다.
    rows = [_row("AAA", pull=4.0, status="VALID_PULLBACK", market="MARKET_RECOVERY")]
    assert rows[0]["eligible_primary"] is False
    with _switches(True, False), mock.patch.object(jarvis12_swing.j3, "_universe_daily", return_value=({}, {}, {})):
        out = jarvis12_swing.adjust(_scan(rows, market="MARKET_RECOVERY", above=True))
        assert [r["ticker"] for r in out["primary_rows"]] == ["AAA"]
        assert out["primary_rows"][0]["grade"]
        assert out["market"]["market_status"] == "MARKET_ON" and out["market"]["j12_gate"] == "SMA200"
        assert jarvis12_swing.market_words(out["market"]) == "200일선 위 · 살 만한 장"
        assert "200일선" in out["explanation_catalog"]["market"]["detail"]
        # 옛 문이 열려 있어도 200일선 아래면 닫는다.
        below = [_row("BBB", pull=4.0, status="VALID_PULLBACK", market="MARKET_ON", above=False)]
        assert below[0]["eligible_primary"] is True
        closed = jarvis12_swing.adjust(_scan(below, market="MARKET_ON", above=False))
        assert closed["primary_rows"] == [] and closed["watch_rows"][0]["primary_status"] == "MARKET_BLOCKED"
        assert jarvis12_swing.market_words(closed["market"]).startswith("200일선 아래")
    # 원본(얼린 결과)은 건드리지 않는다.
    assert rows[0]["eligible_primary"] is False and rows[0]["market_status"] == "MARKET_RECOVERY"


def test_flat_pullback_gives_three_to_six_the_full_twenty_and_marks_eight_plus():
    shallow = _row("SHAL", pull=4.0, status="VALID_PULLBACK", market="MARKET_ON")
    deep = _row("DEEP", pull=8.6, status="PRIORITY_PULLBACK", market="MARKET_ON")
    mid = _row("MIDL", pull=7.0, status="PRIORITY_PULLBACK", market="MARKET_ON")
    assert shallow["pullback_score"] < 20.0 and deep["pullback_score"] == 20.0
    before = shallow["total_score"]
    with _switches(False, True):
        out = jarvis12_swing.adjust(_scan([shallow, deep, mid], market="MARKET_ON"))
    by = {r["ticker"]: r for r in out["all_rows"]}
    assert by["SHAL"]["pullback_score"] == 20.0
    assert by["SHAL"]["total_score"] == round(before - shallow["pullback_score"] + 20.0, 6)
    assert by["SHAL"]["score_parts"][2][1] == 20.0 and by["SHAL"]["pullback"]["score"] == 20.0
    assert by["DEEP"]["pullback_caution"] is True
    assert by["MIDL"]["pullback_caution"] is False and by["SHAL"]["pullback_caution"] is False
    # 같은 점수가 되면 차례는 얼린 동점 규칙(중요 점수 · 6개월 등수 …)을 그대로 따른다.
    assert [r["ticker"] for r in out["primary_rows"]] == [r["ticker"] for r in sorted(out["all_rows"], key=us_swing.candidate_sort_key)]
    assert by["DEEP"]["explanations"]["pullback"]["status"] == "6~10% 내려옴"
    assert shallow["pullback_score"] < 20.0          # 원본은 그대로


def test_frozen_returns_the_scan_before_j12_rules():
    scan = _scan([_row("AAA", pull=4.0, status="VALID_PULLBACK", market="MARKET_ON")], market="MARKET_ON")
    with _switches(False, True):
        out = jarvis12_swing.adjust(scan)
    assert out is not scan and jarvis12_swing.frozen(out) is scan and jarvis12_swing.frozen(scan) is scan


def test_failure_keeps_the_frozen_scan():
    scan = _scan([_row("AAA", pull=4.0, status="VALID_PULLBACK", market="MARKET_ON")], market="MARKET_ON")
    with _switches(True, True), mock.patch.object(us_swing, "_candidate_status", side_effect=RuntimeError("x")):
        assert jarvis12_swing.adjust(scan) is scan


def test_page_reads_the_j12_swing_everywhere_and_saves_the_frozen_list():
    source = PAGE.read_text(encoding="utf-8")
    assert "j3data.breakout_scan()" not in source
    assert source.count("jarvis12_swing.breakout_scan()") == 3
    assert 'picklist_ui.autosave("US", pressed, jarvis12_swing.frozen(found))' in source
    assert "jarvis12_swing.top_pick_part()" in source
    assert "_REQUIRED_J12_SWING_REVISION = 2026111201" in source
    assert jarvis12_swing.MODULE_REVISION == 2026111201
    assert "jarvis12_swing.market_words(market_state)" in source
    assert "flat_pullback and row.get(\"pullback_caution\")" in source
    assert "_REQUIRED_J12_RULES_REVISION = 2026111204" in source and jarvis12_rules.MODULE_REVISION == 2026111204
