"""자비스13 파트별 성적표 + 코스피와 견줘 보기 (2026-10-30 · 자비스12 의 성적표를 한국에 맞춰 옮김).

셈은 자비스12 와 같다 — 산 날마다 같은 돈 · 다음 거래일 시가(저장된 매수금액) · 같은 날 코스피 시가.
한국에서 더한 것 — 다음 날 시가가 상한가에 붙은 줄은 못 산 것으로 뺀다.
"""
from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

import jarvis13_scorecard_compare as j13vx
import test_jarvis13_page as page_test

DAYS = pd.bdate_range("2026-10-01", periods=10)


def _kospi():
    opens = [1000.0 + i * 10 for i in range(10)]
    closes = [1005.0 + i * 10 for i in range(10)]
    return pd.DataFrame({"Open": opens, "High": closes, "Low": opens, "Close": closes}, index=DAYS)


def _stock(closes):
    return pd.DataFrame({"Open": closes, "High": closes, "Low": closes, "Close": closes, "Volume": 1.0}, index=DAYS)


def _rows():
    return [
        # 10/2 목록 → 10/5(월) 시가 100 에 삼 · 마지막 장 110 → +10%
        {"trade_date": DAYS[1].date().isoformat(), "list_kind": "top7", "code": "000001", "name": "가",
         "buy_open": 100.0},
        # 10/6 목록 · 그날 종가 100 인데 다음 날 시가 130 — 상한가에 붙어 못 산 줄
        {"trade_date": DAYS[3].date().isoformat(), "list_kind": "crash", "code": "000002", "name": "나",
         "buy_open": 130.0},
        # 매수금액이 없는 줄 — 세지 않는다(0으로 채우지 않는다)
        {"trade_date": DAYS[1].date().isoformat(), "list_kind": "breakout", "code": "000003", "name": "다",
         "buy_open": None},
    ]


def _frames():
    return {
        "000001": _stock([90.0, 95.0, 100.0, 102.0, 104.0, 105.0, 106.0, 107.0, 108.0, 110.0]),
        "000002": _stock([100.0] * 3 + [100.0] + [131.0] * 6),
        "000003": _stock([50.0] * 10),
    }


class ScorecardMathTests(unittest.TestCase):
    def test_limit_up_open_is_counted_as_not_bought(self):
        ok, blocked = j13vx.split_unfillable(_rows(), _frames())
        self.assertEqual(["000002"], [row["code"] for row in blocked])
        self.assertEqual({"000001", "000003"}, {row["code"] for row in ok})

    def test_part_table_counts_each_row_and_compares_with_kospi_same_days(self):
        ok, _blocked = j13vx.split_unfillable(_rows(), _frames())
        table = j13vx.part_table(ok, _frames(), _kospi(), last_day=DAYS[-1].date())
        top = table["top7"]
        self.assertEqual(1, top["n"])
        self.assertEqual(1, top["win"])
        self.assertAlmostEqual(10.0, top["sum"], places=6)
        kospi_gain = (_kospi()["Close"].iloc[-1] / _kospi()["Open"].iloc[2] - 1.0) * 100.0
        self.assertAlmostEqual(kospi_gain, top["ix_sum"], places=6)
        self.assertEqual(1, top["beat"])                 # +10% > 코스피
        self.assertEqual(0, table["breakout"]["n"])      # 매수금액 없는 줄은 안 센다
        self.assertEqual(0, table["crash"]["n"])         # 못 산 줄은 뺐다

    def test_compute_matches_the_table(self):
        ok, _blocked = j13vx.split_unfillable(_rows(), _frames())
        data = j13vx.compute(ok, _frames(), _kospi(), last_day=DAYS[-1].date())
        cum = [v for v in data["parts"]["top7"]["cum"] if v is not None]
        self.assertAlmostEqual(10.0, cum[-1], places=6)
        self.assertEqual(DAYS[2].date().isoformat(), data["days"][0])     # 산 날부터
        kospi_line = [v for v in data["index"]["all"] if v is not None]
        kospi_gain = (_kospi()["Close"].iloc[-1] / _kospi()["Open"].iloc[2] - 1.0) * 100.0
        self.assertAlmostEqual(round(kospi_gain, 2), kospi_line[-1], places=6)
        html = j13vx.cards_html(data, "all") + j13vx.line_chart_html(data, "all", "d")
        self.assertIn("같은 날 코스피", html)
        self.assertIn("<svg", html)
        bar, _note = j13vx.bar_chart_html(data, "all", "w")
        self.assertIn("<rect", bar)

    def test_last_day_cuts_the_count(self):
        ok, _blocked = j13vx.split_unfillable(_rows(), _frames())
        table = j13vx.part_table(ok, _frames(), _kospi(), last_day=DAYS[5].date())
        self.assertAlmostEqual(5.0, table["top7"]["sum"], places=6)   # 10/8 종가 105

    def test_names_are_the_korean_screen_names(self):
        import picklist_store

        self.assertEqual(("top7", "breakout", "pullback", "crash"), j13vx.PARTS)
        for kind in j13vx.PARTS:
            self.assertTrue(picklist_store.should_show(kind, "KR"), kind)
        self.assertNotIn("나스닥", "".join(j13vx.PART_NAMES.values()) + j13vx.INDEX_NAME)
        self.assertIn('div[class*="st-key-j13vx_t_"] button', j13vx.CSS)
        self.assertNotIn("j12vx_", j13vx.CSS)


class ScorecardPageTests(unittest.TestCase):
    def _app(self):
        extra = (
            patch("picklist_store.available_dates", return_value=["2026-10-02", "2026-10-06"]),
            patch("picklist_store.load_rows", side_effect=lambda day, market, out_dir=None:
                  [row for row in _rows() if row["trade_date"] == day]),
            patch("jarvis4_data.get_daily_frame", side_effect=lambda code, ttl_seconds=300: _frames().get(code)),
            patch("jarvis13_market.index_frame", return_value=_kospi()),
        )
        started = []
        for item in list(page_test._patches()) + list(extra):
            item.start()
            started.append(item)
        self.addCleanup(lambda: [item.stop() for item in reversed(started)])
        app = AppTest.from_file(str(page_test.PAGE), default_timeout=120)
        app.secrets["APP_PASSWORD"] = "test"
        app.session_state["authenticated"] = True
        app.session_state["j13sc_open"] = True
        app.run(timeout=120)
        return app

    def test_scorecard_opens_with_table_and_kospi_compare(self):
        app = self._app()
        self.assertEqual(0, len(app.exception), [e.value for e in app.exception])
        text = " ".join(str(m.value) for m in app.markdown)
        self.assertIn("📊 파트별 성적표", text)
        self.assertIn("매수심사결과 높은 순위 7", text)
        self.assertIn("📈 코스피와 견줘 보기", text)
        self.assertIn("못 산 것으로 빼고", text)
        self.assertIn("<td>1</td>", text)                 # 급락 줄 하나가 「못 산 줄」
        keys = {b.key for b in app.button}
        for key in ("j13sc_span_0", "j13sc_span_4", "j13vx_t_all", "j13vx_p_d", "j13vx_v_line", "close_j13sc_open"):
            self.assertIn(key, keys)

    def test_span_and_view_buttons_work(self):
        app = self._app()
        app.button(key="j13sc_span_0").click().run(timeout=120)       # 일주일
        self.assertEqual("일주일", app.session_state["j13sc_span"])
        app.button(key="j13vx_v_bar").click().run(timeout=120)        # 산 날마다(막대)
        self.assertEqual("bar", app.session_state["j13vx_view"])
        self.assertEqual(0, len(app.exception), [e.value for e in app.exception])

    def test_phone_rules_follow_the_j13_names(self):
        source = page_test.PAGE.read_text(encoding="utf-8")
        call = source.split("mobile_ui.page_css()", 1)[1].split("unsafe_allow_html", 1)[0]
        self.assertIn('.replace("st-key-j3sc_", "st-key-j13sc_")', call)
        self.assertIn('.replace("st-key-j3vx_", "st-key-j13vx_")', call)
        import mobile_ui

        css = mobile_ui.page_css().replace("st-key-j3sc_", "st-key-j13sc_").replace("st-key-j3vx_", "st-key-j13vx_")
        for name in ("j13sc_box", "j13sc_span_", "j13vx_row", "j13vx_rowtabs"):
            self.assertIn(f'div[class*="st-key-{name}"]', css, name)
        for key in ('key="j13sc_box"', 'key=f"j13sc_span_{index}"', 'key="j13vx_rowtabs"', 'key="j13vx_rowopts"'):
            self.assertIn(key, source)


if __name__ == "__main__":
    unittest.main()
