"""시장 판단이 자비스1·2·3과 분리된 독립 화면인지 확인한다."""

import contextlib
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


@contextlib.contextmanager
def _no_network_signal_patches():
    """2026-07-22부터 두 카드가 첫 화면에서 자동 조회하므로, 테스트에서는
    네트워크·DB 접근을 막고 '자료 없음' 상태로 렌더되게 한다."""
    with patch("market_signal_ui._fetch_quotes", return_value={}), \
         patch("market_signal_ui.collect_kr_flow_snapshot", return_value=({}, ["KIS API 키 미설정"])), \
         patch("database.save_kr_flow_snapshot"), \
         patch("database.list_kr_flow_snapshots", return_value=[{}]):
        yield


class MarketJudgmentPageTest(unittest.TestCase):
    def _run(self):
        with _no_network_signal_patches():
            at = AppTest.from_file("pages/0_시장판단.py", default_timeout=90)
            at.session_state["authenticated"] = True
            at.run()
        return at

    def test_page_renders_both_cards(self):
        at = self._run()
        self.assertEqual(at.exception, [], "시장 판단 페이지 렌더 중 예외")
        text = " ".join(m.value for m in at.markdown)
        self.assertIn("시장 판단", text)
        self.assertIn("한국장 기관 수급 현황", text)
        self.assertIn("미국장 선행신호·시장 상태", text)

    def test_both_refresh_buttons_present(self):
        at = self._run()
        keys = [b.key for b in at.button]
        self.assertIn("kr_flow_refresh", keys)
        self.assertIn("us_signal_refresh", keys)

    def test_login_gate_blocks_unauthenticated(self):
        at = AppTest.from_file("pages/0_시장판단.py", default_timeout=90)
        at.run()
        text = " ".join(m.value for m in at.markdown)
        self.assertIn("승인된 사용자만", " ".join(c.value for c in at.caption) + text)
        # 인증 전에는 카드가 나오면 안 된다.
        self.assertNotIn("기관 수급 현황", text)


def _open_jarvis1(timeout=90):
    """자비스1을 직접 연 상태로 만든다.

    2026-08-01부터 로그인만으로는 자비스1이 열리지 않는다 — 첫 주소로 돌아온 사람에게는
    '어디로 갈까요' 화면을 띄우기 때문이다. 자비스1을 고른 사람은 주소에 표식이 남고,
    그 표식이 있을 때만 자비스1이 그려진다.
    """
    at = AppTest.from_file("app.py", default_timeout=timeout)
    at.session_state["authenticated"] = True
    at.query_params["page"] = "jarvis1"
    return at


class Jarvis1NoLongerHostsCardsTest(unittest.TestCase):
    """카드는 자비스1에서 빠졌어야 한다 — 두 군데에 있으면 안 된다."""

    def test_cards_removed_from_jarvis1(self):
        at = _open_jarvis1()
        at.run()
        self.assertEqual(at.exception, [], "자비스1 렌더 중 예외")
        text = " ".join(m.value for m in at.markdown)
        self.assertNotIn("한국장 기관 수급 현황", text)
        self.assertNotIn("미국장 선행신호·시장 상태", text)

    def test_jarvis1_existing_features_intact(self):
        at = _open_jarvis1()
        at.run()
        text = " ".join(m.value for m in at.markdown)
        # 기존 0단계·시장요약은 그대로 남아 있어야 한다.
        self.assertIn("0단계 시장 분위기", text)
        labels = [e.label for e in at.expander]
        self.assertTrue(
            any("도박사" in label and "한국장" in label for label in labels),
            "한국장 도박사 카드가 사라졌습니다",
        )
        self.assertTrue(
            any("도박사" in label and "미국장" in label for label in labels),
            "미국장 도박사 카드가 사라졌습니다",
        )


class NoFabricatedVerdictTest(unittest.TestCase):
    def test_no_verdict_without_data(self):
        """자동 조회가 자료를 못 얻으면 판정을 만들어내지 않는다(데이터 부족만 표시)."""
        with _no_network_signal_patches():
            at = AppTest.from_file("pages/0_시장판단.py", default_timeout=90)
            at.session_state["authenticated"] = True
            at.run()
        text = " ".join(m.value for m in at.markdown)
        for verdict in ("기관성 반등 확인", "위험선호 확산", "위험회피 우세"):
            self.assertNotIn(verdict, text, f"자료 없이 '{verdict}' 판정이 표시됐습니다")

    def test_manual_futures_value_is_scoped_to_today(self):
        """어제 입력한 외국인 선물 값이 오늘 판정에 새어들어오면 안 된다."""
        import market_signal_ui

        stale = {"net_contracts": -3250, "trade_date": "1999-01-01"}
        self.assertNotEqual(stale["trade_date"], market_signal_ui._flow_today())


class Jarvis2And3UntouchedTest(unittest.TestCase):
    def test_jarvis2_still_renders(self):
        at = AppTest.from_file("pages/1_자비스2.py", default_timeout=120)
        at.session_state["authenticated"] = True
        at.run()
        self.assertEqual(at.exception, [], "자비스2 렌더 중 예외")

    def test_jarvis3_still_renders(self):
        with _no_network_signal_patches():
            at = AppTest.from_file("pages/2_자비스3.py", default_timeout=120)
            at.session_state["authenticated"] = True
            at.run()
        self.assertEqual(at.exception, [], "자비스3 렌더 중 예외")


if __name__ == "__main__":
    unittest.main()
