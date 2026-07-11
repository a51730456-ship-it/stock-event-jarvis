import ast
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace


SOURCE = Path("app.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
NAMES = {"_classify_actual_trade_status", "_today_progress_snapshot"}
FUNCTIONS = [node for node in TREE.body if isinstance(node, ast.FunctionDef) and node.name in NAMES]


class _DbStub:
    @staticmethod
    def normalize_actual_action(value):
        return value or "미기록"


namespace = {"db": _DbStub, "datetime": datetime}
exec(compile(ast.Module(body=FUNCTIONS, type_ignores=[]), "app.py", "exec"), namespace)


class TodayProgressTests(unittest.TestCase):
    def test_latest_market_report_only_and_item_counts(self):
        reports = [
            {"id": 1, "saved_at": "2026-07-11T08:00:00", "market_scope": "KR"},
            {"id": 2, "saved_at": "2026-07-11T09:00:00", "market_scope": "KR"},
            {"id": 3, "saved_at": "2026-07-10T09:00:00", "market_scope": "US"},
        ]
        items = {
            1: [{"actual_action": "미기록"}, {"actual_action": "미기록"}],
            2: [{"actual_action": "미기록"}, {"actual_action": "매수"}],
            3: [{"actual_action": "미기록"}],
        }
        result = namespace["_today_progress_snapshot"](reports, items, datetime(2026, 7, 11))
        self.assertTrue(result["kr_saved"])
        self.assertFalse(result["us_saved"])
        self.assertEqual(result["today_action_missing"], 1)
        self.assertEqual(result["holding"], 1)

    def test_duplicate_tickers_are_counted_as_items_and_review_done_excluded(self):
        reports = [{"id": 1, "saved_at": "2026-07-11T09:00:00", "market_scope": "KR"}]
        items = {
            1: [
                {"ticker": "A", "actual_action": "매수"},
                {"ticker": "A", "actual_action": "보류"},
                {"ticker": "B", "actual_action": "제외", "review_done": 1},
            ]
        }
        result = namespace["_today_progress_snapshot"](reports, items, datetime(2026, 7, 11))
        self.assertEqual(result["holding"], 1)
        self.assertEqual(result["review_pending"], 1)


if __name__ == "__main__":
    unittest.main()
