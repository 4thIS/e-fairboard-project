// 12.48" 패널 버전 판별 — 3색 (B) V2 드라이버로 4분면 무늬 + 빨간 띠를 그린다.
// 판정: ① 검정이 진해지고 빨간 띠가 빨갛게 나오면 → (B) V2 패널 확정 (이 드라이버 채택)
//       ② 여전히 회색이거나 이상하면 → 다른 원인(전원 등) 추적
#include <Arduino.h>
#include "ws1248b/DEV_Config.h"
#include "ws1248b/EPD_12in48b.h"

// 사분면 스트리밍 순서/폭은 흑백 드라이버와 동일: M1(좌하,81B) S1(우하,82B) M2(우상,82B) S2(좌상,81B)
static void sendQuad(void (*cmd1)(), void (*dat1)(UBYTE), void (*cmd2)(), void (*dat2)(UBYTE),
                     uint8_t bytes_w, uint8_t kind) {
    // 검정 채널(0x10): 1=흰, 0=검 — kind: 0=대각선 1=세로줄 2=가로줄 3=체스판
    cmd1();
    for (uint16_t y = 0; y < 492; y++)
        for (uint16_t x = 0; x < bytes_w; x++) {
            uint8_t b;
            switch (kind) {
                case 0: b = (((x + (y >> 3)) % 6) < 3) ? 0x00 : 0xff; break;
                case 1: b = ((x / 3) % 2) ? 0xff : 0x00; break;
                case 2: b = ((y / 24) % 2) ? 0xff : 0x00; break;
                default: b = (((x / 4) + (y / 32)) % 2) ? 0xff : 0x00; break;
            }
            dat1(b);
        }
    // 빨강 채널(0x13): 1=빨강 — 각 사분면 아래쪽 92줄(400~491)에 빨간 띠
    cmd2();
    for (uint16_t y = 0; y < 492; y++)
        for (uint16_t x = 0; x < bytes_w; x++) dat2((y >= 400) ? 0xff : 0x00);
}

void setup() {
    Serial.begin(115200);
    delay(300);
    Serial.println("[wsb1248] DEV_ModuleInit");
    DEV_ModuleInit();
    Serial.println("[wsb1248] EPD_12in48B_Init (3색 V2 초기화)");
    EPD_12in48B_Init();
    Serial.println("[wsb1248] 무늬+빨간띠 전송");
    const uint32_t t0 = millis();
    sendQuad(EPD_12in48B_cmd1M1, EPD_12in48B_data1M1, EPD_12in48B_cmd2M1, EPD_12in48B_data2M1, 81, 0);
    sendQuad(EPD_12in48B_cmd1S1, EPD_12in48B_data1S1, EPD_12in48B_cmd2S1, EPD_12in48B_data2S1, 82, 1);
    sendQuad(EPD_12in48B_cmd1M2, EPD_12in48B_data1M2, EPD_12in48B_cmd2M2, EPD_12in48B_data2M2, 82, 2);
    sendQuad(EPD_12in48B_cmd1S2, EPD_12in48B_data1S2, EPD_12in48B_cmd2S2, EPD_12in48B_data2S2, 81, 3);
    Serial.println("[wsb1248] 갱신 시작 (busy 로그 주시)");
    EPD_12in48B_TurnOnDisplay();
    Serial.printf("[wsb1248] 갱신 완료 — %lums\n", (unsigned long)(millis() - t0));
    EPD_12in48B_Sleep();
    Serial.println("[wsb1248] done — 검정 진하기/빨간 띠 여부 확인");
}

void loop() { delay(1000); }
