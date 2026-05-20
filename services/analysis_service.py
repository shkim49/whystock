from __future__ import annotations

import re
from typing import Any

from providers.disclosures import fetch_dart_disclosures
from providers.news import fetch_news_items
from services.related_service import business_theme
from utils import fmt_percent, now_iso, parse_int, parse_number, topic
MATERIAL_TAG_RULES = [
    ("자율주행/피지컬 AI", ("자율주행", "피지컬 ai", "피지컬AI", "robot", "로봇", "테슬라"), "모빌리티 기술 재료가 뉴스에서 반복 노출됩니다."),
    ("실적", ("실적", "매출", "영업이익", "순이익", "컨센서스", "어닝"), "실적 기대 또는 실적 확인이 주가 반응의 중심일 수 있습니다."),
    ("수주/공급계약", ("수주", "공급계약", "계약", "납품", "공급"), "향후 매출로 이어질 수 있는 계약성 재료입니다."),
    ("투자/증설", ("투자", "증설", "시설투자", "공장", "CAPEX", "라인"), "설비 확장이나 투자 계획이 성장 기대를 만들 수 있습니다."),
    ("정책/규제", ("정책", "규제", "정부", "지원", "허가", "승인"), "정책 변화나 인허가 이슈가 업종 심리에 영향을 줄 수 있습니다."),
    ("지분/인수합병", ("지분", "인수", "합병", "매각", "M&A", "투자유치"), "지배구조나 사업 재편 기대가 붙을 수 있는 재료입니다."),
    ("목표주가/리포트", ("목표주가", "리포트", "상향", "하향", "증권사"), "증권사 전망 변화가 투자자 기대를 조정할 수 있습니다."),
    ("반도체/AI", ("반도체", "HBM", "AI", "데이터센터", "GPU"), "AI 인프라와 반도체 사이클에 연결된 테마입니다."),
    ("배터리/전기차", ("배터리", "이차전지", "전기차", "양극재", "리튬"), "전기차와 배터리 소재 수요에 민감한 테마입니다."),
    ("바이오/임상", ("바이오", "임상", "신약", "FDA", "품목허가"), "임상·허가·기술이전 뉴스에 민감한 테마입니다."),
    ("수급/거래량", ("거래량", "수급", "순매수", "외국인", "기관"), "가격 변화에 시장 참여가 동반됐는지 확인하는 재료입니다."),
]

def classify_material_tags(
    stock: dict[str, Any],
    sources: list[dict[str, Any]],
    event: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    text = " ".join(
        [stock.get("name", ""), stock.get("sector", "")]
        + [f"{source.get('title', '')} {source.get('excerpt', '')}" for source in sources]
    )
    text_lower = text.lower()
    tags: list[dict[str, str]] = []
    seen: set[str] = set()
    for label, keywords, description in MATERIAL_TAG_RULES:
        if any(keyword.lower() in text_lower for keyword in keywords):
            tags.append({"label": label, "description": description})
            seen.add(label)
    theme_label, theme_note, _keywords = business_theme(stock)
    if theme_label not in seen:
        tags.append({"label": theme_label, "description": theme_note})
    if event and isinstance(event.get("volume_change_rate"), (int, float)) and abs(event["volume_change_rate"]) >= 100:
        if "수급/거래량" not in seen:
            tags.append(
                {
                    "label": "수급/거래량",
                    "description": "거래량 변화가 커서 단기 관심 확대 여부를 함께 확인해야 합니다.",
                }
            )
    return tags[:6]


def build_news_timeline(sources: list[dict[str, Any]]) -> list[dict[str, str]]:
    timeline = []
    for source in sources:
        if source.get("source_type") != "news":
            continue
        timeline.append(
            {
                "title": source.get("title", "뉴스 제목 없음"),
                "publisher": source.get("publisher", "뉴스"),
                "published_at": source.get("published_at", ""),
                "url": source.get("url", ""),
                "summary": summarize_news_title(source.get("title", "")),
            }
        )
    return timeline[:4]


def summarize_news_title(title: str) -> str:
    clean = re.sub(r"\s+-\s+[^-]+$", "", title).strip()
    if not clean:
        return "선택한 종목과 관련된 최신 뉴스입니다."
    return f"헤드라인 기준으로는 '{clean}' 이슈가 주가 재료로 확인됩니다."


def source_dedupe_key(source: dict[str, Any]) -> tuple[Any, ...]:
    normalized_title = re.sub(r"\s+", "", source.get("title", "")).lower()
    normalized_excerpt = re.sub(r"\s+", " ", source.get("excerpt", "")).strip().lower()[:120]
    normalized_url = source.get("url", "").split("?", 1)[0]
    published_day = str(source.get("published_at") or "")[:10]
    source_type = source.get("source_type")
    if source_type == "disclosure":
        return (
            source_type,
            normalized_title,
            source.get("company", ""),
            published_day,
        )
    if source_type == "news":
        return (
            source_type,
            normalized_title,
            source.get("publisher", ""),
        )
    return (
        source_type,
        normalized_url,
        normalized_title,
        source.get("publisher", ""),
        normalized_excerpt,
    )


def dedupe_sources(sources: list[dict[str, Any]], limit: int = 6) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for source in sources:
        key = source_dedupe_key(source)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(source)
        if len(deduped) >= limit:
            break
    return [{**item, "id": index + 1} for index, item in enumerate(deduped)]


def build_sources(
    stock: dict[str, Any],
    price_history: list[dict[str, Any]],
    event: dict[str, Any],
) -> list[dict[str, Any]]:
    ticker = stock["ticker"]
    sources: list[dict[str, Any]] = [
        {
            "id": 1,
            "source_type": "price",
            "source_type_label": "시세",
            "title": f"{stock['name']} 네이버페이 증권 시세",
            "url": stock.get("end_url") or f"https://m.stock.naver.com/domestic/stock/{ticker}",
            "publisher": "네이버페이 증권",
            "published_at": stock.get("traded_at") or now_iso(),
            "excerpt": "현재가, 전일 대비 변동률, 거래량은 네이버페이 증권 데이터를 기준으로 표시합니다.",
        }
    ]

    latest = price_history[0] if price_history else {}
    if latest:
        sources[0]["excerpt"] = (
            f"{latest.get('localTradedAt', '')} 종가 {latest.get('closePrice', '-')}, "
            f"전일 대비 {latest.get('fluctuationsRatio', '-')}%, "
            f"거래량 {latest.get('accumulatedTradingVolume', '-'):,}주 기준입니다."
        )

    news_items = fetch_news_items(stock["name"], limit=3)
    for news in news_items:
        sources.append(
            {
                "id": len(sources) + 1,
                "source_type": "news",
                "source_type_label": "뉴스",
                **news,
            }
        )

    for disclosure in fetch_dart_disclosures(stock, event)[:2]:
        sources.append(
            {
                "id": len(sources) + 1,
                "source_type": "disclosure",
                "source_type_label": "공시",
                "title": disclosure["title"],
                "url": disclosure["url"],
                "publisher": "DART",
                "published_at": disclosure.get("published_at") or now_iso(),
                "excerpt": disclosure.get("key_sentence") or disclosure.get("summary", ""),
                "summary": disclosure.get("summary", ""),
                "company": disclosure.get("company", stock["name"]),
                "rcp_no": disclosure.get("rcp_no", ""),
            }
        )
    return dedupe_sources(sources, limit=6)


def build_event(stock: dict[str, Any], price_history: list[dict[str, Any]], prefix: str = "briefing") -> dict[str, Any]:
    latest = price_history[0] if price_history else {}
    previous = price_history[1] if len(price_history) > 1 else {}
    current_price = parse_int(latest.get("closePrice")) or stock.get("current_price")
    change_rate = parse_number(latest.get("fluctuationsRatio"))
    if change_rate is None:
        change_rate = stock.get("change_rate")
    latest_volume = parse_int(latest.get("accumulatedTradingVolume"))
    previous_volume = parse_int(previous.get("accumulatedTradingVolume"))
    volume_change_rate = None
    if latest_volume is not None and previous_volume:
        volume_change_rate = ((latest_volume - previous_volume) / previous_volume) * 100

    event_type = "briefing"
    if change_rate is not None and change_rate >= 3:
        event_type = "surge"
    elif change_rate is not None and change_rate <= -3:
        event_type = "drop"

    return {
        "id": f"{prefix}-{stock['ticker']}",
        "stock_id": stock["ticker"],
        "event_type": event_type,
        "change_rate": change_rate,
        "volume_change_rate": volume_change_rate,
        "current_price": current_price,
        "base_price": None,
        "latest_volume": latest_volume,
        "previous_volume": previous_volume,
        "detected_at": stock.get("traded_at") or latest.get("localTradedAt") or now_iso(),
        "window": "1d",
    }

def offline_analysis(
    event: dict[str, Any],
    stock: dict[str, Any],
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    change_rate = event.get("change_rate")
    volume_change_rate = event.get("volume_change_rate")
    direction = "상승" if (change_rate or 0) > 0 else "하락" if (change_rate or 0) < 0 else "보합"
    news_sources = [source for source in sources if source["source_type"] == "news"]
    disclosure_sources = [source for source in sources if source["source_type"] == "disclosure"]
    news_ids = [source["id"] for source in news_sources[:3]]
    movement_phrase = "최근 급등락 이벤트" if event["event_type"] in ("surge", "drop") else "최근 시장 브리핑"

    material_tags = classify_material_tags(stock, sources, event)
    reasons: list[dict[str, Any]] = []
    if news_ids and material_tags:
        headline = re.sub(r"\s+-\s+[^-]+$", "", news_sources[0]["title"]).strip()
        tag = material_tags[0]
        reasons.append(
            {
                "title": f"{tag['label']} 재료 부각",
                "importance": 1,
                "evidence_source_ids": news_ids[:2],
                "explanation": (
                    f"최근 헤드라인에서 '{headline}' 흐름이 확인됩니다. "
                    f"{tag['description']} 현재 변동률은 {fmt_percent(change_rate)}로, 뉴스 재료와 가격 반응을 함께 봐야 합니다."
                ),
            }
        )

    if len(material_tags) > 1 and len(news_ids) > 1:
        tag = material_tags[1]
        reasons.append(
            {
                "title": f"{tag['label']} 기대 확산",
                "importance": 2,
                "evidence_source_ids": news_ids[1:3],
                "explanation": (
                    f"추가 뉴스에서 {tag['label']} 관련 표현이 반복됩니다. "
                    f"{tag['description']} 단일 기사보다 여러 출처에서 같은 재료가 보이는지 확인하는 것이 중요합니다."
                ),
            }
        )

    if disclosure_sources and "최근 공시 매칭 없음" not in disclosure_sources[0].get("excerpt", ""):
        reasons.append(
            {
                "title": "공시 원문 확인 필요",
                "importance": len(reasons) + 1,
                "evidence_source_ids": [disclosure_sources[0]["id"]],
                "explanation": disclosure_sources[0].get("summary") or disclosure_sources[0].get("excerpt", ""),
            }
        )

    if isinstance(volume_change_rate, (int, float)) and abs(volume_change_rate) >= 100:
        reasons.append(
            {
                "title": f"거래량 {fmt_percent(volume_change_rate)} 동반",
                "importance": len(reasons) + 1,
                "evidence_source_ids": [1],
                "explanation": (
                    "가격만 움직인 것이 아니라 거래량도 크게 변했습니다. "
                    "뉴스 재료에 실제 매매 관심이 붙었는지 판단하는 보조 근거입니다."
                ),
            }
        )

    if not reasons:
        reasons.append(
            {
                "title": f"{business_theme(stock)[0]} 흐름 점검",
                "importance": 1,
                "evidence_source_ids": [1],
                "explanation": (
                    f"{topic(stock['name'])} 뚜렷한 최신 뉴스 재료보다 시세와 업종 흐름을 먼저 확인해야 합니다. "
                    f"현재 전일 대비 변동률은 {fmt_percent(change_rate)}입니다."
                ),
            }
        )

    return {
        "summary": (
            f"{topic(stock['name'])} {movement_phrase} 관점에서 보면 가격은 {direction} 흐름이고, "
            "뉴스 재료, 공시 원문, 거래량 반응을 함께 검토할 수 있습니다."
        ),
        "reasons": [
            {**reason, "importance": index + 1}
            for index, reason in enumerate(reasons[:3])
        ],
        "market_reaction": {
            "price_change": fmt_percent(change_rate),
            "volume_change": fmt_percent(volume_change_rate),
        },
        "disclaimer": "투자 추천이 아닌 정보 요약입니다. 시세는 제공처 상황에 따라 지연될 수 있습니다.",
    }

def data_basis(event: dict[str, Any], sources: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "label": f"근거 {len(sources)}건",
        "note": "",
        "price_source": "네이버페이 증권",
        "news_source": "Google 뉴스 RSS",
        "last_price_at": event.get("detected_at"),
    }
