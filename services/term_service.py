from __future__ import annotations

import re
import time
from typing import Any

from ai import TERM_EXPLANATION_SCHEMA, call_llm_json
from cache import TERM_EXPLANATION_CACHE
from config import TERM_CACHE_TTL_SECONDS
from services.related_service import business_theme
TERM_EXPLANATIONS = {
    "거래량": "정해진 기간 동안 거래된 주식 수입니다. 가격 변동과 함께 증가하면 시장 참여가 강했다는 뜻으로 해석할 수 있습니다.",
    "변동률": "전일 종가 대비 현재가가 얼마나 올랐거나 내렸는지를 백분율로 나타낸 값입니다.",
    "전일 대비": "직전 거래일 종가와 비교했다는 뜻입니다. 휴장일이 있으면 오늘이 아니라 마지막 거래일 기준일 수 있습니다.",
    "공시": "상장사가 투자자에게 알려야 하는 중요 정보를 공식적으로 공개한 자료입니다. 뉴스보다 원문 근거로 쓰기 좋습니다.",
    "DART": "금융감독원 전자공시시스템입니다. 기업의 사업보고서, 주요사항보고서, 실적 관련 공시를 확인할 수 있습니다.",
    "IR": "Investor Relations의 약자로, 기업이 투자자와 애널리스트에게 실적과 사업 계획을 설명하는 활동입니다.",
    "기업설명회": "기업이 투자자나 기관을 대상으로 사업 현황과 전망을 설명하는 자리입니다. 보통 IR 일정과 함께 공시됩니다.",
    "분기보고서": "상장사가 분기별 실적과 재무 상태를 정리해 제출하는 공시 문서입니다.",
    "AI": "인공지능을 뜻합니다. 반도체, 소프트웨어, 로봇, 데이터센터 같은 산업 기대와 함께 자주 묶여 움직입니다.",
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
    "개미": "개인 투자자를 속되게 부르는 말입니다. 기관이나 외국인보다 자금 규모는 작지만, 특정 테마나 종목에서는 매수·매도 흐름에 영향을 줄 수 있습니다.",
    "세력": "큰 자금으로 특정 종목의 가격이나 거래량에 영향을 줄 수 있다고 여겨지는 투자 주체를 부르는 시장 용어입니다. 실제 존재나 의도는 확인하기 어렵기 때문에 추정 표현으로 봐야 합니다.",
    "주포": "특정 종목에서 가격 흐름을 주도한다고 여겨지는 큰손이나 매매 주체를 뜻하는 속어입니다. 확인된 공식 정보가 아니라 투자자들이 흐름을 설명할 때 쓰는 표현입니다.",
    "증시": "주식이 거래되는 시장 전체를 뜻합니다. 한국 증시는 보통 코스피와 코스닥 시장 흐름을 함께 말할 때 씁니다.",
    "투자": "미래 수익을 기대하고 자금을 주식, 채권, 부동산 같은 자산에 넣는 일입니다. 수익 가능성과 손실 위험을 함께 봐야 합니다.",
    "투기": "가치나 실적보다 짧은 가격 변동에 기대어 수익을 노리는 거래 성향을 말합니다. 변동성과 손실 위험이 큰 편입니다.",
    "손절": "손실이 난 상태에서 더 큰 손실을 피하려고 매도하는 것을 말합니다.",
    "익절": "이익이 난 상태에서 수익을 확정하려고 매도하는 것을 말합니다.",
    "물타기": "보유 종목이 하락했을 때 추가 매수해 평균 매입 단가를 낮추는 행동입니다. 하락 이유가 해소되지 않으면 위험이 커질 수 있습니다.",
    "불타기": "보유 종목이 오른 뒤 추가 매수해 상승 흐름에 더 올라타는 행동입니다. 추세가 꺾이면 평균 단가가 높아져 손실 위험이 커질 수 있습니다.",
    "상한가": "하루 가격 제한폭의 가장 높은 가격까지 오른 상태입니다.",
    "하한가": "하루 가격 제한폭의 가장 낮은 가격까지 떨어진 상태입니다.",
    "테마주": "실적보다 특정 산업, 정책, 뉴스, 기대감 같은 공통 재료로 함께 움직이는 종목군입니다.",
    "작전주": "인위적으로 가격을 띄우거나 흔드는 불공정거래 의심 종목을 가리키는 말입니다. 실제 여부는 공식 조사나 공시 없이 단정하면 안 됩니다.",
    "큰손": "시장에 영향을 줄 만큼 큰 자금을 움직이는 투자자를 부르는 말입니다. 기관, 외국인, 고액 개인 투자자를 통칭해 말할 때가 많습니다.",
    "선물": "미래의 특정 시점에 정해진 가격으로 자산을 사고팔기로 약속하는 파생상품입니다. 지수나 원자재 방향에 베팅하거나 위험을 줄이는 데 쓰입니다.",
    "옵션": "정해진 가격에 살 권리나 팔 권리를 거래하는 파생상품입니다. 권리만 있고 의무는 없지만 가격 변동성이 크기 때문에 위험 관리가 중요합니다.",
    "선물옵션": "선물과 옵션을 함께 부르는 말입니다. 지수 방향성, 변동성, 헤지 수요가 반영되며 만기일에는 시장 변동성이 커질 수 있습니다.",
    "단타": "짧게는 몇 분, 길게는 며칠 안에 사고파는 단기 매매를 말합니다. 빠른 판단이 필요하지만 수수료와 변동성 부담이 큽니다.",
    "스윙": "며칠에서 몇 주 정도의 흐름을 보고 매매하는 방식입니다. 하루 단타보다 길고 장기 투자보다는 짧은 중간 성격입니다.",
    "장투": "기업의 성장이나 배당을 보고 오랜 기간 보유하는 투자 방식을 말합니다.",
    "오퍼링": "회사가 주식이나 증권을 발행해 투자자에게 판매하는 자금 조달을 뜻합니다. 새 주식이 늘면 기존 주주 지분 희석 부담이 생길 수 있습니다.",
    "배당": "기업이 벌어들인 이익 일부를 주주에게 나눠주는 것입니다. 배당금 규모와 지속 가능성이 중요합니다.",
    "배당락": "배당을 받을 권리가 사라진 뒤 주가가 배당 예상분만큼 낮아져 출발하는 현상입니다.",
    "주주": "회사의 주식을 보유한 사람이나 기관입니다. 보유 지분에 따라 배당, 의결권 같은 권리를 가질 수 있습니다.",
    "주가": "시장에서 거래되는 주식의 가격입니다. 실적, 수급, 금리, 뉴스, 투자심리 등 여러 요인으로 움직입니다.",
    "호가": "투자자가 사거나 팔겠다고 제시한 가격입니다. 매수호가와 매도호가의 차이를 보면 단기 수급을 가늠할 수 있습니다.",
    "시초가": "장 시작 후 처음 형성된 가격입니다. 장 초반 수급과 전날 이후 뉴스를 반영해 크게 움직일 수 있습니다.",
    "종가": "정규장 마지막에 형성된 가격입니다. 하루 흐름을 정리하는 기준 가격으로 많이 씁니다.",
    "고가": "하루 거래 중 가장 높았던 가격입니다.",
    "저가": "하루 거래 중 가장 낮았던 가격입니다.",
    "매수": "주식을 사는 행위입니다.",
    "매도": "주식을 파는 행위입니다.",
    "체결": "매수 주문과 매도 주문이 실제로 거래로 이어진 상태입니다.",
    "예수금": "증권 계좌에 들어 있는 현금성 자금입니다. 매수 가능 금액과 출금 가능 금액은 결제 일정 때문에 다를 수 있습니다.",
    "증거금": "주식이나 파생상품 거래를 위해 미리 맡겨야 하는 보증금 성격의 금액입니다.",
    "미수": "증거금만으로 주식을 산 뒤 결제일까지 부족한 돈을 채워야 하는 거래입니다. 기한 내 갚지 못하면 반대매매 위험이 있습니다.",
    "신용": "증권사에서 돈이나 주식을 빌려 매매하는 거래입니다. 수익이 커질 수 있지만 손실과 이자 부담도 커집니다.",
    "반대매매": "빌린 돈이나 미수금을 갚지 못할 때 증권사가 보유 주식을 강제로 파는 것입니다.",
    "공매도": "주식을 빌려서 먼저 팔고 나중에 다시 사서 갚는 거래입니다. 주가 하락을 예상할 때 쓰이며 숏커버링 수급으로 반대로 오를 수도 있습니다.",
    "숏커버링": "공매도한 투자자가 빌린 주식을 갚기 위해 다시 매수하는 것입니다. 매수세가 몰리면 주가 상승 요인이 될 수 있습니다.",
    "갭상승": "전일 종가보다 높은 가격에서 장이 시작하는 현상입니다. 장전 호재나 강한 매수세가 반영될 때 나타납니다.",
    "갭하락": "전일 종가보다 낮은 가격에서 장이 시작하는 현상입니다. 악재나 매도 압력이 반영될 때 나타납니다.",
    "VI": "변동성 완화장치입니다. 주가가 짧은 시간에 급변하면 일정 시간 단일가 매매로 전환해 과열을 식히는 제도입니다.",
    "서킷브레이커": "시장 전체가 급락할 때 거래를 일시 중단하는 제도입니다. 과도한 공포 매도를 진정시키기 위한 장치입니다.",
    "평단": "평균 매입 단가를 줄여 부르는 말입니다. 보유 주식을 얼마에 샀는지 보는 기준입니다.",
    "물량": "시장에 나오는 매수·매도 주문이나 보유 주식 규모를 말합니다.",
    "매물대": "과거에 거래가 많이 이루어진 가격 구간입니다. 주가가 그 구간에 오면 저항이나 지지로 작용할 수 있습니다.",
    "지지선": "주가가 하락할 때 매수세가 들어와 버틸 것으로 보는 가격대입니다.",
    "저항선": "주가가 상승할 때 매도세가 나와 막힐 것으로 보는 가격대입니다.",
    "신고가": "일정 기간 동안 가장 높은 가격을 새로 기록한 상태입니다.",
    "신저가": "일정 기간 동안 가장 낮은 가격을 새로 기록한 상태입니다.",
    "박스권": "주가가 일정한 상단과 하단 사이에서 반복해서 움직이는 구간입니다.",
    "추세": "주가가 일정 기간 한 방향으로 움직이는 흐름입니다. 상승 추세, 하락 추세, 횡보 추세로 나눠 볼 수 있습니다.",
    "변동성": "가격이 얼마나 크게 흔들리는지를 뜻합니다. 변동성이 크면 기회도 있지만 손실 위험도 커집니다.",
    "액면분할": "주식 한 주의 액면가를 낮춰 주식 수를 늘리는 일입니다. 기업 가치가 바로 변하는 것은 아니지만 거래 접근성이 좋아질 수 있습니다.",
    "무상증자": "회사가 새 주식을 주주에게 돈을 받지 않고 나눠주는 것입니다. 주식 수가 늘지만 기업 가치가 자동으로 증가하는 것은 아닙니다.",
    "권리락": "무상증자나 유상증자 등 신주를 받을 권리가 사라진 뒤 주가 기준이 조정되는 현상입니다.",
    "자사주": "회사가 자기 회사 주식을 보유하거나 매입하는 것을 말합니다. 주주환원이나 주가 안정 신호로 해석될 수 있습니다.",
    "보호예수": "일정 기간 주식을 팔 수 없도록 묶어두는 제도입니다. 해제 시점에는 매도 물량 부담이 생길 수 있습니다.",
    "락업": "보호예수처럼 일정 기간 주식을 팔지 못하게 묶는 약정입니다. 해제 물량은 오버행 이슈가 될 수 있습니다.",
    "블록딜": "장중 시장 충격을 줄이기 위해 대량 주식을 장외에서 한 번에 거래하는 방식입니다.",
    "오버행": "시장에 나올 가능성이 큰 대량 매도 물량 부담을 말합니다. 보호예수 해제나 전환사채 전환 가능성과 연결됩니다.",
    "유통주식수": "실제로 시장에서 거래될 수 있는 주식 수입니다. 유통 물량이 적으면 작은 수급에도 주가가 크게 움직일 수 있습니다.",
    "유상증자": "회사가 새 주식을 발행해 투자자에게 돈을 받고 파는 자금 조달 방식입니다. 성장 투자 재원이 될 수 있지만 기존 주주 지분 희석 부담도 봐야 합니다.",
    "감자": "회사가 자본금을 줄이는 절차입니다. 재무구조 개선 목적일 수 있지만 주주가치 훼손 우려로 해석되는 경우도 많습니다.",
    "전환사채": "일정 조건에서 주식으로 바꿀 수 있는 회사채입니다. 전환 가능 물량이 많으면 향후 주식 수 증가 부담이 생길 수 있습니다.",
    "CB": "전환사채를 뜻합니다. 채권이지만 조건에 따라 주식으로 바뀔 수 있어 오버행 이슈와 함께 자주 언급됩니다.",
    "BW": "신주인수권부사채입니다. 정해진 조건으로 새 주식을 살 수 있는 권리가 붙은 채권이라 주식 수 증가 가능성을 함께 봐야 합니다.",
    "전환가액": "전환사채나 신주인수권이 주식으로 바뀔 때 적용되는 기준 가격입니다.",
    "리픽싱": "전환가액이나 행사가격을 주가 하락 등에 맞춰 조정하는 것을 말합니다. 낮아질수록 전환 가능 주식 수가 늘어 기존 주주에게 부담이 될 수 있습니다.",
    "희석": "새 주식 발행이나 전환사채 전환으로 기존 주주의 지분 비율이나 주당 가치가 낮아지는 현상입니다.",
    "거래정지": "특정 사유로 주식 거래가 일시 중단되는 상태입니다. 공시, 불성실공시, 상장폐지 심사, 중요 정보 확인 등이 원인이 될 수 있습니다.",
    "관리종목": "재무, 공시, 거래량 등 상장 유지에 위험 신호가 있어 거래소가 별도로 지정한 종목입니다.",
    "상장폐지": "거래소에서 더 이상 거래될 수 없게 상장이 취소되는 것입니다. 투자금 회수 가능성이 크게 낮아질 수 있습니다.",
    "불성실공시": "공시를 늦게 내거나 번복, 변경하는 등 공시 의무를 제대로 지키지 않은 경우를 말합니다.",
    "조회공시": "거래소가 주가 급등락이나 풍문에 대해 회사에 사실 여부 설명을 요구하는 공시입니다.",
    "시간외": "정규장 전후에 이루어지는 거래를 말합니다. 거래량이 적어 가격이 크게 흔들릴 수 있습니다.",
    "동시호가": "정해진 시간 동안 주문을 모아 하나의 가격으로 체결하는 방식입니다. 시초가와 종가 형성에 중요합니다.",
    "장전": "정규장이 시작되기 전 시간대를 말합니다. 전날 이후 뉴스와 주문 흐름이 시초가에 반영될 수 있습니다.",
    "장후": "정규장이 끝난 뒤 시간대를 말합니다. 장마감 후 공시나 뉴스가 다음 거래일 흐름에 영향을 줄 수 있습니다.",
    "외국인": "국내 주식을 거래하는 해외 투자자 자금을 뜻합니다. 대형주 수급에서 영향력이 큰 경우가 많습니다.",
    "기관": "연기금, 투신, 보험, 사모펀드 같은 전문 투자기관을 말합니다. 중대형주 수급을 볼 때 자주 확인합니다.",
    "프로그램매매": "정해진 조건이나 지수 차익거래 전략에 따라 컴퓨터가 자동으로 내는 매매입니다. 대형주와 지수 흐름에 영향을 줄 수 있습니다.",
    "연기금": "국민연금 같은 장기성 기관 자금을 말합니다. 대형주 수급에서 안정적인 매수·매도 주체로 자주 봅니다.",
    "ETF": "여러 자산을 묶어 거래소에서 주식처럼 사고파는 펀드입니다. 지수, 업종, 테마에 분산 투자할 때 쓰입니다.",
    "ETN": "증권사가 발행하는 상장지수증권입니다. 기초지표를 따라가지만 발행사 신용위험과 괴리율을 함께 확인해야 합니다.",
    "레버리지": "기초자산 변동보다 더 크게 움직이도록 설계된 상품이나 투자 방식을 말합니다. 수익과 손실이 모두 커질 수 있습니다.",
    "인버스": "기초자산이 하락할 때 수익이 나도록 설계된 상품입니다. 장기 보유 시 복리 효과와 괴리 위험을 봐야 합니다.",
    "괴리율": "ETF나 ETN 가격이 실제 기초가치와 얼마나 벌어졌는지 나타내는 비율입니다.",
    "선반영": "앞으로 나올 호재나 악재가 이미 주가에 어느 정도 반영됐다는 뜻입니다.",
    "재료소멸": "기대했던 뉴스나 이벤트가 실제로 확인된 뒤 더 이상 주가를 밀어 올릴 새 요인이 약해지는 상황입니다.",
    "어닝서프라이즈": "실제 실적이 시장 예상보다 좋게 나온 경우입니다. 주가에 긍정적으로 작용할 수 있습니다.",
    "어닝쇼크": "실제 실적이 시장 예상보다 나쁘게 나온 경우입니다. 주가에 부담이 될 수 있습니다.",
    "피크아웃": "실적이나 업황이 고점을 지나 둔화될 수 있다는 우려를 말합니다.",
    "턴어라운드": "실적이나 업황이 부진에서 회복 국면으로 돌아서는 흐름입니다.",
    "모멘텀": "주가나 실적을 움직이는 힘이나 방향성을 뜻합니다. 실적 모멘텀, 수급 모멘텀처럼 씁니다.",
    "펀더멘털": "기업의 실적, 재무상태, 경쟁력 같은 기초 체력을 말합니다.",
    "밸류에이션": "기업 가치가 현재 주가에 비해 비싼지 싼지 평가하는 과정입니다. PER, PBR 같은 지표를 함께 봅니다.",
    "저평가": "기업 가치나 이익 체력에 비해 주가가 낮게 거래된다고 보는 상태입니다.",
    "고평가": "기업 가치나 이익 체력에 비해 주가가 높게 거래된다고 보는 상태입니다.",
    "매집": "특정 주체가 물량을 꾸준히 사 모으는 것으로 해석되는 흐름입니다. 실제 의도는 확인하기 어렵기 때문에 거래량과 공시를 함께 봐야 합니다.",
    "털기": "단기 투자자들이 손절하거나 물량을 내놓도록 가격을 흔드는 상황을 설명할 때 쓰는 속어입니다. 확인된 사실이라기보다 시장 해석에 가깝습니다.",
    "눌림목": "상승 흐름 중 잠시 조정을 받는 구간을 말합니다. 추세가 유지되는지 거래량과 지지선을 함께 봅니다.",
    "돌파": "주가가 기존 저항선이나 박스권 상단을 넘어서는 움직임입니다.",
    "이평선": "이동평균선을 줄여 부르는 말입니다. 일정 기간 평균 주가를 선으로 표시해 추세를 파악하는 데 씁니다.",
    "골든크로스": "단기 이동평균선이 장기 이동평균선을 위로 돌파하는 신호입니다. 상승 전환 기대를 말할 때 쓰입니다.",
    "데드크로스": "단기 이동평균선이 장기 이동평균선을 아래로 이탈하는 신호입니다. 하락 전환 우려를 말할 때 쓰입니다.",
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

TERM_KEYWORD_HINTS = (
    "HBM",
    "IR",
    "CAPEX",
    "EPS",
    "PER",
    "XBRL",
    "DART",
    "AI 서버",
    "데이터센터",
    "거래대금",
    "거래량",
    "컨센서스",
    "가이던스",
    "분기보고서",
    "반기보고서",
    "사업보고서",
    "자기주식처분",
    "유상증자",
    "전환사채",
    "공급계약",
    "기업설명회",
    "실적",
    "영업이익",
    "개미",
    "세력",
    "주포",
    "증시",
    "투자",
    "투기",
    "손절",
    "익절",
    "물타기",
    "불타기",
    "상한가",
    "하한가",
    "테마주",
    "작전주",
    "큰손",
    "선물",
    "옵션",
    "선물옵션",
    "단타",
    "스윙",
    "장투",
    "오퍼링",
    "배당",
    "배당락",
    "주주",
    "주가",
    "호가",
    "시초가",
    "종가",
    "고가",
    "저가",
    "매수",
    "매도",
    "체결",
    "예수금",
    "증거금",
    "미수",
    "신용",
    "반대매매",
    "공매도",
    "숏커버링",
    "갭상승",
    "갭하락",
    "VI",
    "서킷브레이커",
    "평단",
    "물량",
    "매물대",
    "지지선",
    "저항선",
    "신고가",
    "신저가",
    "박스권",
    "추세",
    "변동성",
    "액면분할",
    "무상증자",
    "권리락",
    "자사주",
    "보호예수",
    "락업",
    "블록딜",
    "오버행",
    "유통주식수",
    "유상증자",
    "감자",
    "전환사채",
    "CB",
    "BW",
    "전환가액",
    "리픽싱",
    "희석",
    "거래정지",
    "관리종목",
    "상장폐지",
    "불성실공시",
    "조회공시",
    "시간외",
    "동시호가",
    "장전",
    "장후",
    "외국인",
    "기관",
    "프로그램매매",
    "연기금",
    "ETF",
    "ETN",
    "레버리지",
    "인버스",
    "괴리율",
    "선반영",
    "재료소멸",
    "어닝서프라이즈",
    "어닝쇼크",
    "피크아웃",
    "턴어라운드",
    "모멘텀",
    "펀더멘털",
    "밸류에이션",
    "저평가",
    "고평가",
    "매집",
    "털기",
    "눌림목",
    "돌파",
    "이평선",
    "골든크로스",
    "데드크로스",
)


def collect_term_text_chunks(payload: dict[str, Any]) -> list[str]:
    chunks: list[str] = []
    analysis = payload.get("analysis") or {}
    chunks.append(analysis.get("summary", ""))
    for reason in analysis.get("reasons", []):
        chunks.extend([reason.get("title", ""), reason.get("explanation", "")])
    for source in payload.get("sources", []):
        chunks.extend([source.get("title", ""), source.get("excerpt", "")])
    for item in payload.get("news_timeline", []):
        chunks.extend([item.get("title", ""), item.get("summary", "")])
    for disclosure in payload.get("disclosure_summaries", []):
        chunks.extend([disclosure.get("title", ""), disclosure.get("summary", ""), disclosure.get("excerpt", "")])
    for related in payload.get("related_stocks", []):
        chunks.extend([related.get("theme", ""), related.get("reason", "")])
    stock = payload.get("stock") or {}
    chunks.extend([stock.get("sector", ""), stock.get("name", "")])
    return [chunk for chunk in chunks if chunk]


def extract_term_candidates(payload: dict[str, Any]) -> list[str]:
    combined_text = "\n".join(collect_term_text_chunks(payload))
    candidates: list[str] = []
    seen: set[str] = set()

    def add_candidate(term: str) -> None:
        clean = re.sub(r"\s+", " ", str(term or "")).strip(" .,;:()[]{}")
        if len(clean) < 2 or clean in seen:
            return
        seen.add(clean)
        candidates.append(clean)

    for match in re.findall(r"\b[A-Z][A-Z0-9-]{1,11}\b", combined_text):
        add_candidate(match)

    lowered = combined_text.lower()
    for keyword in TERM_KEYWORD_HINTS:
        if keyword.lower() in lowered:
            add_candidate(keyword)

    for term in TERM_EXPLANATIONS:
        if term.lower() in lowered:
            add_candidate(term)

    return candidates


def rank_term_candidates(candidates: list[str], payload: dict[str, Any]) -> list[str]:
    if not candidates:
        return []

    stock = payload.get("stock") or {}
    stock_name = str(stock.get("name") or "").strip().lower()
    stock_ticker = str(stock.get("ticker") or "").strip().lower()
    stock_sector = str(stock.get("sector") or "").strip().lower()
    source_titles = " ".join(source.get("title", "") for source in payload.get("sources", []))
    disclosure_titles = " ".join(
        source.get("title", "") for source in payload.get("disclosure_summaries", []) if source.get("title")
    )
    analysis = payload.get("analysis") or {}
    reason_text = " ".join(
        [analysis.get("summary", "")]
        + [reason.get("title", "") for reason in analysis.get("reasons", [])]
        + [reason.get("explanation", "") for reason in analysis.get("reasons", [])]
    )

    scored: list[tuple[int, str]] = []
    for term in candidates:
        lowered = term.lower()
        if lowered in {stock_name, stock_ticker, stock_sector, "kospi", "kosdaq", "krx"}:
            continue
        score = 0
        if lowered in source_titles.lower():
            score += 4
        if lowered in disclosure_titles.lower():
            score += 5
        if lowered in reason_text.lower():
            score += 3
        if term in TERM_EXPLANATIONS:
            score += 2
        if re.fullmatch(r"[A-Z0-9-]{2,12}", term):
            score += 2
        score += min(reason_text.lower().count(lowered), 2)
        if score > 0:
            scored.append((score, term))

    scored.sort(key=lambda item: (-item[0], len(item[1]), item[1]))
    ranked = [term for _score, term in scored[:5]]
    if ranked:
        return ranked

    defaults = ["거래대금", "공시", "실적", business_theme(stock)[0].split("/")[0]]
    return [term for term in defaults if term]


def term_focus(term: str) -> str:
    normalized = term.strip().upper()
    if normalized in {"CB", "BW", "EB", "전환사채", "유상증자", "공시", "DART", "분기보고서", "공급계약", "IR", "기업설명회"}:
        return "disclosure"
    if normalized in {"거래량", "거래대금", "변동률", "전일 대비", "수급", "조정", "시가총액"}:
        return "market"
    if normalized in {"PER", "EPS", "실적", "영업이익", "컨센서스", "가이던스"}:
        return "fundamental"
    if normalized in {"노조 리스크", "리스크"}:
        return "risk"
    return "theme"


def term_definition(term: str) -> str:
    return TERM_EXPLANATIONS.get(term, f"{term}는 이 종목을 이해할 때 자주 등장하는 핵심 용어입니다.")


def term_why_it_matters(term: str, payload: dict[str, Any]) -> str:
    stock = payload.get("stock") or {}
    stock_name = stock.get("name", "이 종목")
    summary = str((payload.get("analysis") or {}).get("summary") or "")
    source_titles = " ".join(source.get("title", "") for source in payload.get("sources", []))
    combined = f"{summary} {source_titles}"
    focus = term_focus(term)

    if term == "DART":
        return f"{stock_name} 이슈를 뉴스 요약이 아니라 공시 원문 기준으로 다시 확인하고 싶을 때 가장 직접적인 출처가 되는 용어입니다."
    if term in {"IR", "기업설명회"}:
        return f"{stock_name}가 시장과 어떤 메시지를 공유하려는지, 실적 설명이나 사업 계획 소통 일정이 있는지 해석할 때 중요합니다."
    if term == "AI":
        return f"{stock_name} 움직임이 단순 개별 뉴스가 아니라 AI 테마 기대와 연결돼 있는지 판단할 때 이 용어가 중요합니다."

    if focus == "disclosure":
        if "계약" in combined:
            return f"{stock_name}의 최근 공시 흐름을 볼 때, 이 용어는 계약 내용이 실제 매출로 이어질 가능성을 읽는 데 중요합니다."
        if "자금" in combined or term in {"CB", "전환사채", "유상증자"}:
            return f"{stock_name} 이슈에서 이 용어는 자금 조달 방식과 잠재적인 주식 수 변화 가능성을 해석할 때 핵심입니다."
        return f"{stock_name} 관련 공시를 읽을 때, 어떤 종류의 발표와 일정인지 빠르게 구분하는 데 도움이 됩니다."
    if focus == "market":
        if term == "거래량":
            return f"{stock_name} 주가가 움직일 때 거래량이 같이 커졌는지 보면, 단순 등락인지 실제 매수세가 붙었는지 가늠하는 데 도움이 됩니다."
        if term == "거래대금":
            return f"{stock_name}에 자금이 얼마나 강하게 몰렸는지 보려면 거래량보다 거래대금이 더 직접적인 단서가 될 수 있습니다."
        if term == "변동률":
            return f"{stock_name}가 하루 동안 얼마나 강하게 반응했는지 보여 주기 때문에, 다른 종목과 움직임의 세기를 비교할 때 중요합니다."
        return f"{stock_name} 수급 흐름을 읽을 때 이 용어는 가격 반응의 강도와 참여 규모를 함께 해석하는 기준이 됩니다."
    if focus == "fundamental":
        return f"{stock_name} 이슈가 단기 뉴스에 그치지 않고 실적 기대까지 이어질 수 있는지 판단할 때 이 용어가 중요합니다."
    if focus == "risk":
        return f"{stock_name}의 생산 차질, 비용 부담, 협상 불확실성처럼 투자심리를 눌러서 주가에 부담이 될 수 있는지 해석할 때 중요합니다."
    return f"{stock_name}가 어떤 산업 기대를 타고 움직였는지 이해하려면 이 용어가 가리키는 테마와 사업 맥락을 함께 봐야 합니다."


def explanation_needs_definition_fallback(term: str, text: str) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return True
    lowered = normalized.lower()
    generic_phrases = (
        "최근 뉴스",
        "공시 맥락",
        "핵심 용어",
        "함께 읽어야",
        "무엇인지",
        "어떤 이슈인지",
    )
    return any(phrase in normalized for phrase in generic_phrases) or lowered in {term.lower(), f"{term.lower()}입니다."}


def explanation_needs_context_fallback(text: str) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return True
    generic_phrases = (
        "함께 봐야",
        "맥락에서 중요",
        "빠르게 이해",
        "도움이 됩니다.",
    )
    return all(phrase not in normalized for phrase in ("매출", "자금", "수급", "거래", "실적", "계약", "공시", "테마", "주가")) and any(
        phrase in normalized for phrase in generic_phrases
    )


def fallback_term_explanations(terms: list[str], payload: dict[str, Any]) -> list[dict[str, str]]:
    explanations = []
    for term in terms[:5]:
        definition = term_definition(term)
        why_it_matters = term_why_it_matters(term, payload)
        explanations.append(
            {
                "term": term,
                "definition": definition,
                "why_it_matters": why_it_matters,
            }
        )
    return explanations


def explain_terms_with_ai(terms: list[str], payload: dict[str, Any]) -> list[dict[str, str]] | None:
    if not terms:
        return []

    stock = payload.get("stock") or {}
    source_titles = "\n".join(
        f"- {source.get('title', '')}" for source in payload.get("sources", [])[:5] if source.get("title")
    )
    cache_key = "|".join(
        [
            "term-v4",
            stock.get("ticker", ""),
            ",".join(terms),
            (payload.get("analysis") or {}).get("summary", "")[:120],
        ]
    )
    cached = TERM_EXPLANATION_CACHE.get(cache_key)
    if cached and time.time() - cached[0] < TERM_CACHE_TTL_SECONDS:
        return cached[1]

    prompt = f"""
종목: {stock.get('name', '')} ({stock.get('ticker', '')}, {stock.get('market', '')})
업종: {stock.get('sector', '')}
설명할 용어: {", ".join(terms)}

최근 맥락:
{(payload.get("analysis") or {}).get("summary", "")}

관련 뉴스/공시 제목:
{source_titles}
"""
    result = call_llm_json(
        instructions=(
            "너는 한국 주식 초보 투자자를 위한 용어 설명 도우미다. "
            "각 용어를 1문장으로 쉽게 설명하고, 왜 지금 이 종목 맥락에서 중요한지 1문장으로 덧붙여라. "
            "definition과 why_it_matters가 같은 말을 반복하지 않게 쓰고, 각 용어의 설명은 서로 다른 표현으로 작성해라. "
            "투자 추천처럼 쓰지 말고, 쉽고 짧은 한국어로 답하라."
        ),
        input_text=prompt,
        schema_name="term_explanations",
        schema=TERM_EXPLANATION_SCHEMA,
        max_output_tokens=900,
    )
    if not isinstance(result, dict) or not isinstance(result.get("terms"), list):
        return None

    normalized = []
    for item in result["terms"]:
        if not all(isinstance(item.get(key), str) and item.get(key).strip() for key in ("term", "definition", "why_it_matters")):
            continue
        term = item["term"].strip()
        definition = item["definition"].strip()
        why_it_matters = item["why_it_matters"].strip()
        if explanation_needs_definition_fallback(term, definition):
            definition = term_definition(term)
        if explanation_needs_context_fallback(why_it_matters):
            why_it_matters = term_why_it_matters(term, payload)
        normalized.append(
            {
                "term": term,
                "definition": definition,
                "why_it_matters": why_it_matters,
            }
        )
    if normalized:
        TERM_EXPLANATION_CACHE[cache_key] = (time.time(), normalized)
    return normalized or None


def detect_terms(payload: dict[str, Any]) -> list[dict[str, str]]:
    candidates = extract_term_candidates(payload)
    ranked = rank_term_candidates(candidates, payload)
    if not ranked:
        return []

    known_terms = [term for term in ranked if term in TERM_EXPLANATIONS]
    unknown_terms = [term for term in ranked if term not in TERM_EXPLANATIONS]

    resolved: dict[str, dict[str, str]] = {
        item["term"]: item for item in fallback_term_explanations(known_terms, payload)
    }
    if unknown_terms:
        ai_terms = explain_terms_with_ai(unknown_terms, payload) or []
        for item in ai_terms:
            resolved[item["term"]] = item
        missing_terms = [term for term in unknown_terms if term not in resolved]
        if missing_terms:
            for item in fallback_term_explanations(missing_terms, payload):
                resolved[item["term"]] = item

    return [resolved[term] for term in ranked if term in resolved]
