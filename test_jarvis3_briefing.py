"""종목 브리핑의 설정 저장·뉴스 후보 축소 회귀 시험."""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timedelta, timezone
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
    # 2026-08-27 상하님 지시로 여섯 자리다 — "사용자 선정 종목은 SKHY, SPCX
    # 2개 더 넣으면 되겠네." 태블릿에서 3칸 2줄로 놓으면 여섯이 딱 찬다.
    assert [row["ticker"] for row in selected] == [
        "NVDA", "TSLA", "PLTR", "AMD", "SKHY", "SPCX"]
    store.replace_selected(2, "META", "Meta Platforms")
    assert store.selected_stocks()[1]["ticker"] == "META"
    assert len(store.selected_stocks()) == 6


def test_extra_stocks_keep_order_and_limit(monkeypatch):
    """자리는 12개다 — 기본 4종목이 실제 줄이 되면서 8에서 늘렸다(2026-08-26)."""
    _isolated_store(monkeypatch)
    limit = store.EXTRA_LIMIT
    assert limit == 12
    for number in range(limit):
        store.add_extra(f"X{number}", f"X {number}")
    assert [row["ticker"] for row in store.extra_stocks()] == [f"X{number}" for number in range(limit)]
    try:
        store.add_extra("OVER", "Over")
    except ValueError as exc:
        assert f"최대 {limit}개" in str(exc)
    else:
        raise AssertionError("자리를 넘겨 저장됐다")
    store.remove_extra(3)
    assert [row["position"] for row in store.extra_stocks()] == list(range(1, limit))


def test_default_extras_become_real_rows_once(monkeypatch):
    """기본 4종목을 한 번만 실제 줄로 옮겨 적는다 — 그래야 ×로 지울 수 있다.

    2026-08-26 상하님 물음 — "RGTI 리게티 컴퓨팅은 x가 왜 없냐?"
    예전에는 화면이 자리만 만들어 보여 줬고 저장고에는 없어서 지울 수가 없었다.
    지운 뒤에 다시 불러도 되살아나면 안 된다.
    """
    _isolated_store(monkeypatch)
    store.ensure_default_extras()
    assert [row["ticker"] for row in store.extra_stocks()] ==         [ticker for ticker, _name in store.DEFAULT_EXTRAS]
    store.ensure_default_extras()
    assert len(store.extra_stocks()) == len(store.DEFAULT_EXTRAS)
    store.remove_extra(4)                      # RGTI 를 지운다
    store.ensure_default_extras()
    assert "RGTI" not in [row["ticker"] for row in store.extra_stocks()]


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
    # 카드는 이제 한 통에 죽 들어가고 자리는 CSS가 잡는다(2026-08-27).
    # 예전에는 두 개씩 묶어 그려서 통 이름이 _0 · _2 로 나뉘어 있었다.
    assert "div.st-key-j3b_grid_selected{padding-top:14px!important;padding-bottom:14px!important}" in source
    assert "grid-template-columns:repeat(2,minmax(0,1fr))" in source, "기본은 두 칸이다"
    assert ".j3b-card.compact{min-height:164px!important}" in source
    assert "visible_stocks = selected + home_extras" in source
    assert '_render_briefing_grid(home_extras, cards, removable=True' in source
    assert 'can_remove = removable and int(stock.get("position", 0)) > 0' in source
    assert ".j3b-card.compact .j3b-chart{display:block!important" in source
    assert 'div[class*="st-key-j3b_del_"]:not([class*="st-key-j3b_del_yes_"])' in source
    assert 'delete_visual = ""' in source
    assert ".j3b-bottom-nav{position:fixed" in source
    assert ".j3b-bottom-nav{width:100vw!important;max-width:430px!important;height:64px!important" in source
    # 칸 하나가 셋 가운데 하나를 차지한다. 키는 이동표와 같은 값을 쓰므로
    # 여기서 픽셀을 외우지 않는다(2026-08-26).
    assert 'div.st-key-j3b_nav_controls [data-testid="stColumn"]{width:33.333%!important' in source
    assert 'st.columns(3, gap="small")' in source
    assert '("mypage", "♙", "마이페이지")' not in source
    assert 'deepl_key=_briefing_secret("DEEPL_API_KEY")' in source
    assert "원하는 테마 이름을 누르면 테마 종목 화면이 이 자리에 열립니다." not in source
    assert '"""20개 미국 테마의 전체 종목에서 상승추세 조정을 찾는다."""' not in source
    assert '[data-testid="stElementContainer"],div.st-key-j3b_nav_controls [data-testid="stColumn"] [data-testid="stButton"]{width:100%' in source
    assert 'st.session_state["j3_briefing_page"] = "home"' in source
    # 장식 그림은 배경을 오려 낸 파일이라 네모를 가리던 타원 마스크가 필요 없다(2026-08-26).
    assert "mask-image:radial-gradient" not in source
    # 머리띠 배경은 견본(visual_reference.png)에서 잘라 낸 장면 한 장이다.
    # 그 안에 지구·도시·구름·고양이버스가 다 들어 있다(2026-08-26).
    assert '_briefing_asset_uri("hero_scene.webp")' in source
    # 캐릭터 그림은 카드마다 넣지 않고 CSS에 네 장만 한 번씩 싣는다(2026-08-26).
    assert "def _decor_css()" in source
    assert '<span class="j3b-decor-img ' in source
    assert ".j3b-hero:has(.j3b-hero-scene):before" in source
    assert "soot_lamp_cut.webp" in source
    assert 'st.switch_page("app.py")' in source


def test_search_shows_the_match_and_adds_only_after_confirming():
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
        # ＋ 만으로는 넣지 않는다. 찾은 종목을 보여 주고 확인을 받는다(2026-08-26).
        add_extra.assert_not_called()
        assert app.session_state["j3b_search_found"][0]["ticker"] == "AAPL"
        next(node for node in app.button if node.key == "j3b_search_ok").click().run(timeout=30)
    add_extra.assert_called_once_with("AAPL", "Apple")


def test_briefing_search_tries_the_local_list_first_then_the_whole_listing():
    """가진 200종목 명부에서 먼저 찾고, 없을 때만 미국 거래소 전체 명부로 넓힌다.

    2026-08-26 상하님 지적 — SPCX(스페이스X)가 안 들어갔다. 200종목에 없어서였다.
    전체 명부는 처음 한 번 받는 데 몇 초 걸리므로, 먼저 찾아보고 없을 때만 간다.
    """
    page = Path(__file__).parent / "pages" / "2_자비스3.py"
    source = page.read_text(encoding="utf-8")
    block = source[source.index("def _briefing_local_search"):source.index("def _schedule_briefing_news_refresh")]
    assert "US_LARGE_CAP_UNIVERSE" in block
    # 가진 명부에서 찾은 것이 있으면 거기서 끝난다.
    assert block.index("if rows:") < block.index("j3data.search_stocks(")
    assert "j3data.search_stocks(query, limit=12)" in block


def test_search_confirms_ionq_from_existing_theme_universe():
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
        add_extra.assert_not_called()
        next(node for node in app.button if node.key == "j3b_search_ok").click().run(timeout=30)
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


def test_same_story_from_two_outlets_is_shown_once():
    """주소가 달라도 제목이 같은 기사는 한 줄만 싣는다."""
    stamp = datetime.now(timezone.utc).isoformat()
    rows = [
        {"headline": "US Stock Market Today: S&P 500 Futures Edge Lower As Inflation Jitters Linger",
         "url": "https://a.test/1", "published_at": stamp},
        {"headline": "US Stock Market Today: S&P 500 Futures Edge Lower As Strong PMI Data Lands",
         "url": "https://b.test/2", "published_at": stamp},
        {"headline": "Nvidia earnings loom over Wall Street", "url": "https://c.test/3",
         "published_at": stamp},
    ]
    kept = news._dedupe(rows)
    assert len(kept) == 2
    assert kept[1]["headline"].startswith("Nvidia")

def _quiet_translation_book(monkeypatch, tmp_path):
    """시험이 진짜 공책(cache/j3_translations.json)을 읽거나 더럽히지 않게 막는다."""
    news._TRANSLATION_CACHE.clear()
    monkeypatch.setattr(news, "_TRANSLATION_FILE", tmp_path / "book.json")
    monkeypatch.setattr(news, "_TRANSLATION_LOADED", False)


def test_public_translation_batches_and_caches(monkeypatch, tmp_path):
    """한 번에 묶어 옮기고, 같은 제목은 다시 부르지 않는다."""
    _quiet_translation_book(monkeypatch, tmp_path)
    calls = []

    def request(url):
        calls.append(url)
        return ["미국 증시 상승", "반도체 수요 증가"]

    monkeypatch.setattr(news, "_request", request)
    texts = ["US stocks rise", "Chip demand grows"]
    assert news._public_translations(texts) == {
        "US stocks rise": "미국 증시 상승", "Chip demand grows": "반도체 수요 증가",
    }
    assert news._public_translations(texts)["US stocks rise"] == "미국 증시 상승"
    assert len(calls) == 1
    assert "clients5.google.com" in calls[0]


def test_next_provider_takes_over_when_the_first_is_blocked(monkeypatch, tmp_path):
    """번역기 한 곳이 막히면 다음이 반드시 이어받는다.

    2026-08-26에 세 곳 가운데 둘(gtx·MyMemory)이 같은 날 429로 막혔다. 예전에는
    첫 곳이 실패하면 continue가 batch를 통째로 건너뛰어 둘째가 돌지 않았다.
    """
    _quiet_translation_book(monkeypatch, tmp_path)
    calls = []

    def request(url):
        calls.append(url)
        if "clients5.google.com" in url:
            raise RuntimeError("첫 번역기 막힘")
        if "mymemory" in url:
            raise RuntimeError("둘째 번역기 막힘")
        return [[[
            "미국 증시 상승 |||59381||| 반도체 수요 증가",
            "US stocks rise |||59381||| Chip demand grows", None, None,
        ]]]

    monkeypatch.setattr(news, "_request", request)
    result = news._public_translations(["US stocks rise", "Chip demand grows"])
    assert result == {
        "US stocks rise": "미국 증시 상승", "Chip demand grows": "반도체 수요 증가",
    }
    assert len(calls) == 3
    assert "translate.googleapis.com" in calls[2]


def test_translated_titles_survive_a_restart(monkeypatch, tmp_path):
    """한 번 옮긴 제목은 공책에 남아, 번역기가 다 막힌 날에도 한글로 나온다."""
    _quiet_translation_book(monkeypatch, tmp_path)
    monkeypatch.setattr(news, "_request", lambda url: ["미국 증시 상승"])
    assert news._public_translations(["US stocks rise"]) == {"US stocks rise": "미국 증시 상승"}

    # 앱을 다시 켠 셈 치고 기억만 지운다. 공책은 그대로 둔다.
    news._TRANSLATION_CACHE.clear()
    monkeypatch.setattr(news, "_TRANSLATION_LOADED", False)

    def blocked(_url):
        raise RuntimeError("번역기가 다 막혔다")

    monkeypatch.setattr(news, "_request", blocked)
    assert news._public_translations(["US stocks rise"]) == {"US stocks rise": "미국 증시 상승"}

def test_a_failed_refresh_keeps_the_news_already_on_screen():
    """뒤에서 다시 받다가 실패해도 **화면에 있던 뉴스를 지우지 않는다**.

    2026-08-26 상하님 지적 — "왜 자꾸 뉴스를 불러오는 중이라고 됐다 안 됐다
    그러냐." 실패할 때마다 옛 결과를 빈 것으로 덮어쓰고 있었다. 그러면 잘
    나오던 카드가 갑자기 「불러오는 중」으로 되돌아간다. 온라인은 무료 뉴스
    자리에서 이따금 거절당하므로 이 일이 자주 나고, 노트북에서는 거의 안 나서
    눈에 안 띄었다.
    """
    import time
    news.clear_cache()
    # 먼저 정상으로 한 벌 담아 둔다 (통신 없이 가짜로 넣는다).
    with news._LOCK:
        news._CACHE["stock:AAA"] = {
            "updated_at": 0,
            "result": {"ok": True, "items": [{"brief": "옛 뉴스"}]},
        }
    boom = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("일부러 낸 실패"))
    original = news._load
    news._load = boom
    try:
        during = news.get_or_schedule("stock", "AAA")
        assert during.get("items"), "다시 받는 동안 옛 뉴스가 사라졌다"
        for _ in range(60):
            if news.peek("stock", "AAA") == "ready":
                break
            time.sleep(0.05)
        after = news.get_or_schedule("stock", "AAA")
    finally:
        news._load = original
    assert after.get("items"), "실패한 뒤 옛 뉴스가 지워졌다"
    assert after["items"][0]["brief"] == "옛 뉴스"
    with news._LOCK:
        assert news._CACHE["stock:AAA"].get("failed"), "다시 받을 표시가 없다"


def test_an_empty_result_does_not_wipe_good_news():
    """빈손으로 돌아와도 옛 뉴스를 지우지 않는다 — 화면에서는 같은 뜻이다."""
    news.clear_cache()
    with news._LOCK:
        news._CACHE["stock:BBB"] = {
            "updated_at": 0,
            "result": {"ok": True, "items": [{"brief": "옛 뉴스"}]},
        }
    original = news._load
    news._load = lambda *a, **k: {"ok": True, "items": []}
    try:
        import time
        news.get_or_schedule("stock", "BBB")
        for _ in range(60):
            if news.peek("stock", "BBB") == "ready":
                break
            time.sleep(0.05)
        after = news.get_or_schedule("stock", "BBB")
    finally:
        news._load = original
    assert after["items"][0]["brief"] == "옛 뉴스", "빈손으로 돌아와 옛 뉴스를 지웠다"

def test_the_open_card_shows_a_six_month_daily_chart():
    """종목을 누르면 **일봉 6개월** 그림이 나오고 그 밑에 뉴스가 온다.

    2026-08-26 상하님 지시 — "관심종목에 종목 클릭하면 일봉 6개월 차트 나오고
    밑에 종목 뉴스 나오게 해 줘."

    접힌 카드의 작은 그림은 예전 그대로 최근 30일이다. 값이 바뀌지 않는 것도
    실측으로 확인했다 — 3개월치로 잰 현재가·등락과 6개월치로 잰 것이 소수점까지
    같고 마지막 30개 종가도 똑같다. 실측 — 작은 그림 30점, 큰 그림 125점.
    """
    page = (Path(__file__).parent / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
    card = page[page.index("    open_card = ("):]
    card = card[:card.index("    card_html = (")]
    assert 'six_month or card.get("chart")' in card, "크게 연 카드가 6개월치를 안 쓴다"
    assert "일봉 6개월" in card, "이름표가 없다"
    # 그림 **뒤에** 뉴스가 와야 한다.
    assert card.index("_briefing_chart(") < card.index("_news_accordion_html("),         "뉴스가 그림보다 위에 있다"
    # **접힌 카드의 작은 그림은 2026-08-28부터 당일이다** (상하님 지적 — "각
    # 종목들 차트가 종가 기준 일봉 차트 맞냐? 뭐가 뭔지 모르겠다. 당일 종가가
    # 되면 당일 차트를 해 줘야지"). 바로 옆에 적히는 값·등락률이 오늘 것인데
    # 그림만 최근 30일이라 둘이 다른 이야기를 하고 있었다.
    # 당일 자료가 없는 날(주말·휴장)에는 예전처럼 최근 30일로 되돌아간다.
    body = page[page.index("    card_body = ("):page.index("    six_month = [")]
    assert 'card.get("chart_today") or card.get("chart")' in body, "접힌 카드가 당일이 아니다"
    assert 'base=card.get("prev_close")' in body, "당일 그림의 기준선이 전일 종가가 아니다"


def test_the_card_data_carries_both_series():
    """카드 자료에 최근 30일과 6개월치가 **둘 다** 실려 있어야 한다."""
    source = (Path(__file__).parent / "jarvis3_data.py").read_text(encoding="utf-8")
    fn = source[source.index("def get_briefing_cards("):]
    fn = fn[:fn.index(chr(10) + "def ", 10)]
    assert 'period="6mo"' in fn, "6개월치를 안 받는다"
    # 2026-09-03 — 그림을 만드는 자리가 `series` 에서 `chart_all` 로 바뀌었다.
    # 야후 일봉이 마지막으로 끝난 장을 아직 안 올린 판에서는 그 장의 종가를
    # 끝에 붙여야 하는데(_daily_lags_last_session), `series` 를 그대로 쓰면
    # 붙일 자리가 없다. **뜻은 그대로다** — 작은 그림은 최근 30일, 큰 그림은 전부.
    assert '"chart": chart_all[-30:]' in fn, "작은 그림이 최근 30일이 아니다"
    assert '"chart6m": chart_all' in fn, "6개월치를 안 싣는다"
    assert '_daily_lags_last_session(' in fn, "일봉이 늦은 판을 안 본다"

def test_the_chart_line_does_not_get_thick_when_stretched():
    """그림을 늘려도 선은 굵어지지 않는다 (2026-08-26 상하님 지적).

    상하님 — "종목 클릭하면 나오는 차트 선이 너무 굵다."

    이 그림은 preserveAspectRatio="none" 으로 늘려 그린다. 그러면 선도 같이
    늘어난다 — 크게 연 카드는 가로로 6.3배가 되어 선이 **7.9px** 로 그려지고
    있었다(브라우저 실측). vector-effect="non-scaling-stroke" 를 주면 어느
    크기에서나 적어 준 만큼만 굵다. 실측 — 7.9px → 1.8px.
    """
    page = (Path(__file__).parent / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
    fn = page[page.index("def _briefing_chart("):]
    fn = fn[:fn.index(chr(10) + "def ", 10)]
    assert 'vector-effect="non-scaling-stroke"' in fn, "늘리면 선까지 굵어진다"
    assert ".j3b-open-card .j3b-chart polyline{stroke-width:1.8px}" in page,         "크게 연 그림의 선 굵기를 안 정했다"
    # 이름표는 조금 더 크게 (상하님 — "일봉 6개월 글자 조금 더 크게").
    assert ".j3b-chart-cap{color:#4da6ff;font-size:15px" in page


def test_the_six_month_chart_has_a_start_line_with_two_colours():
    """일봉 6개월 그림은 시작가에 기준선을 긋고 위아래를 다른 색으로 그린다.

    2026-08-28 상하님 지시 — 야후 파이낸스 폰 화면의 테슬라 6개월 그림처럼
    "시작가 위로 초록색이고 밑으로는 붉은색인데 이것처럼 기준선이 있어야 되지 않나?"
    """
    page = (Path(__file__).parent / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
    namespace: dict = {}
    exec(page[page.index("_BASE_UP_STROKE = "):page.index("def _briefing_items(")], namespace)
    chart = namespace["_briefing_chart"]
    # 시작가 100에서 내려갔다가 올라오는 반년치
    values = [100, 96, 92, 88, 95, 103, 110, 105, 99, 101]
    drawn = chart(values, 2.4, baseline=True)
    assert "stroke-dasharray" in drawn, "기준선이 없다"
    assert namespace["_BASE_UP_STROKE"] in drawn and namespace["_BASE_DOWN_STROKE"] in drawn, \
        "위아래 색이 갈리지 않았다"
    # 가로지르는 자리마다 끊으므로 조각이 여럿이다. 칸마다 그리면 아홉 조각이 된다.
    assert 2 <= drawn.count("<polyline") <= 6, f"조각 수가 이상하다: {drawn.count('<polyline')}"
    # 접힌 카드의 작은 그림은 예전 그대로 — 기준선 없이 한 색이다.
    plain = chart(values, 2.4)
    assert "dasharray" not in plain and plain.count("<polyline") == 1


def test_the_catbus_orbit_carries_the_selected_logos():
    """고양이버스 둘레를 도는 로고 (2026-08-28 상하님 지시).

    상하님이 보내 주신 영상(catbus_logo_orbit_preview.mp4)처럼 사용자 선정 종목의
    로고가 배너를 돈다. 카드와 **같은 로고**를 써야 한 곳만 고쳐지는 일이 없다.
    """
    page = (Path(__file__).parent / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
    orbit = page[page.index("def _briefing_orbit_html("):]
    orbit = orbit[:orbit.index(chr(10) + "def ", 10)]
    assert "_briefing_logo_face(ticker)" in orbit, "궤도가 카드와 다른 로고를 만든다"
    card = page[page.index("def _render_briefing_card("):]
    assert "_briefing_logo_face(ticker)" in card[:card.index(chr(10) + "def ", 10)], \
        "카드가 떼어 낸 로고 함수를 안 쓴다"
    # 시작 시각을 한 바퀴에 고르게 나눠야 로고가 한 덩어리로 몰려 다니지 않는다.
    assert "-_ORBIT_SECONDS * index / len(riders)" in orbit
    assert 'f\'{catbus_html}{_briefing_orbit_html(selected)}</div>\',' in page, \
        "배너에 궤도를 안 달았다"


def test_the_orbit_does_not_squash_the_logos():
    """세로로 누른 만큼 로고가 거꾸로 늘어나야 로고가 안 찌그러진다.

    팔은 scaleY(.23)으로 눌러 동그라미를 타원으로 만든다. 로고 쪽이 그 역수만큼
    늘리지 않으면 로고가 납작해진다. 한쪽만 고치는 일이 잦아 여기서 잡는다.
    """
    page = (Path(__file__).parent / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
    squash = re.search(r"transform:scaleY\((\.\d+)\) rotate\(0deg\)", page)
    stretch = re.search(r"rotate\(0deg\) scaleY\(([\d.]+)\)", page)
    assert squash and stretch, "누른 값이나 늘린 값을 못 찾았다"
    product = float(squash.group(1)) * float(stretch.group(1))
    assert abs(product - 1.0) < 0.01, f"누른 값 × 늘린 값 = {product:.3f} (1이어야 한다)"


def test_the_three_news_are_the_big_ones_and_stay_until_something_bigger():
    """큰 소식부터 세 줄을 싣고, 더 큰 소식이 올 때만 자리를 바꾼다.

    2026-08-28 상하님 지시 — "주요뉴스 3건을 30분마다 새로 받기를 원하는데 그
    주요뉴스보다 비중이 떨어지는 것은 빼고 … 시시한 거면 그냥 기존 뉴스 두고."
    """
    assert news.CACHE_SECONDS == 1800, "30분이 아니다"
    now = datetime.now(timezone.utc)

    def row(headline, source, hours=1.0, twins=1):
        return {"headline": headline, "source": source, "summary": "", "twins": twins,
                "url": f"https://x.test/{abs(hash(headline))}",
                "published_at": (now - timedelta(hours=hours)).isoformat()}

    ranked = news._rank([
        row("A tiny startup opens an office", "Random Blog", 5),
        row("Fed signals rate cut as inflation cools", "Reuters", 1, twins=4),
        row("Nvidia earnings loom over Wall Street", "CNBC", 2, twins=2),
        row("Dow slips as treasury yields climb", "Bloomberg", 3, twins=2),
    ], "market")
    assert ranked[0]["headline"].startswith("Fed signals"), "여러 매체가 쓴 큰 소식이 맨 위여야 한다"
    assert ranked[-1]["source"] == "Random Blog"

    # 화면에 걸린 세 줄은 다 큰 소식이다.
    held = ranked[:3]
    # 갓 올라온 기사라도 한 곳만 쓴 시시한 것이면 큰 소식을 못 밀어낸다.
    trivial = news._rank([row("A local shop changes its sign", "Random Blog", 0.05)], "market")
    assert [item["headline"] for item in news._merge_by_importance(held, trivial)] == \
        [item["headline"] for item in held], "시시한 새 기사가 걸린 줄을 밀어냈다"

    bigger = news._rank([row("Fed cuts rates in emergency move", "Reuters", 0.1, twins=5)], "market")
    after = news._merge_by_importance(held, bigger)
    assert after[0]["headline"].startswith("Fed cuts rates"), "더 큰 소식이 안 들어왔다"
    assert len(after) == 3

    stale = row("Yesterday's story", "Reuters", 30, twins=5)
    stale["weight"] = 99.0
    kept = news._merge_by_importance([stale], news._rank([row("Fresh item", "CNBC", 0.5)], "market"))
    assert not any(item["headline"].startswith("Yesterday") for item in kept), \
        "하루 지난 줄이 자리를 안 비웠다"


def test_stock_news_gets_the_same_tidying_as_the_market_news():
    """종목 뉴스도 시장 뉴스와 **같은 규칙**을 탄다 (2026-08-28 상하님 지시).

    상하님 — "뉴스 정리는 미국시장 한줄 브리핑만 하냐? 종목뉴스도 같이 적용해 줘."

    한 길(`_load`)이 시장·종목을 함께 처리하므로 큰 소식 고르기와 30분 갈아 끼우기는
    처음부터 둘 다에 걸린다. 다만 '큰 이야기'를 재는 낱말만 갈라 둔다 — 시장 카드는
    시장 전체를 흔드는 일, 종목 카드는 **그 회사에 실제로 생긴 일**이다.
    """
    source = Path(__file__).parent.joinpath("jarvis3_briefing_news.py").read_text(encoding="utf-8")
    load = source[source.index("def _load("):]
    load = load[:load.index(chr(10) + "def ", 10)]
    assert "_rank(rows, kind)" in load, "큰 소식부터 줄 세우기가 한 길에 없다"
    assert "_merge_by_importance(held, picked)" in load, "갈아 끼우기가 한 길에 없다"
    assert "if kind ==" not in load, "시장·종목이 서로 다른 길로 간다"

    now = datetime.now(timezone.utc)

    def row(headline, source_name="CNBC", hours=1.0, twins=1):
        return {"headline": headline, "source": source_name, "summary": "", "twins": twins,
                "url": f"https://x.test/{abs(hash(headline))}",
                "published_at": (now - timedelta(hours=hours)).isoformat()}

    ranked = news._rank([
        row("Why Tesla stock could be a buy for patient investors", "Motley Fool", 2),
        row("Tesla recalls 12,000 vehicles over a software issue", "Reuters", 1, twins=3),
        row("Tesla beats delivery estimates for the quarter", "CNBC", 3, twins=2),
    ], "company")
    assert "recalls" in ranked[0]["headline"], "그 회사에 생긴 일이 맨 위여야 한다"
    assert ranked[-1]["source"] == "Motley Fool", "풀이 글이 맨 아래여야 한다"

    # 같은 조건이면 '그 회사에 생긴 일' 낱말이 든 쪽이 높다.
    plain = news._importance(row("Tesla stock moves in Tuesday trading"), "company")
    event = news._importance(row("Tesla wins a 2 billion dollar contract"), "company")
    assert event > plain, "종목 카드에서 큰 소식 낱말이 점수를 못 받는다"


def test_trivial_lines_do_not_freeze_the_card():
    """시시한 줄끼리 있을 때는 새 기사가 그냥 들어온다 (2026-08-28 상하님 물음).

    상하님 — "테슬라는 뉴스가 안 바뀐 것 아닌가?"

    실측으로 까닭이 나왔다. 그날 테슬라 기사 10건이 전부 작은 매체 한 곳짜리라
    점수가 1.31 · 1.20 · 1.20 으로 붙어 있었고, '오래 두기' 덤 0.4 가 그 차이보다
    커서 새 기사가 아무리 와도 자리를 못 뺏었다. 같은 시각 미국시장 쪽은
    3.81 · 3.67 · 2.60 이라 잘 갈렸다.

    상하님 말씀은 "**중요 뉴스면** 좀 더 오래 두고"였으므로, 덤은 큰 소식에만 준다.
    """
    now = datetime.now(timezone.utc)

    def row(headline, source_name, hours, twins=1):
        return {"headline": headline, "source": source_name, "summary": "", "twins": twins,
                "url": f"https://x.test/{abs(hash(headline))}",
                "published_at": (now - timedelta(hours=hours)).isoformat()}

    # 걸린 줄이 다 시시하면(2.0 아래) 새 기사가 들어온다.
    trivial_held = news._rank([
        row("Tesla stock trading higher today", "MarketBeat", 12),
        row("TSLA stock watch: what to know", "Stocktwits", 14),
        row("A look at TSLA charts", "Stocktwits", 16),
    ], "company")
    self_max = max(item["weight"] for item in trivial_held)
    assert self_max < news._STAY_FLOOR, "이 시험의 전제가 깨졌다 — 걸린 줄이 시시해야 한다"
    fresh = news._rank([row("Tesla opens a new store", "Local Paper", 0.1)], "company")
    after = news._merge_by_importance(trivial_held, fresh)
    assert after[0]["headline"].startswith("Tesla opens"), "시시한 줄이 화면을 붙잡고 있다"

    # 걸린 줄이 큰 소식이면 시시한 새 기사가 못 밀어낸다(앞 시험과 같은 규칙).
    big_held = news._rank([
        row("Fed signals rate cut as inflation cools", "Reuters", 1, twins=4),
        row("Nvidia earnings loom over Wall Street", "CNBC", 2, twins=2),
        row("Dow slips as treasury yields climb", "Bloomberg", 3, twins=2),
    ], "market")
    assert min(item["weight"] for item in big_held) >= news._STAY_FLOOR
    kept = news._merge_by_importance(big_held, news._rank(
        [row("A local shop changes its sign", "Random Blog", 0.05)], "market"))
    assert [item["headline"] for item in kept] == [item["headline"] for item in big_held], \
        "큰 소식이 시시한 새 기사에 밀렸다"


def test_news_keeps_being_watched_until_it_arrives():
    """뉴스가 오는 동안 **화면을 다시 그려 볼 것이 있어야** 한다 (2026-09-02).

    상하님 — *"관심종목에 「뉴스 불러오는 중이다」라고 계속 떠 있다. 위에 다시
    실행하기 하면 그제서야 뉴스가 나온다."*

    까닭 — `_schedule_briefing_news_refresh` 는 아직 안 왔으면 그냥 되돌아간다.
    다음 판을 만들어 주는 것이 없으니 영영 그 자리였다. 2026-08-26에 2.5초마다
    브라우저를 통째로 새로고침하던 것을 걷어내면서 그 자리를 안 채운 탓이다.
    """
    page = Path(__file__).parent / "pages" / "2_자비스3.py"
    source = page.read_text(encoding="utf-8")

    # ① 지켜보는 조각이 있어야 하고, **스스로 다시 돌아야** 한다.
    assert "def _briefing_news_watcher(" in source, "지켜보는 조각이 없다"
    head = source[:source.index("def _briefing_news_watcher(")]
    assert head.rstrip().endswith(")"), "조각 위에 데코레이터가 없다"
    decorator = head.rstrip().rsplit(chr(10), 1)[-1]
    assert "st.fragment" in decorator and "run_every" in decorator, (
        f"스스로 다시 도는 조각이 아니다: {decorator}")

    body = source[source.index("def _briefing_news_watcher("):]
    body = body[:body.index(chr(10) + "def ", 10)]

    # ② 새로 온 것이 없으면 **화면을 안 건드린다** — 2초마다 판 전체를 그리면
    #    화면이 버벅거린다(2026-08-26에 걷어낸 그 문제로 되돌아간다).
    assert "if ready <= int(seen) and not over:" in body, "새 것이 없어도 다시 그린다"

    # ③ 왔을 때는 **판 전체**를 다시 그린다 — 카드가 이 조각 밖에 있다.
    assert 'st.rerun(scope="app")' in body, "판 전체를 안 그린다"

    # ④ 시세·뉴스를 **새로 부르지 않는다** — 이미 받아 둔 것을 세기만 한다.
    assert "ready_count" in body
    for banned in ("get_or_schedule", "get_live_quote", "_download"):
        assert banned not in body, f"{banned} 로 새로 받아 온다 — 2초마다 돌면 안 된다"

    # ⑤ 오는 중일 때만 그린다 — 다 왔으면 이 조각도 더 안 돈다.
    call = source[source.index("_schedule_briefing_news_refresh(news_keys)"):]
    call = call[:call.index("_warm_after_news")]
    assert '_briefing_news_watcher(news_keys)' in call, "부르는 자리가 없다"
    assert 'if st.session_state.get("j3b_news_pending")' in call, (
        "다 온 뒤에도 계속 돈다")

    # ⑥ 한없이 기다리지 않는다.
    assert "> 120" in body, "그만 기다리는 자리가 없다"
