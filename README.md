# WhyStock

급등락한 국내 주식의 실제 시세, 뉴스, 공시 링크를 묶어 주가 변동의 이유를 빠르게 요약하는 MVP 웹 서비스입니다.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/shkim49/whystock)

## Requirements

- Python 3.10+
- 인터넷 연결

## Run

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

## Optional AI Analysis

OpenAI API 키가 없으면 내장 규칙 기반 분석으로 동작합니다. API 키를 설정하면 OpenAI Responses API로 분석을 생성합니다.

```powershell
$env:OPENAI_API_KEY="your_api_key"
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
