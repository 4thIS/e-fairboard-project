// e-Paper 노드 — UART LoRa HAT 변형 (임시 프로토타입 하드웨어).
//
// main.cpp(SPI Core1262 + 2.9")와 같은 node_core 상태머신을 쓰되, 하드웨어만 다르다:
//   - LoRa: Waveshare SX126X HAT (E22, UART 9600 투명/고정전송, M0/M1 GPIO 제어)
//   - e-Paper: Waveshare 7.5" (B) 3색 800x480, e-Paper ESP32 Driver Board 고정 배선
// 빌드: pio run -e hat75_node1 (main.cpp 대신 이 파일만 컴파일)
//
// 링크 프레이밍(PROTOCOL.md §7): 공중 페이로드 = COBS(논리패킷)+0x00.
// 전송 모드는 고정(fixed) 유지 — 서버(우진) 결정. 송신(ACK/PONG)은 프레임 앞에 봉투
// [ADDH ADDL CH] = [00 00 48](서버주소 0, 채널 72)을 붙인다. 봉투는 송신 HAT가 소비하고
// 공중으로 나가지 않으며, 수신은 봉투 없이 프레임만 UART로 들어온다(실측 확인).
// 부팅 시 HAT REG3가 0x43(고정)인지 확인·교정한다.

#include <Arduino.h>
#include <GxEPD2_3C.h>
#include <SPI.h>
#include <qrcode.h>

#include <efb/framing.h>
#include <efb/packet.h>
#include <efb/ports.h>
#include <node/layout.h>
#include <node/state_machine.h>
#include <node/templates.h>
#include <node/text.h>

// 16px 한글 비트맵 (gen_font_data.py 생성 — main.cpp와 공유).
extern const uint8_t EFB_HANGUL16[] PROGMEM;
extern const size_t EFB_HANGUL16_LEN;

#ifndef EFB_NODE_ID
#define EFB_NODE_ID 0x01
#endif

// ---- 임시 노드 하드웨어 (docs/CIRCUIT.md 배선 v4 / 드라이버보드 고정 경로) ----
// e-Paper ESP32 Driver Board: 패널 배선이 보드에 납땜돼 있어 바꿀 수 없다.
static constexpr uint8_t EPD_SCK = 13, EPD_MOSI = 14, EPD_CS = 15;
static constexpr uint8_t EPD_BUSY = 25, EPD_RST = 26, EPD_DC = 27;
// SX126X HAT: UART2 + 모드핀. 실크 P3=M0, P2=M1 (BCM 아님 — WiringPi 번호, HARDWARE.md).
static constexpr uint8_t LORA_RX = 16, LORA_TX = 17;
static constexpr uint8_t LORA_M0 = 32, LORA_M1 = 33;
static constexpr uint32_t LORA_BAUD = 9600;
// E22 레지스터: [ADDH ADDL NETID REG0 REG1 CH REG3 CRYPT_H CRYPT_L].
static constexpr uint8_t REG1_ADDR = 0x04;
static constexpr uint8_t REG3_ADDR = 0x06;
static constexpr uint8_t REG3_FIXED = 0x43;  // 고정전송 모드 (서버와 통일)
// REG1 bits7-6 = 서브패킷 크기(00=240B). 32B(11)로 남아 있으면 SET_FIELD 같은 긴 프레임이
// 전파에서 잘려 CRC가 깨진다 — 우리 프레임 최대 ~215B라 240B 필수. 서버 HAT도 동일해야 함.
static constexpr uint8_t REG1_SUBPKT_MASK = 0x3F;  // bits7-6 클리어 = 240B
// 송신 봉투: 서버(게이트웨이 HAT) 주소 0x0000, 채널 72(=922.125MHz, KR920).
static constexpr uint8_t ENV_ADDH = 0x00, ENV_ADDL = 0x00, ENV_CH = 0x48;

static constexpr uint8_t BATT_ADC_PIN = 34;  // 분압 미장착 시 값은 무의미 — MVP에선 무시

static GxEPD2_3C<GxEPD2_750c_Z08, GxEPD2_750c_Z08::HEIGHT / 2> epd(
    GxEPD2_750c_Z08(EPD_CS, EPD_DC, EPD_RST, EPD_BUSY));

namespace {

// HAT로의 송신: 고정전송 봉투 + COBS 프레임. 반이중 전환은 HAT 내부가 처리한다.
class HatRadioOut : public efb::IRadioOut {
public:
    bool send(const uint8_t* data, size_t len) override {
        uint8_t frame[efb::MAX_FRAME];
        const size_t n = efb::encode_frame(data, len, frame, sizeof(frame));
        if (n == 0) return false;
        const uint8_t env[3] = {ENV_ADDH, ENV_ADDL, ENV_CH};
        Serial2.write(env, sizeof(env));
        Serial2.write(frame, n);
        Serial2.flush();  // ACK 타이밍이 서버 T_ack 안에 들도록 즉시 밀어낸다
        Serial.printf("[tx] %uB 송신 (봉투 00 00 48 + 프레임 %uB)\n", (unsigned)len, (unsigned)n);
        return true;
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
        const uint32_t raw = analogReadMilliVolts(BATT_ADC_PIN);
        return static_cast<uint16_t>(raw * 2);  // 100k/100k 분압 가정 (미장착 시 무의미)
    }
};

// main.cpp 의 ProgmemFont 와 동일 — UART 변형에서도 같은 비트맵을 쓴다.
class ProgmemFont : public node::IGlyphSource {
public:
    bool glyph(uint32_t cp, uint8_t out[node::GLYPH_BYTES], uint8_t& advance_px) override {
        size_t index;
        if (cp >= 0x20 && cp <= 0x7E) {
            index = cp - 0x20;
            advance_px = 8;
        } else if (cp >= 0xAC00 && cp <= 0xD7A3) {
            index = 95 + (cp - 0xAC00);
            advance_px = 16;
        } else {
            return false;
        }
        const size_t off = index * node::GLYPH_BYTES;
        if (off + node::GLYPH_BYTES > EFB_HANGUL16_LEN) return false;
        for (size_t i = 0; i < node::GLYPH_BYTES; ++i) {
            out[i] = pgm_read_byte(EFB_HANGUL16 + off + i);
        }
        return true;
    }
};

// 3색 패널 전체 갱신은 ~18초(실측) — 서버 T_ack 안에 못 끝나므로 ACK는 렌더 전에 나간다
// (상태머신이 send_ack 후 commit 하는 순서라 자동으로 그렇게 된다).
class EpdDisplay : public node::IDisplay, public node::ICanvas {
public:
    void pixel(int16_t x, int16_t y) override { epd.drawPixel(x, y, GxEPD_BLACK); }

    void render(const node::DisplayState& s, uint8_t refresh_mode) override {
        const node::TemplateDef* tpl = node::find_template(s.template_id);
        if (!tpl) return;
        (void)refresh_mode;  // 3색 패널은 부분갱신 미지원 — 항상 전체
        epd.setFullWindow();
        epd.firstPage();
        do {
            epd.fillScreen(GxEPD_WHITE);
            for (uint8_t i = 0; i < tpl->field_count; ++i) {
                const node::FieldDef& f = tpl->fields[i];
                if (f.id >= node::MAX_FIELDS || !s.has_field[f.id]) continue;
                const uint8_t scale = node::scale_for(f.font_size);
                const int16_t avail = node::field_avail_w(f, tpl->qr, scale);
                node::draw_utf8(*this, font_, f.x, f.y, s.fields[f.id], scale, avail);
            }
            if (s.has_qr) draw_qr(s.qr_url, tpl->qr);
        } while (epd.nextPage());
    }

    // 부팅 확인용 화면 (HANDOFF §4) — 첫 COMMIT 전까지 노드 생존 여부를 눈으로 확인.
    void boot_screen(uint8_t node_id) {
        char msg[64];
        snprintf(msg, sizeof(msg), "노드 0x%02X — 수신 대기 중", node_id);
        epd.setFullWindow();
        epd.firstPage();
        do {
            epd.fillScreen(GxEPD_WHITE);
            node::draw_utf8(*this, font_, 24, 24, msg, 2, 800 - 24);
        } while (epd.nextPage());
    }

private:
    ProgmemFont font_;

    void draw_qr(const char* url, const node::QrDef& box) {
        const size_t len = strlen(url);
        uint8_t version = 3;
        if (len > 53) version = 5;
        if (len > 106) version = 8;
        if (len > 192) return;
        uint8_t buf[qrcode_getBufferSize(8)];
        QRCode qr;
        if (qrcode_initText(&qr, buf, version, ECC_LOW, url) != 0) return;
        const int16_t scale = box.size / qr.size;
        if (scale < 1) return;
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

HatRadioOut radio_out;
ArduinoClock clock_;
AdcBattery battery;
EpdDisplay display;
node::StateMachine sm(EFB_NODE_ID, radio_out, clock_, display, battery);
efb::FrameAccumulator acc;

// n바이트를 timeout_ms 안에 읽는다. 반환 = 실제 읽은 수.
size_t readN(uint8_t* out, size_t n, uint32_t timeout_ms) {
    size_t got = 0;
    const uint32_t t0 = millis();
    while (got < n && millis() - t0 < timeout_ms) {
        if (Serial2.available()) out[got++] = (uint8_t)Serial2.read();
    }
    return got;
}

// HAT를 설정모드(M0=L, M1=H)로 넣어 REG3가 고정전송(0x43)인지 확인·교정한다.
// 서버·노드 전부 고정 모드로 통일 (하나만 다르면 두절 — HANDOFF §8).
void configureHat() {
    digitalWrite(LORA_M0, LOW);
    digitalWrite(LORA_M1, HIGH);
    delay(150);
    while (Serial2.available()) Serial2.read();  // 부팅 중 끼어든 수신 프레임 배출

    const uint8_t readCmd[3] = {0xC1, 0x00, 0x09};
    Serial2.write(readCmd, sizeof(readCmd));
    uint8_t resp[12];
    const size_t n = readN(resp, sizeof(resp), 500);
    if (n == 12 && resp[0] == 0xC1) {
        Serial.printf("[HAT] 레지스터:");
        for (int i = 3; i < 12; ++i) Serial.printf(" %02X", resp[i]);
        Serial.println();
        const uint8_t reg1 = resp[3 + REG1_ADDR];
        const uint8_t reg3 = resp[3 + REG3_ADDR];
        const uint8_t want1 = reg1 & REG1_SUBPKT_MASK;  // 서브패킷 240B, 나머지 비트 보존
        if (reg1 != want1 || reg3 != REG3_FIXED) {
            // REG1(0x04)~REG3(0x06) 3개를 한 번에 쓴다 — 채널(0x05)은 읽은 값 그대로 보존.
            const uint8_t writeCmd[6] = {0xC0, REG1_ADDR, 0x03,
                                         want1, resp[3 + 0x05], REG3_FIXED};
            Serial2.write(writeCmd, sizeof(writeCmd));
            uint8_t wr[6];
            const size_t wn = readN(wr, sizeof(wr), 500);
            Serial.printf("[HAT] REG1 %02X→%02X, REG3 %02X→%02X %s\n", reg1, want1, reg3,
                          REG3_FIXED, (wn >= 1 && wr[0] == 0xC1) ? "완료" : "실패!");
        } else {
            Serial.println("[HAT] 설정 확인 — 고정전송·서브패킷240 일치");
        }
    } else {
        Serial.printf("[HAT] 설정 읽기 실패(n=%u) — 배선/M0M1 확인. 그래도 진행\n", (unsigned)n);
    }

    digitalWrite(LORA_M1, LOW);  // 일반 전송 모드 복귀
    delay(150);
    while (Serial2.available()) Serial2.read();
}

}  // namespace

void setup() {
    Serial.begin(115200);

    pinMode(LORA_M0, OUTPUT);
    digitalWrite(LORA_M0, LOW);
    pinMode(LORA_M1, OUTPUT);
    digitalWrite(LORA_M1, LOW);
    delay(50);
    Serial2.begin(LORA_BAUD, SERIAL_8N1, LORA_RX, LORA_TX);
    configureHat();

    // 드라이버보드는 패널 SPI가 13/14에 고정 — 기본 VSPI(18/23) 대신 명시해야 한다.
    SPI.begin(EPD_SCK, -1, EPD_MOSI, EPD_CS);
    epd.init(115200, /*initial=*/true, /*reset_duration=*/2, /*pulldown_rst_mode=*/false);
    epd.setRotation(0);  // 800x480 — 템플릿 좌표계와 동일
    display.boot_screen(EFB_NODE_ID);  // 3색 전체갱신 ~18초 — 부팅이 느려지지만 확인 가치가 큼

    Serial.printf("[node 0x%02X] ready (UART HAT, 고정전송+봉투)\n", EFB_NODE_ID);
}

void loop() {
    uint8_t chunk[64];
    size_t n = 0;
    while (Serial2.available() && n < sizeof(chunk)) {
        chunk[n++] = (uint8_t)Serial2.read();
    }
    if (n == 0) return;
    acc.feed(chunk, n);

    uint8_t pkt[efb::MAX_PACKET];
    size_t len;
    while ((len = acc.next(pkt, sizeof(pkt))) > 0) {
        Serial.printf("[rx] 패킷 %uB type=0x%02X seq=%u\n", (unsigned)len,
                      len > 3 ? pkt[3] : 0, len > 4 ? pkt[4] : 0);
        // HAT는 RSSI 바이트를 붙이지 않는 설정(REG3 bit7=0) — 실측치 없음, 0 전달.
        sm.on_radio_bytes(pkt, len, 0);  // COMMIT이면 이 안에서 e-Paper가 돈다 (블로킹 ~18초)
    }
}
