// e-Paper 디스플레이 진단 테스트 (별도 env: disptest)
// 부팅 즉시 전체화면 검정→흰색→빨강→흰색을 칠하고 각 단계 타이밍을 로그로 찍는다.
// 화면이 또렷하면 패널 정상(전원/접촉이 원인이었던 것), 흐릿/번짐이면 전원·FPC 계속 의심.
//   pio run -e disptest -t upload   (upload_port=COM6)
//   pio device monitor -p COM6
#include <Arduino.h>
#include <SPI.h>
#include <GxEPD2_3C.h>

#define EPD_BUSY 25
#define EPD_RST  26
#define EPD_DC   27
#define EPD_CS   15
#define EPD_SCK  13
#define EPD_MOSI 14

GxEPD2_3C<GxEPD2_750c_Z08, GxEPD2_750c_Z08::HEIGHT / 2> display(
    GxEPD2_750c_Z08(EPD_CS, EPD_DC, EPD_RST, EPD_BUSY));

static void fillColor(uint16_t color, const char* name) {
  Serial.printf("\n>>> %s 채우기 시작 (t=%lums)\n", name, millis());
  unsigned long t0 = millis();
  display.setFullWindow();
  display.firstPage();
  do { display.fillScreen(color); } while (display.nextPage());
  Serial.printf("<<< %s 완료 (소요 %lums)\n", name, millis() - t0);
  delay(2500);
}

void setup() {
  Serial.begin(115200);
  delay(800);
  Serial.println("\n[DISPTEST] 시작 — 핀 CS15 DC27 RST26 BUSY25 SCK13 MOSI14");
  pinMode(EPD_BUSY, INPUT);
  Serial.printf("[DISPTEST] 초기 BUSY 핀 = %d\n", digitalRead(EPD_BUSY));

  SPI.begin(EPD_SCK, -1, EPD_MOSI, EPD_CS);
  display.init(115200);           // 진단 로그(_PowerOn/_Update_Full) 활성
  display.setRotation(0);
  Serial.println("[DISPTEST] display.init 완료 — 색 채우기 시작");

  fillColor(GxEPD_BLACK, "검정");
  fillColor(GxEPD_WHITE, "흰색");
  fillColor(GxEPD_RED,   "빨강");
  fillColor(GxEPD_WHITE, "흰색(마무리)");

  Serial.println("[DISPTEST] 전체 완료. 화면이 또렷했으면 패널 정상.");
}

void loop() {}
