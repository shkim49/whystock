from __future__ import annotations

import unittest

from ai import validate_analysis_result
from tests.fixture_utils import read_json_fixture


class AiValidationFixtureTests(unittest.TestCase):
    def test_validate_analysis_result_filters_invalid_reason_and_forbidden_language(self) -> None:
        raw = read_json_fixture("analysis_invalid_response.json")
        sources = read_json_fixture("analysis_sources.json")

        validated = validate_analysis_result(raw, sources)

        self.assertIsNotNone(validated)
        assert validated is not None
        self.assertEqual(validated["summary"], "반도체 업황 개선과 거래량 확대 흐름이 함께 보입니다.")
        self.assertEqual(len(validated["reasons"]), 1)
        self.assertEqual(validated["reasons"][0]["title"], "반도체 업황")
        self.assertEqual(validated["reasons"][0]["evidence_source_ids"], [1, 2])
        self.assertEqual(validated["disclaimer"], "투자 추천이 아닌 정보 요약입니다.")

    def test_validate_analysis_result_returns_none_when_summary_becomes_empty(self) -> None:
        raw = read_json_fixture("analysis_summary_only_forbidden.json")
        sources = read_json_fixture("analysis_sources.json")

        validated = validate_analysis_result(raw, sources)

        self.assertIsNone(validated)


if __name__ == "__main__":
    unittest.main()

