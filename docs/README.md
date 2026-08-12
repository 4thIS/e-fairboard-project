# E-FairBoard 문서

LoRa 기반 중앙제어 e-Paper 전시/게시 팜플렛 시스템 — 설계 문서 모음.

> 2026 임베디드 SW 경진대회 (자유공모) · 팀 4This (우진·준표·효민)

## 문서 목록
| 문서 | 내용 |
|------|------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | 시스템 구조, 역할 분담, 마일스톤 |
| [PROTOCOL.md](PROTOCOL.md) | LoRa 패킷 프로토콜 스펙 (v0.2) |
| [HARDWARE.md](HARDWARE.md) | 부품 BOM, ESP32 핀맵, 전원 결선 |
| [CIRCUIT.md](CIRCUIT.md) | 노드 배선 가이드 — 회로별 결선표·전원 회로 |

## 한 줄 요약  〔v0.3 하드웨어 확정 2026-07-28 반영〕
- 서버(노트북)+SX1262 HAT 직결 1 + e-Paper 노드 2 (저예산 MVP, **게이트웨이 ESP32 없음**)
- MCU+LoRa: **SX1262+ESP32-S3 통합보드**(예: LILYGO T3S3 / Heltec WiFi LoRa32 V3, 모델 미확정) /
  디스플레이: **Waveshare 12.48" 1304×984 흑백 듀얼패널**(MCP23017 I2C 익스팬더 경유)
- 통신: 920MHz(KR) LoRa, 템플릿 기반 중앙제어, 텍스트+QR 전송

## 리포 구조
```
gateway/   # (v0.2 에서 폐지 — 서버가 HAT 직결. 기존 펌웨어는 준표가 정리)
node/      # 통합보드 노드 펌웨어 (SX1262 온보드 SPI + MCP23017 + e-Paper 12.48" + 딥슬립)
server/    # FastAPI 서버 + Vue 대시보드 (HAT 시리얼 브리지, 메모리+JSON, 인메모리 예약)
docs/      # 설계 문서 (본 폴더)
```

## 브랜치
`main`(통합) · `wj`(우진) · `jp`(준표) · `hm`(효민) — 1인 1브랜치, PR로 main 통합.
