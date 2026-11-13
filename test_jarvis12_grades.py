"""기능 ② 종목 성적표 A~F — jarvis12_grades (2026-11-13 상하님 「너의 추천 차례로 다 해라」)."""
from __future__ import annotations

import pathlib
from collections import Counter

import numpy as np
import pandas as pd

import jarvis12_grades as g

PAGE = pathlib.Path("pages/11_자비스12.py")


def _stocks(n=50):
    out = {}
    for i in range(n):
        out[f"T{i:02d}"] = {"annual": [["2024", 100.0, 1, 1], ["2025", 100.0 + i, 1, 1]], "opm": i / 100.0,
                            "pe": (i + 1) if i % 10 else -5.0}
    return out


def _daily(n=50):
    days = pd.bdate_range("2025-01-01", periods=200)
    rng = np.random.default_rng(3)
    out = {}
    for i in range(n):
        steps = 1.0 + rng.normal(0.0005 * i, 0.002 + 0.0004 * i, len(days))
        out[f"T{i:02d}"] = pd.DataFrame({"Close": 100 * np.cumprod(steps)}, index=days)
    return out


def test_grades_follow_the_10_20_40_20_10_split_and_direction():
    raw = g.raw_values(_stocks(), _daily())
    grades = g.grade_table(raw)
    growth = Counter(grades[t].get("growth") for t in grades)
    assert growth == Counter({"A": 5, "B": 10, "C": 20, "D": 10, "F": 5})
    assert grades["T49"]["growth"] == "A" and grades["T00"]["growth"] == "F"      # 매출이 가장 많이 는 쪽이 A
    assert grades["T01"]["value"] == "A"                                         # PER 이 가장 낮은 쪽이 A
    assert "value" not in grades["T00"] and "value" not in grades["T10"]         # 적자(PER 0 이하)는 빈칸 — F 로 안 채움
    assert grades["T00"]["calm"] in ("A", "B")                                   # 가장 조용한 쪽이 A 쪽


def test_card_shows_five_cells_and_blank_when_unmeasured():
    raw = g.raw_values(_stocks(), {})                   # 주가를 아직 못 읽은 판
    data = {"grades": g.grade_table(raw), "raw": raw, "count": 50}
    block = g.card_html("T49", data)
    assert block.count("j12gr-cell") == 5 and "명부 50종목" in block
    assert ">—</b><span class='j12gr-l'>주가 힘" in block                        # 못 잰 과목은 —
    assert "\n" not in block and "$" not in block
    assert g.card_html("ZZZZ", data) == ""


def test_real_file_grades_split_as_promised():
    raw = g.raw_values(g._load_stocks(), {})
    grades = g.grade_table(raw)
    counts = Counter(v.get("margin") for v in grades.values() if v.get("margin"))
    total = sum(counts.values())
    assert total > 150
    assert abs(counts["A"] / total - 0.10) < 0.02 and abs(counts["C"] / total - 0.40) < 0.02


def test_page_puts_the_card_above_the_finance_button():
    source = PAGE.read_text(encoding="utf-8")
    body = source[source.index("def _render_fundamentals_box("):source.index("def _render_day_price_row(")]
    assert body.index("jarvis12_grades.card_html(ticker)") < body.index("재무 한눈에 보기")
    assert "_REQUIRED_J12_GRADES_REVISION = 2026111301" in source and g.MODULE_REVISION == 2026111301
