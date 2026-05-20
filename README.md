# WhyStock

급등락한 국내 주식의 실제 시세, 뉴스, 공시 링크를 묶어 주가 변동의 이유를 빠르게 요약하는 MVP 웹 서비스입니다.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/shkim49/whystock)

## Requirements

- Python 3.10+
- 인터넷 연결

## Run

`.env` 파일을 우선 읽고, 같은 이름의 운영체제 환경변수가 있으면 그 값을 우선 사용합니다.

```powershell
python server.py
```

브라우저에서 아래 주소를 엽니다.

```text
http://127.0.0.1:8000
```

포트가 이미 사용 중이면 다른 포트로 실행합니다.

```powershell
python server.py --port 8010
```

## Verify

```powershell
python tools/smoke_test.py
```

외부 API 없이 fixture 기반 테스트만 돌리고 싶으면 아래 명령을 사용합니다.

```powershell
python tools/fixture_test.py
```

## Optional AI Analysis

AI 분석 우선순위는 다음과 같습니다.

1. Gemini API
2. OpenAI Responses API
3. 내장 규칙 기반 분석

Gemini 키가 있으면 먼저 Gemini를 사용하고, Gemini 호출이 불가능하거나 실패하면 OpenAI를 시도합니다. 둘 다 사용할 수 없으면 규칙 기반 분석으로 동작합니다.

프로젝트 루트의 `.env`에 키를 넣고 서버를 다시 시작합니다.

```text
GEMINI_API_KEY=your_gemini_api_key
GEMINI_TEXT_MODEL=gemini-2.5-flash
OPENAI_API_KEY=your_openai_api_key
OPENAI_TEXT_MODEL=gpt-5.5
```

`GEMINI_API_KEY`만 있으면 Gemini 분석을 우선 사용합니다. `OPENAI_API_KEY`는 Gemini 실패 시에만 fallback으로 사용합니다.

터미널에서 직접 넣고 실행해도 됩니다.

```powershell
$env:GEMINI_API_KEY="your_gemini_api_key"
$env:GEMINI_TEXT_MODEL="gemini-2.5-flash"
# optional fallback
$env:OPENAI_API_KEY="your_openai_api_key"
$env:OPENAI_TEXT_MODEL="gpt-5.5"
python server.py
```

## Files

```text
server.py
web/index.html
web/styles.css
web/app.js
tools/smoke_test.py
docs/plan.md
```

## Local Storage

분석 결과와 근거 자료는 기본적으로 `data/whystock.db`에 저장합니다.
경로를 바꾸고 싶으면 `.env`에 아래 값을 추가할 수 있습니다.

```text
SQLITE_PATH=data/whystock.db
```
