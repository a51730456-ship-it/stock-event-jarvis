import copy
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import gauge_ui
from streamlit.testing.v1 import AppTest

import us_swing_testdata


# 합성 일봉으로 한 번만 돌린 실제 payload를 시험끼리 나눠 쓴다(계산이 느리다).
_SWING_SCAN_CACHE = {}

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


def _breakout_result(count=1, *, market_on=True):
    """설명서 1번(상승장 신고가 눌림매수) 결과 모양.

    **2026-08-20부터 손으로 적은 가짜가 아니라 selector가 실제로 만든 payload다.**
    새 지시문이 화면이 읽는 칸을 크게 늘렸다(핵심점수·보조점수·상태·등급·
    항목별 설명). 손으로 적어 두면 화면 시험과 계산이 조용히 갈라져, 계산이
    바뀌어도 화면 시험은 옛 모양을 계속 통과시킨다. 합성 일봉은
    `us_swing_testdata`가 만들고 `find_breakout_pullback_stocks`가 그대로 돈다.

    `market_on=False`는 나스닥이 조정에서 못 벗어난 날이다 — 그날은 정식 후보가
    한 줄도 나오면 안 된다.
    """
    cached = _SWING_SCAN_CACHE.get(bool(market_on))
    if cached is None:
        cached = us_swing_testdata.scan(market_on=bool(market_on))
        _SWING_SCAN_CACHE[bool(market_on)] = cached
    result = copy.deepcopy(cached)
    result["primary_rows"] = result["primary_rows"][:count]
    result["rows"] = result["primary_rows"]
    result["watch_rows"] = result["watch_rows"][:count]
    return result


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
    # 자비스3의 새 첫 화면은 종목 브리핑이다. 기존 테마·상승장·
    # 급락반등 화면을 검증하는 시험은 하단 '시장분석'으로 들어간 상태로 그린다.
    app.session_state["j3_briefing_page"] = "market"
    for panel in ("theme", "pullback", "top7", "mystock"):
        app.session_state[f"j3_detail_open_{panel}"] = True
        app.session_state[f"j3_buyform_open_{panel}"] = True
    app.session_state["j3_theme_panel_open"] = True
    # 20개 테마 순위표는 2026-08-14부터 **기본이 닫힘**이다(상하님 지시). 표를 보는
    # 시험들은 열어 둔 상태로 그린다. 닫힌 상태는 test_theme_rank_starts_closed가 본다.
    app.session_state["j3_theme_rank_open"] = True
    # 저장해 둔 목록 구역도 펴 둔다 — 그 맨 위에 매수 기록이 나오는지 본다(2026-08-14).
    app.session_state["picklist_archive_open_US"] = True
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
            app.session_state["j3_briefing_page"] = "market"
            app.run(timeout=60)
            self.assertFalse(app.session_state.filtered_state.get("j3_theme_panel_open", False))
            self.assertFalse([
                node for node in app.button if str(node.key or "").startswith("j3lbtn_")
            ])
            # **순위표는 처음에 닫혀 있다**(2026-08-14 상하님 지시 — "화면 처음 열릴 때
            # 순위가 열려 있게 하지 말고 닫아라. 그거 클릭해야 열리지").
            # 표가 안 그려지므로 테마 단추도 아직 없다. 대신 오늘 1~5위 한 줄은 보인다.
            self.assertFalse([
                node for node in app.button if str(node.key or "").startswith("j3tbtn_")
            ], "순위표가 처음부터 열려 있다")
            rank_button = next(
                node for node in app.button
                if str(node.key or "") == "btn_j3_theme_rank_open"
            )
            self.assertIn("열기", str(rank_button.label))
            self.assertTrue(any("class='j3-theme-top5'" in str(node.value)
                                for node in app.markdown), "오늘 1~5위 한 줄이 없다")
            rank_button.click().run(timeout=60)

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
        markdowns = [str(node.value) for node in app.markdown]
        # 제목은 2026-08-21부터 st.subheader가 아니라 **절반 크기 글**이다
        # (상하님 지시 — 28px는 너무 컸다). 글이 화면에 있는지로 본다.
        self.assertTrue(any("미국 전체시장 판단" in value for value in markdowns),
                        "화면 맨 위 제목이 없다")
        # 종목명은 밝은 보라 커스텀 HTML(markdown)로 렌더링된다.
        self.assertTrue(any("NVDA" in value for value in markdowns))
        self.assertTrue(any("j3-stock-name" in value for value in markdowns))
        # 테마 순위표·대장주 1–6위표 모두 HTML(가운데 정렬), 선택은 pills·radio.
        self.assertTrue(any("j3-theme-table" in value for value in markdowns))
        # 순위표는 **맨 위 단추로 여닫는다**(2026-08-14 상하님 지시). 기본은 열림이라
        # 위에는 닫는 글이 뜨고, '종목 찾기' 위에도 닫는 단추가 하나 더 있다.
        rank_keys = {str(node.key or "") for node in app.button}
        self.assertIn("btn_j3_theme_rank_open", rank_keys, "맨 위 순위표 단추가 없다")
        self.assertIn("close_j3_theme_rank_open", rank_keys, "순위표 닫기 단추가 없다")
        # **한 번 눌러 저장**하는 단추가 있어야 한다(2026-08-14 상하님 지시 —
        # "클릭하면 그 시점에 자동매수 한 걸로 저장되게"). 주문은 안 낸다.
        self.assertTrue(
            [node for node in app.button if str(node.key or "").startswith("j3_quick_buy_")],
            "지금 값으로 바로 저장 단추가 없다")
        # 저장해 둔 목록 **맨 위**에 매수 기록 자리가 있어야 한다(같은 지시).
        self.assertTrue(any("내가 저장한 매수 기록" in value for value in markdowns),
                        "저장해 둔 목록 맨 위에 매수 기록이 없다")
        # 단추 밑에 **오늘 1~5위 한 줄**이 있어야 한다(2026-08-14 상하님 지시).
        # (CSS 묶음에도 이름이 나오므로 **실제로 그린 줄**만 고른다.)
        top5 = next((value for value in markdowns
                     if "class='j3-theme-top5'" in value), "")
        self.assertIn("오늘 테마 종목 순위는", top5)
        self.assertIn("순입니다", top5)
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
        # 2026-08-14 — 괄호 안 갈래 이름만 갈래 색으로 칠하느라 그 사이에 <span>이
        # 들어갔다(상하님 지시). 앞말과 갈래 이름이 **한 markdown 안에** 있는지 본다.
        title = next((value for value in markdowns
                      if "종목 선정 근거" in value and "j3-section-title" in value), "")
        self.assertIn("종목 선정 근거", title)
        self.assertIn("(신고가 눌림 전용 배점)", title)
        self.assertIn("j3-title-breakout", title, "갈래 색이 빠졌다")
        self.assertTrue(any("j3-factor-table" in value for value in markdowns))
        self.assertTrue(any("j3-holo-card" in value for value in markdowns))
        # 단타 참고 신호는 접어 뒀다(2026-08-06) — 여는 단추가 있어야 한다.
        self.assertTrue(any("단타 참고 신호 보기" in str(node.label) for node in app.button))
        # 당일 가격 칸(자비스4와 같은 구성) — 시가·고가·저가·전일 종가
        self.assertTrue(any("당일 가격 · 시가/고가/저가 한눈에 보기" in value for value in markdowns))
        self.assertTrue(any("전일 종가" in value for value in markdowns))
        self.assertTrue(any("당일 고가" in value for value in markdowns))
        # 값은 결과 payload에서 그대로 와야 한다 — 시험이 숫자를 손으로 박아 두면
        # 계산이 바뀌어도 화면 시험이 옛 숫자를 계속 통과시킨다.
        top = _breakout_result()["rows"][0]["metrics"]
        for key in ("day_high", "current"):
            self.assertTrue(any(f"${float(top[key]):,.2f}" in value for value in markdowns),
                            f"{key} 값이 화면에 없다")
        self.assertTrue(any("14일 변동성(ATR)" in value for value in markdowns))
        # 상승장 표는 당일주가 칸 대신 **고를 때 필요한 것만** 쓴다
        # (2026-08-21 상하님 지시 — 등수·점수 칸은 선택종목 세부사항에서 본다).
        self.assertTrue(any("등급 / 상태" in value and "눌림 / 며칠째" in value
                            for value in markdowns))
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
            self.assertFalse(any("AVGO" in value for value in names), names)

            # 2순위를 누르면 그 종목으로 바뀐다
            next(
                node for node in app.button if str(node.key or "") == "j3rbf_01"
            ).click().run(timeout=60)

        self.assertEqual(len(app.exception), 0)
        names_after = [
            str(node.value) for node in app.markdown
            if "<div class='j3-stock-name'>" in str(node.value)
        ]
        self.assertTrue(any("AVGO" in value for value in names_after), names_after)
        self.assertEqual(
            app.session_state.filtered_state.get("j3_pullback_selected_ticker"), "AVGO"
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

    def test_clicking_another_leader_switches_detail_in_the_same_run(self):
        """다른 종목을 눌러도 **한 판 안에서** 상세가 그 종목으로 바뀐다.

        2026-08-21에 st.rerun()을 뺐다(상하님 지적 — "종목 클릭 후 5초 걸린다").
        빼도 되는 까닭은 '상세 종목 선택' 라디오가 이 줄보다 뒤에 만들어져서
        방금 넣은 값을 그대로 집어 들기 때문이다. 그 전제가 깨지면 여기가 먼저
        깨진다. 표의 주황 표시도 같은 판에서 옮겨져 있어야 한다.
        """
        with patch("jarvis3_data.get_market_overview", return_value=_market()),              patch("jarvis3_data.get_fear_greed", return_value=_fear_greed()),              patch("market_signal_ui._fetch_quotes", return_value={}),              patch("jarvis3_data.get_theme_rankings", return_value=_ranking()),              patch("jarvis3_data.get_theme_leaders", return_value=_leaders()),              patch("jarvis3_data.prefetch_charts"),              patch("jarvis3_data.get_live_quote", return_value={
                 "ok": True, "current": 179.0, "change_pct": 1.0, "from_high_pct": -1.0,
                 "ret20": 7.0, "atr_pct": 3.0, "source_time": "x", "stale": False,
             }),              patch("jarvis3_data.get_chart_bundle", return_value=_chart_bundle()),              patch("jarvis3_store.ensure_tables"),              patch("jarvis3_store.trade_progress", return_value={
                 "total_count": 0, "open_count": 0, "closed_count": 0, "minimum_sample": 30,
             }),              patch("jarvis3_store.list_trades", return_value=_sample_trades()):
            app = AppTest.from_file(str(PAGE), default_timeout=60)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
            _open_all_details(app)
            app.run(timeout=60)
            buttons = [node for node in app.button if str(node.key or "").startswith("j3lbtn_")]
            self.assertGreaterEqual(len(buttons), 2, "종목 줄이 두 개도 안 그려졌다")
            buttons[1].click().run(timeout=60)

        self.assertEqual(len(app.exception), 0)
        state = app.session_state.filtered_state
        chosen = next(
            (value for key, value in state.items() if str(key).startswith("j3_stock_choice_")),
            None,
        )
        self.assertEqual("AVGO", chosen, state)
        radio = [node for node in app.radio if str(node.label) == "상세 종목 선택"]
        self.assertTrue(radio, "상세 종목 선택 라디오가 사라졌다")
        self.assertEqual("AVGO", radio[0].value, "라디오가 옛 종목에 머물러 있다")
        markdowns = " ".join(str(node.value) for node in app.markdown)
        self.assertIn("st-key-j3lbtn_01", markdowns,
                      "누른 줄에 주황 표시가 안 옮겨졌다")
        self.assertNotIn("st-key-j3lbtn_00", markdowns,
                         "옛 줄에 주황 표시가 남았다")

    def test_crash_factor_table_keeps_only_the_green_name(self):
        """배점표 「심사 항목」 칸에는 **초록 이름만** 둔다 (2026-08-21 상하님 지시).

        상하님 — "급락 후 반등장 심사항목에 밑에 초록색 제목만 두고 나머지 흰색
        내용 다 빼라." 값 줄은 버리지 않고 제목 옆 「설명」 창으로 내린다
        (CLAUDE.md 0-1 마 — 버린 것은 「설명」에 남긴다).
        """
        app = self._run_with_mode("crash", "find_crash_rebound_stocks", _crash_result())
        tables = [str(node.value) for node in app.markdown
                  if "j3_factor_help_pullback_crash" in str(node.value)]
        self.assertTrue(tables, "급락 배점표가 안 그려졌다")
        for table in tables:
            head, _, panel = table.partition("<div class='j3fh-p'>")
            rows = head[head.find("<tbody>"):]
            self.assertNotIn("j3-muted", rows, "배점표 줄에 회색 값 글이 남았다")
            self.assertIn("j3fh-now", panel, "값 줄이 「설명」 창에서도 사라졌다")

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

    def _run_with_mode(self, mode, finder_name, finder_result, *, help_open=True,
                       pick=None):
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
            # 2026-08-22부터 목록은 목록만 그린다 — 상세는 종목을 눌러야
            # 열린다(상하님 지적 "그건 내가 한 적 없다"). 상세를 보는
            # 시험은 여기서 누른 것으로 친다.
            if pick:
                app.session_state["j3_pullback_selected_ticker"] = pick
            app.run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        return app

    def test_no_earned_score_ever_exceeds_its_maximum(self):
        """**획득이 최대보다 크면 안 된다** (2026-08-12 상하님 지적).

        상하님 캡처 — 1등 종목의 '52주 신고가 위치'가 31.1 (25), '유동성'이
        16.2 (15)였다. 뺀 20점을 나머지에 1.25배로 나눠 놓고 최대값 칸을 안
        고쳐서 생긴 일이다. 화면에 그려진 모든 '획득(최대)' 표를 훑어 본다.
        """
        import re

        for mode, finder, result in (
            ("breakout", "find_breakout_pullback_stocks", _breakout_result()),
            ("crash", "find_crash_rebound_stocks", _crash_result()),
        ):
            app = self._run_with_mode(mode, finder, result)
            blob = "".join(str(node.value) for node in app.markdown)
            # <span ...>23.5</span> <span ...>(25)</span> 꼴을 다 뽑는다.
            # **총점 줄은 건너뛴다.** 여기 시험용 가짜 종목은 score를 손으로 박아
            # 둔 값이라 항목 합과 다르다. 진짜 계산에서 총점이 만점을 안 넘는지는
            # test_jarvis3_data.LeaderScoreMaxTests가 실제 종목으로 확인한다.
            found = [
                m for m in re.finditer(
                    r">([-\d.]+)</span>\s*<span[^>]*>\(([-\d.]+)\)</span>", blob)
                if "총점" not in blob[max(0, m.start() - 360):m.start()]
                or "j3-fac-name" not in blob[max(0, m.start() - 360):m.start()]
            ]
            pairs = [(m.group(1), m.group(2)) for m in found
                     if "총점</td>" not in blob[max(0, m.start() - 360):m.start()]]
            self.assertTrue(pairs, f"{mode}: 획득(최대) 짝을 하나도 못 찾았다")
            for got, top in pairs:
                self.assertLessEqual(
                    float(got), float(top) + 0.05,
                    f"{mode}: 획득 {got}이 최대 {top}보다 크다")
                self.assertGreater(
                    float(top), 0.0,
                    f"{mode}: 최대가 0인 줄이 표에 남아 있다 (0점은 빼야 한다)")

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

    def test_breakout_mode_shows_the_gate_first_and_its_own_columns(self):
        """상승장 표는 **자격을 먼저 말하고** 제 칸을 쓴다 (2026-08-20 새 지시문).

        옛 표는 고점 대비·고점 후 며칠·1년 성적 칸이었다. 새 표는 자격을 판단한
        값(RS60 · RS120 · 눌림/day)과 핵심·보조 점수를 나란히 보여준다.
        """
        app = self._run_with_mode("breakout", "find_breakout_pullback_stocks",
                                  _breakout_result())
        markdowns = [str(node.value) for node in app.markdown]
        joined = " ".join(markdowns)
        # 화면이 실제로 찾는 숫자가 그대로 나와야 한다.
        self.assertIn("3~10%", joined)
        self.assertIn("1~3거래일", joined)
        self.assertIn("최근 3개월 상위 20%", joined)
        self.assertIn("최근 6개월 상위 20%", joined)
        # **화면에 개발자 말이 남아 있으면 안 된다**(2026-08-20 상하님 지시).
        for jargon in ("RS60", "RS120", "HARD GATE", "PRIMARY", "WATCH", "percentile"):
            self.assertNotIn(jargon, joined, f"화면에 '{jargon}'이 남아 있다")
        # **총점을 승률처럼 말하지 않는다**(지시문 6·9·10번).
        self.assertIn("총점은 승률이나 보장수익이 아닙니다", joined)
        # 배점 구성이 화면에 그대로 적혀야 한다.
        self.assertIn("최근 3개월 25 + 최근 6개월 25 + 눌림 20", joined)
        self.assertIn("테마 10 + 돌파 거래량 8 + 테마 확산도 5 + 반등 7", joined)
        # 표 머리글은 갈래 전용이다 — 옛 칸 이름이 남아 있으면 안 된다.
        header = next(value for value in markdowns
                      if "티커" in value and "등급 / 상태" in value and "테마" in value)
        for gone in ("고점 후 며칠", "보유일수", "1년 성적", "눌림 점수",
                     "3개월 등수", "6개월 등수", "중요 점수", "보조 점수"):
            self.assertNotIn(gone, header, f"표에서 뺀 칸 {gone}이 남아 있다")
        self.assertLess(header.index("티커"), header.index("등급 / 상태"))
        self.assertLess(header.index("등급 / 상태"), header.index("눌림 / 며칠째"))
        self.assertLess(header.index("눌림 / 며칠째"), header.index("테마"))
        self.assertIn("j3rbf_00", [str(node.key or "") for node in app.button])
        self.assertTrue(any(
            "상승장 (신고가 눌림매수) 닫기" in str(node.label)
            for node in app.button
        ))
        # 시장이 켜진 날은 초록 줄로 알린다.
        self.assertTrue(any("새로 살 후보를 낼 수 있는 장입니다" in str(node.value)
                            for node in app.success), "장이 켜졌다는 알림이 없다")

    def test_breakout_market_off_shows_no_primary_row_at_all(self):
        """**시장이 막힌 날은 정식 후보를 한 줄도 안 만든다** (지시문 6·36번).

        옛 화면은 "표를 잰 자리가 아닙니다"라고 알려만 주고 종목은 그대로
        보여줬다. 새 규칙에서는 그 줄이 자격 자체를 막는다.
        **자리를 채우려고 기준을 낮추지 않는다**(CLAUDE.md 0-1 바).
        """
        app = self._run_with_mode("breakout", "find_breakout_pullback_stocks",
                                  _breakout_result(market_on=False))
        self.assertTrue(any("새로 살 후보를 내지 않습니다" in str(node.value)
                            for node in app.error), "막혔다는 빨간 줄이 없다")
        self.assertEqual(0, len([
            node for node in app.button if str(node.key or "").startswith("j3rbf_")
        ]), "시장이 막혔는데 정식 후보 줄이 나왔다")
        joined = " ".join(str(node.value) for node in app.info)
        self.assertIn("기준을 느슨하게 바꾸지 않습니다", joined)

    def test_crash_mode_shows_both_depth_buckets_and_holding_periods(self):
        app = self._run_with_mode("crash", "find_crash_rebound_stocks", _crash_result())
        joined = " ".join(str(node.value) for node in app.markdown)
        self.assertIn("고점 대비 -20~-30%", joined)
        self.assertIn("고점 대비 -30~-50%", joined)
        # 파는 날 대신 세 기간 성적이 나란히 뜬다.
        self.assertIn("파는 시점은 규칙에 없습니다", joined)
        # 2026-08-06 — 점수가 순위다(별점은 뺐다). 배점표를 화면에 그대로 뿌린다.
        self.assertIn("점수가 곧 순위입니다", joined)
        crash_body = " ".join(
            str(node.value) for node in app.markdown
            if "j3b-bottom-nav" not in str(node.value)
        )
        self.assertNotIn("★", crash_body, "급락 점수에 별점이 되살아났다")
        # 2026-08-19 새판 — 점수를 주는 넷이 설명 표에 다 보여야 한다.
        # **이름은 그 항목이 던지는 질문 꼴이다**(상하님 지적 — "무슨 말인지
        # 못 알아먹겠다"). 옛 이름('테마 6개월 수익률' 같은 것)으로 돌아가면 깨진다.
        for item in ("이 종목이 평소 크게 움직이나", "이 테마가 이미 오름세로 돌아섰나",
                     "이 테마가 통째로 떨어졌나", "이 테마가 지난 반년에 많이 올랐나",
                     "40점"):
            self.assertIn(item, joined, f"배점표에 {item}이 없다")
        # **0점 항목은 뺐다**(2026-08-21 상하님 지시 "빼라"). 열한 줄 중 일곱이
        # 0점이라 표가 그 일곱에 묻혔다. 무엇을 재 보고 버렸는지는
        # docs/US_THEME_SPEC.md 3-3에 남아 있다.
        for gone in ("테마가 덜 빠졌나", "테마 주봉이 오름세인가", "테마가 같이 오르는가"):
            self.assertNotIn(gone, joined, f"0점 항목 {gone}이 배점표에 남았다")
        # 급락 화면은 **위 순위표가 상승장 기준**이라고 밝혀야 한다(2026-08-14).
        self.assertIn("위 테마 순위표 점수는 상승장 기준입니다", joined)
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
        # 파는 날 칸이 '1년 성적'으로 바뀌었다 — 며칠이라고 적지 않는다.
        self.assertNotIn("거래일</span>", block, "파는 날이 표에 되살아났다")

    def test_crash_table_shows_the_theme_rebound_spread_without_scoring_it(self):
        """기준일이 있으면 '테마 반등' 칸이 뜬다 (2026-08-16 상하님 지시).

        첨부 엑셀(나스닥 저점 16회)을 이 집 합격선으로 재니 '저점 뒤 테마 5종목 중
        4개 넘게 올랐나'가 6·9·12개월 모두 합격했다. 다만 그 값은 저점에서 3개월
        지난 뒤에 잰 것이라 **점수로는 못 쓴다** — 보여주기만 한다.
        """
        result = _crash_result()
        result["reference"] = {"ok": True, "armed": True,
                               "reference_date": "2026-07-29",
                               "reference_drop": -11.5, "today_drop": -4.1}
        result["days_since_reference"] = 12
        result["rows"][0].update({"judged_from_high_pct": -34.0,
                                  "now_from_high_pct": -21.0,
                                  "since_reference_pct": 19.7,
                                  "theme_up_total": 5, "theme_up_count": 3,
                                  "theme_up_name": "반도체"})
        app = self._run_with_mode("crash", "find_crash_rebound_stocks", result)
        joined = " ".join(str(node.value) for node in app.markdown)
        header = next(
            str(node.value) for node in app.markdown
            if "갈래" in str(node.value) and "티커" in str(node.value)
        )
        # 칸 차례 — 기준일에서 잰 값 둘이 나란히 있어야 읽힌다.
        self.assertIn("테마 반등", header)
        self.assertLess(header.index("종목저점후"), header.index("테마 반등"))
        self.assertLess(header.index("테마 반등"), header.index("소속 테마"))
        self.assertIn("5개 중 3개", joined, "테마 반등 숫자가 표에 안 실렸다")
        # 며칠 지났는지 없으면 이 숫자를 언제부터 믿을지 알 수 없다.
        self.assertTrue(any("12거래일" in str(node.value) for node in app.info),
                        "기준일에서 며칠 지났는지가 화면에 없다")
        # **점수가 아니라는 것**이 화면에 적혀 있어야 한다(표 아래 작은 글씨).
        captions = " ".join(str(node.value) for node in app.caption)
        self.assertIn("「테마 반등」 칸은 점수에 안 들어갑니다", captions)
        # 이 칸 때문에 점수가 늘면 안 된다 — 만점은 배점 항목만으로 정해진다
        # (2026-08-19에 변동성 40 + 30주선 30 + 동시 하락 20 + 6개월 10 = 100점).
        import jarvis3_data
        self.assertEqual(100.0, jarvis3_data.CRASH_SCORE_MAX)

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
        # 2026-08-19에 항목 이름을 「낙폭 갈래」에서 「고점 대비 낙폭」으로 바꿨다 —
        # '갈래'는 상하님이 화면에서 알아보기 어렵다고 하신 말이다.
        self.assertIn("고점 대비 낙폭", joined)
        # 새 1등 항목(주가 변동성 40점)이 설명 표에 있어야 한다(2026-08-19).
        self.assertIn("이 종목이 평소 크게 움직이나", joined)
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

    def test_limits_are_measured_not_just_stated(self):
        """한계를 적어만 두지 않고 **얼마나 위험한지 잰 결과**를 적는다.

        2026-08-19 상하님 지시로 두 한계를 쟀다
        (research/us_crash_leaveout.py) —
          · 바닥 아홉 번을 하나씩 빼도 네 항목이 다 절반을 넘겼다
          · 10년 내내 있던 종목 +51.6% vs 새로 들어온 종목 +74.6% (새 쪽 12%)
        """
        source = (ROOT / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
        head = source.split('("_crash",')[1].split('("_theme",')[0]
        self.assertIn("한 번씩 빼고", head, "바닥을 빼고 다시 잰 결과가 없다")
        # 글이 줄바꿈으로 토막 나 있어 한 낱말씩 본다.
        self.assertIn("넘겼습니다", head)
        self.assertIn("+51.6%", head, "생존편향 크기가 없다")
        self.assertIn("+74.6%", head)

    def test_moved_high_is_marked_and_explained(self):
        """1년 최고가가 바뀐 종목에 표시가 붙고, 표 밑에 무슨 뜻인지 적힌다."""
        source = (ROOT / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
        self.assertIn("high52_moved", source, "최고가가 바뀐 종목을 안 가린다")
        self.assertIn("1년 최고가가 바뀌었습니다", source, "손 올렸을 때 설명이 없다")
        # 표 밑 설명 — 왜 세 숫자가 빼기로 안 맞는지 한 번 적어 둔다.
        self.assertIn("두 낙폭을 빼도", source)
        self.assertIn("기준일 종가에서 잰 값", source)

    def test_expander_tables_can_be_scrolled_sideways(self):
        """접은 자리(11위~20위)도 옆으로 밀려야 한다 (2026-08-19 상하님 지적).

        스트림릿이 접이 안쪽 <details>에 overflow:hidden을 걸어 둬서, 표는
        1180px인데 상자가 968px에서 잘라 버렸다. 그래서 밀리지도 않고 표만
        삐져나왔다. 1~10위 표는 접이가 아니라 멀쩡했다.

        자르던 그 상자를 미는 상자로 바꿨다. 클래스 이름(st-emotion-cache-…)은
        스트림릿 판이 바뀌면 달라지므로 쓰지 않는다 — 지금 판은 <details>이고
        판이 바뀌면 <div>일 수 있어 둘 다 짚어 둔다.
        """
        source = (ROOT / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
        for key in ("j3_rulebook_rest", "j3_theme_rest"):
            self.assertIn(
                f'.st-key-{key} [data-testid="stExpander"] > details',
                source, f"{key} 접이가 옆으로 안 밀린다")
            self.assertIn(
                f'.st-key-{key} [data-testid="stExpander"] > div',
                source, f"{key} — 스트림릿 판이 바뀔 때 쓸 자리가 없다")
        # 판마다 달라지는 클래스 이름을 **선택자로** 쓰면 안 된다.
        # 주석에 그 이름이 나오는 것은 괜찮다 — 왜 안 쓰는지 적어 둔 것이다.
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith(("#", "*", "//")) or "쓰지 않는다" in stripped:
                continue
            self.assertNotIn(".st-emotion-cache", stripped,
                             "판마다 달라지는 클래스 이름에 기대면 안 된다")

    def test_table_scrollbar_is_thick_enough_to_grab(self):
        """표 밑 미는 막대가 마우스로 집을 만큼 두꺼워야 한다 (2026-08-19 지시).

        **웹킷 쪽만 쓰면 안 된다** — 요즘 크롬은 표준 속성(scrollbar-width·
        scrollbar-color)이 있으면 ::-webkit-scrollbar를 무시한다. 실측으로
        확인했다(웹킷만 넣었을 때 10px 그대로, 표준으로 바꾸니 15px).
        """
        source = (ROOT / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
        block = source.split("표 밑 미는 막대를")[1].split("@media")[0]
        self.assertIn("scrollbar-color", block, "표준 속성이 없다")
        self.assertIn("scrollbar-width: auto", block)
        # 옛 브라우저용 웹킷 쪽도 남아 있어야 한다.
        self.assertIn("::-webkit-scrollbar", block)
        for key in ("j3_rulebook_table", "j3_rulebook_rest", "j3_pullback_table"):
            self.assertIn(f".st-key-{key},", block, f"{key} 막대가 얇은 채로 남았다")

    def test_us_futures_card_is_first_on_the_top_row(self):
        """나스닥100 선물 칸이 **맨 앞**에 있어야 한다 (2026-08-19 상하님 지시).

        상하님 — "한국테마에 있는 미국 나스닥100 선물 미국테마에도 넣어라 가장 위에."

        4대 지수는 정규장이 끝나면 멈추는데 선물은 밤새 움직인다. 장 열리기 전에
        미국이 어느 쪽으로 갈지 먼저 알려 주는 칸이라 맨 앞이다.
        """
        source = (ROOT / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
        block = source.split("top_cells = [")[1].split("]", 1)[0]
        self.assertIn("_us_futures_cell()", block, "선물 칸이 윗줄에 없다")
        self.assertLess(block.index("_us_futures_cell()"),
                        block.index("_us_index_cells"),
                        "선물 칸이 4대 지수보다 뒤에 있다")
        # **한국 파일을 고치지 않고 읽기만 한다** — 같은 것을 여기 새로 쓰면
        # 야후에 같은 요청을 두 번 보내고 두 화면 숫자가 갈라진다.
        fn = source.split("def _us_futures_cell(")[1].split(chr(10) + "def ")[0]
        self.assertIn("jarvis4_data", fn)
        self.assertIn("get_us_futures_live", fn)
        # 모듈이 없거나 조회가 실패해도 화면을 죽이지 않는다.
        self.assertIn("except Exception", fn)

    def test_crash_help_carries_the_holding_period_reference_table(self):
        """설명 창 안에 '얼마나 들고 있었을 때 어땠나' 참고표가 있어야 한다.

        2026-08-19 상하님 지시 — "설명 창에 참고표로 넣어라."
        **배점표가 아니라 설명 창이다.** 앱은 파는 시점을 정하지 않으므로
        (CLAUDE.md 0-1 바) 점수 자리에 두면 앱이 정하는 것처럼 보인다.
        """
        source = (ROOT / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
        head = source.split('("_crash",')[1].split('("_theme",')[0]
        self.assertIn("참고 — 얼마나 들고 있었을 때 어땠나", head)
        self.assertIn("앱은 파는 시점을 정하지 않습니다", head)
        self.assertIn("j3fh-ref", head, "참고표가 배점표 모양을 쓰고 있다")
        for span in ("3개월", "6개월", "1년", "1년 반"):
            self.assertIn(f">{span}</td>", head, f"참고표에 {span}이 없다")
        # 참고표 모양은 **배점표와 달라야** 한다 — 점수 표로 오해하면 안 된다.
        self.assertIn(".j3fh-ref {", source)
        self.assertNotIn("j3fh-ref", source.split("_SCORE_TABLE =")[-1].split("}")[0])

    def test_breakout_detail_uses_the_breakout_ruler(self):
        result = _breakout_result()
        app = self._run_with_mode("breakout", "find_breakout_pullback_stocks", result,
                                  pick=result["rows"][0]["ticker"])
        joined = " ".join(str(node.value) for node in app.markdown)
        self.assertIn("신고가 눌림 전용 배점", joined)
        # 새 배점 일곱 줄이 이름 그대로 표에 있어야 한다.
        for item in ("최근 3개월, 시장보다 강했나", "최근 6개월, 꾸준히 강했나",
                     "최고가에서 알맞게 내려왔나", "같은 테마 다른 종목도 강한가",
                     "신고가 뚫던 날 거래가 늘었나", "같은 테마에서 여럿이 함께 오르나",
                     "다시 위로 움직이기 시작했나"):
            self.assertIn(item, joined, f"배점표에 {item}이 없다")
        # **심사 항목 칸에는 초록 이름만 둔다**(2026-08-21 상하님 지시 —
        # "심사항목 밑에 하얀색 설명 빼라, 초록색 글자만 둬라는 말이다").
        # 한 줄 설명은 「자세히」 창에 그대로 있다.
        for one_line in ("최근 3개월 동안 나스닥보다 얼마나 강하게 오른 종목인지",
                         "52주 신고가 후 너무 무너지지 않고",
                         "이 종목 혼자만 오르는 것이 아니라",
                         "눌림이 끝나고 주가가 다시 위로 움직이기 시작했는지"):
            self.assertIn(one_line, joined, f"한 줄 설명이 없다: {one_line}")
        self.assertFalse(any("j3-fac-note" in str(node.value) for node in app.markdown),
                         "항목 이름 밑에 붙던 글이 되살아났다")
        # 이름 옆의 **실제 값**은 남는다 — 설명이 아니라 왜 이 점수인지 보여 주는
        # 숫자다(지시문 57번).
        self.assertTrue(any("평균의" in value and "j3-fac-name" in value
                            for value in [str(n.value) for n in app.markdown]),
                        "항목 옆 실제 값이 사라졌다")
        # 급락 갈래의 항목 이름이 상승장 표에 섞이면 안 된다.
        for gone in ("최근 11일에 빠졌나", "뚫기 전 60일", "테마가 1년 최고에 붙어 있나"):
            self.assertNotIn(gone, joined, f"옛 상승장/급락 항목 {gone}이 섞였다")
        # **두 점수를 따로 보여준다**(지시문 33번).
        self.assertIn("중요 점수", joined)
        self.assertIn("보조 점수", joined)
        # **손절과 파는 시점은 앱이 안 정한다고 적는다**(지시문 59번).
        # "연구 중"이라고는 안 적는다 — 제가 지금 돌리고 있다는 말로 읽힌다
        # (2026-08-21 상하님 물음 "너가 연구중인가?").
        self.assertIn("앱이 안 정함", joined)
        self.assertNotIn("연구 중", joined, "'연구 중'이 되살아났다")

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
        """설명은 접혀 있다(2026-08-06 사용자 지시 — 설명이 첫 화면을 다 먹었다).

        **2026-08-22에 단추에서 접이칸으로 바꿨다**(상하님 지적 — "이 화면 설명
        보기를 클릭하는데도 25초 걸린다"). 단추는 누를 때마다 서버가 화면을 다시
        그린다. 이 칸은 글자뿐이라 미리 만들어 두고 접어 두면 여닫는 데 서버를
        안 거친다. 화면에서 접혀 보이는 것은 그대로다.

        접혀 있어도 **종목 표와 오늘 이야기 한 줄은 그대로 보여야** 한다.
        """
        app = self._run_with_mode("breakout", "find_breakout_pullback_stocks",
                                  _breakout_result(), help_open=False)
        joined = " ".join(str(node.value) for node in app.markdown)
        labels = [str(node.label) for node in app.expander]
        self.assertTrue(any("이 화면 설명 보기" in label for label in labels),
                        f"설명 접이칸이 없다: {labels}")
        # 접이칸은 **접혀 있어야** 한다 — 펴진 채로 나오면 첫 화면을 다 먹는다.
        for node in app.expander:
            if "이 화면 설명 보기" in str(node.label):
                self.assertFalse(bool(node.proto.expanded), "설명이 펴진 채로 나온다")
        # 접혀 있어도 표와 기준일 한 줄은 남는다.
        self.assertIn("j3rbf_00", [str(node.key or "") for node in app.button])
        self.assertIn("정식 후보", joined)
        # 설명 글은 접이칸 안에 들어 있다(브라우저가 접어서 보여준다).
        self.assertIn("먼저 자격, 그다음 순위", joined)
        # 접이칸 머리글이 곧 닫기라 안쪽 '설명 닫기' 단추는 뺐다.
        self.assertFalse(any("설명 닫기" in str(node.label) for node in app.button),
                         "안 쓰는 닫기 단추가 남았다")

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

    def test_the_drawdown_is_split_into_three_columns(self):
        """낙폭 숫자 셋을 **칸 셋**으로 나눈다(2026-08-07 상하님 지시).

        처음에는 한 칸에 '-21.78% / 지금 -12.69% · +11.0%'로 붙여 뒀는데 칸보다
        길어 잘렸고(캡처에 '금 -12.69% · +11.'로 찍혔다), 세 줄로 겹쳐 놓으니
        이번에는 빽빽했다. 칸을 나누면 칸 이름이 곧 그 숫자의 뜻이 된다.
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
        # 칸 이름 셋이 다 있어야 한다(상하님이 정한 그대로).
        for title in ("고점 대비", "고점대비현재", "종목저점후"):
            self.assertIn(f">{title}<", joined, f"‘{title}’ 칸이 없다")
        # 세 숫자가 각각 제 칸에 들어간다.
        for value in ("-21.78%", "-12.69%", "+11.6%"):
            self.assertIn(value, joined, f"{value}가 표에 없다")
        # 한 칸에 겹쳐 넣던 방식은 걷어냈다.
        self.assertNotIn("j3-dd-line", joined)
        self.assertNotIn("그날 고점 대비", joined)
        # 셋이 무엇인지 설명하는 줄이 표 위에 있어야 한다. '종목저점후'는 그 종목
        # 스스로의 저점이 아니라 기준일이 출발점이므로 그 사실을 밝혀 둔다.
        self.assertIn("<b>낙폭 칸 셋</b>", joined)
        self.assertIn("갈래와 점수는 ‘고점 대비’로 정합니다", joined)
        self.assertIn("그 종목 스스로의 저점이 아니라", joined)
        # 상승장은 칸이 하나 그대로다 — 기준일이라는 것이 없다.
        up = self._run_with_mode("breakout", "find_breakout_pullback_stocks",
                                 _breakout_result())
        up_joined = " ".join(str(node.value) for node in up.markdown)
        self.assertNotIn("고점대비현재", up_joined)

    def test_the_score_has_its_own_column_next_to_the_rank(self):
        """점수는 번호 칸이 아니라 **다음 칸**이다(2026-08-06 사용자 지시).

        번호 칸에 같이 넣었더니 '1'과 '58점'이 붙어 158점처럼 읽혔다.

        **칸 이름은 「번호 · 점수 (참고)」다**(2026-08-07 상하님 지시, 2026-08-20에
        다시 확인하심). 「순위 · 총점」으로 적으면 검증되지 않은 차례를 1위·2위처럼
        보이게 해서 화면이 거짓말을 한다. 이 배점은 상하님 지시문이 정해 준 것이지
        제가 과거차트로 "이 차례가 맞다"를 확인한 것이 아니다.
        """
        app = self._run_with_mode("breakout", "find_breakout_pullback_stocks",
                                  _breakout_result())
        markdowns = [str(node.value) for node in app.markdown]
        joined = " ".join(markdowns)
        # 번호·점수·종목은 각각 다른 칸이라 markdown도 따로 나간다.
        # **실제로 그린 머리글만** 고른다 — CSS 묶음에도 j3-th-head라는 글자가 있다.
        heads = [value for value in markdowns if "j3-th-head'>" in value]
        self.assertTrue(any("j3-th-head'>번호<" in value for value in heads), "번호 칸이 없다")
        self.assertTrue(any("j3-th-head'>점수<" in value for value in heads), "점수 칸이 없다")
        # **(참고)는 뺐다**(2026-08-21 상하님 지시).
        self.assertFalse(any("(참고)" in value for value in heads), "(참고)가 남아 있다")
        source = (ROOT / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
        block = source.split("def _render_us_swing_finder(")[1].split("\ndef ")[0]
        self.assertLess(block.index("j3-th-head'>번호"),
                        block.index("j3-th-head'>점수"))
        self.assertLess(block.index("j3-th-head'>점수"),
                        block.index("j3-th-head'>종목"))
        # 「순위」·「총점」이 되살아나면 여기서 깨진다.
        for gone in ("j3-th-head'>순위", "j3-th-head'>총점"):
            self.assertNotIn(gone, block, f"{gone}이 되살아났다")
        # 중요·보조 점수는 표가 아니라 **선택종목 세부사항**에서 본다(2026-08-21).
        self.assertIn("중요 점수", joined)
        self.assertIn("보조 점수", joined)
        self.assertTrue(any("점수는 승률이 아닙니다" in str(node.value)
                            for node in app.caption), "총점을 승률로 읽지 말라는 말이 없다")

    def test_the_detail_says_each_thing_once(self):
        """같은 말을 되풀이하지 않는다(2026-08-06 상하님 지적).

        예전에는 '이 규칙에는 손절가가 없습니다'가 한 화면에 여섯 번,
        '52주 신고가를 찍고…'가 세 번 나왔다.
        """
        result = _breakout_result()
        app = self._run_with_mode("breakout", "find_breakout_pullback_stocks", result,
                                  pick=result["rows"][0]["ticker"])
        joined = " ".join(
            [str(node.value) for node in app.markdown]
            + [str(node.value) for node in app.success]
            + [str(node.value) for node in app.warning]
        )
        self.assertLessEqual(joined.count("52주 신고가 anchor 뒤"), 1,
                             "종목 근거 문장이 여러 번 나온다")
        # 점수는 하나만 — '이 갈래 점수'·'눌림 점수'가 같이 있어 헷갈렸다.
        self.assertNotIn("이 갈래 점수", joined)
        # 상승장 여섯 칸 상자는 자격을 판단한 값을 보여준다(옛 거래량 칸이 아니다).
        cards = next(str(node.value) for node in app.markdown
                     if "최근 3개월 등수" in str(node.value)
                     and "j3-mc-label" in str(node.value))
        self.assertIn("신고가 후 눌림", cards)
        # **「핵심」·「보조」가 무슨 말인지 모르겠다**(2026-08-21 상하님).
        # 둘 다 점수이므로 이름이 그렇게 말하게 바꿨다.
        self.assertIn("중요 점수", cards)
        self.assertIn("보조 점수", cards)
        self.assertNotIn("핵심점수", cards)
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

    def test_the_theme_card_says_it_is_a_different_ruler(self):
        """테마 자체 점수 70.7/100과 배점표의 테마 40점이 어긋나 보였다(2026-08-07).

        둘 다 맞는 값인데 자가 다르다 — 하나는 테마 순위표가 테마를 100점으로
        잰 값이고, 하나는 이 종목의 급락 배점 100점 중 테마 몫이다. 화면이 그
        사실을 말하지 않으면 "이거 맞냐"는 물음을 다시 받는다.
        """
        source = (ROOT / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
        block = source.split("def _pullback_backdrop_cards(")[1].split("\ndef ")[0]
        self.assertIn("테마 자체 점수", block)
        self.assertIn("다른 자", block)
        self.assertIn("j3-reason-sub", block)
        # 예전 문구가 남아 있으면 무엇을 잰 점수인지 다시 알 수 없어진다.
        self.assertNotIn("최고 테마 점수", block)

    def test_the_detail_does_not_point_at_a_button_that_is_not_there(self):
        """"표 위 설명 보기에 있습니다"가 없는 곳을 가리켰다(2026-08-07 지적).

        이 상세는 **순위 7에서도 열린다.** 거기에는 그 단추가 없어서 가리킨 곳에
        아무것도 없었다. 상하님 지시("중요하지 않으면 빼라")대로 그 줄을 뺐다 —
        배점표는 표 위 설명 구역에 그대로 있고, 무슨 항목에 몇 점인지는 바로 위
        '종목 선정 근거' 표가 이미 다 보여준다.
        """
        source = (ROOT / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
        block = source.split("def _render_pullback_detail(")[1].split("\ndef ")[0]
        self.assertNotIn("표 위 ‘이 화면 설명 보기’에 있습니다", block)
        # 갈래가 아닌 화면(눌림 점수 표)의 안내는 그대로 남는다.
        self.assertIn("눌림 점수는 지금이 눌림 자리로 좋은지", block)
        # 순위 7도 이 상세를 쓴다 — 그래서 여기서 다른 구역을 가리키면 안 된다.
        self.assertIn("_render_pullback_detail(picked, market, ranking, mode=origin_mode)",
                      source)

    def test_the_backdrop_is_two_cards_above_the_score_table(self):
        """네 칸 중 둘은 바로 위 판을 소리 내어 다시 읽는 것이었다(2026-08-07).

        '종목' 칸은 배점표를, '매수' 칸은 매수 심사 카드·지금 할 일 상자·겨자색
        상자에 이어 네 번째로 같은 말을 했다. 시장·테마 둘만 이 상세에서 처음
        나오는 이야기라 둘만 남기고, 자리도 배점표 위로 올렸다.
        """
        source = (ROOT / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
        cards = source.split("def _pullback_backdrop_cards(")[1].split("\ndef ")[0]
        self.assertIn('return [("시장 상황", market_body), ("테마 상황", theme_body)]',
                      cards)
        block = source.split("def _render_pullback_detail(")[1].split("\ndef ")[0]
        # 배점표보다 **위**에 그려야 시장 → 테마 → 종목 순으로 읽힌다.
        self.assertLess(block.index("_pullback_backdrop_cards("),
                        block.index("score_col, plan_col = st.columns"))
        # 차트 뒤 맨 아래 있던 옛 자리는 비어 있어야 한다.
        self.assertNotIn("추천 근거 요약", block)

    def test_the_index_chart_can_be_toggled_by_finger(self):
        """폰에서 다시 눌러도 당일로 안 돌아왔다(2026-08-07 상하님 지적).

        마우스 전용 규칙(:hover)만 있었다. 손으로 누른 자리는 브라우저가 hover를
        붙잡아 둬서 두 번째 누름이 먹지 않고, 태블릿은 손으로는 아예 안 바뀌었다.
        숨긴 체크상자 + 그림을 덮은 label로 누를 때마다 확실히 뒤집는다.
        """
        source = (ROOT / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
        block = source.split("def _index_chart_swap(")[1].split("\ndef ")[0]
        self.assertIn("type='checkbox'", block)
        self.assertIn("j3-idx-tapzone", block)
        # 자리마다 이름이 달라야 한 칸을 눌러도 옆 칸이 같이 안 바뀐다.
        self.assertIn("tap_id", block)
        self.assertIn("key=f\"idx{symbol}\"", source)
        self.assertIn("key=f\"etf{symbol}\"", source)
        # :hover는 **마우스가 주된 장치일 때만** — 손으로 눌러 붙잡힌 hover와
        # 체크상자가 싸우면 다시 안 돌아온다.
        self.assertIn("@media (hover: hover) and (pointer: fine) {", source)
        hover_rules = source.count(".j3-top-cell:hover .j3-idx-swap")
        media_block = source.split("@media (hover: hover) and (pointer: fine) {")[1]
        self.assertEqual(hover_rules, media_block.count(".j3-top-cell:hover .j3-idx-swap"),
                         ":hover 규칙이 미디어쿼리 밖에도 남아 있다")
        self.assertIn(".j3-idx-swap .j3-idx-tap:checked ~ .j3-idx-now", source)
        self.assertIn(".j3-idx-swap .j3-idx-tap:checked ~ .j3-idx-more", source)

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
        # 기존 두 자리와 GENERAL 종목·테마·최종 요약이 모두 이 손질을 거쳐야 한다.
        self.assertEqual(3, source.count("j3-reason-mustard'>{_mustard_html("))

    def test_the_three_charts_stand_side_by_side_without_a_big_copy(self):
        """**맨 위 「크게 보기」는 뺐다**(2026-08-21 상하님 지시).

        상하님 — "일봉 크게 보기를 없애라, 밑에 보면 일봉이 또 있으니."
        같은 그림이 한 화면에 두 번 있었다. 큰 것을 없앴으므로 그것을 바꾸던
        「일봉·주봉·월봉」 단추도 함께 뺐다 — 누를 데는 있는데 바뀌는 것이
        없으면 화면이 거짓말을 한다.
        """
        source = (ROOT / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
        block = source.split("def _render_price_chart_bundle(")[1].split("\ndef ")[0]
        for gone in ("BIG_CHART_HEIGHT", "j3-chart-big-title",
                     "on_click=_pick_bundle_chart", "j3_bundle_pick_"):
            self.assertNotIn(gone, block, f"{gone}이 되살아났다")
        # 셋이 폭을 고르게 나눠 갖는다("너무 왼쪽으로 너무 적게 차지한다" 지적).
        self.assertIn("st.columns(3)", block)
        self.assertNotIn("st.columns([1, 1, 1,", block)
        # 손톱그림 높이는 그대로 108px다 — 눈금·범례를 뺀 작은 그림이다.
        self.assertIn("height=THUMB_CHART_HEIGHT, compact=True", block)
        self.assertIn("THUMB_CHART_HEIGHT = 108", source)
        # **거래량은 일봉 아래에 남는다** — 큰 그림이 그리던 것을 옮겨 왔다.
        self.assertIn('include_volume=timeframe == "일봉"', block)

    def test_rulebook_table_slides_sideways_like_the_pullback_table(self):
        """폰에서 순위·종목이 따로 쌓이던 것을 눌림목 표와 같은 규칙으로 맞췄다.

        표 상자 이름을 옆으로 밀기 규칙 목록에 넣지 않으면 다시 쌓인다
        (2026-08-01 캡처로 확인).
        """
        source = (ROOT / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
        self.assertIn(".st-key-j3_rulebook_table,", source)
        # 2026-08-06 — '점수' 칸이 늘어 이 표만 min-width를 따로 뒀다. 그래서 이
        # 줄만 다른 표와 묶이지 않고 홀로 선다. 2026-08-07에 급락 낙폭이 세 칸으로
        # 갈리면서 열한 칸이 돼 1180px로 넓혔다.
        self.assertIn('.st-key-j3_rulebook_table [data-testid="stHorizontalBlock"] {', source)
        self.assertIn("min-width: 1180px", source)
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
            # 로그인 화면에서는 갈 곳을 고르지 않는다(2026-08-09). 로그인만 하면
            # '어디로 갈까요'가 나오고 거기서 **링크**로 미국테마에 간다 —
            # st.switch_page가 브라우저 기록에 같은 주소를 하나 더 쌓아
            # 뒤로가기가 맨홈을 두 번 지나게 만들었기 때문이다.
            app.text_input[0].set_value("test")
            next(node for node in app.button if node.key == "login_submit").click().run(timeout=60)
            self.assertIn("자비스3", [node.page for node in app.get("page_link")])
            app.session_state["j3_briefing_page"] = "market"
            app.switch_page("pages/2_자비스3.py")
            app.run(timeout=60)

        self.assertEqual(len(app.exception), 0)
        self.assertTrue(app.session_state.filtered_state.get("authenticated"))
        self.assertTrue(any("미국 전체시장 판단" in str(node.value)
                            for node in app.markdown), "화면 맨 위 제목이 없다")

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
            # 로그인 화면에서는 갈 곳을 고르지 않는다(2026-08-09) — 게스트로 들어가면
            # '어디로 갈까요'가 나오고, 거기서 **링크**로 미국테마에 간다.
            next(node for node in app.button if node.key == "login_guest").click().run(timeout=60)
            self.assertTrue(any("어디로 갈까요" in str(node.value) for node in app.markdown))
            self.assertIn("자비스3", [node.page for node in app.get("page_link")])
            app.session_state["j3_briefing_page"] = "market"
            app.switch_page("pages/2_자비스3.py")
            app.run(timeout=60)

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


def test_general_detail_keeps_three_score_groups_and_browser_only_help():
    source = PAGE.read_text(encoding="utf-8")
    self_contained = source[source.index("def _render_stock_detail"):source.index("_THEME_RANK_OPEN")]
    assert '"\uC885\uBAA9\uC810\uC218"' in self_contained
    assert '"\uD14C\uB9C8\uC810\uC218"' in self_contained
    assert '"\uCD5C\uC885\uC810\uC218"' in self_contained
    assert "\uC885\uBAA9 60% + \uD14C\uB9C8 40%" in self_contained
    assert "_general_theme_score_help_html" in self_contained
    helper = source[source.index("def _general_theme_score_help_html"):source.index("def _swing_factor_table_html")]
    assert "components.html(script, height=0)" in helper
    assert "get_live_quote" not in helper
    assert "_download" not in helper


if __name__ == "__main__":
    unittest.main()
