from __future__ import annotations

import argparse
import os
from http.server import ThreadingHTTPServer

import config
from routes import WhyStockHandler
from storage import init_db


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the WhyStock MVP server")
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    parser.add_argument("--port", default=int(os.getenv("PORT", "8000")), type=int)
    args = parser.parse_args()

    init_db()
    httpd = ThreadingHTTPServer((args.host, args.port), WhyStockHandler)
    print(f"WhyStock running at http://{args.host}:{args.port}")
    print(
        "AI providers: "
        f"Gemini={'on' if os.getenv('GEMINI_API_KEY') else 'off'} "
        f"OpenAI={'on' if os.getenv('OPENAI_API_KEY') else 'off'}"
    )
    if config.ENV_FILE.exists():
        print(f"Loaded environment from {config.ENV_FILE}")
    else:
        print("No .env file found. Using process environment only.")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping WhyStock.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
