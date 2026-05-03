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
from datetime import datetime, timedelta, timezone
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
    "자율주행": "차량이 사람의 직접 조작 없이 주변 환경을 인식해 주행하는 기술입니다. 모빌리티, 반도체, 센서 기업과 연결됩니다.",
    "피지컬 AI": "로봇, 차량, 설비처럼 현실 세계에서 움직이는 기기에 AI를 적용하는 흐름입니다.",
    "모빌리티": "차량 공유, 렌터카, 자율주행, 물류처럼 이동 서비스와 기술을 아우르는 산업 흐름입니다.",
    "렌터카": "차량을 일정 기간 빌려주는 사업입니다. 이용률, 차량 매입가, 중고차 가격, 여행 수요에 영향을 받습니다.",
    "전력기기": "변압기, 차단기, 배전반처럼 전기를 보내고 제어하는 장비입니다. 데이터센터와 전력망 투자에 민감합니다.",
    "전력망": "발전소에서 소비처까지 전기를 보내는 송배전 인프라입니다. 노후 교체와 전력 수요 증가가 투자 재료가 됩니다.",
    "데이터센터": "서버와 네트워크 장비를 대규모로 운영하는 시설입니다. AI 확산으로 전력, 냉각, 반도체 수요와 연결됩니다.",
    "수주": "기업이 제품이나 서비스를 공급하기로 계약을 따낸 것입니다. 향후 매출 기대와 연결될 수 있습니다.",
    "공급계약": "특정 고객에게 제품이나 서비스를 공급하기로 한 계약입니다. 규모와 기간을 함께 봐야 합니다.",
    "시설투자": "공장, 설비, 장비에 투자하는 일입니다. 성장 기대와 비용 부담을 동시에 만들 수 있습니다.",
    "유상증자": "회사가 새 주식을 발행해 자금을 조달하는 방식입니다. 자금 목적과 주식 수 증가 영향을 함께 봐야 합니다.",
    "전환사채": "일정 조건에서 주식으로 바꿀 수 있는 채권입니다. 자금 조달과 잠재 주식 수 증가 이슈가 있습니다.",
    "수급": "주식을 사려는 힘과 팔려는 힘의 균형입니다. 가격 변동의 단기 강도를 볼 때 자주 씁니다.",
    "컨센서스": "증권사들의 실적 전망 평균치입니다. 실제 실적이 컨센서스를 넘거나 밑돌면 주가 반응이 커질 수 있습니다.",
    "가이던스": "기업이 제시하는 향후 실적 또는 사업 전망입니다. 시장 기대를 조정하는 역할을 합니다.",
}

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


SECTOR_THEMES = [
    (("쏘카", "렌탈", "모빌리티", "오토"), "모빌리티/렌탈", "차량 공유, 렌터카, 자율주행 데이터, 이동 수요 변화가 핵심 관전 포인트입니다.", ("렌탈", "모빌", "오토", "자동차")),
    (("반도체", "전기전자", "전자", "장비", "하이닉스", "DB하이텍"), "반도체/전자 부품", "AI 서버, 메모리, 장비 투자와 수출 사이클에 민감한 기업입니다.", ("반도체", "전자", "하이닉스", "DB하이텍")),
    (("이차전지", "2차전지", "전지", "화학", "소재", "에코프로", "엘앤에프"), "배터리/소재", "전기차, 에너지저장장치, 양극재·전해질 같은 소재 수요와 연결됩니다.", ("전지", "배터리", "소재", "화학")),
    (("바이오", "제약", "의약", "헬스", "셀트리온", "삼성바이오"), "바이오/헬스케어", "신약, 임상, 위탁생산, 의료 수요 이슈에 주가가 민감하게 움직일 수 있습니다.", ("바이오", "제약", "헬스", "의약")),
    (("자동차", "운송장비", "부품", "현대차", "기아", "모비스"), "자동차/부품", "완성차 생산, 부품 공급망, 전기차 전환, 환율 흐름과 함께 봐야 하는 기업입니다.", ("자동차", "현대", "기아", "모비스")),
    (("금융", "은행", "증권", "보험", "KB", "신한", "하나금융"), "금융", "금리, 대출 성장, 투자심리, 배당 기대가 주가 흐름에 영향을 주는 업종입니다.", ("금융", "은행", "증권", "보험")),
    (("게임", "엔터", "미디어", "콘텐츠", "크래프톤", "하이브", "JYP", "YG"), "콘텐츠/엔터", "신작, 지식재산권, 팬덤 소비, 해외 매출 기대가 주요 관전 포인트입니다.", ("게임", "엔터", "미디어", "콘텐츠")),
    (("소프트웨어", "서비스", "인터넷", "플랫폼", "통신", "NAVER", "카카오"), "플랫폼/IT 서비스", "광고, 커머스, 구독, 클라우드, 사용자 트래픽 흐름과 연결됩니다.", ("플랫폼", "서비스", "인터넷", "카카오", "NAVER")),
    (("건설", "건자재", "부동산", "삼성물산", "현대건설"), "건설/인프라", "수주, 원가, 부동산 경기, 정책 이슈가 실적 기대에 영향을 줍니다.", ("건설", "건자재", "부동산")),
    (("조선", "해운", "운수", "항공", "HD현대", "한화오션"), "운송/조선", "운임, 수주, 유가, 글로벌 물동량 변화에 민감한 산업입니다.", ("조선", "해운", "항공", "운수")),
    (("전력", "일렉트릭", "ELECTRIC", "LS", "효성중공업"), "전력기기/전력망", "변압기, 전력 자동화, 데이터센터 전력 수요와 설비 투자 흐름을 함께 봐야 합니다.", ("전력", "일렉트릭", "ELECTRIC", "전선")),
    (("철강", "금속", "기계"), "소재/기계", "원자재 가격, 설비 투자, 경기 사이클을 함께 확인해야 하는 업종입니다.", ("철강", "금속", "기계")),
    (("유통", "음식료", "섬유", "소비"), "소비재/유통", "내수 소비, 브랜드 수요, 원가 부담, 온라인 전환이 핵심 변수입니다.", ("유통", "식품", "음식료", "소비")),
    (("에너지", "가스", "정유"), "에너지", "유가, 전력 수요, 정책, 원가 전가 가능성이 중요하게 작용합니다.", ("에너지", "가스", "정유")),
]

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


def fetch_form(url: str, data: dict[str, Any], timeout: int = 8) -> str:
    encoded = urllib.parse.urlencode(data).encode("utf-8")
    headers = {**NAVER_HEADERS, "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
    request = urllib.request.Request(url, data=encoded, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


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


def strip_html(value: str) -> str:
    value = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", value)
    value = re.sub(r"(?is)<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


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


def disclosure_summary_from_title(title: str, company: str) -> str:
    if any(keyword in title for keyword in ("영업실적", "잠정실적", "매출", "손익")):
        return "실적 관련 공시입니다. 매출, 영업이익, 전년 대비 증감률이 주가 반응의 핵심입니다."
    if any(keyword in title for keyword in ("단일판매", "공급계약", "수주", "계약체결")):
        return "계약성 공시입니다. 계약 금액, 기간, 최근 매출 대비 비중을 확인해야 합니다."
    if any(keyword in title for keyword in ("유상증자", "전환사채", "신주인수권", "사채권")):
        return "자금 조달 공시입니다. 조달 목적과 기존 주주 지분 희석 가능성을 함께 봐야 합니다."
    if any(keyword in title for keyword in ("타법인", "출자", "취득", "처분", "양수", "양도")):
        return "투자 또는 자산 변동 공시입니다. 사업 재편, 성장 투자, 재무 영향 여부를 확인해야 합니다."
    if any(keyword in title for keyword in ("소송", "제재", "거래정지", "불성실")):
        return "리스크성 공시입니다. 영업 차질이나 투자심리 악화 가능성을 우선 확인해야 합니다."
    if any(keyword in title for keyword in ("정기주주총회", "주주총회", "배당", "현금ㆍ현물배당")):
        return "주주환원 또는 주주총회 관련 공시입니다. 배당, 안건, 지배구조 변화를 확인하는 자료입니다."
    return f"{company}의 최근 공시입니다. 제목과 접수일 기준으로 주가 재료와 직접 관련이 있는지 원문 확인이 필요합니다."


def fetch_disclosure_body_excerpt(rcp_no: str) -> str:
    if not rcp_no:
        return ""
    try:
        text = fetch_text(f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp_no}", timeout=8)
    except (urllib.error.URLError, TimeoutError):
        return ""
    plain = strip_html(text)
    sentences = re.split(r"(?<=[.다요음])\s+", plain)
    useful = [
        sentence.strip()
        for sentence in sentences
        if 35 <= len(sentence.strip()) <= 180
        and not any(
            skip in sentence
            for skip in (
                "function",
                "Copyright",
                "전자공시시스템",
                "홈으로 가기",
                "잠시만 기다려주세요",
                "본문선택",
                "문서목차",
                "다운로드",
                "첨부선택",
            )
        )
    ]
    return useful[0] if useful else ""


def parse_dart_recent_rows(html_text: str, company_name: str) -> list[dict[str, str]]:
    rows = re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", html_text)
    disclosures = []
    for row in rows:
        plain_row = strip_html(row)
        if company_name not in plain_row:
            continue
        report_match = re.search(
            r'href="(?P<href>/dsaf001/main\.do\?rcpNo=(?P<rcp>\d+))"[^>]*title="(?P<title>[^"]+)"',
            row,
            re.I,
        )
        corp_match = re.search(r'title="([^"]+) 기업개황', row)
        if not report_match:
            continue
        title = strip_html(report_match.group("title").replace("공시뷰어 새창", ""))
        date_match = re.search(r"(\d{4}\.\d{2}\.\d{2})", plain_row)
        disclosures.append(
            {
                "title": title,
                "company": corp_match.group(1) if corp_match else company_name,
                "published_at": date_match.group(1) if date_match else "",
                "url": "https://dart.fss.or.kr" + report_match.group("href"),
                "rcp_no": report_match.group("rcp"),
            }
        )
        if len(disclosures) >= 3:
            break
    return disclosures


def fetch_dart_disclosures(stock: dict[str, Any], event: dict[str, Any]) -> list[dict[str, str]]:
    event_date = event.get("detected_at") or now_iso()
    try:
        cursor = datetime.fromisoformat(event_date.replace("Z", "+00:00")).date()
    except ValueError:
        cursor = datetime.now().date()

    found: list[dict[str, str]] = []
    for offset in range(0, 8):
        select_date = (cursor - timedelta(days=offset)).strftime("%Y%m%d")
        page_texts = []
        try:
            page_texts.append(fetch_text(f"https://dart.fss.or.kr/dsac001/mainAll.do?selectDate={select_date}", timeout=10))
        except (urllib.error.URLError, TimeoutError):
            continue
        for page in range(2, 5):
            try:
                page_texts.append(
                    fetch_form(
                        "https://dart.fss.or.kr/dsac001/search.ax",
                        {"currentPage": page, "selectDate": select_date, "mdayCnt": 0},
                        timeout=10,
                    )
                )
            except (urllib.error.URLError, TimeoutError):
                break
        for html_text in page_texts:
            found.extend(parse_dart_recent_rows(html_text, stock["name"]))
            if found:
                break
        if found:
            break

    if not found:
        search_url = "https://dart.fss.or.kr/dsab007/main.do?option=corp&keyword=" + urllib.parse.quote(stock["name"])
        return [
            {
                "title": f"{stock['name']} DART 공시 검색",
                "company": stock["name"],
                "published_at": now_iso(),
                "url": search_url,
                "rcp_no": "",
                "summary": "최근 일자별 공시 목록에서 바로 매칭되는 공시는 확인되지 않았습니다. DART 검색 화면에서 회사명 기준으로 원문을 확인할 수 있습니다.",
                "key_sentence": "최근 공시 매칭 없음",
            }
        ]

    for disclosure in found:
        body_excerpt = fetch_disclosure_body_excerpt(disclosure.get("rcp_no", ""))
        disclosure["summary"] = disclosure_summary_from_title(disclosure["title"], disclosure["company"])
        disclosure["key_sentence"] = body_excerpt or disclosure["summary"]
    return found[:3]


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

    for disclosure in fetch_dart_disclosures(stock, event):
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
- 원인 제목은 '가격 흐름', '거래량 변화'처럼 일반적으로 쓰지 말고, 뉴스나 공시에서 보이는 핵심 재료를 직관적으로 쓴다.
- 최근 급등락이 뚜렷하지 않으면 '종목 브리핑'으로 설명한다.
- 신뢰 점수나 예측성 조건 항목 같은 임의 항목은 만들지 않는다.
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
    for source in payload.get("sources", []):
        chunks.extend([source.get("title", ""), source.get("excerpt", "")])
    for tag in payload.get("material_tags", []):
        chunks.extend([tag.get("label", ""), tag.get("description", "")])
    for item in payload.get("news_timeline", []):
        chunks.extend([item.get("title", ""), item.get("summary", "")])
    for disclosure in payload.get("disclosure_summaries", []):
        chunks.extend([disclosure.get("title", ""), disclosure.get("summary", ""), disclosure.get("excerpt", "")])
    for related in payload.get("related_stocks", []):
        chunks.extend([related.get("theme", ""), related.get("reason", "")])
    stock = payload.get("stock") or {}
    chunks.extend([stock.get("sector", ""), stock.get("name", "")])

    text = " ".join(chunks).lower()
    found = []
    for term, explanation in TERM_EXPLANATIONS.items():
        if term.lower() in text:
            found.append({"term": term, "explanation": explanation})
    if not found:
        for term in ("변동률", "수급", "공시", business_theme(stock)[0].split("/")[0]):
            if term not in TERM_EXPLANATIONS:
                continue
            found.append({"term": term, "explanation": TERM_EXPLANATIONS[term]})
    diverse = []
    seen = set()
    for item in found:
        if item["term"] in seen:
            continue
        diverse.append(item)
        seen.add(item["term"])
    return diverse[:10]


def data_basis(event: dict[str, Any], sources: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "label": f"근거 {len(sources)}건",
        "note": "",
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
    sources = build_sources(stock, price_history, event)
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
        "news_timeline": build_news_timeline(sources),
        "material_tags": classify_material_tags(stock, sources, event),
        "disclosure_summaries": [source for source in sources if source.get("source_type") == "disclosure"],
    }
    payload["terms"] = detect_terms(payload)
    BRIEFING_CACHE[cache_key] = (time.time(), payload)
    return payload


def related_stocks_for(stock: dict[str, Any]) -> list[dict[str, Any]]:
    catalog = load_market_catalog()
    base_label, _base_note, related_keywords = business_theme(stock)
    theme_matches = [
        candidate
        for candidate in catalog
        if candidate["ticker"] != stock["ticker"]
        and related_keywords
        and any(keyword in f"{candidate.get('name', '')} {candidate.get('sector', '')}" for keyword in related_keywords)
    ]
    same_sector = [
        candidate
        for candidate in catalog
        if candidate["ticker"] != stock["ticker"]
        and candidate["sector"] == stock["sector"]
        and candidate not in theme_matches
    ]
    related = (theme_matches + same_sector)[:4]
    return [
        {
            "ticker": item["ticker"],
            "name": item["name"],
            "market": item["market"],
            "sector": item["sector"],
            "relation_type": "same_sector",
            "theme": business_theme(item)[0],
            "reason": related_stock_reason(item, stock, base_label),
        }
        for item in related
    ]


def business_theme(stock: dict[str, Any]) -> tuple[str, str, tuple[str, ...]]:
    text = f"{stock.get('name', '')} {stock.get('sector', '')}"
    for keywords, label, note, related_keywords in SECTOR_THEMES:
        if any(keyword in text for keyword in keywords):
            return label, note, related_keywords
    normalized = str(stock.get("sector") or "")
    if normalized and normalized != "기타":
        return normalized, f"{normalized} 업종 내에서 실적, 수급, 정책 이슈를 함께 비교해볼 수 있는 기업입니다.", ()
    return "동일 시장 비교군", "세부 업종 정보가 제한적이어서 같은 시장 내 가격·거래량 흐름을 비교하는 용도로 볼 수 있습니다.", ()


def related_stock_reason(
    item: dict[str, Any],
    base_stock: dict[str, Any],
    base_label: str,
) -> str:
    theme_label, theme_note, _related_keywords = business_theme(item)
    base_name = base_stock.get("name", "선택 종목")
    item_name = item.get("name", "관련 종목")
    relation = "같은 테마" if theme_label == base_label else "비슷한 시장 흐름"
    return (
        f"{topic(item_name)} {theme_label} 관련 기업입니다. "
        f"{topic(base_name)} {relation}에서 비교하기 좋고, {theme_note}"
    )


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
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    parser.add_argument("--port", default=int(os.getenv("PORT", "8000")), type=int)
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
