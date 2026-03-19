# 시스템 개요

이 문서는 `my-api` 프로젝트를 처음 보는 사람이 "이 시스템이 무엇이고, 어디서 돌아가고, 어떻게 배포되고, 무엇으로 확인하는지"를 한 번에 이해하도록 만든 운영 개요 문서다.

## 1. 한 줄 요약

- `frontend`: Next.js 관리자 콘솔
- `backend`: FastAPI 관리자 API
- `market_api`: 시장 신호/브리핑 전용 별도 FastAPI
- `n8n`: 외부 알림/자동화 워크플로
- `nginx`: 외부 HTTPS 진입점 + 내부 안정 백엔드 주소
- `systemd`: 앱 프로세스 관리
- `SQLite`: 운영 데이터 저장소

## 2. 전체 구성

```mermaid
flowchart LR
    User[사용자 브라우저] --> HTTPS[HTTPS\nansan-jarvis.duckdns.org]
    HTTPS --> Nginx[Nginx]
    Nginx --> Frontend[Next.js Frontend\n127.0.0.1:3000]
    Frontend --> StableBackend[Stable Backend URL\n127.0.0.1:9000]
    StableBackend --> Blue[Backend Slot Blue\n127.0.0.1:8001]
    StableBackend --> Green[Backend Slot Green\n127.0.0.1:8002]
    Nginx --> Market[market_api\n127.0.0.1:8100]
    Blue --> SQLite[(SQLite\n/srv/my-api/data/app.db)]
    Green --> SQLite
    n8n[n8n Container] --> HTTPS
    n8n --> Market
```

핵심은 백엔드가 더 이상 단일 `8000` 포트를 직접 보지 않는다는 점이다.
모든 내부 호출은 `127.0.0.1:9000` 으로 모이고, 이 주소가 현재 활성 슬롯인 `blue` 또는 `green` 으로 연결된다.

## 3. 요청 흐름

### 3-1. 관리자 화면 요청

```mermaid
sequenceDiagram
    participant B as Browser
    participant N as Nginx
    participant F as Frontend 3000
    participant S as Stable Backend 9000
    participant A as Active Backend Slot
    participant D as SQLite

    B->>N: GET /login, /dashboard, /apis
    N->>F: 프론트 페이지 전달
    F->>S: /api/v1/... 호출
    S->>A: 활성 슬롯으로 프록시
    A->>D: 데이터 읽기/쓰기
    D-->>A: 결과 반환
    A-->>S: JSON 응답
    S-->>F: 내부 API 응답
    F-->>N: 렌더링 결과
    N-->>B: HTML/JSON 응답
```

### 3-2. n8n 운영 호출

```mermaid
sequenceDiagram
    participant N8N as n8n
    participant NG as Public Nginx
    participant FE as Frontend Route Handler
    participant SB as Stable Backend 9000
    participant BE as Active Backend Slot

    N8N->>NG: HTTPS /api/proxy/jobs/ops-check
    NG->>FE: Next.js route handler
    FE->>SB: backend /api/v1/jobs/ops-check
    SB->>BE: 활성 슬롯 전달
    BE-->>SB: 결과 반환
    SB-->>FE: JSON 응답
    FE-->>NG: 응답 전달
    NG-->>N8N: 최종 응답
```

## 4. 배포 구조

### 4-1. 디렉터리 역할

- `/srv/my-api/repo`
  - 서버가 `git fetch` 하는 읽기 전용 저장소 미러
- `/srv/my-api/releases/<release_id>`
  - 각 배포 단위의 실제 릴리즈 디렉터리
- `/srv/my-api/current`
  - 현재 활성 릴리즈 심볼릭 링크
- `/srv/my-api/slots/backend-blue`
  - `blue` 슬롯이 실행 중인 릴리즈를 가리키는 심볼릭 링크
- `/srv/my-api/slots/backend-green`
  - `green` 슬롯이 실행 중인 릴리즈를 가리키는 심볼릭 링크
- `/srv/my-api/state/backend-active-slot`
  - 현재 활성 슬롯 이름

### 4-2. 배포 흐름

```mermaid
flowchart TD
    Start[deploy_from_server.sh] --> Fetch[서버 repo fetch]
    Fetch --> Release[새 release 생성]
    Release --> Meta[.release-meta.json 기록]
    Meta --> SyncN8N[n8n compose 동기화]
    SyncN8N --> Pick[유휴 backend 슬롯 선택]
    Pick --> Boot[유휴 슬롯 기동]
    Boot --> VerifySlot[슬롯 healthz/version 검증]
    VerifySlot --> Switch[Nginx upstream 전환]
    Switch --> VerifyStable[9000/version, public healthz 재검증]
    VerifyStable --> Full{mode == full}
    Full -- yes --> RestartOthers[frontend, market_api 재시작]
    Full -- no --> Done[배포 완료]
    RestartOthers --> VerifyOthers[login, market_api, n8n 검증]
    VerifyOthers --> Done
```

배포 실패 시 핵심 복구는 "이전 슬롯으로 Nginx upstream 되돌리기"다.  
즉 서비스 프로세스 전체를 뒤집는 것이 아니라, 트래픽 방향을 이전 슬롯으로 되돌린다.

## 5. 현재 운영에서 중요한 주소

### 외부 확인

- `https://ansan-jarvis.duckdns.org/login`
- `https://ansan-jarvis.duckdns.org/healthz`
- `https://ansan-jarvis.duckdns.org/version`

### 내부 확인

- `http://127.0.0.1:3000`
- `http://127.0.0.1:9000/healthz`
- `http://127.0.0.1:9000/version`
- `http://127.0.0.1:8100/healthz`

### 슬롯 직접 확인

- `http://127.0.0.1:8001/version`
- `http://127.0.0.1:8002/version`

## 6. 현재 운영 확인 명령

### 상태 한 번에 보기

```bash
./scripts/check_release_drift.sh oci-ubuntu
```

정상이라면 아래가 서로 맞아야 한다.

- `local_head`
- `origin_main`
- `server_git_sha`
- `backend_active_slot`
- `backend_release_slot`
- `backend_version_slot`
- `backend_upstream_target`

### 서버에서 직접 보기

```bash
ssh oci-ubuntu 'readlink -f /srv/my-api/current'
ssh oci-ubuntu 'cat /srv/my-api/state/backend-active-slot'
ssh oci-ubuntu 'curl -fsS http://127.0.0.1:9000/version'
ssh oci-ubuntu 'curl -fsS https://ansan-jarvis.duckdns.org/version'
ssh oci-ubuntu 'sudo systemctl status personal-api-admin-backend@blue --no-pager -l'
ssh oci-ubuntu 'sudo systemctl status personal-api-admin-backend@green --no-pager -l'
```

### 슬롯 전환이 실제 되는지 보기

```bash
./scripts/deploy_from_server.sh oci-ubuntu origin/main backend
./scripts/check_release_drift.sh oci-ubuntu
```

이 명령을 실행하면 활성 슬롯이 `blue -> green` 또는 `green -> blue`로 바뀌어야 한다.

## 7. 어떤 파일이 무엇을 담당하는가

### 앱

- `backend/app/main.py`
  - `/healthz`, `/version` 제공
- `frontend/lib/server-api.ts`
  - 프런트가 내부적으로 백엔드를 호출하는 공통 경로
- `services/market_api/`
  - 시장 신호/브리핑 전용 별도 서비스

### 배포

- `scripts/deploy_from_server.sh`
  - 로컬에서 SSH로 서버 배포 트리거
- `scripts/server_prepare_release.sh`
  - 서버에서 `fetch -> release 생성 -> n8n sync -> activate`
- `scripts/remote_activate_release.sh`
  - 슬롯 기동, 검증, upstream 전환, 후속 서비스 검증

### 운영 판별

- `scripts/check_server_drift.sh`
  - 서버 내부 기준 드리프트 점검
- `scripts/check_release_drift.sh`
  - 로컬/원격/실행 중 상태 비교
- `deploy/systemd/personal-api-admin-backend@.service`
  - backend dual-slot systemd 템플릿
- `deploy/nginx/site.conf.example`
  - 외부 HTTPS + 내부 `9000` 안정 주소

## 8. 지금 남아 있는 한계

- 백엔드는 dual-slot 이지만 프런트엔드는 아직 단일 `3000` 인스턴스다.
- `full` 배포에서는 프런트와 `market_api` 재시작이 남는다.
- SQLite를 공유하므로 파괴적 스키마 변경은 여전히 별도 주의가 필요하다.

즉 현재 구조는 "백엔드 우선 무중단에 가까운 배포"까지는 정리됐고, 다음 확장 대상은 프런트엔드 dual-slot 이다.
