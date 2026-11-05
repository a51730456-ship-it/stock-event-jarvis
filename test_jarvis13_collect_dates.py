"""한국 저장기가 **찍을 날**의 장이 열렸나를 묻는지 (2026-11-05 상하님 「4」).

깃허브가 한국 몫 예약을 자정 넘겨 띄우면(11/5 00:31 실행) 찍을 날은 11/4 로 바르게 셌는데, 장이 열렸나는 **지금(11/5)** 을
물어 「쉬는 날」로 착각하고 건너뛰었다 — 「상위 테마 5개」 목록이 한 번도 안 쌓인 까닭이다. research/j13_theme15_collect.traded_on 은
그날 마감 뒤(16:00 한국 시각)를 「지금」으로 넘긴다. 저장기를 통째로 불러오면 jarvis13_flow.install 이 시세 함수를 바꿔 끼워
다른 시험에 번지므로, 함수 하나만 떼어 따로 돌린다.
"""
from __future__ import annotations

import ast
import unittest
from datetime import date, datetime
from datetime import time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
SEOUL = ZoneInfo("Asia/Seoul")


def _traded_on():
    source = (ROOT / "research" / "j13_theme15_collect.py").read_text(encoding="utf-8")
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == "traded_on")
    space = {"date": date, "datetime": datetime, "dtime": dtime, "SEOUL": SEOUL, "data": None}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "traded_on", "exec"), space)
    return space["traded_on"]


def _kospi_last_bar(last: date):
    """jarvis4_data.kr_market_traded_today 와 같은 셈 — 「지금」 날짜의 봉이 마지막 봉이면 열린 날."""
    def check(now=None):
        today = (now or datetime(2026, 11, 5, 0, 31, tzinfo=SEOUL)).astimezone(SEOUL).date()
        if today.weekday() >= 5:
            return False
        return last == today
    return check


class TradeDateTests(unittest.TestCase):
    def test_after_midnight_run_asks_the_trade_date(self):
        traded_on = _traded_on()
        check = _kospi_last_bar(date(2026, 11, 4))                 # 11/4(수) 봉까지 있다 · 지금은 11/5 00:31
        self.assertFalse(check())                                  # 예전 셈 — 11/5 를 물어 「쉬는 날」로 착각
        self.assertTrue(traded_on("2026-11-04", check))            # 고친 셈 — 11/4 를 묻는다

    def test_real_holiday_is_still_skipped(self):
        traded_on = _traded_on()
        check = _kospi_last_bar(date(2026, 9, 23))                 # 그날 봉이 없다(마지막 봉이 앞 날)
        self.assertFalse(traded_on("2026-09-24", check))
        self.assertFalse(traded_on("2026-11-07", _kospi_last_bar(date(2026, 11, 6))))   # 토요일

    def test_unknown_does_not_block(self):
        traded_on = _traded_on()
        self.assertIsNone(traded_on("2026-11-04", lambda now=None: None))

    def test_collector_uses_it(self):
        source = (ROOT / "research" / "j13_theme15_collect.py").read_text(encoding="utf-8")
        body = source.split("def main()", 1)[1]
        self.assertIn("traded_on(trade_date)", body)
        self.assertNotIn("kr_market_traded_today\", lambda: None)()", body)


if __name__ == "__main__":
    unittest.main()
