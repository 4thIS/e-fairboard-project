// e-Paper 노드 — UART LoRa HAT + 12.48"(1304x984, B/W 4패널) 변형.
//
// main_hat.cpp(7.5")에서 디스플레이 계층만 12.48로 교체한 것 (HANDOFF_12in48 §0/§3).
// LoRa·프로토콜·응답 로직은 무변경: Serial2 9600, 고정전송 봉투 [00 00 48], ACK/PONG.
// COMMIT은 렌더(~34초 실측) 뒤에 ACK 가 나간다 — 서버 T_ack 안에 못 들어와 첫 시도는
// 타임아웃, 재전송에서 성공한다(중복 갱신은 state_machine 의 멱등 키가 막는다).
// 그래서 배포는 노드당 ~38초씩 순차로 걸린다 — 노드를 늘리려면 ACK 를 렌더 앞으로
// 옮기거나 COMMIT 을 브로드캐스트해 렌더를 겹쳐야 한다(프로토콜 변경, 준표·우진 협의).
// 빌드: pio run -e hat1248_node1
//
// 디스플레이 드라이버는 GxEPD2가 아니라 Waveshare 공식 3색(B) V2(lib/epd12in48b) — 패널이 (B) V2로 판명(빨간 띠 실측). GxEPD2_1248의
// 초기화 시퀀스는 이 패널 개체에서 busy가 안 풀렸고(실측), 공식 드라이버는 4분면 무늬
// 테스트로 실제 렌더까지 검증됨(2026-08-19). 렌더는 사분면(648/656x492)별 40KB 버퍼에
// 4패스로 그려 스트리밍한다 — 전체 프레임버퍼(160KB)는 ESP32 힙에 안 잡힌다.
//
// 배선: docs 점퍼 22가닥 (1248_full_wiring.jpg) — LoRa 16/17/32/33 유지, 패널은
// 공식 데모 핀에서 LoRa와 겹치는 것만 이동(CS_M2 16→21, DC2 17→27, RST1 33→26,
// BUSY 4개→입력전용 34/35/36/39). 핀 정의는 lib/epd12in48/DEV_Config.h.

#include <Arduino.h>
#include <qrcode.h>

#include "DEV_Config.h"
#include "EPD_12in48b.h"

#include <efb/framing.h>
#include <efb/packet.h>
#include <efb/ports.h>
#include <node/layout.h>
#include <node/state_machine.h>
#include <node/templates.h>
#include <node/text.h>

// 40/56/72px 베이크 폰트 Bold (gen_font_data.py 생성 — main.cpp와 공유). 크기별 native
// 래스터라 확대 계단이 없다 — 폰트 렌더 V2 §A.
extern const uint8_t EFB_COMMON40[];
extern const size_t EFB_COMMON40_LEN;
extern const uint8_t EFB_COMMON56[];
extern const size_t EFB_COMMON56_LEN;
extern const uint8_t EFB_COMMON72[];
extern const size_t EFB_COMMON72_LEN;

#ifndef EFB_NODE_ID
#define EFB_NODE_ID 0x01
#endif

// ---- LoRa HAT (main_hat.cpp와 동일) ----
static constexpr uint8_t LORA_RX = 16, LORA_TX = 17;
static constexpr uint8_t LORA_M0 = 32, LORA_M1_PIN = 33;
static constexpr uint32_t LORA_BAUD = 9600;
static constexpr uint8_t REG1_ADDR = 0x04;
static constexpr uint8_t REG3_ADDR = 0x06;
static constexpr uint8_t REG3_FIXED = 0x43;
static constexpr uint8_t REG1_SUBPKT_MASK = 0x3F;
static constexpr uint8_t ENV_ADDH = 0x00, ENV_ADDL = 0x00, ENV_CH = 0x48;

// ---- 12.48" 패널 지오메트리 ----
static constexpr int16_t PANEL_W = 1304, PANEL_H = 984;
// 사분면: {패널좌표 x0, y0, 바이트폭} — 순서 M1(좌하) S1(우하) M2(우상) S2(좌상)
struct QuadDef { int16_t x0, y0; uint8_t bytes_w; };
static constexpr QuadDef QUADS[4] = {
    {0, 492, 81}, {648, 492, 82}, {648, 0, 82}, {0, 0, 81}};
static constexpr size_t QUAD_BUF_MAX = 82 * 492;

namespace {

class HatRadioOut : public efb::IRadioOut {
public:
    bool send(const uint8_t* data, size_t len) override {
        uint8_t frame[efb::MAX_FRAME];
        const size_t n = efb::encode_frame(data, len, frame, sizeof(frame));
        if (n == 0) return false;
        const uint8_t env[3] = {ENV_ADDH, ENV_ADDL, ENV_CH};
        Serial2.write(env, sizeof(env));
        Serial2.write(frame, n);
        Serial2.flush();
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
    uint16_t read_mv() override { return 0; }  // 임시 노드 — 배터리 미장착
};

// 크기별 bin 3개를 든 베이크 폰트 — setup 에서 add() 로 등록.
node::BakedFont g_font;

// 사분면 4패스 렌더러. pixel()은 논리좌표(템플릿)를 받아 현재 사분면에 들어오는 점만
// 버퍼에 찍는다. 가로 템플릿은 패널 원좌표 그대로(실물 확인 2026-08-19), 세로 템플릿
// (984x1304, 팀 소개)은 90° 회전해 물리 1304x984 로 눕힌다 — 안 하면 왼쪽 984폭에만
// 가로로 그려지는 버그 (실물 사진 2026-08-20, HANDOFF_FONT_RENDER_V2 §B).
class EpdDisplay : public node::IDisplay, public node::ICanvas {
public:
    // 두 플레인 다 1=안 칠함. Black/Red 는 해당 플레인만 0 으로, Paper 는 둘 다 1 로
    // 되돌려 종이를 드러낸다 — 빨강 밴드 위에 흰 글자를 얹는 방식(HANDOFF_NODE_LAYOUT_RED).
    void pixel(int16_t x, int16_t y, node::Ink ink) override {
        int16_t px = x;
        int16_t py = y;
        if (logical_h_ > logical_w_) {  // 세로 → CCW 회전 (방향은 패널 세우는 쪽 실물 확인)
            px = y;
            py = static_cast<int16_t>(logical_w_ - 1 - x);
        }
        const QuadDef& q = QUADS[quad_];
        const int16_t qx = px - q.x0;
        const int16_t qy = py - q.y0;
        if (qx < 0 || qy < 0 || qx >= (int16_t)q.bytes_w * 8 || qy >= 492) return;

        const size_t off = (size_t)qy * q.bytes_w + (qx >> 3);
        const uint8_t bit = 0x80 >> (qx & 7);
        switch (ink) {
            case node::Ink::Black:
                buf_k_[off] &= ~bit;
                buf_r_[off] |= bit;  // 같은 점에 빨강이 남아 있으면 색이 섞인다
                break;
            case node::Ink::Red:
                buf_r_[off] &= ~bit;
                buf_k_[off] |= bit;
                break;
            case node::Ink::Paper:
                buf_k_[off] |= bit;
                buf_r_[off] |= bit;
                break;
        }
    }

    void fill_rect(int16_t x, int16_t y, int16_t w, int16_t h, node::Ink ink) {
        for (int16_t dy = 0; dy < h; ++dy)
            for (int16_t dx = 0; dx < w; ++dx) pixel(x + dx, y + dy, ink);
    }

    // 테두리 = 얇은 채움 사각형 4개 (위·아래·좌·우). 모서리는 겹쳐도 무해하다.
    void stroke_rect(int16_t x, int16_t y, int16_t w, int16_t h, int16_t sw, node::Ink ink) {
        if (sw <= 0 || w <= 0 || h <= 0) return;
        if (sw * 2 >= w || sw * 2 >= h) {  // 테두리가 서로 만나면 그냥 꽉 채운다
            fill_rect(x, y, w, h, ink);
            return;
        }
        fill_rect(x, y, w, sw, ink);
        fill_rect(x, y + h - sw, w, sw, ink);
        fill_rect(x, y + sw, sw, h - 2 * sw, ink);
        fill_rect(x + w - sw, y + sw, sw, h - 2 * sw, ink);
    }

    // 그리는 순서: 장식 → 고정 라벨 → 필드 → QR. 장식이 먼저라 밴드 위에 글자가 얹힌다
    // (HANDOFF_NODE_LAYOUT_RED §2-④). 세로 회전은 pixel() 안에 있어 전부 그대로 통과한다.
    void render(const node::DisplayState& s, uint8_t refresh_mode) override {
        const node::TemplateDef* tpl = node::find_template(s.template_id);
        if (!tpl) return;
        (void)refresh_mode;  // 대형 패널은 전체 갱신만 (HANDOFF §3)
        logical_w_ = tpl->canvas_w;
        logical_h_ = tpl->canvas_h;
        draw_pass([&] {
            for (uint8_t i = 0; i < tpl->deco_count; ++i) {
                const node::Deco& d = tpl->decos[i];
                if (d.fill) fill_rect(d.x, d.y, d.w, d.h, deco_ink(d.fill));
                if (d.stroke) stroke_rect(d.x, d.y, d.w, d.h, d.stroke_w, deco_ink(d.stroke));
            }
            for (uint8_t i = 0; i < tpl->label_count; ++i) {
                const node::Label& l = tpl->labels[i];
                if (!l.text) continue;
                node::draw_utf8(*this, g_font, l.x, l.y, l.text, l.font_size,
                                tpl->canvas_w - l.x, field_ink(l.color));
            }
            for (uint8_t i = 0; i < tpl->field_count; ++i) {
                const node::FieldDef& f = tpl->fields[i];
                if (f.id >= node::MAX_FIELDS || !s.has_field[f.id]) continue;
                const int16_t avail = node::field_avail_w(f, tpl->qr, tpl->canvas_w);
                node::draw_utf8(*this, g_font, f.x, f.y, s.fields[f.id], f.font_size, avail,
                                field_ink(f.color));
            }
            if (s.has_qr) draw_qr(s.qr_url, tpl->qr);
        });
    }

    // 부팅 확인용. 빨강 밴드 위에 종이색 글자를 얹어 두 플레인이 다 살아있는지 눈으로 본다
    // — 배포 전에 빨강 채널 배선·반전 전송이 맞는지 확인할 유일한 화면이다.
    void boot_screen(uint8_t node_id) {
        char msg[64];
        snprintf(msg, sizeof(msg), "노드 0x%02X — 수신 대기 중 (12.48\")", node_id);
        logical_w_ = PANEL_W;
        logical_h_ = PANEL_H;
        draw_pass([&] {
            fill_rect(0, 0, PANEL_W, 120, node::Ink::Red);
            node::draw_utf8(*this, g_font, 24, 24, msg, 72, PANEL_W - 48, node::Ink::Paper);
        });
    }

private:
    // templates.h 의 색 코드 → 잉크. 글자·라벨은 0=검정 1=빨강 2=종이,
    // 장식 fill/stroke 는 0=none(호출 전에 걸러짐) 1=검정 2=빨강 — 값이 한 칸 밀려 있다.
    static node::Ink field_ink(uint8_t c) {
        return c == 1 ? node::Ink::Red : c == 2 ? node::Ink::Paper : node::Ink::Black;
    }
    static node::Ink deco_ink(uint8_t c) {
        return c == 2 ? node::Ink::Red : node::Ink::Black;
    }

    uint8_t* buf_k_ = nullptr;  // 검정 플레인 (0x10)
    uint8_t* buf_r_ = nullptr;  // 빨강 플레인 (0x13)
    int quad_ = 0;
    int16_t logical_w_ = PANEL_W, logical_h_ = PANEL_H;  // 현재 템플릿 캔버스 (회전 판정)

    // 사분면마다: 두 플레인 백지 → 콘텐츠 그리기 → 컨트롤러로 전송(0x10 검정, 0x13 빨강).
    // 마지막에 전체 갱신+슬립. 드라이버는 3색 (B) V2 — 흑백 드라이버는 회색 번짐(실측 폐기).
    template <typename DrawFn>
    void draw_pass(DrawFn draw) {
        static void (*const CMD1[4])() = {EPD_12in48B_cmd1M1, EPD_12in48B_cmd1S1,
                                          EPD_12in48B_cmd1M2, EPD_12in48B_cmd1S2};
        static void (*const DAT1[4])(UBYTE) = {EPD_12in48B_data1M1, EPD_12in48B_data1S1,
                                               EPD_12in48B_data1M2, EPD_12in48B_data1S2};
        static void (*const CMD2[4])() = {EPD_12in48B_cmd2M1, EPD_12in48B_cmd2S1,
                                          EPD_12in48B_cmd2M2, EPD_12in48B_cmd2S2};
        static void (*const DAT2[4])(UBYTE) = {EPD_12in48B_data2M1, EPD_12in48B_data2S1,
                                               EPD_12in48B_data2M2, EPD_12in48B_data2S2};
        if (!buf_k_) buf_k_ = (uint8_t*)malloc(QUAD_BUF_MAX);
        if (!buf_r_) buf_r_ = (uint8_t*)malloc(QUAD_BUF_MAX);
        if (!buf_k_ || !buf_r_) {
            Serial.printf("[epd] 버퍼 할당 실패! (사분면당 %uB x2, 여유 %u)\n",
                          (unsigned)QUAD_BUF_MAX, (unsigned)ESP.getFreeHeap());
            return;
        }
        EPD_12in48B_Init();  // 슬립에서 깨우기 (리셋+레지스터)
        const uint32_t t0 = millis();
        for (quad_ = 0; quad_ < 4; ++quad_) {
            memset(buf_k_, 0xff, QUAD_BUF_MAX);
            memset(buf_r_, 0xff, QUAD_BUF_MAX);
            draw();
            const size_t n = (size_t)QUADS[quad_].bytes_w * 492;
            CMD1[quad_]();  // 0x10 검정 채널: 1=흰 0=검
            for (size_t i = 0; i < n; ++i) DAT1[quad_](buf_k_[i]);
            // 0x13 빨강 채널 — data2 함수가 반전 전송(~data)하므로 1=빨강 없음 그대로 넘긴다
            CMD2[quad_]();
            for (size_t i = 0; i < n; ++i) DAT2[quad_](buf_r_[i]);
        }
        Serial.println("[epd] 데이터 전송 완료 — 갱신 시작 (~35초)");
        EPD_12in48B_TurnOnDisplay();
        EPD_12in48B_Sleep();
        Serial.printf("[epd] 렌더 완료 — %lums\n", (unsigned long)(millis() - t0));
    }

    void draw_qr(const char* url, const node::QrDef& box) {
        const size_t len = strlen(url);
        uint8_t version = 3;
        if (len > 53) version = 5;
        if (len > 106) version = 8;
        if (len > 192) return;
        uint8_t qbuf[qrcode_getBufferSize(8)];
        QRCode qr;
        if (qrcode_initText(&qr, qbuf, version, ECC_LOW, url) != 0) return;
        const int16_t scale = box.size / qr.size;
        if (scale < 1) return;
        const int16_t drawn = scale * qr.size;
        const int16_t ox = box.x + (box.size - drawn) / 2;
        const int16_t oy = box.y + (box.size - drawn) / 2;
        for (uint8_t y = 0; y < qr.size; ++y) {
            for (uint8_t x = 0; x < qr.size; ++x) {
                if (!qrcode_getModule(&qr, x, y)) continue;
                for (int16_t dy = 0; dy < scale; ++dy)
                    for (int16_t dx = 0; dx < scale; ++dx)
                        pixel(ox + x * scale + dx, oy + y * scale + dy, node::Ink::Black);
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

size_t readN(uint8_t* out, size_t n, uint32_t timeout_ms) {
    size_t got = 0;
    const uint32_t t0 = millis();
    while (got < n && millis() - t0 < timeout_ms) {
        if (Serial2.available()) out[got++] = (uint8_t)Serial2.read();
    }
    return got;
}

// HAT 설정 확인·교정 — 고정전송·서브패킷240·채널(공장값이 제각각 — 2호기 HAT은 0x12로 출하됨).
void configureHat() {
    digitalWrite(LORA_M0, LOW);
    digitalWrite(LORA_M1_PIN, HIGH);
    delay(150);
    while (Serial2.available()) Serial2.read();

    const uint8_t readCmd[3] = {0xC1, 0x00, 0x09};
    Serial2.write(readCmd, sizeof(readCmd));
    uint8_t resp[12];
    const size_t n = readN(resp, sizeof(resp), 500);
    if (n == 12 && resp[0] == 0xC1) {
        Serial.printf("[HAT] 레지스터:");
        for (int i = 3; i < 12; ++i) Serial.printf(" %02X", resp[i]);
        Serial.println();
        const uint8_t reg1 = resp[3 + REG1_ADDR];
        const uint8_t ch = resp[3 + 0x05];
        const uint8_t reg3 = resp[3 + REG3_ADDR];
        const uint8_t want1 = reg1 & REG1_SUBPKT_MASK;
        if (reg1 != want1 || ch != ENV_CH || reg3 != REG3_FIXED) {
            const uint8_t writeCmd[6] = {0xC0, REG1_ADDR, 0x03,
                                         want1, ENV_CH, REG3_FIXED};
            Serial2.write(writeCmd, sizeof(writeCmd));
            uint8_t wr[6];
            const size_t wn = readN(wr, sizeof(wr), 500);
            Serial.printf("[HAT] REG1 %02X→%02X, CH %02X→%02X, REG3 %02X→%02X %s\n", reg1, want1,
                          ch, ENV_CH, reg3, REG3_FIXED,
                          (wn >= 1 && wr[0] == 0xC1) ? "완료" : "실패!");
        } else {
            Serial.println("[HAT] 설정 확인 — 고정전송·서브패킷240·채널72 일치");
        }
    } else {
        Serial.printf("[HAT] 설정 읽기 실패(n=%u) — 배선/M0M1 확인. 그래도 진행\n", (unsigned)n);
    }

    digitalWrite(LORA_M1_PIN, LOW);
    delay(150);
    while (Serial2.available()) Serial2.read();
}

}  // namespace

void setup() {
    Serial.begin(115200);

    pinMode(LORA_M0, OUTPUT);
    digitalWrite(LORA_M0, LOW);
    pinMode(LORA_M1_PIN, OUTPUT);
    digitalWrite(LORA_M1_PIN, LOW);
    delay(50);
    Serial2.begin(LORA_BAUD, SERIAL_8N1, LORA_RX, LORA_TX);
    configureHat();

    if (!g_font.add(EFB_COMMON40, EFB_COMMON40_LEN) ||
        !g_font.add(EFB_COMMON56, EFB_COMMON56_LEN) ||
        !g_font.add(EFB_COMMON72, EFB_COMMON72_LEN)) {
        Serial.println("[font] 폰트 bin 헤더 불일치 — 텍스트는 그려지지 않는다");
    }

    DEV_ModuleInit();  // 패널 GPIO·소프트SPI 준비 (LoRa 핀과 무관)
    display.boot_screen(EFB_NODE_ID);  // 전체갱신 ~35초 — 부팅은 느리지만 생존 확인용

    Serial.printf("[node 0x%02X] ready (UART HAT + 12.48\", 고정전송+봉투)\n", EFB_NODE_ID);
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
        sm.on_radio_bytes(pkt, len, 0);  // COMMIT이면 이 안에서 렌더 (블로킹 ~35초)
    }
}
