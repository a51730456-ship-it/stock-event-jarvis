"""자비스13 세부사항 — 「📅 4주간 일별 시세 보기」 (2026-10-30 · 자비스12 의 같은 창을 한국에 맞춰 옮김).

자비스4 의 「당일 가격 한 줄」은 그대로 두고 그 밑에 더한다(상하님 「둘 다 장점을 베낌」 — 빼지 않는다).
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

import test_jarvis13_page as page_test

DAYS = pd.bdate_range(end="2026-10-28", periods=30)


def _frame():
    closes = [100_000.0 + i * 1_000 for i in range(30)]
    closes[-1] = closes[-2] - 2_000                     # 마지막 날은 내림
    return pd.DataFrame({"Open": closes, "High": closes, "Low": closes, "Close": closes, "Volume": 1.0}, index=DAYS)


class DailyPricesTests(unittest.TestCase):
    def _app(self, *, open_box: bool):
        started = []
        for item in list(page_test._patches()) + [patch("jarvis4_data.get_daily_frame", return_value=_frame())]:
            item.start()
            started.append(item)
        self.addCleanup(lambda: [item.stop() for item in reversed(started)])
        app = AppTest.from_file(str(page_test.PAGE), default_timeout=120)
        app.secrets["APP_PASSWORD"] = "test"
        app.session_state["authenticated"] = True
        page_test._open_all_details(app)
        app.session_state["j13_theme_panel_open"] = True
        if open_box:
            app.session_state["j13_daily_prices_theme_000660"] = True
        app.run(timeout=120)
        return app

    def test_closed_box_shows_the_button_and_keeps_the_day_row(self):
        app = self._app(open_box=False)
        self.assertEqual(0, len(app.exception), [e.value for e in app.exception])
        keys = {b.key for b in app.button}
        self.assertIn("btn_j13_daily_prices_theme_000660", keys)
        text = " ".join(str(m.value) for m in app.markdown)
        self.assertIn("당일 가격 · 시가/고가/저가 한눈에 보기", text)      # 자비스4 것은 그대로
        self.assertNotIn("j13dp-pop", text)                              # 누르기 전에는 표를 안 만든다

    def test_open_box_draws_twenty_days_newest_first(self):
        app = self._app(open_box=True)
        self.assertEqual(0, len(app.exception), [e.value for e in app.exception])
        text = " ".join(str(m.value) for m in app.markdown)
        self.assertIn("SK하이닉스 · 4주간 일별 시세", text)
        self.assertEqual(20, text.count("<td class='j13dp-d'>"))
        first = text.index("<td class='j13dp-d'>2026.10.28</td>")
        second = text.index("<td class='j13dp-d'>2026.10.27</td>")
        self.assertLess(first, second)                                   # 최근 날이 맨 위
        self.assertIn("▼ 2,000", text)                                   # 마지막 날 내림 · 원 단위
        self.assertNotIn("j3cz-", text.split("j13dp-tap", 1)[1][:2000])  # 자비스12 창 꾸밈 이름을 안 쓴다


class StockNewsTests(unittest.TestCase):
    def _app(self, *, secrets: bool, news=None):
        started = []
        extra = [patch("jarvis4_data.get_daily_frame", return_value=_frame())]
        if news is not None:
            extra.append(patch("news_data.fetch_naver_news", return_value=news))
        for item in list(page_test._patches()) + extra:
            item.start()
            started.append(item)
        self.addCleanup(lambda: [item.stop() for item in reversed(started)])
        app = AppTest.from_file(str(page_test.PAGE), default_timeout=120)
        app.secrets["APP_PASSWORD"] = "test"
        if secrets:
            app.secrets["NAVER_CLIENT_ID"] = "id"
            app.secrets["NAVER_CLIENT_SECRET"] = "secret"
        app.session_state["authenticated"] = True
        page_test._open_all_details(app)
        app.session_state["j13_theme_panel_open"] = True
        app.session_state["j13_stock_news_theme_000660"] = True
        app.run(timeout=120)
        return app

    def test_news_lists_titles_newest_first_with_safe_links(self):
        news = {"status": "정상", "data": [
            {"title": "SK하이닉스, 신규 공급 계약 체결", "originallink": "https://news.example/a", "link": "",
             "description": "", "pub_date": "2026-10-29T09:10:00+09:00"},
            {"title": "<b>위험</b> 링크", "originallink": "javascript:alert(1)", "link": "",
             "description": "", "pub_date": "2026-10-28T18:00:00+09:00"},
        ]}
        app = self._app(secrets=True, news=news)
        self.assertEqual(0, len(app.exception), [e.value for e in app.exception])
        text = " ".join(str(m.value) for m in app.markdown)
        self.assertIn("SK하이닉스, 신규 공급 계약 체결", text)
        self.assertIn("href='https://news.example/a'", text)
        self.assertNotIn("javascript:", text)                     # http(s) 가 아닌 주소는 걸지 않는다
        self.assertIn("&lt;b&gt;위험&lt;/b&gt;", text)             # 글자는 그대로 보이게 바꿔 적는다
        self.assertIn("2026-10-29 09:10", text)

    def test_without_keys_it_says_so_quietly(self):
        app = self._app(secrets=False)
        self.assertEqual(0, len(app.exception), [e.value for e in app.exception])
        infos = " ".join(str(i.value) for i in app.info)
        self.assertIn("네이버 뉴스 열쇠가 설정되지 않아", infos)


if __name__ == "__main__":
    unittest.main()
