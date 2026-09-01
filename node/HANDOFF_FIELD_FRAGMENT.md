# 인수인계 — 필드 분할 전송(설명 198바이트 한계 돌파)

> **한 줄:** 한 필드(특히 **설명**)를 여러 `SET_FIELD` 조각으로 나눠 보내고, 노드가 다시 합쳐
> 198바이트보다 긴 텍스트를 받게 한다.
>
> **⚠ 펌웨어만으로 안 된다.** 서버가 **쪼개 보내야** 노드가 합칠 게 생긴다. 함께 가야 동작:
> - **스펙 + 서버 = 우진** (PROTOCOL.md 포맷 확정 · 송신·검증·시뮬) · **노드 = hm** (재조립·재플래시)
> - 한쪽만 하면 배포가 깨진다 → **포맷 먼저 확정 → 서버·노드 동시 반영**.
> - (PROTOCOL.md 는 원래 jp 관할 — 우진이 작성하되 값은 jp 와 한 번 맞춘다.)

---

## 0. 배경 — 왜 198에서 막히나
- `SET_FIELD` 페이로드 = `[field_id][text_len(1B)][text…]`, 한 패킷 텍스트 한도 **198B**
  (`MAX_TEXT = MAX_PAYLOAD 200 − 2`). 한글 ≈ 66자에서 잘린다.
- 우리 링크는 E22 서브패킷 240B 설정이라 **한 패킷(≤209B)은 한 번에** 나간다(레퍼런스의 29B
  청크 제약은 그쪽 설정 얘기 — 우리 문제는 링크 MTU 가 아니라 **프로토콜 payload 한도**다).
- 그래서 링크 계층 청크가 아니라 **프로토콜 계층에서 SET_FIELD 를 여러 개**로 쪼갠다.

## 1. 설계 — 헤더 `frag` 바이트를 재사용한 분할 SET_FIELD
헤더에 이미 있다: `[VER][SRC][DST][TYPE][SEQ][FRAG][LEN][payload][CRC16]`.
`FRAG` 바이트 = **bit7=LAST**, 하위 7bit=**인덱스**(`FRAG_SINGLE = 0x80` = 인덱스0·LAST = 지금 단일).

**분할 규칙:**
- 필드 텍스트를 `CHUNK`(≤190B, UTF-8 경계에서 자름 — 글자 중간에서 끊지 말 것) 단위로 나눈다.
- 각 조각 = `SET_FIELD` 패킷:
  - payload = `[field_id][chunk_len][chunk_bytes]` (chunk_len = **그 조각** 길이)
  - FRAG = 인덱스(0,1,2…), **마지막 조각만 bit7 set**.
- **stop-and-wait 유지** — 조각마다 ACK, 한 번에 하나만 in-flight (현재 `link.request` 와 동일).
- 조각 하나면 지금과 동일(FRAG=0x80) → **짧은 필드는 기존과 완전 호환**.

## 2. 파트별 작업

### A. 스펙 — 우진 (PROTOCOL.md; 값은 jp 와 확인)
- `SET_FIELD` 절에 분할 정의: FRAG 인덱스/LAST 의미, `chunk_len` 은 조각 길이, 재조립 규칙,
  **필드 최대 크기**(아래 §3, 예: 512B) 확정. `MAX_TEXT`(QR 등 단일 필드)와 필드 재조립 상한 구분.

### B. 서버 — 우진 (포맷 확정되면 바로)
- `protocol/packet.py`: `build_set_field` 를 조각 리스트로 만들거나, frag 를 지정해 인코딩하는 경로 추가.
- `protocol/link.py`: `request(...)` 에 `frag` 인자 추가(기본 `FRAG_SINGLE`).
- `services/deploy_service.py::build_packet_plan`: 필드 텍스트가 `CHUNK` 초과면 **여러 SET_FIELD**
  (frag 인덱스 부여, 마지막에 LAST)로 전개. plan 튜플에 frag 포함.
- `schemas.py::_MAX_TEXT_BYTES`(198) 와 `templates.py::field_max_bytes` 의 198 상한 → **필드 재조립
  상한**(예 512)으로. (QR 은 198 유지.)
- `simulator/node.py`: 노드와 **같은 재조립** 반영(가상 모드도 동작하게).

### C. 노드 — hm (재플래시)
- `node_core/src/state_machine.cpp::apply()` 의 `SET_FIELD` 처리 교체:
  - `idx = p.frag & 0x7F`, `last = p.frag & 0x80`.
  - `idx == 0` → 그 field_id 조립 버퍼를 **비우고** 시작.
  - chunk 를 버퍼에 **이어붙임**(새 상한 초과 방어 — 넘으면 BAD_TYPE).
  - `last` 면 `staged_.fields[field_id]` 완성 + `has_field=true`. (중간 조각은 미완성 표시.)
- 버퍼 확대: `node_core/include/node/state_machine.h` 의 `MAX_TEXT_LEN`(=`efb::MAX_TEXT` 198)을
  필드용으로 키운다(예 **512**). `DisplayState.fields[MAX_FIELDS][N+1]` ×2(staged/committed)
  → 8×513×2 ≈ 8KB, ESP32 여유 OK.
- **재조립 멱등:** 조각마다 SEQ 가 다르지만 stop-and-wait 라 in-flight 는 1개 → 기존
  `last_handled_seq_` 덯이 재전송 조각의 이중 append 를 막는다(직전 조각과 SEQ 동일). 그대로 둔다.
- `main_hat1248.cpp` 렌더는 완성된 필드를 그리므로 **변경 없음**(멀티라인은 [[HANDOFF_MULTILINE]] 이 담당).

## 3. 크기·신뢰성 결정거리 (합의 필요)
- **필드 상한**: 제안 **512B**(≈한글 170자, 설명 영역 7~8줄). 무제한 아님 — RAM·airtime 때문.
- **CHUNK**: 190B 안팎(payload 여유). 512 → 3조각.
- **airtime**: 설명이 2~3패킷 늘어 조각마다 T_ack(≈1.5s). e-Paper 렌더 34초에 비하면 미미.
- 짧은 필드는 조각 1개(기존과 동일 비용) — 긴 설명일 때만 늘어난다.

## 4. 검증
- 서버 단위테스트: 긴 텍스트 → `build_packet_plan` 이 올바른 frag 인덱스/LAST 로 N조각.
- native(node) 테스트: 조각 순차 수신 → 재조립 == 원문, 마지막 조각에서만 완성, 재전송 조각 이중append 없음.
- e2e(가상+실측): 설명 300자 배포 → 웹 미리보기와 판넬이 같은 내용/줄바꿈.

## 5. 참고
- 현재 송신 경로: `deploy_service.build_packet_plan` → `link.request(..., expect=ACK)` (조각 하나씩).
- 멀티라인 렌더는 별건: [[HANDOFF_MULTILINE]] (이게 되어야 긴 텍스트가 여러 줄로 보인다).
- 이 기능은 "설명 더 길게"가 실제로 필요할 때만 — 66자로 충분하면 우선순위 낮음.
