"""자비스12 관심종목 「넣은 날부터 성적」(2026-10-31 상하님 「자비스12에도 넣어라」)."""
from __future__ import annotations

import sqlite3
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

import jarvis12_watch_since as since

PAGE = Path(__file__).resolve().parent / "pages" / "11_자비스12.py"


def _frame(pairs):
    return pd.DataFrame({"Close": [value for _day, value in pairs]},
                        index=pd.to_datetime([day for day, _value in pairs]))


STOCK = _frame([("2026-10-26", 100.0), ("2026-10-27", 110.0), ("2026-10-28", 105.0),
                ("2026-10-29", 120.0), ("2026-10-30", 132.0)])
BENCH = _frame([("2026-10-26", 6000.0), ("2026-10-27", 6060.0), ("2026-10-28", 5940.0),
                ("2026-10-29", 6000.0), ("2026-10-30", 6120.0)])


class _Conn:
    def __init__(self, rows):
        self._db = sqlite3.connect(":memory:")
        self._db.execute("CREATE TABLE jarvis3_briefing_stocks (group_name TEXT, position INT, ticker TEXT,"
                         " stock_name TEXT, created_at TEXT, updated_at TEXT)")
        self._db.executemany("INSERT INTO jarvis3_briefing_stocks VALUES (?,?,?,?,?,?)", rows)

    def execute(self, sql, params=()):
        return self._db.execute(sql, params)

    def close(self):
        self._db.close()


class _Store:
    def __init__(self, rows, version=1):
        self.rows, self._ALL_MEMO = rows, {"version": version}

    def ensure_tables(self):
        pass

    def _connection(self):
        return _Conn(self.rows)


class RowTests(unittest.TestCase):
    def test_base_is_the_last_close_before_the_added_day(self):
        item = since.row("NVDA", "엔비디아", date(2026, 10, 28), STOCK, BENCH)
        self.assertEqual(date(2026, 10, 27), item["base_day"])          # 그 날 전 마지막 장
        self.assertAlmostEqual(20.0, item["since_pct"])                  # 110 → 132
        self.assertAlmostEqual(0.990099, item["bench_pct"], places=5)    # 6060 → 6120
        self.assertAlmostEqual(20.0 - 0.990099, item["beat_pp"], places=5)
        self.assertEqual(3, item["days"])

    def test_korean_daytime_add_uses_the_close_the_user_was_looking_at(self):
        # 한국 토요일 아침에 넣으면 날짜가 10-31 — 그 전 마지막 종가는 10-30 종가다.
        item = since.row("NVDA", "", date(2026, 10, 31), STOCK, BENCH)
        self.assertEqual(date(2026, 10, 30), item["base_day"])
        self.assertAlmostEqual(0.0, item["since_pct"])
        self.assertEqual(0, item["days"])

    def test_card_price_is_used_for_now_when_given(self):
        item = since.row("NVDA", "", date(2026, 10, 28), STOCK, BENCH, price_now=121.0)
        self.assertAlmostEqual(10.0, item["since_pct"])

    def test_added_before_the_data_leaves_blanks_not_zeros(self):
        item = since.row("NVDA", "", date(2026, 1, 5), STOCK, BENCH)
        self.assertIsNone(item["base"])
        self.assertIsNone(item["since_pct"])
        self.assertIsNone(item["beat_pp"])
        self.assertIsNone(item["bench_pct"])                             # 한쪽만 적지 않는다
        self.assertIn("6개월보다 앞 — 셈 안 함", since.table_html([item]))

    def test_missing_prices_leave_blanks(self):
        item = since.row("NVDA", "", date(2026, 10, 28), None, None)
        self.assertIsNone(item["now"])
        self.assertIsNone(item["bench_pct"])
        self.assertIn("<td>—</td>", since.table_html([item]))


class TableTests(unittest.TestCase):
    def test_table_scrolls_inside_itself_and_says_what_it_is(self):
        text = since.table_html([since.row("NVDA", "엔비디아", date(2026, 10, 28), STOCK, BENCH)])
        self.assertIn("overflow-x:auto", text)                  # 폰에서 화면 전체가 옆으로 넘치지 않게
        self.assertIn("넣은 날부터 성적", text)
        self.assertIn("같은 사이 S&amp;P 500", text.replace("S&P", "S&amp;P"))
        self.assertIn("+20.0%", text)
        self.assertIn("j12ws-up", text)
        self.assertIn("점수·판정에는 안 씁니다", text)
        self.assertIn("10월 28일", text)

    def test_empty_list_draws_nothing(self):
        self.assertEqual("", since.table_html([]))


class StoreTests(unittest.TestCase):
    def setUp(self):
        since._MEMO.update({"at": 0.0, "version": None, "value": None})

    def test_added_day_is_updated_at_and_the_earlier_of_two_groups(self):
        rows = [("selected", 1, "nvda", "엔비디아", "2026-09-10T09:00:00", "2026-10-20T22:10:00"),  # 자리 갈아 끼움
                ("extra", 1, "NVDA", "엔비디아", "2026-10-25T01:00:00", "2026-10-25T01:00:00"),
                ("extra_seed", 1, "-", "-", "2026-08-01T00:00:00", "2026-08-01T00:00:00"),      # 표식 줄은 안 본다
                ("extra", 2, "PLTR", "팔란티어", "2026-10-29T03:00:00", "2026-10-29T03:00:00")]
        self.assertEqual({"NVDA": date(2026, 10, 20), "PLTR": date(2026, 10, 29)}, since.added_map(_Store(rows)))

    def test_a_broken_store_gives_nothing(self):
        class Broken:
            _ALL_MEMO = {"version": 9}

            def ensure_tables(self):
                raise RuntimeError("db down")

        self.assertEqual({}, since.added_map(Broken()))


class PageTests(unittest.TestCase):
    def test_table_comes_after_both_card_grids(self):
        source = PAGE.read_text(encoding="utf-8")
        body = source.split("def _render_stock_briefing(")[1]
        extra_grid = body.index('_render_briefing_grid(home_extras, cards')
        table = body.index("_render_watch_since(visible_stocks, cards)")
        detail = body.index("_render_watch_detail_area(")
        self.assertLess(extra_grid, table)
        self.assertLess(table, detail)

    def test_revision_guard_matches_the_module(self):
        source = PAGE.read_text(encoding="utf-8")
        self.assertIn(f"_REQUIRED_J12_WATCH_SINCE_REVISION = {since.MODULE_REVISION}", source)

    def test_store_is_only_read(self):
        source = Path(since.__file__).read_text(encoding="utf-8")
        for word in ("INSERT", "UPDATE ", "DELETE", "commit("):
            self.assertNotIn(word, source)


if __name__ == "__main__":
    unittest.main()


class RenderTests(unittest.TestCase):
    def test_watch_page_draws_cards_then_the_table(self):
        from unittest.mock import patch
        from streamlit.testing.v1 import AppTest

        stocks = {"selected": [{"position": 1, "ticker": "NVDA", "name": "엔비디아"},
                               {"position": 2, "ticker": "PLTR", "name": "팔란티어"}], "extra": []}
        cards = {ticker: {"ticker": ticker, "name": ticker, "price": 132.0, "change_pct": 1.0,
                          "chart": [90, 95, 100], "stale": False} for ticker in ("NVDA", "PLTR")}

        def fake_download(tickers, **_kw):
            return {t: (BENCH if t == since.BENCH else STOCK) for t in tickers}, {"ok": True}

        with patch("jarvis3_briefing_store.ensure_tables"), \
             patch("jarvis3_briefing_store.all_stocks", return_value=stocks), \
             patch("jarvis3_data.get_briefing_cards", return_value=cards), \
             patch("jarvis3_data._download_cached", side_effect=fake_download), \
             patch("jarvis12_watch_since.added_map", return_value={"NVDA": date(2026, 10, 28)}), \
             patch("jarvis3_briefing_news.get_or_schedule", return_value={"ok": True, "items": []}):
            app = AppTest.from_file(str(PAGE), default_timeout=60)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
            app.session_state["jarvis_access_role"] = "owner"
            app.session_state["j12_briefing_page"] = "home"
            app.run(timeout=60)
        self.assertEqual(0, len(app.exception), [e.value for e in app.exception])
        rendered = [str(node.value) for node in app.markdown]
        table = [i for i, text in enumerate(rendered) if "넣은 날부터 성적" in text]
        self.assertEqual(1, len(table), "표가 한 번 그려져야 한다")
        cards_at = max(i for i, text in enumerate(rendered) if "j3b-card" in text)
        self.assertLess(cards_at, table[0])                  # 카드가 먼저 다 그려진 뒤
        self.assertIn("+20.0%", rendered[table[0]])          # 110(10-27 종가) → 132(카드 값)
        self.assertNotIn("PLTR</b>", rendered[table[0]])      # 넣은 날이 없는 종목은 표에 없다
