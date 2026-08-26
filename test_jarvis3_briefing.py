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
    # 머리띠 배경은 견본(visual_reference.png)에서 잘라 낸 장면 한 장이다.
    # 그 안에 지구·도시·구름·고양이버스가 다 들어 있다(2026-08-26).
    assert '_briefing_asset_uri("hero_scene.png")' in source
    assert ".j3b-hero:has(.j3b-hero-scene):before" in source
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
