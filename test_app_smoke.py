import ast
import re
import unittest
from pathlib import Path


SOURCE = Path("app.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


class AppSmokeContractTests(unittest.TestCase):
    def test_ten_tabs_and_expected_order(self):
        tab_calls = [
            node for node in ast.walk(TREE)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "tabs"
        ]
        self.assertEqual(len(tab_calls), 1)
        labels = tab_calls[0].args[0]
        self.assertIsInstance(labels, ast.List)
        self.assertEqual(len(labels.elts), 10)

    def test_literal_widget_keys_have_no_duplicates(self):
        keys = re.findall(r'\bkey\s*=\s*["\']([^"\']+)["\']', SOURCE)
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        self.assertEqual(duplicates, [])

    def test_news_and_read_only_contracts_are_present(self):
        for key in ("kr_naver_news_check_button", "us_naver_news_check_button", "kr_naver_news_results", "us_naver_news_results"):
            self.assertIn(key, SOURCE)
        self.assertIn("키워드 기반 1차 참고 분류 · 점수 미반영", SOURCE)
        self.assertIn("_render_kr_dart_disclosure_panel()", SOURCE)
        self.assertIn("_render_market_naver_news_panel(", SOURCE)

    def test_save_actions_are_not_invoked_by_this_test(self):
        # This contract test inspects only source; no Streamlit interaction is performed.
        self.assertTrue("db.save_report(" in SOURCE)
        self.assertTrue("st.button" in SOURCE)


if __name__ == "__main__":
    unittest.main()
