from __future__ import annotations

import unittest

from providers.disclosures import parse_dart_detail_search_rows, parse_dart_recent_rows
from providers.market import stock_from_naver
from providers.news import parse_google_news_rss
from tests.fixture_utils import read_json_fixture, read_text_fixture


class ProviderFixtureTests(unittest.TestCase):
    def test_stock_from_naver_fixture(self) -> None:
        raw = read_json_fixture("naver_stock_basic_005930.json")
        stock = stock_from_naver(raw)

        self.assertEqual(stock["ticker"], "005930")
        self.assertEqual(stock["name"], "삼성전자")
        self.assertEqual(stock["sector"], "반도체")
        self.assertEqual(stock["current_price"], 73500)
        self.assertEqual(stock["market_value"], 438780000000000)

    def test_parse_google_news_rss_fixture(self) -> None:
        xml_text = read_text_fixture("google_news_rss_005930.xml")
        items = parse_google_news_rss(xml_text, limit=2)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["publisher"], "연합뉴스")
        self.assertIn("삼성전자", items[0]["title"])
        self.assertTrue(items[0]["url"].startswith("https://news.google.com/"))

    def test_parse_dart_recent_rows_fixture(self) -> None:
        html_text = read_text_fixture("dart_recent_rows_005930.html")
        rows = parse_dart_recent_rows(html_text, "삼성전자")

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["company"], "삼성전자")
        self.assertEqual(rows[0]["rcp_no"], "20260520000123")
        self.assertIn("공급계약", rows[0]["title"])

    def test_parse_dart_detail_rows_fixture(self) -> None:
        html_text = read_text_fixture("dart_detail_rows_005930.html")
        rows = parse_dart_detail_search_rows(html_text)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["company"], "삼성전자")
        self.assertEqual(rows[0]["presenter"], "삼성전자")
        self.assertEqual(rows[0]["rcp_no"], "20260520000999")


if __name__ == "__main__":
    unittest.main()

