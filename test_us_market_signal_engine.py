"""미국장 시장 상태·흐름 판독 엔진 테스트.

한국장 항목이 미국장에 새어들어오지 않는지도 같이 본다.
"""

import unittest
from datetime import datetime, timedelta

import us_market_signal_engine as us
from market_signal_common import SignalStatus, SignalTiming
from us_market_signal_engine import UsMarketVerdict

NOW = datetime(2026, 7, 20, 22, 30)


def _quotes(**by_ticker):
    """티커별 등락률만 주면 as_of는 방금 것으로 채운다."""
    return {
        ticker: {"change_pct": pct, "as_of": NOW - timedelta(seconds=30), "source": "테스트"}
        for ticker, pct in by_ticker.items()
    }


def _risk_on_quotes(**overrides):
    base = {
        "ES=F": 0.8, "NQ=F": 1.2, "SOXX": 1.5, "SMH": 1.4,
        "NVDA": 2.0, "TSLA": 1.0,
        "^VIX": -4.0, "^TNX": -0.5, "DX-Y.NYB": -0.2,
        "^GSPC": 0.9, "^IXIC": 1.1,
    }
    base.update(overrides)
    return _quotes(**base)


class VerdictTest(unittest.TestCase):
    def test_risk_on_when_futures_and_semis_up_with_calm_vix(self):
        result = us.build_us_market_signal_result(_risk_on_quotes(), now=NOW)
        self.assertIs(result.verdict, UsMarketVerdict.RISK_ON)

    def test_risk_on_early_when_vix_pushes_back(self):
        result = us.build_us_market_signal_result(
            _risk_on_quotes(**{"^VIX": 3.0}), now=NOW
        )
        self.assertIs(result.verdict, UsMarketVerdict.RISK_ON_EARLY)

    def test_risk_on_early_when_only_semis_lead(self):
        result = us.build_us_market_signal_result(
            _risk_on_quotes(**{"ES=F": -0.5, "NQ=F": 0.0}), now=NOW
        )
        self.assertIs(result.verdict, UsMarketVerdict.RISK_ON_EARLY)
        self.assertIn("반도체", result.headline)

    def test_risk_off_on_vix_spike_with_futures_down(self):
        result = us.build_us_market_signal_result(
            _risk_on_quotes(**{"ES=F": -1.0, "NQ=F": -1.4, "^VIX": 9.0}), now=NOW
        )
        self.assertIs(result.verdict, UsMarketVerdict.RISK_OFF)
        self.assertIn("VIX 급등", result.headline)

    def test_risk_off_when_futures_and_semis_fall_together(self):
        result = us.build_us_market_signal_result(
            _risk_on_quotes(**{
                "ES=F": -0.9, "NQ=F": -1.1, "SOXX": -1.5, "SMH": -1.6, "^VIX": 1.0,
            }),
            now=NOW,
        )
        self.assertIs(result.verdict, UsMarketVerdict.RISK_OFF)

    def test_mixed_when_nothing_aligns(self):
        result = us.build_us_market_signal_result(
            _quotes(**{
                "ES=F": 0.0, "NQ=F": 0.1, "SOXX": -0.1, "SMH": 0.0,
                "^VIX": 0.5, "^TNX": 0.2, "DX-Y.NYB": 0.0,
                "NVDA": 0.0, "TSLA": 0.0, "^GSPC": 0.0, "^IXIC": 0.0,
            }),
            now=NOW,
        )
        self.assertIs(result.verdict, UsMarketVerdict.MIXED)

    def test_insufficient_data_when_core_missing(self):
        result = us.build_us_market_signal_result({}, now=NOW)
        self.assertIs(result.verdict, UsMarketVerdict.INSUFFICIENT_DATA)

    def test_stale_core_data_blocks_risk_on(self):
        stale = {
            ticker: {"change_pct": pct, "as_of": NOW - timedelta(minutes=20), "source": "테스트"}
            for ticker, pct in {
                "ES=F": 0.8, "NQ=F": 1.2, "SOXX": 1.5, "SMH": 1.4,
                "^VIX": -4.0, "^TNX": -0.5,
            }.items()
        }
        result = us.build_us_market_signal_result(stale, now=NOW)
        self.assertIs(result.verdict, UsMarketVerdict.INSUFFICIENT_DATA)


class FakeSignalTest(unittest.TestCase):
    def test_nq_only_rally_warns(self):
        result = us.build_us_market_signal_result(
            _risk_on_quotes(**{"SOXX": -1.2, "SMH": -1.0}), now=NOW
        )
        self.assertTrue(any("반도체가 따라오지 않는" in w for w in result.warnings))

    def test_nvda_alone_warns(self):
        result = us.build_us_market_signal_result(
            _risk_on_quotes(**{"SOXX": -1.2, "SMH": -1.0, "NVDA": 3.0}), now=NOW
        )
        self.assertTrue(any("NVDA만" in w for w in result.warnings))

    def test_index_up_with_vix_spike_warns(self):
        result = us.build_us_market_signal_result(
            _risk_on_quotes(**{"^VIX": 8.0}), now=NOW
        )
        self.assertTrue(any("VIX가 급등" in w or "동시에 급등" in w for w in result.warnings))

    def test_thin_premarket_warns_only_when_confirmed(self):
        quotes = _risk_on_quotes()
        no_flag = us.build_us_market_signal_result(quotes, now=NOW, extras={})
        self.assertEqual([w for w in no_flag.warnings if "거래량이 얇" in w], [])
        flagged = us.build_us_market_signal_result(
            quotes, now=NOW, extras={"premarket_volume_thin": True}
        )
        self.assertTrue(any("거래량이 얇" in w for w in flagged.warnings))


class UnknownAndSeparationTest(unittest.TestCase):
    def test_missing_change_pct_is_unknown_not_zero(self):
        result = us.build_us_market_signal_result(
            _quotes(**{"ES=F": 0.8, "NQ=F": 1.2, "SOXX": 1.5, "SMH": 1.4, "^VIX": -1.0}),
            now=NOW,
        )
        tnx = result.signal("US_TNX")
        self.assertIs(tnx.status, SignalStatus.UNKNOWN)
        self.assertIsNone(tnx.value)

    def test_no_korean_signals_leak_into_us(self):
        result = us.build_us_market_signal_result(_risk_on_quotes(), now=NOW)
        keys = [s.key for s in result.signals]
        labels = [s.label for s in result.signals]
        self.assertTrue(all(k.startswith("US_") for k in keys), keys)
        for banned in ("프로그램", "금융투자", "투신", "연기금", "베이시스", "비차익", "외국인"):
            self.assertFalse(
                any(banned in label for label in labels),
                f"미국장에 한국장 항목 '{banned}'이 들어왔습니다: {labels}",
            )

    def test_kr_and_us_signal_keys_do_not_collide(self):
        import kr_intraday_flow as kr

        us_keys = {s.key for s in us.build_us_market_signal_result(_risk_on_quotes(), now=NOW).signals}
        kr_keys = set(kr.CORE_KEYS) | {"program_total", "non_arbitrage", "market_basis"}
        self.assertEqual(us_keys & kr_keys, set())

    def test_headline_has_no_action_instruction(self):
        """시장 상태를 읽어주는 카드다. 사라/사지마라를 말하지 않는다."""
        for quotes in (_risk_on_quotes(), _risk_on_quotes(**{"ES=F": -1.0, "NQ=F": -1.4, "^VIX": 9.0})):
            result = us.build_us_market_signal_result(quotes, now=NOW)
            for banned in ("매수", "매도", "사도", "사지", "진입하", "담아도"):
                self.assertNotIn(banned, result.headline, result.headline)

    def test_flow_note_describes_leading_vs_confirming(self):
        result = us.build_us_market_signal_result(_risk_on_quotes(), now=NOW)
        self.assertTrue(result.flow_note)
        self.assertIn("선행", result.flow_note)


class TimingTest(unittest.TestCase):
    def test_futures_and_semis_are_leading_indices_are_confirming(self):
        result = us.build_us_market_signal_result(_risk_on_quotes(), now=NOW)
        self.assertIs(result.signal("US_NQ_FUTURES").timing, SignalTiming.LEADING)
        self.assertIs(result.signal("US_SOXX").timing, SignalTiming.LEADING)
        self.assertIs(result.signal("US_SP500").timing, SignalTiming.CONFIRMING)


class FlowProxyTest(unittest.TestCase):
    """미국 장중 수급 원자료가 없어서 쓰는 무료 대체신호(HYG·VIX 기간구조) 검증."""

    def test_hyg_is_a_leading_signal_in_specs(self):
        keys = {spec[0]: spec for spec in us.US_SIGNAL_SPECS}
        self.assertIn("US_HYG", keys)
        self.assertEqual(keys["US_HYG"][2], "HYG")
        self.assertIs(keys["US_HYG"][3], SignalTiming.LEADING)

    def test_vix_term_contango_is_positive_proxy(self):
        signal = us.build_vix_term_signal(17.0, 20.0)
        self.assertIs(signal.status, SignalStatus.POSITIVE)
        self.assertEqual(signal.key, "US_VIX_TERM")
        self.assertEqual(signal.strength.value, "proxy")

    def test_vix_term_backwardation_is_negative(self):
        signal = us.build_vix_term_signal(24.0, 20.0)
        self.assertIs(signal.status, SignalStatus.NEGATIVE)
        self.assertIn("역전", signal.reason)

    def test_vix_term_flat_zone_is_neutral(self):
        signal = us.build_vix_term_signal(19.6, 20.0)
        self.assertIs(signal.status, SignalStatus.NEUTRAL)

    def test_vix_term_missing_data_stays_unknown_not_zero(self):
        signal = us.build_vix_term_signal(None, 20.0)
        self.assertIs(signal.status, SignalStatus.UNKNOWN)
        self.assertIsNone(signal.value)

    def test_result_includes_vix_term_signal_from_extras(self):
        result = us.build_us_market_signal_result(
            _risk_on_quotes(), now=NOW,
            extras={"vix_current": 17.0, "vix3m_current": 20.0},
        )
        term = result.signal("US_VIX_TERM")
        self.assertIsNotNone(term)
        self.assertIs(term.status, SignalStatus.POSITIVE)

    def test_result_without_extras_reports_term_unknown(self):
        result = us.build_us_market_signal_result(_risk_on_quotes(), now=NOW)
        term = result.signal("US_VIX_TERM")
        self.assertIsNotNone(term)
        self.assertIs(term.status, SignalStatus.UNKNOWN)

    def test_index_up_with_backwardation_warns_hedged_rally(self):
        result = us.build_us_market_signal_result(
            _risk_on_quotes(), now=NOW,
            extras={"vix_current": 24.0, "vix3m_current": 20.0},
        )
        self.assertTrue(any("기간구조" in warning for warning in result.warnings))


if __name__ == "__main__":
    unittest.main()
