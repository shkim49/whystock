from __future__ import annotations

import email.utils
import html
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Any

from providers.http import TRANSIENT_XML_ERRORS, fetch_text


def parse_google_news_rss(xml_text: str, limit: int = 4) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    items: list[dict[str, Any]] = []
    for item in root.findall("./channel/item"):
        title = html.unescape(item.findtext("title", default="뉴스 제목 없음"))
        link = html.unescape(item.findtext("link", default=""))
        pub_date = item.findtext("pubDate", default="")
        source_node = item.find("source")
        publisher = source_node.text if source_node is not None and source_node.text else "Google 뉴스"
        if not link:
            continue
        items.append(
            {
                "title": title,
                "url": link,
                "publisher": publisher,
                "published_at": pub_date,
                "excerpt": title,
            }
        )
        if len(items) >= limit:
            break
    return items


def fetch_news_items(stock_name: str, limit: int = 4) -> list[dict[str, Any]]:
    query = urllib.parse.quote(f"{stock_name} 주가 OR 실적 when:7d")
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        xml_text = fetch_text(url, timeout=8)
        return parse_google_news_rss(xml_text, limit=limit)
    except TRANSIENT_XML_ERRORS:
        return []


def parse_news_published_at(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def fetch_news_count(stock_name: str, limit: int = 100, hours: int = 24) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    count = 0
    for item in fetch_news_items(stock_name, limit=limit):
        published_at = parse_news_published_at(item.get("published_at", ""))
        if published_at and published_at >= cutoff:
            count += 1
    return count
