# OCI Ubuntu 배포 절차

이 문서는 이 프로젝트를 `OCI Ubuntu` 서버에 배포하는 실제 절차를 정리한 문서다. 예시 도메인은 `admin.example.com` 이고, 구성은 아래와 같다.

- `Nginx`: 외부 진입점, HTTPS 종료, 리버스 프록시
- `FastAPI`: `127.0.0.1:8000`
- `Next.js`: `127.0.0.1:3000`
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
```

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
PORT=3000
HOSTNAME=127.0.0.1
BACKEND_BASE_URL=http://127.0.0.1:8000
BACKEND_API_PREFIX=/api/v1
```

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
cd /srv/my-api/frontend
set -a
source /etc/my-api/frontend.env
set +a
npm run start -- --hostname 127.0.0.1 --port 3000
```

다른 터미널에서 확인:

```bash
curl -I http://127.0.0.1:3000/login
```

## 7. systemd 등록

예시 유닛 파일은 저장소의 아래 파일을 사용한다.

- [deploy/systemd/personal-api-admin-backend.service](../deploy/systemd/personal-api-admin-backend.service)
- [deploy/systemd/personal-api-admin-frontend.service](../deploy/systemd/personal-api-admin-frontend.service)

서버에 복사:

```bash
sudo cp /srv/my-api/deploy/systemd/personal-api-admin-backend.service /etc/systemd/system/
sudo cp /srv/my-api/deploy/systemd/personal-api-admin-frontend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable personal-api-admin-backend
sudo systemctl enable personal-api-admin-frontend
sudo systemctl start personal-api-admin-backend
sudo systemctl start personal-api-admin-frontend
```

상태 확인:

```bash
sudo systemctl status personal-api-admin-backend --no-pager
sudo systemctl status personal-api-admin-frontend --no-pager
```

로그 확인:

```bash
sudo journalctl -u personal-api-admin-backend -n 100 --no-pager
sudo journalctl -u personal-api-admin-frontend -n 100 --no-pager
```

## 8. Nginx 설정

예시 설정 파일은 [deploy/nginx/site.conf.example](../deploy/nginx/site.conf.example) 이다.

서버에 복사:

```bash
sudo mkdir -p /var/www/certbot
sudo cp /srv/my-api/deploy/nginx/site.conf.example /etc/nginx/sites-available/admin.example.com
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
```

브라우저 확인 항목:

- `https://admin.example.com/login` 접속
- 관리자 로그인 성공
- `/dashboard` 진입 성공
- API 등록/수정 가능
- DB 연결 테스트 가능
- 로그 페이지 필터 조회 가능

## 11. 업데이트 배포 절차

코드 업데이트 시에는 아래 순서가 안전하다.

```bash
cd /srv/my-api
git pull origin main

source /srv/my-api/.venv/bin/activate
pip install -r /srv/my-api/backend/requirements.txt

cd /srv/my-api/frontend
npm ci
set -a
source /etc/my-api/frontend.env
set +a
npm run build

sudo systemctl restart personal-api-admin-backend
sudo systemctl restart personal-api-admin-frontend
sudo systemctl reload nginx
```

## 12. 실패 가능 지점

- DNS 가 서버 공인 IP를 가리키지 않으면 `certbot` 발급이 실패한다.
- OCI 보안 규칙에서 `80`, `443` 을 열지 않으면 외부 접속이 되지 않는다.
- 이 프론트엔드는 `/api/auth/*`, `/api/proxy/*` 를 Next.js route handler 로 사용하므로, Nginx 에서 `/api/` 를 FastAPI 로 직접 프록시하면 로그인과 프록시 호출이 깨진다.
- `COOKIE_SECURE=true` 인데 HTTPS 없이 직접 접속하면 로그인 쿠키가 정상 동작하지 않는다.
- `CORS_ORIGINS` 값이 JSON 배열 형식이 아니면 백엔드가 시작하지 않는다.
- `backend.env` 와 `frontend.env` 권한이 너무 넓으면 운영 보안상 좋지 않다.
- SQLite 파일 경로의 상위 디렉터리가 없거나 권한이 없으면 백엔드 초기화가 실패한다.

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

- 새 코드 업로드: `/srv/my-api/releases/<timestamp>`
- 사전 빌드 완료 후 `current` 심볼릭 링크 전환
- `backend` 헬스체크 후 `frontend` 재시작
- 오래된 릴리스는 최근 5개만 유지

실행 예시:

```bash
cd /path/to/your/local/my-api
chmod +x scripts/deploy_release.sh scripts/remote_activate_release.sh
./scripts/deploy_release.sh your-ssh-host-alias
```

주의:

- 이 방식은 단일 `uvicorn` 프로세스를 재시작하므로 백엔드 전환 시 수초 수준의 짧은 끊김은 남는다.
- 프런트 빌드와 의존성 설치는 전환 전에 끝내므로 체감 중단은 최소화한다.
