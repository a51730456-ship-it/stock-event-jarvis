import ast
import datetime
import re
import unittest
from pathlib import Path
from unittest.mock import patch

import disclosure_data


def load_fetch_helper():
    source = Path("app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    wanted = {"_kr_dart_stock_code", "_format_dart_date", "_fetch_kr_dart_disclosures"}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    namespace = {"re": re, "datetime": datetime.datetime, "timedelta": datetime.timedelta}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "app.py", "exec"), namespace)
    return namespace


class AppDartContractTests(unittest.TestCase):
    def test_display_contract_for_empty_dates_links_and_multiple_items(self):
        ns = load_fetch_helper()
        self.assertEqual(ns["_format_dart_date"]("20260711"), "2026-07-11")
        self.assertEqual(ns["_format_dart_date"](""), "-")
        source = Path("app.py").read_text(encoding="utf-8")
        self.assertIn("최근 3일 공시 없음", source)
        self.assertIn('st.markdown("---")', source)
        self.assertIn("공시 {len(row['data'])}건", source)
        self.assertIn("https://dart.fss.or.kr/dsaf001/main.do?rcpNo=", source)

    def test_screen_contract_and_no_external_call_before_button(self):
        source = Path("app.py").read_text(encoding="utf-8")
        self.assertIn("📢 한국장 최근 공시 자동 확인", source)
        self.assertIn('key="kr_dart_check_button"', source)
        self.assertIn('"kr_dart_disclosure_results"', source)
        self.assertIn('"kr_dart_checked_at"', source)
        self.assertIn("@st.cache_data(ttl=86400", source)
        panel = source[source.index("def _render_kr_dart_disclosure_panel"):]
        self.assertLess(panel.index("st.button"), panel.index("_fetch_kr_dart_disclosures"))
        self.assertEqual(source.count("fetch_dart_corp_code_map("), 1)
        self.assertEqual(source.count("fetch_recent_dart_disclosures("), 1)

    def test_mock_normal_empty_missing_and_failure_are_read_only(self):
        ns = load_fetch_helper()
        ns["_cached_kr_dart_corp_code_map"] = lambda key: {
            "status": "정상",
            "data": {"005930": {"corp_code": "001", "corp_name": "A"}},
        }
        stocks = [{"name": "A", "ticker": "005930.KS"}, {"name": "B", "ticker": "000660.KS"}, {"name": "C", "ticker": "NO_CODE"}]
        calls = []
        def recent(*args, **kwargs):
            calls.append(args)
            return {"status": "정상", "data": [{"rcept_no": "1"}]}
        ns["disclosure_data"] = disclosure_data
        with patch.object(disclosure_data, "fetch_recent_dart_disclosures", side_effect=recent):
            result = ns["_fetch_kr_dart_disclosures"]("mock-key", stocks, datetime.date(2026, 7, 11))
        self.assertEqual(result["summary"], {"normal": 1, "empty": 0, "failed": 0, "missing": 2})
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["rows"][1]["status"], "corp_code 없음")
        self.assertEqual(result["rows"][2]["status"], "종목코드 없음")
        self.assertEqual(result["start_date"], "20260709")
        self.assertEqual(result["end_date"], "20260711")
        self.assertNotIn("score", repr(result).lower())

    def test_no_key_is_safe_and_failure_status_is_preserved(self):
        ns = load_fetch_helper()
        self.assertEqual(ns["_fetch_kr_dart_disclosures"]("", [], datetime.date(2026, 7, 11))["message"], "OpenDART 인증키 설정이 필요합니다")
        ns["_cached_kr_dart_corp_code_map"] = lambda key: {"status": "정상", "data": {"005930": {"corp_code": "001"}}}
        ns["disclosure_data"] = disclosure_data
        with patch.object(disclosure_data, "fetch_recent_dart_disclosures", return_value={"status": "요청 제한", "data": [], "message": "짧은 오류"}):
            result = ns["_fetch_kr_dart_disclosures"]("mock-key", [{"name": "A", "ticker": "005930.KQ"}], datetime.date(2026, 7, 11))
        self.assertEqual(result["summary"]["failed"], 1)
        self.assertEqual(result["rows"][0]["status"], "요청 제한")


if __name__ == "__main__":
    unittest.main()
