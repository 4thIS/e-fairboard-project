// 12.48" 배선 진단 프로브 — 서브패널 4개를 개별로 깨워 BUSY 반응·전압을 측정한다.
// 해석:
//   BUSY 전압 ~3300mV = 모듈에 전원 공급됨(레벨시프터가 HIGH 구동) / ~0 또는 널뛰기 = 전원·배선 의심
//   power-on 후 BUSY 토글 = 해당 서브패널 살아있음
#include <Arduino.h>
#include <SPI.h>

static constexpr int16_t PIN_SCK = 13, PIN_MISO = 12, PIN_MOSI = 14;
static constexpr int16_t CS_M1 = 23, CS_S1 = 22, CS_M2 = 21, CS_S2 = 19;
static constexpr int16_t DC1 = 25, DC2 = 27, RST1 = 26, RST2 = 5;
static constexpr int16_t BUSY_M1 = 34, BUSY_S1 = 35, BUSY_M2 = 36, BUSY_S2 = 39;

static const int16_t CS_ALL[4] = {CS_M1, CS_S1, CS_M2, CS_S2};
static const int16_t BUSY_ALL[4] = {BUSY_M1, BUSY_S1, BUSY_M2, BUSY_S2};
static const char* NAMES[4] = {"M1", "S1", "M2", "S2"};

static void printBusy(const char* tag) {
    Serial.printf("[probe] %s — BUSY(M1,S1,M2,S2) = %d %d %d %d | mV: %u %u %u %u\n", tag,
                  digitalRead(BUSY_M1), digitalRead(BUSY_S1), digitalRead(BUSY_M2),
                  digitalRead(BUSY_S2), analogReadMilliVolts(BUSY_M1),
                  analogReadMilliVolts(BUSY_S1), analogReadMilliVolts(BUSY_M2),
                  analogReadMilliVolts(BUSY_S2));
}

static void spiCmd(int16_t cs, int16_t dc, uint8_t cmd) {
    SPI.beginTransaction(SPISettings(4000000, MSBFIRST, SPI_MODE0));
    digitalWrite(dc, LOW);
    digitalWrite(cs, LOW);
    SPI.transfer(cmd);
    digitalWrite(cs, HIGH);
    digitalWrite(dc, HIGH);
    SPI.endTransaction();
}

void setup() {
    Serial.begin(115200);
    delay(300);
    Serial.println("[probe] 시작");

    for (int i = 0; i < 4; ++i) { pinMode(CS_ALL[i], OUTPUT); digitalWrite(CS_ALL[i], HIGH); }
    pinMode(DC1, OUTPUT); digitalWrite(DC1, HIGH);
    pinMode(DC2, OUTPUT); digitalWrite(DC2, HIGH);
    pinMode(RST1, OUTPUT); digitalWrite(RST1, HIGH);
    pinMode(RST2, OUTPUT); digitalWrite(RST2, HIGH);
    for (int i = 0; i < 4; ++i) pinMode(BUSY_ALL[i], INPUT);
    SPI.begin(PIN_SCK, PIN_MISO, PIN_MOSI, CS_M1);

    delay(100);
    printBusy("리셋 전");
    digitalWrite(RST1, LOW); digitalWrite(RST2, LOW);
    delay(200);
    printBusy("RST LOW 중");
    digitalWrite(RST1, HIGH); digitalWrite(RST2, HIGH);
    delay(50);
    printBusy("RST HIGH 직후");
    delay(300);
    printBusy("RST 후 300ms");

    // 서브패널별 power-on(0x04) → BUSY 반응 관찰 → power-off(0x02)
    for (int i = 0; i < 4; ++i) {
        const int16_t dc = (i < 2) ? DC1 : DC2;
        Serial.printf("[probe] %s power-on(0x04) 전송, BUSY_%s 3초 관찰:\n", NAMES[i], NAMES[i]);
        const int before = digitalRead(BUSY_ALL[i]);
        spiCmd(CS_ALL[i], dc, 0x04);
        int changes = 0, last = before;
        const uint32_t t0 = millis();
        while (millis() - t0 < 3000) {
            const int v = digitalRead(BUSY_ALL[i]);
            if (v != last) { ++changes; last = v; }
            delayMicroseconds(200);
        }
        Serial.printf("[probe]   시작=%d 끝=%d 토글횟수=%d mV=%u → %s\n", before, last, changes,
                      analogReadMilliVolts(BUSY_ALL[i]),
                      changes > 0 ? "반응 있음(살아있음)" : "반응 없음");
        spiCmd(CS_ALL[i], dc, 0x02);  // power off
        delay(300);
    }
    Serial.println("[probe] 완료");
}

void loop() { delay(1000); }
