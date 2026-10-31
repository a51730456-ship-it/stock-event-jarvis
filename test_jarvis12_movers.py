"""자비스12 「오늘 움직인 까닭」(2026-10-31 상하님 「자비스12에도 넣어라」)."""
from __future__ import annotations

import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

import jarvis12_movers as movers

PAGE = Path(__file__).resolve().parent / "pages" / "11_자비스12.py"


def _utc(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)


class MoversTests(unittest.TestCase):
    def test_only_big_moves_biggest_first_once_each(self):
        rows = [{"ticker": "nvda", "name": "엔비디아", "change_pct": 4.0},
                {"ticker": "PLTR", "change_pct": -6.5},
                {"ticker": "AAPL", "change_pct": 2.9},
                {"ticker": "NVDA", "change_pct": 4.0},          # 두 곳에 있는 종목은 한 번만
                {"ticker": "TSLA", "change_pct": None},
                {"ticker": "", "change_pct": 9.0}]
        self.assertEqual(["PLTR", "NVDA"], [item["ticker"] for item in movers.movers(rows)])


class WindowTests(unittest.TestCase):
    def test_korean_saturday_morning_is_fridays_session(self):
        day, start, end = movers.session_window(_utc("2026-10-31T01:00:00"))   # 한국 토요일 10시
        self.assertEqual(date(2026, 10, 30), day)
        self.assertEqual(_utc("2026-10-29T20:00:00"), start)                  # 목 16:00 ET(여름 시간 끝나기 전)
        self.assertEqual(_utc("2026-10-31T00:00:00"), end)                    # 금 20:00 ET

    def test_monday_before_the_open_looks_back_to_friday_and_its_eve(self):
        day, start, _end = movers.session_window(_utc("2026-11-02T13:00:00"))  # 월 08:00 ET
        self.assertEqual(date(2026, 10, 30), day)
        self.assertEqual(date(2026, 10, 29), start.date())

    def test_during_the_session_it_is_today_from_the_last_close(self):
        day, start, _end = movers.session_window(_utc("2026-11-03T15:00:00"))  # 화 10:00 ET
        self.assertEqual(date(2026, 11, 3), day)
        self.assertEqual(_utc("2026-11-02T21:00:00"), start)                  # 월 16:00 ET(겨울 시간)

    def test_only_titles_in_the_window_newest_first(self):
        start, end = _utc("2026-10-29T20:00:00"), _utc("2026-10-31T00:00:00")
        items = [{"brief": "옛 뉴스", "published_at": "2026-10-29T12:00:00+00:00"},
                 {"brief": "장 전 실적 발표", "published_at": "2026-10-30T11:00:00+00:00", "url": "https://a.example/1"},
                 {"headline": "Shares jump", "published_at": "2026-10-30T18:30:00+00:00"},
                 {"brief": "날짜 없음"},
                 {"brief": "장 끝난 뒤 한참", "published_at": "2026-10-31T03:00:00+00:00"},
                 {"brief": "장중", "published_at": "2026-10-30T15:00:00+00:00"}]
        picked = movers.in_window(items, start, end)
        self.assertEqual(["Shares jump", "장중"], [item["title"] for item in picked])
        self.assertEqual(3, len(movers.in_window(items, start, end, limit=9)))


class PageTests(unittest.TestCase):
    def test_both_places_and_the_revision_guard(self):
        source = PAGE.read_text(encoding="utf-8")
        self.assertIn(f"_REQUIRED_J12_MOVERS_REVISION = {movers.MODULE_REVISION}", source)
        self.assertIn('key="j12_movers_theme")', source)
        self.assertIn('key="j12_movers_watch")', source)
        body = source.split("def _render_movers_reason(")[1].split("\ndef ")[0]
        self.assertIn("_section_toggle(title, key", body)        # 누를 때만
        self.assertIn("원인 확인은 아닙니다", body)

    def test_watch_page_shows_titles_only_when_opened(self):
        from streamlit.testing.v1 import AppTest

        stocks = {"selected": [{"position": 1, "ticker": "NVDA", "name": "엔비디아"},
                               {"position": 2, "ticker": "AAPL", "name": "애플"}], "extra": []}
        cards = {"NVDA": {"ticker": "NVDA", "price": 132.0, "change_pct": 5.2, "chart": [1, 2, 3], "stale": False},
                 "AAPL": {"ticker": "AAPL", "price": 200.0, "change_pct": 0.4, "chart": [1, 2, 3], "stale": False}}
        _day, start, _end = movers.session_window()
        news = {"ok": True, "items": [
            {"brief": "엔비디아 새 칩 공개", "headline": "x", "url": "https://a.example/n",
             "published_at": (start.replace(microsecond=0) + (_end - start) / 2).isoformat()}]}

        def run(opened: bool):
            with patch("jarvis3_briefing_store.ensure_tables"), \
                 patch("jarvis3_briefing_store.all_stocks", return_value=stocks), \
                 patch("jarvis3_data.get_briefing_cards", return_value=cards), \
                 patch("jarvis12_watch_since.added_map", return_value={}), \
                 patch("jarvis3_briefing_news.get_or_schedule", return_value=news):
                app = AppTest.from_file(str(PAGE), default_timeout=60)
                app.secrets["APP_PASSWORD"] = "test"
                app.session_state["authenticated"] = True
                app.session_state["jarvis_access_role"] = "owner"
                app.session_state["j12_briefing_page"] = "home"
                app.session_state["j12_movers_watch"] = opened
                app.run(timeout=60)
            self.assertEqual(0, len(app.exception), [e.value for e in app.exception])
            return " ".join(str(node.value) for node in app.markdown), [b.key for b in app.button]

        closed_text, keys = run(False)
        self.assertIn("btn_j12_movers_watch", keys)
        mark = "noopener'>엔비디아 새 칩 공개</a>」"          # 카드 뉴스 줄에도 같은 글이 있어 까닭 줄 모양으로 본다
        self.assertNotIn(mark, closed_text)
        opened_text, _keys = run(True)
        self.assertIn(mark, opened_text)
        self.assertIn("+5.2%", opened_text)
        self.assertNotIn("AAPL</b>", opened_text)               # 3% 안쪽은 안 받는다


if __name__ == "__main__":
    unittest.main()
