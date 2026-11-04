"""자비스13 관심종목 = 자비스12 관심종목 그대로 (2026-11-04 상하님 「관심종목도 미국테마 그대로 따라 만들어라」)."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import jarvis13_home as home
import jarvis13_home_css as copied

ROOT = Path(__file__).resolve().parent


class HomeTests(unittest.TestCase):
    def setUp(self):
        home._NEWS.clear()
        self.addCleanup(home._NEWS.clear)

    def test_css_is_a_letter_copy_of_jarvis12_with_j13h_names(self):
        css = home.css()
        self.assertNotRegex(css, r"j3b-|j12b")                              # 자비스12 이름이 하나도 안 남는다
        self.assertIn(".j13h-card{height:246px", css)                        # 자비스12 카드 값 그대로
        self.assertIn("j13h_grid_", css)
        self.assertIn("app/static/j12asset/", css)                           # 꾸밈 그림 — 같은 파일
        import importlib.util
        spec = importlib.util.spec_from_file_location("j13_copy_home", ROOT / "research" / "j13_copy_home.py")
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        found = tool.extract()                                                 # 자비스12 화면 파일에서 지금 꺼낸 것
        self.assertEqual([tool.rename(block) for block in found["_BRIEFING_CSS"]], copied.BRIEFING_CSS)
        self.assertEqual(tool.rename(found["_BRIEFING_OPEN_CSS"]), copied.BRIEFING_OPEN_CSS)

    def test_no_indented_lines_so_css_is_not_shown_as_text(self):
        # 2026-11-04 깃허브 사진 — 덩어리를 이어 붙이면 들여쓴 「<style>」 줄이 코드 글이 되어 규칙이 화면에 글자로 찍혔다
        for text in (home.css(), home.hero_html([{"code": "005930", "name": "삼성전자"}])):
            self.assertEqual([], [line for line in text.splitlines() if line[:1] in (" ", "\t")])
        self.assertEqual(home.css().count("<style>"), home.css().count("</style>"))

    def test_korean_colors(self):
        svg = home.chart([100, 101, 99, 102], 1.0, baseline=True, base=100)
        self.assertIn(home.UP_STROKE, svg)
        self.assertIn(home.DOWN_STROKE, svg)
        self.assertEqual(("#ff5b5b", "#5aa9ff"), (home.UP_STROKE, home.DOWN_STROKE))
        self.assertIn(".j13h-up{color:#ff5b5b", home.KR_CSS)

    def test_card_has_today_chart_news_and_detail_button(self):
        card = home.card_data(None, None)
        self.assertEqual({}, card)
        card = {"price": 221500.0, "change_pct": -0.2, "chart_today": [222000, 221000, 221500, 221800, 221500],
                "prev_close": 222000.0, "chart6m": [180000, 200000, 221500]}
        news = [{"brief": "삼성전자, 새 칩 발표", "url": "https://n.news.naver.com/x", "published_at": "2026-11-04T09:00"}]
        out = home.card_html({"code": "005930", "name": "삼성전자"}, card, news, "ok")
        for piece in ("j13h-card-shell", "221,500원", "-0.20%", "stroke-dasharray", "삼성전자, 새 칩 발표",
                      "일봉 6개월", 'data-tk="005930"', "🔎 선택종목 세부사항 보기", "j13h-decor-img", "decline"):
            self.assertIn(piece, out)
        pending = home.card_html({"code": "005930", "name": "삼성전자"}, card, None, "pending")
        self.assertIn("뉴스를 불러오는 중입니다", pending)

    def test_news_cache_keeps_only_good_answers(self):
        calls = []

        def fetch(query):
            calls.append(query)
            if query == "망가짐":
                return {"status": "조회 오류", "data": []}
            return {"status": "정상", "data": [{"title": f"{query} 뉴스", "link": "https://x"}]}

        self.assertEqual(1, home.fetch_news(["코스피", "망가짐"], "id", "secret", fetch=fetch))
        self.assertEqual("코스피 뉴스", home.cached_news("코스피")[0]["brief"])
        self.assertIsNone(home.cached_news("망가짐"))                         # 실패는 안 담는다 — 다음에 다시
        self.assertEqual(0, home.fetch_news(["코스피"], "id", "secret", fetch=fetch))   # 담아 둔 것은 다시 안 받는다
        self.assertEqual(0, home.fetch_news(["새것"], None, None, fetch=fetch))   # 열쇠가 없으면 안 받는다

    def test_hero_and_scripts_use_j13h_names(self):
        hero = home.hero_html([{"code": "005930", "name": "삼성전자"}])
        for piece in ("j13h-home", "JARVIS <b>13</b>", "한국테마", "j13h-orbit", "j13k-scene"):
            self.assertIn(piece, hero)
        # 2026-11-05 상하님 「한국 주식 배경 … 미국테마와 구분하자」 — 고양이 버스 그림(자비스12 와 같은 그림)은 뺐다
        self.assertNotIn("j13h-hero-scene", hero)
        self.assertNotIn("hero_catbus_pop", hero)
        scripts = home.scripts_html()
        self.assertIn("'j13h-pop-close'", scripts)
        self.assertIn("j13h_wdgo_", scripts)
        self.assertNotRegex(scripts, r"j3b|j12b")


if __name__ == "__main__":
    unittest.main()
