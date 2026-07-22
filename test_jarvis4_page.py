"""자비스4 페이지 렌더 테스트 — 네트워크 없이 화면 골격과 계약을 검증한다."""

import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
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
        },
        "foreign": {"ok": True, "net5_amount": 2.41e11, "detail": "삼성전자 5일 +1,200억"},
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


def _trades():
    return [{
        "id": 1, "buy_date": "2026-07-20", "code": "000660", "stock_name": "SK하이닉스",
        "theme_name": "반도체/HBM", "trade_style": "단타", "buy_price": 1_950_000,
        "quantity": 1.0, "status": "보유", "sell_date": None, "sell_price": None,
        "result_pct": None, "market_regime": "중립·선별", "market_score": 60,
        "theme_score": 85, "stock_score": 88, "memo": None,
    }]


def _patches():
    return (
        patch("jarvis4_data.get_market_overview", return_value=_market()),
        patch("jarvis4_data.get_theme_rankings", return_value=_ranking()),
        patch("jarvis4_data.get_theme_leaders", return_value=_leaders()),
        patch("jarvis4_data.get_chart_bundle", return_value=_chart_bundle()),
        patch("jarvis4_data.get_live_quote", return_value={"ok": True, "current": 1_990_000}),
        patch("jarvis4_data.get_intraday_chart", return_value=None),
        patch("jarvis4_data.get_us_futures_live", return_value={
            "ok": True, "stale": False, "values": {
                "NQ=F": {"label": "나스닥100 선물", "current": 29_207.25, "change_pct": 0.53},
                "ES=F": {"label": "S&P500 선물", "current": 7_536.75, "change_pct": 0.30},
            },
        }),
        patch("market_signal_ui.collect_kr_flow_snapshot", return_value=({}, [])),
        patch("database.save_kr_flow_snapshot"),
        patch("database.list_kr_flow_snapshots", return_value=[{}]),
        patch("jarvis4_store.ensure_tables"),
        patch("jarvis4_store.trade_progress", return_value={
            "total_count": 1, "open_count": 1, "closed_count": 0, "minimum_sample": 30,
        }),
        patch("jarvis4_store.list_trades", return_value=_trades()),
    )


def _run_page():
    started = []
    try:
        for item in _patches():
            item.start()
            started.append(item)
        app = AppTest.from_file(str(PAGE), default_timeout=90)
        app.secrets["APP_PASSWORD"] = "test"
        app.session_state["authenticated"] = True
        app.run(timeout=90)
        return app
    finally:
        for item in reversed(started):
            item.stop()


class Jarvis4PageTests(unittest.TestCase):
    def test_page_renders_market_then_flow_then_tabs(self):
        app = _run_page()
        self.assertEqual(len(app.exception), 0)
        subheaders = [str(node.value) for node in app.subheader]
        self.assertIn("한국 전체시장 판단", subheaders)
        markdowns = " ".join(str(node.value) for node in app.markdown)
        # 시장판단의 한국장 기관 수급 반전 카드를 그대로 가져왔는지
        self.assertIn("한국장 기관 수급 반전 포착", markdowns)
        # 동적 테마 선정 문구와 테마표
        self.assertIn("오늘의 강한 테마 20", markdowns)
        self.assertIn("자동 탈락", markdowns)
        # 종목 상세와 한국형 6개 항목
        self.assertIn("SK하이닉스", markdowns)
        self.assertIn("수급(외국인+기관)", markdowns)
        self.assertIn("j4-stock-name", markdowns)

    def test_theme_selection_switches_theme(self):
        started = []
        try:
            for item in _patches():
                item.start()
                started.append(item)
            app = AppTest.from_file(str(PAGE), default_timeout=90)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
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
        self.assertIn("round_to_tick", source)
        self.assertIn("j4tbtn_{index:02d}", source)
        # 자비스3 모듈을 건드리지 않는다
        self.assertNotIn("jarvis3_store", source)
        self.assertNotIn("import jarvis3_data", source)

    def test_login_page_offers_jarvis4(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("한국테마 (자비스4)", source)
        self.assertIn('st.switch_page("pages/3_자비스4.py")', source)

    def test_sidebar_has_five_ordered_items_everywhere(self):
        """페이지마다 사이드바 순서·이름 규칙이 같아야 한다(5번째=한국테마)."""
        for name in ("app.py", "pages/0_시장판단.py", "pages/1_자비스2.py",
                     "pages/2_자비스3.py", "pages/3_자비스4.py"):
            source = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn('li:nth-child(5) { order: 5; }', source, f"{name}에 5번째 순서 규칙 없음")
            self.assertIn('content: "한국테마"', source, f"{name}에 한국테마 라벨 없음")


if __name__ == "__main__":
    unittest.main()
