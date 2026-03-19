# OCI Ubuntu 배포 절차

시스템 전체 구조와 dual-slot 배포 흐름도는 먼저 [system-overview.md](./system-overview.md) 를 보는 편이 빠르다.

이 문서는 이 프로젝트를 `OCI Ubuntu` 서버에 배포하는 실제 절차를 정리한 문서다. 예시 도메인은 `admin.example.com` 이고, 구성은 아래와 같다.

- `Nginx`: 외부 진입점, HTTPS 종료, 리버스 프록시
- `Next.js 안정 주소`: `127.0.0.1:3100`
- `Next.js 슬롯`: `127.0.0.1:3001` (`blue`), `127.0.0.1:3002` (`green`)
- `FastAPI 안정 주소`: `127.0.0.1:9000`
- `FastAPI 슬롯`: `127.0.0.1:8001` (`blue`), `127.0.0.1:8002` (`green`)
- `market_api`: `127.0.0.1:8100` 또는 서버 private IP `:8100`, 내부 전용
- `systemd`: 백엔드/프론트엔드 프로세스 관리
- `SQLite`: `/srv/my-api/data/app.db`
- `릴리스 전환`: `/srv/my-api/releases/<timestamp>` 와 `/srv/my-api/current`

## 1. 선행 조건

- OCI 인스턴스에 Ubuntu 설치 완료
- `admin.example.com` 이 서버 공인 IP를 가리키도록 DNS 설정 완료
- OCI Security List 또는 Network Security Group 에서 아래 포트 허용
- `22/tcp`
- `80/tcp`
- `443/tcp`

서버 접속 후 기본 패키지를 설치한다.

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx python3-venv python3-pip git curl unzip
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
node -v
npm -v
python3 --version
```

권장 기준:

- Node.js 22 LTS
- Python 3.12 이상

## 2. 디렉터리 구성

배포 경로는 `/srv/my-api` 로 가정한다.

```bash
sudo mkdir -p /srv/my-api
sudo mkdir -p /srv/my-api/data
sudo chown -R $USER:$USER /srv/my-api
```

코드를 서버에 배치한다.

```bash
cd /srv/my-api
git clone <YOUR_GIT_REPOSITORY_URL> .
```

만약 이미 복사해 둔 코드가 있다면 `git clone` 대신 파일을 업로드해도 된다.

## 3. 백엔드 환경변수 설정

예시 파일은 저장소의 [deploy/env/backend.env.example](../deploy/env/backend.env.example) 를 기준으로 한다.

서버에는 `systemd` 가 읽는 실제 환경파일을 `/etc/my-api/backend.env` 로 둔다.

```bash
sudo mkdir -p /etc/my-api
sudo cp /srv/my-api/deploy/env/backend.env.example /etc/my-api/backend.env
sudo chmod 600 /etc/my-api/backend.env
sudo nano /etc/my-api/backend.env
```

예시 내용:

```env
APP_NAME=Personal API Admin
ENVIRONMENT=production
DEBUG=false
API_PREFIX=/api/v1

SECRET_KEY=replace-with-a-long-random-string-at-least-32-chars
ENCRYPTION_KEY=replace-with-a-valid-fernet-key
JOB_SHARED_SECRET=replace-with-a-long-random-job-secret
ACCESS_TOKEN_EXPIRE_MINUTES=720
ADMIN_COOKIE_NAME=admin_session
COOKIE_SECURE=true
COOKIE_SAMESITE=lax

DATABASE_URL=sqlite:////srv/my-api/data/app.db
CORS_ORIGINS=["https://admin.example.com"]

BOOTSTRAP_ADMIN_USERNAME=admin
BOOTSTRAP_ADMIN_PASSWORD=change-this-now

DASHBOARD_WINDOW_DAYS=7
LOG_PAGE_SIZE_DEFAULT=20
LOG_PAGE_SIZE_MAX=100
MANAGED_API_ADMIN_BASE_URL=http://127.0.0.1:9000
MANAGED_API_MARKET_BASE_URL=http://127.0.0.1:8100
OPS_COMMAND_SHARED_SECRET=replace-with-a-random-ops-command-secret
OPS_COMMAND_ALLOWED_CHAT_IDS=123456789
```

`MANAGED_API_ADMIN_BASE_URL` 와 `MANAGED_API_MARKET_BASE_URL` 는 관리자 콘솔이 시작될 때 `managed_apis` 기본 항목을 자동 등록할 때 사용한다. 운영 환경에서 내부 호출 주소가 바뀌면 이 값을 같이 맞춰야 한다.

`JOB_SHARED_SECRET` 는 관리자 백엔드의 잡 API와 `market_api`가 공통으로 사용하는 내부 호출용 시크릿이다. 현재 운영에서는 n8n이 아래 두 경로에서 이 값을 헤더 `X-Job-Secret` 으로 보낸다.

- `https://admin.example.com/api/proxy/jobs/ops-check`
- `https://admin.example.com/internal/market-api/...`

`SECRET_KEY` 생성 예시:

```bash
python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
```

`ENCRYPTION_KEY` 생성 예시:

```bash
python3 - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
```

## 4. 프론트엔드 환경변수 설정

예시 파일은 저장소의 [deploy/env/frontend.env.example](../deploy/env/frontend.env.example) 를 기준으로 한다.

```bash
sudo cp /srv/my-api/deploy/env/frontend.env.example /etc/my-api/frontend.env
sudo chmod 600 /etc/my-api/frontend.env
sudo nano /etc/my-api/frontend.env
```

예시 내용:

```env
NODE_ENV=production
PORT=3100
HOSTNAME=127.0.0.1
BACKEND_BASE_URL=http://127.0.0.1:9000
BACKEND_API_PREFIX=/api/v1
```

운영에서는 프런트가 단일 백엔드 포트에 직접 붙지 않고, Nginx 내부 안정 주소 `http://127.0.0.1:9000` 을 보게 한다.
실제 systemd 슬롯 서비스는 `PORT` 값을 직접 쓰지 않고, `/etc/my-api/frontend-slots/<slot>.env` 의 포트 값을 우선 사용한다.

## 4-1. 시장 신호 API 환경변수 설정

예시 파일은 저장소의 [deploy/env/market-api.env.example](../deploy/env/market-api.env.example) 를 기준으로 한다.

```bash
sudo cp /srv/my-api/deploy/env/market-api.env.example /etc/my-api/market-api.env
sudo chmod 600 /etc/my-api/market-api.env
sudo nano /etc/my-api/market-api.env
```

예시 내용:

```env
APP_NAME=Market Signal API
ENVIRONMENT=production
DEBUG=false
API_PREFIX=/api/v1

JOB_SHARED_SECRET=replace-with-a-long-random-job-secret
DATABASE_URL=sqlite:////srv/my-api/services/market_api/data/app.db
MARKET_API_BIND_HOST=127.0.0.1
MARKET_API_PORT=8100

MARKET_RSI_SYMBOL=QLD
MARKET_RSI_PERIOD=14
MARKET_RSI_THRESHOLD=30
MARKET_BRIEFING_SYMBOLS=^GSPC,^IXIC
```

`market_api`를 서버 셸에서만 호출하면 `MARKET_API_BIND_HOST=127.0.0.1`로 충분하다.

`n8n`이 Docker 컨테이너로 실행 중이면, 컨테이너에서 호스트의 `127.0.0.1` 에 직접 접근할 수 없다. 현재 운영 방식은 `market_api` 를 계속 `127.0.0.1` 에 두고, Nginx 내부 프록시 경로를 통해 `n8n`이 HTTPS 주소를 호출하는 방식이다.

예시:

```nginx
location ^~ /internal/market-api/ {
    proxy_pass http://127.0.0.1:8100/;
    proxy_read_timeout 30s;
}
```

이 경우 `n8n` 호출 URL은 아래처럼 잡는다.

```text
https://ansan-jarvis.duckdns.org/internal/market-api/api/v1/briefings/morning
https://ansan-jarvis.duckdns.org/internal/market-api/api/v1/jobs/rsi-check
```

## 4-2. n8n DNS 안정화

최근 운영에서는 `Ops alert` 가 아래와 같은 메시지로 실패한 적이 있었다.

```text
getaddrinfo EAIAGAIN ansan-jarvis.duckdns.org
```

이 오류는 백엔드나 프록시 인증 이전에, `n8n` 컨테이너가 도메인 이름을 DNS로 해석하지 못했다는 뜻이다.
운영에서 `n8n` 을 Docker 컨테이너로 돌린다면, 컨테이너 DNS를 명시적으로 고정하는 편이 안정적이다.

기본값:

- `1.1.1.1`
- `8.8.8.8`

`docker compose` 를 쓴다면 [deploy/docker/n8n.compose.prod.yml](../deploy/docker/n8n.compose.prod.yml) 또는 [deploy/docker/n8n.compose.example.yml](../deploy/docker/n8n.compose.example.yml) 예시처럼 `dns:` 를 추가한다.

```yaml
services:
  n8n:
    image: docker.n8n.io/n8nio/n8n:latest
    dns:
      - 1.1.1.1
      - 8.8.8.8
```

이미 `docker run` 기반으로 운영 중이면 [deploy/systemd/n8n-docker.service.example](../deploy/systemd/n8n-docker.service.example) 예시처럼 `--dns 1.1.1.1 --dns 8.8.8.8` 옵션을 추가한다.

중요:

- DuckDNS 도메인을 `/etc/hosts` 나 `extra_hosts` 로 고정 IP 매핑하지 않는다.
- DuckDNS 는 공인 IP가 바뀔 수 있으므로, 정적 매핑은 더 큰 장애를 만들 수 있다.
- `Ops alert` 의 호출 대상 URL은 계속 `https://ansan-jarvis.duckdns.org/api/proxy/jobs/ops-check` 를 사용한다.

## 5. 백엔드 빌드 및 실행 준비

```bash
cd /srv/my-api
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt
mkdir -p /srv/my-api/data
```

수동 실행 확인:

```bash
cd /srv/my-api/backend
set -a
source /etc/my-api/backend.env
set +a
/srv/my-api/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers
```

다른 터미널에서 헬스체크:

```bash
curl http://127.0.0.1:8000/healthz
```

정상 응답 예시:

```json
{"status":"ok"}
```

관리자 백엔드가 처음 올라오면 아래 기본 API가 `managed_apis`에 자동 등록된다.

- `platform/admin`
- `platform/admin/dashboard`
- `platform/admin/jobs`
- `market/health`
- `market/briefings`
- `market/signals`
- `market/status`

## 6. 프론트엔드 빌드 및 실행 준비

```bash
cd /srv/my-api/frontend
npm ci
set -a
source /etc/my-api/frontend.env
set +a
npm run build
```

수동 실행 확인:

```bash
cd /srv/my-api/current/frontend
set -a
source /etc/my-api/frontend.env
set +a
npm run start -- --hostname 127.0.0.1 --port 3001
```

다른 터미널에서 확인:

```bash
curl -I http://127.0.0.1:3001/login
curl -fsS http://127.0.0.1:3001/api/runtime/version
```

브라우저에서 `/apis`를 열면 왼쪽에는 API 계층 트리, 오른쪽에는 선택한 API 상세 패널이 보여야 한다. 이 화면에는 수동 신규 등록 폼이 없고, 자동 등록된 기본 API와 기존 저장된 API를 탐색/수정하는 용도로 사용한다.

## 6-1. 시장 신호 API 실행 준비

```bash
cd /srv/my-api
source .venv/bin/activate
pip install -r services/market_api/requirements.txt
mkdir -p /srv/my-api/services/market_api/data
```

수동 실행 확인:

```bash
cd /srv/my-api/current/services/market_api
set -a
source /etc/my-api/market-api.env
set +a
/srv/my-api/.venv/bin/uvicorn app.main:app --host "${MARKET_API_BIND_HOST:-127.0.0.1}" --port "${MARKET_API_PORT:-8100}" --proxy-headers
```

다른 터미널에서 헬스체크:

```bash
curl "http://${MARKET_API_BIND_HOST:-127.0.0.1}:${MARKET_API_PORT:-8100}/healthz"
```

브리핑 확인:

```bash
curl -H "X-Job-Secret: <JOB_SHARED_SECRET>" "http://${MARKET_API_BIND_HOST:-127.0.0.1}:${MARKET_API_PORT:-8100}/api/v1/briefings/morning"
```

RSI 확인:

```bash
curl -X POST -H "X-Job-Secret: <JOB_SHARED_SECRET>" "http://${MARKET_API_BIND_HOST:-127.0.0.1}:${MARKET_API_PORT:-8100}/api/v1/jobs/rsi-check"
```

운영 이상 감지 잡 확인:

```bash
curl -H "X-Job-Secret: <JOB_SHARED_SECRET>" "http://127.0.0.1:8000/api/v1/jobs/ops-check"
curl -H "X-Job-Secret: <JOB_SHARED_SECRET>" "https://admin.example.com/api/proxy/jobs/ops-check"
```

현재 운영에서는 `n8n`이 관리자 프론트의 `/api/proxy/jobs/ops-check` 를 호출하고, Next.js 프록시가 `X-Job-Secret` 헤더를 백엔드로 그대로 전달한다.

`Ops alert` 워크플로우 권장값:

- 요청 URL: `GET https://ansan-jarvis.duckdns.org/api/proxy/jobs/ops-check`
- 헤더: `X-Job-Secret: <JOB_SHARED_SECRET>`
- 요청 타임아웃: `10초`
- 재시도 횟수: `3회`
- 시도 간 대기: `5초`
- 실패 텔레그램 발송 조건: 모든 재시도 실패 후 1회만 발송

조회 전용 텔레그램 운영 명령 템플릿:

- [deploy/n8n/workflows/ops-command-telegram.json](../deploy/n8n/workflows/ops-command-telegram.json)
- 같은 텔레그램 봇 credential을 재사용한다.
- import 전 아래 placeholder를 실제 값으로 치환한다.
- `__OPS_PUBLIC_BASE_URL__`
- `__OPS_COMMAND_SHARED_SECRET__`
- `__OPS_COMMAND_ALLOWED_CHAT_IDS__`
- `__N8N_TELEGRAM_CREDENTIAL_ID__`

지원 명령:

- `/ops help`
- `/ops version`
- `/ops drift`
- `/ops overview`

이 워크플로우는 `Telegram Trigger` 가 아니라 일반 `n8n` webhook 으로 Telegram update 를 받는다.
공개 Nginx에서 `/webhook/` 과 `/webhook-test/` 경로를 `127.0.0.1:5678` 로 프록시해야 한다.
또한 `/etc/my-api/n8n.env` 의 `WEBHOOK_URL` 은 공개 HTTPS 도메인으로 맞춰야 한다.
텔레그램 bot webhook URL 은 아래처럼 등록한다.

```bash
curl -fsS "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
  --data-urlencode "url=https://admin.example.com/webhook/telegram/ops-command" \
  --data-urlencode "secret_token=<OPS_COMMAND_SHARED_SECRET>" \
  --data-urlencode 'allowed_updates=["message"]'
```

실패 알림 문구는 원문 오류를 유지하면서 앞에 분류 문구를 붙이는 편이 좋다.

예:

```text
DNS lookup failed
getaddrinfo EAIAGAIN ansan-jarvis.duckdns.org
```

## 7. systemd 등록

예시 유닛 파일은 저장소의 아래 파일을 사용한다.

- [deploy/systemd/personal-api-admin-backend@.service](../deploy/systemd/personal-api-admin-backend@.service)
- [deploy/systemd/personal-api-admin-frontend@.service](../deploy/systemd/personal-api-admin-frontend@.service)
- [deploy/systemd/personal-market-api.service](../deploy/systemd/personal-market-api.service)

서버에 복사:

```bash
sudo mkdir -p /etc/my-api/backend-slots
sudo mkdir -p /etc/my-api/frontend-slots
printf 'BACKEND_SLOT_PORT=8001\n' | sudo tee /etc/my-api/backend-slots/blue.env >/dev/null
printf 'BACKEND_SLOT_PORT=8002\n' | sudo tee /etc/my-api/backend-slots/green.env >/dev/null
printf 'FRONTEND_SLOT_PORT=3001\n' | sudo tee /etc/my-api/frontend-slots/blue.env >/dev/null
printf 'FRONTEND_SLOT_PORT=3002\n' | sudo tee /etc/my-api/frontend-slots/green.env >/dev/null
sudo cp /srv/my-api/deploy/systemd/personal-api-admin-backend@.service /etc/systemd/system/
sudo cp /srv/my-api/deploy/systemd/personal-api-admin-frontend@.service /etc/systemd/system/
sudo cp /srv/my-api/deploy/systemd/personal-market-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable personal-api-admin-backend@blue
sudo systemctl enable personal-api-admin-backend@green
sudo systemctl enable personal-api-admin-frontend@blue
sudo systemctl enable personal-api-admin-frontend@green
sudo systemctl enable personal-market-api
sudo systemctl start personal-api-admin-frontend@blue
sudo systemctl start personal-api-admin-frontend@green
sudo systemctl start personal-market-api
```

상태 확인:

```bash
sudo systemctl status personal-api-admin-backend@blue --no-pager
sudo systemctl status personal-api-admin-backend@green --no-pager
sudo systemctl status personal-api-admin-frontend@blue --no-pager
sudo systemctl status personal-api-admin-frontend@green --no-pager
sudo systemctl status personal-market-api --no-pager
```

로그 확인:

```bash
sudo journalctl -u personal-api-admin-backend@blue -n 100 --no-pager
sudo journalctl -u personal-api-admin-backend@green -n 100 --no-pager
sudo journalctl -u personal-api-admin-frontend@blue -n 100 --no-pager
sudo journalctl -u personal-api-admin-frontend@green -n 100 --no-pager
sudo journalctl -u personal-market-api -n 100 --no-pager
```

## 8. Nginx 설정

예시 설정 파일은 아래 두 파일을 같이 쓴다.

- [deploy/nginx/site.conf.example](../deploy/nginx/site.conf.example)
- [deploy/nginx/my-api-backend-upstream.conf.example](../deploy/nginx/my-api-backend-upstream.conf.example)
- [deploy/nginx/my-api-frontend-upstream.conf.example](../deploy/nginx/my-api-frontend-upstream.conf.example)

서버에 복사:

```bash
sudo mkdir -p /var/www/certbot
sudo cp /srv/my-api/deploy/nginx/site.conf.example /etc/nginx/sites-available/admin.example.com
sudo cp /srv/my-api/deploy/nginx/my-api-backend-upstream.conf.example /etc/nginx/snippets/my-api-backend-upstream.conf
sudo cp /srv/my-api/deploy/nginx/my-api-frontend-upstream.conf.example /etc/nginx/snippets/my-api-frontend-upstream.conf
sudo ln -sf /etc/nginx/sites-available/admin.example.com /etc/nginx/sites-enabled/admin.example.com
sudo nginx -t
sudo systemctl reload nginx
```

초기 SSL 발급 전에는 443 인증서 경로가 없어서 `nginx -t` 가 실패할 수 있다. 그 경우 아래 순서로 진행한다.

1. 먼저 80 포트만 쓰는 임시 설정으로 Nginx를 올린다.
2. `certbot` 으로 인증서를 발급한다.
3. 그 다음 최종 443 설정으로 교체하고 다시 로드한다.

가장 간단한 방법은 `certbot --nginx` 를 사용하는 것이다.

```bash
sudo certbot --nginx -d admin.example.com
```

인증서 자동 갱신 테스트:

```bash
sudo certbot renew --dry-run
```

## 9. UFW 사용 시 방화벽 예시

OCI 보안 규칙과 별개로 서버 내부 방화벽도 쓴다면:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

## 10. 배포 후 점검

아래 순서로 점검한다.

```bash
curl -I https://admin.example.com/login
curl https://admin.example.com/healthz
curl https://admin.example.com/version
curl http://127.0.0.1:9000/healthz
curl http://127.0.0.1:9000/version
```

브라우저 확인 항목:

- `https://admin.example.com/login` 접속
- 관리자 로그인 성공
- `/dashboard` 진입 성공
- API 등록/수정 가능
- DB 연결 테스트 가능
- 로그 페이지 필터 조회 가능
- `personal-market-api` 가 운영 화면에 `healthy` 로 보이는지 확인
- `/apis` 에 `platform/admin/jobs -> Ops Check Job` 이 보이는지 확인

`n8n` 운영 확인 항목:

- `My workflow`: 미국 증시 브리핑 + QLD RSI 발송
- `Ops alert`: 10분 주기 운영 이상 감지 알림

`n8n` 컨테이너 DNS 점검:

```bash
docker exec n8n sh -lc 'cat /etc/resolv.conf'
docker exec n8n node -e 'require("dns").lookup("ansan-jarvis.duckdns.org", console.log)'
docker exec n8n node -e '(async()=>{try{const r=await fetch("https://ansan-jarvis.duckdns.org/api/proxy/jobs/ops-check",{headers:{"X-Job-Secret":"<JOB_SHARED_SECRET>"}});console.log(r.status, await r.text())}catch(e){console.log(e.message)}})()'
```

반복 점검이 필요하면 [scripts/check_n8n_dns.sh](../scripts/check_n8n_dns.sh) 를 서버에 복사해서 사용할 수 있다.
버전 드리프트를 한 번에 점검하려면 로컬에서 [scripts/check_release_drift.sh](../scripts/check_release_drift.sh) 를 실행한다.

```bash
./scripts/check_release_drift.sh your-ssh-host-alias
```

## 11. 업데이트 배포 절차

권장 배포 절차는 서버 쪽 스크립트를 SSH로 트리거하는 방식이다.

```bash
./scripts/deploy_from_server.sh your-ssh-host-alias origin/main full
```

서버 중심 반자동 배포를 쓰려면 서버에 읽기 전용 저장소 미러를 한 번 준비한다.

```bash
sudo mkdir -p /srv/my-api
sudo chown -R ubuntu:ubuntu /srv/my-api
sudo -u ubuntu git clone https://github.com/shinymjg77-ux/my-api.git /srv/my-api/repo
sudo cp /srv/my-api/repo/deploy/env/ops.env.example /etc/my-api/ops.env
sudo cp /srv/my-api/repo/deploy/env/n8n.env.example /etc/my-api/n8n.env
sudo chown root:ubuntu /etc/my-api/ops.env /etc/my-api/n8n.env
sudo chmod 640 /etc/my-api/ops.env /etc/my-api/n8n.env
```

`/etc/my-api/n8n.env` 에는 아래 운영 명령용 값도 채운다.

```env
OPS_PUBLIC_BASE_URL=https://admin.example.com
OPS_COMMAND_SHARED_SECRET=replace-with-the-same-backend-ops-command-secret
OPS_COMMAND_ALLOWED_CHAT_IDS=123456789
N8N_TELEGRAM_CREDENTIAL_ID=replace-with-existing-telegram-credential-id
WEBHOOK_URL=https://admin.example.com/
```

이후 표준 배포 명령은 아래처럼 서버 쪽 스크립트를 SSH로 트리거하는 방식이다.

```bash
./scripts/deploy_from_server.sh your-ssh-host-alias origin/main full
```

서버는 `/srv/my-api/repo` 에서 ref를 fetch 한 뒤 새 release를 만들고, `n8n` compose 동기화와 앱 활성화를 스스로 수행한다.
백엔드만 먼저 무중단에 가깝게 교체하려면 아래처럼 `backend` 모드를 쓴다.

```bash
./scripts/deploy_from_server.sh your-ssh-host-alias origin/main backend
```

## 12. 실패 가능 지점

- DNS 가 서버 공인 IP를 가리키지 않으면 `certbot` 발급이 실패한다.
- OCI 보안 규칙에서 `80`, `443` 을 열지 않으면 외부 접속이 되지 않는다.
- 이 프론트엔드는 `/api/auth/*`, `/api/proxy/*` 를 Next.js route handler 로 사용하므로, Nginx 에서 `/api/` 를 FastAPI 로 직접 프록시하면 로그인과 프록시 호출이 깨진다.
- `COOKIE_SECURE=true` 인데 HTTPS 없이 직접 접속하면 로그인 쿠키가 정상 동작하지 않는다.
- `CORS_ORIGINS` 값이 JSON 배열 형식이 아니면 백엔드가 시작하지 않는다.
- `backend.env` 와 `frontend.env` 권한이 너무 넓으면 운영 보안상 좋지 않다.
- `market-api.env` 권한이 너무 넓으면 운영 보안상 좋지 않다.
- SQLite 파일 경로의 상위 디렉터리가 없거나 권한이 없으면 백엔드 초기화가 실패한다.
- `market_api` 는 내부 서비스이므로 Nginx에 공개 라우팅을 추가하지 않는다.
- `n8n` 컨테이너 DNS가 불안정하면 `getaddrinfo EAIAGAIN ansan-jarvis.duckdns.org` 로 운영 상태 조회가 실패할 수 있다.
- `Ops alert` 에 재시도가 없으면 일시적인 DNS 실패만으로 텔레그램 장애 알림이 발송될 수 있다.

## 13. SQLite 백업 cron

백업 스크립트:

- [scripts/backup_sqlite.sh](../scripts/backup_sqlite.sh)
- [deploy/cron/my-api-backup](../deploy/cron/my-api-backup)
- [scripts/upload_backup.sh](../scripts/upload_backup.sh)
- [deploy/env/ops.env.example](../deploy/env/ops.env.example)

설치:

```bash
sudo mkdir -p /var/log/my-api
sudo chown ubuntu:ubuntu /var/log/my-api
sudo cp /srv/my-api/current/deploy/env/ops.env.example /etc/my-api/ops.env
sudo chown root:ubuntu /etc/my-api/ops.env
sudo chmod 640 /etc/my-api/ops.env
sudo apt-get update
sudo apt-get install -y pipx
sudo -u ubuntu pipx install awscli
chmod +x /srv/my-api/current/scripts/backup_sqlite.sh
sudo cp /srv/my-api/current/deploy/cron/my-api-backup /etc/cron.d/my-api-backup
sudo chmod 644 /etc/cron.d/my-api-backup
```

`upload_backup.sh` 는 `AWS_BIN` 이 비어 있으면 현재 `PATH` 에서 `aws` 를 찾는다. `pipx` 로 설치했다면 보통 `/home/ubuntu/.local/bin/aws` 가 자동으로 사용된다.

수동 실행 확인:

```bash
/srv/my-api/current/scripts/backup_sqlite.sh
ls -lah /srv/my-api/backups/sqlite
```

## 14. 로그 회전

로그 회전 설정 파일:

- [deploy/logrotate/my-api](../deploy/logrotate/my-api)

대상 로그:

- `/var/log/my-api/backup.log`
- `/var/log/my-api/update.log`

설치:

```bash
sudo cp /srv/my-api/current/deploy/logrotate/my-api /etc/logrotate.d/my-api
sudo chmod 644 /etc/logrotate.d/my-api
sudo logrotate -d /etc/logrotate.d/my-api
```

참고:

- `nginx` 로그는 Ubuntu 기본 `/etc/logrotate.d/nginx` 가 이미 처리한다.
- `systemd` 서비스 표준 출력 로그는 `journald` 가 관리하므로 별도 파일 회전 대상이 아니다.

## 15. 장애 알림

알림 스크립트와 서비스:

- [scripts/send_alert.sh](../scripts/send_alert.sh)
- [deploy/systemd/my-api-alert@.service](../deploy/systemd/my-api-alert@.service)

지원 형태:

- `discord`
- `slack`
- `generic`

예시 설정:

```env
ALERT_WEBHOOK_TYPE=discord
ALERT_WEBHOOK_URL=https://discord.com/api/webhooks/...
ALERT_SOURCE=admin.example.com
```

설치:

```bash
sudo cp /srv/my-api/current/deploy/systemd/my-api-alert@.service /etc/systemd/system/
sudo systemctl daemon-reload
```

백엔드/프런트엔드 서비스 실패 시 `OnFailure`로 알림 서비스가 호출된다.
`/etc/my-api/ops.env` 는 `ubuntu` 사용자가 읽을 수 있어야 하므로 `root:ubuntu` 와 `640` 권한을 권장한다.

## 16. 릴리스 기반 업데이트 스크립트

스크립트:

- [scripts/deploy_release.sh](../scripts/deploy_release.sh)
- [scripts/remote_activate_release.sh](../scripts/remote_activate_release.sh)

구조:

- 새 코드 준비: `/srv/my-api/releases/<timestamp>`
- 백엔드는 `blue`, `green` 슬롯 중 유휴 슬롯에 먼저 기동
- 슬롯 직접 헬스체크와 `/version` 검증 후 Nginx upstream 전환
- `full` 모드에서만 `current` 전환 뒤 `frontend`, `market_api` 를 순차 재시작
- release activation 단계에서 managed systemd unit 파일도 `/etc/systemd/system` 으로 자동 동기화
- active 또는 enabled 상태였던 `my-api-drift-check.timer` 는 release activation 마지막에 자동 재시작
- 오래된 릴리스는 최근 5개만 유지하되, `current` 와 슬롯이 가리키는 release 는 보존

실행 예시:

```bash
cd /path/to/your/local/my-api
chmod +x scripts/deploy_from_server.sh scripts/server_prepare_release.sh scripts/remote_activate_release.sh
./scripts/deploy_from_server.sh your-ssh-host-alias origin/main full
```

배포가 끝나면 서버의 `/srv/my-api/current/.release-meta.json` 과 `https://admin.example.com/version` 이 같은 `git_sha`, `release_id`, `built_at` 를 보여야 한다.

서버 중심 배포 스크립트:

- [scripts/deploy_from_server.sh](../scripts/deploy_from_server.sh)
- [scripts/server_prepare_release.sh](../scripts/server_prepare_release.sh)
- [scripts/sync_n8n_config.sh](../scripts/sync_n8n_config.sh)

주의:

- 백엔드는 안정 주소 `127.0.0.1:9000` 뒤에서 슬롯 전환되므로 일반적인 배포에서는 짧은 재기동 없이 교체된다.
- 프런트엔드는 아직 단일 `3000` 인스턴스 구조라 `full` 배포 시 재시작이 남는다.
- 첫 dual-slot 도입 시에는 `full` 모드로 한 번 반영하고, 이후 백엔드 단독 변경은 `backend` 모드를 쓰는 편이 안전하다.

## 17. 드리프트 감시 타이머

설치 파일:

- [scripts/check_server_drift.sh](../scripts/check_server_drift.sh)
- [scripts/self_heal_market_api_proxy.sh](../scripts/self_heal_market_api_proxy.sh)
- [deploy/systemd/my-api-drift-check.service](../deploy/systemd/my-api-drift-check.service)
- [deploy/systemd/my-api-drift-check.timer](../deploy/systemd/my-api-drift-check.timer)

설치:

```bash
sudo cp /srv/my-api/current/deploy/systemd/my-api-drift-check.service /etc/systemd/system/
sudo cp /srv/my-api/current/deploy/systemd/my-api-drift-check.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now my-api-drift-check.timer
```

타이머는 10분마다 실행되며, 드리프트 점검 전에 `self_heal_market_api_proxy.sh` 를 먼저 호출한다.
이 스크립트는 아래 조건이 모두 맞을 때만 제한적으로 자동 복구를 시도한다.

- `market_api` 로컬 헬스체크는 정상
- 공개 `/internal/market-api/healthz` 경로는 비정상
- 활성 Nginx site 파일에 `/internal/market-api/` 프록시 블록이 없음

이 경우에만 프록시 블록을 삽입하고 `nginx -t` 후 reload 한다.
이미 블록이 있는데도 공개 경로가 비정상이면 자동 수정은 하지 않고 로그만 남긴다.

수동 점검:

```bash
/srv/my-api/current/scripts/self_heal_market_api_proxy.sh
/srv/my-api/current/scripts/check_server_drift.sh
./scripts/check_release_drift.sh your-ssh-host-alias
```

## 18. 추후 개선 작업

오늘 기준 운영 반영은 앱 코드 배포와 `n8n` 실운영 설정 수정이 분리되어 있다.
다음 개발 작업은 아래 문서를 기준으로 진행하면 된다.

- [docs/operational-followups.md](./operational-followups.md)

핵심 방향:

- 다음 단계는 프런트엔드까지 blue-green 전환 기반으로 확장하기
