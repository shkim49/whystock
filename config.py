from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
DATA_DIR = ROOT / "data"
ENV_FILE = ROOT / ".env"


def _strip_wrapping_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_dotenv(path: Path = ENV_FILE, override: bool = False) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = _strip_wrapping_quotes(value.strip())
        if not override and key in os.environ:
            continue
        os.environ[key] = value


load_dotenv()

DB_PATH = Path(os.getenv("SQLITE_PATH", str(DATA_DIR / "whystock.db")))

NAVER_HEADERS = {
    "User-Agent": "Mozilla/5.0 WhyStock/1.0",
    "Accept": "application/json,text/xml,application/xml,text/html;q=0.9,*/*;q=0.8",
}

CACHE_TTL_SECONDS = 60
TRENDING_CACHE_TTL_SECONDS = 180
TERM_CACHE_TTL_SECONDS = 3600
MARKET_CATALOG_MAX_PAGES = int(os.getenv("MARKET_CATALOG_MAX_PAGES", "18"))
MARKET_CATALOG_PAGE_SIZE = int(os.getenv("MARKET_CATALOG_PAGE_SIZE", "100"))
TRENDING_CANDIDATE_LIMIT = int(os.getenv("TRENDING_CANDIDATE_LIMIT", "30"))
