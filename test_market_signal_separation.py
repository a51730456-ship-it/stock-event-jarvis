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
    def test_verdict_enums_are_distinct(self):
        # 두 시장의 판정명이 같은 enum이면 조건이 섞인다.
        self.assertIsNot(kr.ReboundVerdict, us.UsMarketVerdict)
        kr_values = {v.value for v in kr.ReboundVerdict}
        us_values = {v.value for v in us.UsMarketVerdict}
        # insufficient_data만 겹치는 건 의도된 공통 개념이다.
        self.assertEqual(kr_values & us_values, {"insufficient_data"})

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
        self.assertIn("확인 신호는 아직 없습니다", common.flow_reading(signals))

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


if __name__ == "__main__":
    unittest.main()
