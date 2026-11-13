"""기능 ⑤ 지난 급락 기록표 · ⑥ 해마다 연중 최대 하락 — jarvis12_history (2026-11-13 상하님 「너의 추천 차례로 다 해라」)."""
from __future__ import annotations

import pathlib
from unittest import mock

import numpy as np
import pandas as pd

import jarvis12_crash as c12
import jarvis12_history as hist

PAGE = pathlib.Path("pages/11_자비스12.py")


def _frame(closes, start="2019-01-01"):
    closes = np.asarray(closes, dtype=float)
    days = pd.bdate_range(start, periods=len(closes))
    return pd.DataFrame({"Open": closes, "High": closes, "Low": closes, "Close": closes}, index=days)


def _path():
    up = list(np.linspace(100, 130, 300))
    dip = list(np.linspace(130, 112, 15)) + list(np.linspace(112, 131, 20))     # −13.8% 바닥 뒤 회복
    rest = list(np.linspace(131, 170, 300))
    dip2 = list(np.linspace(170, 158, 10))                                         # 진행 중(−7%)
    return up + dip + rest + dip2


def test_same_rule_as_the_crash_list():
    frame = _frame(_path())
    with mock.patch.object(c12.j3, "_download_cached", return_value=({c12.SYMBOL: frame}, {})):
        mine = c12.episodes()["episodes"]
    theirs = hist.find_episodes(frame)
    keys = ("start", "reference", "reference_drop", "last_below", "recovered_on")
    assert [{k: e[k] for k in keys} for e in mine] == [{k: e[k] for k in keys} for e in theirs]
    assert len(theirs) == 2 and theirs[-1]["recovered_on"] is None


def test_crash_table_compares_first_day_and_bottom_after_one_year():
    frame = _frame(_path())
    table = hist.crash_table(frame)
    first, second = table["rows"]
    assert first["first_drop"] > first["bottom_drop"]                  # 첫날보다 바닥이 깊다
    assert first["days"] > 0 and not first["ongoing"]
    assert first["first_1y"] is not None and first["bottom_1y"] is not None
    assert first["bottom_1y"] > first["first_1y"]                       # 바닥에서 산 쪽이 더 벌었다
    assert second["ongoing"] and second["bottom_1y"] is None           # 1년이 안 지나면 빈칸(0 으로 안 채움)
    assert table["first"]["n"] == 1 and table["bottom"]["wins"] == 1
    block = hist.crash_html(table)
    assert "처음 −5% 다음 날 샀다면" in block and "바닥 다음 날 샀다면" in block and "진행 중" in block
    assert "\n" not in block and "$" not in block


def test_yearly_drawdown_and_result():
    days = pd.bdate_range("2020-01-01", "2022-12-31")
    closes = np.ones(len(days)) * 100.0
    year = np.array([d.year for d in days])
    closes[year == 2021] = np.r_[np.linspace(100, 120, 100), np.linspace(120, 90, 60),
                                 np.linspace(90, 110, (year == 2021).sum() - 160)]
    closes[year == 2022] = 110.0
    frame = pd.DataFrame({"Open": closes, "High": closes, "Low": closes, "Close": closes}, index=days)
    data = hist.yearly(frame)
    by = {row["year"]: row for row in data["years"]}
    assert by[2021]["drawdown"] == -25.0                               # 120 → 90
    assert by[2021]["result"] == 10.0 and not by[2021]["partial"]
    assert by[2020]["partial"] and by[2022]["partial"]                 # 첫해 · 마지막 해는 다 안 찬 해로 본다
    assert data["summary"]["n"] == 1 and data["summary"]["up_years"] == 1
    block = hist.years_html(data)
    assert "<svg" in block and "해마다 평균" in block and "\n" not in block


def test_page_opens_both_only_when_pressed():
    source = PAGE.read_text(encoding="utf-8")
    assert '"j12_crash_hist_open", close_label="지난 급락 기록표 닫기"' in source
    assert '"j12_years_open"' in source and '_render_history_block("years")' in source
    assert "_REQUIRED_J12_HISTORY_REVISION = 2026111301" in source and hist.MODULE_REVISION == 2026111301
