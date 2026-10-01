"""자비스10 · 한국증시 시험 (2026-09-30).

설명서: docs/JARVIS10_SPEC.md. 네트워크는 쓰지 않는다 — 받기는 모두 가짜 자료로 바꿔 끼운다.
"""
from __future__ import annotations

import re
import socket
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

import jarvis10_data as d
import jarvis10_ui as u

ROOT = Path(__file__).parent
PAGE = ROOT / "pages" / "9_자비스10.py"
PAGE_SOURCE = PAGE.read_text(encoding="utf-8")


def _rising(n: int = 3200, start: float = 1000.0, step: float = 0.0004) -> pd.Series:
    idx = pd.bdate_range("2012-01-02", periods=n)
    wiggle = np.sin(np.arange(n) / 17.0) * 0.004
    return pd.Series(start * np.exp(np.cumsum(step + wiggle - wiggle.mean())), index=idx)


class DataTests(unittest.TestCase):
    def test_long_hold_stats_counts_up_share_median_and_worst(self):
        c = _rising()
        out = d.long_hold_stats(c)
        years = [r["years"] for r in out["rows"]]
        self.assertEqual([1, 3, 5, 10], years)
        ten = out["rows"][-1]
        # 10년 뒤 값과 직접 셈이 같아야 한다(250거래일 = 1년).
        f = (c.shift(-2500) / c - 1).dropna() * 100
        self.assertAlmostEqual(ten["up"], float((f > 0).mean()))
        self.assertAlmostEqual(ten["median"], float(f.median()))
        self.assertAlmostEqual(ten["worst"], float(f.min()))
        self.assertEqual([5, 10], [x["years"] for x in out["dca"]])

    def test_timing_rules_are_the_five_rules_in_order(self):
        rules = d.timing_rules(_rising())["rules"]
        self.assertEqual(["그냥 들고 있기", "200일선 위만 · 달마다", "1년 전보다 높을 때만",
                          "200일선 ±3%", "200일선 위만 · 매일"], [r["name"] for r in rules])
        hold = rules[0]
        self.assertEqual(100.0, hold["held"])
        self.assertEqual(0, hold["switches"])

    def test_index_card_measures_high_drawdown_and_200_day_line(self):
        c = pd.Series([100.0] * 199 + [200.0, 150.0], index=pd.bdate_range("2025-01-01", periods=201))
        card = d.index_card(c)
        self.assertTrue(card["ok"])
        self.assertAlmostEqual(-25.0, card["dd_pct"])
        self.assertAlmostEqual(-25.0, card["change_pct"])
        self.assertAlmostEqual(c.iloc[-200:].mean(), card["sma200"])
        self.assertEqual(card["high_date"], c.index[-2].strftime("%Y-%m-%d"))

    def test_failed_fetch_keeps_the_last_good_value(self):
        """실패했다고 있던 값을 지우지 않는다(CLAUDE.md 0-0-2)."""
        key = ("test-keep",)
        d._CACHE.pop(key, None)
        self.assertEqual("old", d._cached(key, 0, lambda: "old"))

        def boom():
            raise RuntimeError("network down")
        self.assertEqual("old", d._cached(key, 0, boom))
        d._CACHE.pop(key, None)

    def test_kospi_history_falls_back_to_naver_when_yahoo_fails(self):
        naver = pd.DataFrame({"close": _rising(3000).to_numpy()}, index=_rising(3000).index)
        with patch.object(d, "naver_daily", return_value=naver), \
             patch.object(d, "yahoo_daily", side_effect=RuntimeError("blocked")):
            hist, source = d.kospi_close_history()
        self.assertEqual(3000, len(hist))
        self.assertIn("네이버 12년치", source)

    def test_refresh_forgets_only_live_values(self):
        d._CACHE[("naver", "KOSPI", 3000)] = (0, "x")
        d._CACHE[("yahoo", "^KS11", d.KOSPI_HISTORY_START)] = (0, "keep")
        d.forget_live()
        self.assertNotIn(("naver", "KOSPI", 3000), d._CACHE)
        self.assertIn(("yahoo", "^KS11", d.KOSPI_HISTORY_START), d._CACHE)
        d._CACHE.pop(("yahoo", "^KS11", d.KOSPI_HISTORY_START), None)

    def test_flow_is_two_named_stocks_not_the_whole_market(self):
        self.assertEqual(("005930", "000660"), tuple(c for c, _ in d.FLOW_STOCKS))

    def test_fetch_start_is_the_same_all_day(self):
        """받아 둔 자료의 이름표가 하루 동안 같아야 다시 쓴다(2026-10-01 — 1초마다 바뀌어 화면마다 새로 받았다)."""
        morning, night = 1_790_000_000 - 1_790_000_000 % 86400 + 60, 1_790_000_000 - 1_790_000_000 % 86400 + 86000
        with patch.object(d.time, "time", return_value=morning):
            a = d._days_ago(3650)
        with patch.object(d.time, "time", return_value=night):
            b = d._days_ago(3650)
        self.assertEqual(a, b)
        self.assertEqual(0, a % 86400)

    def test_thin_keeps_the_last_value_and_the_limit(self):
        pts = list(range(391))
        out = d._thin(pts)
        self.assertLessEqual(len(out), d.INTRADAY_POINTS + 1)
        self.assertEqual(390, out[-1])
        self.assertEqual(0, out[0])
        self.assertEqual([1, 2, 3], d._thin([1, 2, 3]))

    def test_kr_intraday_uses_the_given_previous_close_as_base(self):
        class _Resp:
            def raise_for_status(self):
                pass

            def json(self):
                return [{"currentPrice": 100.0 + i} for i in range(391)]

        class _Sess:
            def get(self, *a, **k):
                return _Resp()
        d._CACHE.pop(("naver_min", "KOSPI", "2026-09-30"), None)
        with patch.object(d, "_session", return_value=_Sess()):
            out = d.kr_intraday("KOSPI", "2026-09-30", 99.5)
        d._CACHE.pop(("naver_min", "KOSPI", "2026-09-30"), None)
        self.assertEqual(99.5, out["base"])
        self.assertEqual(490.0, out["points"][-1])       # 마지막 값(종가)은 솎아도 남는다

    def test_failed_intraday_leaves_the_card_with_six_months_only(self):
        card = d._with_intraday(d.index_card(_rising(300)), lambda: (_ for _ in ()).throw(RuntimeError("down")))
        self.assertTrue(card["ok"])
        self.assertNotIn("intraday", card)


def _panel_data():
    c = _rising()
    return {"ok": True, "card": d.index_card(c), "hold": d.long_hold_stats(c), "source": "1996년부터",
            "history_monthly": [float(v) for v in c.resample("ME").last()],
            "rules": d.timing_rules(c)}


class HtmlTests(unittest.TestCase):
    def test_words_are_precise_index_fund_or_single_stock(self):
        """상하님 지시 — 코스피 지수 · 코스피200 상품 · 개별 종목을 섞지 않는다."""
        html = u.kospi_panel_html(_panel_data(), "n1", "장 마감")
        for word in ("코스피 지수", "코스피200 상품", "개별 종목"):
            self.assertIn(word, html)
        self.assertNotIn("코스피를 오래", html)       # '코스피'만 쓰지 않는다 — 늘 '코스피 지수'
        sheet = u.help_sheet_html()
        # 설명 창의 사실 칸 제목마다 어느 쪽 이야기인지 붙는다.
        self.assertGreaterEqual(sheet.count("j10-tag-s"), 4)
        self.assertGreaterEqual(sheet.count("j10-tag-i"), 2)
        self.assertGreaterEqual(sheet.count("j10-tag-f"), 1)

    def test_no_buy_or_sell_instruction_on_screen(self):
        html = u.kospi_panel_html(_panel_data(), "n1", "장 마감") + u.help_sheet_html()
        for bad in ("사세요", "파세요", "매수하세요", "매도하세요", "지금 사기 좋은 때"):
            self.assertNotIn(bad, html)
        # 게이지 상자에서 따라오는 행동 문구는 감춘다.
        self.assertIn(".j10-regime .fg-box-foot{display:none!important}", u.page_css("n1"))

    def test_html_is_one_line_and_balanced(self):
        pieces = [u.kospi_panel_html(_panel_data(), "n1", "정규장"), u.help_sheet_html(), u.nav_html(),
                  u.banner_html([100, 200, 300], "정규장"), u.page_css("n1"),
                  u.market_panel_html({}, None, None, "n1")]
        for html in pieces:
            self.assertNotIn("\n", html)
            self.assertEqual(html.count("<div"), html.count("</div>"))

    def test_state_rules_follow_this_run_mark_and_hide_the_wrapper_too(self):
        css = u.page_css("abc123")
        self.assertIn('[data-j10p="market-abc123"] [data-testid="stLayoutWrapper"]:has(> .st-key-j10_page_kospi)', css)
        self.assertIn(':not([data-j10p="market-abc123"]) [data-testid="stLayoutWrapper"]:has(> .st-key-j10_page_market)', css)
        self.assertIn(':not([data-testid="stLayoutWrapper"]) > .st-key-j10_page_market', css)

    def test_hidden_panel_is_parked_not_removed(self):
        """안 보이는 판은 자리를 재 둔 채 숨긴다 — 없애 두면 처음 넘길 때 느린 폰이 멈췄다(2026-10-01)."""
        css = u.page_css("abc123")
        warm = 'html[data-j10warm="abc123"]:not([data-j10p="market-abc123"]) [data-testid="stLayoutWrapper"]:has(> .st-key-j10_page_market)'
        self.assertIn(warm, css)
        rule = css[css.index(warm):]
        rule = rule[:rule.index("}")]
        self.assertIn("visibility:hidden!important", rule)
        self.assertIn("height:0!important", rule)
        self.assertNotIn("display:none", rule)
        # 첫 화면을 그리기 전에는 빼 둔다 — 숨긴 판의 자리 재기가 첫 화면에 얹히지 않게.
        self.assertIn('html:not([data-j10warm="abc123"]):not([data-j10p="market-abc123"]) '
                      '[data-testid="stLayoutWrapper"]:has(> .st-key-j10_page_market)', css)
        self.assertIn("d.documentElement.setAttribute('data-j10warm', n);", u.SWIPE_JS)
        self.assertIn("function edgeCopy(face, rect, vh)", u.SWIPE_JS)

    def test_bottom_bar_sits_where_us_theme_puts_it(self):
        """아래 이동막대는 미국테마 자리 — 오른쪽 아래 스트림릿 표시(얼굴·왕관)를 피한다(2026-10-01 상하님)."""
        css = u.page_css("n1")
        self.assertIn("@media (max-width:600px){:root{--j10-nw:min(286.667px,66.667vw);--j10-nl:8px;--j10-nb:4px;--j10-nh:50px}}", css)
        self.assertIn("--j10-nl:calc(50% - var(--j10-nw) / 2 - 60px)", css)
        # 홈을 누르는 자리도 같은 숫자를 쓴다 — 막대만 옮기면 홈 자리가 엉뚱한 곳에 남는다.
        self.assertIn(".st-key-j10_home_link a{position:fixed!important;z-index:1001!important;bottom:var(--j10-nb)!important;"
                      "left:var(--j10-nl)!important;width:calc(var(--j10-nw) / 3)!important;height:var(--j10-nh)!important", css)
        j3 = (ROOT / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
        self.assertIn("width:min(286.667px,66.667vw)", j3)

    def test_index_card_taps_between_today_and_six_months(self):
        """지수 칸을 누르면 「당일」↔「6개월」 — 미국테마 지수 칸과 같은 장치(2026-10-01 상하님)."""
        card = d.index_card(_rising(300))
        card["intraday"] = {"points": [100, 103, 99, 101], "base": 100}
        html = u._idx_card("코스닥 지수", card, kr=True, sub="9월 30일", nonce="n1", key="kosdaq")
        self.assertIn("class='j10-tap'", html)
        self.assertIn("for='j10t-n1-kosdaq'", html)
        self.assertIn(">당일<", html)
        self.assertIn(">6개월<", html)
        self.assertEqual(html.count("<div"), html.count("</div>"))
        # 당일 자료를 못 받았으면 누를 것이 없다 — 누르면 빈칸이 되지 않게.
        del card["intraday"]
        plain = u._idx_card("코스닥 지수", card, kr=True, sub="9월 30일", nonce="n1", key="kosdaq")
        self.assertNotIn("j10-tap", plain)
        self.assertIn(">6개월<", plain)
        # 코스피 판 맨 위 칸도 같다.
        data = _panel_data()
        data["card"]["intraday"] = {"points": [1, 2, 3], "base": 2}
        self.assertIn("for='j10t-n1-hero'", u.kospi_panel_html(data, "n1", "정규장"))

    def test_line_colors_follow_the_base_line(self):
        """기준선 위는 오른 색, 아래는 내린 색 — 자비스3 선 그림과 같다."""
        svg = u.line_svg([1, 3, 3, 1, 1], 2, "#up", "#dn")
        self.assertIn("stroke='#up'", svg)
        self.assertIn("stroke='#dn'", svg)
        self.assertEqual("", u.line_svg([1], 2, "#up", "#dn"))

    def test_turn_does_not_count_as_a_tap(self):
        """넘기다 손을 뗀 직후의 누름은 지수 칸 누름으로 치지 않는다 — 넘기기 코드가 누르는 홈은 간다."""
        self.assertIn("if (ev.isTrusted && Date.now() < quietUntil)", u.SWIPE_JS)
        self.assertIn("var VER = 'j10-4';", u.SWIPE_JS)
        self.assertIn("j.ver==='j10-4'", u._inject_frame.__code__.co_consts.__repr__())

    def test_market_panel_is_sent_as_a_bundle_and_unpacked_later(self):
        """시장분석 판은 글자 꾸러미로 보내고 첫 화면 뒤에 펼친다 — 첫 화면을 늦추지 않게(2026-10-01)."""
        inner = u.market_panel_html({}, None, None, "n1")
        wrapped = u.deferred_html(inner)
        self.assertTrue(wrapped.startswith("<div hidden class='j10-defer' data-key='"))
        # 글 칸이 읽으면 칸은 딱 둘(꾸러미 · 펼칠 자리)이다 — 판 HTML 은 속성 안의 글자일 뿐이다.
        from html.parser import HTMLParser

        class _Count(HTMLParser):
            tags: list = []

            def handle_starttag(self, tag, attrs):
                self.tags.append(tag)
        counter = _Count()
        counter.tags = []
        counter.feed(wrapped)
        self.assertEqual(["div", "div"], counter.tags)
        import html as _h
        body = wrapped[wrapped.index('data-html="') + len('data-html="'):wrapped.index('"></div>')]
        self.assertNotIn('"', body)
        self.assertNotIn("&#x27;", body)                                  # ' 는 그대로 — 글자가 부풀지 않게
        self.assertEqual(inner, _h.unescape(body))                        # 펼치면 그대로 돌아온다
        self.assertLess(len(wrapped), len(inner) * 1.05 + 200)
        self.assertIn("j10ui.deferred_html(j10ui.help_sheet_html())", PAGE_SOURCE)
        self.assertNotEqual(u.deferred_html(inner)[:60], u.deferred_html(inner + " ")[:60])   # 바뀌면 다시 펼친다
        self.assertIn("j10ui.deferred_html(", PAGE_SOURCE)
        self.assertIn("if (to === 'market') { inflate(); }", u.SWIPE_JS)

    def test_page_turn_matches_jarvis3_shape(self):
        """넘기는 모양은 자비스3 과 같은 숫자(원근 1500 · 끝 0.3 · 더 말림 1.25 · 그늘 56)."""
        self.assertIn("var DEPTH = 1500, CURL = 0.3, BEND = 1.25, CAST = 56;", u.SWIPE_JS)
        j3 = (ROOT / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
        for line in ("var DEPTH = 1500;", "var CURL = 0.3;", "var BEND = 1.25;", "var CAST = 56;"):
            self.assertIn(line, j3)
        # 한국증시 화면이 없으면 아무것도 안 한다 — 다른 화면(자비스3)에서 손가락을 가로채지 않는다.
        self.assertIn("if (!api.alive || g || !ev.touches || ev.touches.length !== 1 || !onPage())", u.SWIPE_JS)


class PageSourceTests(unittest.TestCase):
    def test_guard_and_login_come_before_any_fetch(self):
        guard = PAGE_SOURCE.index('page_access.guard(st, "한국증시")')
        login = PAGE_SOURCE.index("_login_gate()\n")
        first_fetch = min(PAGE_SOURCE.index("j10data.kospi_panel()"), PAGE_SOURCE.index("j10data.market_cards_start()"))
        self.assertLess(guard, login)
        self.assertLess(login, first_fetch)

    def test_swipe_code_is_planted_before_waiting_for_the_market_panel(self):
        self.assertLess(PAGE_SOURCE.index("j10ui.inject_js(st)"), PAGE_SOURCE.index("market_cards_collect(_card_jobs)"))

    def test_bottom_bar_is_drawn_before_waiting_for_the_market_panel(self):
        """이동막대는 시장분석 자료를 기다리기 전에 그린다 — 예전엔 막대가 코스피 판보다 늦게 떴다(2026-10-01)."""
        wait = PAGE_SOURCE.index("market_cards_collect(_card_jobs)")
        self.assertLess(PAGE_SOURCE.index("j10ui.nav_html()"), wait)
        self.assertLess(PAGE_SOURCE.index('st.page_link("app.py", label="홈")'), wait)
        # 무거운 시장 국면 계산은 코스피 판·이동막대를 다 보낸 뒤에 시작한다(CLAUDE.md 0-0-1).
        self.assertLess(PAGE_SOURCE.index("j10ui.nav_html()"), PAGE_SOURCE.index("j10data.overview_start()"))

    def test_required_revisions_match_the_modules(self):
        data_req = int(re.search(r"_REQUIRED_J10_DATA_REVISION = (\d+)", PAGE_SOURCE).group(1))
        ui_req = int(re.search(r"_REQUIRED_J10_UI_REVISION = (\d+)", PAGE_SOURCE).group(1))
        self.assertEqual(d.MODULE_REVISION, data_req)
        self.assertEqual(u.MODULE_REVISION, ui_req)


class PageRunTests(unittest.TestCase):
    def test_page_runs_offline_without_exceptions(self):
        from streamlit.testing.v1 import AppTest

        cards = {"KOSDAQ": d.index_card(_rising()), "USDKRW": d.index_card(_rising(), with_high=False),
                 "FLOW": {"ok": False}}
        with patch.object(socket.socket, "connect", side_effect=AssertionError("external socket blocked")), \
             patch.object(d, "kospi_panel", return_value=_panel_data()), \
             patch.object(d, "market_cards_start", return_value={}), \
             patch.object(d, "market_cards_collect", return_value=cards), \
             patch("jarvis4_data.get_market_overview", return_value={"ok": False}):
            app = AppTest.from_file(str(PAGE), default_timeout=60)
            app.session_state["authenticated"] = True
            app.run()
        self.assertEqual(0, len(app.exception), [e.value for e in app.exception])
        text = " ".join(str(m.value) for m in app.markdown)
        self.assertIn("코스피 지수를 오래 들고 있었다면", text)
        self.assertIn("한국증시 설명", text)
        self.assertIn("j10_refresh", [b.key for b in app.button])
        self.assertIn("j10-nav", text)
        self.assertIn("j10-defer", text)       # 시장분석 판은 꾸러미로 간다(첫 화면 뒤에 펼침)


if __name__ == "__main__":
    unittest.main()
