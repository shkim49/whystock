from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = ROOT / "web" / "assets" / "generated" / "image-prompt.txt"
OUTPUT_PATH = ROOT / "web" / "assets" / "generated" / "why-stock-hero.png"


def main() -> int:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY is not set. Set it first, then rerun this script.", file=sys.stderr)
        return 1

    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    payload = {
        "model": os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1"),
        "prompt": prompt,
        "size": os.getenv("OPENAI_IMAGE_SIZE", "1536x1024"),
        "quality": os.getenv("OPENAI_IMAGE_QUALITY", "medium"),
    }

    request = urllib.request.Request(
        "https://api.openai.com/v1/images/generations",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"Image generation failed: HTTP {exc.code}\n{detail}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"Image generation failed: {exc}", file=sys.stderr)
        return 1

    image = result.get("data", [{}])[0]
    if "b64_json" in image:
        image_bytes = base64.b64decode(image["b64_json"])
    elif "url" in image:
        with urllib.request.urlopen(image["url"], timeout=120) as response:
            image_bytes = response.read()
    else:
        print("Image generation response did not include b64_json or url.", file=sys.stderr)
        return 1

    OUTPUT_PATH.write_bytes(image_bytes)
    print(f"Saved generated image to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

