from __future__ import annotations

import html
import re
from datetime import datetime, timedelta
from typing import Any

from providers.http import TRANSIENT_FETCH_ERRORS, fetch_form, fetch_text, strip_html
from utils import now_iso
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
    except TRANSIENT_FETCH_ERRORS:
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


def fetch_dart_company_info(ticker: str) -> dict[str, str] | None:
    try:
        html_text = fetch_form(
            "https://dart.fss.or.kr/corp/searchCorpL.ax",
            {
                "textCrpNm": ticker,
                "currentPage": 1,
                "corpType": ["P", "A", "X", "E"],
                "corpTypeAll": "all",
            },
            timeout=10,
        )
    except TRANSIENT_FETCH_ERRORS:
        return None

    cik_match = re.search(r"name='hiddenCikCD1' value='(\d+)'", html_text)
    name_match = re.search(r"name='hiddenCikNM1' value='([^']+)'", html_text)
    if not cik_match or not name_match:
        return None

    return {
        "cik": cik_match.group(1),
        "name": html.unescape(name_match.group(1)),
    }


def parse_dart_detail_search_rows(html_text: str) -> list[dict[str, str]]:
    disclosures: list[dict[str, str]] = []
    rows = re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", html_text)
    for row in rows:
        cells = re.findall(r"(?is)<td\b[^>]*>(.*?)</td>", row)
        if len(cells) < 5:
            continue

        report_match = re.search(r'href="/dsaf001/main\.do\?rcpNo=(\d+)"[^>]*>(.*?)</a>', cells[2], re.I | re.S)
        if not report_match:
            continue

        company = strip_html(cells[1])
        title = strip_html(report_match.group(2))
        published_at = strip_html(cells[4])
        presenter = strip_html(cells[3])
        rcp_no = report_match.group(1)
        if not title or not rcp_no:
            continue

        disclosures.append(
            {
                "title": title,
                "company": company,
                "published_at": published_at,
                "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp_no}",
                "rcp_no": rcp_no,
                "presenter": presenter,
            }
        )
        if len(disclosures) >= 3:
            break
    return disclosures


def fetch_dart_disclosures_by_company(stock: dict[str, Any], event: dict[str, Any]) -> list[dict[str, str]]:
    company_info = fetch_dart_company_info(stock["ticker"])
    if not company_info:
        return []

    event_date = event.get("detected_at") or now_iso()
    try:
        end_date = datetime.fromisoformat(event_date.replace("Z", "+00:00")).date()
    except ValueError:
        end_date = datetime.now().date()
    start_date = end_date - timedelta(days=365)

    try:
        html_text = fetch_form(
            "https://dart.fss.or.kr/dsab007/detailSearch.ax",
            {
                "option": "corp",
                "currentPage": 1,
                "maxResults": 15,
                "maxLinks": 10,
                "sort": "date",
                "series": "desc",
                "textCrpCik": company_info["cik"],
                "lateKeyword": "",
                "keyword": "",
                "reportNamePopYn": "",
                "textkeyword": "",
                "businessCode": "all",
                "autoSearch": "N",
                "autoSearchCorp": "Y",
                "textCrpNm": company_info["name"],
                "reportName": "",
                "tocSrch": "",
                "textCrpNm2": "",
                "textPresenterNm": "",
                "startDate": start_date.strftime("%Y%m%d"),
                "endDate": end_date.strftime("%Y%m%d"),
                "finalReport": "recent",
                "businessNm": "",
                "reportName2": "",
                "tocSrch2": "",
                "corporationType": "all",
                "closingAccountsMonth": "all",
                "decadeType": "",
            },
            timeout=12,
        )
    except TRANSIENT_FETCH_ERRORS:
        return []

    return parse_dart_detail_search_rows(html_text)


def fetch_dart_disclosures(stock: dict[str, Any], event: dict[str, Any]) -> list[dict[str, str]]:
    found = fetch_dart_disclosures_by_company(stock, event)
    if found:
        for disclosure in found:
            body_excerpt = fetch_disclosure_body_excerpt(disclosure.get("rcp_no", ""))
            disclosure["summary"] = disclosure_summary_from_title(disclosure["title"], disclosure["company"])
            disclosure["key_sentence"] = body_excerpt or disclosure["summary"]
        return found[:3]

    event_date = event.get("detected_at") or now_iso()
    try:
        cursor = datetime.fromisoformat(event_date.replace("Z", "+00:00")).date()
    except ValueError:
        cursor = datetime.now().date()

    found = []
    for offset in range(0, 8):
        select_date = (cursor - timedelta(days=offset)).strftime("%Y%m%d")
        page_texts = []
        try:
            page_texts.append(fetch_text(f"https://dart.fss.or.kr/dsac001/mainAll.do?selectDate={select_date}", timeout=10))
        except TRANSIENT_FETCH_ERRORS:
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
            except TRANSIENT_FETCH_ERRORS:
                break
        for html_text in page_texts:
            found.extend(parse_dart_recent_rows(html_text, stock["name"]))
            if found:
                break
        if found:
            break

    if not found:
        search_url = "https://dart.fss.or.kr/dsab007/main.do?option=corp&keyword=" + stock["ticker"]
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
