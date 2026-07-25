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
            # 게이지 그림은 지난 값까지 받아 그린다(2026-07-24).
            "fear_greed_detail": {
                "ok": True, "score": 41.0, "rating_kr": "공포", "previous_close": 45.0,
                "previous_1_week": 55.0, "previous_1_month": 57.0, "previous_1_year": 44.0,
                "stale": False,
            },
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
        patch("jarvis4_data.get_all_themes", return_value={
            "ok": True, "stale": False,
            "themes": {1: {"no": 1, "name": "반도체/HBM", "change_pct": 2.4},
                       2: {"no": 2, "name": "은행", "change_pct": -0.4}},
        }),
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
        # 시장 국면·미국 전일·공포탐욕 세 가지 모두 같은 게이지로 보여준다.
        for name in ("시장 국면", "미국 전일", "공포·탐욕 지수 (미국)"):
            self.assertIn(name, top_row)
        # 나란히 서면 구별이 안 되므로 제목 색이 서로 달라야 한다.
        for color in (gauge_ui.TITLE_GREEN, gauge_ui.TITLE_GREEN_DEEP, gauge_ui.TITLE_BLUE):
            self.assertIn(color, top_row)
        # <style>을 지표 줄 안에 넣으면 스트림릿이 그 덩어리를 HTML로 안 보고 글로
        # 흘려버려 CSS가 글자로 찍힌다(2026-07-24 실제 깨짐). 반드시 따로 내보낸다.
        self.assertNotIn("<style>", top_row)
        # 숫자가 두 군데 나오지 않게 '미국 전일' 부제에서는 뺐다.
        self.assertNotIn("공포탐욕 41", markdowns)

    def test_mobile_rules_are_emitted_and_scoped_to_phones(self):
        """폰 전용 규칙이 나가야 하고, 태블릿·PC가 바뀌면 안 된다(2026-07-24)."""
        app = _run_page()
        self.assertEqual(len(app.exception), 0)
        blocks = [str(n.value) for n in app.markdown if "@media (max-width: 600px)" in str(n.value)]
        self.assertEqual(len(blocks), 1, "폰 규칙 덩어리는 하나여야 한다")
        css = blocks[0]
        # 미디어쿼리 밖에 규칙이 새면 PC까지 바뀐다. 미디어쿼리는 둘이다 —
        # 메뉴는 태블릿까지(1200px), 표·글자는 폰만(600px).
        self.assertEqual(css.count("@media"), 2)
        self.assertEqual(css[: len("<style>")], "<style>")
        self.assertEqual(css[len("<style>"): css.index("@media")].strip(), "")
        phone_block = css[css.index("@media (max-width: 600px)"):]
        # 표 두 개와 머리글, 게이지 순서 규칙이 모두 들어 있어야 한다.
        # 눌림목 표(j4pbf_)는 세로로 쌓지 않고 옆으로 밀어 보므로 폰 규칙에 없다.
        for key in ("st-key-j4tbtn_", "j4-th-head", ".fg-box { order"):
            self.assertIn(key, phone_block)
        self.assertNotIn("stSidebarNav", phone_block)


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

    def test_pullback_click_adds_theme_and_selects_stock(self):
        """눌림목 종목을 누르면 그 테마가 목록에 추가되고 상세가 그 종목으로 바뀐다."""
        started = []
        try:
            for item in _patches():
                item.start()
                started.append(item)
            app = AppTest.from_file(str(PAGE), default_timeout=90)
            app.secrets["APP_PASSWORD"] = "test"
            app.session_state["authenticated"] = True
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
        self.assertIn("반도체/HBM", state.get("j4_forced_themes") or [])
        self.assertEqual(len(app.exception), 0)
        # 하나금융지주(086790)는 이 테마의 거래대금 상위 3위 대장주가 아니다.
        # 그래도 '상세 종목 선택'에 더해져 아래 상세가 그 종목으로 바뀌어야 한다
        # (2026-07-24 사용자 지적: 1순위를 눌러도 밑이 안 바뀐다).
        self.assertEqual(state.get("j4_stock_choice_반도체/HBM"), "086790")
        detail_markdowns = [
            str(node.value) for node in app.markdown
            if "<div class='j4-stock-name'>" in str(node.value)
        ]
        self.assertTrue(detail_markdowns, "종목 상세가 렌더되지 않았다")
        self.assertTrue(
            all("하나금융지주" in value for value in detail_markdowns),
            f"상세가 클릭한 종목으로 바뀌지 않았다: {detail_markdowns}",
        )
        radio_labels = [
            str(option)
            for node in app.radio if str(node.label) == "상세 종목 선택"
            for option in node.options
        ]
        self.assertTrue(any("086790" in label for label in radio_labels), radio_labels)

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
        # 5일: 숫자 3/5 와 점(글자가 아니라 CSS 동그라미 — 글꼴마다 크기가 달랐다)
        self.assertIn("3/5", blob)
        self.assertIn("border-radius:50%", blob)
        self.assertIn("#ff5b5b", blob)   # 동반 매수
        self.assertIn("#4da6ff", blob)   # 동반 매도
        self.assertIn("#ffb020", blob)   # 한쪽만
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
        self.assertIn(".st-key-j4_pullback_table { overflow-x: auto", blob)
        self.assertIn("flex-wrap: nowrap !important; min-width: 1180px", blob)
        # 필터 체크박스가 있어야 한다
        self.assertTrue(
            any("동반 순매수" in str(node.label) for node in app.checkbox),
            [str(node.label) for node in app.checkbox],
        )
