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
        whole = {"stockName": "삼성전자", "totalInfos": [{"code": "marketValue", "value": "1,297조 8,739억"}]}
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
        self.assertIn("max-width: 600px", fn.CSS)


class CollectTests(unittest.TestCase):
    def test_failed_codes_keep_their_old_values(self):
        path = _file(dict(_entry(), at="2026-10-31"))
        with patch.object(fn, "fetch_one", side_effect=lambda code, session=None: None):
            result = fn.collect({"005930": "삼성전자"}, path=path, workers=1)
        self.assertEqual({"asked": 1, "got": 0, "failed": 1, "total": 1}, result)
        self.assertEqual("2026-10-31", fn.load_file(path)["stocks"]["005930"]["at"])


if __name__ == "__main__":
    unittest.main()
