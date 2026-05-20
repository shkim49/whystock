from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any

from providers.http import TRANSIENT_PARSE_ERRORS
from utils import fmt_percent, fmt_price

ANALYSIS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "reasons", "market_reaction", "disclaimer"],
    "properties": {
        "summary": {"type": "string"},
        "reasons": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "importance", "evidence_source_ids", "explanation"],
                "properties": {
                    "title": {"type": "string"},
                    "importance": {"type": "integer", "minimum": 1, "maximum": 3},
                    "evidence_source_ids": {"type": "array", "items": {"type": "integer"}},
                    "explanation": {"type": "string"},
                },
            },
        },
        "market_reaction": {
            "type": "object",
            "additionalProperties": False,
            "required": ["price_change", "volume_change"],
            "properties": {
                "price_change": {"type": "string"},
                "volume_change": {"type": "string"},
            },
        },
        "disclaimer": {"type": "string"},
    },
}

TERM_EXPLANATION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["terms"],
    "properties": {
        "terms": {
            "type": "array",
            "maxItems": 5,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["term", "definition", "why_it_matters"],
                "properties": {
                    "term": {"type": "string"},
                    "definition": {"type": "string"},
                    "why_it_matters": {"type": "string"},
                },
            },
        }
    },
}


def build_analysis_prompt(
    event: dict[str, Any],
    stock: dict[str, Any],
    sources: list[dict[str, Any]],
) -> str:
    source_text = "\n".join(
        f"[source_id={source['id']}] type={source['source_type_label']} "
        f"title={source['title']} excerpt={source['excerpt']} url={source['url']}"
        for source in sources
    )
    return f"""
종목: {stock['name']} ({stock['ticker']}, {stock['market']})
섹터: {stock['sector']}
이벤트 유형: {event['event_type']}
전일 대비 변동률: {fmt_percent(event.get('change_rate'))}
거래량 변화율: {fmt_percent(event.get('volume_change_rate'))}
현재가: {fmt_price(event.get('current_price'))}
감지 시각: {event['detected_at']}

근거 자료:
{source_text}

분석 원칙:
- 투자 추천, 매수/매도 판단, 확정적 예측을 하지 않는다.
- 제공된 시세/뉴스/공시 링크에서 확인되는 내용만 사용한다.
- 원인은 최대 3개로 정리하고 각 원인에 evidence_source_ids를 연결한다.
- 원인 제목은 '가격 흐름', '거래량 변화'처럼 일반적으로 쓰지 말고, 뉴스나 공시에서 보이는 핵심 재료를 직관적으로 쓴다.
- 최근 급등락이 뚜렷하지 않으면 '종목 브리핑'으로 설명한다.
- 신뢰 점수나 예측성 조건 항목 같은 임의 항목은 만들지 않는다.
- 한국어로 작성한다.
"""


def extract_openai_output_text(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]

    chunks: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("type") == "output_text" and isinstance(value.get("text"), str):
                chunks.append(value["text"])
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(response.get("output", []))
    return "\n".join(chunks).strip()


def extract_gemini_output_text(response: dict[str, Any]) -> str:
    chunks: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if isinstance(value.get("text"), str):
                chunks.append(value["text"])
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(response.get("candidates", []))
    return "\n".join(chunk.strip() for chunk in chunks if chunk and chunk.strip()).strip()


def _post_json(url: str, body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


BUY_SELL_PATTERNS = (
    r"매수\s*(추천|하세요|관점|타이밍)?",
    r"매도\s*(추천|하세요|관점|타이밍)?",
    r"지금\s*사야",
    r"지금\s*팔아야",
    r"사야\s*합니다",
    r"팔아야\s*합니다",
    r"비중을\s*늘리",
    r"비중을\s*줄이",
    r"강력\s*매수",
    r"강력\s*매도",
    r"buy\b",
    r"sell\b",
)

DETERMINISTIC_PREDICTION_PATTERNS = (
    r"반드시",
    r"확실히",
    r"무조건",
    r"틀림없이",
    r"곧\s*오를",
    r"곧\s*내릴",
    r"계속\s*오를",
    r"계속\s*내릴",
    r"상승할\s*것",
    r"하락할\s*것",
    r"오를\s*것",
    r"내릴\s*것",
    r"급등할\s*것",
    r"급락할\s*것",
    r"목표가",
)


def clean_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"(?<!\n)\n", " ", str(text or ""))
    parts = re.split(r"(?<=[.!?다요])\s+|(?<=\n)", normalized)
    return [clean_whitespace(part) for part in parts if clean_whitespace(part)]


def contains_forbidden_phrase(text: str) -> bool:
    for pattern in BUY_SELL_PATTERNS + DETERMINISTIC_PREDICTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def sanitize_analysis_text(text: str) -> str:
    sentences = split_sentences(text)
    kept = [sentence for sentence in sentences if not contains_forbidden_phrase(sentence)]
    if not kept:
        return ""
    return clean_whitespace(" ".join(kept))


def validate_analysis_result(
    result: dict[str, Any],
    sources: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not isinstance(result, dict):
        return None

    valid_source_ids = {source.get("id") for source in sources if isinstance(source.get("id"), int)}
    summary = sanitize_analysis_text(result.get("summary", ""))
    disclaimer = sanitize_analysis_text(result.get("disclaimer", ""))
    if not summary:
        return None

    raw_reasons = result.get("reasons", [])
    if not isinstance(raw_reasons, list):
        raw_reasons = []

    normalized_reasons: list[dict[str, Any]] = []
    invalid_reason_count = 0
    for raw_reason in raw_reasons[:3]:
        if not isinstance(raw_reason, dict):
            invalid_reason_count += 1
            continue
        title = sanitize_analysis_text(raw_reason.get("title", ""))
        explanation = sanitize_analysis_text(raw_reason.get("explanation", ""))
        source_ids = raw_reason.get("evidence_source_ids", [])
        if not isinstance(source_ids, list):
            source_ids = []
        filtered_source_ids = [
            source_id
            for source_id in source_ids
            if isinstance(source_id, int) and source_id in valid_source_ids
        ]
        if not title or not explanation or not filtered_source_ids:
            invalid_reason_count += 1
            continue
        normalized_reasons.append(
            {
                "title": title,
                "importance": len(normalized_reasons) + 1,
                "evidence_source_ids": filtered_source_ids,
                "explanation": explanation,
            }
        )

    if raw_reasons and not normalized_reasons:
        return None
    if invalid_reason_count >= 2 and len(normalized_reasons) <= 1:
        return None

    market_reaction = result.get("market_reaction", {})
    if not isinstance(market_reaction, dict):
        market_reaction = {}

    price_change = clean_whitespace(market_reaction.get("price_change", ""))
    volume_change = clean_whitespace(market_reaction.get("volume_change", ""))

    return {
        "summary": summary,
        "reasons": normalized_reasons[:3],
        "market_reaction": {
            "price_change": price_change,
            "volume_change": volume_change,
        },
        "disclaimer": disclaimer or "투자 추천이 아닌 정보 요약입니다.",
    }


def call_gemini_json(
    instructions: str,
    input_text: str,
    schema_name: str,
    schema: dict[str, Any],
    max_output_tokens: int = 1600,
) -> Any | None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    model = os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash")
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": input_text,
                    }
                ],
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseJsonSchema": schema,
            "maxOutputTokens": max_output_tokens,
        },
        "systemInstruction": {
            "parts": [
                {
                    "text": f"{instructions}\nJSON schema name: {schema_name}",
                }
            ]
        },
    }
    try:
        result = _post_json(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            payload,
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        )
        output_text = extract_gemini_output_text(result)
        return json.loads(output_text)
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        print(f"[warn] Gemini HTTP error {exc.code}: {error_body}", file=sys.stderr)
        return None
    except TRANSIENT_PARSE_ERRORS as exc:
        print(f"[warn] Gemini structured call failed, trying next provider: {exc}", file=sys.stderr)
        return None


def call_openai_json(
    instructions: str,
    input_text: str,
    schema_name: str,
    schema: dict[str, Any],
    max_output_tokens: int = 1600,
) -> Any | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    payload = {
        "model": os.getenv("OPENAI_TEXT_MODEL", "gpt-5.5"),
        "instructions": instructions,
        "input": input_text,
        "text": {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": schema,
            }
        },
        "max_output_tokens": max_output_tokens,
    }
    try:
        result = _post_json(
            "https://api.openai.com/v1/responses",
            payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        output_text = extract_openai_output_text(result)
        return json.loads(output_text)
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        print(f"[warn] OpenAI HTTP error {exc.code}: {error_body}", file=sys.stderr)
        return None
    except TRANSIENT_PARSE_ERRORS as exc:
        print(f"[warn] OpenAI structured call failed, using fallback: {exc}", file=sys.stderr)
        return None


def call_llm_json(
    instructions: str,
    input_text: str,
    schema_name: str,
    schema: dict[str, Any],
    max_output_tokens: int = 1600,
) -> Any | None:
    gemini_result = call_gemini_json(
        instructions=instructions,
        input_text=input_text,
        schema_name=schema_name,
        schema=schema,
        max_output_tokens=max_output_tokens,
    )
    if gemini_result is not None:
        return gemini_result

    return call_openai_json(
        instructions=instructions,
        input_text=input_text,
        schema_name=schema_name,
        schema=schema,
        max_output_tokens=max_output_tokens,
    )


def analyze_with_ai(
    event: dict[str, Any],
    stock: dict[str, Any],
    sources: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str | None]:
    instructions = (
        "너는 투자 추천을 하지 않는 금융 정보 분석 도우미다. "
        "실제 시세와 근거 링크를 바탕으로 주가 흐름의 이유를 구조화한다."
    )
    prompt = build_analysis_prompt(event, stock, sources)
    gemini_result = call_gemini_json(
        instructions=instructions,
        input_text=prompt,
        schema_name="stock_reason_analysis",
        schema=ANALYSIS_SCHEMA,
        max_output_tokens=1600,
    )
    if isinstance(gemini_result, dict):
        validated = validate_analysis_result(gemini_result, sources)
        if validated is not None:
            return validated, "gemini_api"
        print("[warn] Gemini analysis failed post-processing validation, trying OpenAI", file=sys.stderr)

    openai_result = call_openai_json(
        instructions=instructions,
        input_text=prompt,
        schema_name="stock_reason_analysis",
        schema=ANALYSIS_SCHEMA,
        max_output_tokens=1600,
    )
    if isinstance(openai_result, dict):
        validated = validate_analysis_result(openai_result, sources)
        if validated is not None:
            return validated, "openai_responses_api"
        print("[warn] OpenAI analysis failed post-processing validation, using fallback", file=sys.stderr)
    return None, None
