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

    def test_readability_and_core_button_css_contract(self):
        self.assertIn("font-size: 16px", SOURCE)
        self.assertIn("font-size: 15px !important", SOURCE)
        self.assertIn("color: #d1d5db !important", SOURCE)
        self.assertIn("font-size: 17px !important", SOURCE)
        self.assertIn("min-height: 44px !important", SOURCE)
        for key in (
            "snap_auto_fill", "us_stock_auto_fill", "snap_mood_auto_check",
            "kr_dart_check_button", "kr_naver_news_check_button", "us_naver_news_check_button",
            "kr_quick_save", "kr_quick_confirm_save", "us_swing_quick_save", "us_final_save",
        ):
            self.assertIn(f"st-key-{key}", SOURCE)
        self.assertIn('[class*="st-key-tab3_"] button', SOURCE)
        self.assertIn('[class*="st-key-tab4_"] button', SOURCE)
        self.assertIn("저장한 종목 판단이 며칠 뒤 실제 수익률로 어떻게 나왔는지 확인하는 화면입니다.", SOURCE)
        self.assertNotIn('st.caption("? ??? ?? ?????. ?? ??? ?? ??? ? ??????? ???.")', SOURCE)

    def test_save_actions_are_not_invoked_by_this_test(self):
        # This contract test inspects only source; no Streamlit interaction is performed.
        self.assertTrue("db.save_report(" in SOURCE)
        self.assertTrue("st.button" in SOURCE)

    def test_performance_data_load_gate_contract(self):
        self.assertIn('PERFORMANCE_DATA_LOAD_KEY = "performance_data_load_requested"', SOURCE)
        self.assertIn('"tab4_performance_data_load_button"', SOURCE)
        self.assertIn('"perf_performance_data_load_button"', SOURCE)
        self.assertIn("성과 시세 데이터 불러오기", SOURCE)
        self.assertIn("성과 시세 데이터 미조회", SOURCE)
        self.assertIn("1·3·5·10·20일 성과 확인이 필요할 때만 불러옵니다.", SOURCE)
        self.assertEqual(SOURCE.count("performance.build_verification_rows()"), 1)
        self.assertIn("if _tab4_performance_ready", SOURCE)
        self.assertIn("if _perf_performance_ready", SOURCE)
        self.assertIn("if _perf_performance_ready\n            else []", SOURCE)


if __name__ == "__main__":
    unittest.main()
