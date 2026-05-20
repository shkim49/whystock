from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from storage import fetch_analysis_record, init_db, save_briefing_snapshot


class StorageTests(unittest.TestCase):
    def test_save_briefing_snapshot_persists_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "whystock-test.db"
            init_db(db_path)
            payload = {
                "event": {
                    "id": "briefing-005930",
                    "event_type": "briefing",
                    "detected_at": "2026-05-20T10:15:00+09:00",
                },
                "stock": {
                    "ticker": "005930",
                },
                "analysis": {
                    "generated_by": "gemini_api",
                    "summary": "반도체 업황 개선과 거래량 증가가 함께 보입니다.",
                    "disclaimer": "투자 추천이 아닌 정보 요약입니다.",
                    "reasons": [
                        {
                            "title": "반도체 업황",
                            "importance": 1,
                            "evidence_source_ids": [1],
                            "explanation": "뉴스와 시세가 함께 반응했습니다.",
                        }
                    ],
                },
                "sources": [
                    {
                        "id": 1,
                        "source_type": "news",
                        "title": "삼성전자, 반도체 업황 기대감",
                        "url": "https://example.com/news/1",
                        "publisher": "연합뉴스",
                        "published_at": "2026-05-20T10:00:00+09:00",
                        "excerpt": "반도체 업황 개선 기대가 이어집니다.",
                    }
                ],
            }

            save_briefing_snapshot(payload, db_path)
            analysis = fetch_analysis_record("briefing-005930", db_path)

            self.assertIsNotNone(analysis)
            assert analysis is not None
            self.assertEqual(analysis["ticker"], "005930")
            self.assertEqual(analysis["generated_by"], "gemini_api")
            self.assertIn("반도체 업황", analysis["summary"])


if __name__ == "__main__":
    unittest.main()

