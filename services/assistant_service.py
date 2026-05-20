from __future__ import annotations

import re
from typing import Any

from providers.market import load_market_catalog, stock_lookup
from services.briefing_service import detail_for_ticker
from services.market_service import movers_payload, search_stocks
from services.related_service import related_stocks_for
from services.term_service import TERM_EXPLANATIONS, term_definition
from utils import fmt_percent, topic

SUPPORTED_INTENTS = [
    {
        "id": "stock_briefing",
        "label": "종목 브리핑",
        "example": "삼성전자 오늘 왜 움직였어?",
    },
    {
        "id": "market_summary",
        "label": "시장 요약",
        "example": "오늘 실시간 인기 종목 알려줘",
    },
    {
        "id": "term_explanation",
        "label": "용어 설명",
        "example": "HBM이 뭐야?",
    },
    {
        "id": "related_stocks",
        "label": "관련 종목",
        "example": "SK하이닉스랑 같이 볼 종목 알려줘",
    },
]

STOCK_PARTICLES = (
    "이랑",
    "랑",
    "와",
    "과",
    "에게",
    "한테",
    "에서",
    "으로",
    "로",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "도",
    "만",
)

RELATED_KEYWORDS = (
    "같이 볼",
    "같이 보면",
    "함께 볼",
    "함께 보면",
    "관련 종목",
    "관련주",
    "관련",
    "비슷한 종목",
    "비교",
    "동종",
    "같은 업종",
    "같은 테마",
)

TERM_KEYWORDS = (
    "뭐야",
    "무슨 뜻",
    "뜻",
    "설명",
    "의미",
    "용어",
)

MARKET_KEYWORDS = (
    "급등락",
    "급등",
    "급락",
    "실시간 인기",
    "인기 종목",
    "대장주",
    "대표 종목",
    "많이 오른",
    "많이 내린",
    "오늘 시장",
    "시장 요약",
    "시장 어때",
    "움직인 종목",
    "인기 종목",
    "종목 알려",
    "뭐 올라",
    "뭐 내려",
)

STOCK_BRIEFING_KEYWORDS = (
    "왜",
    "움직",
    "브리핑",
    "분석",
    "이유",
    "어때",
    "주가",
    "상승",
    "하락",
    "올랐",
    "내렸",
    "오늘",
)

EXPLICIT_MARKET_SCOPE_KEYWORDS = (
    "오늘 시장",
    "시장 요약",
    "시장 어때",
    "종목 알려",
    "움직인 종목",
    "인기 종목",
    "실시간 인기",
    "대장주",
    "대표 종목",
    "뭐 올라",
    "뭐 내려",
)


def normalize_message(message: Any) -> str:
    return re.sub(r"\s+", " ", str(message or "")).strip()


def exact_term_match(message: str) -> bool:
    cleaned = normalize_message(message)
    return cleaned in TERM_EXPLANATIONS or cleaned.upper() in TERM_EXPLANATIONS


def classify_intent(message: str) -> str:
    lowered = message.lower()
    if exact_term_match(message):
        return "term_explanation"
    if any(keyword in message for keyword in RELATED_KEYWORDS):
        return "related_stocks"
    if extract_term(message) and (
        any(keyword in message for keyword in TERM_KEYWORDS)
        or re.fullmatch(r"\s*[A-Za-z][A-Za-z0-9-]{1,15}\s*", message)
    ):
        return "term_explanation"
    if any(keyword in message for keyword in MARKET_KEYWORDS):
        return "market_summary"
    if any(keyword in message for keyword in STOCK_BRIEFING_KEYWORDS) or "briefing" in lowered:
        return "stock_briefing"
    return "unsupported"


def strip_stock_particle(token: str) -> str:
    cleaned = token.strip(" .,?!~요죠줘")
    changed = True
    while changed:
        changed = False
        for particle in STOCK_PARTICLES:
            if cleaned.endswith(particle) and len(cleaned) > len(particle) + 1:
                cleaned = cleaned[: -len(particle)]
                changed = True
                break
    return cleaned


def resolve_stock(message: str) -> dict[str, Any] | None:
    ticker_match = re.search(r"\b\d{6}\b", message)
    if ticker_match:
        stock = stock_lookup(ticker_match.group(0))
        if stock:
            return stock

    message_lower = message.lower()
    catalog = load_market_catalog()
    direct_matches = [
        stock
        for stock in catalog
        if (
            str(stock.get("ticker") or "")
            and str(stock.get("ticker") or "") in message
        )
        or (
            str(stock.get("name") or "")
            and str(stock.get("name") or "").lower() in message_lower
        )
    ]
    if direct_matches:
        direct_matches.sort(key=lambda stock: len(str(stock.get("name", ""))), reverse=True)
        return direct_matches[0]

    tokens = re.findall(r"[0-9A-Za-z가-힣]+", message)
    for token in tokens:
        candidate = strip_stock_particle(token)
        if len(candidate) < 2:
            continue
        matches = search_stocks(candidate)
        if matches:
            return matches[0]
    return None


def extract_term(message: str) -> str | None:
    message_lower = message.lower()
    known_matches = [
        term
        for term in TERM_EXPLANATIONS
        if term.lower() in message_lower
    ]
    if known_matches:
        known_matches.sort(key=len, reverse=True)
        return known_matches[0]

    for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{1,15}|[가-힣A-Za-z0-9-]{2,15}", message):
        candidate = strip_stock_particle(token).upper()
        if candidate in TERM_EXPLANATIONS:
            return candidate
        if strip_stock_particle(token) in TERM_EXPLANATIONS:
            return strip_stock_particle(token)
    return None


def compact_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": event.get("id"),
        "ticker": event.get("ticker"),
        "stock_name": event.get("stock_name"),
        "market": event.get("market"),
        "sector": event.get("sector"),
        "change_rate": event.get("change_rate"),
        "summary": event.get("summary"),
    }


def market_category_from_message(message: str) -> tuple[str, str]:
    if "대장주" in message or "대표 종목" in message:
        return "leaders", "대장주 관심 종목"
    if "실시간 인기" in message or "인기 종목" in message:
        return "trending", "실시간 인기 종목"
    if "급등락" in message or "급등" in message or "급락" in message:
        return "trending", "실시간 인기 종목"
    return "trending", "실시간 인기 종목"


def stock_briefing_response(message: str) -> tuple[dict[str, Any], int]:
    stock = resolve_stock(message)
    if not stock:
        return missing_stock_response("stock_briefing")

    briefing = detail_for_ticker(stock["ticker"], prefix="briefing")
    analysis = briefing.get("analysis") or {}
    reasons = analysis.get("reasons") or []
    reason_titles = [reason.get("title", "") for reason in reasons if reason.get("title")]
    reason_text = f" 핵심 재료는 {', '.join(reason_titles[:3])}입니다." if reason_titles else ""
    answer = f"{topic(briefing.get('stock', {}).get('name', stock['name']))} {analysis.get('summary', '아직 분석 결과가 없습니다.')}{reason_text}"
    return {
        "intent": "stock_briefing",
        "answer": answer,
        "stock": briefing.get("stock", stock),
        "event": briefing.get("event"),
        "analysis": analysis,
        "sources": briefing.get("sources", []),
    }, 200


def market_summary_response(message: str) -> tuple[dict[str, Any], int]:
    payload = movers_payload()
    categories = payload.get("categories") or []
    category_id, category_label = market_category_from_message(message)
    selected_category = next((category for category in categories if category.get("id") == category_id), None)
    events = (selected_category or {}).get("events") or payload.get("events", [])
    compact_events = [compact_event(event) for event in events[:5]]
    if compact_events:
        names = [
            f"{event.get('stock_name')}({fmt_percent(event.get('change_rate'))})"
            for event in compact_events[:3]
        ]
        answer = f"오늘 {category_label}은 {', '.join(names)} 순으로 볼 수 있습니다."
    else:
        answer = f"아직 {category_label} 데이터를 찾지 못했습니다."
    return {
        "intent": "market_summary",
        "category_id": category_id,
        "category_label": category_label,
        "answer": answer,
        "events": compact_events,
        "as_of": payload.get("as_of"),
        "data_source": payload.get("data_source"),
    }, 200


def term_explanation_response(message: str) -> tuple[dict[str, Any], int]:
    term = extract_term(message)
    if not term:
        return {
            "intent": "term_explanation",
            "answer": "아직 등록된 용어를 찾지 못했습니다. HBM, PER, 공시처럼 화면에 나온 핵심 용어를 물어봐 주세요.",
            "supported_intents": SUPPORTED_INTENTS,
        }, 200
    definition = term_definition(term)
    return {
        "intent": "term_explanation",
        "answer": f"{term}: {definition}",
        "term": term,
        "definition": definition,
    }, 200


def related_stocks_response(message: str) -> tuple[dict[str, Any], int]:
    stock = resolve_stock(message)
    if not stock:
        return missing_stock_response("related_stocks")

    related = related_stocks_for(stock)
    if related:
        names = ", ".join(item["name"] for item in related[:4])
        answer = f"{topic(stock['name'])} 함께 볼 만한 종목은 {names}입니다."
    else:
        answer = f"{topic(stock['name'])} 관련 종목을 아직 찾지 못했습니다."
    return {
        "intent": "related_stocks",
        "answer": answer,
        "stock": stock,
        "related_stocks": related,
    }, 200


def missing_stock_response(intent: str) -> tuple[dict[str, Any], int]:
    return {
        "intent": intent,
        "answer": "종목명을 찾지 못했습니다. 예: 삼성전자 오늘 왜 움직였어?",
        "supported_intents": SUPPORTED_INTENTS,
    }, 200


def unsupported_response() -> tuple[dict[str, Any], int]:
    return {
        "intent": "unsupported",
        "answer": "아직은 종목 브리핑, 시장 요약, 용어 설명, 관련 종목 질문만 처리할 수 있습니다.",
        "supported_intents": SUPPORTED_INTENTS,
    }, 200


def assistant_chat(body: dict[str, Any]) -> tuple[dict[str, Any], int]:
    message = normalize_message(body.get("message") or body.get("query"))
    if not message:
        return {
            "error": "message_required",
            "answer": "message를 입력해 주세요.",
            "supported_intents": SUPPORTED_INTENTS,
        }, 400

    intent = classify_intent(message)
    resolved_stock = resolve_stock(message)
    if (
        intent == "market_summary"
        and resolved_stock
        and not any(keyword in message for keyword in EXPLICIT_MARKET_SCOPE_KEYWORDS)
    ):
        intent = "stock_briefing"

    if intent == "stock_briefing":
        response, status = stock_briefing_response(message)
    elif intent == "market_summary":
        response, status = market_summary_response(message)
    elif intent == "term_explanation":
        response, status = term_explanation_response(message)
    elif intent == "related_stocks":
        response, status = related_stocks_response(message)
    elif resolved_stock:
        response, status = stock_briefing_response(message)
    elif extract_term(message):
        response, status = term_explanation_response(message)
    else:
        response, status = unsupported_response()

    response["message"] = message
    return response, status
