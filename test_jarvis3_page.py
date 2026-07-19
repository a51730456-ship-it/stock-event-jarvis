import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).parent
PAGE = ROOT / "pages" / "2_자비스3.py"


def _chart(start=100):
    index = pd.bdate_range("2026-01-01", periods=60)
    return pd.DataFrame({"Close": [start + i * .5 for i in range(60)]}, index=index)


def _market():
    base = {"ok": True, "current": 100.0, "change_pct": 1.0, "sma20": 95, "sma50": 90}
    return {
        "ok": True, "score": 85, "regime": "상승 우위", "posture": "조건 충족 종목만 매수 심사",
        "reasons": ["SPY 50일선 위"], "checked_at": "2026-07-19T13:00:00+09:00", "stale": False,
        "score_breakdown": [
            {"label": "SPY 50일선", "earned": 25, "max": 25, "state": "충족"},
            {"label": "QQQ 50일선", "earned": 20, "max": 20, "state": "충족"},
            {"label": "SPY 20일선", "earned": 15, "max": 15, "state": "충족"},
            {"label": "QQQ 20일선", "earned": 15, "max": 15, "state": "충족"},
            {"label": "IWM 50일선", "earned": 10, "max": 10, "state": "충족"},
            {"label": "VIX 위험수준", "earned": 0, "max": 15, "state": "미충족"},
        ],
        "phase": {"label": "장 마감"},
        "rows": {"SPY": base, "QQQ": base, "IWM": base, "DIA": base, "^VIX": {**base, "current": 18.0}},
    }


def _ranking():
    rows = []
    for index, name in enumerate(("반도체", "양자컴퓨팅", "빅테크10"), 1):
        rows.append({
            "rank": index, "name": name, "etf": "SMH", "ok": True,
            "score": 90-index, "status": "주도", "change_pct": 1.2,
            "rs20": 4.0, "rs60": 8.0, "breadth": 75.0,
            "basis": "20일 상대강도 +4.0%p · 구성종목 확산 75%", "source_time": "x",
        })
    return {"ok": True, "rows": rows, "stale": False, "checked_at": "x"}


def _leader_chart_payload(start=100):
    chart = _chart(start)
    chart["MA20"] = chart["Close"].rolling(20).mean()
    chart["MA50"] = chart["Close"].rolling(50).mean()
    return {"ok": True, "price": chart[["Close", "MA20", "MA50"]], "volume": None, "stale": False}


def _leaders():
    rows = []
    for index, ticker in enumerate(("NVDA", "AVGO", "AMD", "MU", "TSM", "ASML"), 1):
        metrics = {
            "ok": True, "current": 180.0-index, "change_pct": 1.0, "from_high_pct": -index,
            "ret20": 8.0-index, "atr_pct": 3.0, "source_time": "x",
        }
        plan = {
            "state": "눌림목 대기", "recommendation": "조건부 후보",
            "trigger": 181.0, "zone_high": 182.0, "invalidation": 174.0,
            "target": 195.0, "buy_reason": "기준가 회복 후 진입합니다.",
        }
        rows.append({
            "rank": index, "ticker": ticker, "name": ticker, "score": 90-index,
            "score_parts": [22, 22, 18, 14, 13], "metrics": metrics, "plan": plan,
            "stock_reason": f"테마 내 종합 {index}위",
            "daily_chart": _leader_chart_payload(),
            "weekly_chart": _leader_chart_payload(80),
        })
    return {"ok": True, "rows": rows, "stale": False, "checked_at": "x", "etf": "SMH"}


def _chart_bundle():
    chart = _chart()
    chart["MA20"] = chart["Close"].rolling(20).mean()
    chart["MA50"] = chart["Close"].rolling(50).mean()
    volume = pd.DataFrame({"Volume": [1_000_000 + index for index in range(len(chart))]}, index=chart.index)
    payload = {"ok": True, "price": chart, "volume": volume, "stale": False}
    return {"ok": True, "charts": {"일봉": payload, "주봉": payload, "월봉": payload}, "stale": False}


class Jarvis3PageTests(unittest.TestCase):
    def test_authenticated_page_renders_market_before_theme_and_records(self):
        with patch("jarvis3_data.get_market_overview", return_value=_market()), \
             patch("jarvis3_data.get_theme_rankings", return_value=_ranking()), \
             patch("jarvis3_data.get_theme_leaders", return_value=_leaders()), \
             patch("jarvis3_data.get_live_quote", return_value={
                 "ok": True, "current": 179.0, "change_pct": 1.0, "from_high_pct": -1.0,
                 "ret20": 7.0, "atr_pct": 3.0, "source_time": "x", "stale": False,
             }), \
             patch("jarvis3_data.get_chart_bundle", return_value=_chart_bundle()), \
             patch("jarvis3_store.ensure_tables"), \
             patch("jarvis3_store.trade_progress", return_value={
                 "total_count": 0, "open_count": 0, "closed_count": 0, "minimum_sample": 30,
             }), \
             patch("jarvis3_store.list_trades", return_value=[]):
            app = AppTest.from_file(str(PAGE), default_timeout=60)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
            app.run(timeout=60)

        self.assertEqual(len(app.exception), 0)
        subheaders = [str(node.value) for node in app.subheader]
        self.assertIn("미국 전체시장 판단", subheaders)
        # 종목명은 밝은 보라 커스텀 HTML(markdown)로 렌더링된다.
        markdowns = [str(node.value) for node in app.markdown]
        self.assertTrue(any("NVDA" in value for value in markdowns))
        self.assertTrue(any("j3-stock-name" in value for value in markdowns))
        # 테마 순위표·대장주 1–6위표 모두 HTML(가운데 정렬), 선택은 pills·radio.
        self.assertTrue(any("j3-theme-table" in value for value in markdowns))
        self.assertTrue(any("52주 고가 대비" in value for value in markdowns))
        self.assertTrue(any("테마 종목 1–6위" in str(node.value) for node in app.markdown))
        self.assertTrue(any("일봉/주봉/월봉 한눈에 보기" in str(node.value) for node in app.markdown))
        self.assertTrue(any("실제 매수 기록" in str(node.value) for node in app.markdown))

    def test_theme_selection_click_actually_switches_theme(self):
        """테마 선택 위젯을 실제로 눌러 테마가 바뀌는지 검증한다(st.pills 클릭 불가 회귀 방지)."""
        with patch("jarvis3_data.get_market_overview", return_value=_market()), \
             patch("jarvis3_data.get_theme_rankings", return_value=_ranking()), \
             patch("jarvis3_data.get_theme_leaders", return_value=_leaders()), \
             patch("jarvis3_data.get_live_quote", return_value={
                 "ok": True, "current": 179.0, "change_pct": 1.0, "from_high_pct": -1.0,
                 "ret20": 7.0, "atr_pct": 3.0, "source_time": "x", "stale": False,
             }), \
             patch("jarvis3_data.get_chart_bundle", return_value=_chart_bundle()), \
             patch("jarvis3_store.ensure_tables"), \
             patch("jarvis3_store.trade_progress", return_value={
                 "total_count": 0, "open_count": 0, "closed_count": 0, "minimum_sample": 30,
             }), \
             patch("jarvis3_store.list_trades", return_value=[]):
            app = AppTest.from_file(str(PAGE), default_timeout=60)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
            app.run(timeout=60)
            theme_radio = [node for node in app.radio if str(node.label) == "테마 선택"]
            self.assertEqual(len(theme_radio), 1, "테마 선택 위젯이 클릭 가능한 형태로 있어야 합니다")
            theme_radio[0].set_value("양자컴퓨팅").run(timeout=60)

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.session_state.filtered_state.get("j3_theme_choice"), "양자컴퓨팅")

    def test_table_click_and_chart_color_contracts_are_present(self):
        source = PAGE.read_text(encoding="utf-8")
        # 테마 선택은 클릭이 확실한 radio로 유지(st.pills는 이 환경에서 클릭 불가).
        self.assertNotIn("st.pills(", source)
        # 테마표는 행 클릭이 되는 st.dataframe(세션 유지) + Styler 글자색.
        self.assertIn('key="j3_theme_rank_table"', source)
        self.assertIn('on_select="rerun"', source)
        self.assertIn("_style_theme_table", source)
        self.assertIn("_selected_rows", source)
        self.assertIn("_leader_table_html", source)
        # 세션을 끊는 HTML 링크(<a href='?...'>)는 절대 넣지 않는다.
        self.assertNotIn("href='?j3t=", source)
        self.assertIn("상세 종목 선택", source)
        self.assertIn("j3_stock_choice_", source)
        self.assertIn("get_chart_bundle", source)
        self.assertIn('range=["#69bff8", "#ff4d4f", "#a855f7"]', source)
        # 색·메달 계약: 종목명 보라 / 라벨 코발트 / 점수 붉은 / 메달 80점 이상만
        self.assertIn("j3-stock-name", source)
        self.assertIn("j3-section-title", source)
        self.assertIn("j3-leader-score", source)
        self.assertIn("🥇", source)
        self.assertIn('float(leader["score"]) >= 80', source)

    def test_main_login_includes_jarvis3_destination(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("자비스3 (미국 테마 레이더)", source)
        self.assertIn('st.switch_page("pages/2_자비스3.py")', source)

    def test_login_can_switch_directly_to_jarvis3(self):
        with patch("jarvis3_data.get_market_overview", return_value=_market()), \
             patch("jarvis3_data.get_theme_rankings", return_value=_ranking()), \
             patch("jarvis3_data.get_theme_leaders", return_value=_leaders()), \
             patch("jarvis3_data.get_live_quote", return_value={
                 "ok": True, "current": 179.0, "change_pct": 1.0, "from_high_pct": -1.0,
                 "ret20": 7.0, "atr_pct": 3.0, "source_time": "x", "stale": False,
             }), \
             patch("jarvis3_data.get_chart_bundle", return_value=_chart_bundle()), \
             patch("jarvis3_store.ensure_tables"), \
             patch("jarvis3_store.trade_progress", return_value={
                 "total_count": 0, "open_count": 0, "closed_count": 0, "minimum_sample": 30,
             }), \
             patch("jarvis3_store.list_trades", return_value=[]):
            app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
            app.secrets["APP_PASSWORD"] = "test"
            app.run(timeout=60)
            app.radio[0].set_value("자비스3 (미국 테마 레이더)")
            app.text_input[0].set_value("test")
            app.button[0].click().run(timeout=60)

        self.assertEqual(len(app.exception), 0)
        self.assertTrue(app.session_state.filtered_state.get("authenticated"))
        self.assertIn("미국 전체시장 판단", [str(node.value) for node in app.subheader])


if __name__ == "__main__":
    unittest.main()
