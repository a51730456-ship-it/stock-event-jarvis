"""한국장·미국장 카드가 서로 섞이지 않는지 확인한다.

공통화한 것은 상태값·신선도·카드 모양뿐이고, 판정 기준과 신호 항목은
시장별로 분리돼 있어야 한다.
"""

import unittest

import kr_intraday_flow as kr
import market_signal_common as common
import us_market_signal_engine as us


class CommonLayerTest(unittest.TestCase):
    def test_kr_reuses_common_types_not_its_own_copy(self):
        # KR이 공통 타입을 재정의하면 두 시장의 상태값이 갈라진다.
        self.assertIs(kr.SignalStatus, common.SignalStatus)
        self.assertIs(kr.SignalTiming, common.SignalTiming)
        self.assertIs(kr.FlowSignal, common.MarketSignal)

    def test_us_reuses_common_types(self):
        self.assertIs(us.SignalStatus, common.SignalStatus)
        self.assertIs(us.SignalTiming, common.SignalTiming)

    def test_freshness_thresholds_are_shared(self):
        for seconds, expected in ((0, "정상"), (200, "지연"), (999, "오래됨"), (None, "확인 필요")):
            self.assertEqual(common.freshness_label(seconds), expected)

    def test_unknown_never_becomes_zero_in_either_engine(self):
        kr_sig = kr.evaluate_investor("fund", "기금·연기금", None, [])
        us_sig = us.build_us_signal(
            "US_VIX", "VIX", None, common.SignalTiming.LEADING, True
        )
        for sig in (kr_sig, us_sig):
            self.assertIs(sig.status, common.SignalStatus.UNKNOWN)
            self.assertIsNone(sig.value)


class VerdictSeparationTest(unittest.TestCase):
    # 두 시장이 **일부러 같이 쓰는** 판정값. 여기 없는 값이 겹치면 조건이 섞인 것이다.
    #   · insufficient_data — 처음부터 공통 개념이었다.
    #   · very_bad — 2026-08-04 「시장 상태 5단계」에서 상하님이 두 시장에 같이 넣으셨다.
    #     이름표도 둘 다 "● 하락 압력 큼"이다("계기판 단계명은 한국장·미국장이 같은
    #     쉬운 말로 쓴다", us_market_signal_engine.py 주석).
    # **판정값을 새로 같이 쓰기로 하면 여기에 적는다.** 안 적으면 이 시험이 막는다 —
    # 그것이 이 시험이 하는 일이다(2026-08-15에 very_bad가 안 적혀 있어 깨져 있었다).
    SHARED_VERDICTS = {"insufficient_data", "very_bad"}

    def test_verdict_enums_are_distinct(self):
        # 두 시장의 판정을 **같은 enum 하나로** 쓰면 조건이 섞인다. 값이 몇 개
        # 겹치는 것과 클래스가 하나인 것은 다른 이야기다.
        self.assertIsNot(kr.ReboundVerdict, us.UsMarketVerdict)
        kr_values = {v.value for v in kr.ReboundVerdict}
        us_values = {v.value for v in us.UsMarketVerdict}
        self.assertEqual(kr_values & us_values, self.SHARED_VERDICTS)
        # 같이 쓰기로 한 값은 **이름표도 같아야 한다** — 같은 말이 두 화면에서
        # 다르게 읽히면 같이 쓰는 뜻이 없다.
        for value in self.SHARED_VERDICTS:
            self.assertEqual(kr.VERDICT_LABEL[kr.ReboundVerdict(value)],
                             us.VERDICT_LABEL[us.UsMarketVerdict(value)], value)

    def test_verdict_labels_do_not_mix_market_vocabulary(self):
        kr_labels = " ".join(kr.VERDICT_LABEL.values())
        us_labels = " ".join(us.VERDICT_LABEL.values())
        self.assertNotIn("위험선호", kr_labels)
        self.assertNotIn("기관성", us_labels)

    def test_no_shared_build_function_with_market_branching(self):
        # build_market_signal_result(market) 같은 거대 분기 함수를 만들지 않는다.
        self.assertFalse(hasattr(common, "build_market_signal_result"))
        self.assertTrue(hasattr(us, "build_us_market_signal_result"))
        self.assertTrue(hasattr(kr, "build_result_from_snapshots"))

    def test_us_engine_has_no_kis_dependency(self):
        import inspect

        source = inspect.getsource(us)
        for banned in ("kis_market_data", "parse_kis_number", "프로그램", "비차익", "베이시스"):
            self.assertNotIn(banned, source.split('"""')[2] if source.count('"""') > 2 else source,
                             f"미국장 엔진에 한국장 요소 '{banned}'")


class HeadlineToneTest(unittest.TestCase):
    """시장 상태 판독기다. 행동 지시를 내리지 않는다."""

    BANNED = ("매수 자리", "매수하", "매도하", "사도 됩", "사지 마", "진입하세")

    def test_kr_headlines_have_no_action_instruction(self):
        import inspect

        source = inspect.getsource(kr.decide_verdict) + inspect.getsource(kr._watching_headline)
        for banned in self.BANNED:
            self.assertNotIn(banned, source, f"한국장 결론에 행동 지시 '{banned}'")

    def test_us_headlines_have_no_action_instruction(self):
        import inspect

        source = inspect.getsource(us.build_us_market_signal_result)
        for banned in self.BANNED:
            self.assertNotIn(banned, source, f"미국장 결론에 행동 지시 '{banned}'")


class FlowReadingTest(unittest.TestCase):
    def test_leading_only_is_called_out(self):
        signals = [
            common.MarketSignal("a", "A", common.SignalStatus.POSITIVE, timing=common.SignalTiming.LEADING),
            common.MarketSignal("b", "B", common.SignalStatus.NEGATIVE, timing=common.SignalTiming.CONFIRMING),
        ]
        self.assertIn("뒤따라오는 신호는 아직 없습니다", common.flow_reading(signals))

    def test_confirming_without_leading_is_flagged_as_late(self):
        signals = [
            common.MarketSignal("b", "B", common.SignalStatus.POSITIVE, timing=common.SignalTiming.CONFIRMING),
        ]
        self.assertIn("뒤늦은", common.flow_reading(signals))

    def test_late_only_is_flagged(self):
        signals = [
            common.MarketSignal("c", "C", common.SignalStatus.POSITIVE, timing=common.SignalTiming.LATE),
        ]
        self.assertIn("지나간", common.flow_reading(signals))


class PlainWordingTest(unittest.TestCase):
    """2026-07-29: 화면 용어가 뜻을 설명해야만 알 수 있는 말이면 안 된다.

    직접·대체·그대로·대신·신선도·보합은 전부 사용자가 "무슨 말이냐"고 되물은
    말이다. 다시 기어들어오지 않게 막는다.
    """

    BANNED = ("신선도", "보합", "선행", "신호세기", "긍정", "부정")

    def test_banned_jargon_is_gone_from_table_words(self):
        import market_signal_ui as ui

        shown = list(ui._STATUS_TEXT.values())
        shown += list(common.TIMING_LABEL.values())
        shown += [ui._SIGNAL_TABLE_LEGEND_HTML]
        for word in self.BANNED:
            for text in shown:
                self.assertNotIn(word, text, f"화면에 '{word}'가 남아 있다")

    def test_flow_reading_uses_plain_words(self):
        signals = [
            common.MarketSignal("a", "A", common.SignalStatus.POSITIVE,
                                timing=common.SignalTiming.LEADING),
            common.MarketSignal("b", "B", common.SignalStatus.POSITIVE,
                                timing=common.SignalTiming.CONFIRMING),
        ]
        text = common.flow_reading(signals)
        self.assertIn("먼저 움직이는 신호", text)
        self.assertNotIn("선행", text)
        self.assertNotIn("확인 신호", text)

    def test_freshness_says_actual_minutes(self):
        self.assertEqual(common.freshness_text(None), "모름")
        self.assertEqual(common.freshness_text(0), "방금")
        self.assertEqual(common.freshness_text(59), "방금")
        self.assertEqual(common.freshness_text(180), "3분 전")
        self.assertEqual(common.freshness_text(7 * 60), "7분 전")
        self.assertEqual(common.freshness_text(3 * 3600), "3시간 전")

    def test_source_word_names_the_actual_place(self):
        def sig(source):
            return common.MarketSignal("k", "L", common.SignalStatus.UNKNOWN, source=source)

        self.assertEqual(common.source_word(sig("KIS")), "증권사")
        self.assertEqual(common.source_word(sig("네이버 선물 투자자동향(지연)")), "네이버")
        self.assertEqual(common.source_word(sig("HTS 수동 입력")), "HTS 입력")
        self.assertEqual(common.source_word(sig("가격 스냅샷")), "네이버 시세")
        self.assertEqual(common.source_word(sig("미연결")), "없음")
        self.assertEqual(common.source_word(sig("")), "없음")

    def test_crashing_stock_is_not_called_flat(self):
        """-12%인 종목에 '보합'이라 적던 사고를 막는다."""
        import market_signal_ui as ui

        neutral = ui._STATUS_TEXT[common.SignalStatus.NEUTRAL]
        self.assertNotIn("보합", neutral)
        self.assertEqual(neutral, "애매")

    def test_every_status_word_has_a_color(self):
        """글자를 바꾸고 색 표를 안 고치면 화면이 회색으로 죽는다."""
        import market_signal_ui as ui

        for timing in common.SignalTiming:
            if timing is common.SignalTiming.FAKE:
                continue
            self.assertIn(common.TIMING_LABEL[timing], ui._TIMING_COLOR)
        for word in ("증권사", "네이버", "HTS 입력", "네이버 시세", "없음"):
            self.assertIn(word, ui._SOURCE_COLOR)


if __name__ == "__main__":
    unittest.main()
