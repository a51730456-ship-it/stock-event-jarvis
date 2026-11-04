"""자비스13 종목 수급 — 네이버 모바일 자료 · 점수에는 안 씀 (2026-11-04 상하님 「고쳐라」 → 「1 · 값만 보이게」)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

import jarvis4_data as j4
import jarvis13_flow as flow

ROOT = Path(__file__).resolve().parent


def _trend(days=6):
    items = []
    for i in range(days):
        items.append({"itemCode": "005930", "bizdate": f"202611{10 - i:02d}",
                      "foreignerPureBuyQuant": "+1,000" if i % 2 == 0 else "-500",
                      "organPureBuyQuant": "+2,000", "closePrice": "222,000",
                      "accumulatedTradingVolume": "13,391,670", "compareToPreviousPrice": {"text": "하락"}})
    return json.dumps(items, ensure_ascii=False)


class _Resp:
    def __init__(self, text):
        self.text, self.encoding = text, None

    def raise_for_status(self):
        return None


class _Session:
    def __init__(self, text):
        self._text, self.urls = text, []

    def get(self, url, timeout=8):
        self.urls.append(url)
        return _Resp(self._text)


class FlowTests(unittest.TestCase):
    def setUp(self):
        flow.install(j4)
        self.addCleanup(flow.uninstall, j4)
        j4._CACHE.clear()

    def test_parse_trend_matches_the_old_table_shape(self):
        rows = flow.parse_trend(_trend(3))
        self.assertEqual("2026.11.10", rows[0]["date"])               # 최근 날이 앞
        self.assertEqual({"date", "close", "volume", "institution_net", "foreign_net"}, set(rows[0]))
        self.assertEqual(1000.0, rows[0]["foreign_net"])
        self.assertEqual(-500.0, rows[1]["foreign_net"])
        self.assertEqual(222000.0, rows[0]["close"])
        self.assertEqual([], flow.parse_trend("<html>"))                # 못 읽으면 빈 줄(지어내지 않음)

    def test_stock_flow_comes_from_the_mobile_feed(self):
        session = _Session(_trend(20))
        with patch.object(j4, "_http_session", return_value=session), \
                patch.object(j4, "_disk_cache_read", return_value=None), patch.object(j4, "_disk_cache_write"):
            result = j4.get_stock_flow("005930")
        self.assertTrue(result["ok"], result)
        self.assertEqual("https://m.stock.naver.com/api/stock/005930/trend?pageSize=20", session.urls[0])
        self.assertEqual("2026.11.10", result["latest_date"])
        self.assertEqual(5, result["window5"])

    def test_scores_stay_without_flow(self):
        metrics = {"current": 100.0, "from_high_pct": -3.0, "ret20": 5.0, "ret60": 10.0, "atr_pct": 3.0,
                   "avg_trading_value": 1e10, "sma20": 95.0, "sma50": 90.0}
        good = {"ok": True, "net5_amount": 5e9, "both_buy_days5": 3}
        score_with, parts_with = j4._stock_score(metrics, dict(good), 2.0)
        score_none, parts_none = j4._j13_original_stock_score(metrics, {"ok": False}, 2.0)
        self.assertEqual(score_none, score_with)                          # 수급이 있어도 점수는 수급 없을 때와 같다
        shown = dict(good)
        j4._stock_score(metrics, shown, 2.0)
        self.assertIsNotNone(shown.get("net5_ratio"))                    # 화면용 값(거래대금 대비 %)은 남는다
        pull_with = j4._pullback_quality(metrics, dict(good)) or {}
        pull_none = j4._j13_original_pullback_quality(metrics, {"ok": False}) or {}
        self.assertEqual(pull_none.get("score"), pull_with.get("score"))

    def test_market_score_gets_no_flow_but_screen_sees_it(self):
        real = {"ok": True, "net5_amount": 3e11, "previous_net5_amount": 1e11}
        with patch.object(j4, "_j13_original_market_foreign_flow", return_value=real):
            flow.uninstall(j4)
            flow.install(j4)
            given = j4._market_foreign_flow()
        self.assertFalse(given["ok"])
        self.assertIsNone(given["previous_net5_amount"])               # 어제 국면 15점에도 안 들어간다
        self.assertEqual(real, flow.for_display(given))
        overview = {"foreign": given, "score_breakdown": [{"label": "외국인·기관 5일 수급", "earned": 0, "max": 15}]}
        marked = flow.mark_display_only(overview)
        self.assertIn("점수 안 씀", marked["score_breakdown"][0]["label"])
        self.assertEqual(0, marked["score_breakdown"][0]["earned"])

    def test_uninstall_restores_the_frozen_module(self):
        flow.uninstall(j4)
        self.assertEqual("https://finance.naver.com/item/frgn.naver?code={code}", j4._STOCK_FLOW_URL)
        self.assertIs(j4._stock_score, j4._j13_original_stock_score)
        flow.install(j4)
        self.assertTrue(j4._STOCK_FLOW_URL.startswith(flow.MARK))

    def test_page_and_theme15_collector_install_it(self):
        page = (ROOT / "pages" / "12_자비스13.py").read_text(encoding="utf-8")
        self.assertIn("jarvis13_flow.install(j4data)", page)
        self.assertEqual(2, page.count("foreign = jarvis13_flow.for_display(overview.get(\"foreign\"))"))
        collector = (ROOT / "research" / "j13_theme15_collect.py").read_text(encoding="utf-8")
        self.assertIn("jarvis13_flow.install(data)", collector)


if __name__ == "__main__":
    unittest.main()
