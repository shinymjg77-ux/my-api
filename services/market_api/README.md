# market_api

QLD RSI 신호 계산과 미국 지수 아침 브리핑을 제공하는 독립 FastAPI 서비스입니다.

## 역할

- Yahoo Finance 일봉 데이터 수집
- QLD RSI(14) 계산과 상태 전이 저장
- S&P500 / Nasdaq 아침 브리핑 생성
- n8n이 호출할 구조화 JSON API 제공

## 실행

```bash
source ../../.venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8100
```

## 주요 API

- `GET /healthz`
- `GET /health`
- `GET /api/v1/briefings/morning`
- `POST /api/v1/jobs/rsi-check`
- `GET /api/v1/status/current`
- `GET /api/v1/status/history`

`/api/v1/*` 엔드포인트는 모두 `X-Job-Secret` 헤더가 필요합니다.
