// LoRa 게이트웨이 (ESP32 + Waveshare Core1262).
//
// 이 파일만 Arduino/RadioLib 을 안다. 중계 로직은 lib/gw_core 에 하드웨어 의존 없이 있고
// 맥에서 테스트된다 (pio test -e native).

#include <Arduino.h>
#include <RadioLib.h>

#include <efb/packet.h>
#include <efb/ports.h>
#include <gw/relay.h>

// HARDWARE.md §3: NSS=5, DIO1=21, RST=4, BUSY=22 (SPI는 VSPI 공유 18/23/19)
static SX1262 radio = new Module(5, 21, 4, 22);

// PROTOCOL.md §1 (KR920)
static constexpr float FREQ_MHZ = 922.1f;
static constexpr float BW_KHZ = 125.0f;
static constexpr uint8_t SF = 9;
static constexpr uint8_t CR = 5;  // 4/5
static constexpr uint8_t SYNC_WORD = 0x12;
static constexpr int8_t TX_DBM = 14;  // TODO: KR920 법정 출력 한도 확정 (PROTOCOL.md §10)
static constexpr uint16_t PREAMBLE = 8;

static constexpr uint32_t SERIAL_BAUD = 921600;  // PROTOCOL.md §7

static volatile bool rx_flag = false;

static void IRAM_ATTR on_dio1() { rx_flag = true; }

namespace {

class SerialOut : public efb::ISerialOut {
public:
    void write(const uint8_t* data, size_t len) override { Serial.write(data, len); }
};

class RadioOut : public efb::IRadioOut {
public:
    bool send(const uint8_t* data, size_t len) override {
        const int state = radio.transmit(const_cast<uint8_t*>(data), len);
        radio.startReceive();  // 반이중 — 송신 후 수신으로 되돌린다
        return state == RADIOLIB_ERR_NONE;
    }
};

SerialOut serial_out;
RadioOut radio_out;
gw::Relay relay(serial_out, radio_out);

}  // namespace

void setup() {
    Serial.begin(SERIAL_BAUD);

    const int state = radio.begin(FREQ_MHZ, BW_KHZ, SF, CR, SYNC_WORD, TX_DBM, PREAMBLE);
    if (state != RADIOLIB_ERR_NONE) {
        while (true) {  // 라디오 없이는 할 수 있는 게 없다
            Serial.printf("radio.begin failed: %d\n", state);
            delay(2000);
        }
    }
    radio.setCRC(2);  // 하드웨어 CRC — 앱 CRC16과 이중 검증 (PROTOCOL.md §1)
    radio.setDio1Action(on_dio1);
    radio.startReceive();
}

void loop() {
    // 서버 -> LoRa
    while (Serial.available()) {
        uint8_t chunk[128];
        const size_t n = Serial.readBytes(chunk, min(Serial.available(), (int)sizeof(chunk)));
        relay.on_serial_bytes(chunk, n);
    }

    // LoRa -> 서버
    if (rx_flag) {
        rx_flag = false;
        uint8_t buf[efb::MAX_PACKET];
        const size_t len = radio.getPacketLength();
        if (len > 0 && len <= sizeof(buf) &&
            radio.readData(buf, len) == RADIOLIB_ERR_NONE) {
            relay.on_radio_bytes(buf, len);
        }
        radio.startReceive();
    }
}
