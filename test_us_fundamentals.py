"""선택종목 세부사항 「📑 재무 한눈에」 (2026-10-07 상하님 지시) — 모으기·읽기·그림·화면 자리."""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

import us_fundamentals as fn

ROOT = Path(__file__).resolve().parent
PAGE = (ROOT / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "picklist_collect.yml").read_text(encoding="utf-8")


def _entry(**over):
    base = {"at": "2026-10-07", "name": "Test Co", "cur": "USD", "fx": 1.0, "px": 100.0,
            "mcap": 200_000.0, "pe": 20.0, "eps": 5.0, "roe": 0.25, "opm": 0.3, "div": 0.5,
            "eq": 50_000.0, "eq_at": "2026.06", "debt_ratio": 80.0, "cur_ratio": 1.5,
            "annual": [["2024.12", 900.0, 100.0, 80.0], ["2025.12", 1000.0, -50.0, -40.0]],
            "quarter": [["26.03", 250.0, 30.0, 20.0]]}
    base.update(over)
    return base


class ReadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "US.json"
        stocks = {"AAA": _entry(), "LOSS": _entry(eps=-1.0, pe=None),
                  "NEG": _entry(eq=-10.0, debt_ratio=None),
                  "KRW": _entry(cur="KRW", fx=0.00075)}
        self.path.write_text(json.dumps({"version": 1, "stocks": stocks}), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_price_moves_rescale_cap_per_pbr(self):
        info = fn.summary("aaa", 110.0, path=self.path)
        self.assertAlmostEqual(info["mcap"], 220_000.0)
        self.assertAlmostEqual(info["pe"], 22.0)
        self.assertAlmostEqual(info["pbr"], 220_000.0 / 50_000.0)
        self.assertTrue(info["rescaled"])
        plain = fn.summary("AAA", None, path=self.path)
        self.assertAlmostEqual(plain["pe"], 20.0)
        self.assertFalse(plain["rescaled"])

    def test_loss_and_negative_equity_are_named_not_hidden(self):
        loss = fn.summary("LOSS", 100.0, path=self.path)
        self.assertTrue(loss["loss"])
        self.assertIsNone(loss["pe"])
        neg = fn.summary("NEG", 100.0, path=self.path)
        self.assertTrue(neg["equity_bad"])
        self.assertIsNone(neg["pbr"])
        html = fn.card_html(loss) + fn.card_html(neg)
        self.assertIn("적자", html)
        self.assertIn("자본잠식", html)

    def test_unknown_ticker_is_none(self):
        self.assertIsNone(fn.summary("ZZZZ", 1.0, path=self.path))
        self.assertEqual(fn.load(Path(self.temp.name) / "missing.json"), {})

    def test_card_has_eight_cells_two_charts_and_currency_note(self):
        html = fn.card_html(fn.summary("KRW", 100.0, path=self.path))
        self.assertEqual(html.count("class='j3fn-cell'"), 8)
        self.assertEqual(html.count("class='j3fn-bars'"), 2)
        self.assertIn("장부는 원", html)
        self.assertIn("1,000원 = 0.75달러", html)
        # 적자 해의 영업이익은 빨강
        self.assertIn("#ff5b5b", html)
        for name in ("시가총액", "PER", "PBR", "ROE", "영업이익률", "배당", "부채비율", "유동비율"):
            self.assertIn(name, html)


class CollectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "US.json"
        stocks = {"OLD": _entry(at="2026-09-01"), "NEW": _entry(at="2099-01-01"), "KEEP": _entry(at="2026-09-02")}
        self.path.write_text(json.dumps({"version": 1, "stocks": stocks}), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_oldest_first_failures_keep_old_values(self):
        def fake(code, _cache):
            return None if code == "KEEP" else _entry(at="2026-10-07", name=f"fresh {code}")

        with mock.patch.object(fn, "fetch_one", side_effect=fake), mock.patch.object(fn.time, "sleep"):
            result = fn.collect(["NEW", "OLD", "KEEP", "ADD"], path=self.path, older_than_days=5, limit=2)
        data = json.loads(self.path.read_text(encoding="utf-8"))["stocks"]
        # 5일 넘은 것(ADD·OLD·KEEP) 중 가장 오래된 둘 — 파일에 없는 ADD, 그다음 OLD
        self.assertEqual(result["wanted"], 2)
        self.assertEqual(data["ADD"]["name"], "fresh ADD")
        self.assertEqual(data["OLD"]["name"], "fresh OLD")
        self.assertEqual(data["KEEP"]["at"], "2026-09-02")          # 손대지 않음
        self.assertEqual(data["NEW"]["at"], "2099-01-01")

    def test_nothing_to_refresh_does_not_touch_the_file(self):
        before = self.path.read_text(encoding="utf-8")
        result = fn.collect(["NEW"], path=self.path, older_than_days=5)
        self.assertEqual(result["wanted"], 0)
        self.assertEqual(self.path.read_text(encoding="utf-8"), before)

    def test_periods_are_old_to_new_converted_to_usd_millions(self):
        frame = pd.DataFrame(
            {pd.Timestamp("2025-12-31"): [2_000_000.0, 500_000.0, 400_000.0],
             pd.Timestamp("2024-12-31"): [1_000_000.0, -100_000.0, -50_000.0],
             pd.Timestamp("2021-12-31"): [float("nan"), float("nan"), float("nan")]},
            index=["Total Revenue", "Operating Income", "Net Income"])
        rows = fn._periods(frame, 2.0, 4, "%Y.%m")
        self.assertEqual([r[0] for r in rows], ["2024.12", "2025.12"])
        self.assertEqual(rows[1][1:], [4.0, 1.0, 0.8])


class ResultsCellTests(unittest.TestCase):
    """표 칸 「연간 실적」·「분기 실적」 (2026-10-07 상하님 지시)."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "US.json"
        stocks = {
            "UP": _entry(annual=[["2024.12", 900.0, 100.0, 80.0], ["2025.12", 1000.0, 250.0, 200.0]],
                         quarter=[["25.06", 200.0, 40.0, 30.0], ["25.09", 210.0, 40.0, 30.0],
                                  ["25.12", 220.0, 40.0, 30.0], ["26.03", 230.0, 40.0, 30.0],
                                  ["26.06", 250.0, 50.0, 40.0]]),
            "LOSS": _entry(annual=[["2024.12", 500.0, -10.0, -5.0], ["2025.12", 300.0, -90.0, -80.0]],
                           quarter=[["25.06", 80.0, -20.0, -10.0], ["26.06", 60.0, -30.0, -20.0]]),
            "OLD": _entry(quarter=[["25.03", 100.0, 10.0, 5.0], ["26.03", 110.0, 12.0, 6.0]]),
            "JUL": _entry(quarter=[["25.07", 100.0, 10.0, 5.0], ["26.07", 110.0, 12.0, 6.0]]),
            "UP2": _entry(quarter=[["25.06", 100.0, 10.0, 5.0], ["26.06", 110.0, 12.0, 6.0]]),
        }
        self.path.write_text(json.dumps({"version": 1, "stocks": stocks}), encoding="utf-8")
        self._patch = mock.patch.object(fn, "DATA_PATH", self.path)
        self._patch.start()
        fn._LOADED.update(mtime=None, data=None)

    def tearDown(self):
        self._patch.stop()
        fn._LOADED.update(mtime=None, data=None)
        self.temp.cleanup()

    def test_growth_and_margin(self):
        with mock.patch.object(fn, "load", lambda path=self.path: fn._read_file(self.path)["stocks"]):
            cells = fn.results_cells(["UP", "LOSS", "OLD", "JUL", "UP2", "NONE"])
        annual, quarter = cells["UP"]
        self.assertIn("매출 +11.1%", annual)                       # 1000/900
        self.assertIn("이익률 25%", annual)
        self.assertIn("매출 +25.0%", quarter)                      # 26.06 250 ÷ 25.06 200
        self.assertIn("이익률 20%", quarter)
        self.assertIn("영업적자", cells["LOSS"][0])
        self.assertIn("매출 -40.0%", cells["LOSS"][0])
        # 다른 종목들(26.06)보다 오래된 분기만 달을 붙인다
        self.assertIn("(26.03)", cells["OLD"][1])
        self.assertNotIn("(26.06)", quarter)
        self.assertNotIn("(26.07)", cells["JUL"][1])                # 결산 달이 다를 뿐 — 오래된 것이 아니다
        self.assertEqual(cells["NONE"], ("<span class='j3-muted'>—</span>",) * 2)
        self.assertIn("<svg", annual)

    def test_same_quarter_only(self):
        rows = [["25.09", 1.0, 1.0, 1.0], ["26.06", 2.0, 1.0, 1.0]]
        self.assertIsNone(fn._same_quarter_last_year(rows))     # 1년 전 같은 분기가 없으면 견주지 않는다


class WiringTests(unittest.TestCase):
    def test_every_detail_view_gets_the_box_right_under_daily_prices(self):
        calls = re.findall(r"_render_day_price_row\(metrics, ticker, panel=panel\)\n\s+"
                           r"_render_fundamentals_box\(ticker, metrics, panel=panel\)", PAGE)
        self.assertEqual(len(calls), 4)

    def test_box_reads_the_file_and_never_downloads(self):
        body = PAGE[PAGE.index("def _render_fundamentals_box("):PAGE.index("def _render_day_price_row(")]
        self.assertIn("us_fundamentals.summary(ticker, price)", body)
        self.assertIn("_list_price_change(", body)
        for banned in ("yf.", "yfinance", "_download_cached", "fetch_one", "collect("):
            self.assertNotIn(banned, body)
        # 숨은 스위치로 여닫는다 — 차트 큰 창 복사 장치(j3cz-t숫자)와 겹치지 않는 이름
        self.assertIn("class='j3cz-tap j3fn-tap'", body)
        self.assertNotRegex(body, r"j3cz-t\d")

    def test_workflow_collects_only_with_a_new_list_and_ships_in_the_same_commit(self):
        self.assertIn("python us_fundamentals.py --max 60 --older-than-days 5", WORKFLOW)
        self.assertIn('git status --porcelain data/picklist', WORKFLOW)
        upload = WORKFLOW[WORKFLOW.index("- name: 저장소에 올리기"):]
        self.assertLess(upload.index("git add data/picklist"), upload.index("git add data/fundamentals"))
        self.assertLess(upload.index("if ! git diff --cached --quiet; then"), upload.index("git add data/fundamentals"))
        step = WORKFLOW[WORKFLOW.index("- name: 미국 재무 모으기"):WORKFLOW.index("- name: 저장소에 올리기")]
        self.assertIn("continue-on-error: true", step)

    def test_data_file_covers_the_roster(self):
        import jarvis3_data

        data = json.loads((ROOT / "data" / "fundamentals" / "US.json").read_text(encoding="utf-8"))
        missing = set(jarvis3_data.US_LARGE_CAP_UNIVERSE) - set(data["stocks"])
        self.assertEqual(missing, set())

    def test_three_tables_get_the_results_columns(self):
        leader = PAGE[PAGE.index("def _render_leader_table("):PAGE.index("def _leader_table_html(")]
        swing = PAGE[PAGE.index("def _render_us_swing_finder("):PAGE.index("def _render_rulebook_finder(")]
        crash = PAGE[PAGE.index("def _render_rulebook_finder("):PAGE.index("def _rerun_here(")]
        top9 = PAGE[PAGE.index("def _render_top7_section("):PAGE.index("def _render_top7_close_above_search(")]
        self.assertIn("us_fundamentals.results_cells(", top9)
        self.assertIn('["연간 실적", "분기 실적"]', top9)
        self.assertIn("cols[7].markdown(_stacked(fund_cells)", top9)
        for block in (leader, swing, crash):
            self.assertIn("us_fundamentals.results_cells(", block)
            self.assertIn('"연간 실적", "분기 실적"', block)
            self.assertIn("us_fundamentals.RESULTS_CSS", block)
        # 상승장·급락은 「티커」 칸을 뺐다 · 급락은 「1년 성적」도
        self.assertNotIn('heads = ["티커"', swing)
        self.assertNotIn('["티커", "당일주가"]', crash)
        self.assertNotIn('"1년 성적"', crash)
        self.assertNotIn("hold_cell", crash)
        # 테마 종목 표는 칸을 다 둔다
        self.assertIn('"매수 상태", "연간 실적", "분기 실적"', leader)

    def test_module_revision_guard(self):
        match = re.search(r"_REQUIRED_US_FUNDAMENTALS_REVISION = (\d+)", PAGE)
        self.assertEqual(int(match.group(1)), fn.MODULE_REVISION)

    def test_no_secrets_in_module(self):
        source = (ROOT / "us_fundamentals.py").read_text(encoding="utf-8").lower()
        for word in ("api_key", "apikey", "token=", "password", "secret"):
            self.assertNotIn(word, source)



class OverviewTests(unittest.TestCase):
    """세부사항 「🏢 종목 개요」 (2026-10-09 상하님 지시 — 가안 1 · 제가 쓴 두 줄)."""

    def test_every_roster_stock_has_two_plain_lines(self):
        import jarvis3_data

        about = json.loads(fn.ABOUT_PATH.read_text(encoding="utf-8"))["stocks"]
        roster = list(jarvis3_data.US_LARGE_CAP_UNIVERSE)
        self.assertEqual(sorted(about), sorted(roster), "명부에 종목이 늘면 US_about.json 에 한 줄을 써 넣는다")
        for code, row in about.items():
            text = row["about"]
            self.assertTrue(text.endswith("."), code)
            self.assertLessEqual(text.count("."), 3, code)                # 두 줄 남짓
            self.assertLessEqual(len(text), 120, code)
            self.assertTrue(row["ko"], code)
            if row.get("listed"):
                self.assertRegex(row["listed"], r"^(19[89]\d|20\d\d)\.\d\d$", code)

    def test_card_reads_files_only(self):
        about = {"stocks": {"AAA": {"ko": "에이", "en": "Aaa", "exch": "나스닥", "ind": "반도체", "listed": "2018.12",
                                    "naver": "AAA.O", "about": "칩을 만드는 회사입니다."}}}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "US_about.json"
            path.write_text(json.dumps(about, ensure_ascii=False), encoding="utf-8")
            entry = _entry()
            entry["co"] = {"state": "MA", "country": "United States", "emp": 4700, "ceo": "Stéphane Bancel"}
            with mock.patch.object(fn, "ABOUT_PATH", path), \
                    mock.patch.object(fn, "_ABOUT_LOADED", {"mtime": None, "data": None}), \
                    mock.patch.object(fn, "load", return_value={"AAA": entry}):
                card = fn.overview_html("aaa", ["반도체", "AI·데이터센터"])
                empty = fn.overview_html("ZZZ", ["반도체"])
        self.assertIn("🏢 에이", card)
        self.assertIn("Aaa · 나스닥 · 2018년 12월 상장", card)
        self.assertIn("앱 테마 · 반도체", card)
        self.assertIn("앱 테마 · AI·데이터센터", card)
        self.assertIn("업종 · 반도체", card)
        self.assertIn("본사 미국 매사추세츠 · 직원 4,700명 · 최고경영자 Stéphane Bancel", card)
        self.assertIn("https://m.stock.naver.com/worldstock/stock/AAA.O/overview", card)
        self.assertEqual(empty, "")                                     # 명부 밖 종목은 카드 없음

    def test_company_facts_and_names(self):
        info = {"companyOfficers": [{"name": "Dr. Stephen  Hoge M.D.", "title": "President"},
                                    {"name": "Mr. Stéphane  Bancel M.B.A.", "title": "CEO & Director"}],
                "state": "MA", "country": "United States", "fullTimeEmployees": 4700}
        self.assertEqual(fn.company_facts(info), {"state": "MA", "country": "United States", "emp": 4700,
                                                  "ceo": "Stéphane Bancel"})
        self.assertIsNone(fn.company_facts({})["ceo"])
        for raw, clean in (("Mr. Leigh Robert Curyer ACA, BA (Acc)", "Leigh Robert Curyer"),
                           ("Brig.Gen. Nadav Zafrir", "Nadav Zafrir"), ("Mr. John C. May II", "John C. May II"),
                           ("Mr. Earl C. Austin Jr.", "Earl C. Austin Jr."), ("Mr. Gen Smith", "Gen Smith"),
                           ("Dr. Albert  Bourla D.V.M., Ph.D.", "Albert Bourla")):
            self.assertEqual(fn._person(raw), clean)

    def test_page_puts_the_card_under_the_green_line_and_fixes_two_words(self):
        self.assertEqual(PAGE.count("+ _overview_html(ticker, metrics),"), 2)  # 테마·순위 9·종목검색 / 상승장·급락
        body = PAGE[PAGE.index("def _render_stock_detail("):PAGE.index("if auth.is_guest():", PAGE.index("def _render_stock_detail("))]
        self.assertIn("_detail_sub_text(theme_row, leader, plan))}</div>\"\n        + _overview_html(ticker, metrics)", body)
        self.assertIn("종목검색으로 찾은 종목", PAGE)
        self.assertIn("'급락 후 반등장 선택 종목' if mode == 'crash' else '눌림목 선택 종목'", PAGE)
        # 옛 줄(「내 종목 대장주 1위」가 나오던 것)은 _detail_sub_text 한 곳으로 모였다.
        self.assertNotIn("{theme_row['name']} 대장주 {leader['rank']}위 · {plan.get('recommendation')}</div>", PAGE)
        self.assertEqual(PAGE.count("_detail_sub_text(theme_row, leader, plan)"), 2)



class _FakeHandle:
    """야후 Ticker 흉내 — street_facts 가 읽는 넷만."""

    def __init__(self):
        import datetime as dt

        self.calendar = {"Earnings Date": [dt.date(2026, 11, 18)], "Earnings Average": 2.47,
                         "Ex-Dividend Date": dt.date(2026, 9, 10), "Dividend Date": dt.date(2026, 10, 1)}
        self.earnings_history = pd.DataFrame(
            {"epsActual": [1.30, 1.62, 1.87, 2.22, -0.5], "epsEstimate": [1.256, 1.538, 1.772, 2.091, -0.4],
             "surprisePercent": [0.035, 0.053, 0.055, 0.062, -0.25]},
            index=pd.to_datetime(["2025-07-31", "2025-10-31", "2026-01-31", "2026-04-30", "2026-07-31"]))
        self.recommendations = pd.DataFrame({"period": ["0m", "-1m"], "strongBuy": [10, 9], "buy": [48, 47],
                                             "hold": [2, 3], "sell": [1, 1], "strongSell": [0, 0]})
        today = pd.Timestamp.now().normalize()
        self.insider_transactions = pd.DataFrame({
            "Text": ["Sale at price 144.13 - 146.07 per share.", "Conversion of Exercise of derivative security",
                     "Purchase at price 10.00 per share.", "Sale at price 99 per share."],
            "Value": [11_691_420.0, 1_866_970.0, 500_000.0, 9_000_000.0],
            "Start Date": [today - pd.Timedelta(days=20), today - pd.Timedelta(days=20),
                           today - pd.Timedelta(days=40), today - pd.Timedelta(days=400)]})


class StreetTests(unittest.TestCase):
    """증권사 화면에 있는 것 — 실적 발표·애널리스트·공매도/내부자/배당·다가오는 일정 (2026-10-09 상하님 지시)."""

    INFO = {"earningsTimestampStart": 1794945600, "isEarningsDateEstimate": False,       # 2026-11-17 15:00 뉴욕
            "numberOfAnalystOpinions": 59, "targetMeanPrice": 328.7, "targetHighPrice": 515.0,
            "targetLowPrice": 180.0, "recommendationKey": "strong_buy", "shortPercentOfFloat": 0.0127,
            "heldPercentInstitutions": 0.714, "heldPercentInsiders": 0.04, "dividendYield": 0.02}

    def test_collect_reads_new_york_date_and_counts_only_market_trades(self):
        with mock.patch.object(fn.time, "time", return_value=1794945600 - 86400 * 30):
            facts = fn.street_facts(_FakeHandle(), dict(self.INFO))
        earn = facts["earn"]
        self.assertEqual(earn["next"], "2026-11-17")             # calendar 의 11/18(한국 시계)이 아니라 뉴욕 날짜
        self.assertEqual(earn["when"], "장 마감 뒤")               # 15:00 으로 적힌 마감 뒤 발표
        self.assertEqual(len(earn["hist"]), 4)
        self.assertEqual(earn["hist"][-1][1:], [-0.5, -0.4, -25.0])
        self.assertEqual(facts["ana"]["buy"], 58)
        self.assertEqual((facts["ana"]["hold"], facts["ana"]["sell"]), (2, 1))
        self.assertEqual(facts["own"]["short"], 1.27)
        self.assertEqual(facts["own"]["ins6m"], [1, 0.5, 1, 11.69])      # 6개월 안 · 시장 매매만(옵션 행사 뺌)
        self.assertEqual(facts["divd"], {"ex": "2026-09-10", "pay": "2026-10-01"})
        self.assertNotIn("div", facts)                            # "div" 는 배당수익률 자리다

    def test_old_earnings_timestamp_falls_back_to_calendar(self):
        info = dict(self.INFO, earningsTimestampStart=1785355200)          # 지난 발표일(7/29)이 남은 종목
        facts = fn.street_facts(_FakeHandle(), info)
        self.assertEqual(facts["earn"]["next"], "2026-11-18")
        self.assertNotIn("when", facts["earn"])

    def test_screen_boxes_and_chips_read_the_file_only(self):
        import datetime as dt

        entry = _entry()
        entry.update({"earn": {"next": "2026-11-17", "when": "장 마감 뒤", "eps_est": 2.47,
                               "hist": [["25.10", 1.3, 1.256, 3.5], ["26.01", 1.62, 1.538, 5.3],
                                        ["26.04", 1.87, 1.772, 5.5], ["26.07", 2.22, 2.091, 6.2]]},
                      "ana": {"n": 59, "mean": 328.7, "hi": 515.0, "lo": 180.0, "buy": 58, "hold": 2, "sell": 1},
                      "own": {"short": 1.27, "inst": 71.4, "ins6m": [0, 0.0, 9, 1370.53]},
                      "divd": {"ex": "2026-09-10", "pay": "2026-10-01"}})
        with mock.patch.object(fn, "load", return_value={"NVDA": entry}):
            html_text = fn.street_html("NVDA", 230.48, today=dt.date(2026, 10, 9))
            near = fn.earnings_chip_css([("j3lbtn_00", "NVDA")], today=dt.date(2026, 11, 12))
            far = fn.earnings_chip_css([("j3lbtn_00", "NVDA")], today=dt.date(2026, 10, 9))
            gone = fn.earnings_days("NVDA", today=dt.date(2026, 11, 20))
        self.assertIn("11월 17일(화) 장 마감 뒤", html_text)
        self.assertIn("39일 남음", html_text)
        self.assertIn("좋았음 4번 중 4번", html_text)
        self.assertIn("사라 58명", html_text)
        self.assertIn("59명 · 1년 뒤 예상", html_text)
        self.assertIn("지금보다 +43%", html_text)
        self.assertIn("점수·판정에는 들어가지 않습니다", html_text)
        self.assertIn("유통 주식의 1.3%", html_text)
        self.assertIn("판 것 9번(13.7억 달러)", html_text)
        self.assertIn("배당락 9월 10일 · 지급 10월 1일", html_text)
        self.assertIn("content:'실적 D-5'", near)
        self.assertEqual(far, "")                                  # 39일 남은 종목은 딱지 없음
        self.assertIsNone(gone)                                    # 지난 날짜는 모른다로 친다

    def test_upcoming_lists_macro_and_roster_earnings(self):
        import datetime as dt

        macro = {"known_until": {"cpi": "2026-12-10", "jobs": "2026-12-04"},
                 "events": [{"date": "2026-10-14", "kind": "cpi", "label": "소비자물가(CPI) 발표"},
                            {"date": "2026-10-28", "kind": "fomc", "label": "미국 금리 결정(FOMC)"},
                            {"date": "2026-11-30", "kind": "fomc", "label": "먼 일정"}]}           # 52일 뒤
        stocks = {code: dict(_entry(), earn={"next": day, "when": "장 전"}) for code, day in
                  (("JPM", "2026-10-13"), ("GS", "2026-10-13"), ("MSFT", "2026-10-28"), ("NVDA", "2026-11-17"))}
        about = {"JPM": {"ko": "JP모건"}, "GS": {"ko": "골드만삭스"}, "MSFT": {"ko": "마이크로소프트"}}
        with mock.patch.object(fn, "load_macro", return_value=macro), \
                mock.patch.object(fn, "load", return_value=stocks), \
                mock.patch.object(fn, "load_about", return_value=about):
            text = fn.upcoming_html(today=dt.date(2026, 10, 9))
        self.assertIn("10/13(화)", text)
        self.assertIn("JP모건·골드만삭스 실적", text)
        self.assertIn("소비자물가(CPI) 발표", text)
        self.assertIn("j3up-fomc", text)
        self.assertIn("미국 금리 결정(FOMC)", text)                  # 19일 뒤 — 큰 발표는 한 달 안이면 보인다
        self.assertNotIn("먼 일정", text)                           # 52일 뒤
        self.assertNotIn("NVDA", text.split("title=")[0])           # 11/17 은 14일 밖

    def test_macro_file_has_the_official_dates(self):
        data = json.loads(fn.MACRO_PATH.read_text(encoding="utf-8"))
        days = {(e["date"], e["kind"]) for e in data["events"]}
        for item in (("2026-10-28", "fomc"), ("2026-12-09", "fomc"), ("2027-01-27", "fomc"),
                     ("2026-10-14", "cpi"), ("2026-11-10", "cpi"), ("2026-11-06", "jobs"), ("2026-12-04", "jobs")):
            self.assertIn(item, days)
        self.assertEqual(data["known_until"]["cpi"], "2026-12-10")

    def test_page_wires_all_five(self):
        self.assertEqual(PAGE.count("_earnings_chips("), 5)          # 정의 1 + 네 표
        self.assertIn("_earnings_chips(button_keys) + \"</style>\"", PAGE)
        self.assertIn("[(f\"j3rbf_{index:02d}\", row.get(\"ticker\")) for index, row in enumerate(rows)]", PAGE)
        self.assertIn("[(f\"j3top7_{index:02d}\", row.get(\"ticker\")) for _label, index, row in labels]", PAGE)
        self.assertIn("*_us_index_cells(overview, phase),\n", PAGE)
        self.assertIn("        _usd_krw_cell(),\n", PAGE)
        self.assertIn("    _start_us_futures_fetch()\n", PAGE)
        self.assertIn("    _start_us_fx_fetch()\n", PAGE)
        self.assertEqual(PAGE.count("_render_stock_news_box(ticker, panel=panel)"), 4)
        self.assertEqual(PAGE.count("_krw_sub(shown_price)"), 3)
        self.assertIn("us_fundamentals.upcoming_html()", PAGE)
        self.assertIn('"j3_news_open_")', PAGE)


if __name__ == "__main__":
    unittest.main()
