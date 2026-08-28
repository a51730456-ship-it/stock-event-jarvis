import unittest
import json
from pathlib import Path
from unittest.mock import patch

import page_access

# 이 시험은 **자비스5 화면을 지나간다.** 그 화면이 닫혀 있으면(2026-08-28 상하님
# 지시) 화면이 안내만 그리고 멈춘다. 시험이
# 틀린 것이 아니라 길이 막힌 것이므로 건너뛴다 — `page_access.OPEN_PAGES` 에
# 이름을 다시 넣으면 저절로 다시 돈다.
_JARVIS5_OPEN = page_access.is_open("자비스5")
_JARVIS5_WHY = "자비스5 화면을 닫아 두어(page_access.OPEN_PAGES) 이 길이 막혀 있다"

from streamlit.testing.v1 import AppTest


PAGE = Path(__file__).parent / "pages" / "4_자비스5.py"


@unittest.skipUnless(_JARVIS5_OPEN, _JARVIS5_WHY)
class Jarvis5PageTests(unittest.TestCase):
    def _patches(self):
        return (
            patch("jarvis5_store.ensure_schema"),
            patch("jarvis5_store.latest_run", return_value=None),
            patch("jarvis5_store.latest_theme_rows", return_value=[]),
            patch("jarvis5_store.theme_activity_history", return_value={}),
            patch("jarvis5_store.recent_signals", return_value=[]),
            patch("jarvis5_store.outcome_summary", return_value=[]),
            patch("jarvis5_collector.collect_once", return_value={
                "ok": True, "theme_count": 266, "stock_row_count": 2272,
                "elapsed_seconds": 4.2,
            }),
        )

    def test_page_is_experimental_and_can_collect_once(self):
        started = []
        try:
            for item in self._patches():
                item.start()
                started.append(item)
            app = AppTest.from_file(str(PAGE), default_timeout=90)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
            app.run(timeout=90)
            self.assertEqual(len(app.exception), 0)
            text = " ".join(str(node.value) for node in app.markdown)
            self.assertIn("테스트용 관찰 도구", text)
            self.assertIn("거래대금은 매수·매도 합계", text)
            button = next(node for node in app.button if "1회 수집" in str(node.label))
            button.click().run(timeout=90)
            self.assertEqual(len(app.exception), 0)
        finally:
            for item in reversed(started):
                item.stop()

    def test_source_keeps_db_and_models_separate(self):
        source = PAGE.read_text(encoding="utf-8")
        self.assertIn("jarvis5_store", source)
        self.assertIn("A 거래활동 급증", source)
        self.assertIn("B 다종목 확산", source)
        self.assertIn("j5-pos", source)
        self.assertIn("j5-neg", source)
        self.assertIn("j5-table th", source)
        self.assertIn("text-align: center", source)
        self.assertNotIn("st.dataframe", source)
        self.assertNotIn("자동매매", source)

    def test_colored_tables_and_explanations_render_with_real_rows(self):
        latest = {
            "captured_at": "2026-07-23T12:30:00+09:00", "theme_count": 266,
            "stock_row_count": 6417, "elapsed_seconds": 2.1,
        }
        theme_rows = [{
            "theme_no": 1, "theme_name": "반도체", "member_count": 12,
            "activity_intensity": 3_250_000_000,
            "baseline_ratio": 1.8, "advancers": 8, "active_count": 9,
            "top_contributor_share": .42, "relative_change_pct": 1.25,
            "median_change_pct": 1.5,
        }, {
            "theme_no": 2, "theme_name": "2차전지", "member_count": 10,
            "activity_intensity": 2_100_000_000,
            "baseline_ratio": None, "advancers": 3, "active_count": 7,
            "top_contributor_share": .61, "relative_change_pct": -.75,
            "median_change_pct": -.2,
        }]
        # 미니차트는 실제 시각으로 가로축을 잡으므로 captured_at·interval_seconds를 함께 준다.
        histories = {
            1: [
                {"captured_at": "2026-07-23T12:00:00+09:00", "interval_seconds": 180,
                 "activity_intensity": 1_800_000_000},
                {"captured_at": "2026-07-23T12:15:00+09:00", "interval_seconds": 180,
                 "activity_intensity": 2_400_000_000},
                {"captured_at": "2026-07-23T12:30:00+09:00", "interval_seconds": 180,
                 "activity_intensity": 3_250_000_000},
            ],
            2: [
                {"captured_at": "2026-07-23T12:15:00+09:00", "interval_seconds": 180,
                 "activity_intensity": 2_500_000_000},
                {"captured_at": "2026-07-23T12:30:00+09:00", "interval_seconds": 180,
                 "activity_intensity": 2_100_000_000},
            ],
        }
        signals = [{
            "captured_at": "2026-07-23T12:27:00+09:00", "theme_name": "반도체",
            "model": "C", "model_version": 2, "stage": "실험감지", "score": 82,
            "feature_json": json.dumps({"interval_value": 19_000_000_000}),
            "reason": "9종목 거래참여 · 상승확산 67%",
        }]
        summary = [{
            "model": "C", "model_version": 2, "horizon_minutes": 10, "sample_count": 25,
            "avg_forward_return_pct": .32, "avg_relative_forward_return_pct": -.08,
            "hit_rate": .56, "enough_samples": True,
        }]
        with patch("jarvis5_store.ensure_schema"), \
             patch("jarvis5_store.latest_run", return_value=latest), \
             patch("jarvis5_store.latest_theme_rows", return_value=theme_rows), \
             patch("jarvis5_store.theme_activity_history", return_value=histories), \
             patch("jarvis5_store.recent_signals", return_value=signals), \
             patch("jarvis5_store.outcome_summary", return_value=summary):
            app = AppTest.from_file(str(PAGE), default_timeout=90)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
            app.run(timeout=90)

        self.assertEqual(len(app.exception), 0)
        markup = " ".join(str(node.value) for node in app.markdown)
        self.assertIn("j5-table", markup)
        self.assertIn("j5-pos", markup)
        self.assertIn("j5-neg", markup)
        self.assertIn("표 읽는 법", markup)
        self.assertIn("거래금액순 아님", markup)
        self.assertIn("j5-spark-line", markup)
        # 미니차트 툴팁에 실제 시간대가 들어간다(고정 문구 '약 30분'을 쓰지 않는다).
        self.assertIn("12:00~12:30", markup)
        self.assertNotIn("약 30분", markup)
        self.assertIn("선행 후보점수", markup)
        self.assertIn("매수 신호가 아니라 검증 전 후보", markup)
        self.assertIn("반도체", markup)


if __name__ == "__main__":
    unittest.main()
