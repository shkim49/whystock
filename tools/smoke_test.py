from __future__ import annotations

import json
import sys
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server


def get_json(path: str) -> dict:
    with urllib.request.urlopen(f"http://127.0.0.1:8765{path}", timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    server.init_db()
    httpd = ThreadingHTTPServer(("127.0.0.1", 8765), server.WhyStockHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        health = get_json("/api/health")
        movers = get_json("/api/events/movers")
        if not health.get("ok"):
            raise RuntimeError("health check failed")
        if len(movers.get("events", [])) < 1:
            raise RuntimeError("movers endpoint returned no events")
        event_id = movers["events"][0]["id"]
        detail = get_json(f"/api/events/{event_id}")
        if not detail.get("analysis") or not detail.get("sources"):
            raise RuntimeError("event detail is incomplete")
        print(f"smoke ok: {len(movers['events'])} events, selected {event_id}")
        return 0
    finally:
        httpd.shutdown()
        httpd.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
