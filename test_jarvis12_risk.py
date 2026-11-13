"""기능 ④ 목록 쏠림(흔들림 · 테마) — jarvis12_risk (2026-11-13 상하님 「너의 추천 차례로 다 해라»)."""
from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd

import jarvis12_risk as risk

PAGE = pathlib.Path("pages/11_자비스12.py")


def _frame(returns, start=100.0):
    days = pd.bdate_range("2024-01-01", periods=len(returns) + 1)
    close = start * np.cumprod(np.r_[1.0, 1.0 + np.asarray(returns)])
    return pd.DataFrame({"Close": close}, index=days)


def _daily():
    rng = np.random.default_rng(7)
    market = rng.normal(0, 0.01, 300)
    return {
        "QQQ": _frame(market),
        "AAA": _frame(market * 2.0),                 # 베타 2
        "BBB": _frame(market * 0.5),                 # 베타 0.5
        "CCC": _frame(market[:60] * 1.0),            # 겹치는 날 모자람 → 못 잼
    }


def test_beta_is_cov_over_var_and_short_history_is_blank():
    daily = _daily()
    assert risk.beta_of(daily["AAA"], daily["QQQ"]) == 2.0
    assert risk.beta_of(daily["BBB"], daily["QQQ"]) == 0.5
    assert risk.beta_of(daily["CCC"], daily["QQQ"]) is None
    assert risk.beta_of(None, daily["QQQ"]) is None


def test_summary_averages_known_betas_and_counts_first_theme():
    rows = [{"ticker": "AAA", "themes": ["유전체·정밀의료", "바이오"]},
            {"ticker": "BBB", "themes": ["유전체·정밀의료"]},
            {"ticker": "CCC", "theme_id": "양자컴퓨팅"}]
    out = risk.summarize(rows, _daily())
    assert out["beta"] == 1.25 and out["measured"] == 2            # (2.0 + 0.5) / 2 · CCC 는 빈칸(0 으로 안 채움)
    assert out["themes"][0] == ("유전체·정밀의료", 2) and out["top_share"] == 67
    block = risk.html(out, "급락 목록")
    assert "흔들림" in block and "1.25" in block and "약 12%" in block
    assert "유전체·정밀의료 67%" in block and "이 테마가 빠지면" in block
    assert "\n" not in block and "~" not in block and "$" not in block      # 스트림릿 글 규칙(CLAUDE.md 0-4)
    assert risk.CSS.startswith("<style>")


def test_nothing_to_show_draws_nothing():
    assert risk.html(risk.summarize([], {}), "목록") == ""
    no_market = risk.summarize([{"ticker": "AAA", "themes": ["A"]}], {"AAA": _daily()["AAA"]})
    assert no_market["beta"] is None and "흔들림" not in risk.html(no_market, "목록")


def test_page_shows_the_box_above_both_tables_only_for_display():
    source = PAGE.read_text(encoding="utf-8")
    assert '_render_list_risk(rows, "급락 목록")' in source
    assert '_render_list_risk(primary + watch, "정식 후보 + 관찰")' in source
    assert "_REQUIRED_J12_RISK_REVISION = 2026111301" in source and risk.MODULE_REVISION == 2026111301
