from __future__ import annotations

import re
import time
from typing import Any

from ai import analyze_with_ai
from cache import BRIEFING_CACHE
from config import CACHE_TTL_SECONDS
from providers.market import fetch_price_history, stock_lookup
from services.analysis_service import (
    build_event,
    build_news_timeline,
    build_sources,
    data_basis,
    offline_analysis,
)
from services.related_service import related_stocks_for
from services.term_service import detect_terms
from storage import save_briefing_snapshot


def detail_for_ticker(ticker: str, prefix: str = "briefing", force_refresh: bool = False) -> dict[str, Any]:
    clean_ticker = re.sub(r"\D", "", ticker)[:6]
    cache_key = f"{prefix}:{clean_ticker}"
    cached = BRIEFING_CACHE.get(cache_key)
    if cached and not force_refresh and time.time() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    stock = stock_lookup(clean_ticker)
    if not stock:
        raise KeyError(clean_ticker)

    price_history = fetch_price_history(clean_ticker)
    event = build_event(stock, price_history, prefix=prefix)
    sources = build_sources(stock, price_history, event)
    analysis, generated_by = analyze_with_ai(event, stock, sources)
    if analysis is None:
        analysis = offline_analysis(event, stock, sources)
        generated_by = "price_news_rule_engine"

    payload = {
        "event": event,
        "stock": stock,
        "sources": sources,
        "analysis": {**analysis, "generated_by": generated_by},
        "related_stocks": related_stocks_for(stock),
        "data_basis": data_basis(event, sources),
        "news_timeline": build_news_timeline(sources),
        "disclosure_summaries": [source for source in sources if source.get("source_type") == "disclosure"],
    }
    payload["terms"] = detect_terms(payload)
    save_briefing_snapshot(payload)
    BRIEFING_CACHE[cache_key] = (time.time(), payload)
    return payload
