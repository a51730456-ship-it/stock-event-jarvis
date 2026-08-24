"""종목 브리핑의 설정 저장·뉴스 후보 축소 회귀 시험."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import jarvis3_briefing_news as news
import jarvis3_briefing_store as store
from streamlit.testing.v1 import AppTest


def _isolated_store(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    monkeypatch.setattr(store, "_connection", lambda: conn)
    monkeypatch.setattr(store, "_READY", False)
    # 각 호출이 close()하므로 테스트 연결은 닫지 않는 얇은 wrapper가 필요하다.
    class Shared:
        def __getattr__(self, name):
            return getattr(conn, name)
        def close(self):
            pass
    monkeypatch.setattr(store, "_connection", lambda: Shared())


def test_selected_slots_are_fixed_and_replaceable(monkeypatch):
    _isolated_store(monkeypatch)
    selected = store.selected_stocks()
    assert [row["ticker"] for row in selected] == ["NVDA", "TSLA", "PLTR", "AMD"]
    store.replace_selected(2, "META", "Meta Platforms")
    assert store.selected_stocks()[1]["ticker"] == "META"
    assert len(store.selected_stocks()) == 4


def test_extra_stocks_keep_order_and_limit(monkeypatch):
    _isolated_store(monkeypatch)
    for number in range(8):
        store.add_extra(f"X{number}", f"X {number}")
    assert [row["ticker"] for row in store.extra_stocks()] == [f"X{number}" for number in range(8)]
    try:
        store.add_extra("NINE", "Nine")
    except ValueError as exc:
        assert "최대 8개" in str(exc)
    else:
        raise AssertionError("9번째 추가 검색 종목이 저장됐다")
    store.remove_extra(3)
    assert [row["position"] for row in store.extra_stocks()] == list(range(1, 8))


def test_news_dedupes_same_url_and_keeps_actual_count():
    rows = news._dedupe([
        {"headline": "AI demand lifts chips", "url": "https://example.test/a"},
        {"headline": "AI demand lifts chips again", "url": "https://example.test/a"},
        {"headline": "Rates rise", "url": "https://example.test/b"},
    ])
    assert len(rows) == 2
    assert len(news._fallback(rows)) == 2


def test_rss_fallback_keeps_verifiable_actual_rows(monkeypatch):
    stamp = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    monkeypatch.setattr(news, "_request_text", lambda _url: f"""
        <rss><channel><item><title>미국 증시 관련 실제 뉴스</title><link>https://example.test/news</link>
        <pubDate>{stamp}</pubDate><source url="https://example.test">테스트 출처</source></item></channel></rss>
    """)
    rows = news._google_news_rss("market", None)
    assert len(rows) == 1
    assert rows[0]["headline"] == "미국 증시 관련 실제 뉴스"
    assert rows[0]["url"] == "https://example.test/news"


def test_first_page_renders_four_slots_and_next_page_button():
    stocks = {
        "selected": [
            {"position": 1, "ticker": "NVDA", "name": "NVIDIA"},
            {"position": 2, "ticker": "TSLA", "name": "Tesla"},
            {"position": 3, "ticker": "PLTR", "name": "Palantir"},
            {"position": 4, "ticker": "AMD", "name": "AMD"},
        ], "extra": [],
    }
    cards = {ticker: {"ticker": ticker, "name": ticker, "price": 100.0,
                      "change_pct": 1.0, "chart": [90, 95, 100], "stale": False}
             for ticker in ("NVDA", "TSLA", "PLTR", "AMD")}
    page = Path(__file__).parent / "pages" / "2_자비스3.py"
    with patch("jarvis3_briefing_store.ensure_tables"), \
         patch("jarvis3_briefing_store.all_stocks", return_value=stocks), \
         patch("jarvis3_data.get_briefing_cards", return_value=cards), \
         patch("jarvis3_briefing_news.get_or_schedule", return_value={"ok": True, "items": []}):
        app = AppTest.from_file(str(page), default_timeout=30)
        app.secrets["APP_PASSWORD"] = "test"
        app.session_state["authenticated"] = True
        app.session_state["jarvis_access_role"] = "owner"
        app.run(timeout=30)
    assert not app.exception
    rendered = " ".join(str(node.value) for node in app.markdown)
    assert "종목 브리핑" in rendered
    assert all(ticker in rendered for ticker in ("NVDA", "TSLA", "PLTR", "AMD"))
    assert any(node.key == "j3b_go_market" for node in app.button)
