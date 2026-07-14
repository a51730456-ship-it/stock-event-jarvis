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

    def test_judgment_prepare_has_one_primary_and_two_recovery_buttons(self):
        self.assertIn('"오늘 종목 판단 준비하기"', SOURCE)
        self.assertIn('key="kr_auto_preview_run"', SOURCE)
        self.assertIn('"문제가 있을 때 단계별 다시 실행"', SOURCE)
        self.assertIn('key="snap_mood_auto_check"', SOURCE)
        self.assertIn('key="snap_auto_fill"', SOURCE)
        self.assertIn('판단 준비 완료: 시장 분위기 확인 / 오늘 주가 입력 / 미리보기 생성', SOURCE)

    def test_candidate_cards_are_restored_and_linked_to_existing_selection(self):
        self.assertIn('rows_by_ticker = {row["ticker"]: row for row in sorted_rows}', SOURCE)
        self.assertIn('mockup1_candidate_', SOURCE)
        # Streamlit은 selectbox가 생성된 뒤 같은 실행 안에서 위젯 키를 직접 바꾸면
        # StreamlitAPIException이 날 수 있다. 후보 카드 클릭은 pending 키에 저장하고,
        # 다음 rerun에서 selectbox 생성 전에 기존 선택 키로 옮기는 구조를 검증한다.
        pending_read = 'pending_ticker = st.session_state.pop("mockup1_pending_ticker", None)'
        selected_write = 'st.session_state["mockup1_selected_ticker"] = pending_ticker'
        selectbox_key = 'key="mockup1_selected_ticker"'
        pending_write = 'st.session_state["mockup1_pending_ticker"] = row["ticker"]'
        for marker in (pending_read, selected_write, selectbox_key, pending_write):
            self.assertIn(marker, SOURCE)
        self.assertLess(SOURCE.index(pending_read), SOURCE.index(selected_write))
        self.assertLess(SOURCE.index(selected_write), SOURCE.index(selectbox_key))
        self.assertLess(SOURCE.index(selectbox_key), SOURCE.index(pending_write))
        self.assertIn('left_col, right_col = st.columns([0.34, 0.66]', SOURCE)
        self.assertNotIn('for row in enumerate([])', SOURCE)

    def test_theme_cards_are_not_rendered_and_table_is_present(self):
        self.assertIn('for index, row in enumerate([]):', SOURCE)
        self.assertIn('"현재 상태"', SOURCE)
        self.assertIn('"세부 입력"', SOURCE)
        self.assertIn('key="kr_theme_detail_selector"', SOURCE)


if __name__ == "__main__":
    unittest.main()
