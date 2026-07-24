import re
import unittest
from unittest.mock import patch

import market_signal_ui as ui


class MarketSignalUiFlowTests(unittest.TestCase):
    def test_kis_success_still_collects_futures_and_electronics(self):
        investor_row = {
            "frgn_ntby_tr_pbmn": "100", "prsn_ntby_tr_pbmn": "-200",
            "orgn_ntby_tr_pbmn": "300", "scrt_ntby_tr_pbmn": "10",
            "ivtr_ntby_tr_pbmn": "20", "pe_fund_ntby_tr_pbmn": "30",
            "fund_ntby_tr_pbmn": "40",
        }

        def investor(_key, _secret, sector_code=None):
            if sector_code:
                return {"ok": True, "row": {"orgn_ntby_tr_pbmn": "999"}}
            return {"ok": True, "row": investor_row}

        with patch.object(ui, "_flow_kis_keys", return_value=("key", "secret")), \
             patch.object(ui.kis_market_data, "get_program_trade_intraday", return_value={
                 "ok": True, "rows": [{"whol_smtn_ntby_tr_pbmn": "100", "whol_ntby_tr_pbmn_icdc2": "10"}],
             }), \
             patch.object(ui.kis_market_data, "get_program_trade_by_investor", return_value={
                 "ok": True, "rows": [{"arbt_ntby_amt": "5", "nabt_ntby_amt": "7"}],
             }), \
             patch.object(ui.kis_market_data, "get_market_investor_intraday", side_effect=investor), \
             patch.object(ui.kis_market_data, "get_kospi200_futures_snapshot", return_value={
                 "ok": True, "basis": 1.2, "market_basis": 1.0,
             }) as futures, \
             patch.object(ui, "_flow_electronics_sector_code", return_value=("001", 1234)), \
             patch.object(ui.price_data, "get_snapshot_defaults", return_value={
                 "ok": True, "current": 100, "open": 99, "low": 98,
             }), \
             patch.object(ui.naver_market_data, "get_foreign_futures_daily_net", return_value={
                 "ok": True, "net_contracts": 500, "source": "test",
             }), \
             patch.object(ui.st, "session_state", {}), \
             patch.object(ui.st, "secrets", {}):
            values, failures = ui.collect_kr_flow_snapshot()

        futures.assert_called_once()
        self.assertEqual(values["futures_basis"], 1.2)
        self.assertEqual(values["electronics_institution_net"], 999)
        self.assertEqual(values["electronics_turnover"], 1234)
        self.assertNotIn("선물 베이시스 조회 실패", " / ".join(failures))


class VerdictGaugeTests(unittest.TestCase):
    """판정 게이지 — 없는 점수를 지어내지 않고 단계만 가리켜야 한다(2026-07-24)."""

    def _result(self, verdict, statuses=()):
        import market_signal_common as common

        signals = []
        for index, status in enumerate(statuses):
            signal = common.MarketSignal(
                key=f"K{index}", label=f"신호{index}", status=status,
                source="x", timing=common.SignalTiming.LEADING,
            )
            signals.append(signal)

        class _R:
            pass

        result = _R()
        result.verdict = verdict
        result.signals = signals
        return result

    def test_needle_moves_from_bad_to_good(self):
        import us_market_signal_engine as us

        def needle(verdict):
            html = ui._verdict_gauge_html(
                self._result(verdict), ui._US_VERDICT_STYLE, ui.US_VERDICT_ORDER
            )
            return float(re.search(r"x2='([\d.]+)'", html).group(1))

        positions = [needle(v) for v in ui.US_VERDICT_ORDER]
        self.assertEqual(positions, sorted(positions), "나쁜 쪽에서 좋은 쪽으로 가야 한다")
        self.assertLess(positions[0], positions[-1])

    def test_no_invented_score_number(self):
        """이 카드의 판정은 0~100 점수가 아니다 — 숫자를 만들어 붙이면 안 된다."""
        import us_market_signal_engine as us

        html = ui._verdict_gauge_html(
            self._result(us.UsMarketVerdict.MIXED), ui._US_VERDICT_STYLE, ui.US_VERDICT_ORDER
        )
        self.assertNotIn("fg-score", html)
        self.assertIn("방향 혼조", html)

    def test_insufficient_data_draws_no_needle(self):
        import us_market_signal_engine as us

        html = ui._verdict_gauge_html(
            self._result(us.UsMarketVerdict.INSUFFICIENT_DATA),
            ui._US_VERDICT_STYLE, ui.US_VERDICT_ORDER,
        )
        self.assertNotIn("fg-needle", html)

    def test_counts_come_from_the_signals(self):
        import market_signal_common as common
        import us_market_signal_engine as us

        S = common.SignalStatus
        html = ui._verdict_gauge_html(
            self._result(us.UsMarketVerdict.MIXED,
                         [S.POSITIVE, S.POSITIVE, S.NEGATIVE, S.UNKNOWN]),
            ui._US_VERDICT_STYLE, ui.US_VERDICT_ORDER,
        )
        self.assertIn("켜진 신호", html)
        self.assertIn("2개", html)
        self.assertIn("확인 필요", html)

    def test_both_markets_have_four_ordered_steps(self):
        self.assertEqual(len(ui.KR_VERDICT_ORDER), 4)
        self.assertEqual(len(ui.US_VERDICT_ORDER), 4)
        for verdict in ui.KR_VERDICT_ORDER + ui.US_VERDICT_ORDER:
            self.assertIn(verdict, ui._VERDICT_SHORT, "눈금에 쓸 짧은 이름이 없다")


if __name__ == "__main__":
    unittest.main()
