# 웹 파트 설계 — 중앙 관리 서버 + 대시보드 (v1.0)

> 2026-07-08 · 담당: 준표(`jp`) · 대상: `server/` (FastAPI 백엔드 + Vue 3 대시보드)
> 전제: LoRa·e-Paper 하드웨어 미도착 — **가상 노드 시뮬레이터로 전체 기능을 먼저 구현**하고, 하드웨어 도착 시 transport 어댑터만 교체한다.

## 1. 목적·범위

ARCHITECTURE.md의 중앙 관리 서버(§3.1)를 하드웨어 없이 완성한다. 범위:

- 게시물 작성/수정/삭제, 템플릿 4종, QR URL 관리
- 노드별·일괄 배포(즉시/예약), 노드 상태 모니터링
- 통계 시각화(성공률·배터리·종이 절감량)
- e-Paper 가상 미리보기(296×128 렌더)
- 가상 게이트웨이·노드 시뮬레이터 (PROTOCOL.md v0.1 구현 — IMG_FRAG 제외)
- 단일 관리자 비밀번호 인증

제외(스트레치): 이미지 분할 전송(IMG_FRAG), 브로드캐스트 최적화, 반복 예약, 자동 재배포, 프론트 테스트 자동화, SQLite 시계열 이력.

## 2. 확정 결정 사항

| 항목 | 결정 | 근거 |
|------|------|------|
| 하드웨어 부재 대응 | **가상 노드 시뮬레이터** — 프로토콜 계층 완전 구현 + transport 인터페이스 분리 | 하드웨어 전환 리스크 최소화, 펌웨어 팀 레퍼런스 확보 |
| 시뮬레이터 실행 모델 | FastAPI 프로세스 내 asyncio 태스크 (인프로세스) | 실행 단순(프로세스 1개), 데모 셋업 실수 방지 |
| transport 절단 수준 | **바이트 스트림** (`read/write bytes`) | COBS 프레이밍까지 지금 검증 — 실모드와 코드 경로 동일 |
| 프론트 동기화 | 폴링 (노드 5초, 배포 진행 중 1초) | 배포가 수 초 내 완료 → 충분한 실시간감, 최소 복잡도 |
| e-Paper 미리보기 | 포함 — 296×128 캔버스 렌더 | 하드웨어 없는 데모의 핵심 장치, 노드 펌웨어 렌더 레퍼런스 |
| 인증 | 단일 관리자 비밀번호(.env) + Bearer 토큰 | 완성도 인상 + 낮은 구현 비용 |
| 프론트 언어 | **TypeScript** | 사용자 결정 |
| UI 라이브러리 | Element Plus + Chart.js | 관리자 대시보드 검증된 조합, 개발 속도 |
| 저장소 | **메모리 상태 + JSON 스냅샷** (DB 없음). SQLite 시계열 이력은 스트레치 | `jp` 브랜치 팀 결정(2026-06-30 c59e25a) 준수, MVP 최소 복잡도 |

## 3. 전체 아키텍처

`.env`의 `TRANSPORT_MODE=virtual|serial` 하나로 모드 전환. 상위 계층(서비스·프로토콜)은 모드를 모른다.

```
[Vue 3 대시보드] ─HTTP(axios, 폴링)─ [FastAPI]
                                       ├ routers → services (deploy/node/schedule/stats)
                                       ├ protocol  : 패킷 codec · CRC16 · COBS · framing · stop-and-wait link
                                       └ transport : Transport 추상 (async read/write bytes)
                                           ├ VirtualTransport (인메모리 duplex 큐)   ← 지금
                                           │    └ [가상 게이트웨이 0x00] ─가상 채널(손실·지연)─ [가상 노드 0x01, 0x02]
                                           └ SerialTransport (pyserial, 921600bps)  ← 하드웨어 도착 후
```

- 가상 모드: FastAPI lifespan에서 가상 게이트웨이 + 노드 2개 + 채널을 asyncio 태스크로 기동.
- 데모 실행: `vite build` 산출물을 FastAPI가 정적 서빙 → **노트북에서 프로세스 1개**로 전체 시연.
- 개발 실행: Vite dev(5173) → FastAPI(8000) 프록시.

## 4. 디렉토리 구조

```
server/
├── backend/
│   ├── app/
│   │   ├── main.py            # 앱 팩토리, lifespan(시뮬레이터·APScheduler 기동), 정적 서빙
│   │   ├── config.py          # .env: TRANSPORT_MODE, SERIAL_PORT, ADMIN_PASSWORD, 폴링 주기
│   │   ├── store.py           # 메모리 상태(AppState) + JSON 스냅샷 영속 (§5.3)
│   │   ├── models.py          # Pydantic 도메인 모델 (Post·Node·Deployment·Schedule)
│   │   ├── schemas.py         # API 요청/응답 스키마
│   │   ├── auth.py            # 비밀번호 검증 → 토큰 발급, Bearer 의존성
│   │   ├── routers/           # auth · posts · nodes · deployments · schedules · stats · sim
│   │   ├── services/
│   │   │   ├── deploy_service.py    # 게시물 → 패킷 시퀀스 → 노드별 전송·결과 기록
│   │   │   ├── node_service.py      # STATUS_REQ 폴링, online/offline 판정, 로그 적재
│   │   │   ├── schedule_service.py  # APScheduler 래핑 (일회성 예약)
│   │   │   └── stats_service.py     # 성공률·종이 절감·배터리 시계열 집계
│   │   ├── protocol/          # ★ PROTOCOL.md v0.1 레퍼런스 구현 (펌웨어 지시서 기반)
│   │   │   ├── packet.py      # 8B 헤더+PAYLOAD+CRC16 codec, TYPE 상수, 페이로드 빌더
│   │   │   ├── crc16.py       # CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF)
│   │   │   ├── cobs.py        # COBS encode/decode
│   │   │   ├── framing.py     # 바이트 스트림 ↔ 프레임(0x00 구분) 스트림
│   │   │   ├── link.py        # stop-and-wait: SEQ 발급·롤오버, T_ack=1500ms, 3회 재시도
│   │   │   └── templates.py   # 템플릿 4종 필드 정의(좌표·폰트·최대길이) — 단일 소스
│   │   ├── transport/
│   │   │   ├── base.py        # Transport 추상
│   │   │   ├── virtual.py     # 인메모리 duplex 큐
│   │   │   └── serial_port.py # pyserial 어댑터 (실모드)
│   │   └── simulator/
│   │       ├── gateway.py     # COBS 프레임 ↔ LoRa 패킷 중계 (게이트웨이 펌웨어와 동일 역할)
│   │       ├── node.py        # 노드 상태머신 (§5.2)
│   │       └── channel.py     # 손실률·전파지연 주입
│   ├── tests/                 # pytest (§8)
│   ├── requirements.txt
│   └── .env.example
└── frontend/                  # Vue 3 + Vite + TypeScript + Pinia + Element Plus
    └── src/
        ├── api/               # axios 클라이언트 (토큰 인터셉터, 401 처리)
        ├── stores/            # auth · nodes · posts · deployments · stats
        ├── views/             # Login · Dashboard · Posts · Deployments · Schedules · Stats
        ├── components/        # EpaperPreview · NodeCard · SimPanel · …
        └── router/            # 인증 가드
```

## 5. 백엔드 상세

### 5.1 프로토콜 계층

PROTOCOL.md v0.1을 그대로 구현하고, 미정 항목 2건을 여기서 확정한다:

- **SEQ 롤오버**: 0xFF 다음 0x00 (mod 256). 중복 검출은 "직전 (TYPE,SEQ)와 동일" 비교이므로 롤오버 영향 없음.
- **엔디안**: 멀티바이트 필드(batt_mV, uptime_s)는 **little-endian**.

`link.py`의 `send_reliable(packet)`: 전송 → ACK 대기(T_ack=1500ms) → 미수신 시 동일 SEQ로 재전송(최대 3회) → 최종 실패 시 `LinkTimeoutError`. ACK의 `result≠OK`(CRC_FAIL/BUSY/BAD_TYPE)면 재시도 또는 에러 전파. 상위(deploy/node service)가 실패 시 노드 OFFLINE 마킹.

`templates.py`: 템플릿 4종(행사 안내/부스 지도/모집 공고/일정표)의 필드별 `(x, y, font_size, max_length)` 정의. max_length는 **UTF-8 바이트 기준**으로 SET_FIELD 페이로드 한도(text ≤ 198B)를 보장한다. 이 파일이 프론트 미리보기(`GET /api/templates`)와 노드 펌웨어 상수의 기준 소스.

### 5.2 시뮬레이터

- **가상 노드 상태머신** (노드 펌웨어 지시서의 스펙이 됨):
  - `SET_TEMPLATE/SET_FIELD/SET_QR` → 스테이징 버퍼에만 반영 + ACK
  - `COMMIT` → 스테이징을 커밋 상태로 반영, e-Paper 갱신 지연 재현(부분 1초/전체 3초) 후 ACK
  - `PING`→`PONG(batt_mV, rssi, status)`, `STATUS_REQ`→`STATUS_RES(batt_mV, last_seq, uptime_s, err_cnt)`
  - **멱등**: 직전 (TYPE,SEQ)와 동일한 패킷 수신 시 재적용 없이 ACK만 재전송
  - 배터리: 시간 경과에 따라 서서히 감소하는 모델 (기울기 설정 가능)
  - 전원 OFF(시뮬 API) 시 완전 무응답
- **가상 채널**: 설정 가능한 패킷 손실률(기본 0%)·지연. LoRa airtime(패킷당 ~0.3~0.5초)을 지연으로 재현해 배포 진행이 실제 속도감으로 보이게 한다.
- **가상 게이트웨이**: 서버발 COBS 프레임 디코딩 → 채널로 송신, 노드 응답 → COBS 인코딩 → 서버로. 실제 게이트웨이 펌웨어와 동일 역할.

### 5.3 상태 저장소 (메모리 + JSON, DB 없음)

`store.py`의 `AppState`(Pydantic)가 전체 상태를 보유하고, 변경 시마다 `data/state.json`에 원자적 스냅샷(임시 파일 작성 후 교체), 기동 시 로드한다. 도메인 모델:

| 모델 | 필드 (요지) |
|------|------|
| `Post` | id, title, template_id, fields(`{field_id: text}`), qr_url, created_at, updated_at |
| `Node` | id(=NodeID 0x01~), name(별칭), status(`online/offline/unknown`), battery_mv, rssi, last_seen_at, current_post_id, history(배터리·RSSI **링버퍼**, 노드당 최대 ~2000점) |
| `Deployment` | id, post_id, status(`running/success/partial/failed`), trigger(`manual/scheduled`), refresh_mode, created_at, finished_at, **targets**(노드별 내포: node_id, status `pending/sending/success/failed`, attempts, error, acked_at) |
| `Schedule` | id, post_id, node_ids, run_at, status(`pending/done/cancelled`), created_at |

- id는 상태 내 카운터로 발급. 관계형 조인 대신 객체 내포(targets ⊂ Deployment).
- 예약은 APScheduler **인메모리 jobstore** 사용 — 기동 시 `pending` Schedule을 JSON에서 읽어 재등록.
- 가상 모드 첫 기동 시 노드 0x01("노드 1"), 0x02("노드 2") 시드.
- SQLite는 시계열 이력이 링버퍼 한도를 넘게 필요해질 때만 도입(스트레치) — 저장소 접근을 `store` 모듈 뒤로 모아 교체 지점을 한 곳으로 유지.

### 5.4 REST API (`/api`)

| 그룹 | 엔드포인트 | 설명 |
|------|------|------|
| auth | `POST /auth/login` | `{password}` → `{token}` (이후 `Authorization: Bearer`) |
| posts | `GET/POST /posts`, `GET/PUT/DELETE /posts/{id}` | 게시물 CRUD |
| templates | `GET /templates` | 템플릿 필드 정의(좌표·폰트·최대길이) — 미리보기·폼 생성용 |
| nodes | `GET /nodes`, `GET /nodes/{id}` | 목록/상세. 상세에 `display_state`(커밋된 template_id·fields·qr_url) 포함 |
| | `POST /nodes/{id}/ping`, `GET /nodes/{id}/history` | 즉시 PING, 배터리·RSSI 시계열 |
| deployments | `POST /deployments` | `{post_id, node_ids\|"all", refresh_mode}` → 비동기 실행, `{deployment_id}` 반환 |
| | `GET /deployments/{id}` | 노드별 진행 상태 — **진행 중 1초 폴링 대상** |
| | `GET /deployments` | 이력 |
| schedules | `GET/POST /schedules`, `DELETE /schedules/{id}` | 일회성 예약 등록/취소 |
| stats | `GET /stats/summary` | 총 배포·성공률·종이 절감량·온라인 노드 수 (배터리 시계열은 `/nodes/{id}/history` 사용) |
| sim | `GET/PUT /sim/config` | 손실률·지연·배터리 방전 속도 (가상 모드 전용) |
| | `POST /sim/nodes/{id}/power` | 노드 전원 토글 — 장애 감지 데모용 |

인증: `POST /auth/login` 제외 전 엔드포인트에 Bearer 의존성. 토큰은 로그인 시 발급하는 서버 메모리 랜덤 토큰(재시작 시 재로그인 — MVP 허용).

### 5.5 배포 파이프라인

1. `POST /deployments` → `Deployment`(대상 노드별 `targets` 포함) 생성, asyncio 태스크로 실행 시작
2. 게시물 → 패킷 시퀀스: `SET_TEMPLATE(1) → SET_FIELD×n → SET_QR(1) → COMMIT(refresh_mode)`
3. 대상 노드에 **순차 유니캐스트**, 각 패킷 stop-and-wait (2노드 ~12초 — 30초 목표 충족. `0xFF` 브로드캐스트는 인코딩만 지원, 최적화는 스트레치)
4. 노드별 결과 기록: 전 패킷 ACK → `success` + `nodes.current_post_id` 갱신 / 실패 → `failed` + attempts·error 기록 + 노드 OFFLINE 마킹
5. 전체 판정: 전부 성공 `success` / 일부 `partial` / 전부 실패 `failed`
6. 예약 배포: APScheduler가 `run_at`에 동일 파이프라인 호출, `trigger=scheduled`

### 5.6 노드 모니터링

`node_service`가 주기(가상 모드 15초, 설정값)마다 각 노드에 STATUS_REQ → 응답을 `Node` 현재값과 이력 링버퍼에 기록. 타임아웃 반복 시 `offline` 판정.

> ⚠️ 실제 노드는 딥슬립으로 항상 수신하지 못한다. 폴링 주기·노드 wake 윈도우 동기화는 **펌웨어 팀과 협의 필요** — 개발 지시서에 협의 항목으로 명시한다. 서버는 주기·타임아웃을 설정값으로 열어두는 것까지가 책임.

## 6. 프론트엔드 상세

### 6.1 페이지

| 페이지 | 내용 |
|------|------|
| 로그인 | 비밀번호 입력 → 토큰 localStorage 저장, 라우터 가드 |
| 대시보드 | 노드 카드(상태 배지·배터리 게이지·RSSI·현재 화면 미리보기 축소판), 요약 통계, 최근 배포 |
| 게시물 관리 | 목록 + 작성/수정 다이얼로그(템플릿 선택 → 동적 필드 폼 → **라이브 미리보기**), 행별 "배포" 버튼 |
| 배포 | 실행 다이얼로그(노드 다중 선택, 부분/전체 갱신) → 진행 화면(노드별 단계·재시도 라이브) + 이력 |
| 예약 | 목록/등록/취소, 실행 결과 표시 |
| 통계 | 성공률 도넛, 노드별 배터리 추이 라인, 종이 절감 누적 카운터 (Chart.js) |
| 시뮬 패널 | 가상 모드일 때만 사이드바 노출: 손실률·지연 슬라이더, 노드 전원 토글 |

### 6.2 EpaperPreview 컴포넌트

- 296×128 캔버스, 흑백 1비트 스타일. `GET /api/templates` 좌표·폰트 정의에 따라 필드 텍스트 배치, QR은 `qrcode` npm 패키지로 실제 생성해 슬롯에 렌더.
- 두 곳에서 재사용: ① 게시물 작성 폼 라이브 미리보기(입력값 기준) ② 노드 현재 화면(`display_state` 기준).
- 폰트·줄바꿈 처리는 근사 렌더로 시작하고, 노드 펌웨어의 실제 렌더 규칙이 확정되면 상수를 맞춘다(지시서 연계).

### 6.3 상태 관리·동기화

- Pinia: `auth` / `nodes`(5초 폴링) / `posts` / `deployments`(진행 중인 배포가 있을 때만 1초 폴링) / `stats`(진입 시 로드)
- axios 인터셉터: 토큰 첨부, 401 → 로그인 리다이렉트

## 7. 에러 처리

| 상황 | 처리 |
|------|------|
| 패킷 3회 재시도 실패 | 타깃 `failed`, 노드 `offline` 마킹, 대시보드 경고 배지, 배포 `partial/failed` |
| ACK result=CRC_FAIL/BUSY | 동일 SEQ 재전송(재시도 카운트 공유), BUSY는 짧은 대기 후 |
| 필드 길이 초과 | 프론트 입력 제한(UTF-8 바이트 계산) + 백엔드 422 이중 검증 |
| 예약 시각에 노드 오프라인 | 시도 후 결과 기록만 (자동 재배포는 스트레치) |
| 시리얼 단절(실모드) | 게이트웨이 "연결 끊김" 상태 표시, 백그라운드 재연결 루프 — 구조만 준비 |
| 서버 재시작 | 진행 중이던 배포는 `failed(interrupted)` 처리, 상태는 JSON 스냅샷에서 로드, `pending` 예약은 APScheduler에 재등록 |

## 8. 테스트 전략

- **프로토콜 단위 테스트**(pytest): CRC16 알려진 벡터, COBS 라운드트립(0x00 포함 데이터), 패킷 encode/decode, 프레임 경계(분할 수신·연속 프레임). → **테스트 벡터를 펌웨어 지시서에 첨부**해 C 구현과 상호 검증.
- **링크 테스트**: 가상 transport로 ACK 타임아웃 → 재전송 → 성공, 3회 실패 → 예외, 멱등(중복 SEQ), SEQ 롤오버.
- **E2E**: 배포 API → 가상 노드 `display_state` 반영 확인. 손실률 30% 주입에서도 재전송으로 최종 성공.
- **API 테스트**: FastAPI TestClient로 CRUD·인증·예약.
- 프론트: 수동 테스트 중심 (자동화는 스트레치).

## 9. 마일스톤

| # | 내용 | 산출물 |
|---|------|------|
| 1 | 프로토콜 계층 + 단위 테스트 | packet/crc16/cobs/framing/link + 테스트 벡터 |
| 2 | transport + 시뮬레이터 | 가상 게이트웨이·노드·채널, 손실 주입 |
| 3 | 상태 저장소(메모리+JSON) + 게시물 CRUD + 배포 파이프라인 | posts/deployments API, E2E 1건 |
| 4 | 예약 + 모니터링 + 통계 API | schedules/stats, STATUS 폴링 |
| 5 | 프론트 스캐폴드 + 로그인 + 게시물/배포 UI | Vue 프로젝트, 핵심 화면 |
| 6 | 미리보기 + 대시보드 + 통계 + 시뮬 패널 | EpaperPreview, 차트 |
| 7 | 폴리싱 + 펌웨어 팀 개발 지시서 | 지시서(프로토콜 레퍼런스·테스트 벡터·상태머신 스펙) |

## 10. 하드웨어 전환 계획

1. `.env`를 `TRANSPORT_MODE=serial`, `SERIAL_PORT=COMx`로 변경 — 코드 변경 없이 시뮬레이터 비활성·pyserial 활성
2. `serial_port.py` 실장 검증(921600bps, COBS 프레이밍은 공용 코드 그대로)
3. 게이트웨이 펌웨어와 프레임 단위 루프백 테스트 → 노드 1대 배포 E2E → 2대
4. 미리보기 렌더 상수를 실제 e-Paper 출력과 대조·보정

## 11. 개방점·후속 작업

- **펌웨어 팀 개발 지시서** (별도 작업): 프로토콜 레퍼런스 구현·테스트 벡터·가상 노드 상태머신·템플릿 정의를 기반으로 작성
- 노드 딥슬립 wake 윈도우 ↔ 서버 폴링 주기 협의 (지시서 항목)
- KR920 TX 출력 한도, 한글 비트맵 폰트 — 펌웨어 영역 (PROTOCOL.md TODO 유지)
- 스트레치: IMG_FRAG, 브로드캐스트 COMMIT 최적화, 반복 예약, 자동 재배포, WebSocket 전환, 프론트 테스트, SQLite 시계열 이력
