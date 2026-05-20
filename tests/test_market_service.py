from __future__ import annotations

import unittest
from typing import Any

import services.market_service as market_service


def candidate(
    ticker: str,
    name: str,
    change_rate: float,
    trading_value: int,
    market_value: int,
    news_count: int,
) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "name": name,
        "market": "KOSPI",
        "sector": "테스트",
        "event": {
            "id": f"live-{ticker}",
            "ticker": ticker,
            "change_rate": change_rate,
        },
        "news_count": news_count,
        "accumulated_trading_value": trading_value,
        "accumulated_trading_volume": 10_000_000,
        "market_value": market_value,
    }


class MarketServiceTests(unittest.TestCase):
    def test_allocate_distinct_category_events_does_not_repeat_tickers(self) -> None:
        candidates = [
            candidate("000001", "급등A", 25.0, 100_000_000_000, 1_000_000_000_000, 2),
            candidate("000002", "급락B", -21.0, 90_000_000_000, 1_000_000_000_000, 3),
            candidate("000003", "대장C", 1.0, 500_000_000_000, 20_000_000_000_000, 4),
            candidate("000004", "대장D", -0.5, 450_000_000_000, 15_000_000_000_000, 5),
            candidate("000005", "대장E", 3.0, 350_000_000_000, 12_000_000_000_000, 20),
            candidate("000006", "인기F", -2.5, 300_000_000_000, 2_000_000_000_000, 18),
        ]

        trending, leaders = market_service.allocate_distinct_category_events(candidates)
        tickers = [event["ticker"] for event in trending + leaders]

        self.assertEqual(len(tickers), len(set(tickers)))
        self.assertEqual({event["category_id"] for event in leaders}, {"leaders"})
        self.assertEqual({event["category_id"] for event in trending}, {"trending"})
        self.assertEqual(len(trending), 3)
        self.assertEqual(len(leaders), 3)

    def test_fetch_trending_candidates_keeps_kospi_leader_seed(self) -> None:
        original_load_market_catalog = market_service.load_market_catalog
        try:
            small_caps = [
                {
                    "ticker": f"1{index:05d}",
                    "name": f"코스닥{index}",
                    "market": "KOSDAQ",
                    "sector": "테스트",
                    "change_rate": 12.0,
                    "accumulated_trading_value": 500_000_000_000,
                    "accumulated_trading_volume": 30_000_000,
                    "market_value": 1_000_000_000_000,
                }
                for index in range(35)
            ]
            kospi_leader = {
                "ticker": "005930",
                "name": "삼성전자",
                "market": "KOSPI",
                "sector": "반도체",
                "change_rate": 0.1,
                "accumulated_trading_value": 50_000_000_000,
                "accumulated_trading_volume": 1_000_000,
                "market_value": 470_000_000_000_000,
            }
            market_service.load_market_catalog = lambda: [*small_caps, kospi_leader]

            candidates = market_service.fetch_trending_candidates()

            self.assertIn("005930", {stock["ticker"] for stock in candidates})
        finally:
            market_service.load_market_catalog = original_load_market_catalog


if __name__ == "__main__":
    unittest.main()
