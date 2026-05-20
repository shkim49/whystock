from __future__ import annotations

from typing import Any

from providers.market import load_market_catalog
from utils import topic
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
