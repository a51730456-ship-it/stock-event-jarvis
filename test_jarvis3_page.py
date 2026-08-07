import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import gauge_ui
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).parent
PAGE = ROOT / "pages" / "2_자비스3.py"


def _chart(start=100):
    index = pd.bdate_range("2026-01-01", periods=60)
    return pd.DataFrame({"Close": [start + i * .5 for i in range(60)]}, index=index)


def _market():
    base = {"ok": True, "current": 100.0, "change_pct": 1.0, "sma20": 95, "sma50": 90}
    return {
        "ok": True, "score": 85, "regime": "상승 여건 양호", "posture": "조건 충족 종목만 매수 심사",
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
        "result_pct": None, "market_regime": "방향 엇갈림", "market_score": 65,
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
                "prev_close": 180.94, "day_open": 181.0, "day_high": 182.4,
                "day_low": 177.2, "day_close": 178.5, "day_is_today": True,
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


def _breakout_result(count=1):
    """설명서 1번(상승장 신고가 눌림) 결과 모양.

    '눌림목 찾기'를 뺀 2026-08-06부터 이 갈래가 기본 표라, 줄을 눌러 보는 시험도
    여기로 온다. 그래서 줄 수를 골라 쓸 수 있게 했다.
    """
    rows = [dict(row) for row in _pullbacks()["rows"][:count]]
    for index, row in enumerate(rows):
        row["wait_days"] = 4
        row["hold_days"] = 120
        row["score"] = 80.0 - index
    return {
        "ok": True, "mode": "breakout", "rows": rows,
        # 2026-08-06 새 기준 — 거르는 것은 눌린 폭(10~15%) 하나이고,
        # 날짜는 1~5일로 넓게 두고 표에 보여만 준다.
        "rule": {"wait_days": (1, 5), "drop_band": (-15.0, -10.0), "hold_days": 120,
                 "win_rate": 71.0, "median_return": 12.5,
                 "base_win_rate": 64.4, "base_median_return": 7.1, "per_year": 30},
        # 표를 잰 자리인지 알려만 준다 — 막지 않는다(2026-08-06).
        "market": {"ok": True, "armed": False, "drop_pct": -20.0, "above_200": False,
                   "max_drop": -10.0,
                   "reason": "나스닥이 200일선 아래이고 고점 대비 -20.0%입니다 — "
                             "오늘은 표를 잰 자리가 아닙니다."},
        "universe_count": 200, "data_count": 199, "window_count": 6,
        "result_limit": 20, "checked_at": "x", "stale": False, "reused_batch": False,
    }


def _crash_result():
    """설명서 2번(급락 후 반등장 낙폭 종목) 결과 모양."""
    rows = [dict(row) for row in _pullbacks()["rows"][:1]]
    rows[0].update({
        "bucket": "deep", "bucket_label": "고점 대비 -30~-50%", "hold_days": 120,
        "win_rate": 69.5, "median_return": 16.4, "base_win_rate": 65.4,
    })
    return {
        "ok": True, "mode": "crash", "rows": rows,
        "rules": ({"key": "shallow", "band": (-30.0, -20.0), "hold_days": 120,
                   "win_rate": 74.6, "median_return": 16.9, "base_win_rate": 65.4,
                   "label": "고점 대비 -20~-30%"},
                  {"key": "deep", "band": (-50.0, -30.0), "hold_days": 120,
                   "win_rate": 69.5, "median_return": 16.4, "base_win_rate": 65.4,
                   "label": "고점 대비 -30~-50%"}),
        "bucket_counts": {"shallow": 3, "deep": 1},
        # 2026-08-06부터 나스닥이 -6~-12%일 때만 켜진다.
        "market": {"ok": True, "armed": True, "drop_pct": -9.0,
                   "band": (-12.0, -6.0), "reason": "시험"},
        "universe_count": 200, "data_count": 199,
        "result_limit": 20, "checked_at": "x", "stale": False, "reused_batch": False,
    }


def _open_all_details(app):
    """상세·매수기록을 미리 펴 둔다.

    2026-07-30부터 이 구역들은 눌러야 열린다(사용자 지시). 테스트에서 단추를
    누르면 patch가 이미 풀린 뒤라 시세를 실제로 받으러 나가므로, 세션 값으로
    열어 둔 상태에서 화면을 그린다. 여는 장치 자체는 test_top_reviewed가 지킨다.
    """
    for panel in ("theme", "pullback", "top7", "mystock"):
        app.session_state[f"j3_detail_open_{panel}"] = True
        app.session_state[f"j3_buyform_open_{panel}"] = True
    app.session_state["j3_theme_panel_open"] = True
    return app


class Jarvis3PageTests(unittest.TestCase):
    def test_guest_hides_only_private_score_panels_but_keeps_stock_detail(self):
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
            app.session_state["jarvis_access_role"] = "guest"
            _open_all_details(app)
            app.run(timeout=60)

        self.assertEqual(len(app.exception), 0)
        button_keys = {str(node.key or "") for node in app.button}
        self.assertIn("j3_pullback_breakout", button_keys)
        self.assertIn("j3_pullback_crash", button_keys)
        self.assertNotIn("j3_pullback_find", button_keys)
        self.assertNotIn("j3_top7_find", button_keys)
        self.assertTrue([node for node in app.text_input if node.key == "j3_my_stock_query"])
        self.assertTrue([node for node in app.radio if str(node.label) == "상세 종목 선택"])
        rendered = [str(node.value) for node in app.markdown]
        self.assertTrue([value for value in rendered if "<div class='j3-stock-name'>" in value])
        markdowns = " ".join(rendered)
        self.assertNotIn("<div class='j3-section-title'>종목 선정 근거", markdowns)
        self.assertNotIn("<div class='j3-section-title'>매수 심사 결과</div>", markdowns)
        self.assertNotIn("<div class='j3-section-title'>추천 근거 요약</div>", markdowns)
        self.assertTrue([node for node in app.button if "bundle_open" in str(node.key or "")])

    def test_theme_rank_click_opens_and_close_button_hides_whole_theme_panel(self):
        """20개 순위의 테마 클릭으로 캡처 속 테마 종목 화면 전체를 여닫는다."""
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
            self.assertFalse(app.session_state.filtered_state.get("j3_theme_panel_open", False))
            self.assertFalse([
                node for node in app.button if str(node.key or "").startswith("j3lbtn_")
            ])

            theme_button = next(
                node for node in app.button if str(node.key or "") == "j3tbtn_00"
            )
            theme_button.click().run(timeout=60)
            self.assertTrue(app.session_state.filtered_state.get("j3_theme_panel_open"))
            self.assertTrue([
                node for node in app.button if str(node.key or "").startswith("j3lbtn_")
            ])
            close_button = next(
                node for node in app.button
                if str(node.key or "") == "close_j3_theme_panel_open_top"
            )
            close_button.click().run(timeout=60)

        self.assertEqual(len(app.exception), 0)
        self.assertFalse(app.session_state.filtered_state.get("j3_theme_panel_open"))
        self.assertFalse([
            node for node in app.button if str(node.key or "").startswith("j3lbtn_")
        ])

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
             patch("jarvis3_data.find_breakout_pullback_stocks",
                   return_value=_breakout_result(2)), \
             patch("jarvis3_store.ensure_tables"), \
             patch("jarvis3_store.trade_progress", return_value={
                 "total_count": 0, "open_count": 0, "closed_count": 0, "minimum_sample": 30,
             }), \
             patch("jarvis3_store.list_trades", return_value=_sample_trades()):
            app = AppTest.from_file(str(PAGE), default_timeout=60)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
            _open_all_details(app)
            app.run(timeout=60)
            # 표는 버튼을 눌러야 나온다(2026-07-25 사용자 지시). 한국테마와 같다.
            # '눌림목 찾기'는 2026-08-06에 뺐으므로 상승장 단추로 연다.
            next(
                node for node in app.button
                if str(node.key or "") == "j3_pullback_breakout"
            ).click().run(timeout=60)
            next(
                node for node in app.button if str(node.key or "") == "j3rbf_00"
            ).click().run(timeout=60)

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
        # 일봉·주봉·월봉은 눌러야 받아 온다(2026-07-30) — 여는 단추가 있어야 한다.
        self.assertTrue(any("일봉 · 주봉 · 월봉 보기" in str(node.label) for node in app.button))
        self.assertTrue(any("j3-pull-table" in value for value in markdowns))
        self.assertTrue(any("NVIDIA" in str(node.label) for node in app.button))
        self.assertTrue(any("j3-down" in value for value in markdowns))
        self.assertEqual(app.session_state.filtered_state.get("j3_pullback_selected_ticker"), "NVDA")
        self.assertTrue(any("눌림목 선택 종목" in value for value in markdowns))
        # 눌림목 상세는 자비스4와 같은 구성이다 — 선정 근거 점수표·매수 심사 결과까지
        # 함께 보여준다(2026-07-24 사용자 지시).
        # 2026-08-06 — '눌림목 찾기'를 빼면서 이 시험도 상승장 갈래로 옮겼다.
        # 그래서 점수표 이름이 갈래 전용 배점 이름이 된다.
        self.assertTrue(any("종목 선정 근거 (신고가 눌림 전용 배점)" in value
                            for value in markdowns))
        self.assertTrue(any("j3-factor-table" in value for value in markdowns))
        self.assertTrue(any("j3-holo-card" in value for value in markdowns))
        # 단타 참고 신호는 접어 뒀다(2026-08-06) — 여는 단추가 있어야 한다.
        self.assertTrue(any("단타 참고 신호 보기" in str(node.label) for node in app.button))
        # 당일 가격 칸(자비스4와 같은 구성) — 시가·고가·저가·전일 종가
        self.assertTrue(any("당일 가격 · 시가/고가/저가 한눈에 보기" in value for value in markdowns))
        self.assertTrue(any("전일 종가" in value for value in markdowns))
        self.assertTrue(any("당일 고가" in value for value in markdowns))
        self.assertTrue(any("$182.40" in value for value in markdowns))
        self.assertTrue(any("14일 변동성(ATR)" in value for value in markdowns))
        self.assertTrue(any("종목 조건점수" in value for value in markdowns))
        # 눌림목 표에 당일주가 칸이 있고 값이 채워진다
        self.assertTrue(any("당일주가" in value for value in markdowns))
        self.assertTrue(any("$178.50" in value for value in markdowns))
        self.assertTrue(any("종목 조건점수" in value for value in markdowns))
        # '점수 두 개는 서로 다른 것을 잽니다'는 없앤 눌림목 찾기 설명에 있던 말이다.
        # 맨 위에서 세 갈래를 뭉뚱그려 설명하지 않는다(2026-08-06 상하님 지적) —
        # 갈래마다 제 설명이 자기 안에 있다.
        self.assertFalse(any("눌림목 종목 찾기 설명 보기" in str(node.label)
                             for node in app.expander),
                         "없앤 눌림목 찾기 설명이 되살아났다")
        # 상단 칸 이름은 '장 상태'가 아니라 '시장 상황'이고 VIX는 붉은색이다
        self.assertTrue(any("시장 상황" in value for value in markdowns))
        # 공포·탐욕 게이지(반원 그림)를 상단에 넣었다. 구간 이름은 한국어다.
        self.assertTrue(any("fg-gauge" in value for value in markdowns))
        self.assertTrue(any("fg-needle" in value for value in markdowns))
        self.assertTrue(any("전일 종가" in value for value in markdowns))
        self.assertFalse(any("EXTREME FEAR" in value for value in markdowns))
        # 게이지는 상단 지표 줄 안, 숫자 칸 바로 옆에 있어야 한다.
        top_row = next(value for value in markdowns if "<div class='j3-top-row'>" in value)
        self.assertIn("fg-box", top_row)
        self.assertIn("공포·탐욕 지수", top_row)
        self.assertIn("SPY (미국 대표주)", top_row)
        self.assertIn("QQQ (미국 기술주)", top_row)
        self.assertTrue(any("j3-ndd-key" in value for value in markdowns))
        source = PAGE.read_text(encoding="utf-8")
        self.assertIn("j3-ndd-title", source)
        self.assertIn("color:{_sign_color(pct)}", source)
        self.assertIn(".j3-ndd-sub { color: #9aa0aa; font-size: 1rem", source)
        self.assertTrue(any("j3-theme-open-guide" in value for value in markdowns))
        page_css = next(value for value in markdowns if "st-key-close_j3_theme_panel_open" in value)
        self.assertIn("#c084fc", page_css)
        self.assertIn("background: rgba(255,255,255,.025)", page_css)
        self.assertIn("justify-content: center", page_css)
        self.assertIn("#ef4b55", page_css)
        self.assertIn("color: #ffffff", page_css)
        # <style>을 지표 줄 안에 넣으면 스트림릿이 그 덩어리를 HTML로 안 보고 글로
        # 흘려버려 CSS가 글자로 찍힌다(2026-07-24 실제 깨짐). 반드시 따로 내보낸다.
        self.assertNotIn("<style>", top_row)
        self.assertFalse(any(">장 상태<" in value for value in markdowns))
        self.assertTrue(any("실제 매수 기록" in str(node.value) for node in app.markdown))

    def test_top7_click_opens_detail_even_though_it_lives_in_a_fragment(self):
        """순위 7을 프래그먼트로 묶은 뒤에도 표→상세가 이어지는지 (2026-07-30).

        묶은 이유는 속도다 — 단추 한 번에 판 전체를 다시 그리던 것을 이 덩이만
        다시 그리게 했다. 다만 표만 묶고 상세를 밖에 두면 종목을 눌러도 상세가
        다시 안 그려진다. 그래서 둘을 같은 덩이에 넣었고, 이 시험이 그것을 지킨다.
        """
        found = {
            "ok": True,
            "rows": [{**row, "pick_rank": index, "sources": ["반도체"]}
                     for index, row in enumerate(_leaders()["rows"][:2], 1)],
            "scanned_themes": 3, "candidate_count": 2, "errors": [],
        }
        with patch("jarvis3_data.get_market_overview", return_value=_market()), \
             patch("jarvis3_data.get_fear_greed", return_value=_fear_greed()), \
             patch("market_signal_ui._fetch_quotes", return_value={}), \
             patch("jarvis3_data.get_theme_rankings", return_value=_ranking()), \
             patch("jarvis3_data.get_theme_leaders", return_value=_leaders()), \
             patch("jarvis3_data.find_top_reviewed_stocks", return_value=found), \
             patch("jarvis3_data.get_chart_bundle", return_value=_chart_bundle()), \
             patch("jarvis3_data.get_live_quote", return_value={
                 "ok": True, "current": 179.0, "change_pct": 1.0, "from_high_pct": -1.0,
                 "ret20": 7.0, "atr_pct": 3.0, "source_time": "x", "stale": False,
             }), \
             patch("jarvis3_store.ensure_tables"), \
             patch("jarvis3_store.trade_progress", return_value={
                 "total_count": 0, "open_count": 0, "closed_count": 0, "minimum_sample": 30,
             }), \
             patch("jarvis3_store.list_trades", return_value=[]):
            app = AppTest.from_file(str(PAGE), default_timeout=60)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
            _open_all_details(app)
            app.run(timeout=60)
            next(
                node for node in app.button if str(node.key or "") == "j3_top7_find"
            ).click().run(timeout=60)
            next(
                node for node in app.button if str(node.key or "") == "j3top7_00"
            ).click().run(timeout=60)

        self.assertEqual(len(app.exception), 0)
        self.assertTrue(
            any("순위 7에서 고른 종목" in str(node.value) for node in app.markdown),
            "종목을 눌렀는데 상세가 안 열렸다",
        )

    def test_pullback_detail_opens_top_ranked_stock_without_click(self):
        """종목을 찾고 나면 누르지 않아도 1순위 상세가 열려 있어야 한다.

        2026-07-24 지시(1순위 자동 열림)는 그대로 두고, 2026-07-25 지시에 따라
        표 자체는 단추를 누른 뒤에 나온다. '눌림목 찾기'를 뺀 2026-08-06부터는
        상승장 단추로 연다.
        """
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
             patch("jarvis3_data.find_breakout_pullback_stocks",
                   return_value=_breakout_result(2)), \
             patch("jarvis3_store.ensure_tables"), \
             patch("jarvis3_store.trade_progress", return_value={
                 "total_count": 0, "open_count": 0, "closed_count": 0, "minimum_sample": 30,
             }), \
             patch("jarvis3_store.list_trades", return_value=_sample_trades()):
            app = AppTest.from_file(str(PAGE), default_timeout=60)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
            _open_all_details(app)
            app.run(timeout=60)
            # 표는 버튼을 눌러야 나온다. 누르기 전에는 안내만 보인다.
            self.assertFalse(any(str(node.key or "") == "j3rbf_00" for node in app.button))
            next(
                node for node in app.button
                if str(node.key or "") == "j3_pullback_breakout"
            ).click().run(timeout=60)

            names = [
                str(node.value) for node in app.markdown
                if "<div class='j3-stock-name'>" in str(node.value)
            ]
            # 아무것도 누르지 않은 첫 화면에서 1순위(NVDA) 상세가 이미 열려 있다
            self.assertTrue(any("NVDA" in value for value in names), names)
            self.assertFalse(any("ANET" in value for value in names), names)

            # 2순위를 누르면 그 종목으로 바뀐다
            next(
                node for node in app.button if str(node.key or "") == "j3rbf_01"
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

    def test_mobile_rules_are_emitted_and_scoped_to_phones(self):
        """폰 전용 규칙이 나가야 하고, 태블릿·PC가 바뀌면 안 된다(2026-07-24)."""
        with patch("jarvis3_data.get_market_overview", return_value=_market()),              patch("jarvis3_data.get_fear_greed", return_value=_fear_greed()),              patch("market_signal_ui._fetch_quotes", return_value={}),              patch("jarvis3_data.get_theme_rankings", return_value=_ranking()),              patch("jarvis3_data.get_theme_leaders", return_value=_leaders()),              patch("jarvis3_data.get_live_quote", return_value={
                 "ok": True, "current": 179.0, "change_pct": 1.0, "from_high_pct": -1.0,
                 "ret20": 7.0, "atr_pct": 3.0, "source_time": "x", "stale": False,
             }),              patch("jarvis3_data.get_chart_bundle", return_value=_chart_bundle()),              patch("jarvis3_data.find_pullback_stocks", return_value=_pullbacks()),              patch("jarvis3_store.ensure_tables"),              patch("jarvis3_store.trade_progress", return_value={
                 "total_count": 0, "open_count": 0, "closed_count": 0, "minimum_sample": 30,
             }),              patch("jarvis3_store.list_trades", return_value=_sample_trades()):
            app = AppTest.from_file(str(PAGE), default_timeout=60)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
            _open_all_details(app)
            app.run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        blocks = [str(n.value) for n in app.markdown if "@media (max-width: 600px)" in str(n.value)]
        self.assertEqual(len(blocks), 1)
        css = blocks[0]
        # 미디어쿼리는 다섯 — 메뉴·상단 지표 줄은 태블릿까지(1200px), 그 중
        # '한 줄에 몇 칸'은 세로·가로 두 갈래(2026-08-01), 표·글자는 폰(600px).
        self.assertEqual(css.count("@media"), 5)
        self.assertEqual(css[: len("<style>")], "<style>")
        self.assertEqual(css[len("<style>"): css.index("@media")].strip(), "")
        phone_block = css[css.index("@media (max-width: 600px)"):]
        # 두 표는 세로로 쌓지 않고 옆으로 밀어 보므로 표·머리글 규칙이 폰 규칙에 없다.
        # 상단 지표 줄(.fg-box)은 태블릿까지 걸리게 1200px 묶음으로 옮겼다.
        self.assertNotIn(".fg-box { order", phone_block)
        self.assertIn(".fg-box { order", css)
        self.assertIn("@media (max-width: 1200px)", css)
        self.assertNotIn("st-key-j3pbf_", phone_block)
        # 대신 표를 감싸는 스크롤 상자가 페이지에 있어야 한다.
        page_source = PAGE.read_text(encoding="utf-8")
        self.assertIn('st.container(key="j3_theme_table")', page_source)
        self.assertIn('st.container(key="j3_pullback_table")', page_source)
        self.assertIn(".st-key-j3_pullback_table", page_source)
        # 메뉴 규칙은 폰 묶음 밖(태블릿까지)에 있어야 한다.
        self.assertNotIn("stSidebarNav", phone_block)


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
            _open_all_details(app)
            app.run(timeout=60)
            theme_radio = [node for node in app.radio if str(node.label) == "테마 선택"]
            self.assertEqual(len(theme_radio), 1, "테마 선택 위젯이 클릭 가능한 형태로 있어야 합니다")
            theme_radio[0].set_value("양자컴퓨팅").run(timeout=60)

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.session_state.filtered_state.get("j3_theme_choice"), "양자컴퓨팅")

    def test_current_leader_name_click_opens_the_detail(self):
        """이미 선택된 첫 종목을 눌러도 닫혀 있던 상세가 즉시 열린다.

        선택값이 같다는 이유로 클릭을 무시하면 첫 행은 눌러도 아무 일이 없었다.
        '상세 종목 선택' 라디오는 그대로 남아 있어야 한다.
        """
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
            _open_all_details(app)
            app.session_state["j3_detail_open_theme"] = False
            app.session_state["j3_leadercmp_open"] = False
            app.run(timeout=60)
            buttons = [node for node in app.button if str(node.key or "").startswith("j3lbtn_")]
            self.assertTrue(buttons, "종목 이름 버튼이 없다 — 표가 눌리지 않는다")
            buttons[0].click().run(timeout=60)

        self.assertEqual(len(app.exception), 0)
        state = app.session_state.filtered_state
        chosen = next(
            (value for key, value in state.items() if str(key).startswith("j3_stock_choice_")),
            None,
        )
        self.assertIsNotNone(chosen, state)
        self.assertTrue(state.get("j3_detail_open_theme"), state)
        self.assertTrue(state.get("j3_leadercmp_open"), state)
        self.assertTrue(any("j3-stock-name" in str(node.value) for node in app.markdown))
        # 라디오는 지우지 않았다(사용자 지시).
        self.assertTrue([node for node in app.radio if str(node.label) == "상세 종목 선택"])

    def test_my_stock_panel_searches_and_opens_detail(self):
        """맨 아래 '내 종목 현재상황'에서 이름을 치면 종목이 뜨고 상세가 열린다."""
        found = {"ok": True, "rows": [
            {"ticker": "NVDA", "name": "NVIDIA Corp", "market": "NASDAQ"},
        ]}
        analyzed = {"ok": True, "row": {
            **_leaders()["rows"][0], "ticker": "NVDA", "name": "NVIDIA",
            "rank": 0, "from_search": True,
        }}
        with patch("jarvis3_data.get_market_overview", return_value=_market()), \
             patch("jarvis3_data.get_fear_greed", return_value=_fear_greed()), \
             patch("market_signal_ui._fetch_quotes", return_value={}), \
             patch("jarvis3_data.get_theme_rankings", return_value=_ranking()), \
             patch("jarvis3_data.get_theme_leaders", return_value=_leaders()), \
             patch("jarvis3_data.get_chart_bundle", return_value=_chart_bundle()), \
             patch("jarvis3_data.search_stocks", return_value=found), \
             patch("jarvis3_data.analyze_one_stock", return_value=analyzed), \
             patch("jarvis3_store.ensure_tables"), \
             patch("jarvis3_store.trade_progress", return_value={
                 "total_count": 0, "open_count": 0, "closed_count": 0, "minimum_sample": 30,
             }), \
             patch("jarvis3_store.list_trades", return_value=_sample_trades()):
            app = AppTest.from_file(str(PAGE), default_timeout=60)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
            _open_all_details(app)
            app.run(timeout=60)
            box = next(
                node for node in app.text_input if str(node.key or "") == "j3_my_stock_query"
            )
            box.set_value("엔비디아").run(timeout=60)

        self.assertEqual(len(app.exception), 0)
        blob = "".join(str(node.value) for node in app.markdown)
        captions = "".join(str(node.value) for node in app.caption)
        self.assertIn("종목검색 (검색종목 세부사항 보기)", blob)
        # 미국 종목이라도 한글로 칠 수 있다는 것을 화면이 알려 준다.
        self.assertIn("한글로 쳐도 됩니다", captions)
        self.assertIn("NVIDIA", blob)

    def test_korean_aliases_cover_the_common_names(self):
        """'영어로만 쳐야 하나'에 대한 답 — 널리 쓰는 한글 이름은 티커로 이어 준다."""
        import jarvis3_data as j3

        for korean, ticker in (("엔비디아", "NVDA"), ("애플", "AAPL"),
                               ("테슬라", "TSLA"), ("팔란티어", "PLTR")):
            self.assertEqual(j3.KOREAN_TICKER_ALIASES.get(korean), ticker)

    def test_leader_table_scrolls_sideways_like_the_others(self):
        """폰·태블릿에서 종목표도 옆으로 밀려야 한다(칸 방식으로 바꾼 뒤 확인)."""
        with patch("jarvis3_data.get_market_overview", return_value=_market()), \
             patch("jarvis3_data.get_fear_greed", return_value=_fear_greed()), \
             patch("market_signal_ui._fetch_quotes", return_value={}), \
             patch("jarvis3_data.get_theme_rankings", return_value=_ranking()), \
             patch("jarvis3_data.get_theme_leaders", return_value=_leaders()), \
             patch("jarvis3_data.get_chart_bundle", return_value=_chart_bundle()), \
             patch("jarvis3_store.ensure_tables"), \
             patch("jarvis3_store.trade_progress", return_value={
                 "total_count": 0, "open_count": 0, "closed_count": 0, "minimum_sample": 30,
             }), \
             patch("jarvis3_store.list_trades", return_value=_sample_trades()):
            app = AppTest.from_file(str(PAGE), default_timeout=60)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
            _open_all_details(app)
            app.run(timeout=60)
        blob = "".join(str(node.value) for node in app.markdown)
        self.assertIn(".st-key-j3_leader_table,", blob)
        self.assertIn('.st-key-j3_leader_table [data-testid="stHorizontalBlock"]', blob)
        self.assertIn('.st-key-j3_leader_table [data-testid="stColumn"]', blob)
        # 눌림목 찾기 버튼도 한국테마와 같은 색이어야 한다.
        self.assertIn('div[class*="st-key-j3_pullback_find"] button', blob)
        self.assertIn("#cfe9ff", blob)

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
            _open_all_details(app)
            app.run(timeout=60)
            # 매수 기록은 눌러야 열린다(2026-07-30 사용자 지시) — _open_all_details가
            # 미리 열어 둔 상태다. 열려 있으면 그 안의 '상세 종목 선택'(복제)도 있다.
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
        self.assertIn("j3-leader-head-gap", source)
        self.assertIn("theme_box.markdown", source)
        self.assertIn("if clicked_ticker:", source)
        # 2026-08-06 — 표에서 종목을 누르면 상세만 열리고 차트는 안 열려서
        # 단추를 또 눌러야 했다. 이제 당일 차트와 일봉·주봉·월봉까지 한 번에 편다.
        for opened in ("j3_detail_open_theme", "j3_intraday_open_theme",
                       "j3_bundle_open_theme", "j3_leadercmp_open"):
            self.assertIn(f'"{opened}"', source, f"{opened}를 안 연다")
        self.assertIn("get_chart_bundle", source)
        self.assertIn('range=["#69bff8", "#ff4d4f", "#a855f7"]', source)
        # 색·메달 계약: 종목명 보라 / 라벨 코발트 / 점수 붉은 / 메달 80점 이상만
        self.assertIn("j3-stock-name", source)
        self.assertIn("j3-section-title", source)
        self.assertIn("j3-leader-score", source)
        # 새 미국 눌림목 표도 기본 dataframe이 아니라 기존 색·정렬 계약을 따른다.
        self.assertIn("j3-pull-table", source)
        self.assertIn("j3-pull-guide", source)
        # '+ 상승은 파랑 · − 하락은 빨강' 줄은 없앤 눌림목 찾기 설명에 있었다.
        # 그 설명을 통째로 뺐다(2026-08-06) — 색 규칙 자체는 아래 클래스가 지킨다.
        self.assertIn(".j3-up { color: #4da6ff", source)
        self.assertIn(".j3-down { color: #ff5b5b", source)
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

    def _run_with_mode(self, mode, finder_name, finder_result, *, help_open=True):
        """설명서 갈래 단추를 눌렀을 때의 화면을 그린다 (2026-08-01).

        설명은 2026-08-06부터 접혀 있다(사용자 지시). 글을 확인하는 시험은
        열어 둔 상태로 그리고, 접혀 있는지 자체는 help_open=False로 확인한다.
        """
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
             patch(f"jarvis3_data.{finder_name}", return_value=finder_result), \
             patch("jarvis3_store.ensure_tables"), \
             patch("jarvis3_store.trade_progress", return_value={
                 "total_count": 0, "open_count": 0, "closed_count": 0, "minimum_sample": 30,
             }), \
             patch("jarvis3_store.list_trades", return_value=_sample_trades()):
            app = AppTest.from_file(str(PAGE), default_timeout=60)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
            _open_all_details(app)
            app.session_state["j3_pullback_open"] = True
            app.session_state["j3_pullback_mode"] = mode
            app.session_state["j3_pullback_result"] = finder_result
            app.session_state["j3_rulebook_help_open"] = bool(help_open)
            app.run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        return app

    def test_only_the_two_rulebook_buttons_remain(self):
        """'눌림목 찾기'는 뺐다(2026-08-06 사용자 지시).

        목적이 '상승장(신고가 눌림매수)'과 같은데 10년치로 재 보니 기준선을
        못 이겼다 — 평상시 57번(기준선 57번), 급락장 54번(기준선 61번).
        """
        app = self._run_with_mode("breakout", "find_breakout_pullback_stocks",
                                  _breakout_result())
        keys = [str(node.key or "") for node in app.button]
        for key in ("j3_pullback_breakout", "j3_pullback_crash"):
            self.assertIn(key, keys, f"{key} 단추가 없다")
        self.assertNotIn("j3_pullback_find", keys, "눌림목 찾기가 되살아났다")

    def test_breakout_mode_shows_the_written_rule_and_its_own_columns(self):
        app = self._run_with_mode("breakout", "find_breakout_pullback_stocks", _breakout_result())
        markdowns = [str(node.value) for node in app.markdown]
        joined = " ".join(markdowns)
        # 화면이 실제로 찾는 숫자가 그대로 나와야 한다(2026-08-06 새 기준).
        self.assertIn("10~15%", joined)
        self.assertIn("1~5거래일", joined)
        self.assertIn("120거래일", joined)
        # 성적 옆에는 늘 기준선이 붙어야 한다.
        self.assertIn("아무 날 아무 종목이나", joined)
        # 눌림목 표가 아니라 이 갈래 전용 표다 — 머리글에 '보유일수'가 있고
        # '눌림 점수'는 없다(설명 글에는 그 말이 남아 있으므로 머리글만 본다).
        header = next(value for value in markdowns if "보유일수" in value and "티커" in value)
        self.assertNotIn("눌림 점수", header)
        self.assertLess(header.index("고점 대비"), header.index("소속 테마"))
        # 며칠 지났는지는 거르지 않고 보여만 준다 — 칸 이름이 그 뜻이어야 한다.
        self.assertLess(header.index("소속 테마"), header.index("고점 후 며칠"))
        self.assertIn("j3rbf_00", [str(node.key or "") for node in app.button])
        self.assertTrue(any(
            "상승장 (신고가 눌림매수) 닫기" in str(node.label)
            for node in app.button
        ))
        # 표를 잰 자리가 아니면 빨간 줄로 알린다 — 그래도 종목은 그대로 나온다
        # (2026-08-06 사용자 결정). 막으면 화면이 통째로 비는 날이 생긴다.
        self.assertTrue(any(
            "표를 잰 자리가 아닙니다" in str(node.value) for node in app.error
        ), "표를 잰 자리가 아닌데 빨간 줄이 없다")
        self.assertEqual(1, len([
            node for node in app.button if str(node.key or "").startswith("j3rbf_")
        ]), "알림만 해야 하는데 종목이 사라졌다")

    def test_crash_mode_shows_both_depth_buckets_and_holding_periods(self):
        app = self._run_with_mode("crash", "find_crash_rebound_stocks", _crash_result())
        joined = " ".join(str(node.value) for node in app.markdown)
        self.assertIn("고점 대비 -20~-30%", joined)
        self.assertIn("고점 대비 -30~-50%", joined)
        self.assertIn("120거래일 보유", joined)
        # 2026-08-06 — 점수가 순위다(별점은 뺐다). 배점표를 화면에 그대로 뿌린다.
        self.assertIn("점수가 곧 순위입니다", joined)
        self.assertNotIn("★", joined, "별점이 되살아났다")
        for item in ("같은 테마 동반", "40점", "최근 11일에 빠졌나", "25점", "낙폭 갈래"):
            self.assertIn(item, joined, f"배점표에 {item}이 없다")
        # 0점으로 뺀 항목도 왜 뺐는지 같이 보여야 같은 실수를 되풀이하지 않는다.
        self.assertIn("거래대금 평소 위 연속", joined)
        self.assertIn("0점", joined)
        header = next(
            str(node.value) for node in app.markdown
            if "갈래" in str(node.value) and "티커" in str(node.value)
        )
        self.assertLess(header.index("고점 대비"), header.index("소속 테마"))
        self.assertLess(header.index("소속 테마"), header.index("갈래"))
        # 승률이 광고로 읽히지 않게 하는 경고가 반드시 함께 있어야 한다.
        self.assertIn("앞으로의 승률이 아닙니다", joined)
        self.assertTrue(any(
            "급락 후 반등장 (낙폭종목) 닫기" in str(node.label)
            for node in app.button
        ))
        source = (ROOT / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
        block = source.split("def _render_rulebook_finder(")[1].split("\ndef ")[0]
        self.assertLess(block.index("j3-pull-stats"), block.index("mode_close_label"))
        self.assertLess(block.index("mode_close_label"), block.index("widths ="))
        self.assertNotIn("avg_text", block)
        self.assertNotIn("together_label", block)
        for hold_class in ("j3-hold-20", "j3-hold-60", "j3-hold-120"):
            self.assertIn(hold_class, block)

    def test_the_two_depth_buckets_get_different_colours(self):
        """두 갈래를 색으로 가른다(2026-08-01 지시).

        설명 카드와 표의 같은 갈래가 같은 색이어야 카드를 보고 줄을 찾을 수 있다.
        갈래는 2026-08-06에 -20~-30% / -30~-50%로 바뀌었다.
        """
        app = self._run_with_mode("crash", "find_crash_rebound_stocks", _crash_result())
        joined = " ".join(str(node.value) for node in app.markdown)
        for name in ("j3-band-deep", "j3-card-deep", "j3-card-mid"):
            self.assertIn(name, joined, f"{name} 색이 화면에 안 실렸다")
        # 표 칸에는 '고점 대비'를 빼고 숫자만 — 폰에서 옆 칸을 덮었다.
        self.assertIn("j3-band-deep'>-30~-50%", joined)

    def test_crash_detail_uses_the_crash_ruler_not_the_ordinary_one(self):
        """낙폭 종목을 누르면 낙폭 전용 배점이 나와야 한다(2026-08-01).

        기존 조건점수는 '신고가에 가까운가·이동평균 위인가'로 절반을 준다. 낙폭
        종목은 그 조건을 정의상 하나도 못 맞춰 전부 '제외'로 나왔다 — 찾아 놓고
        사지 말라는 화면이었다.
        """
        app = self._run_with_mode("crash", "find_crash_rebound_stocks", _crash_result())
        joined = " ".join(str(node.value) for node in app.markdown)
        self.assertIn("급락 반등 전용 배점", joined)
        self.assertIn("낙폭 갈래", joined)
        # 이 규칙에는 기준가도 손절도 없다 — 없는 것을 있는 것처럼 적으면 안 된다.
        # (‘2R 목표’·‘조건 기준가’는 위쪽 테마 대장주 상세에도 나오므로, 이 갈래의
        #  칸이 그것으로 채워지지 않았는지는 아래 소스 검사로 함께 지킨다.)
        self.assertIn("이 규칙에는 없음", joined)
        # 2026-08-06 — 같은 말이 한 화면에 여섯 번 나온다는 지적을 받고 ※ 두 줄을
        # 뺐다. 손절이 없다는 사실은 위 카드('손절가 — 이 규칙에는 없음')와
        # 왼쪽 겨자색 상자가 말한다. 그 둘은 남아 있어야 한다.
        self.assertNotIn("이 규칙에는 기준가도 손절가도 없습니다", joined)
        # 2026-08-07부터 겨자색 상자는 중요한 말만 굵게 뽑는다. '손절가가 없습니다'가
        # <span>으로 감싸이므로 앞말과 붙어 있지 않다 — 두 토막으로 나눠 본다.
        self.assertIn("이 규칙에는 ", joined)
        self.assertIn("j3-mn-key'>손절가가 없습니다", joined)
        source = (ROOT / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
        block = source.split("def _render_pullback_detail(")[1].split("\ndef ")[0]
        self.assertIn('if mode in ("crash", "breakout"):', block)

    def test_breakout_detail_uses_the_breakout_ruler(self):
        app = self._run_with_mode("breakout", "find_breakout_pullback_stocks",
                                  _breakout_result())
        joined = " ".join(str(node.value) for node in app.markdown)
        self.assertIn("신고가 눌림 전용 배점", joined)
        # 2026-08-06 — 60일 상승폭은 배점에서 뺐다(뒤 5년에 졌다). 그 자리를
        # '최근 11일에 빠졌나'가 대신한다. 두 갈래가 같은 항목을 쓴다.
        self.assertIn("최근 11일에 빠졌나", joined)
        self.assertNotIn("최근 60일 상승폭</td>", joined)
        # 상승장에서는 거래대금 연속이 거꾸로였다 — 표 칸에서 빠져야 한다.
        self.assertNotIn("거래대금 (평소 위 연속)", joined)
        self.assertIn("이 규칙에는 없음", joined)

    def test_crash_detail_says_the_market_by_the_reference_day(self):
        """기준일로 찾아 놓고 오늘 낙폭으로 판정하면 앞뒤가 안 맞는다(2026-08-06).

        표는 7/29(-11.5%) 기준으로 찾아 놓고, 상세의 '시장 근거'만
        "오늘 -4.1%라 이 규칙을 쓸 자리가 아닙니다"라고 말하고 있었다.
        """
        reference = {"ok": True, "armed": True, "reference_date": "2026-07-29",
                     "reference_drop": -11.5, "today_drop": -4.1,
                     "days_in_band": 10, "last_in_band": "2026-08-03", "reason": ""}
        with patch("jarvis3_data.crash_reference_day", return_value=reference):
            app = self._run_with_mode("crash", "find_crash_rebound_stocks",
                                      _crash_result())
        joined = " ".join(str(node.value) for node in app.markdown)
        self.assertIn("2026-07-29 기준으로 찾았습니다", joined)
        self.assertIn("-11.5%", joined)
        # 오늘 낙폭으로 "쓸 자리가 아니다"라고 말하지 않는다.
        self.assertNotIn("이 규칙은 6~12% 내려왔을 때 씁니다", joined)
        # 하락폭은 붉은색 진하게(2026-08-06 지시).
        self.assertIn("color:#ff5b5b; font-weight:900", joined)

    def test_only_the_crash_screen_warns_that_the_order_barely_matters(self):
        """급락 화면에만 붙이는 경고다(2026-08-06).

        점수가 96·95·92로 크게 찍혀 1등이 확실히 좋아 보이는데, 재 보면 1등과
        10등 차이가 100번에 1~3번이다. 상승장은 테마 하나로 앞 +8.6 / 뒤 +2.5라
        순위가 실제로 갈리므로 안 붙인다.
        """
        crash = self._run_with_mode("crash", "find_crash_rebound_stocks", _crash_result())
        self.assertTrue(
            any("순위가 성적을 거의 못 가립니다" in str(node.value) for node in crash.caption),
            "급락 화면에 경고가 없다")
        up = self._run_with_mode("breakout", "find_breakout_pullback_stocks",
                                 _breakout_result())
        self.assertFalse(
            any("순위가 성적을 거의 못 가립니다" in str(node.value) for node in up.caption),
            "상승장 화면에까지 경고가 붙었다")

    def test_the_long_explanation_is_folded_until_asked_for(self):
        """설명은 눌러야 나온다(2026-08-06 사용자 지시 — 설명이 첫 화면을 다 먹었다).

        접혀 있어도 **종목 표와 오늘 이야기 한 줄은 그대로 보여야** 한다.
        """
        app = self._run_with_mode("breakout", "find_breakout_pullback_stocks",
                                  _breakout_result(), help_open=False)
        joined = " ".join(str(node.value) for node in app.markdown)
        self.assertNotIn("점수를 매기는 기준", joined, "설명이 접히지 않았다")
        self.assertNotIn("찾는 그물", joined, "설명이 접히지 않았다")
        self.assertTrue(any("이 화면 설명 보기" in str(node.label) for node in app.button),
                        "설명을 펴는 단추가 없다")
        # 접혀 있어도 표와 오늘 이야기는 남는다.
        self.assertIn("j3rbf_00", [str(node.key or "") for node in app.button])
        self.assertTrue(any("표를 잰 자리가 아닙니다" in str(node.value) for node in app.error))
        # 펴면 설명과 닫기 단추가 같이 나온다.
        opened = self._run_with_mode("breakout", "find_breakout_pullback_stocks",
                                     _breakout_result())
        joined_open = " ".join(str(node.value) for node in opened.markdown)
        self.assertIn("점수를 매기는 기준", joined_open)
        self.assertTrue(any("설명 닫기" in str(node.label) for node in opened.button),
                        "닫기 단추가 없다")

    def test_only_ten_rows_are_open_and_the_rest_are_folded(self):
        """급락 표가 20줄이라 화면이 너무 길었다(2026-08-06 사용자 지시).

        처음에는 앞 15줄이었고, 2026-08-07에 **10줄**로 더 줄였다(상하님 지시).
        나머지는 '11위~20위 더 보기'로 접는다.
        """
        result = _crash_result()
        rows = []
        for index in range(20):
            row = dict(result["rows"][0])
            row["ticker"] = f"T{index:02d}"
            row["name"] = f"종목{index:02d}"
            rows.append(row)
        result = {**result, "rows": rows}
        app = self._run_with_mode("crash", "find_crash_rebound_stocks", result)
        # 스무 줄이 다 그려지되(단추 키가 20개), 11번째부터는 접힌 자리에 있다.
        keys = [str(node.key or "") for node in app.button]
        self.assertIn("j3rbf_00", keys)
        self.assertIn("j3rbf_19", keys)
        self.assertTrue(
            any("11위~20위 더 보기" in str(node.label) for node in app.expander),
            "더 보기 접이가 없다")

    def test_the_drawdown_cell_names_each_of_its_three_numbers(self):
        """숫자 셋이 무엇인지 화면 어디에도 없었다(2026-08-07 상하님 지적).

        '-21.78%' 아래에 '지금 -12.69% · +11.0%'를 한 줄로 붙여 뒀는데, 그
        +11.0%가 무엇인지 설명이 없었고 칸보다 길어 좁은 화면에서 양옆이
        잘렸다(캡처에 '금 -12.69% · +11.'로 찍혔다). 줄마다 이름을 붙인다.
        """
        result = _crash_result()
        rows = [dict(result["rows"][0])]
        rows[0].update({
            "judged_from_high_pct": -21.78, "now_from_high_pct": -12.69,
            "since_reference_pct": 11.63, "reference_date": "2026-07-14",
        })
        result = {**result, "rows": rows,
                  "reference": {"armed": True, "reference_date": "2026-07-14"}}
        app = self._run_with_mode("crash", "find_crash_rebound_stocks", result)
        joined = " ".join(str(node.value) for node in app.markdown)
        cell = next(part for part in joined.split("j3-dd-line")[1:2])
        self.assertIn("그날", cell)
        for label in ("그날", "지금", "그 뒤"):
            self.assertIn(f"j3-dd-k'>{label}<", joined, f"‘{label}’ 이름이 없다")
        # 칸 이름은 '그날 고점 대비'가 아니라 '고점 대비' 하나다 — 줄마다 이름이 있다.
        self.assertNotIn("그날 고점 대비", joined)
        # 셋이 무엇인지 설명하는 줄이 표 위에 있어야 한다.
        self.assertIn("‘고점 대비’ 칸의 숫자 셋", joined)
        self.assertIn("갈래와 점수는 ‘그날’로 정합니다", joined)

    def test_the_score_has_its_own_column_next_to_the_rank(self):
        """점수는 순위 칸이 아니라 **다음 칸**이다(2026-08-06 사용자 지시).

        순위 칸에 같이 넣었더니 '1'과 '58점'이 붙어 158점처럼 읽혔다.
        """
        app = self._run_with_mode("breakout", "find_breakout_pullback_stocks",
                                  _breakout_result())
        header = next(
            str(node.value) for node in app.markdown
            if "j3-th-head" in str(node.value) and "점수" in str(node.value)
        )
        self.assertIn("점수", header)
        source = (ROOT / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
        block = source.split("def _render_rulebook_finder(")[1].split("\ndef ")[0]
        self.assertLess(block.index("'j3-th-head'>순위"), block.index("'j3-th-head'>점수"))
        self.assertLess(block.index("'j3-th-head'>점수"), block.index("'j3-th-head'>종목"))

    def test_the_detail_says_each_thing_once(self):
        """같은 말을 되풀이하지 않는다(2026-08-06 상하님 지적).

        예전에는 '이 규칙에는 손절가가 없습니다'가 한 화면에 여섯 번,
        '52주 신고가를 찍고…'가 세 번 나왔다.
        """
        app = self._run_with_mode("breakout", "find_breakout_pullback_stocks",
                                  _breakout_result())
        joined = " ".join(
            [str(node.value) for node in app.markdown]
            + [str(node.value) for node in app.success]
            + [str(node.value) for node in app.warning]
        )
        self.assertLessEqual(joined.count("52주 신고가를 찍고"), 1,
                             "종목 근거 문장이 여러 번 나온다")
        # 금액만 보여주던 칸을 '얼마나 늘었나'로 바꿨다.
        self.assertIn("거래량 (어제 대비)", joined)
        self.assertNotIn("평균 거래대금", joined)
        # 점수는 하나만 — '이 갈래 점수'·'눌림 점수'가 같이 있어 헷갈렸다.
        # ('눌림 점수'는 이 페이지의 다른 표(A 규칙)에도 있으므로 이 여섯 칸 안에서만 본다.)
        self.assertNotIn("이 갈래 점수", joined)
        # 이 페이지에는 여섯 칸짜리 상자가 여럿이다(테마 대장주 상세에도 있다).
        # 갈래 상세의 것만 '거래량 (어제 대비)' 칸을 가진다.
        cards = next(str(node.value) for node in app.markdown
                     if "거래량 (어제 대비)" in str(node.value))
        self.assertIn("이 종목 점수", cards)
        self.assertNotIn("눌림 점수", cards)

    def test_each_section_can_also_be_closed_from_its_bottom(self):
        """구역마다 맨 아래에도 닫기 단추를 둔다(2026-08-01, 한국테마와 같은 장치)."""
        source = (ROOT / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
        self.assertIn("def _section_close(", source)
        for key in ("j3_detail_open_", "j3_bundle_open_"):
            self.assertIn(f'_section_close(f"{key}', source,
                          f"{key} 구역에 아래 닫기 단추가 없다")
        self.assertIn('_section_close("j3_intraday_open_pullback"', source)
        self.assertIn('_section_close("j3_detail_open_pullback"', source)
        self.assertIn('div[class*="st-key-close_"] button', source)

    def test_clicking_a_stock_opens_the_detail_and_the_charts(self):
        """2026-08-01 사용자 지시 — 누르면 세부사항과 차트가 같이 열려야 한다.

        한국테마와 같은 동작이다. 이 세 값이 빠지면 누른 뒤 단추를 또 눌러야 한다.
        """
        source = (ROOT / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
        block = source.split("def _render_rulebook_finder(")[1].split("\ndef ")[0]
        for opened in ("j3_detail_open_pullback", "j3_intraday_open_pullback",
                       "j3_bundle_open_pullback"):
            self.assertIn(opened, block, f"{opened}를 열지 않는다")

    def test_the_mustard_box_bolds_only_what_matters(self):
        """전체를 진하게 하지 말고 중요한 것만(2026-08-07 상하님 지시).

        + 는 스카이블루, − 는 붉은색으로 진하게. 다 굵으면 아무것도 강조되지 않는다.
        """
        source = (ROOT / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
        block = source.split("def _mustard_html(")[1].split("\ndef ")[0]
        # 평문을 먼저 escape하고 그 위에 우리 태그만 얹는다 — 순서가 바뀌면
        # 우리가 얹은 태그까지 글자로 보인다.
        self.assertLess(block.index("html.escape"), block.index("_MUSTARD_NUMBER.sub"))
        self.assertIn("j3-mn-", block)
        # 바탕글은 보통 굵기(500)여야 한다. 700이면 전체가 굵어 예전으로 돌아간다.
        mustard_css = source.split(".j3-reason-mustard {")[1].split("}")[0]
        self.assertIn("font-weight: 500", mustard_css)
        # 오른 값 스카이블루 · 빠진 값 붉은색, 둘 다 진하게.
        self.assertIn(".j3-reason-mustard .j3-mn-up { color: #4fb8ff; font-weight: 900; }",
                      source)
        self.assertIn(".j3-reason-mustard .j3-mn-down { color: #ff4d4f; font-weight: 900; }",
                      source)
        # 상자를 그리는 두 자리 모두 이 손질을 거쳐야 한다.
        self.assertEqual(2, source.count("j3-reason-mustard'>{_mustard_html("))

    def test_one_of_the_three_charts_is_drawn_big_on_top(self):
        """2026-08-07 상하님 지시 — 일봉을 누르면 화면 위에 크게, 주봉을 누르면 주봉이.

        고르는 단추는 on_click으로 값을 바꿔야 한다. 큰 차트를 단추보다 **먼저**
        그리므로, 눌린 값을 그 자리에서 읽으면 한 박자 늦게 바뀐다.
        """
        source = (ROOT / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
        block = source.split("def _render_price_chart_bundle(")[1].split("\ndef ")[0]
        self.assertIn("BIG_CHART_HEIGHT", block)
        self.assertIn("on_click=_pick_bundle_chart", block)
        self.assertIn("j3_bundle_pick_", block)
        # 큰 차트가 세 개짜리 줄보다 먼저 그려져야 '화면 위에' 온다.
        self.assertLess(block.index("j3-chart-big-title"),
                        block.index("st.columns([1, 1, 1, 4.5])"))
        # 아래 셋은 손톱그림이다(2026-08-07 "캡쳐처럼 적게") — 눈금·범례를 빼고
        # 높이를 108px로 줄인다. 마지막 빈 칸이 셋을 왼쪽으로 몰아 폭도 좁힌다.
        self.assertIn("height=THUMB_CHART_HEIGHT, compact=True", block)
        self.assertIn("THUMB_CHART_HEIGHT = 108", source)
        # 단추 키는 영문이어야 지금 고른 단추만 CSS로 밝힐 수 있다.
        self.assertIn('_CHART_KEY = {"일봉": "daily", "주봉": "weekly", "월봉": "monthly"}',
                      source)

    def test_rulebook_table_slides_sideways_like_the_pullback_table(self):
        """폰에서 순위·종목이 따로 쌓이던 것을 눌림목 표와 같은 규칙으로 맞췄다.

        표 상자 이름을 옆으로 밀기 규칙 목록에 넣지 않으면 다시 쌓인다
        (2026-08-01 캡처로 확인).
        """
        source = (ROOT / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
        self.assertIn(".st-key-j3_rulebook_table,", source)
        # 2026-08-06 — '점수' 칸이 늘어 이 표만 min-width를 1000px로 따로 뒀다.
        # 그래서 이 줄만 다른 표와 묶이지 않고 홀로 선다.
        self.assertIn('.st-key-j3_rulebook_table [data-testid="stHorizontalBlock"] {', source)
        self.assertIn("min-width: 1000px", source)
        self.assertIn('.st-key-j3_rulebook_table [data-testid="stColumn"],', source)

    def test_main_login_includes_jarvis3_destination(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("미국테마 (자비스3)", source)
        # 2026-08-01부터 목적지는 _DEST_PAGES 한 곳에 모아 두고 _go_to가 옮긴다.
        # 로그인 화면과 '어디로 갈까요' 화면이 같은 표를 쓴다.
        self.assertIn('"미국테마": "pages/2_자비스3.py"', source)
        self.assertIn("st.switch_page(page)", source)

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
            next(node for node in app.button if node.key == "login_submit").click().run(timeout=60)

        self.assertEqual(len(app.exception), 0)
        self.assertTrue(app.session_state.filtered_state.get("authenticated"))
        self.assertIn("미국 전체시장 판단", [str(node.value) for node in app.subheader])

    def test_guest_button_switches_without_password_and_keeps_restrictions(self):
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
            next(node for node in app.button if node.key == "login_guest").click().run(timeout=60)

        self.assertEqual(len(app.exception), 0)
        state = app.session_state.filtered_state
        self.assertTrue(state.get("authenticated"))
        self.assertEqual(state.get("jarvis_access_role"), "guest")
        button_keys = {str(node.key or "") for node in app.button}
        self.assertIn("j3_pullback_breakout", button_keys)
        self.assertIn("j3_pullback_crash", button_keys)
        self.assertNotIn("j3_pullback_find", button_keys)
        self.assertNotIn("j3_top7_find", button_keys)
        self.assertTrue([node for node in app.text_input if node.key == "j3_my_stock_query"])


if __name__ == "__main__":
    unittest.main()
