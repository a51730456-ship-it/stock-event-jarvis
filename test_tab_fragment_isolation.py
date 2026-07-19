import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).parent
TEST_PASSWORD = "jarvis-fragment-isolation-test"

SOURCE = (ROOT / "app.py").read_text(encoding="utf-8")


def _new_app():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90)
    app.secrets["APP_PASSWORD"] = TEST_PASSWORD
    return app


class TabFragmentStructureTests(unittest.TestCase):
    def test_kr_and_us_tabs_are_wrapped_in_fragments(self):
        # 2026-07-15 사용자 요청: 다른 탭에서 아무 버튼이나 눌러도 한국장/미국장 탭
        # 전체가 다시 그려지며 느려지는 문제 — st.fragment로 KR/US 탭을 분리해서
        # 그 탭 안의 위젯 상호작용이 다른 탭 코드를 다시 실행하지 않게 한다.
        self.assertIn("@st.fragment\ndef _render_tab_kr():", SOURCE)
        self.assertIn("@st.fragment\ndef _render_tab_us():", SOURCE)
        self.assertIn("with tab_kr:\n    _render_tab_kr()", SOURCE)
        self.assertIn("with tab_us:\n    _render_tab_us()", SOURCE)


class TabFragmentIsolationRuntimeTests(unittest.TestCase):
    def test_clicking_kr_button_does_not_rerun_us_tab_fetches(self):
        with patch("bookmaker_data.fetch_bookmaker_snapshot") as mock_bm, \
             patch("deepl_translate.translate_texts_to_ko") as mock_dl, \
             patch("theme_data.fetch_us_sector_snapshot") as mock_us_sector, \
             patch("theme_data.fetch_us_theme_indicators") as mock_us_theme, \
             patch("theme_data.fetch_kr_theme_snapshot") as mock_kr_theme, \
             patch("price_data.get_snapshot_defaults") as mock_snap, \
             patch("price_data.get_top_kr_stocks_by_amount") as mock_top:

            mock_bm.return_value = {"ok": True, "errors": [], "events": []}
            mock_dl.return_value = {"ok": True, "translations": {}}
            mock_us_sector.return_value = {"ok": True, "checked_at": "x", "sectors": []}
            mock_us_theme.return_value = {"ok": True, "checked_at": "x", "values": {}}
            mock_kr_theme.return_value = {"ok": True, "error": None, "checked_at": "x", "themes": {}}
            mock_snap.return_value = {
                "ok": True, "current": 100.0, "prev_close": 99.0, "open": 99.5,
                "high": 101.0, "low": 98.0, "turnover": 1000.0, "market_cap": 1000000.0,
                "as_of_date": "2026-07-15", "as_of_time": None, "data_kind": "daily_close",
            }
            mock_top.return_value = [{"name": "삼성전자", "ticker": "005930.KS", "sector": "반도체"}]

            app = _new_app()
            app.run(timeout=90)
            app.radio[0].set_value("자비스1 (기록장)")
            app.text_input[0].set_value(TEST_PASSWORD)
            app.button[0].click().run(timeout=90)
            self.assertEqual(len(app.exception), 0)

            us_sector_calls_before = mock_us_sector.call_count
            us_theme_calls_before = mock_us_theme.call_count

            kr_prepare_btn = next(b for b in app.button if b.key == "kr_auto_preview_run")
            kr_prepare_btn.click().run(timeout=90)
            self.assertEqual(len(app.exception), 0)

            self.assertEqual(
                us_sector_calls_before, mock_us_sector.call_count,
                "US sector fetch was re-invoked by a KR-tab button click",
            )
            self.assertEqual(
                us_theme_calls_before, mock_us_theme.call_count,
                "US theme fetch was re-invoked by a KR-tab button click",
            )


if __name__ == "__main__":
    unittest.main()
