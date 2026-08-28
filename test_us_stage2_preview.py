import unittest
from pathlib import Path
from unittest.mock import patch

import page_access

# 이 시험은 **자비스1 화면을 지나간다.** 그 화면이 닫혀 있으면(2026-08-28 상하님
# 지시) 로그인 뒤 「어디로 갈까요」에 자비스1 단추가 없어 길이 막힌다. 시험이
# 틀린 것이 아니라 길이 막힌 것이므로 건너뛴다 — `page_access.OPEN_PAGES` 에
# 이름을 다시 넣으면 저절로 다시 돈다.
_JARVIS1_OPEN = page_access.is_open("자비스1")
_JARVIS1_WHY = "자비스1 화면을 닫아 두어(page_access.OPEN_PAGES) 이 길이 막혀 있다"

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).parent
SOURCE = (ROOT / "app.py").read_text(encoding="utf-8")
TEST_PASSWORD = "jarvis-us-stage2-preview-test"

# **로그인 화면에는 갈 곳 고르기가 없다**(2026-08-09 상하님 지시로 뺐다).
# 예전에는 라디오로 갈 곳을 고르고 로그인했는데, 그때 st.switch_page가 주소를
# 기록에 하나 더 쌓아 폰 뒤로가기가 맨홈을 두 번 보여 줬다. 지금은
#   ① 비밀번호 → 로그인  ② '어디로 갈까요' 화면에서 갈 곳을 누른다
# 이고, 자비스1만 링크가 아니라 단추(key="entry_go")다 — 옮겨 갈 페이지가 아니라
# app.py 자신이기 때문이다. 시험도 그 순서를 그대로 따라간다.
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

    def test_us_tab_renders_previews_before_theme_board(self):
        us_tab = SOURCE[SOURCE.index("def _render_tab_us():"):SOURCE.index("with tab_us:\n    _render_tab_us()")]
        rich_preview_at = us_tab.index("_render_us_stock_judgment_preview()")
        table_preview_at = us_tab.index("build_us_stage2_preview()")
        theme_board_at = us_tab.index("테마 참고판 (미국)")
        self.assertLess(rich_preview_at, table_preview_at)
        self.assertLess(table_preview_at, theme_board_at)

    def test_us_theme_board_mirrors_kr_yellow_button_and_detail_inputs(self):
        # 2026-07-15 사용자 반복 요청: 한국장 테마 참고판(노란 버튼 + 표 + 세부 입력)과
        # 같은 형태를 미국장에도 만든다.
        us_tab = SOURCE[SOURCE.index("def _render_tab_us():"):SOURCE.index("with tab_us:\n    _render_tab_us()")]
        self.assertIn('st.button("테마 참고판 자동 조회", key="us_theme_auto_fetch")', us_tab)
        self.assertIn('"세부 입력할 테마 선택", _us_theme_names, key="us_theme_detail_selector"', us_tab)
        for key_prefix in ("us_theme_leader_", "us_theme_laggard_", "us_theme_chase_warning_", "us_theme_memo_"):
            self.assertIn(key_prefix, us_tab)


@unittest.skipUnless(_JARVIS1_OPEN, _JARVIS1_WHY)
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
            next(node for node in app.button if node.key == "login_submit").click().run(timeout=90)
            # 로그인 뒤 나오는 '어디로 갈까요'에서 자비스1로 들어간다.
            next(node for node in app.button if node.key == "entry_go").click().run(timeout=90)
            self.assertEqual(len(app.exception), 0)

            markdown_texts = [str(node.value) for node in app.markdown]
            self.assertTrue(any("종목 판단 미리보기" in t for t in markdown_texts))
            self.assertTrue(any("2단계 판단 미리보기" in t for t in markdown_texts))
            self.assertTrue(any("종목별 1순위 근거" in t for t in markdown_texts))
            self.assertTrue(any("테마 참고판 (미국)" in t for t in markdown_texts))
            self.assertTrue(any("핵심 근거" in t for t in markdown_texts))
            self.assertGreater(len(app.dataframe), 0)


if __name__ == "__main__":
    unittest.main()
