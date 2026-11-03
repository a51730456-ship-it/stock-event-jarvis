"""자비스13 「📑 재무 한눈에」 — 한국 재무(네이버 기업실적분석) 읽기·셈·그리기 (2026-11-03)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import jarvis13_fundamentals as fn

# 네이버 종목 첫 화면 「기업실적분석」 표와 같은 짜임(머리글 두 줄 · 연간 4 + 분기 6 · 끝 칸은 추정치)
_HEAD_YEARS = ["2022.12", "2023.12", "2024.12", "2025.12(E)"]
_HEAD_QUARTERS = ["2024.12", "2025.03", "2025.06", "2025.09", "2025.12", "2026.03(E)"]


def _page(rows: dict, *, cap="415조 4,231", price="70,100", name="삼성전자") -> str:
    head1 = "<tr><th rowspan='2'>주요재무정보</th><th colspan='4'>최근 연간 실적</th><th colspan='6'>최근 분기 실적</th></tr>"
    head2 = "<tr>" + "".join(f"<th>{h}</th>" for h in _HEAD_YEARS + _HEAD_QUARTERS) + "</tr>"
    body = "".join(f"<tr><th>{label}</th>" + "".join(f"<td>{v}</td>" for v in values) + "</tr>"
                   for label, values in rows.items())
    return (f"<div class='wrap_company'><h2><a href='#'>{name}</a></h2></div>"
            f"<p class=\"no_today\"><em><span class=\"blind\">{price}</span></em></p>"
            f"<em id=\"_market_sum\">\n\t\t{cap}</em>억원"
            f"<div class='section cop_analysis'><table><thead>{head1}{head2}</thead><tbody>{body}</tbody></table></div>")


ROWS = {
    "매출액": ["3,022,314", "2,589,355", "3,008,709", "3,300,000", "757,883", "791,405", "745,663", "860,617", "930,837", "900,000"],
    "영업이익": ["433,766", "65,670", "327,260", "400,000", "64,927", "66,853", "46,761", "121,661", "200,737", "180,000"],
    "당기순이익": ["556,541", "154,871", "344,514", "380,000", "77,544", "82,229", "50,990", "122,257", "190,000", "170,000"],
    "영업이익률": ["14.35", "2.54", "10.88", "12.1", "8.57", "8.45", "6.27", "14.14", "21.57", "20.0"],
    "ROE(지배주주)": ["17.07", "4.15", "9.03", "10.0", "", "", "", "", "", ""],
    "부채비율": ["26.41", "25.36", "27.93", "", "27.93", "26.99", "26.40", "28.10", "29.00", ""],
    "당좌비율": ["211.68", "189.46", "187.80", "", "187.80", "190.00", "195.00", "200.00", "205.00", ""],
    "EPS(원)": ["8,057", "2,131", "4,950", "5,500", "", "", "", "", "", ""],
    "BPS(원)": ["50,817", "52,002", "57,930", "60,000", "", "", "", "", "", ""],
    "주당배당금(원)": ["1,444", "1,444", "1,446", "1,500", "", "", "", "", "", ""],
    "시가배당률(%)": ["2.6", "1.9", "2.7", "", "", "", "", "", "", ""],
}


class ParseTests(unittest.TestCase):
    def setUp(self):
        self.out = fn.parse(_page(ROWS))

    def test_actuals_only_no_estimates(self):
        self.assertEqual(["22.12", "23.12", "24.12"], [row[0] for row in self.out["annual"]])
        self.assertEqual(["24.12", "25.03", "25.06", "25.09", "25.12"], [row[0] for row in self.out["quarter"]])
        self.assertEqual([3008709.0, 327260.0, 344514.0], self.out["annual"][-1][1:])

    def test_latest_figures_and_page_values(self):
        self.assertEqual("2024.12", self.out["latest_at"])
        self.assertEqual(4950.0, self.out["latest"]["eps"])
        self.assertEqual(29.0, self.out["latest_q"]["debt"])            # 분기 쪽이 더 새로움
        self.assertEqual(4154231.0, self.out["mcap"])                   # 415조 4,231억 → 억원
        self.assertEqual(70100.0, self.out["px"])
        self.assertEqual("삼성전자", self.out["name"])

    def test_page_without_the_table_gives_none(self):
        self.assertIsNone(fn.parse("<html><body>점검 중</body></html>"))


class SummaryTests(unittest.TestCase):
    def _file(self, entry):
        path = Path(tempfile.mkdtemp()) / "KR.json"
        path.write_text(json.dumps({"stocks": {"005930": entry}}, ensure_ascii=False), encoding="utf-8")
        return path

    def test_values_are_recounted_with_the_price_now(self):
        entry = fn.parse(_page(ROWS))
        entry["at"] = "2026-11-07"
        info = fn.summary("005930", 99000, path=self._file(entry))
        self.assertAlmostEqual(99000 / 4950, info["per"])
        self.assertAlmostEqual(99000 / 57930, info["pbr"])
        self.assertAlmostEqual(1446 / 99000 * 100, info["dy"])
        self.assertAlmostEqual(4154231 * 99000 / 70100, info["mcap"])
        self.assertTrue(info["rescaled"])

    def test_loss_and_missing_values_stay_blank(self):
        rows = dict(ROWS, **{"EPS(원)": ["-1,000", "-500", "-300", "", "", "", "", "", "", ""],
                             "주당배당금(원)": [""] * 10, "시가배당률(%)": [""] * 10})
        entry = fn.parse(_page(rows))
        info = fn.summary("005930", path=self._file(entry))
        self.assertTrue(info["loss"])
        self.assertIsNone(info["per"])
        self.assertIsNone(info["dy"])
        text = fn.card_html(info)
        self.assertIn("적자", text)
        self.assertIn("—", text)

    def test_unknown_code_gives_none(self):
        self.assertIsNone(fn.summary("999999", path=self._file({})))


class CardTests(unittest.TestCase):
    def test_card_says_source_unit_and_that_estimates_are_left_out(self):
        entry = fn.parse(_page(ROWS))
        entry["at"] = "2026-11-07"
        path = Path(tempfile.mkdtemp()) / "KR.json"
        path.write_text(json.dumps({"stocks": {"005930": entry}}, ensure_ascii=False), encoding="utf-8")
        text = fn.card_html(fn.summary("005930", path=path))
        for word in ("시가총액", "415.4조 원", "PER", "PBR", "ROE", "영업이익률", "부채비율", "당좌비율", "연간 실적",
                     "분기 실적", "단위 억 원", "네이버 증권 기업실적분석", "추정치는 뺌", "2024.12 결산 기준"):
            self.assertIn(word, text)
        self.assertIn("max-width: 600px", fn.CSS)                      # 폰은 두 칸 · 표 하나씩


if __name__ == "__main__":
    unittest.main()
