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
    """2026-10-21 밤 상하님 규칙 — 나스닥 고점일 종가부터 잰 낙폭 · 세 칸 · 20개 · 경고 없는 위 10개가 성적표."""

    def _frames(self, depths, high_first=None):
        days = pd.bdate_range("2025-01-01", periods=320)
        frames, members = {}, {}
        for i, depth in enumerate(depths):
            # 고점일(300번째 날) 종가 100 → 기준일(305번째 날) 100×depth → 오늘 ×1.3
            closes = np.r_[np.linspace(50, 100, 301), np.full(9, 100 * depth), np.full(10, 100 * depth * 1.3)]
            if high_first and i in high_first:
                closes[100] = 400.0       # 1년 최고가는 훨씬 앞 — 이 값은 쓰지 않는다(고점일 종가가 기준)
            frames[f"S{i:02d}"] = pd.DataFrame({"Open": closes, "High": closes, "Low": closes, "Close": closes,
                                                "Volume": 1e6 + i}, index=days)
            members[f"S{i:02d}"] = ["테마"]
        return days, frames, members

    def _pick(self, depths, nasdaq_drop=-7.0, high_first=None):
        days, frames, members = self._frames(depths, high_first)
        tickers = sorted(frames)
        seen = []

        def fake_score(row):
            seen.append(row["metrics"]["current"])
            return {"score": 100 - int(row["ticker"][1:])}

        with mock.patch.object(c12.j3, "US_LARGE_CAP_UNIVERSE", tickers), \
                mock.patch.object(c12.j3, "crash_rebound_score", side_effect=fake_score):
            picked, counts = c12._pick(frames, members, days[305].date(), days[300].date(), nasdaq_drop)
        return days, picked, counts, seen

    def test_drop_from_nasdaq_peak_day_three_bands_and_twenty(self):
        # 0~7 −15%(10~20칸) · 8~15 −25% · 16~23 −40% · 24 −5%(칸 밖) · 25 −60%(칸 밖)
        depths = [0.85] * 8 + [0.75] * 8 + [0.60] * 8 + [0.95, 0.40]
        days, picked, counts, seen = self._pick(depths, high_first={0})
        self.assertEqual({"d10": 8, "d20": 8, "d30": 8}, counts)
        self.assertEqual(20, len(picked))                                   # 점수 차례로 20개
        self.assertEqual([f"S{i:02d}" for i in range(20)], [row["ticker"] for row in picked])
        self.assertAlmostEqual(-15.0, picked[0]["judged_from_high_pct"])     # 1년 최고가(400) 아닌 고점일 종가(100)부터
        self.assertEqual(days[300].date().isoformat(), picked[0]["peak_date"])
        self.assertEqual("고점일 대비 -10~-20%", picked[0]["bucket_label"])
        self.assertEqual(81, picked[0]["hold_results"][0]["win_rate"])        # 새 칸 성적
        self.assertTrue(all(abs(v - 85) < 1e-6 or abs(v - 75) < 1e-6 or abs(v - 60) < 1e-6 for v in seen))
        self.assertEqual(days[306].date().isoformat(), picked[0]["buy_date"])
        self.assertAlmostEqual(85.0, picked[0]["buy_open"])
        self.assertAlmostEqual(30.0, picked[0]["since_reference_pct"], places=6)

    def test_three_times_nasdaq_is_flagged_and_scorecard_skips_it(self):
        # 나스닥 −7% → 21% 넘게 빠진 종목(−25 · −40)은 경고. 경고 없는 −15% 종목은 8개뿐 → 2개는 경고 종목으로 채움
        depths = [0.75] * 4 + [0.85] * 8 + [0.60] * 4
        _days, picked, _counts, _seen = self._pick(depths, nasdaq_drop=-7.0)
        flags = {row["ticker"]: row["suspicious"] for row in picked}
        self.assertTrue(flags["S00"])
        self.assertFalse(flags["S04"])
        chosen = [row["ticker"] for row in picked if row["scorecard"]]
        self.assertEqual(10, len(chosen))
        self.assertEqual({f"S{i:02d}" for i in range(4, 12)} | {"S00", "S01"}, set(chosen))   # S02·S03 은 빠짐
        # 점수는 경고와 상관없이 그대로 — 화면 차례도 점수 차례
        self.assertEqual([f"S{i:02d}" for i in range(16)], [row["ticker"] for row in picked])

    def test_drop_story_says_peak_day(self):
        _days, picked, _counts, _seen = self._pick([0.75], nasdaq_drop=-7.0)
        text = c12.drop_story(picked[0])
        self.assertIn("나스닥 고점일(", text)
        self.assertIn("-25.0% 빠졌던", text)
        self.assertIn("수상하게 빠짐", text)
        self.assertIsNone(c12.drop_story({"judged_from_high_pct": -20.0, "reference_date": "2026-07-29"}))

    def test_peak_day_is_the_52_week_intraday_high(self):
        closes = list(np.linspace(100, 130, 300)) + [120, 118, 125, 117]
        frame = _qqq(closes)
        frame.loc[frame.index[290], "High"] = 140.0                         # 장중 최고는 290번째 날
        days = [d.date().isoformat() for d in frame.index]
        peak = c12._peak_of(frame, days[303])
        self.assertEqual(days[290], peak["peak_date"])
        self.assertAlmostEqual((117 / float(frame["Close"].iloc[290]) - 1) * 100, peak["nasdaq_drop"])


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
        # 2026-10-21 — 화면 20개 · 성적표는 그중 scorecard 10개 · 세부 글은 나스닥 고점일부터
        self.assertIn('rows = [row for row in _crash12_cohort_rows() if row.get("scorecard", True)]', J12)
        self.assertIn("_REQUIRED_J12_CRASH_REVISION = 2026102101", J12)
        self.assertEqual(c12.MODULE_REVISION, 2026102101)
        self.assertIn("story12 = jarvis12_crash.drop_story(row)", J12)
        self.assertIn('drop_heads[0] = "고점일 대비"', J12)
        self.assertIn("⚠ 수상하게 빠짐", J12)
        self.assertIn("2026-10-21 밤 고침", SPEC)

    def test_tildes_do_not_turn_into_strikethrough_and_the_warning_stacks(self):
        """2026-10-21 상하님 캡처 — 「10~20%·20~30%」 물결 둘이 짝을 지어 취소선이 됐고, 갈래 칸의 경고가 옆으로 붙어 잘렸다."""
        import re
        ns = {"jarvis12_crash": c12, "_ixic_note": lambda ref: ""}
        exec(J12[J12.index("def _crash12_story("):J12.index("def _render_rulebook_finder(")], ns)
        text = ns["_crash12_story"]({"armed": True, "reference_date": "2026-10-16", "reference_drop": -7.0,
                                     "peak_date": "2026-10-06", "nasdaq_drop": -6.6}, -4.7, 20)
        self.assertIn("10\\~20%", text)
        self.assertIsNone(re.search(r"(?<!\\)~[0-9]", text))       # 숫자 앞 물결은 모두 \~
        band = J12[J12.index("if row.get(\"suspicious\"):"):J12.index("# 순위를 정한 값(테마 동반)")]
        self.assertIn("flex-direction:column", band)
        self.assertNotIn('"<br>', band)                                  # 그리는 글에 줄바꿈 태그 없음


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
