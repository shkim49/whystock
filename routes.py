from __future__ import annotations

import json
import mimetypes
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler
from typing import Any

from config import WEB_DIR
from services.assistant_service import assistant_chat
from services.auth_service import bearer_token, login_user, logout_token, signup_user, user_from_authorization
from services.briefing_service import detail_for_ticker
from services.market_service import movers_payload, search_stocks, ticker_from_event_id
from services.term_service import TERM_EXPLANATIONS
from utils import now_iso


class WhyStockHandler(BaseHTTPRequestHandler):
    server_version = "WhyStock/2.0"

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if path == "/api/health":
                self.send_json({"ok": True, "service": "WhyStock", "time": now_iso()})
            elif path == "/api/auth/me":
                user = self.current_user()
                if user is None:
                    self.send_json({"error": "unauthorized"}, status=401)
                else:
                    self.send_json({"user": user})
            elif path.startswith("/api/") and not self.require_auth():
                return
            elif path == "/api/events/movers":
                force_refresh = query.get("refresh", ["0"])[0] == "1"
                self.send_json(movers_payload(force_refresh=force_refresh))
            elif match := re.fullmatch(r"/api/events/([^/]+)", path):
                event_id = urllib.parse.unquote(match.group(1))
                ticker = ticker_from_event_id(event_id)
                prefix = "briefing" if "briefing-" in event_id else "live"
                force_refresh = query.get("refresh", ["0"])[0] == "1"
                self.send_json(detail_for_ticker(ticker, prefix=prefix, force_refresh=force_refresh))
            elif path == "/api/stocks/search":
                search_query = query.get("query", [""])[0]
                self.send_json({"stocks": search_stocks(search_query)})
            elif match := re.fullmatch(r"/api/stocks/(\d{6})/briefing", path):
                force_refresh = query.get("refresh", ["0"])[0] == "1"
                self.send_json(detail_for_ticker(match.group(1), prefix="briefing", force_refresh=force_refresh))
            elif path == "/api/terms/explain":
                term = query.get("term", [""])[0].strip()
                self.send_json(
                    {
                        "term": term,
                        "explanation": TERM_EXPLANATIONS.get(
                            term,
                            "등록된 용어 설명이 없습니다. 화면 문장에 등장한 주요 금융 용어부터 확장할 수 있습니다.",
                        ),
                    }
                )
            else:
                self.serve_static(path)
        except KeyError:
            self.send_json({"error": "not_found"}, status=404)
        except Exception as exc:  # noqa: BLE001 - demo server should return a visible error
            self.send_json({"error": "server_error", "detail": str(exc)}, status=500)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/auth/signup":
                response, status = signup_user(self.read_json_body())
                self.send_json(response, status=status)
            elif path == "/api/auth/login":
                response, status = login_user(self.read_json_body())
                self.send_json(response, status=status)
            elif path == "/api/auth/logout":
                logout_token(bearer_token(self.headers.get("Authorization")))
                self.send_json({"ok": True})
            elif path.startswith("/api/") and not self.require_auth():
                return
            elif path == "/api/assistant/chat":
                response, status = assistant_chat(self.read_json_body())
                self.send_json(response, status=status)
            elif match := re.fullmatch(r"/api/events/([^/]+)/analyze", path):
                self.read_json_body()
                event_id = urllib.parse.unquote(match.group(1))
                ticker = ticker_from_event_id(event_id)
                prefix = "briefing" if "briefing-" in event_id else "live"
                self.send_json(detail_for_ticker(ticker, prefix=prefix, force_refresh=True))
            else:
                self.send_json({"error": "not_found"}, status=404)
        except KeyError:
            self.send_json({"error": "not_found"}, status=404)
        except Exception as exc:  # noqa: BLE001
            self.send_json({"error": "server_error", "detail": str(exc)}, status=500)

    def read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def current_user(self) -> dict[str, Any] | None:
        if not hasattr(self, "_current_user"):
            self._current_user = user_from_authorization(self.headers.get("Authorization"))
        return self._current_user

    def require_auth(self) -> bool:
        if self.current_user() is not None:
            return True
        self.send_json({"error": "unauthorized"}, status=401)
        return False

    def serve_static(self, path: str) -> None:
        requested = urllib.parse.unquote(path.lstrip("/")) or "index.html"
        candidate = (WEB_DIR / requested).resolve()
        if WEB_DIR not in candidate.parents and candidate != WEB_DIR:
            self.send_error(403)
            return
        if not candidate.exists() or candidate.is_dir():
            candidate = WEB_DIR / "index.html"
        mime, _ = mimetypes.guess_type(candidate)
        data = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[server] {self.address_string()} - {fmt % args}")
