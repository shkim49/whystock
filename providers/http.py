from __future__ import annotations

import html
import http.client
import json
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

from config import NAVER_HEADERS

TRANSIENT_FETCH_ERRORS = (
    urllib.error.URLError,
    TimeoutError,
    http.client.HTTPException,
    ConnectionError,
    OSError,
)
TRANSIENT_PARSE_ERRORS = TRANSIENT_FETCH_ERRORS + (ValueError, json.JSONDecodeError)
TRANSIENT_XML_ERRORS = TRANSIENT_FETCH_ERRORS + (ET.ParseError,)


def fetch_text(url: str, timeout: int = 8) -> str:
    request = urllib.request.Request(url, headers=NAVER_HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def fetch_json(url: str, timeout: int = 8) -> Any:
    return json.loads(fetch_text(url, timeout))


def fetch_form(url: str, data: dict[str, Any], timeout: int = 8) -> str:
    encoded = urllib.parse.urlencode(data, doseq=True).encode("utf-8")
    headers = {**NAVER_HEADERS, "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
    request = urllib.request.Request(url, data=encoded, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def strip_html(value: str) -> str:
    import re

    value = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", value)
    value = re.sub(r"(?is)<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()
