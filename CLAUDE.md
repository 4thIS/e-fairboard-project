# CLAUDE.md — E-FairBoard 협업 헌법

> **이 문서는 이 프로젝트에 참여하는 모든 사람과 모든 AI가 따르는 협업 헌법이다.**
>
> - 사람이든 AI든, 이 저장소에서 어떤 작업을 시작하기 전에 **반드시 이 문서를 먼저 읽는다.**
> - **Claude Code는 프로젝트 루트의 이 파일을 세션 시작 시 자동으로 로드한다.** 다른 AI 도구를 사용할 때는 세션 시작 시 이 파일을 컨텍스트에 직접 포함시킨다.
> - 개인 전역 설정(`~/.claude/CLAUDE.md`)과 이 문서가 충돌하는 경우, **항상 이 문서가 우선한다.**

## 1. 프로젝트 개요

**E-FairBoard** — LoRa 기반 중앙제어 e-Paper 전시/게시 팜플렛 시스템 (2026 임베디드 SW 경진대회 자유공모, 팀 4This).

종이 포스터/팜플렛을 e-Paper 노드로 대체한다. 관리자가 웹 대시보드에서 콘텐츠를 작성·예약하면, FastAPI 서버가 USB 시리얼로 연결된 ESP32 LoRa 게이트웨이를 통해 각 e-Paper 노드에 변경분만 전송한다. 노드는 화면을 갱신하고 성공 여부·배터리 상태를 보고한다.

- 구성: 서버(노트북, FastAPI+Vue) 1 + LoRa 게이트웨이(ESP32) 1 + e-Paper 노드(ESP32) 2
- 통신: 920MHz(KR) LoRa, 템플릿 기반 텍스트+QR 전송, ACK·재전송
- 상세 설계 문서: [docs/](docs/README.md) — 시스템 구조([ARCHITECTURE.md](docs/ARCHITECTURE.md)), 패킷 프로토콜([PROTOCOL.md](docs/PROTOCOL.md)), 하드웨어([HARDWARE.md](docs/HARDWARE.md)), 웹 파트 설계([docs/web/](docs/web/))

## 2. 역할 분담

| 담당 | 브랜치 | 영역 |
|------|:---:|------|
| 우진 (팀장) | `wj` | 시스템 통합 + 게이트웨이 펌웨어(`gateway/`) + 패킷 프로토콜 |
| 준표 | `jp` | 서버·대시보드(`server/`, FastAPI+Vue) + 시리얼 브리지 + 상태·예약 |
| 효민 | `hm` | 노드 펌웨어(`node/`) — e-Paper 렌더 + QR + 딥슬립 + 배터리 |

## 3. 작업 흐름 (Git)

1. **각자 자신의 브랜치에서만 작업한다** — 우진=`wj`, 준표=`jp`, 효민=`hm`. 다른 사람의 브랜치나 main에서 작업하지 않는다.
2. **main에 직접 push하지 않는다.** 자신의 브랜치에 커밋한 뒤 **PR(Merge Request)만 생성**한다.
3. **main으로의 머지는 팀장만 진행한다.** PR 생성자는 머지하지 않고 팀장의 리뷰·머지를 기다린다.
4. AI(Claude Code 등)로 작업할 때도 위 규칙이 동일하게 적용된다 — AI에게 main으로 push시키거나 타인의 영역을 수정하게 하지 않는다.

## 4. 절대 하지 말 것

- **`.env`, `*.pem`, `*.key` 커밋 금지** — .gitignore와 pre-commit hook이 차단
- **main 브랜치 직접 push 금지** — Protected Branches로 차단
- **타 개발 영역 코드 임의 수정 금지** — 필요 시 담당자와 협의
- **`git push --force`, `git reset --hard` 금지**

---

- 생성일시: 2026-07-08 13:17 (KST)
- 수정일시: 2026-07-08 13:17 (KST)
