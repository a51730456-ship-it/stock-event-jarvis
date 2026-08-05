import sqlite3
import unittest

import db_runtime
import jarvis3_store as store


class Jarvis3StoreTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        store.ensure_tables(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_save_trade_preserves_entry_context_and_date(self):
        trade_id = store.save_trade(
            ticker="nvda",
            stock_name="NVIDIA",
            theme_name="반도체",
            buy_date="2026-07-19",
            buy_price=184.2,
            quantity=3,
            trade_style="스윙",
            entry_setup="눌림목 대기",
            recommendation_state="조건부 후보",
            market_regime="상승 여건 양호",
            market_score=85,
            theme_score=91,
            stock_score=88,
            entry_plan={"trigger": 184.2, "invalidation": 178.8},
            snapshot={"source_time": "2026-07-19T13:00:00+09:00"},
            memo="실제 체결",
            connection=self.conn,
        )
        self.assertIsNotNone(trade_id)
        rows = store.list_trades(connection=self.conn)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["ticker"], "NVDA")
        self.assertEqual(rows[0]["buy_date"], "2026-07-19")
        self.assertEqual(rows[0]["buy_price"], 184.2)
        self.assertIn('"trigger":184.2', rows[0]["entry_plan_json"])
        self.assertEqual(rows[0]["status"], "보유")

    def test_close_trade_calculates_result_and_rejects_bad_date(self):
        trade_id = store.save_trade(
            ticker="NVDA", stock_name="NVIDIA", theme_name="반도체",
            buy_date="2026-07-19", buy_price=100, trade_style="스윙",
            connection=self.conn,
        )
        with self.assertRaises(ValueError):
            store.close_trade(trade_id, sell_date="2026-07-18", sell_price=110, connection=self.conn)
        store.close_trade(trade_id, sell_date="2026-07-20", sell_price=110, connection=self.conn)
        row = store.list_trades(connection=self.conn)[0]
        self.assertEqual(row["status"], "청산")
        self.assertAlmostEqual(row["result_pct"], 10.0)

    def test_invalid_price_never_enters_database(self):
        with self.assertRaises(ValueError):
            store.save_trade(
                ticker="NVDA", stock_name="NVIDIA", theme_name="반도체",
                buy_date="2026-07-19", buy_price=float("nan"), trade_style="스윙",
                connection=self.conn,
            )
        self.assertEqual(store.trade_progress(connection=self.conn)["total_count"], 0)

    def test_libsql_compat_adapter_keeps_same_crud_contract(self):
        raw = sqlite3.connect(":memory:")
        adapted = db_runtime.ConnectionAdapter(raw)
        try:
            store.ensure_tables(adapted)
            trade_id = store.save_trade(
                ticker="PANW", stock_name="Palo Alto Networks", theme_name="사이버보안",
                buy_date="2026-07-19", buy_price=210.5, trade_style="스윙",
                connection=adapted,
            )
            self.assertIsNotNone(trade_id)
            rows = store.list_trades(connection=adapted)
            self.assertEqual(rows[0]["ticker"], "PANW")
            self.assertEqual(store.trade_progress(connection=adapted)["open_count"], 1)
        finally:
            adapted.close()


if __name__ == "__main__":
    unittest.main()
