"""자비스12 급락 후 반등장 — 기준일 하루로 정한 10종목 (2026-10-14 상하님 지시 · 설명서 3-3)."""
from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

import jarvis12_crash as c12

ROOT = Path(__file__).resolve().parent
J12 = (ROOT / "pages" / "11_자비스12.py").read_text(encoding="utf-8")
SPEC = (ROOT / "docs" / "US_THEME_SPEC.md").read_text(encoding="utf-8")


def _qqq(closes, start="2025-01-01"):
    days = pd.bdate_range(start, periods=len(closes))
    closes = np.asarray(closes, dtype=float)
    return pd.DataFrame({"Open": closes, "High": closes, "Low": closes, "Close": closes, "Volume": 1}, index=days)


class EpisodeTests(unittest.TestCase):
    def _episodes(self, closes):
        frame = _qqq(closes)
        with mock.patch.object(c12.j3, "_download_cached", return_value=({c12.SYMBOL: frame}, {})):
            return c12.episodes(), frame

    def test_deepest_day_moves_and_recovery_ends_the_crash(self):
        # 300일 오름 → −6% → −9%(가장 깊음) → −5.5% → 전고점 회복 → 다시 −7%(새 급락)
        rise = list(np.linspace(100, 130, 300))
        path = rise + [130 * 0.94, 130 * 0.91, 130 * 0.945, 130.5, 131, 131 * 0.93, 131 * 0.95]
        info, frame = self._episodes(path)
        days = [d.date().isoformat() for d in frame.index]
        first, second = info["episodes"]
        self.assertEqual(days[301], first["reference"])               # −9% 날로 옮겨 갔다
        self.assertAlmostEqual(-9.0, first["reference_drop"], places=1)
        self.assertEqual(days[303], first["recovered_on"])            # 전고점(52주 최고 종가) 회복
        self.assertEqual(days[305], second["reference"])              # 회복 뒤 다시 빠진 것은 새 급락
        self.assertIsNone(second["recovered_on"])

    def test_minus_five_is_the_line(self):
        rise = list(np.linspace(100, 130, 300))
        info, _frame = self._episodes(rise + [130 * 0.955])          # −4.5% — 급락 아님
        self.assertEqual([], info["episodes"])
        info, _frame = self._episodes(rise + [130 * 0.949])          # −5.1% — 급락
        self.assertEqual(1, len(info["episodes"]))


class PickTests(unittest.TestCase):
    def test_five_from_each_group_scored_on_the_reference_day_only(self):
        tickers = [f"S{i:02d}" for i in range(14)]
        days = pd.bdate_range("2025-01-01", periods=320)
        frames, members = {}, {}
        for i, ticker in enumerate(tickers):
            depth = 0.75 if i < 7 else 0.6                            # 앞 일곱 −25% · 뒤 일곱 −40%
            closes = np.r_[np.linspace(50, 100, 300), np.full(10, 100 * depth), np.full(10, 100 * depth * 1.3)]
            frames[ticker] = pd.DataFrame({"Open": closes, "High": closes, "Low": closes, "Close": closes,
                                           "Volume": 1e6 + i}, index=days)
            members[ticker] = ["테마"]
        ref = days[305].date()
        seen = []

        def fake_score(row):
            seen.append(row["metrics"]["current"])                     # 점수는 기준일 값으로 매긴다
            return {"score": 100 - int(row["ticker"][1:])}

        with mock.patch.object(c12.j3, "US_LARGE_CAP_UNIVERSE", tickers), \
                mock.patch.object(c12.j3, "crash_rebound_score", side_effect=fake_score):
            picked, counts = c12._pick(frames, members, ref)
        self.assertEqual({"shallow": 7, "deep": 7}, counts)
        self.assertEqual(10, len(picked))
        self.assertEqual(["shallow"] * 5 + ["deep"] * 5, [row["bucket"] for row in picked])
        self.assertEqual(tickers[:5] + tickers[7:12], [row["ticker"] for row in picked])
        self.assertTrue(all(abs(v - 75) < 1e-6 or abs(v - 60) < 1e-6 for v in seen))   # 오늘(×1.3) 값 아님
        first = picked[0]
        self.assertEqual(days[306].date().isoformat(), first["buy_date"])            # 기준일 다음 거래일
        self.assertAlmostEqual(75.0, first["buy_open"])
        self.assertAlmostEqual(97.5, first["metrics"]["current"])                     # 보이는 값은 오늘 것
        self.assertAlmostEqual(30.0, first["since_reference_pct"], places=6)
        # 두 갈래를 합친 급락 배점 차례(순위 9 가 위 3개를 뽑을 때 쓴다) — 점수 100−번호라 번호 차례
        self.assertEqual([0, 1, 2, 3, 4, 7, 8, 9, 10, 11], [row["score_order"] for row in picked])


class HeldTests(unittest.TestCase):
    def test_rows_held_at_the_period_start_are_rebased_to_that_open(self):
        """9/1~ 처럼 산 날(7/30)보다 뒤에 시작하는 기간에도 그 10종목이 나온다 — 첫 거래일 시가에 들고 있던 셈."""
        days = pd.bdate_range("2026-07-27", "2026-09-10")
        frame = pd.DataFrame({"Open": np.arange(len(days)) + 100.0, "Close": np.arange(len(days)) + 100.5}, index=days)
        rows = [{"trade_date": "2026-07-29", "code": "AAA", "buy_open": 90.0, "shown_until": ""},
                {"trade_date": "2026-03-30", "code": "AAA", "buy_open": 50.0, "shown_until": "2026-06-05"}]
        with mock.patch.object(c12.j3, "_download_cached", return_value=({"AAA": frame}, {})):
            out = c12.held_from(rows, date(2026, 9, 1))
        self.assertEqual(1, len(out))                                   # 다음 급락이 시작된 3월 줄은 안 들어간다
        first = list(days.date).index(date(2026, 9, 1))
        # 다른 파트와 같은 날 — 9/1 목록으로 보고 다음 거래일(9/2) 시가에 산다(9/1 날짜별 목록과 같은 산 값)
        self.assertEqual("2026-09-01", out[0]["trade_date"])
        self.assertEqual("2026-09-02", out[0]["held_from"])
        self.assertAlmostEqual(100.0 + first + 1, out[0]["buy_open"])
        # 첫날이 토요일(9/5)이면 그 뒤 첫 장(월 9/7) 시가 — 그 토요일 목록의 다른 파트와 같은 날(화요일이 아니다)
        with mock.patch.object(c12.j3, "_download_cached", return_value=({"AAA": frame}, {})):
            weekend = c12.held_from(rows, date(2026, 9, 5))
        self.assertEqual(("2026-09-05", "2026-09-07"), (weekend[0]["trade_date"], weekend[0]["held_from"]))
        self.assertAlmostEqual(100.0 + list(days.date).index(date(2026, 9, 7)), weekend[0]["buy_open"])
        # 마지막 날 뒤 장이 아직 없으면 넣지 않는다
        with mock.patch.object(c12.j3, "_download_cached", return_value=({"AAA": frame}, {})):
            self.assertEqual([], c12.held_from(rows, date(2026, 9, 10)))


class PageTests(unittest.TestCase):
    def test_page_shows_the_fixed_list_and_scorecard_counts_one_buy(self):
        self.assertIn('st.session_state["j3_pullback_result"] = jarvis12_crash.crash_list()', J12)
        self.assertIn("if pressed != \"crash\":\n                    picklist_ui.autosave(\"US\", pressed, found)", J12)
        self.assertIn("st.info(_crash12_story(reference, drop_now, len(rows)))", J12)
        self.assertIn("reference = jarvis12_crash.reference()", J12)
        self.assertEqual(3, J12.count('rows = [row for row in rows if row.get("list_kind") != "crash"]'))
        self.assertIn('if day < _SCORECARD_START and not row.get("j12_fixed"):', J12)
        # 순위 9 의 급락 3개 = 이 10종목의 급락 배점 위 3개(2026-10-15) · 그 순위 9 는 같이 쓰는 저장 기록에 안 적는다
        self.assertIn('rows": _crash12_top3(list(crash12.get("rows") or []))', J12)
        blend = J12[J12.index("def _blend_top7("):J12.index("def _render_top_reviewed(")]
        self.assertNotIn("picklist_ui.autosave(", blend)
        # 종목 하나를 급락 배점으로 심사하는 두 곳(날짜별 목록 · 종목검색)은 옛 계산 그대로 — 10개 밖도 심사된다
        self.assertEqual(2, J12.count("_find_scan_row(j3data.find_crash_rebound_stocks(), code)"))
        self.assertIn("2026-10-14 자비스12 그물", SPEC)
        # 성적표를 세기 시작한 날에 이미 끝난 급락(3월)은 빼고 그때 보여 주던 급락부터
        self.assertIn('str(row["episode_recovered"]) >= _SCORECARD_START', J12)
        # 경고 칸 붉은 숫자 — 다른 함수 안의 _red 를 부르다 깨지던 것
        self.assertEqual(2, J12.count('_crash_red(f"{float(drop):.1f}%")'))
        # 기간 첫날에 들고 있던 급락 10종목도 그 기간에 센다(막대 · 기간 고르기 · 견주기)
        self.assertEqual(4, J12.count("_crash12_rows_for("))  # 정의 · 막대 · 기간 고르기 · 견주기
        self.assertIn('rows += [{**row, "_span": label} for row in _crash12_rows_for(_scorecard_span_start(anchor, days))]', J12)

    def test_story_explains_the_situation(self):
        ns = {"jarvis12_crash": c12, "_ixic_note": lambda ref: ""}
        exec(J12[J12.index("def _crash12_story("):J12.index("def _render_rulebook_finder(")], ns)
        text = ns["_crash12_story"]({"armed": True, "reference_date": "2026-07-29", "reference_drop": -11.5,
                                     "recovered_on": "2026-09-22"}, -2.5, 10)
        for piece in ("2026-07-29 기준 10종목", "다음 급락이 올 때까지 이 종목 그대로", "한 번 산 것", "2026-09-22에 전고점"):
            self.assertIn(piece, text)
        self.assertIn("오늘은 이 자리가 없습니다", ns["_crash12_story"]({"armed": False}, None, 0))


if __name__ == "__main__":
    unittest.main()
