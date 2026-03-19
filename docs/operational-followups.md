# 운영 후속 개발 메모

이 문서는 오늘 운영 대응 이후, 추후 구현해야 할 운영 자동화 작업을 정리한 메모다.

## 1. 버전 확인 자동화

상태:

- 1차 구현 완료
- 배포 시 `.release-meta.json` 생성
- 백엔드 `/version` 추가
- 로컬 드리프트 점검 스크립트 추가

현재 문제:

- 로컬 Git HEAD
- `origin/main`
- 서버 `/srv/my-api/current`
- `/opt/n8n/docker-compose.yml`

이 네 가지가 쉽게 같은 버전인지 보이지 않는다.

개발 방향:

- 배포 시 git SHA, release id, built_at 을 `/srv/my-api/current/.release-meta.json` 에 기록
- 백엔드에서 `/healthz` 확장 또는 `/version` 엔드포인트 추가
- 응답에 `git_sha`, `release_id`, `built_at` 포함
- 로컬 점검 스크립트가 아래를 한 번에 비교
- 로컬 HEAD
- `origin/main`
- 서버 current release metadata
- 실행 중 `n8n` compose 설정 해시 또는 마지막 반영 시각

완료 기준:

- 한 명령으로 “로컬/원격/실행 중 버전 동일 여부”를 확인할 수 있어야 함
- 버전 불일치가 있으면 어느 계층이 뒤처졌는지 바로 보여야 함

## 2. n8n 운영 설정 저장소 관리

상태:

- 1차 구현 완료
- 운영용 compose canonical 파일 추가
- 서버 배포 시 `/opt/n8n/docker-compose.yml` 동기화
- `docker compose config` 와 `docker inspect` 기반 검증 추가

현재 문제:

- 앱 코드는 `/srv/my-api/releases/...` 로 배포됨
- `n8n` 실운영 설정은 `/opt/n8n/docker-compose.yml` 에 따로 있음
- 그래서 코드 배포와 `n8n` 변경이 쉽게 분리됨

개발 방향:

- `n8n` 운영용 compose 또는 env 파일을 저장소 관리 대상으로 편입
- 서버 배포 스크립트가 앱 코드뿐 아니라 `n8n` 설정도 함께 동기화
- 배포 후 `docker compose config` 와 `docker inspect` 로 DNS/환경변수 검증 자동화

완료 기준:

- `n8n` 운영 설정 변경이 서버 수기 수정 없이 Git 커밋과 배포로 재현 가능해야 함
- 앱 배포와 `n8n` 운영 설정 반영 상태를 같은 절차에서 검증할 수 있어야 함

## 3. 무중단에 가까운 배포

상태:

- 2차 구현 완료
- 백엔드 우선 dual-slot 전환 적용
- 안정 내부 주소 `127.0.0.1:9000` 추가
- 활성 슬롯 상태와 Nginx upstream 드리프트 감시 추가

현재 상태:

- 백엔드는 `blue`, `green` 슬롯 중 유휴 슬롯에 새 release를 먼저 기동함
- 검증 통과 후 Nginx upstream 만 새 슬롯으로 전환함
- 프런트엔드는 아직 단일 `3000` 인스턴스 구조를 유지함

개발 방향:

- 프런트엔드도 같은 방식으로 2포트 또는 2서비스 구조 검토
- 현재 `full` 배포는 백엔드 슬롯 전환 뒤 프런트/market_api를 순차 재시작함
- 다음 단계는 프런트엔드까지 dual-slot 또는 blue-green으로 확장하는 것

완료 기준:

- 백엔드 배포 중 `healthz` 가 계속 응답해야 함
- 실패 시 이전 슬롯으로 즉시 upstream 롤백 가능해야 함
- `/version`, 활성 슬롯 상태 파일, Nginx upstream 대상이 서로 일치해야 함

## 4. 배포 후 자동 검증

상태:

- 1차 구현 완료
- 배포 스크립트에서 backend/frontend/market_api/n8n 검증 수행

개발 방향:

- 배포 스크립트 끝에서 아래 검증을 자동 실행
- backend `healthz`
- frontend `/login`
- `market_api /healthz`
- `n8n` 컨테이너 DNS 조회
- `n8n` 컨테이너 내부에서 `ops-check` 호출

완료 기준:

- 배포 성공/실패를 사람 눈으로 확인하지 않아도 로그와 종료 코드로 판별 가능해야 함

## 5. 운영 알림 보강

상태:

- 1차 구현 완료
- 배포 실패 알림 본문에 릴리스 메타와 실패 단계 포함
- n8n DNS 실패를 별도 분류로 알림

개발 방향:

- 버전 드리프트 감지 시 텔레그램 또는 OpenClaw 알림
- 배포 실패 시 현재 릴리스/직전 릴리스/헬스체크 결과 함께 전송
- `n8n` DNS 실패도 “일시 DNS 장애”로 분류해서 운영 메시지를 더 읽기 쉽게 개선

완료 기준:

- 장애 원인이 앱, 인증, DNS, 배포 중 어디인지 알림 본문만 보고 구분 가능해야 함
