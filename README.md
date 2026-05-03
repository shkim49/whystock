# WhyStock

WhyStock is an MVP web service that explains the likely reasons behind sharp stock moves in under one minute.

The project is intentionally small enough for a solo university capstone: it runs with Python standard-library modules only, ships a compact frontend, stores sample market events in SQLite, and can optionally call OpenAI for structured AI analysis and image generation when `OPENAI_API_KEY` is configured.

## Core Concept

> 급등락한 종목의 가격 변화, 뉴스, 공시를 연결해 주가 변동의 이유를 1분 안에 구조화해서 보여주는 AI 웹 서비스

## What Is Implemented

- Movement-event centered dashboard
- Stock mover list with live Naver Pay Securities price/change/volume data
- Event detail view with:
  - top reasons
  - clickable source evidence
  - market reaction
  - condition-based scenarios
  - related stocks
  - dynamic term explanations based on the selected event text
- Naver Pay Securities market catalog search
- Google News RSS source collection
- Offline analysis fallback
- Optional OpenAI Responses API integration for structured analysis
- Optional OpenAI Image API script for a project hero/brand image
- Planning document for project presentation

The old numeric confidence score was removed because it would be difficult to justify objectively in an MVP. The UI now shows the number of evidence links and the live data source instead.

## Run

```powershell
python server.py
```

Open:

```text
http://127.0.0.1:8000
```

If port `8000` is busy:

```powershell
python server.py --port 8010
```

## Verify

```powershell
python tools/smoke_test.py
```

## Optional OpenAI Setup

The app works without an API key using the built-in demo analysis engine.

To enable live AI analysis:

```powershell
$env:OPENAI_API_KEY="your_api_key"
python server.py
```

Optional model override:

```powershell
$env:OPENAI_TEXT_MODEL="gpt-5.5"
```

To generate the visual asset with OpenAI Image API:

```powershell
$env:OPENAI_API_KEY="your_api_key"
python tools/generate_brand_image.py
```

The generated image is saved to:

```text
web/assets/generated/why-stock-hero.png
```

The current app includes a deterministic SVG fallback because this Codex session did not have a built-in image generation tool exposed and no `OPENAI_API_KEY` was set.

## Project Structure

```text
.
├── server.py
├── docs/
│   └── plan.md
├── tools/
│   └── generate_brand_image.py
├── web/
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   └── assets/generated/
│       ├── image-prompt.txt
│       └── why-stock-hero.svg
└── data/
    └── whystock.db  # created on first run
```

## API

```text
GET  /api/health
GET  /api/events/movers
GET  /api/events/{event_id}
POST /api/events/{event_id}/analyze
GET  /api/stocks/search?query=삼성
GET  /api/stocks/{stock_id}/related
GET  /api/terms/explain?term=외국인 순매수
```

## Presentation Angle

- This is not a stock prediction service.
- It converts unstructured market information into structured, explainable reasons.
- Every AI reason is tied to evidence sources.
- The output is condition-based, not a promise of future price movement.
