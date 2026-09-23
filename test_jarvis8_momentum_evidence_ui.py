"""Evidence provenance and a small real Streamlit render check."""

import json
import shutil

from jarvis8_momentum_evidence_ui import (
    DIAGNOSTICS, RISK, ROOT, STUDY, load_diagnostics, load_evidence,
)


def _copy_results(target):
    for original in (STUDY, RISK):
        destination = target / original.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, destination)


def test_current_sources_are_verified_or_explicitly_archived():
    checked = load_evidence()
    if checked["state"] == "archive":
        # The deployed app intentionally omits large historical price files.
        assert checked["missing_sources"]
        assert all(name.endswith(".parquet") for name in checked["missing_sources"])
        assert "fresh_close.parquet" in checked["missing_sources"]
    else:
        assert checked["state"] == "verified"


def test_opportunity_diagnostics_recalculate_and_check_sources():
    from research.jarvis8_opportunity_diagnostics_20260923 import calculate

    checked = load_diagnostics()
    if checked["state"] == "archive":
        assert checked["missing_sources"] == ["fresh_close.parquet"]
    else:
        assert checked["state"] == "verified"
        assert checked["result"] == calculate()
    result = checked["result"]
    assert result["method"]["active_count"] == 102
    assert result["concentration"]["momentum"]["remaining_simple_sum_pct_points"] < 0
    # BTC's high-volatility story is not a monotone pattern in J8's own prices.
    edge = [row["mean_excess_pct_points"] for row in result["volatility_quartiles"]]
    assert edge[1] > edge[3]


def test_opportunity_diagnostics_present_changed_source_is_rejected(tmp_path):
    destination = tmp_path / DIAGNOSTICS.relative_to(ROOT)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(DIAGNOSTICS, destination)
    script = tmp_path / "research/jarvis8_opportunity_diagnostics_20260923.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("# modified source", encoding="utf-8")
    assert load_diagnostics(tmp_path)["state"] == "stale"


def test_archive_when_original_sources_are_absent(tmp_path):
    _copy_results(tmp_path)
    result = load_evidence(tmp_path)
    assert result["state"] == "archive"
    assert "fresh_close.parquet" in result["missing_sources"]


def test_changed_present_source_suppresses_figures(tmp_path):
    _copy_results(tmp_path)
    script = tmp_path / "research/independent_high_screen_20260922.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("# changed", encoding="utf-8")
    result = load_evidence(tmp_path)
    assert result["state"] == "stale"
    assert "study" not in result


def test_broken_link_between_studies_suppresses_figures(tmp_path):
    _copy_results(tmp_path)
    risk_path = tmp_path / RISK.relative_to(ROOT)
    risk = json.loads(risk_path.read_text(encoding="utf-8"))
    risk["metadata"]["original_result_sha256"] = "0" * 64
    risk_path.write_text(json.dumps(risk), encoding="utf-8")
    result = load_evidence(tmp_path)
    assert result["state"] == "stale"
    assert "study" not in result


def _study_app():
    import streamlit as st

    from jarvis8_momentum_evidence_ui import render

    render(st)


def test_study_renders_at_short_and_swing_horizons():
    from streamlit.testing.v1 import AppTest

    page = AppTest.from_function(_study_app, default_timeout=20).run()
    assert not page.exception
    assert page.selectbox(key="j8_independent_momentum_hold").value == 20
    assert page.selectbox(key="j8_independent_momentum_cost").value == 0.5
    assert any("17.09%" in item.value for item in page.metric)
    page.selectbox(key="j8_independent_momentum_hold").set_value(1).run()
    assert not page.exception
    assert any("-2.37%" in item.value for item in page.metric)
