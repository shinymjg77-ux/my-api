# 2026-03-20 시장 브리핑 발송 오류

## 요약

2026-03-20 05:30 KST 에 `n8n`의 시장 브리핑 워크플로우가 정상 브리핑 대신 아래 오류 문구를 텔레그램으로 전송했다.

```text
market_api 브리핑 호출 실패
Response body is not valid JSON. Change "Response Format" to "Text"
```

`Ops alert` 워크플로우는 같은 시각에 정상 실행 중이었고, 문제는 시장 브리핑 전용 워크플로우 `My workflow` 경로에 한정돼 있었다.

## 실제 원인

브리핑 워크플로우는 아래 공개 경로를 통해 `market_api`를 호출한다.

- `GET https://ansan-jarvis.duckdns.org/internal/market-api/api/v1/briefings/morning`
- `POST https://ansan-jarvis.duckdns.org/internal/market-api/api/v1/jobs/rsi-check`

하지만 운영 서버의 활성 Nginx 설정 파일 `/etc/nginx/sites-available/btcore-log-console.conf` 에서
`/internal/market-api/` 프록시 블록이 빠져 있었다.

그 결과 요청이 `market_api`로 전달되지 못하고 Next.js 프런트로 흘러가 `404 HTML` 페이지를 반환했다.
`n8n`은 해당 응답을 JSON으로 파싱하려 했고, 그 실패 메시지를 그대로 텔레그램으로 전송했다.

즉, 문제는 `n8n`의 JSON 파서나 `market_api` 자체 장애가 아니라 운영 Nginx 경로 누락이었다.

## 확인 근거

- 2026-03-20 05:30 KST 실행 이력
  - `Ops alert` workflow id `D9sW5kLm2QxP7nRb`: 성공
  - `My workflow` workflow id `TaYv5KrsbygswQi6`: 성공 상태이지만 내부 메시지는 오류 문구 전송
- `execution 294` 데이터에서 아래 메시지 확인
  - `Response body is not valid JSON. Change "Response Format" to "Text"`
- 서버에서 동일 URL 직접 호출 시 복구 전 `404 HTML` 응답 확인
- `market_api` 로컬 헬스체크와 직접 API 호출은 정상
  - `http://127.0.0.1:8100/healthz`
  - `http://127.0.0.1:8100/api/v1/briefings/morning`
  - `http://127.0.0.1:8100/api/v1/jobs/rsi-check`

## 복구 조치

운영 서버에서 활성 Nginx 설정에 아래 블록을 복구했다.

```nginx
location ^~ /internal/market-api/ {
    proxy_pass http://127.0.0.1:8100/;
    proxy_read_timeout 30s;
}
```

적용 절차:

1. `/etc/nginx/sites-available/btcore-log-console.conf` 수정
2. `sudo nginx -t`
3. `sudo systemctl reload nginx`

## 복구 후 검증

복구 직후 아래 검증을 수행했다.

호스트에서:

```bash
curl -H "X-Job-Secret: <JOB_SHARED_SECRET>" \
  https://ansan-jarvis.duckdns.org/internal/market-api/api/v1/briefings/morning

curl -X POST -H "X-Job-Secret: <JOB_SHARED_SECRET>" \
  https://ansan-jarvis.duckdns.org/internal/market-api/api/v1/jobs/rsi-check
```

`n8n` 컨테이너 안에서:

```bash
docker exec n8n node -e "(async()=>{const r=await fetch('https://ansan-jarvis.duckdns.org/internal/market-api/api/v1/briefings/morning',{headers:{'X-Job-Secret':'<JOB_SHARED_SECRET>'}});console.log(r.status, await r.text())})()"

docker exec n8n node -e "(async()=>{const r=await fetch('https://ansan-jarvis.duckdns.org/internal/market-api/api/v1/jobs/rsi-check',{method:'POST',headers:{'X-Job-Secret':'<JOB_SHARED_SECRET>'}});console.log(r.status, await r.text())})()"
```

모든 호출이 `200` 으로 통과했다.

## 재발 방지

- 저장소의 Nginx 예시 파일 `deploy/nginx/site.conf.example` 에도 같은 `/internal/market-api/` 프록시를 반영한다.
- 배포 후 아래 공개 경로를 반드시 확인한다.
  - `/internal/market-api/healthz`
  - `/internal/market-api/api/v1/briefings/morning`
  - `/internal/market-api/api/v1/jobs/rsi-check`
- `n8n` workflow가 `success` 상태라도 실제 텔레그램 본문이 오류일 수 있으므로, 워크플로우 status와 전송 메시지를 함께 봐야 한다.

## 운영 메모

- `/ops status` 는 현재 지원 명령이 아니다.
- 텔레그램 조회 명령은 `/ops help`, `/ops version`, `/ops drift`, `/ops overview` 네 가지만 지원한다.
- GUI가 필요할 때는 로컬에서 아래 터널로 `n8n`을 연다.

```bash
ssh -N -L 5678:127.0.0.1:5678 oci-ubuntu
```
