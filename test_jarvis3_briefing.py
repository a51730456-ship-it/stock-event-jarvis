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


def test_english_news_fallback_uses_one_batched_deepl_call(monkeypatch):
    rows = [
        {"headline": "US stocks rise", "url": "https://example.test/1"},
        {"headline": "Chip demand grows", "url": "https://example.test/2"},
    ]
    seen = {}
    def translate(texts, key):
        seen["texts"], seen["key"] = texts, key
        return {"ok": True, "translations": {
            "US stocks rise": "미국 증시 상승",
            "Chip demand grows": "반도체 수요 증가",
        }, "error": None}
    monkeypatch.setattr(news.deepl_translate, "translate_texts_to_ko", translate)
    result = news._fallback(rows, "deepl-test")
    assert seen == {"texts": ["US stocks rise", "Chip demand grows"], "key": "deepl-test"}
    assert [item["brief"] for item in result] == ["미국 증시 상승", "반도체 수요 증가"]


def test_failed_translation_falls_back_to_original_headline(monkeypatch):
    """번역이 다 막힌 날에도 안내 문구가 아니라 진짜 기사 제목을 보여 준다.

    예전에는 세 줄이 모두 '번역을 잠시 불러오지 못했습니다'로 채워져 무슨 뉴스인지조차
    알 수 없었다(2026-08-26 상하님 지적).
    """
    monkeypatch.setattr(news.deepl_translate, "translate_texts_to_ko", lambda *_args: [])
    monkeypatch.setattr(news, "_public_translations", lambda *_args: {})
    result = news._fallback([{"headline": "English headline", "url": "https://example.test"}], "key")
    assert result[0]["brief"] == "English headline"
    assert "불러오지 못했습니다" not in result[0]["brief"]


def test_empty_deepl_key_uses_cached_public_translation(monkeypatch):
    seen = {}
    def public(texts):
        seen["texts"] = texts
        return {"US stocks rise": "미국 증시 상승"}
    monkeypatch.setattr(news, "_public_translations", public)
    result = news._fallback([{"headline": "US stocks rise", "url": "https://example.test"}])
    assert seen["texts"] == ["US stocks rise"]
    assert result[0]["brief"] == "미국 증시 상승"


def test_public_translation_batches_and_caches(monkeypatch):
    news._TRANSLATION_CACHE.clear()
    calls = []
    def request(url):
        calls.append(url)
        return {"responseData": {"translatedText": "미국 증시 상승\nJARVISBREAK\n반도체 수요 증가"}}
    monkeypatch.setattr(news, "_request", request)
    texts = ["US stocks rise", "Chip demand grows"]
    assert news._public_translations(texts) == {
        "US stocks rise": "미국 증시 상승", "Chip demand grows": "반도체 수요 증가",
    }
    assert news._public_translations(texts)["US stocks rise"] == "미국 증시 상승"
    assert len(calls) == 1


def test_public_translation_uses_second_provider_only_after_first_fails(monkeypatch):
    news._TRANSLATION_CACHE.clear()
    calls = []
    def request(url):
        calls.append(url)
        if "mymemory" in url:
            raise RuntimeError("first provider unavailable")
        return [[[
            "미국 증시 상승 |||59381||| 반도체 수요 증가",
            "US stocks rise |||59381||| Chip demand grows", None, None,
        ]]]
    monkeypatch.setattr(news, "_request", request)
    result = news._public_translations(["US stocks rise", "Chip demand grows"])
    assert result == {
        "US stocks rise": "미국 증시 상승", "Chip demand grows": "반도체 수요 증가",
    }
    assert len(calls) == 2
    assert "translate.googleapis.com" in calls[1]


def test_rss_fallback_keeps_verifiable_actual_rows(monkeypatch):
    stamp = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    seen = {}
    def request_text(url):
        seen["url"] = url
        return f"""
        <rss><channel><item><title>미국 증시 관련 실제 뉴스</title><link>https://example.test/news</link>
        <pubDate>{stamp}</pubDate><source url="https://example.test">테스트 출처</source></item></channel></rss>
        """
    monkeypatch.setattr(news, "_request_text", request_text)
    rows = news._google_news_rss("market", None)
    assert len(rows) == 1
    assert rows[0]["headline"] == "미국 증시 관련 실제 뉴스"
    assert rows[0]["url"] == "https://example.test/news"
    assert "hl=en-US" in seen["url"] and "gl=US" in seen["url"] and "ceid=US%3Aen" in seen["url"]





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
    market_button = next(node for node in app.button if node.key == "j3b_nav_market")
    assert market_button.label == "시장분석"
    assert any(node.key == "j3b_nav_home" for node in app.button)
    assert any(node.key == "j3b_nav_watch" for node in app.button)
    assert "시장분석" in rendered
    assert "본 정보는 투자 참고용" not in rendered
    source = page.read_text(encoding="utf-8")
    assert ".j3b-card.compact{height:158px!important" not in source
    assert "max-height:none!important;overflow:visible!important" in source
    # 가로로는 잘라 화면 밖으로 밀지 않고, 세로로는 카드가 넘칠 수 있어야 한다.
    # (예전 한 줄짜리 규칙이 두 규칙으로 나뉘었다 — 2026-08-26)
    assert "html:has(.j3b-home),body:has(.j3b-home){overflow-x:hidden!important" in source
    assert ".j3b-card.compact{height:auto!important;min-height:174px!important" in source
    assert ".j3b-card.compact .j3b-card-notes{bottom:14px!important" in source
    assert ".j3b-card:not(.compact){min-height:148px!important" in source
    assert ".j3b-card:not(.compact) .j3b-card-notes{bottom:13px!important" in source
    assert "div.st-key-j3b_grid_selected_0{padding-top:14px!important}" in source
    assert "div.st-key-j3b_grid_selected_2{padding-bottom:14px!important}" in source
    assert ".j3b-card.compact{min-height:164px!important}" in source
    assert "visible_stocks = selected + home_extras" in source
    assert '_render_briefing_grid(home_extras, cards, removable=True' in source
    assert 'can_remove = removable and int(stock.get("position", 0)) > 0' in source
    assert ".j3b-card.compact .j3b-chart{display:block!important" in source
    assert 'div[class*="st-key-j3b_del_"]:not([class*="st-key-j3b_del_yes_"])' in source
    assert 'delete_visual = ""' in source
    assert ".j3b-bottom-nav{position:fixed" in source
    assert ".j3b-bottom-nav{width:100vw!important;max-width:430px!important;height:64px!important" in source
    assert 'width:33.333%!important;height:58px!important;flex:0 0 33.333%!important' in source
    assert 'st.columns(3, gap="small")' in source
    assert '("mypage", "♙", "마이페이지")' not in source
    assert 'deepl_key=_briefing_secret("DEEPL_API_KEY")' in source
    assert "원하는 테마 이름을 누르면 테마 종목 화면이 이 자리에 열립니다." not in source
    assert '"""20개 미국 테마의 전체 종목에서 상승추세 조정을 찾는다."""' not in source
    assert '[data-testid="stElementContainer"],div.st-key-j3b_nav_controls [data-testid="stColumn"] [data-testid="stButton"]{width:100%' in source
    assert 'st.session_state["j3_briefing_page"] = "home"' in source
    # 장식 그림은 배경을 오려 낸 파일이라 네모를 가리던 타원 마스크가 필요 없다(2026-08-26).
    assert "mask-image:radial-gradient" not in source
    assert '_briefing_asset_uri("hero_catbus_cut.png")' in source
    assert "soot_lamp_cut.png" in source
    assert 'st.switch_page("app.py")' in source


def test_search_plus_adds_the_first_matching_extra_stock():
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
         patch("jarvis3_briefing_store.add_extra") as add_extra, \
         patch("jarvis3_data.get_briefing_cards", return_value=cards), \
         patch("jarvis3_briefing_news.get_or_schedule", return_value={"ok": True, "items": []}):
        app = AppTest.from_file(str(page), default_timeout=30)
        app.secrets["APP_PASSWORD"] = "test"
        app.session_state["authenticated"] = True
        app.session_state["jarvis_access_role"] = "owner"
        app.run(timeout=30)
        next(node for node in app.text_input if node.key == "j3b_search").input("애플").run(timeout=30)
        next(node for node in app.button if node.key == "j3b_manage_toggle").click().run(timeout=30)
    add_extra.assert_called_once_with("AAPL", "Apple")


def test_briefing_search_uses_the_existing_local_universe_only():
    page = Path(__file__).parent / "pages" / "2_자비스3.py"
    source = page.read_text(encoding="utf-8")
    assert "def _briefing_local_search" in source
    assert "US_LARGE_CAP_UNIVERSE" in source
    briefing_block = source[source.index("def _briefing_local_search"):source.index("def _schedule_briefing_news_refresh")]
    assert "search_stocks(" not in briefing_block


def test_search_plus_adds_ionq_from_existing_theme_universe():
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
         patch("jarvis3_briefing_store.add_extra") as add_extra, \
         patch("jarvis3_data.get_briefing_cards", return_value=cards), \
         patch("jarvis3_briefing_news.get_or_schedule", return_value={"ok": True, "items": []}):
        app = AppTest.from_file(str(page), default_timeout=30)
        app.secrets["APP_PASSWORD"] = "test"
        app.session_state["authenticated"] = True
        app.session_state["jarvis_access_role"] = "owner"
        app.run(timeout=30)
        next(node for node in app.text_input if node.key == "j3b_search").input("Ionq").run(timeout=30)
        next(node for node in app.button if node.key == "j3b_manage_toggle").click().run(timeout=30)
    add_extra.assert_called_once_with("IONQ", "IonQ")


def test_only_articles_about_that_stock_are_kept():
    """이름만 비슷한 다른 회사·국내장 기사를 카드에서 걸러 낸다.

    구글뉴스는 비슷하기만 해도 물어 온다. 2026-08-26에 실제로 테슬라 칸에 모더나
    기사가, 브로드컴 칸에 코스피 기사가, 메타 칸에 메타플래닛 기사가 올라왔다.
    """
    cases = [
        ("META", "메타바이오메드 주식 700주 ↑", False),
        ("META", "메타플래닛, 5거래일간 45% 급등", False),
        ("META", "메타는 올랐는데 알파벳은 빠졌습니다", True),
        ("RGTI", "아이온큐·리게티컴퓨팅 등 급등…美 양자컴퓨터주 강세", True),
        ("TSLA", "모더나 주가 하루만에 177% 폭등", False),
        ("TSLA", "테슬라, 로보택시 사이버캡 9월 3일 공개", True),
        ("AVGO", "삼전닉스 휘청에 코스피 하락 지속…엔비디아 실적 주시", False),
        ("AVGO", "브로드컴(AVGO) 구글 계약 변화 이후", True),
        ("AMD", "레이몬드 제임스, AMD 주식 등급 상향", True),
    ]
    for ticker, headline, keep in cases:
        assert news._is_about({"headline": headline}, "company", ticker) is keep, headline


def test_market_briefing_drops_domestic_market_articles():
    assert news._is_about({"headline": "[시황] 미국증시, 기술주 반등"}, "market", None)
    assert news._is_about({"headline": "뉴욕증시 3대 지수 일제히 상승"}, "market", None)
    assert not news._is_about({"headline": "코스피, 외국인 매도에 하락 마감"}, "market", None)

def test_only_us_media_is_used(monkeypatch):
    """뉴스원은 미국 매체뿐이다. 한글 매체는 쓰지 않는다.

    2026-08-26 상하님 — "미국시장 한줄 브리핑 이거 미국뉴스에서 갖고 와야 된다.
    지금 보니 서울신문도 있네." 네이버와 한글 구글뉴스를 뉴스원에서 뺐다.
    """
    assert not hasattr(news, "_naver_news")
    assert not hasattr(news, "_google_news_rss_ko")
    row = {"headline": "Wall Street ends higher as tech rebounds", "summary": "",
           "source": "Reuters", "url": "https://example.test/us",
           "published_at": datetime.now(timezone.utc).isoformat()}
    monkeypatch.setattr(news, "_google_news_rss", lambda *_args: [row])
    monkeypatch.setattr(news, "_public_translations",
                        lambda *_args: {row["headline"]: "월가, 기술주 반등에 상승 마감"})
    result = news._load("market:", "market", None, "", "", "id", "secret")
    assert result["items"][0]["source"] == "Reuters"
    assert result["items"][0]["brief"] == "월가, 기술주 반등에 상승 마감"


def test_untranslated_headline_stays_in_english(monkeypatch):
    """그날 번역이 다 막혀도 미국 매체 기사를 그대로 보여 준다. 한글 기사로 바꾸지 않는다."""
    row = {"headline": "Wall Street ends higher", "summary": "", "source": "Reuters",
           "url": "https://example.test/us", "published_at": datetime.now(timezone.utc).isoformat()}
    monkeypatch.setattr(news, "_google_news_rss", lambda *_args: [row])
    monkeypatch.setattr(news, "_public_translations", lambda *_args: {})
    monkeypatch.setattr(news.deepl_translate, "translate_texts_to_ko", lambda *_args: [])
    result = news._load("market:", "market", None, "", "")
    assert result["items"][0]["brief"] == "Wall Street ends higher"
    assert result["items"][0]["source"] == "Reuters"


def test_english_articles_about_other_companies_are_dropped():
    """영어 기사도 그 회사 이야기만 남긴다. 티커 세 글자가 없어도 이름으로 가른다."""
    keep = [("TSM", "Taiwan Semiconductor Manufacturing beats estimates"),
            ("GOOGL", "Alphabet stock looks below fair value"),
            ("IONQ", "IonQ names former Samsung executive to its board"),
            ("QCOM", "Qualcomm is poised for a breakout")]
    drop = [("TSM", "Apple unveils a new Mac lineup"),
            ("GOOGL", "Tesla gives older cars a major FSD boost")]
    for ticker, headline in keep:
        assert news._is_about({"headline": headline}, "company", ticker), headline
    for ticker, headline in drop:
        assert not news._is_about({"headline": headline}, "company", ticker), headline
