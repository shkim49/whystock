from __future__ import annotations

import json
import re
import time
import urllib.error
from typing import Any

from cache import CATALOG_CACHE
from config import CACHE_TTL_SECONDS, MARKET_CATALOG_MAX_PAGES, MARKET_CATALOG_PAGE_SIZE
from providers.http import fetch_json
from utils import parse_int, parse_number
SECTOR_OVERRIDES = {
    "005930": "반도체",
    "000660": "반도체",
    "005380": "자동차",
    "035420": "인터넷 플랫폼",
    "035720": "인터넷 플랫폼",
    "051910": "화학/배터리",
    "373220": "배터리",
    "207940": "바이오",
    "068270": "바이오",
    "009150": "전자부품",
    "247540": "이차전지 소재",
    "086520": "이차전지 소재",
    "012450": "방산/항공",
    "034020": "에너지/원전",
    "042700": "반도체 장비",
}

def infer_sector(name: str) -> str:
    rules = [
        ("반도체", ["삼성전자", "하이닉스", "반도체", "DB하이텍"]),
        ("자동차", ["현대차", "기아", "모비스", "타이어"]),
        ("배터리", ["에너지솔루션", "SDI", "에코프로", "엘앤에프", "포스코퓨처"]),
        ("바이오", ["바이오", "셀트리온", "유한양행", "삼성바이오"]),
        ("인터넷 플랫폼", ["NAVER", "카카오", "카카오페이", "카카오뱅크"]),
        ("방산/조선", ["한화", "현대중공업", "조선", "에어로"]),
        ("금융", ["KB", "신한", "하나금융", "우리금융", "삼성생명"]),
    ]
    upper_name = name.upper()
    for sector, keywords in rules:
        if any(keyword.upper() in upper_name for keyword in keywords):
            return sector
    return "국내 주식"


def stock_from_naver(raw: dict[str, Any]) -> dict[str, Any]:
    ticker = raw.get("itemCode") or raw.get("reutersCode") or ""
    market_info = raw.get("stockExchangeType") or {}
    market = raw.get("stockExchangeName") or market_info.get("nameEng") or market_info.get("nameKor") or "KRX"
    name = raw.get("stockName") or raw.get("longname") or raw.get("shortname") or ticker
    return {
        "id": ticker,
        "ticker": ticker,
        "name": name,
        "market": market,
        "sector": SECTOR_OVERRIDES.get(ticker, infer_sector(name)),
        "end_url": raw.get("endUrl") or f"https://m.stock.naver.com/domestic/stock/{ticker}",
        "current_price": parse_int(raw.get("closePriceRaw") or raw.get("closePrice")),
        "change_rate": parse_number(raw.get("fluctuationsRatio")),
        "accumulated_trading_volume": parse_int(raw.get("accumulatedTradingVolumeRaw") or raw.get("accumulatedTradingVolume")),
        "accumulated_trading_value": parse_int(raw.get("accumulatedTradingValueRaw") or raw.get("accumulatedTradingValue")),
        "market_value": parse_int(raw.get("marketValue") or raw.get("marketValueRaw") or raw.get("marketCapRaw")),
        "traded_at": raw.get("localTradedAt"),
        "stock_end_type": raw.get("stockEndType", "stock"),
    }


def fallback_catalog() -> list[dict[str, Any]]:
    rows = [
        ("005930", "삼성전자", "KOSPI", "반도체"),
        ("000660", "SK하이닉스", "KOSPI", "반도체"),
        ("005380", "현대차", "KOSPI", "자동차"),
        ("035420", "NAVER", "KOSPI", "인터넷 플랫폼"),
        ("035720", "카카오", "KOSPI", "인터넷 플랫폼"),
        ("373220", "LG에너지솔루션", "KOSPI", "배터리"),
        ("051910", "LG화학", "KOSPI", "화학/배터리"),
        ("207940", "삼성바이오로직스", "KOSPI", "바이오"),
        ("068270", "셀트리온", "KOSPI", "바이오"),
        ("247540", "에코프로비엠", "KOSDAQ", "이차전지 소재"),
        ("086520", "에코프로", "KOSDAQ", "이차전지 소재"),
        ("042700", "한미반도체", "KOSPI", "반도체 장비"),
        ("012450", "한화에어로스페이스", "KOSPI", "방산/항공"),
        ("034020", "두산에너빌리티", "KOSPI", "에너지/원전"),
    ]
    base_change_rates = [2.4, 1.7, 3.2, -1.1, -2.8, 4.5, -0.9, 1.3, 2.1, 5.4, 4.8, 6.2, 3.7, 2.9]
    base_values = [
        920_000_000_000,
        610_000_000_000,
        280_000_000_000,
        190_000_000_000,
        140_000_000_000,
        210_000_000_000,
        160_000_000_000,
        130_000_000_000,
        115_000_000_000,
        95_000_000_000,
        88_000_000_000,
        155_000_000_000,
        175_000_000_000,
        120_000_000_000,
    ]
    base_market_values = [
        470_000_000_000_000,
        150_000_000_000_000,
        42_000_000_000_000,
        31_000_000_000_000,
        18_000_000_000_000,
        95_000_000_000_000,
        36_000_000_000_000,
        68_000_000_000_000,
        34_000_000_000_000,
        23_000_000_000_000,
        19_000_000_000_000,
        11_000_000_000_000,
        31_000_000_000_000,
        22_000_000_000_000,
    ]
    return [
        {
            "id": ticker,
            "ticker": ticker,
            "name": name,
            "market": market,
            "sector": sector,
            "end_url": f"https://m.stock.naver.com/domestic/stock/{ticker}",
            "current_price": 50_000 + index * 7_500,
            "change_rate": base_change_rates[index],
            "accumulated_trading_volume": 1_200_000 + index * 180_000,
            "accumulated_trading_value": base_values[index],
            "market_value": base_market_values[index],
            "traded_at": None,
            "stock_end_type": "stock",
        }
        for index, (ticker, name, market, sector) in enumerate(rows)
    ]


def load_market_catalog(
    max_pages: int = MARKET_CATALOG_MAX_PAGES,
    page_size: int = MARKET_CATALOG_PAGE_SIZE,
) -> list[dict[str, Any]]:
    now = time.time()
    if CATALOG_CACHE["stocks"] and now - CATALOG_CACHE["loaded_at"] < CACHE_TTL_SECONDS:
        return CATALOG_CACHE["stocks"]

    stocks: dict[str, dict[str, Any]] = {}
    for category in ("KOSPI", "KOSDAQ"):
        for page in range(1, max_pages + 1):
            url = (
                "https://m.stock.naver.com/api/stocks/marketValue/"
                f"{category}?page={page}&pageSize={page_size}"
            )
            try:
                data = fetch_json(url, timeout=10)
            except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
                break
            items = data.get("stocks", [])
            if not items:
                break
            for item in items:
                if item.get("stockEndType") != "stock":
                    continue
                stock = stock_from_naver(item)
                if not re.fullmatch(r"\d{6}", stock["ticker"]):
                    continue
                stocks[stock["ticker"]] = stock
            if len(items) < page_size:
                break

    catalog = list(stocks.values()) or fallback_catalog()
    CATALOG_CACHE.update({"loaded_at": now, "stocks": catalog})
    return catalog


def fetch_stock_basic(ticker: str) -> dict[str, Any] | None:
    ticker = re.sub(r"\D", "", ticker)[:6]
    if len(ticker) != 6:
        return None
    try:
        raw = fetch_json(f"https://m.stock.naver.com/api/stock/{ticker}/basic", timeout=8)
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return None
    if not raw.get("itemCode"):
        return None
    return stock_from_naver(raw)


def fetch_price_history(ticker: str, page_size: int = 5) -> list[dict[str, Any]]:
    try:
        raw = fetch_json(
            f"https://m.stock.naver.com/api/stock/{ticker}/price?pageSize={page_size}&page=1",
            timeout=8,
        )
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(raw, list):
        return []
    return raw

def stock_lookup(ticker: str) -> dict[str, Any] | None:
    basic = fetch_stock_basic(ticker)
    if basic:
        return basic
    for stock in load_market_catalog():
        if stock["ticker"] == ticker:
            return stock
    return None
