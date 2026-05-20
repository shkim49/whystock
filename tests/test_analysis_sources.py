from __future__ import annotations

import unittest

from services.analysis_service import dedupe_sources


class AnalysisSourceTests(unittest.TestCase):
    def test_dedupe_sources_collapses_same_disclosure_title_company_and_day(self) -> None:
        sources = [
            {
                "id": 1,
                "source_type": "price",
                "source_type_label": "시세",
                "title": "삼성전자 시세",
                "url": "https://example.com/price",
                "publisher": "네이버페이 증권",
                "published_at": "2026-05-20T09:00:00+09:00",
                "excerpt": "현재가 기준",
            },
            {
                "id": 2,
                "source_type": "disclosure",
                "source_type_label": "공시",
                "title": "투자설명서(일괄신고)",
                "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=1",
                "publisher": "DART",
                "published_at": "2026-05-20 12:00",
                "excerpt": "공시 요약",
                "company": "NH투자증권",
                "rcp_no": "1",
            },
            {
                "id": 3,
                "source_type": "disclosure",
                "source_type_label": "공시",
                "title": "투자설명서(일괄신고)",
                "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=2",
                "publisher": "DART",
                "published_at": "2026-05-20 12:00",
                "excerpt": "공시 요약",
                "company": "NH투자증권",
                "rcp_no": "2",
            },
        ]

        deduped = dedupe_sources(sources)

        self.assertEqual(len(deduped), 2)
        self.assertEqual([source["id"] for source in deduped], [1, 2])


if __name__ == "__main__":
    unittest.main()
