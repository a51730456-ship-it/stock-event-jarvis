"""자비스13 「📘 이 테마 설명」 짧은 글 (2026-11-04 저녁 상하님 「한국테마 설명이 너무 길다 · 간단히 · 현실과 맞냐?」)."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import jarvis4_data as j4
import jarvis13_crash_record
import jarvis13_help as hp
import method_help

ROOT = Path(__file__).resolve().parent


def _plain(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


class HelpTests(unittest.TestCase):
    def test_short_text_is_much_shorter(self):
        short = len(_plain(hp.short_html()))
        old = len(_plain(jarvis13_crash_record.help_text(method_help.KR_TEXT)))
        self.assertLess(short, old * 0.5, (short, old))                      # 절반 밑

    def test_numbers_match_what_the_app_uses(self):
        text = hp.short_html()
        for piece in ("50억↑", "3~10일", "−4~−6%", "250거래일", "15%↓", "−40~−60%", "20거래일",
                      "시장 50↑", "테마 60↑", "종목 70↑", f"종목 {j4.STRONG_STOCK_OVERRIDE:.0f}↑면 테마 안 봄"):
            self.assertIn(piece, text)
        self.assertIn(jarvis13_crash_record.holds_line(), text)              # 급락 성적은 한 곳에서 읽는다
        page = (ROOT / "jarvis4_data.py").read_text(encoding="utf-8")
        self.assertIn("gates_ok = market_score >= 50 and theme_ok and score >= 70", page)
        self.assertIn("theme_ok = theme_score >= 60 or score >= STRONG_STOCK_OVERRIDE", page)

    def test_flow_is_said_to_be_zero_points(self):
        self.assertIn("점수 0점", hp.short_html())
        self.assertIn(hp.OLD_FLOW_LINE, method_help.KR_TEXT)                  # 얼린 글에서 그 줄을 정확히 찾는다
        old = hp.old_html(method_help.KR_TEXT)
        self.assertNotIn("종목 점수 100점 중 <b>20점</b>으로 넣었습니다", old)
        self.assertIn("점수는 0점", old)

    def test_old_text_is_folded_not_deleted(self):
        out = hp.help_html(method_help.KR_TEXT)
        self.assertIn("<details class='j13hp-old'>", out)
        self.assertIn("한국장 눌림목 매매 설명서", out)
        self.assertNotIn("승률 66.6%", out)                                     # 급락 옛 숫자는 계속 바로잡힌 채

    def test_page_uses_it(self):
        page = (ROOT / "pages" / "12_자비스13.py").read_text(encoding="utf-8")
        self.assertIn("jarvis13_help.help_html(method_help.KR_TEXT)", page)
        self.assertNotIn("j12", hp.CSS)


if __name__ == "__main__":
    unittest.main()
