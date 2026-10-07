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


if __name__ == "__main__":
    unittest.main()
