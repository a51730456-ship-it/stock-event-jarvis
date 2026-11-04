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
                "annual": [], "quarter": []}
        out = fn.card_html(info)
        for text in ("👥 증권사 의견", "4.00", "매수", "207,455원", "지금보다 +72%", "하나증권 10/30", "2026-11-03 기준",
                     "점수 · 판정에는 안 들어갑니다"):
            self.assertIn(text, out)
        self.assertNotIn("남의 제목", out)                                             # 리포트 제목은 안 옮긴다
        self.assertEqual("", fn.street_html({"annual": [], "quarter": []}))          # 자료 없으면 칸도 없다

    def test_recomm_words(self):
        self.assertEqual(["강력 매수", "매수", "중립", "매도", "강력 매도"],
                         [fn.recomm_word(v) for v in (4.8, 4.0, 3.0, 2.0, 1.0)])
