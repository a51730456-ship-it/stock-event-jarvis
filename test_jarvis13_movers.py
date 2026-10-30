"""자비스13 「오늘 움직인 까닭」 — 크게 움직인 종목의 같은 날 뉴스 제목(누를 때만) (2026-10-31 상하님 「다 넣어라」 ③)."""
from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import jarvis13_movers as movers
import test_jarvis13_page as page_test


class MoversTests(unittest.TestCase):
    def test_only_big_moves_biggest_first(self):
        rows = [{"code": "A", "name": "가", "change_pct": 2.9, "day": "2026-10-30"},
                {"code": "B", "name": "나", "change_pct": -7.5, "day": "2026-10-30"},
                {"code": "C", "name": "다", "change_pct": 4.0, "day": "2026-10-30T00:00:00"},
                {"code": "D", "name": "라", "change_pct": None, "day": "2026-10-30"},
                {"code": "", "name": "마", "change_pct": 9.0, "day": "2026-10-30"},
                {"code": "E", "name": "바", "change_pct": float("nan"), "day": "2026-10-30"}]
        out = movers.movers(rows)
        self.assertEqual(["B", "C"], [row["code"] for row in out])   # 3% 넘는 것만 · 크게 움직인 차례
        self.assertEqual("2026-10-30", out[1]["day"])                  # 날짜는 앞 10자

    def test_same_day_only_and_unknown_day_gives_nothing(self):
        items = [{"title": "그날", "pub_date": "2026-10-30 09:10:00"},
                 {"title": "전날", "pub_date": "2026-10-29 18:00:00"},
                 {"title": "날짜 없음", "pub_date": ""}]
        self.assertEqual(["그날"], [item["title"] for item in movers.same_day(items, "2026-10-30")])
        self.assertEqual([], movers.same_day(items, ""))               # 날을 모르면 붙이지 않는다

    def test_pick_puts_direct_company_news_first_and_limits(self):
        items = [{"title": "시장 전반 하락", "pub_date": "2026-10-30 10:00:00", "link": "https://a"},
                 {"title": "가 공급 계약 체결", "pub_date": "2026-10-30 11:00:00", "originallink": "https://b"},
                 {"title": "세 번째", "pub_date": "2026-10-30 12:00:00"}]

        def classify(item, _name, _code):
            return {"level": "기업 직접 재료 후보" if "계약" in item["title"] else "일반 참고"}

        picked = movers.pick(items, "가", "A", classify=classify)
        self.assertEqual(["가 공급 계약 체결", "시장 전반 하락"], [item["title"] for item in picked])
        self.assertEqual("https://b", picked[0]["link"])
        self.assertEqual("2026-10-30 11:00", picked[0]["when"])
        self.assertEqual("기업 직접 재료 후보", picked[0]["level"])

    def test_pick_survives_a_broken_classifier(self):
        def broken(*_args):
            raise RuntimeError("분류 실패")

        picked = movers.pick([{"title": "제목", "pub_date": "2026-10-30 10:00:00"}], "가", "A", classify=broken)
        self.assertEqual(["제목"], [item["title"] for item in picked])
        self.assertEqual("", picked[0]["level"])

    def test_fetch_all_keeps_the_others_when_one_fails(self):
        def fetch(target):
            if target["code"] == "B":
                raise RuntimeError("막힘")
            return {"status": "정상", "data": []}

        out = movers.fetch_all([{"code": "A"}, {"code": "B"}], fetch)
        self.assertEqual("정상", out["A"]["status"])
        self.assertEqual("조회 오류", out["B"]["status"])
        self.assertEqual({}, movers.fetch_all([], fetch))


def _big_mover_leaders():
    result = copy.deepcopy(page_test._leaders())
    result["rows"][0]["metrics"]["change_pct"] = 5.2         # SK하이닉스 +5.2% (그날 2026-07-22)
    return result


class PageTests(unittest.TestCase):
    def _app(self, *, opened=False, keys=False, leaders=None, news=None):
        started = []
        extra = []
        if leaders is not None:
            extra.append(patch("jarvis4_data.get_theme_leaders", return_value=leaders))
        if news is not None:
            extra.append(patch("news_data.fetch_naver_news", side_effect=news))
        for item in list(page_test._patches()) + extra:
            item.start()
            started.append(item)
        self.addCleanup(lambda: [item.stop() for item in reversed(started)])
        app = AppTest.from_file(str(page_test.PAGE), default_timeout=120)
        app.secrets["APP_PASSWORD"] = "test"
        if keys:
            app.secrets["NAVER_CLIENT_ID"] = "id"
            app.secrets["NAVER_CLIENT_SECRET"] = "secret"
        app.session_state["authenticated"] = True
        page_test._open_all_details(app)
        if opened:
            app.session_state["j13_movers_theme"] = True
        app.run(timeout=120)
        self.assertEqual(0, len(app.exception), [e.value for e in app.exception])
        return app

    @staticmethod
    def _text(app) -> str:
        return " ".join(str(item.value) for item in list(app.markdown) + list(app.caption) + list(app.info))

    def test_theme_panel_offers_the_button_without_fetching(self):
        calls = []
        app = self._app(news=lambda *args, **kwargs: calls.append(args) or {"status": "정상", "data": []})
        self.assertIn("btn_j13_movers_theme", {button.key for button in app.button})
        self.assertEqual([], calls)                              # 누르기 전에는 받지 않는다(화면이 기다리지 않게)

    def test_no_big_move_says_so(self):
        app = self._app(opened=True, keys=True)
        self.assertIn("3% 넘게 움직인 종목이 없습니다", self._text(app))

    def test_without_naver_keys_it_says_so(self):
        app = self._app(opened=True, leaders=_big_mover_leaders())
        self.assertIn("네이버 뉴스 열쇠가 설정되지 않아", self._text(app))

    def test_same_day_titles_are_shown_and_marked_not_a_cause(self):
        def news(_cid, _secret, query, **_kwargs):
            self.assertEqual("SK하이닉스", query)
            return {"status": "정상", "data": [
                {"title": "SK하이닉스 공급 계약 체결", "originallink": "https://news.example/a",
                 "pub_date": "2026-07-22 10:30:00", "description": ""},
                {"title": "전날 나온 다른 기사", "link": "https://news.example/b",
                 "pub_date": "2026-07-21 17:00:00", "description": ""}]}

        app = self._app(opened=True, keys=True, leaders=_big_mover_leaders(), news=news)
        text = self._text(app)
        self.assertIn("SK하이닉스 공급 계약 체결", text)
        self.assertNotIn("전날 나온 다른 기사", text)                 # 그날 것만
        self.assertIn("+5.2%", text)
        self.assertIn("원인 확인은 아닙니다", text)
        self.assertIn("j13_movers_theme_data", app.session_state)     # 받은 것은 10분 담아 둔다

    def test_failed_fetch_is_shown_and_not_kept(self):
        app = self._app(opened=True, keys=True, leaders=_big_mover_leaders(),
                        news=lambda *args, **kwargs: {"status": "네트워크 오류", "message": "막힘", "data": []})
        self.assertIn("뉴스를 받지 못했습니다", self._text(app))
        self.assertNotIn("j13_movers_theme_data", app.session_state)  # 못 받은 것은 담지 않는다 — 다음에 다시 받는다

    def test_watch_page_has_the_button_after_the_cards(self):
        source = page_test.PAGE.read_text(encoding="utf-8")
        body = source[source.index("def _render_watch_page"):source.index("def main()")]
        self.assertIn('key="j13_movers_watch"', body)
        self.assertLess(body.index("for start in range(0, len(cards), 3)"), body.index('key="j13_movers_watch"'))


if __name__ == "__main__":
    unittest.main()
