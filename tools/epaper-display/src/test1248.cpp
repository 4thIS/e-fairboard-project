// 12.48"(1304x984, B/W 듀얼패널) 4분면 브링업 테스트 — HANDOFF_12in48 §5-1.
// 배선: docs 점퍼 22가닥 중 패널 16가닥 (1248_full_wiring.jpg). LoRa는 이 테스트에서 안 씀.
// 판정: 화면에 테두리+십자+대각선, 사분면마다 큰 숫자 1~4. 안 나오는 숫자의 사분면이
//       배선/서브패널 문제 (1=좌상 2=우상 3=좌하 4=우하).
#include <Arduino.h>
#include <GxEPD2_BW.h>

static constexpr int16_t PIN_SCK = 13, PIN_MISO = 12, PIN_MOSI = 14;
static constexpr int16_t CS_M1 = 23, CS_S1 = 22, CS_M2 = 21, CS_S2 = 19;
static constexpr int16_t DC1 = 25, DC2 = 27, RST1 = 26, RST2 = 5;
static constexpr int16_t BUSY_M1 = 34, BUSY_S1 = 35, BUSY_M2 = 36, BUSY_S2 = 39;

GxEPD2_BW<GxEPD2_1248, GxEPD2_1248::HEIGHT / 4> display(
    GxEPD2_1248(PIN_SCK, PIN_MISO, PIN_MOSI, CS_M1, CS_S1, CS_M2, CS_S2,
                DC1, DC2, RST1, RST2, BUSY_M1, BUSY_S1, BUSY_M2, BUSY_S2));

void setup() {
    Serial.begin(115200);
    delay(300);
    Serial.println("[test1248] init");
    display.init(115200);  // 진단 로그 켜기 — busy 시간이 시리얼에 찍힌다
    display.setRotation(0);
    Serial.println("[test1248] draw (전체 갱신 ~20-30초)");
    display.setFullWindow();
    display.firstPage();
    do {
        display.fillScreen(GxEPD_WHITE);
        display.drawRect(0, 0, 1304, 984, GxEPD_BLACK);
        display.drawRect(1, 1, 1302, 982, GxEPD_BLACK);
        display.drawLine(652, 0, 652, 983, GxEPD_BLACK);
        display.drawLine(0, 492, 1303, 492, GxEPD_BLACK);
        display.drawLine(0, 0, 1303, 983, GxEPD_BLACK);
        display.drawLine(1303, 0, 0, 983, GxEPD_BLACK);
        display.setTextColor(GxEPD_BLACK);
        display.setTextSize(10);
        display.setCursor(280, 180); display.print("1");
        display.setCursor(960, 180); display.print("2");
        display.setCursor(280, 720); display.print("3");
        display.setCursor(960, 720); display.print("4");
        display.setTextSize(4);
        display.setCursor(430, 470); display.print("E-FairBoard 12.48");
    } while (display.nextPage());
    Serial.println("[test1248] done — 사분면 1/2/3/4 모두 보이는지 확인");
    display.hibernate();
}

void loop() { delay(1000); }
