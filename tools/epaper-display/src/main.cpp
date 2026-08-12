// e-Paper 표시 모듈 테스트베드 — 시리얼로 받은 UTF-8 텍스트를 7.5" 패널에 표시한다.
//
// 지금은 "ESP32가 받은 값"을 시리얼(115200)로 흉내 내서 테스트하고,
// 나중에 준표 펌웨어의 LoRa 수신부가 renderMessage()를 그대로 호출하면 된다.
//
// 패널: GxEPD2_750c_Z08 (7.5" 3색, 800x480) — 전체 갱신 15~20초 걸리는 게 정상.

#include <Arduino.h>
#include <SPI.h>
#include <GxEPD2_3C.h>
#include "fonts/KoreanFont.h"

// Waveshare e-Paper ESP32 Driver Board 고정 배선 (보드에 납땜된 경로라 바꿀 수 없음)
#define EPD_BUSY 25
#define EPD_RST  26
#define EPD_DC   27
#define EPD_CS   15
#define EPD_SCK  13
#define EPD_MOSI 14

GxEPD2_3C<GxEPD2_750c_Z08, GxEPD2_750c_Z08::HEIGHT / 2> display(
    GxEPD2_750c_Z08(EPD_CS, EPD_DC, EPD_RST, EPD_BUSY));

static const int16_t MARGIN = 24;
static const int16_t LINE_H = 30;              // NG20(20px) + 행간
static const int16_t MAX_X  = 800 - MARGIN;
static const int16_t MAX_Y  = 480 - MARGIN;

// UTF-8 텍스트를 자동 줄바꿈으로 그린다. '\n' 지원, 화면 아래를 넘으면 잘라냄.
static void drawWrapped(const char* text, int16_t x0, int16_t y0,
                        uint16_t color = GxEPD_BLACK) {
    int16_t cx = x0, cy = y0;
    const uint8_t* p = (const uint8_t*)text;
    while (*p) {
        uint32_t cp = ngNextCP(p);
        if (cp == '\r') continue;
        if (cp == '\n' || cx + NG20_W > MAX_X) {
            cx = x0;
            cy += LINE_H;
            if (cy + NG20_H > MAX_Y) return;
            if (cp == '\n') continue;
        }
        ngDrawChar(display, cp, cx, cy, color);
        cx += NG20_W;
    }
}

// 받은 텍스트 한 건을 화면 전체에 표시한다 — LoRa 수신부가 부를 진입점.
void renderMessage(const char* text) {
    display.setFullWindow();
    display.firstPage();
    do {
        display.fillScreen(GxEPD_WHITE);
        ngPrintLine(display, "E-FairBoard 수신 테스트", MARGIN, MARGIN, MAX_X, GxEPD_RED);
        drawWrapped(text, MARGIN, MARGIN + 2 * LINE_H);
    } while (display.nextPage());
}

void setup() {
    Serial.begin(115200);
    delay(500);
    Serial.println("[epaper] init 시작");
    SPI.begin(EPD_SCK, -1, EPD_MOSI, EPD_CS);
    display.init(115200);
    display.setRotation(0);
    Serial.println("[epaper] init 완료 — 첫 화면 그리는 중 (15~20초)");
    renderMessage("수신 대기 중...\n\n시리얼(115200)로 텍스트를 보내면 이 자리에 표시됩니다.");
    Serial.println("[epaper] 준비 완료 — 텍스트 한 줄 보내면 화면에 띄웁니다");
}

void loop() {
    static char buf[512];
    static size_t len = 0;
    while (Serial.available()) {
        char c = (char)Serial.read();
        if (c == '\n') {
            buf[len] = 0;
            if (len > 0) {
                Serial.printf("[epaper] 렌더링 시작: %s\n", buf);
                renderMessage(buf);
                Serial.println("[epaper] 렌더링 완료");
            }
            len = 0;
        } else if (c != '\r' && len < sizeof(buf) - 1) {
            buf[len++] = c;
        }
    }
}
