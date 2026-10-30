"""자비스13 5단계 — 밑 막대 · 시장분석 먼저 · 한국 관심종목 (2026-10-30 상하님 「자비스13 관심종목 — 다해라」).

저장고는 임시 DB 로만 돌린다 — 진짜 기록(db/jarvis.sqlite3 · 온라인 원격 DB)은 건드리지 않는다.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

import jarvis13_watch as watch
import jarvis13_watch_store as store
import test_jarvis13_page as page_test

DAYS = pd.bdate_range(end="2026-10-29", periods=40)


def _frame(start=100_000.0, step=1_000.0):
    closes = [start + i * step for i in range(40)]
    return pd.DataFrame({"Open": closes, "High": closes, "Low": closes, "Close": closes, "Volume": 1.0}, index=DAYS)


def _temp_store(case: unittest.TestCase) -> None:
    folder = tempfile.TemporaryDirectory()
    case.addCleanup(folder.cleanup)
    patcher = patch.object(store, "DB_PATH", Path(folder.name) / "watch.sqlite3")
    patcher.start()
    case.addCleanup(patcher.stop)
    store._READY = False
    store._forget()

    def _reset():
        store._READY = False
        store._forget()
    case.addCleanup(_reset)


class StoreTests(unittest.TestCase):
    def setUp(self):
        _temp_store(self)

    def test_add_list_has_remove(self):
        store.add("005930", "삼성전자", price=71_000, kospi=2_500)
        store.add("000660", "SK하이닉스")
        rows = store.list_stocks()
        self.assertEqual(["005930", "000660"], [row["code"] for row in rows])
        self.assertEqual(71_000.0, rows[0]["added_price"])
        self.assertEqual(2_500.0, rows[0]["kospi_at_add"])
        self.assertIsNone(rows[1]["added_price"])             # 못 받은 값은 빈칸 — 0 으로 채우지 않는다
        self.assertTrue(store.has("005930"))
        self.assertTrue(store.remove("005930"))
        self.assertFalse(store.has("005930"))
        self.assertEqual(["000660"], [row["code"] for row in store.list_stocks()])

    def test_duplicate_and_full_are_refused_without_writing(self):
        store.add("005930", "삼성전자")
        with self.assertRaises(ValueError):
            store.add("005930", "삼성전자")
        for index in range(store.LIMIT - 1):
            store.add(f"{100000 + index:06d}", f"종목{index}")
        with self.assertRaises(ValueError):
            store.add("999999", "넘침")
        self.assertEqual(store.LIMIT, len(store.list_stocks()))

    def test_bad_codes_are_refused(self):
        for bad in ("", "12345", "1234567", "00593!", None):
            with self.assertRaises(ValueError):
                store.clean_code(bad)
        self.assertEqual("0001A0", store.clean_code(" 0001a0 "))   # 영문 섞인 새 코드도 받는다

    def test_target_price_is_saved_and_cleared(self):
        store.add("005930", "삼성전자")
        store.set_target("005930", 80_000)
        self.assertEqual(80_000.0, store.list_stocks()[0]["target_price"])
        store.set_target("005930", None)
        self.assertIsNone(store.list_stocks()[0]["target_price"])

    def test_list_is_remembered_and_forgotten_after_a_change(self):
        store.add("005930", "삼성전자")
        first = store.list_stocks()
        with patch.object(store, "_connection", side_effect=AssertionError("원격 DB 에 다시 묻지 않아야 한다")):
            self.assertEqual(first, store.list_stocks())
        store.add("000660", "SK하이닉스")                      # 바꾸면 바로 잊는다
        self.assertEqual(2, len(store.list_stocks()))


class CardTests(unittest.TestCase):
    def test_since_added_uses_the_saved_price_and_kospi(self):
        item = watch.card({"code": "005930", "name": "삼성전자", "added_at": "2026-10-20T10:00:00+09:00",
                           "added_price": 130_000.0, "kospi_at_add": 2_300.0}, _frame(), _frame(2_000, 10))
        self.assertTrue(item["ok"])
        self.assertAlmostEqual((139_000 / 130_000 - 1) * 100, item["since_pct"])
        self.assertAlmostEqual((2_390 / 2_300 - 1) * 100, item["kospi_pct"])
        self.assertAlmostEqual(item["since_pct"] - item["kospi_pct"], item["beat_pp"])
        self.assertAlmostEqual((139_000 / 138_000 - 1) * 100, item["change_pct"])
        self.assertEqual(watch.SPARK_DAYS, len(item["spark"]))
        self.assertEqual(7, item["days"])                       # 10/21 · 22 · 23 · 26 · 27 · 28 · 29

    def test_missing_saved_price_falls_back_to_the_close_that_day(self):
        frame = _frame()
        item = watch.card({"code": "005930", "name": "삼성전자", "added_at": "2026-10-27T16:00:00+09:00"}, frame, None)
        self.assertEqual(float(frame.loc["2026-10-27", "Close"]), item["base"])
        self.assertIsNone(item["kospi_pct"])                    # 코스피를 못 받으면 빈칸
        self.assertIsNone(item["beat_pp"])

    def test_failed_quote_keeps_the_card(self):
        item = watch.card({"code": "005930", "name": "삼성전자", "added_at": "2026-10-27"}, None, None)
        self.assertFalse(item["ok"])
        self.assertIn("시세를 못 받았습니다", watch.card_html(item))

    def test_card_html_is_in_won_with_korean_colors(self):
        item = watch.card({"code": "005930", "name": "삼성<전자>", "added_at": "2026-10-20T10:00:00+09:00",
                           "added_price": 130_000.0, "kospi_at_add": 2_300.0}, _frame(), _frame(2_000, 10))
        text = watch.card_html(item)
        self.assertIn("139,000원", text)
        self.assertIn("넣은 날 10월 20일 · 130,000원 · 7거래일째", text)
        self.assertIn("코스피보다", text)
        self.assertIn("j4-up", text)                            # 오르면 빨강(한국장 색)
        self.assertIn("삼성&lt;전자&gt;", text)                  # 이름은 그대로 보이게 바꿔 적는다

    def test_load_frames_survives_one_failure(self):
        def loader(code):
            if code == "000660":
                raise RuntimeError("막힘")
            return _frame()
        frames = watch.load_frames(["005930", "000660"], loader)
        self.assertIsNotNone(frames["005930"])
        self.assertIsNone(frames["000660"])


class PageTests(unittest.TestCase):
    def _app(self, *, page=None, guest=False, stocks=(), details=False):
        _temp_store(self)
        for code, name, price, kospi in stocks:
            store.add(code, name, price=price, kospi=kospi)
        started = []
        extra = [patch("jarvis4_data.get_daily_frame", return_value=_frame()),
                 patch("jarvis13_market.index_frame", return_value=_frame(2_000, 10))]
        for item in list(page_test._patches()) + extra:
            item.start()
            started.append(item)
        self.addCleanup(lambda: [item.stop() for item in reversed(started)])
        app = AppTest.from_file(str(page_test.PAGE), default_timeout=120)
        app.secrets["APP_PASSWORD"] = "test"
        app.session_state["authenticated"] = True
        if details:
            page_test._open_all_details(app)
        if guest:
            app.session_state["jarvis_access_role"] = "guest"
        if page:
            app.session_state["j13_briefing_page"] = page
        app.run(timeout=120)
        self.assertEqual(0, len(app.exception), [e.value for e in app.exception])
        return app

    @staticmethod
    def _text(app) -> str:
        return " ".join(str(m.value) for m in app.markdown)

    def test_market_comes_first_with_the_bottom_bar(self):
        app = self._app()
        keys = {button.key for button in app.button}
        self.assertTrue({"j13b_nav_home", "j13b_nav_market", "j13b_nav_watch"} <= keys)
        text = self._text(app)
        self.assertIn('<nav class="j13b-bottom-nav">', text)
        self.assertIn('<span class="j13b-nav-item active"><b><svg class="j13b-pie"', text)   # 시장분석이 켜져 있다
        self.assertIn("테마·종목", [option for radio in app.radio for option in radio.options])

    def test_the_bar_order_is_home_market_watch(self):
        text = self._text(self._app())
        nav = text[text.index('<nav class="j13b-bottom-nav">'):]
        self.assertLess(nav.index("홈"), nav.index("시장분석"))
        self.assertLess(nav.index("시장분석"), nav.index("관심종목"))

    def test_bar_switches_to_the_watch_page(self):
        app = self._app()
        next(button for button in app.button if button.key == "j13b_nav_watch").click()
        app.run(timeout=120)
        self.assertEqual(0, len(app.exception), [e.value for e in app.exception])
        self.assertIn("★ 관심종목", self._text(app))
        self.assertEqual("watch", app.session_state["j13_briefing_page"])
        self.assertNotIn("테마·종목", [option for radio in app.radio for option in radio.options])

    def test_empty_watch_page_says_how_to_add(self):
        app = self._app(page="watch")
        self.assertIn("아직 넣은 종목이 없습니다", self._text(app))
        self.assertIn("j13w_query", {box.key for box in app.text_input})

    def test_watch_cards_show_since_added_against_kospi(self):
        app = self._app(page="watch", stocks=[("005930", "삼성전자", 130_000, 2_300)])
        text = self._text(app)
        self.assertIn("삼성전자", text)
        self.assertIn("넣은 날", text)
        self.assertIn("같은 사이 코스피", text)
        keys = {button.key for button in app.button}
        self.assertIn("j13w_open_005930", keys)
        self.assertIn("j13w_remove_005930", keys)

    def test_guest_sees_the_list_but_cannot_change_it(self):
        app = self._app(page="watch", guest=True, stocks=[("005930", "삼성전자", 130_000, 2_300)])
        keys = {button.key for button in app.button}
        self.assertIn("j13w_open_005930", keys)
        self.assertNotIn("j13w_remove_005930", keys)
        self.assertNotIn("j13w_query", {box.key for box in app.text_input})

    def test_remove_button_takes_it_off(self):
        app = self._app(page="watch", stocks=[("005930", "삼성전자", 130_000, 2_300)])
        next(button for button in app.button if button.key == "j13w_remove_005930").click()
        app.run(timeout=120)
        self.assertEqual([], store.list_stocks())
        self.assertIn("뺐습니다", " ".join(str(item.value) for item in app.success))

    def test_buttons_sit_on_one_line_under_each_card(self):
        app = self._app(page="watch", stocks=[("005930", "삼성전자", 130_000, 2_300)])
        source = page_test.PAGE.read_text(encoding="utf-8")
        body = source[source.index("def _render_watch_page"):source.index("def main()")]
        self.assertIn("st.container(horizontal=True", body)          # 세부사항 · 빼기 한 줄
        self.assertIn("j13w-grid", self._text(app))                  # 세 값은 칸 셋에

    def test_removing_inside_the_watch_detail_closes_it_and_says_so_on_top(self):
        app = self._app(page="watch", stocks=[("005930", "삼성전자", 130_000, 2_300)])
        next(button for button in app.button if button.key == "j13w_open_005930").click()
        app.run(timeout=120)
        self.assertIn("j13w_toggle_watch_005930", {button.key for button in app.button})
        next(button for button in app.button if button.key == "j13w_toggle_watch_005930").click()
        app.run(timeout=120)
        self.assertEqual(0, len(app.exception), [e.value for e in app.exception])
        self.assertEqual([], store.list_stocks())
        self.assertIn("뺐습니다", " ".join(str(item.value) for item in app.success))   # 세부사항이 닫혀도 알림은 뜬다
        self.assertNotIn("j13w_toggle_watch_005930", {button.key for button in app.button})

    def test_a_message_lives_for_one_run_only(self):
        app = self._app(page="watch")
        app.session_state["j13w_msg"] = ("옛 알림", "ok", "detail_theme")   # 그 판에 안 그려지는 자리
        app.run(timeout=120)
        app.run(timeout=120)
        self.assertNotIn("옛 알림", " ".join(str(item.value) for item in app.success))
        self.assertIsNone(app.session_state["j13w_msg_now"])           # 다음 판에는 버려져 있다

    def test_detail_offers_add_to_the_owner_only(self):
        app = self._app(details=True)
        keys = {button.key for button in app.button}
        self.assertIn("j13w_toggle_theme_000660", keys)
        next(button for button in app.button if button.key == "j13w_toggle_theme_000660").click()
        app.run(timeout=120)
        saved = store.list_stocks()
        self.assertEqual(["000660"], [row["code"] for row in saved])
        self.assertIsNotNone(saved[0]["added_price"])           # 넣는 순간의 값을 적는다
        self.assertEqual(2_390.0, saved[0]["kospi_at_add"])     # 그때 코스피도
        guest = self._app(details=True, guest=True)
        self.assertNotIn("j13w_toggle_theme_000660", {button.key for button in guest.button})


if __name__ == "__main__":
    unittest.main()
