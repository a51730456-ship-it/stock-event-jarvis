"""자비스13 「📢 최근 공시」(2026-11-04 상하님 「DART 하자」)."""
from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path

import jarvis13_disclosures as dart

PAGE = Path(__file__).resolve().parent / "pages" / "12_자비스13.py"


def _map(calls):
    def fetch(api_key):
        calls.append(api_key)
        return {"status": "정상", "data": {"005930": {"corp_code": "00126380", "corp_name": "삼성전자"}}}
    return fetch


def _list(api_key, corp_code, start, end):
    return {"status": "정상", "data": [
        {"rcept_no": "20261103000123", "rcept_dt": "20261103", "report_nm": "주요사항보고서(유상증자결정)", "flr_nm": "삼성전자"},
        {"rcept_no": "20261028000456", "rcept_dt": "20261028", "report_nm": "분기보고서 (2026.09)", "flr_nm": "삼성전자"},
        {"rcept_no": "", "rcept_dt": "20261020", "report_nm": "번호 없는 줄"},
    ]}


class DisclosureTests(unittest.TestCase):
    def setUp(self):
        dart._MAP.update({"at": 0.0, "value": None, "status": None})

    def test_rows_links_and_caution_chip(self):
        calls = []
        out = dart.recent("key", "005930", fetch_map=_map(calls), fetch_list=_list, today=date(2026, 11, 4))
        self.assertEqual("정상", out["status"])
        self.assertEqual("20261005", out["start"])
        self.assertEqual(2, len(out["rows"]))                         # 번호 없는 줄은 뺀다
        first = out["rows"][0]
        self.assertEqual("2026-11-03", first["day"])
        self.assertTrue(first["caution"])
        self.assertEqual("https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261103000123", first["link"])
        self.assertFalse(out["rows"][1]["caution"])

    def test_code_map_is_kept_for_a_day_and_failures_are_not_kept(self):
        calls = []
        dart.recent("key", "005930", fetch_map=_map(calls), fetch_list=_list)
        dart.recent("key", "005930", fetch_map=_map(calls), fetch_list=_list)
        self.assertEqual(1, len(calls))                               # 두 번째는 담아 둔 표
        dart._MAP.update({"at": 0.0, "value": None})
        bad = dart.recent("key", "005930", fetch_map=lambda k: {"status": "요청 제한", "data": []}, fetch_list=_list)
        self.assertEqual("요청 제한", bad["status"])
        self.assertIsNone(dart._MAP["value"])

    def test_no_key_or_unknown_code(self):
        self.assertEqual("열쇠 없음", dart.recent("", "005930", fetch_map=_map([]), fetch_list=_list)["status"])
        self.assertEqual("공시 회사번호 없음",
                         dart.recent("key", "999999", fetch_map=_map([]), fetch_list=_list)["status"])

    def test_caution_words(self):
        for title in ("전환사채권발행결정", "최대주주 변경", "횡령ㆍ배임혐의발생", "감사의견 거절"):
            self.assertTrue(dart.caution(title), title)
        for title in ("분기보고서", "자기주식취득결정", "현금ㆍ현물배당결정"):
            self.assertFalse(dart.caution(title), title)


class PageTests(unittest.TestCase):
    def test_box_is_in_the_detail_and_only_fetches_when_opened(self):
        source = PAGE.read_text(encoding="utf-8")
        self.assertIn(f"_REQUIRED_J13_DISCLOSURES_REVISION = {dart.MODULE_REVISION}", source)
        detail = source.split("def _render_stock_detail(")[1].split("\ndef ")[0]
        self.assertIn("_render_disclosures_box(code, leader.get(\"name\") or code, panel=panel)", detail)
        box = source.split("def _render_disclosures_box(")[1].split("\ndef ")[0]
        self.assertLess(box.index("_section_toggle("), box.index("jarvis13_disclosures.recent("))   # 누를 때만
        self.assertIn('st.secrets.get("DART_API_KEY")', box)           # 열쇠는 비밀 칸에서만
        self.assertIn("점수·판정에 안 씁니다", box)


if __name__ == "__main__":
    unittest.main()
