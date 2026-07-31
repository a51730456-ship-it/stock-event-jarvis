import re
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import market_signal_common
import market_signal_ui as ui


class MarketSignalUiFlowTests(unittest.TestCase):
    def test_naver_quote_accepts_naive_app_clock_and_aware_trade_time(self):
        quote = {
            "price": 224_250, "day_open": 226_500, "day_low": 219_750,
            "market_status": "OPEN", "traded_at": "2026-07-29T10:33:32+09:00",
        }
        self.assertTrue(ui._fresh_naver_stock_quote(
            quote, now=datetime(2026, 7, 29, 10, 34)
        ))

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
             patch.object(ui.naver_stock_quote, "get_quotes", return_value={}), \
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

    def test_naver_intraday_quotes_override_delayed_daily_prices(self):
        now = datetime(2026, 7, 29, 10, 33, 40, tzinfo=ui._SEOUL_TZ)
        market_flow = {
            "ok": True,
            "values": {
                "personal": -14_258, "foreign": 1_745, "institution": 12_548,
                "securities": 7_088, "insurance": 236, "investment_trust": 3_376,
                "bank": -24, "etc_finance": 31, "pension": 1_842, "etc_corp": -35,
            },
            "source": "네이버 시간별 투자자매매동향(지연 가능)",
        }
        quotes = {
            "005930": {
                "price": 224_250, "day_open": 226_500, "day_low": 219_750,
                "market_status": "OPEN", "traded_at": "2026-07-29T10:33:32+09:00",
            },
            "000660": {
                "price": 1_497_000, "day_open": 1_567_000, "day_low": 1_467_000,
                "market_status": "OPEN", "traded_at": "2026-07-29T10:33:32+09:00",
            },
        }
        with patch.object(ui, "_flow_kis_keys", return_value=(None, None)), \
             patch.object(ui, "_now_seoul", return_value=now), \
             patch.object(
                 ui.naver_market_data, "get_market_investor_flow_intraday",
                 return_value=market_flow,
             ), \
             patch.object(ui.naver_stock_quote, "get_quotes", return_value=quotes), \
             patch.object(ui.price_data, "get_snapshot_defaults") as old_price, \
             patch.object(
                 ui.naver_market_data, "get_foreign_futures_daily_net",
                 return_value={"ok": False},
             ), \
             patch.object(ui.st, "session_state", {}), \
             patch.object(ui.st, "secrets", {}):
            values, _failures = ui.collect_kr_flow_snapshot()
        self.assertEqual(values["samsung_price"], 224_250)
        self.assertEqual(values["hynix_price"], 1_497_000)
        self.assertEqual(values["samsung_day_low"], 219_750)
        self.assertEqual(values["foreign_cash_net_amount"], 174_500)
        old_price.assert_not_called()


class VerdictGaugeTests(unittest.TestCase):
    """판정 게이지 — 네 단계의 위치값과 전일 위치를 표시한다."""

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

    def test_position_score_is_shown_on_the_same_scale_as_previous(self):
        """현재·전일은 같은 판정 위치값 눈금으로 비교한다."""
        import us_market_signal_engine as us

        html = ui._verdict_gauge_html(
            self._result(us.UsMarketVerdict.MIXED),
            ui._US_VERDICT_STYLE,
            ui.US_VERDICT_ORDER,
            show_position_score=True,
        )
        self.assertNotIn("fg-score", html)
        self.assertIn("sig-current-score", html)
        self.assertIn(">38</div>", html)
        self.assertNotIn("2/4단계", html)
        self.assertIn("방향 혼조", html)

    def test_previous_score_keeps_its_own_verdict_color(self):
        import us_market_signal_engine as us

        html = ui._verdict_gauge_html(
            self._result(us.UsMarketVerdict.MIXED),
            ui._US_VERDICT_STYLE,
            ui.US_VERDICT_ORDER,
            previous_stage={
                "score": 12.5, "label": "위험회피", "trade_date": "2026-07-28",
                "period_label": "전일", "color": "#ef4444",
            },
            show_position_score=True,
        )
        self.assertIn("sig-prev-score", html)
        self.assertIn("color:#ef4444", html)
        self.assertIn("전일(07.28) 12 · 위험회피", html)

    def test_us_card_does_not_show_kr_position_score_by_default(self):
        """사용자가 요청한 위치값은 한국장 카드에만 붙이고 미국장에는 번지지 않는다."""
        import us_market_signal_engine as us

        html = ui._verdict_gauge_html(
            self._result(us.UsMarketVerdict.MIXED),
            ui._US_VERDICT_STYLE,
            ui.US_VERDICT_ORDER,
        )
        self.assertNotIn("sig-current-score", html)

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
        self.assertIn("못 읽은 항목", html)

    def test_both_markets_have_four_ordered_steps(self):
        self.assertEqual(len(ui.KR_VERDICT_ORDER), 4)
        self.assertEqual(len(ui.US_VERDICT_ORDER), 4)
        for verdict in ui.KR_VERDICT_ORDER + ui.US_VERDICT_ORDER:
            self.assertIn(verdict, ui._VERDICT_SHORT, "눈금에 쓸 짧은 이름이 없다")

    def test_previous_kr_stage_uses_saved_previous_day(self):
        import kr_intraday_flow as kr

        saved = {
            "trade_date": "2026-07-28",
            "rows": [{"captured_at": "2026-07-28T15:05:00"}],
        }
        rebuilt = self._result(kr.ReboundVerdict.WATCHING)
        with patch.object(
            ui.database, "list_previous_kr_flow_snapshots", return_value=saved
        ), patch.object(
            ui, "_flow_today", return_value="2026-07-29"
        ), patch.object(
            ui.kr_intraday_flow, "build_result_from_snapshots", return_value=rebuilt
        ):
            previous = ui._previous_kr_flow_stage()
        self.assertEqual(previous["trade_date"], "2026-07-28")
        self.assertEqual(previous["score"], 37.5)
        self.assertEqual(previous["label"], "일부 켜짐")
        self.assertEqual(previous["color"], "#eab308")
        self.assertEqual(previous["period_label"], "전일")

    def test_previous_kr_stage_marks_older_snapshot_as_last_saved(self):
        import kr_intraday_flow as kr

        saved = {
            "trade_date": "2026-07-24",
            "rows": [{"captured_at": "2026-07-24T15:05:00"}],
        }
        rebuilt = self._result(kr.ReboundVerdict.NOT_CONFIRMED)
        with patch.object(
            ui.database, "list_previous_kr_flow_snapshots", return_value=saved
        ), patch.object(
            ui, "_flow_today", return_value="2026-07-29"
        ), patch.object(
            ui.kr_intraday_flow, "build_result_from_snapshots", return_value=rebuilt
        ):
            previous = ui._previous_kr_flow_stage()
        self.assertEqual(previous["period_label"], "직전 저장")


class KrFlowAutoRefreshTests(unittest.TestCase):
    def test_first_load_and_new_day_are_due(self):
        now = datetime(2026, 7, 29, 10, 30, tzinfo=ui._SEOUL_TZ)
        self.assertTrue(ui._kr_flow_auto_due(None, None, now))
        self.assertTrue(ui._kr_flow_auto_due(
            object(), datetime(2026, 7, 28, 15, 30, tzinfo=ui._SEOUL_TZ), now
        ))

    def test_intraday_refreshes_after_one_minute_but_not_before(self):
        now = datetime(2026, 7, 29, 10, 30, tzinfo=ui._SEOUL_TZ)
        self.assertFalse(ui._kr_flow_auto_due(
            object(), now - timedelta(seconds=30), now
        ))
        self.assertTrue(ui._kr_flow_auto_due(
            object(), now - timedelta(seconds=60), now
        ))

    def test_naive_now_and_aware_saved_time_can_be_compared(self):
        now = datetime(2026, 7, 29, 10, 30)
        saved = datetime(2026, 7, 29, 10, 29, tzinfo=ui._SEOUL_TZ)
        self.assertTrue(ui._kr_flow_auto_due(object(), saved, now))

    def test_after_hours_does_not_repeat_same_day(self):
        now = datetime(2026, 7, 29, 18, 0, tzinfo=ui._SEOUL_TZ)
        self.assertFalse(ui._kr_flow_auto_due(
            object(), now - timedelta(hours=2), now
        ))


class CardHtmlTests(unittest.TestCase):
    """카드 HTML은 들여쓰기·빈 줄이 없어야 한다.

    여러 줄에 걸쳐 들여쓰면 원인 문구가 비었을 때 마크다운이 다음 줄을 코드블록으로
    잡아 '</div>'가 화면에 글자로 찍힌다(2026-07-24 실제 발생).
    """

    def _render_and_capture(self, cause=None):
        import market_signal_common as common
        import us_market_signal_engine as us

        def _signal(key, status):
            signal = common.MarketSignal(
                key=key, label=key, status=status, source="x",
                timing=common.SignalTiming.LEADING,
            )
            signal.display_value, signal.reason = "+0.1%", "설명"
            return signal

        result = us.UsSignalResult(
            verdict=us.UsMarketVerdict.MIXED,
            verdict_label=us.VERDICT_LABEL[us.UsMarketVerdict.MIXED],
            headline="한 방향이 아닙니다.",
            flow_note="선행 신호 1개만 켜졌습니다.",
            signals=[
                _signal("US_NQ_FUTURES", common.SignalStatus.POSITIVE),
                _signal("US_SOXX", common.SignalStatus.UNKNOWN),
            ],
            data_status="자동 확인 13개",
        )
        captured = []

        class _FakeSt:
            def markdown(self, text, **_kwargs):
                captured.append(text)

            def caption(self, *a, **k):
                pass

            def warning(self, *a, **k):
                pass

            def columns(self, count):
                return [self] * count

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def table(self, *a, **k):
                pass

            def expander(self, *a, **k):
                return self

            def write(self, *a, **k):
                pass

        original = ui.st
        ui.st = _FakeSt()
        try:
            ui.render_market_signal_card(
                result, verdict_style=ui._US_VERDICT_STYLE,
                core_display=ui._US_CORE_DISPLAY, table_keys=ui._US_TABLE_KEYS,
                detail_title="t", detail_caption="c", table_key="k",
                diagnosis_text=(lambda _r: cause) if cause else None,
                verdict_order=ui.US_VERDICT_ORDER,
            )
        finally:
            ui.st = original
        return next(t for t in captured if 'class="sig-body"' in t)

    def test_card_html_is_one_line_without_indentation(self):
        for cause in (None, "키가 없습니다"):
            with self.subTest(cause=cause):
                card = self._render_and_capture(cause)
                self.assertNotIn("\n", card, "줄바꿈이 있으면 코드블록으로 잡힐 수 있다")
                self.assertEqual(card.count("<div"), card.count("</div>"))


class SignedColorTests(unittest.TestCase):
    """오름은 파랑, 내림은 빨강.

    판정색이 값을 통째로 덮으면 오른 건지 내린 건지 알 수 없다 —
    -4.55%가 보합 노랑으로 떠서 구분이 안 됐다(2026-07-29 사용자 지적).
    """

    def test_minus_is_red_and_plus_is_blue(self):
        html = ui._colorize_signed("210,000 (-4.55% · 저점대비 +1.45%)")
        self.assertIn(f"color:{ui._DOWN_COLOR}'>-4.55%", html)
        self.assertIn(f"color:{ui._UP_COLOR}'>+1.45%", html)

    def test_units_other_than_percent_are_colored_too(self):
        self.assertIn(f"color:{ui._UP_COLOR}'>+1,711", ui._colorize_signed("+1,711계약"))

    def test_plain_number_is_left_alone(self):
        self.assertEqual(ui._colorize_signed("209,000"), "209,000")

    def test_missing_value_does_not_crash(self):
        self.assertEqual(ui._colorize_signed(None), "")


class FallingMarketTests(unittest.TestCase):
    """지수가 무너지는 날 '긍정'에 (하락장)을 붙인다. 판정은 안 바꾼다."""

    def _note(self, pct):
        return ui.falling_market_note(snapshot_fn=lambda: {"ok": True, "change_pct": pct})

    def test_big_drop_is_marked(self):
        self.assertEqual(self._note(-6.14)["text"], "(하락장)")

    def test_small_drop_is_not_marked(self):
        """조금 빠진 날까지 붙이면 꼬리표가 늘 붙어 뜻이 없어진다."""
        self.assertIsNone(self._note(-1.9))
        self.assertIsNone(self._note(0.5))

    def test_unreadable_index_marks_nothing(self):
        """못 읽은 것을 '하락장 아님'으로 단정하지 않는다."""
        self.assertIsNone(ui.falling_market_note(snapshot_fn=lambda: {"ok": False}))
        self.assertIsNone(ui.falling_market_note(
            snapshot_fn=lambda: (_ for _ in ()).throw(RuntimeError("망"))))

    def test_tag_goes_only_on_positive_signals(self):
        note = {"label": "코스피", "change_pct": -6.14, "text": "(하락장)"}

        class Fake:
            def __init__(self, status):
                self.status = status

        status = market_signal_common.SignalStatus
        self.assertIn("(하락장)", ui._falling_tag(Fake(status.POSITIVE), note))
        for other in (status.NEUTRAL, status.NEGATIVE, status.UNKNOWN):
            self.assertEqual(ui._falling_tag(Fake(other), note), "")

    def test_no_tag_when_market_is_not_falling(self):
        status = market_signal_common.SignalStatus

        class Fake:
            status = None

        fake = Fake()
        fake.status = status.POSITIVE
        self.assertEqual(ui._falling_tag(fake, None), "")


if __name__ == "__main__":
    unittest.main()


class SaveFailureFallbackTests(unittest.TestCase):
    """2026-07-31 09:27 실발생 — 장 시작 25분 뒤인데 '스냅숏이 아직 없습니다'만 떴다.

    자료는 멀쩡히 들어왔는데(기관 -5,182억 · 외국인 선물 +98계약) DB 저장이
    실패하자 방금 읽은 값까지 통째로 버렸다. 저장은 쌓아 두기용이지
    보여주기의 전제가 아니다.
    """

    def _values(self):
        return {
            "institution_cash_net_amount": -518_200.0,
            "foreign_cash_net_amount": 120_000.0,
            "samsung_price": 208_500.0, "samsung_open": 205_000.0,
            "samsung_day_low": 204_000.0, "samsung_prev_close": 200_000.0,
            "investor_flow_source": "네이버 시간별 투자자매매동향(지연 가능)",
        }

    def test_screen_still_shows_values_when_saving_fails(self):
        with patch.object(ui, "collect_kr_flow_snapshot", return_value=(self._values(), [])), \
             patch.object(ui.database, "save_kr_flow_snapshot", side_effect=RuntimeError("디스크 쓰기 불가")), \
             patch.object(ui.database, "list_kr_flow_snapshots", return_value=[]), \
             patch.object(ui.st, "session_state", {}):
            result = ui.run_kr_flow_check()
        # 스냅숏이 하나도 없다고 접히면 안 된다 — 방금 읽은 값이 있다.
        self.assertTrue(result.signals, "저장이 실패했다고 화면까지 비우면 안 된다")
        institution = result.signal("institution")
        self.assertIsNotNone(institution)
        self.assertIsNotNone(institution.value)

    def test_failure_reason_is_recorded(self):
        state = {}
        with patch.object(ui, "collect_kr_flow_snapshot", return_value=(self._values(), [])), \
             patch.object(ui.database, "save_kr_flow_snapshot", side_effect=RuntimeError("x")), \
             patch.object(ui.database, "list_kr_flow_snapshots", return_value=[]), \
             patch.object(ui.st, "session_state", state):
            ui.run_kr_flow_check()
        self.assertTrue(any("저장 실패" in f for f in state.get("kr_flow_failures", [])))
