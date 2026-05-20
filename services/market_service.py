from __future__ import annotations

import json
import re
import time
from typing import Any

from cache import CATALOG_CACHE, TRENDING_CACHE
from config import TRENDING_CACHE_TTL_SECONDS, TRENDING_CANDIDATE_LIMIT
from providers.market import fetch_price_history, fetch_stock_basic, load_market_catalog
from providers.news import fetch_news_count
from services.analysis_service import build_event
from utils import fmt_percent, now_iso, parse_int
def fmt_trading_value(value: int | None) -> str:
    if not value:
        return "집계 없음"
    if value >= 1_0000_0000_0000:
        return f"{value / 1_0000_0000_0000:.1f}조원"
    return f"{value / 1_0000_0000:.0f}억원"


def fetch_trending_candidates() -> list[dict[str, Any]]:
    catalog = load_market_catalog()
    candidates = []
    for stock in catalog:
        if not isinstance(stock.get("change_rate"), (int, float)):
            continue
        trading_value = stock.get("accumulated_trading_value") or 0
        trading_volume = stock.get("accumulated_trading_volume") or 0
        market_value = stock.get("market_value") or 0
        pre_score = (
            min(trading_value / 150_000_000_000, 4.0)
            + min(trading_volume / 18_000_000, 2.0)
            + min(abs(stock["change_rate"]) / 4, 3.0)
            + min(market_value / 20_000_000_000_000, 2.0)
        )
        candidates.append({**stock, "pre_score": pre_score})

    candidates.sort(key=lambda item: item.get("pre_score", 0), reverse=True)
    selected: dict[str, dict[str, Any]] = {
        stock["ticker"]: stock for stock in candidates[:TRENDING_CANDIDATE_LIMIT]
    }
    kospi_leader_seeds = sorted(
        [stock for stock in candidates if str(stock.get("market", "")).upper() == "KOSPI"],
        key=lambda stock: stock.get("market_value") or 0,
        reverse=True,
    )[:6]
    for stock in kospi_leader_seeds:
        selected.setdefault(stock["ticker"], stock)
    return list(selected.values())


def enrich_trending_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for stock in candidates:
        price_history = fetch_price_history(stock["ticker"])
        latest = price_history[0] if price_history else {}
        latest_volume = parse_int(latest.get("accumulatedTradingVolume")) or stock.get("accumulated_trading_volume") or 0
        current_price = parse_int(latest.get("closePrice")) or stock.get("current_price") or 0
        trading_value = stock.get("accumulated_trading_value")
        if not trading_value and current_price and latest_volume:
            trading_value = current_price * latest_volume
        news_count = fetch_news_count(stock["name"], limit=20)
        event = build_event(stock, price_history, prefix="live")
        enriched.append(
            {
                **stock,
                "event": event,
                "news_count": news_count,
                "accumulated_trading_volume": latest_volume,
                "accumulated_trading_value": trading_value or 0,
                "market_value": stock.get("market_value") or 0,
            }
        )
    return enriched


def score_trending_candidate(stock: dict[str, Any]) -> float:
    change_rate = abs(stock.get("event", {}).get("change_rate") or stock.get("change_rate") or 0)
    trading_value = stock.get("accumulated_trading_value") or 0
    trading_volume = stock.get("accumulated_trading_volume") or 0
    news_count = stock.get("news_count") or 0
    market_value = stock.get("market_value") or 0
    trading_value_score = min(trading_value / 250_000_000_000, 3.0)
    trading_volume_score = min(trading_volume / 25_000_000, 2.0)
    change_score = min(change_rate / 8, 2.5)
    news_score = min(news_count / 8, 2.5)
    scale_score = min(market_value / 40_000_000_000_000, 1.5)
    return (
        trading_value_score * 2.2
        + trading_volume_score * 1.2
        + change_score * 2.0
        + news_score * 2.0
        + scale_score * 0.8
    )


def is_leader_candidate(stock: dict[str, Any]) -> bool:
    if str(stock.get("market", "")).upper() != "KOSPI":
        return False
    market_value = stock.get("market_value") or 0
    return market_value >= 10_000_000_000_000


def score_leader_candidate(stock: dict[str, Any]) -> float:
    trading_value = stock.get("accumulated_trading_value") or 0
    market_value = stock.get("market_value") or 0
    return (
        (market_value / 1_000_000_000_000)
        + min(trading_value / 500_000_000_000, 3.0)
    )


def summarize_trending_candidate(stock: dict[str, Any], category_id: str) -> str:
    event = stock.get("event") or {}
    summary_bits = [f"변동률 {fmt_percent(event.get('change_rate'))}"]
    trading_value = stock.get("accumulated_trading_value")
    if trading_value:
        summary_bits.append(f"거래대금 {fmt_trading_value(trading_value)}")
    news_count = stock.get("news_count") or 0
    if news_count:
        summary_bits.append(f"관련 뉴스 {news_count}건")
    if category_id == "leaders":
        return " / ".join(summary_bits) + " 기준으로 선별한 코스피 대장주 관심 종목입니다."
    return " / ".join(summary_bits) + " 기준으로 선별한 실시간 인기 종목입니다."


def build_category_events(
    stocks: list[dict[str, Any]],
    category_id: str,
    generated_by: str,
    score_fn,
    limit: int = 2,
    exclude_tickers: set[str] | None = None,
) -> list[dict[str, Any]]:
    events = []
    blocked = exclude_tickers or set()
    for stock in sorted(stocks, key=score_fn, reverse=True):
        if stock["ticker"] in blocked:
            continue
        event = stock["event"]
        events.append(
            {
                **event,
                "id": f"{category_id}-{event['id']}",
                "stock_name": stock["name"],
                "ticker": stock["ticker"],
                "market": stock["market"],
                "sector": stock["sector"],
                "summary": summarize_trending_candidate(stock, category_id),
                "generated_by": generated_by,
                "category_id": category_id,
                "popularity_score": round(score_fn(stock), 2),
                "news_count": stock.get("news_count", 0),
                "accumulated_trading_value": stock.get("accumulated_trading_value"),
                "accumulated_trading_volume": stock.get("accumulated_trading_volume"),
                "market_value": stock.get("market_value"),
            }
        )
        if len(events) >= limit:
            break
    return events


def allocate_distinct_category_events(
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    used_tickers: set[str] = set()

    leader_candidates = [stock for stock in candidates if is_leader_candidate(stock)]
    leader_events = build_category_events(
        leader_candidates or candidates,
        category_id="leaders",
        generated_by="live_market_leader_interest_score",
        score_fn=score_leader_candidate,
        limit=3,
        exclude_tickers=used_tickers,
    )
    used_tickers.update(event["ticker"] for event in leader_events)

    trending_events = build_category_events(
        candidates,
        category_id="trending",
        generated_by="live_market_popularity_score",
        score_fn=score_trending_candidate,
        limit=3,
        exclude_tickers=used_tickers,
    )
    return trending_events, leader_events


def movers_payload(force_refresh: bool = False) -> dict[str, Any]:
    now = time.time()
    if force_refresh:
        CATALOG_CACHE.update({"loaded_at": 0.0, "stocks": []})
        TRENDING_CACHE.update({"loaded_at": 0.0, "payload": None})
    cached_payload = TRENDING_CACHE.get("payload")
    if cached_payload and now - TRENDING_CACHE["loaded_at"] < TRENDING_CACHE_TTL_SECONDS:
        return cached_payload

    candidates = enrich_trending_candidates(fetch_trending_candidates())
    trending_events, leader_events = allocate_distinct_category_events(candidates)
    categories = [
        {
            "id": "trending",
            "label": "실시간 인기 종목",
            "description": "코스피·코스닥 전체에서 거래대금, 거래량, 변동률, 뉴스 수를 균형 있게 반영한 관심 종목",
            "events": trending_events,
        },
        {
            "id": "leaders",
            "label": "대장주 관심 종목",
            "description": "코스피 시가총액과 거래대금이 큰 대표 종목",
            "events": leader_events,
        },
    ]
    all_events = [event for category in categories for event in category["events"]]
    payload = {
        "categories": categories,
        "events": all_events,
        "as_of": now_iso(),
        "data_source": "네이버페이 증권 + 뉴스 언급량",
    }
    TRENDING_CACHE.update({"loaded_at": now, "payload": payload})
    return payload


def search_stocks(query: str) -> list[dict[str, Any]]:
    query = query.strip()
    if not query:
        return []
    query_lower = query.lower()
    catalog = load_market_catalog()
    results = [
        stock
        for stock in catalog
        if query_lower in stock["name"].lower()
        or query_lower in stock["ticker"].lower()
        or query_lower in stock["sector"].lower()
    ]

    if re.fullmatch(r"\d{6}", query):
        basic = fetch_stock_basic(query)
        if basic and all(item["ticker"] != basic["ticker"] for item in results):
            results.insert(0, basic)

    results.sort(
        key=lambda stock: (
            0 if stock["name"].lower().startswith(query_lower) else 1,
            stock["name"],
        )
    )
    return results[:24]


def ticker_from_event_id(event_id: str) -> str:
    if match := re.search(r"(\d{6})$", event_id):
        return match.group(1)
    raise KeyError(event_id)
