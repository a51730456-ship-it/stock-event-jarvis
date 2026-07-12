import re
import unittest
from pathlib import Path


SOURCE = Path(__file__).with_name("app.py").read_text(encoding="utf-8")


class TabletStructureTests(unittest.TestCase):
    def test_detail_inputs_are_guarded_by_one_selection(self):
        self.assertIn('key="kr_snapshot_detail_selector"', SOURCE)
        self.assertIn('key="us_snapshot_detail_selector"', SOURCE)
        self.assertIn('if _kr_detail_selected != s["name"]:', SOURCE)
        self.assertIn('if _us_detail_selected != s["name"]:', SOURCE)
        self.assertEqual(SOURCE.count('key="kr_snapshot_detail_selector"'), 1)
        self.assertEqual(SOURCE.count('key="us_snapshot_detail_selector"'), 1)

    def test_theme_detail_has_single_selection_guard(self):
        self.assertIn('key="kr_theme_detail_selector"', SOURCE)
        self.assertIn('if theme_name == _theme_detail_selected:', SOURCE)
        self.assertEqual(SOURCE.count('with st.expander("세부 입력", expanded=True):'), 1)

    def test_tablet_layout_has_no_four_card_market_assumption(self):
        self.assertIn('market_overview_cards_kr', SOURCE)
        self.assertIn('market_overview_cards_us', SOURCE)
        self.assertIn('grid-template-columns: repeat(2, minmax(0, 1fr))', SOURCE)
        self.assertIn('grid-template-columns: minmax(0, 1fr)', SOURCE)


if __name__ == "__main__":
    unittest.main()
