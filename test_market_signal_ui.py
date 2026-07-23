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


if __name__ == "__main__":
    unittest.main()
