"""기능 ③ 내 계획 한 장 — jarvis12_plan (2026-11-13 상하님 「너의 추천 차례로 다 해라」)."""
from __future__ import annotations

import pathlib
from unittest import mock

import pytest

import jarvis12_plan as plan

PAGE = pathlib.Path("pages/11_자비스12.py")


@pytest.fixture()
def temp_db(tmp_path):
    with mock.patch.object(plan, "DB_PATH", tmp_path / "t.sqlite3"), mock.patch.object(plan, "_READY", False), \
            mock.patch.object(plan.db_runtime, "turso_config", return_value=None):
        yield


def test_check_needs_buy_and_sane_levels():
    assert plan.check(None, 90, 120, None)[1] == "산 값(또는 살 값)을 적어 주십시오."
    assert "손절은 산 값보다 낮아야" in plan.check(100, 101, 120, None)[1]
    assert "목표는 산 값보다 높아야" in plan.check(100, 90, 99, None)[1]
    assert "하나는 적어" in plan.check(100, None, None, 10)[1]
    values, problem = plan.check(100, 92, None, 0)
    assert problem is None and values["target"] is None and values["qty"] is None     # 0 은 안 적은 것으로


def test_save_get_delete_round_trip(temp_db):
    assert plan.get("NVDA") is None
    plan.save("nvda", 100, 92, 120, 50)
    got = plan.get("NVDA")
    assert (got["buy"], got["stop"], got["target"], got["qty"]) == (100, 92, 120, 50)
    plan.save("NVDA", 101, 95, None, None)                       # 다시 적으면 바꿔 적음(한 종목 한 줄)
    assert plan.get("NVDA")["target"] is None
    plan.delete("NVDA")
    assert plan.get("NVDA") is None
    with pytest.raises(ValueError):
        plan.save("NVDA", 100, 120, None, None)


def test_outcome_and_card():
    card = {"ticker": "NVDA", "buy": 100.0, "stop": 92.0, "target": 120.0, "qty": 50.0}
    out = plan.outcome(card)
    assert out["target"] == {"price": 120.0, "pct": 20.0, "money": 1000.0}
    assert out["stop"] == {"price": 92.0, "pct": -8.0, "money": -400.0} and out["ratio"] == 2.5
    block = plan.html(card, [95, 97, 99, 101, 103], 104.0)
    assert "목표에 닿으면 +20.0% · +1,000 달러" in block and "손절에 닿으면 -8.0% · −400 달러" in block
    assert "2.5배" in block and "지금 104.00 (+4.0% · +200 달러)" in block and "<polyline" in block
    assert "앱은 손절 · 목표 · 수량을 정하지 않습니다" in block
    assert "\n" not in block and "$" not in block
    assert plan.html(None) == ""


def test_page_opens_by_button_hides_for_guests_and_has_no_defaults():
    source = PAGE.read_text(encoding="utf-8")
    body = source[source.index("def _render_my_plan("):source.index("def _render_day_price_row(")]
    assert "if auth.is_guest():" in body and "_section_toggle(" in body
    assert 'value=(plan or {}).get("stop")' in body and 'value=(plan or {}).get("target")' in body   # 빈칸으로 연다
    assert "_REQUIRED_J12_PLAN_REVISION = 2026111301" in source and plan.MODULE_REVISION == 2026111301
