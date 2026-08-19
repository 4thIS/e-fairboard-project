// 12.48" 결정판 테스트 — Waveshare 공식 드라이버(esp32-epd-12in48)를 우리 핀으로 이식.
// 성공 = 화면 전체가 흰색으로 갱신됨(~20초). 실패 = 어느 컨트롤러에서 멈췄는지 로그에 남음.
#include <Arduino.h>
#include "ws1248/DEV_Config.h"
#include "ws1248/EPD_12in48.h"

void setup() {
    Serial.begin(115200);
    delay(300);
    Serial.println("[ws1248] DEV_ModuleInit");
    DEV_ModuleInit();
    Serial.println("[ws1248] EPD_12in48_Init (리셋+레지스터 설정)");
    EPD_12in48_Init();
    Serial.println("[ws1248] 4분면 무늬 갱신 시작 — 좌하=대각선 우하=세로줄 우상=가로줄 좌상=체스판");
    const uint32_t t0 = millis();
    EPD_12in48_TestPattern();
    Serial.printf("[ws1248] 갱신 완료 — %lums\n", (unsigned long)(millis() - t0));
    EPD_12in48_Sleep();
    Serial.println("[ws1248] done");
}

void loop() { delay(1000); }
