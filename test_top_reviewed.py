"""'매수 심사 결과 높은 순위 7' 자료 함수 (2026-07-30 사용자 지시).

전수 검색을 새로 돌리지 않고, 이미 있는 테마 대장주 + 눌림목 결과만 모아
종목 조건점수 하나로 줄 세운다. 순위 기준이 둘이 되면 표를 못 읽으므로
'점수 하나'라는 규칙을 여기서 붙잡는다.
"""

import unittest
from unittest.mock import patch

import jarvis3_data as j3
import jarvis4_data as j4


def _metrics(**over):
    base = {
        "ok": True, "current": 100.0, "sma20": 98.0, "sma50": 95.0,
        "high52": 110.0, "from_high_pct": -9.0, "ret5": 1.0, "ret20": 5.0,
        "atr": 2.0, "atr_pct": 2.0, "volume_ratio": 1.0, "change_pct": 0.5,
    }
    base.update(over)
    return base


def _kr_leader(code, name, score, **over):
    row = {"code": code, "name": name, "score": score, "metrics": _metrics(),
           "flow": {"ok": False}, "plan": {"state": "관찰"}, "rank": 1}
    row.update(over)
    return row


def _us_leader(ticker, score, **over):
    row = {"ticker": ticker, "name": ticker, "score": score, "metrics": _metrics(),
           "plan": {"state": "관찰"}, "rank": 1}
    row.update(over)
    return row


class KoreaTests(unittest.TestCase):
    def test_ranks_by_stock_score_only_and_caps_at_seven(self):
        themes = [{"name": f"테마{i}", "score": 50 + i} for i in range(4)]

        def fake_leaders(theme_row, market_score=0, theme_score=0):
            index = int(str(theme_row["name"])[-1])
            return {"ok": True, "rows": [
                _kr_leader(f"{index}0000{n}", f"종목{index}{n}", 90 - index * 10 - n)
                for n in range(3)
            ]}

        with patch.object(j4, "get_theme_leaders", side_effect=fake_leaders):
            result = j4.find_top_reviewed_stocks(themes, market_score=60)

        self.assertTrue(result["ok"])
        self.assertEqual(7, len(result["rows"]), "7개로 잘라야 한다")
        scores = [row["score"] for row in result["rows"]]
        self.assertEqual(sorted(scores, reverse=True), scores, "점수 내림차순이 아니다")
        self.assertEqual([1, 2, 3, 4, 5, 6, 7], [r["pick_rank"] for r in result["rows"]])
        self.assertEqual(4, result["scanned_themes"])

    def test_same_stock_in_two_themes_is_kept_once_with_the_better_score(self):
        themes = [{"name": "가", "score": 80}, {"name": "나", "score": 70}]

        def fake_leaders(theme_row, market_score=0, theme_score=0):
            score = 88.0 if theme_row["name"] == "가" else 61.0
            return {"ok": True, "rows": [_kr_leader("005930", "삼성전자", score)]}

        with patch.object(j4, "get_theme_leaders", side_effect=fake_leaders):
            result = j4.find_top_reviewed_stocks(themes, market_score=60)

        self.assertEqual(1, len(result["rows"]))
        self.assertEqual(88.0, result["rows"][0]["score"])
        self.assertEqual(["가", "나"], sorted(result["rows"][0]["sources"]))

    def test_one_broken_theme_does_not_lose_the_others(self):
        themes = [{"name": "성한테마", "score": 80}, {"name": "고장테마", "score": 70}]

        def fake_leaders(theme_row, market_score=0, theme_score=0):
            if theme_row["name"] == "고장테마":
                raise RuntimeError("네이버 응답 없음")
            return {"ok": True, "rows": [_kr_leader("000660", "SK하이닉스", 77.0)]}

        with patch.object(j4, "get_theme_leaders", side_effect=fake_leaders):
            result = j4.find_top_reviewed_stocks(themes, market_score=60)

        self.assertEqual(1, len(result["rows"]))
        self.assertEqual(1, result["scanned_themes"])
        self.assertTrue(any("고장테마" in message for message in result["errors"]))

    def test_pullback_rows_join_in_and_get_rejudged_with_the_real_market_score(self):
        """눌림목 결과는 게이트를 열어 둔 채 계산돼 있다 — 시장 점수로 다시 판정해야 한다."""
        pull = {"code": "035420", "name": "NAVER", "score": 92.0,
                "metrics": _metrics(), "themes": ["가"],
                "plan": {"state": "눌림목 대기", "recommendation": "조건부 후보"}}

        with patch.object(j4, "get_theme_leaders",
                          side_effect=lambda *a, **k: {"ok": True, "rows": []}):
            blocked = j4.find_top_reviewed_stocks(
                [{"name": "가", "score": 80}], market_score=10, extra_rows=[pull]
            )
            allowed = j4.find_top_reviewed_stocks(
                [{"name": "가", "score": 80}], market_score=90, extra_rows=[pull]
            )

        self.assertEqual(1, len(blocked["rows"]))
        self.assertNotEqual(
            "조건부 후보", blocked["rows"][0]["plan"]["recommendation"],
            "시장 점수 10점인데도 조건부 후보로 남았다",
        )
        self.assertEqual("조건부 후보", allowed["rows"][0]["plan"]["recommendation"])

    def test_empty_input_is_not_an_error(self):
        result = j4.find_top_reviewed_stocks([], market_score=60)
        self.assertFalse(result["ok"])
        self.assertEqual([], result["rows"])


class PageWiringTests(unittest.TestCase):
    """자료 함수만 있고 화면에 안 붙어 있으면 아무 소용이 없다."""

    PAGES = {
        "US": ("pages/2_자비스3.py", "j3"),
        "KR": ("pages/3_자비스4.py", "j4"),
    }

    def test_both_pages_show_the_section(self):
        import pathlib

        for market, (path, prefix) in self.PAGES.items():
            source = pathlib.Path(path).read_text(encoding="utf-8")
            self.assertIn("매수심사결과 높은 순위 7", source, f"{market} 화면에 제목이 없다")
            self.assertIn("def _render_top_reviewed(", source, f"{market}에 그리는 함수가 없다")
            self.assertIn("_render_top_reviewed(market, ranking)", source,
                          f"{market}에서 부르지 않는다")
            self.assertIn("find_top_reviewed_stocks(", source, f"{market}가 자료를 안 부른다")
            # 눌림목 결과도 함께 넣어야 한다(사용자 지시).
            self.assertIn(f"{prefix}_pullback_result", source)
            self.assertIn("extra_rows=pull_rows", source)

    def test_clicking_a_row_opens_its_own_detail(self):
        import pathlib

        for market, (path, prefix) in self.PAGES.items():
            source = pathlib.Path(path).read_text(encoding="utf-8")
            self.assertIn(f"{prefix}top7_", source, f"{market}에 종목 단추가 없다")
            self.assertIn(f"{prefix}_top7_pick_row", source)
            self.assertIn("def _render_top_reviewed_detail(", source)
            # 상세는 위 테마 상세·눌림목 상세와 키가 겹치면 안 된다.
            self.assertIn('panel="top7"', source, f"{market} 상세 패널 키가 안 갈렸다")

    def test_results_live_in_a_small_panel(self):
        """'이 테마 기법에 대한 설명'과 같은 작은 창에 담는다(사용자 지시)."""
        import pathlib

        for market, (path, _prefix) in self.PAGES.items():
            source = pathlib.Path(path).read_text(encoding="utf-8")
            self.assertIn("순위 7 펼쳐 보기", source, f"{market}가 작은 창을 안 쓴다")

    def test_module_reload_guards_know_the_new_function(self):
        """규칙 11 — 새 함수를 가드에 안 넣으면 온라인에서 AttributeError가 난다."""
        import pathlib

        for market, (path, _prefix) in self.PAGES.items():
            source = pathlib.Path(path).read_text(encoding="utf-8")
            self.assertIn('"find_top_reviewed_stocks"', source,
                          f"{market} 모듈 리로드 가드에 새 함수가 없다")


class UnitedStatesTests(unittest.TestCase):
    def test_ranks_by_score_and_dedups_by_ticker(self):
        themes = [{"name": "반도체", "score": 80}, {"name": "AI", "score": 75}]

        def fake_leaders(theme_name, market_score=0, theme_score=0):
            score = 91.0 if theme_name == "반도체" else 64.0
            return {"ok": True, "rows": [_us_leader("NVDA", score), _us_leader("AMD", 55.0)]}

        with patch.object(j3, "get_theme_leaders", side_effect=fake_leaders):
            result = j3.find_top_reviewed_stocks(themes, market_score=60)

        self.assertEqual(["NVDA", "AMD"], [row["ticker"] for row in result["rows"]])
        self.assertEqual(91.0, result["rows"][0]["score"])
        self.assertEqual(["AI", "반도체"], sorted(result["rows"][0]["sources"]))

    def test_limit_is_seven_by_default(self):
        self.assertEqual(7, j3.TOP_REVIEW_LIMIT)
        self.assertEqual(7, j4.TOP_REVIEW_LIMIT)


if __name__ == "__main__":
    unittest.main()
