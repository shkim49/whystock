from __future__ import annotations

from typing import Any

CATALOG_CACHE: dict[str, Any] = {"loaded_at": 0.0, "stocks": []}
BRIEFING_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
TRENDING_CACHE: dict[str, Any] = {"loaded_at": 0.0, "payload": None}
TERM_EXPLANATION_CACHE: dict[str, tuple[float, list[dict[str, str]]]] = {}
