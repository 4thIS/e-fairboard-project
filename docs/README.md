# E-FairBoard 문서

LoRa 기반 중앙제어 e-Paper 전시/게시 팜플렛 시스템 — 설계 문서 모음.

> 2026 임베디드 SW 경진대회 (자유공모) · 팀 4This (우진·준표·효민)

## 문서 목록
| 문서 | 내용 |
|------|------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | 시스템 구조, 역할 분담, 마일스톤 |
| [PROTOCOL.md](PROTOCOL.md) | LoRa 패킷 프로토콜 스펙 (v0.1) |
| [HARDWARE.md](HARDWARE.md) | 부품 BOM, ESP32 핀맵, 전원 결선 |

## 한 줄 요약
- 서버(노트북) 1 + LoRa 게이트웨이 1 + e-Paper 노드 2 (저예산 MVP)
- MCU: ESP32 통일 / LoRa: Waveshare Core1262(SX1262, SPI) / 디스플레이: e-Paper 2.9"
- 통신: 920MHz(KR) LoRa, 템플릿 기반 중앙제어, 텍스트+QR 전송

## 리포 구조 (제안)
```
gateway/   # ESP32 게이트웨이 펌웨어 (RadioLib + USB 시리얼)
node/      # ESP32 노드 펌웨어 (RadioLib + GxEPD2 + 딥슬립)
server/    # FastAPI 서버 + Vue 대시보드 (시리얼 브리지, SQLite, 예약)
docs/      # 설계 문서 (본 폴더)
```

## 브랜치
`main`(통합) · `wj`(우진) · `jp`(준표) · `hm`(효민) — 1인 1브랜치, PR로 main 통합.
