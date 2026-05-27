from __future__ import annotations

import json
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server


def request_json(path: str, method: str = "GET", body: dict | None = None, token: str | None = None) -> dict:
    headers = {"Connection": "close"}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:8765{path}",
        data=data,
        headers=headers,
        method=method,
    )
    last_error: Exception | None = None
    for _attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(0.3)
    raise RuntimeError(f"request failed for {path}: {last_error}")


def get_json(path: str, token: str | None = None) -> dict:
    return request_json(path, token=token)


def post_json(path: str, body: dict, token: str | None = None) -> dict:
    return request_json(path, method="POST", body=body, token=token)


def assert_unauthorized_without_token(path: str) -> None:
    request = urllib.request.Request(f"http://127.0.0.1:8765{path}", headers={"Connection": "close"})
    try:
        urllib.request.urlopen(request, timeout=30).close()
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return
        raise
    raise RuntimeError(f"{path} did not require authentication")


def main() -> int:
    server.init_db()
    httpd = ThreadingHTTPServer(("127.0.0.1", 8765), server.WhyStockHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        health = get_json("/api/health")
        if not health.get("ok"):
            raise RuntimeError("health check failed")
        assert_unauthorized_without_token("/api/events/movers")
        auth = post_json(
            "/api/auth/signup",
            {"email": f"smoke-{int(time.time() * 1000)}@example.com", "password": "password123"},
        )
        token = auth.get("token")
        if not token:
            raise RuntimeError("signup did not return a token")
        movers = get_json("/api/events/movers", token=token)
        if len(movers.get("categories", [])) < 2:
            raise RuntimeError("movers endpoint returned no categories")
        if len(movers.get("events", [])) < 1:
            raise RuntimeError("movers endpoint returned no events")
        event_id = movers["events"][0]["id"]
        detail = get_json(f"/api/events/{event_id}", token=token)
        if not detail.get("analysis") or not detail.get("sources"):
            raise RuntimeError("event detail is incomplete")
        terms = detail.get("terms", [])
        if not terms or not terms[0].get("definition"):
            raise RuntimeError("term explanations are missing")
        print(f"smoke ok: {len(movers['events'])} events, selected {event_id}")
        return 0
    finally:
        httpd.shutdown()
        httpd.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
