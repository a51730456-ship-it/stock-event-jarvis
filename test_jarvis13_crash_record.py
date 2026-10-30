"""자비스13 급락 후 반등장 — 다시 잰 성적 · 국면별 표 · 동전주 딱지 · 그림자 목록 (2026-10-31 상하님 「라」)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import jarvis13_crash_record as record
import test_jarvis13_page as page_test


def _rulebook_block() -> str:
    source = page_test.PAGE.read_text(encoding="utf-8")
    return source.split("def _render_rulebook_finder(")[1].split("\ndef ")[0]


class RecordTests(unittest.TestCase):
    def test_holds_line_shows_three_horizons_against_kospi(self):
        line = record.holds_line()
        for text in ("국면 12번", "코스피보다", "20일", "+2.5%p", "40일", "-0.9%p", "60일", "-4.4%p"):
            self.assertIn(text, line)

    def test_record_says_plainly_what_it_is(self):
        with patch.object(record, "SHADOW_DIR", Path(tempfile.mkdtemp())):
            text = record.record_html()
        self.assertIn("길게 들면 코스피보다 못했습니다", text)
        self.assertIn("「12년에 29번 · 100번 중 66.6번」은 국면이 <u>끝나야</u>", text)   # 옛 숫자를 왜 뺐는지
        self.assertIn("0.20%", text)                                                  # 비용
        self.assertIn("<b>종가</b>", text)                                            # 종가 기준
        self.assertIn("j13-shadow-v1", text)
        self.assertIn("아직 저장된 날이 없습니다", text)

    def test_shadow_count_comes_from_the_saved_files(self):
        folder = Path(tempfile.mkdtemp())
        for day in ("2026-11-03", "2026-11-02"):
            (folder / f"{day}.KR.json").write_text("{}", encoding="utf-8")
        (folder / "메모.txt").write_text("x", encoding="utf-8")
        self.assertEqual(["2026-11-02", "2026-11-03"], record.shadow_saved(folder))
        with patch.object(record, "SHADOW_DIR", folder):
            self.assertIn("지금까지 2번 저장(마지막 2026-11-03)", record.record_html())

    def test_episode_table_scrolls_inside_itself_on_phones(self):
        sample = ({"start": "2018-10-11", "end": "2019-01-04", "deepest": "2018-10-29", "depth": -22.4,
                   "ex": {20: 3.1, 40: -1.2, 60: None}},)
        with patch.object(record, "EPISODES", sample), patch.object(record, "EPISODE_RUN", 1):
            table = record._episode_table()
        self.assertIn("overflow-x:auto", table)                  # 화면 전체가 옆으로 넘치지 않게
        self.assertIn("2018-10-11 ~ 2019-01-04", table)
        self.assertIn("+3.1%p", table)
        self.assertIn("-1.2%p", table)
        self.assertIn("<td>—</td>", table)                       # 못 잰 칸은 비워 둔다(0 으로 채우지 않는다)

    def test_episodes_match_the_count_when_filled(self):
        if record.EPISODES:
            self.assertEqual(record.EPISODE_COUNT, len(record.EPISODES))
            self.assertIsNotNone(record.EPISODE_RUN)


class HelpTextTests(unittest.TestCase):
    def test_frozen_help_text_is_corrected_only_in_the_crash_part(self):
        import method_help
        out = record.help_text(method_help.KR_TEXT)
        self.assertNotIn("승률 66.6%", out)
        self.assertNotIn("스물아홉", out)
        self.assertIn("한국에서 다시 잰 성적", out)
        self.assertIn("2026년 3~4월 국면을 빼면", out)
        self.assertIn("그때까지 <b>가장 깊었던 날</b>을 기준일로", out)
        self.assertIn("승률 43.4%(7,410건)", out)                    # 상승장 설명은 그대로
        self.assertNotIn("바로잡음(2026-10-31)", out)                 # 다 찾았으니 덧붙인 경고는 없다

    def test_if_the_frozen_text_ever_changes_a_warning_goes_on_top(self):
        out = record.help_text("<div>바뀐 설명 · 승률 66.6%</div>")
        self.assertTrue(out.startswith("<div class='mh-box mh-warn-box'>"))
        self.assertIn("국면이 끝나야 아는 날로 잰 값", out)

    def test_page_uses_the_slot_and_not_the_frozen_popover(self):
        source = page_test.PAGE.read_text(encoding="utf-8")
        self.assertIn('method_help.render(st, "KR", help_slot=_j13_method_help)', source)
        self.assertIn("jarvis13_crash_record.help_text(method_help.KR_TEXT)", source)
        self.assertIn('key=method_help.popover_key("KR")', source)     # 같은 창 열쇠 — 여닫힘 기억이 그대로


class PageTests(unittest.TestCase):
    def test_crash_help_shows_the_record_not_the_old_win_rate(self):
        block = _rulebook_block()
        crash = block[block.index("elif show_help:"):block.index("funnel = ")]
        self.assertIn("jarvis13_crash_record.record_html()", crash)
        self.assertIn("jarvis13_crash_record.holds_line()", crash)
        self.assertNotIn("win_rate", crash)          # 옛 승률(국면이 끝나야 아는 날로 잰 값)은 급락 설명에서 뺐다
        self.assertIn("그때까지 가장 깊었던 날", crash)

    def test_penny_tag_only_on_the_crash_table(self):
        block = _rulebook_block()
        self.assertIn("coin_tag = (not breakout", block)
        self.assertIn("jarvis13_crash_record.PENNY_PRICE", block)
        self.assertIn("⚠ 1,000원 미만", block)

    def test_crash_help_renders_on_the_page(self):
        result = {"ok": True, "rows": [], "rules": [{"key": "deep", "label": "고점 대비 -40~-60%", "hold_days": 20}],
                  "bucket_counts": {"deep": 0}, "universe_count": 0, "liquid_count": 0, "scanned_count": 0,
                  "screened_count": 0, "result_limit": 20}
        started = []
        for item in list(page_test._patches()) + [patch("jarvis4_data.find_crash_rebound_stocks", return_value=result)]:
            item.start()
            started.append(item)
        self.addCleanup(lambda: [item.stop() for item in reversed(started)])
        app = AppTest.from_file(str(page_test.PAGE), default_timeout=120)
        app.secrets["APP_PASSWORD"] = "test"
        app.session_state["authenticated"] = True
        app.session_state["j13_rulebook_help_open"] = True
        app.run(timeout=120)
        next(button for button in app.button if button.key == "j13_pullback_crash").click()
        app.run(timeout=120)
        self.assertEqual(0, len(app.exception), [e.value for e in app.exception])
        text = " ".join(str(item.value) for item in app.markdown)
        self.assertIn("한국 자료로 다시 잰 성적", text)
        self.assertIn("코스피보다", text)
        self.assertNotIn("승률 66.6%", text)


if __name__ == "__main__":
    unittest.main()
