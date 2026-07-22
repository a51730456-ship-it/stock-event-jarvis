"""자비스4 매수 기록 저장소 테스트 — 기존 테이블을 건드리지 않는지도 함께 본다."""

import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

import jarvis4_store as store


class Jarvis4StoreTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.connection = sqlite3.connect(str(Path(self._temp.name) / "test.sqlite3"))
        self.connection.row_factory = sqlite3.Row
        store.ensure_tables(self.connection)

    def tearDown(self):
        self.connection.close()
        self._temp.cleanup()

    def _save(self, **overrides):
        payload = {
            "code": "000660",
            "stock_name": "SK하이닉스",
            "theme_name": "반도체/HBM",
            "buy_date": date(2026, 7, 22),
            "buy_price": 1_990_000,
            "quantity": 1,
            "trade_style": "스윙",
            "entry_setup": "눌림목 대기",
            "market_score": 60,
            "theme_score": 85,
            "stock_score": 88,
            "flow_score": 17,
            "flow_net5_amount": 3.21e11,
            "connection": self.connection,
        }
        payload.update(overrides)
        return store.save_trade(**payload)

    def test_save_and_list_trade(self):
        trade_id = self._save()
        self.assertIsNotNone(trade_id)
        rows = store.list_trades(connection=self.connection)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["code"], "000660")
        self.assertEqual(rows[0]["status"], "보유")
        self.assertEqual(rows[0]["trade_style"], "스윙")

    def test_danta_style_is_allowed(self):
        """자비스4는 1차부터 단타를 포함한다(사용자 지시)."""
        self._save(trade_style="단타")
        self.assertEqual(store.list_trades(connection=self.connection)[0]["trade_style"], "단타")

    def test_invalid_trade_style_rejected(self):
        with self.assertRaises(ValueError):
            self._save(trade_style="스캘핑")

    def test_zero_price_rejected(self):
        with self.assertRaises(ValueError):
            self._save(buy_price=0)

    def test_close_trade_computes_result_pct(self):
        trade_id = self._save(buy_price=100_000)
        store.close_trade(
            trade_id, sell_date=date(2026, 7, 24), sell_price=110_000, connection=self.connection
        )
        row = store.list_trades(connection=self.connection)[0]
        self.assertEqual(row["status"], "청산")
        self.assertAlmostEqual(row["result_pct"], 10.0, places=6)

    def test_sell_before_buy_rejected(self):
        trade_id = self._save(buy_date=date(2026, 7, 22))
        with self.assertRaises(ValueError):
            store.close_trade(
                trade_id, sell_date=date(2026, 7, 21), sell_price=1_000, connection=self.connection
            )

    def test_double_close_rejected(self):
        trade_id = self._save()
        store.close_trade(
            trade_id, sell_date=date(2026, 7, 23), sell_price=2_000_000, connection=self.connection
        )
        with self.assertRaises(ValueError):
            store.close_trade(
                trade_id, sell_date=date(2026, 7, 24), sell_price=2_100_000, connection=self.connection
            )

    def test_progress_counts(self):
        self._save()
        second = self._save(code="005930", stock_name="삼성전자")
        store.close_trade(
            second, sell_date=date(2026, 7, 23), sell_price=2_000_000, connection=self.connection
        )
        progress = store.trade_progress(connection=self.connection)
        self.assertEqual(progress["total_count"], 2)
        self.assertEqual(progress["open_count"], 1)
        self.assertEqual(progress["closed_count"], 1)
        self.assertEqual(progress["minimum_sample"], 30)

    def test_uses_separate_table_from_jarvis3(self):
        """자비스3 기록 테이블과 절대 섞이면 안 된다."""
        self._save()
        names = {
            row[0] for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        self.assertIn("jarvis4_trades", names)
        self.assertNotIn("jarvis3_trades", names)
        self.assertNotIn("reports", names)


if __name__ == "__main__":
    unittest.main()
