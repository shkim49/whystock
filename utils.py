from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


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
