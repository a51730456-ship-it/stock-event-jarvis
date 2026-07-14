import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).parent
SOURCE = (ROOT / "app.py").read_text(encoding="utf-8")
TEST_PASSWORD = "jarvis-us-stage2-preview-test"


def _new_app():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90)
    app.secrets["APP_PASSWORD"] = TEST_PASSWORD
    return app


class USStage2PreviewStructureTests(unittest.TestCase):
    def test_build_us_stage2_preview_reuses_existing_swing_score_engine(self):
        # 2026-07-15 사용자 반복 요청: 한국장의 "2단계 판단 미리보기"와 동일한 형태를
        # 미국장에도 만든다. 새 점수 공식을 만들지 않고 기존 compute_us_swing_breakdown()을
        # 재사용해야 한다 — "② 미국장 스윙 계산 결과"와 다른 결과가 나오면 안 된다.
        preview_fn = SOURCE[
            SOURCE.index("def build_us_stage2_preview():"):
            SOURCE.index("def _build_item_text_lookup():")
        ]
        self.assertIn("compute_us_swing_breakdown(", preview_fn)
        self.assertIn("US_SNAPSHOT_STOCKS", preview_fn)

    def test_us_tab_renders_stage2_preview_before_theme_radar(self):
        us_tab = SOURCE[SOURCE.index("def _render_tab_us():"):SOURCE.index("with tab_us:\n    _render_tab_us()")]
        preview_at = us_tab.index("build_us_stage2_preview()")
        theme_radar_at = us_tab.index("미국장 테마 레이더 1차 참고판")
        self.assertLess(preview_at, theme_radar_at)


class USStage2PreviewRuntimeTests(unittest.TestCase):
    def test_preview_table_and_reason_cards_render(self):
        def snap_side_effect(ticker):
            turnovers = {"TSLA": 300.0, "AMD": 900.0, "AAPL": 400.0}
            return {
                "ok": True, "current": 105.0, "prev_close": 100.0, "open": 101.0,
                "high": 106.0, "low": 99.0, "turnover": turnovers.get(ticker, 50.0),
                "market_cap": 1000000.0, "as_of_date": "2026-07-15", "as_of_time": None,
                "data_kind": "daily_close",
            }

        with patch("bookmaker_data.fetch_bookmaker_snapshot") as mock_bm, \
             patch("deepl_translate.translate_texts_to_ko") as mock_dl, \
             patch("theme_data.fetch_us_sector_snapshot") as mock_us_sector, \
             patch("theme_data.fetch_us_theme_indicators") as mock_us_theme, \
             patch("theme_data.fetch_kr_theme_snapshot") as mock_kr_theme, \
             patch("price_data.get_snapshot_defaults", side_effect=snap_side_effect), \
             patch("price_data.get_top_kr_stocks_by_amount") as mock_top:

            mock_bm.return_value = {"ok": True, "errors": [], "events": []}
            mock_dl.return_value = {"ok": True, "translations": {}}
            mock_us_sector.return_value = {"ok": True, "checked_at": "x", "sectors": []}
            mock_us_theme.return_value = {"ok": True, "checked_at": "x", "values": {}}
            mock_kr_theme.return_value = {"ok": True, "error": None, "checked_at": "x", "themes": {}}
            mock_top.return_value = [{"name": "삼성전자", "ticker": "005930.KS", "sector": "반도체"}]

            app = _new_app()
            app.run(timeout=90)
            app.text_input[0].set_value(TEST_PASSWORD)
            app.button[0].click().run(timeout=90)
            self.assertEqual(len(app.exception), 0)

            self.assertTrue(
                any("미국 종목 판단 미리보기" in str(node.value) for node in app.markdown)
            )
            self.assertTrue(
                any("종목별 1순위 근거" in str(node.value) for node in app.markdown)
            )
            self.assertGreater(len(app.dataframe), 0)


if __name__ == "__main__":
    unittest.main()
