"""한국 급락 「그림자 목록」 저장 (2026-10-31 상하님 「라 로 해라」) — 재기와 같은 셈으로 고르는지 · 신호 난 날만 쓰는지."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "research"))
_SPEC = importlib.util.spec_from_file_location("j13_shadow_collect", ROOT / "research" / "j13_shadow_collect.py")
shadow = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(shadow)
rm = shadow.rm


def _cut(wide, idx, upto: int):
    """upto 번째 날까지만 남긴다 — 그날 저녁에 돌린 것과 같다."""
    return ({key: frame.iloc[:upto + 1] for key, frame in wide.items()},
            {name: frame.iloc[:upto + 1] for name, frame in idx.items()})


class ShadowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wide, cls.idx, cls.meta, _note = rm.load_fake()
        cls.env = rm.prepare(cls.wide, cls.idx)
        cls.eps = rm.episodes(cls.env, shadow.THRESHOLD)
        cls.episode = next(e for e in cls.eps if len(e["lows"]) >= 2 and len(e["zone"]) > len(e["lows"]))

    def _decide_at(self, day: int) -> dict:
        wide, idx = _cut(self.wide, self.idx, day)
        return shadow.decide(rm.prepare(wide, idx), self.meta)

    def test_a_new_low_day_picks_the_same_stocks_as_the_remeasure(self):
        day = self.episode["lows"][1]
        result = self._decide_at(day)
        self.assertTrue(result["phase"])
        self.assertTrue(result["signal"])
        # 재기(evaluate)와 같은 고르기 — 그날 사는 칸(다음 날 시가)만 빼고 그대로
        env = self.env
        dd = rm.stock_dd(env, "kpeak", day)
        with np.errstate(invalid="ignore"):
            cand = env["pool_np"][day] & (dd <= -0.50) & (dd >= -0.80) & ~env["bad_np"][day] & ~(env["ret11_np"][day] > 0.05)
        expected = {list(env["codes"])[i] for i in np.where(cand)[0]}
        self.assertEqual(expected, {row["code"] for row in result["rows"]})
        self.assertEqual(len(expected), result["count"])
        self.assertTrue(all(-80 <= row["dd_from_kospi_peak_pct"] <= -50 for row in result["rows"]))

    def test_a_day_inside_the_phase_but_not_a_new_low_saves_nothing(self):
        day = next(p for p in self.episode["zone"] if p not in self.episode["lows"])
        result = self._decide_at(day)
        self.assertTrue(result["phase"])
        self.assertFalse(result["signal"])
        self.assertIsNone(shadow.save(result, Path(tempfile.mkdtemp())))

    def test_outside_a_phase_saves_nothing(self):
        day = self.episode["start"] - 30
        result = self._decide_at(day)
        self.assertFalse(result["phase"])
        self.assertFalse(result["signal"])

    def test_save_writes_once_and_never_overwrites(self):
        result = self._decide_at(self.episode["lows"][1])
        folder = Path(tempfile.mkdtemp())
        first = shadow.save(result, folder)
        self.assertIsNotNone(first)
        saved = json.loads(first.read_text(encoding="utf-8"))
        self.assertEqual("j13-shadow-v1", saved["rule"])
        self.assertEqual(result["date"], saved["date"])
        self.assertIn("코스피 1년 최고 종가 −15% 아래 국면", saved["rule_text"])
        self.assertIsNone(shadow.save({**result, "count": 0, "rows": []}, folder))   # 그날 처음 적은 것이 기록이다
        self.assertEqual(result["count"], json.loads(first.read_text(encoding="utf-8"))["count"])

    def test_the_rule_is_the_one_written_in_the_spec(self):
        spec = (ROOT / "docs" / "KR_THEME_SPEC.md").read_text(encoding="utf-8")
        self.assertTrue("j13-shadow-v1" in spec, "설명서 3-4-1 에 그림자 목록 규칙 이름이 없다")   # 설명서에 적은 규칙 그대로
        self.assertTrue("−50~−80%" in spec and "새 바닥" in spec, "설명서의 규칙 글이 다르다")
        self.assertEqual((-0.80, -0.50), shadow.BAND)
        self.assertEqual(-0.15, shadow.THRESHOLD)


if __name__ == "__main__":
    unittest.main()
