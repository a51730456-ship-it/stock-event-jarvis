"""한국장 장중 기관 수급 반전 엔진 판정 테스트.

핵심 회귀 방지 대상:
- UNKNOWN이 FALSE/0으로 바뀌지 않는지
- 외국인 선물 직접값 유무로 CONFIRMED와 PROXY_CONFIRMED가 갈리는지
- 비차익 15분 판정이 누적값이 아니라 증분으로 되는지
"""

import unittest
from datetime import datetime, timedelta

import kr_intraday_flow as flow
from kr_intraday_flow import (
    ForeignFuturesFlowSnapshot,
    ReboundVerdict,
    SignalStatus,
)


BASE = datetime(2026, 7, 20, 10, 0)


def _ts(minutes):
    return BASE + timedelta(minutes=minutes)


class ParseNumberTest(unittest.TestCase):
    def test_comma_and_sign(self):
        self.assertEqual(flow.parse_kis_number("1,234,567"), 1234567.0)
        self.assertEqual(flow.parse_kis_number("-3,250"), -3250.0)
        self.assertEqual(flow.parse_kis_number("+1,000"), 1000.0)

    def test_missing_is_none_not_zero(self):
        for value in ("", "-", "--", None, "N/A", "  "):
            self.assertIsNone(flow.parse_kis_number(value), f"{value!r} should be None")

    def test_zero_stays_zero(self):
        # 실제로 0원이 확인된 경우는 0이어야 한다. None과 구분된다.
        self.assertEqual(flow.parse_kis_number("0"), 0.0)

    def test_garbage_is_none(self):
        self.assertIsNone(flow.parse_kis_number("abc"))
        self.assertIsNone(flow.parse_kis_number(True))


class SectorLookupTest(unittest.TestCase):
    def test_finds_electronics_by_name_variants(self):
        rows = [
            {"bstp_cls_code": "0002", "hts_kor_isnm": "음식료품"},
            {"bstp_cls_code": "0013", "hts_kor_isnm": "전기·전자"},
        ]
        self.assertEqual(flow.find_electronics_sector_code(rows), "0013")

    def test_returns_none_when_absent(self):
        # 못 찾으면 코드를 추측하지 않는다.
        self.assertIsNone(flow.find_electronics_sector_code([{"hts_kor_isnm": "화학"}]))
        self.assertIsNone(flow.find_electronics_sector_code([]))


class NonArbitrageTest(unittest.TestCase):
    def test_15min_continuous_inflow_is_positive(self):
        history = [(_ts(0), 100.0), (_ts(5), 200.0), (_ts(10), 350.0), (_ts(15), 500.0)]
        sig = flow.evaluate_non_arbitrage(history, current_net=500.0)
        self.assertIs(sig.status, SignalStatus.POSITIVE)

    def test_rising_cumulative_but_short_span_is_neutral(self):
        # 누적값만 보면 늘었지만 15분이 안 됐다. POSITIVE로 새면 안 된다.
        history = [(_ts(0), 100.0), (_ts(3), 200.0), (_ts(6), 300.0), (_ts(9), 400.0)]
        sig = flow.evaluate_non_arbitrage(history, current_net=400.0)
        self.assertIs(sig.status, SignalStatus.NEUTRAL)

    def test_cumulative_positive_but_last_delta_negative(self):
        # 누적 순매수는 +500이지만 최근 구간은 유출이다. 증분으로 봐야 잡힌다.
        history = [(_ts(0), 800.0), (_ts(5), 700.0), (_ts(10), 600.0), (_ts(15), 500.0)]
        sig = flow.evaluate_non_arbitrage(history, current_net=500.0)
        self.assertIs(sig.status, SignalStatus.NEGATIVE)

    def test_single_snapshot_is_unknown(self):
        sig = flow.evaluate_non_arbitrage([(_ts(0), 100.0)], current_net=100.0)
        self.assertIs(sig.status, SignalStatus.UNKNOWN)
        self.assertIn("부족", sig.reason)


class StockReboundTest(unittest.TestCase):
    def test_open_recovered_is_positive(self):
        sig = flow.evaluate_stock_rebound(
            "samsung", "삼성전자", {"current": 71000, "open": 70500, "low": 69000}
        )
        self.assertIs(sig.status, SignalStatus.POSITIVE)

    def test_low_recovery_above_threshold(self):
        sig = flow.evaluate_stock_rebound(
            "hynix", "SK하이닉스", {"current": 100900, "open": 102000, "low": 100000}
        )
        self.assertIs(sig.status, SignalStatus.POSITIVE)

    def test_new_low_overrides_open_recovery(self):
        sig = flow.evaluate_stock_rebound(
            "samsung",
            "삼성전자",
            {"current": 71000, "open": 70500, "low": 69000},
            recent_lows=[70000, 69500, 69000],
        )
        self.assertIs(sig.status, SignalStatus.NEGATIVE)
        self.assertIn("저점 재갱신", sig.reason)

    def test_missing_price_is_unknown(self):
        sig = flow.evaluate_stock_rebound("samsung", "삼성전자", {"current": None, "open": 1, "low": 1})
        self.assertIs(sig.status, SignalStatus.UNKNOWN)


class ForeignFuturesTest(unittest.TestCase):
    def test_unconnected_is_unknown_not_zero(self):
        sig = flow.evaluate_foreign_futures(None)
        self.assertIs(sig.status, SignalStatus.UNKNOWN)
        self.assertIsNone(sig.value)
        self.assertEqual(sig.display_value, "확인 필요")

    def test_manual_input_net_buy_is_positive(self):
        snap = ForeignFuturesFlowSnapshot(
            net_contracts=1200, previous_net_contracts=-300, as_of=BASE,
            source="HTS", available=True,
        )
        self.assertIs(flow.evaluate_foreign_futures(snap).status, SignalStatus.POSITIVE)

    def test_shrinking_net_sell_is_positive(self):
        snap = ForeignFuturesFlowSnapshot(
            net_contracts=-1000, previous_net_contracts=-3250, as_of=BASE,
            source="HTS", available=True,
        )
        self.assertIs(flow.evaluate_foreign_futures(snap).status, SignalStatus.POSITIVE)


def _snapshot(minutes, **overrides):
    row = {
        "captured_at": _ts(minutes).isoformat(),
        "non_arbitrage_net_amount": None,
        "arbitrage_net_amount": None,
        "program_net_amount": None,
        "futures_market_basis": None,
        "samsung_price": None,
        "samsung_open": None,
        "samsung_day_low": None,
        "hynix_price": None,
        "hynix_open": None,
        "hynix_day_low": None,
        "institution_cash_net_amount": None,
        "securities_net_amount": None,
        "investment_trust_net_amount": None,
        "private_fund_net_amount": None,
        "fund_net_amount": None,
        "foreign_cash_net_amount": None,
        "personal_cash_net_amount": None,
        "electronics_turnover": None,
        "electronics_institution_net": None,
    }
    row.update(overrides)
    return row


def _rebound_snapshots():
    """비차익 15분 유입 + 베이시스 개선 + 반도체 동시 반등 상태."""
    return [
        _snapshot(
            m,
            non_arbitrage_net_amount=100.0 * (i + 1),
            arbitrage_net_amount=50.0 * (i + 1),
            program_net_amount=150.0 * (i + 1),
            futures_market_basis=-0.6 + 0.2 * i,
            samsung_price=70000 + 200 * i,
            samsung_open=70100,
            samsung_day_low=69500,
            hynix_price=100000 + 500 * i,
            hynix_open=100200,
            hynix_day_low=99000,
            institution_cash_net_amount=100.0 * (i + 1),
            securities_net_amount=80.0 * (i + 1),
            electronics_turnover=1000.0 + 100 * i,
        )
        for i, m in enumerate((0, 5, 10, 15))
    ]


class VerdictTest(unittest.TestCase):
    def test_confirmed_requires_direct_foreign_futures(self):
        result = flow.build_result_from_snapshots(
            _rebound_snapshots(),
            foreign_futures=ForeignFuturesFlowSnapshot(
                net_contracts=800, previous_net_contracts=-1200,
                as_of=_ts(15), source="HTS", available=True,
            ),
            now=_ts(16),
        )
        self.assertIs(result.verdict, ReboundVerdict.CONFIRMED)

    def test_proxy_confirmed_when_futures_unknown(self):
        result = flow.build_result_from_snapshots(
            _rebound_snapshots(), foreign_futures=None, now=_ts(16)
        )
        self.assertIs(result.verdict, ReboundVerdict.PROXY_CONFIRMED)
        self.assertIn("대체", result.verdict_label)
        # 대체판정을 "확인"이라고 쓰면 안 된다.
        self.assertNotIn("반등 확인", result.verdict_label)

    def test_watching_when_only_some_core_positive(self):
        rows = _rebound_snapshots()
        for row in rows:
            # 하이닉스만 계속 저점 갱신 → 동시 반등 아님
            row["hynix_price"] = 98000
            row["hynix_open"] = 100200
            row["hynix_day_low"] = 98000
        result = flow.build_result_from_snapshots(rows, now=_ts(16))
        self.assertIs(result.verdict, ReboundVerdict.WATCHING)

    def test_not_confirmed_on_selling_expansion(self):
        rows = [
            _snapshot(
                m,
                non_arbitrage_net_amount=-100.0 * (i + 1),
                program_net_amount=-150.0 * (i + 1),
                futures_market_basis=-0.2 - 0.2 * i,
                samsung_price=69000 - 100 * i,
                samsung_open=70100,
                samsung_day_low=69000 - 100 * i,
                hynix_price=98000 - 200 * i,
                hynix_open=100200,
                hynix_day_low=98000 - 200 * i,
            )
            for i, m in enumerate((0, 5, 10, 15))
        ]
        result = flow.build_result_from_snapshots(rows, now=_ts(16))
        self.assertIs(result.verdict, ReboundVerdict.NOT_CONFIRMED)

    def test_insufficient_data_when_core_missing(self):
        rows = [_snapshot(0), _snapshot(5)]
        result = flow.build_result_from_snapshots(rows, now=_ts(6))
        self.assertIs(result.verdict, ReboundVerdict.INSUFFICIENT_DATA)

    def test_insufficient_data_when_no_snapshots(self):
        result = flow.build_result_from_snapshots([], now=BASE)
        self.assertIs(result.verdict, ReboundVerdict.INSUFFICIENT_DATA)

    def test_stale_data_does_not_produce_confirmed(self):
        # 20분 지난 데이터로 "기관성 반등 확인"을 내면 안 된다.
        result = flow.build_result_from_snapshots(
            _rebound_snapshots(),
            foreign_futures=ForeignFuturesFlowSnapshot(
                net_contracts=800, previous_net_contracts=-1200,
                as_of=_ts(15), source="HTS", available=True,
            ),
            now=_ts(40),
        )
        self.assertIs(result.verdict, ReboundVerdict.INSUFFICIENT_DATA)


class FakeReboundTest(unittest.TestCase):
    def test_samsung_only_rebound_warns(self):
        by_key = {
            "samsung": flow.FlowSignal("samsung", "삼성전자", SignalStatus.POSITIVE),
            "hynix": flow.FlowSignal("hynix", "SK하이닉스", SignalStatus.NEGATIVE),
            "program_total": flow.FlowSignal("program_total", "전체 프로그램", SignalStatus.NEGATIVE),
        }
        warnings = flow.detect_fake_rebound(by_key)
        self.assertTrue(any("삼성전자만" in w for w in warnings))

    def test_no_volume_warning_only_when_turnover_confirmed_down(self):
        by_key = {
            "samsung": flow.FlowSignal("samsung", "삼성전자", SignalStatus.POSITIVE),
            "hynix": flow.FlowSignal("hynix", "SK하이닉스", SignalStatus.POSITIVE),
        }
        # 거래대금 확인이 안 되면(None) 경고하지 않는다.
        self.assertEqual(
            [w for w in flow.detect_fake_rebound(by_key, extras={"semis_turnover_declining": None})
             if "거래량 없는" in w],
            [],
        )
        warnings = flow.detect_fake_rebound(by_key, extras={"semis_turnover_declining": True})
        self.assertTrue(any("거래량 없는" in w for w in warnings))

    def test_securities_only_buying_warns(self):
        by_key = {
            "securities": flow.FlowSignal("securities", "금융투자", SignalStatus.POSITIVE),
            "investment_trust": flow.FlowSignal("investment_trust", "투신", SignalStatus.NEGATIVE),
            "fund": flow.FlowSignal("fund", "기금·연기금", SignalStatus.NEGATIVE),
        }
        warnings = flow.detect_fake_rebound(by_key)
        self.assertTrue(any("금융투자 단독" in w for w in warnings))


class UnknownHandlingTest(unittest.TestCase):
    def test_none_never_becomes_zero_or_negative(self):
        for sig in (
            flow.evaluate_program_total(None, []),
            flow.evaluate_investor("fund", "기금·연기금", None, []),
            flow.evaluate_foreign_futures(None),
        ):
            self.assertIs(sig.status, SignalStatus.UNKNOWN, sig.key)
            self.assertIsNone(sig.value, sig.key)

    def test_late_signal_after_13h(self):
        sig = flow.classify_late_signal(datetime(2026, 7, 20, 13, 20), "사이드카")
        self.assertIs(sig.timing, flow.SignalTiming.LATE)
        self.assertIn("늦은 신호", sig.reason)

    def test_signal_before_13h_is_confirming(self):
        sig = flow.classify_late_signal(datetime(2026, 7, 20, 10, 20), "프로그램 대량매수")
        self.assertIs(sig.timing, flow.SignalTiming.CONFIRMING)


if __name__ == "__main__":
    unittest.main()
