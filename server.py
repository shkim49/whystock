from __future__ import annotations

import argparse
import html
import json
import mimetypes
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
DATA_DIR = ROOT / "data"

NAVER_HEADERS = {
    "User-Agent": "Mozilla/5.0 WhyStock/1.0",
    "Accept": "application/json,text/xml,application/xml,text/html;q=0.9,*/*;q=0.8",
}

CATALOG_CACHE: dict[str, Any] = {"loaded_at": 0.0, "stocks": []}
BRIEFING_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
CACHE_TTL_SECONDS = 600

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

TERM_EXPLANATIONS = {
    "거래량": "정해진 기간 동안 거래된 주식 수입니다. 가격 변동과 함께 증가하면 시장 참여가 강했다는 뜻으로 해석할 수 있습니다.",
    "변동률": "전일 종가 대비 현재가가 얼마나 올랐거나 내렸는지를 백분율로 나타낸 값입니다.",
    "전일 대비": "직전 거래일 종가와 비교했다는 뜻입니다. 휴장일이 있으면 오늘이 아니라 마지막 거래일 기준일 수 있습니다.",
    "공시": "상장사가 투자자에게 알려야 하는 중요 정보를 공식적으로 공개한 자료입니다. 뉴스보다 원문 근거로 쓰기 좋습니다.",
    "DART": "금융감독원 전자공시시스템입니다. 기업의 사업보고서, 주요사항보고서, 실적 관련 공시를 확인할 수 있습니다.",
    "시가총액": "주가에 상장 주식 수를 곱한 값입니다. 기업의 시장 규모를 비교할 때 사용합니다.",
    "PER": "주가를 주당순이익으로 나눈 값입니다. 시장이 이익 대비 어느 정도 가격을 매기는지 볼 때 사용합니다.",
    "EPS": "주당순이익입니다. 기업 순이익을 발행 주식 수로 나눈 값입니다.",
    "영업이익": "본업에서 벌어들인 이익입니다. 일회성 손익보다 기업의 사업 경쟁력을 볼 때 중요합니다.",
    "실적": "매출, 영업이익, 순이익 같은 기업의 경영 성과입니다. 주가 변동의 핵심 재료가 되는 경우가 많습니다.",
    "목표주가": "증권사가 분석을 바탕으로 제시하는 예상 적정 주가입니다. 투자 추천이 아니라 참고 자료로 봐야 합니다.",
    "리레이팅": "기업이나 업종에 대한 시장의 평가 수준이 이전보다 높아지는 현상입니다.",
    "조정": "주가가 오른 뒤 차익 실현이나 부담으로 잠시 하락하거나 쉬어가는 흐름입니다.",
    "차익 실현": "이미 오른 주식을 팔아 이익을 확정하는 움직임입니다. 단기 하락 요인이 될 수 있습니다.",
    "외국인 순매수": "외국인 투자자의 매수 금액이 매도 금액보다 큰 상태입니다. 대형주 수급을 볼 때 자주 쓰입니다.",
    "기관 순매수": "기관 투자자의 매수 금액이 매도 금액보다 큰 상태입니다.",
    "반도체": "메모리, 파운드리, 장비, 소재를 포함하는 산업입니다. AI 서버와 데이터센터 투자 흐름에 민감합니다.",
    "HBM": "고대역폭 메모리입니다. AI 서버와 고성능 연산에 많이 쓰이는 반도체 부품입니다.",
    "AI 서버": "AI 모델 학습과 추론에 쓰이는 고성능 서버입니다. 반도체, 전력, 냉각, 장비 업종에 영향을 줄 수 있습니다.",
    "이차전지": "충전해서 다시 쓸 수 있는 배터리입니다. 전기차와 에너지저장장치 수요에 영향을 받습니다.",
    "바이오": "의약품, 위탁생산, 신약 개발 등 생명과학 기반 산업을 말합니다.",
    "플랫폼": "검색, 커머스, 콘텐츠, 광고처럼 사용자와 서비스를 연결하는 인터넷 기반 사업입니다.",
    "노조 리스크": "파업, 임금 협상, 생산 차질 가능성처럼 노사 이슈가 기업 실적이나 투자심리에 부담이 되는 상황입니다.",
}

ANALYSIS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "reasons", "market_reaction", "scenarios", "disclaimer"],
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
        "scenarios": {
            "type": "array",
            "maxItems": 2,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "condition"],
                "properties": {"title": {"type": "string"}, "condition": {"type": "string"}},
            },
        },
        "disclaimer": {"type": "string"},
    },
}


def init_db() -> None:
    """Compatibility hook for the smoke test. Live data is fetched on demand."""
    DATA_DIR.mkdir(exist_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def parse_number(value: Any) -> float | None:
    if value in (None, "", "-", "N/A"):
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def parse_int(value: Any) -> int | None:
    number = parse_number(value)
    if number is None:
        return None
    return int(number)


def fmt_percent(value: float | None) -> str:
    if value is None:
        return "확인 불가"
    return f"{value:+.2f}%"


def fmt_price(value: int | None) -> str:
    if value is None:
        return "확인 불가"
    return f"{value:,}원"


def topic(name: str) -> str:
    if not name:
        return name
    last = name[-1]
    if "가" <= last <= "힣":
        return f"{name}{'은' if (ord(last) - ord('가')) % 28 else '는'}"
    return f"{name}는"


def fetch_text(url: str, timeout: int = 8) -> str:
    request = urllib.request.Request(url, headers=NAVER_HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def fetch_json(url: str, timeout: int = 8) -> Any:
    return json.loads(fetch_text(url, timeout))


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
    return [
        {
            "id": ticker,
            "ticker": ticker,
            "name": name,
            "market": market,
            "sector": sector,
            "end_url": f"https://m.stock.naver.com/domestic/stock/{ticker}",
            "current_price": None,
            "change_rate": None,
            "traded_at": None,
            "stock_end_type": "stock",
        }
        for ticker, name, market, sector in rows
    ]


def load_market_catalog(max_pages: int = 12, page_size: int = 100) -> list[dict[str, Any]]:
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


def fetch_news_items(stock_name: str, limit: int = 4) -> list[dict[str, Any]]:
    query = urllib.parse.quote(f"{stock_name} 주가 OR 실적 when:7d")
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        xml_text = fetch_text(url, timeout=8)
        root = ET.fromstring(xml_text)
    except (urllib.error.URLError, TimeoutError, ET.ParseError):
        return []

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


def build_sources(stock: dict[str, Any], price_history: list[dict[str, Any]]) -> list[dict[str, Any]]:
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

    news_items = fetch_news_items(stock["name"], limit=4)
    for news in news_items:
        sources.append(
            {
                "id": len(sources) + 1,
                "source_type": "news",
                "source_type_label": "뉴스",
                **news,
            }
        )

    dart_query = urllib.parse.quote(stock["name"])
    sources.append(
        {
            "id": len(sources) + 1,
            "source_type": "disclosure",
            "source_type_label": "공시",
            "title": f"{stock['name']} DART 공시 검색",
            "url": f"https://dart.fss.or.kr/dsab007/main.do?option=corp&keyword={dart_query}",
            "publisher": "DART",
            "published_at": now_iso(),
            "excerpt": "기업 공시 원문 확인이 필요할 때 금융감독원 DART 검색 화면으로 이동합니다.",
        }
    )
    return sources


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


def stock_lookup(ticker: str) -> dict[str, Any] | None:
    basic = fetch_stock_basic(ticker)
    if basic:
        return basic
    for stock in load_market_catalog():
        if stock["ticker"] == ticker:
            return stock
    return None


def offline_analysis(
    event: dict[str, Any],
    stock: dict[str, Any],
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    change_rate = event.get("change_rate")
    volume_change_rate = event.get("volume_change_rate")
    direction = "상승" if (change_rate or 0) > 0 else "하락" if (change_rate or 0) < 0 else "보합"
    news_sources = [source for source in sources if source["source_type"] == "news"]
    news_ids = [source["id"] for source in news_sources[:3]]
    movement_phrase = "최근 급등락 이벤트" if event["event_type"] in ("surge", "drop") else "최근 시장 브리핑"

    news_summary = "관련 최신 뉴스가 확인되지 않았습니다."
    if news_sources:
        titles = " / ".join(source["title"] for source in news_sources[:2])
        news_summary = f"최근 뉴스 헤드라인에서 '{titles}' 흐름이 확인됩니다."

    reasons = [
        {
            "title": "실제 시세 기준 가격 흐름",
            "importance": 1,
            "evidence_source_ids": [1],
            "explanation": (
                f"네이버페이 증권 기준 {topic(stock['name'])} 전일 대비 {fmt_percent(change_rate)}입니다. "
                "이 수치는 임의 값이 아니라 최신 시세 응답에서 가져온 값입니다."
            ),
        },
        {
            "title": "거래량 변화 확인",
            "importance": 2,
            "evidence_source_ids": [1],
            "explanation": (
                f"최근 거래량은 직전 거래일 대비 {fmt_percent(volume_change_rate)}입니다. "
                "가격 변동과 거래량 변화를 함께 봐야 움직임의 강도를 판단할 수 있습니다."
            ),
        },
    ]
    if news_ids:
        reasons.append(
            {
                "title": "관련 뉴스 흐름",
                "importance": 3,
                "evidence_source_ids": news_ids,
                "explanation": news_summary,
            }
        )

    return {
        "summary": (
            f"{topic(stock['name'])} {movement_phrase} 관점에서 보면 가격은 {direction} 흐름이고, "
            f"관련 뉴스와 공시 확인 링크를 함께 검토할 수 있습니다."
        ),
        "reasons": reasons[:3],
        "market_reaction": {
            "price_change": fmt_percent(change_rate),
            "volume_change": fmt_percent(volume_change_rate),
        },
        "scenarios": [
            {
                "title": "흐름 유지 가능 조건",
                "condition": "관련 뉴스가 추가로 확인되고 거래량이 유지될 경우 현재 방향성이 이어질 수 있습니다.",
            },
            {
                "title": "반대 흐름 가능 조건",
                "condition": "뉴스 재료가 약해지거나 거래량이 줄면 단기 조정 또는 반등 실패 가능성을 봐야 합니다.",
            },
        ],
        "disclaimer": "투자 추천이 아닌 정보 요약입니다. 시세는 제공처 상황에 따라 지연될 수 있습니다.",
    }


def build_openai_prompt(
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
- 최근 급등락이 뚜렷하지 않으면 '종목 브리핑'으로 설명한다.
- 신뢰 점수 같은 임의 점수는 만들지 않는다.
- 한국어로 작성한다.
"""


def extract_output_text(response: dict[str, Any]) -> str:
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


def analyze_with_openai(
    event: dict[str, Any],
    stock: dict[str, Any],
    sources: list[dict[str, Any]],
) -> dict[str, Any] | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    payload = {
        "model": os.getenv("OPENAI_TEXT_MODEL", "gpt-5.5"),
        "instructions": (
            "너는 투자 추천을 하지 않는 금융 정보 분석 도우미다. "
            "실제 시세와 근거 링크를 바탕으로 주가 흐름의 이유를 구조화한다."
        ),
        "input": build_openai_prompt(event, stock, sources),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "stock_reason_analysis",
                "strict": True,
                "schema": ANALYSIS_SCHEMA,
            }
        },
        "max_output_tokens": 1600,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            result = json.loads(response.read().decode("utf-8"))
        output_text = extract_output_text(result)
        return json.loads(output_text)
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        print(f"[warn] OpenAI analysis failed, using offline fallback: {exc}", file=sys.stderr)
        return None


def detect_terms(payload: dict[str, Any]) -> list[dict[str, str]]:
    chunks: list[str] = []
    analysis = payload.get("analysis") or {}
    chunks.append(analysis.get("summary", ""))
    for reason in analysis.get("reasons", []):
        chunks.extend([reason.get("title", ""), reason.get("explanation", "")])
    for scenario in analysis.get("scenarios", []):
        chunks.extend([scenario.get("title", ""), scenario.get("condition", "")])
    for source in payload.get("sources", []):
        chunks.extend([source.get("title", ""), source.get("excerpt", "")])
    stock = payload.get("stock") or {}
    chunks.extend([stock.get("sector", ""), stock.get("name", "")])

    text = " ".join(chunks).lower()
    found = []
    for term, explanation in TERM_EXPLANATIONS.items():
        if term.lower() in text:
            found.append({"term": term, "explanation": explanation})
    if not found:
        for term in ("변동률", "거래량", "공시"):
            found.append({"term": term, "explanation": TERM_EXPLANATIONS[term]})
    return found[:8]


def data_basis(event: dict[str, Any], sources: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "label": f"근거 {len(sources)}건",
        "note": "신뢰점수는 임의 산식이 되기 쉬워 제거했습니다. 대신 실제 시세 출처와 근거 링크 수를 보여줍니다.",
        "price_source": "네이버페이 증권",
        "news_source": "Google 뉴스 RSS",
        "last_price_at": event.get("detected_at"),
    }


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
    sources = build_sources(stock, price_history)
    analysis = analyze_with_openai(event, stock, sources)
    generated_by = "openai_responses_api"
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
    }
    payload["terms"] = detect_terms(payload)
    BRIEFING_CACHE[cache_key] = (time.time(), payload)
    return payload


def related_stocks_for(stock: dict[str, Any]) -> list[dict[str, Any]]:
    catalog = load_market_catalog()
    same_sector = [
        candidate
        for candidate in catalog
        if candidate["ticker"] != stock["ticker"] and candidate["sector"] == stock["sector"]
    ]
    related = same_sector[:4]
    return [
        {
            "ticker": item["ticker"],
            "name": item["name"],
            "market": item["market"],
            "sector": item["sector"],
            "relation_type": "same_sector",
            "reason": f"{stock['sector']} 흐름을 함께 받는 국내 종목입니다.",
        }
        for item in related
    ]


def movers_payload() -> dict[str, Any]:
    catalog = load_market_catalog()
    candidates = [
        stock for stock in catalog if isinstance(stock.get("change_rate"), (int, float))
    ]
    candidates.sort(key=lambda item: abs(item.get("change_rate") or 0), reverse=True)
    events = []
    for stock in candidates[:3]:
        price_history = fetch_price_history(stock["ticker"])
        event = build_event(stock, price_history, prefix="live")
        events.append(
            {
                **event,
                "stock_name": stock["name"],
                "ticker": stock["ticker"],
                "market": stock["market"],
                "sector": stock["sector"],
                "summary": (
                    f"네이버페이 증권 기준 전일 대비 {fmt_percent(event.get('change_rate'))}입니다."
                ),
                "generated_by": "naver_live_market",
            }
        )
    return {"events": events, "as_of": now_iso(), "data_source": "네이버페이 증권"}


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
    for prefix in ("live-", "briefing-"):
        if event_id.startswith(prefix):
            ticker = event_id.removeprefix(prefix)
            if re.fullmatch(r"\d{6}", ticker):
                return ticker
    raise KeyError(event_id)


class WhyStockHandler(BaseHTTPRequestHandler):
    server_version = "WhyStock/2.0"

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/health":
                self.send_json({"ok": True, "service": "WhyStock", "time": now_iso()})
            elif path == "/api/events/movers":
                self.send_json(movers_payload())
            elif match := re.fullmatch(r"/api/events/([^/]+)", path):
                event_id = urllib.parse.unquote(match.group(1))
                ticker = ticker_from_event_id(event_id)
                prefix = "live" if event_id.startswith("live-") else "briefing"
                self.send_json(detail_for_ticker(ticker, prefix=prefix))
            elif path == "/api/stocks/search":
                params = urllib.parse.parse_qs(parsed.query)
                query = params.get("query", [""])[0]
                self.send_json({"stocks": search_stocks(query)})
            elif match := re.fullmatch(r"/api/stocks/(\d{6})/briefing", path):
                self.send_json(detail_for_ticker(match.group(1), prefix="briefing"))
            elif path == "/api/terms/explain":
                params = urllib.parse.parse_qs(parsed.query)
                term = params.get("term", [""])[0].strip()
                self.send_json(
                    {
                        "term": term,
                        "explanation": TERM_EXPLANATIONS.get(
                            term,
                            "등록된 용어 설명이 없습니다. 화면 문장에 등장한 주요 금융 용어부터 확장할 수 있습니다.",
                        ),
                    }
                )
            else:
                self.serve_static(path)
        except KeyError:
            self.send_json({"error": "not_found"}, status=404)
        except Exception as exc:  # noqa: BLE001 - demo server should return a visible error
            self.send_json({"error": "server_error", "detail": str(exc)}, status=500)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        try:
            if match := re.fullmatch(r"/api/events/([^/]+)/analyze", path):
                self.read_json_body()
                event_id = urllib.parse.unquote(match.group(1))
                ticker = ticker_from_event_id(event_id)
                prefix = "live" if event_id.startswith("live-") else "briefing"
                self.send_json(detail_for_ticker(ticker, prefix=prefix, force_refresh=True))
            else:
                self.send_json({"error": "not_found"}, status=404)
        except KeyError:
            self.send_json({"error": "not_found"}, status=404)
        except Exception as exc:  # noqa: BLE001
            self.send_json({"error": "server_error", "detail": str(exc)}, status=500)

    def read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_static(self, path: str) -> None:
        requested = urllib.parse.unquote(path.lstrip("/")) or "index.html"
        candidate = (WEB_DIR / requested).resolve()
        if WEB_DIR not in candidate.parents and candidate != WEB_DIR:
            self.send_error(403)
            return
        if not candidate.exists() or candidate.is_dir():
            candidate = WEB_DIR / "index.html"
        mime, _ = mimetypes.guess_type(candidate)
        data = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[server] {self.address_string()} - {fmt % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the WhyStock MVP server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()

    init_db()
    httpd = ThreadingHTTPServer((args.host, args.port), WhyStockHandler)
    print(f"WhyStock running at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping WhyStock.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
