from __future__ import annotations

import unittest
from typing import Any

import services.assistant_service as assistant_service


class AssistantServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_load_market_catalog = assistant_service.load_market_catalog
        self.original_search_stocks = assistant_service.search_stocks
        self.original_detail_for_ticker = assistant_service.detail_for_ticker
        self.original_movers_payload = assistant_service.movers_payload
        self.original_related_stocks_for = assistant_service.related_stocks_for

        self.stocks = [
            {
                "ticker": "005930",
                "name": "삼성전자",
                "market": "KOSPI",
                "sector": "반도체",
            },
            {
                "ticker": "000660",
                "name": "SK하이닉스",
                "market": "KOSPI",
                "sector": "반도체",
            },
        ]

        assistant_service.load_market_catalog = lambda: self.stocks
        assistant_service.search_stocks = self.fake_search_stocks
        assistant_service.detail_for_ticker = self.fake_detail_for_ticker
        assistant_service.movers_payload = self.fake_movers_payload
        assistant_service.related_stocks_for = self.fake_related_stocks_for

    def tearDown(self) -> None:
        assistant_service.load_market_catalog = self.original_load_market_catalog
        assistant_service.search_stocks = self.original_search_stocks
        assistant_service.detail_for_ticker = self.original_detail_for_ticker
        assistant_service.movers_payload = self.original_movers_payload
        assistant_service.related_stocks_for = self.original_related_stocks_for

    def fake_search_stocks(self, query: str) -> list[dict[str, Any]]:
        lowered = query.lower()
        return [
            stock
            for stock in self.stocks
            if lowered in stock["name"].lower() or lowered in stock["ticker"]
        ]

    def fake_detail_for_ticker(self, ticker: str, prefix: str = "briefing") -> dict[str, Any]:
        stock = next(stock for stock in self.stocks if stock["ticker"] == ticker)
        return {
            "stock": stock,
            "event": {"id": f"{prefix}-{ticker}", "change_rate": 2.1},
            "analysis": {
                "summary": "반도체 업황 기대와 거래대금 증가가 함께 나타났습니다.",
                "reasons": [
                    {"title": "반도체 업황 기대", "explanation": "뉴스 흐름이 반영됐습니다."}
                ],
                "generated_by": "fixture",
            },
            "sources": [],
        }

    def fake_movers_payload(self) -> dict[str, Any]:
        return {
            "categories": [
                {
                    "id": "trending",
                    "events": [
                        {
                            "id": "trending-live-000660",
                            "ticker": "000660",
                            "stock_name": "SK하이닉스",
                            "market": "KOSPI",
                            "sector": "반도체",
                            "change_rate": 1.3,
                            "summary": "거래대금과 뉴스 기준 인기 종목입니다.",
                        }
                    ],
                },
                {
                    "id": "leaders",
                    "events": [
                        {
                            "id": "leaders-live-005930",
                            "ticker": "005930",
                            "stock_name": "삼성전자",
                            "market": "KOSPI",
                            "sector": "반도체",
                            "change_rate": 0.4,
                            "summary": "시가총액 기준 대장주 관심 종목입니다.",
                        }
                    ],
                },
            ],
            "events": [],
            "as_of": "2026-05-20T09:00:00+09:00",
            "data_source": "fixture",
        }

    def fake_related_stocks_for(self, stock: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "ticker": "005930",
                "name": "삼성전자",
                "market": "KOSPI",
                "sector": "반도체",
                "relation_type": "same_sector",
                "theme": "반도체/전자 부품",
                "reason": "같은 반도체 테마에서 비교하기 좋습니다.",
            }
        ]

    def test_stock_briefing_intent(self) -> None:
        response, status = assistant_service.assistant_chat({"message": "삼성전자 오늘 왜 움직였어?"})

        self.assertEqual(status, 200)
        self.assertEqual(response["intent"], "stock_briefing")
        self.assertEqual(response["stock"]["ticker"], "005930")
        self.assertIn("반도체 업황 기대", response["answer"])

    def test_stock_name_only_defaults_to_briefing(self) -> None:
        response, status = assistant_service.assistant_chat({"message": "삼성전자"})

        self.assertEqual(status, 200)
        self.assertEqual(response["intent"], "stock_briefing")
        self.assertEqual(response["stock"]["ticker"], "005930")

    def test_stock_question_with_market_word_prefers_briefing(self) -> None:
        response, status = assistant_service.assistant_chat({"message": "삼성전자 급등락 이유"})

        self.assertEqual(status, 200)
        self.assertEqual(response["intent"], "stock_briefing")
        self.assertEqual(response["stock"]["ticker"], "005930")

    def test_market_summary_intent(self) -> None:
        response, status = assistant_service.assistant_chat({"message": "오늘 급등락 종목 알려줘"})

        self.assertEqual(status, 200)
        self.assertEqual(response["intent"], "market_summary")
        self.assertEqual(response["category_id"], "trending")
        self.assertEqual(response["events"][0]["ticker"], "000660")
        self.assertIn("SK하이닉스", response["answer"])

    def test_market_summary_accepts_natural_market_question(self) -> None:
        response, status = assistant_service.assistant_chat({"message": "오늘 시장 어때?"})

        self.assertEqual(status, 200)
        self.assertEqual(response["intent"], "market_summary")

    def test_market_summary_can_select_trending_category(self) -> None:
        response, status = assistant_service.assistant_chat({"message": "실시간 인기 종목 알려줘"})

        self.assertEqual(status, 200)
        self.assertEqual(response["intent"], "market_summary")
        self.assertEqual(response["category_id"], "trending")
        self.assertEqual(response["events"][0]["ticker"], "000660")

    def test_market_summary_can_select_leader_category(self) -> None:
        response, status = assistant_service.assistant_chat({"message": "대장주 알려줘"})

        self.assertEqual(status, 200)
        self.assertEqual(response["intent"], "market_summary")
        self.assertEqual(response["category_id"], "leaders")
        self.assertEqual(response["events"][0]["ticker"], "005930")

    def test_term_explanation_intent(self) -> None:
        response, status = assistant_service.assistant_chat({"message": "HBM이 뭐야?"})

        self.assertEqual(status, 200)
        self.assertEqual(response["intent"], "term_explanation")
        self.assertEqual(response["term"], "HBM")
        self.assertIn("고대역폭", response["definition"])

    def test_known_term_only_defaults_to_explanation(self) -> None:
        response, status = assistant_service.assistant_chat({"message": "PER"})

        self.assertEqual(status, 200)
        self.assertEqual(response["intent"], "term_explanation")
        self.assertEqual(response["term"], "PER")

    def test_common_market_slang_term(self) -> None:
        response, status = assistant_service.assistant_chat({"message": "개미"})

        self.assertEqual(status, 200)
        self.assertEqual(response["intent"], "term_explanation")
        self.assertEqual(response["term"], "개미")
        self.assertIn("개인 투자자", response["definition"])

    def test_common_terms_added_for_chat(self) -> None:
        for term in ("큰손", "선물", "단타", "오퍼링", "배당", "주주", "주가", "전환사채", "시간외"):
            with self.subTest(term=term):
                response, status = assistant_service.assistant_chat({"message": term})

                self.assertEqual(status, 200)
                self.assertEqual(response["intent"], "term_explanation")
                self.assertEqual(response["term"], term)
                self.assertTrue(response["definition"])

    def test_related_stocks_intent(self) -> None:
        response, status = assistant_service.assistant_chat({"message": "SK하이닉스랑 같이 볼 종목 알려줘"})

        self.assertEqual(status, 200)
        self.assertEqual(response["intent"], "related_stocks")
        self.assertEqual(response["stock"]["ticker"], "000660")
        self.assertEqual(response["related_stocks"][0]["ticker"], "005930")

    def test_related_stocks_accepts_related_stock_keyword(self) -> None:
        response, status = assistant_service.assistant_chat({"message": "SK하이닉스 관련주"})

        self.assertEqual(status, 200)
        self.assertEqual(response["intent"], "related_stocks")
        self.assertEqual(response["stock"]["ticker"], "000660")

    def test_empty_message_returns_400(self) -> None:
        response, status = assistant_service.assistant_chat({"message": ""})

        self.assertEqual(status, 400)
        self.assertEqual(response["error"], "message_required")


if __name__ == "__main__":
    unittest.main()
