"""뉴스 본문 읽기 (2026-09-17 상하님 지시 '가' — 광고 없이 본문만 한글로 앱 안에서)."""

import unittest
from pathlib import Path
from unittest.mock import patch

import jarvis3_news_reader as reader

ROOT = Path(__file__).parent

_ARTICLE = """
<html><head>
<meta property="og:description" content="Amundi lessened its position in shares of Tesla by 9.5% in the second quarter, filing shows.">
</head><body>
<nav><p>Markets Stocks Crypto Subscribe to our newsletter today for more</p></nav>
<div class="ad"><p>Advertisement — sign up for the free trial now please</p></div>
<article><div class="body">
<p>Tesla, Inc. (NASDAQ:TSLA - Free Report) shares rose 3% on Tuesday after the company reported stronger deliveries than analysts expected, and trading volume was well above its recent average.</p>
<p>The electric vehicle maker delivered more cars in the quarter, helped by demand in China and a new lower-priced model that arrived in June and sold out in several markets.</p>
<p>Analysts at several banks raised their price targets, although some warned that margins could stay under pressure through next year.</p>
<p>Subscribe to our newsletter</p>
</div></article>
<aside><p>Related: Ten stocks to buy now before the market closes today and tomorrow</p></aside>
<footer><p>Copyright 2026 All rights reserved by the publisher of this website</p></footer>
</body></html>
"""


class ExtractTests(unittest.TestCase):
    def test_keeps_only_the_article_paragraphs(self):
        body, summary = reader.extract_article(_ARTICLE)
        self.assertEqual(len(body), 3)
        self.assertTrue(body[0].startswith("Tesla, Inc. (NASDAQ:TSLA)"))
        self.assertNotIn("Free Report", body[0], "마켓비트 꼬리표는 떼고 문단은 살린다")
        joined = " ".join(body)
        for junk in ("Subscribe", "Advertisement", "Related:", "Copyright"):
            self.assertNotIn(junk, joined)
        self.assertIn("Amundi", summary)

    def test_structured_article_body_is_used_first(self):
        import json

        story = chr(10).join([
            "First paragraph of the story that is long enough to count as a real paragraph here, "
            "with a few more words added for length.",
            "Second paragraph of the story that is also long enough to count, and it keeps going "
            "for a while longer so the whole body is clearly an article.",
            "Third paragraph continues the story with more words and more detail about what "
            "happened in the market today and why it matters to investors watching closely.",
        ])
        page = ('<html><head><script type="application/ld+json">'
                + json.dumps({"@type": "NewsArticle", "articleBody": story})
                + '</script></head><body><p>short</p></body></html>')
        body, _summary = reader.extract_article(page)
        self.assertEqual(len(body), 3)
        self.assertTrue(body[0].startswith("First paragraph"))

    def test_a_price_widget_is_not_an_article(self):
        page = "<html><body><div><p>" + "AMD $ 512.50 $8.30 1.65% IBD Stock Analysis " * 3 + "</p></div></body></html>"
        body, _summary = reader.extract_article(page)
        self.assertEqual(body, [], "문단 하나짜리 시세 조각은 본문으로 치지 않는다")

    def test_trim_stops_at_a_paragraph_boundary(self):
        kept = reader.trim_paragraphs(["a" * 700, "b" * 700, "c" * 700], 1800)
        self.assertEqual(kept, ["a" * 700, "b" * 700])


class ReadTests(unittest.TestCase):
    class _Response:
        def __init__(self, status, text=""):
            self.status_code, self.text = status, text

    def test_paywall_is_marked_blocked(self):
        with patch.object(reader, "resolve_google_news", return_value="https://www.barrons.com/x"), \
             patch.object(reader.requests, "get", return_value=self._Response(401)):
            row = reader.read_article("https://news.google.com/rss/articles/abc")
        self.assertEqual(row["status"], "blocked")

    def test_article_is_translated_to_korean(self):
        with patch.object(reader, "resolve_google_news", return_value="https://example.com/a"), \
             patch.object(reader.requests, "get", return_value=self._Response(200, _ARTICLE)), \
             patch.object(reader, "translate_paragraphs", side_effect=lambda ps: [f"한글 {i}" for i, _ in enumerate(ps)]):
            row = reader.read_article("https://news.google.com/rss/articles/abc")
        self.assertEqual(row["status"], "ok")
        self.assertEqual(row["paragraphs"], ["한글 0", "한글 1", "한글 2"])

    def test_translation_blocked_keeps_english_body(self):
        with patch.object(reader, "resolve_google_news", return_value="https://example.com/a"), \
             patch.object(reader.requests, "get", return_value=self._Response(200, _ARTICLE)), \
             patch.object(reader, "translate_paragraphs", return_value=None):
            row = reader.read_article("https://news.google.com/rss/articles/abc")
        self.assertEqual(row["status"], "english")
        self.assertEqual(len(row["paragraphs"]), 3)

    def test_never_uses_deepl(self):
        """제목 번역이 DeepL 한도를 쓴다 — 본문까지 보내면 며칠 만에 제목이 영어로 돌아간다."""
        source = (ROOT / "jarvis3_news_reader.py").read_text(encoding="utf-8")
        code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
        code = code.split('"""', 2)[-1]
        self.assertNotIn("deepl", code.lower())


class ScreenWiringTests(unittest.TestCase):
    def test_news_loading_does_not_wait_for_articles(self):
        """본문을 기다리게 했더니 여섯 종목 뉴스가 1.4초 → 5.4초로 늦어졌다(2026-09-17 실측)."""
        source = (ROOT / "jarvis3_briefing_news.py").read_text(encoding="utf-8")
        body = source[source.index("def _load("):source.index("def _news_reader(")]
        self.assertIn("reader.schedule(", body)
        self.assertNotIn("read_now(", body)

    def test_popup_shows_article_before_the_original_link(self):
        page = (ROOT / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
        body = page[page.index("def _news_original_html("):page.index("def _news_accordion_html(")]
        self.assertLess(body.index("_news_article_html(url)"), body.index("원문 기사 열기"))
        self.assertIn("_article_wait_carry()", page)
        self.assertIn("if _article_arrived():", page)


if __name__ == "__main__":
    unittest.main()
