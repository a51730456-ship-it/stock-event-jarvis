import unittest
from pathlib import Path


SOURCE = Path("app.py").read_text(encoding="utf-8")


class SelectedActionReviewContractTests(unittest.TestCase):
    def test_default_filters_and_id_based_selection_are_present(self):
        self.assertIn('["행동 미입력", "보유 중", "거래 종료", "전체"]', SOURCE)
        self.assertIn('["복기 대기", "복기 완료", "전체"]', SOURCE)
        self.assertIn('key="tab3_selected_item_id"', SOURCE)
        self.assertIn('key="tab4_selected_item_id"', SOURCE)
        self.assertIn('f"#{item[\'id\']} ·', SOURCE)

    def test_detail_renderers_are_guarded_by_one_selected_item(self):
        self.assertIn('if _tab3_selected_item is not None:', SOURCE)
        self.assertIn('if _tab4_selected_item is not None:', SOURCE)
        self.assertIn('_render_actual_trade_entry_inputs(_tab3_item, key_prefix="tab3_")', SOURCE)
        self.assertIn('_render_review_tag_editors(', SOURCE)
        self.assertIn('db.update_report_item_actual_action', SOURCE)
        self.assertIn('db.update_report_item_review', SOURCE)

    def test_selection_is_cleared_when_filter_removes_item(self):
        self.assertIn('st.session_state.pop("tab3_selected_item_id", None)', SOURCE)
        self.assertIn('st.session_state.pop("tab4_selected_item_id", None)', SOURCE)


if __name__ == "__main__":
    unittest.main()
