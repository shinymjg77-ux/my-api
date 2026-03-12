# my-api

FastAPI 백엔드와 Next.js 관리자 프론트엔드로 구성된 개인 운영용 API 관리 콘솔입니다.  
API 엔드포인트, DB 연결, 운영 로그, 관리자 계정 보안 설정을 한 화면에서 다룰 수 있게 구성했습니다.

## 구성

- `backend/`: FastAPI, SQLAlchemy, SQLite/PostgreSQL 지원
- `frontend/`: Next.js App Router, Tailwind 기반 관리자 UI
- `deploy/`: Nginx, systemd, cron, logrotate 예시 설정
- `scripts/`: 배포, 백업, 알림, 백업 업로드 스크립트
- `docs/`: OCI Ubuntu 배포 문서

## 주요 기능

- 관리자 로그인과 세션 쿠키 인증
- API 엔드포인트 등록, 수정, 활성화 관리
- DB 연결 정보 저장과 즉시 연결 테스트
- 운영 로그 조회
- 관리자 비밀번호 변경 UI
- SQLite 백업, 원격 업로드 훅, 장애 알림 훅

## 로컬 실행

### 1. 백엔드

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example .env
```

`.env`에서 최소한 아래 값을 실제 값으로 바꿔야 합니다.

- `SECRET_KEY`
- `ENCRYPTION_KEY`
- `BOOTSTRAP_ADMIN_PASSWORD`

백엔드 실행:

```bash
cd backend
../.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 2. 프론트엔드

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

기본 접속:

- 프론트엔드: `http://127.0.0.1:3000`
- 백엔드 헬스체크: `http://127.0.0.1:8000/healthz`

## 운영 배포

OCI Ubuntu 서버 배포 절차와 운영 자동화 문서는 아래를 참고하면 됩니다.

- [docs/deploy-oci-ubuntu.md](docs/deploy-oci-ubuntu.md)

## GitHub 업로드 전 주의

아래 파일은 커밋하지 않도록 `.gitignore`에 포함했습니다.

- `.env`
- `.venv/`
- `frontend/node_modules/`
- `frontend/.next/`
- `data/`
- `.omx/`

즉, 실제 비밀번호, SQLite DB 파일, 빌드 산출물은 저장소에 올라가지 않도록 정리돼 있습니다.
