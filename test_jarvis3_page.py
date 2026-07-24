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


def _intraday_chart_payload():
    index = pd.date_range("2026-07-21 09:30", periods=30, freq="min")
    price = pd.DataFrame({"Close": [100 + i * 0.1 for i in range(30)]}, index=index)
    return {"ok": True, "price": price, "prev_close": 99.5, "source_time": "2026-07-21T23:00:00+09:00"}


def _sample_trades():
    return [{
        "id": 1, "buy_date": "2026-07-20", "ticker": "NVDA", "stock_name": "NVIDIA",
        "theme_name": "반도체", "trade_style": "스윙", "buy_price": 150.0,
        "quantity": 1.0, "status": "보유", "sell_date": None, "sell_price": None,
        "result_pct": None, "market_regime": "중립·선별", "market_score": 65,
        "theme_score": 80, "stock_score": 85, "memo": None,
    }]


def _fear_greed():
    return {
        "ok": True, "score": 41.0, "rating": "fear", "rating_kr": "공포",
        "previous_close": 45.0, "previous_1_week": 55.0, "previous_1_month": 57.0,
        "previous_1_year": 44.0, "as_of": "x", "stale": False, "source": "CNN Fear & Greed",
    }


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
            # 1위는 당일 차트가 있고 2위부터는 없는 상황(자료 없음 분기)을 함께 검증한다.
            "intraday_chart": _intraday_chart_payload() if index == 1 else None,
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


def _pullbacks():
    return {
        "ok": True, "universe_count": 137, "data_count": 137, "trend_count": 54,
        "window_count": 22, "window": (1, 20), "reused_batch": True,
        "rows": [{
            "pullback_rank": 1, "name": "NVIDIA", "ticker": "NVDA",
            "pullback": {
                "score": 82.5, "high52_days_ago": 7, "from_high_pct": -8.2,
                "gap_pct": 1.4, "parts": [20, 18, 17, 14, 5],
            },
            "metrics": {
                "ok": True, "current": 178.5, "change_pct": -1.35, "ret5": 2.0, "ret20": 6.0,
                "from_high_pct": -8.2, "sma20": 176.0, "sma50": 170.0, "sma200": 150.0,
                "high52": 194.0, "volume_ratio": 1.1, "atr": 6.0, "atr_pct": 3.4,
                "avg_dollar_volume": 3_200_000_000,
            },
            "themes": ["반도체", "AI 인프라"],
        }, {
            "pullback_rank": 2, "name": "Arista Networks", "ticker": "ANET",
            "pullback": {
                "score": 79.0, "high52_days_ago": 10, "from_high_pct": -6.9,
                "gap_pct": 2.5, "parts": [19, 17, 16, 13, 4],
            },
            "metrics": {
                "ok": True, "current": 176.6, "change_pct": 1.0, "ret5": 1.0, "ret20": 4.0,
                "from_high_pct": -6.9, "sma20": 172.0, "sma50": 165.0, "sma200": 140.0,
                "high52": 190.0, "volume_ratio": 1.0, "atr": 5.0, "atr_pct": 2.8,
                "avg_dollar_volume": 1_444_000_000,
            },
            "themes": ["AI 인프라"],
        }],
    }


class Jarvis3PageTests(unittest.TestCase):
    def test_authenticated_page_renders_market_before_theme_and_records(self):
        with patch("jarvis3_data.get_market_overview", return_value=_market()), \
             patch("jarvis3_data.get_fear_greed", return_value=_fear_greed()), \
             patch("market_signal_ui._fetch_quotes", return_value={}), \
             patch("jarvis3_data.get_theme_rankings", return_value=_ranking()), \
             patch("jarvis3_data.get_theme_leaders", return_value=_leaders()), \
             patch("jarvis3_data.get_live_quote", return_value={
                 "ok": True, "current": 179.0, "change_pct": 1.0, "from_high_pct": -1.0,
                 "ret20": 7.0, "atr_pct": 3.0, "source_time": "x", "stale": False,
             }), \
             patch("jarvis3_data.get_chart_bundle", return_value=_chart_bundle()), \
             patch("jarvis3_data.find_pullback_stocks", return_value=_pullbacks()), \
             patch("jarvis3_store.ensure_tables"), \
             patch("jarvis3_store.trade_progress", return_value={
                 "total_count": 0, "open_count": 0, "closed_count": 0, "minimum_sample": 30,
             }), \
             patch("jarvis3_store.list_trades", return_value=_sample_trades()):
            app = AppTest.from_file(str(PAGE), default_timeout=60)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
            app.run(timeout=60)
            pullback_button = next(
                node for node in app.button if str(node.key or "") == "j3pbf_00"
            )
            pullback_button.click().run(timeout=60)

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
        self.assertTrue(any("j3-pull-table" in value for value in markdowns))
        self.assertTrue(any("NVIDIA" in str(node.label) for node in app.button))
        self.assertTrue(any("j3-down" in value for value in markdowns))
        self.assertEqual(app.session_state.filtered_state.get("j3_pullback_selected_ticker"), "NVDA")
        self.assertTrue(any("눌림목 선택 종목" in value for value in markdowns))
        # 눌림목 상세는 자비스4와 같은 구성이다 — 선정 근거 점수표·매수 심사 결과까지
        # 함께 보여준다(2026-07-24 사용자 지시).
        self.assertTrue(any("종목 선정 근거 (미국형 5개 항목)" in value for value in markdowns))
        self.assertTrue(any("j3-factor-table" in value for value in markdowns))
        self.assertTrue(any("j3-holo-card" in value for value in markdowns))
        self.assertTrue(any("가격 칸이 채워지는 기준" in value for value in markdowns))
        self.assertTrue(any("j3-danta-box" in value for value in markdowns))
        self.assertTrue(any("14일 변동성(ATR)" in value for value in markdowns))
        self.assertTrue(any("종목 조건점수" in value for value in markdowns))
        # 눌림목 표에 당일주가 칸이 있고 값이 채워진다
        self.assertTrue(any("당일주가" in value for value in markdowns))
        self.assertTrue(any("$178.50" in value for value in markdowns))
        # 상단 칸 이름은 '장 상태'가 아니라 '시장 상황'이고 VIX는 붉은색이다
        self.assertTrue(any("시장 상황" in value for value in markdowns))
        self.assertFalse(any(">장 상태<" in value for value in markdowns))
        self.assertTrue(any("실제 매수 기록" in str(node.value) for node in app.markdown))

    def test_pullback_detail_opens_top_ranked_stock_without_click(self):
        """클릭하지 않아도 눌림목 1순위 상세가 바로 열려 있어야 한다(2026-07-24 지시)."""
        with patch("jarvis3_data.get_market_overview", return_value=_market()), \
             patch("jarvis3_data.get_fear_greed", return_value=_fear_greed()), \
             patch("market_signal_ui._fetch_quotes", return_value={}), \
             patch("jarvis3_data.get_theme_rankings", return_value=_ranking()), \
             patch("jarvis3_data.get_theme_leaders", return_value=_leaders()), \
             patch("jarvis3_data.get_live_quote", return_value={
                 "ok": True, "current": 179.0, "change_pct": 1.0, "from_high_pct": -1.0,
                 "ret20": 7.0, "atr_pct": 3.0, "source_time": "x", "stale": False,
             }), \
             patch("jarvis3_data.get_chart_bundle", return_value=_chart_bundle()), \
             patch("jarvis3_data.find_pullback_stocks", return_value=_pullbacks()), \
             patch("jarvis3_store.ensure_tables"), \
             patch("jarvis3_store.trade_progress", return_value={
                 "total_count": 0, "open_count": 0, "closed_count": 0, "minimum_sample": 30,
             }), \
             patch("jarvis3_store.list_trades", return_value=_sample_trades()):
            app = AppTest.from_file(str(PAGE), default_timeout=60)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
            app.run(timeout=60)

            names = [
                str(node.value) for node in app.markdown
                if "<div class='j3-stock-name'>" in str(node.value)
            ]
            # 아무것도 누르지 않은 첫 화면에서 1순위(NVDA) 상세가 이미 열려 있다
            self.assertTrue(any("NVDA" in value for value in names), names)
            self.assertFalse(any("ANET" in value for value in names), names)

            # 2순위를 누르면 그 종목으로 바뀐다
            next(
                node for node in app.button if str(node.key or "") == "j3pbf_01"
            ).click().run(timeout=60)

        self.assertEqual(len(app.exception), 0)
        names_after = [
            str(node.value) for node in app.markdown
            if "<div class='j3-stock-name'>" in str(node.value)
        ]
        self.assertTrue(any("ANET" in value for value in names_after), names_after)
        self.assertEqual(
            app.session_state.filtered_state.get("j3_pullback_selected_ticker"), "ANET"
        )

    def test_theme_selection_click_actually_switches_theme(self):
        """테마 선택 위젯을 실제로 눌러 테마가 바뀌는지 검증한다(st.pills 클릭 불가 회귀 방지)."""
        with patch("jarvis3_data.get_market_overview", return_value=_market()), \
             patch("jarvis3_data.get_fear_greed", return_value=_fear_greed()), \
             patch("market_signal_ui._fetch_quotes", return_value={}), \
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
             patch("jarvis3_store.list_trades", return_value=_sample_trades()):
            app = AppTest.from_file(str(PAGE), default_timeout=60)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
            app.run(timeout=60)
            theme_radio = [node for node in app.radio if str(node.label) == "테마 선택"]
            self.assertEqual(len(theme_radio), 1, "테마 선택 위젯이 클릭 가능한 형태로 있어야 합니다")
            theme_radio[0].set_value("양자컴퓨팅").run(timeout=60)

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.session_state.filtered_state.get("j3_theme_choice"), "양자컴퓨팅")

    def test_form_stock_radio_switches_selection_too(self):
        """매수 폼 안의 상세 종목 선택(아래 라디오)에서 골라도 전체 선택이 바뀐다."""
        with patch("jarvis3_data.get_market_overview", return_value=_market()), \
             patch("jarvis3_data.get_fear_greed", return_value=_fear_greed()), \
             patch("market_signal_ui._fetch_quotes", return_value={}), \
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
             patch("jarvis3_store.list_trades", return_value=_sample_trades()):
            app = AppTest.from_file(str(PAGE), default_timeout=60)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
            app.run(timeout=60)
            stock_radios = [node for node in app.radio if str(node.label) == "상세 종목 선택"]
            self.assertEqual(len(stock_radios), 2, "위·아래 두 곳에 상세 종목 선택이 있어야 합니다")
            stock_radios[1].set_value("AVGO").run(timeout=60)

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.session_state.filtered_state.get("j3_stock_choice_반도체"), "AVGO")

    def test_table_click_and_chart_color_contracts_are_present(self):
        source = PAGE.read_text(encoding="utf-8")
        # 테마 선택은 클릭이 확실한 radio로 유지(st.pills는 이 환경에서 클릭 불가).
        self.assertNotIn("st.pills(", source)
        # 테마표·대장주표 모두 가운데 정렬 HTML 표(선택은 테마/상세 라디오).
        self.assertIn("_render_theme_table", source)
        self.assertIn("j3tbtn_", source)  # 테마명 클릭 버튼
        self.assertIn("_leader_table_html", source)
        self.assertIn("j3-bar-green", source)  # 구성종목 확산 초록 막대
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
        # 새 미국 눌림목 표도 기본 dataframe이 아니라 기존 색·정렬 계약을 따른다.
        self.assertIn("j3-pull-table", source)
        self.assertIn("j3-pull-guide", source)
        self.assertIn("+ 상승은 파랑", source)
        self.assertIn("− 하락은 빨강", source)
        self.assertNotIn("st.dataframe(view, hide_index=True", source)
        self.assertIn("🥇", source)
        self.assertIn('float(leader["score"]) >= 80', source)
        # 2026-07-22 추가 계약: 공포·탐욕 지수 칸, 당일 차트, 매수 기록 현황,
        # 시장판단 신호 카드 재사용, 테마 버튼 키 2자리 고정폭(CSS 부분일치 버그 방지).
        self.assertIn("공포·탐욕 지수", source)
        self.assertIn("_intraday_chart", source)
        self.assertIn("당일 · 실시간(지연 가능)", source)
        self.assertIn("매수 기록 현황", source)
        self.assertIn("render_us_market_signal_card", source)
        # 한국장 수급 카드는 자비스4(국내) 전용 — 미국 페이지에는 넣지 않는다(2026-07-22).
        self.assertNotIn("render_kr_flow_card", source)
        self.assertIn("j3tbtn_{index:02d}", source)

    def test_main_login_includes_jarvis3_destination(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("미국테마 (자비스3)", source)
        self.assertIn('st.switch_page("pages/2_자비스3.py")', source)

    def test_login_can_switch_directly_to_jarvis3(self):
        with patch("jarvis3_data.get_market_overview", return_value=_market()), \
             patch("jarvis3_data.get_fear_greed", return_value=_fear_greed()), \
             patch("market_signal_ui._fetch_quotes", return_value={}), \
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
             patch("jarvis3_store.list_trades", return_value=_sample_trades()):
            app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
            app.secrets["APP_PASSWORD"] = "test"
            app.run(timeout=60)
            app.radio[0].set_value("미국테마 (자비스3)")
            app.text_input[0].set_value("test")
            app.button[0].click().run(timeout=60)

        self.assertEqual(len(app.exception), 0)
        self.assertTrue(app.session_state.filtered_state.get("authenticated"))
        self.assertIn("미국 전체시장 판단", [str(node.value) for node in app.subheader])


if __name__ == "__main__":
    unittest.main()
