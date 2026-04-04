# market_api

QLD RSI 신호 계산, 미국 지수 아침 브리핑, NEOS ETF 배당 마감일 신호를 제공하는 독립 FastAPI 서비스입니다.

## 역할

- Yahoo Finance 일봉 데이터 수집
- QLD RSI(14) 계산과 상태 전이 저장
- S&P500 / Nasdaq 아침 브리핑 생성
- XQQI / QQQI 배당 권리 최종 매수 마감일 계산
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
- `POST /api/v1/jobs/distribution-deadline-check`
- `GET /api/v1/status/current`
- `GET /api/v1/status/history`

`/api/v1/*` 엔드포인트는 모두 `X-Job-Secret` 헤더가 필요합니다.

미국 주식시장이 주말 또는 `Good Friday` 같은 full holiday 인 날에는
브리핑/QLD 응답이 `should_send=false`, `skip_reason="market_closed"` 를 반환합니다.
이 경우 운영 workflow 는 텔레그램을 보내지 않습니다.

## 배당 마감일 신호

`POST /api/v1/jobs/distribution-deadline-check` 는 NEOS 공식 `XQQI` / `QQQI` 분배 일정을 읽고, 배당 권리를 받기 위한 마지막 매수 가능 미국 정규장 세션을 계산합니다.

- `alert_kst_date`: 한국 기준으로 사용자가 행동해야 하는 아침 날짜
- `deadline_kst_date`: 마지막 매수 가능 미국장이 끝나는 시점이 걸치는 한국 날짜
- `alert_due`: 현재 실행 시점에 실제 알림을 보내야 하는지 여부

운영에서는 `distribution_deadline_states.last_alert_key` 로 중복 발송을 막고, `distribution_deadline_alerts` 에 발송 이력을 남깁니다.

배당 알림 workflow 와 별도 health workflow 가 이 endpoint 를 함께 사용합니다.

- `neos-distribution-deadline.json`: `05:30 KST` 배당 알림 전용
- `neos-distribution-health.json`: `10분`마다 호출해 endpoint 장애를 감시
- HTTP 5xx, transport error, 비정상 payload 는 조회 실패로 간주
- `2회 연속 실패` 시 운영 텔레그램 채널로 1회 알림, 정상 응답 복귀 시 복구 메시지 1회 발송
- 정상 응답이면서 `alert_due=false` 인 경우는 장애가 아니라 단순 무알림 상태입니다
