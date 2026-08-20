// e-Paper 노드 (ESP32 + Core1262 + e-Paper 2.9").
//
// 이 파일만 Arduino/RadioLib/GxEPD2 를 안다. 상태머신은 lib/node_core 에 하드웨어 의존 없이
// 있고 맥에서 테스트된다 (pio test -e native).
//
// MVP는 상시 수신 — 서버가 15초마다 STATUS_REQ 를 폴링하므로 딥슬립하면 응답할 수 없다.
// 딥슬립은 wake 윈도우와 서버 폴링 주기를 맞춰야 해서 범위 밖 (web-design.md §5.6).

#include <Arduino.h>
#include <GxEPD2_BW.h>
#include <RadioLib.h>
#include <qrcode.h>

#include <efb/packet.h>
#include <efb/ports.h>
#include <node/state_machine.h>
#include <node/templates.h>
#include <node/layout.h>
#include <node/text.h>

// 32px 한글 비트맵 (node/src/font_data.cpp — Neo둥근모 SIL OFL 1.1 파생, assets/OFL.txt).
// 완성형 전체 11,172자 + ASCII. 서브셋이 아니라 서버 입력 검증이 필요 없다 (이슈 #12).
extern const uint8_t EFB_HANGUL32[] PROGMEM;
extern const size_t EFB_HANGUL32_LEN;

#ifndef EFB_NODE_ID
#define EFB_NODE_ID 0x01  // 노드마다 다르게 — platformio.ini 의 build_flags 로 덮어쓴다
#endif

// HARDWARE.md §3: LoRa NSS=5, DIO1=21, RST=4, BUSY=22
static SX1262 radio = new Module(5, 21, 4, 22);

// HARDWARE.md §3: e-Paper CS=17, DC=25, RST=26, BUSY=27 (SPI는 18/23 공유)
static GxEPD2_BW<GxEPD2_290_T94, GxEPD2_290_T94::HEIGHT> epd(
    GxEPD2_290_T94(/*CS=*/17, /*DC=*/25, /*RST=*/26, /*BUSY=*/27));

static constexpr uint8_t BATT_ADC_PIN = 34;  // HARDWARE.md §3: ADC1, 100k/100k 분압

// PROTOCOL.md §1 (KR920)
static constexpr float FREQ_MHZ = 922.1f;
static constexpr float BW_KHZ = 125.0f;
static constexpr uint8_t SF = 9;
static constexpr uint8_t CR = 5;  // 4/5
static constexpr uint8_t SYNC_WORD = 0x12;
static constexpr int8_t TX_DBM = 14;  // TODO: KR920 법정 출력 한도 확정 (PROTOCOL.md §10)
static constexpr uint16_t PREAMBLE = 8;

static volatile bool rx_flag = false;

static void IRAM_ATTR on_dio1() { rx_flag = true; }

namespace {

class RadioOut : public efb::IRadioOut {
public:
    bool send(const uint8_t* data, size_t len) override {
        const int state = radio.transmit(const_cast<uint8_t*>(data), len);
        radio.startReceive();  // 반이중 — 송신 후 수신으로 되돌린다
        return state == RADIOLIB_ERR_NONE;
    }
};

class ArduinoClock : public efb::IClock {
public:
    uint32_t millis() override { return ::millis(); }
    void delay(uint32_t ms) override { ::delay(ms); }
};

class AdcBattery : public node::IBattery {
public:
    uint16_t read_mv() override {
        // 100k/100k 분압 → 실제 전압의 절반이 ADC로 들어온다.
        // TODO: 보드별 ADC 비선형 보정 — 하드웨어 도착 후 실측 캘리브레이션 필요.
        const uint32_t raw = analogReadMilliVolts(BATT_ADC_PIN);
        return static_cast<uint16_t>(raw * 2);
    }
};

// 32px 한글 비트맵 폰트 — PROGMEM. 완성형 전체(11,172자)라 서브셋 두부가 없다 (이슈 #12).
class ProgmemFont : public node::IGlyphSource {
public:
    bool glyph(uint32_t cp, uint8_t out[node::GLYPH_BYTES], uint8_t& advance_px) override {
        size_t index;
        if (cp >= 0x20 && cp <= 0x7E) {
            index = cp - 0x20;
            advance_px = 16;  // ASCII 반각
        } else if (cp >= 0xAC00 && cp <= 0xD7A3) {
            index = 95 + (cp - 0xAC00);  // ASCII 95자 다음
            advance_px = 32;             // 한글 전각
        } else {
            return false;
        }
        const size_t off = index * node::GLYPH_BYTES;
        if (off + node::GLYPH_BYTES > EFB_HANGUL32_LEN) return false;
        for (size_t i = 0; i < node::GLYPH_BYTES; ++i) {
            out[i] = pgm_read_byte(EFB_HANGUL32 + off + i);
        }
        return true;
    }
};

// GxEPD2 렌더. 이 호출은 블로킹이라 도는 동안(부분 ~1초 / 전체 ~3초) 노드는 무선을 못 듣는다.
// 서버는 총 4회 x T_ack 1.5초 = 6초를 기다리므로 전체갱신이 5.3초를 넘으면 배포가 실패한다.
// 하드웨어 도착 후 실측할 것 — 넘으면 COMMIT 전용 T_ack 을 우진과 협의해야 한다.
class EpdDisplay : public node::IDisplay, public node::ICanvas {
public:
    void pixel(int16_t x, int16_t y) override { epd.drawPixel(x, y, GxEPD_BLACK); }

    void render(const node::DisplayState& s, uint8_t refresh_mode) override {
        const node::TemplateDef* tpl = node::find_template(s.template_id);
        if (!tpl) return;

        if (refresh_mode == 1) {
            epd.setFullWindow();  // 템플릿 전환 — 고스팅 제거
        } else {
            epd.setPartialWindow(0, 0, epd.width(), epd.height());
        }

        epd.firstPage();
        do {
            epd.fillScreen(GxEPD_WHITE);

            for (uint8_t i = 0; i < tpl->field_count; ++i) {
                const node::FieldDef& f = tpl->fields[i];
                if (f.id >= node::MAX_FIELDS || !s.has_field[f.id]) continue;

                // 폭을 넘는 글자는 draw_utf8 이 잘라낸다 — 화면 밖으로 절대 안 나간다.
                // 서버가 max_bytes 로 막지만 ASCII는 반각이라 바이트당 폭이 한글보다 넓다
                // (ASCII 8px/B vs 한글 5.33px/B). 바이트 상한만으로는 못 막으므로 픽셀로 잰다.
                const uint8_t scale = node::scale_for(f.font_size);
                const int16_t avail = node::field_avail_w(f, tpl->qr, scale);
                node::draw_utf8(*this, font_, f.x, f.y, s.fields[f.id], scale, avail);
            }

            if (s.has_qr) draw_qr(s.qr_url, tpl->qr);
        } while (epd.nextPage());
    }

private:
    ProgmemFont font_;

    // QR은 URL 문자열만 받아 노드가 직접 렌더한다 — 대역폭 최소화 (PROTOCOL.md §4).
    void draw_qr(const char* url, const node::QrDef& box) {
        const size_t len = strlen(url);

        // 버전이 클수록 모듈이 촘촘해진다. e-Paper 박스가 작아 모듈당 2px 밑으로 떨어지면
        // 스캔이 안 된다. TODO: QR 버전 <-> URL 길이 상한을 우진과 확정 (미해결 항목).
        uint8_t version = 3;  // 29x29, ECC_LOW 기준 바이트 53
        if (len > 53) version = 5;
        if (len > 106) version = 8;
        if (len > 192) return;  // 이 박스에 담을 수 없다 — 그리지 않는다

        uint8_t buf[qrcode_getBufferSize(8)];
        QRCode qr;
        if (qrcode_initText(&qr, buf, version, ECC_LOW, url) != 0) return;

        const int16_t scale = box.size / qr.size;
        if (scale < 1) return;
        if (scale < 2) Serial.printf("[qr] %dpx/module — 스캔 실패 위험\n", scale);

        const int16_t drawn = scale * qr.size;
        const int16_t ox = box.x + (box.size - drawn) / 2;
        const int16_t oy = box.y + (box.size - drawn) / 2;

        for (uint8_t y = 0; y < qr.size; ++y) {
            for (uint8_t x = 0; x < qr.size; ++x) {
                if (!qrcode_getModule(&qr, x, y)) continue;
                epd.fillRect(ox + x * scale, oy + y * scale, scale, scale, GxEPD_BLACK);
            }
        }
    }
};

RadioOut radio_out;
ArduinoClock clock_;
AdcBattery battery;
EpdDisplay display;
node::StateMachine sm(EFB_NODE_ID, radio_out, clock_, display, battery);

}  // namespace

void setup() {
    Serial.begin(115200);

    epd.init(115200, /*initial=*/true, /*reset_duration=*/2, /*pulldown_rst_mode=*/false);
    epd.setRotation(1);  // 296x128 가로

    const int state = radio.begin(FREQ_MHZ, BW_KHZ, SF, CR, SYNC_WORD, TX_DBM, PREAMBLE);
    if (state != RADIOLIB_ERR_NONE) {
        while (true) {
            Serial.printf("radio.begin failed: %d\n", state);
            delay(2000);
        }
    }
    radio.setCRC(2);  // 하드웨어 CRC — 앱 CRC16과 이중 검증 (PROTOCOL.md §1)
    radio.setDio1Action(on_dio1);
    radio.startReceive();

    Serial.printf("[node 0x%02X] ready\n", EFB_NODE_ID);
}

void loop() {
    if (!rx_flag) return;
    rx_flag = false;

    uint8_t buf[efb::MAX_PACKET];
    const size_t len = radio.getPacketLength();
    if (len > 0 && len <= sizeof(buf) && radio.readData(buf, len) == RADIOLIB_ERR_NONE) {
        const int8_t rssi = static_cast<int8_t>(radio.getRSSI());
        sm.on_radio_bytes(buf, len, rssi);  // COMMIT이면 이 안에서 e-Paper가 돈다 (블로킹)
    }
    radio.startReceive();
}
