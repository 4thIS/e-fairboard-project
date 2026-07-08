# server/ 백엔드 코어 설계 (1차)

- 날짜: 2026-07-08 / 담당: 준표(`jp`) / 상태: 승인됨
- 근거 문서: `docs/ARCHITECTURE.md`, `docs/PROTOCOL.md`(v0.1)

## 1. 목표와 범위

**목표**: 게이트웨이 하드웨어 없이 개발·검증 가능한 FastAPI 백엔드 코어.
모의 게이트웨이 시뮬레이터로 E2E(게시물 작성→배포→ACK→상태 반영)를 재현하고,
실물 도착 시 transport 구현체만 교체한다.

**1차 범위 (이 스펙)**
- 패킷 코덱(CRC16/COBS) + 시리얼 브리지 + 모의 게이트웨이
- REST API: 게시물 CRUD·배포·예약·노드 상태·템플릿·통계
- 상태: 메모리 + JSON 영속 (DB 없음, ARCHITECTURE §6)
- pytest 테스트

**비범위 (2차 이후)**: Vue 대시보드, IMG_FRAG 분할 전송, SQLite 시계열 이력.

## 2. 디렉토리 구조

```
server/
├─ pyproject.toml            # uv 관리
├─ app/
│  ├─ main.py                # FastAPI 앱, lifespan에서 GatewayLink 기동/종료
│  ├─ config.py              # 시리얼 포트·보레이트·타임아웃·데이터 경로 (env 오버라이드)
│  ├─ protocol/
│  │  ├─ const.py            # TYPE 10종, NodeID, result 코드 (PROTOCOL §3)
│  │  ├─ packet.py           # Packet dataclass, encode/decode, crc16_ccitt
│  │  └─ cobs.py             # cobs_encode / cobs_decode
│  ├─ bridge/
│  │  ├─ transport.py        # Transport 추상 + SerialTransport(pyserial)
│  │  └─ gateway_link.py     # 프레임 분리(0x00), SEQ 발급, 응답 매칭, 수신 루프
│  ├─ core/
│  │  ├─ state.py            # Node·Post·Stats 인메모리 + JSON 원자적 영속
│  │  ├─ templates.py        # 템플릿 4종 정의 (PROTOCOL §8, 펌웨어와 동기화)
│  │  ├─ deploy.py           # 배포 오케스트레이터 (PROTOCOL §4 시퀀스)
│  │  └─ scheduler.py        # APScheduler(AsyncIO) 예약 배포
│  └─ api/
│     ├─ posts.py  nodes.py  deploy.py  templates.py  stats.py
├─ sim/
│  └─ fake_gateway.py        # FakeGatewayTransport + 가상 노드 2대
├─ tests/
└─ data/state.json           # 런타임 생성 (gitignore)
```

## 3. 컴포넌트 설계

### 3.1 protocol/ — 순수 코덱 (시리얼·asyncio 무관)
- `Packet(ver, src, dst, type, seq, frag, payload)` — LEN은 payload에서 유도
- `encode(p) -> bytes`: 8B 헤더 + payload + CRC16(CCITT-FALSE, poly 0x1021, init 0xFFFF)
- `decode(b) -> Packet`: 길이·CRC 검증, 실패 시 `PacketError`
- 멀티바이트 필드(batt_mV, uptime_s)는 **little-endian** (PROTOCOL §10 권장안 채택)
- 의존성 없음 → 우진·효민 펌웨어 구현의 레퍼런스 겸용

### 3.2 bridge/ — 전송 계층
- `Transport`(추상): `async read(n)`, `async write(b)`, `open()`, `close()`
  - `SerialTransport`: pyserial 921600bps (실물용)
  - `FakeGatewayTransport`: sim/ 구현체 (개발·테스트용) — 교체점은 이 인터페이스 하나
- `GatewayLink`:
  - 백그라운드 수신 루프: 0x00 구분자로 프레임 분리 → COBS 디코드 → Packet 디코드
  - CRC 불일치 프레임은 폐기 + 경고 로그
  - SEQ: **노드별 카운터**, 0xFF→0x00 롤오버, (dst, seq)로 응답 매칭
  - `request(packet, timeout) -> Packet`: 전송 후 매칭 응답 대기 (기본 6s = GW 최악 재전송 3×1.5s + 여유)
  - 비요청 수신 패킷(PONG·STATUS_RES 등)은 state 갱신 콜백으로 전달
  - 시리얼 단절 시 지수 백오프 재연결

### 3.3 core/ — 도메인
- `Node`: node_id, name, online, last_seen, batt_mv, rssi, err_cnt
- `Post`: id, template_id, fields{field_id: text}, qr_url, target_node_ids,
  status(`draft|scheduled|deploying|deployed|partial|failed`), schedule_at, deployed_at
- `Stats`: 배포 성공/실패 누적, 종이 절감 카운트(성공 배포 × 대상 노드 수)
- 영속: 변경 시 `data/state.json`에 tmp 파일 작성 후 rename(원자적). 기동 시 로드.
- `deploy.py`: §4 시퀀스 — SET_TEMPLATE(템플릿 변경 시만) → SET_FIELD×n → SET_QR → COMMIT.
  노드별 순차 실행, 각 단계 ACK(result=0) 확인. 실패 노드는 상위 재시도 1회 후 OFFLINE 마킹.
  전 노드 성공=`deployed`, 일부=`partial`, 전부 실패=`failed`.
- `scheduler.py`: date trigger로 `deploy` 호출. 잡은 인메모리지만 `scheduled` 포스트가
  JSON에 영속되므로 기동 시 미래 예약은 재등록, 지난 예약은 `failed` 처리.
- 필드 검증: 템플릿 필드 id·최대길이(templates.py 상수), SET_FIELD payload ≤ 200B 한도.

### 3.4 api/ — REST (모두 `/api` prefix)

| 메서드·경로 | 동작 |
|---|---|
| GET `/templates` | 템플릿 4종 정의(필드·QR 슬롯) |
| GET·POST `/posts`, GET·PUT·DELETE `/posts/{id}` | 게시물 CRUD (draft) |
| POST `/posts/{id}/deploy` | 즉시 배포 (body: node_ids — 일괄=전체 나열. MVP는 순차 유니캐스트, LoRa 브로드캐스트(0xFF)는 후순위 최적화) |
| POST `/posts/{id}/schedule` | 예약 (body: at, node_ids) / DELETE로 취소 |
| GET `/nodes` | 노드 목록·온라인·배터리·last_seen |
| POST `/nodes/{id}/ping` | PING→PONG 왕복 확인 |
| POST `/nodes/{id}/status` | STATUS_REQ→STATUS_RES 갱신 |
| GET `/stats` | 성공률·종이절감·노드 요약 (대시보드용) |
| GET `/health` | 서버·브리지 연결 상태 |

### 3.5 sim/fake_gateway.py — 모의 게이트웨이
- `FakeGatewayTransport(Transport)`: 서버가 write한 프레임을 디코드해
  가상 노드 2대(0x01, 0x02) 상태머신에 전달, 응답을 read 버퍼로 되돌림
- 노드 상태머신: SET_*→스테이징+ACK, COMMIT→"화면 갱신"(로그)+ACK,
  PING→PONG(가짜 배터리·RSSI), STATUS_REQ→STATUS_RES, (TYPE,SEQ) 중복이면 ACK만 재전송(멱등)
- 실패 주입 설정: 특정 노드 무응답(OFFLINE 경로), CRC 오염(폐기 경로), 지연
- 브로드캐스트(0xFF): 노드별 NodeID×200ms 슬롯 지연 후 ACK (§5 재현)

## 4. 데이터 흐름

```
curl/대시보드 → api → core.deploy → GatewayLink.request → Transport
                                    (fake ↔ serial 교체점)     ↓
   state 갱신 ← ACK/PONG/STATUS_RES ← 수신 루프 ← ─ ─ ─ ─ 모의/실물 GW·노드
       ↓
   data/state.json (원자적 flush)          예약: scheduler → 동일 경로
```

## 5. 에러 처리

| 상황 | 처리 |
|---|---|
| CRC/COBS 불일치 | 프레임 폐기 + 경고 로그 (카운터 증가) |
| 응답 타임아웃 | 상위 재시도 1회 → 실패 시 노드 OFFLINE 마킹, 배포 결과에 반영 |
| 시리얼 단절 | 지수 백오프 재연결, `/health`에 노출 |
| JSON 저장 실패 | tmp+rename 원자성, 실패 시 로그 (메모리 상태는 유지) |
| API 입력 오류 | Pydantic 검증 422 (필드 길이·템플릿 id·노드 id) |

## 6. 테스트 전략 (pytest)

1. **코덱**: encode/decode 왕복, CRC16 고정 벡터, 경계(LEN 0·200), 오염 시 PacketError
2. **COBS**: payload에 0x00 포함/전부 0x00/빈 payload 왕복
3. **GatewayLink**: FakeTransport로 SEQ 매칭·타임아웃·롤오버·비요청 패킷 콜백
4. **deploy E2E**: FakeGW로 성공/부분 실패(무응답 노드)/중복 SEQ 멱등/브로드캐스트
5. **state**: JSON 영속 왕복, 원자적 쓰기
6. **API**: httpx AsyncClient — CRUD·배포·예약·422 검증

## 7. 환경·실행

- `uv` 의존성 관리 (fastapi-vue-board/backend와 동일 패턴)
- 실행: `uv run fastapi dev app/main.py` (기본 FakeGW 모드, `EFB_SERIAL_PORT` 설정 시 실물)
- 테스트: `uv run pytest`
- 브랜치: `jp` → 완료 후 PR

## 8. 가정·스펙 공백 (팀 합의 필요)

1. **GW=투명 릴레이 가정**: PROTOCOL §7은 프레이밍만 정의. 본 설계는 "GW가 노드 패킷
   (ACK·PONG·STATUS_RES)을 시리얼로 그대로 중계하고, LoRa stop-and-wait 재전송(§5)은
   GW가 자체 처리"로 가정 → PROTOCOL §10 TODO에 명문화하여 우진과 합의
2. **엔디안**: little-endian 채택 (§10 권장안) — 펌웨어 측 동일 적용 필요
3. **템플릿 필드 최대길이**: 서버 `templates.py` 상수로 우선 정의(예: 제목 32자) →
   효민의 e-Paper 렌더 구현 시 실측으로 동기화
4. **서버 상위 타임아웃 6s**: GW 재전송 파라미터(T_ack 1.5s×3) 확정 시 재조정
