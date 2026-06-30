# LoRa 패킷 프로토콜 스펙 (v0.1)

서버 ↔ 게이트웨이 ↔ 노드 간 통신 규약. 초안 — 구현하며 갱신.

## 0. 토폴로지·주소
```
[FastAPI 서버] ─USB Serial(COBS)─ [게이트웨이 0x00] ─LoRa 920MHz─ [노드1 0x01], [노드2 0x02]
```
- NodeID 1byte: `0x00`=게이트웨이, `0x01~0xFE`=노드, `0xFF`=브로드캐스트(일괄 배포)
- 게이트웨이가 마스터(폴링/푸시), 노드는 응답만.

## 1. LoRa 라디오 파라미터 (KR920)
| 항목 | 값 | 비고 |
|------|----|------|
| 주파수 | 922.1 MHz | KR920(920.9~923.3) 내, 양 끝단 회피 |
| SF | 9 | 거리·속도 균형, 측정 후 7~10 튜닝 |
| Bandwidth | 125 kHz | |
| Coding Rate | 4/5 | |
| Preamble | 8 symbol | |
| Sync Word | 0x12 (private) | SX1262 |
| TX Power | 14 dBm | **KR920 법정 출력 한도 확인 후 설정** |
| HW CRC | ON | RadioLib `setCRC(true)`, 앱 CRC16과 이중 검증 |

## 2. 논리 패킷 포맷 (LoRa·Serial 공통)
| 필드 | 크기 | 설명 |
|------|:---:|------|
| VER | 1 | 프로토콜 버전 = 0x01 |
| SRC | 1 | 송신 NodeID |
| DST | 1 | 수신 NodeID (0xFF=브로드캐스트) |
| TYPE | 1 | 메시지 타입(§3) |
| SEQ | 1 | 시퀀스 번호(ACK 매칭·중복검출) |
| FRAG | 1 | bit7=LAST, bit0~6=조각 인덱스(단일=0x80) |
| LEN | 1 | PAYLOAD 길이(0~200) |
| PAYLOAD | 0~200 | 데이터 |
| CRC16 | 2 | CRC-16/CCITT-FALSE, VER~PAYLOAD 대상 |

- 고정 오버헤드 8B 헤더 + 2B CRC = 10B. PAYLOAD ≤ 200B.
- CRC16: poly=0x1021, init=0xFFFF, no reflect.

## 3. 메시지 타입
| TYPE | 이름 | 방향 | PAYLOAD |
|:---:|------|------|---------|
| 0x01 | PING | GW→Node | 없음 |
| 0x02 | PONG | Node→GW | batt_mV(2), rssi(1), status(1) |
| 0x10 | SET_TEMPLATE | GW→Node | template_id(1) |
| 0x11 | SET_FIELD | GW→Node | field_id(1), text_len(1), UTF-8 text |
| 0x12 | SET_QR | GW→Node | qr_slot(1), url_len(1), URL text |
| 0x13 | COMMIT | GW→Node | refresh_mode(1): 0=부분,1=전체 |
| 0x14 | IMG_FRAG | GW→Node | (스트레치) 이미지 조각, FRAG 분할 |
| 0x20 | ACK | Node→GW | ack_seq(1), result(1): 0=OK,1=CRC_FAIL,2=BUSY,3=BAD_TYPE |
| 0x30 | STATUS_REQ | GW→Node | 없음 |
| 0x31 | STATUS_RES | Node→GW | batt_mV(2), last_seq(1), uptime_s(2), err_cnt(1) |

## 4. 게시물 업데이트 시퀀스 (템플릿 기반)
```
GW→Node : SET_TEMPLATE(id)            (템플릿 바뀔 때만)   →  ACK
GW→Node : SET_FIELD(제목/일정/장소…)   반복               →  ACK (필드마다)
GW→Node : SET_QR(상세URL)                                →  ACK
GW→Node : COMMIT(refresh_mode)        e-Paper 실제 갱신   →  ACK(OK)
```
- SET_* 는 노드 램(스테이징)에만 적용, COMMIT에서 한 번에 화면 갱신 → 깜빡임 1회.
- refresh_mode: 텍스트 일부=0(부분갱신, 빠름), 템플릿 전환=1(전체갱신, 고스팅 제거).
- QR은 URL 문자열만 전송 → 노드가 `QRCode` 라이브러리로 렌더(대역폭 최소화).

## 5. ACK·재전송·신뢰성
- **Stop-and-wait**: GW는 전송 후 ACK 대기, 다음 진행.
- T_ack = 1500ms (SF9 왕복+처리 여유), N_retry = 3.
- 3회 실패 → 노드 OFFLINE 마킹 → 서버 보고.
- **중복 검출**: 노드는 (TYPE,SEQ) 직전값과 동일 시 재적용 없이 ACK만 재전송(멱등).
- **브로드캐스트 ACK 충돌 방지**: DST=0xFF COMMIT 시 각 노드 `NodeID×200ms` 슬롯에 ACK.

## 6. 분할 전송 (IMG_FRAG, 스트레치)
- FRAG: bit7=LAST, bit0~6=조각 인덱스(0~127).
- 재조립 키 = (SRC, base_SEQ). 조각마다 stop-and-wait ACK.
- 전 조각 CRC OK + LAST 수신 → 적용. 누락은 해당 인덱스 재요청.
- MVP는 텍스트+QR만 → 결선 후 여력 시 구현.

## 7. 서버↔게이트웨이 시리얼 프레이밍 (USB)
- USB 스트림 경계 → **COBS 인코딩 + 0x00 구분자**.
- 프레임 = `COBS(논리패킷) + 0x00`. 수신측이 0x00에서 분리 후 디코딩.
- pyserial(서버) ↔ ESP32 UART(게이트웨이), 기본 921600 bps.

## 8. 노드 템플릿 정의 (펌웨어 내장, LittleFS)
| template_id | 용도 | 필드(field_id) |
|:---:|------|------|
| 0 | 행사 안내 | 0=제목, 1=일시, 2=장소, 3=비고 / QR0=상세 |
| 1 | 부스 지도 | 0=구역명, 1=부스번호 / QR0=지도 |
| 2 | 모집 공고 | 0=제목, 1=마감, 2=대상 / QR0=신청 |
| 3 | 일정표 | 0=날짜, 1~3=세션 / QR0=전체일정 |
- 필드 = (x, y, 폰트크기, 최대길이). 좌표·폰트는 펌웨어 상수 → 서버는 값만 전송.

## 9. 타이밍 예산 ("30초 이내" 검증)
| 단계 | 패킷 | 추정(SF9/BW125) |
|------|------|------|
| SET_TEMPLATE+ACK | 1 | ~0.4s |
| SET_FIELD×3+ACK | 3 | ~1.2s |
| SET_QR+ACK | 1 | ~0.5s |
| COMMIT+ACK+갱신 | 1 | 부분~1s / 전체(2.9")~3s |
| **합계(노드 1대)** | 6 | **~5~6초** |
- 2노드 브로드캐스트 COMMIT 시에도 < 15초 → 목표 30초 충족.

## 10. 미정·TODO
- [ ] KR920 법정 TX 출력 한도 수치 확정
- [ ] 한글 비트맵 폰트(나눔/Galmuri) e-Paper 적용 방식
- [ ] SEQ 롤오버(0xFF→0x00) 규칙 명문화
- [ ] 구조체 바이트 정렬·엔디안 명시(little-endian 권장)
