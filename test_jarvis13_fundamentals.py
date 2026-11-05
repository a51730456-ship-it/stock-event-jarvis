"""자비스13 「📑 재무 한눈에」 — 한국 재무(네이버 모바일 재무 JSON) 읽기·셈·그리기 (2026-11-03)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import jarvis13_fundamentals as fn


def _finance(keys, rows, consensus=()):
    """네이버 모바일 재무와 같은 짜임 — trTitleList(머리) · rowList(줄마다 칸 사전, 차례 뒤섞임)."""
    heads = [{"isConsensus": "Y" if k in consensus else "N", "title": f"{k[:4]}.{k[4:]}.", "key": k} for k in keys]
    row_list = [{"title": title, "columns": {k: {"value": v, "cx": None} for k, v in reversed(list(zip(keys, values)))}}
                for title, values in rows.items()]
    return {"financeInfo": {"trTitleList": heads, "rowList": row_list}}


ANNUAL = _finance(["202312", "202412", "202512", "202612"], {
    "매출액": ["2,589,355", "3,008,709", "3,336,059", "7,219,632"],
    "영업이익": ["65,670", "327,260", "436,011", "3,830,004"],
    "당기순이익": ["154,871", "344,514", "452,068", "3,090,231"],
    "영업이익률": ["2.54", "10.88", "13.07", "53.0"],
    "ROE": ["4.15", "9.03", "10.85", "40.0"],
    "부채비율": ["25.36", "27.93", "29.94", ""],
    "당좌비율": ["189.46", "187.80", "183.27", ""],
    "EPS": ["2,131", "4,950", "6,564", "45,000"],
    "BPS": ["52,002", "57,930", "63,997", "90,000"],
    "주당배당금": ["1,444", "1,446", "1,668", "2,000"],
}, consensus=("202612",))
QUARTER = _finance(["202506", "202509", "202512", "202603", "202606", "202609"], {
    "매출액": ["745,663", "860,617", "938,374", "1,338,734", "1,714,995", "2,007,657"],
    "영업이익": ["46,761", "121,661", "200,737", "500,000", "894,924", "1,069,435"],
    "당기순이익": ["50,990", "122,257", "190,000", "450,000", "800,000", "900,000"],
    "부채비율": ["26.40", "26.64", "29.94", "28.00", "27.50", ""],
    "당좌비율": ["195.0", "204.62", "183.27", "190.0", "199.0", ""],
}, consensus=("202609",))


class ParseTests(unittest.TestCase):
    def test_estimates_are_left_out_and_order_is_by_month(self):
        rows, latest, at = fn.parse_finance(ANNUAL, "annual")
        self.assertEqual(["23.12", "24.12", "25.12"], [row[0] for row in rows])
        self.assertEqual([3336059.0, 436011.0, 452068.0], rows[-1][1:])
        self.assertEqual("2025.12", at)
        self.assertEqual(6564.0, latest["eps"])
        q_rows, q_latest, _ = fn.parse_finance(QUARTER, "quarter")
        self.assertEqual(["25.06", "25.09", "25.12", "26.03", "26.06"], [row[0] for row in q_rows])
        self.assertEqual(27.5, q_latest["debt"])

    def test_money_text(self):
        self.assertEqual(12978739.0, fn._won_text("1,297조 8,739억"))
        self.assertEqual(4078.0, fn._won_text("4,078억"))
        self.assertIsNone(fn._won_text(""))

    def test_fetch_one_puts_it_together(self):
        whole = {"stockName": "삼성전자", "totalInfos": [{"code": "marketValue", "value": "1,297조 8,739억"},
                                                       {"code": "highPriceOf52Weeks", "value": "380,000"},
                                                       {"code": "lowPriceOf52Weeks", "value": "93,500"},
                                                       {"code": "foreignRate", "value": "46.16%"}]}
        answers = {"finance/annual": ANNUAL, "finance/quarter": QUARTER, "integration": whole,
                   "basic": {"closePrice": "222,000"}}

        class Resp:
            def __init__(self, data):
                self.status_code, self._data = (200, data) if data is not None else (404, None)

            def json(self):
                return self._data

        class Session:
            def get(self, url, **_kw):
                return Resp(next((v for k, v in answers.items() if url.endswith(k)), None))

        out = fn.fetch_one("005930", Session())
        self.assertEqual("삼성전자", out["name"])
        self.assertEqual(12978739.0, out["mcap"])
        self.assertEqual(222000.0, out["px"])
        self.assertEqual(380000.0, out["hi52"])
        self.assertEqual(46.16, out["foreign"])
        self.assertEqual(27.5, out["latest_q"]["debt"])

    def test_nothing_from_naver_gives_none(self):
        class Session:
            def get(self, url, **_kw):
                class R:
                    status_code = 500
                return R()

        self.assertIsNone(fn.fetch_one("999999", Session()))


def _entry():
    a_rows, a_latest, a_at = fn.parse_finance(ANNUAL, "annual")
    q_rows, q_latest, _ = fn.parse_finance(QUARTER, "quarter")
    return {"annual": a_rows, "quarter": q_rows, "latest": a_latest, "latest_at": a_at,
            "latest_q": {"debt": q_latest["debt"], "quick": q_latest["quick"]},
            "name": "삼성전자", "mcap": 12978739.0, "px": 222000.0, "at": "2026-11-07"}


def _file(entry):
    path = Path(tempfile.mkdtemp()) / "KR.json"
    path.write_text(json.dumps({"stocks": {"005930": entry}}, ensure_ascii=False), encoding="utf-8")
    return path


class SummaryTests(unittest.TestCase):
    def test_values_are_recounted_with_the_price_now(self):
        info = fn.summary("005930", 244200, path=_file(_entry()))
        self.assertAlmostEqual(244200 / 6564, info["per"])
        self.assertAlmostEqual(244200 / 63997, info["pbr"])
        self.assertAlmostEqual(1668 / 244200 * 100, info["dy"])
        self.assertAlmostEqual(12978739.0 * 1.1, info["mcap"])
        self.assertEqual(27.5, info["debt"])                         # 분기 쪽이 더 새로움
        self.assertTrue(info["rescaled"])

    def test_loss_and_missing_values_stay_blank(self):
        entry = _entry()
        entry["latest"] = dict(entry["latest"], eps=-1000.0, dps=None)
        info = fn.summary("005930", path=_file(entry))
        self.assertTrue(info["loss"])
        self.assertIsNone(info["per"])
        self.assertIsNone(info["dy"])
        self.assertIn("적자", fn.card_html(info))

    def test_unknown_code_gives_none(self):
        self.assertIsNone(fn.summary("999999", path=_file(_entry())))


class CardTests(unittest.TestCase):
    def test_card_says_source_unit_and_that_estimates_are_left_out(self):
        text = fn.card_html(fn.summary("005930", path=_file(_entry())))
        for word in ("시가총액", "1,297.9조 원", "PER", "PBR", "ROE", "영업이익률", "부채비율", "당좌비율", "연간 실적",
                     "분기 실적", "단위 억 원", "네이버 증권", "추정치는 뺌", "2025.12 결산 기준"):
            self.assertIn(word, text)
        # 폰 규칙은 mobile_ui 에만 둔다(CLAUDE.md 12) · 칸은 자비스12 재무 창처럼 늘 네 칸(2026-11-04 상하님 「미국테마와 비교」)
        self.assertNotIn("@media", fn.CSS)
        self.assertIn(".j13fn-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr))", fn.CSS)


class ExtraCellsTests(unittest.TestCase):
    def test_52week_and_foreign_show_only_when_there(self):
        entry = dict(_entry(), hi52=380000.0, lo52=93500.0, foreign=46.16)
        text = fn.card_html(fn.summary("005930", 228000, path=_file(entry)))
        for word in ("52주 최고", "380,000원", "지금 -40.0%", "52주 최저", "93,500원", "외국인 비율", "46.2%"):
            self.assertIn(word, text)
        plain = fn.card_html(fn.summary("005930", path=_file(_entry())))    # 옛 파일(값 없음)은 줄을 안 그린다
        self.assertNotIn("52주 최고", plain)


class CollectTests(unittest.TestCase):
    def test_failed_codes_keep_their_old_values(self):
        path = _file(dict(_entry(), at="2026-10-31"))
        with patch.object(fn, "fetch_one", side_effect=lambda code, session=None: None):
            result = fn.collect({"005930": "삼성전자"}, path=path, workers=1)
        self.assertEqual({"asked": 1, "got": 0, "failed": 1, "total": 1}, result)
        self.assertEqual("2026-10-31", fn.load_file(path)["stocks"]["005930"]["at"])



class PageTests(unittest.TestCase):
    def test_detail_shows_the_box_and_guard_matches(self):
        source = (Path(__file__).resolve().parent / "pages" / "12_자비스13.py").read_text(encoding="utf-8")
        self.assertIn(f"_REQUIRED_J13_FUNDAMENTALS_REVISION = {fn.MODULE_REVISION}", source)
        detail = source.split("def _render_stock_detail(")[1].split("\ndef ")[0]
        self.assertLess(detail.index("_render_fundamentals_box(code, metrics, panel=panel)"), detail.index("_render_watch_toggle("))
        box = source.split("def _render_fundamentals_box(")[1].split("\ndef ")[0]
        self.assertIn("class='j13fz-tap'", box)    # 2026-11-04 자비스12 처럼 창 — 숨은 스위치로 브라우저가 여닫는다(서버에 안 묻는다)
        self.assertNotIn("requests", box)                           # 받으러 가지 않는다


class EarnInsiderTests(unittest.TestCase):
    """2026-11-04 밤 상하님 「왜 이거 안 넣냐 말 좀 들어라」 — 자비스12 「📅 실적 발표 · 👥 애널리스트 의견 · 🔍 공매도·내부자·배당」
    셋을 같은 자리 · 같은 차례로. 한국에서 받을 수 있는 것만(DART · 네이버 · 와이즈리포트), 못 받는 것은 그렇다고 적는다."""

    QUARTER = {"financeInfo": {"trTitleList": [{"key": "202606", "isConsensus": "N"}, {"key": "202609", "isConsensus": "Y"},
                                               {"key": "202612", "isConsensus": "Y"}],
                               "rowList": [{"title": "매출액", "columns": {"202606": {"value": "740,000"},
                                                                         "202609": {"value": "860,617"}}},
                                           {"title": "영업이익", "columns": {"202609": {"value": "105,123"}}}]}}

    def test_estimate_takes_first_consensus_column(self):
        self.assertEqual({"at": "2026.09", "rev": 860617.0, "op": 105123.0}, fn.parse_estimate(self.QUARTER))
        self.assertIsNone(fn.parse_estimate({"financeInfo": {"trTitleList": [{"key": "202606", "isConsensus": "N"}]}}))

    def test_wise_count_reads_label_not_needle(self):
        cells = ["4.00", "투자의견", "목표주가 (원)", "EPS (원)", "PER (배)", "추정기관수", "4.00", "477,500", "45,644", "4.81", "20"]
        html = '<table id="cTB15">' + "".join(f"<td>{c}</td>" for c in cells) + "</table>"
        self.assertEqual(20, fn.parse_wise_count(html))
        self.assertIsNone(fn.parse_wise_count("<table></table>"))

    def test_quarter_of_filing_day(self):
        self.assertEqual(["26.09", "26.06", "26.03", "25.12"],
                         [fn._quarter_of(d) for d in ("2026-10-08", "2026-07-30", "2026-04-29", "2026-01-29")])

    def test_reaction_uses_day_before_and_after(self):
        import pandas as pd
        frame = pd.DataFrame({"Close": [100.0, 102.0, 110.0]},
                             index=pd.to_datetime(["2026-10-07", "2026-10-08", "2026-10-10"]))
        self.assertAlmostEqual(10.0, fn.reaction(frame, "2026-10-08"))             # 10/7 100 → 10/10 110
        self.assertIsNone(fn.reaction(frame, "2026-10-10"))                         # 뒤 장이 아직 없으면 안 적는다
        self.assertIsNone(fn.reaction(None, "2026-10-08"))

    def test_next_guess_is_marked_estimate(self):
        from datetime import date
        earn = ["2026-10-28", "2026-07-30", "2026-04-29", "2026-01-29", "2025-10-30"]
        self.assertEqual("1월 28일쯤 · 85일 남음", fn._next_guess(earn, date(2026, 11, 4)))
        self.assertEqual("", fn._next_guess([], date(2026, 11, 4)))

    def test_first_announcement_per_quarter(self):
        # 2026-11-04 깃허브 실제 삼성전자 — 10/29 · 10/8 · 7/30 · 7/7 … (한 분기에 두 번)
        earn = ["2026-10-29", "2026-10-08", "2026-07-30", "2026-07-07", "2026-04-30", "2026-04-07", "2026-01-29", "2026-01-08"]
        self.assertEqual(["2026-10-08", "2026-07-07", "2026-04-07", "2026-01-08"], fn._first_per_quarter(earn))
        out = fn.street_html({"earn": earn, "quarter": []})
        self.assertEqual(1, out.count("<th>26.09</th>"))

    def test_three_boxes_in_jarvis12_order(self):
        import pandas as pd
        from datetime import date
        frame = pd.DataFrame({"Close": [100.0, 95.0, 104.0, 99.0]},
                             index=pd.to_datetime(["2026-07-29", "2026-07-31", "2026-10-27", "2026-10-29"]))
        info = {"earn": ["2026-10-28", "2026-07-30"], "est": {"at": "2026.12", "op": 120000.0, "rev": 900000.0},
                "quarter": [["26.06", 740000.0, 95000.0, 1.0], ["26.09", 860000.0, 101000.0, 1.0]],
                "consensus": {"recomm": 4.0, "target": 150000.0, "at": "2026-11-03", "n": 20}, "price": 100000.0,
                "reports": [], "foreign": 50.2,
                "ins": {"since": "2026-05-05", "up": 3, "down": 1, "up_sh": 25000.0, "down_sh": 500.0},
                "divd": {"year": 2025, "dps": 1446.0, "yield": 2.6, "payout": 33.0}, "divdays": ["2026-10-30"]}
        out = fn.street_html(info, frame, today=date(2026, 11, 4))
        self.assertLess(out.index("📅 실적 발표"), out.index("👥 애널리스트 의견"))
        self.assertLess(out.index("👥 애널리스트 의견"), out.index("🔍 공매도 · 내부자 · 배당"))
        for text in ("추정", "26.12 영업이익", "12.0조 원", "26.09", "101,000", "-5.0%", "-4.8%", "· 20곳",
                     "늘림 3번(2.5만 주)", "줄임 1번(500주)", "주당 1,446원", "배당수익률 2.6%", "배당성향 33%",
                     "최근 배당 결정 10/30", "못 받음 — 거래소", "「예상 대 실제」는 못 적습니다"):
            self.assertIn(text, out)
        self.assertNotIn("j3", out.replace("j13", ""))                              # 자비스12 이름과 안 섞임

    def test_no_data_keeps_the_box_with_a_reason(self):
        # 2026-11-05 상하님 「3」 — 자료 없는 상자도 자리를 두고 까닭 한 줄(전에는 감춰 「안 된다」로 보였다)
        out = fn.street_html({"consensus": {"recomm": 3.0}, "reports": []})
        self.assertLess(out.index("📅 실적 발표"), out.index("👥 애널리스트 의견"))
        self.assertLess(out.index("👥 애널리스트 의견"), out.index("🔍 공매도 · 내부자 · 배당"))
        self.assertIn(fn.EMPTY_EARN, out)
        self.assertIn(fn.EMPTY_OWN, out)
        self.assertNotIn(fn.EMPTY_ANA, out)                                          # 의견은 있다
        self.assertNotIn("26.09", out)                                               # 없는 값은 지어내지 않는다

    def test_stock_outside_the_file_says_so_in_all_three(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "KR.json"
            path.write_text('{"stocks": {}}', encoding="utf-8")
            block = fn.street_block("999999", 1000.0, path=path)
        self.assertTrue(block.startswith(fn.STREET_CSS))
        self.assertEqual(3, block.count(fn.NOT_IN_FILE))
        self.assertEqual("", fn.street_block("", path=path))

    def test_dart_extra_reads_both_date_shapes(self):
        from datetime import date

        class Resp:
            status_code = 200

            def __init__(self, data):
                self._data = data

            def json(self):
                return self._data

        class Session:
            def get(self, url, params=None, timeout=None):
                name = url.rsplit("/", 1)[-1]
                if name == "list.json":
                    return Resp({"status": "000", "list": [
                        {"rcept_dt": "20261028", "report_nm": "연결재무제표기준영업(잠정)실적(공정공시)"},
                        {"rcept_dt": "20261029", "report_nm": "[기재정정]연결재무제표기준영업(잠정)실적(공정공시)"},
                        {"rcept_dt": "20261030", "report_nm": "현금ㆍ현물배당결정"}]})
                if name == "elestock.json":
                    return Resp({"status": "000", "list": [
                        {"rcept_dt": "2026-10-01", "sp_stock_lmp_irds_cnt": "1,000"},
                        {"rcept_dt": "20260901", "sp_stock_lmp_irds_cnt": "-200"},
                        {"rcept_dt": "2025-01-01", "sp_stock_lmp_irds_cnt": "99,999"}]})     # 6개월 밖 — 뺀다
                return Resp({"status": "000", "list": [{"se": "주당 현금배당금(원)", "thstrm": "1,446"},
                                                       {"se": "현금배당수익률(%)", "thstrm": "2.6"},
                                                       {"se": "(연결)현금배당성향(%)", "thstrm": "33.0"}]})

        out = fn.dart_extra("열쇠", "00126380", Session(), today=date(2026, 11, 4))
        self.assertEqual(["2026-10-28"], out["earn"])                               # 정정 공시는 뺀다
        self.assertEqual(["2026-10-30"], out["divdays"])
        self.assertEqual((1, 1, 1000.0, 200.0), (out["ins"]["up"], out["ins"]["down"], out["ins"]["up_sh"], out["ins"]["down_sh"]))
        self.assertEqual({"year": 2025, "dps": 1446.0, "yield": 2.6, "payout": 33.0}, out["divd"])

    def test_overview_and_boxes_go_out_separately(self):
        # 2026-11-05 상하님 「너 사기쳤네」 — 한 번에 내보내면 스트림릿이 상자를 버렸다(그려 보니 0개)
        page = (Path(__file__).resolve().parent / "pages" / "12_자비스13.py").read_text(encoding="utf-8")
        self.assertNotIn("street += jarvis13_fundamentals.street_block(", page)
        self.assertIn("st.markdown(overview, unsafe_allow_html=True)", page)

    def test_page_passes_daily_frame(self):
        page = (Path(__file__).resolve().parent / "pages" / "12_자비스13.py").read_text(encoding="utf-8")
        self.assertIn("street_block(code, price_now, frame=j4data.get_daily_frame(code))", page)
        self.assertIn(f"_REQUIRED_J13_FUNDAMENTALS_REVISION = {fn.MODULE_REVISION}", page)

    def test_workflow_reads_dart_key_from_secret_only(self):
        flow = (Path(__file__).resolve().parent / ".github" / "workflows" / "j13_fundamentals.yml").read_text(encoding="utf-8")
        self.assertIn("DART_API_KEY: ${{ secrets.DART_API_KEY }}", flow)


if __name__ == "__main__":
    unittest.main()


class ColorRuleTests(unittest.TestCase):
    """2026-11-04 상하님 「부채비율 유동비율 색깔 봐라 · 기준이 안 되어 색깔이 같은 거냐?」 — 자비스12 와 같은 문턱."""

    def _color(self, html_text, name):
        import re
        return re.search(name + r"</b><i style='color:([^']+)'", html_text).group(1)

    def test_same_thresholds_as_jarvis12(self):
        import jarvis13_fundamentals as fn
        bad = fn.card_html({"loss": True, "roe": -14.4, "opm": -0.5, "debt": 250, "quick": 75, "annual": [], "quarter": []})
        self.assertEqual(fn.NEG, self._color(bad, "PER"))          # 적자
        self.assertEqual(fn.NEG, self._color(bad, "ROE"))          # 마이너스
        self.assertEqual(fn.NEG, self._color(bad, "영업이익률"))
        self.assertEqual(fn.WARN, self._color(bad, "부채비율"))     # 200%↑
        self.assertEqual(fn.WARN, self._color(bad, "당좌비율"))     # 100%↓
        good = fn.card_html({"per": 10, "roe": 12, "opm": 8, "debt": 170, "quick": 120, "annual": [], "quarter": []})
        for name in ("PER", "ROE", "영업이익률", "부채비율", "당좌비율"):
            self.assertEqual("#ffffff", self._color(good, name), name)
        self.assertEqual((200.0, 100.0), (fn.DEBT_WARN, fn.QUICK_WARN))
        self.assertIn("주의", good)

    def test_losses_in_the_table_are_blue(self):
        import jarvis13_fundamentals as fn
        out = fn.card_html({"annual": [["24.12", 742696, -3557, -23725]], "quarter": []})
        self.assertIn(f"color:{fn.NEG}'>-3,557", out)
        self.assertIn(f"color:{fn.NEG}'>-23,725", out)


class NarrowCardTests(unittest.TestCase):
    """2026-11-04 상하님 캡처 — 폰에서 실적 표가 잘려 옛 칸(23.12·24.12)만 보였다. 좁은 카드는 자비스12 폰처럼 두 칸 · 그림 한 칸 가득."""

    def test_narrow_card_stacks_like_jarvis12_phone(self):
        self.assertIn(".j13fn{container-type:inline-size}", fn.CSS)
        block = fn.CSS.split("@container (max-width: 620px){")[1].split("}\n}")[0]
        self.assertIn(".j13fn-grid{grid-template-columns:1fr 1fr", block)
        self.assertIn(".j13fn-charts{grid-template-columns:1fr", block)
        self.assertIn(".j13fn-t{table-layout:fixed}", fn.CSS)            # 칸이 넘치지 않고 최신 칸까지 다 들어간다


class StreetTests(unittest.TestCase):
    """2026-11-04 상하님 「한국테마에서 3번째 캡쳐 빠졌고」 — 자비스12 「애널리스트 의견 · 목표주가」 자리(받을 수 있는 것만)."""

    WHOLE = {"consensusInfo": {"itemCode": "096770", "createDate": "2026-11-03", "recommMean": "4.00",
                               "priceTargetMean": "207,455"},
             "researches": [{"bnm": "하나증권", "wdt": "2026-10-30", "tit": "남의 제목"},
                            {"bnm": "KB증권", "wdt": "2026-10-29", "tit": "남의 제목 2"}]}

    def test_parse_from_integration(self):
        self.assertEqual({"recomm": 4.0, "target": 207455.0, "at": "2026-11-03"}, fn.parse_consensus(self.WHOLE))
        self.assertEqual([["하나증권", "2026-10-30"], ["KB증권", "2026-10-29"]], fn.parse_reports(self.WHOLE))
        self.assertIsNone(fn.parse_consensus({}))                                     # 없으면 지어내지 않는다

    def test_box_shows_target_gap_and_no_titles(self):
        info = {"consensus": fn.parse_consensus(self.WHOLE), "reports": fn.parse_reports(self.WHOLE), "price": 120700.0,
                "foreign": 16.4, "dps": 2000.0, "dy": 1.66, "latest_at": "2025.12", "annual": [], "quarter": []}
        out = fn.street_html(info)
        for text in ("👥 애널리스트 의견", "4.00", "매수", "207,455원", "지금보다 +72%", "하나증권 10/30", "11/03 기준",
                     "점수·판정에는 들어가지 않습니다", "🔍 공매도 · 내부자 · 배당", "16.4%", "주당 2,000원"):
            self.assertIn(text, out)
        self.assertNotIn("남의 제목", out)                                             # 리포트 제목은 안 옮긴다
        empty = fn.street_html({"annual": [], "quarter": []})                        # 자료 없으면 칸마다 까닭 한 줄
        for reason in (fn.EMPTY_EARN, fn.EMPTY_ANA, fn.EMPTY_OWN):
            self.assertIn(reason, empty)
        # 2026-11-04 상하님 「왜 재무현황 안에 집어넣었냐」 — 재무 창 안에는 없다
        self.assertNotIn("애널리스트 의견", fn.card_html(info))

    def test_page_puts_it_above_the_fundamentals_button(self):
        page = (Path(__file__).resolve().parent / "pages" / "12_자비스13.py").read_text(encoding="utf-8")
        block = page[page.index("jarvis13_fundamentals.street_block("):]
        self.assertLess(block.index("street_block("), block.index("_render_fundamentals_box(code, metrics, panel=panel)"))
        self.assertNotIn("j3st", fn.STREET_CSS)                                       # 자비스12 이름과 안 섞임

    def test_report_dates_from_naver_shape(self):
        # 2026-11-04 실제 모은 값은 「20261030」 모양이었다(처음에는 「030」으로 잘못 나왔다)
        out = fn.street_html({"reports": [["하나증권", "20261030"], ["KB증권", "2026-10-09"], ["X", "날짜없음"]]})
        self.assertIn("하나증권 10/30", out)
        self.assertIn("KB증권 10/9", out)
        self.assertNotIn("030", out.replace("10/30", ""))

    def test_recomm_words(self):
        self.assertEqual(["강력 매수", "매수", "중립", "매도", "강력 매도"],
                         [fn.recomm_word(v) for v in (4.8, 4.0, 3.0, 2.0, 1.0)])


class OverviewTests(unittest.TestCase):
    """2026-11-04 상하님 「다른 것도 확인하고 미국테마 형식 따라서 해라」 — 자비스12 「🏢 종목 개요」 자리(있는 것만)."""

    def test_overview_shows_app_themes_first_and_link(self):
        out = fn.overview_html("096770", "SK이노베이션", theme="2차전지",
                               themes=["정유", "2차전지", "윤활유", "LPG", "석유화학", "폐배터리", "주유소", "ESS"],
                               info={"mcap": 204047.0})
        self.assertIn("🏢 SK이노베이션", out)
        self.assertLess(out.index("앱 테마 · 2차전지"), out.index("앱 테마 · 정유"))      # 지금 보는 테마가 맨 앞
        self.assertEqual(6, out.count("j13ov-chip j13ov-t"))
        self.assertIn("외 2개", out)
        self.assertIn("coinfo.naver?code=096770", out)
        self.assertIn("시가총액 20.4조 원", out)
        self.assertNotIn("j3ov", out)

    def test_page_order_matches_jarvis12(self):
        page = (Path(__file__).resolve().parent / "pages" / "12_자비스13.py").read_text(encoding="utf-8")
        block = page[page.index("jarvis13_fundamentals.overview_html("):]
        self.assertLess(block.index("overview_html("), block.index("street_block("))
        self.assertLess(block.index("street_block("), block.index("_render_fundamentals_box(code, metrics, panel=panel)"))
