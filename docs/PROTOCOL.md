# LoRa 패킷 프로토콜 스펙 (v0.2)

서버 ↔ 노드 간 통신 규약.

> **v0.2 개정 (2026-07-15)** — 하드웨어가 확정되며 물리·링크 계층을 실제에 맞춘다:
> **Waveshare SX1262 LoRa HAT을 서버 PC에 직결**(게이트웨이 ESP32 제거), e-Paper **7.5" 800×480 3색**.
> 개정은 팀장(우진) 주도. **애플리케이션 계층(§2~4)은 그대로 유효**하고, 물리·링크·타이밍(§0·1·5·7·9)만
> 다시 썼다. **펌웨어 구현과 무선 실측값(공중속도·MTU·타이밍) 최종 확정은 준표.** 실측 항목은 §10 TODO.
> v0.1 대비 변경점은 각 섹션 머리에 표시한다.

## 0. 토폴로지·주소  〔변경〕

```
[FastAPI 서버 + SX1262 HAT(USB)] ─LoRa 920MHz─ [노드1 0x01], [노드2 0x02]
```
- **게이트웨이 ESP32가 없다.** 서버 PC에 SX1262 HAT을 USB(UART)로 직접 연결하고, 서버가 마스터다.
  각 노드는 ESP32 + SX1262 HAT + e-Paper.
- NodeID 1byte: `0x00`=서버(마스터), `0x01~0xFE`=노드, `0xFF`=브로드캐스트(일괄 배포).
- 서버가 마스터(폴링/푸시), 노드는 응답만. (v0.1의 "게이트웨이" 역할을 서버가 직접 수행.)

## 1. LoRa 라디오 파라미터 (KR920)  〔변경 — RadioLib 직접설정 → HAT AT 레지스터〕

라디오 칩은 v0.1과 같은 **SX1262**지만, HAT의 온보드 MCU가 이를 감싸 **UART 투명 전송**으로 노출한다.
SF/BW/CR을 코드로 직접 지정하지 않고 **HAT의 AT 레지스터(공중속도 프리셋)로 설정**한다
(`server/tools/config_hat.py` 형식: M0=GND·M1 제거로 설정모드 진입 후 `0xC0` 쓰기).

| 항목 | 값 | 비고 |
|------|----|------|
| HAT 밴드 모델 | **915M 변형** | KR920(920.9~923.3)을 포함. 868M(EU) 모델 아님 — **효민 구매 확인** |
| 주파수 | 922.1 MHz | `START_FREQ=850`, freq_offset = 72. 양 끝단 회피 |
| 공중속도(air rate) | **2400 bps (시작값)** | SF/BW를 내부 캡슐화. 거리·속도 균형 보며 튜닝(실측) |
| UART 보드레이트 | **9600 bps** | PC↔HAT, ESP32↔HAT 공통(HAT 공장기본) |
| TX Power | **22 dBm (HAT 최대)** | **KR920 법정 출력 한도 확인 후 하향 설정** (§10) |
| 버퍼/서브패킷 | 240 B | 단일 전송 상한 관련 — MTU 실측 근거(§2·§6) |
| 앱 CRC | ON | 우리 CRC16(§2)로 무결성 검증. HAT은 RSSI 비활성(`opt2=0x43`) |

- 두 노드의 HAT과 서버 HAT을 **같은 주소(0)·네트워크(0)·채널**로 설정하고, 대상 구분은
  논리 패킷의 DST(§2)로 한다. (레퍼런스와 동일한 투명·고정전송 방식.)

## 2. 논리 패킷 포맷 (공통)  〔유지〕

HAT은 이 패킷을 그대로 실어 나르는 투명 파이프다. 서버 `app/protocol/packet.py`가 이미
transport-무관하게 구현하며, 전송 매체가 바뀌어도 이 포맷은 유지된다.

| 필드 | 크기 | 설명 |
|------|:---:|------|
| VER | 1 | 프로토콜 버전 = 0x01 (패킷 포맷 자체는 미변경) |
| SRC | 1 | 송신 NodeID (서버=0x00) |
| DST | 1 | 수신 NodeID (0xFF=브로드캐스트) |
| TYPE | 1 | 메시지 타입(§3) |
| SEQ | 1 | 시퀀스 번호(ACK 매칭·중복검출) |
| FRAG | 1 | bit7=LAST, bit0~6=조각 인덱스(단일=0x80) |
| LEN | 1 | PAYLOAD 길이(0~200) |
| PAYLOAD | 0~200 | 데이터 |
| CRC16 | 2 | CRC-16/CCITT-FALSE, VER~PAYLOAD 대상 |

- 고정 오버헤드 8B 헤더 + 2B CRC = 10B. PAYLOAD ≤ 200B (단, **MTU 실측 전까지 상한**; §6 참조).
- CRC16: poly=0x1021, init=0xFFFF, no reflect.
- **LEN 필드가 프레임을 자기 구분**한다 — 수신측이 헤더를 먼저 읽어 길이를 알므로 COBS가 불필요(§7).

## 3. 메시지 타입  〔유지 — 방향 라벨만 GW→S〕

| TYPE | 이름 | 방향 | PAYLOAD |
|:---:|------|------|---------|
| 0x01 | PING | S→Node | 없음 |
| 0x02 | PONG | Node→S | batt_mV(2), rssi(1), status(1) |
| 0x10 | SET_TEMPLATE | S→Node | template_id(1) |
| 0x11 | SET_FIELD | S→Node | field_id(1), text_len(1), UTF-8 text |
| 0x12 | SET_QR | S→Node | qr_slot(1), url_len(1), URL text |
| 0x13 | COMMIT | S→Node | refresh_mode(1): 0=부분,1=전체 |
| 0x14 | IMG_FRAG | S→Node | (스트레치) 이미지 조각, FRAG 분할 |
| 0x20 | ACK | Node→S | ack_seq(1), result(1): 0=OK,1=CRC_FAIL,2=BUSY,3=BAD_TYPE |
| 0x30 | STATUS_REQ | S→Node | 없음 |
| 0x31 | STATUS_RES | Node→S | batt_mV(2), last_seq(1), uptime_s(2), err_cnt(1) |

> 색(적색) 지정 필드는 v0.2 범위 밖이다. 7.5" 패널은 3색(흑·백·적)을 그릴 수 있으므로, 향후
> SET_FIELD/템플릿에 색 필드를 추가할 수 있다 — **별도 개정(v0.3)에서 준표와 협의**.

### 3.1 PAYLOAD 바이트 배치 (전부 little-endian)  〔유지〕

멀티바이트 필드는 전부 **little-endian**. 서버(Python `struct`)와 펌웨어(C 구조체)가 동일 배치를 사용한다.
C 측은 `__attribute__((packed))` 필수 — 패딩이 끼면 배치가 어긋난다.

| 메시지 | 배치 | Python struct | 크기 |
|---|---|---|:---:|
| PONG | batt_mV u16 · rssi i8 · status u8 | `<HbB` | 4B |
| ACK | ack_seq u8 · result u8 | `<BB` | 2B |
| STATUS_RES | batt_mV u16 · last_seq u8 · uptime_s u16 · err_cnt u8 | `<HBHB` | 6B |
| SET_TEMPLATE | template_id u8 | `<B` | 1B |
| SET_FIELD | field_id u8 · text_len u8 · UTF-8 text(≤198B) | - | 2+nB |
| SET_QR | qr_slot u8 · url_len u8 · URL text | - | 2+nB |
| COMMIT | refresh_mode u8 (0=부분, 1=전체) | `<B` | 1B |

예) PONG(batt 3900mV, rssi -60dBm, status 0) → `3C 0F C4 00`

C 참조 구조체:
```c
typedef struct __attribute__((packed)) {
    uint16_t batt_mv;   // little-endian (ESP32 기본)
    int8_t   rssi;
    uint8_t  status;
} pong_payload_t;
```

> rssi: HAT은 RSSI 출력을 비활성(§1)했다. 노드가 자체 측정한 값을 담거나, 필요 시 HAT RSSI를
> 켜서 채운다 — 구현 시 준표 결정.

## 4. 게시물 업데이트 시퀀스 (템플릿 기반)  〔유지 — COMMIT ACK 타이밍만 §5〕

```
S→Node : SET_TEMPLATE(id)             (템플릿 바뀔 때만)   →  ACK
S→Node : SET_FIELD(제목/일정/장소…)    반복               →  ACK (필드마다)
S→Node : SET_QR(상세URL)                                 →  ACK
S→Node : COMMIT(refresh_mode)         스테이징 검증        →  ACK(OK) → (비동기 렌더)
```
- SET_* 는 노드 램(스테이징)에만 적용, COMMIT에서 한 번에 화면 갱신 → 깜빡임 1회.
- refresh_mode: 텍스트 일부=0(부분갱신), 템플릿 전환=1(전체갱신, 고스팅 제거).
  **주의: 7.5" 3색 패널은 부분갱신 지원이 제한적**이다 — 실제 지원 여부는 준표 확인(§10).
- QR은 URL 문자열만 전송 → 노드가 `QRCode` 라이브러리로 렌더(대역폭 최소화).

## 5. ACK·재전송·신뢰성  〔변경 — 타이밍 상향 + COMMIT ACK 순서 수정〕

- **Stop-and-wait**: 서버는 전송 후 ACK 대기, 다음 진행.
- **T_ack ≈ 2500ms, N_retry ≈ 5** (레퍼런스 실측 기반. 공중속도 2400bps·UART 9600·HAT 처리
  지연을 반영. 실측 후 최종 확정 — §10).
- N_retry 실패 → 노드 OFFLINE 마킹 → 서버 보고.
- **중복 검출**: 노드는 (TYPE,SEQ) 직전값과 동일 시 재적용 없이 ACK만 재전송(멱등).
- **브로드캐스트 ACK 충돌 방지**: DST=0xFF COMMIT 시 각 노드 `NodeID×슬롯` 간격으로 ACK.

### 5.1 COMMIT ACK는 렌더 *전*에 보낸다  〔신규 — 중요〕

7.5" 3색 e-Paper 전체 갱신은 **~15~20초** 걸린다. 렌더가 끝난 뒤 ACK를 보내면 T_ack(2.5초)을
한참 넘겨 **매 COMMIT이 타임아웃·재전송**된다.

따라서 노드는 **COMMIT 수신 → 스테이징 유효성 검증 → 즉시 ACK(OK) → 그 후 비동기로 렌더**한다.
서버는 ACK로 "전송 성공"을 확정하고 다음 노드로 넘어간다. 실제 화면 반영은 렌더 완료 후
(수 초~수십 초 뒤). 렌더 중 노드는 수신 불가 — 다음 명령이 오면 재전송으로 흡수한다.
(레퍼런스도 "ACK는 렌더 전"이다.)

## 6. 분할 전송 (FRAG)  〔변경 — MTU 실측·SET_FIELD 로 확대 가능〕

- FRAG: bit7=LAST, bit0~6=조각 인덱스(0~127). 재조립 키 = (SRC, base_SEQ). 조각마다 stop-and-wait ACK.
- 전 조각 CRC OK + LAST 수신 → 적용. 누락은 해당 인덱스 재요청.
- **MTU 실측 필요**: HAT 버퍼는 240B지만 레퍼런스는 안정성을 위해 **22B 청크**로 나눴다. 공중속도
  2400bps에서 단일 전송의 신뢰 상한을 실측한 뒤:
  - 상한이 200B 이상이면 §2 그대로(단일 SET_FIELD 가능).
  - 상한이 그보다 작으면 **FRAG 분할을 이미지(IMG_FRAG)뿐 아니라 SET_FIELD/SET_QR 에도 적용**한다
    (레퍼런스의 BEGIN/DATA 청크와 같은 역할). 이 경우 §2의 LEN 상한을 MTU에 맞춰 낮춘다.

## 7. 서버 ↔ HAT 시리얼 (USB)  〔변경 — COBS 제거, 게이트웨이 없음〕

- 게이트웨이 ESP32가 없으므로 "서버↔게이트웨이"가 아니라 **서버↔HAT** 링크다.
- pyserial(서버) ↔ **SX1262 HAT UART, 9600 bps**.
- **COBS 불필요**: §2 패킷의 LEN 필드가 프레임을 자기 구분한다(헤더 먼저 읽고 길이만큼 수신).
  v0.1의 COBS+0x00 프레이밍은 제거한다 — 서버 `app/protocol/cobs.py`·`framing.py`는 이에 맞춰
  정리(우진, 서버 transport 교체 작업과 연동).
- HAT 고정전송: TX 시 라우팅 헤더 `[ADDR_H][ADDR_L][CH]`를 앞에 붙이면 HAT이 이를 **소비**(공중
  전송 안 됨)하고 뒤의 논리 패킷만 송신. 수신 = 논리 패킷만.

## 8. 노드 템플릿 정의 (펌웨어 내장, LittleFS)  〔변경 — 5종·800×480〕

캔버스는 **템플릿의 속성**이다(대부분 800×480 가로, "팀 소개"는 480×800 세로). 좌표·폰트·최대길이의
단일 기준 소스는 `server/backend/app/protocol/templates.py`이고, `tools/gen_templates.py`가
`node/.../templates.h`를 생성한다.

| template_id | 용도 | 필드(field_id) | 캔버스 |
|:---:|------|------|:---:|
| 0 | 행사 안내 | 0=제목, 1=일시, 2=장소, 3=비고 / QR0=상세 | 800×480 |
| 1 | 부스 지도 | 0=구역명, 1=부스번호 / QR0=지도 | 800×480 |
| 2 | 모집 공고 | 0=제목, 1=마감, 2=대상 / QR0=신청 | 800×480 |
| 3 | 일정표 | 0=날짜, 1~3=세션 / QR0=전체일정 | 800×480 |
| 4 | 팀 소개 | 0=팀명, 1~3=주제 / QR0=상세 | 480×800(세로) |

- 필드 = (x, y, 폰트크기, 최대길이). 폰트는 16×16 비트맵의 **정수배**(16/32/48/64px).
- 800×480 좌표 재배치는 웹 파트 스펙(`docs/web/`)에서 확정 — templates.py가 기준.

## 9. 타이밍 예산 ("30초 이내" 재검토)  〔변경 — 7.5" 3색 기준, 목표 위협〕

v0.1의 6초 예산은 2.9" 2색·SF9 직접전송 가정이었다. 새 하드웨어로 다시 본다(모두 **추정 — 실측 필요**):

| 단계 | 추정 | 근거 |
|------|------|------|
| 패킷 전송(SET_×n + COMMIT), 노드 1대 | ~5~10s | 공중속도 2400bps + UART 9600 + stop-and-wait ACK. 청크 분할 시 증가 |
| COMMIT 후 e-Paper 전체 렌더 | **~15~20s** | 7.5" 3색은 2색보다 훨씬 느림. 노드에서 **비동기**(§5.1) |

- **패킷 전달 완료**(전 노드 ACK): 2노드 순차 ~10~20s → 30초 목표 **가능**.
- **화면 실제 반영 완료**(렌더까지): 전달 + 렌더 15~20s → **30초 초과 가능**. 렌더는 노드 간
  병렬이라 마지막 노드 기준.
- ⚠ **"30초 이내"의 정의(전달 vs 반영)와 수치를 팀에서 재조정해야 한다.** 실측 전엔 확정 불가.

## 10. 미정·TODO
- [ ] **공중속도·MTU 실측** — 2400bps에서 단일 전송 신뢰 상한(§6), 타이밍(§9), T_ack·N_retry(§5)
- [ ] **KR920 법정 TX 출력 한도** 수치 확정 → HAT power 하향(§1)
- [ ] **915M 밴드 HAT** 조달 확인 (868M 아님) — 효민(§1)
- [ ] **7.5" 3색 부분갱신 지원 여부** — 안 되면 refresh_mode=0 의미 재정의(§4)
- [ ] **"30초 이내" 목표 재조정** — 전달/반영 정의 + 수치 (팀 결정, §9)
- [ ] 한글 비트맵 폰트 e-Paper 적용(16×16 정수배; 800×480에선 32/48/64px 사용)
- [ ] (v0.3) 적색 지원 — SET_FIELD/템플릿 색 필드 (§3)
- [x] 게이트웨이 ESP32 제거, HAT 서버 직결 — 하드웨어 확정(2026-07-15)
- [x] SEQ 롤오버 — 노드별 독립 SEQ, 0xFF→0x00 순환 (서버 구현 확정, 2026-07-08)
- [x] 구조체 바이트 정렬·엔디안 — little-endian 확정, §3.1에 배치 명문화 (2026-07-08)
