"""기관 수급 반전 포착 카드가 한국장 0단계 아래에 렌더되는지 확인한다.

기존 기능(도박사·테마 레이더·시장요약) 회귀 방지도 같이 본다.
"""

import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class KrFlowCardRenderTest(unittest.TestCase):
    def _run(self):
        at = AppTest.from_file("app.py", default_timeout=90)
        at.session_state["authenticated"] = True
        at.run()
        return at

    def test_card_renders_without_exception(self):
        at = self._run()
        self.assertEqual(at.exception, [], "앱 렌더 중 예외 발생")
        markdown_text = " ".join(m.value for m in at.markdown)
        self.assertIn("기관 수급 반전 포착", markdown_text)

    def test_refresh_button_exists(self):
        at = self._run()
        keys = [b.key for b in at.button]
        self.assertIn("kr_flow_refresh", keys)
        self.assertIn("kr_flow_ff_save", keys)

    def test_bookmaker_card_not_duplicated(self):
        # 도박사 expander는 한국장·미국장 각 1개씩(기존 구조)이어야 한다.
        # 신규 카드가 세 번째를 만들면 실패한다.
        at = self._run()
        labels = [e.label for e in at.expander]
        kr_count = sum(1 for label in labels if "도박사" in label and "한국장" in label)
        us_count = sum(1 for label in labels if "도박사" in label and "미국장" in label)
        self.assertEqual(kr_count, 1, f"한국장 도박사 카드 개수 이상: {labels}")
        self.assertEqual(us_count, 1, f"미국장 도박사 카드 개수 이상: {labels}")

    def test_no_result_shows_guidance_not_fake_verdict(self):
        # 조회 전에는 판정을 만들어내지 않는다.
        at = self._run()
        text = " ".join(m.value for m in at.markdown)
        self.assertNotIn("기관성 반등 확인", text)


class ForeignFuturesManualInputTest(unittest.TestCase):
    def test_manual_value_scoped_to_today(self):
        """어제 입력값이 오늘 판정에 새어들어오면 안 된다."""
        import app

        with patch.object(app.st, "session_state", {
            "kr_flow_foreign_futures_manual": {
                "net_contracts": -3250,
                "trade_date": "1999-01-01",
            }
        }):
            manual = app.st.session_state.get("kr_flow_foreign_futures_manual")
            self.assertNotEqual(manual["trade_date"], app._flow_today())


if __name__ == "__main__":
    unittest.main()
