# 하드웨어 — BOM · 핀맵 · 전원

대상: 2노드 MVP (게이트웨이 1 + 노드 2 + 예비 1). ESP32 통일, Core1262(SX1262 SPI).

## 1. 부품 BOM
| # | 품목 | 사양 | 수량 |
|---|------|------|:---:|
| 1 | ESP32 DevKitC | WROOM-32, CP2102, 38pin | 4 |
| 2 | Waveshare Core1262 (SX1262) | **915M**, SPI, 안테나 동봉확인 | 4 |
| 3 | 915MHz 안테나 | IPEX/스프링 (미동봉 시) | 0~4 |
| 4 | e-Paper 2.9" | 296×128, SPI, 부분갱신 | 2 |
| 5 | 18650 배터리(보호회로) | 3.7V 2000~3000mAh | 2 |
| 6 | 18650 홀더 1셀 | | 2 |
| 7 | TP4056 충전모듈 | USB-C, 보호회로 | 2 |
| 8 | MT3608 부스트(5V) | 노드 18650→5V VIN | 2 |
| 9 | 0.96" OLED (선택) | I2C, 게이트웨이 상태 | 0~1 |
| 10 | 점퍼선·만능기판·데이터USB | | 1세트 |
| 11 | 470µF 캐패시터 등 | LoRa TX 디커플링 | 1세트 |

- 수량 근거: ESP32·Core1262 = 게이트웨이1+노드2+예비1. e-Paper·배터리계열 = 노드2(게이트웨이 USB급전).
- ⚠️ Core1262는 **915M 변형** 선택(868M은 920 정합 손실), 안테나 **동봉 여부 확인**.

## 2. 공유 SPI 버스 (VSPI)
LoRa·e-Paper 모두 SPI → 버스 공유, CS만 분리. e-Paper는 쓰기 전용(MISO 미사용).

| 신호 | ESP32 GPIO | 연결 |
|------|:---:|------|
| SCK  | 18 | Core1262 SCK + e-Paper CLK |
| MOSI | 23 | Core1262 MOSI + e-Paper DIN |
| MISO | 19 | Core1262 MISO (e-Paper 미연결) |

## 3. 노드 핀맵 (ESP32 + Core1262 + e-Paper)
### LoRa Core1262 (SX1262)
| 모듈 핀 | ESP32 GPIO |
|------|:---:|
| NSS(CS) | 5 |
| RST | 4 |
| BUSY | 22 |
| DIO1(IRQ) | 21 |
| SCK/MOSI/MISO | 18/23/19 (공유) |
| VCC/GND | 3V3/GND |
| ANT | 안테나 (**무안테나 송신 금지**) |

### e-Paper 2.9" (Waveshare SPI)
| 모듈 핀 | ESP32 GPIO |
|------|:---:|
| CS | 17 |
| DC | 25 |
| RST | 26 |
| BUSY | 27 |
| CLK/DIN | 18/23 (공유) |
| VCC/GND | 3V3/GND |

### 보조
| 기능 | ESP32 GPIO | 비고 |
|------|:---:|------|
| 배터리 ADC | 34 | ADC1, 입력전용, 100k/100k 분압 |
| 상태 LED | 2 | 온보드 |

### RadioLib / GxEPD2 핀 선언 (예시)
```cpp
// SX1262: NSS, DIO1, RST, BUSY
SX1262 radio = new Module(5, 21, 4, 22);
// e-Paper: CS=17, DC=25, RST=26, BUSY=27
```

## 4. 게이트웨이 핀맵
- LoRa 결선은 노드와 동일. e-Paper 없음(17/25/26/27 비움).
- 서버 연결 = USB 시리얼(내장 USB-UART), 별도 핀 불필요.
- 선택 OLED(I2C): SDA=32, SCL=33.

## 5. 전원 결선 (노드)
```
18650(3.0~4.2V) ─ TP4056 ─ MT3608(부스트 5V) ─ ESP32 VIN(5V)
                                              └ 470µF 벌크캡(LoRa TX 돌입전류)
ESP32 3V3 ─ Core1262 VCC, e-Paper VCC ;  공통 GND
```
- ⚠️ **DevKitC 딥슬립 수 mA**(AMS1117+CP2102) → "2주 동작"엔 베어 WROOM 권장. 데모/MVP는 DevKitC OK.
- ⚠️ **LoRa TX 돌입전류(~120mA)** → Core1262 VCC 근처 470µF+0.1µF 디커플링.
- 저전력 대안: 부스트 대신 저드롭 LDO(AP2112-3.3) 직접 3V3 급전.

## 6. 핀 충돌 점검
- LoRa: 5,18,23,19,4,22,21 / e-Paper: 17,25,26,27(+공유 18,23) → **충돌 없음**.
- 회피: GPIO0/2(부팅·LED)/12/15(스트래핑) 출력 미사용, 6~11(내장 Flash) 미사용.
- 배터리 ADC는 Wi-Fi와 충돌 없는 **ADC1(GPIO34)** 사용.

## 7. 조립 순서
1. ESP32 단독 부팅 → 2. Core1262 + RadioLib 송수신(안테나) → 3. e-Paper + GxEPD2 출력
→ 4. SPI 공유 동시 동작 → 5. 배터리/부스트 → 6. 딥슬립 전류 측정 → 7. 케이스.
