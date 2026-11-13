"""기능 ① 실적 날 흔들림 예보 — jarvis12_options (2026-11-13 상하님 「너의 추천 차례로 다 해라」)."""
from __future__ import annotations

import json
import pathlib
from datetime import date
from unittest import mock

import pandas as pd

import jarvis12_options as o

PAGE = pathlib.Path("pages/11_자비스12.py")


def test_expiry_must_hold_the_report():
    expiries = ["2026-11-14", "2026-11-17", "2026-11-21", "2026-12-19"]
    assert o.pick_expiry(expiries, date(2026, 11, 17), after_close=False) == "2026-11-17"
    assert o.pick_expiry(expiries, date(2026, 11, 17), after_close=True) == "2026-11-21"     # 장 마감 뒤면 다음 날 이후
    assert o.pick_expiry(["2026-12-19"], date(2026, 11, 17), after_close=True) is None       # 10일 넘게 먼 만기는 안 씀


def test_straddle_uses_mid_price_at_the_money():
    calls = pd.DataFrame({"strike": [95.0, 100.0, 105.0], "bid": [7.0, 4.0, 2.0], "ask": [7.4, 4.4, 2.2], "lastPrice": [7, 4, 2]})
    puts = pd.DataFrame({"strike": [95.0, 100.0, 105.0], "bid": [2.0, 3.8, 6.0], "ask": [2.2, 4.2, 6.4], "lastPrice": [2, 4, 6]})
    found = o.straddle_move(calls, puts, 101.0)
    assert found == {"strike": 100.0, "straddle": 8.2, "move": 8.1}            # (4.2 + 4.0) ÷ 101
    assert o.straddle_move(calls.iloc[:0], puts, 101.0) is None


def test_old_or_passed_values_are_not_shown_and_box_draws_band_and_dots():
    moves = {"NVDA": {"at": "2026-11-13", "earn": "2026-11-17", "when": "장 마감 뒤", "expiry": "2026-11-21",
                      "spot": 180.0, "strike": 180.0, "straddle": 14.4, "move": 8.0}}
    assert o.move_for("NVDA", moves, date(2026, 11, 14))["move"] == 8.0
    assert o.move_for("NVDA", moves, date(2026, 11, 18)) is None                  # 발표가 지남
    assert o.move_for("NVDA", moves, date(2026, 11, 19)) is None
    stale = {"NVDA": {**moves["NVDA"], "at": "2026-11-05"}}
    assert o.move_for("NVDA", stale, date(2026, 11, 14)) is None                  # 5일 넘게 묵음
    block = o.html(moves["NVDA"], {"25.10": -3.2, "26.01": -5.5, "26.04": -1.8, "26.07": 8.7})
    assert "−8.0%" in block and "+8.0%" in block and "11월 17일 장 마감 뒤" in block
    assert block.count("j12im-dot") == 4 and "4번 중 1번은 이 폭보다 크게" in block
    assert "\n" not in block and "$" not in block
    assert o.html(None) == ""


def test_collect_keeps_old_values_for_failures_and_drops_passed(tmp_path):
    fund = tmp_path / "US.json"
    fund.write_text(json.dumps({"stocks": {
        "AAA": {"earn": {"next": "2026-11-17", "when": "장 마감 뒤"}},
        "BBB": {"earn": {"next": "2026-11-18", "when": "장 전"}},
        "CCC": {"earn": {"next": "2026-12-30"}},
        "DDD": {"earn": {"next": "2026-11-19"}}}}), encoding="utf-8")
    out = tmp_path / "US_implied.json"
    out.write_text(json.dumps({"moves": {
        "BBB": {"at": "2026-11-12", "earn": "2026-11-18", "move": 5.0},
        "ZZZ": {"at": "2026-11-01", "earn": "2026-11-05", "move": 9.0}}}), encoding="utf-8")

    def fake(ticker, day, after_close):
        return ({"expiry": "2026-11-21", "spot": 50.0, "strike": 50.0, "straddle": 3.0, "move": 6.0}
                if ticker in ("AAA", "DDD") else None)

    with mock.patch.object(o, "FUND", fund), mock.patch.object(o, "OUT", out), \
            mock.patch.object(o, "_today", return_value=date(2026, 11, 13)), mock.patch.object(o, "implied_move", side_effect=fake):
        summary = o.collect()
    saved = json.loads(out.read_text(encoding="utf-8"))["moves"]
    assert summary == {"targets": 3, "got": 2, "failed": ["BBB"]}                 # CCC 는 14일 밖
    assert saved["DDD"]["when"] == ""                                             # 발표 시각을 모르면 빈칸(「장 전」으로 안 채움)
    assert saved["AAA"]["move"] == 6.0 and saved["BBB"]["move"] == 5.0           # 못 받으면 옛 값을 둔다
    assert saved["AAA"]["when"] == "장 마감 뒤"
    assert "ZZZ" not in saved                                                     # 발표가 지난 값은 버린다


def test_page_reads_only_the_file():
    source = PAGE.read_text(encoding="utf-8")
    assert "jarvis12_options.move_for(ticker)" in source and "implied_move(" not in source
    assert "_REQUIRED_J12_OPTIONS_REVISION = 2026111302" in source and o.MODULE_REVISION == 2026111302
