# my-api

FastAPI 백엔드와 Next.js 관리자 프론트엔드로 구성된 개인 운영용 API 관리 콘솔입니다.  
운영 콘솔은 API 브라우저, DB 연결, 운영 로그, 관리자 계정 보안 설정을 관리하고, 시장 신호 계산용 API는 같은 저장소 안의 별도 서비스 경로로 분리해 둡니다.

## 구성

- `backend/`: FastAPI 기반 관리자 백엔드
- `frontend/`: Next.js App Router, Tailwind 기반 관리자 UI
- `services/market_api/`: QLD RSI / 미국 지수 브리핑 전용 독립 FastAPI 서비스
- `deploy/`: Nginx, systemd, cron, logrotate 예시 설정
- `scripts/`: 배포, 백업, 알림, 백업 업로드 스크립트
- `docs/`: OCI Ubuntu 배포 문서

## 주요 기능

- 관리자 로그인과 세션 쿠키 인증
- API 계층 트리 탐색과 상세 패널 기반 메타데이터 수정
- 기본 운영 API 자동 등록과 그룹 경로(`group_path`) 기반 계층화
- DB 연결 정보 저장과 즉시 연결 테스트
- 운영 로그 조회
- 관리자 비밀번호 변경 UI
- SQLite 백업, 원격 업로드 훅, 장애 알림 훅
- 시장 신호/브리핑은 `services/market_api`에서 별도 제공

## API 브라우저

`/apis` 화면은 새 API를 직접 추가하는 등록 폼이 아니라, 운영 대상 API를 계층 구조로 탐색하고 상세 메타데이터를 수정하는 화면입니다.

- 왼쪽: `group_path` 기준 폴더 트리
- 오른쪽: 선택한 API의 이름, 그룹 경로, URL, 메서드, 설명, 활성 상태, 생성/수정 시각
- 검색: API 이름과 그룹 경로 둘 다 검색

백엔드 시작 시 `managed_apis`에 기본 API가 자동 등록됩니다. 현재 기본 항목은 아래 범주를 포함합니다.

- `platform/admin`
- `platform/admin/dashboard`
- `market/health`
- `market/briefings`
- `market/signals`
- `market/status`

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
- 필요하면 `MANAGED_API_ADMIN_BASE_URL`
- 필요하면 `MANAGED_API_MARKET_BASE_URL`

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

### 3. 시장 신호 서비스

```bash
cd services/market_api
../../.venv/bin/pip install -r requirements.txt
cp .env.example .env
../../.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8100
```

기본 접속:

- 시장 신호 API 헬스체크: `http://127.0.0.1:8100/healthz`

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
