"""자비스4 페이지 렌더 테스트 — 네트워크 없이 화면 골격과 계약을 검증한다."""

import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import gauge_ui
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).parent
PAGE = ROOT / "pages" / "3_자비스4.py"


def _index_metrics(current=6641.52, change=0.87):
    return {
        "ok": True, "current": current, "prev_close": current / (1 + change / 100),
        "change_pct": change, "ret5": 1.2, "ret20": 3.4, "ret60": 5.6,
        "sma20": current * 0.98, "sma50": current * 0.95, "sma200": current * 0.9,
        "high52": current * 1.1, "from_high_pct": -9.0, "volume_ratio": 1.1,
        "avg_trading_value": 5e11, "atr": current * 0.01, "atr_pct": 1.0,
        "last_date": "2026-07-22",
    }


def _market():
    return {
        "ok": True, "score": 60, "regime": "중립·선별", "posture": "비중 축소·확인 후 진입",
        "previous_market": {
            "ok": True, "score": 55, "regime": "중립·선별",
            "posture": "비중 축소·확인 후 진입",
        },
        "reasons": ["KOSPI 50일선 위"],
        "score_breakdown": [
            {"label": "KOSPI 50일선", "earned": 20, "max": 20, "state": "충족"},
            {"label": "KOSPI 20일선", "earned": 10, "max": 10, "state": "충족"},
            {"label": "KOSDAQ 50일선", "earned": 0, "max": 15, "state": "미충족"},
            {"label": "KOSDAQ 20일선", "earned": 0, "max": 10, "state": "미충족"},
            {"label": "미국 전일", "earned": 15, "max": 15, "state": "충족"},
            {"label": "외국인·기관 5일 수급", "earned": 15, "max": 15, "state": "충족"},
            {"label": "원/달러 안정", "earned": 0, "max": 15, "state": "미충족"},
        ],
        "rows": {
            "KOSPI": _index_metrics(),
            "KOSDAQ": _index_metrics(1824.30, -0.34),
            "USDKRW": _index_metrics(1384.5, -0.21),
        },
        "us_prev": {
            "ok": True, "spy_change": 0.74, "qqq_change": 1.66,
            "regime": "중립·선별", "score": 65, "fear_greed": 41.0, "fear_greed_label": "공포",
            "market_overview": {
                "ok": True, "score": 65, "regime": "중립·선별",
                "posture": "비중 축소·확인 후 진입",
                "previous_market": {
                    "ok": True, "score": 60, "regime": "중립·선별",
                    "posture": "비중 축소·확인 후 진입",
                },
            },
            # 게이지 그림은 지난 값까지 받아 그린다(2026-07-24).
            "fear_greed_detail": {
                "ok": True, "score": 41.0, "rating_kr": "공포", "previous_close": 45.0,
                "previous_1_week": 55.0, "previous_1_month": 57.0, "previous_1_year": 44.0,
                "stale": False,
            },
        },
        "foreign": {
            "ok": True, "net5_amount": 2.41e11,
            "live_ok": True, "live_net5_amount": -18_786 * 1e8,
            "live_foreign_net5_amount": -8_000 * 1e8,
            "live_institution_net5_amount": -10_786 * 1e8,
            "live_as_of": "2026-07-29T10:55:00+09:00",
            "live_stale": False,
            "detail": "삼성전자 5일 +1,200억",
            "stocks": [
                {
                    "label": "삼성전자", "live_net5_amount": -7_500 * 1e8,
                    "day_net_amount": -3_100 * 1e8, "day_date": "2026.07.28",
                    "flow": {"latest_date": "2026.07.28"},
                },
                {
                    "label": "SK하이닉스", "live_net5_amount": -11_286 * 1e8,
                    "day_net_amount": -4_250 * 1e8, "day_date": "2026.07.28",
                    "flow": {"latest_date": "2026.07.28"},
                },
            ],
        },
        "intraday_flow": {
            "ok": True, "foreign_eok": 1_745, "institution_eok": 12_548,
            "net_amount": 14_293 * 1e8, "as_of_time": "10:37",
            "source": "네이버 시간별 투자자매매동향(지연 가능)",
            "realtime": False, "stale": False,
        },
        "phase": {"label": "정규장", "seoul_time": "2026-07-22T10:00:00+09:00"},
        "checked_at": "2026-07-22T10:00:00+09:00",
    }


def _theme_stocks(count=6):
    return [
        {"code": f"00066{i}", "name": f"종목{i}", "price": 100_000 + i * 1000,
         "change_pct": 2.0 - i * 0.3, "volume": 500_000, "trading_value": 5e10}
        for i in range(count)
    ]


def _ranking():
    rows = []
    for index, name in enumerate(("반도체/HBM", "조선/해운", "방산"), 1):
        rows.append({
            "no": 500 + index, "name": name, "ok": True, "rank": index,
            "score": 90 - index * 5, "status": "주도", "change_pct": 2.4 - index * 0.4,
            "relative": 9.8 - index, "up_ratio": 83.0, "strong_ratio": 45.0,
            "stock_count": 12, "total_trading_value": 3e12, "is_new": index == 3,
            "stocks": _theme_stocks(),
            "basis": "KOSPI 대비 +9.8%p · 구성종목 상승 83%",
        })
    return {
        "ok": True, "rows": rows, "entered": ["방산"], "dropped": ["게임"],
        "total_scanned": 266, "kospi_change": 0.87,
        "checked_at": "2026-07-22T10:00:00+09:00", "stale": False, "error": None,
    }


def _flow(ok=True):
    return {
        "ok": ok, "rows": [], "net5_amount": 3.21e11, "net20_amount": 9e11,
        "net5_shares": 100_000, "buy_streak_days": 4,
        # 동반(둘 다 순매수) 자료 — 5일은 점까지, 20일은 숫자만 쓴다.
        "day_marks": ["both_buy", "both_buy", "one", "both_buy", "both_sell"],
        "both_buy_days5": 3, "window5": 5,
        "both_buy_days20": 14, "both_sell_days20": 3, "window20": 20,
        "turnover5_amount": 6.42e12, "net5_ratio_pct": 5.0,
        "foreign_net5": 60_000, "institution_net5": 40_000, "latest_date": "2026.07.21",
    }


def _leaders():
    rows = []
    for index, (code, name) in enumerate(
        (("000660", "SK하이닉스"), ("042700", "한미반도체"), ("007660", "이수페타시스")), 1
    ):
        metrics = _index_metrics(1_990_000 - index * 100_000, 2.3 - index * 0.5)
        plan = {
            "state": "눌림목 대기", "recommendation": "조건부 후보",
            "trigger": 1_996_000, "zone_high": 2_010_000,
            "invalidation": 1_868_000, "target": 2_252_000,
            "buy_reason": "상승 추세 안의 20일선 눌림으로 기준가 회복 후에만 진입합니다.",
        }
        rows.append({
            "code": code, "name": name, "rank": index, "score": 88.6 - index * 5,
            "score_parts": [17.2, 12.9, 15.0, 15.0, 5.5, 17.0],
            "metrics": metrics, "flow": _flow(), "plan": plan,
            "stock_reason": f"테마 내 종합 {index}위 · 외국인+기관 5일 +3,210억",
            "daily": None,
        })
    return {"ok": True, "rows": rows, "theme_ret20": 8.0, "checked_at": "x"}


def _pullback_stocks():
    """눌림목 종목 찾기 결과(사용자 스펙: 신고가 1~20일 전 · 테마 2개 이상 · 75점 이상)."""
    rows = []
    for index, (code, name, themes) in enumerate(
        (("086790", "하나금융지주", ["반도체/HBM", "조선/해운"]),
         ("055550", "신한지주", ["조선/해운", "방산"])), 1
    ):
        rows.append({
            "code": code, "name": name, "themes": themes, "theme_name": themes[0],
            "price": 60_000, "change_pct": 0.5, "volume": 400_000, "trading_value": 2e10,
            "metrics": _index_metrics(60_000, 0.5),
            "flow": _flow(), "score": 95.5 - index * 5, "peak_score": 96.7 - index * 5,
            "score_parts": [20, 15, 20, 15, 10, 15],
            "pullback": {"score": 95.1 - index, "gap_pct": 1.1, "from_high_pct": -7.6,
                         "high52_days_ago": 3 * index, "above_sma200": True,
                         "parts": [25, 25, 20, 15, 10]},
            "pullback_rank": index,
            "plan": {"state": "눌림목 대기", "recommendation": "조건부 후보"},
        })
    return {
        "ok": True, "stale": False, "rows": rows,
        "multi_theme_count": 291, "scanned_count": 180, "screened_count": 21,
        "window": (1, 20), "checked_at": "x",
    }


def _chart_payload():
    index = pd.bdate_range("2026-01-01", periods=60)
    frame = pd.DataFrame({"Close": [100_000 + i * 500 for i in range(60)]}, index=index)
    frame["MA20"] = frame["Close"].rolling(20).mean()
    frame["MA50"] = frame["Close"].rolling(50).mean()
    volume = pd.DataFrame({"Volume": [500_000 + i for i in range(60)]}, index=index)
    return {"ok": True, "price": frame[["Close", "MA20", "MA50"]], "volume": volume}


def _chart_bundle():
    payload = _chart_payload()
    return {"ok": True, "charts": {"일봉": payload, "주봉": payload, "월봉": payload}}


def _us_market_overview():
    return {
        "ok": True,
        "phase": {"label": "장 마감"},
        "rows": {
            "^GSPC": {
                "ok": True, "current": 7_428.78,
                "change_pct": 0.21, "last_session_change_pct": 0.21,
            },
            "^IXIC": {
                "ok": True, "current": 24_876.91,
                "change_pct": -0.22, "last_session_change_pct": -0.22,
            },
            "^DJI": {
                "ok": True, "current": 52_747.32,
                "change_pct": 1.03, "last_session_change_pct": 1.03,
            },
            "^NDX": {
                "ok": True, "current": 27_763.13,
                "change_pct": -0.98, "last_session_change_pct": -0.98,
            },
        },
    }


def _trades():
    return [{
        "id": 1, "buy_date": "2026-07-20", "code": "000660", "stock_name": "SK하이닉스",
        "theme_name": "반도체/HBM", "trade_style": "단타", "buy_price": 1_950_000,
        "quantity": 1.0, "status": "보유", "sell_date": None, "sell_price": None,
        "result_pct": None, "market_regime": "중립·선별", "market_score": 60,
        "theme_score": 85, "stock_score": 88, "memo": None,
    }]


def _patches(market=None):
    return (
        patch("jarvis4_data.get_market_overview", return_value=market or _market()),
        patch("jarvis4_data.get_theme_rankings", return_value=_ranking()),
        patch("jarvis4_data.get_all_themes", return_value={
            "ok": True, "stale": False,
            "themes": {1: {"no": 1, "name": "반도체/HBM", "change_pct": 2.4},
                       2: {"no": 2, "name": "은행", "change_pct": -0.4}},
        }),
        patch("jarvis4_data.get_theme_leaders", return_value=_leaders()),
        patch("jarvis4_data.get_chart_bundle", return_value=_chart_bundle()),
        patch("jarvis4_data.get_live_quote", return_value={"ok": True, "current": 1_990_000}),
        patch("jarvis4_data.get_intraday_chart", return_value=None),
        patch("jarvis4_data.get_index_intraday", return_value={
            "points": [6_590.0, 6_610.0, 6_641.52], "base": 6_584.2,
        }),
        patch("jarvis4_data.get_us_futures_live", return_value={
            "ok": True, "stale": False, "values": {
                "NQ=F": {
                    "label": "나스닥100 선물", "current": 28_149.25,
                    "prev_close": 27_922.0, "change_pct": 0.81,
                    "chart": {"points": [27_980.0, 28_020.0, 28_149.25], "base": 27_922.0},
                    "as_of": "07.29 09:22",
                },
                "ES=F": {
                    "label": "S&P500 선물", "current": 7_498.25,
                    "prev_close": 7_465.25, "change_pct": 0.44,
                    "chart": {"points": [7_470.0, 7_485.0, 7_498.25], "base": 7_465.25},
                    "as_of": "07.29 09:22",
                },
            },
        }),
        patch("jarvis4_data.get_fx_intraday", return_value={
            "ok": True, "stale": False, "current": 1_455.98,
            "prev_close": 1_453.71, "change_pct": 0.16,
            "chart": {"points": [1_453.8, 1_454.9, 1_455.98], "base": 1_453.71},
            "as_of": "07.29 09:22",
        }),
        patch("us_index_data.display", return_value=[
            ("^GSPC", "S&P 500"), ("^IXIC", "나스닥 종합"),
            ("^DJI", "다우존스"), ("^NDX", "나스닥100"),
        ]),
        patch("us_index_data.market_overview", return_value=_us_market_overview()),
        patch("us_index_data.sparklines", return_value={
            # 차트 끝값은 일부러 요약값과 다르게 둔다. 한국테마가 이 값을 숫자로
            # 재계산하지 않고 미국테마의 요약값을 그대로 쓰는지 검증한다.
            "^GSPC": {"points": [7_410.0, 7_427.26], "base": 7_413.0},
            "^IXIC": {"points": [24_900.0, 24_874.45], "base": 24_932.0},
            "^DJI": {"points": [52_650.0, 52_731.60], "base": 52_206.0},
            "^NDX": {"points": [27_800.0, 27_760.90], "base": 28_040.0},
        }),
        patch("jarvis4_data.find_pullback_stocks", return_value=_pullback_stocks()),
        patch("market_signal_ui.collect_kr_flow_snapshot", return_value=({}, [])),
        patch("database.save_kr_flow_snapshot"),
        patch("database.list_kr_flow_snapshots", return_value=[{}]),
        patch("jarvis4_store.ensure_tables"),
        patch("jarvis4_store.trade_progress", return_value={
            "total_count": 1, "open_count": 1, "closed_count": 0, "minimum_sample": 30,
        }),
        patch("jarvis4_store.list_trades", return_value=_trades()),
    )


def _run_page(market=None):
    started = []
    try:
        for item in _patches(market):
            item.start()
            started.append(item)
        app = AppTest.from_file(str(PAGE), default_timeout=90)
        app.secrets["APP_PASSWORD"] = "test"
        app.session_state["authenticated"] = True
        _open_all_details(app)
        app.run(timeout=90)
        return app
    finally:
        for item in reversed(started):
            item.stop()


def _open_all_details(app):
    """상세·매수기록을 미리 펴 둔다.

    2026-07-30부터 이 구역들은 눌러야 열린다(사용자 지시). 테스트에서 단추를
    누르면 patch가 이미 풀린 뒤라 시세를 실제로 받으러 나가므로, 세션 값으로
    열어 둔 상태에서 화면을 그린다. 여는 장치 자체는 test_top_reviewed가 지킨다.
    """
    for panel in ("theme", "pullback", "top7", "mystock"):
        app.session_state[f"j4_detail_open_{panel}"] = True
        app.session_state[f"j4_buyform_open_{panel}"] = True
    app.session_state["j4_theme_panel_open"] = True
    return app


class Jarvis4PageTests(unittest.TestCase):
    def test_theme_rank_click_opens_and_close_button_hides_whole_theme_panel(self):
        """한국도 순위의 테마 클릭으로 종목 화면 전체를 열고 닫는다."""
        started = []
        try:
            for item in _patches():
                item.start()
                started.append(item)
            app = AppTest.from_file(str(PAGE), default_timeout=90)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
            app.run(timeout=90)
            self.assertFalse(app.session_state.filtered_state.get("j4_theme_panel_open", False))
            self.assertFalse([
                node for node in app.button if str(node.key or "").startswith("j4lbtn_")
            ])

            theme_button = next(
                node for node in app.button if str(node.key or "") == "j4tbtn_00"
            )
            theme_button.click().run(timeout=90)
            self.assertTrue(app.session_state.filtered_state.get("j4_theme_panel_open"))
            self.assertTrue([
                node for node in app.button if str(node.key or "").startswith("j4lbtn_")
            ])
            close_button = next(
                node for node in app.button
                if str(node.key or "") == "close_j4_theme_panel_open_top"
            )
            close_button.click().run(timeout=90)
        finally:
            for item in reversed(started):
                item.stop()

        self.assertEqual(len(app.exception), 0)
        self.assertFalse(app.session_state.filtered_state.get("j4_theme_panel_open"))
        self.assertFalse([
            node for node in app.button if str(node.key or "").startswith("j4lbtn_")
        ])

    def test_current_leader_name_click_opens_comparison_and_detail(self):
        """이미 선택된 1위 종목도 누르면 비교와 상세가 함께 열린다."""
        started = []
        try:
            for item in _patches():
                item.start()
                started.append(item)
            app = AppTest.from_file(str(PAGE), default_timeout=90)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
            _open_all_details(app)
            app.session_state["j4_detail_open_theme"] = False
            app.session_state["j4_leadercmp_open"] = False
            app.run(timeout=90)
            buttons = [
                node for node in app.button if str(node.key or "").startswith("j4lbtn_")
            ]
            self.assertTrue(buttons, "종목 이름 버튼이 없다")
            buttons[0].click().run(timeout=90)
        finally:
            for item in reversed(started):
                item.stop()

        self.assertEqual(len(app.exception), 0)
        state = app.session_state.filtered_state
        self.assertTrue(state.get("j4_detail_open_theme"), state)
        self.assertTrue(state.get("j4_leadercmp_open"), state)
        self.assertTrue(any("j4-stock-name" in str(node.value) for node in app.markdown))
        self.assertTrue([node for node in app.radio if str(node.label) == "상세 종목 선택"])

    def test_page_renders_market_then_flow_then_tabs(self):
        app = _run_page()
        self.assertEqual(len(app.exception), 0)
        subheaders = [str(node.value) for node in app.subheader]
        self.assertIn("한국 전체시장 판단", subheaders)
        markdowns = " ".join(str(node.value) for node in app.markdown)
        # 시장판단의 한국장 기관 수급 반전 카드를 그대로 가져왔는지
        self.assertIn("한국장 기관 수급 현황", markdowns)
        # 동적 테마 선정 문구와 테마표
        self.assertIn("오늘의 강한 테마", markdowns)
        self.assertIn("자동 탈락", markdowns)
        # 종목 상세와 한국형 6개 항목
        self.assertIn("SK하이닉스", markdowns)
        self.assertIn("수급(외국인+기관)", markdowns)
        self.assertIn("j4-stock-name", markdowns)
        # 공포·탐욕 게이지를 한국테마 상단에도 넣었다(2026-07-24 사용자 요청).
        # 구간 이름은 한국어여야 한다.
        self.assertIn("fg-gauge", markdowns)
        self.assertIn("fg-needle", markdowns)
        self.assertIn("공포·탐욕 지수", markdowns)
        self.assertIn("전일 종가", markdowns)
        self.assertNotIn("EXTREME FEAR", markdowns)
        # 게이지는 상단 지표 줄 안에 있어야 한다 — 아래 큰 카드로 빼지 않는다.
        top_row = next(
            str(node.value) for node in app.markdown
            if "<div class='j4-top-row'>" in str(node.value)
        )
        self.assertIn("fg-box", top_row)
        # 시장 국면·미국 시장국면·공포탐욕 세 가지 모두 같은 게이지로 보여준다.
        self.assertIn("시장 국면 (한국)", top_row)
        us_country = "<span style='color:#44f0a1'>(미국)</span>"
        self.assertIn(f"{us_country} 시장 국면", top_row)
        self.assertIn(f"{us_country} 공포·탐욕 지수", top_row)
        self.assertEqual(top_row.count(us_country), 2)
        self.assertTrue(any(
            "j4-gauge-after-gap" in str(node.value) for node in app.markdown
        ))
        # 선물 숫자와 차트는 같은 1분봉 응답을 쓰고 시각도 함께 보여준다.
        self.assertIn("28,149", top_row)
        self.assertIn("1분봉 기준 07.29 09:22", top_row)
        self.assertIn("<svg", top_row)
        # 미국 4대 지수 숫자는 차트 끝점으로 재계산하지 않고 미국테마 값을 쓴다.
        for value in ("7,428.78", "24,876.91", "52,747.32", "27,763.13"):
            self.assertIn(value, top_row)
        for chart_last in ("7,427.26", "24,874.45", "52,731.60", "27,760.90"):
            self.assertNotIn(f">{chart_last}<", top_row)
        # 세 카드 제목은 사용자 요청대로 같은 스카이블루를 쓴다.
        self.assertGreaterEqual(top_row.count(gauge_ui.TITLE_BLUE), 3)
        self.assertIn("전일 시장국면", top_row)
        # <style>을 지표 줄 안에 넣으면 스트림릿이 그 덩어리를 HTML로 안 보고 글로
        # 흘려버려 CSS가 글자로 찍힌다(2026-07-24 실제 깨짐). 반드시 따로 내보낸다.
        self.assertNotIn("<style>", top_row)
        # 숫자가 두 군데 나오지 않게 '미국 전일' 부제에서는 뺐다.
        self.assertNotIn("공포탐욕 41", markdowns)
        self.assertIn("대표종목 5일 수급 (현재가 환산)", top_row)
        self.assertIn("-18,786억", top_row)
        # 종목별 금액은 부호대로 칠한다. 회색 한 줄에 몰아 두면 어느 쪽이
        # 파는 쪽인지 안 보인다(2026-07-29 지시).
        self.assertIn("삼성전자 <span style='color:#ff5b5b", top_row)
        self.assertIn("-3,100억", top_row)
        self.assertIn("SK하이닉스 <span style='color:#ff5b5b", top_row)
        self.assertIn("-4,250억", top_row)
        # 완료 거래일 한 줄, 당일 한 줄로 나눈다(2026-07-29 지정 형식).
        # 날짜는 줄 앞에 한 번만 적는다 — 종목마다 붙이면 같은 날짜가 두 번 나온다.
        self.assertIn("(07.28) : 삼성전자", top_row)
        self.assertIn("(당일) : 아직 안 올라왔습니다", top_row)
        self.assertNotIn("위 줄은 종목별 하루치입니다", top_row)
        self.assertNotIn("종목별 당일 수급은 장 마감 뒤 공개됩니다", top_row)
        self.assertIn("현재가 1분 자동조회", top_row)
        # '5일 확정 수급수량 × 현재가'는 뺐다(2026-07-29 지시).
        self.assertNotIn("5일 확정 수급수량", top_row)
        self.assertNotIn("KOSPI 당일 외국인+기관 수급", top_row)

    def test_today_line_fills_in_when_published(self):
        """당일 수급이 올라오면 '(당일)' 줄이 숫자로 채워진다.

        완료 거래일 줄은 그대로 07.28을 지켜야 한다 — 두 줄이 같은 값이 되면
        어제와 오늘을 구별할 수 없다(2026-07-29 지정 형식).
        """
        market = _market()
        for stock, amount in zip(market["foreign"]["stocks"], (-1_200 * 1e8, -2_400 * 1e8)):
            stock["today_net_amount"] = amount
            stock["today_date"] = "2026.07.29"
        app = _run_page(market)
        self.assertEqual(len(app.exception), 0)
        top_row = next(
            str(node.value) for node in app.markdown
            if "<div class='j4-top-row'>" in str(node.value)
        )
        self.assertIn("(07.28) : 삼성전자", top_row)
        self.assertIn("(당일) : 삼성전자", top_row)
        self.assertIn("-1,200억", top_row)
        self.assertIn("-2,400억", top_row)
        # 채워졌으면 기다리라는 안내는 사라져야 한다.
        self.assertNotIn("아직 안 올라왔습니다", top_row)

    def test_representative_flow_names_only_successful_stock(self):
        """한 종목 조회만 성공하면 두 종목 합계인 것처럼 표시하지 않는다."""
        market = _market()
        market["intraday_flow"] = {"ok": False}
        market["foreign"]["live_ok"] = False
        market["foreign"]["stocks"] = [
            {"label": "삼성전자", "flow": {"latest_date": "2026.07.28"}},
        ]
        app = _run_page(market)
        self.assertEqual(len(app.exception), 0)
        top_row = next(
            str(node.value) for node in app.markdown
            if "<div class='j4-top-row'>" in str(node.value)
        )
        self.assertIn("삼성전자 (일부 자료)", top_row)
        self.assertNotIn("삼성전자+SK하이닉스", top_row)

    def test_representative_flow_discloses_mixed_source_dates(self):
        """두 종목의 최신 일자가 다르면 더 최신 날짜 하나로 뭉뚱그리지 않는다."""
        market = _market()
        market["intraday_flow"] = {"ok": False}
        market["foreign"]["live_ok"] = False
        market["foreign"]["stocks"] = [
            {"label": "삼성전자", "flow": {"latest_date": "2026.07.28"}},
            {"label": "SK하이닉스", "flow": {"latest_date": "2026.07.27"}},
        ]
        app = _run_page(market)
        self.assertEqual(len(app.exception), 0)
        top_row = next(
            str(node.value) for node in app.markdown
            if "<div class='j4-top-row'>" in str(node.value)
        )
        self.assertIn("기준일 상이(2026.07.27~2026.07.28)", top_row)

    def test_mobile_rules_are_emitted_and_scoped_to_phones(self):
        """폰 전용 규칙이 나가야 하고, 태블릿·PC가 바뀌면 안 된다(2026-07-24)."""
        app = _run_page()
        self.assertEqual(len(app.exception), 0)
        blocks = [str(n.value) for n in app.markdown if "@media (max-width: 600px)" in str(n.value)]
        self.assertEqual(len(blocks), 1, "폰 규칙 덩어리는 하나여야 한다")
        css = blocks[0]
        # 미디어쿼리 밖에 규칙이 새면 PC까지 바뀐다. 미디어쿼리는 다섯 —
        # 메뉴·상단 지표 줄은 태블릿까지(1200px), 그 중 '한 줄에 몇 칸'은
        # 세로·가로 두 갈래(2026-08-01), 표·글자는 폰(600px).
        self.assertEqual(css.count("@media"), 5)
        self.assertEqual(css[: len("<style>")], "<style>")
        self.assertEqual(css[len("<style>"): css.index("@media")].strip(), "")
        phone_block = css[css.index("@media (max-width: 600px)"):]
        # 표 두 개와 머리글, 게이지 순서 규칙이 모두 들어 있어야 한다.
        # 눌림목 표(j4pbf_)는 세로로 쌓지 않고 옆으로 밀어 보므로 폰 규칙에 없다.
        # 자비스4의 두 표는 세로로 쌓지 않고 옆으로 밀어 보므로 표 규칙이 폰 규칙에 없다.
        # 머리글도 숨기지 않는다 — 숨겼더니 폰에서 '종목·눌림 점수'가 안 보였다.
        # 상단 지표 줄(.fg-box)은 태블릿까지 걸리게 1200px 묶음으로 옮겼다.
        self.assertNotIn(".fg-box { order", phone_block)
        self.assertIn(".fg-box { order", css)
        self.assertIn("@media (max-width: 1200px)", css)
        self.assertNotIn("stSidebarNav", phone_block)


    def test_the_two_rulebook_buttons_sit_next_to_the_pullback_button(self):
        """설명서 두 갈래 단추 — 미국테마와 같은 자리·같은 모양(2026-08-01 사용자 지시)."""
        app = _run_page()
        self.assertEqual(len(app.exception), 0)
        keys = [str(node.key or "") for node in app.button]
        for key in ("j4_pullback_find", "j4_pullback_breakout", "j4_pullback_crash"):
            self.assertIn(key, keys, f"{key} 단추가 없다")
        source = Path("pages/3_자비스4.py").read_text(encoding="utf-8")
        self.assertIn("finder_cols = st.columns(3)", source)

    def test_rulebook_table_slides_sideways_like_the_others(self):
        """새 표를 옆으로 밀기 규칙 목록에 안 넣으면 폰에서 줄이 쌓이고 값이 겹친다."""
        source = Path("pages/3_자비스4.py").read_text(encoding="utf-8")
        self.assertIn(".st-key-j4_rulebook_table,", source)
        self.assertIn('.st-key-j4_rulebook_table [data-testid="stColumn"],', source)
        # 칸이 열 개라 900px로는 글자가 짓눌린다 — 자기 폭을 따로 갖는다(2026-08-01).
        block = source.split('.st-key-j4_rulebook_table [data-testid="stHorizontalBlock"] {')[1]
        self.assertIn("min-width: 1150px", block.split("}")[0])

    def test_korea_shows_its_own_numbers_never_the_us_ones(self):
        """2026-08-01에 한국 자료로 직접 쟀다. 미국 성적은 여전히 옮겨 적지 않는다."""
        source = Path("pages/3_자비스4.py").read_text(encoding="utf-8")
        block = source.split("def _render_rulebook_finder(")[1].split("\ndef ")[0]
        for banned in ("59.7", "92.6", "+18.0", "+11.2", "+24.9"):
            self.assertNotIn(banned, block, f"한국 화면에 미국 성적 {banned}이 들어갔다")
        # 숫자는 코드(jarvis4_data)에서 가져와야 한다 — 화면에 손으로 적으면 어긋난다.
        self.assertIn("rule.get('win_rate')", block.replace('"', "'"))

    def test_korea_always_shows_the_baseline_next_to_the_score(self):
        """성적만 적으면 광고가 된다.

        오늘 살아남은 종목만 보고 잰 것이라, 같은 종목으로 잰 '아무 날이나 샀으면'과
        견줄 때만 규칙이 값을 했는지 알 수 있다. 진 갈래는 졌다고 적어야 한다.
        """
        source = Path("pages/3_자비스4.py").read_text(encoding="utf-8")
        block = source.split("def _render_rulebook_finder(")[1].split("\ndef ")[0]
        self.assertIn("아무 날이나 사서 같은 기간 들고 있었으면", block)
        self.assertIn("아무 종목이나 샀으면", block)
        self.assertIn("기준선보다 못했습니다", block)
        self.assertIn("기준선보다 나았습니다", block)
        # 급락 국면이 몇 번뿐이었는지도 밝혀야 한다.
        self.assertIn("CRASH_REBOUND_EVENTS", block)

    def test_each_section_can_also_be_closed_from_its_bottom(self):
        """폰에서 구역 끝까지 내려가면 위 여는 단추가 화면 밖으로 나간다.

        닫으려고 다시 위로 올라가야 했다(2026-08-01 사용자 지시).
        구역마다 맨 아래에도 작은 닫기 단추를 둔다.
        """
        source = Path("pages/3_자비스4.py").read_text(encoding="utf-8")
        self.assertIn("def _section_close(", source)
        for key in ("j4_detail_open_", "j4_intraday_open_", "j4_bundle_open_"):
            self.assertIn(f'_section_close(f"{key}', source,
                          f"{key} 구역에 아래 닫기 단추가 없다")
        # 위 여는 단추보다 작고 조용해야 한다 — 같은 모양이면 화면이 어지럽다.
        self.assertIn('div[class*="st-key-close_"] button', source)

    def test_clicking_a_stock_opens_the_detail_and_the_charts(self):
        """2026-08-01 사용자 지시 — 누르면 세부사항과 차트가 같이 열려야 한다.

        그전에는 종목을 누른 뒤 '세부사항 보기'와 '일봉·주봉·월봉 보기'를 또
        눌러야 했다. 이 세 값이 빠지면 그 불편이 그대로 돌아온다.
        """
        source = Path("pages/3_자비스4.py").read_text(encoding="utf-8")
        block = source.split("def _render_rulebook_finder(")[1].split("\ndef ")[0]
        for opened in ("j4_detail_open_pullback", "j4_intraday_open_pullback",
                       "j4_bundle_open_pullback"):
            self.assertIn(opened, block, f"{opened}를 열지 않는다")

    def test_theme_cell_shows_one_name_and_cannot_overflow(self):
        """테마 이름을 다 늘어놓아 칸을 뚫고 왼쪽 값들을 덮었다(2026-08-01 캡처).

        대표 하나만 적고 나머지는 '외 N'으로 세며, 넘치면 …로 자른다.
        """
        source = Path("pages/3_자비스4.py").read_text(encoding="utf-8")
        block = source.split("def _render_rulebook_finder(")[1].split("\ndef ")[0]
        self.assertIn("외 {rest}", block)
        self.assertIn("j4-rb-clip", block)
        # 자르는 규칙 자체도 있어야 한다.
        self.assertIn("text-overflow: ellipsis", source.split(".j4-rb-clip {")[1].split("}")[0])

    def test_rulebook_table_compares_trading_value_and_shows_themes(self):
        """2026-08-01 사용자 지시 — 테마를 넣고, 거래대금은 견줄 수 있게 비중으로.

        액수만 보면 큰 회사가 늘 커서 종목끼리 비교가 안 된다.
        """
        source = Path("pages/3_자비스4.py").read_text(encoding="utf-8")
        block = source.split("def _render_rulebook_finder(")[1].split("\ndef ")[0]
        self.assertIn("거래대금 (평소 대비)", block)
        self.assertIn("소속 테마", block)
        self.assertIn("avg_trading_value", block)
        self.assertIn("배</span>", block)
        headers = block.split("headers = [", 1)[1].split("]", 1)[0]
        self.assertLess(headers.index("고점 대비"), headers.index("소속 테마"))
        self.assertLess(headers.index("소속 테마"), headers.index("갈래"))
        self.assertNotIn("together_label", block)
        for hold_class in ("j4-hold-20", "j4-hold-60", "j4-hold-120"):
            self.assertIn(hold_class, block)
        self.assertIn('_section_close("j4_pullback_open", mode_close_label)', block)

    def test_breakout_table_swaps_in_the_gain_column(self):
        """상승장에서 값을 한 것은 거래대금 비중이 아니라 최근 60일 상승폭이다."""
        source = Path("pages/3_자비스4.py").read_text(encoding="utf-8")
        block = source.split("def _render_rulebook_finder(")[1].split("\ndef ")[0]
        self.assertIn("최근 60일 상승폭 (거래대금)", block)
        self.assertIn('ret60 = metrics.get("ret60")', block)

    def test_rulebook_detail_uses_its_own_ruler(self):
        """설명서 갈래는 기존 6개 항목이 아니라 갈래 전용 배점으로 잰다(2026-08-01).

        기존 배점은 '신고가에 얼마나 가까운가'로 점수를 줘서 낙폭 종목이 정의상
        전부 '제외'로 나왔다. 이 갈림이 빠지면 그 화면으로 되돌아간다.
        """
        source = Path("pages/3_자비스4.py").read_text(encoding="utf-8")
        self.assertIn("_RULEBOOK_SCORERS", source)
        self.assertIn("crash_rebound_score", source)
        self.assertIn("breakout_score", source)
        # 상세 화면이 후보가 들고 온 배점을 실제로 쓰는지.
        self.assertIn('leader.get("factor_names")', source)
        self.assertIn('leader.get("factor_max")', source)
        # 기준가·손절 칸은 이 규칙에 없다.
        self.assertIn('if plan.get("rule_mode"):', source)
        self.assertIn("이 규칙에는 없음", source)

    def test_theme_selection_switches_theme(self):
        started = []
        try:
            for item in _patches():
                item.start()
                started.append(item)
            app = AppTest.from_file(str(PAGE), default_timeout=90)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
            _open_all_details(app)
            app.run(timeout=90)
            theme_radio = [node for node in app.radio if str(node.label) == "테마 선택"]
            self.assertEqual(len(theme_radio), 1)
            theme_radio[0].set_value("조선/해운").run(timeout=90)
        finally:
            for item in reversed(started):
                item.stop()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.session_state.filtered_state.get("j4_theme_choice"), "조선/해운")

    def test_korean_color_rule_and_won_currency(self):
        """한국장은 상승 빨강·하락 파랑이고 금액 단위는 원이다(자비스3와 반대·다름)."""
        source = PAGE.read_text(encoding="utf-8")
        self.assertIn('.j4-up { color: #ff5b5b; }', source)
        self.assertIn('.j4-down { color: #4da6ff; }', source)
        self.assertIn('return "j4-up" if float(value) >= 0 else "j4-down"', source)
        self.assertIn('f"{float(value):,.0f}원"', source)
        # 금액 표기는 전부 원화여야 한다(자비스3의 USD 표기가 새어들어오면 안 된다).
        self.assertNotIn("(USD)", source)
        self.assertNotIn("_price(", source)

    def test_page_contracts_present(self):
        source = PAGE.read_text(encoding="utf-8")
        # 수급 카드 재사용, 단타 참고 신호, 호가단위, 동적 테마
        self.assertIn("render_kr_flow_card", source)
        self.assertIn("단타 참고 신호", source)
        # 나스닥100 선물 실시간 칸(2026-07-22 사용자 요청)과 가격칸 설명
        self.assertIn("나스닥100 선물", source)
        self.assertIn("get_us_futures_live", source)
        self.assertIn("가격 칸이 채워지는 기준", source)
        # 눌림목 종목 찾기(사용자 스펙) — 통과 종목 교차 표는 2026-07-22 제거됐다
        self.assertIn("_render_pullback_finder", source)
        self.assertIn("find_pullback_stocks", source)
        self.assertNotIn("_render_pass_table", source)
        self.assertIn("round_to_tick", source)
        self.assertIn("j4tbtn_{index:02d}", source)
        # 온라인에서 옛 모듈이 남아도 죽지 않도록 필요한 함수를 전부 검사해 reload한다
        # (2026-07-22 get_us_futures_live 누락으로 AttributeError 발생)
        self.assertIn("_REQUIRED_J4_FUNCTIONS", source)
        # 전체 테마 직접 찾기(2026-07-22: 순위 밖 테마도 보고 싶다는 요구)
        self.assertIn("_render_theme_finder", source)
        self.assertIn("j4_forced_themes", source)
        self.assertIn("force_names", source)
        for name in ("get_us_futures_live", "find_pullback_stocks", "get_intraday_chart"):
            self.assertIn(f'"{name}"', source)
        # 자비스3 모듈을 건드리지 않는다
        self.assertNotIn("jarvis3_store", source)
        self.assertNotIn("import jarvis3_data", source)

    def test_pullback_finder_runs_only_after_button_and_is_clickable(self):
        """느린 전수검색은 버튼으로 시작하고 결과 종목은 클릭할 수 있어야 한다."""
        started = []
        try:
            for item in _patches():
                item.start()
                started.append(item)
            app = AppTest.from_file(str(PAGE), default_timeout=90)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
            _open_all_details(app)
            app.run(timeout=90)
            self.assertEqual(len(app.exception), 0)
            markdowns = " ".join(str(node.value) for node in app.markdown)
            self.assertIn("눌림목 종목 찾기", markdowns)
            self.assertNotIn("눌림목 베스트", markdowns)
            keys = [str(node.key or "") for node in app.button]
            self.assertIn("j4_pullback_find", keys)
            self.assertFalse([key for key in keys if key.startswith("j4pbf_")])
            find_button = next(
                node for node in app.button if str(node.key or "") == "j4_pullback_find"
            )
            find_button.click().run(timeout=90)
            keys = [str(node.key or "") for node in app.button]
            self.assertTrue([key for key in keys if key.startswith("j4pbf_")])
        finally:
            for item in reversed(started):
                item.stop()

    def test_reopening_does_not_search_again_within_five_minutes(self):
        """닫았다 바로 다시 열 때 같은 결과를 또 찾으면 안 된다 (2026-07-31).

        오늘 '새로 찾기' 단추를 뺐더니 열 때마다 다시 찾아 느려졌다는 지적을 받았다.
        단추는 하나로 두되, 방금 찾아 둔 것이 5분 안이면 조회 없이 그대로 편다.
        """
        started = []
        try:
            for item in _patches():
                item.start()
                started.append(item)
            with patch("jarvis4_data.find_pullback_stocks",
                       return_value=_pullback_stocks()) as search,                  patch("jarvis4_data.clear_pullback_cache") as clear:
                app = AppTest.from_file(str(PAGE), default_timeout=90)
                app.secrets["APP_PASSWORD"] = "test"
                app.session_state["authenticated"] = True
                _open_all_details(app)
                app.run(timeout=90)

                def press():
                    next(node for node in app.button
                         if str(node.key or "") == "j4_pullback_find").click().run(timeout=90)

                press()                      # 열기 — 여기서 한 번 찾는다
                self.assertEqual(1, search.call_count)
                press()                      # 닫기
                self.assertFalse(app.session_state.filtered_state.get("j4_pullback_open"))
                press()                      # 다시 열기 — 또 찾으면 안 된다
                self.assertEqual(1, search.call_count, "다시 열 때 또 찾았다")
                self.assertEqual(1, clear.call_count, "다시 열 때 캐시를 또 지웠다")
                self.assertTrue(app.session_state.filtered_state.get("j4_pullback_open"))
                keys = [str(node.key or "") for node in app.button]
                self.assertTrue([k for k in keys if k.startswith("j4pbf_")],
                                "다시 열었는데 표가 안 보인다")
        finally:
            for item in reversed(started):
                item.stop()

    def test_pullback_click_opens_its_own_detail_only(self):
        """눌림목 종목을 누르면 **아래 눌림목 상세만** 그 종목으로 열린다.

        2026-07-29 지시로 상세를 위(테마 종목)·아래(눌림목)로 갈랐다. 예전에는
        눌림목을 누르면 테마 선택까지 옮겨 가 위쪽 상세가 통째로 바뀌었다 —
        두 종목을 나란히 볼 수 없었다.
        """
        started = []
        try:
            for item in _patches():
                item.start()
                started.append(item)
            app = AppTest.from_file(str(PAGE), default_timeout=90)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
            _open_all_details(app)
            app.run(timeout=90)
            find_button = next(
                node for node in app.button if str(node.key or "") == "j4_pullback_find"
            )
            find_button.click().run(timeout=90)
            target = [node for node in app.button if str(node.key or "") == "j4pbf_00"]
            self.assertEqual(len(target), 1)
            target[0].click().run(timeout=90)
        finally:
            for item in reversed(started):
                item.stop()
        state = app.session_state.filtered_state
        self.assertEqual(len(app.exception), 0)
        # 고른 종목은 눌림목 상세용 자리에만 남는다.
        self.assertEqual((state.get("j4_pullback_pick") or ("", ""))[1], "086790")
        detail_markdowns = [
            str(node.value) for node in app.markdown
            if "<div class='j4-stock-name'>" in str(node.value)
        ]
        self.assertTrue(detail_markdowns, "종목 상세가 렌더되지 않았다")
        # 아래 눌림목 상세에는 고른 종목이 떠야 한다.
        self.assertTrue(
            any("하나금융지주" in value for value in detail_markdowns),
            f"눌림목 상세가 안 열렸다: {detail_markdowns}",
        )
        # 위쪽 테마 종목 상세는 그대로 남아야 한다 — 둘을 나란히 보는 것이 목적이다.
        self.assertGreaterEqual(len(detail_markdowns), 2, detail_markdowns)
        self.assertTrue(
            any("하나금융지주" not in value for value in detail_markdowns),
            f"위쪽 테마 상세까지 눌림목 종목으로 바뀌었다: {detail_markdowns}",
        )
        # 테마 선택은 건드리지 않는다.
        self.assertNotIn("반도체/HBM", state.get("j4_forced_themes") or [])

    def test_leader_name_click_changes_the_detail(self):
        """표의 종목 이름을 누르면 위쪽 상세가 그 종목으로 바뀐다(2026-07-29 지시).

        예전에는 순수 HTML 표라 이름을 눌러도 아무 일이 없었다 — 눌림목 표는
        눌리는데 이 표만 안 눌려 고장으로 보였다.
        """
        started = []
        try:
            for item in _patches():
                item.start()
                started.append(item)
            app = AppTest.from_file(str(PAGE), default_timeout=90)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
            _open_all_details(app)
            app.run(timeout=90)
            # 2위(한미반도체) 이름 버튼을 누른다.
            target = next(
                node for node in app.button if str(node.key or "") == "j4lbtn_01"
            )
            target.click().run(timeout=90)
        finally:
            for item in reversed(started):
                item.stop()
        self.assertEqual(len(app.exception), 0)
        state = app.session_state.filtered_state
        self.assertEqual(state.get("j4_stock_choice_반도체/HBM"), "042700")
        details = [
            str(node.value) for node in app.markdown
            if "<div class='j4-stock-name'>" in str(node.value)
        ]
        self.assertTrue(
            any("한미반도체" in value for value in details),
            f"이름을 눌렀는데 상세가 안 바뀌었다: {details}",
        )

    def test_leader_table_scrolls_sideways_like_the_others(self):
        """폰·태블릿에서 종목표도 옆으로 밀려야 한다.

        칸 방식으로 바꾸면서 이미 도는 두 표와 같은 CSS에 얹었는지 확인한다 —
        빠뜨리면 좁은 화면에서 칸이 세로로 쌓인다.
        """
        started = []
        try:
            for item in _patches():
                item.start()
                started.append(item)
            app = AppTest.from_file(str(PAGE), default_timeout=90)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
            _open_all_details(app)
            app.run(timeout=90)
        finally:
            for item in reversed(started):
                item.stop()
        blob = "".join(str(node.value) for node in app.markdown)
        # 셀렉터는 이미 도는 두 표와 한 묶음으로 적혀 있다. 세 규칙에 다 들어갔는지 본다.
        self.assertIn(".st-key-j4_leader_table,", blob)
        self.assertIn('.st-key-j4_leader_table [data-testid="stHorizontalBlock"]', blob)
        self.assertIn('.st-key-j4_leader_table [data-testid="stColumn"]', blob)
        # 옆으로 밀기 규칙과 같은 묶음에 있어야 뜻이 있다.
        self.assertIn("overflow-x: auto", blob)

    def test_all_six_leaders_are_selectable(self):
        """표에 1~6위를 보여주면서 상세는 1~3위만 고를 수 있었다(2026-07-29 지적).

        4~6위를 눌러도 아무 일이 없어 고장으로 보였다. 표에 나온 여섯 개는
        모두 '상세 종목 선택'에 있어야 한다.
        """
        six = _leaders()
        base = six["rows"][0]
        for index, (code, name) in enumerate(
            (("034730", "SK"), ("010950", "S-Oil"), ("096770", "SK이노베이션")), 4
        ):
            six["rows"].append({**base, "code": code, "name": name, "rank": index,
                                "score": 40.0 - index})
        started = []
        try:
            for item in _patches():
                item.start()
                started.append(item)
            leaders = patch("jarvis4_data.get_theme_leaders", return_value=six)
            leaders.start()
            started.append(leaders)
            app = AppTest.from_file(str(PAGE), default_timeout=90)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
            _open_all_details(app)
            app.run(timeout=90)
        finally:
            for item in reversed(started):
                item.stop()
        self.assertEqual(len(app.exception), 0)
        picker = next(
            node for node in app.radio
            if str(node.label) == "상세 종목 선택" and len(node.options) > 1
        )
        self.assertEqual(len(picker.options), 6, list(picker.options))
        # AppTest는 화면에 보이는 글자를 준다. 4~6위가 실제로 골라지는지 본다.
        labels = " / ".join(str(option) for option in picker.options)
        for code in ("034730", "010950", "096770"):
            self.assertIn(code, labels, labels)

    def test_my_stock_panel_searches_and_opens_detail(self):
        """맨 아래 '내 종목 현재상황'에서 이름을 치면 종목이 뜨고 상세가 열린다."""
        started = []
        search = patch("jarvis4_data.search_stocks", return_value={
            "ok": True,
            "rows": [{"code": "086790", "name": "하나금융지주", "market": "KOSPI"}],
        })
        analyze = patch("jarvis4_data.analyze_one_stock", return_value={
            "ok": True,
            "row": {
                "code": "086790", "name": "하나금융지주", "rank": 0,
                "score": 61.2, "score_parts": [0, 12, 18, 15, 8, 8],
                "metrics": _index_metrics(60_000, 0.5), "flow": _flow(),
                "plan": {"state": "눌림목 대기", "recommendation": "조건부 후보"},
                "daily": None, "partial": False, "bars": 240,
                "stock_reason": "직접 찾은 종목",
            },
        })
        try:
            for item in _patches():
                item.start()
                started.append(item)
            for extra in (search, analyze):
                extra.start()
                started.append(extra)
            app = AppTest.from_file(str(PAGE), default_timeout=90)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
            _open_all_details(app)
            app.run(timeout=90)
            box = next(
                node for node in app.text_input if str(node.key or "") == "j4_my_stock_query"
            )
            box.set_value("하나금융").run(timeout=90)
        finally:
            for item in reversed(started):
                item.stop()
        self.assertEqual(len(app.exception), 0)
        headings = [str(node.value) for node in app.markdown]
        self.assertTrue(
            any("종목검색 (검색종목 세부사항 보기)" in value for value in headings),
            "‘종목검색’ 제목이 없다",
        )
        details = [v for v in headings if "<div class='j4-stock-name'>" in v]
        self.assertTrue(
            any("하나금융지주" in value for value in details),
            f"찾은 종목 상세가 안 열렸다: {details}",
        )

    def test_pullback_table_shows_today_price_column(self):
        """눌림목 표는 신고가와 고점 대비 사이에 당일주가를 보여준다(2026-07-24)."""
        started = []
        try:
            for item in _patches():
                item.start()
                started.append(item)
            app = AppTest.from_file(str(PAGE), default_timeout=90)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
            _open_all_details(app)
            app.run(timeout=90)
            next(
                node for node in app.button if str(node.key or "") == "j4_pullback_find"
            ).click().run(timeout=90)
        finally:
            for item in reversed(started):
                item.stop()
        self.assertEqual(len(app.exception), 0)
        headers = [str(node.value) for node in app.markdown if "j4-th-head" in str(node.value)]
        titles = [value for value in headers if "당일주가" in value]
        self.assertTrue(titles, "당일주가 칸이 없다")
        cells = " ".join(str(node.value) for node in app.markdown)
        self.assertIn("60,000원", cells)


if __name__ == "__main__":
    unittest.main()


class PartnerFlowColumnTests(unittest.TestCase):
    """동반 수급 칸이 실제로 그려지는지 확인한다 (2026-07-25).

    폰·태블릿·PC가 같은 HTML을 쓰므로 여기서 통과하면 세 화면 모두 나온다
    (폰은 mobile_ui가 같은 칸을 세로로 쌓고 이름표만 붙인다).
    """

    def test_partner_columns_and_filter_render(self):
        started = []
        try:
            for item in _patches():
                item.start()
                started.append(item)
            app = AppTest.from_file(str(PAGE), default_timeout=90)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
            _open_all_details(app)
            app.run(timeout=90)
            next(
                node for node in app.button if str(node.key or "") == "j4_pullback_find"
            ).click().run(timeout=90)
        finally:
            for item in reversed(started):
                item.stop()

        self.assertEqual(len(app.exception), 0)
        markdowns = [str(node.value) for node in app.markdown]
        blob = "\n".join(markdowns)

        # 머리글
        self.assertIn("동반(5일)", blob)
        self.assertIn("동반(매수/매도/20일)", blob)
        self.assertIn("수급(대금%)", blob)
        # 5일: 숫자 3/5 와 동그라미. 글자(●○)는 글꼴마다 크기가 달라 SVG 원으로 그린다.
        # 반반으로 갈랐더니 어지럽다고 해서 세 색으로 되돌렸다(2026-07-25).
        self.assertIn("3/5", blob)
        self.assertIn("<circle cx='5' cy='5'", blob)
        self.assertIn("#ff5b5b", blob)   # 둘 다 순매수 — 빨강
        self.assertIn("#4da6ff", blob)   # 둘 다 순매도 — 파랑
        self.assertNotIn("A4.5,4.5", blob)   # 반원은 더 이상 그리지 않는다
        # 20일: 막대 하나에 매수·매도를 같이 담고 숫자는 매수/매도/전체
        self.assertIn(">14</span>/", blob)
        self.assertIn(">3</span>/", blob)
        self.assertIn(">20</span>", blob)
        # 수급은 금액이 아니라 거래대금 대비 비중만 보여준다(금액은 감이 없다).
        self.assertIn("+5.0%", blob)
        self.assertNotIn("대금 +", blob)
        # 점 읽는 법(왼쪽이 최근일)과 수급 기준일을 화면에 밝혀 둔다
        captions = " ".join(str(node.value) for node in app.caption)
        self.assertIn("왼쪽이 가장 최근 거래일", captions)
        self.assertIn("수급 기준일", captions)

    def test_wide_tables_scroll_sideways_on_small_screens(self):
        """좁은 화면에서는 칸을 쥐어짜지 않고 표만 옆으로 민다(2026-07-25 사용자 지시).

        칸을 줄이면 글자가 잘리고, 세로로 쌓으면 줄이 길어진다. 그래서 표를 원래
        폭으로 두고 손가락으로 미는 방식을 쓴다 — 폰·태블릿 공통.
        """
        started = []
        try:
            for item in _patches():
                item.start()
                started.append(item)
            app = AppTest.from_file(str(PAGE), default_timeout=90)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
            _open_all_details(app)
            app.run(timeout=90)
            next(
                node for node in app.button if str(node.key or "") == "j4_pullback_find"
            ).click().run(timeout=90)
        finally:
            for item in reversed(started):
                item.stop()

        self.assertEqual(len(app.exception), 0)
        blob = chr(10).join(str(node.value) for node in app.markdown)
        # 테마 종목표: 감싸는 상자와 최소 폭
        self.assertIn("j4-table-scroll", blob)
        self.assertIn("min-width: 980px", blob)
        # 눌림목표: 상자가 스크롤되고 줄이 접히지 않아야 한다
        self.assertIn(".st-key-j4_theme_table { overflow-x: auto", blob)
        self.assertIn("min-width: 900px", blob)
        self.assertIn("flex-wrap: nowrap !important; min-width: 1180px", blob)
        # 11~20위를 담은 '더 보기'도 같은 규칙을 받아야 한다. 빠뜨렸더니 폰에서
        # 그 안만 칸이 세로로 쌓였다(2026-07-25).
        self.assertIn(".st-key-j4_theme_rest", blob)
        self.assertIn('.st-key-j4_theme_rest [data-testid="stHorizontalBlock"]', blob)
        # 필터 체크박스가 있어야 한다
        self.assertTrue(
            any("동반 순매수" in str(node.label) for node in app.checkbox),
            [str(node.label) for node in app.checkbox],
        )
