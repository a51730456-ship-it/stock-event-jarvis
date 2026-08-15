"""상위 테마 5개 × 각 종목 1~3위 = 15종목 (2026-08-15 상하님 지시).

상하님 — "20개 테마 중 상위 테마 5위, 각 테마 중 1~3위, 그렇게 하면 15종목이
나오겠지?"

여기서 지키는 것 셋이다.
  ① **점수를 새로 만들지 않는다.** 테마를 눌렀을 때 나오는 「테마 종목 1–6위」와
     같은 조건점수·같은 차례여야 한다. 여기서 따로 재면 같은 종목이 두 화면에서
     다른 등수로 나온다.
  ② 순위는 **테마 안 등수**다. 1·2·3이 테마마다 되풀이된다.
  ③ 화면과 저장 목록이 **같은 함수**를 부른다(CLAUDE.md 10-1).
"""

from __future__ import annotations

import pathlib
import unittest

import jarvis3_data as j3
import picklist_store as store


THEME_ROWS = [
    {"name": "가테마", "score": 90.0},
    {"name": "나테마", "score": 80.0},
    {"name": "다테마", "score": 70.0},
    {"name": "라테마", "score": 60.0},
    {"name": "마테마", "score": 50.0},
    {"name": "바테마", "score": 40.0},
]


def _fake_leaders(theme_name, market_score=0, theme_score=0, **_kwargs):
    """테마마다 종목 다섯을 조건점수 순으로 돌려주는 가짜 대장주 목록."""
    rows = []
    for index in range(1, 6):
        rows.append({
            "ticker": f"{theme_name[0]}{index}",
            "name": f"{theme_name}{index}호",
            "score": 100.0 - index,
            "rank": index,
            "metrics": {"current": 10.0 * index, "from_high_pct": -3.0},
            "plan": {"state": "관찰"},
        })
    return {"ok": True, "rows": rows}


class ThemeTopPicksTests(unittest.TestCase):
    def setUp(self):
        self._real_leaders = j3.get_theme_leaders
        self._real_prefetch = j3._prefetch_leader_quotes
        j3.get_theme_leaders = _fake_leaders
        j3._prefetch_leader_quotes = lambda *_a, **_k: None

    def tearDown(self):
        j3.get_theme_leaders = self._real_leaders
        j3._prefetch_leader_quotes = self._real_prefetch

    def test_five_themes_times_three_makes_fifteen(self):
        """상위 5테마 × 각 3종목 = 15종목. 테마 등수 순으로 온다."""
        out = j3.find_theme_top_picks(THEME_ROWS, market_score=0)
        self.assertTrue(out["ok"])
        self.assertEqual(15, len(out["rows"]), "15종목이 아니다")
        # 위 다섯 테마만 — 6등 '바테마'는 안 들어간다.
        self.assertEqual(["가테마", "나테마", "다테마", "라테마", "마테마"], out["themes"])
        self.assertNotIn("바테마", {row["theme_name"] for row in out["rows"]})
        # 테마 등수는 1~5, 테마마다 세 줄씩.
        self.assertEqual([1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5, 5],
                         [row["theme_place"] for row in out["rows"]])

    def test_rank_repeats_one_two_three_inside_each_theme(self):
        """순위는 **테마 안 등수**다 — 1~15로 통으로 매기지 않는다."""
        out = j3.find_theme_top_picks(THEME_ROWS, market_score=0)
        self.assertEqual([1, 2, 3] * 5, [row["rank"] for row in out["rows"]])

    def test_it_does_not_rescore_anything(self):
        """조건점수를 다시 재지 않는다 — 대장주 목록이 준 값 그대로다."""
        out = j3.find_theme_top_picks(THEME_ROWS, market_score=0)
        for row in out["rows"]:
            self.assertEqual(100.0 - row["rank"], row["score"], row["ticker"])

    def test_how_many_themes_and_stocks_is_one_place(self):
        """테마 수·종목 수는 모듈이 정한다 — 화면·수집기가 그 값을 읽어 쓴다."""
        self.assertEqual(5, j3.THEME_TOP_THEMES)
        self.assertEqual(3, j3.THEME_TOP_PER_THEME)
        out = j3.find_theme_top_picks(THEME_ROWS, market_score=0,
                                      top_themes=2, per_theme=1)
        self.assertEqual(2, len(out["rows"]))


class StorageTests(unittest.TestCase):
    def setUp(self):
        self._real_leaders = j3.get_theme_leaders
        self._real_prefetch = j3._prefetch_leader_quotes
        j3.get_theme_leaders = _fake_leaders
        j3._prefetch_leader_quotes = lambda *_a, **_k: None

    def tearDown(self):
        j3.get_theme_leaders = self._real_leaders
        j3._prefetch_leader_quotes = self._real_prefetch

    def test_saved_rows_keep_the_theme_and_its_place(self):
        """저장 줄에 '어느 테마 몇 등의 몇 위'가 남아야 한다."""
        out = j3.find_theme_top_picks(THEME_ROWS, market_score=0)
        rows = store.rows_from_result(
            out, market="US", list_kind="theme15", trade_date="2026-08-15", limit=20)
        self.assertEqual(15, len(rows))
        self.assertEqual([1, 2, 3] * 5, [int(row["rank"]) for row in rows])
        self.assertEqual("가테마", rows[0]["origin"])
        self.assertEqual(1.0, rows[0]["theme_place"])
        self.assertEqual("마테마", rows[-1]["origin"])
        self.assertEqual(5.0, rows[-1]["theme_place"])

    def test_it_is_a_united_states_list_only(self):
        """미국 화면에만 있는 갈래다 — 한국에는 없으니 저장하지 않는다."""
        self.assertTrue(store.should_save("theme15", "US"))
        self.assertFalse(store.should_save("theme15", "KR"))
        self.assertFalse(store.should_show("theme15", "KR"))

    def test_it_comes_first_in_the_saved_list(self):
        """화면 차례와 같아야 한다 — 순위표 바로 아래가 이 목록이다."""
        self.assertEqual("theme15", store.KIND_ORDER[0])


class PageWiringTests(unittest.TestCase):
    def test_screen_and_collector_call_the_same_function(self):
        """화면과 클라우드 수집기가 **같은 함수**를 부른다(CLAUDE.md 10-1)."""
        page = pathlib.Path("pages/2_자비스3.py").read_text(encoding="utf-8")
        collector = pathlib.Path("picklist_collector.py").read_text(encoding="utf-8")
        self.assertIn("find_theme_top_picks(", page, "화면이 안 부른다")
        self.assertIn("find_theme_top_picks(", collector, "수집기가 안 부른다")
        self.assertIn('picklist_ui.autosave("US", "theme15"', page,
                      "화면이 보여 준 목록을 저장하지 않는다")

    def test_it_sits_right_under_the_theme_ranking(self):
        """자리는 「20개 테마 실시간 순위」와 「종목 찾기」 사이다(상하님 지시)."""
        page = pathlib.Path("pages/2_자비스3.py").read_text(encoding="utf-8")
        after_rank = page.split('_section_close(_THEME_RANK_OPEN')[1]
        head = after_rank.split("📉 종목 찾기")[0]
        self.assertIn("_render_theme_top15(market, ranking)", head,
                      "순위표와 '종목 찾기' 사이에 없다")

    def test_it_has_a_close_button_at_the_bottom(self):
        page = pathlib.Path("pages/2_자비스3.py").read_text(encoding="utf-8")
        block = page.split("def _render_theme_top15(")[1].split("\ndef ")[0]
        self.assertIn("_section_close(_THEME_TOP15_OPEN", block, "맨 아래 닫기가 없다")


if __name__ == "__main__":
    unittest.main()
