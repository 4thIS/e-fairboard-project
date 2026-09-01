# 노드 펌웨어 인수인계 — 전체 초기화(RESET) 브로드캐스트

> **한 줄:** 서버가 행사 종료 때 **브로드캐스트 RESET(0x15)** 을 쏘면, 모든 노드가 동시에
> **기본(대기) 화면**으로 돌아가야 한다. 지금은 **노드가 0x15를 몰라서 패킷을 버린다.**
>
> - 대상 펌웨어: `node/src/main_hat1248.cpp` (최신 12.48" (B) V2 3색) @ `main`
> - 담당: **hm** (펌웨어). ①②는 공용 프로토콜이라 jp(PROTOCOL 주관)와 값만 확인.
> - 서버·웹은 완료(main). **노드 4곳만** 손대면 끝난다.

---

## 0. 현황 — 왜 지금 실제로 동작 안 하나

**서버·웹은 다 됨(main):**
- `server/.../protocol/packet.py` — `MsgType.RESET = 0x15`
- `server/.../protocol/link.py` — `broadcast(type, dst=0xFF, repeat=3, gap=0.3s)` **ACK 대기 없음(fire-and-forget)**
- `POST /api/nodes/reset` + 대시보드 헤더 **"전체 초기화"** 버튼 → 브로드캐스트 발사

**진짜 원인 — C++ 프로토콜이 0x15를 모른다:**
- `shared/lib/efb_protocol/include/efb/packet.h` enum과 `.../src/packet.cpp` 의 `is_known_type()` 에
  `RESET` 이 없다(0x14 다음 바로 0x20).
- 그래서 `decode()` 가 **`UNKNOWN_TYPE`** 을 반환 → `state_machine.cpp:13-16` 에서 패킷을 그냥
  버린다(`++err_cnt_; return;`). 서버가 3번 쏴도 노드가 **문전에서 버린다.**

**⚠ 옛 인수인계서 정정:** "브로드캐스트 수신을 허용하라"는 **이미 되어 있다** —
`state_machine.cpp:17` 이 `p.dst == efb::BROADCAST` 를 통과시킨다. 추가 작업 불필요.

---

## 1. 할 일 — 딱 4곳

### ① 프로토콜 enum에 RESET 추가
`shared/lib/efb_protocol/include/efb/packet.h` (28행 부근)
```cpp
    IMG_FRAG = 0x14,
    RESET    = 0x15,   // 브로드캐스트 전체 초기화 (ACK 없음) — 서버 packet.py 와 동일 값
    ACK      = 0x20,
```

### ② `is_known_type()` 에 RESET 추가
`shared/lib/efb_protocol/src/packet.cpp` (30행 부근)
```cpp
        case IMG_FRAG:
        case RESET:        // ← 이게 없으면 decode() 가 계속 UNKNOWN_TYPE 로 버린다
            return true;
```

### ③ 대기화면 렌더 훅 추가 (상태머신이 부를 수 있게)
`boot_screen()` 은 `main_hat1248.cpp` 의 `EpdDisplay` 에만 있고 `IDisplay` 인터페이스엔 없어서
하드웨어 비의존 상태머신이 못 부른다. 인터페이스를 한 줄 넓힌다.

`node/lib/node_core/include/node/state_machine.h` — `IDisplay`:
```cpp
struct IDisplay {
    virtual ~IDisplay() = default;
    virtual void render(const DisplayState& s, uint8_t refresh_mode) = 0;
    virtual void render_standby() = 0;   // RESET → 기본/대기 화면
};
```

`node/src/main_hat1248.cpp` — `EpdDisplay` 에 구현(기존 `boot_screen` 재사용):
```cpp
    void render_standby() override { boot_screen(EFB_NODE_ID); }
```
> `boot_screen` 은 이미 "노드 0xNN — 수신 대기 중 (12.48")" 빨강밴드+종이색 글자 화면이라
> 그대로 대기 화면으로 쓴다. 빨강 플레인 배선·knockout 재확인도 겸한다.
>
> **왜 `committed_` 만 비우고 `render()` 하면 안 되나:** template_id 가 -1 이면 `render()` 가
> `find_template` null 로 조기 리턴 → **화면이 안 지워지고 옛 내용이 남는다.** 전용 standby 렌더가 필요.

### ④ 상태머신에서 RESET 처리
`node/lib/node_core/src/state_machine.cpp` — `on_radio_bytes()`, `p.dst` 필터 통과 직후
(PING/STATUS_REQ 조회 분기와 같은 자리, **일반 경로 dedup·apply·ACK 앞에서** 가로챈다):
```cpp
    if (p.type == efb::RESET) {
        if (!standby_) {                 // 반복 3회 → 이미 대기면 재렌더 생략(~35초 절약)
            staged_    = DisplayState{};
            committed_ = DisplayState{};
            display_.render_standby();   // 블로킹 ~35초
            standby_ = true;
        }
        return;                          // ACK 없음 — 서버는 dst=0xFF fire-and-forget
    }
```
- 멤버 추가: `bool standby_ = false;`
- `commit_staged()` 로 새 내용을 반영할 때 `standby_ = false;` 로 되돌린다.

> **반복 dedup 주의:** `link.broadcast()` 는 3회를 **각각 다른 SEQ**(`_next_seq()`)로 보낸다.
> 그래서 기존 SEQ 기반 멱등(`last_handled_seq_`)이 **안 통한다** → 위처럼 `standby_` 플래그로 막는다.

---

## 2. 검증

**native 단위테스트** (`node/test/test_node_sm/test_main.cpp` 에 케이스 추가):
- RESET 브로드캐스트를 deliver → `committed_` 비워지고 `render_standby()` **1회** 호출,
  **ACK 미전송**(mock radio count 불변) 확인.
- 같은 RESET 3회 반복 → `render_standby()` 는 **1회만**(standby_ 가드).
- `pio test -e native` 통과.

**실측:**
- 서버/웹 헤더 **"전체 초기화"** → 확인 → 두 노드가 **동시에** "수신 대기 중" 화면으로.
- 서버 응답 `{ok:true, broadcast:true, nodes:2}`, 판넬이 대기 화면.
- 브로드캐스트라 한 번 발사로 전 노드가 같이 바뀌는지(순차 아님) 확인.

---

## 3. 손대지 말 것 / 참고
- 서버·웹 완료 — **노드만** 남음.
- 폰트·빨강 플레인·장식·세로 회전·`boot_screen` 렌더 로직: 그대로.
- 프로토콜 값 `0x15` 는 서버 `packet.py` 가 정본 — C++ enum 은 **동기화만**.
- 관련 서버 코드(참고): `app/protocol/packet.py`(RESET), `link.py::broadcast()`,
  `routers/nodes.py::reset_all` (`POST /api/nodes/reset`).
