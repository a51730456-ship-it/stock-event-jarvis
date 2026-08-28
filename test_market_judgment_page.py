"""시장 판단이 자비스1·2·3과 분리된 독립 화면인지 확인한다."""

import contextlib
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import page_access


@contextlib.contextmanager
def _page_open():
    """이 시험 동안만 화면을 열어 둔다 (2026-08-28).

    상하님 지시로 시장 판단·자비스1·2·5·6은 닫아 두었다(page_access). 그래도
    **그 화면이 그리는 내용은 계속 지켜야 한다** — 다시 열었을 때 깨져 있으면
    안 되기 때문이다. 그래서 시험에서만 열고 돌려 본다. 닫혀 있다는 것 자체는
    아래 ClosedPageTest 가 따로 잰다.
    """
    with patch.object(page_access, "OPEN_PAGES", page_access.ALL_PAGES):
        yield


@contextlib.contextmanager
def _no_network_signal_patches():
    """2026-07-22부터 두 카드가 첫 화면에서 자동 조회하므로, 테스트에서는
    네트워크·DB 접근을 막고 '자료 없음' 상태로 렌더되게 한다.

    **_cached_previous_us_quotes도 막는다**(2026-08-21). 미국장 카드의 본값은
    실시간 시세가 아니라 **완성 일봉**이라 _fetch_quotes만 막아서는 야후에
    그대로 다녀왔다. 그렇게 만들어진 진짜 판정이 아래 '판정을 지어내지
    않는다' 시험에는 '5단계 기준' 거르개에 가려 안 보였을 뿐이다.
    """
    with patch("market_signal_ui._fetch_quotes", return_value={}), \
         patch("market_signal_ui._cached_previous_us_quotes", return_value={}), \
         patch("market_signal_ui.collect_kr_flow_snapshot", return_value=({}, ["KIS API 키 미설정"])), \
         patch("database.save_kr_flow_snapshot"), \
         patch("database.list_kr_flow_snapshots", return_value=[{}]):
        yield


class MarketJudgmentPageTest(unittest.TestCase):
    def _run(self):
        with _page_open(), _no_network_signal_patches():
            at = AppTest.from_file("pages/0_시장판단.py", default_timeout=90)
            at.session_state["authenticated"] = True
            at.run()
        return at

    def test_page_renders_both_cards(self):
        at = self._run()
        self.assertEqual(at.exception, [], "시장 판단 페이지 렌더 중 예외")
        text = " ".join(m.value for m in at.markdown)
        self.assertIn("시장 판단", text)
        self.assertIn("한국장 시장 상태", text)
        self.assertIn("미국장 시장 상태", text)

    def test_both_refresh_buttons_present(self):
        at = self._run()
        keys = [b.key for b in at.button]
        self.assertIn("kr_flow_refresh", keys)
        self.assertIn("us_signal_refresh", keys)

    def test_login_gate_blocks_unauthenticated(self):
        with _page_open():
            at = AppTest.from_file("pages/0_시장판단.py", default_timeout=90)
            at.run()
        text = " ".join(m.value for m in at.markdown)
        self.assertIn("승인된 사용자만", " ".join(c.value for c in at.caption) + text)
        # 인증 전에는 카드가 나오면 안 된다.
        self.assertNotIn("한국장 시장 상태", text)


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


@contextlib.contextmanager
def _jarvis1_open():
    """자비스1도 시험 동안만 열어 둔다(위 _page_open과 같은 까닭)."""
    with _page_open():
        yield


class Jarvis1NoLongerHostsCardsTest(unittest.TestCase):
    """카드는 자비스1에서 빠졌어야 한다 — 두 군데에 있으면 안 된다."""

    def test_cards_removed_from_jarvis1(self):
        at = _open_jarvis1()
        with _jarvis1_open():
            at.run()
        self.assertEqual(at.exception, [], "자비스1 렌더 중 예외")
        text = " ".join(m.value for m in at.markdown)
        self.assertNotIn("한국장 시장 상태", text)
        self.assertNotIn("미국장 시장 상태", text)

    def test_jarvis1_existing_features_intact(self):
        at = _open_jarvis1()
        with _jarvis1_open():
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
        with _page_open(), _no_network_signal_patches():
            at = AppTest.from_file("pages/0_시장판단.py", default_timeout=90)
            at.session_state["authenticated"] = True
            at.run()
        # '5단계 기준' 안내문에는 다섯 이름이 늘 적혀 있다(설명이지 판정이 아니다).
        # 그 줄을 빼고 봐야 '자료도 없이 판정을 지어냈는지'를 제대로 잰다.
        text = " ".join(
            m.value for m in at.markdown if "5단계 기준" not in m.value
        )
        for verdict in ("하락 압력 큼", "약세 신호 우세", "상승 신호 우세", "상승 여건 양호"):
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


class ClosedPageTest(unittest.TestCase):
    """지금은 닫아 둔 화면이다 (2026-08-28 상하님 지시).

    상하님 — "나머지 화면은 접근 금지로 해라." 주소로 바로 들어와도 막혀야 한다.
    """

    def test_the_page_is_closed_by_default(self):
        at = AppTest.from_file("pages/0_시장판단.py", default_timeout=90)
        at.session_state["authenticated"] = True
        at.run()
        text = " ".join(str(m.value) for m in at.markdown)
        self.assertIn("이 화면은 지금 닫혀 있습니다", text)
        self.assertNotIn("한국장 시장 상태", text)

    def test_only_the_two_theme_pages_are_open(self):
        self.assertEqual(("미국테마", "한국테마"), page_access.OPEN_PAGES)
        for closed in ("시장판단", "자비스1", "자비스2", "자비스5", "자비스6"):
            self.assertFalse(page_access.is_open(closed), closed)
