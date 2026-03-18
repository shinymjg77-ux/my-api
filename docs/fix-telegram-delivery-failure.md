# 텔레그램 전송 실패 해결하기

이 문서는 `n8n`이 텔레그램을 보내려다가 실패했을 때,
왜 그런 일이 생겼는지 아주 쉽게 설명하고,
어디를 보고 어떻게 고치면 되는지 순서대로 알려준다.

이번에 실제로 생긴 문제는 이것이었다.

- `market_api`는 서버 안에서 잘 켜져 있었다.
- `n8n`도 잘 켜져 있었지만 Docker 컨테이너 안에서 돌고 있었다.
- 그런데 `n8n`이 `127.0.0.1:8100`으로 API를 부르려다가 실패했다.

## 1. 무슨 일이 있었나

처음에는 워크플로우가 이렇게 생각하고 있었다.

- `미국 증시 브리핑 API는 127.0.0.1:8100에 있다`
- `QLD RSI 체크 API도 127.0.0.1:8100에 있다`

겉으로 보면 맞는 말처럼 보인다.
서버에서 직접 보면 정말 `market_api`는 `127.0.0.1:8100`에서 잘 돌고 있기 때문이다.

그런데 `n8n`은 서버 본체 안이 아니라 **Docker 컨테이너 안**에 있었다.
그래서 `n8n`이 말하는 `127.0.0.1`은 서버가 아니라 **컨테이너 자기 자신**이었다.

그래서 결과는 이렇게 됐다.

- 서버는 `market_api`가 잘 살아 있음
- `n8n`은 엉뚱한 자기 방 문을 두드림
- 문이 없으니 연결 실패
- 텔레그램으로 실패 메시지가 옴

## 2. `127.0.0.1`이 왜 문제였나

아주 쉽게 비유하면 이렇다.

- 서버 본체 = 큰 집
- Docker 컨테이너 = 큰 집 안의 작은 방
- `127.0.0.1` = “내 방 안”

서버 본체에서 `127.0.0.1`이라고 하면 “큰 집 안의 나 자신”을 뜻한다.
하지만 Docker 컨테이너 안에서 `127.0.0.1`이라고 하면 “그 작은 방 안의 나 자신”을 뜻한다.

즉, 둘 다 같은 숫자를 써도 **같은 장소가 아니다**.

이번 문제를 한 줄로 말하면 이렇다.

> `n8n`은 작은 방 안에서 `127.0.0.1`을 보고 있었고, `market_api`는 큰 집 안에 있었기 때문에 서로 못 만났다.

## 3. 어디를 보면 문제를 찾을 수 있나

### 3-1. 텔레그램 실패 메시지 보기

가장 먼저 텔레그램에 이런 식의 메시지가 왔다.

```text
market_api 브리핑 호출 실패
connect ECONNREFUSED 127.0.0.1:8100
```

이 뜻은 간단하다.

- `connect` = 연결을 시도했다
- `ECONNREFUSED` = 그런데 상대가 안 받았다
- `127.0.0.1:8100` = 여기로 갔다가 실패했다

즉, 문제는 “텔레그램”이 아니라 “그 전에 API 연결이 안 됐다”는 뜻이다.

### 3-2. `market_api`가 정말 살아 있는지 보기

서버에서 직접 이 명령을 치면 된다.

```bash
curl http://127.0.0.1:8100/healthz
```

이 명령은 `market_api`에게 “살아 있어?” 하고 물어보는 것이다.

정상이라면 이렇게 나온다.

```json
{"status":"ok"}
```

이렇게 나오면 `market_api` 자체는 죽은 게 아니다.
즉, 문제는 프로그램이 꺼진 것이 아니라 **가는 길**이 잘못된 것이다.

### 3-3. `n8n` 안에서 같은 길이 되는지 보기

이번 문제는 `n8n`이 Docker 안에 있었기 때문에 생겼다.
그래서 “서버에서 되는지”만 보면 안 되고,
“컨테이너 안에서도 되는지”를 봐야 한다.

예를 들면 이런 식으로 확인할 수 있다.

```bash
docker exec n8n node -e '(async () => { try { const res = await fetch("https://ansan-jarvis.duckdns.org/internal/market-api/healthz"); console.log(res.status, await res.text()); } catch (error) { console.log(error.message); } })()'
```

이 명령은 `n8n` 컨테이너 안에서 직접 길을 따라가 보게 하는 것이다.

## 4. 처음 시도했던 방법

처음에는 이렇게 생각할 수 있다.

### 방법 1. 서버 private IP로 붙여 보기

예:

```text
http://10.0.0.68:8100
```

또는 Docker 브리지 주소를 써 보는 방법도 있다.

예:

```text
http://172.18.0.1:8100
```

이 방법이 되는 서버도 있다.
하지만 이번 서버에서는 Docker 네트워크 조건 때문에 컨테이너에서 이 길로도 잘 못 갔다.

즉, “숫자 주소를 바꿔 붙여 보면 되겠지”가 항상 정답은 아니다.

## 5. 이번에 최종으로 고친 방법

이번에는 가장 안정적인 길을 만들었다.

### 핵심 생각

- `market_api`는 계속 서버 안 `127.0.0.1:8100`에 둔다
- `Nginx`가 중간 문지기 역할을 한다
- `n8n`은 `Nginx`가 열어 둔 HTTPS 주소로만 들어간다

이렇게 바꾸면 좋은 점이 있다.

- Docker가 서버의 loopback을 직접 못 봐도 괜찮다
- `n8n`은 그냥 평범한 웹 주소를 부르면 된다
- 실제 운영 경로가 한 군데로 정리된다

### 바뀐 구조

예전:

```text
n8n -> http://127.0.0.1:8100
```

이제:

```text
n8n -> https://ansan-jarvis.duckdns.org/internal/market-api/...
        -> Nginx
        -> http://127.0.0.1:8100
```

## 6. 실제로 무엇을 바꿨나

### 6-1. `market_api`는 그대로 둠

`market_api`는 서버 안에서 계속 이렇게 실행한다.

```text
127.0.0.1:8100
```

즉, 프로그램 자체는 옮기지 않았다.
대신 **가는 길만 바꿨다**.

### 6-2. Nginx에 새 길을 만듦

Nginx 설정에 이런 경로를 추가했다.

```nginx
location ^~ /internal/market-api/ {
    proxy_pass http://127.0.0.1:8100/;
    proxy_read_timeout 30s;
}
```

이 뜻은 이렇다.

- 누가 `/internal/market-api/`로 오면
- Nginx가 그 요청을
- 서버 안의 `127.0.0.1:8100`으로 대신 전달한다

즉, Nginx가 “안내 데스크” 역할을 하는 것이다.

### 6-3. `n8n` 워크플로우 주소를 바꿈

브리핑 API:

```text
https://ansan-jarvis.duckdns.org/internal/market-api/api/v1/briefings/morning
```

RSI 체크 API:

```text
https://ansan-jarvis.duckdns.org/internal/market-api/api/v1/jobs/rsi-check
```

이제 `n8n`은 직접 `127.0.0.1`로 가지 않고,
항상 Nginx를 통해 들어간다.

## 7. 고친 뒤 어떻게 확인하나

### 7-1. `market_api`가 살아 있는지 확인

```bash
curl http://127.0.0.1:8100/healthz
```

뜻:
서버 안의 `market_api`가 살아 있는지 확인

정상 결과:

```json
{"status":"ok"}
```

### 7-2. Nginx 프록시 길이 열렸는지 확인

```bash
curl https://ansan-jarvis.duckdns.org/internal/market-api/healthz
```

뜻:
Nginx를 거쳐서도 `market_api`에 닿는지 확인

정상 결과:

```json
{"status":"ok"}
```

### 7-3. `n8n`이 실제 API를 부를 수 있는지 확인

브리핑 API:

```bash
docker exec n8n node -e '(async () => { const res = await fetch("https://ansan-jarvis.duckdns.org/internal/market-api/api/v1/briefings/morning", { headers: { "X-Job-Secret": "여기에_실제_시크릿" } }); console.log(res.status, await res.text()); })()'
```

RSI 체크 API:

```bash
docker exec n8n node -e '(async () => { const res = await fetch("https://ansan-jarvis.duckdns.org/internal/market-api/api/v1/jobs/rsi-check", { method: "POST", headers: { "X-Job-Secret": "여기에_실제_시크릿" } }); console.log(res.status, await res.text()); })()'
```

뜻:
정말로 `n8n`이 있는 자리에서 이 길이 되는지 확인

### 7-4. 마지막으로 워크플로우 실행

이제 `My workflow`를 수동 실행해 본다.

정상이라면:

- 미국 증시 브리핑 텔레그램 1건이 온다
- `QLD` 상태가 바뀌지 않았다면 RSI 텔레그램은 안 온다

이번 실제 응답 기준으로는 `changed: false`였기 때문에,
정상이라면 **브리핑 메시지 1건만 오는 것**이 맞다.

## 8. 앞으로 같은 실수를 막는 법

이 규칙만 기억하면 된다.

### 규칙 1. Docker 안의 `127.0.0.1`은 서버의 `127.0.0.1`이 아니다

이건 가장 중요하다.

`n8n`이 Docker 안에 있다면,
워크플로우에 `127.0.0.1` 주소를 넣을 때는 꼭 한 번 더 생각해야 한다.

### 규칙 2. “서버에서 curl이 된다”와 “컨테이너에서도 된다”는 다르다

서버에서 되는 것만 보고 끝내면 안 된다.
Docker 안에서도 같은 길이 되는지 꼭 확인해야 한다.

### 규칙 3. 내부 서비스는 Nginx 프록시 경로로 묶어 두면 편하다

직접 IP를 여기저기 넣기보다,
Nginx가 정해 둔 길 하나로 부르게 하면 운영이 단순해진다.

## 9. 한 줄 요약

`n8n`이 Docker 안에 있으면 `127.0.0.1`은 서버 자신이 아니라 컨테이너 자신이다.  
그래서 이번 문제는 `market_api`가 죽은 게 아니라, `n8n`이 잘못된 문을 두드린 것이었다.  
해결은 `Nginx`를 통해 올바른 문을 만들어 주는 것이었다.
